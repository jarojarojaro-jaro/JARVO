"""Sesje omp jako rozmówcy panelu (docs/centrum §3.2, krok 1d): wpisy, skrzynka, blokada, dzierżawa, stan, ogon tury.

Sesję omp prowadzi tylko proces skrzynki (`jarvo sesja <klucz> skrzynka`, jarvo/sesje_omp.py) albo terminal
(`jarvo sesja <klucz> terminal`), nigdy dashboard. Dashboard kładzie wiadomość do skrzynki, czyta stan i ogon tury.
Moduł jest samodzielny (sama biblioteka standardowa): ładuje go wtyczka HQ (`_load`) i CLI Jarva (importlib po
ścieżce), więc obie strony mają jedną definicję wpisu, ścieżek i stanu.

Wpis w `<dane>/jarvo/konfig/sesje.json` (klucz = dopisek; rozmówcą jest tylko wpis z `panel.zaplecze = "omp"`):

    {"<klucz>": {"nazwa": "…", "skrzynka": "~/…/skrzynka", "czat": "-100…", "watek": "7",
                 "panel": {"zaplecze": "omp", "sesje": "~/…/sesje", "sesja": "<id sesji>", "cwd": "~/…",
                           "omp_arg": ["--no-context-files", "--append-system-prompt", "~/…/system.md"],
                           "opis": "…", "kolejnosc": 2, "potwierdzenia": false, "zamykaj_bezczynna_min": 30,
                           "pobierz_linki": ["/ścieżka/python", "/ścieżka/pobierz_link.py"]}}}

Układ skrzynki: `nowe/` (czeka), `zrobione/`, `bledy/`, `tura/<tura>.jsonl` (strumień tury), `sesja.lock` (flock:
skrzynka i terminal), `stan.json` (`tura {id, pid, start, klucze}`, `terminal {pid, od}`, `powiadomiono`).

Kontrakt dla panelu (CentrumUI; wszystko synchroniczne i szybkie, wołać w wątku albo `asyncio.to_thread`):

    wpisy(dane) -> dict[klucz, Wpis]          wpisy omp z sesje.json; zły wpis ma `blad` (np. „niebezpieczna ścieżka”)
    rozmowcy(dane) -> list[dict]              lista do lewej kolumny: klucz, nazwa, opis, kolejnosc, potwierdzenia
    stan(wpis) -> dict                        {stan: pracuje|terminal|kolejka|wolny|offline, czeka, najstarsza_s,
                                               tura, terminal_od, powod}; dzierżawa omp w pamięci 2 s (dla odznak)
    wyslij(wpis, tekst, klucz, media=(), lustro=True) -> dict
                                              {plik, nowy}; ten sam `klucz` = ten sam plik (idempotencja)
    przebieg(wpis, klucz) -> dict             {stan: kolejka|pracuje|gotowe|blad|brak, terminal, tura, odpowiedz, blad}
    ogon(wpis, tura, od=0) -> (zdarzenia, od) zdarzenia tury od bajtu `od`: {typ: delta, tekst} |
                                              {typ: narzedzie, nazwa, intencja} | {typ: koniec, ok, kod, odpowiedz}
    zatrzymaj(wpis) -> bool                   SIGTERM dla omp bieżącej tury (tylko proces z `--session-dir` wpisu)
    ponow(wpis, klucz) -> dict                ta sama wiadomość jeszcze raz do `nowe/` (nowy klucz `<klucz>-p<n>`)
    plik_sesji(wpis) -> Path | None           plik *.jsonl sesji (oś: czytnik_omp.os_sesji)

Wyników i argumentów narzędzi nie ma nigdzie: plik tury ma tylko tekst, nazwę i intencję narzędzia.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import fcntl
except ImportError:                              # Windows: sesje omp w etapie 1 tylko na POSIX
    fcntl = None

PLIK_KONFIGURACJI = "sesje.json"
STANY = ("pracuje", "terminal", "kolejka", "wolny", "offline")
KLUCZ_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SESJA_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{5,63}")
TURA_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")
DZIERZAWA_S = 2.0
_dzierzawy: dict[str, tuple[float, bool | None]] = {}


@dataclass
class Wpis:
    klucz: str
    nazwa: str
    skrzynka: Path | None = None
    sesje: Path | None = None
    sesja: str = ""
    cwd: Path | None = None
    omp_arg: list[str] = field(default_factory=list)
    czat: str = ""
    watek: str = ""
    opis: str = ""
    kolejnosc: int = 99
    potwierdzenia: bool = False
    zamykaj_bezczynna_min: float = 0
    pobierz_linki: list[str] = field(default_factory=list)
    blad: str = ""

    def __getattr__(self, nazwa):                 # katalogi skrzynki: w.nowe, w.zrobione, w.bledy, w.tura
        if nazwa in ("nowe", "zrobione", "bledy", "tura") and self.skrzynka is not None:
            return self.skrzynka / nazwa
        raise AttributeError(nazwa)

    @property
    def blokada(self) -> Path:
        return self.skrzynka / "sesja.lock"

    @property
    def plik_stanu(self) -> Path:
        return self.skrzynka / "stan.json"

    def katalogi(self) -> None:
        for k in (self.nowe, self.zrobione, self.bledy, self.tura):
            k.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- konfiguracja i ścieżki

def bezpieczna(surowa: str, dom: Path | None = None) -> Path | None:
    """Ścieżka z `~` pod domem użytkownika, bez dowiązań na zewnątrz, istniejąca część należy do użytkownika."""
    dom = (dom or Path.home()).resolve()
    p = Path(os.path.expanduser(str(surowa or "")))
    if not str(surowa or "").strip() or not p.is_absolute():
        return None
    try:
        r = p.resolve()
    except (OSError, RuntimeError):
        return None
    if r != dom and dom not in r.parents:
        return None
    if r.exists() and hasattr(os, "geteuid") and r.stat().st_uid != os.geteuid():
        return None
    return r


def _arg(a: str) -> str:
    return os.path.expanduser(a) if a.startswith("~/") else a


def wpis_z(klucz: str, surowy: dict, dom: Path | None = None) -> Wpis | None:
    """Wpis omp albo None (wpis bez `panel.zaplecze = omp`). Wpis z błędem dostaje `blad` i stan `offline`."""
    panel = surowy.get("panel") if isinstance(surowy, dict) else None
    if not isinstance(panel, dict) or panel.get("zaplecze") != "omp":
        return None
    w = Wpis(klucz=klucz, nazwa=str(surowy.get("nazwa") or klucz), opis=str(panel.get("opis") or ""),
             czat=str(surowy.get("czat") or ""), watek=str(surowy.get("watek") or ""),
             potwierdzenia=bool(panel.get("potwierdzenia")))
    try:
        w.kolejnosc = int(panel.get("kolejnosc", 99))
        w.zamykaj_bezczynna_min = float(panel.get("zamykaj_bezczynna_min") or 0)
    except (TypeError, ValueError):
        w.blad = "zły wpis"
    w.omp_arg = [_arg(str(a)) for a in panel.get("omp_arg") or [] if isinstance(a, (str, int, float))]
    w.pobierz_linki = [_arg(str(a)) for a in panel.get("pobierz_linki") or [] if isinstance(a, str)]
    w.sesja = str(panel.get("sesja") or "")
    if not KLUCZ_RE.fullmatch(klucz):
        w.blad = w.blad or "zły klucz"
    elif not SESJA_RE.fullmatch(w.sesja):
        w.blad = w.blad or "brak sesji"
    w.skrzynka = bezpieczna(surowy.get("skrzynka"), dom)
    w.sesje = bezpieczna(panel.get("sesje"), dom)
    w.cwd = Path(os.path.expanduser(str(panel.get("cwd") or "~")))
    if w.skrzynka is None or w.sesje is None:
        w.blad = w.blad or "niebezpieczna ścieżka"
    return w


def wpisy(dane: Path, dom: Path | None = None) -> dict[str, Wpis]:
    try:
        surowe = json.loads((Path(dane) / "jarvo" / "konfig" / PLIK_KONFIGURACJI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    wynik = {}
    for k, v in (surowe if isinstance(surowe, dict) else {}).items():
        w = wpis_z(str(k).strip().lower(), v, dom)
        if w is not None:
            wynik[w.klucz] = w
    return wynik


def rozmowcy(dane: Path, dom: Path | None = None) -> list[dict]:
    return [{"klucz": w.klucz, "nazwa": w.nazwa, "opis": w.opis, "kolejnosc": w.kolejnosc, "zaplecze": "omp",
             "potwierdzenia": w.potwierdzenia, "czat": w.czat, "watek": w.watek, "blad": w.blad}
            for w in sorted(wpisy(dane, dom).values(), key=lambda w: (w.kolejnosc, w.klucz))]


# ---------------------------------------------------------------- blokada, dzierżawa, stan

def program_omp() -> str | None:
    return os.environ.get("JARVO_OMP") or shutil.which("omp")


def blokada_zajeta(w: Wpis) -> bool:
    """Próbny flock (bez czekania): True, gdy trzyma go terminal albo tura skrzynki."""
    if fcntl is None or not w.blokada.exists():
        return False
    with w.blokada.open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
    return False


def dzierzawa(w: Wpis, *, pamiec: float = 0.0) -> bool | None:
    """`omp session lease --json -- <sesja>`: True, gdy sesję trzyma działający omp; None, gdy nie wiadomo."""
    teraz = time.monotonic()
    if pamiec and w.sesja in _dzierzawy and teraz - _dzierzawy[w.sesja][0] < pamiec:
        return _dzierzawy[w.sesja][1]
    omp = program_omp()
    wynik: bool | None = None
    if omp:
        try:
            r = subprocess.run([omp, "session", "lease", "--json", "--", w.sesja], capture_output=True, text=True,
                               timeout=15)
            held = json.loads(r.stdout or "{}").get("held") or [] if r.returncode == 0 else None
            wynik = None if held is None else any(str(h).startswith(w.sesja) or w.sesja.startswith(str(h))
                                                 for h in held if h)
        except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
            wynik = None
    _dzierzawy[w.sesja] = (teraz, wynik)
    return wynik


def czytaj_stan(w: Wpis) -> dict:
    try:
        s = json.loads(w.plik_stanu.read_text(encoding="utf-8"))
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def zapisz_stan(w: Wpis, **zmiany) -> dict:
    s = {**czytaj_stan(w), **zmiany}
    zapisz_atomowo(w.plik_stanu, s)
    return s


def zapisz_atomowo(plik: Path, dane: dict) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_name(f".{plik.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(plik)


def zyje(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def czekajace(w: Wpis) -> list[Path]:
    return sorted(w.nowe.glob("*.json")) if w.skrzynka is not None and w.nowe.is_dir() else []


def plik_sesji(w: Wpis) -> Path | None:
    if w.sesje is None or not w.sesja:
        return None
    pliki = sorted(w.sesje.glob(f"*_{w.sesja}*.jsonl")) or sorted(w.sesje.glob(f"*{w.sesja}*.jsonl"))
    return pliki[-1] if pliki else None


def stan(w: Wpis) -> dict:
    """Stan rozmówcy dla odznak (wołać co ~2 s; dzierżawa omp w pamięci 2 s)."""
    wynik = {"klucz": w.klucz, "stan": "offline", "czeka": 0, "najstarsza_s": 0, "tura": None, "terminal_od": None,
             "powod": w.blad or None}
    if w.blad:
        return wynik
    if fcntl is None:
        wynik["powod"] = "blokada plików tylko na Linuksie i macOS"
        return wynik
    if not program_omp():
        wynik["powod"] = "brak programu omp"
        return wynik
    nowe = czekajace(w)
    wynik["czeka"] = len(nowe)
    if nowe:
        try:
            wynik["najstarsza_s"] = round(time.time() - nowe[0].stat().st_mtime)
        except OSError:
            pass
    s = czytaj_stan(w)
    tura = s.get("tura") if isinstance(s.get("tura"), dict) else None
    if tura and zyje(tura.get("pid")):
        wynik.update(stan="pracuje", tura={k: tura.get(k) for k in ("id", "pid", "start", "klucze")})
        return wynik
    term = s.get("terminal") if isinstance(s.get("terminal"), dict) else None
    if blokada_zajeta(w) or dzierzawa(w, pamiec=DZIERZAWA_S):
        wynik["stan"] = "terminal"
        if term and zyje(term.get("pid")):
            wynik["terminal_od"] = term.get("od")
        return wynik
    wynik["stan"] = "kolejka" if nowe else "wolny"
    return wynik


# ---------------------------------------------------------------- skrzynka: wysyłka, przebieg, ogon

def _plik_klucza(klucz: str) -> str:
    if not KLUCZ_RE.fullmatch(klucz or ""):
        raise ValueError("zły klucz wiadomości")
    return f"panel-{klucz}.json"


def _znajdz(w: Wpis, nazwa: str) -> tuple[str, Path] | None:
    for gdzie in ("nowe", "zrobione", "bledy"):
        p = getattr(w, gdzie) / nazwa
        if p.exists():
            return gdzie, p
    return None


def wyslij(w: Wpis, tekst: str, klucz: str, media=(), lustro: bool = True) -> dict:
    """Wiadomość z panelu do `nowe/` (zapis atomowy). Ścieżki `media` (obrazy z inbox/) trafiają do pola `media`."""
    if w.blad or w.skrzynka is None:
        raise ValueError(w.blad or "wpis bez skrzynki")
    nazwa = _plik_klucza(klucz)
    w.katalogi()
    juz = _znajdz(w, nazwa)
    if juz:
        return {"plik": str(juz[1]), "nowy": False}
    plik = w.nowe / nazwa
    zapisz_atomowo(plik, {"dopisek": w.klucz, "nazwa": w.nazwa, "tekst": str(tekst or ""),
                          "media": [str(m) for m in media], "czas": time.strftime("%Y-%m-%d %H:%M:%S"),
                          "zrodlo": "panel", "klucz": klucz, "lustro": bool(lustro),
                          "chat_id": w.czat, "watek": w.watek, "odpowiedz_na": ""})
    return {"plik": str(plik), "nowy": True}


def przebieg(w: Wpis, klucz: str) -> dict:
    """Gdzie jest wiadomość panelu: kolejka (terminal: True, gdy sesję trzyma terminal), pracuje, gotowe, blad."""
    nazwa = _plik_klucza(klucz)
    wynik = {"stan": "brak", "terminal": False, "tura": None, "odpowiedz": None, "blad": None}
    if w.skrzynka is None:
        return wynik
    znal = _znajdz(w, nazwa)
    if not znal:
        return wynik
    gdzie, p = znal
    if gdzie == "nowe":
        s = stan(w)
        t = s.get("tura") or {}
        if s["stan"] == "pracuje" and klucz in (t.get("klucze") or []):
            return {**wynik, "stan": "pracuje", "tura": t.get("id")}
        return {**wynik, "stan": "kolejka", "terminal": s["stan"] == "terminal"}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if gdzie == "zrobione":
        return {**wynik, "stan": "gotowe", "tura": d.get("tura"), "odpowiedz": d.get("odpowiedz")}
    return {**wynik, "stan": "blad", "tura": d.get("tura"), "blad": str(d.get("blad") or "")[-300:]}


def ogon(w: Wpis, tura: str, od: int = 0) -> tuple[list[dict], int]:
    """Nowe zdarzenia z `tura/<tura>.jsonl` od bajtu `od` (tylko pełne linie); zwraca też nowy `od`."""
    if not TURA_RE.fullmatch(tura or "") or w.skrzynka is None:
        return [], od
    try:
        with (w.tura / f"{tura}.jsonl").open("rb") as f:
            f.seek(od)
            dane = f.read()
    except OSError:
        return [], od
    koniec = dane.rfind(b"\n") + 1
    zdarzenia = []
    for linia in dane[:koniec].splitlines():
        try:
            z = json.loads(linia)
        except ValueError:
            continue
        if isinstance(z, dict) and z.get("typ") in ("delta", "narzedzie", "koniec"):
            zdarzenia.append(z)
    return zdarzenia, od + koniec


def proces_tury(w: Wpis, pid) -> bool:
    """Czy `pid` to omp z `--session-dir` tego wpisu (Linux: /proc; inaczej `ps`)."""
    try:
        pid = int(pid)
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            argv = [a.decode(errors="replace") for a in argv if a]
        except OSError:
            r = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
            argv = r.stdout.split()
    except (ValueError, TypeError, OSError, subprocess.TimeoutExpired):
        return False
    tekst = " ".join(argv)
    return "omp" in tekst and str(w.sesje) in argv and "--session-dir" in argv


def zatrzymaj(w: Wpis) -> bool:
    tura = czytaj_stan(w).get("tura") or {}
    pid = tura.get("pid") if isinstance(tura, dict) else None
    if not pid or not zyje(pid) or not proces_tury(w, pid):
        return False
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError:
        return False
    return True


def ponow(w: Wpis, klucz: str) -> dict:
    """Ta sama wiadomość jeszcze raz (z `bledy/` albo `zrobione/`) jako nowa wiadomość w `nowe/`."""
    znal = _znajdz(w, _plik_klucza(klucz))
    if not znal:
        raise ValueError("nie ma takiej wiadomości")
    d = json.loads(znal[1].read_text(encoding="utf-8"))
    if znal[0] == "nowe":
        return {"plik": str(znal[1]), "nowy": False, "klucz": klucz}
    baza = re.sub(r"-p\d+$", "", klucz)
    n = 1
    while _znajdz(w, _plik_klucza(f"{baza}-p{n}")):
        n += 1
    nowy = f"{baza}-p{n}"
    r = wyslij(w, d.get("tekst") or "", nowy, d.get("media") or [], bool(d.get("lustro", True)))
    return {**r, "klucz": nowy}


def nowa_tura() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)

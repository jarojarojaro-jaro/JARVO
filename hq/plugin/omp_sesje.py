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
                           "pobierz_linki": ["/ścieżka/python", "/ścieżka/pobierz_link.py"],
                           "przed_tura": ["python3", "~/…/kernel.py", "system"]}}}

`przed_tura`: polecenie, które skrzynka uruchamia przed każdą turą (np. Kernel składa system.md z arsenałem floty);
gdy zmieni plik podany w `omp_arg` (np. `--append-system-prompt`), skrzynka między turami startuje nowy proces omp.

Układ skrzynki: `nowe/` (czeka), `zrobione/`, `bledy/`, `tura/<tura>.jsonl` (strumień tury), `sesja.lock` (flock:
skrzynka i terminal), `stan.json` (`tura {id, pid, start, klucze}`, `rpc {pid, skrzynka, od}` (proces `omp --mode rpc`
skrzynki), `terminal {pid, od}`, `powiadomiono`), `komendy/<klucz>.json` i `komendy/zrobione/` (komendy panelu, np.
/compact), `licznik.json` (zużycie sesji, skrzynka odświeża je w trakcie tury), `zatrzymaj` (prośba o abort tury),
`zwolnij` (terminal czeka na sesję: proces RPC kończy się po turze), `nowe/.budzik` (budzi usługę skrzynki: jednostka
systemd `.path` patrzy na `nowe/`).

Kontrakt dla panelu (CentrumUI; wszystko synchroniczne i szybkie, wołać w wątku albo `asyncio.to_thread`):

    wpisy(dane) -> dict[klucz, Wpis]          wpisy omp z sesje.json; zły wpis ma `blad` (np. „niebezpieczna ścieżka”)
    rozmowcy(dane) -> list[dict]              lista do lewej kolumny: klucz, nazwa, opis, kolejnosc, potwierdzenia
    stan(wpis) -> dict                        {stan: pracuje|terminal|kolejka|wolny|offline, czeka, najstarsza_s,
                                               tura, terminal_od, proces_od, powod}; dzierżawa omp w pamięci 2 s
    wyslij(wpis, tekst, klucz, media=(), lustro=True) -> dict
                                              {plik, nowy}; ten sam `klucz` = ten sam plik (idempotencja)
    dopisz(wpis, tekst, klucz, media=(), lustro=True) -> dict
                                              {plik, nowy, tryb: steer|kolejka}: w trakcie tury skrzynka wysyła ją do
                                              tury jako steer (jak Enter w terminalu omp), bez tury = zwykła wiadomość
    przebieg(wpis, klucz) -> dict             {stan: kolejka|pracuje|wlaczony|gotowe|blad|brak, terminal, tura,
                                              odpowiedz, blad}; `wlaczony` = dopisek doszedł do trwającej tury `tura`
    ogon(wpis, tura, od=0) -> (zdarzenia, od) zdarzenia tury od bajtu `od`: {typ: delta, tekst} |
                                              {typ: narzedzie, nazwa, intencja} | {typ: koniec, ok, kod, odpowiedz}
    zatrzymaj(wpis) -> bool                   abort bieżącej tury (prośba do skrzynki; bez skrzynki SIGTERM, tylko
                                              dla procesu omp z `--session-dir` wpisu)
    ponow(wpis, klucz) -> dict                ta sama wiadomość jeszcze raz do `nowe/` (nowy klucz `<klucz>-p<n>`)
    komendy_omp(wpis) -> list[dict]           komendy, które skrzynka wykonuje: [{nazwa, opis, aliasy}]
    komenda(wpis, nazwa, argumenty, klucz) -> dict
                                              {plik, nowy}: komenda do skrzynki (compact = compress); w trakcie tury
                                              czeka na jej koniec (compact w omp przerywa trwającą turę)
    wynik_komendy(wpis, klucz) -> dict        {stan: kolejka|pracuje|gotowe|blad|brak, wynik, blad}
    licznik(wpis) -> dict                     {model, kontekst, okno, procent, wejscie, wyjscie, cache_odczyt,
                                              cache_zapis, koszt, czas}: na żywo od skrzynki, bez niej z pliku sesji
    plik_sesji(wpis) -> Path | None           plik *.jsonl sesji (oś: czytnik_omp.os_sesji)
    model_skrzynki(wpis) -> str               model z `/model` w panelu (`<skrzynka>/model.json`), "" = z `omp_arg`
    ustaw_model_skrzynki(wpis, model|None)    zapis albo usunięcie wyboru; argumenty_tury(wpis) wstawia go do tury
    podsumowanie_sesji(wpis) -> dict          model ostatniej odpowiedzi i zużycie sesji (`/model`, `/usage`)

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
PLIK_LICZNIKA, PLIK_ZATRZYMAJ, PLIK_ZWOLNIJ, BUDZIK = "licznik.json", "zatrzymaj", "zwolnij", ".budzik"
# komendy panelu, które skrzynka wykonuje przez RPC omp (jarvo/sesje_omp.py): nazwa → (opis, aliasy)
KOMENDY = {"compact": ("Skompresuj kontekst sesji; po spacji możesz dodać, na czym się skupić", ("compress",))}
LICZNIK_PUSTY = {"model": "", "kontekst": 0, "okno": 0, "procent": 0.0, "wejscie": 0, "wyjscie": 0, "cache_odczyt": 0,
                 "cache_zapis": 0, "koszt": 0.0, "czas": None}
_podsumowania: dict[str, tuple[int, int, dict]] = {}


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
    przed_tura: list[str] = field(default_factory=list)
    blad: str = ""

    def __getattr__(self, nazwa):                 # katalogi skrzynki: w.nowe, w.zrobione, w.bledy, w.tura, w.komendy
        if nazwa in ("nowe", "zrobione", "bledy", "tura", "komendy") and self.skrzynka is not None:
            return self.skrzynka / nazwa
        raise AttributeError(nazwa)

    @property
    def blokada(self) -> Path:
        return self.skrzynka / "sesja.lock"

    @property
    def plik_stanu(self) -> Path:
        return self.skrzynka / "stan.json"

    def katalogi(self) -> None:
        for k in (self.nowe, self.zrobione, self.bledy, self.tura, self.komendy / "zrobione"):
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


_VENV_HASZ = re.compile(r"^(?P<venvs>.*[/\\]venvs)[/\\]narzedzia-[0-9a-f]{12}(?P<reszta>[/\\].*)$")


def _program_narzedzi(a: str) -> str:
    """Python venvu narzędzi wpisany ze skrótem wersji (`venvs/narzedzia-<12 hex>/bin/python`) po aktualizacji już nie
    istnieje: 20.11 pobieranie linków dla Kernela padło na `narzedzia-bcc37257827c` usuniętym przez sprzątanie.
    Brak pliku → stała ścieżka `venvs/narzedzia/…` (dowiązanie instalatora), a bez niej najnowszy `narzedzia-*`."""
    m = _VENV_HASZ.match(a)
    if not m or os.path.exists(a):
        return a
    venvs = Path(m.group("venvs"))
    stala = str(venvs / "narzedzia") + m.group("reszta")
    if os.path.exists(stala):
        return stala
    kandydaci = sorted(venvs.glob("narzedzia-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for k in kandydaci:
        if os.path.exists(str(k) + m.group("reszta")):
            return str(k) + m.group("reszta")
    return a


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
    w.pobierz_linki = [_program_narzedzi(_arg(str(a))) for a in panel.get("pobierz_linki") or [] if isinstance(a, str)]
    w.przed_tura = [_arg(str(a)) for a in panel.get("przed_tura") or [] if isinstance(a, str)]
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


# ---------------------------------------------------------------- model i zużycie (komendy panelu, komendy.py)
# `/model <wzorzec>` w panelu zapisuje wybór w `<skrzynka>/model.json` ({"model": "<dostawca/model>"}); tura skrzynki
# (jarvo/sesje_omp.py) bierze go zamiast `--model` z `omp_arg` wpisu. Terminal zostaje przy `omp_arg` (tam właściciel
# ma własne /model omp). `/model` i `/usage` czytają model i zużycie z pliku sesji (wiadomości asystenta).
PLIK_MODELU = "model.json"


def model_skrzynki(w: Wpis) -> str:
    if w.skrzynka is None:
        return ""
    try:
        d = json.loads((w.skrzynka / PLIK_MODELU).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(d.get("model") or "") if isinstance(d, dict) else ""


def ustaw_model_skrzynki(w: Wpis, model: str | None) -> None:
    if w.skrzynka is None:
        raise ValueError("wpis bez skrzynki")
    plik = w.skrzynka / PLIK_MODELU
    if model:
        zapisz_atomowo(plik, {"model": str(model)})
    else:
        plik.unlink(missing_ok=True)


def argumenty_tury(w: Wpis) -> list[str]:
    """`omp_arg` wpisu dla tury skrzynki: model z panelu zastępuje `--model` wpisu (omp przyjmuje flagę raz)."""
    model = model_skrzynki(w)
    if not model:
        return list(w.omp_arg)
    out, pomin = [], False
    for a in w.omp_arg:
        if pomin:
            pomin = False
        elif a == "--model":
            pomin = True
        elif not a.startswith("--model="):
            out.append(a)
    return out + ["--model", model]


def podsumowanie_sesji(w: Wpis) -> dict:
    """Model ostatniej odpowiedzi i zużycie całej sesji z pliku *.jsonl: {model, dostawca, odpowiedzi, wejscie,
    wyjscie, cache_odczyt, cache_zapis, koszt, kontekst}; brak pliku = zera i pusty model."""
    wynik = {"model": "", "dostawca": "", "odpowiedzi": 0, "wejscie": 0, "wyjscie": 0, "cache_odczyt": 0,
             "cache_zapis": 0, "koszt": 0.0, "kontekst": 0}
    plik = plik_sesji(w)
    if plik is None:
        return wynik
    try:
        st = plik.stat()
        juz = _podsumowania.get(str(plik))
        if juz and juz[:2] == (st.st_mtime_ns, st.st_size):  # panel pyta co 2 s (licznik), plik sesji bywa duży
            return dict(juz[2])
        linie = plik.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return wynik
    for linia in linie:
        try:
            e = json.loads(linia)
        except ValueError:
            continue
        m = e.get("message") if isinstance(e, dict) and e.get("type") == "message" else None
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        u = m.get("usage") if isinstance(m.get("usage"), dict) else {}
        wynik["odpowiedzi"] += 1
        wynik["wejscie"] += _liczba(u, "input")
        wynik["wyjscie"] += _liczba(u, "output")
        wynik["cache_odczyt"] += _liczba(u, "cacheRead")
        wynik["cache_zapis"] += _liczba(u, "cacheWrite")
        koszt = u.get("cost").get("total") if isinstance(u.get("cost"), dict) else None
        wynik["koszt"] += float(koszt) if isinstance(koszt, (int, float)) else 0.0
        kontekst = _liczba(u, "input") + _liczba(u, "cacheRead") + _liczba(u, "cacheWrite")
        wynik["kontekst"] = kontekst or wynik["kontekst"]   # odpowiedź z błędem dostawcy ma same zera
        wynik["model"], wynik["dostawca"] = str(m.get("model") or ""), str(m.get("provider") or "")
    _podsumowania[str(plik)] = (st.st_mtime_ns, st.st_size, dict(wynik))
    return wynik


def _liczba(u: dict, k: str) -> int:
    v = u.get(k)
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def proces_skrzynki(w: Wpis, s: dict | None = None) -> dict | None:
    """`rpc` ze stanu, gdy żyją i skrzynka, i jej proces `omp --mode rpc` (sesję trzyma skrzynka, nie terminal)."""
    r = (czytaj_stan(w) if s is None else s).get("rpc")
    if isinstance(r, dict) and zyje(r.get("skrzynka")) and zyje(r.get("pid")):
        return r
    return None


def stan(w: Wpis) -> dict:
    """Stan rozmówcy dla odznak (wołać co ~2 s; dzierżawa omp w pamięci 2 s). Sesja otwarta w procesie RPC skrzynki
    bez tury to `wolny` albo `kolejka` (wiadomość ruszy od razu), z `proces_od`."""
    wynik = {"klucz": w.klucz, "stan": "offline", "czeka": 0, "najstarsza_s": 0, "tura": None, "terminal_od": None,
             "proces_od": None, "powod": w.blad or None}
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
    rpc = proces_skrzynki(w, s)
    if rpc is not None:
        wynik["proces_od"] = rpc.get("od")
    term = s.get("terminal") if isinstance(s.get("terminal"), dict) else None
    if rpc is None and (blokada_zajeta(w) or dzierzawa(w, pamiec=DZIERZAWA_S)):
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


def wyslij(w: Wpis, tekst: str, klucz: str, media=(), lustro: bool = True, **dodatki) -> dict:
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
                          "chat_id": w.czat, "watek": w.watek, "odpowiedz_na": "", **dodatki})
    return {"plik": str(plik), "nowy": True}


def _tura_trwa(w: Wpis) -> bool:
    t = czytaj_stan(w).get("tura")
    return isinstance(t, dict) and zyje(t.get("pid"))


def dopisz(w: Wpis, tekst: str, klucz: str, media=(), lustro: bool = True) -> dict:
    """Wiadomość, którą skrzynka w trakcie tury wysyła do niej jako steer (`steer: true` w `nowe/`); bez tury zwykła
    wiadomość. `tryb` mówi, co było w chwili zapisu: tura mogła się skończyć tuż potem, wtedy wiadomość rusza jako
    własna tura i przebieg() pokaże kolejka, pracuje, gotowe zamiast wlaczony."""
    r = wyslij(w, tekst, klucz, media, lustro, steer=True)
    return {**r, "tryb": "steer" if _tura_trwa(w) else "kolejka"}


def przebieg(w: Wpis, klucz: str) -> dict:
    """Gdzie jest wiadomość panelu: kolejka (terminal: True, gdy sesję trzyma terminal), pracuje, wlaczony (dopisek
    doszedł do trwającej tury `tura`; jej odpowiedź jest odpowiedzią i na niego), gotowe, blad."""
    nazwa = _plik_klucza(klucz)
    wynik = {"stan": "brak", "terminal": False, "tura": None, "odpowiedz": None, "blad": None}
    if w.skrzynka is None:
        return wynik
    znal = _znajdz(w, nazwa)
    if not znal:
        return wynik
    gdzie, p = znal
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        d = d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        d = {}
    if d.get("wlaczony"):
        return {**wynik, "stan": "wlaczony", "tura": d["wlaczony"], "odpowiedz": d.get("odpowiedz")}
    if gdzie == "nowe":
        s = stan(w)
        t = s.get("tura") or {}
        if s["stan"] == "pracuje" and klucz in (t.get("klucze") or []):
            return {**wynik, "stan": "pracuje", "tura": t.get("id")}
        return {**wynik, "stan": "kolejka", "terminal": s["stan"] == "terminal"}
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
    """Stop bieżącej tury: przy żywej skrzynce prośba `zatrzymaj` (skrzynka wysyła RPC `abort`, a gdy omp nie
    odpowie, SIGTERM); bez skrzynki SIGTERM, tylko dla procesu omp z `--session-dir` wpisu."""
    s = czytaj_stan(w)
    tura = s.get("tura") or {}
    pid = tura.get("pid") if isinstance(tura, dict) else None
    if not pid or not zyje(pid) or not proces_tury(w, pid):
        return False
    if proces_skrzynki(w, s) is not None:
        (w.skrzynka / PLIK_ZATRZYMAJ).write_text(str(tura.get("id") or ""), encoding="utf-8")
        return True
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


# ---------------------------------------------------------------- komendy panelu i licznik (skrzynka RPC)

def obudz(w: Wpis) -> None:
    """Plik w `nowe/` bez `.json`: jednostka `.path` uruchamia skrzynkę, a nikt nie bierze go za wiadomość."""
    (w.nowe / BUDZIK).write_text(str(time.time()), encoding="utf-8")


def komendy_omp(w: Wpis) -> list[dict]:
    if w.blad:
        return []
    return [{"nazwa": n, "opis": o, "aliasy": list(a)} for n, (o, a) in KOMENDY.items()]


def nazwa_komendy(nazwa: str) -> str:
    n = str(nazwa or "").strip().lstrip("/").lower()
    for k, (_opis, aliasy) in KOMENDY.items():
        if n == k or n in aliasy:
            return k
    raise ValueError("nieznana komenda")


def komenda(w: Wpis, nazwa: str, argumenty, klucz: str) -> dict:
    """Komenda do `komendy/<klucz>.json` (ten sam klucz = ten sam plik) i budzik skrzynki; wykonuje ją skrzynka
    przez RPC omp, także gdy procesu nie ma (uruchamia go). W trakcie tury czeka na jej koniec."""
    if w.blad or w.skrzynka is None:
        raise ValueError(w.blad or "wpis bez skrzynki")
    n = nazwa_komendy(nazwa)
    if not KLUCZ_RE.fullmatch(klucz or ""):
        raise ValueError("zły klucz komendy")
    w.katalogi()
    for p in (w.komendy / f"{klucz}.json", w.komendy / "zrobione" / f"{klucz}.json"):
        if p.exists():
            return {"plik": str(p), "nowy": False}
    arg = " ".join(map(str, argumenty)) if isinstance(argumenty, (list, tuple)) else str(argumenty or "")
    plik = w.komendy / f"{klucz}.json"
    zapisz_atomowo(plik, {"nazwa": n, "argumenty": arg.strip()[:4000], "klucz": klucz, "stan": "kolejka",
                          "czas": time.strftime("%Y-%m-%d %H:%M:%S")})
    obudz(w)
    return {"plik": str(plik), "nowy": True}


def komendy_czekajace(w: Wpis) -> list[Path]:
    return sorted(w.komendy.glob("*.json")) if w.skrzynka is not None and w.komendy.is_dir() else []


def wynik_komendy(w: Wpis, klucz: str) -> dict:
    """{stan: kolejka|pracuje|gotowe|blad|brak, wynik, blad}."""
    if not KLUCZ_RE.fullmatch(klucz or ""):
        raise ValueError("zły klucz komendy")
    wynik = {"stan": "brak", "wynik": "", "blad": None}
    if w.skrzynka is None:
        return wynik
    for p, gotowa in ((w.komendy / "zrobione" / f"{klucz}.json", True), (w.komendy / f"{klucz}.json", False)):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d = d if isinstance(d, dict) else {}
        except OSError:
            continue
        except ValueError:
            d = {}
        if gotowa:
            return {"stan": "blad" if d.get("blad") else "gotowe", "wynik": str(d.get("wynik") or ""),
                    "blad": str(d["blad"]) if d.get("blad") else None}
        return {**wynik, "stan": "pracuje" if d.get("stan") == "pracuje" else "kolejka"}
    return wynik


def licznik(w: Wpis) -> dict:
    """Zużycie sesji dla panelu: `licznik.json` skrzynki (get_session_stats RPC, odświeżany po każdej odpowiedzi
    modelu), gdy proces RPC żyje albo plik sesji nie jest od niego nowszy; inaczej z pliku sesji (okno kontekstu
    tylko, gdy skrzynka znała je dla tego samego modelu). Nic nie wiadomo = zera; nigdy wyjątek."""
    wynik = dict(LICZNIK_PUSTY)
    try:
        if w.blad or w.skrzynka is None:
            return wynik
        plik = w.skrzynka / PLIK_LICZNIKA
        try:
            zapis = json.loads(plik.read_text(encoding="utf-8"))
            zapis = {k: zapis[k] for k in LICZNIK_PUSTY if k in zapis} if isinstance(zapis, dict) else {}
            t_zapisu = plik.stat().st_mtime
        except (OSError, ValueError):
            zapis, t_zapisu = {}, 0.0
        sesja = plik_sesji(w)
        t_sesji = sesja.stat().st_mtime if sesja is not None else 0.0
        if zapis and (proces_skrzynki(w) is not None or t_sesji <= t_zapisu + 5):
            return {**wynik, **zapis}
        if sesja is None:
            return wynik
        p = podsumowanie_sesji(w)
        model = f"{p['dostawca']}/{p['model']}" if p["dostawca"] and p["model"] else p["model"]
        okno = int(zapis.get("okno") or 0) if zapis.get("model") == model else 0
        wynik.update(model=model, kontekst=p["kontekst"], okno=okno, wejscie=p["wejscie"], wyjscie=p["wyjscie"],
                     cache_odczyt=p["cache_odczyt"], cache_zapis=p["cache_zapis"], koszt=round(p["koszt"], 6),
                     procent=round(p["kontekst"] * 100 / okno, 1) if okno else 0.0, czas=t_sesji)
        return wynik
    except Exception:                               # licznik to dodatek: nigdy nie psuje panelu
        return dict(LICZNIK_PUSTY)

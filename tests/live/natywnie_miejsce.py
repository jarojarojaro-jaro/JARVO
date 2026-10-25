#!/usr/bin/env python3
"""Miejsce na dysku instalacji natywnej, na żywo (docs/NATYWNIE.md: c3 pkt 11, Z31; obszar instalator-miejsce).

    python -X utf8 -B tests/live/natywnie_miejsce.py sprawdz [--korzen R] [--wyniki KATALOG] [--max-gb N]
    python -X utf8 -B tests/live/natywnie_miejsce.py bez-sieci [--korzen R] [--wyniki KATALOG] [-- ARGUMENTY]
    python -X utf8 -B tests/live/natywnie_miejsce.py odmowa [--korzen NOWY] [--wyniki KATALOG] [--wolne-gb N]

Działa na zainstalowanym korzeniu (--korzen, JARVO_ROOT albo domyślny katalog systemu), samą biblioteką standardową,
z pakietem jarvo/ tego repo (układ katalogów, szacunek z manifestu, zajęte miejsce).

sprawdz (tylko odczyt, po udanej instalacji):
  1. sprzątanie: w <cache>/pobrane nie ma plików, cache uv i pixi mają poniżej 1 MB (albo ich nie ma), w checkoucie
     Hermesa nie ma node_modules (korzeń i web/), a źródła skilli w <cache>/build zostały (aktualizacja buduje flotę),
  2. znaczniki gotowych części: narzędzia (.jarvo-suma), venvy, modele, Tesseract, Hermes i front; bez nich drugi
     przebieg sięgnąłby do sieci po to, czego po sprzątaniu nie ma już w cache,
  3. Tesseract po usunięciu cache pixi: `--list-langs` z pol i eng,
  4. zajęte miejsce (instalator.zajete_miejsce) wobec szacunku z manifestu tej wersji (potrzebne_miejsce, całość):
     „zostaje” nie może być mniejsze od zajętego o więcej niż 25 %, a szczyt z zapasem nie mniejszy niż zajęte
     + to, co zwolniło sprzątanie (ostatni wiersz „Sprzątanie” z <logi>/instalacja.log): tuż przed sprzątaniem
     jedno i drugie było na dysku naraz, więc to dolna granica prawdziwego szczytu; z --max-gb także górna granica
     zajętego,
  5. `jarvo doctor --json`: wynik „wolne miejsce” podaje zajęte i wolne miejsce.
bez-sieci: kolejny przebieg polecenia instalacji (`jarvo instaluj` tej instalacji z ARGUMENTAMI po `--`, np.
  --bez-autostartu --bez-path) z HTTPS_PROXY na martwy port 127.0.0.1, więc każde pobranie kończy się błędem: kod 0,
  „Zmiany w tym przebiegu: brak.”, bez „pobieram”, bez błędów i bez wiersza „Sprzątanie”, a <program> i <cache> bez
  zmian (nazwy i rozmiary plików przed i po; bez kodu bajtowego, który Python zapisuje sam przy imporcie).
odmowa: instalacja w nowym katalogu (--korzen, domyślnie <wyniki>/odmowa-korzen), gdy na jego dysku jest --wolne-gb
  (domyślnie 1; 0 = prawdziwe wolne miejsce): kod 1 jeszcze w kroku „Sprawdzenie komputera”, komunikat z potrzebą
  i poleceniem z JARVO_ROOT, a katalog nie powstał. Instalator rusza tylko wtedy, gdy bilans z tym samym otoczeniem
  już mówi „za mało” (inaczej punkt jest pominięty), więc ten tryb niczego nie instaluje.
Raport JSON w <wyniki>/miejsce.json (dopisuje punkty kolejnych trybów) i na stdout; kod 0 = wszystkie punkty przeszły.

W CI (.github/workflows/natywnie.yml) po teście na żywo: `sprawdz`, po drugim przebiegu: `bez-sieci -- <flagi
instalacji>`, na końcu przed odinstalowaniem: `odmowa`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from jarvo import instalator, sciezki, srodowisko  # noqa: E402
from jarvo import tesseract as jtesseract  # noqa: E402

MB, GB = instalator.MB, instalator.GB
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ZMIANY_BRAK = "Zmiany w tym przebiegu: brak."
ZNACZNIKI = {"venv-": ".jarvo-venv.json", "model-": ".jarvo-model.json"}


class Raport:
    def __init__(self, wyniki: Path, tryb: str):
        self.plik = wyniki / "miejsce.json"
        wyniki.mkdir(parents=True, exist_ok=True)
        try:
            self.dane = json.loads(self.plik.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.dane = {"punkty": []}
        self.tryb = tryb
        self.dane.setdefault("punkty", [])
        self.od = len(self.dane["punkty"])          # kod wyjścia liczy tylko punkty tego uruchomienia

    def punkt(self, nazwa: str, ok: bool | None, opis: str) -> None:
        """ok None = pominięty (z powodem), nie liczy się jako błąd."""
        self.dane["punkty"].append({"tryb": self.tryb, "nazwa": nazwa, "ok": ok, "opis": opis,
                                    "czas": time.strftime("%Y-%m-%dT%H:%M:%S")})
        znak = {True: "[ok]   ", False: "[błąd] ", None: "[pomin]"}[ok]
        print(f"{znak} {self.tryb}: {nazwa}: {opis}", flush=True)

    def zapisz(self, **pola) -> int:
        self.dane.update(pola)
        self.plik.write_text(json.dumps(self.dane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bledy = [p for p in self.dane["punkty"][self.od:] if p["ok"] is False]
        print(json.dumps({"tryb": self.tryb, "bledy": len(bledy), "raport": str(self.plik)}, ensure_ascii=False))
        return 1 if bledy else 0


def uklad(korzen: str | None) -> sciezki.Uklad:
    env = dict(os.environ)
    if korzen:
        env["JARVO_ROOT"] = korzen
    return instalator.bezwzgledny(sciezki.uklad(env))


def _pliki(katalog: Path) -> list[Path]:
    return sorted(p for p in katalog.rglob("*") if p.is_file()) if katalog.is_dir() else []


def _log_instalacji(u: sciezki.Uklad) -> str:
    try:
        return (u.logi / "instalacja.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _zwolnione_w_logu(tekst: str) -> tuple[int, int]:
    """(ostatnie „Sprzątanie: zwolnione X GB”, suma ostatnich „usunięte …node_modules (N MB)”) w bajtach."""
    sprzatanie = re.findall(r"Sprzątanie: zwolnione ([\d,]+) GB", tekst)
    node = re.findall(r"Hermes: usunięte (?:web/)?node_modules \((\d+) MB\)", tekst)
    return (int(float(sprzatanie[-1].replace(",", ".")) * GB) if sprzatanie else 0,
            sum(int(x) for x in node[-2:]) * MB)


# ------------------------------------------------------------------------------------------------ sprawdz

def tryb_sprawdz(a) -> int:
    u = uklad(a.korzen)
    rap = Raport(Path(a.wyniki), "sprawdz")
    biez = srodowisko.biezace(u)
    if not biez:
        rap.punkt("instalacja", False, f"brak {u.program / 'current.json'}: Jarvo nie jest zainstalowane w {u.root}")
        return rap.zapisz(korzen=str(u.root))
    # 1. sprzątanie
    pobrane = _pliki(u.cache / "pobrane")
    rap.punkt("archiwa narzędzi usunięte", not pobrane,
              "w <cache>/pobrane pusto" if not pobrane else "zostały: " + ", ".join(p.name for p in pobrane[:5]))
    for nazwa, kat in (("cache uv", u.cache / "uv"), ("cache pixi", u.cache / "pixi")):
        b = instalator.rozmiar_katalogu(kat)
        rap.punkt(f"{nazwa} wyczyszczony", b < instalator.PROG_SPRZATANIA, f"{kat}: {b / MB:.1f} MB")
    checkout = Path(str(biez.get("hermes") or ""))
    nm = [k for k in (checkout / "node_modules", checkout / "web" / "node_modules") if k.exists()]
    rap.punkt("node_modules frontu usunięte", bool(checkout.name) and not nm,
              f"{checkout}: " + ("bez node_modules" if not nm else "zostały " + ", ".join(map(str, nm))))
    if (u.dane / "profiles").is_dir():
        zrodla = sorted((u.cache / "build").glob("*@*"))
        bajty = sum(instalator.rozmiar_katalogu(z) for z in zrodla)
        rap.punkt("źródła skilli zostały", bool(zrodla),
                  f"{len(zrodla)} źródeł w {u.cache / 'build'} ({instalator.gb(bajty)} GB)")
    # 2. znaczniki gotowych części
    braki = []
    for nazwa, wpis in srodowisko.narzedzia(u).items():
        kat = Path(str((wpis or {}).get("katalog") or ""))
        if nazwa == "tesseract":
            znacznik = kat / jtesseract.ZNACZNIK
        else:
            znacznik = kat / next((z for p, z in ZNACZNIKI.items() if nazwa.startswith(p)), ".jarvo-suma")
        if not znacznik.is_file():
            braki.append(f"{nazwa} ({znacznik})")
    for z in (".jarvo-hermes.json", ".jarvo-web-dist.json"):
        if not (checkout / z).is_file():
            braki.append(f"Hermes ({checkout / z})")
    rap.punkt("znaczniki gotowych części", not braki, "wszystkie są" if not braki else "brak: " + "; ".join(braki[:6]))
    # 3. Tesseract bez cache pixi
    tess = srodowisko.narzedzia(u).get("tesseract") or {}
    if tess.get("program"):
        ok, opis = jtesseract.sprawdz(Path(tess["program"]), Path((tess.get("env") or {}).get("TESSDATA_PREFIX", "")))
        rap.punkt("Tesseract działa po usunięciu cache pixi", ok, f"--list-langs: {opis}")
    else:
        rap.punkt("Tesseract działa po usunięciu cache pixi", None, "ta instalacja nie ma Tesseracta")
    # 4. zajęte miejsce wobec szacunku z manifestu
    zajete = instalator.zajete_miejsce(u)
    razem = sum(zajete.values())
    app = instalator.katalog_aplikacji(u)
    potrzeby = instalator.potrzebne_miejsce(u, app, sciezki.platforma(), wszystko=True)   # jak na pustym dysku
    szczyt = int(sum(p.szczyt for p in potrzeby) * (1 + instalator.ZAPAS)) + instalator.ZAPAS_MB * MB
    zostaje = sum(p.zostaje for p in potrzeby)
    sprzatanie, node = _zwolnione_w_logu(_log_instalacji(u))
    dolna = razem + sprzatanie            # tuż przed sprzątaniem było na dysku jedno i drugie naraz
    rap.punkt("szacunek „zostaje” nie zaniża zajętego", zostaje >= razem * 0.75,
              f"zajęte {instalator.opis_zajetego(zajete)}, szacunek po sprzątaniu {instalator.gb(zostaje)} GB "
              f"({zostaje / max(razem, 1):.2f} zajętego)")
    rap.punkt("szczyt z zapasem obejmuje dolną granicę prawdziwego szczytu", szczyt >= dolna,
              f"szacunek {instalator.gb(szczyt)} GB, dolna granica {instalator.gb(dolna)} GB (zajęte "
              f"{instalator.gb(razem)} + sprzątanie {instalator.gb(sprzatanie)}; node_modules "
              f"{instalator.gb(node)} GB zniknęło wcześniej, zaraz po budowie frontu)")
    if a.max_gb:
        rap.punkt(f"Jarvo zajmuje najwyżej {a.max_gb} GB", razem <= a.max_gb * GB, f"zajęte {instalator.gb(razem)} GB")
    # 5. doctor
    argv = instalator.polecenie_jarva(u, "doctor", "--json")
    try:
        w = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                           creationflags=NO_WINDOW)
        d = json.loads(w.stdout)
        miejsce = next((x for x in d.get("wyniki", []) if x.get("nazwa") == "wolne miejsce"), {})
        ok = "Jarvo zajmuje" in str(miejsce.get("opis")) and "wolne" in str(miejsce.get("opis"))
        rap.punkt("doctor pokazuje zajęte i wolne miejsce", ok,
                  f"[{miejsce.get('stan')}] {miejsce.get('opis')}" if miejsce else "brak wyniku „wolne miejsce”")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        rap.punkt("doctor pokazuje zajęte i wolne miejsce", False, f"{type(e).__name__}: {str(e)[:200]}")
    return rap.zapisz(korzen=str(u.root), zajete=zajete, szacunek={"szczyt": szczyt, "zostaje": zostaje,
                                                                     "czesci": {p.opis: [p.szczyt, p.zostaje]
                                                                                for p in potrzeby}})


# ------------------------------------------------------------------------------------------------ bez-sieci

def _migawka(u: sciezki.Uklad) -> dict[str, int]:
    """{ścieżka względna: rozmiar} plików <program> i <cache>, bez kodu bajtowego (__pycache__, .pyc): ten zapisuje
    sam Python przy imporcie, także działający serwis, a nie instalator."""
    wynik = {}
    for kat in (u.program, u.cache):
        for p in _pliki(kat):
            if p.suffix == ".pyc" or "__pycache__" in p.parts:
                continue
            try:
                wynik[str(p.relative_to(u.root) if instalator._w_korzeniu(p, u.root) else p)] = p.stat().st_size
            except OSError:
                continue
    return wynik


def _martwy_port() -> int:
    """Port 127.0.0.1, na którym nikt nie słucha (od systemu, gniazdo od razu zamknięte)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tryb_bez_sieci(a) -> int:
    u = uklad(a.korzen)
    wyniki = Path(a.wyniki)
    rap = Raport(wyniki, "bez-sieci")
    if not srodowisko.biezace(u):
        rap.punkt("instalacja", False, f"Jarvo nie jest zainstalowane w {u.root}")
        return rap.zapisz(korzen=str(u.root))
    przed = _migawka(u)
    proxy = f"http://127.0.0.1:{_martwy_port()}"
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                                                                    "NO_PROXY")}
    env.update({"HTTPS_PROXY": proxy, "https_proxy": proxy, "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost", "PYTHONUTF8": "1"})
    argv = instalator.polecenie_jarva(u, "instaluj", *a.argumenty, env=env)
    t0 = time.monotonic()
    try:
        w = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                           timeout=3600, creationflags=NO_WINDOW)
        kod, tekst = w.returncode, f"{w.stdout}\n{w.stderr}"
    except (OSError, subprocess.SubprocessError) as e:
        kod, tekst = -1, f"{type(e).__name__}: {e}"
    czas = time.monotonic() - t0
    (wyniki / "bez-sieci.log").write_text(tekst, encoding="utf-8")
    linie = [x.strip() for x in tekst.splitlines()]
    rap.punkt("instalacja bez sieci kończy się kodem 0", kod == 0, f"kod {kod} po {czas:.0f} s (proxy {proxy})")
    rap.punkt("drugi przebieg niczego nie zmienia", ZMIANY_BRAK in tekst,
              next((x for x in reversed(linie) if "Zmiany w tym przebiegu" in x), "brak wiersza „Zmiany…”"))
    pobrane = [x for x in linie if re.search(r"\bpobieram\b", x, re.I)]
    bledy = [x for x in linie if re.search(r"\bBŁĄD\b", x)]
    rap.punkt("nic nie pobrane i bez błędów", not pobrane and not bledy, "; ".join((pobrane + bledy)[:4]) or "tak")
    sprzatanie = [x for x in linie if x.startswith("Sprzątanie:")]
    rap.punkt("nic do sprzątania", not sprzatanie, sprzatanie[0] if sprzatanie else "brak wiersza „Sprzątanie”")
    po = _migawka(u)
    roznica = sorted(set(przed.items()) ^ set(po.items()))
    rap.punkt("<program> i <cache> bez zmian", not roznica,
              f"{len(przed)} plików" if not roznica else "zmienione: " + ", ".join(k for k, _v in roznica[:6]))
    miejsce = next((x for x in linie if x.startswith("Miejsce:")), "")
    return rap.zapisz(korzen=str(u.root), miejsce_po_przebiegu=miejsce)


# ------------------------------------------------------------------------------------------------ odmowa

def tryb_odmowa(a) -> int:
    wyniki = Path(a.wyniki)
    rap = Raport(wyniki, "odmowa")
    korzen = Path(os.path.abspath(a.korzen or str(wyniki / "odmowa-korzen")))
    if korzen.exists():
        rap.punkt("nowy katalog", False, f"{korzen} już istnieje: odmowę sprawdzamy na nowym katalogu")
        return rap.zapisz(korzen=str(korzen))
    u = instalator.bezwzgledny(sciezki.uklad({**os.environ, "JARVO_ROOT": str(korzen)}))
    dysk_korzenia = instalator.dysk(u.root)

    def wolne(p) -> int:
        if a.wolne_gb and instalator.dysk(p) == dysk_korzenia:
            return int(a.wolne_gb * GB)
        return instalator.wolne_miejsce(p)
    ot = instalator.Otoczenie(wolne_miejsce=wolne)
    platforma = sciezki.platforma()
    bilans = instalator.bilans_dyskow(u, instalator.potrzebne_miejsce(u, REPO, platforma), ot)
    if not [b for b in bilans if b["wolne"] is not None and b["wolne"] < b["potrzeba"]]:
        rap.punkt("odmowa przy braku miejsca", None, f"na dysku {bilans[0]['punkt']} jest dość miejsca "
                  f"({instalator.gb(bilans[0]['wolne'] or 0)} GB): instalatora nie uruchamiam")
        return rap.zapisz(korzen=str(korzen))
    log: list[str] = []
    kod = instalator.instaluj(u, REPO, autostart=False, start=False, bez_path=True, log=log.append, otoczenie=ot,
                              platforma=platforma)
    tekst = "\n".join(log)
    (wyniki / "odmowa.log").write_text(tekst + "\n", encoding="utf-8")
    rap.punkt("kod 1 w kroku „Sprawdzenie komputera”", kod == 1 and "BŁĄD w kroku „Sprawdzenie komputera”" in tekst,
              f"kod {kod}")
    rap.punkt("komunikat z potrzebą i poleceniem", "potrzebuje na nim ok." in tekst and "JARVO_ROOT" in tekst
              and "Niczego nie zainstalowałem." in tekst,
              next((x for x in log if x.startswith("BŁĄD")), "brak wiersza BŁĄD")[:300])
    rap.punkt("niczego nie zainstalowano", not korzen.exists(), f"{korzen} " + ("nie powstał" if not korzen.exists()
                                                                                 else "powstał"))
    return rap.zapisz(korzen=str(korzen), odmowa=tekst)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    reszta: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, reszta = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tryb", choices=("sprawdz", "bez-sieci", "odmowa"))
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT); w trybie odmowa: nowy katalog")
    ap.add_argument("--wyniki", default=str(Path.cwd() / "natywnie-miejsce"), help="katalog raportu i logów")
    ap.add_argument("--max-gb", type=float, default=0.0, help="sprawdz: Jarvo zajmuje najwyżej tyle GB")
    ap.add_argument("--wolne-gb", type=float, default=1.0,
                    help="odmowa: wolne miejsce na dysku korzenia (0 = prawdziwe)")
    a = ap.parse_args(argv)
    a.argumenty = reszta
    return {"sprawdz": tryb_sprawdz, "bez-sieci": tryb_bez_sieci, "odmowa": tryb_odmowa}[a.tryb](a)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Miejsce na dysku, system plików i sprzątanie instalacji natywnej, na żywo (docs/NATYWNIE.md: c3 pkt 11, Z31;
obszar miejsce). Sama biblioteka standardowa i pakiet jarvo/ tego repo (układ katalogów, szacunek z manifestu, zajęte
miejsce, woluminy); punkty raportu, katalog artefaktów i maskowanie sekretów bierze z tests/live/natywnie_e2e.py.

    python -X utf8 -B tests/live/natywnie_miejsce.py sprawdz   [--korzen R] [--artefakty KATALOG] [--max-gb N]
    python -X utf8 -B tests/live/natywnie_miejsce.py bez-sieci [--korzen R] [--artefakty KATALOG] [-- ARGUMENTY]
    python -X utf8 -B tests/live/natywnie_miejsce.py zamki     [--korzen R] [--artefakty KATALOG]
    python -X utf8 -B tests/live/natywnie_miejsce.py dyski     [--korzen R] [--artefakty KATALOG]
    python -X utf8 -B tests/live/natywnie_miejsce.py odmowa    [--korzen NOWY] [--artefakty KATALOG] [--wolne-gb N]

Korzeń: --korzen, JARVO_ROOT albo domyślny katalog systemu. Artefakty: --artefakty, $JARVO_E2E_ARTEFAKTY,
$RUNNER_TEMP/natywnie-artefakty albo katalog tymczasowy (jak w natywnie_e2e.py).

sprawdz (po udanej instalacji; tylko odczyt poza `jarvo doctor --json`):
  1. sprzątanie: w <cache>/pobrane nie ma archiwów narzędzi tej wersji (świeże pliki innych procesów mogą zostać),
     cache uv i pixi mają poniżej 1 MB (albo ich nie ma), w checkoucie Hermesa nie ma node_modules (korzeń i web/),
     a źródła skilli w <cache>/build zostały (aktualizacja buduje flotę),
  2. znaczniki gotowych części: narzędzia (.jarvo-suma), venvy, modele, Tesseract, Hermes i front; bez nich drugi
     przebieg sięgnąłby do sieci po to, czego po sprzątaniu nie ma już w cache,
  3. Tesseract po usunięciu cache pixi: `--list-langs` z pol i eng,
  4. zajęte miejsce (instalator.zajete_miejsce) wobec szacunku z manifestu tej wersji (potrzebne_miejsce, całość):
     „zostaje” nie mniejsze od zajętego o więcej niż 25 %, a szczyt z zapasem nie mniejszy niż zajęte + to, co
     zwolniło sprzątanie (ostatni wiersz „Sprzątanie” z <logi>/instalacja.log: tuż przed sprzątaniem jedno i drugie
     było na dysku naraz, więc to dolna granica prawdziwego szczytu); z --max-gb także górna granica zajętego,
  5. części w szacunku: każda część zmierzona na dysku (narzędzia, venvy, modele, Tesseract, checkout Hermesa, front
     z cache npm, źródła skilli, build, profile) i to, co sprzątanie zwolniło według dziennika (archiwa, cache uv,
     node_modules), najwyżej jej szacunek × (1 + ZAPAS) + 50 MB. Stałe HERMES_MB i FLOTA_MB z jarvo/instalator.py
     i współczynniki rozpakowania zmierzono na Windows 11 x64, więc ten punkt wskazuje, którą poprawić na innym
     systemie albo po zmianie pinu Hermesa czy floty,
  6. `jarvo doctor --json`: wynik „wolne miejsce” podaje zajęte i wolne miejsce.
bez-sieci: kolejny przebieg polecenia instalacji (`jarvo instaluj` tej instalacji z ARGUMENTAMI po `--`, np.
  --bez-autostartu --bez-path) z HTTPS_PROXY na martwy port 127.0.0.1, więc każde pobranie kończy się błędem: kod 0,
  „Zmiany w tym przebiegu: brak.”, bez „pobieram”, bez błędów i bez wiersza „Sprzątanie”, a <program> i <cache> bez
  zmian (nazwy i rozmiary plików przed i po; bez kodu bajtowego, który Python zapisuje sam przy imporcie).
zamki: drugi instalator równolegle. Proces pomocniczy trzyma zamki instalatorów w <stan> (przy-uzyciu.lock,
  venvy.lock, hermes.lock, tesseract.lock), a sprzątanie instalatora (_Instalacja.sprzatanie) biegnie na tej instalacji
  z plikami próby: archiwum z sumą narzędzia tej wersji, stare archiwum i świeże `.czesc` w <cache>/pobrane, plik
  w cache uv i w cache pixi (po 2 MB). Przy zajętych zamkach wszystko zostaje, z wierszami w logu i bez czekania na
  zamek; po ich zwolnieniu znika wszystko poza świeżym `.czesc` (cache uv czyści prawdziwe `uv cache clean`). Na
  końcu test usuwa swoje pliki; <logi>/instalacja.log zostaje bez zmian.
dyski: dyski, które instalator może polecić na korzeń (instalator.dyski_lokalne), każdy na woluminie z ochroną
  dostępu (polecany: Windows NTFS albo ReFS na dysku stałym, macOS APFS bez noowners, Linux ext4, xfs, btrfs…)
  i z zapisem, oraz wolumin korzenia bez bez_ochrony (nieznany, np. overlay, nie jest błędem); w miejsce.json
  wszystkie woluminy systemu z decyzją. Tylko odczyt.
odmowa: dwie instalacje w nowych katalogach (--korzen, domyślnie <artefakty>/miejsce-odmowa), żadna niczego nie
  zakłada: (a) na dysku korzenia jest --wolne-gb (domyślnie 1; 0 = prawdziwe wolne miejsce): kod 1 w kroku
  „Sprawdzenie komputera”, komunikat z potrzebą i poleceniem z JARVO_ROOT (instalator rusza tylko wtedy, gdy bilans
  z tym samym otoczeniem mówi „za mało”, inaczej punkt jest pominięty); (b) w <korzen>-exfat, z atrapą woluminu exFAT
  na dysku korzenia: kod 1 w kroku 1, komunikat o ochronie dostępu z innymi dyskami albo radą i poleceniem
  z JARVO_ROOT.

Punkty idą do <artefakty>/raport.json (ten sam plik co w natywnie_e2e.py, więc jego `podsumowanie` je pokazuje,
identyfikatory miejsce-<tryb>-<n>), szczegóły z czasem i kodem każdego trybu do <artefakty>/miejsce.json, wyjście
instalatora do <artefakty>/miejsce-*.log. Kod wyjścia: 0 = wszystkie punkty tego uruchomienia przeszły (pominięte się
nie liczą), 1 = któryś nie przeszedł, 2 = złe argumenty.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

TU = Path(__file__).resolve().parent
if str(TU) not in sys.path:
    sys.path.insert(0, str(TU))
import natywnie_e2e as e2e  # noqa: E402  (dodaje też katalog repo do sys.path)
from jarvo import instalator, manifest, modele, przy_uzyciu, sciezki, srodowisko, venvy  # noqa: E402
from jarvo import tesseract as jtesseract  # noqa: E402

REPO = e2e.REPO
WINDOWS = os.name == "nt"
MB, GB = instalator.MB, instalator.GB
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ZMIANY_BRAK = "Zmiany w tym przebiegu: brak."
ZNACZNIKI = {"venv-": ".jarvo-venv.json", "model-": ".jarvo-model.json", "node-floty": ".jarvo-lock"}   # infra/node/node_floty.py
TOLERANCJA_MB = 50               # części w szacunku: zmierzone ≤ szacunek × (1 + ZAPAS) + tyle MB
PROBA = "jarvo-proba-miejsca"    # nazwa plików próby trybu zamki


class Przebieg:
    """Punkty jednego trybu: w <artefakty>/raport.json (natywnie_e2e.Raport) i w <artefakty>/miejsce.json razem
    ze szczegółami, kodem i czasem trybu."""

    def __init__(self, art: Path, tryb: str):
        self.art, self.tryb, self.t0 = art, tryb, time.monotonic()
        self.rap = e2e.Raport(art)
        self.punkty: list[dict] = []

    def punkt(self, nazwa: str, ok: bool | None, opis: str, **dane) -> bool:
        """ok None = pominięty (z powodem), nie liczy się jako błąd."""
        opis = e2e.bez_sekretow(opis)
        self.punkty.append({"nazwa": nazwa, "ok": ok, "opis": opis, "czas": e2e.teraz(), **dane})
        return self.rap.punkt(f"miejsce-{self.tryb}-{len(self.punkty)}", f"miejsce {self.tryb}: {nazwa}", ok, opis)

    def koniec(self, **szczegoly) -> int:
        kod = 1 if self.rap.bledy else 0
        czas = round(time.monotonic() - self.t0, 1)
        plik = self.art / "miejsce.json"
        dane = e2e.wczytaj_json(plik)
        dane = dane if isinstance(dane, dict) else {}
        dane.setdefault("tryby", {})[self.tryb] = {"kod": kod, "czas_s": czas, "koniec": e2e.teraz(),
                                                    "punkty": self.punkty, **szczegoly}
        e2e.zapisz_json(plik, dane)
        print(json.dumps({"tryb": self.tryb, "kod": kod, "czas_s": czas, "bledy": len(self.rap.bledy),
                          "raport": str(plik)}, ensure_ascii=False), flush=True)
        return kod


def uklad(korzen: str | None) -> sciezki.Uklad:
    env = dict(os.environ)
    if korzen:
        env["JARVO_ROOT"] = korzen
    return instalator.bezwzgledny(sciezki.uklad(env))


def _pliki(katalog: Path) -> list[Path]:
    return sorted(p for p in katalog.rglob("*") if p.is_file()) if katalog.is_dir() else []


def _rozmiar(p: Path | str | None) -> int:
    return instalator.rozmiar_katalogu(p) if p and Path(p).exists() else 0


def _log_instalacji(u: sciezki.Uklad) -> str:
    try:
        return (u.logi / "instalacja.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _gb_z_logu(tekst: str) -> int:
    return int(float(tekst.replace(",", ".")) * GB)


def zwolnione_w_logu(tekst: str) -> dict[str, int]:
    """Z ostatniego „Sprzątanie: zwolnione X GB (archiwa narzędzi A GB, cache uv B GB, …)” i ostatnich „Hermes:
    usunięte (web/)node_modules (N MB)” w dzienniku instalacji: {"razem", "archiwa narzędzi", "cache uv",
    "cache pixi", "node_modules"} w bajtach (brak wiersza = 0)."""
    wynik = {"razem": 0, "archiwa narzędzi": 0, "cache uv": 0, "cache pixi": 0, "node_modules": 0}
    linie = [x for x in tekst.splitlines() if "Sprzątanie: zwolnione" in x]
    if linie:
        m = re.search(r"Sprzątanie: zwolnione ([\d,]+) GB", linie[-1])
        wynik["razem"] = _gb_z_logu(m.group(1)) if m else 0
        for nazwa, ile in re.findall(r"(archiwa narzędzi|cache uv|cache pixi) ([\d,]+) GB", linie[-1]):
            wynik[nazwa] = _gb_z_logu(ile)
    node = re.findall(r"Hermes: usunięte ((?:web/)?node_modules) \((\d+) MB\)", tekst)
    ostatnie: dict[str, int] = {}
    for nazwa, ile in node:
        ostatnie[nazwa] = int(ile) * MB
    wynik["node_modules"] = sum(ostatnie.values())
    return wynik


def nasze_sumy(app: Path, platforma: str) -> set[str]:
    """16 znaków sumy archiwów narzędzi z `kiedy: instalacja` tej wersji dla platformy."""
    narz = manifest.wczytaj(app)
    return {str(manifest.plik(narz, n, platforma).get("sha256") or "")[:16]
            for n in instalator.narzedzia_instalacji(narz, platforma)} - {""}


# ------------------------------------------------------------------------------------------------ sprawdz

def czesci_w_szacunku(u: sciezki.Uklad, app: Path, platforma: str, biez: dict, potrzeby: list,
                      zwolnione: dict[str, int]) -> list[dict]:
    """Każda część szacunku (potrzebne_miejsce, całość) z pomiarem: na dysku po instalacji albo z dziennika
    sprzątania (części chwilowe). [{"czesc", "zmierzone", "szacunek", "ok"}] w bajtach."""
    szac = {p.opis.split(" (")[0]: p for p in potrzeby}
    narz = manifest.wczytaj(app)
    spis = srodowisko.narzedzia(u)
    pomiary: dict[str, tuple[int, int]] = {}

    def dodaj(czesc: str, zmierzone: int, szacunek: int | None = None) -> None:
        if czesc in szac or szacunek is not None:
            pomiary[czesc] = (zmierzone, szac[czesc].zostaje if szacunek is None else szacunek)

    nazwy = instalator.narzedzia_instalacji(narz, platforma)
    dodaj("narzędzia", sum(_rozmiar((spis.get(n) or {}).get("katalog")) for n in nazwy))
    dodaj("venvy", sum(_rozmiar(venvy.katalog(u, n, w)) for n, w in manifest.venvy(app).items()
                       if isinstance(w, dict) and (w.get("kiedy") or "instalacja") == "instalacja"))
    dodaj("modele", sum(_rozmiar(modele.katalog(u.jarvo_dane / "models", m)) for m in manifest.modele(app).values()
                        if isinstance(m, dict) and (m.get("kiedy") or "instalacja") == "instalacja"))
    if jtesseract.projekt(app) is not None:
        dodaj("Tesseract", _rozmiar(jtesseract.katalog(u, app)))
    checkout = Path(str(biez.get("hermes") or ""))
    dodaj("Hermes", _rozmiar(checkout) if checkout.name else 0)
    web = Path(str(biez.get("web_dist") or ""))
    front = _rozmiar(web) if web.name and not instalator._w_korzeniu(web, checkout) else 0
    dodaj("front panelu i cache npm", front + _rozmiar(u.cache / "npm"))
    dodaj("źródła skilli floty", sum(_rozmiar(z) for z in (u.cache / "build").glob("*@*")))
    dodaj("build floty", _rozmiar(u.build))
    dodaj("profile floty", _rozmiar(u.dane / "profiles"))
    if "archiwa narzędzi" in szac:
        dodaj("archiwa narzędzi", zwolnione["archiwa narzędzi"], szac["archiwa narzędzi"].szczyt)
    uv = sum(szac[c].szczyt for c in ("cache uv venvów", "cache uv Hermesa") if c in szac)
    if uv:
        dodaj("cache uv (venvy i Hermes)", zwolnione["cache uv"], uv)
    if "node_modules frontu" in szac:
        dodaj("node_modules frontu", zwolnione["node_modules"], szac["node_modules frontu"].szczyt)
    wynik = []
    for czesc, (zmierzone, szacunek) in pomiary.items():
        granica = int(szacunek * (1 + instalator.ZAPAS)) + TOLERANCJA_MB * MB
        wynik.append({"czesc": czesc, "zmierzone": zmierzone, "szacunek": szacunek, "ok": zmierzone <= granica})
    return wynik


def tryb_sprawdz(a) -> int:
    u = uklad(a.korzen)
    p = Przebieg(e2e.katalog_artefaktow(a.artefakty), "sprawdz")
    biez = srodowisko.biezace(u)
    if not biez:
        p.punkt("instalacja", False, f"brak {u.program / 'current.json'}: Jarvo nie jest zainstalowane w {u.root}")
        return p.koniec(korzen=str(u.root))
    app = instalator.katalog_aplikacji(u)
    platforma = sciezki.platforma()
    # 1. sprzątanie
    nasze = nasze_sumy(app, platforma)
    pobrane = _pliki(u.cache / "pobrane")
    zle = [x.name for x in pobrane if x.name[16:17] == "-" and x.name[:16] in nasze and not x.name.endswith(".czesc")]
    p.punkt("archiwa narzędzi usunięte", not zle,
            ("zostały: " + ", ".join(zle[:5])) if zle else
            f"w <cache>/pobrane bez archiwów narzędzi tej wersji (inne pliki: {len(pobrane)})")
    for nazwa, kat in (("cache uv", u.cache / "uv"), ("cache pixi", u.cache / "pixi")):
        b = _rozmiar(kat)
        p.punkt(f"{nazwa} wyczyszczony", b < instalator.PROG_SPRZATANIA, f"{kat}: {b / MB:.1f} MB")
    checkout = Path(str(biez.get("hermes") or ""))
    nm = [k for k in (checkout / "node_modules", checkout / "web" / "node_modules") if k.exists()]
    p.punkt("node_modules frontu usunięte", bool(checkout.name) and not nm,
            f"{checkout}: " + ("bez node_modules" if not nm else "zostały " + ", ".join(map(str, nm))))
    if (u.dane / "profiles").is_dir():
        zrodla = sorted((u.cache / "build").glob("*@*"))
        p.punkt("źródła skilli zostały", bool(zrodla), f"{len(zrodla)} źródeł w {u.cache / 'build'} "
                f"({instalator.gb(sum(_rozmiar(z) for z in zrodla))} GB)")
    # 2. znaczniki gotowych części
    braki = []
    for nazwa, wpis in srodowisko.narzedzia(u).items():
        kat = Path(str((wpis or {}).get("katalog") or ""))
        if nazwa == "tesseract":
            znacznik = kat / jtesseract.ZNACZNIK
        else:
            znacznik = kat / next((z for pre, z in ZNACZNIKI.items() if nazwa.startswith(pre)), ".jarvo-suma")
        if not znacznik.is_file():
            braki.append(f"{nazwa} ({znacznik})")
    for z in (".jarvo-hermes.json", ".jarvo-web-dist.json"):
        if not (checkout / z).is_file():
            braki.append(f"Hermes ({checkout / z})")
    p.punkt("znaczniki gotowych części", not braki, "wszystkie są" if not braki else "brak: " + "; ".join(braki[:6]))
    # 3. Tesseract bez cache pixi
    tess = srodowisko.narzedzia(u).get("tesseract") or {}
    if tess.get("program"):
        ok, opis = jtesseract.sprawdz(Path(tess["program"]), Path((tess.get("env") or {}).get("TESSDATA_PREFIX", "")))
        p.punkt("Tesseract działa po usunięciu cache pixi", ok, f"--list-langs: {opis}")
    else:
        p.punkt("Tesseract działa po usunięciu cache pixi", None, "ta instalacja nie ma Tesseracta")
    # 4. zajęte miejsce wobec szacunku z manifestu
    zajete = instalator.zajete_miejsce(u)
    razem = sum(zajete.values())
    potrzeby = instalator.potrzebne_miejsce(u, app, platforma, wszystko=True)   # jak na pustym dysku
    szczyt = int(sum(x.szczyt for x in potrzeby) * (1 + instalator.ZAPAS)) + instalator.ZAPAS_MB * MB
    zostaje = sum(x.zostaje for x in potrzeby)
    zwolnione = zwolnione_w_logu(_log_instalacji(u))
    dolna = razem + zwolnione["razem"]     # tuż przed sprzątaniem było na dysku jedno i drugie naraz
    p.punkt("szacunek „zostaje” nie zaniża zajętego", zostaje >= razem * 0.75,
            f"zajęte {instalator.opis_zajetego(zajete)}, szacunek po sprzątaniu {instalator.gb(zostaje)} GB "
            f"({zostaje / max(razem, 1):.2f} zajętego)")
    p.punkt("szczyt z zapasem obejmuje dolną granicę prawdziwego szczytu", szczyt >= dolna,
            f"szacunek {instalator.gb(szczyt)} GB, dolna granica {instalator.gb(dolna)} GB (zajęte "
            f"{instalator.gb(razem)} + sprzątanie {instalator.gb(zwolnione['razem'])}; node_modules "
            f"{instalator.gb(zwolnione['node_modules'])} GB zniknęło wcześniej, zaraz po budowie frontu)")
    if a.max_gb:
        p.punkt(f"Jarvo zajmuje najwyżej {a.max_gb:g} GB", razem <= a.max_gb * GB, f"zajęte {instalator.gb(razem)} GB")
    # 5. każda część w swoim szacunku
    czesci = czesci_w_szacunku(u, app, platforma, biez, potrzeby, zwolnione)
    ponad = [c for c in czesci if not c["ok"]]
    p.punkt("części w szacunku", not ponad,
            "; ".join(f"{c['czesc']} {c['zmierzone'] / MB:.0f} MB > szacunek {c['szacunek'] / MB:.0f} MB" for c in ponad)
            + (" (popraw HERMES_MB, FLOTA_MB albo ROZPAKOWANIE w jarvo/instalator.py, venv_mb w vendor/natywne.yaml)"
               if ponad else "")
            or ", ".join(f"{c['czesc']} {c['zmierzone'] / MB:.0f}/{c['szacunek'] / MB:.0f} MB" for c in czesci))
    # 6. doctor
    argv = instalator.polecenie_jarva(u, "doctor", "--json")
    try:
        w = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                           creationflags=NO_WINDOW)
        d = json.loads(w.stdout)
        miejsce = next((x for x in d.get("wyniki", []) if x.get("nazwa") == "wolne miejsce"), {})
        ok = "Jarvo zajmuje" in str(miejsce.get("opis")) and "wolne" in str(miejsce.get("opis"))
        p.punkt("doctor pokazuje zajęte i wolne miejsce", ok,
                f"[{miejsce.get('stan')}] {miejsce.get('opis')}" if miejsce else "brak wyniku „wolne miejsce”")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        p.punkt("doctor pokazuje zajęte i wolne miejsce", False, f"{type(e).__name__}: {str(e)[:200]}")
    return p.koniec(korzen=str(u.root), platforma=platforma, zajete=zajete, zwolnione=zwolnione, czesci=czesci,
                    szacunek={"szczyt": szczyt, "zostaje": zostaje,
                              "czesci": {x.opis: [x.szczyt, x.zostaje] for x in potrzeby}})


# ------------------------------------------------------------------------------------------------ bez-sieci

def _migawka(u: sciezki.Uklad) -> dict[str, int]:
    """{ścieżka względna: rozmiar} plików <program> i <cache>, bez kodu bajtowego (__pycache__, .pyc): ten zapisuje
    sam Python przy imporcie, także działający serwis, a nie instalator."""
    wynik = {}
    for kat in (u.program, u.cache):
        for plik in _pliki(kat):
            if plik.suffix == ".pyc" or "__pycache__" in plik.parts:
                continue
            try:
                wynik[str(plik.relative_to(u.root) if instalator._w_korzeniu(plik, u.root) else plik)] = \
                    plik.stat().st_size
            except OSError:
                continue
    return wynik


def _martwy_port() -> int:
    """Port 127.0.0.1, na którym nikt nie słucha (od systemu, gniazdo od razu zamknięte)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _json_stanu(u: sciezki.Uklad, nazwa: str) -> dict:
    """`<stan>/<nazwa>` jako słownik (brak albo błąd odczytu = pusty), do porównania przed i po przebiegu."""
    try:
        d = json.loads((u.stan / nazwa).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(d, dict) and isinstance(d.get("env"), dict):          # srodowisko.json: zmienne procesów
        d = {**{k: v for k, v in d.items() if k != "env"}, **{f"env.{k}": v for k, v in d["env"].items()}}
    return d if isinstance(d, dict) else {}


def tryb_bez_sieci(a) -> int:
    u = uklad(a.korzen)
    art = e2e.katalog_artefaktow(a.artefakty)
    p = Przebieg(art, "bez-sieci")
    if not srodowisko.biezace(u):
        p.punkt("instalacja", False, f"Jarvo nie jest zainstalowane w {u.root}")
        return p.koniec(korzen=str(u.root))
    przed = _migawka(u)
    spisy_przed = {n: _json_stanu(u, n) for n in ("narzedzia.json", "srodowisko.json")}
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
    (art / "miejsce-bez-sieci.log").write_text(e2e.bez_sekretow(tekst), encoding="utf-8")
    linie = [x.strip() for x in tekst.splitlines()]
    p.punkt("instalacja bez sieci kończy się kodem 0", kod == 0, f"kod {kod} po {czas:.0f} s (proxy {proxy})")
    roznice = []
    for n, stare in spisy_przed.items():
        nowe = _json_stanu(u, n)
        for klucz in sorted(set(stare) | set(nowe), key=str):
            if stare.get(klucz) != nowe.get(klucz):
                roznice.append(f"{n}:{klucz}")
    p.punkt("drugi przebieg niczego nie zmienia", ZMIANY_BRAK in tekst,
            next((x for x in reversed(linie) if "Zmiany w tym przebiegu" in x), "brak wiersza „Zmiany…”")
            + (f" (inne wpisy: {', '.join(roznice[:12])})" if roznice else ""))
    pobrane = [x for x in linie if re.search(r"\bpobieram\b", x, re.I)]
    bledy = [x for x in linie if re.search(r"\bBŁĄD\b", x)]
    p.punkt("nic nie pobrane i bez błędów", not pobrane and not bledy, "; ".join((pobrane + bledy)[:4]) or "tak")
    sprzatanie = [x for x in linie if x.startswith("Sprzątanie:")]
    p.punkt("nic do sprzątania", not sprzatanie, sprzatanie[0] if sprzatanie else "brak wiersza „Sprzątanie”")
    po = _migawka(u)
    roznica = sorted(set(przed.items()) ^ set(po.items()))
    p.punkt("<program> i <cache> bez zmian", not roznica,
            f"{len(przed)} plików" if not roznica else "zmienione: " + ", ".join(k for k, _v in roznica[:6]))
    miejsce = next((x for x in linie if x.startswith("Miejsce:")), "")
    return p.koniec(korzen=str(u.root), czas_instalacji_s=round(czas, 1), miejsce_po_przebiegu=miejsce)


# ------------------------------------------------------------------------------------------------ zamki

@contextlib.contextmanager
def zamki_drugiego_procesu(sciezki_zamkow: list[Path]):
    """Zamki instalatorów (przenosne.Zamek) trzymane przez osobny proces, jak przez drugi instalator, aż do końca
    bloku."""
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); from jarvo.przenosne import Zamek\n"
           "zamki = [Zamek(p) for p in sys.argv[2:]]   # odwołania zostają: zamknięty plik zwolniłby zamek\n"
           "for z in zamki:\n    z.__enter__()\nprint('trzymam', flush=True)\nsys.stdin.read()\n")
    proc = subprocess.Popen([sys.executable, "-I", "-c", kod, str(REPO), *map(str, sciezki_zamkow)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, creationflags=NO_WINDOW)
    try:
        if proc.stdout.readline().strip() != "trzymam":
            raise RuntimeError("proces pomocniczy nie wziął zamków")
        yield
    finally:
        with contextlib.suppress(OSError):
            proc.stdin.close()
        proc.wait(timeout=60)


def _sprzatanie(u: sciezki.Uklad, app: Path, platforma: str) -> tuple[list[str], float]:
    """Sprzątanie instalatora na tej instalacji (wiersze dziennika tylko w pamięci) i jego czas w s."""
    linie: list[str] = []
    inst = instalator._Instalacja(u, app, instalator.Otoczenie(), linie.append, autostart=False, web_lokalnie=False,
                                  start=False, bez_path=True, platforma=platforma)
    inst.narz = dict(srodowisko.narzedzia(u))
    inst.log = linie.append                      # bez dopisywania do <logi>/instalacja.log
    t0 = time.monotonic()
    inst.sprzatanie()
    return linie + [f"Uwaga: {x}" for x in inst.uwagi], time.monotonic() - t0


def tryb_zamki(a) -> int:
    u = uklad(a.korzen)
    art = e2e.katalog_artefaktow(a.artefakty)
    p = Przebieg(art, "zamki")
    if not srodowisko.biezace(u) or "uv" not in srodowisko.narzedzia(u):
        p.punkt("instalacja", False, f"Jarvo z uv nie jest zainstalowane w {u.root}")
        return p.koniec(korzen=str(u.root))
    app = instalator.katalog_aplikacji(u)
    platforma = sciezki.platforma()
    nasza = sorted(nasze_sumy(app, platforma))[0]
    pobrane = u.cache / "pobrane"
    proba = {"archiwum tego przebiegu": pobrane / f"{nasza}-{PROBA}.zip",
             "stare archiwum": pobrane / f"{'0' * 16}-{PROBA}-stare.zip",
             "świeże .czesc innego procesu": pobrane / f"{'0' * 16}-{PROBA}.zip.czesc",
             "cache uv": u.cache / "uv" / PROBA / "plik.bin", "cache pixi": u.cache / "pixi" / PROBA / "plik.bin"}
    if any(f.exists() for f in proba.values()):
        p.punkt("pliki próby", False, "pliki próby już są (przerwany poprzedni przebieg?): "
                + ", ".join(str(f) for f in proba.values() if f.exists()))
        return p.koniec(korzen=str(u.root))
    log_przed = _log_instalacji(u)
    for f in proba.values():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"\0" * (2 * MB))
    stare = time.time() - instalator.SWIEZE_S - 600
    os.utime(proba["stare archiwum"], (stare, stare))
    zamki = [u.stan / przy_uzyciu.ZAMEK, *(u.stan / z for z in venvy.ZAMKI_CACHE), u.stan / jtesseract.ZAMEK]
    try:
        with zamki_drugiego_procesu(zamki):
            linie, czas = _sprzatanie(u, app, platforma)
        (art / "miejsce-zamki-zajete.log").write_text("\n".join(linie) + "\n", encoding="utf-8")
        zostaly = [k for k, f in proba.items() if f.exists()]
        p.punkt("zajęte zamki: sprzątanie niczego nie usuwa", zostaly == list(proba),
                "zostały wszystkie pliki próby" if zostaly == list(proba) else
                "zniknęły: " + ", ".join(k for k in proba if k not in zostaly))
        oczekiwane = {"pobrane": "trwa instalacja narzędzia przy pierwszym użyciu",
                      "uv": "drugi instalator właśnie buduje venv albo instaluje", "pixi": "drugi instalator właśnie "
                      "instaluje Tesseracta"}
        brak = [k for k, o in oczekiwane.items() if not any(o in x for x in linie)]
        p.punkt("zajęte zamki: wiersze w dzienniku, bez czekania", not brak and czas < 120,
                f"{czas:.1f} s" + (f"; brak wiersza dla: {', '.join(brak)}" if brak else ""))
        linie, czas = _sprzatanie(u, app, platforma)
        (art / "miejsce-zamki-wolne.log").write_text("\n".join(linie) + "\n", encoding="utf-8")
        zostaly = [k for k, f in proba.items() if f.exists()]
        p.punkt("wolne zamki: znika wszystko poza świeżym .czesc", zostaly == ["świeże .czesc innego procesu"],
                f"zostały: {', '.join(zostaly) or 'nic'} ({czas:.1f} s)")
        uv = [x.strip() for x in linie if x.strip().startswith(("cache uv:", "cache uv zostaje"))]
        p.punkt("cache uv przez uv cache clean", bool(uv) and uv[-1].startswith("cache uv:"), uv[-1] if uv else
                "brak wiersza uv")
    finally:
        for f in proba.values():
            with contextlib.suppress(OSError):
                f.unlink()
        for k in (u.cache / "uv" / PROBA, u.cache / "pixi" / PROBA):
            with contextlib.suppress(OSError):
                k.rmdir()
    p.punkt("dziennik instalacji bez zmian", _log_instalacji(u) == log_przed, str(u.logi / "instalacja.log"))
    return p.koniec(korzen=str(u.root), zamki=[str(z) for z in zamki])


# ------------------------------------------------------------------------------------------------ dyski

def _opis_woluminu(w: instalator.Wolumin | None) -> str:
    return f"{w.typ} ({', '.join(sorted(w.opcje))})" if w else "nieznany"


def tryb_dyski(a) -> int:
    u = uklad(a.korzen)
    p = Przebieg(e2e.katalog_artefaktow(a.artefakty), "dyski")
    woluminy: list[instalator.Wolumin] = []
    if not WINDOWS:
        try:
            woluminy = instalator._woluminy()
        except (OSError, subprocess.SubprocessError) as e:
            p.punkt("woluminy systemu", False, f"{type(e).__name__}: {e}")
    dyski = instalator.dyski_lokalne()
    opisy, zle = [], []
    for d in dyski:
        w = instalator.wolumin(d)
        dom = not WINDOWS and d == Path.home()
        ok = w is not None and instalator.polecany(w, systemowy=dom) and os.access(d, os.W_OK)
        opisy.append(f"{d}: {_opis_woluminu(w)}")
        if not ok:
            zle.append(f"{d}: {_opis_woluminu(w)}")
    if dyski:
        p.punkt("dyski do polecenia mają ochronę dostępu i zapis", not zle, "; ".join(zle or opisy))
    else:
        p.punkt("dyski do polecenia mają ochronę dostępu i zapis", None,
                "żadnego dysku do polecenia (np. katalog domowy na NFS albo w kontenerze)")
    w = instalator.wolumin(u.root)
    powod = instalator.bez_ochrony(w) if w else None
    p.punkt("wolumin korzenia z ochroną dostępu", powod is None,
            f"{u.root}: {_opis_woluminu(w)}" + (f": {powod}" if powod else
                                                "" if w else " (sieciowy, overlay albo tmpfs: instalator nie odmawia)"))
    decyzje = [{"urzadzenie": x.urzadzenie, "punkt": x.punkt, "typ": x.typ, "opcje": sorted(x.opcje),
                "bez_ochrony": instalator.bez_ochrony(x), "polecany": instalator.polecany(x)} for x in woluminy]
    return p.koniec(korzen=str(u.root), dyski=[str(d) for d in dyski], wolumin_korzenia=_opis_woluminu(w),
                    woluminy=decyzje)


# ------------------------------------------------------------------------------------------------ odmowa

def _nowy_korzen(p: Przebieg, korzen: Path) -> sciezki.Uklad | None:
    if korzen.exists():
        p.punkt("nowy katalog", False, f"{korzen} już istnieje: odmowę sprawdzamy na nowym katalogu")
        return None
    return instalator.bezwzgledny(sciezki.uklad({**os.environ, "JARVO_ROOT": str(korzen)}))


def _instaluj(u: sciezki.Uklad, ot: instalator.Otoczenie, platforma: str) -> tuple[int, str]:
    log: list[str] = []
    kod = instalator.instaluj(u, REPO, autostart=False, start=False, bez_path=True, log=log.append, otoczenie=ot,
                              platforma=platforma)
    return kod, "\n".join(log)


def tryb_odmowa(a) -> int:
    art = e2e.katalog_artefaktow(a.artefakty)
    p = Przebieg(art, "odmowa")
    korzen = Path(os.path.abspath(a.korzen or str(art / "miejsce-odmowa")))
    platforma = sciezki.platforma()
    teksty: dict[str, str] = {}
    # (a) za mało miejsca na dysku korzenia
    u = _nowy_korzen(p, korzen)
    if u is not None:
        dysk_korzenia = instalator.dysk(u.root)

        def wolne(sciezka) -> int:
            if a.wolne_gb and instalator.dysk(sciezka) == dysk_korzenia:
                return int(a.wolne_gb * GB)
            return instalator.wolne_miejsce(sciezka)
        ot = instalator.Otoczenie(wolne_miejsce=wolne)
        bilans = instalator.bilans_dyskow(u, instalator.potrzebne_miejsce(u, REPO, platforma), ot)
        if not [b for b in bilans if b["wolne"] is not None and b["wolne"] < b["potrzeba"]]:
            p.punkt("za mało miejsca: odmowa", None, f"na dysku {bilans[0]['punkt']} jest dość miejsca "
                    f"({instalator.gb(bilans[0]['wolne'] or 0)} GB): instalatora nie uruchamiam")
        else:
            kod, tekst = _instaluj(u, ot, platforma)
            teksty["miejsce"] = tekst
            (art / "miejsce-odmowa.log").write_text(tekst + "\n", encoding="utf-8")
            p.punkt("za mało miejsca: kod 1 w kroku „Sprawdzenie komputera”",
                    kod == 1 and "BŁĄD w kroku „Sprawdzenie komputera”" in tekst, f"kod {kod}")
            p.punkt("za mało miejsca: komunikat z potrzebą i poleceniem", "potrzebuje na nim ok." in tekst
                    and "JARVO_ROOT" in tekst and "Niczego nie zainstalowałem." in tekst,
                    next((x for x in tekst.splitlines() if x.startswith("BŁĄD")), "brak wiersza BŁĄD")[:300])
            p.punkt("za mało miejsca: niczego nie zainstalowano", not korzen.exists(),
                    f"{korzen} " + ("nie powstał" if not korzen.exists() else "powstał"))
    # (b) wolumin bez ochrony dostępu (atrapa exFAT na dysku korzenia)
    korzen_b = korzen.with_name(korzen.name + "-exfat")
    u = _nowy_korzen(p, korzen_b)
    if u is not None:
        dysk_korzenia = instalator.dysk(u.root)
        exfat = (instalator.Wolumin("X:\\", "X:\\", "exFAT", frozenset({"staly"})) if WINDOWS else
                 instalator.Wolumin("/dev/proba1", "/media/proba", "exfat", frozenset({"rw"})))
        ot = instalator.Otoczenie(wolumin=lambda s: exfat if instalator.dysk(s) == dysk_korzenia
                                  else instalator.wolumin(s))
        kod, tekst = _instaluj(u, ot, platforma)
        teksty["dysk"] = tekst
        (art / "miejsce-odmowa-dysk.log").write_text(tekst + "\n", encoding="utf-8")
        p.punkt("dysk bez ochrony: kod 1 w kroku „Sprawdzenie komputera”",
                kod == 1 and "BŁĄD w kroku „Sprawdzenie komputera”: korzeń" in tekst, f"kod {kod}")
        p.punkt("dysk bez ochrony: komunikat z radą i poleceniem", "nie przechowuje uprawnień" in tekst
                and "JARVO_ROOT" in tekst and "Niczego nie zainstalowałem." in tekst,
                next((x for x in tekst.splitlines() if x.startswith("BŁĄD")), "brak wiersza BŁĄD")[:300])
        p.punkt("dysk bez ochrony: niczego nie zainstalowano", not korzen_b.exists(),
                f"{korzen_b} " + ("nie powstał" if not korzen_b.exists() else "powstał"))
    return p.koniec(korzen=str(korzen), odmowa=teksty)


def main(argv: list[str] | None = None) -> int:
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    reszta: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, reszta = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="natywnie_miejsce.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("tryb", choices=("sprawdz", "bez-sieci", "zamki", "dyski", "odmowa"))
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT); w trybie odmowa: nowy katalog")
    ap.add_argument("--artefakty", help="katalog raportu i logów (domyślnie $JARVO_E2E_ARTEFAKTY albo "
                    "$RUNNER_TEMP/natywnie-artefakty)")
    ap.add_argument("--max-gb", type=float, default=0.0, help="sprawdz: Jarvo zajmuje najwyżej tyle GB")
    ap.add_argument("--wolne-gb", type=float, default=1.0,
                    help="odmowa: wolne miejsce na dysku korzenia (0 = prawdziwe)")
    a = ap.parse_args(argv)
    a.argumenty = reszta
    tryby = {"sprawdz": tryb_sprawdz, "bez-sieci": tryb_bez_sieci, "zamki": tryb_zamki, "dyski": tryb_dyski,
             "odmowa": tryb_odmowa}
    return tryby[a.tryb](a)


if __name__ == "__main__":
    sys.exit(main())

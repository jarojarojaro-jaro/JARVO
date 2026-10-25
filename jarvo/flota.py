"""Flota natywnie: build profili i instalacja floty w układzie instalacji (docs/NATYWNIE.md: S05, S06, S07, E4).

`zainstaluj_flote(u, env, *, log=print, pierwsza=None, wznow_rutyny=False) -> dict`
  1. scripts/build.py Pythonem venvu Hermesa (checkout z `<program>/current.json`, H13; ma ruamel, PyYAML i API
     crona) do `<root>/build`: --hermes-src <checkout>, --out i --runtime-build-dir `<root>/build`, --cache
     `<cache>/build` (klony źródeł skilli przeżywają kolejne buildy, a build zostaje odtwarzalny), --wybor-modelu
     `<dane>/jarvo/state/dostawca-modeli.json` (dostawca z pierwszego spotkania), --env-file
     `<dane>/jarvo/konfig/jarvo.env`, gdy jest (D02), i opcje ścieżek z kontraktu tokenów E4 (OPCJE_BUILDU: --dane
     i reszta), o ile ta wersja build.py je zna (`build.py --help`). Opcja, której build.py nie zna, to ostrzeżenie
     w logu i w wyniku (`build.bez_opcji`): ten token zostaje w buildzie z wartością kontenerową.
  2. scripts/install_fleet.py tym samym Pythonem: --dane, --build, --repo (kod tej wersji), --narzedzia
     `<program>/narzedzia-floty`, --hermes-python, --natywnie, --podsumowanie `<stan>/flota.json`; sekrety z
     `<dane>/jarvo/konfig` (host.env i <agent>.env), gdy jest tam host.env, inaczej --bez-sekretow (klucze są
     wtedy od razu w .env w `<dane>`, a do agentów idą przez share_keys.py); --first-run przy pierwszej
     instalacji (bez profilu Jarva z distribution.yaml, albo `pierwsza=True`), --resume-cron z `wznow_rutyny`.
  3. Wynik: podsumowanie install_fleet.py (agenci, wtyczki, dowiązania, zmiany, `restart_bramy`, `restart_panelu`,
     skarbiec, lint, ostrzeżenia, bez sekretów) i `build` (katalog, użyte opcje, czas).

Restartu nie robimy: robi go nadzorca. `uslugi_do_restartu(wynik)` daje nazwy usług nadzorcy ("brama", "panel")
dla `nadzorca.polacz(u).restart(nazwa)`, a po restarcie albo pierwszym starcie panelu ten, kto go zrobił, woła
`potwierdz_restart_panelu(u, wynik["odcisk_panelu"])`: następna instalacja nie zleci wtedy restartu panelu bez zmian
we wtyczkach (ten sam znacznik co w install-fleet.sh).

Środowisko obu kroków to `env` (zwykle srodowisko.srodowisko(u)) bez zmiennych obcych (PYTHONPATH, cudzy venv,
HERMES_YOLO_MODE…), z HERMES_HOME = `<dane>`, JARVO_HERMES_PYTHON (build crona) i wyjściem w UTF-8. Polecenia
dostają listę argumentów (bez powłoki) i `-P`, więc katalog bieżący nie trafia do sys.path. Moduł działa na bibliotece
standardowej (Python Jarva), YAML czytają dopiero skrypty w Pythonie Hermesa.
"""
from __future__ import annotations

import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from . import przenosne, sciezki, srodowisko
from .sciezki import WINDOWS, Uklad

APP = Path(__file__).resolve().parent.parent          # kod tej wersji Jarva (zawiera scripts/ i jarvo/)
ORKIESTRATOR = "jarvo"                                # jak install_fleet.py: jego profil = flota już zainstalowana
ZNACZNIK_PANELU = ".odcisk-panelu"                    # <dane>/plugins: odcisk wtyczek panelu po jego restarcie
CZAS_BUILDU = 3600.0             # pierwszy build klonuje źródła skilli (ok. 2 GB), kolejne biorą je z <cache>/build
CZAS_INSTALACJI = 3600.0         # profile update kopiuje skille 10 profili, zasiew skarbca, lint
# Tokeny ścieżek E4 (wspólny kontrakt build.py, install_fleet.py i skilli; docs/NATYWNIE.md S06, F12, F14, F17)
# → opcje build.py, które je ustawiają; pierwsza nazwa znana tej wersji build.py wygrywa. JARVO_DIR, KNOWLEDGE_DIR,
# MISSIONS_DIR, WORKSPACES_DIR i INBOX_DIR build liczy z --dane, BUILD_DIR to --runtime-build-dir.
OPCJE_BUILDU = (
    ("DATA_DIR", ("--dane",)),
    ("REPO_DIR", ("--repo-dir", "--repo")),
    ("TOOLS_DIR", ("--tools-dir", "--narzedzia-dir", "--narzedzia")),
    ("BIN_DIR", ("--bin-dir", "--bin-floty", "--bin")),
    ("PY", ("--py", "--python-floty")),
)
# układ natywny (bez niego build.py zostaje przy ścieżkach kontenera i odrzuca ścieżki Windows) i system docelowy:
# wartości per system z S06 (silnik przeglądarki, wyszukiwarka, polecenia STT i TTS, zakazy)
OPCJA_UKLADU = ("--uklad", "natywny")
OPCJA_SYSTEMU = "--system"
_OPCJA = re.compile(r"^\s+(?:-\w(?: \S+)?, )?(--[a-z][a-z0-9-]*)")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_SLOWO = re.compile(r"[A-Za-z0-9_./:@%+=,-]+")              # słowo polecenia powłoki, które nie wymaga cudzysłowu
_FLAGI = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


class BladFloty(RuntimeError):
    """Build albo instalacja floty się nie udały (komunikat po polsku, bez sekretów)."""


# --- środowisko i procesy -------------------------------------------------------------------------------------------

def _env(u: Uklad, env: dict, python: Path) -> dict[str, str]:
    """`env` bez zmiennych obcych (srodowisko.OBCE: PYTHONPATH, cudzy venv, HERMES_YOLO_MODE…) + HERMES_HOME Jarva,
    Python Hermesa dla budowy crona i wyjście w UTF-8. Na Windows nazwy zmiennych nie rozróżniają wielkości liter."""
    obce = {o.upper() for o in srodowisko.OBCE}
    wynik = {str(k): str(v) for k, v in dict(env).items() if str(k).upper() not in obce}
    for klucz, wartosc in (("HERMES_HOME", str(u.dane)), ("JARVO_HERMES_PYTHON", str(python)),
                           ("PYTHONUTF8", "1"), ("PYTHONIOENCODING", "utf-8"), ("NO_COLOR", "1")):
        for k in [k for k in wynik if k.upper() == klucz.upper()]:
            del wynik[k]
        wynik[klucz] = wartosc
    return wynik


def _strumien(argv: list, *, cwd: Path, env: dict, log: Callable[[str], None], czas: float,
              wciecie: str = "    ") -> tuple[int, list[str]]:
    """Program bez wejścia i bez okna konsoli; jego wyjście linia po linii do `log`. Po `czas` sekundach zabity.
    Zwraca kod wyjścia i ostatnie linie (do komunikatu błędu)."""
    ogon: deque[str] = deque(maxlen=12)
    try:
        proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", creationflags=_FLAGI)
    except OSError as e:
        raise BladFloty(f"Nie uruchomię {Path(str(argv[0])).name}: {e}") from None
    zabity = threading.Event()

    def zabij() -> None:
        zabity.set()
        proc.kill()

    zegar = threading.Timer(czas, zabij)
    zegar.start()
    try:
        with proc:
            for surowa in proc.stdout:
                linia = _ANSI.sub("", surowa).rstrip()
                if linia.strip():
                    ogon.append(linia)
                    log(wciecie + linia)
            kod = proc.wait()
    finally:
        zegar.cancel()
    if zabity.is_set():
        ogon.append(f"(przerwane po {int(czas)} s)")
    return kod, list(ogon)


def opcje_buildu(python: Path, build_py: Path, env: dict, cwd: Path) -> set[str]:
    """Opcje, które zna ta wersja build.py (z `--help`; tylko lista opcji, nie opis w docstringu)."""
    try:
        w = subprocess.run([str(python), "-P", str(build_py), "--help"], cwd=str(cwd), env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, creationflags=_FLAGI)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise BladFloty(f"build.py --help: {e}") from None
    if w.returncode:
        koniec = " / ".join(x for x in (w.stdout + w.stderr).splitlines()[-3:] if x.strip())
        raise BladFloty(f"build.py --help: kod {w.returncode}: {koniec}")
    return {m.group(1) for linia in w.stdout.splitlines() if (m := _OPCJA.match(linia))}


# --- układ ------------------------------------------------------------------------------------------------------

def katalog_kodu(u: Uklad) -> Path:
    """Kod aktywnej wersji Jarva (`app` z current.json), a bez instalacji katalog, z którego działa ten moduł."""
    app = srodowisko.biezace(u).get("app")
    return Path(app) if app and (Path(app) / "scripts" / "build.py").is_file() else APP


def python_hermesa(u: Uklad) -> tuple[Path, Path]:
    """(checkout Hermesa, Python jego venvu) z current.json; BladFloty, gdy Hermesa nie ma."""
    hermes = srodowisko.biezace(u).get("hermes")
    if not hermes:
        raise BladFloty(f"Nie ma zainstalowanego Hermesa: {u.program / 'current.json'} nie wskazuje checkoutu. "
                        "Uruchom najpierw instalację Jarva (`jarvo instaluj`).")
    checkout = Path(hermes)
    python = srodowisko.hermes_python(checkout)
    if not python.is_file():
        raise BladFloty(f"Brak Pythona Hermesa ({python}): instalacja jest niepełna. Uruchom `jarvo instaluj` "
                        "jeszcze raz.")
    return checkout, python


def python_floty(u: Uklad, hermes_py: Path) -> Path:
    """Python skryptów floty (token @@PY@@, F12): venv narzędzi z `<stan>/narzedzia.json` (wpis `venv-narzedzia`,
    pole `python`), a do czasu jego instalacji Python Hermesa, jak `python3` w kontenerze."""
    wpis = srodowisko.narzedzia(u).get("venv-narzedzia")
    py = (wpis or {}).get("python") if isinstance(wpis, dict) else None
    return Path(py) if py and Path(py).is_file() else hermes_py


def wartosci_tokenow(u: Uklad, app: Path, py: Path) -> dict[str, str]:
    """Wartości tokenów ścieżek tej instalacji, zawsze z „/” (Path.as_posix()). @@PY@@ to słowo polecenia w skillach:
    w cudzysłowie, gdy ścieżka ma spację albo inny znak spoza bezpiecznych (np. polskie litery w nazwie użytkownika);
    opcji build.py idzie ścieżka bez cudzysłowu (cudzysłów dokłada build)."""
    jd = u.jarvo_dane
    py_tekst = py.as_posix()
    return {
        "DATA_DIR": u.dane.as_posix(),
        "JARVO_DIR": jd.as_posix(),
        "KNOWLEDGE_DIR": (jd / "knowledge").as_posix(),
        "MISSIONS_DIR": (jd / "missions").as_posix(),
        "WORKSPACES_DIR": (jd / "workspaces").as_posix(),
        "INBOX_DIR": (jd / "inbox").as_posix(),
        "REPO_DIR": Path(app).as_posix(),
        "BUILD_DIR": u.build.as_posix(),
        "TOOLS_DIR": (u.program / "narzedzia-floty").as_posix(),
        "BIN_DIR": u.bin_floty.as_posix(),
        "PY": py_tekst if _SLOWO.fullmatch(py_tekst) else f'"{py_tekst}"',
    }


def argv_buildu(u: Uklad, app: Path, checkout: Path, python: Path, py_floty: Path, znane: set[str]) \
        -> tuple[list[str], dict[str, str], list[str]]:
    """(argv build.py, {token: użyta opcja}, tokeny bez opcji w tej wersji build.py)."""
    jd = u.jarvo_dane
    argv = [str(python), "-P", str(Path(app) / "scripts" / "build.py"), "--hermes-src", str(checkout),
            "--out", str(u.build), "--cache", str(u.cache / "build"), "--runtime-build-dir", u.build.as_posix(),
            "--wybor-modelu", str(jd / "state" / "dostawca-modeli.json")]
    konfig = jd / "konfig" / "jarvo.env"
    if konfig.is_file():
        argv += ["--env-file", str(konfig)]
    if OPCJA_UKLADU[0] in znane:
        argv += list(OPCJA_UKLADU)
    if OPCJA_SYSTEMU in znane:
        argv += [OPCJA_SYSTEMU, system()]
    sciezki_opcji = {"DATA_DIR": u.dane.as_posix(), "REPO_DIR": Path(app).as_posix(),
                     "TOOLS_DIR": (u.program / "narzedzia-floty").as_posix(), "BIN_DIR": u.bin_floty.as_posix(),
                     "PY": py_floty.as_posix()}
    uzyte: dict[str, str] = {}
    brak: list[str] = []
    for token, nazwy in OPCJE_BUILDU:
        opcja = next((n for n in nazwy if n in znane), None)
        if opcja is None:
            brak.append(token)
            continue
        argv += [opcja, sciezki_opcji[token]]
        uzyte[token] = opcja
    return argv, uzyte, brak


def system() -> str:
    """System tej instalacji w nazwach build.py (--system): windows, macos albo linux."""
    return "windows" if WINDOWS else "macos" if sciezki.MACOS else "linux"


def argv_instalacji(u: Uklad, app: Path, python: Path, *, pierwsza: bool, wznow_rutyny: bool) -> list[str]:
    konfig = u.jarvo_dane / "konfig"                   # źródłowe sekrety (D02), gdy właściciel je tam trzyma
    sekrety = ["--sekrety", str(konfig)] if (konfig / "host.env").is_file() else ["--bez-sekretow"]
    return [str(python), "-P", str(Path(app) / "scripts" / "install_fleet.py"), "--dane", str(u.dane),
            "--build", str(u.build), "--repo", str(app), "--narzedzia", str(u.program / "narzedzia-floty"),
            "--hermes-python", str(python), "--natywnie", "--podsumowanie", str(u.stan / "flota.json"), *sekrety,
            *(["--first-run"] if pierwsza else []), *(["--resume-cron"] if wznow_rutyny else [])]


def pierwsza_instalacja(u: Uklad) -> bool:
    """Flota jeszcze niezainstalowana: profil Jarva bez distribution.yaml (wtedy model floty trafia do hosta)."""
    return not (u.dane / "profiles" / ORKIESTRATOR / "distribution.yaml").is_file()


# --- przebieg -----------------------------------------------------------------------------------------------------

def zainstaluj_flote(u: Uklad, env: dict, *, log: Callable[[str], None] = print, pierwsza: bool | None = None,
                     wznow_rutyny: bool = False) -> dict:
    """Build profili do `<root>/build` i instalacja floty w `<dane>` (opis w docstringu modułu). Zwraca podsumowanie
    install_fleet.py z polem `build`; BladFloty, gdy któryś krok się nie uda."""
    app = katalog_kodu(u)
    checkout, python = python_hermesa(u)
    for k in (u.build, u.cache, u.stan, u.dane):
        k.mkdir(parents=True, exist_ok=True)
    e = _env(u, env, python)
    py_floty = python_floty(u, python)
    build_py = app / "scripts" / "build.py"
    if not build_py.is_file() or not (app / "scripts" / "install_fleet.py").is_file():
        raise BladFloty(f"{app} nie ma scripts/build.py i scripts/install_fleet.py: to nie jest kod Jarva.")

    log(f"Build floty: {u.build}")
    argv, uzyte, brak = argv_buildu(u, app, checkout, python, py_floty, opcje_buildu(python, build_py, e, app))
    if brak:
        log(f"  ! ta wersja build.py nie zna opcji dla tokenów {', '.join(brak)}: w buildzie zostają ich wartości "
            "kontenerowe (np. /opt/data)")
    start = time.monotonic()
    kod, ogon = _strumien(argv, cwd=app, env=e, log=log, czas=CZAS_BUILDU)
    czas_buildu = round(time.monotonic() - start, 1)
    if kod or not (u.build / "BUILD.json").is_file():
        raise BladFloty(f"build floty nie przeszedł (kod {kod}):\n" + "\n".join(f"    {x}" for x in ogon[-6:]))

    pierwsza = pierwsza_instalacja(u) if pierwsza is None else pierwsza
    log("Instalacja floty" + (" (pierwsza)" if pierwsza else ""))
    podsumowanie = u.stan / "flota.json"
    podsumowanie.unlink(missing_ok=True)
    start = time.monotonic()
    kod, ogon = _strumien(argv_instalacji(u, app, python, pierwsza=pierwsza, wznow_rutyny=wznow_rutyny),
                          cwd=u.dane, env=e, log=log, czas=CZAS_INSTALACJI, wciecie="  ")
    wynik = srodowisko.wczytaj_json(podsumowanie)
    if kod or not wynik:
        raise BladFloty(f"instalacja floty nie przeszła (kod {kod}):\n" + "\n".join(f"    {x}" for x in ogon[-6:]))
    wynik["build"] = {"katalog": u.build.as_posix(), "opcje": uzyte, "bez_opcji": brak, "czas_s": czas_buildu,
                      "tokeny": wartosci_tokenow(u, app, py_floty)}
    wynik["czas_instalacji_s"] = round(time.monotonic() - start, 1)
    wynik["pierwsza"] = pierwsza
    return wynik


def uslugi_do_restartu(wynik: dict) -> list[str]:
    """Nazwy usług nadzorcy do restartu po instalacji floty (kolejność startu nadzorcy: brama, potem panel)."""
    return [nazwa for nazwa, pole in (("brama", "restart_bramy"), ("panel", "restart_panelu")) if wynik.get(pole)]


def potwierdz_restart_panelu(u: Uklad, odcisk: str) -> bool:
    """Po restarcie (albo pierwszym starcie) panelu: zapis odcisku wtyczek, z którymi wstał (`<dane>/plugins/
    .odcisk-panelu`, jak install-fleet.sh). True = zapisano; pusty odcisk (brak wtyczek panelu) niczego nie zapisuje."""
    odcisk = str(odcisk or "").strip()
    if not re.fullmatch(r"[0-9a-f]{16}", odcisk):
        return False
    cel = u.dane / "plugins" / ZNACZNIK_PANELU
    try:
        if cel.read_text(encoding="utf-8").strip() == odcisk:
            return False
    except OSError:
        pass
    przenosne.zapisz_atomowo(cel, odcisk + "\n")
    return True


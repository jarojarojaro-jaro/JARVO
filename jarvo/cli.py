"""Polecenie `jarvo` natywnie (docs/NATYWNIE.md, N01–N17 i c4): jedno CLI w Pythonie na Windows, macOS i Linuksie.

Woła je `<root>\\bin\\jarvo.cmd` albo `~/.local/bin/jarvo` przez jarvo/start.py (`python -I -X utf8`), w kopii repo
`python -m jarvo`. Samo `jarvo` to `jarvo chat`. `--korzen <root>` na początku (launcher i autostart instalacji spod
JARVO_ROOT) ustawia korzeń jak JARVO_ROOT: zadanie Harmonogramu nie przekazuje zmiennych środowiska.

  instaluj             instalacja albo naprawa (jarvo/instalator.py; bootstrap woła ją sam)
  serwis               nadzorca bramy i panelu na pierwszym planie (jarvo/nadzorca.py; autostart woła go w tle)
  up, down             start serwisu (mechanizmem autostartu, gdy jest) i czekanie na panel, a bez instalacji
                       instalacja jak `jarvo instaluj` / zatrzymanie serwisu ze znacznikiem `<stan>/zatrzymany.json`:
                       autostart nie podniesie go sam, aż `jarvo up`, `jarvo panel` albo instalacja (N02)
  status [--json]      serwis z kanału nadzorcy (bez niego z <stan>/nadzorca.json), wersje, autostart, porty (N03)
  panel                startuje serwis, gdy nie działa, czeka na panel i otwiera go w przeglądarce (N06)
  chat                 rozmowa w terminalu: `hermes -p <profil> chat` w środowisku Jarva, tryb zgód w JARVO_TRYB_ZGOD
                       (sekcja d; tryb egzekwuje wtyczka zgód z etapu E4)
  logs [usługa] [-f]   logi nadzorcy i usług (<logi>) i Hermesa (<dane>/logs) (N04)
  autostart on|off|status                                                                        (N08)
  doctor [--json]      diagnoza z polską radą przy każdym wyniku (N10): korzeń, miejsce, Python i SQLite, uv,
                       Hermes wobec pinu, porty, brama API (klucz w <dane>/.env, GET /health), narzędzia, venvy
                       i modele z narzedzia.json, programy floty, autostart, polecenie jarvo, git (Windows: z Git Bash)
  version, help        wersja kodu i przypięty Hermes (też --wersja) / pomoc, także jednego polecenia (N16)
  update, uninstall, migruj: w budowie (etapy E4, E13, E12), kod 2

Panel liczy się tylko NASZ: /api/status z hermes_home = <dane> tej instalacji (instalator.stan_panelu). Port 9119
może trzymać stara flota z WSL albo prywatny Hermes właściciela; wtedy polecenie mówi, kto trzyma port.

Na starcie procesu (Windows) NoDefaultCurrentDirectoryInExePath=1: shutil.which i cmd.exe nie szukają programów
w katalogu bieżącym. Bez konsoli (pythonw.exe z Harmonogramu) wyjście i błędy idą do <logi>/serwis-start.log.
Zmienne instalacji z <stan>/ustawienia.json (JARVO_PANEL_PORT) obowiązują, gdy nie ma ich w otoczeniu.

Moduły nadzorcy, Hermesa, autostartu i dziennika zmian hosta ładujemy dopiero przy użyciu (instalator.modul), więc
`jarvo --help`, status i doctor działają też na pustym katalogu i przy niepełnej instalacji. Status i doctor niczego
nie zapisują. Wszystko, co dotyka komputera, idzie przez instalator.Otoczenie (atrapy w testach).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

from . import instalator, manifest, sciezki, srodowisko
from .instalator import (Otoczenie, _uruchom, adres_panelu, kto_slucha, port_panelu, port_zajety,  # noqa: F401
                         stan_serwisu)
from .sciezki import MACOS, WINDOWS, BladUkladu, Uklad

TRYBY = ("pytaj", "projekt", "pelny")        # sekcja (d); domyślny „projekt” (decyzja I08)
PROFIL = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")   # jak _PROFILE_NAME_RE w hermes_cli/main.py
SQLITE_MIN = (3, 51, 3)                      # błąd WAL-reset naprawiony w 3.51.3 (hermes_state_wal.py)
PORTY = (("panel", None), ("API bramy", None), ("podgląd HQ", 9120), ("ekran telefonu", 9122))
NASZE_PORTY = {"panel", "API bramy"}         # bez działającego serwisu muszą być wolne
CZAS_STOPU = instalator.CZAS_STOPU
W_BUDOWIE = {
    "update": ("E4", "procedura z docs/NATYWNIE.md (c4): nowa wersja obok starej, drenaż bramy, przełączenie i "
                     "powrót przy błędzie. Do tego czasu nową wersję daje ponowne polecenie instalacji (stare pliki "
                     "zostają, gotowe kroki są pomijane)."),
    "uninstall": ("E13", "stop, cofnięcie dziennika zmian hosta od końca, usunięcie programu; dane tylko z --all."),
    "migruj": ("E12", "przeniesienie danych ze starej instalacji z Dockerem i WSL (docs/NATYWNIE.md, sekcja f)."),
}
BOOTSTRAP = "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/jarvo/bootstrap"
RADA_INSTALACJI = ("Zainstaluj Jarvo jednym poleceniem: "
                   + (f"irm {BOOTSTRAP}/install.ps1 | iex (PowerShell)" if WINDOWS else
                      f"curl -fsSL {BOOTSTRAP}/install.sh | bash")
                   + "; w kopii repo: python -m jarvo instaluj. Inny katalog: ustaw JARVO_ROOT.")


# ---------------------------------------------------------------- argparse po polsku

_PO_POLSKU = {
    "usage: ": "użycie: ",
    "positional arguments": "argumenty",
    "options": "opcje",
    "optional arguments": "opcje",
    "show this help message and exit": "pokaż tę pomoc i zakończ",
    "%(prog)s: error: %(message)s\n": "%(prog)s: błąd: %(message)s\n",
    "unrecognized arguments: %s": "nieznane argumenty: %s",
    "the following arguments are required: %s": "brakuje argumentów: %s",
    "invalid choice: %(value)r (choose from %(choices)s)": "nieznana wartość %(value)r (do wyboru: %(choices)s)",
    "argument %(argument_name)s: %(message)s": "argument %(argument_name)s: %(message)s",
    "expected one argument": "brakuje wartości",
    "invalid %(type)s value: %(value)r": "zła wartość: %(value)r",
    "ambiguous option: %(option)s could match %(matches)s": "niejednoznaczna opcja %(option)s: pasuje do %(matches)s",
}


@contextlib.contextmanager
def _po_polsku():
    """Napisy argparse (użycie, opcje, błędy) po polsku tylko na czas budowy parsera i parsowania: argparse bierze
    je przez gettext w chwili użycia, a podmiana na stałe zmieniłaby argparse w całym procesie (np. w testach)."""
    stary = argparse._
    argparse._ = lambda tekst: _PO_POLSKU.get(tekst, tekst)
    try:
        yield
    finally:
        argparse._ = stary


def _profil(wartosc: str) -> str:
    wartosc = wartosc.strip().casefold()
    if not PROFIL.match(wartosc):
        raise argparse.ArgumentTypeError(f"{wartosc!r} to nie nazwa profilu (małe litery, cyfry, - i _)")
    return wartosc


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvo", description="Jarvo natywnie: flota agentów na Twoim komputerze. "
                                "Samo `jarvo` otwiera rozmowę (jarvo chat).")
    p.add_argument("--wersja", action="store_true", help="wersja kodu Jarva i przypięty Hermes")
    p.add_argument("--korzen", metavar="KATALOG", help="korzeń instalacji (jak JARVO_ROOT; tylko na początku)")
    sub = p.add_subparsers(dest="polecenie", metavar="polecenie", title="polecenia")

    s = sub.add_parser("instaluj", help="instalacja albo naprawa (bootstrap woła ją sam)",
                       description="Instaluje albo naprawia Jarvo w katalogu z JARVO_ROOT (domyślnie %LOCALAPPDATA%"
                       "\\Jarvo, ~/.jarvo albo ~/.local/share/jarvo). Drugi przebieg niczego nie zmienia.")
    s.add_argument("--bez-autostartu", action="store_true", help="bez startu nadzorcy po zalogowaniu")
    s.add_argument("--web-lokalnie", action="store_true",
                   help="zbuduj front panelu od nowa na tym komputerze (npm), także gdy jest gotowy")
    s.add_argument("--bez-startu", action="store_true", help="nie uruchamiaj serwisu i nie czekaj na panel")
    s.add_argument("--bez-path", action="store_true",
                   help="polecenie jarvo tylko w <korzeń>/bin, bez PATH i plików startowych powłoki (próby)")
    s.set_defaults(funkcja=polecenie_instaluj)

    s = sub.add_parser("serwis", add_help=False, help="nadzorca bramy i panelu (pierwszy plan; autostart w tle)",
                       description="Argumenty idą do nadzorcy (jarvo serwis --help).")
    s.set_defaults(funkcja=polecenie_serwis)

    s = sub.add_parser("up", help="uruchom serwis w tle i poczekaj na panel")
    s.set_defaults(funkcja=polecenie_up)
    s = sub.add_parser("down", help="zatrzymaj serwis (brama kończy trwające tury); wstanie dopiero po jarvo up")
    s.set_defaults(funkcja=polecenie_down)

    s = sub.add_parser("status", help="czy serwis działa: brama, panel, wersje, autostart, porty")
    s.add_argument("--json", action="store_true", help="wynik w JSON (CI, skrypty)")
    s.set_defaults(funkcja=polecenie_status)

    s = sub.add_parser("panel", help="otwiera panel w przeglądarce (startuje serwis, gdy trzeba)")
    s.add_argument("--bez-przegladarki", action="store_true", help="tylko uruchom i wypisz adres")
    s.set_defaults(funkcja=polecenie_panel)

    s = sub.add_parser("chat", help="rozmowa z Jarvem w terminalu (domyślne polecenie)", allow_abbrev=False,
                       description="Rozmowa przez Hermesa w środowisku Jarva. Dodatkowe argumenty idą do "
                       "`hermes chat` (np. --resume <id>).")
    s.add_argument("--tryb", choices=TRYBY, default="projekt",
                   help="zgody: pytaj = o każdy zapis i polecenie, projekt = bez pytania w folderze projektu "
                        "(domyślny), pelny = bez pytań na tę sesję")
    s.add_argument("--profil", type=_profil, default="jarvo", help="profil agenta (domyślnie jarvo)")
    s.set_defaults(funkcja=polecenie_chat)

    s = sub.add_parser("logs", help="logi nadzorcy i Hermesa")
    s.add_argument("usluga", nargs="?", metavar="usługa",
                   help="brama, panel, nadzorca, instalacja albo hermes (Hermes: hermes-agent, hermes-gateway…)")
    s.add_argument("-f", "--sledz", action="store_true", help="pokazuj nowe wiersze na bieżąco (Ctrl+C kończy)")
    s.add_argument("-n", "--wiersze", type=int, default=None, help="ile ostatnich wierszy (domyślnie 40)")
    s.set_defaults(funkcja=polecenie_logs)

    s = sub.add_parser("autostart", help="start nadzorcy po zalogowaniu: on, off, status")
    s.add_argument("akcja", choices=("on", "off", "status"), metavar="on|off|status")
    s.set_defaults(funkcja=polecenie_autostart)

    s = sub.add_parser("doctor", help="diagnoza instalacji z radą przy każdym wyniku")
    s.add_argument("--json", action="store_true", help="wynik w JSON (CI)")
    s.set_defaults(funkcja=polecenie_doctor)

    s = sub.add_parser("version", aliases=["wersja"], help="wersja kodu Jarva i przypięty Hermes (jak --wersja)")
    s.set_defaults(funkcja=lambda u, _a, _r, _ot: polecenie_wersja(u))
    s = sub.add_parser("help", aliases=["pomoc"], help="pomoc: lista poleceń albo opis jednego (jarvo help status)")
    s.add_argument("temat", nargs="?", metavar="polecenie", help="polecenie, którego opis pokazać")
    s.set_defaults(funkcja=polecenie_help)

    for nazwa, (etap, _opis) in W_BUDOWIE.items():
        s = sub.add_parser(nazwa, add_help=False, help=f"w budowie (etap {etap})")
        s.set_defaults(funkcja=polecenie_w_budowie)
    return p


# ---------------------------------------------------------------- start procesu

def _przygotuj_proces() -> None:
    """Windows: shutil.which (Python 3.12+) i cmd.exe nie szukają programu w katalogu bieżącym (obcy uv.exe albo
    git.cmd w katalogu, w którym wpisano polecenie, nie wygra z prawdziwym); dziedziczą to też procesy potomne."""
    if WINDOWS:
        os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"


def _bezpieczne_wyjscie() -> None:
    """Polskie znaki nie wywracają polecenia, gdy wyjście idzie do pliku w stronie kodowej bez nich
    (launcher i tak ustawia -X utf8; to zapas dla `python -m jarvo` z przekierowaniem)."""
    for strumien in (sys.stdout, sys.stderr):
        kod = (getattr(strumien, "encoding", "") or "").lower().replace("-", "").replace("_", "")
        if strumien is not None and kod not in ("utf8", "utf8sig"):
            with contextlib.suppress(AttributeError, ValueError, OSError):
                strumien.reconfigure(errors="replace")


class _LogBledow(io.TextIOBase):
    """sys.stdout i sys.stderr procesu bez konsoli (pythonw.exe z Harmonogramu: oba są None, więc komunikaty i błędy
    startu `jarvo serwis` by zginęły). Plik otwieramy przy pierwszym zapisie, z nagłówkiem: czas, PID i polecenie."""

    def __init__(self, sciezka: Path, argv: list[str]):
        super().__init__()
        self.sciezka, self.argv, self._f = sciezka, list(argv), None

    def writable(self) -> bool:
        return True

    def write(self, tekst: str) -> int:
        if not tekst:
            return 0
        if self._f is None:
            try:
                self.sciezka.parent.mkdir(parents=True, exist_ok=True)
                instalator.przytnij_log(self.sciezka)
                self._f = open(self.sciezka, "a", encoding="utf-8", errors="replace", buffering=1)
                self._f.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} jarvo {' '.join(self.argv)} "
                              f"(PID {os.getpid()}, bez konsoli)\n")
            except OSError:
                return len(tekst)
        with contextlib.suppress(OSError, ValueError):
            self._f.write(tekst)
        return len(tekst)

    def flush(self) -> None:
        if self._f is not None:
            with contextlib.suppress(OSError, ValueError):
                self._f.flush()

    def close(self) -> None:
        if self._f is not None:
            with contextlib.suppress(OSError, ValueError):
                self._f.close()
        super().close()


def _log_bez_konsoli(env: dict) -> Path:
    """`<logi>/serwis-start.log` instalacji, a gdy korzenia jeszcze nie ma: plik w katalogu tymczasowym."""
    try:
        u = sciezki.uklad(env)
        if u.root.is_dir():
            return u.logi / instalator.LOG_STARTU
    except BladUkladu:
        pass
    return Path(tempfile.gettempdir()) / "jarvo-serwis-start.log"


def _zdejmij_korzen(argv: list[str]) -> tuple[str | None, list[str]]:
    if argv[:1] == ["--korzen"] and len(argv) >= 2:
        return argv[1], argv[2:]
    if argv[:1] and argv[0].startswith("--korzen="):
        return argv[0].split("=", 1)[1], argv[1:]
    return None, argv


def _ustal_korzen(ot: Otoczenie, korzen: str | None, prawdziwy: bool) -> None:
    """--korzen albo JARVO_ROOT jako ścieżka bezwzględna (względną liczymy od katalogu bieżącego, `~` rozwijamy):
    trafia do jarvo.cmd i argv autostartu, a te startują w innym katalogu."""
    wartosc = korzen or ot.env.get("JARVO_ROOT")
    if not wartosc:
        return
    pelna = os.path.abspath(os.path.expanduser(wartosc))
    ot.env["JARVO_ROOT"] = pelna
    if prawdziwy:                                 # nadzorca i procesy potomne biorą korzeń z os.environ
        os.environ["JARVO_ROOT"] = pelna


def _uklad(ot: Otoczenie, polecenie: str | None) -> Uklad | None:
    """Układ katalogów. Korzeń z polskimi znakami, którego jeszcze nie ma (krótką nazwę 8.3 system poda dopiero dla
    istniejącego katalogu, c1): `instaluj` go zakłada, a status, doctor i reszta mówią „nie zainstalowane” bez
    tworzenia czegokolwiek. None = błąd (komunikat wypisany)."""
    try:
        return sciezki.uklad(ot.env)
    except BladUkladu as e:
        blad = e
    root = sciezki._korzen(ot.env)
    if not root.exists():
        if polecenie not in ("instaluj", "up"):              # `up` bez instalacji instaluje (N02)
            return Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                         logi=root / "logi", cache=root / "cache", build=root / "build")
        try:
            root.mkdir(parents=True, exist_ok=True)
            return sciezki.uklad(ot.env)
        except (OSError, BladUkladu) as e:
            blad = e
    print(f"BŁĄD: {blad}", file=sys.stderr)
    return None


def main(argv: list[str] | None = None, *, otoczenie: Otoczenie | None = None) -> int:
    """`jarvo <polecenie>`; kod wyjścia: 0 dobrze, 1 błąd albo serwis nie działa (status), 2 złe argumenty
    i polecenia w budowie, 130 przerwane przez Ctrl+C."""
    prawdziwy = otoczenie is None
    if prawdziwy:
        _przygotuj_proces()
    _bezpieczne_wyjscie()
    korzen, argv = _zdejmij_korzen(list(sys.argv[1:] if argv is None else argv))
    ot = otoczenie or Otoczenie()
    _ustal_korzen(ot, korzen, prawdziwy)
    if prawdziwy and (sys.stderr is None or sys.stdout is None):   # pythonw.exe bez konsoli: do serwis-start.log
        log = _LogBledow(_log_bez_konsoli(ot.env), argv)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--wersja")):
        argv = ["chat", *argv]                    # samo `jarvo` albo same opcje rozmowy (`jarvo --tryb pytaj`)
    try:
        with _po_polsku():
            parser = _parser()
            args, reszta = parser.parse_known_args(argv)
            if reszta and args.polecenie not in ("chat", "serwis", *W_BUDOWIE):
                parser.error(f"nieznane argumenty: {' '.join(reszta)}")
    except SystemExit as e:                       # --help albo błąd argumentów: argparse już wypisał komunikat
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    u = _uklad(ot, args.polecenie)
    if u is None:
        return 1
    for klucz, wartosc in instalator.ustawienia(u).items():   # port panelu z instalacji (autostart nie zna sesji)
        if not str(ot.env.get(klucz) or "").strip():
            ot.env[klucz] = wartosc
            if prawdziwy:
                os.environ[klucz] = wartosc
    if args.wersja:
        return polecenie_wersja(u)
    if reszta[:1] == ["--"]:
        reszta = reszta[1:]
    try:
        return args.funkcja(u, args, reszta, ot)
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as e:                        # noqa: BLE001 - błąd polecenia: komunikat zamiast śladu stosu
        if ot.env.get("JARVO_DEBUG") == "1":
            raise
        print(f"BŁĄD: {type(e).__name__}: {e} (pełny ślad: JARVO_DEBUG=1)", file=sys.stderr)
        return 1


# ---------------------------------------------------------------- polecenia

def _zainstalowane(u: Uklad) -> bool:
    return bool(srodowisko.biezace(u).get("app"))


def _brak_instalacji(u: Uklad) -> int:
    print(f"Jarvo nie jest zainstalowane w {u.root}.\n{RADA_INSTALACJI}", file=sys.stderr)
    return 1


def polecenie_wersja(u: Uklad) -> int:
    app = instalator.katalog_aplikacji(u)
    try:
        pin = manifest.hermes(app)
        hermes = f"Hermes {pin.get('wersja')} ({pin.get('tag')}, {str(pin.get('commit'))[:7]})"
    except (OSError, ValueError, KeyError):
        hermes = "Hermes: brak manifestu"
    print(f"Jarvo {instalator.wersja_aplikacji(app)} ({app}); {hermes}")
    return 0


def polecenie_help(_u: Uklad, a, _reszta, _ot: Otoczenie) -> int:
    """`jarvo help [polecenie]`: pomoc całości albo jednego polecenia (jak `jarvo <polecenie> --help`)."""
    with _po_polsku():
        parser = _parser()
        polecenia = next(ak.choices for ak in parser._actions if isinstance(ak, argparse._SubParsersAction))
        if not a.temat:
            parser.print_help()
            return 0
        if a.temat not in polecenia:
            print(f"Nie znam polecenia {a.temat!r}. Są: {', '.join(sorted(polecenia))}.", file=sys.stderr)
            return 2
        if a.temat == "serwis":                   # argumenty idą do nadzorcy, on ma własną pomoc
            print("jarvo serwis: nadzorca bramy i panelu. Jego opcje: jarvo serwis --help")
            return 0
        polecenia[a.temat].print_help()
    return 0


def polecenie_instaluj(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    return instalator.instaluj(u, instalator.APP, autostart=not a.bez_autostartu, web_lokalnie=a.web_lokalnie,
                               start=not a.bez_startu, bez_path=a.bez_path, otoczenie=ot)


def polecenie_serwis(u: Uklad, _a, reszta, ot: Otoczenie) -> int:
    try:
        nadzorca = ot.modul("nadzorca")
    except ImportError as e:
        print(f"BŁĄD: brak modułu nadzorcy ({e}). Instalacja jest niepełna: uruchom ją ponownie.", file=sys.stderr)
        return 1
    with _po_polsku():                            # pomoc i błędy argumentów nadzorcy też po polsku
        try:
            return int(nadzorca.main(list(reszta)) or 0)
        except SystemExit as e:                   # --help i złe argumenty z argparse nadzorcy
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)


def polecenie_w_budowie(_u: Uklad, a, _reszta, _ot: Otoczenie) -> int:
    etap, opis = W_BUDOWIE[a.polecenie]
    print(f"jarvo {a.polecenie} jest w budowie (etap {etap} planu docs/NATYWNIE.md): {opis}", file=sys.stderr)
    return 2


def uruchom_na_pierwszym_planie(argv: list[str], env: dict) -> int:
    """Program interaktywny w tym terminalu. POSIX: exec (sygnały, kod wyjścia i terminal przechodzą wprost).
    Windows: proces potomny, a ten ignoruje Ctrl+C: dostaje je cała konsola, a przerywa tylko rozmowa (Hermes)."""
    sys.stdout.flush()
    sys.stderr.flush()
    if not WINDOWS:
        os.execvpe(argv[0], argv, env)
    stary = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        return subprocess.Popen(argv, env=env).wait()
    finally:
        signal.signal(signal.SIGINT, stary)


def polecenie_chat(u: Uklad, a, reszta, ot: Otoczenie) -> int:
    biez = srodowisko.biezace(u)
    if not biez.get("hermes"):
        return _brak_instalacji(u)
    if a.profil != "default" and not (u.dane / "profiles" / a.profil).is_dir():
        print(f"Profil {a.profil} nie jest jeszcze zainstalowany (profile floty instaluje etap E4). Rozmowa "
              "z samym Hermesem: jarvo chat --profil default", file=sys.stderr)
        return 1
    try:
        hermes = ot.modul("hermes")
    except ImportError as e:
        print(f"BŁĄD: brak modułu Hermesa ({e}). Uruchom instalację ponownie.", file=sys.stderr)
        return 1
    if a.tryb == "pelny" and a.profil == "jarvo-operator":
        print("Tryb pełny nie jest dostępny dla jarvo-operator (praca na ekranie zawsze z pytaniem o zgodę).",
              file=sys.stderr)
        return 1
    env = srodowisko.srodowisko(u, ot.env)
    env.pop("HERMES_YOLO_MODE", None)            # tryb pełny tylko flagą --yolo tej jednej sesji, nigdy w środowisku
    env["JARVO_TRYB_ZGOD"] = a.tryb              # odczytuje go wtyczka jarvo-zgody
    folder = os.getcwd()                         # folder, w którym właściciel wpisał polecenie (tryb „projekt”)
    env["JARVO_FOLDER_PROJEKTU"] = folder
    # H20: narzędzia plików Hermesa piszą tylko pod HERMES_WRITE_SAFE_ROOT (lista z os.pathsep, agent/file_safety.py);
    # w czacie dochodzi folder projektu, inaczej zapis, na który tryb (albo właściciel w trybie pytaj) się zgodził,
    # i tak kończy się „Write denied … outside HERMES_WRITE_SAFE_ROOT” (sprawdzone 2026-10-25 na Windows 11)
    env["HERMES_WRITE_SAFE_ROOT"] = os.pathsep.join(dict.fromkeys([str(u.dane), folder]))
    yolo = ["--yolo"] if a.tryb == "pelny" else []
    argv = [str(x) for x in hermes.argv_hermesa(Path(biez["hermes"]), "-p", a.profil, "chat", *yolo, *reszta)]
    return int((ot.na_pierwszym_planie or uruchom_na_pierwszym_planie)(argv, env))


def _serwis_z_panelem(u: Uklad, ot: Otoczenie) -> str | None:
    """Panel tej instalacji odpowiada albo serwis rusza w tle i panel wstaje; adres albo None (komunikat już
    wypisany). Najpierw zdejmujemy znacznik `jarvo down`. Port zajęty przez inny program (stara flota z WSL,
    prywatny Hermes) to od razu błąd z radą: panel Jarva na nim nie wstanie."""
    try:
        instalator.zdejmij_zatrzymanie(u, ot)
    except instalator.BladInstalacji as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return None
    adres = adres_panelu(ot.env)
    panel, opis = instalator.stan_panelu(u, ot)
    if panel == "nasz":
        return adres
    stan, powod = stan_serwisu(u, ot)
    if stan is None and powod.startswith("brak modułu"):
        print(f"BŁĄD: {powod}. Uruchom instalację ponownie.", file=sys.stderr)
        return None
    if panel == "obcy":
        print(f"BŁĄD: {instalator.opis_obcego_portu(port_panelu(ot.env), opis, ot)}", file=sys.stderr)
        return None
    try:
        if stan is None:
            print("Serwis nie działa: uruchamiam go…")
            print(f"Serwis uruchomiony {instalator.uruchom_serwis(u, ot, print)}.")
        return instalator.czekaj_na_panel(u, ot, print)
    except instalator.BladInstalacji as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return None


def polecenie_panel(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    adres = _serwis_z_panelem(u, ot)
    if adres is None:
        return 1
    print(f"Panel: {adres}")
    if not a.bez_przegladarki:
        (ot.otworz or webbrowser.open)(adres)
    return 0


def polecenie_up(u: Uklad, _a, _reszta, ot: Otoczenie) -> int:
    if not _zainstalowane(u):
        # N02: `up` bez instalacji instaluje (jak `jarvo instaluj`, z autostartem; serwis i panel na końcu)
        print(f"Jarvo nie jest zainstalowane w {u.root}: instaluję (jak `jarvo instaluj`).")
        kod = instalator.instaluj(u, instalator.APP, otoczenie=ot)
        if kod == 0:
            print(f"Jarvo działa. Panel: {adres_panelu(ot.env)}")
        return kod
    adres = _serwis_z_panelem(u, ot)
    if adres is None:
        return 1
    print(f"Jarvo działa. Panel: {adres}")
    return 0


def polecenie_down(u: Uklad, _a, _reszta, ot: Otoczenie) -> int:
    """Zatrzymanie ze znacznikiem `<stan>/zatrzymany.json`: nadzorca nie wstanie sam (zapasowe wyzwalacze
    Harmonogramu co 5 minut, odblokowanie, logowanie), aż `jarvo up`, `jarvo panel` albo instalacja go zdejmie.
    Najpierw znacznik (nowy nadzorca, który go zobaczy, zatrzymuje się sam), potem stop kanałem i czekanie."""
    if not u.stan.is_dir():
        print("Serwis nie działa (Jarvo nie jest zainstalowane w tym katalogu).")
        return 0
    stan, powod = stan_serwisu(u, ot)
    try:
        zna = instalator.oznacz_zatrzymanie(u, ot, "jarvo down")
    except instalator.BladInstalacji as e:
        print(f"Uwaga: {e}.", file=sys.stderr)
        zna = None
    if stan is None:
        print(f"Serwis nie działa ({powod}).")
    else:
        print("Zatrzymuję serwis (brama kończy trwające tury)…")
        try:
            instalator.zatrzymaj_serwis(u, ot, "jarvo down")
        except instalator.BladInstalacji as e:
            print(f"BŁĄD: {e}", file=sys.stderr)
            return 1
        print("Serwis zatrzymany.")
    if zna:
        print("Nie wstanie sam, także z autostartu, dopóki nie wpiszesz `jarvo up` albo `jarvo panel`.")
    elif zna is False:
        print("Uwaga: ta wersja nadzorcy nie zna znacznika zatrzymania, więc autostart może go podnieść (Windows: "
              "zapasowe wyzwalacze co 5 minut). Wznowienie: jarvo up; na stałe bez startu: jarvo autostart off.")
    return 0


# ---------------------------------------------------------------- status

def _porty(u: Uklad, env: dict) -> list[tuple[str, int]]:
    """Porty Jarva: panel (JARVO_PANEL_PORT albo 9119), API bramy (instalator.port_api: JARVO_API_PORT, port
    z `<dane>/.env` albo 8642), podgląd HQ i ekran telefonu."""
    dynamiczne = {"panel": port_panelu(env), "API bramy": instalator.port_api(u, env)}
    return [(nazwa, port if port else dynamiczne[nazwa]) for nazwa, port in PORTY]


def zbierz_status(u: Uklad, ot: Otoczenie) -> dict:
    biez = srodowisko.biezace(u)
    stan, powod = stan_serwisu(u, ot)
    z_pliku: dict = {}
    if stan is None and u.stan.is_dir():
        with contextlib.suppress(Exception):     # brak modułu albo uszkodzony plik: zostaje tylko powód
            z_pliku = dict(ot.modul("nadzorca").stan_z_pliku(u) or {})
    porty = {str(port): {"nazwa": nazwa, "zajety": port_zajety(port)} for nazwa, port in _porty(u, ot.env)}
    panel = {"stan": "brak", "opis": "nikt nie słucha"}
    if porty.get(str(port_panelu(ot.env)), {}).get("zajety"):
        panel = dict(zip(("stan", "opis"), instalator.stan_panelu(u, ot)))
    return {
        "root": str(u.root),
        "zainstalowane": bool(biez.get("app")),
        "wersja": biez.get("wersja"), "app": biez.get("app"), "hermes": biez.get("hermes"),
        "narzedzia": {n: w.get("wersja") for n, w in sorted(srodowisko.narzedzia(u).items()) if isinstance(w, dict)},
        "serwis": {"dziala": stan is not None, "powod": powod, "stan": stan if stan is not None else z_pliku,
                   "z_pliku": stan is None and bool(z_pliku),
                   "proces_zyje": bool(stan is not None or z_pliku.get("dziala")),
                   "zatrzymanie": instalator.zatrzymanie(u) if u.stan.is_dir() else None},
        "autostart": instalator.stan_autostartu(u, ot),
        "porty": porty,
        "panel": adres_panelu(ot.env),
        "panel_jarva": panel,
    }


def _opis_uslug(stan: dict) -> list[str]:
    """Usługi nadzorcy (`{"uslugi": {nazwa: {"stan", "pid", "ostatni_kod", "gotowa", "powod", ...}}}`) w wierszach
    `nazwa: stan, PID …`; obcy kształt danych pokazujemy jako klucz: wartość."""
    uslugi = stan.get("uslugi")
    if isinstance(uslugi, dict):
        uslugi = [{"nazwa": k, **(v if isinstance(v, dict) else {"stan": v})} for k, v in uslugi.items()]
    if not isinstance(uslugi, list):
        return [f"    {k}: {v}" for k, v in stan.items() if not isinstance(v, (dict, list))]
    wiersze = []
    for us in uslugi:
        if not isinstance(us, dict):
            continue
        czesci = [str(us.get("stan", "?"))]
        if us.get("gotowa") is True:
            czesci.append("gotowa")
        for klucz, etykieta in (("pid", "PID"), ("ostatni_kod", "kod"), ("kod", "kod"), ("restarty", "restarty"),
                                ("powod", "powód")):
            wartosc = us.get(klucz)
            if wartosc is None or wartosc == "" or (klucz in ("pid", "restarty") and not wartosc):
                continue
            czesci.append(f"{etykieta} {wartosc}")
        wiersze.append(f"    {us.get('nazwa', '?')}: {', '.join(czesci)}")
    return wiersze


def _opis_autostartu(a: dict) -> str:
    if a.get("sprawdzony") is False:
        return f"nie sprawdzony ({a.get('powod', '?')})"
    if a.get("opis"):                             # jarvo/autostart.py składa gotowy wiersz dla statusu
        return str(a["opis"])
    if "wlaczony" in a:
        return "włączony" if a["wlaczony"] else "wyłączony (jarvo autostart on)"
    return ", ".join(f"{k}: {v}" for k, v in a.items()) or "?"


def _opis_panelu(p: dict) -> str:
    if p.get("stan") == "nasz":
        return "odpowiada panel Jarva"
    if p.get("stan") == "obcy":
        return f"port trzyma inny program: {p.get('opis')}"
    return f"nie odpowiada ({p.get('opis')})"


def opis_statusu(r: dict) -> str:
    w = [f"Jarvo: {r['root']}"]
    if not r["zainstalowane"]:
        w.append(f"  instalacja: brak. {RADA_INSTALACJI}")
    else:
        w.append(f"  wersja:     {r.get('wersja') or '?'} ({r.get('app')})")
        w.append(f"  Hermes:     {r.get('hermes') or 'brak (instalacja niepełna)'}")
        if r["narzedzia"]:
            w.append("  narzędzia:  " + ", ".join(f"{n} {v}" for n, v in r["narzedzia"].items()))
    s = r["serwis"]
    z = s.get("zatrzymanie")
    if s["dziala"]:
        w.append("  serwis:     działa")
    elif z is not None:
        opis = ", ".join(str(z[k]) for k in ("powod", "kiedy") if z.get(k))
        w.append(f"  serwis:     zatrzymany{f' ({opis})' if opis else ''}: autostart go nie uruchomi, start: jarvo up"
                 + ("; ostatni stan z pliku:" if s["z_pliku"] else ""))
    elif s["proces_zyje"]:
        w.append(f"  serwis:     proces nadzorcy żyje, ale kanał nie odpowiada ({s['powod']}); ostatni stan z pliku:")
    else:
        w.append(f"  serwis:     nie działa ({s['powod']})" + ("; ostatni stan z pliku:" if s["z_pliku"] else ""))
    if s.get("stan"):
        w += _opis_uslug(s["stan"])
    w.append(f"  autostart:  {_opis_autostartu(r['autostart'])}")
    w.append("  porty:      " + ", ".join(f"{port} {'zajęty' if p['zajety'] else 'wolny'} ({p['nazwa']})"
                                          for port, p in r["porty"].items()))
    w.append(f"  panel:      {r['panel']} ({_opis_panelu(r.get('panel_jarva') or {})})")
    return "\n".join(w)


def polecenie_status(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    raport = zbierz_status(u, ot)
    print(json.dumps(raport, ensure_ascii=False, indent=2) if a.json else opis_statusu(raport))
    return 0 if raport["serwis"]["dziala"] else 1


# ---------------------------------------------------------------- logs

def pliki_logow(u: Uklad) -> dict[str, Path]:
    """Logi nadzorcy i usług (`<logi>/*.log`) i Hermesa (`<dane>/logs/*.log` jako hermes-<nazwa>)."""
    logi: dict[str, Path] = {}
    if u.logi.is_dir():
        logi.update({p.stem: p for p in sorted(u.logi.glob("*.log"))})
    if (u.dane / "logs").is_dir():
        logi.update({f"hermes-{p.stem}": p for p in sorted((u.dane / "logs").glob("*.log"))})
    return logi


def ogon(p: Path, n: int) -> list[str]:
    """Ostatnie `n` wierszy pliku bez czytania całości (logi mają do 10 MB)."""
    with open(p, "rb") as f:
        f.seek(0, os.SEEK_END)
        koniec = f.tell()
        blok, dane = 1 << 16, b""
        while koniec > 0 and dane.count(b"\n") <= n:
            start = max(0, koniec - blok)
            f.seek(start)
            dane = f.read(koniec - start) + dane
            koniec = start
    return dane.decode("utf-8", errors="replace").splitlines()[-n:] if n > 0 else []


def polecenie_logs(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    logi = pliki_logow(u)
    if not logi:
        print(f"Brak logów w {u.logi} i {u.dane / 'logs'} (serwis jeszcze nie działał?).", file=sys.stderr)
        return 1
    if a.usluga:
        wybrane = {k: p for k, p in logi.items() if k == a.usluga} or \
                  {k: p for k, p in logi.items() if k.startswith(a.usluga)}
        if not wybrane:
            print(f"Nie znam logu {a.usluga!r}. Są: {', '.join(logi)}.", file=sys.stderr)
            return 2
    else:
        wybrane = {k: p for k, p in logi.items() if not k.startswith("hermes-")} or logi
    n = a.wiersze if a.wiersze is not None else (40 if len(wybrane) > 1 else 100)
    for nazwa, p in wybrane.items():
        if len(wybrane) > 1:
            print(f"==> {nazwa} ({p}) <==")
        for wiersz in ogon(p, n):
            print(wiersz)
    if not a.usluga and any(k.startswith("hermes-") for k in logi):
        print("(logi Hermesa: jarvo logs hermes)")
    if a.sledz:
        return sledz_logi(wybrane, ot)
    return 0


def sledz_logi(pliki: dict[str, Path], ot: Otoczenie, *, obiegi: int | None = None) -> int:
    """`tail -f` dla kilku plików naraz; plik przycięty przy rotacji („kopiuj i przytnij”, c2) czytamy od nowa."""
    pozycje = {k: p.stat().st_size if p.exists() else 0 for k, p in pliki.items()}
    prefiks = len(pliki) > 1
    i = 0
    try:
        while obiegi is None or i < obiegi:
            i += 1
            for nazwa, p in pliki.items():
                try:
                    rozmiar = p.stat().st_size
                except OSError:
                    continue
                if rozmiar < pozycje[nazwa]:
                    pozycje[nazwa] = 0
                if rozmiar == pozycje[nazwa]:
                    continue
                with open(p, "rb") as f:
                    f.seek(pozycje[nazwa])
                    dane = f.read()
                kompletne = dane[:dane.rfind(b"\n") + 1]          # niepełny wiersz poczeka na koniec
                pozycje[nazwa] += len(kompletne)
                for wiersz in kompletne.decode("utf-8", errors="replace").splitlines():
                    print(f"[{nazwa}] {wiersz}" if prefiks else wiersz, flush=True)
            ot.czekaj(0.5)
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------- autostart

def polecenie_autostart(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    if a.akcja == "on" and not _zainstalowane(u):
        return _brak_instalacji(u)
    try:
        auto = ot.modul("autostart")
    except ImportError as e:
        print(f"BŁĄD: brak modułu autostartu ({e}). Uruchom instalację ponownie.", file=sys.stderr)
        return 1
    try:
        if a.akcja == "on":
            instalator.wywolaj(auto.wlacz, u, instalator.polecenie_jarva(u, "serwis", okno=False, env=ot.env),
                               env=ot.env)
        elif a.akcja == "off":
            instalator.wywolaj(auto.wylacz, u, env=ot.env)
    except instalator.bledy_autostartu(auto) as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        if a.akcja == "on":
            print(f"Rada: {instalator.rada_autostartu(False)}", file=sys.stderr)
        return 1
    print(f"Autostart: {_opis_autostartu(instalator.stan_autostartu(u, ot))}")
    return 0


# ---------------------------------------------------------------- doctor

def _wynik(nazwa: str, stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": nazwa, "stan": stan, "opis": opis, "rada": rada}


def _sqlite_ok(wersja: tuple) -> bool:
    return tuple(wersja) >= SQLITE_MIN


def _fts5_ok() -> bool:
    """FTS5 z remove_diacritics: wyszukiwanie skarbca bez polskich znaków („ges” znajduje „Gęś”)."""
    try:
        with contextlib.closing(sqlite3.connect(":memory:")) as con:
            con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')")
            con.execute("INSERT INTO t VALUES ('Gęś')")
            return con.execute("SELECT count(*) FROM t WHERE t MATCH 'ges'").fetchone()[0] == 1
    except sqlite3.Error:
        return False


def _bin(narz: dict, nazwa: str, program: str) -> Path | None:
    """Program narzędzia z narzedzia.json (katalogi `bin`, inaczej katalog wersji), sprawdzany wprost w tych
    katalogach: shutil.which na Windows zajrzałby najpierw do katalogu bieżącego (także z podanym path=)."""
    wpis = narz.get(nazwa) or {}
    nazwy = [program + r for r in (".exe", ".cmd", ".bat")] if WINDOWS else [program]
    for katalog in wpis.get("bin") or [wpis.get("katalog")]:
        if not katalog or not os.path.isabs(str(katalog)):
            continue
        for n in nazwy:
            p = Path(katalog) / n
            if p.is_file() and (WINDOWS or os.access(p, os.X_OK)):
                return p
    return None


def sprawdz_korzen(u: Uklad) -> dict:
    if not u.root.is_dir():
        return _wynik("korzeń", "blad", f"{u.root} nie istnieje: Jarvo nie jest tu zainstalowane", RADA_INSTALACJI)
    try:
        with tempfile.NamedTemporaryFile(dir=u.root, prefix=".doctor-", delete=True):
            pass
    except OSError as e:
        return _wynik("korzeń", "blad", f"{u.root}: brak zapisu ({e.strerror or e})",
                      "Sprawdź uprawnienia katalogu albo ustaw JARVO_ROOT na katalog w swoim profilu.")
    niski = str(u.root).lower()
    if "onedrive" in niski or "mobile documents" in niski or "icloud" in niski:
        return _wynik("korzeń", "uwaga", f"{u.root} leży w folderze synchronizowanym (OneDrive albo iCloud)",
                      "Bazy SQLite w trybie WAL psują się przy synchronizacji: przenieś Jarvo poza ten folder "
                      "(JARVO_ROOT na lokalny dysk) i zainstaluj ponownie.")
    if not str(u.program).isascii():
        return _wynik("korzeń", "blad", f"{u.program} ma znaki spoza ASCII",
                      "Ustaw JARVO_ROOT na katalog z samymi literami ASCII (np. C:\\Jarvo) i zainstaluj ponownie.")
    return _wynik("korzeń", "ok", f"{u.root} (zapis działa)")


def sprawdz_miejsce(u: Uklad) -> dict:
    p = u.root
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        wolne = shutil.disk_usage(p).free / 1e9
    except OSError as e:
        return _wynik("wolne miejsce", "uwaga", f"nie umiem sprawdzić ({e})", "Sprawdź dysk ręcznie.")
    opis = f"{wolne:.1f} GB wolnego na dysku z {p}"
    if wolne < instalator.MIN_MIEJSCA_GB:
        return _wynik("wolne miejsce", "blad", opis, f"Jarvo potrzebuje co najmniej {instalator.MIN_MIEJSCA_GB} GB "
                      f"(cała instalacja z flotą ok. {instalator.ROZMIAR_GB} GB): zwolnij miejsce albo ustaw "
                      "JARVO_ROOT na inny dysk.")
    if wolne < 10:
        return _wynik("wolne miejsce", "uwaga", opis, "Flota z narzędziami i modelami potrzebuje więcej (kilka GB "
                      "na filmy, przeglądarki i lektora): zwolnij miejsce, zanim je doinstalujesz.")
    return _wynik("wolne miejsce", "ok", opis)


def sprawdz_python(u: Uklad) -> dict:
    wersja = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info < (3, 12):
        return _wynik("Python", "blad", f"{wersja} ({sys.executable}) jest za stary",
                      "Polecenie jarvo potrzebuje Pythona 3.12+: uruchom je przez jarvo.cmd albo ~/.local/bin/jarvo "
                      "(Python 3.13 z instalacji).")
    jarva = instalator.python_jarva(u)
    if _zainstalowane(u) and Path(sys.executable).resolve() != jarva.resolve():
        return _wynik("Python", "uwaga", f"{wersja} ({sys.executable}), a nie Python Jarva ({jarva})",
                      "Doctor działa na innym Pythonie niż polecenie jarvo: wyniki SQLite mogą się różnić. "
                      "Uruchom `jarvo doctor` z nowego terminala.")
    return _wynik("Python", "ok", f"{wersja} ({sys.executable})")


def sprawdz_sqlite(u: Uklad) -> list[dict]:
    wyniki = []
    wersja = sqlite3.sqlite_version
    if not _sqlite_ok(sqlite3.sqlite_version_info):
        wyniki.append(_wynik("SQLite", "blad", f"{wersja} w {sys.executable}: ma błąd WAL-reset (potrzebne "
                             f"{'.'.join(map(str, SQLITE_MIN))}+)",
                             "Polecenie jarvo ma działać na Pythonie z instalacji (python-build-standalone 20261021, "
                             "SQLite 3.53): uruchom je przez jarvo.cmd albo ~/.local/bin/jarvo, a gdy to nie "
                             "pomoże, zainstaluj ponownie."))
    elif not _fts5_ok():
        wyniki.append(_wynik("SQLite", "blad", f"{wersja}: brak FTS5 z remove_diacritics",
                             "Wyszukiwanie skarbca bez polskich znaków nie zadziała: zainstaluj ponownie."))
    else:
        wyniki.append(_wynik("SQLite", "ok", f"{wersja} z FTS5 (remove_diacritics)"))
    checkout = srodowisko.biezace(u).get("hermes")
    python = srodowisko.hermes_python(Path(checkout)) if checkout else None
    if python and python.is_file():
        try:
            w = _uruchom([python, "-I", "-c", "import sqlite3; print(sqlite3.sqlite_version)"]).stdout.strip()
            ok = bool(re.fullmatch(r"\d+\.\d+\.\d+", w)) and _sqlite_ok(tuple(int(x) for x in w.split(".")))
        except (OSError, subprocess.SubprocessError):
            w, ok = "?", False
        wyniki.append(_wynik("SQLite Hermesa", "ok" if ok else "blad", f"{w} w {python}", "" if ok else
                             "Środowisko Hermesa ma być zbudowane na Pythonie z instalacji: zainstaluj ponownie."))
    return wyniki


def sprawdz_uv(u: Uklad, app: Path) -> dict:
    narz = srodowisko.narzedzia(u)
    uv = _bin(narz, "uv", "uv")
    if uv is None:
        return _wynik("uv", "blad", "brak (narzedzia.json nie zna uv albo nie ma pliku)",
                      "Uruchom instalację (jarvo instaluj albo polecenie jednej linii): uv pobierze się z sumą "
                      "z manifestu.")
    try:
        oczekiwana = manifest.wersja(manifest.wczytaj(app), "uv")
    except (OSError, ValueError, KeyError):
        oczekiwana = ""
    try:
        wyjscie = _uruchom([uv, "--version"]).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return _wynik("uv", "blad", f"{uv} się nie uruchamia ({e})", "Uruchom instalację ponownie.")
    if oczekiwana and oczekiwana not in wyjscie.split():
        return _wynik("uv", "uwaga", f"{wyjscie or '?'}, a manifest ma {oczekiwana}",
                      "Uruchom instalację ponownie: dobierze wersję z manifestu.")
    return _wynik("uv", "ok", f"{wyjscie} ({uv})")


def sprawdz_hermesa(u: Uklad, app: Path) -> dict:
    checkout = srodowisko.biezace(u).get("hermes")
    if not checkout:
        return _wynik("Hermes", "blad", "brak checkoutu w current.json", "Uruchom instalację (jarvo instaluj).")
    checkout = Path(checkout)
    try:
        pin = manifest.hermes(app)
    except (OSError, ValueError, KeyError):
        pin = {}
    head = instalator.head_gita(checkout)
    if not checkout.is_dir() or head is None:
        return _wynik("Hermes", "blad", f"{checkout}: brak checkoutu gita", "Uruchom instalację ponownie.")
    if pin.get("commit") and head != pin["commit"]:
        return _wynik("Hermes", "blad", f"{checkout}: commit {head[:12]}, a pin ma {str(pin['commit'])[:12]} "
                      f"({pin.get('tag', '?')})", "Uruchom instalację ponownie: zrobi checkout przypiętego commitu. "
                      "Nie używaj `hermes update` (ciągnie gałąź główną, H16).")
    if not srodowisko.hermes_python(checkout).is_file():
        return _wynik("Hermes", "blad", f"{checkout}: brak środowiska .venv", "Uruchom instalację ponownie "
                      "(uv sync --locked).")
    return _wynik("Hermes", "ok", f"{pin.get('wersja', '?')} ({head[:7]} = pin {pin.get('tag', '?')}) w {checkout}")


def _pidy_jarva(stan: dict | None) -> set[int]:
    """PID-y nadzorcy i jego usług (z dziećmi launchera venvu na Windows) z kanału nadzorcy."""
    pidy: set[int] = set()
    if not isinstance(stan, dict):
        return pidy
    n = stan.get("nadzorca")
    if isinstance(n, dict) and isinstance(n.get("pid"), int):
        pidy.add(n["pid"])
    uslugi = stan.get("uslugi")
    for us in (uslugi.values() if isinstance(uslugi, dict) else []):
        if isinstance(us, dict):
            if isinstance(us.get("pid"), int):
                pidy.add(us["pid"])
            pidy.update(p for p in us.get("pidy") or [] if isinstance(p, int))
    return pidy


def sprawdz_porty(u: Uklad, ot: Otoczenie, stan: dict | None = None) -> list[dict]:
    """Porty Jarva: wolne albo zajęte przez Jarvo. Panel rozpoznajemy po /api/status (stan_panelu), resztę po PID
    procesu, który słucha (sluchacz), wobec PID-ów usług z nadzorcy: sam zajęty port nie znaczy, że to Jarvo."""
    dziala = stan is not None
    nasze = _pidy_jarva(stan)
    wyniki = []
    for nazwa, port in _porty(u, ot.env):
        etykieta = f"port {port} ({nazwa})"
        if not port_zajety(port):
            if dziala and nazwa in NASZE_PORTY:
                usluga = "panel" if nazwa == "panel" else "brama"
                wyniki.append(_wynik(etykieta, "uwaga", "serwis działa, ale nikt nie słucha",
                                     f"Zobacz `jarvo logs {usluga}` i `jarvo status`."))
            else:
                wyniki.append(_wynik(etykieta, "ok", "wolny"))
            continue
        if nazwa == "panel":
            panel, opis = instalator.stan_panelu(u, ot)
            if panel == "nasz":
                wyniki.append(_wynik(etykieta, "ok", "panel Jarva"))
                continue
            if panel == "obcy":
                wyniki.append(_wynik(etykieta, "blad", f"zajęty: {opis}",
                                     instalator.opis_obcego_portu(port, opis, ot)))
                continue
        s = ot.sluchacz(port)
        if s and s[0] in nasze:
            wyniki.append(_wynik(etykieta, "ok", f"używa go Jarvo ({s[1]}, PID {s[0]})"))
            continue
        kto = f"{s[1]} (PID {s[0]})" if s else "inny program"
        rada = (f"Zamknij ten program albo zmień jego port; Jarvo potrzebuje {port} na 127.0.0.1."
                + (" Inny port panelu: JARVO_PANEL_PORT i polecenie instalacji jeszcze raz." if nazwa == "panel"
                   else ""))
        if dziala and s is None:
            wyniki.append(_wynik(etykieta, "uwaga", "zajęty; nie umiem sprawdzić, przez kogo (brak netstat albo "
                                 "lsof)", rada))
        else:
            wyniki.append(_wynik(etykieta, "blad" if nazwa in NASZE_PORTY and not dziala else "uwaga",
                                 f"zajęty przez {kto}" + (", nie przez usługę Jarva" if dziala else ""), rada))
    return wyniki


def sprawdz_autostart(u: Uklad, ot: Otoczenie) -> dict:
    if not _zainstalowane(u):
        return _wynik("autostart", "uwaga", "nie sprawdzony (brak instalacji)", "Po instalacji: jarvo autostart on.")
    stan = instalator.stan_autostartu(u, ot)
    if stan.get("sprawdzony") is False:
        return _wynik("autostart", "uwaga", _opis_autostartu(stan), "Uruchom instalację ponownie.")
    if not stan.get("wlaczony") or stan.get("nasz") is False:
        return _wynik("autostart", "uwaga", _opis_autostartu(stan), "Włącz: jarvo autostart on (bez tego serwis "
                      "trzeba uruchamiać ręcznie po każdym zalogowaniu: jarvo up).")
    return _wynik("autostart", "ok", _opis_autostartu(stan))


def sprawdz_polecenie(u: Uklad, ot: Otoczenie) -> dict:
    if not _zainstalowane(u):
        return _wynik("polecenie jarvo", "uwaga", "nie sprawdzone (brak instalacji)", "Po instalacji: nowe okno "
                      "terminala.")
    nasze = [u.root / "bin" / ("jarvo.cmd" if WINDOWS else "jarvo")]
    if not WINDOWS:
        nasze.insert(0, Path.home() / ".local" / "bin" / "jarvo")
    znalezione = shutil.which("jarvo", path=ot.env.get("PATH"))
    if znalezione is None:
        kiedy = ("otwórz nowe okno terminala" if WINDOWS else "otwórz nowe okno Terminala" if MACOS else
                 "zaloguj się ponownie (terminal w GNOME i KDE nie czyta ~/.profile, w którym jest blok PATH)")
        return _wynik("polecenie jarvo", "uwaga", f"nie ma go w PATH tego terminala (plik: {nasze[0]})",
                      f"PATH zmienia się dla nowych sesji: {kiedy}, albo uruchamiaj pełną ścieżką. Po instalacji "
                      "z --bez-path zawsze pełną ścieżką.")
    if all(Path(znalezione).resolve() != p.resolve() for p in nasze):
        return _wynik("polecenie jarvo", "uwaga", f"w PATH najpierw jest {znalezione}, a nie {nasze[0]}",
                      "To zwykle polecenie starej instalacji (Docker, WSL) albo innej kopii Jarva: usuń je albo "
                      "uruchamiaj tę pełną ścieżką. Migracja: etap E12.")
    return _wynik("polecenie jarvo", "ok", znalezione)


def sprawdz_git(u: Uklad, ot: Otoczenie) -> dict:
    """git: na Windows z manifestu (Git for Windows z Git Bash dla narzędzia terminal Hermesa, I05), na macOS
    i Linuksie z systemu (manifest ma tam `brak`)."""
    narz = srodowisko.narzedzia(u)
    if "git" in narz:
        git = _bin(narz, "git", "git")
        bash = Path(str((narz["git"].get("env") or {}).get("HERMES_GIT_BASH_PATH") or ""))
        if git is None:
            return _wynik("git", "blad", f"brak git.exe w {narz['git'].get('katalog')}",
                          "Uruchom instalację ponownie: Git for Windows pobierze się z sumą z manifestu.")
        if WINDOWS and not bash.is_file():
            return _wynik("git", "blad", f"{git}, ale bez Git Bash ({bash})",
                          "Narzędzie terminal agentów potrzebuje Git Bash: uruchom instalację ponownie.")
        return _wynik("git", "ok", f"{narz['git'].get('wersja')} ({git}" + (f", Git Bash {bash})" if WINDOWS else ")"))
    git = instalator.program_bezwzgledny(ot, "git")
    if git:
        return _wynik("git", "ok", git)
    rada = ("Uruchom instalację ponownie: Git for Windows z manifestu (I05)." if WINDOWS else
            "macOS: xcode-select --install; Linux: menedżer pakietów (np. sudo apt install git).")
    return _wynik("git", "uwaga", "brak w PATH (potrzebny do instalacji i aktualizacji Hermesa)", rada)


def sprawdz_narzedzia(u: Uklad) -> list[dict]:
    """Narzędzia, venvy, modele i programy floty z `<stan>/narzedzia.json`: czy są na dysku (bez uruchamiania)."""
    if not _zainstalowane(u):
        return []
    narz = srodowisko.narzedzia(u)
    brak, venvy, modele = [], [], []
    for nazwa, wpis in sorted(narz.items()):
        if not isinstance(wpis, dict):
            continue
        katalog = Path(str(wpis.get("katalog") or ""))
        if nazwa.startswith("venv-"):
            ok = Path(str(wpis.get("python") or "")).is_file()
            venvy.append(nazwa[5:])
        elif nazwa == "tesseract":
            ok = Path(str(wpis.get("program") or "")).is_file()
        else:
            ok = katalog.is_dir()
            if nazwa.startswith("model-"):
                modele.append(nazwa[6:])
        if not ok:
            brak.append(nazwa)
    wyniki = []
    if brak:
        wyniki.append(_wynik("narzędzia", "blad", f"brak na dysku: {', '.join(brak)}",
                             "Uruchom instalację ponownie: brakujące pobiorą się z sumą z manifestu."))
    else:
        wyniki.append(_wynik("narzędzia", "ok", f"{len(narz)} wpisów (venvy: {', '.join(venvy) or 'brak'}; modele: "
                             f"{', '.join(modele) or 'brak'})"))
    if "venv-narzedzia" in narz:
        from . import bin_floty
        programy = bin_floty.sprawdz(u)
        chce = [*bin_floty.NA_ZYWO, *(["tesseract"] if "tesseract" in narz else [])]
        braki = [p for p in chce if not programy.get(p)]
        wyniki.append(_wynik("programy floty", "blad" if braki else "ok",
                             f"brak: {', '.join(braki)} w {u.bin_floty}" if braki else
                             f"{', '.join(chce)} w {u.bin_floty}",
                             "Uruchom instalację ponownie (krok „Programy floty”)." if braki else ""))
    return wyniki


def sprawdz_brame(u: Uklad, ot: Otoczenie, stan: dict | None) -> dict:
    """API bramy (H05): klucz w `<dane>/.env` i brama słucha na 127.0.0.1:<port> (GET /health: hermes-agent)."""
    nazwa = "API bramy"
    if not _zainstalowane(u):
        return _wynik(nazwa, "uwaga", "nie sprawdzone (brak instalacji)", RADA_INSTALACJI)
    port = instalator.port_api(u, ot.env)
    if not instalator.klucz_api_dobry(instalator.czytaj_env(u.dane / ".env").get("API_SERVER_KEY", "")):
        return _wynik(nazwa, "blad", f"brak klucza API_SERVER_KEY w {u.dane / '.env'}: brama nie otworzy API",
                      "Uruchom instalację ponownie: dopisze klucz (krok „Klucz API bramy”).")
    if stan is None:
        return _wynik(nazwa, "uwaga", f"nie sprawdzone: serwis nie działa (port {port})", "Uruchom: jarvo up.")
    brama = (stan.get("uslugi") or {}).get("brama") if isinstance(stan.get("uslugi"), dict) else None
    odp = ot.zapytaj_http(f"http://127.0.0.1:{port}/health", 2.0)
    if odp and odp[0] == 200 and isinstance(odp[1], dict) and odp[1].get("platform") == "hermes-agent":
        return _wynik(nazwa, "ok", f"brama słucha na http://127.0.0.1:{port} (Hermes {odp[1].get('version', '?')})")
    opis = "nikt nie odpowiada" if odp is None else f"odpowiedź HTTP {odp[0]} nie od bramy Hermesa"
    stan_bramy = (brama or {}).get("stan") if isinstance(brama, dict) else None
    return _wynik(nazwa, "blad", f"http://127.0.0.1:{port}/health: {opis} (brama: {stan_bramy or '?'})",
                  "Zobacz `jarvo logs brama` (np. port zajęty przez innego Hermesa albo zły klucz), potem `jarvo down` "
                  "i `jarvo up`; inny port: JARVO_API_PORT i polecenie instalacji jeszcze raz.")


def zbierz_diagnoze(u: Uklad, ot: Otoczenie) -> dict:
    app = instalator.katalog_aplikacji(u)
    stan, _ = stan_serwisu(u, ot)
    wyniki = [sprawdz_korzen(u), sprawdz_miejsce(u), sprawdz_python(u), *sprawdz_sqlite(u), sprawdz_uv(u, app),
              sprawdz_hermesa(u, app), *sprawdz_porty(u, ot, stan), sprawdz_brame(u, ot, stan),
              *sprawdz_narzedzia(u), sprawdz_autostart(u, ot), sprawdz_polecenie(u, ot), sprawdz_git(u, ot)]
    return {"root": str(u.root), "czas": time.strftime("%Y-%m-%dT%H:%M:%S"), "serwis": stan is not None,
            "wyniki": wyniki, "bledy": sum(w["stan"] == "blad" for w in wyniki),
            "uwagi": sum(w["stan"] == "uwaga" for w in wyniki)}


def opis_diagnozy(d: dict) -> str:
    znak = {"ok": "[ok]   ", "uwaga": "[uwaga]", "blad": "[błąd] "}
    w = [f"Jarvo doctor: {d['root']}"]
    for r in d["wyniki"]:
        w.append(f"  {znak[r['stan']]} {r['nazwa']}: {r['opis']}")
        if r["rada"] and r["stan"] != "ok":
            w.append(f"          rada: {r['rada']}")
    ok = len(d["wyniki"]) - d["bledy"] - d["uwagi"]
    w.append(f"Wynik: {ok} ok, {d['uwagi']} uwag, {d['bledy']} błędów.")
    return "\n".join(w)


def polecenie_doctor(u: Uklad, a, _reszta, ot: Otoczenie) -> int:
    d = zbierz_diagnoze(u, ot)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else opis_diagnozy(d))
    return 1 if d["bledy"] else 0

"""Hermes natywnie z przypięcia (docs/NATYWNIE.md: H01, H02, H03, H13, H16, H23, H24, I13; c3 punkt 5, c4).

To, co w kontenerze robił obraz Hermesa, robimy sami, bez instalatorów Hermesa (scripts/install.ps1 i install.sh):
tamte pobierają uv, Node i PortableGit bez sum, ustawiają HERMES_HOME i PATH użytkownika, a gdy `uv sync --locked`
się nie uda, po cichu instalują z PyPI bez sum (H01, H02). Pin (repo, tag, commit, dodatki) jest w jednym miejscu:
vendor/natywne.yaml, czytany przez `manifest.hermes(app)`.

`zainstaluj`  `git clone --filter=blob:none --no-checkout` do `<program>/hermes/<commit[:12]>.new`, potem
              `git -c core.longpaths=true -c core.autocrlf=false checkout <commit>` i kontrola `rev-parse HEAD`;
              dopiero zgodny checkout dostaje nazwę `<commit[:12]>` (przerwany klon nie udaje gotowego). Potem trzy
              kroki uv (venv w `.venv`, H02), każdy plik z sumą:
              1. `uv sync --locked --no-install-project --no-build --extra <dodatek>…`: zależności z uv.lock, same
                 gotowe koła (paczka ze źródeł budowałaby się z zależnościami budowy z PyPI bez sum);
              2. `uv pip install --no-config --require-hashes --no-deps --only-binary :all:` zależności budowy
                 projektu z ZALEZNOSCI_BUDOWY. [build-system] w f97608f to setuptools==83.0.0 i wheel bez wersji,
                 a uv.lock ich nie obejmuje, więc izolowana budowa brałaby je z PyPI bez sum (wheel w wersji z dnia
                 instalacji). Wymaganie budowy spoza tej listy (albo inna wersja) zatrzymuje instalację;
              3. `uv sync --locked --no-build-isolation --offline …`: edytowalna budowa hermes-agent w venvie z kroku
                 2, bez sieci. Dokładny sync usuwa potem setuptools i wheel, jeśli zależności z locka ich nie
                 wymagają (f97608f z dodatkami z pinu: usuwa oba; sprawdzone 2026-10-25 na Windows 11).
              Środowisko uv: UV_PYTHON (nasz Python z PBS), UV_PYTHON_DOWNLOADS=never, UV_CACHE_DIR=<cache>/uv,
              UV_LINK_MODE=copy (c4: na Windows załadowanych .pyd nie da się nadpisać) i UV_NO_SYSTEM_CONFIG=1
              (uv.toml systemu: %SYSTEMDRIVE%\\ProgramData\\uv, który na Windows założy każde konto bez admina,
              i /etc/uv). BEZ UV_NO_CONFIG: z nim uv nie czyta [tool.uv] z pyproject.toml Hermesa (m.in.
              exclude-newer), więc lock nie pasuje (sprawdzone 2026-10-24 na f97608f: „The lockfile at `uv.lock`
              needs to be updated”), a instalator Hermesa schodzi wtedy do PyPI bez sum. Zmienne UV_* z otoczenia
              właściciela odcinamy (UV_NO_CONFIG, UV_INDEX_URL…), a uv.toml użytkownika zasłania pusty katalog: na
              Windows uv 0.12.13 czyta go z %APPDATA%\\uv (sprawdzone 2026-10-24; XDG_CONFIG_HOME na Windows nie
              działa), na POSIX z XDG_CONFIG_HOME i XDG_CONFIG_DIRS (c3 punkt 5). Błąd locka albo sumy kończy
              instalację wyjątkiem, bez instalacji w zastępstwie. Znacznik `.jarvo-hermes.json` (commit, dodatki,
              Python) sprawia, że drugi przebieg nic nie robi.
`web_dist`    Front dashboardu z web/: `npm ci --ignore-scripts --no-audit --no-fund --include=dev` (package-lock.json
              z sumami integrity; --include=dev, bo odziedziczone NODE_ENV=production pomija tsc i vite, por.
              hermes_cli/main_web_build.py:317) i `npm run build` do hermes_cli/web_dist, cache npm w <cache>/npm.
              Po zbudowaniu node_modules (ok. 0,3 GB: korzeń checkoutu i web/, bo web jest workspace'em npm
              z package-lock.json korzenia) znika pod zamkiem hermes.lock: znacznik ZNACZNIK_WEB sprawia, że kolejny
              przebieg frontu nie buduje, a `--web-lokalnie` robi `npm ci` od nowa (z cache npm, który zostaje).
              Resztki node_modules ze starszej wersji przy gotowym froncie usuwamy bez czekania na zamek (trzyma
              go drugi instalator: zostają do następnego przebiegu). Gdy na zamek czekaliśmy, a front zbudował
              w tym czasie drugi instalator, dostajemy i tak kopię z łatkami Jarva (dist_jarva), nie gołego dista.
              Potem `dist_jarva`: kopia w <program>/web-dist/<skrót> z łatkami Jarva (branding/patch_dashboard.py
              --web --natywnie: tytuł i marka, powłoka /jarvo z przekierowaniem z „/”, polski, bez przycisku
              „Update Hermes” i bez sprawdzania aktualizacji, H16) i to ją web_dist zwraca (HERMES_WEB_DIST panelu,
              S12). hermes_cli/web_dist w checkoucie zostaje bez zmian, pliki Pythona Hermesa też. Skrót liczymy
              z treści dista i plików brandingu: nowa wersja Jarva albo Hermesa = nowy katalog obok, a stary zostaje
              dla działającego panelu do przełączenia current.json (c4). Łatka, która nie pasuje do dista (nowy układ
              plików Hermesa), to ostrzeżenie i front bez brandingu: ścisłe wzory zatrzymują CI (test E2E panelu),
              nie instalację u właściciela (S12). Docelowo gotowy dist z łatkami zbuduje CI (I12, P05).
`konfiguracja_bezpieczna`  config.yaml w HERMES_HOME Jarva przez CLI Hermesa (`config get --json` i `config set`,
              hermes_cli/config.py:3479 i :3603). Klucze z f97608f (I13):
              - security.tirith_enabled: false (domyślne true, config_defaults.py:1753; czyta
                tools/tirith_security.py:53): tirith pobiera binarkę z releases/latest bez sumy (H23).
              - security.allow_lazy_installs: false (config_defaults.py:1765; tools/lazy_deps.py:325): blokuje
                doinstalowywanie paczek z PyPI w locie zawsze; samo HERMES_DISABLE_LAZY_INSTALLS=1 blokuje tylko
                bez trwałego katalogu docelowego (lazy_deps.py:335) (H03).
              - auth.adopt_external_logins: false (config_defaults.py:1724; agent/credential_sources.py:32):
                Jarvo nie pożycza logowań Codex CLI i Claude Code właściciela (H15).
              - updates.check: false (config_defaults.py:2314; hermes_cli/banner.py:388-391 zwraca wtedy None):
                bez pytania GitHuba i bez „Update available … run 'hermes update'” w `--version`
                (_startup_fast.py:214-219), w banerze CLI (banner.py:1011-1017) i w TUI (tui_gateway/server.py:86).
                Panel sam pyta /api/hermes/update/check na stronie System: to ukrywa powłoka Jarva (H16).
              - terminal.home_mode: profile, jeśli ta wersja go zna (config_defaults.py:315; czyta
                hermes_constants.py:1003 przez TERMINAL_HOME_MODE z gateway/run.py:1995 i cli_config_load.py:87).
                Działa tylko, gdy istnieje <HERMES_HOME>/home (hermes_constants.py:941-947), więc go zakładamy (H24).
              - terminal.auto_source_bashrc: false (config_defaults.py:327, domyślnie true): migawka powłoki agenta
                nie wczytuje ~/.profile, ~/.bash_profile i ~/.bashrc właściciela z prawdziwego HOME procesu bramy
                (tools/environments/local.py:707-739 i :942), np. wyeksportowanych tokenów. Wymagany na macOS
                i Linuksie; na Windows f97608f nie czyta tych plików nigdy (local.py:729), więc tam bez przymusu.
              - Windows: terminal.shell_init_files: [<stan>/powloka/<profil>.sh] (config_defaults.py:321;
                local.py:721-748 i :942: Git Bash czyta te pliki przed migawką środowiska terminala). Plik ustawia
                USERPROFILE, APPDATA, LOCALAPPDATA, XDG_CONFIG_HOME, GH_CONFIG_DIR, CODEX_HOME
                i NPM_CONFIG_USERCONFIG w katalogu domowym profilu, bo home_mode przestawia tylko HOME, które czytają
                git i ssh z Git Bash, a programy Windows (gh, codex, npm, python) biorą katalogi z tych zmiennych
                (H24, sekcja d). Leży w <stan>, poza HERMES_WRITE_SAFE_ROOT, więc narzędzia plików agenta go nie
                zmienią; instalacja pisze go od nowa.
              Każde wywołanie ma `-p default` (albo `-p <profil>`): bez niego lepki <HERMES_HOME>/active_profile
              przekierowałby zapis do profilu (hermes_cli/main.py:593). Klucz, którego dana wersja Hermesa nie zna,
              CLI zgłasza jako „Config key not set” (config.py:3626): tirith i home_mode wtedy pomijamy, a brak
              pozostałych zatrzymuje instalację (nowa wersja wymaga przeglądu, czym je zastąpiono).
`wersja`, `argv_hermesa`  `<venv>/python -P -m hermes_cli.main …` (H13): bez polecenia `hermes` w PATH i bez zmiennych
              użytkownika; HERMES_HOME tylko w środowisku procesu. `-P` (Python 3.11+): bieżący katalog nie trafia do
              sys.path, więc json.py podrzucony w katalogu roboczym (HERMES_HOME, do którego piszą agenci, albo folder
              projektu `jarvo chat`) nie podmieni modułu; Hermes sam dokłada korzeń checkoutu
              (hermes_cli/main.py:41-45), resztę daje instalacja edytowalna. Nigdy `hermes update` (H16).

Programy (git, uv, npm) bierzemy tylko po pełnej ścieżce: podanej albo znalezionej w katalogach bezwzględnych z PATH
lub z narzedzia.json, nigdy w bieżącym katalogu. Na Windows shutil.which (Python 3.12+) dokłada bieżący katalog przed
każdą ścieżką, chyba że proces ma NoDefaultCurrentDirectoryInExePath: ustawiamy ją na czas szukania i w środowisku
każdego wywołania (cmd.exe w npm i git też nie szuka wtedy w bieżącym katalogu). Programy uruchamiamy na Windows bez
okna konsoli tylko wtedy, gdy sami jej nie mamy (pythonw, przycisk w panelu), żeby Ctrl+C docierało do nich z konsoli;
na POSIX we własnej grupie procesów. Po przerwaniu albo limicie czasu zatrzymujemy całe drzewo procesów, zanim zwolnimy
zamek hermes.lock.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import urllib.parse
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from . import przenosne, srodowisko
from .sciezki import WINDOWS, Uklad

ZNACZNIK = ".jarvo-hermes.json"          # w checkoucie: commit, dodatki i Python zainstalowanego venvu
ZNACZNIK_WEB = ".jarvo-web-dist.json"    # w checkoucie: commit, z którego zbudowano hermes_cli/web_dist
# kod tej wersji Jarva (branding/ z łatkami dista); bez resolve(), jak instalator: krótka nazwa 8.3 zostaje ASCII
APP = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# pliki brandingu, od których zależy łatana kopia dista (patch_dashboard.py --web --natywnie); zmiana = nowy katalog
PLIKI_BRANDINGU = ("patch_dashboard.py", "powloka.json", "powloka.js", "i18n/pl.json", "favicon.ico", "favicon.svg")
# git: długie ścieżki i LF z repo na Windows; bez gc i maintenance w tle (trzymałyby pliki przy zmianie nazwy);
# lowSpeed zrywa zastygłe pobieranie także w fetch i w leniwym dociąganiu blobów przy checkoucie (dzieci gita
# dziedziczą -c przez GIT_CONFIG_PARAMETERS)
GIT_C = ("-c", "core.longpaths=true", "-c", "core.autocrlf=false", "-c", "gc.auto=0",
         "-c", "maintenance.auto=false", "-c", "advice.detachedHead=false",
         "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=120")
# zmienne UV_* z otoczenia, które zostają: dotyczą sieci, nie tego, co i skąd instalujemy
UV_ZOSTAJE = ("UV_NATIVE_TLS", "UV_HTTP_TIMEOUT")
CZAS_CLI = 180                          # s na jedno wywołanie CLI Hermesa (config, --version)

# Zależności budowy hermes-agent ([build-system] requires): nazwa → (wersja, sha256 koła py3-none-any z PyPI). Jedyne
# paczki instalowane poza zależnościami z uv.lock: wheel nie ma tam wcale, a setuptools 83.0.0 jest z tą samą sumą,
# ale tylko dla dodatków dev i voice. Sumy z PyPI JSON API, policzone też strumieniowo z pobranych kół 2026-10-25.
# wheel 0.48.0 to najnowsze wydanie (2026-08-11); jego zależność packaging 26.0 jest zależnością główną Hermesa
# w uv.lock, więc przychodzi w kroku 1. Do przeniesienia do vendor/natywne.yaml (koordynator).
ZALEZNOSCI_BUDOWY = {
    "setuptools": ("83.0.0", "29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3"),
    "wheel": ("0.48.0", "3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab"),
}

# (klucz, wartość dla `config set`, wartość z `config get --json`, czy wymagany w każdej wersji); na Windows
# dochodzi terminal.shell_init_files z plikiem profilu (_klucze_profilu)
BEZPIECZNE = (
    ("security.tirith_enabled", "false", False, False),
    ("security.allow_lazy_installs", "false", False, True),
    ("auth.adopt_external_logins", "false", False, True),
    ("updates.check", "false", False, True),
    ("terminal.home_mode", "profile", "profile", False),
    ("terminal.auto_source_bashrc", "false", False, not WINDOWS),
)

_SHA = re.compile(r"[0-9a-f]{40}")
_DODATEK = re.compile(r"[a-z0-9][a-z0-9._-]*")
_PROFIL = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")      # jak hermes_cli/main.py (_PROFILE_NAME_RE)
_WYMAGANIE = re.compile(r"(?P<nazwa>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:==\s*(?P<wersja>[A-Za-z0-9.+!_-]+))?")
_POSTEP = re.compile(r"\d{1,3}%")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")             # kolory i czyszczenie linii (vite, npm) poza logiem
_URL_Z_HASLEM = re.compile(r"(\w+://)[^/\s@]+@")          # https://ktoś:token@… i https://token@…
_WERSJA = re.compile(r"Hermes Agent v(\d[\w.+-]*)")
_BEZ_CWD = "NoDefaultCurrentDirectoryInExePath"
_ZAMEK_WHICH = threading.Lock()                         # os.environ jest wspólne dla wątków


class BladHermesa(RuntimeError):
    """Instalacja albo konfiguracja Hermesa się nie udała (komunikat po polsku, bez sekretów)."""


def argv_hermesa(checkout: Path, *argumenty: str) -> list[str]:
    """Polecenie CLI Hermesa: python venvu checkoutu + `-P -m hermes_cli.main` + argumenty (H13). `-P`: bez
    bieżącego katalogu w sys.path, więc katalog roboczy nie podmieni modułów (docstring modułu)."""
    return [str(srodowisko.hermes_python(Path(checkout))), "-P", "-m", "hermes_cli.main",
            *(str(a) for a in argumenty)]


def katalog_checkoutu(u: Uklad, commit: str) -> Path:
    """`<program>/hermes/<commit[:12]>`: wersje obok siebie, `jarvo update` robi nowy katalog (H16, c4)."""
    return u.program / "hermes" / commit[:12]


# --- pomocnicze ---------------------------------------------------------------------------------------------------

def _bez_sekretow(tekst: str) -> str:
    """Hasło albo token w adresie (https://ktoś:token@…, https://token@…) nie trafia do logu."""
    return _URL_Z_HASLEM.sub(r"\1***@", tekst)


def _ustaw(env: dict[str, str], klucz: str, wartosc: str) -> None:
    """Ustawia zmienną; na Windows usuwa najpierw tę samą nazwę inną wielkością liter (os.environ ma wielkie)."""
    if WINDOWS:
        for k in [k for k in env if k.upper() == klucz.upper()]:
            del env[k]
    env[klucz] = wartosc


def _bez(env: dict[str, str], *przedrostki: str, zostaw: Iterable[str] = ()) -> dict[str, str]:
    zostaw = {z.upper() for z in zostaw}
    return {k: v for k, v in env.items() if not k.upper().startswith(przedrostki) or k.upper() in zostaw}


def _jawne(katalogi: Iterable[str]) -> list[str]:
    """Same katalogi bezwzględne (bez cudzysłowów z PATH Windows): pusty wpis, `.` albo `bin` to bieżący katalog."""
    wynik = []
    for k in katalogi:
        k = str(k).strip().strip('"')
        if k and Path(k).is_absolute() and k not in wynik:
            wynik.append(k)
    return wynik


def _katalogi_path() -> list[str]:
    return _jawne((os.environ.get("PATH") or "").split(os.pathsep))


def _baza() -> dict[str, str]:
    """os.environ bez zmiennych, które przestawiłyby narzędzia na cudzy Python, venv albo Hermesa (srodowisko.OBCE);
    PATH tylko z katalogów bezwzględnych, a na Windows z NoDefaultCurrentDirectoryInExePath: programy, które
    uruchamiają git, uv i npm (cmd.exe, node, python), też nie biorą niczego z bieżącego katalogu."""
    obce = {o.upper() for o in srodowisko.OBCE}
    env = {k: v for k, v in os.environ.items() if k.upper() not in obce}
    for k in [k for k in env if k.upper() == "PATH"]:
        env[k] = os.pathsep.join(_jawne(env[k].split(os.pathsep)))
    if WINDOWS:
        _ustaw(env, _BEZ_CWD, "1")
    return env


def _szukaj(nazwa: str, katalogi: Iterable[str]) -> str | None:
    """Pełna ścieżka programu `nazwa` z podanych katalogów bezwzględnych albo None. shutil.which zna PATHEXT (.exe,
    .cmd); NoDefaultCurrentDirectoryInExePath w procesie na czas szukania nie pozwala mu zajrzeć do bieżącego
    katalogu (Python 3.12+ robi to na Windows także przy jawnym `path`). Wynik spoza tych katalogów odrzucamy."""
    jawne = _jawne(katalogi)
    if not jawne or not nazwa or os.path.dirname(nazwa):
        return None
    with _ZAMEK_WHICH:
        przed = os.environ.get(_BEZ_CWD)
        if WINDOWS:
            os.environ[_BEZ_CWD] = "1"
        try:
            wynik = shutil.which(nazwa, path=os.pathsep.join(jawne))
        finally:
            if WINDOWS:
                if przed is None:
                    os.environ.pop(_BEZ_CWD, None)
                else:
                    os.environ[_BEZ_CWD] = przed
    if not wynik or not Path(wynik).is_absolute():
        return None
    return wynik if any(_ta_sama(Path(wynik).parent, k) for k in jawne) else None


def _program(sciezka: str | os.PathLike | None, nazwa: str) -> str:
    """Pełna ścieżka programu: podana ścieżka bezwzględna istniejącego pliku albo goła nazwa szukana tylko
    w katalogach bezwzględnych z PATH (shutil.which zna .exe i .cmd na Windows), nigdy w bieżącym katalogu."""
    if sciezka:
        tekst = str(sciezka)
        if os.path.dirname(tekst):
            if not Path(tekst).is_absolute():
                raise BladHermesa(f"Program {nazwa}: potrzebna pełna ścieżka, a jest względna ({tekst}).")
            if Path(tekst).is_file():
                return tekst
        else:
            znaleziony = _szukaj(tekst, _katalogi_path())
            if znaleziony:
                return znaleziony
    raise BladHermesa(f"Nie znalazłem programu {nazwa}" + (f" ({sciezka})." if sciezka else "."))


def _teraz() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ta_sama(a, b) -> bool:
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _ma_konsole() -> bool:
    """Czy ten proces ma konsolę (Windows): pythonw i procesy w tle bez okna jej nie mają."""
    if not WINDOWS:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except (AttributeError, OSError):
        return False


def _uruchomienie() -> dict:
    """Argumenty Popen: na Windows CREATE_NO_WINDOW tylko bez własnej konsoli (inaczej mignęłoby okno, a z konsolą
    Ctrl+C dociera też do programu); na POSIX nowa sesja, żeby zatrzymać całą grupę procesów (_zakoncz)."""
    if WINDOWS:
        return {"creationflags": 0 if _ma_konsole() else subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def _zakoncz(proc: subprocess.Popen) -> None:
    """Zatrzymuje program razem z jego procesami potomnymi (git, uv i npm mają własne) po Ctrl+C albo limicie czasu,
    żeby nic nie pisało dalej w checkoucie ani nie trzymało jego plików, gdy zwalniamy hermes.lock."""
    if proc.poll() is None:
        try:
            if WINDOWS:
                taskkill = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "taskkill.exe"
                subprocess.run([str(taskkill), "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=15)          # domyka potoki (i wątki czytające communicate na Windows)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def _strumien(argv: list, *, cwd: Path, env: dict, log: Callable[[str], None],
              przemilcz: Callable[[str], bool] | None = None) -> tuple[int, list[str]]:
    """Uruchamia program, a jego wyjście (stdout i stderr) przekazuje do `log` linia po linii; paski postępu co 5 s.
    Zwraca kod wyjścia i ostatnie linie (do komunikatu błędu). Wyjątek w trakcie (Ctrl+C) zatrzymuje drzewo procesów."""
    ogon: deque[str] = deque(maxlen=40)
    try:
        proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", **_uruchomienie())
    except OSError as e:
        raise BladHermesa(f"Nie uruchomię {Path(str(argv[0])).name}: {e}") from None
    ostatni_postep = 0.0
    with proc:
        try:
            for surowa in proc.stdout:
                linia = _bez_sekretow(_ANSI.sub("", surowa).rstrip())
                if not linia.strip():
                    continue
                ogon.append(linia)
                if przemilcz and przemilcz(linia):
                    continue
                if _POSTEP.search(linia) and "100%" not in linia:
                    teraz = time.monotonic()
                    if teraz - ostatni_postep < 5:
                        continue
                    ostatni_postep = teraz
                log(f"    {linia}")
            kod = proc.wait()
        except BaseException:
            _zakoncz(proc)
            raise
    return kod, list(ogon)


def _wywolaj(argv: list, *, env: dict, cwd: Path, opis: str, czas: int = CZAS_CLI) -> subprocess.CompletedProcess:
    """Krótkie wywołanie z przechwyconym wyjściem i limitem czasu (stdin zamknięty: nic nie czeka na człowieka)."""
    argv = [str(a) for a in argv]
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                **_uruchomienie())
    except OSError as e:
        raise BladHermesa(f"{opis}: nie uruchomię {Path(argv[0]).name}: {e}") from None
    with proc:
        try:
            wyjscie, bledy = proc.communicate(timeout=czas)
        except subprocess.TimeoutExpired:
            _zakoncz(proc)
            raise BladHermesa(f"{opis}: brak odpowiedzi po {czas} s.") from None
        except BaseException:
            _zakoncz(proc)
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, wyjscie, bledy)


def _koncowka(*teksty: str, linie: int = 8) -> str:
    wszystkie = [_bez_sekretow(x) for t in teksty if t for x in t.splitlines() if x.strip()]
    return "\n".join(f"    {x}" for x in wszystkie[-linie:])


def _usun_drzewo(p: Path) -> None:
    """rmtree, który radzi sobie z plikami tylko do odczytu (paczki gita na Windows); onexc dopiero od 3.12."""
    def odblokuj(funkcja, sciezka, _blad):
        os.chmod(sciezka, stat.S_IWRITE)
        funkcja(sciezka)
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=odblokuj)
    else:
        shutil.rmtree(p, onerror=odblokuj)


def _przenies(z: Path, do: Path, proby: int = 40) -> None:
    """Zmiana nazwy katalogu; na Windows ponawia, gdy plik chwilowo trzyma antywirus albo indeksowanie."""
    for i in range(proby):
        try:
            os.replace(z, do)
            return
        except PermissionError as e:
            if not WINDOWS or i == proby - 1:
                raise BladHermesa(f"Nie mogę zmienić nazwy {z} na {do.name}: {e}. Zamknij programy, które "
                                  "mogą trzymać pliki w tym katalogu, i uruchom instalację jeszcze raz.") from None
            time.sleep(0.25)


def _wyklucz(checkout: Path, *nazwy: str) -> None:
    """Znaczniki Jarva w `.git/info/exclude`: `git status` checkoutu zostaje czysty (doctor może to sprawdzać)."""
    info = checkout / ".git" / "info"
    if not (checkout / ".git").is_dir():
        return
    plik = info / "exclude"
    try:
        tresc = plik.read_text(encoding="utf-8")
    except FileNotFoundError:
        tresc = ""
    brak = [f"/{n}" for n in nazwy if f"/{n}" not in tresc.splitlines()]
    if brak:
        if tresc and not tresc.endswith("\n"):
            tresc += "\n"
        przenosne.zapisz_atomowo(plik, tresc + "".join(f"{b}\n" for b in brak))


# --- git --------------------------------------------------------------------------------------------------------

def _env_git(sufit: Path) -> dict[str, str]:
    """Bez GIT_* z otoczenia (GIT_DIR, GIT_WORK_TREE, GIT_CONFIG_PARAMETERS, GIT_ASKPASS…) i bez okien z pytaniem
    o hasło; GIT_CEILING_DIRECTORIES nie pozwala wejść do repo nad katalogiem Jarva."""
    env = _bez(_baza(), "GIT_")
    env.pop("SSH_ASKPASS", None)
    _ustaw(env, "GIT_TERMINAL_PROMPT", "0")
    _ustaw(env, "GCM_INTERACTIVE", "never")
    _ustaw(env, "GIT_CEILING_DIRECTORIES", str(sufit))
    return env


def _head(git: str, katalog: Path, env: dict) -> str | None:
    if not (katalog / ".git").exists():
        return None
    w = _wywolaj([git, *GIT_C, "rev-parse", "HEAD"], env=env, cwd=katalog, opis="git rev-parse")
    return w.stdout.strip().lower() if w.returncode == 0 else None


def _checkout(repo: str, commit: str, docelowy: Path, *, git: str, log) -> None:
    env = _env_git(docelowy.parent)
    if docelowy.exists():
        head = _head(git, docelowy, env)
        if head is None:
            raise BladHermesa(f"{docelowy} istnieje, ale nie jest checkoutem gita. Usuń ten katalog i uruchom "
                              "instalację jeszcze raz.")
        if head != commit:
            raise BladHermesa(f"{docelowy} ma commit {head[:12]}, a przypięty jest {commit[:12]}. Usuń ten katalog "
                              "i uruchom instalację jeszcze raz (nie poprawiam cudzych zmian w kodzie Hermesa).")
        _wyklucz(docelowy, ZNACZNIK, ZNACZNIK_WEB)
        return
    nowy = docelowy.with_name(docelowy.name + ".new")
    if nowy.exists():
        try:
            _usun_drzewo(nowy)
        except OSError as e:
            raise BladHermesa(f"Nie mogę usunąć {nowy} (resztki przerwanej instalacji): {e}. Zamknij programy, które "
                              "mogą trzymać pliki w tym katalogu, i uruchom instalację jeszcze raz.") from None
    nowy.parent.mkdir(parents=True, exist_ok=True)
    log(f"Hermes: pobieram kod z {_bez_sekretow(repo)} (git clone bez blobów historii)…")
    kod, ogon = _strumien([git, *GIT_C, "clone", "--filter=blob:none", "--no-checkout", "--progress",
                           "-c", "core.longpaths=true", "-c", "core.autocrlf=false", repo, str(nowy)],
                          cwd=nowy.parent, env=env, log=log)
    if kod:
        raise BladHermesa(f"git clone {_bez_sekretow(repo)} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
    w = _wywolaj([git, *GIT_C, "cat-file", "-t", commit], env=env, cwd=nowy, opis="git cat-file")
    if w.returncode or w.stdout.strip() != "commit":
        log(f"Hermes: commitu {commit[:12]} nie ma w gałęziach repo, pobieram go wprost…")
        kod, ogon = _strumien([git, *GIT_C, "fetch", "--filter=blob:none", "origin", commit], cwd=nowy, env=env,
                              log=log)
        if kod:
            raise BladHermesa(f"Commitu {commit[:12]} nie ma w {_bez_sekretow(repo)} (git fetch: kod {kod}):\n"
                              + _koncowka(*ogon))
    log(f"Hermes: checkout {commit[:12]} (git dociąga pliki tego commitu, bez paska postępu)…")
    kod, ogon = _strumien([git, *GIT_C, "checkout", commit], cwd=nowy, env=env, log=log)
    if kod:
        raise BladHermesa(f"git checkout {commit[:12]} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
    head = _head(git, nowy, env)
    if head != commit:
        raise BladHermesa(f"Po checkoucie HEAD to {head or 'nic'}, a przypięty jest {commit}: nie instaluję kodu "
                          "innego niż przypięty.")
    _wyklucz(nowy, ZNACZNIK, ZNACZNIK_WEB)
    _przenies(nowy, docelowy)


# --- uv ---------------------------------------------------------------------------------------------------------

def _env_uv(u: Uklad, python: str) -> dict[str, str]:
    env = _bez(_baza(), "UV_", zostaw=UV_ZOSTAJE)
    pusty = u.stan / "bez-konfiguracji-uv"      # zamiast uv.toml właściciela (zawsze pusty katalog)
    pusty.mkdir(parents=True, exist_ok=True)
    for klucz, wartosc in (("UV_PYTHON", python), ("UV_PYTHON_DOWNLOADS", "never"),
                           ("UV_CACHE_DIR", str(u.cache / "uv")), ("UV_LINK_MODE", "copy"),
                           ("UV_NO_SYSTEM_CONFIG", "1")):
        _ustaw(env, klucz, wartosc)
    if WINDOWS:
        _ustaw(env, "APPDATA", str(pusty))      # %APPDATA%\uv\uv.toml; przy okazji bez site-packages użytkownika
    else:
        _ustaw(env, "XDG_CONFIG_HOME", str(pusty))
        _ustaw(env, "XDG_CONFIG_DIRS", str(pusty))
    return env


def _nazwa_paczki(nazwa: str) -> str:
    return re.sub(r"[-_.]+", "-", nazwa).lower()        # PEP 503


def _wymagania_budowy(checkout: Path) -> list[str]:
    """Linie `nazwa==wersja --hash=sha256:…` dla [build-system] requires z pyproject.toml checkoutu. Każde wymaganie
    musi pasować do ZALEZNOSCI_BUDOWY (nazwa, a przy `==` także wersja); inne zatrzymuje instalację, bo budowałoby
    się z paczek bez przeglądu i sumy. Brak [build-system] = setuptools (PEP 517)."""
    try:
        dane = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BladHermesa(f"{checkout}: nie czytam pyproject.toml ({e}).") from None
    wymagania = (dane.get("build-system") or {}).get("requires")
    if wymagania is None:
        wymagania = ["setuptools"]
    linie = []
    for wymaganie in wymagania:
        m = _WYMAGANIE.fullmatch(str(wymaganie).strip())
        przypiete = ZALEZNOSCI_BUDOWY.get(_nazwa_paczki(m["nazwa"])) if m else None
        if przypiete is None or (m["wersja"] and m["wersja"] != przypiete[0]):
            raise BladHermesa(f"Hermes wymaga do budowy {str(wymaganie)!r}, a przypięte z sumą są tylko: "
                              + ", ".join(f"{n}=={w}" for n, (w, _s) in ZALEZNOSCI_BUDOWY.items())
                              + ". Nowa zależność budowy wymaga przeglądu (docs/SOURCES.md) i sumy w "
                                "ZALEZNOSCI_BUDOWY; nie instaluję jej z PyPI bez sumy.")
        linia = f"{_nazwa_paczki(m['nazwa'])}=={przypiete[0]} --hash=sha256:{przypiete[1]}"
        if linia not in linie:
            linie.append(linia)
    return linie


def _linia_paczki(linia: str) -> bool:
    return linia.startswith((" + ", " - ", " ~ ", " Downloaded "))


def _powod_uv(krok: str, kod: int, ogon: list[str]) -> str:
    tekst = "\n".join(ogon)
    niski = tekst.lower()
    if "needs to be updated" in niski or ("lockfile" in niski and "--locked" in niski):
        powod = "uv.lock nie pasuje do pyproject.toml tego commitu"
    elif "hash mismatch" in niski or ("hash" in niski and "does not match" in niski):
        powod = "suma pliku z PyPI nie zgadza się z przypiętą"
    elif ("wheel for the current platform" in niski or "no wheels with a matching platform" in niski
          or "binary distribution" in niski):
        powod = "w uv.lock nie ma gotowej paczki (koła) dla tego systemu, a ze źródeł nie buduję"
    elif "no module named" in niski and ("setuptools" in niski or "wheel" in niski):
        powod = "w venvie brak zależności budowy (setuptools, wheel)"
    elif "offline" in niski or "network connectivity is disabled" in niski:
        powod = "krok bez sieci chciał pobrać coś spoza uv.lock"
    else:
        powod = "uv zakończył się błędem"
    return (f"Hermes: `{krok}` nie przeszedł (kod {kod}): {powod}. Nie instaluję niczego bez sum z uv.lock "
            "(żadnej instalacji z PyPI w zastępstwie). Ostatnie linie:\n" + _koncowka(*ogon))


def _gotowy(checkout: Path, commit: str, dodatki: list[str], python: str) -> bool:
    z = srodowisko.wczytaj_json(checkout / ZNACZNIK)
    return (z.get("commit") == commit and sorted(z.get("dodatki") or []) == sorted(dodatki)
            and _ta_sama(z.get("python"), python) and srodowisko.hermes_python(checkout).is_file())


def _pin(pin: dict) -> tuple[str, str, list[str], str]:
    commit = str(pin.get("commit") or "").lower()
    repo = str(pin.get("repo") or "")
    dodatki = pin.get("dodatki") or []
    if not _SHA.fullmatch(commit):
        raise BladHermesa(f"Pin Hermesa: commit musi być pełnym SHA (40 znaków), jest {commit[:44]!r}.")
    if not repo.startswith("https://"):
        raise BladHermesa(f"Pin Hermesa: repo tylko przez https (jest {_bez_sekretow(repo)[:60]!r}).")
    try:
        czesci = urllib.parse.urlsplit(repo)
        z_logowaniem = "@" in czesci.netloc or czesci.username is not None or czesci.password is not None
    except ValueError:
        z_logowaniem = True
    if z_logowaniem:
        # git zapisałby pełny adres w <checkout>/.git/config, a token trafiłby też do znacznika i logów
        raise BladHermesa("Pin Hermesa: adres repo bez loginu i tokenu (jest "
                          f"{_bez_sekretow(repo)[:60]!r}); dostęp do prywatnej kopii idzie przez magazyn kluczy.")
    if not isinstance(dodatki, list) or not all(isinstance(d, str) and _DODATEK.fullmatch(d) for d in dodatki):
        raise BladHermesa(f"Pin Hermesa: dodatki to lista nazw extras z pyproject.toml (jest {dodatki!r}).")
    return commit, repo, list(dodatki), str(pin.get("tag") or commit[:12])


def _uv(uv: str, argumenty: list[str], *, opis: str, checkout: Path, env: dict, log) -> None:
    kod, ogon = _strumien([uv, *argumenty], cwd=checkout, env=env, log=log, przemilcz=_linia_paczki)
    if kod:
        raise BladHermesa(_powod_uv(opis, kod, ogon))


def _zaleznosci(u: Uklad, docelowy: Path, dodatki: list[str], *, uv: str, python: str, log) -> list[str]:
    """Trzy kroki uv z docstringu modułu; zwraca zainstalowane zależności budowy (do znacznika)."""
    budowa = _wymagania_budowy(docelowy)          # przed pierwszym uv: zła zależność budowy = nic nie instalujemy
    env = _env_uv(u, python)
    extras = [x for d in dodatki for x in ("--extra", d)]
    log(f"Hermes: zależności z uv.lock (uv sync --locked, same koła; dodatki: {', '.join(dodatki) or 'brak'})…")
    _uv(uv, ["sync", "--locked", "--no-install-project", "--no-build", *extras], opis="uv sync --locked",
        checkout=docelowy, env=env, log=log)
    venv_python = srodowisko.hermes_python(docelowy)
    if not venv_python.is_file():
        raise BladHermesa(f"uv sync skończył się bez błędu, ale nie ma {venv_python}.")
    log("Hermes: zależności budowy z przypiętymi sumami (" + ", ".join(x.split(" ", 1)[0] for x in budowa) + ")…")
    fd, plik = tempfile.mkstemp(prefix="hermes-budowa-", suffix=".txt", dir=str(u.stan))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(f"{x}\n" for x in budowa))
        _uv(uv, ["pip", "install", "--python", str(venv_python), "--no-config", "--require-hashes", "--no-deps",
                 "--only-binary", ":all:", "-r", plik], opis="uv pip install --require-hashes",
            checkout=docelowy, env=env, log=log)
    finally:
        Path(plik).unlink(missing_ok=True)
    log("Hermes: budowa hermes-agent w venvie (uv sync --locked --no-build-isolation, bez sieci)…")
    _uv(uv, ["sync", "--locked", "--no-build-isolation", "--offline", *extras],
        opis="uv sync --locked --no-build-isolation", checkout=docelowy, env=env, log=log)
    return [x.split(" ", 1)[0] for x in budowa]


def zainstaluj(u: Uklad, pin: dict, *, git, uv, python, log: Callable[[str], None] = print) -> Path:
    """Checkout przypiętego commitu Hermesa i zależności z uv.lock z dodatkami z pinu; zwraca katalog checkoutu.
    `git`, `uv`, `python`: pełne ścieżki programów (albo nazwy szukane tylko w PATH). Gotowa instalacja (znacznik
    z tym samym commitem, dodatkami i Pythonem) = bez żadnego wywołania. Każdy błąd to BladHermesa po polsku."""
    commit, repo, dodatki, tag = _pin(pin)
    docelowy = katalog_checkoutu(u, commit)
    python = _program(python, "python")
    if _gotowy(docelowy, commit, dodatki, python):
        log(f"Hermes {tag} ({commit[:12]}): już zainstalowany w {docelowy}")
        return docelowy
    git, uv = _program(git, "git"), _program(uv, "uv")
    with przenosne.Zamek(u.stan / "hermes.lock"):
        if _gotowy(docelowy, commit, dodatki, python):        # drugi instalator skończył, gdy czekaliśmy
            return docelowy
        _checkout(repo, commit, docelowy, git=git, log=log)
        (docelowy / ZNACZNIK).unlink(missing_ok=True)
        budowa = _zaleznosci(u, docelowy, dodatki, uv=uv, python=python, log=log)
        if not srodowisko.hermes_python(docelowy).is_file():
            raise BladHermesa(f"uv sync skończył się bez błędu, ale nie ma {srodowisko.hermes_python(docelowy)}.")
        przenosne.zapisz_atomowo(docelowy / ZNACZNIK, json.dumps({
            "commit": commit, "tag": pin.get("tag"), "wersja": pin.get("wersja"), "repo": _bez_sekretow(repo),
            "dodatki": dodatki, "python": python, "budowa": budowa, "zainstalowano": _teraz(),
        }, ensure_ascii=False, indent=2) + "\n")
    log(f"Hermes {tag} ({commit[:12]}): gotowy w {docelowy}")
    return docelowy


# --- front dashboardu ---------------------------------------------------------------------------------------------

def _znajdz_npm(u: Uklad) -> str | None:
    """npm z Node Jarva (`<stan>/narzedzia.json`, wpis node), a gdy go nie ma, z PATH (droga dewelopera); nigdy
    z bieżącego katalogu."""
    narz = srodowisko.narzedzia(u)
    for nazwa in ("node", "nodejs"):
        wpis = narz.get(nazwa)
        katalogi = [str(Path(k)) for k in (wpis.get("bin") or [])] if isinstance(wpis, dict) else []
        znaleziony = _szukaj("npm", katalogi)
        if znaleziony:
            return znaleziony
    return _szukaj("npm", _katalogi_path())


def _env_npm(u: Uklad, npm: str) -> dict[str, str]:
    env = {k: v for k, v in _baza().items() if k.upper() != "NODE_ENV"}
    _ustaw(env, "npm_config_cache", str(u.cache / "npm"))
    _ustaw(env, "npm_config_update_notifier", "false")
    _ustaw(env, "NO_COLOR", "1")
    sciezka = next((v for k, v in env.items() if k.upper() == "PATH"), "")
    _ustaw(env, "PATH", os.pathsep.join([str(Path(npm).parent), sciezka]).rstrip(os.pathsep))  # node obok npm
    return env


def _linia_vite(linia: str) -> bool:
    return bool(re.search(r"web_dist[\\/]", linia))


def _web_gotowy(checkout: Path, dist: Path, commit: str) -> bool:
    return (srodowisko.wczytaj_json(checkout / ZNACZNIK_WEB).get("commit") == commit
            and (dist / "index.html").is_file())


def _bajty(katalog: Path) -> int:
    """Rozmiar plików drzewa bez wchodzenia w dowiązania i punkty połączenia (npm linkuje nimi workspace'y)."""
    razem, stos = 0, [str(katalog)]
    while stos:
        try:
            with os.scandir(stos.pop()) as it:
                wpisy = list(it)
        except OSError:
            continue
        for e in wpisy:
            try:
                if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                    continue
                if e.is_dir(follow_symlinks=False):
                    stos.append(e.path)
                else:
                    razem += e.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return razem


def _usun_node_modules(checkout: Path, log: Callable[[str], None]) -> None:
    """node_modules po zbudowaniu frontu (docstring modułu: korzeń checkoutu i web/). rmtree nie wchodzi w punkty
    połączenia (node_modules/web → web), więc źródła frontu zostają. Plik zajęty (antywirus na Windows) zostawia
    katalog do następnej instalacji, bez błędu."""
    for katalog in (checkout / "node_modules", checkout / "web" / "node_modules"):
        if not katalog.is_dir() or katalog.is_symlink():
            continue
        mb = _bajty(katalog) / 1e6
        try:
            _usun_drzewo(katalog)
        except OSError as e:
            log(f"Hermes: {katalog} zostaje do następnej instalacji ({e})")
            continue
        log(f"Hermes: usunięte {katalog.relative_to(checkout).as_posix()} ({mb:.0f} MB): front jest zbudowany")


def web_dist(u: Uklad, checkout: Path, *, npm=None, log: Callable[[str], None] = print, jarva: bool = True) -> Path:
    """Buduje front dashboardu z `web/` do `hermes_cli/web_dist` i zwraca katalog dla HERMES_WEB_DIST panelu: kopię
    z łatkami Jarva (`dist_jarva`), a bez nich (`jarva=False` albo łatka nie pasuje) sam front Hermesa. Zbudowany
    front dla tego commitu (znacznik) = bez wywołań npm."""
    checkout = Path(checkout)
    dist = checkout / "hermes_cli" / "web_dist"
    commit = srodowisko.wczytaj_json(checkout / ZNACZNIK).get("commit")
    if not commit:
        raise BladHermesa(f"{checkout}: brak znacznika instalacji Hermesa ({ZNACZNIK}); najpierw zainstaluj().")
    if _web_gotowy(checkout, dist, commit):
        log(f"Hermes: front dashboardu już zbudowany ({dist})")
        if any((k / "node_modules").is_dir() for k in (checkout, checkout / "web")):   # z wersji przed sprzątaniem
            try:                    # bez czekania: drugi instalator, który trzyma zamek, usunie je sam po budowie
                with przenosne.Zamek(u.stan / "hermes.lock", czekaj=False):
                    if _web_gotowy(checkout, dist, commit):
                        _usun_node_modules(checkout, log)
            except BlockingIOError:
                log("Hermes: node_modules zostają do następnego przebiegu (drugi instalator właśnie używa checkoutu)")
        return dist_jarva(u, dist, log=log) if jarva else dist
    web = checkout / "web"
    if not (web / "package.json").is_file():
        raise BladHermesa(f"{checkout}: brak web/package.json, nie ma z czego zbudować frontu.")
    npm = _program(npm or _znajdz_npm(u), "npm")
    with contextlib.ExitStack() as zamek:
        zamek.enter_context(przenosne.Zamek(u.stan / "hermes.lock"))
        if _web_gotowy(checkout, dist, commit):         # drugi instalator zbudował front, gdy czekaliśmy
            zamek.close()                               # dist_jarva bierze ten sam zamek
            return dist_jarva(u, dist, log=log) if jarva else dist
        (checkout / ZNACZNIK_WEB).unlink(missing_ok=True)
        env = _env_npm(u, npm)
        log("Hermes: zależności frontu (npm ci z package-lock.json, bez skryptów instalacyjnych)…")
        kod, ogon = _strumien([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--include=dev"],
                              cwd=web, env=env, log=log)
        if kod:
            raise BladHermesa(f"npm ci w {web} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
        log("Hermes: budowa frontu (npm run build)…")
        kod, ogon = _strumien([npm, "run", "build"], cwd=web, env=env, log=log, przemilcz=_linia_vite)
        if kod:
            raise BladHermesa(f"npm run build w {web} nie przeszedł (kod {kod}):\n" + _koncowka(*ogon))
        if not (dist / "index.html").is_file():
            raise BladHermesa(f"npm run build skończył się bez błędu, ale nie ma {dist / 'index.html'}.")
        _wyklucz(checkout, ZNACZNIK, ZNACZNIK_WEB)
        przenosne.zapisz_atomowo(checkout / ZNACZNIK_WEB, json.dumps(
            {"commit": commit, "zbudowano": _teraz()}, indent=2) + "\n")
        _usun_node_modules(checkout, log)
    log(f"Hermes: front dashboardu gotowy ({dist})")
    return dist_jarva(u, dist, log=log) if jarva else dist


def _skrot_dista(dist: Path, brand: Path) -> str:
    """sha256 treści dista (ścieżki względne z „/” i skróty plików, w stałej kolejności) i plików brandingu."""
    h = hashlib.sha256(b"jarvo-dist/1\0")
    pliki = sorted((p for p in dist.rglob("*") if p.is_file()), key=lambda p: p.relative_to(dist).as_posix())
    for p in pliki:
        h.update(p.relative_to(dist).as_posix().encode("utf-8") + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    for nazwa in PLIKI_BRANDINGU:
        p = brand / nazwa
        h.update(f"branding/{nazwa}\0".encode("utf-8") + (hashlib.sha256(p.read_bytes()).digest() if p.is_file() else b"-"))
    return h.hexdigest()


def _linia_latki(linia: str) -> bool:
    """Wiersze „✓ …” i „· …” łatki zostają w ogonie (do komunikatu błędu), ale nie zasypują logu instalacji."""
    return linia.lstrip().startswith(("✓", "·"))


def dist_jarva(u: Uklad, dist: Path, *, brand: Path | None = None, log: Callable[[str], None] = print) -> Path:
    """Kopia frontu `dist` z łatkami Jarva w `<program>/web-dist/<skrót>` (S12, H16; docstring modułu) i jej katalog;
    obok `<skrót>.json` z opisem (poza katalogiem dista: dashboard podaje każdy plik dista pod `/`). Gotowa kopia
    = bez łatania. Łatka, której nie ma albo która nie pasuje do dista = ostrzeżenie w logu i `dist` bez zmian."""
    dist = Path(dist)
    brand = Path(brand) if brand else APP / "branding"
    latka = brand / "patch_dashboard.py"
    if not latka.is_file():
        log(f"Hermes: UWAGA: nie ma {latka}, więc panel dostaje front Hermesa bez brandingu Jarva.")
        return dist
    skrot = _skrot_dista(dist, brand)
    katalog = u.program / "web-dist"
    docelowy, opis = katalog / skrot[:16], katalog / f"{skrot[:16]}.json"

    def gotowy() -> bool:
        return (docelowy / "index.html").is_file() and srodowisko.wczytaj_json(opis).get("skrot") == skrot

    if gotowy():
        log(f"Hermes: front z łatkami Jarva już jest ({docelowy})")
        return docelowy
    with przenosne.Zamek(u.stan / "hermes.lock"):
        if gotowy():                                   # drugi instalator skończył, gdy czekaliśmy
            return docelowy
        nowy = katalog / f"{skrot[:16]}.new"
        for stary in (nowy, docelowy):                 # resztki przerwanej łatki albo kopia bez opisu: od nowa
            if stary.exists():
                _usun_drzewo(stary)
        katalog.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dist, nowy)
        log("Hermes: łatki Jarva we froncie panelu (powłoka /jarvo, marka, polski, bez „Update Hermes”)…")
        argv = [sys.executable, "-I", "-X", "utf8", str(latka), str(brand), "--web", str(nowy), "--natywnie"]
        try:
            kod, ogon = _strumien(argv, cwd=brand, env=_baza(), log=log, przemilcz=_linia_latki)
        except BladHermesa as e:
            kod, ogon = -1, [str(e)]
        if kod:
            try:
                _usun_drzewo(nowy)
            except OSError:
                pass
            log(f"Hermes: UWAGA: łatki Jarva nie pasują do frontu tej wersji Hermesa (kod {kod}). Panel działa z "
                "frontem Hermesa bez brandingu, a jego przycisku „Update Hermes” nie używaj (zrywa przypiętą wersję; "
                "Jarvo aktualizuje `jarvo update`). Ostatnie linie:\n" + _koncowka(*ogon))
            return dist
        _przenies(nowy, docelowy)
        przenosne.zapisz_atomowo(opis, json.dumps({"skrot": skrot, "zrodlo": str(dist), "branding": str(brand),
                                                   "zbudowano": _teraz()}, ensure_ascii=False, indent=2) + "\n")
    log(f"Hermes: front z łatkami Jarva gotowy ({docelowy})")
    return docelowy


# --- konfiguracja ---------------------------------------------------------------------------------------------------

def _env_cli(env: dict, hermes_home: str) -> dict[str, str]:
    """Środowisko CLI Hermesa: `env` bez zmiennych obcych (inny Hermes, PYTHONPATH, PYTHONHOME…), HERMES_HOME
    Jarva, wyjście w UTF-8 (chyba że wywołujący ustawił inaczej) i na Windows bez szukania w bieżącym katalogu."""
    obce = {o.upper() for o in srodowisko.OBCE}
    wynik = {str(k): str(v) for k, v in dict(env).items() if str(k).upper() not in obce}
    for klucz, wartosc in (("PYTHONUTF8", "1"), ("PYTHONIOENCODING", "utf-8")):
        if not any(k.upper() == klucz for k in wynik):
            wynik[klucz] = wartosc
    _ustaw(wynik, "HERMES_HOME", str(hermes_home))
    if WINDOWS:
        _ustaw(wynik, _BEZ_CWD, "1")
    return wynik


def _cytat_bash(tekst: str) -> str:
    return "'" + tekst.replace("'", "'\\''") + "'"


def _dom_windows(dom: Path) -> dict[str, Path]:
    """Katalogi użytkownika dla programów Windows w terminalu agenta, wszystkie w katalogu domowym profilu `dom`
    (H24): USERPROFILE (~ w Pythonie, os.homedir w Node), APPDATA, LOCALAPPDATA, XDG_CONFIG_HOME oraz konfiguracja
    gh, Codex CLI i npm."""
    appdata = dom / "AppData" / "Roaming"
    return {
        "USERPROFILE": dom,
        "APPDATA": appdata,
        "LOCALAPPDATA": dom / "AppData" / "Local",
        "XDG_CONFIG_HOME": dom / ".config",
        "GH_CONFIG_DIR": appdata / "GitHub CLI",
        "CODEX_HOME": dom / ".codex",
        "NPM_CONFIG_USERCONFIG": dom / ".npmrc",
    }


def _powloka_windows(dom: Path) -> str:
    """Treść pliku terminal.shell_init_files dla Windows: eksporty z _dom_windows w formie Windows (Git Bash
    przekazuje je programom natywnym bez zmian), LF, każda wartość w apostrofach basha."""
    linie = ["# Jarvo (docs/NATYWNIE.md, H24 i sekcja d): plik zapisuje jarvo/hermes.py przy każdej instalacji.",
             "# Git Bash czyta go przed migawką środowiska terminala agenta (terminal.shell_init_files), więc",
             "# programy Windows widzą katalog domowy profilu, a nie katalogi właściciela."]
    linie += [f"export {k}={_cytat_bash(str(v))}" for k, v in _dom_windows(dom).items()]
    return "\n".join(linie) + "\n"


def _przygotuj_powloke(u: Uklad, profil: str, dom: Path) -> Path:
    """`<stan>/powloka/<profil>.sh` i katalogi, na które wskazuje (Codex CLI odmawia pracy, gdy CODEX_HOME nie
    istnieje). Ta sama treść = bez zapisu."""
    katalogi = _dom_windows(dom)
    for k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "CODEX_HOME"):
        katalogi[k].mkdir(parents=True, exist_ok=True)
    plik = u.stan / "powloka" / f"{profil}.sh"
    tresc = _powloka_windows(dom)
    try:
        jest = plik.read_text(encoding="utf-8")
    except OSError:
        jest = None
    if jest != tresc:
        przenosne.zapisz_atomowo(plik, tresc)
    return plik


def _klucze_profilu(u: Uklad, profil: str, home: Path) -> list[tuple[str, str, object, bool]]:
    """BEZPIECZNE i, na Windows, terminal.shell_init_files z plikiem tego profilu (H24)."""
    klucze = list(BEZPIECZNE)
    if WINDOWS:
        plik = str(_przygotuj_powloke(u, profil, home / "home"))
        klucze.append(("terminal.shell_init_files", json.dumps([plik]), [plik], True))
    return klucze


def _config_get(checkout: Path, env: dict, profil: str, klucz: str) -> tuple[bool, object]:
    """(czy ta wersja zna klucz, wartość z config.yaml albo domyślna) przez `config get --json`."""
    w = _wywolaj(argv_hermesa(checkout, "-p", profil, "config", "get", klucz, "--json"), env=env, cwd=checkout,
                 opis=f"hermes config get {klucz}")
    if w.returncode:
        if "config key not set" in f"{w.stderr}\n{w.stdout}".lower():
            return False, None
        raise BladHermesa(f"hermes -p {profil} config get {klucz}: kod {w.returncode}:\n"
                          + _koncowka(w.stdout, w.stderr))
    linie = [x for x in w.stdout.splitlines() if x.strip()]
    try:
        return True, json.loads(linie[-1])
    except (IndexError, ValueError):
        raise BladHermesa(f"hermes config get {klucz} --json: nie rozumiem odpowiedzi:\n"
                          + _koncowka(w.stdout)) from None


def konfiguracja_bezpieczna(u: Uklad, checkout: Path, env: dict, log: Callable[[str], None] = print, *,
                            profile: Iterable[str] = ()) -> None:
    """Bezpieczne wartości w config.yaml HERMES_HOME Jarva (lista BEZPIECZNE, na Windows także shell_init_files;
    źródła w docstringu modułu) przez `hermes config set`; potem odczyt kontrolny. `profile`: nazwy zainstalowanych
    profili floty do ustawienia tak samo (I13: we wszystkich profilach). Wartość już zgodna = bez zapisu. Brak
    wymaganego klucza w tej wersji albo profilu = BladHermesa."""
    checkout = Path(checkout)
    env = _env_cli(env, str(u.dane))
    u.dane.mkdir(parents=True, exist_ok=True)
    profile = list(profile)
    for p in profile:
        if not _PROFIL.fullmatch(p) or p == "default":
            raise BladHermesa(f"Zła nazwa profilu Hermesa: {p!r}.")
        if not (u.dane / "profiles" / p).is_dir():   # bez pustych katalogów profilu z plików powłoki (Windows)
            raise BladHermesa(f"Nie ma profilu {p} ({u.dane / 'profiles' / p}): najpierw go zainstaluj, potem "
                              "konfiguracja.")
    for profil in ["default", *profile]:
        home = u.dane if profil == "default" else u.dane / "profiles" / profil
        gdzie = "" if profil == "default" else f" (profil {profil})"
        for klucz, tekst, oczekiwana, wymagany in _klucze_profilu(u, profil, home):
            jest, obecna = _config_get(checkout, env, profil, klucz)
            if not jest:
                if wymagany:
                    raise BladHermesa(f"Ta wersja Hermesa nie zna klucza {klucz}. Zanim ją przypniesz, sprawdź w jej "
                                      "kodzie, czym go zastąpiono (docs/NATYWNIE.md, I13).")
                log(f"Hermes{gdzie}: tej wersji nie dotyczy {klucz} (nie ma takiego klucza), pomijam")
                continue
            if obecna != oczekiwana:
                w = _wywolaj(argv_hermesa(checkout, "-p", profil, "config", "set", klucz, tekst), env=env,
                             cwd=checkout, opis=f"hermes config set {klucz}")
                if w.returncode:
                    raise BladHermesa(f"hermes -p {profil} config set {klucz} {tekst}: kod {w.returncode}:\n"
                                      + _koncowka(w.stdout, w.stderr))
                jest, obecna = _config_get(checkout, env, profil, klucz)
                if obecna != oczekiwana:
                    raise BladHermesa(f"{klucz}{gdzie}: po zapisie Hermes podaje {obecna!r}, a ma być {oczekiwana!r}.")
                log(f"Hermes{gdzie}: {klucz} = {tekst}")
            if klucz == "terminal.home_mode":
                (home / "home").mkdir(parents=True, exist_ok=True)   # bez katalogu Hermes zostawia HOME właściciela


def _zmienna(env: dict, nazwa: str) -> str:
    """Wartość zmiennej z `env` bez względu na wielkość liter nazwy (Windows) albo ""."""
    return next((str(v) for k, v in env.items() if str(k).upper() == nazwa and v), "")


def wersja(checkout: Path, env: dict, *, u: Uklad | None = None) -> str:
    """Wersja Hermesa z `hermes -p default --version` (np. "0.21.5"), zawsze w HERMES_HOME Jarva: `u.dane`, a bez
    `u` HERMES_HOME z `env` od srodowisko.srodowisko(u), czyli `<JARVO_ROOT>/dane`. Inny katalog (np. prywatny Hermes
    właściciela, gdzie Hermes czyta config i zapisuje .update_check) = BladHermesa bez uruchamiania. `-p default`
    omija lepki active_profile. Po konfiguracja_bezpieczna() bez pytania GitHuba."""
    env = dict(env)
    if u is not None:
        dom = str(u.dane)
    else:
        dom, korzen = _zmienna(env, "HERMES_HOME"), _zmienna(env, "JARVO_ROOT")
        if not dom or not korzen or not _ta_sama(dom, Path(korzen) / "dane"):
            raise BladHermesa("wersja(): HERMES_HOME spoza Jarva (ma być <JARVO_ROOT>/dane); użyj "
                              "srodowisko.srodowisko(u) albo podaj u=.")
    w = _wywolaj(argv_hermesa(checkout, "-p", "default", "--version"), env=_env_cli(env, dom), cwd=Path(checkout),
                 opis="hermes --version")
    m = _WERSJA.search(w.stdout or "")
    if w.returncode or not m:
        raise BladHermesa(f"hermes --version: kod {w.returncode}, brak wersji w odpowiedzi:\n"
                          + _koncowka(w.stdout, w.stderr))
    return m.group(1)

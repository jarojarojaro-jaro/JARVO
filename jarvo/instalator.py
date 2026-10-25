"""Instalator Jarva natywnie: `jarvo instaluj` po bootstrapie (docs/NATYWNIE.md, c3, c1, c4, N01, L01–L03, H05,
S01, S11, F12; etapy E3 i E4).

Bootstrap (jarvo/bootstrap/install.ps1 albo install.sh) pobiera uv i Pythona 3.13 z sumami wpisanymi w skrypt, kod
Jarva z GitHuba do `<program>/app/<sha12>` i woła `python -I -X utf8 <app>/jarvo/start.py instaluj` (bez
JARVO_TOKEN: klucz był potrzebny tylko do pobrania kodu). Po jednym poleceniu Jarvo działa z flotą. Krok po kroku,
z paskiem i nazwą kroku:

   1. sprawdzenie: platforma (bez Maca z Intelem, I06), stara instalacja z WSL/Dockerem w tym miejscu, korzeń jako
      osobny katalog (same katalogi Jarva: ochrona dostępu obejmuje całe drzewo), porty panelu i API, wolne miejsce,
   2. katalogi z c1; cały korzeń tylko dla właściciela (przenosne.chron z dziedziczeniem w dół: korzeń na innym
      dysku dziedziczyłby zapis dla Użytkowników uwierzytelnionych, a autostart uruchamia kod z `<program>` jako
      właściciel), `<dane>` i `<stan>` jeszcze osobno,
   3. narzędzia z manifestu (vendor/natywne.lock.json): każdy wpis z `kiedy: instalacja` z plikiem dla tej platformy
      (wpis `brak` pomijamy), w kolejności uv, Python 3.13 i 3.12, git (Windows: Git for Windows z Git Bash), Node.js,
      potem reszta (ffmpeg, Chrome for Testing, pandoc, qpdf, ExifTool, pixi…), każde przez pobieracz: suma przed
      rozpakowaniem, katalog wersji, drugi przebieg bez sieci (znacznik z sumą),
   4. venvy z `kiedy: instalacja` (narzedzia, ocr, claude-seo; jarvo/venvy.py: uv venv + uv pip install
      --require-hashes --no-deps z locka o sumie z manifestu, do `<program>/venvs/<nazwa>-<skrót locka>`),
   5. modele z `kiedy: instalacja` do `<dane>/jarvo/models` (jarvo/modele.py: lektory, Indra OCR, języki
      Tesseracta, fonty Noto), potem Tesseract z pixi.lock (jarvo/tesseract.py, TESSDATA_PREFIX na tessdata-fast),
   6. `<stan>/narzedzia.json` (narzędzia, venvy, modele, Tesseract), 7. wersja Jarva (kod tej wersji),
   8. Hermes: checkout przypiętego commitu i `uv sync --locked` (jarvo/hermes.py, I02) gitem z manifestu (Windows),
   9. front panelu zawsze z checkoutu bieżącego pinu npm-em z Node.js z manifestu (hermes.web_dist pomija gotowy;
      `--web-lokalnie` buduje go od nowa); bez Node.js jasna rada,
  10. bezpieczne ustawienia Hermesa (I13),
  11. klucz API bramy (H05): API_SERVER_KEY (secrets.token_hex(32)) i API_SERVER_PORT (JARVO_API_PORT, potem port
      już zapisany, inaczej 8642) w `<dane>/.env` tylko dla właściciela; bez klucza brama nie otwiera /v1/runs,
  12. przełączenie wersji: `<program>/current.json` dopiero teraz, atomowo, po udanych krokach 3–11, więc nieudana
      aktualizacja zostawia działającą starą wersję; serwis starej zatrzymujemy tuż przed przełączeniem (na ten czas
      znacznik zatrzymania), poprzedni current.json zostaje obok (current.poprzedni.json),
  13. programy floty w `<program>/bin-floty` (jarvo/bin_floty.py: python3, jarvo-tts, jarvo-stt, jarvo-klucz,
      tesseract; S01, F12), tylko w PATH procesów Jarva,
  14. flota (jarvo/flota.py): build.py w układzie natywnym ze ścieżkami instalacji (--py = Python venvu narzędzi,
      --bin-dir = bin-floty, --hermes-src = checkout) i install_fleet.py; restart usług zleca krok „Serwis”,
  15. `<stan>/srodowisko.json` (tylko część Jarva: bez PATH właściciela i przełączników bootstrapu, więc drugi
      przebieg z innego okna niczego nie zmienia; ze zmiennymi narzędzi i bramy z buildu) i `<stan>/ustawienia.json`
      (JARVO_PANEL_PORT, JARVO_API_PORT: zadanie Harmonogramu nie przekazuje zmiennych sesji, więc porty pamięta
      instalacja),
  16. polecenie `jarvo` dla właściciela: Windows `<root>\\bin\\jarvo.cmd` i wpis w PATH użytkownika (HKCU\\Environment,
      rozgłoszenie WM_SETTINGCHANGE), macOS i Linux `~/.local/bin/jarvo` i oznaczony blok PATH w ~/.zprofile albo
      ~/.profile, gdy trzeba; `--bez-path`: tylko `<root>/bin/jarvo`, bez zmian poza katalogiem Jarva (próby),
  17. autostart nadzorcy (jarvo/autostart.py), na razie bez startu; błąd (brak user busa systemd, sesja bez GUI na
      macOS, polityka Harmonogramu) to uwaga z radą, a instalacja idzie dalej; nowy plist na macOS od razu
      wyładowany ze starą definicją (launchd trzyma ją w pamięci, a `kickstart` uruchomiłby starą),
  18. serwis: zdjęty znacznik zatrzymania i start mechanizmem autostartu, gdy działa (IgnoreNew trzyma jedną kopię),
      inaczej `jarvo serwis` w tle z otoczeniem bez sekretów; działający serwis startuje od nowa, gdy ten przebieg
      zmienił current.json, ustawienia, klucz API, środowisko procesów (nadzorca trzyma je od swojego startu) albo
      definicję autostartu; gdy zmieniła się tylko flota, nadzorca restartuje bramę albo panel (jak install-fleet.sh),
  19. czekanie na NASZ panel: /api/status z hermes_home = `<dane>` (port 9119 może trzymać stara flota z WSL albo
      prywatny Hermes właściciela; wtedy od razu komunikat, kto trzyma port); serwis, który nie działa, albo panel
      w postoju to błąd od razu, bez czekania na limit. Panel, który wstał po instalacji floty, potwierdza jej
      odcisk wtyczek (flota.potwierdz_restart_panelu).

Każda zmiana poza katalogami Jarva idzie przez jarvo/zmiany_hosta.py (wpis w dzienniku przed zmianą, D08), żeby
`jarvo uninstall` cofnął ją od końca. Przebieg jest idempotentny: drugi niczego nie zmienia (narzędzia ze zgodną
sumą zostają, pliki zapisujemy tylko przy innej treści, PATH i blok rc tylko, gdy ich brak). Instalacja spod
JARVO_ROOT innego niż domyślny dostaje korzeń w argv (`jarvo --korzen <root> …`) w poleceniu jarvo i w autostarcie:
zadanie Harmonogramu nie przekazuje zmiennych środowiska. Programy systemu wołamy pełną ścieżką, a instalator pracuje
w katalogu kodu Jarva: nic nie zostanie wzięte z katalogu, w którym wklejono polecenie instalacji. Wszystko, co
dotyka komputera (rejestr, procesy w tle, sieć lokalna, moduły ładowane przy użyciu), idzie przez `Otoczenie`, które
testy podmieniają atrapami.
"""
from __future__ import annotations

import contextlib
import importlib.util
import dataclasses
import http.client
import importlib
import inspect
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import manifest, pobieracz, przenosne, sciezki, srodowisko
from .sciezki import MACOS, WINDOWS, Uklad

# bez resolve(): na Windows rozwinąłby krótką nazwę 8.3 (ASCII) do pełnej z polskimi znakami, a `<program>` ma mieć
# ścieżkę ASCII (c1); tak samo w jarvo/start.py
APP = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # kod tej wersji (jarvo/ i vendor/)
PORT_PANELU = 9119                                   # jak nadzorca.PORT_PANELU; inny: JARVO_PANEL_PORT
PORT_API = 8642                                      # API bramy Hermesa (H05); inny: JARVO_API_PORT
SCIEZKA_PANELU = "/"            # panel Hermesa; adres HQ (/jarvo) dojdzie z wtyczką floty w etapie E4
ZNACZNIK = "Jarvo natywnie (jarvo instaluj)"         # w poleceniu jarvo: plik jest nasz i wolno go nadpisać
# kolejność narzędzi (c3): uv → Python → git (Windows: checkout Hermesa i Git Bash) → Node.js (front panelu) → reszta
PIERWSZE = ("uv", "python313", "python312", "git", "node")
OPISY = {"uv": "uv", "python313": "Python 3.13", "python312": "Python 3.12", "git": "git i Git Bash",
         "node": "Node.js i npm"}
MIN_MIEJSCA_GB = 2              # próg odmowy; cała instalacja z flotą zajmuje więcej (ROZMIAR_GB, uwaga w kroku 1)
# instalacja z flotą zmierzona 2026-10-25 na Windows 11 x64: 8,5 GB = <program> 4,6 GB (narzędzia 2,1, venvy 1,5,
# Hermes 1,2) + cache 3,4 GB (koła uv 1,4, źródła skilli 0,94, archiwa narzędzi 0,69, pixi 0,35) + dane 0,46 GB
ROZMIAR_GB = 9
CZAS_PANELU = 180.0             # pierwszy start panelu (import Hermesa, bazy) trwa kilkanaście–kilkadziesiąt sekund
CZAS_NADZORCY = 30.0            # tyle czekamy, aż nadzorca otworzy kanał (start przez autostart, czekanie na panel)
CZAS_STOPU = 120.0              # drenaż bramy i zatrzymanie panelu; dłużej, gdy nadzorca poda CZAS_ZATRZYMANIA
PATH_RC = ('case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac  '
           "# polecenie jarvo (usunie je jarvo uninstall)")
# korzeń to osobny katalog Jarva: chron obejmuje całe drzewo, więc katalogu z cudzymi plikami nie ruszamy
W_KORZENIU = frozenset({"program", "dane", "stan", "logi", "cache", "build", "bin", "desktop.ini", "thumbs.db",
                        ".ds_store"})
PRZYKLAD_KORZENIA = "D:\\Jarvo" if WINDOWS else "~/jarvo-natywnie"
# zmienne instalacji w <stan>/ustawienia.json: polecenie jarvo bierze je, gdy nie ma ich w otoczeniu, bo zadanie
# Harmonogramu, LaunchAgent i jednostka systemd nie znają zmiennych sesji, w której instalowano
USTAWIENIA = ("JARVO_PANEL_PORT", "JARVO_API_PORT")
_LINIA_ENV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
ZATRZYMANIE = "zatrzymany.json"  # <stan>/zatrzymany.json: znacznik `jarvo down` (zapas, gdy nadzorca go nie zna)
MECHANIZMY_STARTU = ("harmonogram", "launchagent", "systemd")   # autostart, który umie uruchomić serwis od razu
LOG_STARTU = "serwis-start.log"
MAKS_LOGU_STARTU = 5 * 2 ** 20  # większy przy starcie serwisu idzie do .1


class BladInstalacji(RuntimeError):
    """Krok instalacji się nie udał: komunikat po polsku z radą, bez sekretów."""


# ---------------------------------------------------------------- programy systemu, sieć lokalna, procesy w tle

def modul(nazwa: str) -> Any:
    """Moduł pakietu jarvo ładowany dopiero przy użyciu: `jarvo --help`, status i doctor działają też przy
    niepełnej instalacji (np. bez nadzorcy), a polecenie mówi wtedy, czego brakuje."""
    return importlib.import_module(f"{__package__}.{nazwa}")


def wywolaj(f: Callable, *argumenty, **nazwane) -> Any:
    """f(*argumenty, **nazwane) bez argumentów nazwanych, których f nie przyjmuje: moduły rodzeństwa (autostart,
    nadzorca) dochodzą do nowych parametrów (env, powod) w swoim tempie, a starsza wersja ich nie zna."""
    try:
        parametry = inspect.signature(f).parameters
    except (TypeError, ValueError):
        return f(*argumenty, **nazwane)
    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parametry.values()):
        nazwane = {k: v for k, v in nazwane.items() if k in parametry}
    return f(*argumenty, **nazwane)


def systemowy(nazwa: str) -> str | None:
    """Program systemu pełną ścieżką: Windows `%SystemRoot%\\System32\\<nazwa>.exe` (goła nazwa w CreateProcess
    szuka najpierw w katalogu bieżącym), POSIX pierwszy z bezwzględnych katalogów PATH i /usr/sbin, /sbin."""
    if WINDOWS:
        p = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / f"{nazwa}.exe"
        return str(p) if p.is_file() else None
    katalogi = [k for k in os.environ.get("PATH", "").split(os.pathsep) if os.path.isabs(k)]
    return shutil.which(nazwa, path=os.pathsep.join(dict.fromkeys([*katalogi, "/usr/sbin", "/sbin", "/usr/bin",
                                                                   "/bin"])))


def program_bezwzgledny(ot: "Otoczenie", nazwa: str) -> str | None:
    """Program z PATH tylko z pełną ścieżką: względny wpis w PATH (albo katalog bieżący) nie podsunie cudzego gita."""
    p = ot.program(nazwa)
    return p if p and os.path.isabs(p) else None


def _uruchom(argv: list, czas: float = 20) -> subprocess.CompletedProcess:
    return subprocess.run([str(x) for x in argv], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=czas, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def port_zajety(port: int, czas: float = 0.3) -> bool:
    """Czy ktoś słucha na 127.0.0.1:<port> (połączenie TCP, bez wysyłania danych)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=czas):
            return True
    except OSError:
        return False


def sluchacz(port: int) -> tuple[int, str] | None:
    """(PID, nazwa programu), który słucha na porcie, albo None, gdy nie wiadomo: netstat i tasklist z System32
    (Windows), lsof (POSIX). Gniazdo słuchające rozpoznajemy po adresie obcym *:0, bo nazwa stanu (LISTENING)
    zależy od języka Windowsa."""
    try:
        if WINDOWS:
            netstat, tasklist = systemowy("netstat"), systemowy("tasklist")
            if not netstat:
                return None
            for linia in _uruchom([netstat, "-ano", "-p", "TCP"]).stdout.splitlines():
                cz = linia.split()
                if (len(cz) == 5 and cz[1].rsplit(":", 1)[-1] == str(port) and cz[2] in ("0.0.0.0:0", "[::]:0")
                        and cz[4].isdigit()):
                    nazwa = "?"
                    if tasklist:
                        wynik = _uruchom([tasklist, "/FI", f"PID eq {cz[4]}", "/FO", "CSV", "/NH"]).stdout.strip()
                        nazwa = wynik.split(",")[0].strip('"') if wynik.startswith('"') else "?"
                    return int(cz[4]), nazwa
            return None
        lsof = systemowy("lsof")
        if not lsof:
            return None
        pid = nazwa = None
        for linia in _uruchom([lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"]).stdout.splitlines():
            if linia.startswith("p") and pid is None:
                pid = linia[1:]
            elif linia.startswith("c") and nazwa is None:
                nazwa = linia[1:]
        return (int(pid), nazwa or "?") if pid and pid.isdigit() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def kto_slucha(port: int) -> str | None:
    """`nazwa (PID n)` programu, który słucha na porcie (sluchacz), albo None."""
    s = sluchacz(port)
    return f"{s[1]} (PID {s[0]})" if s else None


def zapytaj_http(url: str, czas: float = 2.0) -> tuple[int, Any] | None:
    """GET `url` na tym komputerze, bez proxy z ustawień systemu (127.0.0.1 nigdy nie idzie przez serwer
    pośredniczący): (kod HTTP, treść JSON albo None) albo None, gdy nikt nie odpowiada. Kod 0: ktoś słucha, ale nie
    mówi po HTTP."""
    otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    zadanie = urllib.request.Request(url, headers={"User-Agent": "jarvo", "Accept": "application/json"})
    try:
        with otwieracz.open(zadanie, timeout=czas) as odp:
            kod, dane = odp.status, odp.read(1 << 20)
    except urllib.error.HTTPError as e:
        kod, dane = e.code, b""
    except http.client.HTTPException as e:
        return None if isinstance(e, ConnectionError) else (0, None)   # RemoteDisconnected = jeszcze nie słucha
    except (urllib.error.URLError, OSError, ValueError):
        return None
    try:
        return kod, json.loads(dane.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return kod, None


def uruchom_w_tle(argv: list[str], env: dict, log: Path) -> int:
    """Proces odłączony od tego terminala (zamknięcie okna go nie kończy), wyjście dopisywane do `log`. Na Windows
    bez okna, we własnej grupie i poza zadaniem (Job) rodzica, jeśli zadanie na to pozwala."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as wyj:
        kw: dict[str, Any] = dict(stdin=subprocess.DEVNULL, stdout=wyj, stderr=subprocess.STDOUT, env=env,
                                  cwd=str(Path(argv[0]).parent), close_fds=True)
        if not WINDOWS:
            return subprocess.Popen(argv, start_new_session=True, **kw).pid
        flagi = przenosne.flagi_tla()
        try:
            return subprocess.Popen(argv, creationflags=flagi | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw).pid
        except OSError:                      # zadanie rodzica nie pozwala na wyjście (np. część runnerów CI)
            return subprocess.Popen(argv, creationflags=flagi, **kw).pid


@dataclass
class Otoczenie:
    """Wszystko, czego instalator i polecenia używają poza własnymi plikami: moduły Jarva ładowane przy użyciu,
    zmienne procesu, rejestr Windows (atrapa z interfejsem zmiany_hosta.Rejestr), programy z PATH, procesy w tle,
    sieć lokalna (zapytanie HTTP, kto słucha na porcie), przeglądarka i zegar. Testy podstawiają atrapy, więc nie
    dotykają komputera."""
    modul: Callable[[str], Any] = modul
    env: dict = field(default_factory=lambda: dict(os.environ))
    rejestr: Any = None                                  # None = winreg (zmiany_hosta.Rejestr)
    program: Callable[[str], str | None] = przenosne.program
    uruchom_w_tle: Callable[[list[str], dict, Path], int] = uruchom_w_tle
    zapytaj_http: Callable[[str, float], tuple[int, Any] | None] = zapytaj_http
    sluchacz: Callable[[int], tuple[int, str] | None] = sluchacz
    otworz: Callable[[str], bool] | None = None          # przeglądarka; None = webbrowser.open
    na_pierwszym_planie: Callable[[list[str], dict], int] | None = None   # None = cli.uruchom_na_pierwszym_planie
    czekaj: Callable[[float], None] = time.sleep
    zegar: Callable[[], float] = time.monotonic


# ---------------------------------------------------------------- układ wersji: Python, polecenie, panel, serwis

def _klucz(p: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def ten_sam_katalog(a: Path | str, b: Path | str) -> bool:
    """Ta sama ścieżka (bez wielkości liter na Windows) albo ten sam katalog na dysku (krótka nazwa 8.3, dowiązanie)."""
    if _klucz(a) == _klucz(b):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def bezwzgledny(u: Uklad) -> Uklad:
    """Układ ze ścieżkami bezwzględnymi (os.path.abspath, bez resolve(): krótka nazwa 8.3 zostaje, c1)."""
    return dataclasses.replace(u, **{f.name: Path(os.path.abspath(getattr(u, f.name))) for f in dataclasses.fields(u)})


def korzen_domyslny(u: Uklad, env: dict | None = None) -> bool:
    """Czy `u` to domyślny korzeń tego użytkownika (a nie JARVO_ROOT próby, CI albo drugiej instalacji)."""
    env = {k: v for k, v in (os.environ if env is None else env).items() if k != "JARVO_ROOT"}
    try:
        return _klucz(sciezki.uklad(env).root) == _klucz(u.root)
    except sciezki.BladUkladu:
        return False


def korzen_nieosobny(u: Uklad) -> str | None:
    """Powód odmowy, gdy korzeń nie jest osobnym katalogiem Jarva (katalog główny dysku, katalog domowy albo katalog
    z cudzymi plikami): ochrona dostępu (chron) obejmuje całe drzewo korzenia."""
    root = Path(os.path.abspath(u.root))
    if root.parent == root:
        return f"{root} to katalog główny dysku"
    dom = _klucz(Path.home())
    if _klucz(root) == dom or dom.startswith(_klucz(root).rstrip("\\/") + os.sep):
        return f"{root} to katalog domowy albo katalog nad nim"
    try:
        nazwy = [e.name for e in os.scandir(root)]
    except OSError:
        return None
    obce = sorted(n for n in nazwy if n.casefold() not in W_KORZENIU and not n.startswith(".doctor-"))
    if obce:
        return f"w {root} są pliki spoza Jarva: {', '.join(obce[:5])}{' …' if len(obce) > 5 else ''}"
    return None


def python_jarva(u: Uklad, *, okno: bool = True) -> Path:
    """Python polecenia jarvo i nadzorcy: python313 z `<stan>/narzedzia.json` (PBS, SQLite 3.53). `okno=False` na
    Windows = pythonw.exe (autostart i serwis w tle bez konsoli). Bez wpisu: bieżący interpreter."""
    katalog = (srodowisko.narzedzia(u).get("python313") or {}).get("katalog")
    if katalog:
        k = Path(katalog)
        p = k / ("python.exe" if okno else "pythonw.exe") if WINDOWS else k / "bin" / "python3"
        if p.is_file():
            return p
    exe = Path(sys.executable)
    if WINDOWS and not okno and exe.with_name("pythonw.exe").is_file():
        return exe.with_name("pythonw.exe")
    return exe


def katalog_aplikacji(u: Uklad) -> Path:
    """Kod aktywnej wersji Jarva: `app` z current.json, a bez instalacji katalog, z którego działa ten kod."""
    app = srodowisko.biezace(u).get("app")
    return Path(app) if app and (Path(app) / "jarvo" / "start.py").is_file() else APP


def argumenty_korzenia(u: Uklad, env: dict | None = None) -> list[str]:
    """`--korzen <root>` dla instalacji spod JARVO_ROOT (pusta lista dla domyślnego korzenia)."""
    return [] if korzen_domyslny(u, env) else ["--korzen", str(u.root)]


def polecenie_jarva(u: Uklad, *argumenty: str, okno: bool = True, env: dict | None = None) -> list[str]:
    """argv polecenia jarvo aktywnej wersji, np. `polecenie_jarva(u, "serwis", okno=False)` dla autostartu."""
    start = katalog_aplikacji(u) / "jarvo" / "start.py"
    return [str(python_jarva(u, okno=okno)), "-I", "-X", "utf8", str(start), *argumenty_korzenia(u, env),
            *argumenty]


def port_poprawny(wartosc: str) -> bool:
    wartosc = str(wartosc).strip()
    return wartosc.isdigit() and 0 < int(wartosc) < 65536


def port_panelu(env: dict | None = None) -> int:
    """Port panelu: JARVO_PANEL_PORT (próby i druga instalacja obok, ten sam co w nadzorcy) albo 9119."""
    wartosc = str((os.environ if env is None else env).get("JARVO_PANEL_PORT") or PORT_PANELU).strip()
    return int(wartosc) if port_poprawny(wartosc) else PORT_PANELU


def adres_panelu(env: dict | None = None) -> str:
    """Zawsze 127.0.0.1, nie localhost (c4): localhost bywa najpierw ::1, a panel słucha tylko na IPv4."""
    return f"http://127.0.0.1:{port_panelu(env)}{SCIEZKA_PANELU}"


def czytaj_env(plik: Path) -> dict[str, str]:
    """{nazwa: wartość} z pliku .env (bez komentarzy, cudzysłowy zdjęte); brak pliku = {}."""
    try:
        tekst = Path(plik).read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    wynik = {}
    for linia in tekst.splitlines():
        m = _LINIA_ENV.match(linia)
        if not m or linia.lstrip().startswith("#"):
            continue
        wartosc = m.group(2).strip()
        if len(wartosc) >= 2 and wartosc[0] == wartosc[-1] and wartosc[0] in "'\"":
            wartosc = wartosc[1:-1]
        wynik[m.group(1)] = wartosc
    return wynik


def ustaw_w_env(tekst: str, nazwa: str, wartosc: str) -> str:
    """Treść .env z `nazwa=wartosc`: pierwsza linia tej zmiennej podmieniona (kolejne usunięte), a bez niej dopisana
    na końcu; reszta pliku bez zmian, LF."""
    linie = tekst.replace("\r\n", "\n").split("\n")
    if linie and linie[-1] == "":
        linie.pop()
    wynik, jest = [], False
    for linia in linie:
        m = _LINIA_ENV.match(linia)
        if m and m.group(1) == nazwa and not linia.lstrip().startswith("#"):
            if not jest:
                wynik.append(f"{nazwa}={wartosc}")
                jest = True
            continue
        wynik.append(linia)
    if not jest:
        wynik.append(f"{nazwa}={wartosc}")
    return "\n".join(wynik) + "\n"


def port_api(u: Uklad, env: dict | None = None) -> int:
    """Port API bramy (H05): JARVO_API_PORT (próby, druga instalacja obok; pamięta go <stan>/ustawienia.json), potem
    API_SERVER_PORT zapisany w `<dane>/.env`, inaczej 8642."""
    wartosc = str((os.environ if env is None else env).get("JARVO_API_PORT") or "").strip()
    if port_poprawny(wartosc):
        return int(wartosc)
    zapisany = czytaj_env(u.dane / ".env").get("API_SERVER_PORT", "").strip()
    return int(zapisany) if port_poprawny(zapisany) else PORT_API


def klucz_api_dobry(klucz: str) -> bool:
    """Klucz, z którym brama otworzy API (Hermes: has_usable_secret, co najmniej 16 znaków, bez zaślepek)."""
    k = str(klucz or "").strip()
    return len(k) >= 16 and not re.fullmatch(r"(?i)(changeme|change-me|your[-_].*|x+|\*+|<.*>|\.\.\.+)", k)


def narzedzia_instalacji(narz: dict, platforma: str) -> list[str]:
    """Narzędzia manifestu do instalacji na tej platformie: `kiedy: instalacja` (bez pola: instalacja) i plik dla
    platformy (wpis `brak` pomijamy, np. git na macOS i Linuksie, Lightpanda na Windows). Kolejność: PIERWSZE, potem
    reszta alfabetycznie."""
    nazwy = []
    for nazwa, wpis in narz.items():
        if not isinstance(wpis, dict) or (wpis.get("kiedy") or "instalacja") != "instalacja":
            continue
        try:
            manifest.plik(narz, nazwa, platforma)
        except manifest.BrakNarzedzia:
            continue
        nazwy.append(nazwa)
    return sorted(nazwy, key=lambda n: (PIERWSZE.index(n) if n in PIERWSZE else len(PIERWSZE), n))


def ustawienia(u: Uklad) -> dict[str, str]:
    """`<stan>/ustawienia.json`: zmienne tej instalacji (USTAWIENIA), które polecenie jarvo przyjmuje, gdy nie ma
    ich w otoczeniu."""
    dane = srodowisko.wczytaj_json(u.stan / "ustawienia.json")
    return {k: str(dane[k]).strip() for k in USTAWIENIA if str(dane.get(k) or "").strip()}


def env_floty(env: dict) -> dict[str, str]:
    """Otoczenie procesu Jarva bez sekretów i zmiennych obcych (srodowisko.przechodzi: SEKRET, OBCE; bez wielkości
    liter): JARVO_TOKEN, klucze API i agent ssh z powłoki właściciela nie trafiają do nadzorcy, bramy ani panelu."""
    return {k: v for k, v in env.items() if srodowisko.przechodzi(k)}


def stan_serwisu(u: Uklad, ot: Otoczenie | None = None) -> tuple[dict | None, str]:
    """(stan nadzorcy na żywo z jego kanału albo None, powód braku). Nic nie tworzy na dysku."""
    ot = ot or Otoczenie()
    if not u.stan.is_dir():
        return None, "Jarvo nie jest zainstalowane w tym katalogu"
    try:
        nadzorca = ot.modul("nadzorca")
    except ImportError as e:
        return None, f"brak modułu nadzorcy ({e})"
    try:
        stan = nadzorca.polacz(u).status()
    except Exception as e:    # noqa: BLE001 - kanał zamknięty, brak potoku albo gniazda, limit czasu: serwis nie działa
        opis = str(e).strip()[:160]
        return None, opis or type(e).__name__
    return (stan if isinstance(stan, dict) else {"stan": stan}), ""


def stan_autostartu(u: Uklad, ot: Otoczenie) -> dict:
    """autostart.stan(u) albo {"sprawdzony": False, "powod"}: brak instalacji, modułu albo narzędzia systemu."""
    if not u.stan.is_dir():
        return {"sprawdzony": False, "powod": "brak instalacji"}
    try:
        return dict(wywolaj(ot.modul("autostart").stan, u, env=ot.env) or {})
    except Exception as e:                        # noqa: BLE001 - brak modułu albo narzędzia systemu: tylko opis
        return {"sprawdzony": False, "powod": f"{type(e).__name__}: {str(e)[:120]}"}


def bledy_autostartu(auto: Any) -> tuple[type[BaseException], ...]:
    """Błędy włączenia autostartu, przy których instalacja idzie dalej (uwaga z radą): BladAutostartu modułu
    (brak user busa, launchctl bez sesji GUI, polityka Harmonogramu), OSError i ValueError (zły argument)."""
    blad = getattr(auto, "BladAutostartu", None)
    return ((blad,) if isinstance(blad, type) and issubclass(blad, Exception) else ()) + (OSError, ValueError)


# ---------------------------------------------------------------- panel: tylko panel tej instalacji

def stan_panelu(u: Uklad, ot: Otoczenie) -> tuple[str, str]:
    """Kto odpowiada na porcie panelu: ("nasz", "") = dashboard Hermesa tej instalacji (/api/status: hermes_home
    = `<dane>`, a bez tego pola, np. za bramką logowania, install_id z `<dane>/install_id`); ("brak", powód) = nikt
    albo panel jeszcze wstaje (5xx); ("obcy", opis) = inny program: stara flota z WSL (localhost:9119 przekazany
    z WSL), prywatny Hermes właściciela albo cokolwiek innego. Sam zajęty port nie dowodzi, że działa panel Jarva."""
    odp = ot.zapytaj_http(f"http://127.0.0.1:{port_panelu(ot.env)}/api/status", 2.0)
    if odp is None:
        return "brak", "brak odpowiedzi"
    kod, tresc = odp
    if kod >= 500:
        return "brak", f"HTTP {kod}"
    if kod != 200 or not isinstance(tresc, dict) or "version" not in tresc:
        return "obcy", ("program, który nie odpowiada jak panel Hermesa ("
                        + (f"/api/status: HTTP {kod}" if kod else "odpowiedź spoza HTTP") + ")")
    dom = tresc.get("hermes_home")
    if isinstance(dom, str) and dom.strip():
        return ("nasz", "") if ten_sam_katalog(dom, u.dane) else ("obcy", f"panel innego Hermesa (HERMES_HOME {dom})")
    try:
        nasz_id = (u.dane / "install_id").read_text(encoding="utf-8").strip().lower()
    except OSError:
        nasz_id = ""
    if nasz_id and str(tresc.get("install_id") or "").strip().lower() == nasz_id:
        return "nasz", ""
    return "obcy", "panel Hermesa, który nie podaje HERMES_HOME (np. za bramką logowania)"


def opis_obcego_portu(port: int, opis: str, ot: Otoczenie) -> str:
    """Komunikat z radą, gdy port panelu trzyma inny program (kto: sluchacz)."""
    s = ot.sluchacz(port)
    kto = f"{s[1]} (PID {s[0]})" if s else "inny program"
    wsl = (" To port przekazany z WSL: zwykle stara flota Jarvo z Dockerem." if s and "wslrelay" in s[1].lower()
           else "")
    return (f"port {port} na 127.0.0.1 trzyma {kto}: {opis}.{wsl} Panel Jarva na nim nie wstanie. Zamknij ten "
            "program albo daj Jarvu inny port: ustaw JARVO_PANEL_PORT (np. 9129) i uruchom polecenie instalacji "
            "jeszcze raz (instalacja zapamięta port).")


def usluga_nadzorcy(stan: dict | None, nazwa: str) -> dict:
    """Opis usługi `nazwa` ze stanu nadzorcy ({"uslugi": {nazwa: {"stan", "pid", "powod", ...}}}) albo {}."""
    uslugi = stan.get("uslugi") if isinstance(stan, dict) else None
    us = uslugi.get(nazwa) if isinstance(uslugi, dict) else None
    return us if isinstance(us, dict) else {}


def czekaj_na_panel(u: Uklad, ot: Otoczenie, log: Callable[[str], None], limit: float = CZAS_PANELU) -> str:
    """Czeka, aż na porcie panelu odpowie panel TEJ instalacji (stan_panelu); zwraca adres. BladInstalacji od razu,
    gdy port trzyma inny program albo nadzorca postawił panel w postój (kod 78), po CZAS_NADZORCY s bez działającego
    serwisu (np. nie wystartował: powód w serwis-start.log) i po `limit` s (z radą, gdzie szukać przyczyny)."""
    adres = adres_panelu(ot.env)
    start = ot.zegar()
    ostatni = 0
    bez_serwisu: float | None = None
    while True:
        stan, opis = stan_panelu(u, ot)
        if stan == "nasz":
            return adres
        if stan == "obcy":
            raise BladInstalacji(opis_obcego_portu(port_panelu(ot.env), opis, ot))
        teraz = ot.zegar()
        serwis, powod = stan_serwisu(u, ot)
        if serwis is None:
            bez_serwisu = teraz if bez_serwisu is None else bez_serwisu
            if teraz - bez_serwisu >= CZAS_NADZORCY:
                raise BladInstalacji(f"serwis Jarva nie działa ({powod}), więc panel {adres} nie wstanie. Zobacz "
                                     "`jarvo logs serwis-start` i `jarvo logs nadzorca`, potem uruchom `jarvo up`.")
        else:
            bez_serwisu = None
            panel = usluga_nadzorcy(serwis, "panel")
            if panel.get("stan") == "postoj":
                raise BladInstalacji(f"nadzorca zatrzymał panel (kod {panel.get('ostatni_kod', '?')}: "
                                     f"{panel.get('powod') or 'bez powodu'}). Zobacz `jarvo logs panel`, popraw "
                                     "przyczynę, potem `jarvo down` i `jarvo up`.")
        minelo = teraz - start
        if minelo >= limit:
            raise BladInstalacji(f"panel {adres} nie odpowiada po {int(limit)} s ({opis}). Sprawdź `jarvo status` "
                                 "i `jarvo logs panel`, potem uruchom `jarvo panel` jeszcze raz.")
        if int(minelo) // 15 > ostatni:
            ostatni = int(minelo) // 15
            log(f"    czekam na panel… {int(minelo)} s")
        ot.czekaj(1.0)


# ---------------------------------------------------------------- serwis: start, zatrzymanie, znacznik zatrzymania

def _funkcja_nadzorcy(ot: Otoczenie, nazwa: str) -> Callable | None:
    try:
        f = getattr(ot.modul("nadzorca"), nazwa, None)
    except ImportError:
        return None
    return f if callable(f) else None


def oznacz_zatrzymanie(u: Uklad, ot: Otoczenie, powod: str = "") -> bool:
    """Znacznik trwałego zatrzymania `<stan>/zatrzymany.json` (`jarvo down`, aktualizacja): `jarvo serwis` przy nim
    kończy się od razu kodem 0, więc zapasowe wyzwalacze Harmonogramu (co 5 minut, odblokowanie), LaunchAgent ani
    systemd nie podnoszą floty, aż `jarvo up`, `jarvo panel` albo instalacja go zdejmie. True = nadzorca zna znacznik
    (nadzorca.oznacz_zatrzymanie); False = starszy nadzorca bez tej funkcji: zostaje sam plik w tym samym formacie,
    którego taki nadzorca nie sprawdza. BladInstalacji, gdy pliku nie da się zapisać."""
    f = _funkcja_nadzorcy(ot, "oznacz_zatrzymanie")
    try:
        if f is not None:
            wywolaj(f, u, powod=powod)
            return True
        przenosne.zapisz_atomowo(u.stan / ZATRZYMANIE, _json({
            "wersja": 1, "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S"), "powod": powod or None, "pid": os.getpid()}))
    except OSError as e:
        raise BladInstalacji(f"nie zapisałem znacznika zatrzymania {u.stan / ZATRZYMANIE} ({e.strerror or e}): "
                             "autostart może uruchomić serwis znowu") from e
    return False


def zdejmij_zatrzymanie(u: Uklad, ot: Otoczenie) -> None:
    """Zdejmuje znacznik trwałego zatrzymania przed startem serwisu (nadzorca.zdejmij_zatrzymanie albo plik).
    BladInstalacji, gdy pliku nie da się usunąć: serwis przy nim i tak skończyłby się od razu."""
    f = _funkcja_nadzorcy(ot, "zdejmij_zatrzymanie")
    try:
        if f is not None:
            f(u)
        elif u.stan.is_dir():
            (u.stan / ZATRZYMANIE).unlink(missing_ok=True)
    except OSError as e:
        raise BladInstalacji(f"nie zdjąłem znacznika zatrzymania {u.stan / ZATRZYMANIE} ({e.strerror or e}), a przy "
                             "nim serwis od razu się kończy. Usuń ten plik i uruchom `jarvo up`.") from e


def zatrzymanie(u: Uklad) -> dict | None:
    """Treść znacznika trwałego zatrzymania (`kiedy`, `powod`) albo None, gdy go nie ma (do `jarvo status`)."""
    p = u.stan / ZATRZYMANIE
    return (srodowisko.wczytaj_json(p) or {"kiedy": None}) if p.is_file() else None


def _nadzorca_zyje(u: Uklad, nadzorca: Any) -> bool:
    """Czy proces nadzorcy z `<stan>/nadzorca.json` jeszcze żyje (kanał zamyka się chwilę przed końcem procesu, a do
    końca trzyma on blokadę jednej kopii i zadanie Harmonogramu w stanie Running)."""
    try:
        return bool((nadzorca.stan_z_pliku(u) or {}).get("dziala"))
    except Exception:                             # noqa: BLE001 - brak funkcji albo uszkodzony plik: nie wiadomo
        return False


def zatrzymaj_serwis(u: Uklad, ot: Otoczenie, powod: str = "", limit: float | None = None) -> bool:
    """Zatrzymuje działający serwis kanałem nadzorcy (brama kończy trwające tury; nowy nadzorca zapisuje przy tym
    znacznik zatrzymania) i czeka, aż kanał zniknie, a proces nadzorcy się skończy (dopiero wtedy `schtasks /Run`
    i blokada jednej kopii wpuszczą nowego). False = serwis nie działał; BladInstalacji po `limit` s (domyślnie
    CZAS_ZATRZYMANIA nadzorcy z zapasem, co najmniej CZAS_STOPU)."""
    stan, _ = stan_serwisu(u, ot)
    if stan is None:
        return False
    nadzorca = ot.modul("nadzorca")
    if limit is None:
        limit = max(CZAS_STOPU, float(getattr(nadzorca, "CZAS_ZATRZYMANIA", 0) or 0) + 10)
    koniec = ot.zegar() + limit
    try:
        wywolaj(nadzorca.polacz(u).stop, czekaj=limit, powod=powod or "zatrzymanie z polecenia jarvo")
    except Exception:  # noqa: BLE001 - już się zatrzymuje albo kanał zamknął się w trakcie: decyduje czekanie niżej
        pass
    while stan_serwisu(u, ot)[0] is not None or _nadzorca_zyje(u, nadzorca):
        if ot.zegar() >= koniec:
            raise BladInstalacji(f"serwis nie zatrzymał się w {int(limit)} s; zobacz `jarvo logs nadzorca` i spróbuj "
                                 "jeszcze raz.")
        ot.czekaj(1.0)
    return True


def przytnij_log(p: Path, maks: int = MAKS_LOGU_STARTU) -> None:
    """Log startu bez rotacji nadzorcy: większy niż `maks` idzie do `<nazwa>.1` (poprzednia kopia znika)."""
    try:
        if p.stat().st_size > maks:
            os.replace(p, p.with_name(p.name + ".1"))
    except OSError:
        pass


def uruchom_serwis(u: Uklad, ot: Otoczenie, log: Callable[[str], None] | None = None, *,
                   autostart: bool | None = None) -> str:
    """Startuje `jarvo serwis` w tle i zwraca opis do komunikatu. Najpierw zdejmuje znacznik zatrzymania. Gdy
    autostart jest włączony i nasz (`autostart=None`: sprawdzamy), start idzie jego mechanizmem (Harmonogram `/Run`,
    launchctl, systemctl --user): IgnoreNew trzyma wtedy jedną kopię, a zapasowe wyzwalacze nie stawiają drugiej.
    Inaczej (albo gdy mechanizm nie podniesie nadzorcy w CZAS_NADZORCY) odłączony proces z otoczeniem bez sekretów,
    wyjście w `<logi>/serwis-start.log`."""
    zdejmij_zatrzymanie(u, ot)
    argv = polecenie_jarva(u, "serwis", okno=False, env=ot.env)
    if autostart is None:
        st = stan_autostartu(u, ot)
        autostart = bool(st.get("wlaczony") and st.get("nasz") and st.get("mechanizm") in MECHANIZMY_STARTU)
    if autostart:
        try:
            # ta sama definicja co przy instalacji (argv i env), więc wlacz tylko uruchamia: /Run, enable --now,
            # kickstart albo bootstrap wyładowanego LaunchAgenta
            wynik = wywolaj(ot.modul("autostart").wlacz, u, argv, start=True, log=None, env=ot.env)
            ruszyl = isinstance(wynik, dict) and bool(wynik.get("uruchomiony"))
            powod = "; ".join(str(x) for x in (wynik.get("uwagi") or [])) if isinstance(wynik, dict) else ""
        except Exception as e:                   # noqa: BLE001 - mechanizm systemu zawiódł (np. launchctl bez GUI)
            ruszyl, powod = False, f"{type(e).__name__}: {str(e)[:160]}"
        if ruszyl:
            koniec = ot.zegar() + CZAS_NADZORCY
            while True:
                if stan_serwisu(u, ot)[0] is not None:
                    return "przez autostart"
                if ot.zegar() >= koniec:
                    break
                ot.czekaj(1.0)
            powod = f"nadzorca nie otworzył kanału w {int(CZAS_NADZORCY)} s"
        if log:
            log(f"autostart nie uruchomił serwisu ({powod or 'bez powodu'}): uruchamiam go w tle")
    przytnij_log(u.logi / LOG_STARTU)
    pid = ot.uruchom_w_tle(argv, env_floty(ot.env), u.logi / LOG_STARTU)
    return f"w tle (PID {pid})"


# ---------------------------------------------------------------- git i wersja kodu

def head_gita(katalog: Path) -> str | None:
    """SHA commitu HEAD w checkoucie bez uruchamiania gita: odłączony HEAD, gałąź w refs albo packed-refs,
    także w git worktree (plik .git z `gitdir:` i katalog wspólny z `commondir`)."""
    git = Path(katalog) / ".git"
    try:
        if git.is_file():
            wskazanie = git.read_text(encoding="utf-8").strip()
            if not wskazanie.startswith("gitdir:"):
                return None
            git = (Path(katalog) / wskazanie.split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head if re.fullmatch(r"[0-9a-f]{40}", head) else None
        ref = head.split(":", 1)[1].strip()
        bazy = [git]
        if (git / "commondir").is_file():
            bazy.append((git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve())
        for baza in bazy:
            plik = baza / ref
            if plik.is_file():
                return plik.read_text(encoding="utf-8").strip() or None
            spakowane = baza / "packed-refs"
            if spakowane.is_file():
                for linia in spakowane.read_text(encoding="utf-8").splitlines():
                    czesci = linia.split()
                    if len(czesci) == 2 and czesci[1] == ref:
                        return czesci[0]
    except OSError:
        return None
    return None


def wersja_aplikacji(app: Path) -> str:
    """Wersja kodu Jarva: `.jarvo-wersja` z bootstrapu (pełny SHA), w kopii repo HEAD gita, inaczej „dev”."""
    try:
        sha = (Path(app) / ".jarvo-wersja").read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        sha = head_gita(app) or ""
    return sha[:12] if re.fullmatch(r"[0-9a-f]{7,40}", sha) else "dev"


# ---------------------------------------------------------------- polecenie jarvo dla właściciela

def tresc_jarvo_cmd(python: Path, start: Path, korzen: list[str] = ()) -> bytes:
    """`<root>\\bin\\jarvo.cmd`: cmd.exe czyta plik w stronie kodowej OEM, więc tylko ASCII (ścieżki w `<program>`
    są ASCII, c1); CRLF, bo etykiety i goto w cmd psują się na LF. .cmd, bo polityka Restricted blokuje .ps1 (N01)."""
    dodatki = "".join(f' "{a}"' if a != "--korzen" else " --korzen" for a in korzen)
    tekst = (f"@echo off\r\nrem {ZNACZNIK}: polecenie jarvo. Instalator nadpisuje ten plik przy kazdej wersji.\r\n"
             f'"{python}" -I -X utf8 "{start}"{dodatki} %*\r\nexit /b %ERRORLEVEL%\r\n')
    if not tekst.isascii() or "%" in "".join(korzen):
        raise BladInstalacji(f"ścieżka {python}, {start} albo {' '.join(korzen)} ma znaki spoza ASCII albo %, "
                             "a cmd.exe ich nie odczyta. Ustaw JARVO_ROOT na katalog z samymi literami ASCII "
                             "(np. C:\\Jarvo) i zainstaluj ponownie.")
    return tekst.encode("ascii")


def tresc_jarvo_sh(python: Path, start: Path, korzen: list[str] = ()) -> str:
    """`~/.local/bin/jarvo`: /bin/sh, exec bez pośredniego procesu (sygnały i kod wyjścia idą wprost)."""
    argv = " ".join(shlex.quote(str(a)) for a in [python, "-I", "-X", "utf8", start, *korzen])
    return (f"#!/bin/sh\n# {ZNACZNIK}: polecenie jarvo. Instalator nadpisuje ten plik przy każdej wersji.\n"
            f'exec {argv} "$@"\n')


def korzen_polecenia(tekst: str) -> str | None:
    """Korzeń, któremu służy nasze polecenie jarvo (`--korzen <root>` w treści), None = korzeń domyślny."""
    m = re.search(r"""--korzen ("[^"]*"|'(?:[^']|'"'"')*'|\S+)""", tekst)
    if not m:
        return None
    wartosc = m.group(1)
    if wartosc.startswith('"'):
        return wartosc[1:-1]
    return shlex.split(wartosc)[0] if wartosc.startswith("'") else wartosc


def plik_rc(dom: Path, powloka: str, macos: bool) -> Path:
    """Plik startowy powłoki logowania: zsh (domyślna na macOS) czyta ~/.zprofile; bash czyta pierwszy istniejący
    z ~/.bash_profile i ~/.profile, więc nowy ~/.bash_profile przesłoniłby czyjś ~/.profile."""
    if macos or Path(powloka or "").name == "zsh":
        return dom / ".zprofile"
    return dom / ".bash_profile" if (dom / ".bash_profile").is_file() else dom / ".profile"


def kiedy_dziala_path() -> str:
    """Kiedy nowy wpis PATH zadziała: macOS Terminal otwiera powłokę logowania, a terminal w GNOME i KDE nie (czyta
    ~/.bashrc albo ~/.zshrc), więc na Linuksie dopiero po ponownym zalogowaniu."""
    if WINDOWS:
        return "w nowym oknie terminala"
    if MACOS:
        return "w nowym oknie Terminala"
    return "po ponownym zalogowaniu (terminal w GNOME i KDE nie czyta ~/.profile)"


def obca_instalacja(u: Uklad, dom: Path | None = None, *, polecenie_w_domu: bool = True) -> str | None:
    """Powód odmowy, gdy w miejscu instalacji jest stara instalacja (WSL i Docker) albo cudze polecenie jarvo
    (`polecenie_w_domu=False`: ~/.local/bin nas nie obchodzi, bo polecenie idzie do `<root>/bin`). Migracja
    przyjdzie w etapie E12 (`jarvo migruj`); do tego czasu niczego z niej nie nadpisujemy."""
    if WINDOWS:
        if (u.root / "wsl").is_dir():
            return f"w {u.root} jest stara instalacja Jarvo z WSL (katalog wsl)"
        cmd = u.root / "bin" / "jarvo.cmd"
        if cmd.is_file() and ZNACZNIK not in cmd.read_text(encoding="utf-8", errors="replace"):
            return f"{cmd} należy do starej instalacji Jarvo (WSL)"
        return None
    if not polecenie_w_domu:
        return None
    cel = (dom or Path.home()) / ".local" / "bin" / "jarvo"
    if cel.is_symlink() or cel.exists():
        try:
            nasz = cel.is_file() and not cel.is_symlink() and ZNACZNIK in cel.read_text(encoding="utf-8",
                                                                                         errors="replace")
        except OSError:
            nasz = False
        if not nasz:
            cel_linku = f" (dowiązanie do {os.readlink(cel)})" if cel.is_symlink() else ""
            return f"{cel}{cel_linku} należy do innej instalacji Jarvo (np. starej z Dockerem)"
    return None


def rada_npm() -> str:
    """Rada, gdy front panelu trzeba zbudować, a nie ma Node.js z npm (wymagania: `engines` w package.json Hermesa
    f97608f: node ^22.22.0 || ^24.11.0 || >=26.0.0, npm <11.10.0 || >=11.17.0)."""
    if WINDOWS:
        skad = "instalator .msi albo wersja .zip z https://nodejs.org (bez uprawnień administratora: .zip)"
    elif MACOS:
        skad = "instalator .pkg z https://nodejs.org"
    else:
        skad = "menedżer pakietów (np. sudo apt install nodejs npm) albo https://nodejs.org"
    return ("front panelu (strona w przeglądarce) budujemy na razie na tym komputerze z kodu Hermesa, a do tego "
            "potrzebny jest Node.js z npm (gotowy front z wydania Jarva przyjdzie później, S12). Zainstaluj Node.js "
            f"24 LTS (24.11+), 22.22+ albo 26+: {skad}. Potem uruchom polecenie instalacji jeszcze raz: gotowe kroki "
            "zostaną pominięte.")


def rada_autostartu(start: bool) -> str:
    """Rada, gdy autostartu nie da się włączyć (instalacja idzie dalej)."""
    teraz = "Serwis uruchamiam bezpośrednio. " if start else ""
    if WINDOWS:
        tekst = "Harmonogram zadań odmówił. Po zalogowaniu serwis trzeba uruchamiać ręcznie (`jarvo up`)."
    elif MACOS:
        tekst = ("Bez sesji graficznej (np. przez ssh) launchctl nie wczyta LaunchAgenta: zrobi to następne logowanie "
                 "na pulpit, a do tego czasu serwis uruchamia `jarvo up`.")
    else:
        tekst = ("Bez usług systemd użytkownika (WSL bez systemd, kontener, sesja przez su albo sudo) serwis po "
                 "ponownym uruchomieniu komputera wstanie dopiero po `jarvo up`. Po zalogowaniu zwykłą sesją: "
                 "`jarvo autostart on`.")
    return (teraz + tekst + " Instalacja bez autostartu: JARVO_NO_AUTOSTART=1 (albo jarvo instaluj "
            "--bez-autostartu).")


# ---------------------------------------------------------------- przebieg instalacji

def _pasek(i: int, n: int, szerokosc: int = 24) -> str:
    pelne = round(szerokosc * i / n)
    return "[" + "#" * pelne + "-" * (szerokosc - pelne) + f"] {i:>2}/{n}"


def _zapisz_jesli_inne(cel: Path, tresc: str | bytes) -> bool:
    dane = tresc.encode("utf-8") if isinstance(tresc, str) else tresc
    try:
        if cel.is_file() and cel.read_bytes() == dane:
            return False
    except OSError:
        pass
    przenosne.zapisz_atomowo(cel, dane)
    return True


def _json(dane: dict) -> str:
    return json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _wolne_gb(sciezka: Path) -> float:
    p = Path(sciezka)
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


@contextlib.contextmanager
def _katalog_biezacy(katalog: Path):
    """Katalog bieżący na czas instalacji: kod Jarva (tylko dla właściciela), a nie katalog, w którym wklejono
    polecenie; program wołany gołą nazwą (np. icacls) nie przyjdzie z cudzego katalogu."""
    try:
        stary = os.getcwd()
        os.chdir(katalog)
    except OSError:
        yield
        return
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.chdir(stary)


class _Instalacja:
    def __init__(self, u: Uklad, app: Path, ot: Otoczenie, log: Callable[[str], None], *, autostart: bool,
                 web_lokalnie: bool, start: bool, bez_path: bool, platforma: str | None):
        self.u, self.app, self.ot, self._log = u, Path(os.path.abspath(app)), ot, log
        self.autostart, self.web_lokalnie, self.start, self.bez_path = autostart, web_lokalnie, start, bez_path
        self.platforma = platforma
        self.narz: dict = {}
        self.checkout: Path | None = None
        self.nowe: dict = {}                 # current.json nowej wersji: zapis dopiero w kroku „Przełączenie wersji”
        self.restart = False                 # zmienił się current.json albo ustawienia: serwis startuje od nowa
        self.autostart_zmieniony = False     # nowa definicja autostartu: działający serwis ma stare polecenie
        self.oznaczone = False               # ten przebieg zatrzymał serwis i postawił znacznik zatrzymania
        self.autostart_dziala: bool | None = None
        self.cel_polecenia: Path | None = None
        self.zmiany: list[str] = []          # co zmienił ten przebieg (drugi przebieg: nic)
        self.uwagi: list[str] = []
        self._bufor: list[str] = []
        self.wynik_floty: dict | None = None  # podsumowanie install_fleet.py z tego przebiegu
        self.panel_po_flocie = False         # panel wstał (albo wstał od nowa) po instalacji floty w tym przebiegu

    # dziennik instalacji: ekran + <logi>/instalacja.log (bez sekretów: komunikaty ich nie zawierają)
    def log(self, tekst: str) -> None:
        self._log(tekst)
        self._bufor.append(tekst)
        if self.u.logi.is_dir():
            try:
                with open(self.u.logi / "instalacja.log", "a", encoding="utf-8") as f:
                    f.write("".join(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {t}\n" for t in self._bufor))
                self._bufor.clear()
            except OSError:
                pass

    def podlog(self, tekst: str) -> None:
        self.log(f"    {tekst}")

    def kroki(self) -> list[tuple[str, Callable[[], None]]]:
        """Kroki tej instalacji: narzędzia, venvy i modele z manifestu dla tej platformy (c3)."""
        self.platforma = self.platforma or sciezki.platforma()
        narz = manifest.wczytaj(self.app)
        nazwy = narzedzia_instalacji(narz, self.platforma)
        venvy = [n for n, w in manifest.venvy(self.app).items()
                 if isinstance(w, dict) and (w.get("kiedy") or "instalacja") == "instalacja"]
        modele = [n for n, m in manifest.modele(self.app).items()
                  if isinstance(m, dict) and (m.get("kiedy") or "instalacja") == "instalacja"]
        k: list[tuple[str, Callable[[], None]]] = [("Sprawdzenie komputera", self.sprawdzenie),
                                                    ("Katalogi", self.katalogi)]
        k += [(OPISY.get(nazwa, nazwa), lambda n=nazwa: self.narzedzie(n)) for nazwa in nazwy]
        k += [(f"Venv {nazwa}", lambda n=nazwa: self.venv(n)) for nazwa in venvy]
        k += [(f"Model {nazwa}", lambda n=nazwa: self.model(n)) for nazwa in modele]
        if "pixi" in nazwy and (self.app / "vendor" / "pixi" / "tesseract" / "pixi.lock").is_file():
            k.append(("Tesseract", self.tesseract))
        k += [("Spis narzędzi", self.spis_narzedzi), ("Wersja Jarva", self.wersja_jarva), ("Hermes", self.hermes),
              ("Front panelu", self.front), ("Bezpieczne ustawienia Hermesa", self.konfiguracja),
              ("Klucz API bramy", self.klucz_api), ("Przełączenie wersji", self.przelaczenie),
              ("Programy floty", self.programy_floty), ("Flota", self.flota),
              ("Środowisko procesów", self.zapis_srodowiska), ("Polecenie jarvo", self.polecenie)]
        if self.autostart:
            k.append(("Autostart", self.wlacz_autostart))
        if self.start:
            k += [("Serwis", self.serwis), ("Panel", self.panel)]
        return k

    def uruchom(self) -> int:
        try:
            kroki = self.kroki()
        except (sciezki.BladUkladu, OSError, ValueError, KeyError) as e:
            self.log(f"BŁĄD: {e}" if isinstance(e, sciezki.BladUkladu) else
                     f"BŁĄD: manifest narzędzi {self.app / manifest.LOCK} jest nieczytelny ({type(e).__name__}: "
                     f"{e}). Pobierz Jarvo jeszcze raz poleceniem instalacji.")
            return 1
        self.log(f"Jarvo natywnie: instalacja w {self.u.root}")
        for i, (nazwa, krok) in enumerate(kroki, 1):
            self.log(f"{_pasek(i, len(kroki))}  {nazwa}")
            try:
                krok()
            except Exception as e:    # noqa: BLE001 - każdy błąd kroku kończy instalację czytelnym komunikatem
                self.log(f"BŁĄD w kroku „{nazwa}”: {e}")
                self._slad()
                self._po_bledzie()
                self.log("Instalację można uruchomić ponownie: gotowe kroki zostaną pominięte.")
                return 1
        if self.oznaczone:                   # bez startu teraz (--bez-startu): autostart podniesie nową wersję sam
            zdejmij_zatrzymanie(self.u, self.ot)
        for uwaga in self.uwagi:
            self.log(f"Uwaga: {uwaga}")
        zmiany = ", ".join(dict.fromkeys(self.zmiany)) or "brak"
        self.log(f"Gotowe. Zmiany w tym przebiegu: {zmiany}.")
        if self.start:
            self.log(f"Panel: {adres_panelu(self.ot.env)}")
        self.log(self._polecenia())
        return 0

    def _po_bledzie(self) -> None:
        """Znacznik zatrzymania z tej aktualizacji nie zostaje (to nie `jarvo down`): autostart może podnieść serwis
        sam, a ponowiona instalacja uruchomi go od nowa na wersji z current.json."""
        if self.oznaczone:
            with contextlib.suppress(Exception):
                zdejmij_zatrzymanie(self.u, self.ot)
            self.log("Serwis Jarva stoi (zatrzymany na czas aktualizacji): uruchom go poleceniem `jarvo up` albo "
                     "uruchom instalację jeszcze raz.")

    def _zatrzymaj(self, powod: str) -> None:
        """Działający serwis zatrzymany na czas tego przebiegu: znacznik (zapasowe wyzwalacze autostartu nie podniosą
        starej wersji w trakcie) i stop kanałem. Znacznik zdejmuje krok „Serwis”, koniec przebiegu albo błąd."""
        self.oznaczone = True
        oznacz_zatrzymanie(self.u, self.ot, powod)
        zatrzymaj_serwis(self.u, self.ot, powod)

    def _slad(self) -> None:
        """Pełny ślad błędu tylko do pliku dziennika (na ekranie wystarczy komunikat)."""
        if self.u.logi.is_dir():
            try:
                with open(self.u.logi / "instalacja.log", "a", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except OSError:
                pass

    def _polecenia(self) -> str:
        """Ostatni wiersz: polecenia na start i kiedy działają (profil jarvo przychodzi z flotą w etapie E4)."""
        chat = ("jarvo chat" if (self.u.dane / "profiles" / "jarvo").is_dir() else
                "jarvo chat --profil default (profil jarvo przyjdzie z flotą w etapie E4)")
        cel = self.cel_polecenia
        if self.bez_path:
            gdzie = f"pełną ścieżką {cel}" if cel else "pełną ścieżką"
        elif cel is not None and str(cel.parent) in self.ot.env.get("PATH", "").split(os.pathsep):
            gdzie = "działają już w tym terminalu"
        else:
            gdzie = kiedy_dziala_path() + (f"; od razu: {cel}" if cel is not None and not WINDOWS else "")
        return f"Polecenia: jarvo panel, jarvo status, jarvo doctor, {chat} ({gdzie})."

    # -- kroki
    def sprawdzenie(self) -> None:
        self.platforma = self.platforma or sciezki.platforma()
        self.podlog(f"platforma {self.platforma}, Python {sys.version.split()[0]}")
        powod = obca_instalacja(self.u, polecenie_w_domu=not self.bez_path)
        if powod:
            raise BladInstalacji(f"{powod}. Migracja (jarvo migruj) przyjdzie w etapie E12; do tego czasu zainstaluj "
                                 "Jarvo natywnie w osobnym katalogu: ustaw JARVO_ROOT (np. D:\\Jarvo albo ~/jarvo-"
                                 "natywnie) i uruchom polecenie instalacji ponownie.")
        powod = korzen_nieosobny(self.u)
        if powod:
            raise BladInstalacji(f"{powod}. Jarvo potrzebuje osobnego katalogu, bo dostęp do całego korzenia dostaje "
                                 f"tylko właściciel: ustaw JARVO_ROOT na nowy katalog (np. {PRZYKLAD_KORZENIA}) i "
                                 "uruchom polecenie instalacji ponownie.")
        for zmienna in USTAWIENIA:
            port = str(self.ot.env.get(zmienna) or "").strip()
            if port and not port_poprawny(port):
                raise BladInstalacji(f"{zmienna}={port!r}: potrzebny numer portu od 1 do 65535.")
        if port_api(self.u, self.ot.env) == port_panelu(self.ot.env):
            raise BladInstalacji(f"panel i API bramy nie mogą mieć tego samego portu ({port_panelu(self.ot.env)}): "
                                 "zmień JARVO_PANEL_PORT albo JARVO_API_PORT.")
        wolne = _wolne_gb(self.u.root)
        if wolne < MIN_MIEJSCA_GB:
            raise BladInstalacji(f"na dysku z {self.u.root} jest {wolne:.1f} GB wolnego miejsca, a instalacja "
                                 f"potrzebuje co najmniej {MIN_MIEJSCA_GB} GB. Zwolnij miejsce albo ustaw JARVO_ROOT "
                                 "na inny dysk.")
        if wolne < ROZMIAR_GB and not (self.u.program / "current.json").is_file():
            uwaga = (f"na dysku z {self.u.root} jest {wolne:.1f} GB wolnego miejsca, a instalacja z flotą zajmuje "
                     f"ok. {ROZMIAR_GB} GB: może zabraknąć miejsca (JARVO_ROOT na inny dysk)")
            self.podlog(f"uwaga: {uwaga}")
            self.uwagi.append(uwaga)

    def katalogi(self) -> None:
        nowe = [k for k in [*self.u.katalogi(), self.u.stan / "gateway-locks"] if not k.is_dir()]
        for k in nowe:
            k.mkdir(parents=True, exist_ok=True)
        # cały korzeń tylko dla właściciela, z dziedziczeniem w dół (program, bin, logi, cache): na innym dysku
        # dziedziczyłby ACL dysku z zapisem dla Użytkowników uwierzytelnionych; <dane> i <stan> jeszcze osobno
        # (sekrety, klucze API i kanał nadzorcy, D02, c2)
        for k in (self.u.root, self.u.dane, self.u.stan):
            przenosne.chron(k, katalog=True)
        if nowe:
            self.zmiany.append("katalogi")

    def narzedzie(self, nazwa: str) -> None:
        n = manifest.wczytaj(self.app)
        wpis = manifest.plik(n, nazwa, self.platforma)
        wersja = manifest.wersja(n, nazwa)
        docelowy = self.u.program / "narzedzia" / nazwa / pobieracz.katalog_wersji(wersja)
        try:
            bylo = (docelowy / ".jarvo-suma").read_text(encoding="utf-8").strip() == wpis["sha256"]
        except OSError:
            bylo = False
        katalog = pobieracz.zainstaluj(nazwa, wersja, wpis, self.u.program / "narzedzia", self.u.cache / "pobrane")
        self.narz[nazwa] = {
            "wersja": wersja, "katalog": str(katalog),
            "bin": [str(katalog / b) for b in wpis.get("bin") or []],
            "env": {str(k): str(v).replace("{katalog}", str(katalog)) for k, v in (wpis.get("env") or {}).items()},
        }
        self.podlog(f"{nazwa} {wersja}: {'już jest' if bylo else 'zainstalowany'} ({katalog})")
        if not bylo:
            self.zmiany.append(nazwa)

    def venv(self, nazwa: str) -> None:
        """Venv z locka manifestu (jarvo/venvy.py) na Pythonie z kroku narzędzi."""
        wpis = manifest.venvy(self.app)[nazwa]
        python = str(wpis.get("python") or "python312")
        if python not in self.narz or "uv" not in self.narz:
            raise BladInstalacji(f"venv {nazwa} potrzebuje {python} i uv z manifestu, a ich nie ma dla platformy "
                                 f"{self.platforma}")
        spis, zmiana = self.ot.modul("venvy").zainstaluj(self.u, self.app, nazwa, wpis, uv=self._bin_narzedzia("uv"),
                                                          python=self._bin_narzedzia(python), log=self.podlog)
        self.narz[f"venv-{nazwa}"] = spis
        self.podlog(f"venv {nazwa}: {'zainstalowany' if zmiana else 'już jest'} ({spis['katalog']})")
        if zmiana:
            self.zmiany.append(f"venv {nazwa}")

    def model(self, nazwa: str) -> None:
        """Model z manifestu do `<dane>/jarvo/models` (jarvo/modele.py), każdy plik z sumą."""
        wpis = manifest.modele(self.app)[nazwa]
        spis, zmiana = self.ot.modul("modele").zainstaluj(nazwa, wpis, self.u.jarvo_dane / "models", log=self.podlog)
        self.narz[f"model-{nazwa}"] = spis
        self.podlog(f"model {nazwa}: {'pobrany' if zmiana else 'już jest'} ({spis['katalog']})")
        if zmiana:
            self.zmiany.append(f"model {nazwa}")

    def tesseract(self) -> None:
        """Tesseract z pixi.lock (jarvo/tesseract.py) i próba `--list-langs` z językami z modelu tessdata-fast."""
        t = self.ot.modul("tesseract")
        pixi = self.narz["pixi"]
        spis, zmiana = t.zainstaluj(self.u, self.app, pixi=Path(pixi["katalog"]) / ("pixi.exe" if WINDOWS else "pixi"),
                                    env_narzedzia=pixi.get("env") or {}, platforma=self.platforma,
                                    modele=self.u.jarvo_dane / "models", log=self.podlog)
        ok, opis = t.sprawdz(Path(spis["program"]), Path(spis["env"]["TESSDATA_PREFIX"]))
        if not ok:
            raise BladInstalacji(f"Tesseract {spis.get('wersja')} nie działa ({opis}). Zobacz <logi>/instalacja.log "
                                 "i uruchom instalację jeszcze raz.")
        self.narz["tesseract"] = spis
        self.podlog(f"Tesseract {spis.get('wersja')}: {'zainstalowany' if zmiana else 'już jest'}, języki: {opis}")
        if zmiana:
            self.zmiany.append("tesseract")

    def spis_narzedzi(self) -> None:
        spis = {**srodowisko.narzedzia(self.u), **self.narz}
        if _zapisz_jesli_inne(self.u.stan / "narzedzia.json", _json(spis)):
            self.zmiany.append("narzedzia.json")

    def wersja_jarva(self) -> None:
        if not (self.app / "jarvo" / "start.py").is_file():
            raise BladInstalacji(f"{self.app} nie wygląda na kod Jarva (brak jarvo/start.py)")
        wersja = wersja_aplikacji(self.app)
        self.nowe.update(app=str(self.app), wersja=wersja)
        biez = srodowisko.biezace(self.u)
        if biez.get("app") and biez["app"] != str(self.app):
            self.podlog(f"wersja {wersja}: {self.app} (obok działającej {biez.get('wersja') or '?'}; przełączenie "
                        "po udanych krokach)")
        else:
            self.podlog(f"wersja {wersja}: {self.app}")

    def _bin_narzedzia(self, nazwa: str) -> Path:
        k = Path(self.narz[nazwa]["katalog"])
        if nazwa == "uv":
            return k / ("uv.exe" if WINDOWS else "uv")
        return k / "python.exe" if WINDOWS else k / "bin" / "python3"

    def _program_narzedzia(self, nazwa: str, program: str) -> Path | None:
        """Program narzędzia z tego przebiegu (katalogi `bin` wpisu), np. git.exe z Git for Windows, npm.cmd z Node."""
        wpis = self.narz.get(nazwa) or {}
        nazwy = [f"{program}.exe", f"{program}.cmd"] if WINDOWS else [program]
        for katalog in wpis.get("bin") or []:
            for n in nazwy:
                if (Path(katalog) / n).is_file():
                    return Path(katalog) / n
        return None

    def _git(self) -> Path:
        if "git" in self.narz:                   # Windows: zawsze git z manifestu (I05), nigdy z PATH właściciela
            git = self._program_narzedzia("git", "git")
            if git is None:
                raise BladInstalacji(f"w {self.narz['git']['katalog']} nie ma git.exe (katalog cmd): archiwum Git "
                                     "for Windows jest niepełne. Usuń ten katalog i uruchom instalację jeszcze raz.")
            return git
        git = program_bezwzgledny(self.ot, "git")
        ok = False
        if git:
            try:
                ok = subprocess.run([git, "--version"], capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=60, env=env_floty(self.ot.env),
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        if ok:
            return Path(git)
        if WINDOWS:
            rada = ("Na razie potrzebny jest Git for Windows w PATH (https://git-scm.com/download/win); własny "
                    "Git for Windows z sumą (wpis w vendor/natywne.yaml) instalator podłączy w etapie E4 "
                    "(decyzja I05).")
        elif MACOS:
            rada = "Zainstaluj narzędzia wiersza poleceń Xcode: xcode-select --install."
        else:
            rada = "Zainstaluj git menedżerem pakietów systemu (np. sudo apt install git)."
        raise BladInstalacji(f"brak działającego programu git (potrzebny do pobrania Hermesa). {rada} Potem "
                             "uruchom polecenie instalacji ponownie.")

    def hermes(self) -> None:
        h = self.ot.modul("hermes")
        pin = manifest.hermes(self.app)
        checkout = h.zainstaluj(self.u, pin, git=self._git(), uv=self._bin_narzedzia("uv"),
                                python=self._bin_narzedzia("python313"), log=self.podlog)
        self.checkout = Path(checkout)
        self.nowe["hermes"] = str(self.checkout)

    def _checkout(self) -> Path:
        if self.checkout is None:
            raise BladInstalacji("brak checkoutu Hermesa (krok „Hermes” się nie wykonał)")
        return self.checkout

    def _jest_npm(self) -> bool:
        """npm z Node Jarva (narzedzia.json) albo z PATH, jak szuka go hermes.web_dist."""
        for nazwa in ("node", "nodejs"):
            for k in (srodowisko.narzedzia(self.u).get(nazwa) or {}).get("bin") or []:
                if any((Path(k) / n).is_file() for n in ("npm.cmd", "npm")):
                    return True
        return program_bezwzgledny(self.ot, "npm") is not None

    def front(self) -> None:
        # zawsze z checkoutu bieżącego pinu: hermes.web_dist pomija front zbudowany dla tego commitu (znacznik), więc
        # po zmianie pinu nie zostaje front starej wersji przy nowym backendzie
        checkout = self._checkout()
        h = self.ot.modul("hermes")
        znacznik = getattr(h, "ZNACZNIK_WEB", None)
        if self.web_lokalnie and isinstance(znacznik, str):
            (checkout / znacznik).unlink(missing_ok=True)          # --web-lokalnie: budowa od nowa
        npm = self._program_narzedzia("node", "npm")       # Node.js z manifestu, nie z PATH właściciela
        try:
            dist = h.web_dist(self.u, checkout, npm=str(npm) if npm else None, log=self.podlog)
        except Exception as e:
            if not npm and not self._jest_npm():
                raise BladInstalacji(rada_npm()) from e
            raise
        self.nowe["web_dist"] = str(dist)

    def _narz(self) -> dict:
        """narzedzia.json z dysku i wpisy z tego przebiegu (spis zapisuje krok „Spis narzędzi”)."""
        return {**srodowisko.narzedzia(self.u), **self.narz}

    def _env(self) -> dict[str, str]:
        """Środowisko procesu Jarva dla NOWEJ wersji (current.json przełączamy dopiero później)."""
        return srodowisko.srodowisko(self.u, self.ot.env, biez={**srodowisko.biezace(self.u), **self.nowe},
                                     narz=self._narz())

    def konfiguracja(self) -> None:
        self.ot.modul("hermes").konfiguracja_bezpieczna(self.u, self._checkout(), self._env(), log=self.podlog)

    def klucz_api(self) -> None:
        """H05: API_SERVER_KEY i API_SERVER_PORT w `<dane>/.env` (brama i panel czytają go przy starcie; Hermes
        nadpisuje nim zmienne procesu). Brakujący albo za słaby klucz: nowy secrets.token_hex(32); dobry zostaje.
        Plik tylko dla właściciela. Klucz nie trafia na ekran ani do dziennika."""
        plik = self.u.dane / ".env"
        try:
            tekst = plik.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            tekst = ""
        except OSError as e:
            raise BladInstalacji(f"nie czytam {plik} ({e.strerror or e})") from e
        wartosci = czytaj_env(plik)
        port = str(port_api(self.u, self.ot.env))
        co = []
        if not klucz_api_dobry(wartosci.get("API_SERVER_KEY", "")):
            tekst = ustaw_w_env(tekst, "API_SERVER_KEY", secrets.token_hex(32))
            co.append("klucz API bramy")
        if wartosci.get("API_SERVER_PORT", "").strip() != port:
            tekst = ustaw_w_env(tekst, "API_SERVER_PORT", port)
            co.append(f"port API {port}")
        if co:
            przenosne.zapisz_atomowo(plik, tekst)
            self.zmiany += co
            self.restart = True                  # brama czyta .env tylko przy starcie
        try:
            przenosne.chron(plik, katalog=False)
        except OSError as e:
            raise BladInstalacji(f"nie ograniczę dostępu do {plik} do właściciela ({e})") from e
        self.podlog(f"API bramy: http://127.0.0.1:{port} (klucz w {plik}" + (", nowy)" if co and "klucz API bramy"
                                                                              in co else ")"))

    def przelaczenie(self) -> None:
        biez = srodowisko.biezace(self.u)
        nowe = {**biez, **self.nowe}
        if nowe == biez:
            self.podlog(f"bez zmian (wersja {nowe.get('wersja') or '?'})")
            return
        if stan_serwisu(self.u, self.ot)[0] is not None:
            self.podlog("zatrzymuję serwis poprzedniej wersji (brama kończy trwające tury)…")
            self._zatrzymaj("aktualizacja Jarva")
        if biez:
            # poprzednia wersja obok: `jarvo update` wraca do niej, gdy nowa nie wstanie (c4, pkt 5)
            przenosne.zapisz_atomowo(self.u.program / "current.poprzedni.json", _json(biez))
        przenosne.zapisz_atomowo(self.u.program / "current.json", _json(nowe))
        self.zmiany.append("current.json")
        self.restart = True
        self.podlog(f"current.json: wersja {nowe.get('wersja') or '?'}, Hermes {Path(str(nowe.get('hermes'))).name}")

    def zapis_srodowiska(self) -> None:
        ust = {k: str(self.ot.env[k]).strip() for k in USTAWIENIA if str(self.ot.env.get(k) or "").strip()}
        cel = self.u.stan / "ustawienia.json"
        if (ust or cel.is_file()) and _zapisz_jesli_inne(cel, _json(ust)):
            self.zmiany.append("ustawienia.json")
            self.restart = True
        # tylko część Jarva: bez PATH właściciela i przełączników bootstrapu, więc ta sama treść z każdego okna;
        # ze zmiennymi narzędzi i bramy z buildu floty (krok „Flota” był przed tym)
        cel = self.u.stan / "srodowisko.json"
        przed = cel.read_bytes() if cel.is_file() else b""
        narz = self._narz()
        srodowisko.zapisz(self.u, srodowisko.srodowisko(self.u, dict(ust), narz=narz), narz=narz)
        if cel.read_bytes() != przed:
            self.zmiany.append("srodowisko.json")
            self.restart = True                  # nadzorca trzyma środowisko usług od swojego startu

    def programy_floty(self) -> None:
        """bin-floty: python3, jarvo-tts, jarvo-stt, jarvo-klucz i tesseract (jarvo/bin_floty.py, S01, F12)."""
        narz = self._narz()
        venv = narz.get("venv-narzedzia")
        if not isinstance(venv, dict) or not venv.get("python"):
            self.podlog("ta wersja nie ma venvu narzędzi: programy floty pominięte")
            return
        tess = (narz.get("tesseract") or {}).get("program")
        zmiany = self.ot.modul("bin_floty").przygotuj(
            self.u, venv_python=Path(venv["python"]), uv=self._bin_narzedzia("uv") if "uv" in self.narz else None,
            tesseract=Path(tess) if tess else None, log=self.podlog)
        zmiany = list(zmiany or []) + self._agent_browser(narz)
        self.podlog(f"programy floty w {self.u.bin_floty}: " + ("zapisane" if zmiany else "bez zmian"))
        if zmiany:
            self.zmiany.append("programy floty")

    def _agent_browser(self, narz: dict) -> list:
        """Program `agent-browser` w bin-floty (nakładka Jarva z infra/bin/agent_browser.py tej wersji: wyłącza serwer
        podglądu demona, C05) dla Pythona z instalacji; na macOS i Linuksie także `chromium` dla chrome-headless-shell."""
        if not isinstance(narz.get("agent-browser"), dict):
            return []
        zrodlo = self.app / "infra" / "bin" / "agent_browser.py"
        spec = importlib.util.spec_from_file_location("jarvo_agent_browser", zrodlo)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        chrome = ((narz.get("chrome-headless-shell") or {}).get("env") or {}).get("CHROME_PATH")
        return [str(p) for p in modul.zainstaluj(self.u.bin_floty, self._bin_narzedzia("python313"), chrome=chrome)]

    def flota(self) -> None:
        """Build profili i instalacja floty (jarvo/flota.py); restart usług zleca krok „Serwis” (nadzorca)."""
        fl = self.ot.modul("flota")
        wynik = fl.zainstaluj_flote(self.u, srodowisko.srodowisko(self.u, self.ot.env, narz=self._narz()),
                                    log=self.podlog)
        self.wynik_floty = wynik if isinstance(wynik, dict) else {}
        agenci = self.wynik_floty.get("agenci") or []
        zmiany = self.wynik_floty.get("zmiany") or []
        self.podlog(f"flota: {len(agenci)} agentów ({', '.join(agenci)}); "
                    + (f"zmiany: {', '.join(zmiany[:6])}{'…' if len(zmiany) > 6 else ''}" if zmiany else "bez zmian"))
        for ostrzezenie in self.wynik_floty.get("ostrzezenia") or []:
            self.uwagi.append(f"flota: {ostrzezenie}")
        if zmiany:
            self.zmiany.append("flota")

    def uslugi_floty(self) -> list[str]:
        """Usługi nadzorcy do restartu po instalacji floty (brama, panel)."""
        if not self.wynik_floty:
            return []
        try:
            return list(self.ot.modul("flota").uslugi_do_restartu(self.wynik_floty))
        except ImportError:
            return []

    def polecenie(self) -> None:
        python = python_jarva(self.u)
        start = self.app / "jarvo" / "start.py"
        korzen = argumenty_korzenia(self.u, self.ot.env)
        if WINDOWS:
            self.polecenie_windows(self.u.root / "bin", sciezki.krotka_sciezka(python),
                                   sciezki.krotka_sciezka(start), korzen)
        else:
            self.polecenie_posix(Path.home(), python, start, korzen)

    def polecenie_windows(self, katalog: Path, python: Path, start: Path, korzen: list[str]) -> None:
        zm = self.ot.modul("zmiany_hosta")
        cel = katalog / "jarvo.cmd"
        self.cel_polecenia = cel
        if zm.zapisz_plik(self.u, cel, tresc_jarvo_cmd(python, start, korzen), None):
            self.zmiany.append(str(cel))
        self.podlog(f"polecenie: {cel}")
        if self.bez_path:
            self.podlog("PATH użytkownika bez zmian (--bez-path): polecenie uruchomisz pełną ścieżką")
            return
        if zm.dodaj_do_path(self.u, katalog, rejestr=self.ot.rejestr):
            self.zmiany.append("PATH użytkownika")
            self.podlog(f"PATH użytkownika: dopisany {katalog} (nowe okna terminala go widzą)")
        inne = shutil.which("jarvo", path=self.ot.env.get("PATH", ""))
        if inne and Path(inne).resolve().parent != Path(katalog).resolve():
            self.uwagi.append(f"w PATH wcześniej jest inne polecenie jarvo ({inne}); to uruchomisz pełną ścieżką "
                              f"{cel}")

    def polecenie_posix(self, dom: Path, python: Path, start: Path, korzen: list[str]) -> None:
        zm = self.ot.modul("zmiany_hosta")
        tresc = tresc_jarvo_sh(python, start, korzen)
        cel = dom / ".local" / "bin" / "jarvo"
        if not self.bez_path and cel.is_file():
            # nasze polecenie innej instalacji Jarva (np. domyślnej, a ta jest spod JARVO_ROOT): zostaje jej
            stary = korzen_polecenia(cel.read_text(encoding="utf-8", errors="replace"))
            if stary is None:
                stary = str(sciezki.uklad({k: v for k, v in self.ot.env.items() if k != "JARVO_ROOT"}).root)
            if _klucz(stary) != _klucz(self.u.root):
                self.uwagi.append(f"{cel} uruchamia inną instalację Jarva ({stary}); polecenie tej: "
                                  f"{self.u.root / 'bin' / 'jarvo'}")
                self.bez_path = True
        if self.bez_path:
            cel = self.u.root / "bin" / "jarvo"
        self.cel_polecenia = cel
        if zm.zapisz_plik(self.u, cel, tresc, 0o755):
            self.zmiany.append(str(cel))
        self.podlog(f"polecenie: {cel}")
        if self.bez_path or str(cel.parent) in self.ot.env.get("PATH", "").split(os.pathsep):
            return
        rc = plik_rc(dom, self.ot.env.get("SHELL", ""), MACOS)
        tekst = rc.read_text(encoding="utf-8", errors="replace") if rc.is_file() else ""
        sam_doklada = re.search(r"(\$HOME|\$\{HOME\}|~)/\.local/bin|" + re.escape(str(cel.parent)), tekst)
        if "# >>> jarvo >>>" not in tekst and sam_doklada:
            # plik sam dokłada ~/.local/bin do PATH (na Ubuntu i Debianie tylko, gdy katalog był przy logowaniu)
            self.podlog(f"PATH: {rc} dokłada {cel.parent} sam; polecenie zadziała {kiedy_dziala_path()}")
            return
        if zm.dodaj_blok_rc(self.u, rc, PATH_RC):
            self.zmiany.append(str(rc))
        self.podlog(f"PATH: blok jarvo w {rc} (zadziała {kiedy_dziala_path()})")

    def wlacz_autostart(self) -> None:
        auto = self.ot.modul("autostart")
        argv = polecenie_jarva(self.u, "serwis", okno=False, env=self.ot.env)
        try:
            # na razie bez startu: serwis uruchamia krok „Serwis” (tym samym mechanizmem, gdy działa)
            wynik = wywolaj(auto.wlacz, self.u, argv, start=False, log=self.podlog, env=self.ot.env)
            wynik = wynik if isinstance(wynik, dict) else {}
            if wynik.get("zmieniony") and wynik.get("mechanizm") == "launchagent":
                self._przeladuj_agenta(auto, argv)
        except bledy_autostartu(auto) as e:
            self.autostart_dziala = False
            self.podlog(f"autostart nie włączony: {str(e)[:300]}")
            self.uwagi.append(f"autostart nie działa ({str(e)[:300]}). {rada_autostartu(self.start)}")
            return
        self.autostart_dziala = wynik.get("mechanizm") in MECHANIZMY_STARTU
        if wynik.get("zmieniony"):
            self.autostart_zmieniony = True
            self.zmiany.append("autostart")

    def _przeladuj_agenta(self, auto: Any, argv: list[str]) -> None:
        """macOS, nowy plist: launchd trzyma wczytaną definicję w pamięci, a `launchctl kickstart` uruchomiłby starą
        (inny kod Jarva) aż do wylogowania. Działający serwis zatrzymujemy kanałem (drenaż bramy), wyładowujemy
        agenta (autostart.wylacz: bootout) i zapisujemy plist bez wczytania: wczyta go krok „Serwis” (bootstrap),
        a przy --bez-startu `jarvo up` albo następne logowanie."""
        if stan_serwisu(self.u, self.ot)[0] is not None:
            self.podlog("nowa definicja LaunchAgenta: zatrzymuję serwis, żeby launchd wczytał ją od nowa")
            self._zatrzymaj("nowa definicja autostartu")
        wywolaj(auto.wylacz, self.u, log=None, env=self.ot.env)
        wywolaj(auto.wlacz, self.u, argv, start=False, log=None, env=self.ot.env)

    def serwis(self) -> None:
        stan, _ = stan_serwisu(self.u, self.ot)
        if stan is not None and (self.restart or self.autostart_zmieniony):
            # działa stara wersja, stare ustawienia albo stare polecenie autostartu (np. po przerwanej aktualizacji
            # wstał z zapasowego wyzwalacza Harmonogramu, a ten przebieg przerejestrował zadanie): od nowa
            self.podlog("serwis działa ze starą wersją, ustawieniami albo poleceniem autostartu: uruchamiam go od nowa")
            self._zatrzymaj("aktualizacja Jarva")
            stan = None
        if stan is not None:
            zdejmij_zatrzymanie(self.u, self.ot)
            uslugi = self.uslugi_floty()
            if uslugi:
                self._restart_uslug(stan, uslugi)
            else:
                self.podlog("serwis działa")
            return
        sposob = uruchom_serwis(self.u, self.ot, self.podlog, autostart=bool(self.autostart_dziala))
        self.oznaczone = False
        self.panel_po_flocie = self.wynik_floty is not None
        self.podlog(f"serwis uruchomiony {sposob}")

    def _restart_uslug(self, stan: dict, uslugi: list[str]) -> None:
        """Działający serwis, zmieniona tylko flota: nadzorca restartuje bramę albo panel (łagodnie: brama kończy
        tury), a my czekamy, aż usługa wstanie z nowym PID-em i będzie gotowa (najdłużej CZAS_PANELU s)."""
        nadzorca = self.ot.modul("nadzorca")
        przed = {n: usluga_nadzorcy(stan, n).get("pid") for n in uslugi}
        self.podlog(f"flota się zmieniła: restart {' i '.join(uslugi)} przez nadzorcę")
        for nazwa in uslugi:
            wywolaj(nadzorca.polacz(self.u).restart, nazwa)
        koniec = self.ot.zegar() + CZAS_PANELU
        while True:
            teraz, _ = stan_serwisu(self.u, self.ot)
            gotowe = [n for n in uslugi if teraz is not None and usluga_nadzorcy(teraz, n).get("gotowa") is True
                      and usluga_nadzorcy(teraz, n).get("pid") not in (None, przed[n])]
            if len(gotowe) == len(uslugi):
                break
            if self.ot.zegar() >= koniec:
                self.uwagi.append(f"po restarcie {' i '.join(sorted(set(uslugi) - set(gotowe)))} nie zgłosiły "
                                  f"gotowości w {int(CZAS_PANELU)} s: sprawdź `jarvo status` i `jarvo logs`")
                return
            self.ot.czekaj(1.0)
        self.panel_po_flocie = "panel" in uslugi
        self.podlog(f"po restarcie gotowe: {', '.join(uslugi)}")

    def panel(self) -> None:
        self.podlog(f"panel Jarva odpowiada: {czekaj_na_panel(self.u, self.ot, self.log)}")
        odcisk = (self.wynik_floty or {}).get("odcisk_panelu")
        if self.panel_po_flocie and odcisk:
            # panel wstał po instalacji floty: następna instalacja nie zleci jego restartu bez zmian we wtyczkach
            self.ot.modul("flota").potwierdz_restart_panelu(self.u, odcisk)


def wypisz(tekst: str) -> None:
    """Domyślny `log`: wiersz od razu na ekran (pasek pobierania idzie na stderr, więc bez flush kolejność w logu
    CI się miesza)."""
    print(tekst, flush=True)


def instaluj(u: Uklad, app: Path, *, autostart: bool = True, web_lokalnie: bool = False, start: bool = True,
             bez_path: bool = False, log: Callable[[str], None] = wypisz, otoczenie: Otoczenie | None = None,
             platforma: str | None = None) -> int:
    """Instalacja albo naprawa Jarva w układzie `u` z kodu w `app`; 0 = gotowe, 1 = błąd (komunikat wypisany).
    `start=False` kończy po poleceniu jarvo i autostarcie (bez startu serwisu); `bez_path=True`: polecenie tylko
    w `<root>/bin`, bez PATH i plików startowych powłoki (próby na komputerze właściciela)."""
    inst = _Instalacja(bezwzgledny(u), app, otoczenie or Otoczenie(), log, autostart=autostart,
                       web_lokalnie=web_lokalnie, start=start, bez_path=bez_path, platforma=platforma)
    with _katalog_biezacy(inst.app):
        return inst.uruchom()

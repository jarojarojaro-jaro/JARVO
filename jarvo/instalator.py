"""Instalator Jarva natywnie: `jarvo instaluj` po bootstrapie (docs/NATYWNIE.md, c3, c1, c4, N01, L01–L03, H05,
S01, S11, F12; etapy E3 i E4).

Bootstrap (jarvo/bootstrap/install.ps1 albo install.sh) pobiera uv i Pythona 3.13 z sumami wpisanymi w skrypt, kod
Jarva z GitHuba do `<program>/app/<sha12>` i woła `python -I -X utf8 <app>/jarvo/start.py instaluj` (bez
JARVO_TOKEN: klucz był potrzebny tylko do pobrania kodu). Po jednym poleceniu Jarvo działa z flotą. Krok po kroku,
z paskiem i nazwą kroku:

   1. sprawdzenie: platforma (bez Maca z Intelem, I06), stara instalacja z WSL/Dockerem (wykryj_stara), korzeń jako
      osobny katalog (same katalogi Jarva: ochrona dostępu obejmuje całe drzewo), porty panelu i API, system plików
      korzenia (bez_ochrony: FAT, exFAT, NTFS na Linuksie i wolumin macOS z noowners nie trzymają uprawnień
      właściciela), miejsce na dysku: potrzeba liczona z manifestu (potrzebne_miejsce: rozmiary plików narzędzi,
      pobranie_mb i venv_mb venvów, rozmiary paczek z pixi.lock, modele, Hermes z frontem i flota; tylko części,
      których jeszcze nie ma) wobec wolnego miejsca na każdym dysku instalacji; zły system plików albo za mało miejsca
      = koniec przed zapisaniem czegokolwiek, z listą innych dysków lokalnych z ochroną dostępu i miejscem (polecany:
      Windows NTFS albo ReFS na dysku stałym, macOS APFS bez noowners, Linux ext4, xfs, btrfs…) i gotowym poleceniem
      z JARVO_ROOT (Z31),
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
      Tesseracta, fonty Noto), potem Tesseract z pixi.lock (jarvo/tesseract.py, TESSDATA_PREFIX na tessdata-fast)
      i narzędzia npm floty (infra/node/node_floty.py tej wersji: `npm ci --ignore-scripts` z package-lock.json npm-em
      z Node.js z manifestu do `<program>/node-floty/<skrót locka>`: HyperFrames, Lighthouse, playwright-core, three,
      inspo-mcp…; wpis `node-floty` z NODE_PATH i node_modules/.bin, P02, I32),
   6. `<stan>/narzedzia.json` (narzędzia, venvy, modele, Tesseract, narzędzia npm), 7. wersja Jarva (kod tej wersji),
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
      tesseract; S01, F12; nakładka agent-browser i `manimgx`, który instaluje swój venv przy pierwszym wywołaniu,
      M04), tylko w PATH procesów Jarva,
  14. flota (jarvo/flota.py): build.py w układzie natywnym ze ścieżkami instalacji (--py = Python venvu narzędzi,
      --bin-dir = bin-floty, --hermes-src = checkout) i install_fleet.py; restart usług zleca krok „Serwis”,
  15. `<stan>/srodowisko.json` (tylko część Jarva: bez PATH właściciela i przełączników bootstrapu, więc drugi
      przebieg z innego okna niczego nie zmienia; ze zmiennymi narzędzi i bramy z buildu) i `<stan>/ustawienia.json`
      (JARVO_PANEL_PORT, JARVO_API_PORT: zadanie Harmonogramu nie przekazuje zmiennych sesji, więc porty pamięta
      instalacja),
      stara instalacja z Dockerem (migracja.wykryj, tylko odczyt): przeniesienie danych `jarvo migruj` za zgodą
      przed poleceniem, autostartem i startem (nigdy dwie floty naraz); bez zgody kod 3 i stara flota pracuje dalej,
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

Po udanym przebiegu sprzątanie (c3 pkt 11, Z31): pobrane archiwa (`<cache>/pobrane`), cache uv (`uv cache clean`),
cache pixi, cache npm narzędzi floty (`<cache>/npm-floty`) i resztki starych wersji narzędzi; node_modules frontu
Hermesa znika już zaraz po budowie (hermes.web_dist). Cache sprzątamy pod zamkami, które biorą instalatory (przy
pierwszym użyciu, venvy, hermes, tesseract), bez czekania: drugi instalator, który właśnie z nich korzysta, zostawia je
do następnego sprzątania; świeży plik innego procesu w `<cache>/pobrane` (np. pobieranie przeglądarki komputera Jarva
przy starcie usługi) też zostaje.
Gotowe części mają znaczniki (suma narzędzia, venvu, modelu, Tesseracta, Hermesa, frontu), więc kolejny przebieg ich
nie pobiera ani nie buduje i działa bez sieci. Kompromis: część uszkodzona albo usunięta ręcznie (np. venv bez
znacznika, narzędzie bez katalogu) potrzebuje wtedy sieci, bo jej kół, paczek ani archiwów nie ma już w cache, a nowy
lock przy aktualizacji pobiera koła od nowa. Zostają źródła skilli buildu (`<cache>/build`: aktualizacja buduje flotę)
i cache npm (`--web-lokalnie` robi `npm ci` od nowa). Na końcu wiersz „Miejsce” z tym, ile zajmuje Jarvo i ile jest
wolnego (to samo pokazuje `jarvo doctor`).

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
import stat
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


class PrzeniesienieOdlozone(BladInstalacji):
    """Właściciel nie zgodził się (jeszcze) na przeniesienie danych starej instalacji: wersja natywna jest gotowa,
    ale stoi, a stara flota pracuje dalej. Instalacja kończy się kodem 3 (bootstrap: to nie błąd)."""


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


# ---------------------------------------------------------------- dyski: wolne miejsce, system plików, dyski lokalne

# Linux: systemy plików dysków lokalnych z /proc/self/mounts, które instalator poleca na korzeń (polecany): trzymają
# uprawnienia właściciela, dowiązania (archiwa Node, workspace'y npm) i blokady plików; sieciowe (nfs, cifs), obrazy
# (squashfs snapów, iso9660), systemy w pamięci (tmpfs, overlay) i BEZ_UPRAWNIEN odpadają
LOKALNE_FS = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "jfs", "reiserfs", "bcachefs", "zfs"})
MACOS_FS = frozenset({"apfs", "hfs"})              # macOS (`mount`): tylko z opcją local i bez noowners
WINDOWS_FS = frozenset({"ntfs", "refs"})           # Windows (GetVolumeInformationW): tylko na dysku stałym
# bez uprawnień właściciela: chmod 0700 z przenosne.chron nic nie zmienia albo kończy się EPERM (Linux: FAT, exFAT,
# NTFS przez ntfs3 i ntfs-3g, który montuje się jako fuseblk, tak jak exfat-fuse; macOS: msdos, exfat i ntfs tylko do
# odczytu), więc korzeń nie byłby tylko dla właściciela (c1): instalator go tam nie zakłada (DyskBezOchrony, krok 1)
BEZ_UPRAWNIEN = frozenset({"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk"})
FILE_PERSISTENT_ACLS = 0x8         # flaga GetVolumeInformationW: wolumin trzyma ACL (NTFS, ReFS; FAT32 i exFAT nie)
_TYPY_NAPEDU = {2: "wymienny", 3: "staly", 4: "sieciowy", 5: "cd", 6: "ramdysk"}       # GetDriveTypeW
SYSTEM = "windows" if WINDOWS else "macos" if MACOS else "linux"
_MOUNT_MACOS = re.compile(r"^(?P<urzadzenie>\S+) on (?P<punkt>.+) \((?P<opcje>[^)]*)\)\s*$")


@dataclass(frozen=True)
class Wolumin:
    """System plików, na którym leży ścieżka: urządzenie, punkt montowania, typ (ext4, apfs, NTFS…) i opcje montowania
    z /proc/self/mounts albo z `mount` na macOS; na Windows opcje to rodzaj dysku z GetDriveTypeW („staly”,
    „wymienny”, „sieciowy”…) i „acl”, gdy wolumin trzyma uprawnienia (FILE_PERSISTENT_ACLS)."""
    urzadzenie: str
    punkt: str
    typ: str
    opcje: frozenset = frozenset()


def istniejacy(sciezka: Path | str) -> Path:
    """Najbliższy istniejący katalog nad `sciezka` (albo ona sama): przed instalacją korzenia jeszcze nie ma."""
    p = Path(os.path.abspath(str(sciezka)))
    while not p.exists() and p.parent != p:
        p = p.parent
    return p


def wolne_miejsce(sciezka: Path | str) -> int:
    """Wolne bajty na dysku, na którym leży (albo powstanie) `sciezka`."""
    return shutil.disk_usage(istniejacy(sciezka)).free


def dysk(sciezka: Path | str) -> int:
    """Identyfikator dysku (st_dev najbliższego istniejącego katalogu; na Windows numer seryjny woluminu): ta sama
    wartość = ten sam system plików, więc potrzeby części instalacji na nim się sumują."""
    return os.stat(istniejacy(sciezka)).st_dev


def punkt_dysku(sciezka: Path | str) -> str:
    """Dysk do komunikatu: Windows litera z ukośnikiem (C:\\), POSIX punkt montowania (/, /home, /Volumes/Dane)."""
    p = istniejacy(sciezka)
    if WINDOWS:
        naped = os.path.splitdrive(str(p))[0]
        return naped + "\\" if naped and not naped.startswith("\\\\") else (naped or str(p))
    try:
        numer = os.stat(p).st_dev
        while p.parent != p and os.stat(p.parent).st_dev == numer:
            p = p.parent
    except OSError:
        pass
    return str(p)


def _bez_ucieczek(tekst: str) -> str:
    """Ścieżka z /proc/self/mounts: spacja, tabulator i ukośnik są tam jako \\040, \\011, \\134."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), tekst)


def woluminy_linux(tekst: str) -> list[Wolumin]:
    """Wpisy treści /proc/self/mounts (punkt montowania bez ucieczek \\040)."""
    wynik = []
    for linia in tekst.splitlines():
        cz = linia.split()
        if len(cz) >= 4:
            wynik.append(Wolumin(cz[0], _bez_ucieczek(cz[1]), cz[2], frozenset(cz[3].split(","))))
    return wynik


def woluminy_macos(tekst: str) -> list[Wolumin]:
    """Wpisy wyjścia `mount` na macOS: typ to pierwsza pozycja w nawiasie, reszta to opcje."""
    wynik = []
    for linia in tekst.splitlines():
        m = _MOUNT_MACOS.match(linia.strip())
        if m:
            opcje = [o.strip() for o in m["opcje"].split(",")]
            wynik.append(Wolumin(m["urzadzenie"], m["punkt"], opcje[0], frozenset(opcje[1:])))
    return wynik


def bez_ochrony(w: Wolumin, system: str = SYSTEM) -> str | None:
    """Czemu na woluminie `w` korzeń Jarva nie byłby tylko dla właściciela (c1), albo None: Windows bez ACL (FAT32,
    exFAT: icacls w kroku „Katalogi” zawiedzie), macOS z opcją noowners (domyślna dla dysków zewnętrznych: każde konto
    jest tam właścicielem każdego pliku, więc chmod 0700 nikogo nie zatrzyma), system plików z BEZ_UPRAWNIEN."""
    if system == "windows":
        return None if "acl" in w.opcje else f"system plików {w.typ or '?'} nie przechowuje uprawnień (ACL)"
    if system == "macos" and "noowners" in w.opcje:
        return ("wolumin ignoruje właścicieli plików (opcja noowners, domyślna dla dysków zewnętrznych): każde konto "
                "na tym Macu jest tam właścicielem każdego pliku")
    if w.typ.lower() in BEZ_UPRAWNIEN:
        return f"system plików {w.typ} nie przechowuje uprawnień właściciela plików"
    return None


def polecany(w: Wolumin, system: str = SYSTEM, *, systemowy: bool = False) -> bool:
    """Czy instalator może polecić wolumin `w` na korzeń (inne_dyski): dysk lokalny z zapisem i ochroną dostępu
    (bez_ochrony). Windows: dysk stały z NTFS albo ReFS; macOS: apfs albo hfs z opcją local na urządzeniu /dev/…, bez
    read-only i bez nobrowse (woluminy systemu; `systemowy=True` dla woluminu katalogu domowego, który ma nobrowse);
    Linux: system plików z LOKALNE_FS na urządzeniu /dev/… (zfs: zbiór danych), bez ro. Sieciowe, wymienne, obrazy
    i systemy w pamięci odpadają."""
    if bez_ochrony(w, system):
        return False
    typ = w.typ.lower()
    if system == "windows":
        return typ in WINDOWS_FS and "staly" in w.opcje
    if system == "macos":
        return (typ in MACOS_FS and w.urzadzenie.startswith("/dev/") and "local" in w.opcje
                and "read-only" not in w.opcje and (systemowy or "nobrowse" not in w.opcje))
    return typ in LOKALNE_FS and "ro" not in w.opcje and (w.urzadzenie.startswith("/dev/") or typ == "zfs")


def punkty_linux(tekst: str) -> list[str]:
    """Punkty montowania z treści /proc/self/mounts, które instalator może polecić (polecany)."""
    return [w.punkt for w in woluminy_linux(tekst) if polecany(w, "linux")]


def punkty_macos(tekst: str) -> list[str]:
    """Punkty montowania z wyjścia `mount` na macOS, które instalator może polecić (polecany; katalog domowy liczy
    dyski_lokalne osobno)."""
    return [w.punkt for w in woluminy_macos(tekst) if polecany(w, "macos")]


def _woluminy() -> list[Wolumin]:
    """Woluminy macOS (`mount` z /sbin) albo Linuksa (/proc/self/mounts); OSError, gdy system nie odpowie."""
    if MACOS:
        mount = systemowy("mount")
        return woluminy_macos(_uruchom([mount]).stdout) if mount else []
    return woluminy_linux(Path("/proc/self/mounts").read_text(encoding="utf-8", errors="replace"))


def wolumin_posix(sciezka: Path | str, woluminy: list[Wolumin]) -> Wolumin | None:
    """Wolumin lokalny (urządzenie /dev/… albo zbiór zfs) z `woluminy`, na którym leży `sciezka`: ten sam st_dev co
    jego punkt montowania (na macOS katalog domowy leży na /System/Volumes/Data przez firmlink, więc sam przedrostek
    ścieżki nie wystarcza). Punktów sieciowych i automatycznych nie dotykamy (stat na martwym NFS potrafi wisieć),
    więc dla nich None = nie wiadomo."""
    try:
        p = istniejacy(sciezka)
        numer = os.stat(p).st_dev
    except OSError:
        return None
    trafione = []
    for w in woluminy:
        if not (w.urzadzenie.startswith("/dev/") or w.typ == "zfs"):
            continue
        # macOS: ścieżka przez firmlink (/Users → /System/Volumes/Data/Users) leży na woluminie danych, także gdy
        # st_dev ścieżki wygląda jak st_dev zapieczętowanego „/” tylko do odczytu (macOS 15 w CI)
        if w.punkt != "/" and "root data" in w.opcje and os.path.isabs(str(p)):
            with contextlib.suppress(OSError):
                if os.path.samefile(p, w.punkt.rstrip("/") + str(p)):
                    return w
        try:
            if os.stat(w.punkt).st_dev == numer:
                trafione.append(w)
        except OSError:
            continue
    # kilka woluminów z tym samym st_dev: najpierw ten z zapisem
    return next((w for w in trafione if not {"read-only", "ro"} & w.opcje), trafione[0] if trafione else None)


def _kernel32() -> Any:
    """Własna kopia kernel32 (argtypes nie zmienia innym modułom) z typami funkcji woluminów."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetLogicalDrives.restype = wintypes.DWORD
    k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    k32.GetDriveTypeW.restype = wintypes.UINT
    k32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    k32.GetVolumePathNameW.restype = wintypes.BOOL
    k32.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                                          ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    k32.GetVolumeInformationW.restype = wintypes.BOOL
    return k32


def wolumin_windows(sciezka: Path | str, k32: Any = None) -> Wolumin | None:
    """Wolumin Windows ścieżki: GetVolumePathNameW (litera dysku albo katalog montowania), GetDriveTypeW
    i GetVolumeInformationW (system plików i flaga FILE_PERSISTENT_ACLS). None = system nie odpowie (np. pusty czytnik
    kart, dysk sieciowy bez połączenia)."""
    import ctypes
    from ctypes import wintypes
    k32 = k32 or _kernel32()
    sciezka = str(sciezka)
    bufor = ctypes.create_unicode_buffer(max(len(sciezka) + 2, 1024))
    if not k32.GetVolumePathNameW(sciezka, bufor, len(bufor)):
        return None
    punkt = bufor.value
    typ, flagi = ctypes.create_unicode_buffer(64), wintypes.DWORD()
    if not k32.GetVolumeInformationW(punkt, None, 0, None, None, ctypes.byref(flagi), typ, len(typ)):
        return None
    opcje = {_TYPY_NAPEDU.get(k32.GetDriveTypeW(punkt), "inny")} | ({"acl"} if flagi.value & FILE_PERSISTENT_ACLS
                                                                    else set())
    return Wolumin(punkt, punkt, typ.value, frozenset(opcje))


def wolumin(sciezka: Path | str) -> Wolumin | None:
    """Wolumin, na którym leży (albo powstanie) `sciezka` (wolumin_windows, wolumin_posix); None = nie wiadomo, a wtedy
    instalator nie odmawia (np. katalog domowy na NFS albo kontener z overlay)."""
    try:
        if WINDOWS:
            return wolumin_windows(istniejacy(sciezka))
        return wolumin_posix(sciezka, _woluminy())
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        return None


def _dyski_windows() -> list[Path]:
    """Dyski stałe Windows z NTFS albo ReFS (GetDriveTypeW = DRIVE_FIXED, potem polecany): bez wymiennych, sieciowych,
    CD, RAM-dysków i bez dysków USB z FAT32 albo exFAT, które zgłaszają się jako stałe."""
    k32 = _kernel32()
    maska = k32.GetLogicalDrives()
    wynik = []
    for i in range(26):
        litera = f"{chr(65 + i)}:\\"
        if maska >> i & 1 and k32.GetDriveTypeW(litera) == 3:
            w = wolumin_windows(litera, k32)
            if w is not None and polecany(w, "windows"):
                wynik.append(Path(litera))
    return wynik


def dyski_lokalne() -> list[Path]:
    """Katalogi, w których instalator może polecić korzeń Jarva (polecany: dysk lokalny z ochroną dostępu): Windows
    dyski stałe z NTFS albo ReFS, macOS i Linux katalog domowy (gdy jego wolumin jest lokalny i z ochroną dostępu)
    i punkty montowania z zapisem dla właściciela, bez spacji w ścieżce (psuje polecenia skilli, c1). Pusta lista, gdy
    system nie odpowie."""
    try:
        if WINDOWS:
            return _dyski_windows()
        woluminy = _woluminy()
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        return []
    dom = wolumin_posix(Path.home(), woluminy)
    wynik = [Path.home()] if dom is not None and polecany(dom, SYSTEM, systemowy=True) else []
    gorne = {w.punkt: w for w in woluminy}          # ten sam punkt dwa razy: widać ostatnie montowanie (na wierzchu)
    for punkt, w in gorne.items():
        if (polecany(w, SYSTEM) and Path(punkt) not in wynik and not any(z.isspace() for z in punkt)
                and os.path.isdir(punkt) and os.access(punkt, os.W_OK | os.X_OK)):
            wynik.append(Path(punkt))
    return wynik


@dataclass
class Otoczenie:
    """Wszystko, czego instalator i polecenia używają poza własnymi plikami: moduły Jarva ładowane przy użyciu,
    zmienne procesu, rejestr Windows (atrapa z interfejsem zmiany_hosta.Rejestr), programy z PATH, procesy w tle,
    sieć lokalna (zapytanie HTTP, kto słucha na porcie), dyski (wolne miejsce, który dysk, system plików, dyski
    lokalne), przeglądarka i zegar. Testy podstawiają atrapy, więc nie dotykają komputera."""
    modul: Callable[[str], Any] = modul
    env: dict = field(default_factory=lambda: dict(os.environ))
    rejestr: Any = None                                  # None = winreg (zmiany_hosta.Rejestr)
    program: Callable[[str], str | None] = przenosne.program
    uruchom_w_tle: Callable[[list[str], dict, Path], int] = uruchom_w_tle
    zapytaj_http: Callable[[str, float], tuple[int, Any] | None] = zapytaj_http
    sluchacz: Callable[[int], tuple[int, str] | None] = sluchacz
    wolne_miejsce: Callable[[Path], int] = wolne_miejsce
    dysk: Callable[[Path], Any] = dysk
    wolumin: Callable[[Path], Wolumin | None] = wolumin
    dyski: Callable[[], list[Path]] = dyski_lokalne
    otworz: Callable[[str], bool] | None = None          # przeglądarka; None = webbrowser.open
    na_pierwszym_planie: Callable[[list[str], dict], int] | None = None   # None = cli.uruchom_na_pierwszym_planie
    stara: Callable[[Uklad, Any], Any] | None = None    # stara instalacja z Dockerem; None = wykryj_stara
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


ZMIENNA_MIGRACJI = "JARVO_MIGRACJA"      # "nie": instalacja obok starej floty bez propozycji przeniesienia (próby)


def migracja_zakonczona(u: Uklad) -> bool:
    """`jarvo migruj` przeniósł już starą instalację (<stan>/migracja.json: zakończona i niewycofana)."""
    try:
        d = json.loads((u.stan / "migracja.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(d, dict) and bool(d.get("zakonczona")) and not d.get("wycofana")


def wykryj_stara(u: Uklad, ot: Otoczenie) -> Any:
    """Stara instalacja z Dockerem i WSL do przeniesienia (migracja.wykryj: tylko odczyt, bez startu WSL i Dockera)
    albo None: nie ma jej, migracja już się zakończyła albo JARVO_MIGRACJA=nie."""
    if str(ot.env.get(ZMIENNA_MIGRACJI) or "").strip().lower() in ("nie", "0", "no") or migracja_zakonczona(u):
        return None
    try:
        m = ot.modul("migracja")
        w = m.wykryj(m.SystemMigracji(env=dict(ot.env)), u)
    except (ImportError, OSError, ValueError, RuntimeError):
        return None
    return w if getattr(w, "jest", False) else None


def obca_instalacja(u: Uklad, dom: Path | None = None, *, polecenie_w_domu: bool = True) -> str | None:
    """Powód, dla którego nie nadpisujemy miejsca instalacji: stara instalacja (WSL i Docker) albo cudze polecenie
    jarvo (`polecenie_w_domu=False`: ~/.local/bin nas nie obchodzi, bo polecenie idzie do `<root>/bin`). Po
    zakończonej migracji (`jarvo migruj`) stara instalacja już nie przeszkadza (zostaje do sprzątania)."""
    if migracja_zakonczona(u):
        return None
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


# ---------------------------------------------------------------- miejsce instalacji (c3 pkt 11, Z31)

MB, GB = 10 ** 6, 10 ** 9
# rozpakowane narzędzie ≈ rozmiar pliku z manifestu × współczynnik formatu, z zapasem na całość (zmierzone 2026-10-25
# na Windows 11 x64: 17 narzędzi, archiwa 0,72 GB → 2,06 GB po rozpakowaniu, szacunek 2,24 GB; zip zwykle × 1,8–3,1,
# ale pandoc × 5,6, tar.gz Pythonów × 2,9, tar.bz2 Gita × 3,5)
ROZPAKOWANIE = {"zip": 3.0, "tar.gz": 3.0, "tgz": 3.0, "tar.xz": 4.5, "tar.bz2": 4.0, "tar": 1.0, "plik": 1.0}
# Hermes i flota: stałe w MB, zmierzone 2026-10-25 na Windows 11 x64 i te same dla każdej platformy. Manifest ich nie
# podaje i podać nie może bez zmiany scripts/natywne.py (lock przepisuje z sekcji hermes tylko repo, tag, commit, wersję
# i dodatki), a przed instalacją nie ma skąd wziąć rozmiaru checkoutu ani .venv przypiętego commitu (uv.lock Hermesa
# przychodzi dopiero z checkoutem). Po zmianie pinu Hermesa albo floty pilnuje ich test na żywo
# tests/live/natywnie_miejsce.py (tryb sprawdz: każda część zmierzona na dysku nie większa niż jej szacunek z zapasem).
# Hermes f97608f z dodatkami pinu: checkout 753 MB z .git bez blobów historii (235) i .venv (322) plus pliki .pyc, które
# Python dopisze przy pracy (zostaje), cache uv z kołami .venv (317 MB, znika po instalacji), node_modules frontu
# (280 MB, znika zaraz po budowie), front: dist, kopia z łatkami Jarva i cache npm (72 MB, zostaje)
HERMES_MB = {"checkout": 850, "cache_uv": 350, "node_modules": 300, "front": 80}
# flota: źródła skilli buildu w <cache>/build (31 repo, 0,94 GB; zostają, bo aktualizacja buduje flotę), build
# w <root>/build i profile z wtyczkami w <dane>
FLOTA_MB = {"zrodla": 1000, "build": 100, "profile": 150}
# narzędzia npm floty w MB (infra/node, npm ci z locka b5a1f4c9e3b8; zmierzone 2026-10-25 na Windows 11 x64): katalog
# `<program>/node-floty/<skrót>` bez onnxruntime, 438 MB plików i 483 MB na dysku NTFS (tysiące małych plików; zostaje),
# i paczki w cache npm `<cache>/npm-floty`, 239 MB (znika po instalacji); do przeniesienia do manifestu (koordynator)
NODE_FLOTY_MB = {"katalog": 490, "cache": 260}
ZAPAS = 0.1                     # do potrzeby z manifestu +10 % (pliki tymczasowe, różnice archiwów między systemami)
ZAPAS_MB = 500                  # i 0,5 GB na dysku korzenia zawsze: dziennik, bazy, build floty w każdym przebiegu
MIN_WOLNEGO_GB = 2              # doctor: mniej = błąd (bazy SQLite, logi i rendery przestają się zapisywać)
ZALECANE_WOLNE_GB = 10          # doctor i instalacja: mniej = uwaga (aktualizacja, narzędzia przy pierwszym użyciu)
CZESCI = ("program", "dane", "cache", "build")     # części korzenia w opisie zajętego miejsca; reszta to „inne”
PROG_SPRZATANIA = MB            # cache mniejszy (same znaczniki programu) zostaje: drugi przebieg nie woła uv ani pixi
# plik w <cache>/pobrane zmieniony w ostatnich 15 min może być w użyciu: pobieracz dopisuje do `.czesc` co porcję (próba
# czeka najwyżej 60 s na dane i 15 s między próbami), a gotowe archiwum rozpakowuje zaraz po pobraniu
SWIEZE_S = 15 * 60


class BrakMiejsca(BladInstalacji):
    """Instalacja nie zmieści się na tym dysku (albo, DyskBezOchrony, nie może na nim stanąć): komunikat z potrzebą,
    innymi dyskami i gotowym poleceniem. Krok 1 kończy się bez śladu błędu w dzienniku, bo niczego jeszcze nie
    zapisał."""


class DyskBezOchrony(BrakMiejsca):
    """Korzeń na woluminie bez ochrony dostępu (bez_ochrony: FAT, exFAT, NTFS na Linuksie, macOS z noowners):
    komunikat z innymi dyskami i gotowym poleceniem."""


@dataclass(frozen=True)
class Potrzeba:
    """Miejsce jednej części instalacji w bajtach: `szczyt` w czasie instalacji (z pobranymi archiwami i cache),
    `zostaje` po sprzątaniu; `gdzie` = katalog, na którego dysku leży ta część."""
    opis: str
    gdzie: Path
    szczyt: int
    zostaje: int


def gb(bajty: float) -> str:
    """Gigabajty po polsku: „11,4”, a poniżej 1 GB dwie cyfry po przecinku („0,72”)."""
    wartosc = bajty / GB
    return (f"{wartosc:.1f}" if abs(wartosc) >= 1 else f"{wartosc:.2f}").replace(".", ",")


def _tekst_pliku(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _do_instalacji(wpis: Any) -> bool:
    return isinstance(wpis, dict) and (wpis.get("kiedy") or "instalacja") == "instalacja"


def rozpakowane(wpis: dict) -> int:
    """Bajty narzędzia po rozpakowaniu: rozmiar pliku z wpisu platformy × ROZPAKOWANIE formatu."""
    return int(int(wpis.get("rozmiar") or 0) * ROZPAKOWANIE.get(str(wpis.get("format") or "zip"), 3.0))


def modul_kodu(plik: Path, nazwa: str) -> Any:
    """Moduł z kodu wersji Jarva po ścieżce (infra/node/node_floty.py, jarvo/manimgx.py, infra/bin/agent_browser.py):
    bez dopisywania czegokolwiek do sys.path, tak jak instalator bierze kod instalowanej wersji."""
    spec = importlib.util.spec_from_file_location(nazwa, plik)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def modul_node_floty(app: Path) -> Any | None:
    """infra/node/node_floty.py wersji `app`, gdy ta wersja ma narzędzia npm floty (node_floty.py i package-lock.json
    w infra/node), inaczej None."""
    katalog = Path(app) / "infra" / "node"
    if not ((katalog / "node_floty.py").is_file() and (katalog / "package-lock.json").is_file()):
        return None
    return modul_kodu(katalog / "node_floty.py", "jarvo_node_floty")


def potrzebne_miejsce(u: Uklad, app: Path, platforma: str, *, wszystko: bool = False) -> list[Potrzeba]:
    """Ile miejsca zajmie instalacja z manifestu tej wersji (vendor/natywne.lock.json) na platformie `platforma`:
    narzędzia z `kiedy: instalacja` (plik w <cache>/pobrane i rozpakowany w <program>), venvy (venvy.miejsce:
    pobranie_mb i venv_mb, koła w cache uv), modele (rozmiary plików), Tesseract (tesseract.miejsce: rozmiary paczek
    z pixi.lock), narzędzia npm floty (NODE_FLOTY_MB, gdy kod ma infra/node z lockiem, a manifest ma Node.js dla tej
    platformy), Hermes z frontem dla pinu z manifestu (stałe HERMES_MB) i flota (FLOTA_MB, gdy kod ma fleet.yaml).
    Części, które już są (znacznik sumy narzędzia, venvu, modelu, Tesseracta, narzędzi npm tego locka, Hermesa
    i frontu tego pinu, źródła skilli w <cache>/build, profile w <dane>), liczą się jako 0, więc drugi przebieg
    potrzebuje tylko zapasu; `wszystko=True` liczy całość jak na pustym dysku. Bez zapasu (dolicza go
    bilans_dyskow). Tylko odczyt."""
    from . import hermes, modele, tesseract, venvy
    narz = manifest.wczytaj(app)
    nazwy = narzedzia_instalacji(narz, platforma)
    wynik: list[Potrzeba] = []
    archiwa = rozp = ile = 0
    for nazwa in nazwy:
        wpis = manifest.plik(narz, nazwa, platforma)
        kat = u.program / "narzedzia" / nazwa / pobieracz.katalog_wersji(manifest.wersja(narz, nazwa))
        if not wszystko and _tekst_pliku(kat / ".jarvo-suma") == str(wpis.get("sha256")):
            continue
        archiwa, rozp, ile = archiwa + int(wpis.get("rozmiar") or 0), rozp + rozpakowane(wpis), ile + 1
    if ile:
        wynik += [Potrzeba(f"archiwa narzędzi ({ile})", u.cache, archiwa, 0),
                  Potrzeba(f"narzędzia ({ile})", u.program, rozp, rozp)]
    venv = cache = ile = 0
    for nazwa, wpis in manifest.venvy(app).items():
        if not _do_instalacji(wpis) or (not wszystko and venvy.zainstalowany(venvy.katalog(u, nazwa, wpis), wpis)):
            continue
        v, c = venvy.miejsce(wpis, platforma)
        venv, cache, ile = venv + v, cache + c, ile + 1
    if ile:
        wynik += [Potrzeba(f"venvy ({ile})", u.program, venv, venv), Potrzeba("cache uv venvów", u.cache, cache, 0)]
    pliki = ile = 0
    for model in manifest.modele(app).values():
        if not _do_instalacji(model) or (not wszystko and modele.gotowy(modele.katalog(u.jarvo_dane / "models",
                                                                                         model), model)):
            continue
        pliki, ile = pliki + sum(int(p.get("rozmiar") or 0) for p in model.get("pliki") or []), ile + 1
    if pliki:
        wynik.append(Potrzeba(f"modele ({ile})", u.jarvo_dane / "models", pliki, pliki))
    if "pixi" in nazwy and tesseract.projekt(app) is not None and (wszystko or not tesseract.zainstalowany(u, app)):
        cache, srodowisko_pixi, zostaje = tesseract.miejsce(app, platforma)
        wynik += [Potrzeba("cache pixi (Tesseract)", u.cache, cache, 0),
                  Potrzeba("Tesseract", u.program, srodowisko_pixi, zostaje)]
    nf = modul_node_floty(app) if "node" in nazwy else None
    if nf is not None and (wszystko or not nf.gotowy(nf.katalog_wersji(u.program, nf.suma_locka()), nf.suma_locka())):
        wynik += [Potrzeba("narzędzia npm floty", u.program, NODE_FLOTY_MB["katalog"] * MB,
                           NODE_FLOTY_MB["katalog"] * MB),
                  Potrzeba("cache npm narzędzi floty", u.cache, NODE_FLOTY_MB["cache"] * MB, 0)]
    try:
        pin = manifest.hermes(app)
    except KeyError:                                # manifest bez przypięcia Hermesa (tylko narzędzia)
        pin = {}
    commit = str(pin.get("commit") or "").lower() if isinstance(pin, dict) else ""
    if commit:
        mb = HERMES_MB
        checkout = hermes.katalog_checkoutu(u, commit)
        jest = not wszystko and srodowisko.wczytaj_json(checkout / hermes.ZNACZNIK).get("commit") == commit
        if not jest:
            wynik += [Potrzeba("Hermes (checkout i .venv)", u.program, int(mb["checkout"] * MB),
                               int(mb["checkout"] * MB)),
                      Potrzeba("cache uv Hermesa", u.cache, int(mb["cache_uv"] * MB), 0)]
        if not jest or srodowisko.wczytaj_json(checkout / hermes.ZNACZNIK_WEB).get("commit") != commit:
            wynik += [Potrzeba("node_modules frontu", u.program, int(mb["node_modules"] * MB), 0),
                      Potrzeba("front panelu i cache npm", u.program, int(mb["front"] * MB), int(mb["front"] * MB))]
    if (Path(app) / "fleet.yaml").is_file():
        if wszystko or not any((u.cache / "build").glob("*@*")):
            wynik.append(Potrzeba("źródła skilli floty", u.cache, FLOTA_MB["zrodla"] * MB, FLOTA_MB["zrodla"] * MB))
        if wszystko or not (u.dane / "profiles").is_dir():
            wynik += [Potrzeba("build floty", u.build, FLOTA_MB["build"] * MB, FLOTA_MB["build"] * MB),
                      Potrzeba("profile floty", u.dane, FLOTA_MB["profile"] * MB, FLOTA_MB["profile"] * MB)]
    return wynik


def miejsce_przy_uzyciu(app: Path, platforma: str) -> int:
    """Bajty narzędzi, venvów i modeli z `kiedy: przy-uzyciu` manifestu (Camoufox, Parakeet, CAD, ManimGX…) po
    instalacji: tyle zajmą jeszcze przy pierwszym użyciu (doctor)."""
    from . import venvy
    razem = 0
    narz = manifest.wczytaj(app)
    for nazwa, wpis in narz.items():
        if isinstance(wpis, dict) and wpis.get("kiedy") == "przy-uzyciu":
            with contextlib.suppress(manifest.BrakNarzedzia):
                razem += rozpakowane(manifest.plik(narz, nazwa, platforma))
    for wpis in manifest.venvy(app).values():
        if isinstance(wpis, dict) and wpis.get("kiedy") == "przy-uzyciu":
            razem += venvy.miejsce(wpis, platforma)[0]
    for model in manifest.modele(app).values():
        if isinstance(model, dict) and model.get("kiedy") == "przy-uzyciu":
            razem += sum(int(p.get("rozmiar") or 0) for p in model.get("pliki") or [])
    return razem


def bilans_dyskow(u: Uklad, potrzeby: list[Potrzeba], ot: Otoczenie) -> list[dict]:
    """Potrzeba z zapasem i wolne miejsce na każdym dysku, na którym leży część instalacji (Linux bez JARVO_ROOT:
    cache w ~/.cache bywa na innym dysku niż korzeń), najpierw dysk korzenia: [{"dysk", "punkt", "sciezka",
    "potrzeba", "zostaje", "wolne", "korzen"}]. `potrzeba` = suma szczytów × (1 + ZAPAS), na dysku korzenia jeszcze
    ZAPAS_MB; `wolne` None = system nie podał."""
    grupy: dict[Any, dict] = {}

    def dodaj(sciezka: Path, szczyt: int, zostaje: int) -> None:
        try:
            klucz = ot.dysk(sciezka)
        except OSError:
            klucz = _klucz(istniejacy(sciezka))
        g = grupy.setdefault(klucz, {"dysk": klucz, "sciezka": Path(sciezka), "szczyt": 0, "zostaje": 0})
        g["szczyt"] += szczyt
        g["zostaje"] += zostaje

    dodaj(u.root, 0, 0)
    for p in potrzeby:
        dodaj(p.gdzie, p.szczyt, p.zostaje)
    wynik = []
    for i, g in enumerate(grupy.values()):
        try:
            wolne = ot.wolne_miejsce(g["sciezka"])
        except OSError:
            wolne = None
        wynik.append({"dysk": g["dysk"], "punkt": punkt_dysku(g["sciezka"]), "sciezka": g["sciezka"],
                      "potrzeba": int(g["szczyt"] * (1 + ZAPAS)) + (ZAPAS_MB * MB if i == 0 else 0),
                      "zostaje": g["zostaje"], "wolne": wolne, "korzen": i == 0})
    return wynik


def inne_dyski(u: Uklad, potrzeba: int, ot: Otoczenie, pelne: set | None = None) -> list[dict]:
    """Dyski lokalne z ochroną dostępu (ot.dyski = dyski_lokalne: tylko woluminy, które przechodzą polecany) poza
    dyskami `pelne` (domyślnie dysk korzenia i cache) z co najmniej `potrzeba` B wolnego, od największego wolnego
    miejsca: [{"punkt", "wolne", "korzen"}], gdzie `korzen` to proponowany JARVO_ROOT (Windows `<dysk>\\Jarvo`, macOS
    i Linux `<katalog>/jarvo`; JARVO_ROOT przenosi pod korzeń także cache i logi, więc dysk musi pomieścić całość)."""
    zajete = set(pelne or ())
    for k in (() if pelne is not None else (u.root, u.cache)):
        with contextlib.suppress(OSError):
            zajete.add(ot.dysk(k))
    try:
        punkty = list(ot.dyski())
    except OSError:
        punkty = []
    wynik = []
    for punkt in punkty:
        try:
            numer, wolne = ot.dysk(punkt), ot.wolne_miejsce(punkt)
        except OSError:
            continue
        if numer in zajete or wolne is None or wolne < potrzeba:
            continue
        zajete.add(numer)
        wynik.append({"punkt": str(punkt), "wolne": wolne,
                      "korzen": str(Path(punkt) / ("Jarvo" if WINDOWS else "jarvo"))})
    return sorted(wynik, key=lambda k: -k["wolne"])


def polecenie_instalacji(korzen: str, *, windows: bool = WINDOWS) -> str:
    """Instalacja jednym poleceniem (bootstrap jak w radzie `jarvo` bez instalacji) z JARVO_ROOT=`korzen`: PowerShell
    na Windows, bash na macOS i Linuksie."""
    from .cli import BOOTSTRAP
    if windows:
        return f"$env:JARVO_ROOT = '{korzen.replace(chr(39), chr(39) * 2)}'; irm {BOOTSTRAP}/install.ps1 | iex"
    return f"curl -fsSL {BOOTSTRAP}/install.sh | JARVO_ROOT={shlex.quote(korzen)} bash"


def _gdzie_indziej(u: Uklad, app: Path, platforma: str, pelne: set, ot: Otoczenie, punkt: str, *, zwolnij: str,
                   instalacja: bool) -> str:
    """Druga część komunikatu nowej instalacji, która nie może stanąć na dysku `punkt`: inne dyski lokalne z ochroną
    dostępu i miejscem na całą instalację (inne_dyski poza `pelne`) i gotowe polecenie z JARVO_ROOT na pierwszym z nich,
    a bez takiego dysku `zwolnij` (co zrobić na tym dysku, z „albo” na końcu) lub inny dysk z przykładem polecenia.
    `instalacja=True`: na końcu pliki programu startowego, które bootstrap zostawił w korzeniu."""
    calosc = int(sum(p.szczyt for p in potrzebne_miejsce(u, app, platforma, wszystko=True)) * (1 + ZAPAS))
    calosc += ZAPAS_MB * MB
    kandydaci = inne_dyski(u, calosc, ot, pelne=pelne)
    if kandydaci:
        tekst = ("Wystarczy miejsca na: " + ", ".join(f"{k['punkt']} ({gb(k['wolne'])} GB wolnego)"
                                                      for k in kandydaci)
                 + f". Zainstaluj Jarvo tam jednym poleceniem{' w PowerShellu' if WINDOWS else ''}:\n    "
                 + polecenie_instalacji(kandydaci[0]["korzen"]))
    else:
        if WINDOWS:
            przyklad, dysk_ok = ("E:\\Jarvo" if punkt.upper().startswith("D:") else "D:\\Jarvo"), "z NTFS"
        elif MACOS:
            przyklad, dysk_ok = "/Volumes/Dysk/jarvo", "z APFS, bez „Ignoruj prawa własności na tym woluminie”"
        else:
            przyklad, dysk_ok = "/mnt/dysk/jarvo", "np. z ext4, xfs albo btrfs (nie FAT, exFAT ani NTFS)"
        tekst = (f"Nie znalazłem innego dysku lokalnego z ok. {gb(calosc)} GB wolnego, na którym Jarvo zachowa ochronę "
                 f"dostępu: {zwolnij}podłącz inny dysk ({dysk_ok}) i uruchom polecenie instalacji jeszcze raz "
                 f"z JARVO_ROOT na katalogu na nim, np.:\n    {polecenie_instalacji(przyklad)}")
    startowe = rozmiar_katalogu(u.root) if instalacja and u.root.is_dir() else 0
    if startowe:
        tekst += (f"\nPliki programu startowego ({gb(startowe)} GB: uv, Python i kod Jarva) są w {u.root}: po "
                  "instalacji w innym miejscu możesz usunąć ten katalog.")
    return tekst


def komunikat_braku_miejsca(u: Uklad, app: Path, platforma: str, brak: list[dict], ot: Otoczenie, *,
                            instalacja: bool = True) -> str:
    """Komunikat, gdy na dysku z `brak` (bilans_dyskow) zabraknie miejsca. Aktualizacja (jest current.json): działająca
    wersja zostaje, rada to zwolnić miejsce. Nowa instalacja: inne dyski lokalne z ochroną dostępu i miejscem na
    całość (_gdzie_indziej) i gotowe polecenie z JARVO_ROOT na pierwszym z nich, a bez takiego dysku: ile zwolnić.
    `instalacja=False` (doctor): bez zdań o tym, co zrobił instalator."""
    b = brak[0]
    nowa = not (u.program / "current.json").is_file()
    tekst = (f"na dysku {b['punkt']} jest {gb(b['wolne'])} GB wolnego miejsca, a "
             + ("instalacja Jarva" if nowa else "ta aktualizacja Jarva")
             + f" potrzebuje na nim ok. {gb(b['potrzeba'])} GB (w trakcie, z pobranymi archiwami i cache; po "
             f"sprzątaniu zostaje ok. {gb(b['zostaje'])} GB). ")
    brakuje = gb(b["potrzeba"] - b["wolne"])
    if not nowa:
        return tekst + (f"Działająca wersja zostaje bez zmian. Zwolnij na tym dysku co najmniej {brakuje} GB "
                        "i uruchom polecenie instalacji jeszcze raz.")
    if instalacja:
        tekst += "Niczego nie zainstalowałem. "
    return tekst + _gdzie_indziej(u, app, platforma, {x["dysk"] for x in brak}, ot, b["punkt"],
                                  zwolnij=f"zwolnij na dysku {b['punkt']} co najmniej {brakuje} GB albo ",
                                  instalacja=instalacja)


def komunikat_dysku_bez_ochrony(u: Uklad, app: Path, platforma: str, w: Wolumin, powod: str, ot: Otoczenie) -> str:
    """Komunikat, gdy nowa instalacja miałaby stanąć na woluminie bez ochrony dostępu (bez_ochrony): krok 1 kończy się,
    zanim cokolwiek zapisze, z innymi dyskami (_gdzie_indziej) i gotowym poleceniem; na macOS z noowners także rada,
    jak włączyć właścicieli plików na tym woluminie."""
    punkt = punkt_dysku(u.root)
    tekst = (f"korzeń {u.root} leży na dysku {punkt} ({w.typ}), a tam {powod}. Jarvo nie ograniczyłby dostępu do "
             "swoich plików (klucze API, sekrety, kod uruchamiany przez autostart) do Twojego konta. Niczego nie "
             "zainstalowałem. ")
    if "noowners" in w.opcje:
        tekst += ("Możesz włączyć właścicieli plików na tym woluminie (Finder → Informacje → odznacz „Ignoruj prawa "
                  f"własności na tym woluminie” albo `sudo diskutil enableOwnership {w.punkt}`) i uruchomić polecenie "
                  "instalacji jeszcze raz. ")
    try:
        pelne = {ot.dysk(u.root)}
    except OSError:
        pelne = set()
    return tekst + _gdzie_indziej(u, app, platforma, pelne, ot, punkt, zwolnij="", instalacja=True)


def rozmiar_katalogu(katalog: Path | str, widziane: set | None = None, *, wlasne: bool = False) -> int:
    """Bajty plików w drzewie `katalog` bez wchodzenia w dowiązania i punkty połączenia (junction: wtyczki floty,
    workspace'y npm). Twarde dowiązanie liczy się raz, gdy system podaje numer pliku (POSIX; os.scandir na Windows
    go nie podaje, więc suma jest tam górnym oszacowaniem). `wlasne=True`: tylko pliki bez innych twardych dowiązań
    (os.stat także na Windows), czyli tyle, ile zwolni usunięcie katalogu: cache pixi dzieli pliki ze środowiskiem
    Tesseracta. Brak katalogu = 0."""
    widziane = set() if widziane is None else widziane
    razem = 0
    stos = [str(katalog)]
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
                    continue
                st = os.stat(e.path, follow_symlinks=False) if wlasne and WINDOWS else e.stat(follow_symlinks=False)
            except OSError:
                continue
            if wlasne and st.st_nlink > 1:
                continue
            if st.st_nlink > 1 and st.st_ino:
                if (st.st_dev, st.st_ino) in widziane:
                    continue
                widziane.add((st.st_dev, st.st_ino))
            razem += st.st_size
    return razem


def _w_korzeniu(katalog: Path, root: Path) -> bool:
    return _klucz(katalog).startswith(_klucz(root).rstrip("\\/") + os.sep)


def usun_drzewo(p: Path) -> None:
    """rmtree, które zdejmuje atrybut tylko do odczytu (archiwa, paczki gita) i pomija pliki, których nie da się
    usunąć (zajęte przez działający program na Windows): zostają do następnego sprzątania. Punkty połączenia
    (junction) usuwa bez wchodzenia do ich celu (Python 3.12+)."""
    def ponow(funkcja, sciezka, _blad):
        try:
            os.chmod(sciezka, stat.S_IWRITE | stat.S_IREAD)
            funkcja(sciezka)
        except OSError:
            pass
    shutil.rmtree(p, onexc=ponow)


def usun_zawartosc(katalog: Path, zostaw: Callable[[os.DirEntry], bool] | None = None) -> int:
    """Pliki i podkatalogi `katalog` (sam katalog zostaje, dowiązań nie ruszamy) poza tymi, dla których `zostaw(wpis)`
    mówi True; zajęty plik zostaje. Zwraca liczbę wpisów, które zostały na prośbę `zostaw`."""
    try:
        with os.scandir(katalog) as it:
            wpisy = list(it)
    except OSError:
        return 0
    zostalo = 0
    for e in wpisy:
        try:
            if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                continue
            if zostaw is not None and zostaw(e):
                zostalo += 1
                continue
            if e.is_dir(follow_symlinks=False):
                usun_drzewo(Path(e.path))
            else:
                os.chmod(e.path, stat.S_IWRITE | stat.S_IREAD)
                os.unlink(e.path)
        except OSError:
            continue
    return zostalo


def sprzatnij_pobrane(u: Uklad, nasze: set[str], log: Callable[[str], None], *, teraz: float | None = None) -> bool:
    """Archiwa w `<cache>/pobrane` po udanym przebiegu: pliki `<16 znaków sumy>-…` z `nasze` (archiwa narzędzi tego
    przebiegu, już rozpakowane) i wszystko, czego nikt nie zmieniał od SWIEZE_S s (resztki przerwanych pobrań
    `.czesc`, archiwa starych wersji). Świeży plik spoza tego przebiegu zostaje do następnego sprzątania: pobiera go
    albo rozpakowuje inny proces (drugi instalator, przeglądarka komputera Jarva przy starcie usługi, sterownik rąk),
    a pobieracz nie bierze blokady; usunięty na macOS i Linuksie w trakcie pobierania psułby je (dopisywanie do
    odłączonego pliku, potem zła suma). Całość pod zamkiem instalacji przy pierwszym użyciu (przy_uzyciu.ZAMEK, ten sam
    co pobieranie narzędzia przy pierwszym użyciu), bez czekania: zajęty = takie pobranie właśnie trwa, więc archiwa
    zostają. True = sprzątanie przeszło."""
    from . import przy_uzyciu
    teraz = time.time() if teraz is None else teraz

    def zostaw(e: os.DirEntry) -> bool:
        nasz = not e.name.endswith(".czesc") and e.name[16:17] == "-" and e.name[:16] in nasze
        return not nasz and teraz - e.stat(follow_symlinks=False).st_mtime < SWIEZE_S

    try:
        zamek = przenosne.Zamek(u.stan / przy_uzyciu.ZAMEK, czekaj=False)
        zamek.__enter__()
    except BlockingIOError:
        log("archiwa w <cache>/pobrane zostają do następnej instalacji: trwa instalacja narzędzia przy pierwszym "
            "użyciu")
        return False
    try:
        zostalo = usun_zawartosc(u.cache / "pobrane", zostaw)
    finally:
        zamek.__exit__(None, None, None)
    if zostalo:
        log(f"w {u.cache / 'pobrane'} zostają świeże pliki, które pobiera albo rozpakowuje inny proces ({zostalo}): "
            "usunie je następne sprzątanie")
    return True


def zajete_miejsce(u: Uklad) -> dict[str, int]:
    """Bajty plików Jarva według części: program, dane, cache, build i inne (stan, logi, bin w korzeniu); na Linuksie
    bez JARVO_ROOT także cache i logi z katalogów XDG poza korzeniem. Tylko odczyt."""
    widziane: set = set()
    wynik = {c: 0 for c in (*CZESCI, "inne")}
    try:
        with os.scandir(u.root) as it:
            wpisy = list(it)
    except OSError:
        wpisy = []
    for e in wpisy:
        czesc = e.name.lower() if e.name.lower() in CZESCI else "inne"
        try:
            if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                continue
            wynik[czesc] += (rozmiar_katalogu(e.path, widziane) if e.is_dir(follow_symlinks=False)
                             else e.stat(follow_symlinks=False).st_size)
        except OSError:
            continue
    for czesc, k in (("cache", u.cache), ("inne", u.logi)):
        if not _w_korzeniu(k, u.root):
            wynik[czesc] += rozmiar_katalogu(k, widziane)
    return wynik


def opis_zajetego(zajete: dict[str, int]) -> str:
    """„5,3 GB (program 4,1, cache 0,95, dane 0,31)”: części od 0,01 GB."""
    czesci = ", ".join(f"{k} {gb(v)}" for k, v in zajete.items() if v >= GB // 100)
    return f"{gb(sum(zajete.values()))} GB" + (f" ({czesci})" if czesci else "")


def sprawdz_miejsce(u: Uklad, ot: Otoczenie | None = None) -> dict:
    """Wynik `jarvo doctor` „wolne miejsce” (ta nazwa zostaje: CI dopuszcza po niej uwagę na małym dysku runnera): ile
    zajmuje Jarvo (zajete_miejsce) i ile jest wolnego na dysku korzenia; poniżej MIN_WOLNEGO_GB błąd, poniżej
    ZALECANE_WOLNE_GB uwaga z tym, ile zajmą narzędzia przy pierwszym użyciu. Przed instalacją: ile potrzebuje
    instalacja z manifestu tej wersji i czy się zmieści (za mało = błąd z innymi dyskami i poleceniem). Tylko odczyt."""
    ot = ot or Otoczenie()

    def wynik(stan: str, opis: str, rada: str = "") -> dict:
        return {"nazwa": "wolne miejsce", "stan": stan, "opis": opis, "rada": rada}

    try:
        wolne = ot.wolne_miejsce(u.root)
    except OSError as e:
        return wynik("uwaga", f"nie umiem sprawdzić ({e})", "Sprawdź dysk ręcznie.")
    punkt = punkt_dysku(u.root)
    app = katalog_aplikacji(u)
    try:
        platforma = sciezki.platforma()
    except sciezki.BladUkladu:
        platforma = ""
    if not (u.program / "current.json").is_file():
        try:
            potrzeby = potrzebne_miejsce(u, app, platforma) if platforma else None
        except (OSError, ValueError, KeyError):
            potrzeby = None
        if potrzeby is None:
            return wynik("ok", f"{gb(wolne)} GB wolnego na dysku {punkt} (Jarva tu jeszcze nie ma)")
        bilans = bilans_dyskow(u, potrzeby, ot)
        opis = (f"{gb(wolne)} GB wolnego na dysku {punkt}; instalacja potrzebuje ok. {gb(bilans[0]['potrzeba'])} GB "
                f"(po sprzątaniu zostaje ok. {gb(sum(p.zostaje for p in potrzeby))} GB)")
        brak = [b for b in bilans if b["wolne"] is not None and b["wolne"] < b["potrzeba"]]
        if brak:
            return wynik("blad", opis, komunikat_braku_miejsca(u, app, platforma, brak, ot, instalacja=False))
        return wynik("ok", opis)
    opis = f"Jarvo zajmuje {opis_zajetego(zajete_miejsce(u))}; wolne {gb(wolne)} GB na dysku {punkt}"
    if wolne < MIN_WOLNEGO_GB * GB:
        return wynik("blad", opis, f"Przy zapełnionym dysku bazy (SQLite), logi i rendery przestają się zapisywać: "
                                   f"zwolnij miejsce na dysku {punkt}.")
    if wolne < ZALECANE_WOLNE_GB * GB:
        try:
            dodatki = f"ok. {gb(miejsce_przy_uzyciu(app, platforma))} GB" if platforma else "kilka GB"
        except (OSError, ValueError, KeyError):
            dodatki = "kilka GB"
        return wynik("uwaga", opis, "Aktualizacja stawia nową wersję obok działającej, a narzędzia przy pierwszym "
                                    f"użyciu (Camoufox, Parakeet, CAD, ManimGX…) zajmą jeszcze {dodatki}: zwolnij "
                                    "miejsce, zanim je doinstalujesz.")
    return wynik("ok", opis)


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
        self.stara: Any = None               # stara instalacja z Dockerem (migracja.Wykrycie): najpierw przeniesienie

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
        if "node" in nazwy and modul_node_floty(self.app) is not None:      # po Node.js i ffmpeg z manifestu
            k.append(("Narzędzia npm floty", self.node_floty))
        k += [("Spis narzędzi", self.spis_narzedzi), ("Wersja Jarva", self.wersja_jarva), ("Hermes", self.hermes),
              ("Front panelu", self.front), ("Bezpieczne ustawienia Hermesa", self.konfiguracja),
              ("Klucz API bramy", self.klucz_api), ("Przełączenie wersji", self.przelaczenie),
              ("Programy floty", self.programy_floty), ("Flota", self.flota),
              ("Środowisko procesów", self.zapis_srodowiska)]
        # stara flota z Dockerem: polecenie jarvo, autostart i start dopiero po przeniesieniu danych (nigdy dwie
        # floty naraz: jeden token Telegrama to jedna brama)
        self.stara = (self.ot.stara or wykryj_stara)(self.u, self.ot)
        if self.stara is not None:
            k.append(("Przeniesienie ze starej instalacji", self.przeniesienie))
        k.append(("Polecenie jarvo", self.polecenie))
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
            except PrzeniesienieOdlozone as e:
                self.log(str(e))
                return 3
            except Exception as e:    # noqa: BLE001 - każdy błąd kroku kończy instalację czytelnym komunikatem
                self.log(f"BŁĄD w kroku „{nazwa}”: {e}")
                if isinstance(e, BrakMiejsca):       # komunikat ma już polecenie z JARVO_ROOT albo radę
                    return 1
                self._slad()
                self._po_bledzie()
                self.log("Instalację można uruchomić ponownie: gotowe kroki zostaną pominięte.")
                return 1
        if self.oznaczone:                   # bez startu teraz (--bez-startu): autostart podniesie nową wersję sam
            zdejmij_zatrzymanie(self.u, self.ot)
        self.sprzatanie()
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

    # -- sprzątanie po udanym przebiegu (c3 pkt 11, Z31; docstring modułu)
    def _funkcja(self, modul: str, nazwa: str) -> Callable | None:
        """Funkcja modułu Jarva z Otoczenia albo None (brak modułu albo starsza wersja bez tej funkcji)."""
        try:
            f = getattr(self.ot.modul(modul), nazwa, None)
        except ImportError:
            return None
        return f if callable(f) else None

    def _archiwa_przebiegu(self) -> set[str]:
        """16 znaków sumy archiwów narzędzi z manifestu, które ten przebieg zainstalował albo zastał (self.narz):
        są już rozpakowane, więc sprzątanie usuwa je od razu, także świeże."""
        try:
            narz = manifest.wczytaj(self.app)
        except (OSError, ValueError, KeyError):
            return set()
        wynik = set()
        for nazwa in self.narz:
            with contextlib.suppress(manifest.BrakNarzedzia, KeyError, TypeError, AttributeError):
                if isinstance(narz.get(nazwa), dict):
                    wynik.add(str(manifest.plik(narz, nazwa, self.platforma).get("sha256") or "")[:16])
        return wynik - {""}

    def sprzatanie(self) -> None:
        """Archiwa z <cache>/pobrane (sprzatnij_pobrane: archiwa tego przebiegu i pliki starsze niż SWIEZE_S, także
        niedokończone .czesc), cache uv (venvy.sprzatnij_cache), cache pixi (tesseract.sprzatnij_cache), cache npm
        narzędzi floty (`<cache>/npm-floty`: paczki z locka infra/node, które npm ci już rozpakował; nowy lock pobierze
        je od nowa, jak koła uv) i katalogi `<wersja>.stary-*` narzędzi, które pobieracz zostawił przy zajętym pliku.
        Cache sprzątamy pod tymi samymi zamkami, które biorą instalatory (przy pierwszym użyciu, venvy, hermes,
        tesseract), bez czekania: drugi instalator, który właśnie z nich korzysta, zostawia je do następnego sprzątania.
        Zwolnione miejsce to pliki bez innych twardych dowiązań przed i po (rozmiar_katalogu wlasne=True: plik dzielony
        ze środowiskiem Tesseracta miejsca nie zwalnia). Cache poniżej PROG_SPRZATANIA (same pliki znaczników) zostaje,
        więc drugi przebieg nie woła uv. Nic tu nie przerywa udanej instalacji: błąd to uwaga. Na końcu wiersz „Miejsce”
        (zajęte i wolne, jak w `jarvo doctor`)."""
        zwolnione: list[tuple[str, int]] = []

        def rozmiar(katalog: Path) -> int:
            return rozmiar_katalogu(katalog, wlasne=True) if katalog.exists() else 0

        def mierz(opis: str, katalog: Path, sprzataj: Callable[[], Any], prog: int = PROG_SPRZATANIA) -> None:
            przed = rozmiar(katalog)
            if not przed or przed < prog:
                return
            try:
                sprzataj()
            except Exception as e:  # noqa: BLE001 - sprzątanie nie psuje udanej instalacji
                self.uwagi.append(f"sprzątanie ({opis}) nie przeszło: {type(e).__name__}: {str(e)[:200]}")
            zwolnione.append((opis, max(przed - rozmiar(katalog), 0)))

        nasze = self._archiwa_przebiegu()
        mierz("archiwa narzędzi", self.u.cache / "pobrane", lambda: sprzatnij_pobrane(self.u, nasze, self.podlog),
              prog=1)
        uv = self._funkcja("venvy", "sprzatnij_cache")
        if uv is not None and "uv" in self.narz:
            mierz("cache uv", self.u.cache / "uv", lambda: uv(self.u, self._bin_narzedzia("uv"), log=self.podlog))
        pixi = self._funkcja("tesseract", "sprzatnij_cache")
        if pixi is not None:
            mierz("cache pixi", self.u.cache / "pixi", lambda: pixi(self.u, log=self.podlog))
        nf = modul_node_floty(self.app)                  # paczki npm narzędzi floty: drugi przebieg ich nie potrzebuje
        if nf is not None:
            npm_floty = self.u.cache / nf.CACHE_NPM
            mierz("cache npm narzędzi floty", npm_floty, lambda: usun_drzewo(npm_floty), prog=1)
        for stary in sorted((self.u.program / "narzedzia").glob("*/*.stary-*")):
            mierz(f"stara wersja {stary.parent.name}", stary, lambda s=stary: usun_drzewo(s), prog=1)
        razem = sum(z for _o, z in zwolnione)
        if razem:
            self.log(f"Sprzątanie: zwolnione {gb(razem)} GB ("
                     + ", ".join(f"{o} {gb(z)} GB" for o, z in zwolnione if z) + ")")
        try:
            wolne = self.ot.wolne_miejsce(self.u.root)
        except OSError:
            return
        self.log(f"Miejsce: Jarvo zajmuje {opis_zajetego(zajete_miejsce(self.u))}; wolne {gb(wolne)} GB na dysku "
                 f"{punkt_dysku(self.u.root)}")

    # -- kroki
    def sprawdzenie(self) -> None:
        self.platforma = self.platforma or sciezki.platforma()
        self.podlog(f"platforma {self.platforma}, Python {sys.version.split()[0]}")
        powod = obca_instalacja(self.u, polecenie_w_domu=not self.bez_path)
        if self.stara is not None:
            self.podlog("stara instalacja z Dockerem: najpierw wersja natywna (bez startu), potem przeniesienie "
                        "danych za zgodą" + (f" ({powod})" if powod else ""))
        elif powod:
            obok = (f"ustaw JARVO_ROOT na osobny katalog (np. {PRZYKLAD_KORZENIA})" if WINDOWS else
                    "uruchom polecenie z JARVO_BEZ_PATH=1 (polecenie jarvo tylko w <korzeń>/bin)")
            raise BladInstalacji(f"{powod}. Uruchom polecenie instalacji bez JARVO_MIGRACJA=nie: przeniesie dane do "
                                 f"wersji natywnej (pyta o zgodę przed każdą zmianą). Obok starej instalacji: {obok}.")
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
        self.bilans_miejsca()

    def bilans_miejsca(self) -> None:
        """Najpierw wolumin korzenia (Otoczenie.wolumin, bez_ochrony): na FAT, exFAT, NTFS na Linuksie albo woluminie
        macOS z noowners korzeń nie byłby tylko dla właściciela, więc nowa instalacja kończy się DyskBezOchrony
        (z innymi dyskami i poleceniem), a działająca instalacja dostaje uwagę (aktualizacji nie blokujemy). Wolumin
        nieznany (None) nie zatrzymuje. Potem potrzeba z manifestu (potrzebne_miejsce: tylko części, których jeszcze
        nie ma) wobec wolnego miejsca na każdym dysku instalacji (bilans_dyskow). Za mało = BrakMiejsca. Obie odmowy
        są jeszcze w kroku 1, czyli zanim instalator cokolwiek zapisze (katalogi zakłada krok 2). Mało miejsca po
        instalacji = uwaga."""
        try:
            w = self.ot.wolumin(self.u.root)
        except OSError:
            w = None
        powod = bez_ochrony(w) if w is not None else None
        if powod and not (self.u.program / "current.json").is_file():
            raise DyskBezOchrony(komunikat_dysku_bez_ochrony(self.u, self.app, self.platforma, w, powod, self.ot))
        if powod:
            uwaga = (f"korzeń {self.u.root} leży na dysku {punkt_dysku(self.u.root)} ({w.typ}), a tam {powod}: "
                     "ochrona dostępu do plików Jarva nie działa. Zainstaluj Jarvo od nowa na dysku z ochroną "
                     "dostępu (JARVO_ROOT)" + (" albo włącz właścicieli plików na tym woluminie (sudo diskutil "
                                               f"enableOwnership {w.punkt})" if "noowners" in w.opcje else ""))
            self.podlog(f"uwaga: {uwaga}")
            self.uwagi.append(uwaga)
        potrzeby = potrzebne_miejsce(self.u, self.app, self.platforma)
        bilans = bilans_dyskow(self.u, potrzeby, self.ot)
        for b in bilans:
            wolne = "nie wiem, ile" if b["wolne"] is None else f"{gb(b['wolne'])} GB"
            if not potrzeby:
                self.podlog(f"miejsce na dysku {b['punkt']}: wszystkie części instalacji już są (zapas "
                            f"{gb(b['potrzeba'])} GB), wolne {wolne}")
                continue
            self.podlog(f"miejsce na dysku {b['punkt']}: potrzeba ok. {gb(b['potrzeba'])} GB w trakcie instalacji "
                        f"(po sprzątaniu zostaje ok. {gb(b['zostaje'])} GB), wolne {wolne}")
        brak = [b for b in bilans if b["wolne"] is not None and b["wolne"] < b["potrzeba"]]
        if brak:
            raise BrakMiejsca(komunikat_braku_miejsca(self.u, self.app, self.platforma, brak, self.ot))
        korzen = bilans[0]
        po = None if korzen["wolne"] is None else korzen["wolne"] - korzen["zostaje"]
        if po is not None and potrzeby and po < ZALECANE_WOLNE_GB * GB:
            uwaga = (f"po instalacji zostanie ok. {gb(po)} GB wolnego na dysku {korzen['punkt']}: aktualizacja i "
                     "narzędzia przy pierwszym użyciu (Camoufox, Parakeet, CAD…) potrzebują więcej (`jarvo doctor` "
                     "pokazuje zajęte i wolne miejsce)")
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
        if nazwa in przenosne.PRZEGLADARKI_CHROMIUM and przenosne.dla_piaskownicy_chromium(katalog):
            self.podlog(f"{nazwa}: odczyt dla piaskownicy Chromium (ALL RESTRICTED APPLICATION PACKAGES)")
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

    def node_floty(self) -> None:
        """Narzędzia npm floty (P02, I32): infra/node/node_floty.py tej wersji robi `npm ci --ignore-scripts` z
        package-lock.json (suma integrity każdej paczki z registry.npmjs.org) do `<program>/node-floty/<skrót locka>`
        npm-em z Node.js z manifestu (nigdy z PATH właściciela), z cache npm w `<cache>/npm-floty`, który sprząta koniec
        udanego przebiegu. Wpis `node-floty` w narzedzia.json daje procesom Jarva node_modules/.bin w PATH (hyperframes,
        lighthouse, svgo…), NODE_PATH (playwright-core, three, inspo-mcp dla skryptów floty i serwerów MCP), HyperFrames
        bez telemetrii i autoaktualizacji, z ffmpeg i ffprobe z manifestu. Katalog gotowy dla tego locka = bez npm
        i bez sieci (drugi przebieg niczego nie zmienia)."""
        nf = modul_node_floty(self.app)
        npm = self._program_narzedzia("node", "npm")
        if npm is None:
            katalog = (self.narz.get("node") or {}).get("katalog") or "katalogu Node.js"
            raise BladInstalacji(f"narzędzia npm floty potrzebują npm z Node.js z manifestu, a w {katalog} go nie ma: "
                                 "usuń ten katalog i uruchom instalację jeszcze raz")
        bin_ffmpeg = [Path(k) for nazwa in ("ffmpeg", "ffmpeg-macos", "ffprobe-macos")
                      for k in (self.narz.get(nazwa) or {}).get("bin") or []]
        try:
            spis, zmiana = nf.zainstaluj(self.u.program, npm, cache=self.u.cache, bin_ffmpeg=bin_ffmpeg,
                                         log=self.podlog)
        except nf.BladNodeFloty as e:
            raise BladInstalacji(f"{e}\nPrzy błędzie sieci uruchom instalację jeszcze raz: pobrane już paczki zostają "
                                 f"w {self.u.cache / nf.CACHE_NPM}.") from None
        self.narz["node-floty"] = spis
        self.podlog(f"narzędzia npm floty: {'zainstalowane' if zmiana else 'już są'} ({spis['katalog']})")
        if zmiana:
            self.zmiany.append("narzędzia npm floty")

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
        zmiany = list(zmiany or []) + self._agent_browser(narz) + self._manimgx()
        self.podlog(f"programy floty w {self.u.bin_floty}: " + ("zapisane" if zmiany else "bez zmian"))
        if zmiany:
            self.zmiany.append("programy floty")

    def _agent_browser(self, narz: dict) -> list:
        """Program `agent-browser` w bin-floty (nakładka Jarva z infra/bin/agent_browser.py tej wersji: wyłącza serwer
        podglądu demona, C05) dla Pythona z instalacji; na macOS i Linuksie także `chromium` dla chrome-headless-shell."""
        if not isinstance(narz.get("agent-browser"), dict):
            return []
        modul = modul_kodu(self.app / "infra" / "bin" / "agent_browser.py", "jarvo_agent_browser")
        chrome = ((narz.get("chrome-headless-shell") or {}).get("env") or {}).get("CHROME_PATH")
        return [str(p) for p in modul.zainstaluj(self.u.bin_floty, self._bin_narzedzia("python313"), chrome=chrome)]

    def _manimgx(self) -> list:
        """Program `manimgx` w bin-floty (jarvo/manimgx.py tej wersji, M04) dla Pythona 3.13 z instalacji, zbudowany
        jak nakładka agent-browsera: pierwsze wywołanie instaluje venv `manimgx` z locka z sumami (przy pierwszym
        użyciu, jarvo/przy_uzyciu.py), potem przekazuje argumenty do programu venvu. Skille Wideografa wołają
        `manimgx inspect|render …` tak jak w obrazie z dodatkiem `manim`."""
        zrodlo = self.app / "jarvo" / "manimgx.py"
        if not zrodlo.is_file() or "python313" not in self.narz \
                or not (self.app / "infra" / "bin" / "agent_browser.py").is_file():
            return []
        modul = modul_kodu(zrodlo, "jarvo_manimgx")
        return [str(p) for p in modul.zainstaluj(self.u.bin_floty, self._bin_narzedzia("python313"))]

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

    def przeniesienie(self) -> None:
        """Dane starej instalacji z Dockerem do tej (jarvo/migracja.py: rozbrojenie starej floty, kopia z sumą, próba,
        import; każda zmiana za zgodą, JARVO_YES=1 = zgoda). Start robią następne kroki tej instalacji. Bez zgody:
        PrzeniesienieOdlozone, a stara flota pracuje dalej; przerwana migracja rusza przy następnym przebiegu od
        pierwszego niezrobionego etapu."""
        migracja = self.ot.modul("migracja")
        argv = ["--bez-startu", *(["--tak"] if self.ot.env.get("JARVO_YES") == "1" else [])]
        self.log("")
        kod = migracja.main(argv, uklad=self.u, otoczenie=self.ot)
        self.log("")
        if kod == 3:
            raise PrzeniesienieOdlozone(
                "Bez zgody na przeniesienie: stara flota pracuje dalej i niczego w niej nie zmieniłem. Wersja natywna "
                f"jest zainstalowana w {self.u.root}, ale nie działa (nigdy dwie floty naraz). Przeniesienie danych: "
                "uruchom to samo polecenie instalacji jeszcze raz.")
        if kod != 0:
            raise BladInstalacji("przeniesienie danych przerwane (opis wyżej; dziennik "
                                 f"{self.u.logi / 'migracja.log'}). Dane starej instalacji są nietknięte albo w kopii, "
                                 "a ponowne polecenie instalacji rusza od pierwszego niezrobionego etapu.")
        self.zmiany.append("przeniesienie ze starej instalacji")
        self.stara = None

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
        if not self.bez_path and (cel.is_symlink() or (cel.is_file() and ZNACZNIK not in cel.read_text(
                encoding="utf-8", errors="replace"))):
            # stare polecenie (np. dowiązanie do ~/jarvo/bin/jarvo), którego migracja nie dostała zgody usunąć
            self.uwagi.append(f"{cel} należy do innej instalacji Jarvo i zostaje; polecenie tej: "
                              f"{self.u.root / 'bin' / 'jarvo'}")
            self.bez_path = True
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
    """Instalacja albo naprawa Jarva w układzie `u` z kodu w `app`; 0 = gotowe, 1 = błąd (komunikat wypisany), 3 =
    gotowe bez przeniesienia danych starej instalacji z Dockerem (brak zgody: stara flota pracuje dalej, ta stoi).
    `start=False` kończy po poleceniu jarvo i autostarcie (bez startu serwisu); `bez_path=True`: polecenie tylko
    w `<root>/bin`, bez PATH i plików startowych powłoki (próby na komputerze właściciela)."""
    inst = _Instalacja(bezwzgledny(u), app, otoczenie or Otoczenie(), log, autostart=autostart,
                       web_lokalnie=web_lokalnie, start=start, bez_path=bez_path, platforma=platforma)
    with _katalog_biezacy(inst.app):
        return inst.uruchom()

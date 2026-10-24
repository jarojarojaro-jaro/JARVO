"""Nadzorca procesów Jarva: polecenie `jarvo serwis` (docs/NATYWNIE.md: H04, H09, H22, c2, I10, N03).

Zastępuje s6 z kontenera. Autostart systemu (Harmonogram zadań, LaunchAgent, systemd --user) uruchamia tylko to
polecenie, na pierwszym planie: jeden kod na trzy systemy, bez NSSM, WinSW, supervisord i bez `hermes gateway
install` (I10). Jeden nadzorca na korzeń Jarva: blokada `<stan>/nadzorca.lock` bez czekania, drugi start kończy się
komunikatem i kodem 1.

Usługi (uslugi_jarva; flagi i zmienne sprawdzone w kodzie Hermesa f97608f):
- brama (H04): `python -m hermes_cli.main gateway run --external-supervisor`. Flaga ustawia w procesie
  HERMES_GATEWAY_EXTERNAL_SUPERVISOR=1, więc /restart z czatu i `hermes update` kończą bramę kodem 75 i oddają
  restart nadzorcy, zamiast stawiać odłączonego pomocnika (gateway/restart.py is_gateway_supervisor_process,
  gateway/slash_commands.py). HERMES_SUPERVISED_CHILD=1 to znacznik launchera: brama i panel mają stałą tożsamość
  profilu (nie idą za `hermes profile use`), a polecenie z wnętrza bramy nie zabije procesu, który je hostuje; sam
  nie wybiera drogi kodu 75 (Harmonogram Hermesa ustawia go bez polityki restartu). HERMES_GATEWAY_DETACHED=1: na
  Windows brama ignoruje Ctrl+C i Ctrl+Break z konsoli. Dlatego łagodne zatrzymanie bramy to znacznik planowanego
  zatrzymania `<dane>/.gateway-planned-stop.json`, który pisze pomocnik Hermesa `python -m gateway.systemd_stop_mark
  <pid>` (ten sam co ExecStop jego jednostki systemd). Brama sprawdza znacznik co 0,5 s, drenuje tury i kończy się
  kodem 0; bez niego SIGTERM wygląda dla niej na awarię. Kod 75 (EX_TEMPFAIL) = restart po ok. 5 s, kod 78
  (EX_CONFIG, np. ten sam token w dwóch miejscach) = postój z powodem z `<dane>/gateway_state.json`, aż właściciel
  poprawi konfigurację i zleci restart. Gotowość: odpowiedź na `identify` przez potok sterujący bramy
  (gateway/control_socket.py: Windows `\\\\.\\pipe\\hermes-gateway-<skrót>`, POSIX `<dane>/gateway.sock`).
- panel (H09): `python -m hermes_cli.main dashboard --host 127.0.0.1 --port <JARVO_PANEL_PORT albo 9119> --no-open
  --skip-build`, gotowy, gdy GET /api/status zwraca 200. uvicorn kończy się łagodnie na Ctrl+Break i SIGTERM.

Pętla (c2): start w kolejności (panel czeka na gotowość bramy, najdłużej `limit_kolejnosci`); kod 75 = restart po
ok. 5 s; kod 78 = postój; inne kody = ponowienie z rosnącą przerwą 5 s → 5 min (zeruje ją 10 min działania).
Gotową usługę sprawdzamy dalej co 30 s, ale tylko do raportu (własne strażniki ma Hermes). Stan (pid, od kiedy,
restarty, ostatni kod, gotowość, powód) w `<stan>/nadzorca.json`, zapisywany atomowo. Czyta go `jarvo status`:
WMIC zniknął z Windows 11, więc PID-y zna tylko nadzorca (N03).

Windows: dzieci startują z CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB (bez BREAKAWAY,
gdy job rodzica go zabrania), bez Job Object z KILL_ON_JOB_CLOSE i nigdy przez `taskkill /T`. `Scripts\\python.exe`
venvu to launcher: uruchamia bazowy python.exe jako dziecko we własnym jobie (KILL_ON_JOB_CLOSE |
SILENT_BREAKAWAY_OK) i sam ignoruje zdarzenia konsoli (sprawdzone na Windows 11, sekcja l). Zatrzymanie usługi:
najpierw łagodnie (Windows: CTRL_BREAK_EVENT do grupy przez krótki proces pomocnika, który dołącza do ukrytej
konsoli usługi, bo GenerateConsoleCtrlEvent działa tylko w obrębie jednej konsoli; POSIX: SIGTERM), po 30 s
zabicie launchera i jego BEZPOŚREDNICH dzieci (lista przez CreateToolhelp32Snapshot, bez conhost.exe), bez
wnuków: pracownicy kanbana i polecenia terminala mają własną ukrytą konsolę i są poza jobem launchera, więc
kończą swoje karty (H07).

Logi: stdout i stderr usługi w `<logi>/<nazwa>.log` (na Windows uchwyt tylko do dopisywania, z FILE_SHARE_READ,
WRITE i DELETE), rotacja „kopiuj i przytnij”: do 3 kopii `.1`–`.3` po 10 MB. Dziennik nadzorcy: `<logi>/nadzorca.log`.
Środowiska, argumentów ani sekretów tam nie piszemy.

Kanał sterowania (multiprocessing.connection, wiadomości JSON, nigdy pickle): Windows potok `\\\\.\\pipe\\jarvo-
nadzorca-<skrót korzenia>` z DACL tylko dla bieżącego użytkownika i bez klientów zdalnych; POSIX gniazdo
`<stan>/nadzorca.sock` (0600 w katalogu 0700; przy zbyt długiej ścieżce krótkie w katalogu tymczasowym). Klucz
authkey `<stan>/nadzorca.klucz` (secrets.token_bytes, chron), nowy przy każdym starcie. polacz(u) daje klienta:
status(), restart(nazwa), stop(). Proces usługi, który przeżył poprzedniego nadzorcę (np. zabitego twardo albo
z zamkniętym oknem konsoli), nadzorca rozpoznaje po PID-zie i czasie startu ze stanu i zatrzymuje przed startem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from multiprocessing import connection
from pathlib import Path
from typing import Callable

from . import przenosne, srodowisko
from .sciezki import LINUX, WINDOWS, BladUkladu, Uklad, uklad

KOD_RESTART = 75          # EX_TEMPFAIL: brama (i panel przy zajętym porcie) prosi o restart
KOD_POSTOJ = 78           # EX_CONFIG: błąd konfiguracji, ponowienie nic nie zmieni
PORT_PANELU = 9119
WERSJA_STANU = 1

_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_MAKS_GNIAZDA = 100                       # sun_path: 104 bajty na macOS, 108 na Linuksie
_MAKS_WIADOMOSCI = 1 << 20
_SEKRETY = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{25,}|\b(?:sk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{12,}"
                      r"|[A-Za-z0-9_-]{32,}")


class BladNadzorcy(RuntimeError):
    """Błąd nadzorcy albo kanału sterowania (komunikat po polsku, bez sekretów)."""


class NadzorcaJuzDziala(BladNadzorcy):
    """Inny nadzorca trzyma już blokadę tego korzenia Jarva."""


class NadzorcaNieDziala(BladNadzorcy):
    """Kanał sterowania nie odpowiada: nadzorca nie działa albo dopiero startuje."""


@dataclass
class Usluga:
    """Proces pod nadzorem.

    `gotowa()` -> bool: czy usługa już obsługuje (None: gotowa od startu). `kolejnosc`: mniejsze startują pierwsze,
    następne czekają na ich gotowość. `przed_stopem(pidy)` dostaje PID-y właściwych procesów (na Windows dzieci
    launchera) tuż przed łagodnym zatrzymaniem. `powod_postoju()` dopowiada powód kodu 78. `launcher`: czy argv[0]
    uruchamia właściwy proces jako swoje dziecko (None: rozpoznaj `Scripts\\python.exe` venvu; tylko Windows).
    """
    nazwa: str
    argv: list[str]
    cwd: str | Path | None = None
    env: dict[str, str] | None = None
    gotowa: Callable[[], bool] | None = None
    kolejnosc: int = 0
    przed_stopem: Callable[[list[int]], None] | None = None
    powod_postoju: Callable[[], str | None] | None = None
    launcher: bool | None = None


# --- procesy na Windows: ctypes, sama biblioteka standardowa ------------------------------------------------------

if WINDOWS:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _NIEWAZNY = ctypes.c_void_p(-1).value
    _STILL_ACTIVE = 259
    _PRAWO_ZAPYTANIA = 0x1000             # PROCESS_QUERY_LIMITED_INFORMATION
    _PRAWO_ZAKONCZENIA = 0x0001           # PROCESS_TERMINATE
    _SYNCHRONIZE = 0x00100000

    class _WpisProcesu(ctypes.Structure):             # PROCESSENTRY32W
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    class _AtrybutyBezpieczenstwa(ctypes.Structure):  # SECURITY_ATTRIBUTES
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    def _sygnatury() -> None:
        H, D, B, P = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER
        for biblioteka, nazwa, wynik, argumenty in (
                (_k32, "CreateToolhelp32Snapshot", H, [D, D]),
                (_k32, "Process32FirstW", B, [H, P(_WpisProcesu)]),
                (_k32, "Process32NextW", B, [H, P(_WpisProcesu)]),
                (_k32, "OpenProcess", H, [D, B, D]),
                (_k32, "GetExitCodeProcess", B, [H, P(D)]),
                (_k32, "GetProcessTimes", B, [H] + [P(wintypes.FILETIME)] * 4),
                (_k32, "TerminateProcess", B, [H, wintypes.UINT]),
                (_k32, "WaitForSingleObject", D, [H, D]),
                (_k32, "CloseHandle", B, [H]),
                (_k32, "CreateFileW", H, [wintypes.LPCWSTR, D, D, wintypes.LPVOID, D, D, H]),
                (_k32, "CreateNamedPipeW", H, [wintypes.LPCWSTR, D, D, D, D, D, D, P(_AtrybutyBezpieczenstwa)]),
                (_k32, "GetCurrentProcess", H, []),
                (_k32, "LocalFree", wintypes.HLOCAL, [wintypes.HLOCAL]),
                (_adv, "OpenProcessToken", B, [H, D, P(H)]),
                (_adv, "GetTokenInformation", B, [H, ctypes.c_int, wintypes.LPVOID, D, P(D)]),
                (_adv, "ConvertSidToStringSidW", B, [wintypes.LPVOID, P(wintypes.LPWSTR)]),
                (_adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", B,
                 [wintypes.LPCWSTR, D, P(wintypes.LPVOID), P(wintypes.ULONG)])):
            f = getattr(biblioteka, nazwa)
            f.restype, f.argtypes = wynik, argumenty

    _sygnatury()

    def _czas_startu(uchwyt) -> int | None:
        t = [wintypes.FILETIME() for _ in range(4)]
        if not _k32.GetProcessTimes(uchwyt, *(ctypes.byref(x) for x in t)):
            return None
        return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime

    def _sid_uzytkownika() -> str | None:
        """SID bieżącego użytkownika (z tokenu procesu) jako tekst S-1-5-…, albo None."""
        token = wintypes.HANDLE()
        if not _adv.OpenProcessToken(_k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):   # TOKEN_QUERY
            return None
        try:
            n = wintypes.DWORD()
            _adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(n))                     # TokenUser
            if not n.value:
                return None
            bufor = ctypes.create_string_buffer(n.value)
            if not _adv.GetTokenInformation(token, 1, bufor, n, ctypes.byref(n)):
                return None
            sid = ctypes.cast(bufor, ctypes.POINTER(wintypes.LPVOID))[0]
            tekst = wintypes.LPWSTR()
            if not _adv.ConvertSidToStringSidW(sid, ctypes.byref(tekst)):
                return None
            try:
                return tekst.value
            finally:
                _k32.LocalFree(ctypes.cast(tekst, wintypes.LPVOID))
        finally:
            _k32.CloseHandle(token)


def _odcisk(pid: int | None) -> str | None:
    """Czas startu działającego procesu jako tekst: odróżnia go od innego procesu, który dostał ten sam PID.
    None, gdy proces nie działa (także zombie)."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if WINDOWS:
        h = _k32.OpenProcess(_PRAWO_ZAPYTANIA, False, pid)
        if not h:
            return None
        try:
            kod = wintypes.DWORD()
            if not _k32.GetExitCodeProcess(h, ctypes.byref(kod)) or kod.value != _STILL_ACTIVE:
                return None
            czas = _czas_startu(h)
            return None if czas is None else str(czas)
        finally:
            _k32.CloseHandle(h)
    if LINUX:
        try:
            pola = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace").rpartition(")")[2].split()
        except OSError:
            return None
        return pola[19] if len(pola) > 19 and pola[0] not in ("Z", "X") else None    # pole 22: starttime
    try:                                  # macOS: osobne -o, bo tekst po „=” to nagłówek do końca argumentu
        wynik = subprocess.run(["ps", "-o", "stat=", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    stan, _, start = wynik.stdout.strip().partition(" ")
    if not stan or stan.startswith("Z"):
        return None
    return start.strip() or None


def dzieci(pid: int) -> list[tuple[int, str]]:
    """Bezpośrednie dzieci procesu na Windows jako (pid, odcisk): bez conhost.exe (ukryta konsola znika sama) i bez
    procesów starszych od rodzica (ich rodzicem był wcześniejszy proces z tym samym PID-em). Poza Windows pusto."""
    if not WINDOWS:
        return []
    rodzic = _odcisk(pid)
    if rodzic is None:
        return []
    migawka = _k32.CreateToolhelp32Snapshot(0x2, 0)                                 # TH32CS_SNAPPROCESS
    if not migawka or migawka == _NIEWAZNY:
        return []
    kandydaci = []
    try:
        wpis = _WpisProcesu()
        wpis.dwSize = ctypes.sizeof(_WpisProcesu)
        jest = _k32.Process32FirstW(migawka, ctypes.byref(wpis))
        while jest:
            if (wpis.th32ParentProcessID == pid and wpis.th32ProcessID not in (0, pid)
                    and wpis.szExeFile.lower() != "conhost.exe"):
                kandydaci.append(wpis.th32ProcessID)
            jest = _k32.Process32NextW(migawka, ctypes.byref(wpis))
    finally:
        _k32.CloseHandle(migawka)
    wynik = []
    for d in kandydaci:
        odcisk = _odcisk(d)
        if odcisk is not None and int(odcisk) >= int(rodzic):
            wynik.append((d, odcisk))
    return wynik


def _zabij_pid(pid: int, odcisk: str | None = None) -> bool:
    """Twarde zabicie JEDNEGO procesu (bez drzewa). Z `odcisk` tylko wtedy, gdy to dalej ten sam proces."""
    if WINDOWS:
        h = _k32.OpenProcess(_PRAWO_ZAKONCZENIA | _PRAWO_ZAPYTANIA | _SYNCHRONIZE, False, pid)
        if not h:
            return False
        try:
            if odcisk is not None and str(_czas_startu(h)) != odcisk:
                return False
            if not _k32.TerminateProcess(h, 1):
                return False
            _k32.WaitForSingleObject(h, 5000)
            return True
        finally:
            _k32.CloseHandle(h)
    if odcisk is not None and _odcisk(pid) != odcisk:
        return False
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except OSError:
        return False


# GenerateConsoleCtrlEvent działa tylko w obrębie konsoli wołającego, a usługa ma własną ukrytą konsolę
# (CREATE_NO_WINDOW). Pomocnik odłącza się od swojej, dołącza do konsoli usługi i wysyła Ctrl+Break jej grupie
# (PID lidera = PID usługi). Sam nie należy do tej grupy, więc zdarzenia nie dostaje.
_KOD_CTRL_BREAK = ("import ctypes,sys\n"
                   "k=ctypes.WinDLL('kernel32',use_last_error=True)\n"
                   "p=int(sys.argv[1])\n"
                   "k.FreeConsole()\n"
                   "if not k.AttachConsole(p):sys.exit(2)\n"
                   "k.SetConsoleCtrlHandler(None,1)\n"
                   "sys.exit(0 if k.GenerateConsoleCtrlEvent(1,p) else 3)\n")


def _lagodnie(pid: int) -> bool:
    """Prośba o zakończenie: POSIX SIGTERM do procesu, Windows CTRL_BREAK_EVENT do jego grupy procesów."""
    if not WINDOWS:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False
    try:
        wynik = subprocess.run([sys.executable, "-I", "-S", "-c", _KOD_CTRL_BREAK, str(pid)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=_CREATE_NO_WINDOW, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return wynik.returncode == 0


def _czy_launcher(usluga: Usluga) -> bool:
    if not WINDOWS:
        return False                      # na POSIX python venvu to sam interpreter, jego dzieci to pracownicy
    if usluga.launcher is not None:
        return bool(usluga.launcher)
    p = Path(usluga.argv[0]) if usluga.argv else Path()
    return (p.name.lower() in ("python.exe", "pythonw.exe") and p.parent.name.lower() == "scripts"
            and (p.parent.parent / "pyvenv.cfg").is_file())


# --- logi: dopisywanie i rotacja „kopiuj i przytnij” -------------------------------------------------------------

class _Dziennik:
    """Plik logu otwierany tylko do dopisywania. Usługa trzyma własny uchwyt, więc pliku nie przenosimy, tylko
    kopiujemy i przycinamy: dzięki trybowi dopisywania jej kolejne zapisy trafiają na nowy koniec pliku, bez dziury."""

    def __init__(self, sciezka: Path, maks: int, kopie: int):
        self.sciezka, self.maks, self.kopie = Path(sciezka), int(maks), int(kopie)
        self._blokada = threading.Lock()

    def otworz(self):
        """Nowy obiekt pliku (bez bufora) do stdout/stderr procesu albo własnych wpisów."""
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        if not WINDOWS:
            return os.fdopen(os.open(self.sciezka, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab", buffering=0)
        # FILE_APPEND_DATA bez FILE_WRITE_DATA: system dopisuje każdy zapis na końcu, także po przycięciu;
        # FILE_SHARE_READ | WRITE | DELETE: rotacja i podgląd logu działają, gdy usługa pisze (c2)
        h = _k32.CreateFileW(str(self.sciezka), 0x0004 | _SYNCHRONIZE, 0x7, None, 4, 0x80, None)   # OPEN_ALWAYS
        if not h or h == _NIEWAZNY:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            fd = msvcrt.open_osfhandle(h, os.O_APPEND)
        except OSError:
            _k32.CloseHandle(h)
            raise
        return os.fdopen(fd, "ab", buffering=0)

    def dopisz(self, tekst: str) -> None:
        try:
            with self.otworz() as f:
                f.write(tekst.encode("utf-8"))
        except OSError:
            pass

    def rotuj(self, wymus: bool = False) -> bool:
        """Gdy plik ma `maks` bajtów: .2 → .3, .1 → .2, kopia bieżącego → .1, bieżący przycięty do zera."""
        with self._blokada:
            try:
                if not wymus and self.sciezka.stat().st_size < self.maks:
                    return False
            except OSError:
                return False
            for i in range(self.kopie - 1, 0, -1):
                stara = self.sciezka.with_name(f"{self.sciezka.name}.{i}")
                if stara.exists():
                    os.replace(stara, self.sciezka.with_name(f"{self.sciezka.name}.{i + 1}"))
            if self.kopie > 0:
                shutil.copyfile(self.sciezka, self.sciezka.with_name(f"{self.sciezka.name}.1"))
            with open(self.sciezka, "r+b") as f:
                f.truncate(0)
            return True


# --- kanał sterowania ---------------------------------------------------------------------------------------------

def _skrot(sciezka: Path) -> str:
    """16 znaków sha256 znormalizowanej ścieżki (ten sam przepis co potok bramy w gateway/control_socket.py)."""
    norm = os.path.normcase(str(Path(sciezka).expanduser().resolve(strict=False)))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def adres_kanalu(u: Uklad) -> tuple[str, str]:
    """(adres, rodzina) kanału nadzorcy: potok na Windows, gniazdo uniksowe na POSIX."""
    skrot = _skrot(u.root)
    if WINDOWS:
        return rf"\\.\pipe\jarvo-nadzorca-{skrot}", "AF_PIPE"
    p = u.stan / "nadzorca.sock"
    if len(os.fsencode(str(p))) <= _MAKS_GNIAZDA:
        return str(p), "AF_UNIX"
    for baza in (tempfile.gettempdir(), "/tmp"):
        p = Path(baza) / f"jarvo-{os.getuid()}-{skrot}" / "nadzorca.sock"
        if len(os.fsencode(str(p))) <= _MAKS_GNIAZDA:
            break
    return str(p), "AF_UNIX"


def _przygotuj_gniazdo(sciezka: Path) -> None:
    """Katalog gniazda 0700, nasz i nie dowiązanie (krótka ścieżka bywa we wspólnym katalogu tymczasowym)."""
    katalog = sciezka.parent
    katalog.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = os.lstat(katalog)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise BladNadzorcy(f"Katalog gniazda nadzorcy {katalog} nie należy do bieżącego użytkownika.")
    os.chmod(katalog, 0o700)
    if os.path.lexists(sciezka):          # trzymamy blokadę korzenia, więc stare gniazdo jest martwe
        os.unlink(sciezka)


if WINDOWS:
    class _PotokWlasciciela(connection.PipeListener):
        """PipeListener z DACL tylko dla bieżącego użytkownika (D:P(A;;GA;;;<SID>)) i bez klientów zdalnych.
        Bez DACL (gdy system jej nie poda) dostęp chroni sam klucz authkey."""

        def __init__(self, adres: str):
            self._sd = None
            self._sa = None
            sid = _sid_uzytkownika()
            sd = wintypes.LPVOID()
            if sid and _adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    f"D:P(A;;GA;;;{sid})", 1, ctypes.byref(sd), None):
                self._sd = sd
                self._sa = _AtrybutyBezpieczenstwa(ctypes.sizeof(_AtrybutyBezpieczenstwa), sd.value, False)
            super().__init__(adres)

        def _new_handle(self, first=False):
            flagi = 0x00000003 | 0x40000000 | (0x00080000 if first else 0)   # DUPLEX, OVERLAPPED, FIRST_INSTANCE
            tryb = 0x4 | 0x2 | 0x8                                           # MESSAGE, READMODE_MESSAGE, REJECT_REMOTE
            h = _k32.CreateNamedPipeW(self._address, flagi, tryb, 255, connection.BUFSIZE, connection.BUFSIZE,
                                      0xFFFFFFFF, ctypes.byref(self._sa) if self._sa is not None else None)
            if not h or h == _NIEWAZNY:
                raise ctypes.WinError(ctypes.get_last_error())
            return h

        def zwolnij(self) -> None:
            if self._sd is not None:
                _k32.LocalFree(self._sd)
                self._sd = self._sa = None


class _Sluchacz:
    """Jak multiprocessing.connection.Listener, ale potok z DACL właściciela, a wymiana HMAC na kluczu (uwierzytelnij)
    poza accept(): klient, który połączy się i zamilknie, nie blokuje kolejnych."""

    def __init__(self, adres: str, rodzina: str, klucz: bytes):
        self._klucz = klucz
        if rodzina == "AF_PIPE":
            self._l = _PotokWlasciciela(adres)
            self.dacl = self._l._sa is not None
            return
        stara = os.umask(0o177)            # gniazdo nigdy nie jest dostępne dla innych, nawet przez chwilę
        try:
            self._l = connection.SocketListener(adres, "AF_UNIX", backlog=8)
        finally:
            os.umask(stara)
        os.chmod(adres, 0o600)
        self.dacl = True

    def accept(self):
        return self._l.accept()

    def uwierzytelnij(self, c) -> None:
        connection.deliver_challenge(c, self._klucz)
        connection.answer_challenge(c, self._klucz)

    def close(self) -> None:
        self._l.close()
        if WINDOWS:
            self._l.zwolnij()


class _Kanal:
    """Wątek kanału sterowania: jedno połączenie = jedno pytanie JSON i jedna odpowiedź."""

    def __init__(self, nadzorca: "Nadzorca"):
        self._n = nadzorca
        self.adres, self.rodzina = adres_kanalu(nadzorca.u)
        self.plik_klucza = nadzorca.u.stan / "nadzorca.klucz"
        self._klucz = b""
        self._sluchacz: _Sluchacz | None = None
        self._watek: threading.Thread | None = None
        self._koniec = threading.Event()

    def start(self) -> None:
        self._klucz = secrets.token_bytes(32)
        przenosne.zapisz_atomowo(self.plik_klucza, self._klucz, tryb=0o600)
        przenosne.chron(self.plik_klucza)
        if self.rodzina == "AF_UNIX":
            _przygotuj_gniazdo(Path(self.adres))
        self._sluchacz = _Sluchacz(self.adres, self.rodzina, self._klucz)
        if not self._sluchacz.dacl:
            self._n._log("kanał: potok bez własnej DACL (system nie podał SID-u), chroni go klucz")
        self._watek = threading.Thread(target=self._petla, name="nadzorca-kanal", daemon=True)
        self._watek.start()

    def _petla(self) -> None:
        while not self._koniec.is_set():
            try:
                polaczenie = self._sluchacz.accept()
            except Exception as e:           # kanał nie może paść: krótka przerwa i dalej
                if self._koniec.is_set():
                    break
                if not isinstance(e, (OSError, EOFError, ValueError)):
                    self._n._log(f"kanał: błąd ({type(e).__name__})")
                time.sleep(0.05)
                continue
            if self._koniec.is_set():
                polaczenie.close()
                break
            threading.Thread(target=self._obsluz_polaczenie, args=(polaczenie,), name="nadzorca-klient",
                             daemon=True).start()

    def _obsluz_polaczenie(self, polaczenie) -> None:
        with polaczenie:
            try:
                self._sluchacz.uwierzytelnij(polaczenie)
                zadanie = json.loads(polaczenie.recv_bytes(_MAKS_WIADOMOSCI).decode("utf-8"))
                odp = self._n._obsluz(zadanie) if isinstance(zadanie, dict) else \
                    {"ok": False, "blad": "Wiadomość musi być obiektem JSON."}
                polaczenie.send_bytes(json.dumps(odp, ensure_ascii=False).encode("utf-8"))
            except connection.AuthenticationError:
                if not self._koniec.is_set():
                    self._n._log("kanał: odrzucone połączenie bez właściwego klucza")
            except (OSError, EOFError, ValueError):
                pass

    def zamknij(self) -> None:
        self._koniec.set()
        if self._watek is not None and self._watek.is_alive():
            try:                                     # budzi accept() czekające na następnego klienta
                with connection.Client(self.adres, self.rodzina, authkey=self._klucz):
                    pass
            except (OSError, EOFError, connection.AuthenticationError):
                pass
            self._watek.join(5)
        if self._sluchacz is not None:
            try:
                self._sluchacz.close()
            except OSError:
                pass
        if self.rodzina == "AF_UNIX" and Path(self.adres).parent != self._n.u.stan:
            try:                                     # krótki katalog gniazda w katalogu tymczasowym
                Path(self.adres).parent.rmdir()
            except OSError:
                pass
        try:
            self.plik_klucza.unlink(missing_ok=True)
        except OSError:
            pass


class Klient:
    """Klient kanału nadzorcy (dla `jarvo status`, `restart`, `stop`, `update`)."""

    def __init__(self, u: Uklad, limit: float = 15.0):
        self.u, self.limit = u, limit
        self.adres, self.rodzina = adres_kanalu(u)

    def _klucz(self) -> bytes:
        try:
            return (self.u.stan / "nadzorca.klucz").read_bytes()
        except OSError:
            raise NadzorcaNieDziala(f"Nadzorca Jarva nie działa dla {self.u.root} (brak klucza kanału). "
                                    "Uruchom `jarvo serwis` albo `jarvo up`.") from None

    def _zapytaj(self, zadanie: dict) -> dict:
        klucz = self._klucz()
        try:
            with connection.Client(self.adres, self.rodzina, authkey=klucz) as c:
                c.send_bytes(json.dumps(zadanie).encode("utf-8"))
                if not c.poll(self.limit):
                    raise NadzorcaNieDziala(f"Nadzorca nie odpowiedział w {self.limit:g} s.")
                odp = json.loads(c.recv_bytes(_MAKS_WIADOMOSCI).decode("utf-8"))
        except connection.AuthenticationError:
            raise BladNadzorcy("Kanał nadzorcy odrzucił klucz (nadzorca właśnie startuje od nowa?). "
                               "Spróbuj jeszcze raz.") from None
        except (OSError, EOFError, ValueError) as e:
            raise NadzorcaNieDziala(f"Nadzorca Jarva nie działa albo dopiero startuje ({type(e).__name__}).") \
                from None
        if not isinstance(odp, dict) or not odp.get("ok"):
            raise BladNadzorcy(str((odp if isinstance(odp, dict) else {}).get("blad") or
                                   "Nadzorca odrzucił polecenie."))
        return odp

    def status(self) -> dict:
        """Bieżący stan: {"nadzorca": {...}, "uslugi": {nazwa: {"stan", "pid", "od", "restarty", ...}}}."""
        return self._zapytaj({"polecenie": "status"})["stan"]

    def restart(self, nazwa: str) -> dict:
        """Zleca restart usługi (łagodnie, potem twardo); wraca od razu, stan pokazuje status()."""
        return self._zapytaj({"polecenie": "restart", "nazwa": nazwa})

    def stop(self, czekaj: float = 0.0) -> dict:
        """Zatrzymuje nadzorcę i usługi; z `czekaj` czeka, aż proces nadzorcy się skończy."""
        odp = self._zapytaj({"polecenie": "stop"})
        if czekaj > 0:
            koniec = time.monotonic() + czekaj
            while _odcisk(odp.get("pid")) == odp.get("odcisk") and odp.get("odcisk"):
                if time.monotonic() >= koniec:
                    raise BladNadzorcy(f"Nadzorca nie zatrzymał się w {czekaj:g} s (pid {odp.get('pid')}).")
                time.sleep(0.1)
        return odp


def polacz(u: Uklad, limit: float = 15.0) -> Klient:
    """Klient kanału działającego nadzorcy; NadzorcaNieDziala, gdy nadzorcy nie ma."""
    k = Klient(u, limit)
    k._klucz()
    return k


def stan_z_pliku(u: Uklad) -> dict:
    """Ostatni zapisany stan (`<stan>/nadzorca.json`) i pole "dziala": czy proces nadzorcy jeszcze żyje. Pusty
    słownik, gdy nadzorca nigdy nie działał. Nie dotyka blokady, więc nie przeszkadza startującemu nadzorcy."""
    dane = srodowisko.wczytaj_json(u.stan / "nadzorca.json")
    if not dane:
        return {}
    n = dane.get("nadzorca") if isinstance(dane.get("nadzorca"), dict) else {}
    dane["dziala"] = bool(n.get("stan") != "zatrzymany" and n.get("odcisk")
                          and _odcisk(n.get("pid")) == n.get("odcisk"))
    return dane


# --- brama i panel Hermesa ----------------------------------------------------------------------------------------

def potok_bramy(dane: Path) -> str:
    """Potok sterujący bramy Hermesa dla HERMES_HOME (gateway/control_socket.py windows_pipe_name)."""
    return rf"\\.\pipe\hermes-gateway-{_skrot(dane)}"


def _gniazdo_bramy(dane: Path) -> Path | None:
    bezposrednie = Path(dane) / "gateway.sock"
    if bezposrednie.exists():
        return bezposrednie
    try:
        cel = (Path(dane) / "gateway.sock.path").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(cel) if cel and Path(cel).exists() else None


def _czytaj_linie(czytaj: Callable[[], bytes], koniec: float) -> bytes | None:
    kawalki: list[bytes] = []
    while time.monotonic() < koniec:
        k = czytaj()
        if not k:
            break
        kawalki.append(k)
        if b"\n" in k or sum(map(len, kawalki)) > _MAKS_WIADOMOSCI:
            break
    return b"".join(kawalki).partition(b"\n")[0] or None


def _pytanie_potok(nazwa: str, zadanie: bytes, limit: float) -> bytes | None:
    koniec = time.monotonic() + limit
    while True:
        try:
            f = open(nazwa, "r+b", buffering=0)
            break
        except FileNotFoundError:
            return None
        except OSError:                   # wszystkie instancje potoku zajęte: krótko czekamy
            if time.monotonic() >= koniec:
                return None
            time.sleep(0.05)
    with f:
        f.write(zadanie)
        return _czytaj_linie(lambda: f.read(65536), koniec)


def _pytanie_gniazdo(dane: Path, zadanie: bytes, limit: float) -> bytes | None:
    import socket
    sciezka = _gniazdo_bramy(dane)
    if sciezka is None:
        return None
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(limit)
        s.connect(str(sciezka))
        s.sendall(zadanie)
        return _czytaj_linie(lambda: s.recv(65536), time.monotonic() + limit)


def zapytaj_brame(dane: Path, polecenie: str = "identify", limit: float = 2.0) -> dict | None:
    """Jedno pytanie do kanału sterującego bramy (linia JSON tam i z powrotem); None, gdy brama nie odpowiada.
    Na Windows odczyt potoku nie ma limitu czasu, dlatego nadzorca pyta z osobnego wątku."""
    zadanie = json.dumps({"verb": polecenie, "id": 1, "protocol": 1}).encode("utf-8") + b"\n"
    try:
        surowe = _pytanie_potok(potok_bramy(dane), zadanie, limit) if WINDOWS else \
            _pytanie_gniazdo(dane, zadanie, limit)
        odp = json.loads(surowe.decode("utf-8")) if surowe else None
    except (OSError, ValueError):
        return None
    wynik = odp.get("result") if isinstance(odp, dict) and odp.get("ok") is True else None
    return wynik if isinstance(wynik, dict) else None


def brama_gotowa(dane: Path) -> bool:
    """Brama tego HERMES_HOME odpowiada na `identify` (to jest jej dowód życia, bez zgadywania po PID-ach)."""
    return zapytaj_brame(dane) is not None


_BEZ_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_gotowa(adres: str, limit: float = 2.0) -> bool:
    """GET `adres` (pętla zwrotna, bez proxy systemu) zwraca 200."""
    try:
        with _BEZ_PROXY.open(urllib.request.Request(adres, headers={"User-Agent": "jarvo-nadzorca/1"}),
                             timeout=limit) as odp:
            return odp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _bez_sekretow(tekst: str) -> str:
    return _SEKRETY.sub("…", tekst)


def _powod_bramy(dane: Path) -> str | None:
    """Powód zatrzymania zapisany przez bramę (gateway_state.json: exit_reason), bez tokenów."""
    powod = srodowisko.wczytaj_json(Path(dane) / "gateway_state.json").get("exit_reason")
    return _bez_sekretow(str(powod))[:300] if powod else None


def _znacznik_planowanego_stopu(python: Path, env: dict[str, str], pidy: list[int]) -> None:
    """Znacznik planowanego zatrzymania dla właściwego procesu bramy, pomocnikiem samego Hermesa: format znacznika
    (PID i czas startu procesu) zostaje po jego stronie i zmienia się razem z nim."""
    if not pidy:
        return
    subprocess.run([str(python), "-m", "gateway.systemd_stop_mark", str(pidy[0])], env=env,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                   creationflags=_CREATE_NO_WINDOW if WINDOWS else 0)


def _argv_hermesa(checkout: Path, *argumenty: str) -> list[str]:
    try:
        from .hermes import argv_hermesa
    except ImportError:                   # do czasu jarvo/hermes.py: python venvu Hermesa -m hermes_cli.main
        return [str(srodowisko.hermes_python(checkout)), "-m", "hermes_cli.main", *argumenty]
    return list(argv_hermesa(checkout, *argumenty))


def _port_panelu(env: dict[str, str]) -> int:
    tekst = str(env.get("JARVO_PANEL_PORT") or PORT_PANELU).strip()
    port = int(tekst) if tekst.isdigit() else 0
    if not 1 <= port <= 65535:
        raise BladNadzorcy(f"JARVO_PANEL_PORT={tekst!r}: potrzebny numer portu od 1 do 65535.")
    return port


def uslugi_jarva(u: Uklad, env: dict[str, str]) -> list[Usluga]:
    """Brama i panel Hermesa z bieżącej wersji (`<program>/current.json`), w środowisku procesów Jarva `env`."""
    biez = srodowisko.biezace(u)
    if not biez.get("hermes"):
        raise BladNadzorcy(f"Nie ma zainstalowanego Hermesa: {u.program / 'current.json'} nie wskazuje checkoutu. "
                           "Uruchom instalację Jarva (`jarvo instaluj`).")
    checkout = Path(biez["hermes"])
    python = srodowisko.hermes_python(checkout)
    if not python.is_file():
        raise BladNadzorcy(f"Brak Pythona Hermesa ({python}): instalacja jest niepełna. Uruchom `jarvo instaluj` "
                           "jeszcze raz.")
    port = _port_panelu(env)
    dane = Path(env.get("HERMES_HOME") or u.dane)
    katalog = dane if dane.is_dir() else checkout          # jak launcher Hermesa: stały katalog = HERMES_HOME
    env_bramy = {**env, "HERMES_GATEWAY_DETACHED": "1", "HERMES_SUPERVISED_CHILD": "1"}
    env_panelu = {**env, "HERMES_SUPERVISED_CHILD": "1"}
    web = biez.get("web_dist")
    if web and (Path(web) / "index.html").is_file():
        env_panelu["HERMES_WEB_DIST"] = str(web)
    brama = Usluga("brama", _argv_hermesa(checkout, "gateway", "run", "--external-supervisor"), cwd=katalog,
                   env=env_bramy, gotowa=partial(brama_gotowa, dane), kolejnosc=0,
                   przed_stopem=partial(_znacznik_planowanego_stopu, python, env_bramy),
                   powod_postoju=partial(_powod_bramy, dane))
    panel = Usluga("panel", _argv_hermesa(checkout, "dashboard", "--host", "127.0.0.1", "--port", str(port),
                                          "--no-open", "--skip-build"),
                   cwd=katalog, env=env_panelu, gotowa=partial(http_gotowa, f"http://127.0.0.1:{port}/api/status"),
                   kolejnosc=1)
    return [brama, panel]


# --- nadzorca -----------------------------------------------------------------------------------------------------

def _iso(t: float | None) -> str | None:
    return None if t is None else datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def _kod_tekst(kod: int) -> str:
    if kod < 0:
        return f"{kod} (sygnał {-kod})"
    return f"{kod} (0x{kod:08X})" if kod > 0xFFFF else str(kod)


class _Stan:
    """Stan jednej usługi w pętli nadzorcy."""

    def __init__(self, usluga: Usluga, dziennik: _Dziennik):
        self.u, self.dziennik = usluga, dziennik
        self.stan = "czeka"           # czeka, dziala, zatrzymywanie, ponowienie, postoj, zatrzymana
        self.proces: subprocess.Popen | None = None
        self.pid: int | None = None
        self.odcisk: str | None = None
        self.pidy: list[int] = []
        self.launcher = False
        self.od: float | None = None
        self.start_mono = 0.0
        self.generacja = 0
        self.restarty = 0
        self.bledy = 0
        self.ostatni_kod: int | None = None
        self.gotowa: bool | None = None
        self.gotowa_od: float | None = None
        self.powod: str | None = None
        self.nastepny = 0.0
        self.nastepny_wall: float | None = None
        self.termin = 0.0
        self.po_zatrzymaniu = "stop"
        self.zabity = False
        self.sonda: threading.Thread | None = None
        self.wynik_sondy: tuple[int, bool] | None = None
        self.ostatnia_sonda = 0.0
        self.szukaj_dzieci = 0.0
        self.czekanie_zgloszone = False


class Nadzorca:
    """Pętla nadzoru usług jednego korzenia Jarva. uruchom() blokuje do zatrzymaj() (albo polecenia stop z kanału).
    Czasy (sekundy) skracają testy; domyślne są z planu (c2)."""

    def __init__(self, u: Uklad, uslugi: list[Usluga], env: dict[str, str] | None = None, *,
                 przerwa_restartu: float = 5.0, przerwa_min: float = 5.0, przerwa_max: float = 300.0,
                 reset_po: float = 600.0, limit_stopu: float = 30.0, limit_kolejnosci: float = 60.0,
                 co_ile_gotowosc: float = 1.0, co_ile_zycie: float = 30.0, co_ile_rotacja: float = 5.0,
                 takt: float = 0.25, log_max: int = 10 * 2 ** 20, log_kopie: int = 3, kanal: bool = True,
                 log: Callable[[str], None] | None = None):
        nazwy = [x.nazwa for x in uslugi]
        if len(set(nazwy)) != len(nazwy):
            raise ValueError("nazwy usług muszą być różne")
        for nazwa in nazwy:
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", nazwa):    # nazwa trafia do nazwy pliku logu
                raise ValueError(f"zła nazwa usługi {nazwa!r}: małe litery, cyfry, - i _")
        self.u = u
        self.env = dict(os.environ if env is None else env)
        self.przerwa_restartu, self.przerwa_min, self.przerwa_max = przerwa_restartu, przerwa_min, przerwa_max
        self.reset_po, self.limit_stopu, self.limit_kolejnosci = reset_po, limit_stopu, limit_kolejnosci
        self.co_ile_gotowosc, self.co_ile_zycie, self.co_ile_rotacja = co_ile_gotowosc, co_ile_zycie, co_ile_rotacja
        self.takt = takt
        self._stany = {x.nazwa: _Stan(x, _Dziennik(u.logi / f"{x.nazwa}.log", log_max, log_kopie))
                       for x in sorted(uslugi, key=lambda x: x.kolejnosc)}
        self._dziennik = _Dziennik(u.logi / "nadzorca.log", log_max, log_kopie)
        self._plik_logu = None
        self._blokada_logu = threading.Lock()
        self._log_zewn = log
        self._z_kanalem = kanal
        self._kanal: _Kanal | None = None
        self._plik_stanu = u.stan / "nadzorca.json"
        self._stop = threading.Event()
        self._budzik = threading.Event()
        self._polecenia: queue.Queue = queue.Queue()
        self._blokada = threading.Lock()
        self._migawka: dict = {}
        self._brudny = True
        self._breakaway = True
        self._calosc = False                 # zatrzymujemy wszystko
        self._koniec_calosci = 0.0
        self._od: float | None = None
        self._odcisk_wlasny: str | None = None

    # --- sterowanie z zewnątrz (wątki, sygnały, kanał) ---

    def zatrzymaj(self) -> None:
        """Zatrzymanie łagodne: usługi w odwrotnej kolejności, potem koniec uruchom(). Bezpieczne z innego wątku."""
        self._stop.set()
        self._budzik.set()

    def restart(self, nazwa: str) -> None:
        if nazwa not in self._stany:
            raise BladNadzorcy(f"Nie ma usługi {nazwa!r}; są: {', '.join(self._stany)}.")
        self._polecenia.put(("restart", nazwa))
        self._budzik.set()

    def stan(self) -> dict:
        """Ostatnia migawka stanu (ta sama, co w pliku i w kanale)."""
        with self._blokada:
            return json.loads(json.dumps(self._migawka))

    def _obsluz(self, zadanie: dict) -> dict:
        polecenie = zadanie.get("polecenie")
        if polecenie == "status":
            with self._blokada:
                return {"ok": True, "stan": self._migawka}
        if polecenie == "restart":
            nazwa = zadanie.get("nazwa")
            if self._stop.is_set():
                return {"ok": False, "blad": "Nadzorca właśnie się zatrzymuje."}
            try:
                self.restart(str(nazwa))
            except BladNadzorcy as e:
                return {"ok": False, "blad": str(e)}
            return {"ok": True, "nazwa": nazwa}
        if polecenie == "stop":
            self.zatrzymaj()
            return {"ok": True, "pid": os.getpid(), "odcisk": self._odcisk_wlasny}
        return {"ok": False, "blad": f"Nieznane polecenie {polecenie!r} (są: status, restart, stop)."}

    # --- główna pętla ---

    def uruchom(self) -> None:
        zamek = przenosne.Zamek(self.u.stan / "nadzorca.lock", czekaj=False)
        try:
            zamek.__enter__()
        except BlockingIOError:
            raise NadzorcaJuzDziala(_komunikat_juz_dziala(self.u)) from None
        try:
            self._przygotuj()
            self._log(f"nadzorca: start (pid {os.getpid()}), usługi: {', '.join(self._stany)}")
            self._posprzataj_po_poprzednim()
            if self._z_kanalem:
                self._kanal = _Kanal(self)
            self._zapisz_stan()                       # klient kanału od początku dostaje pełny stan
            if self._kanal is not None:
                self._kanal.start()
            self._petla()
        finally:
            try:
                self._sprzatnij_awaryjnie()
                if self._kanal is not None:
                    self._kanal.zamknij()
                self._zapisz_stan(koniec=True)
                self._log("nadzorca: koniec")
                with self._blokada_logu:
                    if self._plik_logu is not None:
                        self._plik_logu.close()
                        self._plik_logu = None
            finally:
                zamek.__exit__(None, None, None)

    def _przygotuj(self) -> None:
        self.u.stan.mkdir(parents=True, exist_ok=True)
        self.u.logi.mkdir(parents=True, exist_ok=True)
        przenosne.chron(self.u.stan)          # klucz kanału, gniazdo i blokady bramy: tylko właściciel
        if not WINDOWS:
            przenosne.chron(self.u.logi)
        self._dziennik.rotuj()
        self._plik_logu = self._dziennik.otworz()
        self._od, self._odcisk_wlasny = time.time(), _odcisk(os.getpid())

    def _petla(self) -> None:
        ostatnia_rotacja = ostatni_zapis = time.monotonic()
        while True:
            teraz = time.monotonic()
            if self._calosc and teraz > self._koniec_calosci:
                return                        # bezpiecznik: resztę zabije _sprzatnij_awaryjnie
            try:
                if self._stop.is_set() and not self._calosc:
                    self._zatrzymaj_wszystko()
                self._obsluz_polecenia()
                for s in self._stany.values():
                    self._krok(s, teraz)
                if teraz - ostatnia_rotacja >= self.co_ile_rotacja:
                    ostatnia_rotacja = teraz
                    self._rotuj_logi()
                if self._brudny or teraz - ostatni_zapis >= 30:
                    ostatni_zapis = teraz
                    self._zapisz_stan()
                if self._calosc and (not any(s.stan in ("dziala", "zatrzymywanie") for s in self._stany.values())
                                     or teraz > self._koniec_calosci):
                    return
                self._budzik.wait(self.takt)
                self._budzik.clear()
            except KeyboardInterrupt:         # uruchom() bez main(): Ctrl+C = łagodne zatrzymanie
                self.zatrzymaj()
            except Exception as e:            # jeden błąd nie może zostawić usług bez nadzoru
                self._log(f"nadzorca: błąd pętli: {type(e).__name__}: {str(e)[:200]}")
                time.sleep(min(self.takt * 4, 1.0))

    def _obsluz_polecenia(self) -> None:
        while True:
            try:
                rodzaj, nazwa = self._polecenia.get_nowait()
            except queue.Empty:
                return
            if rodzaj == "restart" and not self._calosc:
                self._log(f"{nazwa}: restart na polecenie")
                self._zatrzymaj_usluge(self._stany[nazwa], "restart")

    def _krok(self, s: _Stan, teraz: float) -> None:
        if s.stan == "czeka":
            if not self._calosc and self._kolej_na(s, teraz):
                self._start(s)
        elif s.stan == "dziala":
            kod = s.proces.poll()
            if kod is not None:
                self._po_wyjsciu(s, kod)
                return
            self._szukaj_dzieci(s, teraz)
            self._sonda(s, teraz)
        elif s.stan == "zatrzymywanie":
            kod = s.proces.poll()
            if kod is not None:
                self._po_zatrzymaniu(s, kod)
            elif teraz >= s.termin and not s.zabity:
                self._zabij(s)
        elif s.stan == "ponowienie" and not self._calosc and teraz >= s.nastepny:
            self._start(s)

    def _kolej_na(self, s: _Stan, teraz: float) -> bool:
        """Czy wcześniejsze usługi już ruszyły: działają i są gotowe, stoją albo czekamy na nie za długo."""
        for inna in self._stany.values():
            if inna.u.kolejnosc >= s.u.kolejnosc:
                continue
            if inna.stan == "czeka":
                return False
            if inna.stan == "dziala" and inna.gotowa is False:
                if teraz - inna.start_mono < self.limit_kolejnosci:
                    return False
                if not s.czekanie_zgloszone:
                    s.czekanie_zgloszone = True
                    self._log(f"{s.u.nazwa}: {inna.u.nazwa} nie zgłosiła gotowości w {self.limit_kolejnosci:g} s, "
                              "startuję mimo to")
        return True

    # --- start, wyjście, zatrzymanie ---

    def _popen(self, s: _Stan, env: dict[str, str], plik) -> subprocess.Popen:
        kw = dict(cwd=str(s.u.cwd) if s.u.cwd else None, env=env, stdin=subprocess.DEVNULL, stdout=plik,
                  stderr=subprocess.STDOUT, close_fds=True)
        if not WINDOWS:
            return subprocess.Popen(s.u.argv, start_new_session=True, **kw)    # Ctrl+C w terminalu ich nie dotyka
        flagi = _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP
        if self._breakaway:
            try:
                return subprocess.Popen(s.u.argv, creationflags=flagi | _CREATE_BREAKAWAY_FROM_JOB, **kw)
            except PermissionError:
                self._breakaway = False
                self._log("nadzorca: job rodzica nie pozwala na CREATE_BREAKAWAY_FROM_JOB, startuję bez tej flagi")
        return subprocess.Popen(s.u.argv, creationflags=flagi, **kw)

    def _start(self, s: _Stan) -> None:
        env = dict(self.env if s.u.env is None else s.u.env)
        s.generacja += 1
        if s.generacja > 1:
            s.restarty += 1
        s.gotowa = None if s.u.gotowa is None else False
        s.gotowa_od, s.wynik_sondy, s.zabity, s.pidy = None, None, False, []
        try:
            s.dziennik.rotuj()
        except OSError:
            pass                          # spróbujemy przy następnej rotacji; start ważniejszy
        try:
            plik = s.dziennik.otworz()
        except OSError as e:
            self._nieudany_start(s, f"nie otworzę logu {s.dziennik.sciezka}: {e.strerror or e}")
            return
        try:
            plik.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} nadzorca: start {s.u.nazwa} ===\n".encode("utf-8"))
            s.proces = self._popen(s, env, plik)
        except (OSError, ValueError) as e:
            self._nieudany_start(s, f"nie uruchomiłem {Path(s.u.argv[0]).name if s.u.argv else '?'}: "
                                    f"{getattr(e, 'strerror', None) or e}")
            return
        finally:
            plik.close()
        s.pid = s.proces.pid
        s.odcisk = _odcisk(s.pid)
        s.launcher = _czy_launcher(s.u)
        s.pidy = [] if s.launcher else [s.pid]
        s.od, s.start_mono = time.time(), time.monotonic()
        s.ostatnia_sonda = s.szukaj_dzieci = s.start_mono
        s.stan, s.powod, s.nastepny_wall = "dziala", None, None
        self._log(f"{s.u.nazwa}: start (pid {s.pid})" + (f", restart nr {s.restarty}" if s.restarty else ""))
        self._brudny = True

    def _przerwa(self, bledy: int) -> float:
        return min(self.przerwa_min * 2 ** min(max(bledy - 1, 0), 30), self.przerwa_max)

    def _ponow(self, s: _Stan, przerwa: float) -> None:
        s.stan, s.nastepny = "ponowienie", time.monotonic() + przerwa
        s.nastepny_wall = time.time() + przerwa

    def _nieudany_start(self, s: _Stan, powod: str) -> None:
        s.proces, s.bledy = None, s.bledy + 1
        przerwa = self._przerwa(s.bledy)
        self._ponow(s, przerwa)
        s.powod = f"{powod}; ponowienie za {przerwa:g} s"
        self._log(f"{s.u.nazwa}: {s.powod}")
        self._brudny = True

    def _po_wyjsciu(self, s: _Stan, kod: int) -> None:
        czas = time.monotonic() - s.start_mono
        s.ostatni_kod, s.proces = kod, None
        s.gotowa = None if s.u.gotowa is None else False
        s.dziennik.dopisz(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} nadzorca: {s.u.nazwa} zakończony kodem "
                          f"{_kod_tekst(kod)} po {czas:.0f} s ===\n")
        if kod == KOD_RESTART:
            self._ponow(s, self.przerwa_restartu)
            s.powod = f"kod 75: usługa poprosiła o restart (za {self.przerwa_restartu:g} s)"
        elif kod == KOD_POSTOJ:
            s.stan, s.nastepny_wall = "postoj", None
            try:
                dodatek = s.u.powod_postoju() if s.u.powod_postoju else None
            except Exception:
                dodatek = None
            dodatek = _bez_sekretow(str(dodatek))[:300] if dodatek else None
            s.powod = ("kod 78: błąd konfiguracji" + (f" ({dodatek})" if dodatek else "") +
                       f"; po poprawce: `jarvo serwis --restart {s.u.nazwa}`")
        else:
            if czas >= self.reset_po:
                s.bledy = 0
            s.bledy += 1
            przerwa = self._przerwa(s.bledy)
            self._ponow(s, przerwa)
            s.powod = f"kod {_kod_tekst(kod)} po {czas:.0f} s działania; ponowienie za {przerwa:g} s"
        self._log(f"{s.u.nazwa}: {s.powod}")
        self._brudny = True

    def _pidy_wlasciwe(self, s: _Stan) -> list[int]:
        if s.launcher:
            d = [p for p, _ in dzieci(s.pid)]
            if d:
                return d
        return [s.pid]

    def _zatrzymaj_usluge(self, s: _Stan, po: str = "stop") -> None:
        """Łagodnie (przed_stopem, potem Ctrl+Break albo SIGTERM), twardo po `limit_stopu`; `po`: stop albo restart."""
        if s.stan == "zatrzymywanie":
            s.po_zatrzymaniu = po
            return
        if s.stan != "dziala":
            if po == "restart":
                s.bledy = 0
                self._start(s)
            elif s.stan in ("czeka", "ponowienie"):
                s.stan, s.powod, s.nastepny_wall = "zatrzymana", None, None
                self._brudny = True
            return
        s.stan, s.po_zatrzymaniu = "zatrzymywanie", po
        s.termin = time.monotonic() + self.limit_stopu
        self._log(f"{s.u.nazwa}: zatrzymuję (pid {s.pid})")
        if s.u.przed_stopem is not None:
            try:
                s.u.przed_stopem(self._pidy_wlasciwe(s))
            except Exception as e:
                self._log(f"{s.u.nazwa}: przygotowanie zatrzymania nie wyszło ({type(e).__name__})")
        _lagodnie(s.pid)
        self._brudny = True

    def _zabij(self, s: _Stan) -> None:
        """Launcher i jego bezpośrednie dzieci, nigdy wnuki (pracownicy kanbana kończą swoje karty)."""
        s.zabity = True
        zabite = []
        if s.launcher:
            for pid, odcisk in dzieci(s.pid):
                if _zabij_pid(pid, odcisk):
                    zabite.append(pid)
        try:
            s.proces.kill()
        except OSError:
            pass
        self._log(f"{s.u.nazwa}: nie skończył się w {self.limit_stopu:g} s, zabity pid {s.pid}"
                  + (f" i dzieci {', '.join(map(str, zabite))}" if zabite else ""))

    def _po_zatrzymaniu(self, s: _Stan, kod: int) -> None:
        s.ostatni_kod, s.proces = kod, None
        s.gotowa = None if s.u.gotowa is None else False
        s.dziennik.dopisz(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} nadzorca: {s.u.nazwa} zatrzymany "
                          f"(kod {_kod_tekst(kod)}) ===\n")
        self._log(f"{s.u.nazwa}: zatrzymany (kod {_kod_tekst(kod)})")
        if s.po_zatrzymaniu == "restart" and not self._calosc:
            s.bledy = 0
            self._start(s)
        else:
            s.stan, s.powod, s.nastepny_wall = "zatrzymana", None, None
        self._brudny = True

    def _zatrzymaj_wszystko(self) -> None:
        self._calosc = True
        self._koniec_calosci = time.monotonic() + self.limit_stopu + 10
        self._log("nadzorca: zatrzymuję usługi")
        for s in reversed(list(self._stany.values())):
            self._zatrzymaj_usluge(s, "stop")
        self._brudny = True

    def _sprzatnij_awaryjnie(self) -> None:
        """Po błędzie albo przekroczeniu czasu: nic, co uruchomiliśmy, nie zostaje bez nadzoru."""
        for s in self._stany.values():
            if s.proces is not None and s.proces.poll() is None:
                self._zabij(s)
                try:
                    s.proces.wait(10)
                except subprocess.TimeoutExpired:
                    pass
            if s.proces is not None and s.proces.poll() is not None:
                s.ostatni_kod, s.proces = s.proces.returncode, None
                s.stan = "zatrzymana"

    # --- gotowość, dzieci, logi, stan ---

    def _szukaj_dzieci(self, s: _Stan, teraz: float) -> None:
        if s.launcher and not s.pidy and teraz >= s.szukaj_dzieci:
            s.szukaj_dzieci = teraz + 0.5
            d = [p for p, _ in dzieci(s.pid)]
            if d:
                s.pidy = d
                self._brudny = True

    def _sonda(self, s: _Stan, teraz: float) -> None:
        """Sprawdzanie gotowości w osobnym wątku (odczyt potoku na Windows nie ma limitu czasu)."""
        if s.u.gotowa is None:
            return
        if s.sonda is not None:
            if s.sonda.is_alive():
                return
            s.sonda = None
            wynik, s.wynik_sondy = s.wynik_sondy, None
            if wynik is not None and wynik[0] == s.generacja:
                if wynik[1] and not s.gotowa:
                    s.gotowa, s.gotowa_od = True, time.time()
                    self._log(f"{s.u.nazwa}: gotowa po {teraz - s.start_mono:.1f} s")
                    self._brudny = True
                elif not wynik[1] and s.gotowa:
                    s.gotowa, s.gotowa_od = False, None
                    self._log(f"{s.u.nazwa}: przestała odpowiadać")
                    self._brudny = True
        if teraz - s.ostatnia_sonda < (self.co_ile_zycie if s.gotowa else self.co_ile_gotowosc):
            return
        s.ostatnia_sonda = teraz
        generacja, sprawdz = s.generacja, s.u.gotowa

        def praca() -> None:
            try:
                ok = bool(sprawdz())
            except Exception:
                ok = False
            s.wynik_sondy = (generacja, ok)
            self._budzik.set()

        s.sonda = threading.Thread(target=praca, name=f"sonda-{s.u.nazwa}", daemon=True)
        s.sonda.start()

    def _rotuj_logi(self) -> None:
        for d in [self._dziennik, *(s.dziennik for s in self._stany.values())]:
            try:
                d.rotuj()
            except OSError as e:
                self._log(f"nadzorca: rotacja {d.sciezka.name} nie wyszła ({e.strerror or e})")

    def _log(self, tekst: str) -> None:
        linia = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {tekst}"
        with self._blokada_logu:
            if self._plik_logu is not None:
                try:
                    self._plik_logu.write((linia + "\n").encode("utf-8"))
                except OSError:
                    pass
        if self._log_zewn is not None:
            try:
                self._log_zewn(linia)
            except Exception:
                pass

    def _opis(self, s: _Stan) -> dict:
        zyje = s.proces is not None
        return {"stan": s.stan, "pid": s.pid if zyje else None, "pidy": list(s.pidy) if zyje else [],
                "odcisk": s.odcisk if zyje else None, "launcher": s.launcher, "od": _iso(s.od) if zyje else None,
                "restarty": s.restarty, "bledy_z_rzedu": s.bledy, "ostatni_kod": s.ostatni_kod,
                "gotowa": s.gotowa, "gotowa_od": _iso(s.gotowa_od), "powod": s.powod,
                "nastepny_start": _iso(s.nastepny_wall) if s.stan == "ponowienie" else None,
                "kolejnosc": s.u.kolejnosc, "log": str(s.dziennik.sciezka)}

    def _zapisz_stan(self, koniec: bool = False) -> None:
        dane = {"wersja": WERSJA_STANU,
                "nadzorca": {"pid": os.getpid(), "odcisk": self._odcisk_wlasny, "od": _iso(self._od),
                             "stan": "zatrzymany" if koniec else ("zatrzymuje" if self._calosc else "dziala"),
                             "korzen": str(self.u.root), "kanal": self._kanal.adres if self._kanal else None},
                "uslugi": {nazwa: self._opis(s) for nazwa, s in self._stany.items()},
                "zapisano": _iso(time.time())}
        with self._blokada:
            self._migawka = dane
        self._brudny = False
        try:
            przenosne.zapisz_atomowo(self._plik_stanu, json.dumps(dane, ensure_ascii=False, indent=2) + "\n")
        except OSError as e:
            self._log(f"nadzorca: nie zapisałem stanu ({e.strerror or e})")

    def _posprzataj_po_poprzednim(self) -> None:
        """Procesy usług, które przeżyły poprzedniego nadzorcę (ten sam PID i czas startu co w stanie)."""
        stary = srodowisko.wczytaj_json(self._plik_stanu).get("uslugi")
        for nazwa, wpis in (stary.items() if isinstance(stary, dict) else []):
            if not isinstance(wpis, dict):
                continue
            pid, odcisk = wpis.get("pid"), wpis.get("odcisk")
            if not isinstance(pid, int) or not isinstance(odcisk, str) or _odcisk(pid) != odcisk:
                continue
            launcher = bool(wpis.get("launcher")) and WINDOWS
            self._log(f"{nazwa}: proces {pid} po poprzednim nadzorcy dalej działa, zatrzymuję go")
            s = self._stany.get(nazwa)
            if s is not None and s.u.przed_stopem is not None:
                try:
                    s.u.przed_stopem([p for p, _ in dzieci(pid)] if launcher else [pid])
                except Exception:
                    pass
            _lagodnie(pid)
            koniec = time.monotonic() + self.limit_stopu
            while _odcisk(pid) == odcisk and time.monotonic() < koniec:
                time.sleep(min(self.takt, 0.2))
            if _odcisk(pid) == odcisk:
                if launcher:
                    for d, o in dzieci(pid):
                        _zabij_pid(d, o)
                _zabij_pid(pid, odcisk)
                self._log(f"{nazwa}: proces {pid} nie skończył się w {self.limit_stopu:g} s, zabity")


def _komunikat_juz_dziala(u: Uklad) -> str:
    n = srodowisko.wczytaj_json(u.stan / "nadzorca.json").get("nadzorca")
    pid = n.get("pid") if isinstance(n, dict) else None
    return (f"Nadzorca Jarva już działa dla {u.root}" + (f" (pid {pid})" if pid else "") +
            ". Stan: `jarvo serwis --status`, zatrzymanie: `jarvo serwis --stop`.")


def _zajety(u: Uklad) -> bool:
    try:
        with przenosne.Zamek(u.stan / "nadzorca.lock", czekaj=False):
            return False
    except BlockingIOError:
        return True


def _wypisz(tekst: str, blad: bool = False) -> None:
    strumien = sys.stderr if blad else sys.stdout
    if strumien is None:                  # pythonw.exe z autostartu nie ma konsoli
        return
    try:
        print(tekst, file=strumien, flush=True)
    except UnicodeEncodeError:
        print(tekst.encode("ascii", "replace").decode("ascii"), file=strumien, flush=True)
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    """`jarvo serwis`: nadzorca na pierwszym planie (autostart uruchamia właśnie to). Ctrl+C albo SIGTERM
    zatrzymuje usługi łagodnie. --status, --restart i --stop rozmawiają z działającym nadzorcą przez kanał."""
    parser = argparse.ArgumentParser(prog="jarvo serwis", description="Nadzorca procesów Jarva: brama i panel "
                                     "Hermesa, restart po awarii, logi i stan dla `jarvo status`.")
    grupa = parser.add_mutually_exclusive_group()
    grupa.add_argument("--status", action="store_true", help="stan działającego nadzorcy (JSON)")
    grupa.add_argument("--restart", metavar="USLUGA", help="uruchom usługę ponownie (brama, panel)")
    grupa.add_argument("--stop", action="store_true", help="zatrzymaj nadzorcę i jego usługi")
    args = parser.parse_args(argv)
    try:
        u = uklad()
    except BladUkladu as e:
        _wypisz(str(e), blad=True)
        return 1
    if args.status or args.restart or args.stop:
        try:
            klient = polacz(u)
            if args.status:
                _wypisz(json.dumps(klient.status(), ensure_ascii=False, indent=2))
            elif args.restart:
                klient.restart(args.restart)
                _wypisz(f"{args.restart}: restart zlecony.")
            else:
                klient.stop(czekaj=120)
                _wypisz("Nadzorca Jarva zatrzymany.")
        except BladNadzorcy as e:
            _wypisz(str(e), blad=True)
            return 1
        return 0
    if _zajety(u):                        # zanim cokolwiek zbudujemy: drugi start = komunikat i kod 1
        _wypisz(_komunikat_juz_dziala(u), blad=True)
        return 1
    try:
        env = srodowisko.srodowisko(u)
        nadzorca = Nadzorca(u, uslugi_jarva(u, env), env, log=_wypisz)
    except BladNadzorcy as e:
        _wypisz(str(e), blad=True)
        return 1
    poprzednie = {}
    for nazwa in ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP"):
        numer = getattr(signal, nazwa, None)
        if numer is not None:
            try:
                poprzednie[numer] = signal.signal(numer, lambda *_: nadzorca.zatrzymaj())
            except (OSError, ValueError):     # nie w głównym wątku
                pass
    try:
        nadzorca.uruchom()
    except BladNadzorcy as e:             # także NadzorcaJuzDziala (wyścig dwóch startów)
        _wypisz(str(e), blad=True)
        return 1
    except OSError as e:                # np. ACL katalogu stanu albo kanał: komunikat zamiast śladu stosu
        _wypisz(f"Nadzorca Jarva nie wystartował: {e}", blad=True)
        return 1
    finally:
        for numer, obsluga in poprzednie.items():
            try:
                signal.signal(numer, obsluga)
            except (OSError, ValueError, TypeError):
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

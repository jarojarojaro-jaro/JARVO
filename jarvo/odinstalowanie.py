"""Odinstalowanie Jarva natywnie: `jarvo uninstall [--all] [--yes] [--json]` (docs/NATYWNIE.md: N11, c4
„jarvo uninstall”, D08, T08, etap E13), a do tego narzędzia wspólne z aktualizacją (jarvo/aktualizacja.py): lista
procesów z pełną ścieżką programu i wierszem polecenia (Windows: ctypes, Linux: /proc, macOS: ps), procesy, które
korzystają z katalogu, usuwanie drzew mimo plików tylko do odczytu, dowiązań i zablokowanych plików, skan śladów.

Kolejność (c4):
  1. sprawdzenie korzenia: to ma być instalacja Jarva (`<program>/current.json` albo pliki w `<stan>`) w osobnym
     katalogu (nie katalog główny dysku, nie katalog domowy ani nad nim); zgoda (bez --yes i bez terminala: odmowa),
     przy --all drugie pytanie o dane (--yes odpowiada „tak” na oba),
  2. stop: znacznik zatrzymania (zapasowe wyzwalacze autostartu nie podniosą serwisu w trakcie), nadzorca kanałem
     (brama kończy tury), potem każdy proces z programem w korzeniu i jego potomkowie (pracownicy kanbana, rozmowy,
     przeglądarki, polecenia terminala agentów), oprócz tego procesu i jego przodków (cmd.exe z jarvo.cmd, terminal);
     procesu, który ma korzeń tylko w wierszu polecenia (np. edytor z otwartym katalogiem), nie zamykamy: raport,
  3. autostart off (jarvo/autostart.wylacz: zadanie Harmonogramu, LaunchAgent, jednostka systemd --user, wpis HKCU
     Run), K6 (reset TCC dla CuaDriver.app) dojdzie z ekranem właściciela,
  4. cofnięcie dziennika zmian hosta od końca (jarvo/zmiany_hosta.cofnij): PATH użytkownika, blok w pliku startowym
     powłoki, ~/.local/bin/jarvo, autostart i linger, tylko tam, gdzie dalej jest nasza wartość. Wpis pliku z korzenia
     (jarvo.cmd, `<root>/bin/jarvo`) zapominamy, a plik znika razem z korzeniem: cmd.exe czyta jarvo.cmd jeszcze po
     końcu tego polecenia (usunięty wcześniej daje „The batch file cannot be found.” i kod 1, sprawdzone na Windows 11).
     Wpis, którego nie dało się cofnąć: pytanie (z --yes dalej), opis w raporcie i kod 1,
  5. wpis w „Aplikacje” (HKCU\\...\\Uninstall\\Jarvo), gdy wskazuje ten korzeń (dziś instalator go nie zakłada),
  6. klucz GitHuba `jarvo-github` w magazynie systemu (N15: Menedżer poświadczeń, pęk kluczy, libsecret; czyta go
     `jarvo update`): z --all usunięty, chyba że na tym koncie jest inna instalacja Jarva (domyślny korzeń, gdy to
     nie on, albo stara z WSL czy Dockerem), bo klucz jest wspólny dla wszystkich; wtedy i bez --all zostaje celowo,
  7. usunięcie `<program>`, `<stan>`, `<root>/bin`, build, cache i logów (Linux: katalogi XDG Jarva), `<dane>` tylko
     z --all; obce pliki w korzeniu zostają. Na Windows plików .exe i .dll Pythona tego polecenia nie da się usunąć
     do jego końca, a jarvo.cmd czyta jeszcze cmd.exe: oba usuwa proces sprzątający (PowerShell z System32, bez plików
     tymczasowych, korzeń jawnie w wierszu polecenia), który czeka na koniec tego procesu, usuwa resztę i pusty
     korzeń. Czego nie usunie przez minutę (plik trzyma inny program), to przenosi zmianą nazwy do %TEMP% (działa też
     dla uruchomionego .exe na tym samym dysku) i zapisuje w HKCU RunOnce (rmdir przy następnym logowaniu). Gdy
     przeniesienie się nie uda (korzeń na innym dysku niż %TEMP%, katalog bieżący innego programu), wpis RunOnce ma
     warunek: usuwa ścieżkę tylko wtedy, gdy w korzeniu nie ma nowej instalacji (`<program>\\current.json`), więc
     ponowna instalacja w tym samym korzeniu przed wylogowaniem zostaje nietknięta,
  8. skan śladów (katalogi, polecenie jarvo, PATH użytkownika, blok w pliku startowym, autostart, wpis „Aplikacje”,
     klucz GitHuba, procesy, wpisy dziennika z błędem) i raport: co zostaje celowo (dane bez --all, Python tego
     polecenia do chwili jego końca, stara instalacja z WSL albo Dockerem do migracji E12, obce pliki w korzeniu,
     wspólny klucz GitHuba), a co jest śladem do usunięcia ręcznie (wtedy kod 1). Stara instalacja: tylko informacja,
     sprzątanie osobnym pytaniem w migracji (f).

Pytania idą na stderr (przy --json stdout ma sam raport JSON). Wszystko, co dotyka komputera poza plikami (procesy,
pytania, polecenia systemu, rejestr, magazyn kluczy, proces w tle), idzie przez `Zaplecze` i instalator.Otoczenie,
więc testy podstawiają atrapy. Moduły ładujemy przed usuwaniem plików: po usunięciu biblioteki standardowej Pythona
z `<program>` (POSIX) nowy import by się nie udał.
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
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import instalator, sciezki, zmiany_hosta
from .instalator import Otoczenie
from .sciezki import LINUX, MACOS, WINDOWS, Uklad

KLUCZ_APLIKACJI = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
KLUCZ_RUNONCE = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
NAZWA_APLIKACJI = "Jarvo"
MAGAZYN_KLUCZA = "jarvo-github"         # klucz GitHuba w magazynie systemu (N15); czyta go jarvo/aktualizacja.py
CZAS_SPRZATANIA = 60                    # s: tyle proces sprzątający ponawia usuwanie, potem wpis RunOnce
CZAS_KONCA = 10.0                       # s na zakończenie procesu po SIGTERM (POSIX), potem SIGKILL
ZNACZNIKI_INSTALACJI = (("program", "current.json"), ("stan", "narzedzia.json"), ("stan", "zmiany-hosta.jsonl"),
                        ("stan", "nadzorca.json"))
TAK = ("t", "tak", "y", "yes")
_FLAGA_LINKU = 0x400                     # FILE_ATTRIBUTE_REPARSE_POINT: dowiązanie albo junction na Windows


class BladOdinstalowania(RuntimeError):
    """Odinstalowanie nie może się zacząć (komunikat po polsku z radą)."""


# ---------------------------------------------------------------- procesy

@dataclass(frozen=True)
class Proces:
    """Proces użytkownika: PID, PID rodzica, pełna ścieżka programu (albo sama nazwa, gdy system jej nie podał),
    wiersz polecenia (może być pusty) i czas startu (do odróżnienia PID-u użytego ponownie; None = nie wiadomo)."""
    pid: int
    rodzic: int
    program: str
    polecenie: str = ""
    start: int | None = None

    def opis(self) -> str:
        nazwa = re.split(r"[\\/]", self.program)[-1] if self.program else "?"
        return f"{nazwa} (PID {self.pid})"


if WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _WpisProcesu(ctypes.Structure):             # PROCESSENTRY32W
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    class _NapisUnicode(ctypes.Structure):            # UNICODE_STRING
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]

    _BIBLIOTEKI: list = []

    def _biblioteki():
        """kernel32 i ntdll z sygnaturami (raz na proces)."""
        if not _BIBLIOTEKI:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            nt = ctypes.WinDLL("ntdll")
            H, D, B, P = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER
            for biblioteka, nazwa, wynik, argumenty in (
                    (k32, "CreateToolhelp32Snapshot", H, [D, D]),
                    (k32, "Process32FirstW", B, [H, P(_WpisProcesu)]),
                    (k32, "Process32NextW", B, [H, P(_WpisProcesu)]),
                    (k32, "OpenProcess", H, [D, B, D]),
                    (k32, "QueryFullProcessImageNameW", B, [H, D, wintypes.LPWSTR, P(D)]),
                    (k32, "GetProcessTimes", B, [H] + [P(wintypes.FILETIME)] * 4),
                    (k32, "GetExitCodeProcess", B, [H, P(D)]),
                    (k32, "TerminateProcess", B, [H, wintypes.UINT]),
                    (k32, "WaitForSingleObject", D, [H, D]),
                    (k32, "CloseHandle", B, [H]),
                    (k32, "ProcessIdToSessionId", B, [D, P(D)]),
                    (nt, "NtQueryInformationProcess", ctypes.c_long,
                     [H, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG, P(wintypes.ULONG)])):
                f = getattr(biblioteka, nazwa)
                f.restype, f.argtypes = wynik, argumenty
            _BIBLIOTEKI[:] = [k32, nt]
        return _BIBLIOTEKI[0], _BIBLIOTEKI[1]

    def _wiersz_polecenia(nt, uchwyt) -> str:
        """Wiersz polecenia innego procesu: NtQueryInformationProcess(ProcessCommandLineInformation = 60), od
        Windows 8.1 z samym prawem PROCESS_QUERY_LIMITED_INFORMATION (tak robi psutil)."""
        dlugosc = wintypes.ULONG(0)
        nt.NtQueryInformationProcess(uchwyt, 60, None, 0, ctypes.byref(dlugosc))
        if not 0 < dlugosc.value <= 1 << 20:
            return ""
        bufor = ctypes.create_string_buffer(dlugosc.value)
        if nt.NtQueryInformationProcess(uchwyt, 60, bufor, dlugosc, ctypes.byref(dlugosc)) != 0:
            return ""
        napis = _NapisUnicode.from_buffer(bufor)
        if not napis.Buffer or not napis.Length:
            return ""
        return ctypes.wstring_at(napis.Buffer, napis.Length // 2)

    def _procesy_windows() -> list[Proces]:
        k32, nt = _biblioteki()
        migawka = k32.CreateToolhelp32Snapshot(0x2, 0)                          # TH32CS_SNAPPROCESS
        if not migawka or migawka == ctypes.c_void_p(-1).value:
            return []
        wpisy = []
        try:
            wpis = _WpisProcesu()
            wpis.dwSize = ctypes.sizeof(_WpisProcesu)
            jest = k32.Process32FirstW(migawka, ctypes.byref(wpis))
            while jest:
                wpisy.append((int(wpis.th32ProcessID), int(wpis.th32ParentProcessID), wpis.szExeFile))
                jest = k32.Process32NextW(migawka, ctypes.byref(wpis))
        finally:
            k32.CloseHandle(migawka)
        wynik = []
        for pid, rodzic, nazwa in wpisy:
            program, polecenie, start = "", "", None
            uchwyt = k32.OpenProcess(0x1000, False, pid) if pid else None       # PROCESS_QUERY_LIMITED_INFORMATION
            if uchwyt:
                try:
                    bufor = ctypes.create_unicode_buffer(32768)
                    n = wintypes.DWORD(len(bufor))
                    if k32.QueryFullProcessImageNameW(uchwyt, 0, bufor, ctypes.byref(n)):
                        program = bufor.value
                    polecenie = _wiersz_polecenia(nt, uchwyt)
                    czasy = [wintypes.FILETIME() for _ in range(4)]
                    if k32.GetProcessTimes(uchwyt, *(ctypes.byref(c) for c in czasy)):
                        start = (czasy[0].dwHighDateTime << 32) | czasy[0].dwLowDateTime
                finally:
                    k32.CloseHandle(uchwyt)
            wynik.append(Proces(pid, rodzic, program or nazwa, polecenie, start))
        return wynik

    def _zakoncz_windows(pid: int) -> bool:
        k32, _ = _biblioteki()
        uchwyt = k32.OpenProcess(0x0001 | 0x00100000, False, pid)              # PROCESS_TERMINATE | SYNCHRONIZE
        if not uchwyt:
            return False
        try:
            if not k32.TerminateProcess(uchwyt, 1):
                return False
            k32.WaitForSingleObject(uchwyt, 5000)
            return True
        finally:
            k32.CloseHandle(uchwyt)

    def _zyje_windows(pid: int) -> bool:
        k32, _ = _biblioteki()
        uchwyt = k32.OpenProcess(0x1000, False, pid)
        if not uchwyt:
            return False
        try:
            kod = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(uchwyt, ctypes.byref(kod))) and kod.value == 259   # STILL_ACTIVE
        finally:
            k32.CloseHandle(uchwyt)

    def _sesja_windows(pid: int) -> int | None:
        """Sesja Windows procesu (ProcessIdToSessionId nie otwiera procesu, więc działa też dla programu
        uruchomionego jako administrator); None, gdy procesu nie ma."""
        k32, _ = _biblioteki()
        sesja = wintypes.DWORD()
        return int(sesja.value) if k32.ProcessIdToSessionId(pid, ctypes.byref(sesja)) else None


def sesja_procesu(pid: int) -> int | None:
    """Sesja logowania procesu na Windows (ta sama sesja = ten sam pulpit użytkownika, także podniesione programy);
    poza Windows None."""
    if not WINDOWS:
        return None
    try:
        return _sesja_windows(int(pid))
    except (OSError, ValueError, OverflowError):
        return None


def _procesy_linux() -> list[Proces]:
    """Procesy tego użytkownika z /proc: program (dowiązanie exe), wiersz polecenia (cmdline), rodzic i czas startu
    (pola 4 i 22 ze stat)."""
    uid = os.getuid()
    wynik = []
    for nazwa in os.listdir("/proc"):
        if not nazwa.isdigit():
            continue
        katalog = f"/proc/{nazwa}"
        try:
            if os.stat(katalog).st_uid != uid:
                continue
            pola = Path(katalog, "stat").read_text(encoding="utf-8", errors="replace").rpartition(")")[2].split()
            cmd = Path(katalog, "cmdline").read_bytes()
        except OSError:
            continue
        try:
            program = os.readlink(f"{katalog}/exe")
        except OSError:
            program = ""
        polecenie = " ".join(c.decode("utf-8", "surrogateescape") for c in cmd.split(b"\0") if c)
        rodzic = int(pola[1]) if len(pola) > 1 and pola[1].isdigit() else 0
        start = int(pola[19]) if len(pola) > 19 and pola[19].isdigit() else None
        wynik.append(Proces(int(nazwa), rodzic, program or polecenie.split(" ", 1)[0], polecenie, start))
    return wynik


def _procesy_ps() -> list[Proces]:
    """macOS (i zapas na POSIX): `ps -axww -o pid=,ppid=,uid=,command=` w locale C, tylko procesy tego użytkownika."""
    ps = "/bin/ps" if os.path.exists("/bin/ps") else shutil.which("ps") or "ps"
    try:
        r = subprocess.run([ps, "-axww", "-o", "pid=,ppid=,uid=,command="], capture_output=True, timeout=60,
                           env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        return []
    uid = os.getuid() if hasattr(os, "getuid") else None
    wynik = []
    for linia in r.stdout.decode("utf-8", "replace").splitlines():
        czesci = linia.split(None, 3)
        if len(czesci) < 4 or not (czesci[0].isdigit() and czesci[1].isdigit() and czesci[2].isdigit()):
            continue
        if uid is not None and int(czesci[2]) != uid:
            continue
        polecenie = czesci[3]
        wynik.append(Proces(int(czesci[0]), int(czesci[1]), polecenie.split(" ", 1)[0], polecenie))
    return wynik


def procesy() -> list[Proces]:
    """Procesy użytkownika z pełną ścieżką programu i wierszem polecenia (tylko odczyt)."""
    if WINDOWS:
        return _procesy_windows()
    if LINUX and os.path.isdir("/proc"):
        return _procesy_linux()
    return _procesy_ps()


def zyje(pid: int) -> bool:
    """Czy proces działa. POSIX: zakończone dziecko tego procesu zbieramy (inaczej wisi jako zombie, a kill(pid, 0)
    dalej się udaje), a na Linuksie zombie cudzego rodzica (stan Z w /proc) też liczy się jako zakończony."""
    if WINDOWS:
        return _zyje_windows(pid)
    with contextlib.suppress(ChildProcessError, OSError):
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if LINUX:
        try:
            stan = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace").rpartition(")")[2].split()
        except OSError:
            return True
        return not stan or stan[0] not in ("Z", "X")
    if MACOS:
        try:
            r = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)], capture_output=True, timeout=10,
                               env={**os.environ, "LC_ALL": "C"})
        except (OSError, subprocess.SubprocessError):
            return True
        stan = r.stdout.decode("utf-8", "replace").strip()
        return bool(stan) and not stan.startswith("Z")
    return True


def zakoncz(lista: list[Proces], czas: float = CZAS_KONCA) -> list[Proces]:
    """Kończy procesy. Windows: TerminateProcess (bez drzewa, potomków dostajemy na liście osobno). POSIX: SIGTERM,
    po `czas` sekundach SIGKILL. Zwraca te, które dalej żyją."""
    if WINDOWS:
        for p in lista:
            _zakoncz_windows(p.pid)
        return [p for p in lista if _zyje_windows(p.pid)]
    for p in lista:
        with contextlib.suppress(OSError):
            os.kill(p.pid, signal.SIGTERM)
    koniec = time.monotonic() + czas
    zostale = [p for p in lista if zyje(p.pid)]
    while zostale and time.monotonic() < koniec:
        time.sleep(0.2)
        zostale = [p for p in zostale if zyje(p.pid)]
    for p in zostale:
        with contextlib.suppress(OSError):
            os.kill(p.pid, signal.SIGKILL)
    time.sleep(0.2 if zostale else 0)
    return [p for p in zostale if zyje(p.pid)]


def przodkowie(pid: int, lista: list[Proces]) -> set[int]:
    """PID-y przodków procesu (rodzic, dziadek…) z jednej migawki; pętla PID-ów użytych ponownie się kończy."""
    rodzice = {p.pid: p.rodzic for p in lista}
    wynik: set[int] = set()
    biezacy = rodzice.get(pid)
    while biezacy and biezacy not in wynik and biezacy != pid:
        wynik.add(biezacy)
        biezacy = rodzice.get(biezacy)
    return wynik


def _postaci(p: Path | str) -> list[str]:
    """Postaci ścieżki do porównań: bezwzględna, rzeczywista (Windows: krótka nazwa 8.3 rozwinięta, dowiązania)
    i na Windows krótka 8.3 (tak `<program>` wygląda przy korzeniu z polskimi znakami, c1), bez wielkości liter na
    Windows i macOS, na Windows z ukośnikami w obie strony; bez separatora na końcu."""
    wynik = set()
    postaci = [os.path.abspath(str(p)), os.path.realpath(str(p))]
    if WINDOWS:
        with contextlib.suppress(OSError, ValueError):
            postaci.append(str(sciezki.krotka_sciezka(Path(postaci[0]))))
    for x in postaci:
        if WINDOWS and x.startswith("\\\\?\\"):
            x = x[4:]
        x = x.rstrip("\\/") or x
        if WINDOWS or MACOS:
            x = x.casefold()
        wynik.add(x)
        if WINDOWS:
            wynik.add(x.replace("\\", "/"))
    return sorted(wynik, key=len, reverse=True)


def zawiera_sciezke(tekst: str, katalog: Path | str) -> bool:
    """Czy w tekście (program albo wiersz polecenia) jest ścieżka `katalog` albo coś w nim: za nazwą katalogu musi
    być separator, cudzysłów, spacja albo koniec (D:\\Jarvo to nie D:\\JarvoTest)."""
    if not tekst:
        return False
    t = tekst.casefold() if WINDOWS or MACOS else tekst
    for k in _postaci(katalog):
        i = t.find(k)
        while i >= 0:
            j = i + len(k)
            if j == len(t) or t[j] in "\\/\"' \t":
                return True
            i = t.find(k, i + 1)
    return False


def w_katalogu(sciezka: str, katalog: Path | str) -> bool:
    """Czy plik `sciezka` (np. program procesu) leży w `katalog` (także po rozwinięciu krótkiej nazwy 8.3
    i dowiązań)."""
    if not sciezka:
        return False
    s0 = sciezka[4:] if WINDOWS and sciezka.startswith("\\\\?\\") else sciezka
    kandydaci = {s0}
    if os.path.isabs(s0):
        with contextlib.suppress(OSError, ValueError):
            kandydaci.add(os.path.realpath(s0))
    postaci = [k.replace("/", "\\") if WINDOWS else k for k in _postaci(katalog)]
    for s in kandydaci:
        s = s.casefold() if WINDOWS or MACOS else s
        if WINDOWS:
            s = s.replace("/", "\\")
        for k in postaci:
            if s == k or s.startswith(k + ("\\" if WINDOWS else "/")):
                return True
    return False


def uzywaja(katalog: Path | str, lista: list[Proces], pomin: set[int] = frozenset()) -> list[Proces]:
    """Procesy, które mają w katalogu program albo podają go w wierszu polecenia (python <app>/jarvo/start.py)."""
    return [p for p in lista if p.pid not in pomin and (w_katalogu(p.program, katalog)
                                                         or zawiera_sciezke(p.polecenie, katalog))]


def procesy_jarva(korzen: Path, lista: list[Proces], pomin: set[int]) -> tuple[list[Proces], list[Proces]]:
    """(do zamknięcia, tylko wspominające): procesy z programem w korzeniu i ich potomkowie (rodzic starszy od
    dziecka, gdy oba czasy startu znamy) / procesy, które mają korzeń tylko w wierszu polecenia."""
    po_pid = {p.pid: p for p in lista}
    jarva = {p.pid for p in lista if p.pid not in pomin and w_katalogu(p.program, korzen)}
    zmiana = True
    while zmiana:
        zmiana = False
        for p in lista:
            if p.pid in jarva or p.pid in pomin or p.rodzic not in jarva:
                continue
            r = po_pid.get(p.rodzic)
            if r is not None and r.start is not None and p.start is not None and p.start < r.start:
                continue                                    # rodzicem był wcześniejszy proces z tym samym PID-em
            jarva.add(p.pid)
            zmiana = True
    do_zamkniecia = [p for p in lista if p.pid in jarva]
    wspominajace = [p for p in lista if p.pid not in jarva and p.pid not in pomin
                    and zawiera_sciezke(p.polecenie, korzen)]
    return do_zamkniecia, wspominajace


# ---------------------------------------------------------------- usuwanie plików

def _dluga(p: Path | str) -> str:
    """Windows: ścieżka z przedrostkiem \\\\?\\ (bez limitu MAX_PATH, np. node_modules w checkoucie Hermesa)."""
    s = os.path.abspath(str(p))
    if not WINDOWS or s.startswith("\\\\?\\"):
        return s
    return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s


def _krotka(s: str) -> str:
    if s.startswith("\\\\?\\UNC\\"):
        return "\\\\" + s[8:]
    return s[4:] if s.startswith("\\\\?\\") else s


def _klucz(p: Path | str) -> str:
    return os.path.normcase(_krotka(os.path.abspath(str(p))))


def _jest_linkiem(wpis: os.DirEntry) -> bool:
    """Dowiązanie albo junction: usuwamy sam wpis, bez wchodzenia do celu (wtyczki floty bywają junction, H27)."""
    try:
        if wpis.is_symlink():
            return True
        if WINDOWS:
            return bool(wpis.stat(follow_symlinks=False).st_file_attributes & _FLAGA_LINKU)
    except OSError:
        return False
    return False


def _usun_wpis(funkcja: Callable[[str], None], sciezka: str, bledy: list[str]) -> bool:
    for proba in range(3):
        try:
            funkcja(sciezka)
            return True
        except FileNotFoundError:
            return True
        except OSError as e:
            if proba == 0:
                with contextlib.suppress(OSError):
                    os.chmod(sciezka, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if os.path.isdir(sciezka) else 0))
                continue
            if proba == 2 or not WINDOWS:
                bledy.append(f"{_krotka(sciezka)}: {e.strerror or type(e).__name__}")
                return False
            time.sleep(0.2)                     # Windows: plik chwilowo trzyma antywirus albo indeksowanie
    return False


def usun_drzewo(p: Path | str, bledy: list[str] | None = None, *, pomin: tuple | list | set = ()) -> bool:
    """Usuwa plik albo drzewo katalogów bez wchodzenia w dowiązania i junction (usuwa sam wpis). Pliki tylko do
    odczytu odblokowuje (paczki gita, archiwa tar na Windows). Ścieżki z `pomin` (z całą zawartością) zostają, a ich
    katalogi nadrzędne też. Czego nie da się usunąć (np. .exe działającego programu na Windows), dopisuje do `bledy`
    i idzie dalej. True, gdy nic nie zostało (poza `pomin`)."""
    bledy = [] if bledy is None else bledy
    zostaw = {_klucz(x) for x in pomin}

    def usun(sciezka: str, wpis: os.DirEntry | None) -> bool:
        if _klucz(sciezka) in zostaw:
            return False
        if wpis is None:
            try:
                st = os.lstat(sciezka)
            except FileNotFoundError:
                return True
            except OSError as e:
                bledy.append(f"{_krotka(sciezka)}: {e.strerror or e}")
                return False
            link = stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _FLAGA_LINKU)
            katalog = stat.S_ISDIR(st.st_mode)
        else:
            link = _jest_linkiem(wpis)
            try:
                katalog = wpis.is_dir(follow_symlinks=False)
            except OSError:
                katalog = False
        if link:
            # junction i dowiązanie do katalogu na Windows usuwa rmdir, resztę unlink
            return _usun_wpis(os.rmdir if (WINDOWS and os.path.isdir(sciezka)) else os.unlink, sciezka, bledy)
        if not katalog:
            return _usun_wpis(os.unlink, sciezka, bledy)
        wszystko = True
        try:
            with os.scandir(sciezka) as it:
                wpisy = list(it)
        except FileNotFoundError:
            return True
        except OSError as e:
            if not _usun_wpis(lambda s: os.chmod(s, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC), sciezka, bledy):
                bledy.append(f"{_krotka(sciezka)}: {e.strerror or e}")
                return False
            try:
                with os.scandir(sciezka) as it:
                    wpisy = list(it)
            except OSError as e2:
                bledy.append(f"{_krotka(sciezka)}: {e2.strerror or e2}")
                return False
        for w in wpisy:
            wszystko = usun(os.path.join(sciezka, w.name), w) and wszystko
        return _usun_wpis(os.rmdir, sciezka, bledy) if wszystko else False

    return usun(_dluga(p), None)


def rozmiar(p: Path | str, limit: int = 500_000) -> int:
    """Bajty plików w drzewie (bez wchodzenia w dowiązania), do `limit` wpisów: do raportu „zwolnione miejsce”."""
    suma = n = 0
    stos = [_dluga(p)]
    while stos and n < limit:
        try:
            with os.scandir(stos.pop()) as it:
                for w in it:
                    n += 1
                    if _jest_linkiem(w):
                        continue
                    try:
                        if w.is_dir(follow_symlinks=False):
                            stos.append(w.path)
                        else:
                            suma += w.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return suma


# ---------------------------------------------------------------- zaplecze: to, co dotyka komputera

def _terminal() -> bool:
    try:
        return bool(sys.stdin is not None and sys.stdin.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def pytaj(tekst: str) -> str:
    """Pytanie do właściciela na stderr i odpowiedź z wejścia (bez końca wiersza; koniec wejścia = pusta odpowiedź).
    Nie input(): ten pisze pytanie na stdout, a przy `--json` (np. `> raport.json`) stdout to sam raport JSON."""
    strumien = sys.stderr or sys.stdout
    with contextlib.suppress(AttributeError, OSError, ValueError):
        strumien.write(tekst)
        strumien.flush()
    try:
        linia = sys.stdin.readline() if sys.stdin is not None else ""
    except (OSError, ValueError):
        linia = ""
    return linia.rstrip("\r\n")


# ---------------------------------------------------------------- klucz GitHuba w magazynie systemu (N15)

def _cred_windows(usun: bool) -> bool:
    """Menedżer poświadczeń Windows, poświadczenie ogólne MAGAZYN_KLUCZA: czy jest (CredReadW, treść od razu
    zwalniana, nigdzie nie trafia), a z `usun` usunięcie (CredDeleteW)."""
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    if usun:
        adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        adv.CredDeleteW.restype = wintypes.BOOL
        return bool(adv.CredDeleteW(MAGAZYN_KLUCZA, 1, 0))                   # CRED_TYPE_GENERIC
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    wsk = ctypes.c_void_p()
    if not adv.CredReadW(MAGAZYN_KLUCZA, 1, 0, ctypes.byref(wsk)):
        return False
    adv.CredFree(wsk)
    return True


def _magazyn_posix(usun: bool) -> bool:
    """macOS: pęk kluczy (`security find-generic-password` bez -w nie wypisuje hasła, `delete-generic-password`);
    Linux: libsecret (`secret-tool lookup` i `clear`), wyjście tylko w pamięci. Brak narzędzia = brak klucza."""
    if MACOS:
        argv = ["/usr/bin/security", "delete-generic-password" if usun else "find-generic-password", "-s",
                MAGAZYN_KLUCZA]
    else:
        narzedzie = shutil.which("secret-tool", path="/usr/bin:/bin:/usr/local/bin")
        if not narzedzie:
            return False
        argv = [narzedzie, "clear" if usun else "lookup", "service", MAGAZYN_KLUCZA]
    if not os.path.isfile(argv[0]):
        return False
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and (usun or MACOS or bool(r.stdout.strip()))


def klucz_github_jest() -> bool:
    """Czy w magazynie systemu jest klucz `jarvo-github` (tylko odczyt; plik zapasowy `<dane>/jarvo/konfig/github-
    token` znika razem z danymi)."""
    try:
        return _cred_windows(False) if WINDOWS else _magazyn_posix(False)
    except (OSError, ValueError, AttributeError):
        return False


def usun_klucz_github() -> bool:
    """Usuwa klucz `jarvo-github` z magazynu systemu; True, gdy po tym go tam nie ma."""
    with contextlib.suppress(OSError, ValueError, AttributeError):
        if WINDOWS:
            _cred_windows(True)
        else:
            _magazyn_posix(True)
    return not klucz_github_jest()


def rada_klucza() -> str:
    """Jak usunąć klucz ręcznie (bez wartości klucza)."""
    if WINDOWS:
        return f"cmdkey /delete:{MAGAZYN_KLUCZA} (albo Menedżer poświadczeń > Poświadczenia systemu Windows)"
    if MACOS:
        return f"security delete-generic-password -s {MAGAZYN_KLUCZA}"
    return f"secret-tool clear service {MAGAZYN_KLUCZA}"


def uruchom_odlaczony(argv: list[str], *, cwd: str | None = None) -> int:
    """Proces niezależny od tego (zamknięcie okna i koniec tego procesu go nie kończą), bez okna i bez wyjścia."""
    kw: dict[str, Any] = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=cwd, close_fds=True)
    if not WINDOWS:
        return subprocess.Popen(argv, start_new_session=True, **kw).pid
    flagi = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        return subprocess.Popen(argv, creationflags=flagi | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw).pid
    except OSError:                          # zadanie rodzica nie pozwala na wyjście z niego (część runnerów CI)
        return subprocess.Popen(argv, creationflags=flagi, **kw).pid


def strumien(argv: list[str], *, env: dict, cwd: Path | str | None, log: Callable[[str], None],
             czas: float | None = None) -> int:
    """Program z wyjściem przekazywanym wiersz po wierszu do `log` (UTF-8); kod wyjścia, 124 po `czas` sekundach
    (proces zabity). Bez okna konsoli na Windows."""
    proc = subprocess.Popen([str(a) for a in argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, cwd=str(cwd) if cwd else None,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    koniec = None if czas is None else time.monotonic() + czas
    zabity = False

    def pilnuj() -> None:
        nonlocal zabity
        while proc.poll() is None:
            if koniec is not None and time.monotonic() > koniec:
                zabity = True
                with contextlib.suppress(OSError):
                    proc.kill()
                return
            time.sleep(1.0)

    straznik = threading.Thread(target=pilnuj, daemon=True)
    straznik.start()
    assert proc.stdout is not None
    for wiersz in iter(proc.stdout.readline, b""):
        log(wiersz.decode("utf-8", "replace").rstrip("\r\n"))
    kod = proc.wait()
    straznik.join(timeout=5)
    return 124 if zabity else kod


def przechwyc(argv: list[str], *, env: dict, cwd: Path | str | None, czas: float = 600) -> tuple[int, str]:
    """Program z przechwyconym wyjściem (stdout; stderr osobno, pomijany): (kod, tekst); 124 po limicie czasu."""
    try:
        r = subprocess.run([str(a) for a in argv], stdin=subprocess.DEVNULL, capture_output=True, env=env,
                           cwd=str(cwd) if cwd else None, timeout=czas,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError as e:
        return 126, str(e)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def _wpis_aplikacji(nazwa: str) -> dict | None:
    """Wartości klucza HKCU\\...\\Uninstall\\<nazwa> (wpis w „Aplikacje”) albo None, gdy go nie ma."""
    if not WINDOWS:
        return None
    import winreg
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{KLUCZ_APLIKACJI}\\{nazwa}")
    except OSError:
        return None
    wynik = {}
    with k:
        i = 0
        while True:
            try:
                n, w, _typ = winreg.EnumValue(k, i)
            except OSError:
                break
            wynik[n] = str(w)
            i += 1
    return wynik


def _usun_wpis_aplikacji(nazwa: str) -> None:
    if WINDOWS:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{KLUCZ_APLIKACJI}\\{nazwa}")


@dataclass
class Zaplecze:
    """To, czego odinstalowanie i aktualizacja używają poza instalator.Otoczenie: procesy (lista, zakończenie, sesja
    Windows), proces odłączony (sprzątanie na Windows), pytania do właściciela (na stderr), polecenia systemu dla
    dziennika zmian hosta, wpis w „Aplikacje”, klucz GitHuba w magazynie systemu (czy jest, usunięcie), programy
    z wyjściem na bieżąco (instalator nowej wersji) i z wyjściem przechwyconym (`jarvo doctor --json`). Testy
    podstawiają atrapy (magazynu kluczy właściciela test nie dotyka)."""
    procesy: Callable[[], list[Proces]] = procesy
    zakoncz: Callable[[list[Proces]], list[Proces]] = zakoncz
    odlacz: Callable[..., int] = uruchom_odlaczony
    pytaj: Callable[[str], str] = pytaj
    terminal: Callable[[], bool] = _terminal
    wykonaj: Callable[[list], tuple[int, str]] = zmiany_hosta.uruchom_domyslnie
    aplikacje: Callable[[str], dict | None] = _wpis_aplikacji
    usun_aplikacje: Callable[[str], None] = _usun_wpis_aplikacji
    klucz_jest: Callable[[], bool] = klucz_github_jest
    usun_klucz: Callable[[], bool] = usun_klucz_github
    sesja: Callable[[int], int | None] = sesja_procesu
    strumien: Callable[..., int] = strumien
    przechwyc: Callable[..., tuple[int, str]] = przechwyc
    pid: int = field(default_factory=os.getpid)


# ---------------------------------------------------------------- układ i korzeń

def uklad_instalacji(u: Uklad, env: dict) -> Uklad:
    """Układ, z którym działa instalacja. Procesy floty mają JARVO_ROOT w otoczeniu (jarvo/srodowisko.py), a na
    Linuksie JARVO_ROOT przenosi logi i cache z katalogów XDG do korzenia (sciezki.uklad). Polecenie jarvo i autostart
    podają korzeń tylko wtedy, gdy nie jest domyślny, więc dla domyślnego liczymy układ bez JARVO_ROOT, jak one."""
    if env.get("JARVO_ROOT") and instalator.korzen_domyslny(u, env):
        with contextlib.suppress(sciezki.BladUkladu):
            return sciezki.uklad({k: v for k, v in env.items() if k != "JARVO_ROOT"})
    return u


def env_podprocesu(u: Uklad, env: dict) -> dict:
    """Otoczenie polecenia jarvo uruchamianego z tego procesu (instalator nowej wersji, doctor, pomocnik aktualizacji
    pod nadzorcą i `jarvo update` z panelu): bez JARVO_TOKEN (klucz zostaje w tym procesie, jak w bootstrapie), bez
    JARVO_REF (zmienna z okna, w którym instalowano, nie zmienia refu instalacji: ten jest w `.jarvo-ref` kodu i przy
    `jarvo update --ref`) i bez JARVO_ROOT dla domyślnego korzenia (korzeń inny niż domyślny dostaje `--korzen` w argv)."""
    wynik = {k: v for k, v in env.items() if k.upper() not in ("JARVO_TOKEN", "JARVO_REF")}
    if instalator.korzen_domyslny(u, env):
        wynik.pop("JARVO_ROOT", None)
    return wynik


def inna_instalacja(u: Uklad, env: dict) -> str | None:
    """Inna instalacja Jarva na tym koncie, która korzysta z tego samego magazynu kluczy: stara z WSL albo Dockerem
    i instalacja w domyślnym korzeniu, gdy `u` nim nie jest. Opis albo None. Tylko odczyt."""
    stara = stara_instalacja(u, env)
    if stara:
        return stara
    if not instalator.korzen_domyslny(u, env):
        with contextlib.suppress(sciezki.BladUkladu, OSError):
            domyslny = sciezki.uklad({k: v for k, v in env.items() if k != "JARVO_ROOT"})
            if zainstalowane(domyslny):
                return f"instalacja Jarva w {domyslny.root}"
    return None


def zly_korzen(u: Uklad) -> str | None:
    """Powód odmowy usuwania: katalog główny dysku, katalog domowy albo katalog nad nim."""
    root = Path(os.path.abspath(u.root))
    if root.parent == root:
        return f"{root} to katalog główny dysku"
    dom = _klucz(Path.home())
    k = _klucz(root)
    if k == dom or dom.startswith(k.rstrip("\\/") + os.sep):
        return f"{root} to katalog domowy albo katalog nad nim"
    return None


def zainstalowane(u: Uklad) -> bool:
    """Czy w korzeniu jest instalacja Jarva (current.json albo pliki stanu instalatora i nadzorcy)."""
    return any((getattr(u, czesc) / plik).is_file() for czesc, plik in ZNACZNIKI_INSTALACJI)


def stara_instalacja(u: Uklad, env: dict | None = None) -> str | None:
    """Opis starej instalacji z WSL albo Dockerem obok (do migracji, etap E12), albo None."""
    env = os.environ if env is None else env
    if WINDOWS:
        wsl = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jarvo" / "wsl"
        if wsl.is_dir():
            return f"stara instalacja Jarvo z WSL ({wsl})"
        cmd = u.root / "bin" / "jarvo.cmd"
        if cmd.is_file() and instalator.ZNACZNIK not in cmd.read_text(encoding="utf-8", errors="replace"):
            return f"polecenie starej instalacji Jarvo z WSL ({cmd})"
        return None
    stara = Path.home() / "jarvo-local"
    return f"stara instalacja Jarvo z Dockerem ({stara})" if stara.is_dir() else None


# ---------------------------------------------------------------- skan śladów

def _plik_polecenia_posix(u: Uklad) -> Path | None:
    """~/.local/bin/jarvo, jeśli to nasze polecenie dla TEGO korzenia."""
    cel = Path.home() / ".local" / "bin" / "jarvo"
    try:
        if not cel.is_file() or cel.is_symlink():
            return None
        tekst = cel.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if instalator.ZNACZNIK not in tekst:
        return None
    korzen = instalator.korzen_polecenia(tekst)
    if korzen is None:
        try:
            korzen = str(sciezki.uklad({k: v for k, v in os.environ.items() if k != "JARVO_ROOT"}).root)
        except sciezki.BladUkladu:
            return None
    return cel if _klucz(korzen) == _klucz(u.root) else None


def skan_sladow(u: Uklad, ot: Otoczenie, z: Zaplecze, *, dane_zostaja: bool, na_pozniej: list[Path] = (),
                pliki_rc: list[str] = (), bledy_dziennika: list[str] = (), pomin: set[int] = frozenset(),
                klucz_github: bool | None = None, klucz_zostaje: str | None = None) -> dict:
    """Ślady Jarva na komputerze: {"slady": [{rodzaj, opis, rada}], "celowo": [{rodzaj, opis, powod}]}. Tylko
    odczyt (ten sam skaner może wołać `jarvo doctor`). `klucz_github` i `klucz_zostaje`: stan klucza GitHuba po
    kroku odinstalowania (None = zapytaj magazyn i ustal powód sam)."""
    slady: list[dict] = []
    celowo: list[dict] = []
    pozniej = {_klucz(p) for p in na_pozniej}

    def slad(rodzaj: str, opis: str, rada: str) -> None:
        slady.append({"rodzaj": rodzaj, "opis": opis, "rada": rada})

    def zostaje(rodzaj: str, opis: str, powod: str) -> None:
        celowo.append({"rodzaj": rodzaj, "opis": opis, "powod": powod})

    usun = ("Usuń ręcznie" + (" (Eksplorator albo Remove-Item -Recurse)" if WINDOWS else " (rm -rf)")
            + " albo uruchom jarvo uninstall jeszcze raz po ponownej instalacji.")
    for nazwa, k in (("program", u.program), ("stan", u.stan), ("polecenie", u.root / "bin"), ("build", u.build),
                     ("logi", u.logi), ("cache", u.cache)):
        if not os.path.lexists(k):
            continue
        if _klucz(k) in pozniej or any(_klucz(p).startswith(_klucz(k) + os.sep) for p in na_pozniej):
            zostaje("katalog", f"{k}", "usunie go proces sprzątający zaraz po zakończeniu tego polecenia (Python tego "
                                       "polecenia i jarvo.cmd są w użyciu do jego końca)")
        else:
            slad("katalog", f"{nazwa}: {k}", usun)
    if u.dane.exists():
        if dane_zostaja:
            zostaje("dane", str(u.dane), "bez --all dane zostają (profile, rozmowy, skarbiec, klucze, modele); usunie "
                                         "je jarvo uninstall --all albo ręcznie")
        else:
            slad("katalog", f"dane: {u.dane}", usun)
    if u.root.is_dir():
        try:
            obce = sorted(e.name for e in os.scandir(u.root)
                          if e.name not in ("program", "dane", "stan", "logi", "cache", "build", "bin"))
        except OSError:
            obce = []
        if obce:
            zostaje("obce pliki", f"w {u.root}: {', '.join(obce[:8])}", "nie należą do Jarva, więc ich nie ruszam")
    if not WINDOWS:
        cel = _plik_polecenia_posix(u)
        if cel is not None:
            slad("polecenie", str(cel), f"Usuń plik: rm {cel}")
        for p in pliki_rc:
            try:
                if "# >>> jarvo >>>" in Path(p).read_text(encoding="utf-8", errors="replace"):
                    slad("blok-rc", f"blok jarvo w {p}", f"Usuń z {p} wiersze od „# >>> jarvo >>>” do "
                                                        "„# <<< jarvo <<<”.")
            except OSError:
                continue
    else:
        wpis = str(u.root / "bin")
        try:
            obecna = (ot.rejestr or zmiany_hosta.Rejestr()).czytaj(zmiany_hosta.ENV, "Path")
        except OSError:
            obecna = None
        czesci = (obecna[0] if obecna else "").split(";")
        if any(zmiany_hosta._klucz_path(c) == zmiany_hosta._klucz_path(wpis) for c in czesci if c.strip()):
            if stara_instalacja(u, ot.env):
                zostaje("PATH", f"PATH użytkownika: {wpis}", "tego samego wpisu używa stara instalacja z WSL")
            else:
                slad("PATH", f"PATH użytkownika: {wpis}", "Usuń wpis: Ustawienia > System > Informacje > Zaawansowane "
                                                         "ustawienia systemu > Zmienne środowiskowe > Path.")
        aplikacja = z.aplikacje(NAZWA_APLIKACJI)
        if aplikacja is not None:
            miejsce = aplikacja.get("InstallLocation") or aplikacja.get("UninstallString") or ""
            if zawiera_sciezke(miejsce, u.root):
                slad("aplikacje", f"wpis „Aplikacje” HKCU\\{KLUCZ_APLIKACJI}\\{NAZWA_APLIKACJI}",
                     "Usuń go w Ustawienia > Aplikacje albo regedit.")
            else:
                zostaje("aplikacje", f"wpis „Aplikacje” {NAZWA_APLIKACJI}", "nie wskazuje tej instalacji (stara "
                                                                           "instalacja?), więc go nie ruszam")
    jest_klucz = z.klucz_jest() if klucz_github is None else klucz_github
    if jest_klucz:
        opis = f"klucz GitHuba {MAGAZYN_KLUCZA} w magazynie systemu"
        if klucz_zostaje is None:
            inna = inna_instalacja(u, ot.env)
            klucz_zostaje = (f"korzysta z niego też {inna}" if inna
                             else "bez --all dane i klucz zostają" if dane_zostaja else None)
        if klucz_zostaje:
            zostaje("klucz", opis, f"{klucz_zostaje}; ręcznie: {rada_klucza()}")
        else:
            slad("klucz", opis, f"Usuń go: {rada_klucza()}.")
    auto = stan_autostartu(u, ot, z)
    if auto.get("mechanizm") and auto.get("nasz"):
        slad("autostart", str(auto.get("opis") or auto.get("nazwa")), "Wyłącz: jarvo autostart off przed "
             "odinstalowaniem albo ręcznie (taskschd.msc, launchctl bootout, systemctl --user disable).")
    for p in uzywaja(u.root, z.procesy(), pomin):
        slad("proces", f"{p.opis()}: {(p.polecenie or p.program)[:200]}", "Zamknij ten program (korzysta z katalogu "
                                                                          "Jarva).")
    for opis in bledy_dziennika:
        slad("dziennik", opis, "Cofnij tę zmianę ręcznie (opis wyżej).")
    stara = stara_instalacja(u, ot.env)
    if stara:
        zostaje("stara instalacja", stara, "sprzątanie starej instalacji to osobny krok migracji (jarvo migruj, etap "
                                           "E12)")
    return {"slady": slady, "celowo": celowo}


def stan_autostartu(u: Uklad, ot: Otoczenie, z: Zaplecze) -> dict:
    """autostart.stan(u) z poleceniami systemu z zaplecza (także gdy `<stan>` już nie ma: instalator.stan_autostartu
    wtedy systemu nie pyta) albo {"sprawdzony": False, "powod"}."""
    try:
        return dict(instalator.wywolaj(ot.modul("autostart").stan, u, z.wykonaj, env=ot.env, rejestr=ot.rejestr) or {})
    except Exception as e:                    # noqa: BLE001 - brak modułu albo narzędzia systemu: tylko opis
        return {"sprawdzony": False, "powod": f"{type(e).__name__}: {str(e)[:120]}"}


# ---------------------------------------------------------------- proces sprzątający (Windows)

# PowerShell kończy napis w apostrofach na każdym z tych znaków (ASCII ' i typograficzne ‘ ’ ‚ ‛), a w środku
# napisu każdy z nich podwaja się tak samo jak ' (specyfikacja języka: single-quote-character)
_APOSTROFY = ("'", "‘", "’", "‚", "‛")
_CUDZYSLOW = "|"                         # zastępczy znak cudzysłowu w poleceniu RunOnce: w nazwie pliku Windows go nie ma


def _ps_napis(tekst: str) -> str:
    """Napis PowerShella w apostrofach: każdy znak, który PowerShell bierze za apostrof, podwojony (np. korzeń
    w profilu O’Brien). Bez cudzysłowów: powershell.exe 5.1 psuje je w argumencie -Command."""
    tekst = str(tekst)
    for z in _APOSTROFY:
        tekst = tekst.replace(z, z + z)
    return "'" + tekst + "'"


def polecenie_runonce(sciezka: Path | str, *, znacznik: Path | str | None = None,
                      korzen: Path | str | None = None) -> str:
    """Wartość wpisu HKCU RunOnce, która przy następnym logowaniu usuwa `sciezka` (cmd.exe rmdir /s /q nie wchodzi
    w junction). Ze `znacznik` (`<program>\\current.json`) tylko wtedy, gdy go nie ma: ponowna instalacja w tym samym
    korzeniu przed wylogowaniem zostaje nietknięta. Z `korzen` na końcu pusty korzeń (rmdir bez /s)."""
    usun = f'rmdir /s /q "{sciezka}"' + (f' & rmdir "{korzen}" 2>nul' if korzen else "")
    if znacznik:
        return f'cmd.exe /c if not exist "{znacznik}" ({usun})'
    return f"cmd.exe /c {usun}"


def skrypt_sprzatania(pidy: list[int], sciezki_do_usuniecia: list[Path], korzen: Path, *, usun_korzen: bool,
                      czas: int = CZAS_SPRZATANIA, runonce: bool = True, znacznik: Path | None = None) -> str:
    """Skrypt procesu sprzątającego (PowerShell 5.1, bez cudzysłowów): czeka na koniec procesów `pidy` (to polecenie
    i ewentualnie cmd.exe z jarvo.cmd), daje cmd.exe 2 s na dokończenie pliku wsadowego, usuwa ścieżki (ponawia przez
    `czas` sekund), potem pusty korzeń (gdy `usun_korzen`). Czego nie usunie (plik trzyma inny program), to przenosi
    do %TEMP% (zmiana nazwy przechodzi także dla uruchomionego .exe, gdy %TEMP% jest na tym samym dysku), zdejmuje
    pusty korzeń i zapisuje usunięcie w HKCU RunOnce (rmdir przy następnym logowaniu). Ścieżka, której nie dało się
    przenieść (inny dysk, katalog bieżący innego programu), dostaje wpis z warunkiem `znacznik` (domyślnie
    `<korzen>\\program\\current.json`, polecenie_runonce): przy ponownej instalacji nic nie znika. Bez `runonce` tylko
    zostawia: tak robią testy, żeby nie pisać do rejestru właściciela."""
    skrot = hashlib.sha256(_klucz(korzen).encode("utf-8")).hexdigest()[:8]
    lista = ", ".join(_ps_napis(p) for p in sciezki_do_usuniecia) or "''"
    znacznik = Path(znacznik) if znacznik else Path(korzen) / "program" / "current.json"
    warunkowe = []                               # ścieżka → polecenie RunOnce z warunkiem („|” zamiast cudzysłowu)
    for p in sciezki_do_usuniecia:
        polecenie = polecenie_runonce(p, znacznik=znacznik, korzen=korzen if usun_korzen else None)
        warunkowe.append(f"{_ps_napis(p)} = {_ps_napis(polecenie.replace(chr(34), _CUDZYSLOW))}")
    w = ["$ErrorActionPreference = 'SilentlyContinue'", "$ProgressPreference = 'SilentlyContinue'",
         f"foreach ($p in @({', '.join(str(int(x)) for x in pidy) or '0'})) {{ Wait-Process -Id $p -Timeout 600 }}",
         "Start-Sleep -Seconds 2",
         f"$sciezki = @({lista}) | Where-Object {{ $_ }}",
         f"$korzen = {_ps_napis(korzen)}",
         f"for ($i = 0; $i -lt {int(czas)}; $i++) {{",
         "  foreach ($s in $sciezki) {",
         "    if (Test-Path -LiteralPath $s) { Remove-Item -LiteralPath $s -Recurse -Force }",
         "  }",
         "  if (-not ($sciezki | Where-Object { Test-Path -LiteralPath $_ })) { break }",
         "  Start-Sleep -Seconds 1",
         "}"]
    pusty_korzen = ("if ((Test-Path -LiteralPath $korzen) -and -not (Get-ChildItem -LiteralPath $korzen -Force)) "
                    "{ Remove-Item -LiteralPath $korzen -Force }")
    if usun_korzen:
        w.append(pusty_korzen)
    if not runonce:
        return "\n".join(w)
    w += ["$q = [char]34",
          f"$klucz = 'HKCU:\\' + {_ps_napis(KLUCZ_RUNONCE)}",
          "$tmp = [IO.Path]::GetTempPath()",
          f"$warunkowe = @{{ {'; '.join(warunkowe)} }}",
          "$n = 0",
          "foreach ($s in $sciezki) {",
          "  if (Test-Path -LiteralPath $s) {",
          "    $n++",
          f"    $cel = Join-Path $tmp ('jarvo-usun-{skrot}-' + $n)",
          "    try {",
          "      Move-Item -LiteralPath $s -Destination $cel -Force -ErrorAction Stop",
          "      $wartosc = 'cmd.exe /c rmdir /s /q ' + $q + $cel + $q",
          "    } catch {",
          f"      $wartosc = $warunkowe[$s].Replace({_ps_napis(_CUDZYSLOW)}, $q)",
          "    }",
          "    if (-not (Test-Path -LiteralPath $klucz)) { New-Item -Path $klucz -Force | Out-Null }",
          f"    $nazwa = 'Jarvo-sprzatanie-{skrot}-' + $n",
          "    New-ItemProperty -LiteralPath $klucz -Name $nazwa -Value $wartosc -PropertyType String -Force |",
          "      Out-Null",
          "  }",
          "}"]
    if usun_korzen:
        w.append(pusty_korzen)
    return "\n".join(w)


def argv_sprzatania(skrypt: str) -> list[str]:
    ps = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / \
        "powershell.exe"
    return [str(ps), "-NoLogo", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", skrypt]


def _python_w_korzeniu(u: Uklad) -> Path | None:
    """Katalog Pythona tego procesu, gdy leży w korzeniu (Windows: jego .exe i .dll są zablokowane do końca)."""
    baza = Path(os.path.abspath(sys.base_prefix or os.path.dirname(sys.executable)))
    exe = Path(os.path.abspath(sys.executable))
    for k in (exe.parent, baza):
        if w_katalogu(str(k), u.root) and _klucz(k) != _klucz(u.root):
            return k
    return None


# ---------------------------------------------------------------- odinstalowanie

def _tak(odp: str | None) -> bool:
    return str(odp or "").strip().casefold() in TAK


def _wypisz(tekst: str) -> None:
    print(tekst, flush=True)


def _na_stderr(tekst: str) -> None:
    print(tekst, file=sys.stderr, flush=True)


class _Odinstalowanie:
    def __init__(self, u: Uklad, ot: Otoczenie, z: Zaplecze, log: Callable[[str], None], *, wszystko: bool,
                 tak: bool):
        self.u, self.ot, self.z, self.log = u, ot, z, log
        self.wszystko, self.tak = wszystko, tak
        self.usun_dane = False
        self.na_pozniej: list[Path] = []
        self.pliki_rc: list[str] = []
        self.bledy: list[str] = []
        self.bledy_dziennika: list[str] = []
        self.raport: dict = {"root": str(u.root), "czas": time.strftime("%Y-%m-%dT%H:%M:%S"), "wszystko": wszystko,
                             "dane_usuniete": False, "zatrzymane": [], "cofniete": [], "usuniete": [], "bledy": [],
                             "slady": [], "celowo": [], "sprzatanie": None, "wynik": None}
        self.lista: list[Proces] = []
        self.pomin: set[int] = set()
        self.klucz_github: bool | None = None        # klucz GitHuba w magazynie po kroku „Klucz GitHuba”
        self.klucz_zostaje: str | None = None        # dlaczego zostaje (bez --all, inna instalacja)

    def podlog(self, tekst: str) -> None:
        self.log(f"    {tekst}")

    # -- przebieg
    def uruchom(self) -> int:
        u = self.u
        powod = zly_korzen(u)
        if powod:
            return self._koniec("odmowa", f"BŁĄD: {powod}: tu niczego nie usuwam (JARVO_ROOT wskazuje zły katalog?).",
                                kod=1)
        if not zainstalowane(u):
            self.log(f"Jarvo nie jest zainstalowane w {u.root} (brak {u.program / 'current.json'} i plików w "
                     f"{u.stan}). Sprawdzam tylko ślady.")
            return self._skan_i_koniec("brak instalacji")
        if not self._zgoda():
            return self._koniec("anulowane", "Anulowano: niczego nie zmieniłem.", kod=0)
        self.log(f"Jarvo: odinstalowanie z {u.root}" + (" razem z danymi" if self.usun_dane else
                                                         " (dane zostają)"))
        for nazwa, krok in (("Zatrzymanie serwisu", self.zatrzymaj), ("Procesy Jarva", self.procesy),
                            ("Autostart", self.autostart), ("Dziennik zmian hosta", self.dziennik),
                            ("Wpis w „Aplikacje”", self.aplikacje), ("Klucz GitHuba", self.klucz),
                            ("Pliki", self.pliki)):
            self.log(f"[{nazwa}]")
            try:
                if krok() is False:
                    return self._koniec("przerwane", "Przerwano: pliki Jarva zostają, możesz uruchomić jarvo "
                                                     "uninstall jeszcze raz.", kod=1)
            except Exception as e:            # noqa: BLE001 - krok nie może zostawić połowy bez raportu
                self.bledy.append(f"{nazwa}: {type(e).__name__}: {e}")
                self.podlog(f"BŁĄD: {type(e).__name__}: {e}")
        return self._skan_i_koniec("odinstalowane")

    def _zgoda(self) -> bool:
        if self.tak:
            self.usun_dane = self.wszystko
            return True
        if not self.z.terminal():
            raise BladOdinstalowania("bez terminala nie mogę zapytać o zgodę: dodaj --yes (z --all usuwa też dane)")
        co = "program, narzędzia, logi, cache, autostart i polecenie jarvo"
        if not _tak(self.z.pytaj(f"Odinstalować Jarvo z {self.u.root}? Usunę {co}. [t/N] ")):
            return False
        if self.wszystko:
            self.usun_dane = _tak(self.z.pytaj(
                f"Usunąć też dane z {self.u.dane} (profile, rozmowy, skarbiec, klucze, modele)? Tego nie da się "
                "cofnąć. [t/N] "))
            if not self.usun_dane:
                self.log("Dane zostają.")
        return True

    def zatrzymaj(self) -> None:
        u, ot = self.u, self.ot
        if not u.stan.is_dir():
            self.podlog("brak katalogu stanu: serwis nie działał")
            return
        try:
            instalator.oznacz_zatrzymanie(u, ot, "jarvo uninstall")
        except instalator.BladInstalacji as e:
            self.podlog(f"uwaga: {e}")
        stan, powod = instalator.stan_serwisu(u, ot)
        if stan is None:
            self.podlog(f"serwis nie działa ({powod})")
            return
        self.podlog("zatrzymuję serwis (brama kończy trwające tury)…")
        try:
            instalator.zatrzymaj_serwis(u, ot, "jarvo uninstall")
            self.podlog("serwis zatrzymany")
        except instalator.BladInstalacji as e:
            self.podlog(f"uwaga: {e}; procesy zamknę w następnym kroku")

    def procesy(self) -> None:
        self.lista = self.z.procesy()
        self.pomin = {self.z.pid, *przodkowie(self.z.pid, self.lista)}
        do_zamkniecia, wspominajace = procesy_jarva(self.u.root, self.lista, self.pomin)
        if not do_zamkniecia:
            self.podlog("żaden proces Jarva nie działa")
        else:
            self.podlog("zamykam: " + ", ".join(p.opis() for p in do_zamkniecia[:12])
                        + (" …" if len(do_zamkniecia) > 12 else ""))
            zostale = self.z.zakoncz(do_zamkniecia)
            self.raport["zatrzymane"] = [p.opis() for p in do_zamkniecia if p not in zostale]
            for p in zostale:
                self.bledy.append(f"proces {p.opis()} nie dał się zamknąć")
        for p in wspominajace:
            self.podlog(f"nie zamykam {p.opis()}: to nie program Jarva, a korzysta z jego katalogu "
                        f"({(p.polecenie or p.program)[:120]})")

    def autostart(self) -> None:
        try:
            auto = self.ot.modul("autostart")
        except ImportError as e:
            self.podlog(f"brak modułu autostartu ({e}): zostaje dziennik zmian hosta")
            return
        try:
            wynik = instalator.wywolaj(auto.wylacz, self.u, self.z.wykonaj, env=self.ot.env, rejestr=self.ot.rejestr,
                                       log=None)
        except instalator.bledy_autostartu(auto) as e:
            self.podlog(f"uwaga: {str(e)[:300]}")
            return
        wynik = wynik if isinstance(wynik, dict) else {}
        self.podlog(f"autostart {wynik.get('nazwa') or ''}: " + ("usunięty" if wynik.get("usuniety") else "nie był "
                                                                 "włączony"))

    def dziennik(self) -> bool:
        u = self.u
        wpisy = zmiany_hosta.wpisy(u)
        self.pliki_rc = [w["szczegoly"].get("sciezka") for w in wpisy
                         if w["rodzaj"] == "blok-rc" and w["szczegoly"].get("sciezka")]
        for w in wpisy:
            sciezka = w["szczegoly"].get("sciezka")
            if w["rodzaj"] == "plik" and sciezka and w_katalogu(str(sciezka), u.root):
                zmiany_hosta.zapomnij(u, "plik", **w["szczegoly"])     # zniknie razem z korzeniem (docstring, 4)
        if not wpisy:
            self.podlog("dziennik pusty: Jarvo niczego nie zmieniał poza swoim katalogiem")
            return True
        raport = zmiany_hosta.cofnij(u, self.z.wykonaj, rejestr=self.ot.rejestr, log=self.podlog)
        self.raport["cofniete"] = raport
        bledy = [r["opis"] for r in raport if r["wynik"] == "blad"]
        self.bledy_dziennika = bledy
        if not bledy:
            return True
        self.podlog(f"nie cofnąłem {len(bledy)} zmian (opis wyżej)")
        if self.tak:
            return True
        return _tak(self.z.pytaj("Usunąć mimo to pliki Jarva? Tych zmian nie da się wtedy cofnąć poleceniem jarvo, "
                                 "tylko ręcznie. [t/N] "))

    def aplikacje(self) -> None:
        wpis = self.z.aplikacje(NAZWA_APLIKACJI)
        if wpis is None:
            self.podlog("brak wpisu")
            return
        if zawiera_sciezke(wpis.get("InstallLocation") or wpis.get("UninstallString") or "", self.u.root):
            self.z.usun_aplikacje(NAZWA_APLIKACJI)
            self.podlog(f"usunięty wpis {NAZWA_APLIKACJI}")
        else:
            self.podlog(f"wpis {NAZWA_APLIKACJI} nie wskazuje tej instalacji: zostaje")

    def klucz(self) -> None:
        """Klucz GitHuba `jarvo-github` w magazynie systemu (docstring modułu, krok 6): z --all znika, chyba że korzysta
        z niego inna instalacja Jarva na tym koncie. Bez --all zostaje razem z danymi."""
        self.klucz_github = bool(self.z.klucz_jest())
        if not self.klucz_github:
            self.podlog(f"brak klucza {MAGAZYN_KLUCZA} w magazynie systemu")
            return
        inna = inna_instalacja(self.u, self.ot.env)
        if not self.usun_dane:
            self.klucz_zostaje = "bez --all dane i klucz zostają"
        elif inna:
            self.klucz_zostaje = f"korzysta z niego też {inna}"
        if self.klucz_zostaje:
            self.podlog(f"klucz {MAGAZYN_KLUCZA} w magazynie systemu zostaje: {self.klucz_zostaje}")
            return
        if self.z.usun_klucz():
            self.klucz_github = False
            self.raport["usuniete"].append(f"magazyn systemu: {MAGAZYN_KLUCZA}")
            self.podlog(f"usunięty klucz {MAGAZYN_KLUCZA} z magazynu systemu")
        else:
            self.podlog(f"BŁĄD: klucz {MAGAZYN_KLUCZA} nie dał się usunąć z magazynu systemu (opis w skanie śladów)")

    def pliki(self) -> None:
        u = self.u
        if WINDOWS:
            python = _python_w_korzeniu(u)
            if python is not None:
                self.na_pozniej.append(python)
            if any(_klucz(p.program).endswith("\\cmd.exe") for p in self.lista if p.pid in self.pomin):
                self.na_pozniej.append(u.root / "bin")     # cmd.exe dokończy jarvo.cmd po końcu tego procesu
        cele = [u.program, u.stan, u.root / "bin", u.build, u.logi, u.cache]
        if self.usun_dane:
            cele.append(u.dane)
        with contextlib.suppress(OSError):
            cele += [Path(e.path) for e in os.scandir(u.root) if e.name.startswith(".doctor-")]
        for cel in cele:
            if not os.path.lexists(cel):
                continue
            bledy: list[str] = []
            pozniej = [p for p in self.na_pozniej if _klucz(p) == _klucz(cel) or w_katalogu(str(p), cel)]
            if pozniej and _klucz(pozniej[0]) == _klucz(cel):
                self.podlog(f"{cel}: usunie go proces sprzątający po zakończeniu tego polecenia")
                continue
            if usun_drzewo(cel, bledy, pomin=pozniej):
                self.raport["usuniete"].append(str(cel))
                self.podlog(f"usunięty {cel}")
            elif pozniej and not bledy:
                self.raport["usuniete"].append(str(cel))
                self.podlog(f"usunięty {cel} (poza {', '.join(str(p) for p in pozniej)}: usunie go proces "
                            "sprzątający)")
            else:
                self.bledy += bledy[:20]
                self.podlog(f"nie usunąłem wszystkiego z {cel}: {'; '.join(bledy[:3])}")
        self.raport["dane_usuniete"] = self.usun_dane and not u.dane.exists()
        if LINUX:                                       # katalogi XDG Jarva: ~/.local/state/jarvo bez logów
            for k in (u.logi.parent,):
                if k.name == "jarvo" and k.is_dir() and not _klucz(k).startswith(_klucz(u.root)):
                    with contextlib.suppress(OSError):
                        k.rmdir()
        if u.root.is_dir() and not self.na_pozniej:
            with contextlib.suppress(OSError):
                u.root.rmdir()                          # tylko pusty (bez danych i obcych plików)

    # -- koniec
    def _sprzatanie(self) -> None:
        """Windows: proces sprzątający dla `na_pozniej` (docstring modułu, krok 6): czeka na ten proces i na cmd.exe,
        który uruchomił jarvo.cmd z korzenia (`cmd /c …\\jarvo.cmd uninstall` kończy się zaraz po nas; terminal,
        w którym wpisano polecenie, zostaje i na niego nie czekamy)."""
        if not self.na_pozniej:
            return
        pidy = [self.z.pid]
        for p in self.lista:
            if (p.pid in self.pomin and p.pid != self.z.pid and _klucz(p.program).endswith("\\cmd.exe")
                    and zawiera_sciezke(p.polecenie, self.u.root)):
                pidy.append(p.pid)
        do_usuniecia = sorted({_klucz(p): p for p in [*self.na_pozniej, *([self.u.program] if
                                                                            self.u.program.exists() else [])]}.values(),
                              key=str)
        skrypt = skrypt_sprzatania(pidy, do_usuniecia, self.u.root, usun_korzen=not self.u.dane.exists(),
                                   znacznik=self.u.program / "current.json")
        system32 = Path(os.environ.get("SystemRoot") or "C:\\Windows") / "System32"
        try:
            pid = self.z.odlacz(argv_sprzatania(skrypt), cwd=str(system32))
            self.raport["sprzatanie"] = {"pid": pid, "czeka_na": pidy, "sciezki": [str(p) for p in do_usuniecia]}
            self.podlog(f"proces sprzątający (PID {pid}) usunie po zakończeniu tego polecenia: "
                        + ", ".join(str(p) for p in do_usuniecia))
        except OSError as e:
            self.raport["slady"].append({"rodzaj": "błąd", "opis": f"proces sprzątający nie wystartował ({e})",
                                         "rada": "Usuń ręcznie po zakończeniu tego polecenia: "
                                                 + ", ".join(str(p) for p in do_usuniecia)})

    def _skan_i_koniec(self, wynik: str) -> int:
        dane_zostaja = self.u.dane.exists() and not self.usun_dane
        skan = skan_sladow(self.u, self.ot, self.z, dane_zostaja=dane_zostaja, na_pozniej=self.na_pozniej,
                           pliki_rc=self.pliki_rc, bledy_dziennika=self.bledy_dziennika,
                           pomin=self.pomin or {self.z.pid}, klucz_github=self.klucz_github,
                           klucz_zostaje=self.klucz_zostaje)
        self.raport.update(skan)
        if wynik == "odinstalowane":
            self._sprzatanie()              # po skanie: proces sprzątający ma korzeń w wierszu polecenia
        for b in self.bledy:
            if not any(b in s["opis"] for s in skan["slady"]):
                self.raport["slady"].append({"rodzaj": "błąd", "opis": b, "rada": "Zobacz opis i usuń ręcznie."})
        w = []
        if wynik == "odinstalowane":
            w.append(f"Jarvo odinstalowane z {self.u.root}.")
        if self.raport["celowo"]:
            w.append("Zostaje celowo:")
            w += [f"  - {c['opis']}: {c['powod']}" for c in self.raport["celowo"]]
        if self.raport["slady"]:
            w.append("Ślady do usunięcia ręcznie:")
            w += [f"  - {s['opis']}. {s['rada']}" for s in self.raport["slady"]]
        else:
            w.append("Śladów Jarva na komputerze nie ma" + (" (poza tym, co zostaje celowo)."
                                                             if self.raport["celowo"] else "."))
        kod = 1 if self.raport["slady"] else 0
        return self._koniec(wynik, "\n".join(w), kod=kod)

    def _koniec(self, wynik: str, tekst: str, *, kod: int) -> int:
        self.raport["wynik"] = wynik
        self.raport["kod"] = kod
        self.raport["bledy"] = self.bledy
        for linia in tekst.splitlines():
            self.log(linia)
        return kod


def odinstaluj(u: Uklad, ot: Otoczenie | None = None, *, wszystko: bool = False, tak: bool = False,
               log: Callable[[str], None] | None = None, zaplecze: Zaplecze | None = None) -> tuple[int, dict]:
    """`jarvo uninstall`: (kod wyjścia, raport). 0 = odinstalowane bez śladów (albo anulowane), 1 = ślady, błąd albo
    odmowa. Raport: root, wynik, zatrzymane, cofniete (dziennik), usuniete, slady, celowo, sprzatanie, bledy."""
    ot = ot or Otoczenie()
    z = zaplecze or Zaplecze()
    u = instalator.bezwzgledny(uklad_instalacji(u, ot.env))
    przebieg = _Odinstalowanie(u, ot, z, log or _wypisz, wszystko=wszystko, tak=tak)
    with instalator._katalog_biezacy(Path.home()):       # bieżący katalog w korzeniu zablokowałby usunięcie (Windows)
        try:
            kod = przebieg.uruchom()
        except BladOdinstalowania as e:
            kod = przebieg._koniec("odmowa", f"BŁĄD: {e}", kod=1)
    return kod, przebieg.raport


def polecenie(u: Uklad, a, ot: Otoczenie, *, zaplecze: Zaplecze | None = None) -> int:
    """Wejście z jarvo/cli.py: `jarvo uninstall [--all] [--yes] [--json]`."""
    jako_json = bool(getattr(a, "json", False))
    kod, raport = odinstaluj(u, ot, wszystko=bool(getattr(a, "wszystko", False)), tak=bool(getattr(a, "tak", False)),
                             log=_na_stderr if jako_json else _wypisz, zaplecze=zaplecze)
    if jako_json:
        print(json.dumps(raport, ensure_ascii=False, indent=2), flush=True)
    return kod



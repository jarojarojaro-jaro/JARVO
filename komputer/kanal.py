"""Kanały usługi Komputera Jarva natywnie (docs/NATYWNIE.md J03, J09): MCP sterownika (`cua`) i sterowanie (`ster`).

Adres liczy się z samego korzenia Jarva (JARVO_ROOT), tym samym przepisem co kanał nadzorcy (16 znaków sha256
znormalizowanej ścieżki), więc bramka `jarvo_cua.py`, wtyczka Operatora i `jarvo komputer` trafiają w tę samą usługę
bez dodatkowych zmiennych:
  Windows  \\\\.\\pipe\\jarvo-komputer-cua-<skrót> i ...-ster-<skrót>: potok nazwany z DACL tylko dla bieżącego
           użytkownika (D:P(A;;GA;;;<SID>)), bez klientów zdalnych (PIPE_REJECT_REMOTE_CLIENTS), pierwsza instancja
           zakładana z FILE_FLAG_FIRST_PIPE_INSTANCE (cudzy potok o tej nazwie = usługa nie wstaje). Klient sprawdza,
           że potok trzyma proces usługi (GetNamedPipeServerProcessId = pid z `<stan>/komputer/usluga.json`).
  POSIX    `<stan>/komputer/cua.sock` i `ster.sock`, 0600 w katalogu 0700 (przy ścieżce ponad 100 bajtów katalog
           `jarvo-<uid>-<skrót>-k` w katalogu tymczasowym).
Strumień to bajty (wiersze JSON, jak gniazda Komputera w kontenerze). Na Windows wejście i wyjście idą przez I/O
z nakładaniem (overlapped), bo synchroniczny uchwyt potoku szereguje odczyt i zapis z dwóch wątków.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

WINDOWS = os.name == "nt"
MAKS_GNIAZDA = 100                       # sun_path: 104 bajty na macOS, 108 na Linuksie
BUFOR = 1 << 16


class BladKanalu(OSError):
    """Kanał usługi nie odpowiada albo należy do innego procesu (komunikat po polsku)."""


def skrot(root: str | os.PathLike) -> str:
    """16 znaków sha256 znormalizowanej ścieżki korzenia (jak jarvo/nadzorca.py `_skrot`)."""
    norm = os.path.normcase(str(Path(root).expanduser().resolve(strict=False)))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def katalog_stanu(root: str | os.PathLike) -> Path:
    """`<stan>/komputer` (stan = <root>/stan, docs/NATYWNIE.md c1)."""
    return Path(root) / "stan" / "komputer"


def adres(root: str | os.PathLike, nazwa: str) -> str:
    """Adres kanału `nazwa` ("cua" albo "ster") usługi Komputera tego korzenia."""
    if nazwa not in ("cua", "ster"):
        raise ValueError(nazwa)
    s = skrot(root)
    if WINDOWS:
        return rf"\\.\pipe\jarvo-komputer-{nazwa}-{s}"
    p = katalog_stanu(root) / f"{nazwa}.sock"
    if len(os.fsencode(str(p))) <= MAKS_GNIAZDA:
        return str(p)
    for baza in (tempfile.gettempdir(), "/tmp"):
        p = Path(baza) / f"jarvo-{os.getuid()}-{s}-k" / f"{nazwa}.sock"
        if len(os.fsencode(str(p))) <= MAKS_GNIAZDA:
            break
    return str(p)


def pid_uslugi(root: str | os.PathLike) -> int | None:
    """PID usługi z `<stan>/komputer/usluga.json` (zapisuje go usługa po starcie), albo None."""
    try:
        dane = json.loads((katalog_stanu(root) / "usluga.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = dane.get("pid") if isinstance(dane, dict) else None
    return pid if isinstance(pid, int) and pid > 0 else None


# --------------------------------------------------------------------------- Windows: potoki przez ctypes i _winapi

if WINDOWS:
    import ctypes
    import _winapi
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _NIEWAZNY = ctypes.c_void_p(-1).value
    _BLAD_POTOKU = (109, 232, 233, 995)         # BROKEN_PIPE, NO_DATA, PIPE_NOT_CONNECTED, OPERATION_ABORTED

    class _SA(ctypes.Structure):                 # SECURITY_ATTRIBUTES
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    for _f, _wynik, _arg in (
            ("CreateNamedPipeW", wintypes.HANDLE, [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                                   wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                                   ctypes.POINTER(_SA)]),
            ("GetNamedPipeServerProcessId", wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]),
            ("GetNamedPipeClientProcessId", wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]),
            ("GetCurrentProcess", wintypes.HANDLE, []),
            ("LocalFree", wintypes.HLOCAL, [wintypes.HLOCAL]),
            ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE])):
        getattr(_k32, _f).restype, getattr(_k32, _f).argtypes = _wynik, _arg
    for _f, _wynik, _arg in (
            ("OpenProcessToken", wintypes.BOOL, [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]),
            ("GetTokenInformation", wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                                    ctypes.POINTER(wintypes.DWORD)]),
            ("ConvertSidToStringSidW", wintypes.BOOL, [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]),
            ("ConvertStringSecurityDescriptorToSecurityDescriptorW", wintypes.BOOL,
             [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.ULONG)])):
        getattr(_adv, _f).restype, getattr(_adv, _f).argtypes = _wynik, _arg

    def sid_uzytkownika() -> str | None:
        """SID bieżącego użytkownika (z tokenu procesu), np. S-1-5-21-…, albo None."""
        token = wintypes.HANDLE()
        if not _adv.OpenProcessToken(_k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):     # TOKEN_QUERY
            return None
        try:
            n = wintypes.DWORD()
            _adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(n))                         # TokenUser
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

    def _czekaj(ov, czas: float | None) -> None:
        """Czeka na operację z nakładaniem; po `czas` sekundach anuluje ją i rzuca TimeoutError."""
        ms = 0xFFFFFFFF if czas is None else max(0, int(czas * 1000))
        wynik = _winapi.WaitForMultipleObjects([ov.event], False, ms)
        if wynik == 0x102:                       # WAIT_TIMEOUT
            ov.cancel()
            try:
                ov.GetOverlappedResult(True)
            except OSError:
                pass
            raise TimeoutError("kanał Komputera: brak danych w terminie")

    class _UchwytPotoku:
        """Strumień bajtów na uchwycie potoku (overlapped): recv, sendall, settimeout, shutdown, close."""

        def __init__(self, h: int):
            self._h = h
            self._czas: float | None = None
            self._lock = threading.Lock()

        def settimeout(self, czas: float | None) -> None:
            self._czas = czas

        def recv(self, n: int = BUFOR) -> bytes:
            if self._h is None:
                return b""
            try:
                ov, err = _winapi.ReadFile(self._h, n, overlapped=True)
            except OSError as e:
                if getattr(e, "winerror", None) in _BLAD_POTOKU:
                    return b""
                raise
            try:
                if err == _winapi.ERROR_IO_PENDING:
                    _czekaj(ov, self._czas)
                przeczytane, err = ov.GetOverlappedResult(True)
            except OSError as e:
                if getattr(e, "winerror", None) in _BLAD_POTOKU:
                    return b""
                raise
            if err in _BLAD_POTOKU:
                return b""
            return bytes(ov.getbuffer())[:przeczytane]

        def sendall(self, dane: bytes) -> None:
            widok = memoryview(dane)
            with self._lock:
                while widok:
                    if self._h is None:
                        raise BrokenPipeError("kanał Komputera zamknięty")
                    try:
                        ov, err = _winapi.WriteFile(self._h, bytes(widok[:BUFOR]), overlapped=True)
                        if err == _winapi.ERROR_IO_PENDING:
                            _czekaj(ov, None if self._czas is None else max(self._czas, 30.0))
                        zapisane, err = ov.GetOverlappedResult(True)
                    except OSError as e:
                        if getattr(e, "winerror", None) in _BLAD_POTOKU:
                            raise BrokenPipeError("kanał Komputera zamknięty") from None
                        raise
                    if err:
                        raise BrokenPipeError(f"kanał Komputera: błąd zapisu {err}")
                    widok = widok[zapisane:]

        def shutdown(self, _how=None) -> None:
            """Potok nie ma półzamknięcia: koniec pisania = nic (zamyka dopiero close)."""

        def pid_drugiej_strony(self, serwer: bool) -> int | None:
            pid = wintypes.ULONG()
            f = _k32.GetNamedPipeServerProcessId if serwer else _k32.GetNamedPipeClientProcessId
            return pid.value if self._h is not None and f(self._h, ctypes.byref(pid)) else None

        def close(self) -> None:
            h, self._h = self._h, None
            if h is not None:
                try:
                    _winapi.CloseHandle(h)
                except OSError:
                    pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()


def _przygotuj_katalog_gniazda(sciezka: Path) -> None:
    """Katalog gniazda 0700, nasz i nie dowiązanie (krótka ścieżka bywa we wspólnym katalogu tymczasowym)."""
    katalog = sciezka.parent
    katalog.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = os.lstat(katalog)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise BladKanalu(f"Katalog gniazda Komputera {katalog} nie należy do bieżącego użytkownika.")
    os.chmod(katalog, 0o700)
    if os.path.lexists(sciezka):             # usługa trzyma blokadę korzenia, więc stare gniazdo jest martwe
        os.unlink(sciezka)


class Serwer:
    """Słuchacz kanału: każde połączenie trafia do `obsluga(strumien)` w osobnym wątku."""

    def __init__(self, adres_kanalu: str, obsluga: Callable, nazwa: str = "kanal"):
        self.adres, self.obsluga, self.nazwa = adres_kanalu, obsluga, nazwa
        self._stop = threading.Event()
        self._watek: threading.Thread | None = None
        self._gniazdo: socket.socket | None = None
        self.dacl = True
        self._sa = self._sd = None

    # --- start i pętla

    def start(self) -> "Serwer":
        if WINDOWS:
            self._przygotuj_dacl()
            h = self._nowa_instancja(pierwsza=True)       # cudzy potok o tej nazwie: błąd teraz, nie później
            self._watek = threading.Thread(target=self._petla_windows, args=(h,), daemon=True,
                                           name=f"kanal-{self.nazwa}")
        else:
            sciezka = Path(self.adres)
            _przygotuj_katalog_gniazda(sciezka)
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            stara = os.umask(0o177)
            try:
                s.bind(self.adres)
                os.chmod(self.adres, 0o600)
                s.listen(16)
                s.settimeout(0.5)
            except BaseException:
                s.close()
                raise
            finally:
                os.umask(stara)
            self._gniazdo = s
            self._watek = threading.Thread(target=self._petla_posix, daemon=True, name=f"kanal-{self.nazwa}")
        self._watek.start()
        return self

    def _przygotuj_dacl(self) -> None:
        sid = sid_uzytkownika()
        sd = wintypes.LPVOID()
        if sid and _adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(f"D:P(A;;GA;;;{sid})", 1,
                                                                             ctypes.byref(sd), None):
            self._sd = sd
            self._sa = _SA(ctypes.sizeof(_SA), sd.value, False)
        else:
            self.dacl = False

    def _nowa_instancja(self, pierwsza: bool = False) -> int:
        tryb_otwarcia = 0x00000003 | 0x40000000 | (0x00080000 if pierwsza else 0)  # DUPLEX, OVERLAPPED, FIRST
        tryb = 0x00000000 | 0x00000000 | 0x00000008                              # BYTE, READMODE_BYTE, REJECT_REMOTE
        h = _k32.CreateNamedPipeW(self.adres, tryb_otwarcia, tryb, 255, BUFOR, BUFOR, 0,
                                  ctypes.byref(self._sa) if self._sa is not None else None)
        if not h or h == _NIEWAZNY:
            blad = ctypes.get_last_error()
            if pierwsza and blad in (5, 231):       # ACCESS_DENIED, PIPE_BUSY: potok o tej nazwie ma ktoś inny
                raise BladKanalu(f"Potok {self.adres} już istnieje (inna usługa Komputera albo obcy program).")
            raise ctypes.WinError(blad)
        return h

    def _czekaj_na_klienta(self, h: int) -> bool | None:
        """ConnectNamedPipe z nakładaniem: True = klient połączony, False = nieudane połączenie (nowa instancja),
        None = kanał się zamyka."""
        try:
            ov = _winapi.ConnectNamedPipe(h, overlapped=True)
        except OSError as e:
            return True if getattr(e, "winerror", None) == 535 else False    # 535: klient był przed nami
        while not self._stop.is_set():
            if _winapi.WaitForMultipleObjects([ov.event], False, 500) != 0x102:
                try:
                    _, err = ov.GetOverlappedResult(True)
                except OSError as e:
                    err = getattr(e, "winerror", 1)
                return err in (0, 535)
        ov.cancel()
        try:
            ov.GetOverlappedResult(True)
        except OSError:
            pass
        return None

    def _instancja_z_ponowieniem(self) -> int | None:
        for _ in range(20):
            try:
                return self._nowa_instancja()
            except OSError:
                if self._stop.is_set():
                    return None
                time.sleep(0.05)
        return None

    def _petla_windows(self, h: int | None) -> None:
        try:
            while h is not None and not self._stop.is_set():
                polaczony = self._czekaj_na_klienta(h)
                if polaczony is None:
                    break
                if not polaczony:                  # klient zniknął w trakcie łączenia: ta instancja do wyrzucenia
                    _winapi.CloseHandle(h)
                    h = self._instancja_z_ponowieniem()
                    continue
                # następna instancja PRZED obsługą tej: nazwa potoku nie znika ani na chwilę, więc klient, który
                # przyjdzie w tym czasie, czeka (PIPE_BUSY) zamiast dostać „nie ma usługi”
                nastepny = self._instancja_z_ponowieniem()
                threading.Thread(target=self._obsluz, args=(_UchwytPotoku(h),), daemon=True,
                                 name=f"kanal-{self.nazwa}-klient").start()
                h = nastepny
        finally:
            if h is not None:
                try:
                    _winapi.CloseHandle(h)
                except OSError:
                    pass

    def _petla_posix(self) -> None:
        while not self._stop.is_set():
            try:
                klient, _ = self._gniazdo.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                if self._stop.is_set():
                    return
                time.sleep(0.05)
                continue
            klient.setblocking(True)
            threading.Thread(target=self._obsluz, args=(klient,), daemon=True,
                             name=f"kanal-{self.nazwa}-klient").start()

    def _obsluz(self, strumien) -> None:
        try:
            self.obsluga(strumien)
        except Exception:  # noqa: BLE001 - jedno połączenie nie zatrzymuje kanału
            try:
                strumien.close()
            except OSError:
                pass

    def zamknij(self) -> None:
        self._stop.set()
        if self._watek is not None:
            self._watek.join(3.0)
        if self._gniazdo is not None:
            try:
                self._gniazdo.close()
            finally:
                try:
                    os.unlink(self.adres)
                except OSError:
                    pass
        if WINDOWS and self._sd is not None:
            _k32.LocalFree(self._sd)
            self._sd = self._sa = None


def pid_klienta(strumien) -> int | None:
    """PID procesu po drugiej stronie połączenia przyjętego przez Serwer (do dziennika; None, gdy nie wiadomo)."""
    if WINDOWS:
        return strumien.pid_drugiej_strony(serwer=False) if hasattr(strumien, "pid_drugiej_strony") else None
    try:
        import struct
        if hasattr(socket, "SO_PEERCRED"):
            pid, _, _ = struct.unpack("3i", strumien.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                                struct.calcsize("3i")))
            return pid
    except OSError:
        pass
    return None


def polacz(adres_kanalu: str, czas: float = 5.0, oczekiwany_pid: int | None = None):
    """Połączenie z kanałem usługi (strumień z recv/sendall/settimeout/close). BladKanalu, gdy usługi nie ma
    albo potok trzyma inny proces niż `oczekiwany_pid` (Windows)."""
    koniec = time.monotonic() + czas
    if WINDOWS:
        brak_od = None
        while True:
            try:
                _winapi.WaitNamedPipe(adres_kanalu, max(1, min(1000, int((koniec - time.monotonic()) * 1000))))
                h = _winapi.CreateFile(adres_kanalu, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE, 0, _winapi.NULL,
                                       _winapi.OPEN_EXISTING, _winapi.FILE_FLAG_OVERLAPPED, _winapi.NULL)
                break
            except OSError as e:
                if getattr(e, "winerror", None) in (2, 3):          # FILE_NOT_FOUND, PATH_NOT_FOUND
                    brak_od = brak_od or time.monotonic()
                    if time.monotonic() - brak_od > 0.3 or time.monotonic() >= koniec:
                        raise BladKanalu("Komputer Jarva nie działa (brak kanału usługi).") from None
                    time.sleep(0.03)
                    continue
                if e.winerror not in (_winapi.ERROR_SEM_TIMEOUT, _winapi.ERROR_PIPE_BUSY) \
                        or time.monotonic() >= koniec:
                    raise BladKanalu(f"Kanał Komputera nie odpowiada ({e.strerror or e}).") from None
        strumien = _UchwytPotoku(h)
        if oczekiwany_pid is not None:
            pid = strumien.pid_drugiej_strony(serwer=True)
            if pid != oczekiwany_pid:
                strumien.close()
                raise BladKanalu(f"Potok Komputera trzyma inny proces (PID {pid}) niż usługa Jarva "
                                 f"(PID {oczekiwany_pid}): połączenie przerwane.")
        strumien.settimeout(max(0.05, koniec - time.monotonic()) if czas else None)
        return strumien
    if not os.path.exists(adres_kanalu):
        raise BladKanalu("Komputer Jarva nie działa (brak gniazda usługi).")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(max(czas, 0.05))
        s.connect(adres_kanalu)
    except OSError as e:
        s.close()
        raise BladKanalu(f"Kanał Komputera nie odpowiada ({e.strerror or e}).") from None
    return s


def czytaj_wiersz(strumien, maks: int = 1 << 20) -> bytes:
    """Jeden wiersz (bez końca wiersza) albo to, co przyszło przed zamknięciem połączenia."""
    czesci, razem = [], 0
    while razem < maks:
        k = strumien.recv(BUFOR)
        if not k:
            break
        czesci.append(k)
        razem += len(k)
        if b"\n" in k:
            break
    return b"".join(czesci).split(b"\n", 1)[0]


def zapytaj(adres_kanalu: str, polecenie: dict, czas: float = 5.0, oczekiwany_pid: int | None = None,
            maks: int = 1 << 20) -> dict:
    """Jedno polecenie JSON na kanale `ster` i odpowiedź (słownik). `maks`: najdłuższa odpowiedź w bajtach (klatka
    podglądu bywa większa niż 1 MB)."""
    s = polacz(adres_kanalu, czas, oczekiwany_pid)
    try:
        s.settimeout(czas)
        s.sendall((json.dumps(polecenie, ensure_ascii=False) + "\n").encode("utf-8"))
        linia = czytaj_wiersz(s, maks)
    except (TimeoutError, socket.timeout):
        raise BladKanalu(f"Komputer nie odpowiedział w {czas:g} s.") from None
    except OSError as e:
        raise BladKanalu(f"Kanał Komputera przerwany ({e.strerror or e}).") from None
    finally:
        s.close()
    try:
        odp = json.loads(linia or b"{}")
    except ValueError:
        raise BladKanalu("Komputer odpowiedział nie po JSON-owemu.") from None
    return odp if isinstance(odp, dict) else {"ok": False, "blad": "zła odpowiedź"}

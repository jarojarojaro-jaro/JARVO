"""Chrome DevTools Protocol przez potok, bez zależności (Komputer Jarva natywnie, docs/NATYWNIE.md J02).

Przeglądarka nie słucha na żadnym porcie: rozmowę CDP ma tylko proces, który ją uruchomił (usługa Komputera), więc
inny program właściciela ani agent z terminalem nie podłączy się do niej po TCP (decyzja I18, deny J17 dla
`--remote-debugging-port`). Wiadomości to JSON zakończony bajtem NUL (format `--remote-debugging-pipe`).

- Windows: dwa anonimowe potoki; uchwyty dziedziczy tylko przeglądarka (lista STARTUPINFO `handle_list`), a dostaje
  je w `--remote-debugging-io-pipes=<odczyt>,<zapis>` (sprawdzone na Chrome for Testing 153: Browser.getVersion
  przez potok, bez portu).
- POSIX: `os.posix_spawn` z dup2 na deskryptory 3 (polecenia) i 4 (odpowiedzi), których oczekuje
  `--remote-debugging-pipe`; przeglądarka we własnej grupie procesów (zatrzymanie całej grupy). posix_spawn nie zamyka
  innych deskryptorów, więc te, które proces dostał od rodzica bez CLOEXEC (runner CI, terminal), dostają CLOEXEC
  przed startem: przeglądarka ma tylko 0–4.

Wątek czytający rozdziela odpowiedzi (po `id`) i zdarzenia; zdarzenia idą do słuchaczy z osobnego wątku, więc
słuchacz może sam wysłać polecenie i czekać na odpowiedź.
"""
from __future__ import annotations

import itertools
import json
import os
import queue
import signal
import subprocess
import threading
import time
from typing import Any, Callable

WINDOWS = os.name == "nt"
MAKS_WIADOMOSC = 64 << 20          # zrzut ekranu w base64 bywa duży; większa wiadomość = błąd protokołu
CZAS_POLECENIA = 30.0


class BladCDP(RuntimeError):
    """Przeglądarka odrzuciła polecenie (kod i komunikat CDP) albo nie odpowiedziała."""

    def __init__(self, metoda: str, tekst: str, kod: int | None = None):
        super().__init__(f"{metoda}: {tekst}")
        self.metoda, self.tekst, self.kod = metoda, tekst, kod


class KoniecPrzegladarki(BladCDP):
    """Potok CDP się zamknął: przeglądarka skończyła pracę albo padła."""


class _ProcesPosix:
    """Minimalny odpowiednik Popen dla procesu z posix_spawn (pid, poll, wait, terminate, kill)."""

    def __init__(self, pid: int):
        self.pid = pid
        self.returncode: int | None = None
        self._lock = threading.Lock()

    def poll(self) -> int | None:
        with self._lock:
            if self.returncode is None:
                try:
                    pid, status = os.waitpid(self.pid, os.WNOHANG)
                except ChildProcessError:
                    self.returncode = -1
                    return self.returncode
                if pid:
                    self.returncode = os.waitstatus_to_exitcode(status)
            return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        koniec = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if koniec is not None and time.monotonic() >= koniec:
                raise subprocess.TimeoutExpired("przeglądarka", timeout)
            time.sleep(0.05)
        return self.returncode

    def _sygnal(self, sygnal: int) -> None:
        if self.poll() is not None:
            return
        try:
            os.killpg(self.pid, sygnal)               # cała grupa: renderery i GPU razem z przeglądarką
        except OSError:
            try:
                os.kill(self.pid, sygnal)
            except OSError:
                pass

    def terminate(self) -> None:
        self._sygnal(signal.SIGTERM)

    def kill(self) -> None:
        self._sygnal(signal.SIGKILL)


def _wyzej(fd: int) -> int:
    """Kopia deskryptora o numerze ≥ 10 (z CLOEXEC), żeby dup2 na 3 i 4 zawsze tworzył nowy deskryptor."""
    import fcntl
    nowy = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
    os.close(fd)
    return nowy


def _bez_dziedziczenia() -> None:
    """CLOEXEC na każdym deskryptorze ≥ 3 tego procesu. Własne deskryptory Pythona już go mają (PEP 446), ale te
    odziedziczone od rodzica bez niego (CI: 142–145 od runnera) posix_spawn przekazałby przeglądarce."""
    for katalog in ("/proc/self/fd", "/dev/fd"):
        try:
            fds = [int(x) for x in os.listdir(katalog)]
        except (OSError, ValueError):
            continue
        for fd in fds:
            try:
                if fd > 2 and os.get_inheritable(fd):
                    os.set_inheritable(fd, False)
            except OSError:
                pass                      # deskryptor katalogu z listdir, już zamknięty
        return


def _uruchom_posix(program: str, argv: list[str], env: dict, log) -> tuple[_ProcesPosix, int, int]:
    """Przeglądarka z poleceniami na fd 3 i odpowiedziami na fd 4."""
    _bez_dziedziczenia()
    r_pol, w_pol = os.pipe()          # rodzic pisze polecenia, dziecko czyta (3)
    r_odp, w_odp = os.pipe()          # dziecko pisze odpowiedzi (4), rodzic czyta
    r_pol, w_odp = _wyzej(r_pol), _wyzej(w_odp)
    akcje: list[tuple] = [(os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0),
                          (os.POSIX_SPAWN_DUP2, r_pol, 3), (os.POSIX_SPAWN_DUP2, w_odp, 4)]
    log_fd = None
    if log is not None:
        log_fd = _wyzej(os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
        akcje += [(os.POSIX_SPAWN_DUP2, log_fd, 1), (os.POSIX_SPAWN_DUP2, log_fd, 2)]
    else:
        akcje += [(os.POSIX_SPAWN_OPEN, 1, os.devnull, os.O_WRONLY, 0),
                  (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0)]
    try:
        pid = os.posix_spawn(program, argv, env, file_actions=akcje, setpgroup=0)
    finally:
        for fd in (r_pol, w_odp, log_fd):
            if fd is not None:
                os.close(fd)
    return _ProcesPosix(pid), r_odp, w_pol


def _uruchom_windows(program: str, argv: list[str], env: dict, log) -> tuple[subprocess.Popen, int, int]:
    import msvcrt
    r_pol, w_pol = os.pipe()
    r_odp, w_odp = os.pipe()
    h_czyt, h_pisz = msvcrt.get_osfhandle(r_pol), msvcrt.get_osfhandle(w_odp)
    os.set_handle_inheritable(h_czyt, True)
    os.set_handle_inheritable(h_pisz, True)
    si = subprocess.STARTUPINFO()
    si.lpAttributeList = {"handle_list": [h_czyt, h_pisz]}       # dziedziczą tylko te dwa uchwyty (i standardowe)
    argv = [argv[0], f"--remote-debugging-io-pipes={h_czyt},{h_pisz}", *argv[1:]]
    wyjscie = open(log, "ab") if log is not None else subprocess.DEVNULL
    flagi = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        proces = subprocess.Popen(argv, executable=program, env=env, startupinfo=si, close_fds=True,
                                  stdin=subprocess.DEVNULL, stdout=wyjscie, stderr=wyjscie, creationflags=flagi)
    finally:
        os.close(r_pol)
        os.close(w_odp)
        if wyjscie is not subprocess.DEVNULL:
            wyjscie.close()
    return proces, r_odp, w_pol


class Oczekiwanie:
    """Wysłane polecenie CDP; `wynik(czas)` czeka na odpowiedź (BladCDP przy błędzie albo braku odpowiedzi)."""

    def __init__(self, przegladarka: "Przegladarka", ident: int, metoda: str, gotowe: threading.Event):
        self._p, self._ident, self.metoda, self._gotowe = przegladarka, ident, metoda, gotowe
        self._wynik: dict | None = None

    def wynik(self, czas: float | None = None) -> dict:
        if self._wynik is None:
            self._wynik = self._p._odbierz(self._ident, self.metoda, self._gotowe, czas)
        return self._wynik

    def gotowe(self, czas: float = 0.0) -> bool:
        """Czy przyszła odpowiedź (czeka najwyżej `czas` sekund)."""
        return self._gotowe.wait(czas)


class Przegladarka:
    """Uruchomiona przeglądarka i jej potok CDP. `wyslij` czeka na odpowiedź; `sluchaj` dodaje słuchacza zdarzeń
    (metoda, params, sesja). Sesje celów (flatten) podaje się w `sesja`."""

    def __init__(self, program: str, argumenty: list[str], *, env: dict | None = None, log=None,
                 czas_polecenia: float = CZAS_POLECENIA):
        self.program = str(program)
        self.argumenty = ["--remote-debugging-pipe", *argumenty]
        self.env = dict(os.environ if env is None else env)
        self.log = log
        self.czas_polecenia = czas_polecenia
        self.proces = None
        self._czyt = self._pisz = -1
        self._ids = itertools.count(1)
        self._czeka: dict[int, list] = {}
        self._lock = threading.Lock()
        self._lock_pisz = threading.Lock()
        self._sluchacze: list[Callable[[str, dict, str | None], None]] = []
        self._zdarzenia: queue.Queue = queue.Queue()
        self._koniec = threading.Event()

    @property
    def pid(self) -> int | None:
        return getattr(self.proces, "pid", None)

    def start(self) -> "Przegladarka":
        argv = [self.program, *self.argumenty]
        if WINDOWS:
            self.proces, self._czyt, self._pisz = _uruchom_windows(self.program, argv, self.env, self.log)
        else:
            self.proces, self._czyt, self._pisz = _uruchom_posix(self.program, argv, self.env, self.log)
        threading.Thread(target=self._czytaj, name="cdp-czytnik", daemon=True).start()
        threading.Thread(target=self._rozsylaj, name="cdp-zdarzenia", daemon=True).start()
        return self

    def dziala(self) -> bool:
        return not self._koniec.is_set() and self.proces is not None and self.proces.poll() is None

    def sluchaj(self, sluchacz: Callable[[str, dict, str | None], None]) -> None:
        self._sluchacze.append(sluchacz)

    # --- wysyłanie

    def _zapisz(self, dane: bytes) -> None:
        with self._lock_pisz:
            widok = memoryview(dane)
            while widok:
                n = os.write(self._pisz, widok)
                widok = widok[n:]

    def wyslij(self, metoda: str, params: dict | None = None, sesja: str | None = None,
               czas: float | None = None) -> dict:
        """Polecenie CDP i jego wynik; BladCDP przy błędzie albo braku odpowiedzi w `czas` sekund."""
        return self.nadaj(metoda, params, sesja).wynik(czas)

    def nadaj(self, metoda: str, params: dict | None = None, sesja: str | None = None) -> "Oczekiwanie":
        """Polecenie CDP bez czekania na odpowiedź (wynik później: `.wynik()`). Cel wstrzymany na starcie
        (waitForDebuggerOnStart) nie odpowiada np. na Page.enable przed Runtime.runIfWaitingForDebugger, więc
        przygotowanie celu wysyła wszystko naraz i dopiero potem czeka."""
        if self._koniec.is_set():
            raise KoniecPrzegladarki(metoda, "przeglądarka nie działa")
        ident = next(self._ids)
        wiadomosc: dict[str, Any] = {"id": ident, "method": metoda, "params": params or {}}
        if sesja:
            wiadomosc["sessionId"] = sesja
        gotowe = threading.Event()
        with self._lock:
            self._czeka[ident] = [gotowe, None]
        try:
            self._zapisz(json.dumps(wiadomosc, ensure_ascii=False).encode("utf-8") + b"\0")
        except OSError as e:
            with self._lock:
                self._czeka.pop(ident, None)
            raise KoniecPrzegladarki(metoda, f"potok CDP zamknięty ({e.strerror or e})") from None
        return Oczekiwanie(self, ident, metoda, gotowe)

    def _odbierz(self, ident: int, metoda: str, gotowe: threading.Event, czas: float | None) -> dict:
        if not gotowe.wait(self.czas_polecenia if czas is None else czas):
            with self._lock:
                self._czeka.pop(ident, None)
            raise BladCDP(metoda, "przeglądarka nie odpowiedziała w czasie")
        with self._lock:
            odp = self._czeka.pop(ident, [None, None])[1]
        if odp is None:
            raise KoniecPrzegladarki(metoda, "przeglądarka zakończyła pracę")
        if "error" in odp:
            blad = odp["error"] if isinstance(odp["error"], dict) else {}
            raise BladCDP(metoda, str(blad.get("message") or "błąd"), blad.get("code"))
        return odp.get("result") or {}

    # --- odbieranie

    def _czytaj(self) -> None:
        bufor = b""
        try:
            while True:
                kawalek = os.read(self._czyt, 1 << 20)
                if not kawalek:
                    break
                bufor += kawalek
                while b"\0" in bufor:
                    linia, bufor = bufor.split(b"\0", 1)
                    self._wiadomosc(linia)
                if len(bufor) > MAKS_WIADOMOSC:
                    break
        except OSError:
            pass
        finally:
            self._koniec.set()
            with self._lock:
                czekajace = list(self._czeka.values())
            for wpis in czekajace:
                wpis[0].set()                        # odpowiedź None = koniec przeglądarki
            self._zdarzenia.put(None)

    def _wiadomosc(self, linia: bytes) -> None:
        try:
            msg = json.loads(linia)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(msg, dict):
            return
        if "id" in msg:
            with self._lock:
                wpis = self._czeka.get(msg["id"])
                if wpis is not None:
                    wpis[1] = msg
                    wpis[0].set()
            return
        if isinstance(msg.get("method"), str):
            self._zdarzenia.put((msg["method"], msg.get("params") or {}, msg.get("sessionId")))

    def _rozsylaj(self) -> None:
        while True:
            zdarzenie = self._zdarzenia.get()
            if zdarzenie is None:
                return
            for sluchacz in list(self._sluchacze):
                try:
                    sluchacz(*zdarzenie)
                except Exception:  # noqa: BLE001 - słuchacz nie może zatrzymać rozsyłania zdarzeń
                    pass

    # --- zatrzymanie

    def zamknij(self, czas: float = 10.0) -> int | None:
        """Browser.close, a po `czas` sekundach zabicie (POSIX: cała grupa procesów)."""
        if self.proces is None:
            return None
        if self.proces.poll() is None and not self._koniec.is_set():
            try:
                self.wyslij("Browser.close", czas=min(czas, 5.0))
            except BladCDP:
                pass
        try:
            self.proces.wait(timeout=czas)
        except subprocess.TimeoutExpired:
            self.proces.kill()
            try:
                self.proces.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        for fd in (self._czyt, self._pisz):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._czyt = self._pisz = -1
        return self.proces.poll()

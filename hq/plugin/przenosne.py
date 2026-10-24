"""Przenośne pomocniki wtyczki HQ (docs/NATYWNIE.md, etap E1: W06, W07, W09): ten sam kod w kontenerze (Linux),
na macOS i na Windows; na Linuksie zachowanie bez zmian.

- **Podprocesy w wątkach** (`uruchom`): dashboard Hermesa na Windows działa na SelectorEventLoop, a tam
  `asyncio.create_subprocess_exec` rzuca NotImplementedError. Program biegnie więc w `subprocess.Popen`, a pętla
  czeka na wątek (`asyncio.to_thread`). Limit czasu kończy się `asyncio.TimeoutError` (jak `asyncio.wait_for`)
  po zabiciu programu i czekaniu na jego koniec; anulowane zadanie też zabija program (`zabij`: SIGKILL na POSIX,
  TerminateProcess na Windows). Na Windows bez okna konsoli (CREATE_NO_WINDOW).
- **Blokada między procesami** (`zamek`): wyłączna blokada pliku (fcntl.flock na POSIX, msvcrt.locking na
  Windows); dashboard i agenci (scripts/jarvo_link.py) dopisują do tych samych plików stanu. `zastap`: os.replace
  z ponawianiem na Windows, gdzie czytany właśnie plik nie da się podmienić (WinError 5/32).
- **Plik tylko dla właściciela** (`tryb_pliku`): na POSIX chmod jak dotąd. Na Windows os.chmod ustawia tylko
  „tylko do odczytu”, więc tryb bez praw grupy i innych (0600) zdejmuje z pliku wpisy dziedziczone i daje
  właścicielowi pełny dostęp (`icacls`, wbudowany w system, bez nowych paczek); wpisy SYSTEM i Administratorzy
  z domyślnej listy procesu zostają, jak przy kluczach OpenSSH. To ochrona pomocnicza: błąd icacls nie zatrzymuje
  zapisu. `tylko_dla_wlasciciela` sprawdza wynik (testy).
Testy: tests/test_hq_core.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Iterator, Sequence

WINDOWS = os.name == "nt"
PIPE, STDOUT, DEVNULL = subprocess.PIPE, subprocess.STDOUT, subprocess.DEVNULL
# Windows: programy z dashboardu (ffmpeg, jarvo-tts, hermes) bez własnego okna konsoli
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0
ZAMEK_CO_S = 0.05            # Windows: co tyle ponawiamy zajętą blokadę (msvcrt nie ma czekania bez limitu)


# ----------------------------------------------------------------------------------------------- podprocesy

def popen(argv: Sequence, **kw) -> subprocess.Popen:
    """subprocess.Popen; na Windows bez okna konsoli."""
    if BEZ_OKNA:
        kw["creationflags"] = kw.get("creationflags", 0) | BEZ_OKNA
    return subprocess.Popen(list(argv), **kw)


def zabij(proc: subprocess.Popen) -> None:
    """Koniec programu bez czekania (SIGKILL na POSIX, TerminateProcess na Windows); zakończony pomija."""
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:                  # skończył się między poll() a kill()
            pass


def _zbierz(proc: subprocess.Popen, na_linie: Callable[[bytes], None] | None) -> tuple[int, bytes, bytes]:
    """W wątku: wyjście programu do końca. Z `na_linie` stdout linia po linii, stderr w osobnym wątku (pełny potok
    zatrzymałby program w pół linii postępu)."""
    if na_linie is None:
        out, err = proc.communicate()
        return proc.returncode, out or b"", err or b""
    bledy: list[bytes] = []
    watek = None
    if proc.stderr is not None:
        watek = threading.Thread(target=lambda: bledy.append(proc.stderr.read()), daemon=True)
        watek.start()
    with proc.stdout:
        for linia in proc.stdout:
            na_linie(linia)
    kod = proc.wait()
    if watek is not None:
        watek.join()
        proc.stderr.close()
    return kod, b"", b"".join(bledy)


async def uruchom(argv: Sequence, *, timeout: float | None = None, stdin=None, stdout=PIPE, stderr=PIPE,
                  na_linie: Callable[[bytes], None] | None = None,
                  przy_starcie: Callable[[subprocess.Popen], None] | None = None) -> tuple[int, bytes, bytes]:
    """Program w wątku → (kod, stdout, stderr) w bajtach (bez PIPE: puste). `na_linie(bajty)`: stdout czytany linia
    po linii (postęp ffmpeg `-progress pipe:1`), w wyniku pusty. `przy_starcie(proc)`: uchwyt programu, np. do
    przerwania z innej trasy (`zabij`). Brak programu = OSError od razu, jak przy asyncio."""
    proc = popen(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    try:
        if przy_starcie is not None:
            przy_starcie(proc)
        return await asyncio.wait_for(asyncio.to_thread(_zbierz, proc, na_linie), timeout)
    except asyncio.TimeoutError:
        zabij(proc)
        await asyncio.to_thread(proc.wait)       # pliki programu zamknięte, zanim wołający po nim posprząta
        raise
    except BaseException:                        # anulowanie (koniec pętli), błąd w na_linie: program nie zostaje sam
        zabij(proc)
        raise


# ----------------------------------------------------------------------------------------------- blokada

@contextlib.contextmanager
def zamek(sciezka: Path | str, czekaj: bool = True) -> Iterator[None]:
    """Wyłączna blokada pliku `sciezka` między procesami (plik zostaje na dysku). `czekaj=False`: zajęta blokada
    = BlockingIOError od razu."""
    with open(sciezka, "a+b") as f:              # bez skracania: inny proces może właśnie trzymać ten plik
        if not WINDOWS:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | (0 if czekaj else fcntl.LOCK_NB))
            yield                                # zamknięcie pliku zdejmuje blokadę
            return
        import msvcrt
        while True:
            f.seek(0)                            # wszyscy blokują ten sam bajt (pozycja 0, także za końcem pliku)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if not czekaj:
                    raise BlockingIOError(f"blokada zajęta: {sciezka}") from None
                time.sleep(ZAMEK_CO_S)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def zastap(zrodlo: Path | str, cel: Path | str, proby: int = 40) -> None:
    """os.replace (zapis atomowy przez plik tymczasowy). Na Windows plik czytany właśnie przez inny proces albo wątek
    (bez FILE_SHARE_DELETE) daje PermissionError (WinError 5/32): ponawiamy co 50 ms, najwyżej `proby` razy."""
    for proba in range(proby):
        try:
            os.replace(zrodlo, cel)
            return
        except PermissionError:
            if not WINDOWS or proba == proby - 1:
                raise
            time.sleep(0.05)


# ----------------------------------------------------------------------------------------------- uprawnienia

def _system32(program: str) -> str:
    """Program systemu Windows z System32 (nie z PATH: w Git Bash `whoami` to inny program)."""
    return str(Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / program)


@functools.lru_cache(maxsize=1)
def _konto() -> str:
    """Konto procesu dla icacls: `*SID` z `whoami /user` (bez zależności od języka systemu i polskich liter
    w nazwie), zapasowo DOMENA\\nazwa."""
    try:
        r = subprocess.run([_system32("whoami.exe"), "/user", "/fo", "csv", "/nh"], stdin=DEVNULL,
                           capture_output=True, timeout=15, creationflags=BEZ_OKNA)
        sid = r.stdout.decode("ascii", "ignore").strip().rsplit(",", 1)[-1].strip().strip('"')
        if r.returncode == 0 and sid.startswith("S-1-"):
            return "*" + sid
    except (OSError, subprocess.SubprocessError):
        pass
    import getpass
    nazwa, domena = getpass.getuser(), os.environ.get("USERDOMAIN")
    return f"{domena}\\{nazwa}" if domena else nazwa


def _icacls(*argv: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run([_system32("icacls.exe"), *argv], stdin=DEVNULL, capture_output=True, timeout=30,
                              creationflags=BEZ_OKNA)
    except (OSError, subprocess.SubprocessError):
        return None


def tryb_pliku(sciezka: Path | str, tryb: int) -> bool:
    """chmod (na POSIX błąd jak z os.chmod). Na Windows tryb bez praw grupy i innych (np. 0600) zdejmuje wpisy
    dziedziczone i daje właścicielowi pełny dostęp (`icacls <plik> /inheritance:r /grant:r <konto>:F`).
    False = na Windows ACL nie ustawiona (brak icacls, dysk bez ACL, np. exFAT); zapis idzie dalej."""
    os.chmod(sciezka, tryb)
    if not WINDOWS or tryb & 0o077:
        return True
    r = _icacls(str(sciezka), "/inheritance:r", "/grant:r", f"{_konto()}:F")
    return r is not None and r.returncode == 0


def tylko_dla_wlasciciela(sciezka: Path | str) -> bool:
    """Czy plik ma ochronę `tryb_pliku(…, 0o600)`: na POSIX bez praw grupy i innych; na Windows bez wpisów
    dziedziczonych („(I)” w icacls) i z pełnym dostępem właściciela."""
    if not WINDOWS:
        return not stat.S_IMODE(os.stat(sciezka).st_mode) & 0o077
    import getpass
    r = _icacls(str(sciezka))
    if r is None or r.returncode != 0:
        return False
    out = r.stdout.decode("utf-8", "replace").lower()
    return "(i)" not in out and f"\\{getpass.getuser().lower()}:(f)" in out

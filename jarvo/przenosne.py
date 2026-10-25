"""Przenośne prymitywy dla Windows, macOS i Linuksa (docs/NATYWNIE.md, sekcja e, punkt 3).

- `zapisz_atomowo`: zapis przez plik tymczasowy i os.replace, z ponawianiem, gdy Windows trzyma plik (WinError 5/32/33).
- `czytaj_tekst`: odczyt pliku podmienianego przez `zapisz_atomowo` w innym procesie (Windows: chwilowa odmowa dostępu).
- `Zamek`: blokada między procesami na pliku (msvcrt.locking na Windows, fcntl.flock na POSIX).
- `chron`: plik albo katalog tylko dla właściciela (POSIX chmod 0600/0700, Windows ACL przez icacls).
- `program`: pełna ścieżka programu przez shutil.which (na Windows także .exe i .cmd).
- `flagi_tla`: creationflags dla procesów w tle bez okna konsoli (Windows) i nowej grupy procesów.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

WINDOWS = os.name == "nt"


def zapisz_atomowo(cel: Path, tresc: str | bytes, tryb: int | None = None, proby: int = 20) -> None:
    """Zapis całego pliku naraz: czytelnik widzi starą albo nową treść, nigdy połowę. Tekst w UTF-8 z LF."""
    cel = Path(cel)
    cel.parent.mkdir(parents=True, exist_ok=True)
    dane = tresc.encode("utf-8") if isinstance(tresc, str) else tresc
    fd, tmp = tempfile.mkstemp(prefix=f".{cel.name}.", suffix=".tmp", dir=str(cel.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dane)
            f.flush()
            os.fsync(f.fileno())
        if tryb is not None and not WINDOWS:
            os.chmod(tmp, tryb)
        for i in range(proby):
            try:
                os.replace(tmp, cel)
                break
            except PermissionError:          # Windows: plik otwarty przez innego czytelnika (antywirus, indeksowanie)
                if not WINDOWS or i == proby - 1:
                    raise
                time.sleep(0.05 * (i + 1))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def czytaj_tekst(p: Path, kodowanie: str = "utf-8", proby: int = 10) -> str:
    """Cały plik jako tekst. Na Windows otwarcie w chwili, gdy inny proces podmienia plik (os.replace w
    `zapisz_atomowo`), kończy się odmową dostępu (próba: 19 na 53 tys. odczytów `nadzorca.json`), choć plik jest
    i ma pełną treść, więc kilka prób, zanim błąd pójdzie dalej."""
    for i in range(proby):
        try:
            return Path(p).read_text(encoding=kodowanie)
        except PermissionError:
            if not WINDOWS or i == proby - 1:
                raise
            time.sleep(0.01 * (i + 1))
    raise AssertionError("nieosiągalne")


class Zamek:
    """Blokada wyłączna na pliku `sciezka` (tworzony, gdy brak). `with Zamek(p):` czeka; `Zamek(p, czekaj=False)`
    rzuca BlockingIOError, gdy zajęty. Działa między procesami na tym samym komputerze."""

    def __init__(self, sciezka: Path, czekaj: bool = True):
        self.sciezka = Path(sciezka)
        self.czekaj = czekaj
        self._f = None

    def __enter__(self) -> "Zamek":
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.sciezka, "a+b")
        try:
            if WINDOWS:
                import msvcrt
                f.seek(0)
                if self.czekaj:
                    while True:                       # LK_LOCK ponawia tylko 10 razy co sekundę: czekamy sami
                        try:
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            time.sleep(0.1)
                else:
                    try:
                        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError as e:
                        raise BlockingIOError(str(e)) from None
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | (0 if self.czekaj else fcntl.LOCK_NB))
        except BaseException:
            f.close()
            raise
        self._f = f
        return self

    def __exit__(self, *_exc) -> None:
        f, self._f = self._f, None
        if f is None:
            return
        try:
            if WINDOWS:
                import msvcrt
                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


def chron(sciezka: Path, katalog: bool | None = None) -> None:
    """Dostęp tylko dla bieżącego użytkownika. POSIX: 0700 dla katalogu, 0600 dla pliku. Windows: os.chmod tego nie
    potrafi, więc ACL bez dziedziczenia z jednym wpisem dla użytkownika (icacls jest w każdym Windows)."""
    p = Path(sciezka)
    katalog = p.is_dir() if katalog is None else katalog
    if not WINDOWS:
        os.chmod(p, 0o700 if katalog else 0o600)
        return
    uzytkownik = os.environ.get("USERNAME") or ""
    domena = os.environ.get("USERDOMAIN") or ""
    kto = f"{domena}\\{uzytkownik}" if domena and uzytkownik else uzytkownik
    if not kto:
        raise OSError("nie wiem, kim jest bieżący użytkownik (brak USERNAME)")
    prawo = "(OI)(CI)F" if katalog else "F"
    wynik = subprocess.run(["icacls", str(p), "/inheritance:r", "/grant:r", f"{kto}:{prawo}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if wynik.returncode:
        raise OSError(f"icacls {p}: {(wynik.stderr or wynik.stdout).strip()[:200]}")


def program(nazwa: str, sciezka: str | None = None) -> str | None:
    """Pełna ścieżka programu albo None. Na Windows shutil.which zna PATHEXT (.exe, .cmd), a goła nazwa w argv nie."""
    return shutil.which(nazwa, path=sciezka)


def flagi_tla() -> int:
    """creationflags procesu w tle: na Windows bez okna konsoli i we własnej grupie (Ctrl+C rodzica go nie zabija)."""
    if not WINDOWS:
        return 0
    return subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

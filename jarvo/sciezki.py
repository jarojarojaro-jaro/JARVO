"""Katalogi instalacji natywnej na Windows, macOS i Linuksie (docs/NATYWNIE.md, sekcja c1).

    <root>      Windows %LOCALAPPDATA%\\Jarvo, macOS ~/.jarvo, Linux ${XDG_DATA_HOME:-~/.local/share}/jarvo
    <program>   <root>/program: kod Jarva, Hermes, Python, narzędzia; wymienny, wersje obok siebie, ścieżka ASCII
    <dane>      <root>/dane = HERMES_HOME Jarva (profile, sesje, skarbiec, sekrety); przeżywa aktualizacje
    <stan>      <root>/stan: środowisko procesów, dziennik zmian hosta, blokady bramy, kanał nadzorcy
    logi        Windows i macOS <root>/logi, Linux ${XDG_STATE_HOME:-~/.local/state}/jarvo/logi
    cache       Windows i macOS <root>/cache, Linux ${XDG_CACHE_HOME:-~/.cache}/jarvo
    build       <root>/build: wynik scripts/build.py (odtwarzalny)

`JARVO_ROOT` przenosi wszystko pod inny korzeń (testy, CI, druga instalacja). Jarvo nie używa domyślnego katalogu
Hermesa (%LOCALAPPDATA%\\hermes, ~/.hermes): prywatny Hermes właściciela i Jarvo mają się nie widzieć.
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")

PLATFORMY = ("windows-x64", "windows-arm64", "macos-arm64", "linux-x64", "linux-arm64")


class BladUkladu(RuntimeError):
    """Nie da się ustalić katalogów (komunikat po polsku dla właściciela)."""


def platforma(system: str | None = None, maszyna: str | None = None) -> str:
    """Klucz platformy z manifestu (vendor/zrodla.yaml, pole `pliki`). macOS Intel nie jest wspierany (decyzja I06)."""
    system = (system or sys.platform).lower()
    maszyna = (maszyna or platform.machine() or "").lower()
    arm = maszyna in ("arm64", "aarch64", "armv8", "armv8l") or maszyna.startswith("arm64")
    if system.startswith("win") or system == "nt":
        return "windows-arm64" if arm else "windows-x64"
    if system == "darwin":
        if not arm:
            raise BladUkladu("Jarvo nie działa na Macach z procesorem Intel: Hermes ich nie wspiera "
                             "(docs/NATYWNIE.md, decyzja I06). Potrzebny Mac z Apple Silicon (M1 i nowsze).")
        return "macos-arm64"
    if system.startswith("linux"):
        return "linux-arm64" if arm else "linux-x64"
    raise BladUkladu(f"Nieznany system {system!r}: Jarvo działa na Windows 10/11, macOS (Apple Silicon) i Linuksie.")


def _domowy() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()) if WINDOWS else Path.home()


def _korzen(env: dict) -> Path:
    if env.get("JARVO_ROOT"):
        return Path(env["JARVO_ROOT"]).expanduser()
    if WINDOWS:
        baza = env.get("LOCALAPPDATA") or str(_domowy() / "AppData" / "Local")
        return Path(baza) / "Jarvo"
    if MACOS:
        # nie ~/Library/Application Support: spacja w ścieżce psuje niecytowane polecenia w skillach (c1)
        return Path.home() / ".jarvo"
    return Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "jarvo"


def krotka_sciezka(p: Path) -> Path:
    """Na Windows krótka nazwa 8.3 istniejącej ścieżki (GetShortPathNameW), gdy pełna ma znaki spoza ASCII; inaczej
    ścieżka bez zmian. espeak-ng, OpenCV i Tesseract mają wąskie API ścieżek (B13)."""
    if not WINDOWS or str(p).isascii() or not p.exists():
        return p
    import ctypes
    from ctypes import wintypes
    f = ctypes.windll.kernel32.GetShortPathNameW
    f.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    f.restype = wintypes.DWORD
    bufor = ctypes.create_unicode_buffer(32768)
    n = f(str(p), bufor, len(bufor))
    krotka = Path(bufor.value) if 0 < n < len(bufor) else p
    return krotka if str(krotka).isascii() else p


@dataclass(frozen=True)
class Uklad:
    root: Path
    program: Path
    dane: Path
    stan: Path
    logi: Path
    cache: Path
    build: Path

    @property
    def jarvo_dane(self) -> Path:
        """<dane>/jarvo: skarbiec, misje, katalogi robocze, skrzynka, modele, konfiguracja Jarva."""
        return self.dane / "jarvo"

    @property
    def bin_floty(self) -> Path:
        """Programy tylko dla procesów floty (python3, jarvo-tts, agent-browser…), nigdy w PATH właściciela."""
        return self.program / "bin-floty"

    @property
    def bin_wlasciciela(self) -> Path:
        """Katalog z poleceniem `jarvo` w PATH właściciela (Windows: jarvo.cmd; macOS i Linux: ~/.local/bin)."""
        return self.root / "bin" if WINDOWS else Path.home() / ".local" / "bin"

    def katalogi(self) -> list[Path]:
        """Katalogi, które zakłada instalator (bez katalogu właściciela z poleceniem jarvo)."""
        return [self.root, self.program, self.dane, self.stan, self.logi, self.cache, self.build, self.jarvo_dane,
                self.bin_floty]


def uklad(env: dict | None = None) -> Uklad:
    """Układ katalogów dla tego komputera (env domyślnie os.environ). Nie tworzy niczego na dysku."""
    env = dict(os.environ if env is None else env)
    root = _korzen(env)
    if WINDOWS or MACOS:
        logi, cache = root / "logi", root / "cache"
    else:
        logi = Path(env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "jarvo" / "logi"
        cache = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "jarvo"
    if env.get("JARVO_ROOT"):
        logi, cache = root / "logi", root / "cache"
    program = root / "program"
    if WINDOWS and not str(program).isascii():
        program = krotka_sciezka(root) / "program" if root.exists() else program
        if not str(program).isascii():
            raise BladUkladu(f"Ścieżka {root} ma znaki spoza ASCII, a system nie podał krótkiej nazwy. Ustaw "
                             "JARVO_ROOT na katalog z samymi literami ASCII (np. C:\\Jarvo) i uruchom instalację "
                             "jeszcze raz.")
    return Uklad(root=root, program=program, dane=root / "dane", stan=root / "stan", logi=logi, cache=cache,
                 build=root / "build")

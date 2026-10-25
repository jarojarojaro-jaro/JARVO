"""Aplikacje z `--aplikacje` → tożsamości, które sprawdza sterownik w trybie bounded (cua-driver-rs 0.38.0).

  Windows  pełna ścieżka programu .exe jako `bundle_id` (sterownik porównuje ją ze ścieżką procesu odczytaną
           z systemu, bez wielkości liter i bez przedrostka \\\\?\\); nazwa szukana w PATH systemu i w App Paths
           rejestru (tylko odczyt, np. chrome, msedge, firefox). Aplikacje ze Sklepu (alias w WindowsApps, np.
           nowy Paint) mają proces pod inną ścieżką z wersją, więc ręce ich nie obejmują; Notatnik z System32
           w Windows 11 z Notatnikiem ze Sklepu otwiera tamten, więc sterownik go nie dopuści
  macOS    bundle id (com.apple.TextEdit) albo nazwa aplikacji z /Applications, /System/Applications
           i ~/Applications (CFBundleIdentifier z Info.plist)
  Linux    rzeczywista ścieżka programu ELF jako `executable` (skrypt startowy, np. /usr/bin/firefox w Ubuntu,
           wskazuje inny proces niż ten, który sterownik zobaczy: wtedy podaj ścieżkę samego programu)

Nigdy na ekranie właściciela: powłoki i terminale (ręce nie dają agentowi terminala), interpretery, narzędzia
systemu i administracji, powłoka pulpitu (explorer.exe to też pasek zadań), menedżery haseł, Jarvo, Hermes
i sam sterownik. Tej listy nie da się wyłączyć flagą.

launch_app w rozmowie (poza_zgoda): nazwa musi wskazywać aplikację ze zgody (pasuje), a każda ścieżka (`path`,
`launch_path` i nazwa, która wygląda na ścieżkę) dokładnie jej tożsamość (ta_sama_tozsamosc); program o tej samej
nazwie w innym katalogu (np. Pobrane\\notepad.exe) to odmowa.
"""
from __future__ import annotations

import ntpath
import os
import plistlib
import re
import shutil
import sys
from pathlib import Path
from typing import Callable

from .zgoda import Aplikacja

ZAKAZANE = frozenset({
    # powłoki, terminale i konsole
    "cmd", "powershell", "powershell_ise", "pwsh", "wt", "windowsterminal", "conhost", "openconsole", "bash", "sh",
    "zsh", "fish", "dash", "ksh", "csh", "tcsh", "nu", "wsl", "wslhost", "wslg", "mintty", "git-bash", "git-cmd",
    "terminal", "iterm", "iterm2", "gnome-terminal", "gnome-terminal-server", "kgx", "ptyxis", "konsole", "xterm",
    "uxterm", "rxvt", "urxvt", "alacritty", "kitty", "wezterm", "wezterm-gui", "tilix", "xfce4-terminal",
    "terminator", "lxterminal", "mate-terminal", "qterminal", "foot", "warp", "hyper", "tabby", "ghostty",
    # interpretery i uruchamianie kodu
    "python", "python3", "pythonw", "py", "pyw", "node", "deno", "bun", "perl", "ruby", "php", "lua", "java",
    "javaw", "wscript", "cscript", "mshta", "rundll32", "regsvr32", "msiexec", "osascript", "script editor",
    "automator", "shortcuts", "scriptmonkey",
    # system i administracja
    "explorer", "regedit", "regedt32", "mmc", "taskmgr", "control", "msconfig", "services", "eventvwr", "gpedit",
    "secpol", "compmgmt", "diskmgmt", "devmgmt", "systemsettings", "systempropertiesadvanced", "sysdm", "resmon",
    "perfmon", "lusrmgr", "netplwiz", "useraccountcontrolsettings", "consent", "lsass", "winlogon", "sudo", "su",
    "pkexec", "gksudo", "kdesu", "systemd", "system preferences", "system settings", "activity monitor",
    "keychain access", "disk utility", "directory utility", "console", "migration assistant", "boot camp assistant",
    "gnome-control-center", "gnome-system-monitor", "ksysguard", "plasma-systemmonitor", "dconf-editor", "seahorse",
    "gnome-disks", "gparted", "synaptic", "gnome-software", "discover", "baobab", "xfce4-settings-manager",
    # menedżery haseł
    "1password", "bitwarden", "keepass", "keepassxc", "lastpass", "dashlane", "enpass", "nordpass", "proton pass",
    # Jarvo, Hermes i sam sterownik
    "jarvo", "hermes", "cua-driver", "cuadriver", "cua driver", "cua-driver-uia",
})
ZAKAZANE_BUNDLE = frozenset({
    "com.apple.terminal", "com.googlecode.iterm2", "dev.warp.warp-stable", "net.kovidgoyal.kitty",
    "com.github.wez.wezterm", "io.alacritty", "co.zeit.hyper", "com.mitchellh.ghostty", "org.tabby",
    "com.apple.systempreferences", "com.apple.settings", "com.apple.activitymonitor", "com.apple.keychainaccess",
    "com.apple.diskutility", "com.apple.console", "com.apple.scripteditor2", "com.apple.automator",
    "com.apple.shortcuts", "com.apple.migrateassistant", "com.apple.finder", "com.apple.systemevents",
    "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop", "org.keepassxc.keepassxc",
    "com.lastpass.lastpassmacdesktop", "com.dashlane.dashlanephonefinal", "com.trycua.driver",
})
# nazwy po polsku → program (Windows); reszta jak w systemie
ALIASY_WINDOWS = {"notatnik": "notepad", "kalkulator": "calc", "paint": "mspaint", "wordpad": "write"}
BUNDLE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+){2,}$")
KATALOGI_MACOS = ("/Applications", "/System/Applications", "/System/Applications/Utilities",
                  "/Applications/Utilities", "~/Applications")


class BladAplikacji(ValueError):
    """Aplikacji nie ma, jest zakazana albo nie da się ustalić jej tożsamości (komunikat dla właściciela)."""


def _rdzen(nazwa: str) -> str:
    """Nazwa programu bez katalogu i końcówki (ścieżki Windows i POSIX na każdym systemie), małymi literami."""
    n = re.split(r"[\\/]", nazwa.strip().strip('"'))[-1].casefold()
    for koncowka in (".exe", ".app", ".cmd", ".bat", ".com", ".desktop", ".appimage"):
        if n.endswith(koncowka):
            n = n[: -len(koncowka)]
    return n


def zakazana(nazwa: str, tozsamosc: dict | None = None) -> str | None:
    """Powód odmowy, gdy aplikacja jest na liście zakazanych (po nazwie, programie albo bundle id)."""
    kandydaci = {_rdzen(nazwa)}
    for wartosc in (tozsamosc or {}).values():
        if isinstance(wartosc, str):
            kandydaci.add(_rdzen(wartosc))
            if wartosc.casefold() in ZAKAZANE_BUNDLE:
                return f"{nazwa}: tej aplikacji ręce nie obejmują (terminal, system, hasła albo sam Jarvo)"
    if kandydaci & ZAKAZANE:
        return f"{nazwa}: tej aplikacji ręce nie obejmują (terminal, system, hasła albo sam Jarvo)"
    return None


def _app_paths(nazwa: str) -> str | None:
    """Windows App Paths (HKCU, potem HKLM): tylko odczyt, np. chrome.exe → pełna ścieżka."""
    try:
        import winreg
    except ImportError:
        return None
    plik = nazwa if nazwa.lower().endswith(".exe") else nazwa + ".exe"
    klucz = "Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + plik
    for korzen in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(korzen, klucz) as k:
                wartosc, _ = winreg.QueryValueEx(k, "")
        except OSError:
            continue
        wartosc = os.path.expandvars(str(wartosc).strip().strip('"'))
        if wartosc:
            return wartosc
    return None


def _sciezka_systemu(env: dict | None = None) -> str:
    """PATH do szukania programów: na Windows katalogi systemu i PATH bez bieżącego katalogu."""
    env = os.environ if env is None else env
    return env.get("PATH", "") or os.defpath


def _windows(nazwa: str, which: Callable[[str], str | None], app_paths: Callable[[str], str | None],
             istnieje: Callable[[str], bool]) -> dict:
    """Ścieżki przez ntpath, więc ta sama logika działa w testach na każdym systemie."""
    n = nazwa.strip().strip('"')
    if re.match(r"^[A-Za-z]:[\\/]", n) or n.startswith("\\\\"):
        sciezka = n
    else:
        n = ALIASY_WINDOWS.get(n.casefold(), n)
        sciezka = which(n) or which(n + ".exe") or app_paths(n)
        if not sciezka:
            raise BladAplikacji(f"{nazwa}: nie znalazłem takiego programu (podaj nazwę z PATH, np. notepad, albo pełną "
                                "ścieżkę do pliku .exe)")
    if not ntpath.isabs(sciezka) or not re.match(r"^(?:[A-Za-z]:[\\/]|\\\\[^\\?.])", sciezka):
        raise BladAplikacji(f"{nazwa}: {sciezka} to nie pełna ścieżka programu")
    p = ntpath.normpath(sciezka)
    if not p.lower().endswith(".exe"):
        raise BladAplikacji(f"{nazwa}: {p} to nie program .exe")
    if re.search(r"\\(?:Microsoft\\WindowsApps|WindowsApps)\\", p, re.I):
        raise BladAplikacji(f"{nazwa}: {p} to aplikacja ze Sklepu Microsoft (alias WindowsApps): jej proces ma inną "
                            "ścieżkę, więc sterownik by jej nie dopuścił. Ręce obsługują klasyczne programy .exe "
                            "(podaj pełną ścieżkę programu).")
    if not istnieje(p):
        raise BladAplikacji(f"{nazwa}: nie ma pliku {p}")
    return {"bundle_id": p}


def _bundle_z_plist(app: Path, czytaj: Callable[[Path], dict]) -> str | None:
    try:
        dane = czytaj(app / "Contents" / "Info.plist")
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None
    bid = dane.get("CFBundleIdentifier") if isinstance(dane, dict) else None
    return str(bid) if bid else None


def _czytaj_plist(p: Path) -> dict:
    with open(p, "rb") as f:
        return plistlib.load(f)


def _macos(nazwa: str, czytaj: Callable[[Path], dict], katalogi: tuple[str, ...]) -> dict:
    n = nazwa.strip()
    if BUNDLE.match(n) and "/" not in n:
        return {"bundle_id": n}
    kandydaci = [Path(n).expanduser()] if n.startswith(("/", "~")) else [
        Path(k).expanduser() / (n if n.endswith(".app") else n + ".app") for k in katalogi]
    for app in kandydaci:
        if app.suffix == ".app" and app.is_dir():
            bid = _bundle_z_plist(app, czytaj)
            if bid:
                return {"bundle_id": bid}
    raise BladAplikacji(f"{nazwa}: nie znalazłem aplikacji (podaj nazwę z /Applications, np. TextEdit, albo bundle "
                        "id, np. com.apple.TextEdit)")


def _elf(p: Path) -> bool:
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def _linux(nazwa: str, which: Callable[[str], str | None]) -> dict:
    n = nazwa.strip()
    sciezka = n if n.startswith("/") else which(n)
    if not sciezka:
        raise BladAplikacji(f"{nazwa}: nie znalazłem takiego programu w PATH (podaj pełną ścieżkę)")
    p = Path(os.path.realpath(sciezka))
    if not p.is_file():
        raise BladAplikacji(f"{nazwa}: nie ma pliku {p}")
    if not _elf(p):
        raise BladAplikacji(f"{nazwa}: {p} to skrypt startowy, nie program: sterownik zobaczy inny proces. Podaj "
                            "ścieżkę samego programu (np. /usr/lib/firefox/firefox).")
    return {"executable": str(p)}


def rozpoznaj(nazwy: list[str], *, system: str | None = None, which: Callable[[str], str | None] | None = None,
              app_paths: Callable[[str], str | None] | None = None, czytaj_plist: Callable[[Path], dict] | None = None,
              katalogi_macos: tuple[str, ...] = KATALOGI_MACOS, env: dict | None = None,
              istnieje: Callable[[str], bool] = os.path.isfile) -> list[Aplikacja]:
    """Lista nazw (bez powtórzeń) → aplikacje z tożsamością; BladAplikacji przy pierwszym problemie."""
    system = system or sys.platform
    if which is None:
        sciezka = _sciezka_systemu(env)
        which = lambda n: shutil.which(n, path=sciezka)  # noqa: E731
    wynik: list[Aplikacja] = []
    widziane: set[str] = set()
    for surowa in nazwy:
        nazwa = " ".join(str(surowa).split())
        if not nazwa:
            continue
        if len(nazwa) > 260 or any(ord(z) < 32 for z in nazwa):
            raise BladAplikacji(f"{nazwa[:40]!r}: zła nazwa aplikacji")
        if (powod := zakazana(nazwa)) is not None:
            raise BladAplikacji(powod)
        if system.startswith("win"):
            tozsamosc = _windows(nazwa, which, app_paths or _app_paths, istnieje)
        elif system == "darwin":
            tozsamosc = _macos(nazwa, czytaj_plist or _czytaj_plist, katalogi_macos)
        else:
            tozsamosc = _linux(nazwa, which)
        if (powod := zakazana(nazwa, tozsamosc)) is not None:
            raise BladAplikacji(powod)
        klucz = next(iter(tozsamosc.values())).casefold()
        if klucz in widziane:
            continue
        widziane.add(klucz)
        wynik.append(Aplikacja(nazwa, tozsamosc))
    if not wynik:
        raise BladAplikacji("Podaj co najmniej jedną aplikację (--aplikacje notatnik,mspaint).")
    return wynik


def _sciezka(tekst: str) -> bool:
    """Napis wygląda na ścieżkę programu (katalog, dysk albo końcówka pliku programu), a nie na nazwę."""
    t = tekst.strip().strip('"')
    return bool(re.search(r"[\\/]", t) or re.match(r"^[A-Za-z]:", t)
                or t.casefold().endswith((".exe", ".app", ".cmd", ".bat", ".com", ".lnk", ".ps1", ".vbs", ".sh",
                                          ".desktop", ".appimage", ".scr", ".pif", ".msi")))


def ta_sama_tozsamosc(zgoda_aplikacje, sciezka: str, platforma: str) -> bool:
    """Ścieżka programu to dokładnie tożsamość z zgody: Windows pełna ścieżka .exe (bez wielkości liter, bez
    przedrostka \\\\?\\), Linux rzeczywista ścieżka programu; macOS nie przyjmuje ścieżek (tylko bundle id)."""
    s = sciezka.strip().strip('"')
    if platforma.startswith("windows"):
        if s.startswith("\\\\?\\"):
            s = s[4:]
        if not re.match(r"^[A-Za-z]:[\\/]", s):
            return False
        klucz = ntpath.normcase(ntpath.normpath(s))
        return any(ntpath.normcase(ntpath.normpath(str(a.tozsamosc["bundle_id"]))) == klucz
                   for a in zgoda_aplikacje if isinstance(a.tozsamosc.get("bundle_id"), str))
    if platforma.startswith("linux"):
        if not s.startswith("/"):
            return False
        import posixpath
        klucz = posixpath.normpath(s)
        return any(posixpath.normpath(str(a.tozsamosc["executable"])) == klucz
                   for a in zgoda_aplikacje if isinstance(a.tozsamosc.get("executable"), str))
    return False


def poza_zgoda(zgoda_aplikacje, args: dict, platforma: str) -> str | None:
    """Powód odmowy launch_app albo None. Każdy podany identyfikator musi wskazywać aplikację ze zgody: ścieżka
    (`path`, `launch_path` i każda nazwa, która wygląda na ścieżkę) dokładnie tę ze zgody, bundle id na macOS
    dokładnie ten ze zgody, a nazwa nazwę albo program ze zgody (pasuje)."""
    pola = {k: args.get(k) for k in ("name", "bundle_id", "path", "launch_path") if args.get(k) is not None}
    if not pola:
        return "launch_app bez nazwy aplikacji"
    for klucz, wartosc in pola.items():
        if not isinstance(wartosc, str) or not wartosc.strip() or len(wartosc) > 1024 \
                or any(ord(z) < 32 for z in wartosc):
            return f"launch_app: {klucz} to nie nazwa aplikacji"
        if klucz in ("path", "launch_path") or _sciezka(wartosc):
            if platforma.startswith("macos"):
                return "launch_app na macOS tylko po bundle id albo nazwie aplikacji ze zgody, bez ścieżek"
            if not ta_sama_tozsamosc(zgoda_aplikacje, wartosc, platforma):
                return f"launch_app: {klucz} {wartosc[:80]!r} to nie program ze zgody (ścieżka musi być dokładnie tą " \
                       "ze zgody)"
        elif klucz == "bundle_id" and platforma.startswith("macos") and BUNDLE.match(wartosc.strip()):
            if not any(str(a.tozsamosc.get("bundle_id", "")).casefold() == wartosc.strip().casefold()
                       for a in zgoda_aplikacje):
                return f"launch_app: bundle id {wartosc[:80]!r} jest poza zgodą"
        elif not pasuje(zgoda_aplikacje, wartosc):
            return f"launch_app: tej aplikacji ({wartosc[:60]!r}) nie ma w zgodzie właściciela"
    return None


def pasuje(zgoda_aplikacje, nazwa: str | None = None, bundle_id: str | None = None) -> bool:
    """Czy launch_app (nazwa albo bundle id z argumentów) dotyczy aplikacji ze zgody: nazwa podana przez
    właściciela, rdzeń nazwy programu albo identyczna tożsamość (bez wielkości liter)."""
    szukane = {s.casefold() for s in (nazwa, bundle_id) if isinstance(s, str) and s.strip()}
    szukane |= {_rdzen(s) for s in list(szukane)}
    if not szukane:
        return False
    for a in zgoda_aplikacje:
        znane = {a.nazwa.casefold(), _rdzen(a.nazwa)}
        n = ALIASY_WINDOWS.get(a.nazwa.casefold())
        if n:
            znane.add(n)
        for klucz, wartosc in a.tozsamosc.items():
            znane |= {str(wartosc).casefold(), _rdzen(str(wartosc))}
            if klucz == "bundle_id" and BUNDLE.match(str(wartosc)):
                znane.add(str(wartosc).rsplit(".", 1)[-1].casefold())      # com.apple.Safari → safari
        if szukane & znane:
            return True
    return False

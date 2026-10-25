"""Sterownik rąk: cua-driver-rs 0.38.0 po przeglądzie (vendor/zrodla.yaml, wpis cua; docs/SOURCES.md).

Gdzie leży:
  Windows, Linux  `<program>/narzedzia/cua-driver/0.38.0/` (manifest `vendor/natywne.yaml`, kiedy: przy-uzyciu;
                  pobiera `jarvo komputer rece on`), bez wpisu w PATH procesów floty
  macOS           `/Applications/CuaDriver.app` (od 0.36 goła binarka nie działa, a uprawnienia Dostępność
                  i Nagrywanie ekranu macOS przypina do aplikacji com.trycua.driver); kopiuje ją właściciel

Przed każdym uruchomieniem bramka sprawdza: sumę sha256 samego programu (PROGRAMY z przeglądu), podpis
(Windows: WinVerifyTrust bez sieci i nazwa podpisującego „Cua AI, Inc.”; macOS: `codesign --verify` oraz
identyfikator com.trycua.driver i zespół YCK386LBJ7; Linux: sama suma, bo Sigstore wymaga kryptografii spoza
biblioteki standardowej, a sumę przegląd sprawdził dwiema drogami), na Windows brak pracownika UIAccess obok
programu, a w procesie bramki brak praw administratora (UIPI: sterownik ze średnim poziomem integralności nie
sięga do okien administratora; z podniesionymi prawami sięgałby).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import MACOS_APLIKACJA, MACOS_ID, MACOS_ZESPOLY, PODPIS_WINDOWS, PROGRAMY, UIACCESS, WERSJA

WINDOWS = os.name == "nt"
NAZWA = "cua-driver"

# Zmienne otoczenia, które sterownik dostaje z procesu bramki (reszta znika: klucze API, porty HTTP sterownika,
# polityki i manifesty spoza bramki, przełączniki trybu bez ograniczeń, Wayland bez XWayland, zmienne Jarva).
PRZECHODZA = frozenset(n.upper() for n in (
    "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "USERPROFILE", "HOMEDRIVE",
    "HOMEPATH", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA", "ALLUSERSPROFILE", "PUBLIC", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "PROGRAMW6432", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432",
    "USERNAME", "USERDOMAIN", "COMPUTERNAME", "OS", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TZ",
    "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_DESKTOP", "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "DBUS_SESSION_BUS_ADDRESS", "AT_SPI_BUS_ADDRESS",
    "DESKTOP_SESSION", "GDK_BACKEND", "QT_QPA_PLATFORM", "__CF_USER_TEXT_ENCODING",
))


class BladSterownika(RuntimeError):
    """Sterownika nie ma, ma inną sumę albo podpis, albo środowisko nie pozwala go uruchomić."""

    def __init__(self, kod: str, komunikat: str):
        super().__init__(komunikat)
        self.kod = kod


@dataclass(frozen=True)
class Sterownik:
    """Sprawdzony program. `przedrostek` to początek argv (prawdziwy: [program]; atrapa w testach: [python, plik]),
    `aplikacja` to CuaDriver.app na macOS (start przez LaunchServices: `open -n -g -a`)."""
    program: Path
    przedrostek: tuple[str, ...]
    sha256: str
    podpis: str = ""
    aplikacja: Path | None = None
    dodatki: dict = field(default_factory=dict)

    def argv(self, *argumenty: str) -> list[str]:
        return [*self.przedrostek, *argumenty]


def katalog(program_dir: Path) -> Path:
    """`<program>/narzedzia/cua-driver/<wersja>` (jak jarvo/pobieracz.py: katalog_wersji)."""
    return Path(program_dir) / "narzedzia" / NAZWA / WERSJA.split("+", 1)[0]


def sciezka_programu(program_dir: Path, platforma: str, aplikacja_macos: Path = MACOS_APLIKACJA) -> Path:
    plik, _ = PROGRAMY[platforma]
    if platforma.startswith("macos"):
        return Path(aplikacja_macos) / plik
    return katalog(program_dir) / plik


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


# ---------------------------------------------------------------- podpis Windows (WinVerifyTrust, bez sieci)

def podpis_windows(p: Path) -> str:
    """Nazwa podpisującego (CERT_NAME_SIMPLE_DISPLAY_TYPE) po udanym WinVerifyTrust; BladSterownika, gdy podpisu
    nie ma albo jest nieważny. Bez sprawdzania odwołań w sieci (WTD_REVOKE_NONE, tylko pamięć podręczna adresów):
    znacznik czasu Microsoftu trzyma podpis ważnym także po wygaśnięciu krótkiego certyfikatu."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

    class WINTRUST_FILE_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE),
                    ("pgKnownSubject", ctypes.POINTER(GUID))]

    class WINTRUST_DATA(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)), ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    class CRYPT_PROVIDER_CERT(ctypes.Structure):           # tylko początek struktury: cbStruct i pCert
        _fields_ = [("cbStruct", wintypes.DWORD), ("pCert", ctypes.c_void_p)]

    class CRYPT_PROVIDER_SGNR(ctypes.Structure):           # początek: cbStruct, sftVerifyAsOf, csCertChain, łańcuch
        _fields_ = [("cbStruct", wintypes.DWORD), ("sftVerifyAsOf", wintypes.FILETIME),
                    ("csCertChain", wintypes.DWORD), ("pasCertChain", ctypes.POINTER(CRYPT_PROVIDER_CERT))]

    wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    wintrust.WinVerifyTrust.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), ctypes.POINTER(WINTRUST_DATA)]
    wintrust.WinVerifyTrust.restype = ctypes.c_long
    wintrust.WTHelperProvDataFromStateData.argtypes = [wintypes.HANDLE]
    wintrust.WTHelperProvDataFromStateData.restype = ctypes.c_void_p
    wintrust.WTHelperGetProvSignerFromChain.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL,
                                                        wintypes.DWORD]
    wintrust.WTHelperGetProvSignerFromChain.restype = ctypes.POINTER(CRYPT_PROVIDER_SGNR)
    crypt32.CertGetNameStringW.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                           wintypes.LPWSTR, wintypes.DWORD]
    crypt32.CertGetNameStringW.restype = wintypes.DWORD

    akcja = GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    plik = WINTRUST_FILE_INFO(ctypes.sizeof(WINTRUST_FILE_INFO), str(p), None, None)
    dane = WINTRUST_DATA()
    dane.cbStruct = ctypes.sizeof(WINTRUST_DATA)
    dane.dwUIChoice = 2                                     # WTD_UI_NONE
    dane.fdwRevocationChecks = 0                            # WTD_REVOKE_NONE
    dane.dwUnionChoice = 1                                  # WTD_CHOICE_FILE
    dane.pFile = ctypes.pointer(plik)
    dane.dwStateAction = 1                                  # WTD_STATEACTION_VERIFY
    dane.dwProvFlags = 0x1000 | 0x10                        # WTD_CACHE_ONLY_URL_RETRIEVAL | REVOCATION_CHECK_NONE
    brak_okna = wintypes.HANDLE(-1)                         # INVALID_HANDLE_VALUE: bez interakcji
    wynik = wintrust.WinVerifyTrust(brak_okna, ctypes.byref(akcja), ctypes.byref(dane))
    try:
        if wynik != 0:
            kod = wynik & 0xFFFFFFFF
            powod = {0x800B0100: "plik nie ma podpisu", 0x80096010: "podpis nie pasuje do pliku (plik zmieniony)",
                     0x800B0003: "to nie podpisany program (nieznany format pliku)",
                     0x800B0109: "łańcuch certyfikatu nie kończy się zaufanym urzędem",
                     0x800B0101: "certyfikat wygasł bez znacznika czasu"}.get(kod, f"WinVerifyTrust 0x{kod:08X}")
            raise BladSterownika("zly_podpis", f"{p.name}: {powod}")
        dostawca = wintrust.WTHelperProvDataFromStateData(dane.hWVTStateData)
        podpisujacy = wintrust.WTHelperGetProvSignerFromChain(dostawca, 0, False, 0) if dostawca else None
        if not podpisujacy or podpisujacy.contents.csCertChain < 1:
            raise BladSterownika("zly_podpis", f"{p.name}: podpis bez łańcucha certyfikatów")
        cert = podpisujacy.contents.pasCertChain[0].pCert
        bufor = ctypes.create_unicode_buffer(512)
        crypt32.CertGetNameStringW(cert, 4, 0, None, bufor, len(bufor))          # CERT_NAME_SIMPLE_DISPLAY_TYPE
        return bufor.value
    finally:
        dane.dwStateAction = 2                              # WTD_STATEACTION_CLOSE
        wintrust.WinVerifyTrust(brak_okna, ctypes.byref(akcja), ctypes.byref(dane))


# ---------------------------------------------------------------- podpis macOS (codesign)

def pola_codesign(wyjscie: str) -> dict[str, str]:
    """`codesign -dv` pisze na stderr pary klucz=wartość; liczy się pierwsze wystąpienie (jak w Hermesie)."""
    pola: dict[str, str] = {}
    for wiersz in wyjscie.splitlines():
        klucz, znak, wartosc = wiersz.partition("=")
        if znak and klucz.strip() not in pola:
            pola[klucz.strip()] = wartosc.strip()
    return pola


def podpis_macos(aplikacja: Path, uruchom: Callable[[list[str]], subprocess.CompletedProcess] | None = None) -> str:
    """`codesign --verify --strict --deep` i `codesign -dv`: identyfikator com.trycua.driver i zespół z przeglądu."""
    uruchom = uruchom or (lambda argv: subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                                      errors="replace", timeout=60, stdin=subprocess.DEVNULL))
    codesign = "/usr/bin/codesign"
    try:
        r = uruchom([codesign, "--verify", "--strict", "--deep", str(aplikacja)])
    except (OSError, subprocess.SubprocessError) as e:
        raise BladSterownika("zly_podpis", f"codesign nie zadziałał: {e}") from None
    if r.returncode != 0:
        raise BladSterownika("zly_podpis", f"{aplikacja.name}: podpis nieważny ({(r.stderr or r.stdout).strip()[:200]})")
    r = uruchom([codesign, "-dv", "--verbose=2", str(aplikacja)])
    pola = pola_codesign(r.stderr or "")
    if pola.get("Identifier") != MACOS_ID:
        raise BladSterownika("zly_podpis", f"{aplikacja.name}: identyfikator {pola.get('Identifier')!r}, a ma być {MACOS_ID}")
    if pola.get("TeamIdentifier") not in MACOS_ZESPOLY:
        raise BladSterownika("zly_podpis", f"{aplikacja.name}: zespół {pola.get('TeamIdentifier')!r} spoza przeglądu "
                                           f"({', '.join(MACOS_ZESPOLY)})")
    return f"{pola.get('Authority') or 'Developer ID'} ({pola['TeamIdentifier']})"


# ---------------------------------------------------------------- sprawdzenie programu

def sprawdz(program_dir: Path, platforma: str, *, podpis: bool = True, aplikacja_macos: Path = MACOS_APLIKACJA,
            uruchom: Callable | None = None) -> Sterownik:
    """Sterownik gotowy do uruchomienia albo BladSterownika (kody: brak_sterownika, zla_suma, uiaccess, zly_podpis)."""
    if platforma not in PROGRAMY:
        raise BladSterownika("brak_sterownika", f"Ręce nie działają na {platforma}.")
    p = sciezka_programu(program_dir, platforma, aplikacja_macos)
    if not p.is_file():
        rada = ("skopiuj CuaDriver.app do /Applications (jarvo komputer rece on pokaże, skąd)"
                if platforma.startswith("macos") else "jarvo komputer rece on pobierze go z sumą")
        raise BladSterownika("brak_sterownika", f"Nie ma sterownika rąk ({p}): {rada}.")
    _, oczekiwana = PROGRAMY[platforma]
    suma = sha256(p)
    if suma != oczekiwana:
        raise BladSterownika("zla_suma", f"{p} ma sumę {suma[:12]}…, a przegląd {WERSJA} zna {oczekiwana[:12]}…: "
                                         "nie uruchamiam. Usuń katalog sterownika i włącz ręce od nowa.")
    if platforma.startswith("windows") and (p.parent / UIACCESS).exists():
        raise BladSterownika("uiaccess", f"Obok sterownika leży {UIACCESS} (UIAccess omija UIPI i sięga do okien "
                                         "administratora): nie uruchamiam. Usuń go albo katalog sterownika.")
    opis = ""
    aplikacja = None
    if platforma.startswith("macos"):
        aplikacja = Path(aplikacja_macos)
        if podpis:
            opis = podpis_macos(aplikacja, uruchom)
    elif platforma.startswith("windows") and podpis:
        opis = podpis_windows(p)
        if opis != PODPIS_WINDOWS:
            raise BladSterownika("zly_podpis", f"{p.name}: podpisał {opis!r}, a przegląd zna {PODPIS_WINDOWS!r}")
    return Sterownik(program=p, przedrostek=(str(p),), sha256=suma, podpis=opis, aplikacja=aplikacja)


# ---------------------------------------------------------------- środowisko i prawa procesu

def srodowisko(baza: dict, dom: Path, *, demon: bool, program_dir: Path | None = None) -> dict[str, str]:
    """Otoczenie sterownika: tylko PRZECHODZA z `baza` + stałe Jarva. Telemetria (PostHog) i sprawdzanie
    aktualizacji wyłączone, stan sterownika w `dom`, tryb unrestricted zablokowany. `demon`: `serve` kończy się
    przy końcu stdin (bramka trzyma potok, więc znika razem z nią)."""
    env = {k: str(v) for k, v in baza.items() if k.upper() in PRZECHODZA}
    sciezka = [s for s in str(baza.get("PATH") or baza.get("Path") or "").split(os.pathsep) if s]
    if program_dir is not None:                    # bez katalogów Jarva (bin-floty, narzędzia) w PATH sterownika
        korzen = os.path.normcase(os.path.abspath(program_dir)).rstrip("\\/") + os.sep
        sciezka = [s for s in sciezka if not os.path.normcase(os.path.abspath(s)).startswith(korzen)]
    env["PATH"] = os.pathsep.join(sciezka) or os.defpath
    dom = Path(dom)
    env.update({
        "CUA_DRIVER_RS_HOME": str(dom),
        "CUA_DRIVER_TELEMETRY_HOME": str(dom / "telemetria"),
        "CUA_HOME": str(dom / "cua"),
        "CUA_DRIVER_RS_TELEMETRY_ENABLED": "0", "CUA_TELEMETRY_ENABLED": "0", "CUA_TELEMETRY": "0", "DO_NOT_TRACK": "1",
        "CUA_DRIVER_RS_UPDATE_CHECK": "0",
        "CUA_DRIVER_DISABLE_UNRESTRICTED": "1",
        "CUA_DRIVER_PERMISSION_MODE": "bounded",
        "CUA_DRIVER_EMBEDDED": "1",
    })
    if demon:
        env["CUA_DRIVER_PARENT_LIVENESS_STDIN"] = "1"
    return env


def podwyzszone() -> bool:
    """Czy proces ma prawa administratora: Windows token podniesiony albo poziom integralności co najmniej wysoki,
    POSIX euid 0. Wtedy sterownik sięgałby do okien administratora, więc ręce nie startują."""
    if not WINDOWS:
        return os.geteuid() == 0
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD)]
    advapi.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    advapi.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    advapi.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        return True                                  # nie wiadomo: jak przy prawach administratora (odmowa)
    try:
        n = wintypes.DWORD()
        podniesiony = wintypes.DWORD()
        if not advapi.GetTokenInformation(token, 20, ctypes.byref(podniesiony), ctypes.sizeof(podniesiony),
                                          ctypes.byref(n)):           # TokenElevation
            return True
        if podniesiony.value:
            return True
        advapi.GetTokenInformation(token, 25, None, 0, ctypes.byref(n))  # TokenIntegrityLevel
        bufor = ctypes.create_string_buffer(n.value)
        if not advapi.GetTokenInformation(token, 25, bufor, n, ctypes.byref(n)):
            return True
        sid = ctypes.cast(bufor, ctypes.POINTER(ctypes.c_void_p))[0]
        ile = advapi.GetSidSubAuthorityCount(sid).contents.value
        poziom = advapi.GetSidSubAuthority(sid, ile - 1).contents.value
        return poziom >= 0x3000                      # SECURITY_MANDATORY_HIGH_RID
    finally:
        k32.CloseHandle(token)


def ekran_linux(env: dict) -> str | None:
    """Powód odmowy na Linuksie: sterownik działa z X11 albo XWayland (DISPLAY); samego Waylanda nie obsługujemy
    (pomocnik GNOME z wydania wymaga instalacji rozszerzenia powłoki, więc go nie bierzemy)."""
    if env.get("DISPLAY"):
        return None
    if env.get("WAYLAND_DISPLAY"):
        return ("Ręce na Linuksie potrzebują X11 albo XWayland (zmienna DISPLAY). W sesji Wayland włącz XWayland "
                "albo zaloguj się do sesji X11.")
    return "Ręce potrzebują ekranu: brak DISPLAY (sesja bez pulpitu, SSH albo kontener)."


def uwagi_linux(env: dict) -> list[str]:
    """Ostrzeżenia bez odmowy: drzewo dostępności (AT-SPI2) wymaga magistrali sesji."""
    if not env.get("DBUS_SESSION_BUS_ADDRESS") and not (Path(env.get("XDG_RUNTIME_DIR") or "/nonexistent") / "bus").exists():
        return ["brak magistrali sesji D-Bus: sterownik nie zobaczy drzewa dostępności (AT-SPI2), tylko zrzuty"]
    return []


INSTRUKCJA_MACOS = (
    "macOS wymaga dwóch zgód dla aplikacji Cua Driver (com.trycua.driver), które dajesz sam, raz:\n"
    "  1. Ustawienia systemowe → Prywatność i ochrona → Dostępność: włącz „Cua Driver”.\n"
    "  2. Ustawienia systemowe → Prywatność i ochrona → Nagrywanie ekranu i dźwięku z systemu: włącz „Cua Driver”.\n"
    "Jarvo nie zmienia tych ustawień sam. Jeśli przełącznik jest włączony, a sterownik dalej nie widzi ekranu (zgoda\n"
    "dla starszej wersji), wyłącz i włącz go jeszcze raz albo: tccutil reset Accessibility com.trycua.driver\n"
    "i tccutil reset ScreenCapture com.trycua.driver, a potem zgódź się od nowa.")


def instrukcja_kopii_macos(zrodlo: Path) -> str:
    return ("Sterownik rąk na macOS to aplikacja CuaDriver.app w /Applications (wymaga hasła administratora,\n"
            "Jarvo tego nie robi sam). Skopiuj ją z pobranej i sprawdzonej sumą paczki:\n"
            f"  sudo ditto \"{zrodlo}\" /Applications/CuaDriver.app\n"
            "albo przeciągnij ją w Finderze do folderu Aplikacje. Potem jeszcze raz: jarvo komputer rece on ...")


def system_platformy(platforma: str) -> str:
    return "win32" if platforma.startswith("windows") else "darwin" if platforma.startswith("macos") else "linux"


def biezacy_system() -> str:
    return sys.platform

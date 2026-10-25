"""Autostart nadzorcy Jarva (docs/NATYWNIE.md: H22, c2 „Autostart”, N08 `jarvo autostart on/off/status`, D08).

Mechanizm systemu uruchamia `jarvo serwis` po zalogowaniu i podnosi go po awarii. Procesami Jarva zarządza już sam
nadzorca (zasada 5: bez NSSM, WinSW i supervisord). Wszystko bez admina i bez sudo:

- Windows: zadanie Harmonogramu `Jarvo-<SID>`. Folder główny Harmonogramu jest jeden na cały komputer, a instalacja
  jest na konto, więc nazwa niesie SID właściciela (tak robi OneDrive). Definicja z pliku XML w UTF-16,
  `schtasks /Create /TN <nazwa> /XML <plik> /F` bez wcześniejszego kasowania (nieudana rejestracja nie zabiera
  działającego zadania), start `/Run`, usunięcie `/Delete /F`, stan `/Query`. Zadanie wyłączone w Harmonogramie
  (taskschd.msc, program „przyspieszający start”) `jarvo autostart on` włącza z powrotem: `/Change /ENABLE`, a gdy
  to nie przejdzie albo wyłączono same wyzwalacze, rejestracja od nowa. Wyzwalacze: logowanie z opóźnieniem PT15S,
  a zapasowo odblokowanie sesji i co 5 minut (gdy nadzorca działa, IgnoreNew nic nie robi). Każdy wyzwalacz ma
  UserId bieżącego użytkownika (SID): wyzwalacza „dowolny użytkownik” Harmonogram nie przyjmuje bez admina (tak
  `schtasks /SC ONLOGON` i Hermes bez UserId kończą na „Odmowa dostępu”). Dokumentacja wymaga admina tylko przy
  wyzwalaczu startu systemu; konta bez admina z zapasowymi wyzwalaczami nikt jeszcze nie sprawdził (runner CI jest
  adminem), więc gdy Harmonogram odrzuci pełną definicję, rejestrujemy sam wyzwalacz logowania, a gdy odmówi
  w ogóle (polityka), wpis HKCU Run (start po zalogowaniu, bez podtrzymania po awarii). Ustawienia: bez zatrzymania
  na baterii, bez limitu czasu (PT0S), priorytet 5 (normalny), ponowienie co minutę do 999 razy. Czy Harmonogram
  ponawia zadanie zakończone kodem innym niż 0, a nie tylko takie, które nie wystartowało, nie jest sprawdzone:
  awarię nadzorcy pewnie łapie dopiero wyzwalacz co 5 minut. Domyślne `schtasks /SC ONLOGON` zatrzymałoby nadzorcę
  na baterii i po 72 godzinach.
- macOS: LaunchAgent `~/Library/LaunchAgents/pl.jarvo.nadzorca.plist`: RunAtLoad, KeepAlive przy wyjściu z błędem,
  ThrottleInterval 30, ExitTimeOut 45, logi do `<logi>`, bez ProcessType Background (dławiłby render);
  `launchctl bootstrap/bootout/print` w domenie gui/<uid>. Usługę wyłączoną w launchd (`launchctl disable`, stan
  przetrwa restart) `on` włącza z powrotem (`launchctl enable`). Powiadomienie „Background Items” jest normalne.
- Linux: `jarvo.service` w katalogu jednostek, w którym naprawdę szuka menedżer usług użytkownika (jego UnitPath,
  zwykle `~/.config/systemd/user`): Restart=on-failure, KillMode=mixed, TimeoutStopSec=45 (dłużej niż 30 s
  drenażu bramy), `systemctl --user`. Cudzej jednostki o tej nazwie (bez naszego znacznika, w tym katalogu albo
  w innym, który nasza by przesłoniła) ani maski nie ruszamy. Bez user busa (WSL bez systemd, kontener, su) jasny
  komunikat. Linger (start bez logowania) tylko na wyraźne życzenie: `wlacz_linger()` zapisuje go w dzienniku po
  udanym włączeniu, z odciskiem pliku lingera, a `wylacz_linger()` usuwa wpis, więc `jarvo uninstall` nie wyłączy
  lingera, który właściciel włączył sam (także po wyłączeniu naszego poza Jarvem: plik ma wtedy inny odcisk).

launchd i systemd --user nie czytają ~/.zprofile ani ~/.profile, więc LaunchAgent i jednostka dostają jawne
środowisko z chwili instalacji (`zmienne_uslugi`): nadzorca ma wyliczyć ten sam układ katalogów co instalator.
Instalacja spod JARVO_ROOT (próby, CI) dostaje nazwy z przyrostkiem skrótu korzenia (`Jarvo-<SID>-1a2b3c4d`,
`pl.jarvo.nadzorca-1a2b3c4d`, `jarvo-1a2b3c4d.service`), więc nie rusza prawdziwego autostartu właściciela.
Każde włączenie trafia do dziennika zmian hosta przed zmianą (jarvo/zmiany_hosta.py), więc `jarvo uninstall` je
cofnie. Polecenia systemu idą przez `wykonaj(argv) -> (kod, wyjście)`: domyślnie subprocess, w testach atrapa.

Umowa z nadzorcą (jarvo/nadzorca.py):
- planowane zatrzymanie kończy `jarvo serwis` kodem 0 (launchd i systemd go wtedy nie podnoszą); start przy już
  działającym nadzorcy też powinien kończyć się kodem 0, bo inaczej launchd podnosi go co 30 s, a systemd co 10 s;
- na Windows zapasowe wyzwalacze uruchomią go znowu po `jarvo stop`, więc nadzorca przy starcie szanuje znacznik
  planowanego zatrzymania i trzyma blokadę jednej instancji;
- Linux, KillMode=mixed: SIGTERM dostaje tylko nadzorca, a to, co zostało w grupie (brama, panel), systemd zabija
  SIGKILL-em zaraz po jego wyjściu, więc nadzorca kończy się dopiero po bramie i panelu, wszystko w 45 s
  (pracownicy kanbana żyją w osobnym scope, `systemd-run --user --scope` Hermesa);
- `wylacz()` na Windows nie zatrzymuje działającego nadzorcy (`schtasks /End` zabiłby go bez drenażu bramy); na
  macOS i Linuksie system wysyła mu SIGTERM i czeka 45 s;
- zadanie Harmonogramu nie ustawia zmiennych środowiska: instalacja spod JARVO_ROOT podaje korzeń w argv
  (`jarvo --korzen <root> serwis`, jarvo/instalator.py), a domyślną wyznacza %LOCALAPPDATA%.
"""
from __future__ import annotations

import csv
import hashlib
import io
import ntpath
import os
import plistlib
import posixpath
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import sciezki, zmiany_hosta
from .przenosne import zapisz_atomowo
from .sciezki import Uklad
from .zmiany_hosta import Wykonaj

SYSTEMY = ("windows", "macos", "linux")
ZNACZNIK = "[jarvo-autostart]"           # w opisie zadania i w nagłówku jednostki: tak rozpoznajemy nasze
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
OPOZNIENIE = "PT15S"
CO_ILE = "PT5M"
POCZATEK_CYKLU = "2026-01-01T00:00:00"   # stała data: ten sam XML przy każdej instalacji (odcisk się nie zmienia)
ETYKIETA = "pl.jarvo.nadzorca"
JEDNOSTKA = "jarvo"
LIMIT_ZATRZYMANIA = 45                   # s: dłużej niż drenaż bramy (30 s, c2)
KLUCZ_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
LAUNCHCTL = "/bin/launchctl"
PRZERWA_LAUNCHCTL = 1.0                  # s między próbami bootstrap: po bootout launchd chwilę sprząta
KATALOG_LINGER = "/var/lib/systemd/linger"   # logind: plik <użytkownik> w nim = linger włączony
WYNIK_DZIALA = "267009"                  # SCHED_S_TASK_RUNNING (0x41301) w kolumnie „Last Result” schtasks /V
# wartości, które Harmonogram przyjmuje, gdy elementu nie ma (eksport pomija domyślne)
DOMYSLNE = {"MultipleInstancesPolicy": "IgnoreNew", "DisallowStartIfOnBatteries": "true",
            "StopIfGoingOnBatteries": "true", "ExecutionTimeLimit": "PT72H", "Priority": "7"}
WYZWALACZE = {"LogonTrigger": "logowanie", "SessionStateChangeTrigger": "odblokowanie sesji",
              "TimeTrigger": "co 5 minut"}       # nazwy wyzwalaczy naszego zadania w `jarvo status`
# katalogi XDG, od których zależy układ Jarva na Linuksie (jarvo/sciezki.py) i katalog jednostek, z domyślnymi
XDG = (("XDG_DATA_HOME", (".local", "share")), ("XDG_STATE_HOME", (".local", "state")),
       ("XDG_CACHE_HOME", (".cache",)), ("XDG_CONFIG_HOME", (".config",)))
NAZWA_ZMIENNEJ = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class BladAutostartu(RuntimeError):
    """Autostartu nie da się włączyć, wyłączyć albo sprawdzić (komunikat po polsku dla właściciela)."""


def system_biezacy() -> str:
    """windows, macos albo linux."""
    if sciezki.WINDOWS:
        return "windows"
    if sciezki.MACOS:
        return "macos"
    if sciezki.LINUX:
        return "linux"
    raise BladAutostartu("Autostart Jarva działa na Windows, macOS i Linuksie.")


def _system(system: str | None) -> str:
    s = system or system_biezacy()
    if s not in SYSTEMY:
        raise ValueError(f"system {s!r}: znane są {', '.join(SYSTEMY)}")
    return s


def _env(env: dict | None) -> dict:
    return dict(os.environ if env is None else env)


def _dom(dom) -> Path:
    return Path(dom) if dom else Path.home()


def _linia(tekst: str) -> str:
    """Pierwszy niepusty wiersz wyjścia programu, do komunikatu (bez reszty wydruku)."""
    for w in (tekst or "").splitlines():
        if w.strip():
            return w.strip()[:300]
    return "brak komunikatu"


def _sha(dane: bytes | str) -> str:
    return hashlib.sha256(dane.encode("utf-8") if isinstance(dane, str) else dane).hexdigest()


def _argv(argv, system: str) -> list[str]:
    argv = [str(a) for a in argv]
    if not argv:
        raise ValueError("autostart: puste polecenie")
    if system == "windows":
        pelna = bool(ntpath.splitdrive(argv[0])[0]) and ntpath.isabs(argv[0])
    else:
        pelna = posixpath.isabs(argv[0])
    if not pelna:
        raise ValueError(f"autostart: program musi mieć pełną ścieżkę, a jest {argv[0]!r}")
    for a in argv:
        if any(z in a for z in "\0\r\n"):
            raise ValueError(f"autostart: argument ze znakiem nowego wiersza albo NUL: {a!r}")
        if system == "windows" and "%" in a:
            raise ValueError(f"autostart: Harmonogram rozwija %ZMIENNE% w poleceniu, a argument ma znak %: {a!r}")
    return argv


# ---------------------------------------------------------------- nazwy i środowisko usługi

def _klucz_korzenia(p: Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _przyrostek(u: Uklad, env: dict | None = None) -> str:
    """"" dla domyślnego korzenia, "-<8 znaków sha256 korzenia>" dla każdego innego (JARVO_ROOT)."""
    env = {k: v for k, v in _env(env).items() if k != "JARVO_ROOT"}
    try:
        domyslny = sciezki.uklad(env).root
    except sciezki.BladUkladu:
        domyslny = None
    if domyslny is not None and _klucz_korzenia(domyslny) == _klucz_korzenia(u.root):
        return ""
    return "-" + hashlib.sha256(_klucz_korzenia(u.root).encode("utf-8")).hexdigest()[:8]


def _konto_w_nazwie(kto: str) -> str:
    """Konto w nazwie zadania: SID bez zmian. Zapasowe DOMENA\\użytkownik (gdy SID-u nie ma) tylko w znakach, które
    nazwa zadania może mieć (ukośnik to folder Harmonogramu) i które schtasks odda wiernie w stronie OEM, z sumą
    pełnej nazwy, żeby „Michał” i „Michaś” nie dostały tego samego zadania."""
    if re.fullmatch(r"S-1-\d+(?:-\d+)+", kto):
        return kto
    czytelne = re.sub(r"[^0-9A-Za-z.-]+", "_", kto.replace("\\", "-")).strip("_.")[:40]
    return f"{czytelne or 'konto'}-{_sha(kto.casefold())[:8]}"


def nazwa_zadania(u: Uklad, env: dict | None = None, *, kto: str | None = None) -> str:
    """Windows: „Jarvo-<SID>” dla domyślnego korzenia, „Jarvo-<SID>-<8 znaków skrótu korzenia>” dla JARVO_ROOT.
    Folder Harmonogramu jest wspólny dla wszystkich kont komputera, więc bez SID-u drugie konto trafiłoby na zadanie
    pierwszego (zwykłe: „Odmowa dostępu”, administrator: nadpisanie). `kto` (SID) jest dla testów."""
    return f"Jarvo-{_konto_w_nazwie(kto or _uzytkownik_windows())}{_przyrostek(u, env)}"


def etykieta_agenta(u: Uklad, env: dict | None = None) -> str:
    """macOS: etykieta LaunchAgenta (pl.jarvo.nadzorca, z przyrostkiem korzenia jak nazwa_zadania)."""
    return ETYKIETA + _przyrostek(u, env)


def nazwa_jednostki(u: Uklad, env: dict | None = None) -> str:
    """Linux: jednostka systemd --user (jarvo.service, z przyrostkiem korzenia jak nazwa_zadania)."""
    return f"{JEDNOSTKA}{_przyrostek(u, env)}.service"


def zmienne_uslugi(u: Uklad, system: str, env: dict | None = None, dom: Path | None = None) -> dict[str, str]:
    """Środowisko LaunchAgenta (macOS) i jednostki (Linux) z chwili instalacji: launchd i systemd --user nie czytają
    plików startowych powłoki, a nadzorca ma wyliczyć ten sam układ katalogów co instalator (jarvo/sciezki.py).
    macOS: JARVO_ROOT zawsze (układ z nim i bez niego jest ten sam) i te zmienne XDG, które miała powłoka.
    Linux: XDG_DATA_HOME, XDG_STATE_HOME, XDG_CACHE_HOME i XDG_CONFIG_HOME zawsze (bez zmiennej domyślne ze
    specyfikacji), bo wyznaczają domyślny korzeń, logi i cache. JARVO_ROOT tylko wtedy, gdy układ instalatora z niego
    wyszedł (zmienna w `env` albo korzeń inny niż domyślny): w sciezki.uklad JARVO_ROOT przenosi logi i cache
    z katalogów XDG do korzenia, więc dla zwykłej instalacji korzeń przypina samo XDG_DATA_HOME."""
    env = _env(env)
    wynik: dict[str, str] = {}
    if system == "macos" or env.get("JARVO_ROOT") or _przyrostek(u, env):
        wynik["JARVO_ROOT"] = str(u.root)
    for nazwa, domyslna in XDG:
        if env.get(nazwa):
            wynik[nazwa] = os.path.abspath(env[nazwa])      # względną sciezki.uklad liczy od bieżącego katalogu
        elif system == "linux":
            wynik[nazwa] = str(_dom(dom).joinpath(*domyslna))
    return wynik


def _zmienne(zmienne: dict | None) -> dict[str, str]:
    wynik = {}
    for nazwa, wartosc in (zmienne or {}).items():
        wartosc = str(wartosc)
        if not NAZWA_ZMIENNEJ.fullmatch(nazwa) or any(z in wartosc for z in "\0\r\n"):
            raise ValueError(f"autostart: zmienna środowiska {nazwa}={wartosc!r}")
        wynik[nazwa] = wartosc
    return wynik


def _pusty_stan(system: str, nazwa: str, plik) -> dict:
    return {"system": system, "mechanizm": None, "nazwa": nazwa, "plik": str(plik) if plik else None,
            "wlaczony": False, "nasz": False, "dziala": None, "pid": None}


def _opis(s: dict) -> str:
    """Jeden wiersz dla `jarvo status`."""
    if not s.get("mechanizm"):
        return "wyłączony" + (f" ({s['blad']})" if s.get("blad") else "")
    nazwy = {"harmonogram": "zadanie Harmonogramu", "run": "wpis HKCU Run", "launchagent": "LaunchAgent",
             "systemd": "usługa systemd --user"}
    czesci = [f"{nazwy[s['mechanizm']]} {s['nazwa']}"]
    if s["mechanizm"] == "run":
        czesci.append("bez podtrzymania po awarii")
    if s.get("nasz") is None:
        czesci.append("nie wiadomo, czy założył go Jarvo")
    elif not s["nasz"]:
        czesci.append("nie założył go Jarvo")
    elif not s.get("blad"):
        # Windows osobno: wyłączone całe zadanie i wyłączone wyzwalacze; macOS i Linux znają tylko „wyłączone”
        wylaczone = ["wyłączone w systemie"] if s.get("wylaczone_w_systemie", not s.get("wlaczony")) else []
        if s.get("wylaczone_wyzwalacze"):
            wylaczone.append("wyłączone wyzwalacze: " + ", ".join(WYZWALACZE.get(w, w)
                                                                    for w in s["wylaczone_wyzwalacze"]))
        if wylaczone:
            czesci.append(", ".join(wylaczone) + " (włączy je jarvo autostart on)")
    if s.get("dziala") is True:
        czesci.append("działa" + (f", pid {s['pid']}" if s.get("pid") else ""))
    elif s.get("dziala") is False:
        czesci.append("nie działa")
    if s.get("linger"):
        czesci.append("także bez logowania (linger)")
    if s.get("blad"):
        czesci.append(s["blad"])
    return ("włączony" if s.get("wlaczony") and s.get("nasz") else "nieaktywny") + " (" + ", ".join(czesci) + ")"


# ---------------------------------------------------------------- Windows: Harmonogram zadań

def _schtasks() -> str:
    # pełna ścieżka: goła nazwa w CreateProcess szuka najpierw w katalogu bieżącym
    return ntpath.join(os.environ.get("SystemRoot") or "C:\\Windows", "System32", "schtasks.exe")


def _sid() -> str:
    """SID bieżącego użytkownika z tokenu procesu (OpenProcessToken + GetTokenInformation(TokenUser))."""
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):      # TOKEN_QUERY
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        n = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(n))                          # TokenUser
        bufor = ctypes.create_string_buffer(n.value)
        if not advapi.GetTokenInformation(token, 1, bufor, n, ctypes.byref(n)):
            raise ctypes.WinError(ctypes.get_last_error())
        tekst = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(ctypes.cast(bufor, ctypes.POINTER(ctypes.c_void_p))[0],
                                             ctypes.byref(tekst)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return tekst.value
        finally:
            k32.LocalFree(ctypes.cast(tekst, ctypes.c_void_p))
    finally:
        k32.CloseHandle(token)


def _uzytkownik_windows() -> str:
    """SID bieżącego użytkownika (tak zapisuje go eksport zadania; bez kłopotu z polskimi znakami w nazwie konta
    i ze zmianą nazwy). Zapas: DOMENA\\użytkownik ze zmiennych."""
    if sciezki.WINDOWS:
        try:
            return _sid()
        except OSError:
            pass
    kto, domena = os.environ.get("USERNAME") or "", os.environ.get("USERDOMAIN") or ""
    if not kto:
        raise BladAutostartu("Nie wiem, kim jest bieżący użytkownik Windows (brak SID i USERNAME).")
    return f"{domena}\\{kto}" if domena else kto


def _xml(argv: list[str], uzytkownik: str, katalog, zapasowe: bool, odcisk: str) -> str:
    def el(rodzic, tag, tekst=None, **atrybuty):
        e = ET.SubElement(rodzic, tag, atrybuty)
        if tekst is not None:
            e.text = tekst
        return e

    task = ET.Element("Task", {"version": "1.2", "xmlns": NS})
    info = el(task, "RegistrationInfo")
    el(info, "Author", "Jarvo")
    el(info, "Description", f"Jarvo: nadzorca procesów (jarvo serwis) po zalogowaniu i po awarii. {ZNACZNIK} "
                            f"odcisk={odcisk}")
    # kolejność w wyzwalaczach jak w schemacie: Enabled, StartBoundary, Repetition, potem UserId, Delay, StateChange
    wyzwalacze = el(task, "Triggers")
    t = el(wyzwalacze, "LogonTrigger")
    el(t, "Enabled", "true")
    el(t, "UserId", uzytkownik)
    el(t, "Delay", OPOZNIENIE)
    if zapasowe:
        t = el(wyzwalacze, "SessionStateChangeTrigger")
        el(t, "Enabled", "true")
        el(t, "UserId", uzytkownik)
        el(t, "StateChange", "SessionUnlock")
        t = el(wyzwalacze, "TimeTrigger")
        el(t, "Enabled", "true")
        el(t, "StartBoundary", POCZATEK_CYKLU)
        powtorz = el(t, "Repetition")
        el(powtorz, "Interval", CO_ILE)
        el(powtorz, "StopAtDurationEnd", "false")
    kto = el(el(task, "Principals"), "Principal", id="Author")
    el(kto, "UserId", uzytkownik)
    el(kto, "LogonType", "InteractiveToken")         # tylko w sesji zalogowanego właściciela, bez hasła
    el(kto, "RunLevel", "LeastPrivilege")
    ust = el(task, "Settings")
    for nazwa, wartosc in (("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
                           ("StopIfGoingOnBatteries", "false"), ("AllowHardTerminate", "true"),
                           ("StartWhenAvailable", "true"), ("RunOnlyIfNetworkAvailable", "false")):
        el(ust, nazwa, wartosc)
    bezczynnosc = el(ust, "IdleSettings")
    el(bezczynnosc, "StopOnIdleEnd", "false")
    el(bezczynnosc, "RestartOnIdle", "false")
    for nazwa, wartosc in (("AllowStartOnDemand", "true"), ("Enabled", "true"), ("Hidden", "false"),
                           ("RunOnlyIfIdle", "false"), ("WakeToRun", "false"), ("ExecutionTimeLimit", "PT0S"),
                           ("Priority", "5")):
        el(ust, nazwa, wartosc)
    ponow = el(ust, "RestartOnFailure")
    el(ponow, "Interval", "PT1M")
    el(ponow, "Count", "999")
    akcja = el(el(task, "Actions", Context="Author"), "Exec")
    el(akcja, "Command", argv[0])
    if len(argv) > 1:
        el(akcja, "Arguments", subprocess.list2cmdline(argv[1:]))     # reguły CreateProcess, jak sys.argv
    if katalog is not None:
        el(akcja, "WorkingDirectory", str(katalog))
    ET.indent(task, "  ")
    return '<?xml version="1.0" encoding="UTF-16"?>\n' + ET.tostring(task, encoding="unicode") + "\n"


def _xml_i_odcisk(argv, uzytkownik: str, katalog=None, zapasowe: bool = True) -> tuple[bytes, str]:
    argv = _argv(argv, "windows")
    odcisk = _sha(_xml(argv, uzytkownik, katalog, zapasowe, ""))[:12]
    return ("\ufeff" + _xml(argv, uzytkownik, katalog, zapasowe, odcisk)).encode("utf-16-le"), odcisk


def xml_zadania(argv, uzytkownik: str, *, katalog=None, zapasowe: bool = True) -> bytes:
    """Definicja zadania Harmonogramu (schemat 1.2) w UTF-16 z BOM, tak jak zapisuje ją sam Windows. Opis niesie
    ZNACZNIK i odcisk treści: po nim rozpoznajemy nasze zadanie i to, czy trzeba je zarejestrować ponownie.
    `zapasowe=False` zostawia tylko wyzwalacz logowania."""
    return _xml_i_odcisk(argv, uzytkownik, katalog, zapasowe)[0]


def _czytaj_xml(tekst: str) -> dict:
    """Najważniejsze pola z `schtasks /Query /XML` (eksport pomija wartości domyślne: uzupełniamy je).
    `wlaczone`: Settings/Enabled (wyłączenie całego zadania), `wylaczone_wyzwalacze`: wyzwalacze z Enabled=false."""
    pusty = {"opis": "", "polecenie": "", "argumenty": "", "wlaczone": True, "ustawienia": dict(DOMYSLNE),
             "wyzwalacze": [], "wylaczone_wyzwalacze": []}
    try:
        korzen = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", tekst.lstrip("\ufeff")))
    except ET.ParseError:
        return pusty
    ns = {"t": NS}

    def pole(sciezka: str, domyslna: str = "", w=korzen) -> str:
        e = w.find(sciezka, ns)
        return (e.text or "").strip() if e is not None else domyslna

    ustawienia = {k: pole(f"t:Settings/t:{k}", d) for k, d in DOMYSLNE.items()}
    ustawienia["RestartOnFailureInterval"] = pole("t:Settings/t:RestartOnFailure/t:Interval")
    ustawienia["RestartOnFailureCount"] = pole("t:Settings/t:RestartOnFailure/t:Count")
    e = korzen.find("t:Triggers", ns)                # nie `or []`: prawdziwość elementu jest przestarzała (3.12)
    wyzwalacze = list(e) if e is not None else []
    return {"opis": pole("t:RegistrationInfo/t:Description"), "polecenie": pole("t:Actions/t:Exec/t:Command"),
            "argumenty": pole("t:Actions/t:Exec/t:Arguments"),
            "wlaczone": pole("t:Settings/t:Enabled", "true").lower() != "false", "ustawienia": ustawienia,
            "wyzwalacze": [e.tag.rsplit("}", 1)[-1] for e in wyzwalacze],
            "wylaczone_wyzwalacze": [e.tag.rsplit("}", 1)[-1] for e in wyzwalacze
                                     if pole("t:Enabled", "true", e).lower() == "false"]}


def _zadanie(wykonaj: Wykonaj, nazwa: str) -> tuple[str, dict | str | None]:
    """("jest", pola) / ("brak", None) / ("nieczytelne", powód): jest na liście, ale definicji nie da się odczytać /
    ("blad", powód): Harmonogram nie podaje nawet listy. Brak potwierdza pełna lista zadań, bo komunikat
    „nie ma takiego zadania” schtasks podaje w języku systemu."""
    kod, wyj = wykonaj([_schtasks(), "/Query", "/TN", nazwa, "/XML"])
    if kod == 0 and "<Task" in wyj:
        return "jest", _czytaj_xml(wyj)
    kod_listy, lista = wykonaj([_schtasks(), "/Query", "/FO", "CSV", "/NH"])
    if kod_listy != 0:
        return "blad", _linia(wyj if kod else lista)
    szukane = "\\" + nazwa.casefold()
    for wiersz in csv.reader(io.StringIO(lista.replace("\r", ""))):
        if wiersz and wiersz[0].strip().casefold() == szukane:
            return "nieczytelne", _linia(wyj)
    return "brak", None


def _dziala_windows(wykonaj: Wykonaj, nazwa: str) -> bool | None:
    kod, wyj = wykonaj([_schtasks(), "/Query", "/TN", nazwa, "/FO", "CSV", "/V", "/NH"])
    if kod != 0:
        return None
    for wiersz in csv.reader(io.StringIO(wyj.replace("\r", ""))):
        if len(wiersz) > 6:                              # kolumny: …, 3 Status, …, 6 Last Result
            return wiersz[6].strip() == WYNIK_DZIALA or wiersz[3].strip().casefold() == "running"
    return None


def _rejestr(rejestr):
    return rejestr if rejestr is not None else (zmiany_hosta.Rejestr() if sciezki.WINDOWS else None)


def _run_nasz(wartosc: str, u: Uklad) -> bool:
    w = wartosc.casefold()
    return str(u.program).casefold() in w or str(u.root).casefold() in w


def _usun_run(u: Uklad, nazwa: str, r) -> bool:
    obecna = r.czytaj(KLUCZ_RUN, nazwa)
    if obecna is None or not _run_nasz(obecna[0], u):
        return False
    r.usun(KLUCZ_RUN, nazwa)
    return True


def _windows_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, rejestr, env) -> dict:
    kto = _uzytkownik_windows()
    nazwa = nazwa_zadania(u, env, kto=kto)
    plik = u.stan / "autostart" / f"{nazwa}.xml"
    wynik = {"system": "windows", "mechanizm": "harmonogram", "nazwa": nazwa, "plik": str(plik),
             "zmieniony": False, "uruchomiony": None, "uwagi": []}
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "nieczytelne":
        raise BladAutostartu(f"W Harmonogramie zadań jest zadanie {nazwa}, ale jego definicji nie da się odczytać "
                             f"({z}), więc go nie nadpisuję. Sprawdź je w taskschd.msc (starą kopię Jarva usuń) "
                             "i włącz autostart jeszcze raz.")
    if jest == "jest" and ZNACZNIK not in z["opis"]:
        raise BladAutostartu(f"W Harmonogramie zadań jest już zadanie {nazwa}, którego nie założył Jarvo. Zmień "
                             "jego nazwę albo je usuń (taskschd.msc) i włącz autostart jeszcze raz.")
    wylaczone = jest == "jest" and (not z["wlaczone"] or bool(z["wylaczone_wyzwalacze"]))
    # najpierw pełna definicja; gdy Harmonogram jej nie przyjmie (np. polityka nie pozwala na zapasowe
    # wyzwalacze), sam wyzwalacz logowania; dopiero potem wpis HKCU Run
    powody: list[str] = []
    for zapasowe in (True, False):
        xml, odcisk = _xml_i_odcisk(argv, kto, u.root, zapasowe)
        zmiany_hosta.dopisz(u, "autostart-windows", tryb="harmonogram", nazwa=nazwa, odcisk=odcisk)
        if jest == "jest" and f"odcisk={odcisk}" in z["opis"]:
            if not wylaczone:
                break                                   # ta sama definicja i włączona: nic do zrobienia
            if not z["wylaczone_wyzwalacze"]:
                # wyłączone całe zadanie (taskschd.msc, program „przyspieszający start”): sam przełącznik
                kod, wyj = wykonaj([_schtasks(), "/Change", "/TN", nazwa, "/ENABLE"])
                if kod == 0:
                    wynik["zmieniony"] = True
                    break
                powody.append(_linia(wyj))
            # wyłączone wyzwalacze albo /Change nie przeszedł: nasza definicja od nowa (Enabled=true wszędzie)
        zapisz_atomowo(plik, xml)
        kod, wyj = wykonaj([_schtasks(), "/Create", "/TN", nazwa, "/XML", str(plik), "/F"])
        if kod == 0:
            wynik["zmieniony"] = True
            break
        powody.append(_linia(wyj))
    else:
        return _windows_run(u, argv, nazwa, rejestr, powody[0], wynik)
    if wylaczone and wynik["zmieniony"]:
        wynik["uwagi"].append(f"Zadanie {nazwa} było wyłączone w Harmonogramie: włączone z powrotem.")
    if not zapasowe:
        wynik["uwagi"].append("Harmonogram nie przyjął zapasowych wyzwalaczy (odblokowanie sesji, co 5 minut"
                              + (f": {powody[0]}" if powody else "") + "). Zostaje start po zalogowaniu; czy po "
                              "awarii Harmonogram podniesie nadzorcę sam, nie wiadomo, więc gdy serwis nie działa, "
                              "uruchom go: jarvo up.")
    r = _rejestr(rejestr)
    if r is not None and _usun_run(u, nazwa, r):     # zapas z czasu odmowy Harmonogramu: dwa starty to za dużo
        wynik["zmieniony"] = True
    kiedy = "po zalogowaniu, po odblokowaniu i co 5 minut, gdy nadzorca nie działa" if zapasowe else "po zalogowaniu"
    wynik["komunikat"] = (f"Autostart {'włączony' if wynik['zmieniony'] else 'bez zmian'}: zadanie Harmonogramu "
                          f"{nazwa} ({kiedy}).")
    if start:
        kod, wyj = wykonaj([_schtasks(), "/Run", "/TN", nazwa])
        wynik["uruchomiony"] = kod == 0
        if kod:
            wynik["uwagi"].append(f"Zadanie jest, ale nie wystartowało: {_linia(wyj)}")
    return wynik


def _windows_run(u: Uklad, argv: list[str], nazwa: str, rejestr, powod: str, wynik: dict) -> dict:
    """Zapas, gdy polityka blokuje Harmonogram: wpis HKCU Run startuje nadzorcę po zalogowaniu (c2)."""
    r = _rejestr(rejestr)
    if r is None:
        raise BladAutostartu(f"Harmonogram zadań odmówił: {powod}")
    wartosc = subprocess.list2cmdline(argv)
    obecna = r.czytaj(KLUCZ_RUN, nazwa)
    if obecna is not None and obecna[0] != wartosc and not _run_nasz(obecna[0], u):
        raise BladAutostartu(f"Harmonogram zadań odmówił ({powod}), a wpis HKCU Run {nazwa} należy do innego "
                             "programu: zostawiam go i autostartu nie włączam.")
    zmiany_hosta.dopisz(u, "autostart-windows", tryb="run", nazwa=nazwa, wartosc=wartosc)
    if obecna is None or obecna[0] != wartosc:
        r.zapisz(KLUCZ_RUN, nazwa, wartosc, zmiany_hosta.REG_SZ)
        wynik["zmieniony"] = True
    wynik.update(mechanizm="run", uruchomiony=False,
                 komunikat=f"Autostart przez wpis HKCU Run {nazwa}: Harmonogram zadań odmówił ({powod}).")
    wynik["uwagi"].append("Nadzorca wstanie po zalogowaniu, ale po awarii sam już nie wstanie, a teraz trzeba go "
                          "uruchomić osobno.")
    return wynik


def _windows_wylacz(u: Uklad, wykonaj: Wykonaj, rejestr, env) -> dict:
    nazwa = nazwa_zadania(u, env)
    wynik = {"system": "windows", "nazwa": nazwa, "usuniety": False, "uwagi": []}
    r = _rejestr(rejestr)
    if r is not None and _usun_run(u, nazwa, r):     # zapas z czasu, gdy Harmonogram odmawiał (może dalej odmawia)
        wynik["usuniety"] = True
    jest, z = _zadanie(wykonaj, nazwa)
    if jest in ("blad", "nieczytelne"):
        if not wynik["usuniety"]:
            raise BladAutostartu(f"Nie mogę sprawdzić zadania {nazwa} w Harmonogramie: {z}")
        wynik["uwagi"].append(f"Zadania {nazwa} w Harmonogramie nie mogę sprawdzić ({z}): zostaje.")
    elif jest == "jest" and ZNACZNIK not in z["opis"]:
        wynik["uwagi"].append(f"Zadanie {nazwa} w Harmonogramie nie jest Jarva: zostawiam je.")
    elif jest == "jest":
        kod, wyj = wykonaj([_schtasks(), "/Delete", "/TN", nazwa, "/F"])
        if kod:
            raise BladAutostartu(f"schtasks /Delete /TN {nazwa}: {_linia(wyj)}")
        wynik["usuniety"] = True
    if wynik["usuniety"]:
        wynik["uwagi"].append("Działający nadzorca pracuje dalej, aż zatrzyma go `jarvo stop` albo wylogowanie.")
    return wynik


def _windows_stan(u: Uklad, wykonaj: Wykonaj, rejestr, env) -> dict:
    nazwa = nazwa_zadania(u, env)
    wynik = _pusty_stan("windows", nazwa, u.stan / "autostart" / f"{nazwa}.xml")
    wynik["ustawienia"] = {}
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "jest":
        # włączony = samo zadanie włączone i choć jeden wyzwalacz, który może je uruchomić
        sam_start = len(z["wyzwalacze"]) > len(z["wylaczone_wyzwalacze"])
        wynik.update(mechanizm="harmonogram", wlaczony=z["wlaczone"] and sam_start,
                     wylaczone_w_systemie=not z["wlaczone"], nasz=ZNACZNIK in z["opis"],
                     ustawienia=z["ustawienia"], wyzwalacze=z["wyzwalacze"],
                     wylaczone_wyzwalacze=z["wylaczone_wyzwalacze"], polecenie=z["polecenie"],
                     argumenty=z["argumenty"], dziala=_dziala_windows(wykonaj, nazwa))
        return wynik
    if jest == "nieczytelne":
        wynik.update(mechanizm="harmonogram", nasz=None, blad=f"definicji zadania nie da się odczytać: {z}")
        return wynik
    if jest == "blad":
        wynik["blad"] = f"Harmonogram nie odpowiada: {z}"
    r = _rejestr(rejestr)
    obecna = r.czytaj(KLUCZ_RUN, nazwa) if r is not None else None
    if obecna is not None:
        wynik.update(mechanizm="run", wlaczony=True, nasz=_run_nasz(obecna[0], u))
    return wynik


def _cofnij_windows(s: dict, wykonaj: Wykonaj, rejestr) -> tuple[str, str]:
    nazwa = s["nazwa"]
    if s.get("tryb") == "run":
        r = _rejestr(rejestr)
        if r is None:
            return "pominiete", f"wpis HKCU Run {nazwa}: rejestr jest tylko na Windows"
        obecna = r.czytaj(KLUCZ_RUN, nazwa)
        if obecna is None:
            return "brak", f"wpis HKCU Run {nazwa}: już go nie ma"
        if obecna[0] != s["wartosc"]:
            return "nie-nasze", f"wpis HKCU Run {nazwa}: zmieniony po instalacji, zostaje"
        r.usun(KLUCZ_RUN, nazwa)
        return "cofniete", f"wpis HKCU Run {nazwa}: usunięty"
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "brak":
        return "brak", f"zadanie Harmonogramu {nazwa}: już go nie ma"
    if jest != "jest":
        return "blad", f"zadanie Harmonogramu {nazwa}: nie mogę go sprawdzić ({z})"
    if f"odcisk={s['odcisk']}" not in z["opis"]:
        return "nie-nasze", f"zadanie Harmonogramu {nazwa}: to już inna definicja, zostaje"
    kod, wyj = wykonaj([_schtasks(), "/Delete", "/TN", nazwa, "/F"])
    if kod:
        return "blad", f"schtasks /Delete /TN {nazwa}: {_linia(wyj)}"
    return "cofniete", f"zadanie Harmonogramu {nazwa}: usunięte"


# ---------------------------------------------------------------- macOS: LaunchAgent

def _uid() -> int:
    return os.getuid() if hasattr(os, "getuid") else 0


def _plik_agenta(dom: Path | None, etykieta: str) -> Path:
    return _dom(dom) / "Library" / "LaunchAgents" / f"{etykieta}.plist"


def plist_agenta(argv, u: Uklad, etykieta: str = ETYKIETA, *, zmienne: dict | None = None) -> bytes:
    """LaunchAgent nadzorcy; `zmienne` idą do EnvironmentVariables (zwykle zmienne_uslugi(u, "macos"))."""
    log = str(u.logi / "autostart.log")
    dane = {"Label": etykieta, "ProgramArguments": _argv(argv, "macos"), "WorkingDirectory": str(u.root),
            "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 30,
            "ExitTimeOut": LIMIT_ZATRZYMANIA, "StandardOutPath": log, "StandardErrorPath": log}
    if zmienne:
        dane["EnvironmentVariables"] = _zmienne(zmienne)
    return plistlib.dumps(dane, sort_keys=False)


def _bootstrap(wykonaj: Wykonaj, domena: str, plik: Path, proby: int = 3) -> tuple[int, str]:
    kod, wyj = 1, ""
    for i in range(proby):
        kod, wyj = wykonaj([LAUNCHCTL, "bootstrap", domena, str(plik)])
        if kod == 0:
            break
        if i < proby - 1:
            time.sleep(PRZERWA_LAUNCHCTL)
    return kod, wyj


def _wylaczony_w_launchd(wykonaj: Wykonaj, domena: str, etykieta: str) -> bool | None:
    """Czy usługę wyłączono w launchd (`launchctl disable`; stan przetrwa restart i blokuje bootstrap).
    `print-disabled` podaje wiersz `"etykieta" => disabled` (starsze macOS: `=> true`); None: nie wiadomo."""
    kod, wyj = wykonaj([LAUNCHCTL, "print-disabled", domena])
    if kod != 0:
        return None
    m = re.search(rf'^\s*"{re.escape(etykieta)}"\s*=>\s*(\w+)', wyj, re.M)
    return bool(m) and m.group(1).lower() in ("disabled", "true")


def _macos_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, dom, env) -> dict:
    et = etykieta_agenta(u, env)
    plik = _plik_agenta(dom, et)
    dane = plist_agenta(argv, u, et, zmienne=zmienne_uslugi(u, "macos", env, dom))
    domena = f"gui/{_uid()}"
    cel = f"{domena}/{et}"
    wynik = {"system": "macos", "mechanizm": "launchagent", "nazwa": et, "plik": str(plik), "zmieniony": False,
             "uruchomiony": None, "uwagi": []}
    zmiany_hosta.dopisz(u, "autostart-macos", etykieta=et, sciezka=str(plik), sha256=_sha(dane))
    zaladowany = wykonaj([LAUNCHCTL, "print", cel])[0] == 0
    rowny = plik.is_file() and plik.read_bytes() == dane
    if not rowny:
        u.logi.mkdir(parents=True, exist_ok=True)
        zapisz_atomowo(plik, dane, tryb=0o644)
        wynik["zmieniony"] = True
    if _wylaczony_w_launchd(wykonaj, domena, et):
        kod, wyj = wykonaj([LAUNCHCTL, "enable", cel])
        if kod:
            raise BladAutostartu(f"LaunchAgent {et} jest wyłączony w launchd (launchctl disable), a launchctl enable "
                                 f"{cel} odmówił: {_linia(wyj)}")
        wynik["zmieniony"] = True
        wynik["uwagi"].append(f"LaunchAgent {et} był wyłączony w launchd (launchctl disable): włączony z powrotem.")
    wynik["komunikat"] = f"Autostart {'włączony' if wynik['zmieniony'] else 'bez zmian'}: LaunchAgent {et} ({plik})."
    if not start:
        if wynik["zmieniony"] or not zaladowany:
            wynik["uwagi"].append("LaunchAgent wczyta się przy następnym logowaniu.")
        return wynik
    if zaladowany and rowny:
        kod, wyj = wykonaj([LAUNCHCTL, "kickstart", cel])      # bez -k: działającego nadzorcy nie restartuje
        wynik["uruchomiony"] = kod == 0
        return wynik
    if zaladowany:
        wykonaj([LAUNCHCTL, "bootout", cel])                  # stara definicja: SIGTERM, potem nowa
    kod, wyj = _bootstrap(wykonaj, domena, plik)
    if kod != 0:
        raise BladAutostartu(f"launchctl bootstrap {domena} {plik}: {_linia(wyj)}. Plik zostaje i wczyta się przy "
                             "następnym logowaniu.")
    wynik["uruchomiony"] = True
    wynik["uwagi"].append("macOS może pokazać powiadomienie o elementach działających w tle: to Jarvo.")
    return wynik


def _macos_wylacz(u: Uklad, wykonaj: Wykonaj, dom, env) -> dict:
    et = etykieta_agenta(u, env)
    plik, cel = _plik_agenta(dom, et), f"gui/{_uid()}/{et}"
    wynik = {"system": "macos", "nazwa": et, "usuniety": False, "uwagi": []}
    if wykonaj([LAUNCHCTL, "print", cel])[0] == 0:
        kod, wyj = wykonaj([LAUNCHCTL, "bootout", cel])      # launchd wysyła SIGTERM i czeka ExitTimeOut
        if kod:
            wynik["uwagi"].append(f"launchctl bootout {cel}: {_linia(wyj)}")
        wynik["usuniety"] = True
    if plik.is_file():
        plik.unlink()
        wynik["usuniety"] = True
    return wynik


def _macos_stan(u: Uklad, wykonaj: Wykonaj, dom, env) -> dict:
    et = etykieta_agenta(u, env)
    plik = _plik_agenta(dom, et)
    domena = f"gui/{_uid()}"
    wynik = _pusty_stan("macos", et, plik)
    if plik.is_file():
        try:
            nasz = plistlib.loads(plik.read_bytes()).get("Label") == et
        except Exception:  # noqa: BLE001 - uszkodzony plist to po prostu „nie nasz”
            nasz = False
        wylaczony = _wylaczony_w_launchd(wykonaj, domena, et)
        wynik.update(mechanizm="launchagent", wlaczony=wylaczony is not True, nasz=nasz)
    kod, wyj = wykonaj([LAUNCHCTL, "print", f"{domena}/{et}"])
    if kod == 0:
        stan = re.search(r"^\s*state = (\S+)", wyj, re.M)
        pid = re.search(r"^\s*pid = (\d+)", wyj, re.M)
        wynik.update(dziala=bool(stan and stan.group(1) == "running"), pid=int(pid.group(1)) if pid else None)
    elif wynik["mechanizm"]:
        wynik["dziala"] = False
    return wynik


def _cofnij_macos(s: dict, wykonaj: Wykonaj) -> tuple[str, str]:
    plik = Path(s["sciezka"])
    if not plik.is_file():
        return "brak", f"LaunchAgent {s['etykieta']}: pliku już nie ma"
    if _sha(plik.read_bytes()) != s["sha256"]:
        return "nie-nasze", f"LaunchAgent {s['etykieta']}: plik zmieniony po instalacji, zostaje"
    wykonaj([LAUNCHCTL, "bootout", f"gui/{_uid()}/{s['etykieta']}"])   # niezaładowany to też dobrze
    plik.unlink()
    return "cofniete", f"LaunchAgent {s['etykieta']}: usunięty"


# ---------------------------------------------------------------- Linux: systemd --user

def _systemctl() -> str:
    return shutil.which("systemctl") or "/usr/bin/systemctl"


def _loginctl() -> str:
    return shutil.which("loginctl") or "/usr/bin/loginctl"


def _menedzer(wykonaj: Wykonaj) -> tuple[dict | None, str]:
    """Środowisko menedżera usług użytkownika (`systemctl --user show-environment`); None, gdy nie ma user busa."""
    kod, wyj = wykonaj([_systemctl(), "--user", "show-environment"])
    if kod != 0:
        return None, wyj
    return {m.group(1): m.group(2) for m in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", wyj, re.M)}, wyj


def _kandydaci_jednostek(env: dict, dom, menedzer: dict) -> list[Path]:
    """Gdzie może być katalog jednostek użytkownika: XDG_CONFIG_HOME z powłoki, z menedżera i domyślne ~/.config."""
    wynik: list[Path] = []
    for baza in (env.get("XDG_CONFIG_HOME"), menedzer.get("XDG_CONFIG_HOME")):
        if baza and os.path.isabs(baza) and Path(baza) / "systemd" / "user" not in wynik:
            wynik.append(Path(baza) / "systemd" / "user")
    domyslny = _dom(dom) / ".config" / "systemd" / "user"
    return wynik if domyslny in wynik else [*wynik, domyslny]


def _katalog_jednostek(wykonaj: Wykonaj, env: dict, dom, menedzer: dict | None, nazwa: str) -> Path:
    """Katalog jednostek, w którym menedżer usług użytkownika naprawdę szuka (jego UnitPath). systemd --user nie
    czyta ~/.profile, więc XDG_CONFIG_HOME ustawione tylko w powłoce bywa mu obce, a jednostka obok jego ścieżki
    to „Unit file does not exist”. Bez busa: kandydat, w którym jest już nasz plik."""
    kandydaci = _kandydaci_jednostek(env, dom, menedzer or {})
    if menedzer is None:
        return next((k for k in kandydaci if (k / nazwa).exists()), kandydaci[0])
    kod, wyj = wykonaj([_systemctl(), "--user", "show", "--property=UnitPath"])
    sciezki_menedzera = f" {wyj.strip().removeprefix('UnitPath=')} " if kod == 0 else ""
    for k in kandydaci:
        if f" {k} " in sciezki_menedzera:
            return k
    # starszy systemd albo własna ścieżka jednostek: tak jak liczy ją sam menedżer
    baza = menedzer.get("XDG_CONFIG_HOME") or ""
    return (Path(baza) if os.path.isabs(baza) else _dom(dom) / ".config") / "systemd" / "user"


def _obca_jednostka(wykonaj: Wykonaj, plik: Path, nazwa: str) -> str | None:
    """Dlaczego nie wolno zapisać jednostki `nazwa` (None: wolno): w naszym katalogu leży cudzy plik bez znacznika,
    menedżer ma jednostkę o tej nazwie gdzie indziej (nasza by ją przesłoniła) albo usługa jest zamaskowana."""
    rada = "Cudzej jednostki Jarvo nie nadpisuje: zmień jej nazwę albo ją usuń i włącz autostart jeszcze raz."
    if plik.is_file() and ZNACZNIK not in plik.read_text(encoding="utf-8", errors="replace"):
        return f"w {plik} jest już jednostka {nazwa}, której nie założył Jarvo. {rada}"
    kod, wyj = wykonaj([_systemctl(), "--user", "show", nazwa, "--property=FragmentPath"])
    fragment = wyj.strip().removeprefix("FragmentPath=").strip() if kod == 0 else ""
    if fragment == "/dev/null":
        return (f"usługa {nazwa} jest zamaskowana (systemctl --user mask). Odblokuj ją: systemctl --user unmask "
                f"{nazwa} i włącz autostart jeszcze raz.")
    if fragment and Path(fragment) != plik:
        try:
            nasza = ZNACZNIK in Path(fragment).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            nasza = True          # nieaktualna pamięć menedżera (plik usunięty bez daemon-reload): nic nie przesłonimy
        except OSError:
            nasza = False
        if not nasza:
            return (f"menedżer usług ma już jednostkę {nazwa} w {fragment}, której nie założył Jarvo, a nasza by ją "
                    f"przesłoniła. {rada}")
    return None


def _slowo_systemd(s: str, *, dolar: bool = True) -> str:
    """Jedno słowo wiersza systemd w cudzysłowie: ucieczki C (\\\\ i \\"), %% zamiast % (specyfikatory) i, gdy
    `dolar`, $$ zamiast $ (ExecStart podstawia $ZMIENNE; Environment= nie). Program dostaje dokładnie `s`."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return '"' + (s.replace("$", "$$") if dolar else s) + '"'


def jednostka_systemd(argv, u: Uklad, *, zmienne: dict | None = None) -> str:
    """Jednostka systemd --user nadzorcy; `zmienne` idą do Environment= (zwykle zmienne_uslugi(u, "linux"))."""
    argv = _argv(argv, "linux")
    if str(u.root) != str(u.root).strip():
        raise ValueError(f"autostart: korzeń ze spacją na brzegu: {u.root!r}")
    linie = [f"# {ZNACZNIK} Jarvo: nadzorca procesów (jarvo serwis). Zapisuje go `jarvo autostart on`, usuwa "
             "`jarvo autostart off`.",
             "[Unit]",
             "Description=Jarvo: nadzorca procesów (jarvo serwis)",
             "",
             "[Service]",
             "Type=simple",
             "ExecStart=" + " ".join(_slowo_systemd(a) for a in argv),
             "WorkingDirectory=" + str(u.root).replace("%", "%%")]
    linie += ["Environment=" + _slowo_systemd(f"{k}={v}", dolar=False) for k, v in _zmienne(zmienne).items()]
    linie += ["Restart=on-failure",
              "RestartSec=10",
              # SIGTERM tylko do nadzorcy; resztę grupy systemd zabija SIGKILL-em zaraz po jego wyjściu, więc
              # nadzorca kończy się dopiero po bramie i panelu
              "KillMode=mixed",
              f"TimeoutStopSec={LIMIT_ZATRZYMANIA}",
              "",
              "[Install]",
              "WantedBy=default.target",
              ""]
    return "\n".join(linie)


def _bez_busa(wyj: str) -> BladAutostartu:
    return BladAutostartu("Brak usług systemd użytkownika: `systemctl --user` nie odpowiada "
                          f"({_linia(wyj)}). Tak bywa w WSL bez systemd, w kontenerze, w sesji z su albo sudo "
                          "i w systemie bez systemd. Zaloguj się zwykłą sesją (pulpit, konsola albo ssh) i włącz "
                          "autostart jeszcze raz; do tego czasu (a bez systemd zawsze) nadzorcę uruchamia jarvo up.")


def _linux_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, dom, env) -> dict:
    nazwa = nazwa_jednostki(u, env)
    menedzer, wyj = _menedzer(wykonaj)
    if menedzer is None:
        raise _bez_busa(wyj)
    plik = _katalog_jednostek(wykonaj, env, dom, menedzer, nazwa) / nazwa
    powod = _obca_jednostka(wykonaj, plik, nazwa)
    if powod:
        raise BladAutostartu(f"Autostartu nie włączam: {powod}")
    tresc = jednostka_systemd(argv, u, zmienne=zmienne_uslugi(u, "linux", env, dom))
    wynik = {"system": "linux", "mechanizm": "systemd", "nazwa": nazwa, "plik": str(plik), "zmieniony": False,
             "uruchomiony": None, "uwagi": []}
    zmiany_hosta.dopisz(u, "autostart-linux", jednostka=nazwa, sciezka=str(plik), sha256=_sha(tresc))
    if not (plik.is_file() and plik.read_bytes() == tresc.encode("utf-8")):
        zapisz_atomowo(plik, tresc, tryb=0o644)
        wynik["zmieniony"] = True
        kod, wyj = wykonaj([_systemctl(), "--user", "daemon-reload"])
        if kod:
            raise BladAutostartu(f"systemctl --user daemon-reload: {_linia(wyj)}")
    polecenie = ["enable", "--now", nazwa] if start else ["enable", nazwa]
    kod, wyj = wykonaj([_systemctl(), "--user", *polecenie])
    if kod:
        raise BladAutostartu(f"systemctl --user {' '.join(polecenie)}: {_linia(wyj)}. Szczegóły: "
                             f"systemctl --user status {nazwa}")
    wynik["uruchomiony"] = True if start else None
    wynik["komunikat"] = (f"Autostart {'włączony' if wynik['zmieniony'] else 'bez zmian'}: usługa systemd "
                          f"użytkownika {nazwa} (systemctl --user status {nazwa}).")
    if wynik["zmieniony"]:
        wynik["uwagi"].append("Usługa działa w sesji zalogowanego użytkownika; start bez logowania tylko z "
                              "lingerem, na wyraźne życzenie.")
    return wynik


def _usun_jednostke(wykonaj: Wykonaj, plik: Path, nazwa: str) -> None:
    wykonaj([_systemctl(), "--user", "disable", "--now", nazwa])          # SIGTERM i TimeoutStopSec na drenaż
    link = plik.parent / "default.target.wants" / nazwa
    if link.is_symlink():                                               # bez busa disable nie zdejmie dowiązania
        link.unlink()
    plik.unlink()
    wykonaj([_systemctl(), "--user", "daemon-reload"])


def _linux_wylacz(u: Uklad, wykonaj: Wykonaj, dom, env) -> dict:
    nazwa = nazwa_jednostki(u, env)
    plik = _katalog_jednostek(wykonaj, env, dom, _menedzer(wykonaj)[0], nazwa) / nazwa
    wynik = {"system": "linux", "nazwa": nazwa, "usuniety": False, "uwagi": []}
    if not plik.is_file():
        return wynik
    if ZNACZNIK not in plik.read_text(encoding="utf-8", errors="replace"):
        wynik["uwagi"].append(f"Jednostka {plik} nie jest Jarva: zostawiam ją.")
        return wynik
    _usun_jednostke(wykonaj, plik, nazwa)
    wynik["usuniety"] = True
    return wynik


def _linux_stan(u: Uklad, wykonaj: Wykonaj, dom, env) -> dict:
    nazwa = nazwa_jednostki(u, env)
    menedzer, _ = _menedzer(wykonaj)
    plik = _katalog_jednostek(wykonaj, env, dom, menedzer, nazwa) / nazwa
    wynik = _pusty_stan("linux", nazwa, plik)
    wynik["bus"] = menedzer is not None
    if plik.is_file():
        wynik.update(mechanizm="systemd", nasz=ZNACZNIK in plik.read_text(encoding="utf-8", errors="replace"))
        if wynik["bus"]:
            wynik["wlaczony"] = wykonaj([_systemctl(), "--user", "is-enabled", nazwa])[1].strip() == "enabled"
            wynik["dziala"] = wykonaj([_systemctl(), "--user", "is-active", nazwa])[1].strip() == "active"
            if wynik["dziala"]:
                kod, wyj = wykonaj([_systemctl(), "--user", "show", nazwa, "--property=MainPID", "--value"])
                wynik["pid"] = int(wyj.strip()) if kod == 0 and wyj.strip().isdigit() and wyj.strip() != "0" else None
        else:
            wynik["blad"] = "brak usług systemd użytkownika (user bus)"
    wynik["linger"] = _linger(wykonaj, _uzytkownik_posix())
    return wynik


def _cofnij_linux(s: dict, wykonaj: Wykonaj) -> tuple[str, str]:
    plik, nazwa = Path(s["sciezka"]), s["jednostka"]
    if not plik.is_file():
        return "brak", f"jednostka {nazwa}: pliku już nie ma"
    if _sha(plik.read_bytes()) != s["sha256"]:
        return "nie-nasze", f"jednostka {nazwa}: plik zmieniony po instalacji, zostaje"
    _usun_jednostke(wykonaj, plik, nazwa)
    return "cofniete", f"jednostka systemd --user {nazwa}: usunięta"


def _uzytkownik_posix() -> str:
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except (ImportError, KeyError, AttributeError):
        import getpass
        return getpass.getuser()


def _linger(wykonaj: Wykonaj, kto: str) -> bool | None:
    kod, wyj = wykonaj([_loginctl(), "show-user", kto, "--property=Linger", "--value"])
    return wyj.strip().lower() == "yes" if kod == 0 else None


def _odcisk_lingera(kto: str) -> str | None:
    """Czas zapisu (ns) pliku `<KATALOG_LINGER>/<użytkownik>`: logind zakłada go albo dotyka przy enable-linger,
    a usuwa przy disable-linger. Inny odcisk niż we wpisie = linger włączył potem ktoś inny. None: brak pliku."""
    try:
        return str((Path(KATALOG_LINGER) / kto).stat().st_mtime_ns)
    except OSError:
        return None


def _nasz_linger(s: dict) -> bool:
    """Czy włączony linger to dalej ten z wpisu. Wpis bez odcisku (plik był nieczytelny przy włączaniu): tak."""
    return not s.get("odcisk") or _odcisk_lingera(s["uzytkownik"]) == s["odcisk"]


def wlacz_linger(u: Uklad, wykonaj: Wykonaj | None = None, *, log=print) -> bool:
    """Linux: nadzorca wstaje po uruchomieniu komputera, także bez logowania (`loginctl enable-linger`). Tylko na
    wyraźne życzenie właściciela (N08). Zwraca True, gdy coś zmienił; linger włączony wcześniej przez kogoś innego
    zostaje bez wpisu (to nie nasza zmiana). Wpis w dzienniku powstaje dopiero po udanym włączeniu (wyjątek od
    zasady „wpis przed zmianą”), z odciskiem pliku lingera: wpis bez zmiany albo bez odcisku kazałby
    `jarvo uninstall` wyłączyć linger, który właściciel włączy kiedyś sam."""
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    log = log or (lambda *_: None)
    kto = _uzytkownik_posix()
    if _linger(wykonaj, kto):
        log(f"Linger dla {kto} był już włączony: nic nie zmieniam.")
        return False
    kod, wyj = wykonaj([_loginctl(), "enable-linger", kto])
    if kod:
        raise BladAutostartu(f"loginctl enable-linger {kto}: {_linia(wyj)}. Bez uprawnień zrobi to administrator: "
                             f"sudo loginctl enable-linger {kto}")
    zmiany_hosta.dopisz(u, "linger", uzytkownik=kto, odcisk=_odcisk_lingera(kto))
    log(f"Linger włączony: usługi {kto} (w tym nadzorca Jarva) wstają po uruchomieniu komputera bez logowania.")
    return True


def wylacz_linger(u: Uklad, wykonaj: Wykonaj | None = None, *, log=print) -> bool:
    """Wyłącza linger tylko wtedy, gdy włączył go Jarvo (wpis w dzienniku i ten sam plik lingera), i usuwa wpis:
    linger, który właściciel włączy potem sam, nie jest już nasz i `jarvo uninstall` go nie ruszy. Gdy ktoś
    wyłączył nasz linger albo włączył go od nowa po swojemu, też tylko usuwa wpis. Zwraca True, gdy wyłączył."""
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    log = log or (lambda *_: None)
    kto = _uzytkownik_posix()
    nasze = [w["szczegoly"] for w in zmiany_hosta.wpisy(u)
             if w["rodzaj"] == "linger" and w["szczegoly"].get("uzytkownik") == kto]
    if not nasze:
        log(f"Linger dla {kto} nie włączał Jarvo: zostawiam.")
        return False
    stan = _linger(wykonaj, kto)
    if stan is None:
        raise BladAutostartu(f"loginctl show-user {kto} nie odpowiada: nie wiem, czy linger jest włączony. Wpis "
                             "w dzienniku zostaje do następnej próby.")
    wylacza = bool(stan) and _nasz_linger(nasze[-1])
    if wylacza:
        kod, wyj = wykonaj([_loginctl(), "disable-linger", kto])
        if kod:
            raise BladAutostartu(f"loginctl disable-linger {kto}: {_linia(wyj)}")
    for s in nasze:
        zmiany_hosta.zapomnij(u, "linger", **s)
    if wylacza:
        log(f"Linger wyłączony: usługi {kto} startują dopiero po zalogowaniu.")
    else:
        log(f"Linger dla {kto} " + ("włączył po Jarvie ktoś inny: zostawiam go" if stan else "był już wyłączony")
            + " i usuwam tylko wpis z dziennika.")
    return wylacza


def _cofnij_linger(s: dict, wykonaj: Wykonaj) -> tuple[str, str]:
    kto = s["uzytkownik"]
    stan = _linger(wykonaj, kto)
    if stan is None:
        return "blad", f"linger {kto}: loginctl nie odpowiada"
    if not stan:
        return "brak", f"linger {kto}: już wyłączony"
    if not _nasz_linger(s):
        return "nie-nasze", f"linger {kto}: włączony ponownie po Jarvie, zostaje"
    kod, wyj = wykonaj([_loginctl(), "disable-linger", kto])
    if kod:
        return "blad", f"loginctl disable-linger {kto}: {_linia(wyj)}"
    return "cofniete", f"linger {kto}: wyłączony"


# ---------------------------------------------------------------- polecenia

def wlacz(u: Uklad, argv, wykonaj: Wykonaj | None = None, *, start: bool = True, system: str | None = None,
          dom: Path | None = None, rejestr=None, env: dict | None = None, log=print) -> dict:
    """Włącza autostart nadzorcy i domyślnie od razu go uruchamia; wyłączony w systemie (Harmonogram, launchd,
    systemctl disable) włącza z powrotem. `argv` to pełne polecenie z bezwzględną ścieżką programu, np.
    [<python>/pythonw.exe, -I, -X, utf8, <app>/jarvo/start.py, serwis]. Wpis w dzienniku zmian hosta powstaje
    przed zmianą; drugi raz z tym samym argv niczego nie zmienia. Zwraca {"system", "mechanizm", "nazwa", "plik",
    "zmieniony", "uruchomiony", "uwagi", "komunikat"}. `env` (domyślnie os.environ) daje przyrostek nazwy
    i środowisko usługi; `system`, `dom` (katalog domowy) i `rejestr` (atrapa winreg) są dla testów."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    env = _env(env)
    argv = _argv(argv, s)
    if s == "windows":
        wynik = _windows_wlacz(u, argv, wykonaj, start, rejestr, env)
    elif s == "macos":
        wynik = _macos_wlacz(u, argv, wykonaj, start, dom, env)
    else:
        wynik = _linux_wlacz(u, argv, wykonaj, start, dom, env)
    if log:
        for linia in [wynik.get("komunikat"), *wynik["uwagi"]]:
            if linia:
                log(linia)
    return wynik


def wylacz(u: Uklad, wykonaj: Wykonaj | None = None, *, system: str | None = None, dom: Path | None = None,
           rejestr=None, env: dict | None = None, log=print) -> dict:
    """Wyłącza autostart (`jarvo autostart off`): usuwa zadanie, wpis HKCU Run, LaunchAgenta albo jednostkę, jeśli
    są Jarva. Wpisy w dzienniku zostają (cofnięcie przy odinstalowaniu powie wtedy „już nie ma”). Zwraca
    {"system", "nazwa", "usuniety", "uwagi"}."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    env = _env(env)
    if s == "windows":
        wynik = _windows_wylacz(u, wykonaj, rejestr, env)
    elif s == "macos":
        wynik = _macos_wylacz(u, wykonaj, dom, env)
    else:
        wynik = _linux_wylacz(u, wykonaj, dom, env)
    if log:
        log(f"Autostart wyłączony ({wynik['nazwa']})." if wynik["usuniety"] else "Autostart nie był włączony.")
        for linia in wynik["uwagi"]:
            log(linia)
    return wynik


def stan(u: Uklad, wykonaj: Wykonaj | None = None, *, system: str | None = None, dom: Path | None = None,
         rejestr=None, env: dict | None = None) -> dict:
    """Stan autostartu dla `jarvo status` i doctora: {"system", "mechanizm" (harmonogram, run, launchagent,
    systemd albo None), "nazwa", "plik", "wlaczony" (False także dla wyłączonego w systemie i dla zadania bez
    żadnego włączonego wyzwalacza), "nasz" (None = nie wiadomo), "dziala" (None = nie wiadomo), "pid", "opis"};
    Windows dodaje "ustawienia", "wyzwalacze", "wylaczone_wyzwalacze" i "wylaczone_w_systemie" z zarejestrowanego
    zadania, Linux "bus" i "linger"."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    env = _env(env)
    if s == "windows":
        wynik = _windows_stan(u, wykonaj, rejestr, env)
    elif s == "macos":
        wynik = _macos_stan(u, wykonaj, dom, env)
    else:
        wynik = _linux_stan(u, wykonaj, dom, env)
    wynik["opis"] = _opis(wynik)
    return wynik


def cofnij_wpis(u: Uklad, wpis: dict, wykonaj: Wykonaj, *, rejestr=None) -> tuple[str, str]:
    """Cofnięcie jednego wpisu autostartu z dziennika (woła je zmiany_hosta.cofnij): tylko to, co dalej nasze."""
    rodzaj, s = wpis["rodzaj"], wpis["szczegoly"]
    if rodzaj == "autostart-windows":
        return _cofnij_windows(s, wykonaj, rejestr)
    if rodzaj == "autostart-macos":
        return _cofnij_macos(s, wykonaj)
    if rodzaj == "autostart-linux":
        return _cofnij_linux(s, wykonaj)
    if rodzaj == "linger":
        return _cofnij_linger(s, wykonaj)
    return "blad", f"{rodzaj}: to nie wpis autostartu"

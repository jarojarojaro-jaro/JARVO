"""Autostart nadzorcy Jarva (docs/NATYWNIE.md: H22, c2 „Autostart”, N08 `jarvo autostart on/off/status`, D08).

Mechanizm systemu uruchamia `jarvo serwis` po zalogowaniu i podnosi go po awarii. Procesami Jarva zarządza już sam
nadzorca (zasada 5: bez NSSM, WinSW i supervisord). Wszystko bez admina i bez sudo:

- Windows: zadanie Harmonogramu z pliku XML w UTF-16, `schtasks /Create /TN <nazwa> /XML <plik> /F` bez
  wcześniejszego kasowania (nieudana rejestracja nie zabiera działającego zadania), start `/Run`, usunięcie
  `/Delete /F`, stan `/Query`. Wyzwalacze: logowanie z opóźnieniem PT15S, a zapasowo odblokowanie sesji i co
  5 minut (gdy nadzorca działa, IgnoreNew nic nie robi). Każdy wyzwalacz ma UserId bieżącego użytkownika (SID):
  wyzwalacza „dowolny użytkownik” Harmonogram nie przyjmuje bez admina (tak `schtasks /SC ONLOGON` i Hermes bez
  UserId kończą na „Odmowa dostępu”). Dokumentacja wymaga admina tylko przy wyzwalaczu startu systemu; konta bez
  admina z zapasowymi wyzwalaczami nikt jeszcze nie sprawdził (runner CI jest adminem), więc gdy Harmonogram
  odrzuci pełną definicję, rejestrujemy sam wyzwalacz logowania, a gdy odmówi w ogóle (polityka), wpis HKCU Run
  (start po zalogowaniu, bez podtrzymania po awarii). Ustawienia: bez zatrzymania na baterii, bez limitu czasu
  (PT0S), priorytet 5 (normalny), ponowienie co minutę do 999 razy. Domyślne `schtasks /SC ONLOGON` zatrzymałoby
  nadzorcę na baterii i po 72 godzinach.
- macOS: LaunchAgent `~/Library/LaunchAgents/pl.jarvo.nadzorca.plist`: RunAtLoad, KeepAlive przy wyjściu z błędem,
  ThrottleInterval 30, ExitTimeOut 45, logi do `<logi>`, bez ProcessType Background (dławiłby render);
  `launchctl bootstrap/bootout/print` w domenie gui/<uid>. Powiadomienie „Background Items” jest normalne.
- Linux: `~/.config/systemd/user/jarvo.service`: Restart=on-failure, KillMode=mixed, TimeoutStopSec=45 (dłużej niż
  30 s drenażu bramy), `systemctl --user`. Bez user busa (WSL bez systemd, kontener, su) jasny komunikat. Linger
  (start bez logowania) tylko na wyraźne życzenie: osobne `wlacz_linger()` z wpisem w dzienniku.

Instalacja spod JARVO_ROOT (próby, CI) dostaje nazwy z przyrostkiem skrótu korzenia (`Jarvo-1a2b3c4d`,
`pl.jarvo.nadzorca-1a2b3c4d`, `jarvo-1a2b3c4d.service`), więc nie rusza prawdziwego autostartu właściciela.
Każde włączenie trafia do dziennika zmian hosta przed zmianą (jarvo/zmiany_hosta.py), więc `jarvo uninstall` je
cofnie. Polecenia systemu idą przez `wykonaj(argv) -> (kod, wyjście)`: domyślnie subprocess, w testach atrapa.

Umowa z nadzorcą: zwykłe zatrzymanie kończy `jarvo serwis` kodem 0 (launchd i systemd go wtedy nie podnoszą),
a na Windows zapasowe wyzwalacze uruchomią go znowu, więc nadzorca przy starcie szanuje znacznik planowanego
zatrzymania i trzyma blokadę jednej instancji. `wylacz()` na Windows nie zatrzymuje działającego nadzorcy
(`schtasks /End` zabiłby go bez drenażu bramy); na macOS i Linuksie system wysyła mu SIGTERM. Zadanie
Harmonogramu nie ustawia zmiennych środowiska: próbna instalacja spod JARVO_ROOT podaje korzeń w argv albo launcher
bierze go ze swojej ścieżki; LaunchAgent i jednostka dostają JARVO_ROOT w środowisku.
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
WYNIK_DZIALA = "267009"                  # SCHED_S_TASK_RUNNING (0x41301) w kolumnie „Last Result” schtasks /V
# wartości, które Harmonogram przyjmuje, gdy elementu nie ma (eksport pomija domyślne)
DOMYSLNE = {"MultipleInstancesPolicy": "IgnoreNew", "DisallowStartIfOnBatteries": "true",
            "StopIfGoingOnBatteries": "true", "ExecutionTimeLimit": "PT72H", "Priority": "7"}


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


# ---------------------------------------------------------------- nazwy

def _klucz_korzenia(p: Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _przyrostek(u: Uklad, env: dict | None = None) -> str:
    """"" dla domyślnego korzenia, "-<8 znaków sha256 korzenia>" dla każdego innego (JARVO_ROOT)."""
    env = {k: v for k, v in (os.environ if env is None else env).items() if k != "JARVO_ROOT"}
    try:
        domyslny = sciezki.uklad(env).root
    except sciezki.BladUkladu:
        domyslny = None
    if domyslny is not None and _klucz_korzenia(domyslny) == _klucz_korzenia(u.root):
        return ""
    return "-" + hashlib.sha256(_klucz_korzenia(u.root).encode("utf-8")).hexdigest()[:8]


def nazwa_zadania(u: Uklad, env: dict | None = None) -> str:
    """Windows: „Jarvo” dla domyślnego korzenia, „Jarvo-<8 znaków skrótu korzenia>” dla JARVO_ROOT."""
    return "Jarvo" + _przyrostek(u, env)


def etykieta_agenta(u: Uklad, env: dict | None = None) -> str:
    """macOS: etykieta LaunchAgenta (pl.jarvo.nadzorca, z przyrostkiem jak nazwa_zadania)."""
    return ETYKIETA + _przyrostek(u, env)


def nazwa_jednostki(u: Uklad, env: dict | None = None) -> str:
    """Linux: jednostka systemd --user (jarvo.service, z przyrostkiem jak nazwa_zadania)."""
    return f"{JEDNOSTKA}{_przyrostek(u, env)}.service"


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
    if not s.get("nasz"):
        czesci.append("nie założył go Jarvo")
    elif not s.get("wlaczony") and not s.get("blad"):
        czesci.append("wyłączone w systemie")
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
    """Najważniejsze pola z `schtasks /Query /XML` (eksport pomija wartości domyślne: uzupełniamy je)."""
    pusty = {"opis": "", "polecenie": "", "argumenty": "", "wlaczone": True, "ustawienia": dict(DOMYSLNE),
             "wyzwalacze": []}
    try:
        korzen = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", tekst.lstrip("\ufeff")))
    except ET.ParseError:
        return pusty
    ns = {"t": NS}

    def pole(sciezka: str, domyslna: str = "") -> str:
        e = korzen.find(sciezka, ns)
        return (e.text or "").strip() if e is not None else domyslna

    ustawienia = {k: pole(f"t:Settings/t:{k}", d) for k, d in DOMYSLNE.items()}
    ustawienia["RestartOnFailureInterval"] = pole("t:Settings/t:RestartOnFailure/t:Interval")
    ustawienia["RestartOnFailureCount"] = pole("t:Settings/t:RestartOnFailure/t:Count")
    wyzwalacze = korzen.find("t:Triggers", ns)
    return {"opis": pole("t:RegistrationInfo/t:Description"), "polecenie": pole("t:Actions/t:Exec/t:Command"),
            "argumenty": pole("t:Actions/t:Exec/t:Arguments"),
            "wlaczone": pole("t:Settings/t:Enabled", "true").lower() != "false", "ustawienia": ustawienia,
            "wyzwalacze": [e.tag.rsplit("}", 1)[-1] for e in wyzwalacze] if wyzwalacze is not None else []}


def _zadanie(wykonaj: Wykonaj, nazwa: str) -> tuple[str, dict | str | None]:
    """("jest", pola) / ("brak", None) / ("blad", powód). Brak potwierdza pełna lista zadań, bo komunikat
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
            return "blad", _linia(wyj)                   # jest na liście, a definicji nie dało się odczytać
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


def _windows_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, rejestr) -> dict:
    nazwa = nazwa_zadania(u)
    kto = _uzytkownik_windows()
    plik = u.stan / "autostart" / f"{nazwa}.xml"
    wynik = {"system": "windows", "mechanizm": "harmonogram", "nazwa": nazwa, "plik": str(plik),
             "zmieniony": False, "uruchomiony": None, "uwagi": []}
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "jest" and ZNACZNIK not in z["opis"]:
        raise BladAutostartu(f"W Harmonogramie zadań jest już zadanie {nazwa}, którego nie założył Jarvo. Zmień "
                             "jego nazwę albo je usuń (taskschd.msc) i włącz autostart jeszcze raz.")
    # najpierw pełna definicja; gdy Harmonogram jej nie przyjmie (np. polityka nie pozwala na zapasowe
    # wyzwalacze), sam wyzwalacz logowania z ponowieniem po awarii; dopiero potem wpis HKCU Run
    powody: list[str] = []
    for zapasowe in (True, False):
        xml, odcisk = _xml_i_odcisk(argv, kto, u.root, zapasowe)
        zmiany_hosta.dopisz(u, "autostart-windows", tryb="harmonogram", nazwa=nazwa, odcisk=odcisk)
        if jest == "jest" and f"odcisk={odcisk}" in z["opis"]:
            break
        zapisz_atomowo(plik, xml)
        kod, wyj = wykonaj([_schtasks(), "/Create", "/TN", nazwa, "/XML", str(plik), "/F"])
        if kod == 0:
            wynik["zmieniony"] = True
            break
        powody.append(_linia(wyj))
    else:
        return _windows_run(u, argv, nazwa, rejestr, powody[0], wynik)
    if not zapasowe:
        wynik["uwagi"].append("Harmonogram nie przyjął zapasowych wyzwalaczy (odblokowanie sesji, co 5 minut"
                              + (f": {powody[0]}" if powody else "") + "). Zostaje start po zalogowaniu i "
                              "ponowienie po awarii.")
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


def _windows_wylacz(u: Uklad, wykonaj: Wykonaj, rejestr) -> dict:
    nazwa = nazwa_zadania(u)
    wynik = {"system": "windows", "nazwa": nazwa, "usuniety": False, "uwagi": []}
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "blad":
        raise BladAutostartu(f"Nie mogę sprawdzić zadania {nazwa} w Harmonogramie: {z}")
    if jest == "jest" and ZNACZNIK not in z["opis"]:
        wynik["uwagi"].append(f"Zadanie {nazwa} w Harmonogramie nie jest Jarva: zostawiam je.")
    elif jest == "jest":
        kod, wyj = wykonaj([_schtasks(), "/Delete", "/TN", nazwa, "/F"])
        if kod:
            raise BladAutostartu(f"schtasks /Delete /TN {nazwa}: {_linia(wyj)}")
        wynik["usuniety"] = True
    r = _rejestr(rejestr)
    if r is not None and _usun_run(u, nazwa, r):
        wynik["usuniety"] = True
    if wynik["usuniety"]:
        wynik["uwagi"].append("Działający nadzorca pracuje dalej, aż zatrzyma go `jarvo stop` albo wylogowanie.")
    return wynik


def _windows_stan(u: Uklad, wykonaj: Wykonaj, rejestr) -> dict:
    nazwa = nazwa_zadania(u)
    wynik = _pusty_stan("windows", nazwa, u.stan / "autostart" / f"{nazwa}.xml")
    wynik["ustawienia"] = {}
    jest, z = _zadanie(wykonaj, nazwa)
    if jest == "jest":
        wynik.update(mechanizm="harmonogram", wlaczony=z["wlaczone"], nasz=ZNACZNIK in z["opis"],
                     ustawienia=z["ustawienia"], wyzwalacze=z["wyzwalacze"], polecenie=z["polecenie"],
                     argumenty=z["argumenty"], dziala=_dziala_windows(wykonaj, nazwa))
    elif jest == "blad":
        wynik["blad"] = f"Harmonogram nie odpowiada: {z}"
    else:
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
    if jest == "blad":
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
    return (Path(dom) if dom else Path.home()) / "Library" / "LaunchAgents" / f"{etykieta}.plist"


def plist_agenta(argv, u: Uklad, etykieta: str = ETYKIETA, *, jarvo_root: bool = False) -> bytes:
    """LaunchAgent nadzorcy. `jarvo_root=True` przekazuje korzeń próbnej instalacji (JARVO_ROOT); domyślnej nie,
    bo na Linuksie JARVO_ROOT przenosi logi i cache z katalogów XDG (jarvo/sciezki.py)."""
    log = str(u.logi / "autostart.log")
    dane = {"Label": etykieta, "ProgramArguments": _argv(argv, "macos"), "WorkingDirectory": str(u.root),
            "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 30,
            "ExitTimeOut": LIMIT_ZATRZYMANIA, "StandardOutPath": log, "StandardErrorPath": log}
    if jarvo_root:
        dane["EnvironmentVariables"] = {"JARVO_ROOT": str(u.root)}
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


def _macos_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, dom) -> dict:
    et = etykieta_agenta(u)
    plik = _plik_agenta(dom, et)
    dane = plist_agenta(argv, u, et, jarvo_root=bool(_przyrostek(u)))
    domena, cel = f"gui/{_uid()}", f"gui/{_uid()}/{et}"
    wynik = {"system": "macos", "mechanizm": "launchagent", "nazwa": et, "plik": str(plik), "zmieniony": False,
             "uruchomiony": None, "uwagi": []}
    zmiany_hosta.dopisz(u, "autostart-macos", etykieta=et, sciezka=str(plik), sha256=_sha(dane))
    zaladowany = wykonaj([LAUNCHCTL, "print", cel])[0] == 0
    rowny = plik.is_file() and plik.read_bytes() == dane
    if not rowny:
        u.logi.mkdir(parents=True, exist_ok=True)
        zapisz_atomowo(plik, dane, tryb=0o644)
        wynik["zmieniony"] = True
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


def _macos_wylacz(u: Uklad, wykonaj: Wykonaj, dom) -> dict:
    et = etykieta_agenta(u)
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


def _macos_stan(u: Uklad, wykonaj: Wykonaj, dom) -> dict:
    et = etykieta_agenta(u)
    plik = _plik_agenta(dom, et)
    wynik = _pusty_stan("macos", et, plik)
    if plik.is_file():
        try:
            nasz = plistlib.loads(plik.read_bytes()).get("Label") == et
        except Exception:  # noqa: BLE001 - uszkodzony plist to po prostu „nie nasz”
            nasz = False
        wynik.update(mechanizm="launchagent", wlaczony=True, nasz=nasz)
    kod, wyj = wykonaj([LAUNCHCTL, "print", f"gui/{_uid()}/{et}"])
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


def _katalog_jednostek(dom: Path | None) -> Path:
    if dom:
        return Path(dom) / ".config" / "systemd" / "user"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"


def _slowo_systemd(s: str, *, zmienne: bool = True) -> str:
    """Jedno słowo wiersza systemd w cudzysłowie: ucieczki C (\\\\ i \\"), %% zamiast % (specyfikatory) i, gdy
    `zmienne`, $$ zamiast $ (ExecStart podstawia $ZMIENNE; Environment= nie). Program dostaje dokładnie `s`."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return '"' + (s.replace("$", "$$") if zmienne else s) + '"'


def jednostka_systemd(argv, u: Uklad, *, jarvo_root: bool = False) -> str:
    """Jednostka systemd --user nadzorcy. `jarvo_root` jak w plist_agenta."""
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
    if jarvo_root:
        linie.append("Environment=" + _slowo_systemd(f"JARVO_ROOT={u.root}", zmienne=False))
    linie += ["Restart=on-failure",
              "RestartSec=10",
              "KillMode=mixed",                               # SIGTERM do nadzorcy, reszta grupy po limicie
              f"TimeoutStopSec={LIMIT_ZATRZYMANIA}",
              "",
              "[Install]",
              "WantedBy=default.target",
              ""]
    return "\n".join(linie)


def _bez_busa(wyj: str) -> BladAutostartu:
    return BladAutostartu("Brak usług systemd użytkownika: `systemctl --user` nie odpowiada "
                          f"({_linia(wyj)}). Tak bywa w WSL bez systemd, w kontenerze i w sesji z su albo sudo. "
                          "Zaloguj się zwykłą sesją (pulpit, konsola albo ssh) i włącz autostart jeszcze raz; "
                          "do tego czasu nadzorcę uruchamia `jarvo serwis`.")


def _linux_wlacz(u: Uklad, argv: list[str], wykonaj: Wykonaj, start: bool, dom) -> dict:
    nazwa = nazwa_jednostki(u)
    kod, wyj = wykonaj([_systemctl(), "--user", "show-environment"])
    if kod != 0:
        raise _bez_busa(wyj)
    plik = _katalog_jednostek(dom) / nazwa
    tresc = jednostka_systemd(argv, u, jarvo_root=bool(_przyrostek(u)))
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


def _linux_wylacz(u: Uklad, wykonaj: Wykonaj, dom) -> dict:
    nazwa = nazwa_jednostki(u)
    plik = _katalog_jednostek(dom) / nazwa
    wynik = {"system": "linux", "nazwa": nazwa, "usuniety": False, "uwagi": []}
    if not plik.is_file():
        return wynik
    if ZNACZNIK not in plik.read_text(encoding="utf-8", errors="replace"):
        wynik["uwagi"].append(f"Jednostka {plik} nie jest Jarva: zostawiam ją.")
        return wynik
    _usun_jednostke(wykonaj, plik, nazwa)
    wynik["usuniety"] = True
    return wynik


def _linux_stan(u: Uklad, wykonaj: Wykonaj, dom) -> dict:
    nazwa = nazwa_jednostki(u)
    plik = _katalog_jednostek(dom) / nazwa
    wynik = _pusty_stan("linux", nazwa, plik)
    wynik["bus"] = wykonaj([_systemctl(), "--user", "show-environment"])[0] == 0
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


def wlacz_linger(u: Uklad, wykonaj: Wykonaj | None = None, *, log=print) -> bool:
    """Linux: nadzorca wstaje po uruchomieniu komputera, także bez logowania (`loginctl enable-linger`). Tylko na
    wyraźne życzenie właściciela (N08), z wpisem w dzienniku. Zwraca True, gdy coś zmienił; linger włączony
    wcześniej przez kogoś innego zostaje bez wpisu (to nie nasza zmiana)."""
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    log = log or (lambda *_: None)
    kto = _uzytkownik_posix()
    if _linger(wykonaj, kto):
        log(f"Linger dla {kto} był już włączony: nic nie zmieniam.")
        return False
    zmiany_hosta.dopisz(u, "linger", uzytkownik=kto)
    kod, wyj = wykonaj([_loginctl(), "enable-linger", kto])
    if kod:
        raise BladAutostartu(f"loginctl enable-linger {kto}: {_linia(wyj)}. Bez uprawnień zrobi to administrator: "
                             f"sudo loginctl enable-linger {kto}")
    log(f"Linger włączony: usługi {kto} (w tym nadzorca Jarva) wstają po uruchomieniu komputera bez logowania.")
    return True


def wylacz_linger(u: Uklad, wykonaj: Wykonaj | None = None, *, log=print) -> bool:
    """Wyłącza linger tylko wtedy, gdy włączył go Jarvo (jest wpis w dzienniku)."""
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    log = log or (lambda *_: None)
    kto = _uzytkownik_posix()
    if not any(w["rodzaj"] == "linger" and w["szczegoly"].get("uzytkownik") == kto for w in zmiany_hosta.wpisy(u)):
        log(f"Linger dla {kto} nie włączał Jarvo: zostawiam.")
        return False
    if not _linger(wykonaj, kto):
        return False
    kod, wyj = wykonaj([_loginctl(), "disable-linger", kto])
    if kod:
        raise BladAutostartu(f"loginctl disable-linger {kto}: {_linia(wyj)}")
    log(f"Linger wyłączony: usługi {kto} startują dopiero po zalogowaniu.")
    return True


def _cofnij_linger(s: dict, wykonaj: Wykonaj) -> tuple[str, str]:
    kto = s["uzytkownik"]
    stan = _linger(wykonaj, kto)
    if stan is None:
        return "blad", f"linger {kto}: loginctl nie odpowiada"
    if not stan:
        return "brak", f"linger {kto}: już wyłączony"
    kod, wyj = wykonaj([_loginctl(), "disable-linger", kto])
    if kod:
        return "blad", f"loginctl disable-linger {kto}: {_linia(wyj)}"
    return "cofniete", f"linger {kto}: wyłączony"


# ---------------------------------------------------------------- polecenia

def wlacz(u: Uklad, argv, wykonaj: Wykonaj | None = None, *, start: bool = True, system: str | None = None,
          dom: Path | None = None, rejestr=None, log=print) -> dict:
    """Włącza autostart nadzorcy i domyślnie od razu go uruchamia. `argv` to pełne polecenie z bezwzględną
    ścieżką programu, np. [<python>/pythonw.exe, -I, -X, utf8, <app>/jarvo/start.py, serwis]. Wpis w dzienniku
    zmian hosta powstaje przed zmianą; drugi raz z tym samym argv niczego nie zmienia. Zwraca {"system",
    "mechanizm", "nazwa", "plik", "zmieniony", "uruchomiony", "uwagi", "komunikat"}. `system`, `dom` (katalog
    domowy) i `rejestr` (atrapa winreg) są dla testów."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    argv = _argv(argv, s)
    if s == "windows":
        wynik = _windows_wlacz(u, argv, wykonaj, start, rejestr)
    elif s == "macos":
        wynik = _macos_wlacz(u, argv, wykonaj, start, dom)
    else:
        wynik = _linux_wlacz(u, argv, wykonaj, start, dom)
    if log:
        for linia in [wynik.get("komunikat"), *wynik["uwagi"]]:
            if linia:
                log(linia)
    return wynik


def wylacz(u: Uklad, wykonaj: Wykonaj | None = None, *, system: str | None = None, dom: Path | None = None,
           rejestr=None, log=print) -> dict:
    """Wyłącza autostart (`jarvo autostart off`): usuwa zadanie, LaunchAgenta albo jednostkę, jeśli są Jarva.
    Wpisy w dzienniku zostają (cofnięcie przy odinstalowaniu powie wtedy „już nie ma”). Zwraca {"system",
    "nazwa", "usuniety", "uwagi"}."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    if s == "windows":
        wynik = _windows_wylacz(u, wykonaj, rejestr)
    elif s == "macos":
        wynik = _macos_wylacz(u, wykonaj, dom)
    else:
        wynik = _linux_wylacz(u, wykonaj, dom)
    if log:
        log(f"Autostart wyłączony ({wynik['nazwa']})." if wynik["usuniety"] else "Autostart nie był włączony.")
        for linia in wynik["uwagi"]:
            log(linia)
    return wynik


def stan(u: Uklad, wykonaj: Wykonaj | None = None, *, system: str | None = None, dom: Path | None = None,
         rejestr=None) -> dict:
    """Stan autostartu dla `jarvo status` i doctora: {"system", "mechanizm" (harmonogram, run, launchagent,
    systemd albo None), "nazwa", "plik", "wlaczony", "nasz", "dziala" (None = nie wiadomo), "pid", "opis"};
    Windows dodaje "ustawienia" i "wyzwalacze" z zarejestrowanego zadania, Linux "bus" i "linger"."""
    s = _system(system)
    wykonaj = wykonaj or zmiany_hosta.uruchom_domyslnie
    if s == "windows":
        wynik = _windows_stan(u, wykonaj, rejestr)
    elif s == "macos":
        wynik = _macos_stan(u, wykonaj, dom)
    else:
        wynik = _linux_stan(u, wykonaj, dom)
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

"""Telefon testowy Twórcy aplikacji natywnie: `jarvo android status|on|off|ekran` (docs/NATYWNIE.md: N12, U04, U05,
E13, F08, decyzja I24; etap E11).

W kontenerze telefonem testowym był emulator Google albo Redroid w usłudze floty, a ekran pokazywał ws-scrcpy w HQ
(proxy :9122). Natywnie, bez Dockera, telefonem jest telefon właściciela z debugowaniem USB albo bezprzewodowym
(Android 11+) albo emulator z Android Studio, przez adb z Android SDK Platform-Tools r37.0.1 (vendor/natywne.yaml,
`kiedy: przy-uzyciu`). Ekran pokazuje scrcpy 5.0.1 w osobnym oknie. Podgląd w HQ (port 9122) jest natywnie wyłączony
(I24): zamiast strony w panelu jest okno scrcpy na tym komputerze.

  jarvo android on [--akceptuje-licencje] [--wifi ADRES:PORT] [--paruj ADRES:PORT [--kod KOD]] [--urzadzenie SERIAL]
        platform-tools przy pierwszym użyciu (licencja Google: akceptacja właściciela przed pierwszym pobraniem,
        zapamiętana w <stan>/android.json), serwer adb z ADB_MDNS=0 (bez szukania telefonów w sieci lokalnej),
        parowanie i połączenie przez Wi-Fi na adres podany wprost, wybór urządzenia. Flota (urzadzenie.py) bierze adb
        z <stan>/narzedzia.json, a stan i numer urządzenia z <stan>/android.json
  jarvo android ekran [--urzadzenie SERIAL] [--bez-dzwieku] [--rozmiar PIKSELE]
        okno scrcpy z ekranem telefonu (scrcpy przy pierwszym użyciu, ten sam adb co flota); zamknięcie okna
        kończy podgląd, a `jarvo android off` zamyka je razem z serwerem adb
  jarvo android off [--zostaw-adb]
        flota przestaje używać telefonu: znacznik w <stan>/android.json, rozłączenie Wi-Fi, zatrzymanie serwera adb
  jarvo android status [--json]
        adb, licencja, stan, urządzenia (serwera adb nie uruchamia, gdy telefon jest wyłączony), scrcpy, podgląd w HQ

Integracja z jarvo/cli.py jak jarvo/wiedza_cli.py: `dodaj_polecenia(sub)` dopisuje polecenie `android`,
`sprawdzenia(u, ot)` daje wyniki dla `jarvo doctor` (telefon nie jest wymagany: brak platform-tools to „ok” z opisem).
Moduł działa też sam: `python -I -X utf8 jarvo/android.py status`. Wyjście adb idzie do pliku, nie do potoku: serwer
adb, który polecenie uruchamia w tle, dziedziczy uchwyty, więc potok nie dostałby końca (Windows), jak przy demonie
agent-browsera. Na macOS i Linuksie klucz adb właściciela (~/.android/adbkey z katalogu domowego konta) idzie do
serwera przez ADB_VENDOR_KEYS: terminal agenta ma inny HOME (H24), a bez tego telefon pytałby o zgodę dla nowego
klucza po restarcie serwera z terminala agenta (Windows: adb bierze profil z konta, nie z USERPROFILE).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):                         # `python jarvo/android.py`: pakiet jarvo z katalogu wyżej
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvo import przenosne, przy_uzyciu, sciezki, srodowisko  # noqa: E402
from jarvo.sciezki import WINDOWS, Uklad  # noqa: E402

STAN = "android.json"                                  # <stan>/android.json: licencja, włączony, urządzenie, Wi-Fi
KLUCZE_ADB = ("adbkey", "adbkey.pub")                  # klucz adb w <katalog konta>/.android
PLATFORM_TOOLS = "platform-tools"
SCRCPY = "scrcpy"
LICENCJA_URL = "https://developer.android.com/studio/terms"
ADRES = re.compile(r"^(?:\[[0-9A-Fa-f:.%]+\]|[A-Za-z0-9][A-Za-z0-9.\-]*):\d{1,5}$")   # host:port, IPv6 w nawiasach
SERIAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-\[\]%]{0,127}$")
KOD = re.compile(r"^\d{6}$")                           # kod parowania z „Debugowanie bezprzewodowe” (6 cyfr)
CZAS_ADB = 60.0
STANY = {"device": "gotowy", "unauthorized": "czeka na zgodę na telefonie", "offline": "nie odpowiada",
         "no permissions": "brak uprawnień do USB", "authorizing": "łączy się", "connecting": "łączy się",
         "recovery": "tryb recovery", "sideload": "tryb sideload", "bootloader": "bootloader"}
RADY = {
    "unauthorized": "odblokuj telefon i zaakceptuj okno „Zezwolić na debugowanie USB?” (zaznacz „Zawsze zezwalaj "
                    "z tego komputera”), potem jarvo android on jeszcze raz",
    "offline": "odłącz i podłącz kabel albo wyłącz i włącz debugowanie USB, potem jarvo android on",
    "no permissions": "Linux: reguły udev dla telefonów z Androidem (np. pakiet android-sdk-platform-tools-common, "
                      "wymaga sudo) i ponowne podłączenie kabla",
}
JAK_PODLACZYC = ("Telefon: Ustawienia → Informacje o telefonie → 7 razy „Numer kompilacji” (opcje programisty), potem "
                 "Opcje programisty → Debugowanie USB i kabel do tego komputera (Windows: przy niektórych telefonach "
                 "sterownik USB producenta). Bez kabla (Android 11+): Debugowanie bezprzewodowe → Parowanie kodem i "
                 "jarvo android on --paruj ADRES:PORT --kod KOD, potem --wifi ADRES:PORT z ekranu debugowania. "
                 "Emulator z Android Studio adb widzi sam.")
PODGLAD_HQ = ("podgląd ekranu w HQ (przycisk 📱, port 9122) jest w instalacji natywnej wyłączony (decyzja I24): "
              "ekran pokazuje okno scrcpy, `jarvo android ekran`")


def _wynik(nazwa: str, stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": nazwa, "stan": stan, "opis": opis, "rada": rada}


def _teraz() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- stan i programy

def stan_androida(u: Uklad) -> dict:
    """`<stan>/android.json`: {"licencja_sdk": {"zaakceptowano", "adres"}, "wlaczony", "serial", "wifi", "kiedy"}."""
    return srodowisko.wczytaj_json(u.stan / STAN)


def zapisz_stan(u: Uklad, dane: dict) -> None:
    przenosne.zapisz_atomowo(u.stan / STAN, json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def adb(u: Uklad) -> Path | None:
    """adb z platform-tools tej instalacji; na Linuksie arm64 (Google nie wydaje tam platform-tools) adb z systemu."""
    p = przy_uzyciu.program_narzedzia(przy_uzyciu.gotowe_narzedzie(u, PLATFORM_TOOLS), "adb")
    if p is None and sciezki.platforma() == "linux-arm64":
        systemowy = przenosne.program("adb")
        p = Path(systemowy) if systemowy and os.path.isabs(systemowy) else None
    return p


def scrcpy(u: Uklad) -> Path | None:
    return przy_uzyciu.program_narzedzia(przy_uzyciu.gotowe_narzedzie(u, SCRCPY), "scrcpy")


def katalog_adb() -> Path | None:
    """`.android` w katalogu domowym konta, gdzie adb trzyma klucz (adbkey, adbkey.pub): Windows z profilu konta
    (SHGetFolderPathW, jak adb: USERPROFILE z terminala agenta nic tu nie zmienia, sprawdzone), POSIX z bazy kont,
    nie z HOME (terminal agenta ma HOME profilu, H24)."""
    if WINDOWS:
        import ctypes
        bufor = ctypes.create_unicode_buffer(32768)
        try:
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, bufor) != 0:   # CSIDL_PROFILE
                return None
        except (AttributeError, OSError):
            return None
        return Path(bufor.value) / ".android"
    import pwd
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".android"
    except (KeyError, OSError):
        return None


def klucz_wlasciciela() -> Path | None:
    """Klucz adb właściciela dla ADB_VENDOR_KEYS: na macOS i Linuksie `<katalog konta>/.android/adbkey`; na Windows
    None, bo adb i tak bierze profil z konta, a nie z USERPROFILE."""
    if WINDOWS:
        return None
    k = katalog_adb()
    return k / "adbkey" if k is not None else None


def klucze_przed() -> set[str]:
    k = katalog_adb()
    return {n for n in KLUCZE_ADB if k is not None and (k / n).is_file()}


def zapisz_klucze(u: Uklad, przed: set[str]) -> list[Path]:
    """Klucz adb, który założył serwer uruchomiony przez `jarvo android on` (nie było go wcześniej): wpis „plik”
    w dzienniku zmian hosta (D08) po fakcie, jak linger, bo treść generuje adb; `jarvo uninstall` usunie go, gdy się nie
    zmienił. Klucza, który był (Android Studio, wcześniejszy adb), nie zapisujemy: nie jest nasz."""
    from jarvo import zmiany_hosta
    k = katalog_adb()
    zapisane = []
    for nazwa in KLUCZE_ADB:
        p = k / nazwa if k is not None else None
        if p is not None and nazwa not in przed and p.is_file():
            zmiany_hosta.dopisz(u, "plik", sciezka=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            zapisane.append(p)
    return zapisane


def env_adb(u: Uklad, baza: dict | None = None) -> dict:
    """Otoczenie adb: ADB_MDNS=0 (z manifestu platform-tools) i na macOS i Linuksie klucz adb właściciela
    w ADB_VENDOR_KEYS (telefon zna już ten klucz, więc po restarcie serwera z terminala agenta nie pyta o zgodę)."""
    env = dict(os.environ if baza is None else baza)
    w = przy_uzyciu.gotowe_narzedzie(u, PLATFORM_TOOLS) or {}
    env.update({str(k): str(v) for k, v in (w.get("env") or {}).items()})
    env.setdefault("ADB_MDNS", "0")
    klucz = klucz_wlasciciela()
    if klucz is not None and klucz.is_file():
        obecne = [x for x in str(env.get("ADB_VENDOR_KEYS") or "").split(os.pathsep) if x]
        env["ADB_VENDOR_KEYS"] = os.pathsep.join(dict.fromkeys([*obecne, str(klucz)]))
    return env


def uruchom_adb(program: Path | str, argv: list[str], env: dict, czas: float = CZAS_ADB) -> tuple[int, str]:
    """(kod, wyjście) adb. Wyjście do pliku tymczasowego, nie do potoku: `adb start-server` (i każde polecenie, które
    uruchamia serwer) zostawia proces w tle z uchwytami polecenia."""
    with tempfile.TemporaryFile() as plik:
        try:
            p = subprocess.run([str(program), *argv], stdin=subprocess.DEVNULL, stdout=plik, stderr=subprocess.STDOUT,
                               env=env, timeout=czas, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            kod = p.returncode
        except subprocess.TimeoutExpired:
            kod = 124
        except OSError as e:
            return 127, f"nie uruchomię {program}: {e.strerror or e}"
        plik.seek(0)
        tekst = plik.read().decode("utf-8", errors="replace")
    return kod, tekst.replace("\r\n", "\n").strip()


def wersja_adb(program: Path | str, env: dict) -> str | None:
    """Wersja platform-tools z `adb version` („Version 37.0.1-…”) bez uruchamiania serwera."""
    kod, tekst = uruchom_adb(program, ["version"], env, czas=20)
    m = re.search(r"^Version\s+(\S+)", tekst, re.M)
    return (m.group(1).split("-")[0] if m else "?") if kod == 0 else None


def urzadzenia(tekst: str) -> list[dict]:
    """Wiersze `adb devices -l`: [{"serial", "stan", "model", "usb", "transport"}]."""
    wynik = []
    for linia in tekst.splitlines():
        linia = linia.strip()
        if not linia or linia.startswith(("List of devices", "*", "adb ")):
            continue
        czesci = linia.split(None, 1)
        if len(czesci) < 2:
            continue
        serial, reszta = czesci
        stan = "no permissions" if reszta.startswith("no permissions") else reszta.split()[0]
        cechy = dict(x.split(":", 1) for x in reszta.split() if ":" in x and not x.startswith(("http", "[http")))
        wynik.append({"serial": serial, "stan": stan, "model": (cechy.get("model") or "").replace("_", " ") or None,
                      "usb": "usb" in cechy, "transport": cechy.get("transport_id")})
    return wynik


def lista_urzadzen(program: Path | str, env: dict) -> tuple[list[dict], str | None]:
    """(urządzenia, błąd): `adb devices -l` (uruchamia serwer adb, gdy go nie ma)."""
    kod, tekst = uruchom_adb(program, ["devices", "-l"], env)
    if kod:
        return [], tekst[-300:] or f"adb devices: kod {kod}"
    return urzadzenia(tekst), None


def wybierz(lista: list[dict], chce: str | None = None, poprzedni: str | None = None) -> tuple[str | None, str]:
    """(serial, powód): wskazany (musi być na liście), jedyny gotowy albo poprzedni, gdy wciąż jest gotowy."""
    gotowe = [d["serial"] for d in lista if d["stan"] == "device"]
    if chce:
        if any(d["serial"] == chce for d in lista):
            return chce, "wskazany"
        return None, f"adb nie widzi urządzenia {chce}"
    if len(gotowe) == 1:
        return gotowe[0], "jedyne gotowe"
    if poprzedni and poprzedni in gotowe:
        return poprzedni, "wybrane wcześniej"
    if not gotowe:
        return None, "brak gotowego urządzenia"
    return None, f"kilka gotowych urządzeń ({', '.join(gotowe)}): wskaż jedno, --urzadzenie SERIAL"


def _opis_urzadzenia(d: dict) -> str:
    stan = STANY.get(d["stan"], d["stan"])
    gdzie = "USB" if d.get("usb") else ("emulator" if d["serial"].startswith("emulator-") else
                                        ("Wi-Fi" if ":" in d["serial"] else "adb"))
    return f"{d.get('model') or 'urządzenie'} ({d['serial']}, {gdzie}): {stan}"


def _android_wersja(program: Path, serial: str, env: dict) -> str | None:
    kod, tekst = uruchom_adb(program, ["-s", serial, "shell", "getprop", "ro.build.version.release"], env, czas=20)
    return tekst.strip().splitlines()[-1] if kod == 0 and tekst.strip() else None


# ---------------------------------------------------------------- licencja

def tekst_licencji(app: Path | None = None, u: Uklad | None = None) -> str:
    mb = przy_uzyciu.rozmiar_mb(app or przy_uzyciu.app_instalacji(u), PLATFORM_TOOLS) if (app or u) else None
    return ("Android SDK Platform-Tools (adb) to program Google na licencji Android Software Development Kit License "
            f"Agreement: {LICENCJA_URL}. Jarvo pobiera go wprost od Google (dl.google.com, "
            f"{mb or 'ok. 8'} MB, bez kopii u nas) i sprawdza sumę SHA-256; scrcpy (ekran telefonu) ma w paczce ten "
            "sam adb.")


def zgoda_na_licencje(u: Uklad, a, wejscie=None, wyjscie=None) -> bool:
    """Zgoda właściciela na licencję SDK przed pierwszym pobraniem: zapamiętana, --akceptuje-licencje albo pytanie
    w terminalu (bez terminala: odmowa z radą)."""
    st = stan_androida(u)
    if st.get("licencja_sdk"):
        return True
    wejscie = wejscie or sys.stdin
    wyjscie = wyjscie or sys.stdout
    print(tekst_licencji(u=u), file=wyjscie)
    if not getattr(a, "akceptuje_licencje", False):
        if wejscie is None or not getattr(wejscie, "isatty", lambda: False)():
            print("Bez terminala nie zapytam o licencję: uruchom jarvo android on --akceptuje-licencje, jeśli ją "
                  "akceptujesz.", file=wyjscie)
            return False
        print("Akceptujesz tę licencję? [t/N] ", end="", file=wyjscie, flush=True)
        odp = (wejscie.readline() or "").strip().lower()
        if odp not in ("t", "tak", "y", "yes"):
            print("\nBez akceptacji licencji nie pobieram programów z adb Google (platform-tools, scrcpy).",
                  file=wyjscie)
            return False
    st["licencja_sdk"] = {"zaakceptowano": _teraz(), "adres": LICENCJA_URL}
    zapisz_stan(u, st)
    return True


# ---------------------------------------------------------------- polecenia

def _bez_instalacji(u: Uklad) -> int:
    print(f"Jarvo nie jest zainstalowane natywnie w {u.root}: telefon testowy działa w instalacji natywnej (w "
          "kontenerze: bin/jarvo android).", file=sys.stderr)
    return 1


def _zapewnij_adb(u: Uklad, a) -> Path | None:
    p = adb(u)
    if p is not None:
        return p
    if sciezki.platforma() == "linux-arm64":
        print("Google nie wydaje platform-tools na Linux arm64. Zainstaluj adb z pakietów systemu (np. sudo apt "
              "install adb) i uruchom jarvo android on jeszcze raz.", file=sys.stderr)
        return None
    if not zgoda_na_licencje(u, a):
        return None
    try:
        przy_uzyciu.narzedzie(u, PLATFORM_TOOLS, log=print)
    except przy_uzyciu.BladPrzyUzyciu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return None
    return adb(u)


def polecenie_on(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    for nazwa, wartosc, wzor in (("--wifi", a.wifi, ADRES), ("--paruj", a.paruj, ADRES),
                                 ("--urzadzenie", a.urzadzenie, SERIAL)):
        if wartosc and not wzor.match(wartosc):
            print(f"{nazwa} {wartosc!r}: potrzebny " + ("adres ADRES:PORT z ekranu debugowania bezprzewodowego"
                                                        if wzor is ADRES else "numer z `adb devices`"),
                  file=sys.stderr)
            return 2
    program = _zapewnij_adb(u, a)
    if program is None:
        return 1
    st = stan_androida(u)
    env = env_adb(u)
    wersja = wersja_adb(program, env)
    przed = klucze_przed()
    kod, tekst = uruchom_adb(program, ["start-server"], env)
    if kod:
        print(f"BŁĄD: serwer adb nie wstał (kod {kod}): {tekst[-300:]}", file=sys.stderr)
        return 1
    zapisz_klucze(u, przed)                              # nowy klucz adb: ślad poza katalogiem Jarva (D08)
    env = env_adb(u)                                     # klucz właściciela już jest (adb założył go przy starcie)
    if a.paruj:
        kodp = a.kod
        if not kodp and getattr(sys.stdin, "isatty", lambda: False)():
            print("Kod parowania z telefonu (6 cyfr): ", end="", flush=True)
            kodp = (sys.stdin.readline() or "").strip()
        if not kodp or not KOD.match(kodp):
            print("--kod: 6 cyfr z okna „Paruj urządzenie za pomocą kodu” na telefonie.", file=sys.stderr)
            return 2
        kod, tekst = uruchom_adb(program, ["pair", a.paruj, kodp], env)
        if kod or "Successfully paired" not in tekst:
            print(f"BŁĄD: parowanie z {a.paruj} się nie udało: {tekst[-300:]}", file=sys.stderr)
            return 1
        print(f"Sparowano z {a.paruj}. Teraz połączenie: jarvo android on --wifi ADRES:PORT (port z ekranu "
              "„Debugowanie bezprzewodowe”, inny niż port parowania).")
    if a.wifi:
        kod, tekst = uruchom_adb(program, ["connect", a.wifi], env)
        if kod or not re.search(r"connected to|already connected", tekst):
            print(f"BŁĄD: adb connect {a.wifi}: {tekst[-300:]}", file=sys.stderr)
            return 1
        st["wifi"] = a.wifi
    elif st.get("wifi"):                                  # po restarcie serwera adb połączenie Wi-Fi trzeba odnowić
        uruchom_adb(program, ["connect", st["wifi"]], env, czas=20)
    lista, blad = lista_urzadzen(program, env)
    if blad:
        print(f"BŁĄD: adb devices: {blad}", file=sys.stderr)
        return 1
    serial, powod = wybierz(lista, a.urzadzenie or a.wifi, st.get("serial"))
    if a.urzadzenie and serial is None:
        print(f"BŁĄD: {powod}. Urządzenia: " + ("; ".join(_opis_urzadzenia(d) for d in lista) or "brak"),
              file=sys.stderr)
        return 1
    st.update(wlaczony=True, serial=serial, kiedy=_teraz())
    zapisz_stan(u, st)
    print(f"Telefon testowy Twórcy aplikacji: włączony (adb {wersja or '?'}, {program}).")
    for d in lista:
        print(f"  {_opis_urzadzenia(d)}" + (f"; rada: {RADY[d['stan']]}" if d["stan"] in RADY else ""))
    if serial:
        android = _android_wersja(program, serial, env)
        print(f"Urządzenie floty: {serial}" + (f" (Android {android})" if android else "") + f" [{powod}]. Twórca "
              "aplikacji instaluje na nim aplikację, robi zrzuty i testy wrogie (urzadzenie.py).")
    else:
        print(f"Urządzenie floty: jeszcze nie wybrane ({powod}). " + (JAK_PODLACZYC if not lista else
              "Gdy będzie jedno gotowe urządzenie, flota weźmie je sama."))
    print(f"Ekran telefonu w osobnym oknie: jarvo android ekran. Uwaga: {PODGLAD_HQ}.")
    return 0


def polecenie_off(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    st = stan_androida(u)
    program = adb(u)
    if program is not None:
        env = env_adb(u)
        if st.get("wifi"):
            uruchom_adb(program, ["disconnect", st["wifi"]], env, czas=20)
        if not getattr(a, "zostaw_adb", False):
            uruchom_adb(program, ["kill-server"], env, czas=20)  # okno scrcpy traci połączenie i zamyka się samo
    st.update(wlaczony=False, kiedy=_teraz())
    zapisz_stan(u, st)
    print("Telefon testowy wyłączony: Twórca aplikacji go nie używa (aplikacje na telefonie zostają). Włączenie: "
          "jarvo android on.")
    return 0


def uruchom_okno(argv: list[str], **kw) -> subprocess.Popen:
    """Program z oknem (scrcpy) odpięty od terminala; testy podmieniają tę funkcję."""
    return subprocess.Popen(argv, **kw)


def polecenie_ekran(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    st = stan_androida(u)
    program = adb(u)
    if not st.get("wlaczony") or program is None:
        print("Telefon testowy jest wyłączony: najpierw jarvo android on.", file=sys.stderr)
        return 1
    if a.urzadzenie and not SERIAL.match(a.urzadzenie):
        print(f"--urzadzenie {a.urzadzenie!r}: numer z `adb devices`.", file=sys.stderr)
        return 2
    ekran = scrcpy(u)
    if ekran is None:
        if sciezki.platforma() == "linux-arm64":
            print("scrcpy nie ma wydania na Linux arm64: ekranu w oknie tu nie będzie (telefon działa dalej przez "
                  "adb).", file=sys.stderr)
            return 1
        if not zgoda_na_licencje(u, a):                  # w paczce scrcpy jest adb z licencją SDK
            return 1
        try:
            przy_uzyciu.narzedzie(u, SCRCPY, log=print)
        except przy_uzyciu.BladPrzyUzyciu as e:
            print(f"BŁĄD: {e}", file=sys.stderr)
            return 1
        ekran = scrcpy(u)
        if ekran is None:
            print(f"BŁĄD: w katalogu scrcpy nie ma programu scrcpy ({przy_uzyciu.gotowe_narzedzie(u, SCRCPY)})",
                  file=sys.stderr)
            return 1
    env = env_adb(u)
    env["ADB"] = str(program)                            # ten sam adb co flota, nie kopia z paczki scrcpy
    lista, blad = lista_urzadzen(program, env)
    serial, powod = wybierz(lista, a.urzadzenie, st.get("serial"))
    if blad or serial is None:
        print(f"Nie pokażę ekranu: {blad or powod}. {JAK_PODLACZYC}", file=sys.stderr)
        return 1
    d = next((x for x in lista if x["serial"] == serial), {"model": None})
    argv = [str(ekran), "-s", serial, "--window-title", f"Jarvo: {d.get('model') or serial}"]
    if a.bez_dzwieku:
        argv.append("--no-audio")
    if a.rozmiar:
        argv += ["--max-size", str(a.rozmiar)]
    u.logi.mkdir(parents=True, exist_ok=True)
    log = u.logi / "scrcpy.log"
    with open(log, "ab") as f:
        f.write(f"\n=== {_teraz()} {' '.join(argv)}\n".encode("utf-8"))
        f.flush()
        kw: dict = {"stdin": subprocess.DEVNULL, "stdout": f, "stderr": subprocess.STDOUT, "env": env,
                    "close_fds": True, "cwd": str(Path(ekran).parent)}
        if WINDOWS:                                      # bez okna konsoli; samo okno SDL z ekranem telefonu
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        try:
            proc = uruchom_okno(argv, **kw)
        except OSError as e:
            print(f"BŁĄD: nie uruchomię scrcpy ({e.strerror or e})", file=sys.stderr)
            return 1
    with contextlib.suppress(subprocess.TimeoutExpired):
        kod = proc.wait(3)
        print(f"BŁĄD: scrcpy zakończył się od razu (kod {kod}); ostatnie linie w {log}:\n"
              + "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]), file=sys.stderr)
        return 1
    print(f"Ekran telefonu {d.get('model') or serial} w oknie scrcpy (zamknij okno, gdy skończysz; log: {log}).")
    return 0


def opis_stanu(u: Uklad) -> dict:
    st = stan_androida(u)
    program = adb(u)
    ekran = scrcpy(u)
    env = env_adb(u)
    app = przy_uzyciu.app_instalacji(u)
    wynik = {"platforma": sciezki.platforma(), "adb": str(program) if program else None,
             "adb_wersja": wersja_adb(program, env) if program else None,
             "licencja_sdk": (st.get("licencja_sdk") or {}).get("zaakceptowano") if isinstance(
                 st.get("licencja_sdk"), dict) else None,
             "wlaczony": bool(st.get("wlaczony")), "serial": st.get("serial"), "wifi": st.get("wifi"),
             "urzadzenia": None, "scrcpy": str(ekran) if ekran else None,
             "pobranie_mb": {n: przy_uzyciu.rozmiar_mb(app, n) for n in (PLATFORM_TOOLS, SCRCPY)},
             "podglad_hq": "wyłączony natywnie (I24)", "wlaczano": bool(st)}
    if program is not None and st.get("wlaczony"):
        wynik["urzadzenia"], wynik["blad_adb"] = lista_urzadzen(program, env)
    return wynik


def polecenie_status(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    s = opis_stanu(u)
    if getattr(a, "json", False):
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    stan = ("włączony" if s["wlaczony"] else "wyłączony (jarvo android on)" if s["wlaczano"]
            else "jeszcze nie włączony (jarvo android on)")
    print(f"Telefon testowy Twórcy aplikacji: {stan}")
    mb = s["pobranie_mb"]
    print("  adb: " + (f"platform-tools {s['adb_wersja'] or '?'} ({s['adb']})" if s["adb"] else
                       f"nie zainstalowany: pobierze go jarvo android on ({mb.get(PLATFORM_TOOLS) or '?'} MB "
                       "od Google, po akceptacji licencji)"))
    if s["licencja_sdk"]:
        print(f"  licencja Android SDK: zaakceptowana {s['licencja_sdk']}")
    if s["urzadzenia"] is not None:
        if s["urzadzenia"]:
            for d in s["urzadzenia"]:
                print(f"  {_opis_urzadzenia(d)}" + (" ← flota" if d["serial"] == s["serial"] else ""))
        else:
            print(f"  urządzenia: brak{' (' + s['blad_adb'] + ')' if s.get('blad_adb') else ''}. {JAK_PODLACZYC}")
    print("  ekran: " + (f"scrcpy w osobnym oknie ({s['scrcpy']}): jarvo android ekran" if s["scrcpy"] else
                         f"scrcpy pobierze się przy pierwszym jarvo android ekran ({mb.get(SCRCPY) or '?'} MB)"))
    print(f"  {PODGLAD_HQ}")
    return 0


# ---------------------------------------------------------------- jarvo doctor

def sprawdzenia(u: Uklad, ot=None) -> list[dict]:
    """Wyniki dla `jarvo doctor` (niczego nie zapisują i nie uruchamiają serwera adb). Telefon nie jest wymagany."""
    if not przy_uzyciu.natywnie(u):
        return []
    st = stan_androida(u)
    program = adb(u)
    wyniki = []
    if program is None:
        if st.get("wlaczony"):
            wyniki.append(_wynik("telefon (adb)", "uwaga", "telefon testowy włączony, ale brak adb w instalacji",
                                 "Uruchom jarvo android on (pobierze platform-tools jeszcze raz)."))
        elif sciezki.platforma() == "linux-arm64":
            wyniki.append(_wynik("telefon (adb)", "ok", "platform-tools nie ma wydania na Linux arm64; adb z systemu "
                                 "(np. sudo apt install adb), gdy potrzebny telefon"))
        else:
            wyniki.append(_wynik("telefon (adb)", "ok", "nie włączony (opcjonalny): jarvo android on pobierze "
                                 "platform-tools od Google po akceptacji licencji"))
    else:
        wersja = wersja_adb(program, env_adb(u))
        if wersja is None:
            wyniki.append(_wynik("telefon (adb)", "uwaga", f"{program} się nie uruchamia",
                                 "Uruchom jarvo android on (sprawdzi i w razie potrzeby pobierze platform-tools)."))
        else:
            wyniki.append(_wynik("telefon (adb)", "ok", f"platform-tools {wersja}; telefon testowy "
                                 + ("włączony" + (f", urządzenie {st['serial']}" if st.get("serial") else
                                                  ", urządzenie jeszcze nie wybrane") if st.get("wlaczony") else
                                    "wyłączony (jarvo android on)")))
    ekran = scrcpy(u)
    wyniki.append(_wynik("ekran telefonu", "ok", ("scrcpy w osobnym oknie: jarvo android ekran" if ekran else
                                                 "scrcpy pobierze się przy pierwszym jarvo android ekran")
                         + "; podgląd w HQ (:9122) wyłączony natywnie (I24)"))
    return wyniki


# ---------------------------------------------------------------- parser

def dodaj_polecenia(sub) -> None:
    """Polecenie `android` w parserze jarvo (cli._parser); funkcje biorą (u, a, reszta, ot). Samo `jarvo android` =
    status."""
    s = sub.add_parser("android", help="telefon testowy Twórcy aplikacji: status, on, off, ekran",
                       description="Telefon testowy Twórcy aplikacji: Twój telefon z Androidem (USB albo Wi-Fi) "
                       "albo emulator, przez adb z Android platform-tools; ekran w oknie scrcpy.")
    s.set_defaults(funkcja=polecenie_status, json=False)
    t = s.add_subparsers(dest="android_polecenie", metavar="polecenie", title="polecenia")
    k = t.add_parser("status", help="adb, licencja, urządzenia, ekran")
    k.add_argument("--json", action="store_true")
    k.set_defaults(funkcja=polecenie_status)
    k = t.add_parser("on", help="włącz: platform-tools (pierwszy raz po akceptacji licencji Google), serwer adb, "
                                "urządzenie floty")
    k.add_argument("--akceptuje-licencje", action="store_true",
                   help="akceptuję licencję Android SDK (bez pytania; do skryptów i CI)")
    k.add_argument("--wifi", metavar="ADRES:PORT", help="połączenie przez Wi-Fi (adres z ekranu debugowania "
                   "bezprzewodowego)")
    k.add_argument("--paruj", metavar="ADRES:PORT", help="parowanie kodem (Android 11+, okno „Paruj urządzenie za "
                   "pomocą kodu”)")
    k.add_argument("--kod", metavar="KOD", help="6 cyfr kodu parowania (bez niego: pytanie w terminalu)")
    k.add_argument("--urzadzenie", metavar="SERIAL", help="urządzenie floty, gdy jest ich kilka (numer z jarvo "
                   "android status)")
    k.set_defaults(funkcja=polecenie_on)
    k = t.add_parser("off", help="wyłącz: flota nie używa telefonu, serwer adb zatrzymany")
    k.add_argument("--zostaw-adb", action="store_true", help="bez zatrzymania serwera adb (np. dla Android Studio)")
    k.set_defaults(funkcja=polecenie_off)
    k = t.add_parser("ekran", help="ekran telefonu w osobnym oknie (scrcpy)")
    k.add_argument("--urzadzenie", metavar="SERIAL", help="inne urządzenie niż urządzenie floty")
    k.add_argument("--bez-dzwieku", action="store_true", help="bez przekazywania dźwięku z telefonu")
    k.add_argument("--rozmiar", type=int, metavar="PIKSELE", help="najdłuższy bok okna (np. 1024)")
    k.add_argument("--akceptuje-licencje", action="store_true", help=argparse.SUPPRESS)
    k.set_defaults(funkcja=polecenie_ekran)


def main(argv: list[str] | None = None) -> int:
    """`python -I -X utf8 jarvo/android.py <status|on|off|ekran> …` bez reszty CLI (do czasu wpięcia w jarvo/cli.py)."""
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    p = argparse.ArgumentParser(prog="jarvo", description="Telefon testowy (docs/NATYWNIE.md, etap E11).")
    sub = p.add_subparsers(dest="polecenie", metavar="polecenie", title="polecenia")
    sub.required = True
    dodaj_polecenia(sub)
    a = p.parse_args(["android", *(sys.argv[1:] if argv is None else argv)])
    try:
        u = sciezki.uklad()
    except sciezki.BladUkladu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    try:
        return int(a.funkcja(u, a, [], None) or 0)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())

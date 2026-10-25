#!/usr/bin/env python3
"""Telefon testowy z Androidem przez adb (warstwa 2 bramki aplikacji): instalacja, zrzuty, logi i testy wrogie na
prawdziwym systemie Android (telefon właściciela przez USB albo Wi-Fi, emulator z Android Studio, a w kontenerze
emulator Google albo Redroid w usłudze floty).

    urzadzenie.py status [--json]                        # czy jest urządzenie, wersja Androida, ekran
    urzadzenie.py zainstaluj <plik.apk>
    urzadzenie.py otworz <pakiet | exp://…>               # aplikacja albo podgląd w Expo Go
    urzadzenie.py zrzut <plik.png>
    urzadzenie.py logi [--pakiet p] [--linie 200]
    urzadzenie.py wrogie <pakiet | exp://…> <outdir> [--tylko duza-czcionka,ciemny,…]
    urzadzenie.py przywroc                                # ustawienia zostawione przez przerwany test

Urządzenie i adb:
- instalacja natywna (jest `<JARVO_ROOT>/program/current.json`): telefon włącza właściciel poleceniem
  `jarvo android on` (jarvo/android.py: platform-tools przy pierwszym użyciu po akceptacji licencji Google). adb
  z `<stan>/narzedzia.json` (wpis platform-tools; na Linuksie arm64 adb z systemu), stan i urządzenie z
  `<stan>/android.json`; bez wybranego urządzenia bierzemy jedyne gotowe z `adb devices`. `jarvo android off` =
  flota nie używa telefonu (kod 3). Serwer adb startuje z wyjściem do pliku (proces w tle dziedziczy uchwyty, potok by
  nie dostał końca), z ADB_MDNS=0, z logiem serwera w logach Jarva (ANDROID_ADB_LOG_PATH z android.json), a na macOS
  i Linuksie z katalogiem domowym adb w `<stan>/adb-dom` (klucz adb Jarva nie trafia do katalogu domowego właściciela)
  i kluczem adb właściciela w ADB_VENDOR_KEYS (telefon, który go zna, nie pyta o zgodę jeszcze raz),
- kontener: `JARVO_ANDROID_ADB` (domyślnie `jarvo-android:5555`, usługa floty `android` w sieci wewnętrznej; włącza
  ją właściciel: `jarvo android on`), adb z obrazu. Port adb nigdy nie wychodzi poza sieć floty.
`JARVO_ADB` i `JARVO_ANDROID_ADB` z otoczenia wygrywają w obu przypadkach.

Testy wrogie (każdy: ustawienie → uruchomienie → zrzut → awarie z bufora `crash` i błędy ReactNativeJS → przywrócenie
ustawień): start, duza-czcionka (font_scale 2.0), maly-ekran (720×1280, 320 dpi), ciemny, offline (tryb samolotowy,
Wi-Fi i dane wyłączone; `not_run`, gdy urządzenie nie umie odciąć sieci albo adb idzie do telefonu przez Wi-Fi),
uprawnienia (odebrane wszystkie przyznane, potem oddane), wstecz (dwa razy), smierc-procesu (aplikacja w tle zabita
i przywrócona), swieza-instalacja (dane wyczyszczone; nie dla Expo Go). Wynik: <outdir>/wrogie.json + zrzuty.

Urządzeniem floty bywa prywatny telefon właściciela, więc test zostawia go takim, jakim był:
- przed każdą zmianą ustawienia skrypt odczytuje obecną wartość i zapisuje ją w dzienniku przywróceń na dysku
  (instalacja natywna: `<stan>/android-przywroc.json`, kontener: `<dane Jarva>/state/android-przywroc.json`), po teście
  przywraca ją i sprawdza odczytem, także po błędzie adb, przekroczeniu czasu i Ctrl+C. Czego nie przywrócił (telefon
  odłączony w trakcie), przywraca następne polecenie tego skryptu, `urzadzenie.py przywroc` albo `jarvo android off`;
  `wrogie` nie rusza, dopóki takie zaległości są. Dziennik zna tylko ustawienia z listy (USTAWIENIA), a polecenia
  przywrócenia składa kod, nie plik,
- wartości, której nie da się odczytać, na telefonie nie zmienia (test `not_run`); na urządzeniu jednorazowym (urządzenie
  floty w kontenerze, emulator) wraca wtedy do domyślnej, jak dotąd,
- nieodwracalne kroki (`pm clear` w swieza-instalacja) tylko na urządzeniu jednorazowym albo na telefonie, który
  właściciel oznaczył jako testowy (`jarvo android on --telefon-testowy`),
- bez śladów: zrzut hierarchii widoku w /data/local/tmp (usuwany od razu), bufor logów bez `logcat -c` (czytany od
  chwili startu testu i tylko dla testowanej aplikacji; na urządzeniu jednorazowym `logcat -c` jak dotąd).
Kody: 0 dobrze, 1 któryś test ma status `blad`, 3 nie ma urządzenia, 4 na telefonie zostały ustawienia zmienione przez
test (lista na stderr i w wrogie.json, `telefon_zmieniony`: powiedz o tym właścicielowi).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SERIAL_KONTENERA = "jarvo-android:5555"                # usługa floty `android` w sieci kontenera
WINDOWS = os.name == "nt"
EXPO_GO = "host.exp.exponent"
CZEKAJ_S = float(os.environ.get("JARVO_ANDROID_CZEKAJ", "6"))
SCENARIUSZE = ["start", "duza-czcionka", "maly-ekran", "ciemny", "offline", "uprawnienia", "wstecz", "smierc-procesu",
               "swieza-instalacja"]
AWARIA_RE = re.compile(r"FATAL EXCEPTION|ANR in|has stopped|przestała działać|Process: \S+, PID|ReactNativeJS.*(Error|Exception)", re.I)
PLIK_PRZYWROCEN = "android-przywroc.json"
ZRZUT_UI = "/data/local/tmp/jarvo-ui.xml"             # nie /sdcard: tam plik zostałby w pamięci telefonu właściciela
CZAS_PRZYWROCENIA = 20                                 # s na jedno polecenie przywrócenia
# adb przez sieć: adres:port (adb connect, debugowanie bezprzewodowe) albo nazwa mDNS (adb-…._adb-tls-connect._tcp)
PRZEZ_SIEC = re.compile(r"^(?:\[[0-9A-Fa-f:.%]+\]|[A-Za-z0-9][A-Za-z0-9.\-]*):\d{1,5}$|\._adb-tls-")
ZNIKNAL = re.compile(r"not found|offline|no devices|unauthorized|brak odpowiedzi|nie uruchomię", re.I)


class BrakUrzadzenia(Exception):
    pass


class TelefonZmieniony(Exception):
    """Na urządzeniu zostały ustawienia zmienione przez test, których nie udało się przywrócić (kod 4)."""


# ------------------------------------------------------------------ instalacja natywna (jarvo android, docs/NATYWNIE.md U04)

WLACZ = ("właściciel włącza go poleceniem `jarvo android on` (telefon z debugowaniem USB albo bezprzewodowym, "
         "emulator z Android Studio; bramka-aplikacji: references/wrogie.md, „Urządzenie z Androidem”)")


def korzen_natywny() -> Path | None:
    """Korzeń instalacji natywnej Jarva (JARVO_ROOT z `program/current.json`); w kontenerze None."""
    k = os.environ.get("JARVO_ROOT")
    return Path(k) if k and (Path(k) / "program" / "current.json").is_file() else None


def _json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def stan_natywny(korzen: Path) -> dict:
    """`<stan>/android.json` z `jarvo android on|off`: wlaczony, serial, wifi, telefon_testowy, log_adb."""
    return _json(korzen / "stan" / "android.json")


def _platform_tools(korzen: Path) -> dict:
    w = _json(korzen / "stan" / "narzedzia.json").get("platform-tools")
    return w if isinstance(w, dict) else {}


def adb_natywny(korzen: Path) -> str | None:
    """adb z platform-tools instalacji (`jarvo android on` pobiera je przy pierwszym użyciu); Linux arm64: z systemu."""
    w = _platform_tools(korzen)
    for k in (w.get("bin") or []) or [w.get("katalog")]:
        p = Path(str(k)) / ("adb.exe" if WINDOWS else "adb")
        if k and p.is_file():
            return str(p)
    if sys.platform.startswith("linux") and platform.machine().lower() in ("aarch64", "arm64"):
        return shutil.which("adb")
    return None


def klucz_wlasciciela() -> Path | None:
    """~/.android/adbkey z katalogu domowego konta (POSIX; nie z HOME, które terminal agenta ma z profilu). Windows:
    None, bo adb i tak bierze profil z konta, a nie z USERPROFILE."""
    if WINDOWS:
        return None
    import pwd
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".android" / "adbkey"
    except (KeyError, OSError):
        return None


def dom_adb(korzen: Path) -> Path | None:
    """HOME adb na macOS i Linuksie: `<stan>/adb-dom` (to samo co jarvo/android.py), więc klucz adb Jarva i plik
    sparowanych telefonów leżą w katalogu Jarva; Windows: None (adb bierze profil konta, nie HOME)."""
    return None if WINDOWS else korzen / "stan" / "adb-dom"


def env_adb(korzen: Path) -> dict:
    """Otoczenie adb instalacji natywnej: zmienne z wpisu platform-tools (ADB_MDNS=0), katalog domowy adb Jarva i log
    serwera jak w `jarvo android on`, klucz adb właściciela w ADB_VENDOR_KEYS."""
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (_platform_tools(korzen).get("env") or {}).items()})
    env.setdefault("ADB_MDNS", "0")
    dom = dom_adb(korzen)
    if dom is not None:
        env["HOME"] = str(dom)
    log = str(stan_natywny(korzen).get("log_adb") or "")
    if log and os.path.isabs(log) and Path(log).parent.is_dir():   # serwer adb bez katalogu logu nie wstaje
        env["ANDROID_ADB_LOG_PATH"] = log
    klucz = klucz_wlasciciela()
    if klucz is not None and klucz.is_file():
        obecne = [x for x in env.get("ADB_VENDOR_KEYS", "").split(os.pathsep) if x]
        env["ADB_VENDOR_KEYS"] = os.pathsep.join(dict.fromkeys([*obecne, str(klucz)]))
    return env


def plik_przywrocen(korzen: Path | None) -> Path | None:
    """Dziennik przywróceń: `<stan>/android-przywroc.json` instalacji natywnej, w kontenerze w `<dane Jarva>/state`;
    None, gdy nie ma gdzie go zapisać (wtedy tylko w pamięci procesu)."""
    if korzen is not None:
        return korzen / "stan" / PLIK_PRZYWROCEN
    stan = Path(os.environ.get("JARVO_DATA_DIR") or "/opt/data/jarvo") / "state"
    return stan / PLIK_PRZYWROCEN if stan.is_dir() and os.access(stan, os.W_OK) else None


class Adb:
    """Cienka warstwa nad adb (podmieniana w testach). Bez argumentów: urządzenie i adb z otoczenia, instalacji
    natywnej (jarvo android) albo kontenera (jarvo-android:5555, adb z obrazu). `korzen` i `env` podaje jawnie
    jarvo/android.py (przywracanie przy `jarvo android off`)."""

    def __init__(self, serial: str | None = None, adb: str | None = None, *, korzen: Path | None = None,
                 env: dict | None = None):
        self.korzen = korzen if korzen is not None else (korzen_natywny() if serial is None or adb is None else None)
        natywny = (stan_natywny(self.korzen).get("serial") or None) if self.korzen else None
        self.serial = serial or os.environ.get("JARVO_ANDROID_ADB") or natywny or (
            None if self.korzen else SERIAL_KONTENERA)
        self.adb = adb or os.environ.get("JARVO_ADB") or (adb_natywny(self.korzen) if self.korzen else None) or "adb"
        self.env = env if env is not None else (env_adb(self.korzen) if self.korzen else None)
        self.plik_przywrocen = plik_przywrocen(self.korzen)
        self.polaczony = False
        self.przywrocone_zalegle: list[str] = []
        self.zalegle: list[str] = []                    # zaległe przywrócenia, których nie udało się wykonać

    def run(self, *args: str, timeout: int = 60, binarnie: bool = False):
        try:
            r = subprocess.run([self.adb, "-s", self.serial, *args], capture_output=True, timeout=timeout, env=self.env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"adb {' '.join(args)[:120]}: brak odpowiedzi po {timeout} s (telefon odłączony?)") from None
        except OSError as e:
            raise RuntimeError(f"adb: nie uruchomię {self.adb} ({e.strerror or e})") from None
        if r.returncode != 0 and not binarnie:
            raise RuntimeError(f"adb {' '.join(args)}: {r.stderr.decode(errors='replace').strip()[:300]}")
        return r.stdout if binarnie else r.stdout.decode(errors="replace")

    def sh(self, polecenie: str, timeout: int = 60) -> str:
        return self.run("shell", polecenie, timeout=timeout)

    def _adb(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
        """Polecenie adb przy łączeniu (connect, devices, get-state): brak odpowiedzi albo brak programu to
        BrakUrzadzenia z radą, nie ślad stosu. Serwer adb już działa (`_serwer`), więc potok dostaje koniec."""
        try:
            return subprocess.run([self.adb, *args], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout, env=self.env)
        except subprocess.TimeoutExpired:
            raise BrakUrzadzenia(f"adb {' '.join(args)}: brak odpowiedzi po {timeout} s; " + (
                WLACZ if self.korzen is not None else "urządzenie floty nie odpowiada (jarvo android status)")) from None
        except OSError as e:
            raise BrakUrzadzenia(f"nie uruchomię {self.adb} ({e.strerror or e})") from None

    def _serwer(self) -> None:
        """Serwer adb (instalacja natywna): start z wyjściem do pliku, bo proces w tle dziedziczy uchwyty polecenia,
        a potok nie dostałby końca (Windows); potem odnowienie połączenia Wi-Fi z `jarvo android on --wifi`."""
        dom = dom_adb(self.korzen)
        if dom is not None and self.env is not None and self.env.get("HOME") == str(dom):
            dom.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile() as f:
            try:
                r = subprocess.run([self.adb, "start-server"], stdin=subprocess.DEVNULL, stdout=f,
                                   stderr=subprocess.STDOUT, env=self.env, timeout=60)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise BrakUrzadzenia(f"serwer adb nie wstał ({e}); {WLACZ}") from None
            f.seek(0)
            wyjscie = f.read().decode("utf-8", errors="replace").strip()
        if r.returncode:
            raise BrakUrzadzenia(f"serwer adb nie wstał (kod {r.returncode}: {wyjscie[-200:]}); {WLACZ}")
        wifi = stan_natywny(self.korzen).get("wifi")
        if wifi and self.serial in (None, wifi):
            self._adb("connect", wifi)

    def _jedyne(self) -> str:
        """Jedyne gotowe urządzenie z `adb devices` (instalacja natywna bez wybranego urządzenia)."""
        r = self._adb("devices")
        wiersze = [w.split() for w in r.stdout.splitlines()[1:] if w.strip() and not w.startswith("*")]
        gotowe = [w[0] for w in wiersze if len(w) >= 2 and w[1] == "device"]
        if len(gotowe) == 1:
            return gotowe[0]
        if gotowe:
            raise BrakUrzadzenia(f"kilka urządzeń ({', '.join(gotowe)}): właściciel wybiera urządzenie floty "
                                 "poleceniem `jarvo android on --urzadzenie SERIAL`")
        inne = ", ".join(" ".join(w[:2]) for w in wiersze)
        raise BrakUrzadzenia("nie widzę telefonu" + (f" ({inne}: odblokuj telefon i zaakceptuj na nim debugowanie)"
                                                     if inne else "") + f"; {WLACZ}")

    def polacz(self) -> None:
        """Urządzenie gotowe do pracy (raz na proces), potem zaległe przywrócenia ustawień z przerwanego testu."""
        if self.polaczony:
            return
        if self.korzen is not None and not os.environ.get("JARVO_ANDROID_ADB"):
            st = stan_natywny(self.korzen)
            if not st.get("wlaczony"):
                raise BrakUrzadzenia("telefon testowy " + ("wyłączony (jarvo android off)" if st else
                                                           "nie jest włączony") + f"; {WLACZ}")
        if not shutil.which(self.adb) and not Path(self.adb).exists():
            if self.korzen is not None:
                raise BrakUrzadzenia(f"brak adb w instalacji Jarva (platform-tools pobiera `jarvo android on` po "
                                     f"akceptacji licencji Google); {WLACZ}")
            raise BrakUrzadzenia("brak adb w obrazie floty (pakiet adb; obraz sprzed wersji z usługą android: `jarvo update`)")
        if self.korzen is not None:
            self._serwer()
            if not self.serial:
                self.serial = self._jedyne()
        if ":" in self.serial:
            self._adb("connect", self.serial)
        stan = self._adb("-s", self.serial, "get-state")
        if stan.stdout.strip() != "device":
            if self.korzen is not None:
                raise BrakUrzadzenia(f"urządzenie {self.serial} niedostępne ({(stan.stderr or stan.stdout).strip()[:200]}); "
                                     f"{WLACZ}")
            raise BrakUrzadzenia(f"urządzenie {self.serial} niedostępne ({(stan.stderr or stan.stdout).strip()[:200]}); "
                                 "właściciel włącza je poleceniem `jarvo android on` (emulator przy KVM albo Redroid przy binderze, docs/MOBILE.md §5)")
        self.polaczony = True
        self.przywrocone_zalegle, self.zalegle = przywroc_zalegle(self)
        if self.przywrocone_zalegle:
            print("Przywróciłem ustawienia telefonu zostawione przez przerwany test: "
                  + ", ".join(self.przywrocone_zalegle) + ".", file=sys.stderr)
        if self.zalegle:
            print("UWAGA: na telefonie zostały ustawienia zmienione przez przerwany test, których nie umiem teraz "
                  f"przywrócić: {', '.join(self.zalegle)}. Spróbuję przy następnym poleceniu (urzadzenie.py przywroc).",
                  file=sys.stderr)


# ------------------------------------------------------------------ ustawienia telefonu: odczyt, zmiana, przywrócenie

NOCNE = ("yes", "no", "auto", "custom", "custom_schedule", "custom_bedtime")
_LICZBA = re.compile(r"^\d{1,2}(?:\.\d{1,6})?$")
_ROZMIAR = re.compile(r"^\d{2,5}x\d{2,5}$")
_GESTOSC = re.compile(r"^\d{2,4}$")
_PAKIET = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")
_UPRAWNIENIE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*\.permission\.[A-Za-z0-9_]+$")
OPISY = {"font_scale": "rozmiar czcionki", "wm_size": "rozmiar ekranu", "wm_density": "gęstość ekranu",
         "noc": "tryb ciemny", "samolot": "tryb samolotowy", "wifi": "Wi-Fi", "dane": "dane komórkowe",
         "demo_zgoda": "zgoda na tryb demo paska stanu", "demo": "tryb demo paska stanu",
         "uprawnienie": "uprawnienie aplikacji"}
# wartość domyślna, gdy na urządzeniu jednorazowym nie da się odczytać obecnej (zachowanie sprzed dziennika przywróceń)
DOMYSLNE = {"font_scale": "1.0", "wm_size": "-", "wm_density": "-", "noc": "no", "samolot": "0", "wifi": "1",
            "dane": "1", "demo_zgoda": "null"}


def _ostatnia(tekst: str) -> str:
    linie = [x.strip() for x in (tekst or "").splitlines() if x.strip()]
    return linie[-1] if linie else ""


def _wm(adb: Adb, co: str) -> str | None:
    """Nadpisany rozmiar albo gęstość ekranu z `wm size|density` („-” = bez nadpisania), None = nie do odczytania."""
    out = adb.sh(f"wm {co}")
    if not re.search(rf"Physical {co}:\s*\S+", out):
        return None
    nad = re.search(rf"Override {co}:\s*(\S+)", out)
    if not nad:
        return "-"
    return nad.group(1) if (_ROZMIAR if co == "size" else _GESTOSC).match(nad.group(1)) else None


def _noc(adb: Adb) -> str | None:
    m = re.search(r"Night mode:\s*(\S+)", adb.sh("cmd uimode night"))
    return m.group(1) if m and m.group(1) in NOCNE else None


def _ustawienie(adb: Adb, polecenie: str, dozwolone: tuple[str, ...] | None = None) -> str | None:
    v = _ostatnia(adb.sh(polecenie))
    if dozwolone is None:
        return v if v == "null" or _LICZBA.match(v) else None
    return v if v in dozwolone else None


CZYTAJ = {
    "font_scale": lambda a: _ustawienie(a, "settings get system font_scale"),
    "wm_size": lambda a: _wm(a, "size"),
    "wm_density": lambda a: _wm(a, "density"),
    "noc": _noc,
    "samolot": lambda a: _ustawienie(a, "settings get global airplane_mode_on", ("0", "1")),
    # wifi_on: 1 włączone, 2 włączone mimo trybu samolotowego, 0 wyłączone, 3 wyłączone przez tryb samolotowy
    "wifi": lambda a: {"0": "0", "3": "0", "1": "1", "2": "1"}.get(_ostatnia(a.sh("settings get global wifi_on"))),
    "dane": lambda a: _ustawienie(a, "settings get global mobile_data", ("0", "1")),
    "demo_zgoda": lambda a: _ustawienie(a, "settings get global sysui_demo_allowed", ("0", "1", "null")),
}
USTAWIENIA = (*CZYTAJ, "demo", "uprawnienie")


def polecenia_przywrocenia(ustawienie: str, wartosc: str) -> list[str]:
    """Polecenia `adb shell`, które przywracają ustawienie do wartości sprzed testu. Tylko znane ustawienia i wartości
    o znanym kształcie: dziennik na dysku daje nazwę i wartość, a polecenie składa ten kod (ValueError dla innych)."""
    v = str(wartosc)
    if ustawienie == "font_scale" and (v == "null" or _LICZBA.match(v)):
        return ["settings delete system font_scale" if v == "null" else f"settings put system font_scale {v}"]
    if ustawienie == "wm_size" and (v == "-" or _ROZMIAR.match(v)):
        return ["wm size reset" if v == "-" else f"wm size {v}"]
    if ustawienie == "wm_density" and (v == "-" or _GESTOSC.match(v)):
        return ["wm density reset" if v == "-" else f"wm density {v}"]
    if ustawienie == "noc" and v in NOCNE:
        return [f"cmd uimode night {v}"]
    if ustawienie == "samolot" and v in ("0", "1"):
        return [f"cmd connectivity airplane-mode {'enable' if v == '1' else 'disable'}"]
    if ustawienie == "wifi" and v in ("0", "1"):
        return [f"svc wifi {'enable' if v == '1' else 'disable'}"]
    if ustawienie == "dane" and v in ("0", "1"):
        return [f"svc data {'enable' if v == '1' else 'disable'}"]
    if ustawienie == "demo_zgoda" and v in ("0", "1", "null"):
        return ["settings delete global sysui_demo_allowed" if v == "null" else
                f"settings put global sysui_demo_allowed {v}"]
    if ustawienie == "demo":
        return ["am broadcast -a com.android.systemui.demo -e command exit"]
    if ustawienie == "uprawnienie":
        pakiet, _, upr = v.partition(" ")
        if _PAKIET.match(pakiet) and _UPRAWNIENIE.match(upr):
            return [f"pm grant {pakiet} {upr}"]
    raise ValueError(f"nieznane ustawienie albo wartość w dzienniku przywróceń: {ustawienie}={v!r}")


def _rowne(ustawienie: str, teraz: str | None, ma_byc: str) -> bool:
    if teraz is None:
        return False
    if ustawienie == "font_scale" and teraz != "null" and ma_byc != "null":
        return abs(float(teraz) - float(ma_byc)) < 1e-6
    return teraz == ma_byc


def przywrocone(adb: Adb, ustawienie: str, wartosc: str) -> bool:
    """Czy ustawienie ma już wartość sprzed testu (odczyt z urządzenia). Tryb demo: nie da się go odczytać."""
    if ustawienie == "uprawnienie":
        pakiet, _, upr = wartosc.partition(" ")
        return upr in _przyznane(adb, pakiet)
    czytaj = CZYTAJ.get(ustawienie)
    return True if czytaj is None else _rowne(ustawienie, czytaj(adb), wartosc)


def odczytaj(adb: Adb, ustawienie: str, jednorazowe: bool) -> tuple[str | None, bool]:
    """(wartość, odczytana): obecna wartość ustawienia. Nieodczytana: na urządzeniu jednorazowym domyślna (jak przed
    dziennikiem przywróceń; po przywróceniu nie da się jej sprawdzić), na telefonie None (test tej wartości nie
    zmienia, bo nie umiałby jej przywrócić)."""
    try:
        v = CZYTAJ[ustawienie](adb)
    except RuntimeError:
        v = None
    if v is not None:
        return v, True
    return (DOMYSLNE.get(ustawienie) if jednorazowe else None), False


def _wczytaj_przywrocenia(plik: Path | None) -> dict:
    if plik is None:
        return {}
    d = _json(plik)
    return {k: [w for w in v if isinstance(w, dict)] for k, v in d.items() if isinstance(v, list)}


def _zapisz_przywrocenia(plik: Path | None, dane: dict) -> None:
    """Zapis atomowy (plik tymczasowy obok i zamiana); pusty dziennik = brak pliku."""
    if plik is None:
        return
    dane = {k: v for k, v in dane.items() if v}
    if not dane:
        try:
            plik.unlink()
        except FileNotFoundError:
            pass
        return
    plik.parent.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_name(f".{plik.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, plik)


def zalegle_przywrocenia(adb: Adb) -> list[dict]:
    """Wpisy dziennika przywróceń dla tego urządzenia (także nieznane: przywracanie je pomija i usuwa)."""
    return _wczytaj_przywrocenia(adb.plik_przywrocen).get(adb.serial or "", [])


def opis(wpis: dict) -> str:
    u = str(wpis.get("ustawienie"))
    v = str(wpis.get("wartosc"))
    if u == "uprawnienie":
        return f"{OPISY[u]} {v.partition(' ')[2]}"
    if u == "demo":
        return OPISY[u]
    return f"{OPISY.get(u, u)} (było: {'domyślne' if v in ('-', 'null') else v})"


def przywroc_wpisy(adb: Adb, wpisy: list[dict]) -> list[dict]:
    """Przywraca wpisy od końca, każdy osobno, i sprawdza odczytem; zwraca wpisy nieprzywrócone. Dziennik na dysku
    traci wpisy przywrócone, a nieprzywrócone w nim zostają. Gdy urządzenie zniknęło (odłączone, brak odpowiedzi),
    reszty nie próbuje: zostaje na następny raz."""
    nieudane: list[dict] = []
    zniknal = False
    kolejnosc = list(reversed(wpisy))
    # tryb samolotowy przed Wi-Fi: włączenie Wi-Fi w trybie samolotowym zapamiętuje w Androidzie „Wi-Fi zostaje
    # w trybie samolotowym” (wifi_apm_state), czego właściciel nie wybrał; po zdjęciu trybu Wi-Fi wraca samo
    samoloty = [w for w in kolejnosc if w.get("ustawienie") == "samolot"]
    if samoloty:
        kolejnosc = samoloty + [w for w in kolejnosc if w.get("ustawienie") != "samolot"]
    for w in kolejnosc:
        if zniknal:
            nieudane.append(w)
            continue
        try:
            polecenia = polecenia_przywrocenia(str(w.get("ustawienie")), str(w.get("wartosc")))
        except ValueError:
            continue                                     # nie nasz wpis: nie wykonujemy go i nie trzymamy
        try:
            for p in polecenia:
                adb.sh(p, timeout=CZAS_PRZYWROCENIA)
            ok = (przywrocone(adb, str(w["ustawienie"]), str(w["wartosc"])) if w.get("sprawdz", True) else True)
        except RuntimeError as e:
            ok = False
            zniknal = bool(ZNIKNAL.search(str(e)))
        if not ok:
            nieudane.append(w)
    nieudane.reverse()
    zostaja = {id(w) for w in nieudane}
    gotowe = {w.get("id") for w in wpisy if id(w) not in zostaja}
    dane = _wczytaj_przywrocenia(adb.plik_przywrocen)
    if adb.serial in dane:
        dane[adb.serial] = [w for w in dane[adb.serial] if w.get("id") not in gotowe]
        _zapisz_przywrocenia(adb.plik_przywrocen, dane)
    return nieudane


def _znany(wpis: dict) -> bool:
    try:
        polecenia_przywrocenia(str(wpis.get("ustawienie")), str(wpis.get("wartosc")))
    except ValueError:
        return False
    return True


def przywroc_zalegle(adb: Adb) -> tuple[list[str], list[str]]:
    """(przywrócone, nieprzywrócone) z dziennika na dysku dla tego urządzenia: zmiany z testu, który się nie
    skończył (telefon odłączony w trakcie, proces zabity). Wpis spoza listy ustawień znika bez wykonania."""
    wpisy = zalegle_przywrocenia(adb)
    if not wpisy:
        return [], []
    nieudane = przywroc_wpisy(adb, wpisy)
    zostaly = {id(w) for w in nieudane}
    return [opis(w) for w in wpisy if id(w) not in zostaly and _znany(w)], [opis(w) for w in nieudane]


class Zmiany:
    """Ustawienia urządzenia zmienione na czas jednego testu. `zmien` zapisuje wartość sprzed zmiany (w pamięci
    i w dzienniku przywróceń na dysku) PRZED wykonaniem zmiany; `przywroc` cofa od końca, każde ustawienie osobno,
    i sprawdza odczytem. Czego nie przywrócił, zostaje w dzienniku dla następnego polecenia."""

    def __init__(self, adb: Adb, test: str = ""):
        self.adb, self.test = adb, test
        self.wpisy: list[dict] = []

    def zmien(self, ustawienie: str, wartosc: str, polecenia: list[str], *, sprawdz: bool = True) -> None:
        """`sprawdz=False`: wartość domyślna zamiast odczytanej (urządzenie jednorazowe), po przywróceniu bez
        sprawdzenia odczytem."""
        polecenia_przywrocenia(ustawienie, wartosc)      # tylko to, co umiemy przywrócić
        wpis = {"id": uuid.uuid4().hex, "ustawienie": ustawienie, "wartosc": str(wartosc), "sprawdz": bool(sprawdz),
                "test": self.test, "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S")}
        dane = _wczytaj_przywrocenia(self.adb.plik_przywrocen)
        dane.setdefault(self.adb.serial or "", []).append(wpis)
        _zapisz_przywrocenia(self.adb.plik_przywrocen, dane)
        self.wpisy.append(wpis)
        try:
            for p in polecenia:
                self.adb.sh(p)
        except RuntimeError:
            czytelne = ustawienie in CZYTAJ or ustawienie == "uprawnienie"   # tryb demo: nie wiadomo, czy wszedł
            try:
                bez_zmiany = sprawdz and czytelne and przywrocone(self.adb, ustawienie, str(wartosc))
            except RuntimeError:
                bez_zmiany = False
            if bez_zmiany:                               # polecenie nic nie zmieniło: wpis niepotrzebny
                self.wpisy.remove(wpis)
                dane = _wczytaj_przywrocenia(self.adb.plik_przywrocen)
                dane[self.adb.serial or ""] = [w for w in dane.get(self.adb.serial or "", []) if w.get("id") != wpis["id"]]
                _zapisz_przywrocenia(self.adb.plik_przywrocen, dane)
            raise

    def przywroc(self) -> list[str]:
        """Opisy ustawień, których nie przywrócił (pusta lista = urządzenie jak przed testem)."""
        if not self.wpisy:
            return []
        nieudane = przywroc_wpisy(self.adb, self.wpisy)
        self.wpisy = []
        return [opis(w) for w in nieudane]


def urzadzenie_testowe(adb: Adb) -> dict:
    """{"jednorazowe", "przez_siec", "dlaczego"}: jednorazowe = urządzenie floty w kontenerze, emulator albo telefon
    oznaczony przez właściciela jako testowy (wolno nieodwracalne kroki); przez_siec = adb do telefonu przez Wi-Fi
    (tryb samolotowy odciąłby adb)."""
    serial = adb.serial or ""
    if adb.korzen is None:
        return {"jednorazowe": True, "przez_siec": False, "dlaczego": "urządzenie floty w kontenerze"}
    emulator = serial.startswith("emulator-")
    if not emulator:
        for wlasciwosc in ("ro.kernel.qemu", "ro.boot.qemu"):
            try:
                emulator = _ostatnia(adb.sh(f"getprop {wlasciwosc}", timeout=20)) == "1"
            except RuntimeError:
                emulator = False
            if emulator:
                break
    testowy = serial in (stan_natywny(adb.korzen).get("telefon_testowy") or [])
    przez_siec = bool(PRZEZ_SIEC.search(serial)) and not emulator
    if emulator:
        return {"jednorazowe": True, "przez_siec": przez_siec, "dlaczego": "emulator"}
    if testowy:
        return {"jednorazowe": True, "przez_siec": przez_siec, "dlaczego": "telefon testowy (oznaczył go właściciel)"}
    return {"jednorazowe": False, "przez_siec": przez_siec, "dlaczego": "telefon właściciela"}


# ------------------------------------------------------------------ polecenia

def status(adb: Adb) -> dict:
    adb.polacz()
    rozm = adb.sh("wm size").strip().split()[-1]
    return {"serial": adb.serial, "android": adb.sh("getprop ro.build.version.release").strip(),
            "sdk": adb.sh("getprop ro.build.version.sdk").strip(), "model": adb.sh("getprop ro.product.model").strip(),
            "ekran": rozm, "gestosc": adb.sh("wm density").strip().split()[-1],
            "expo_go": EXPO_GO in adb.sh(f"pm list packages {EXPO_GO}"), "telefon": urzadzenie_testowe(adb),
            "zalegle_przywrocenia": list(adb.zalegle)}


def otworz(adb: Adb, cel: str) -> str:
    """Uruchamia aplikację (pakiet) albo podgląd Expo Go (exp://…); zwraca pakiet na pierwszym planie."""
    if cel.startswith(("exp://", "exps://")):
        adb.sh(f"am start -a android.intent.action.VIEW -d '{cel}' {EXPO_GO}")
        return EXPO_GO
    adb.sh(f"monkey -p {cel} -c android.intent.category.LAUNCHER 1")
    return cel


def na_wierzchu(adb: Adb) -> str:
    out = adb.sh("dumpsys activity activities")
    m = re.search(r"(?:mResumedActivity|topResumedActivity)[^\n]*?\s([\w.]+)/", out)
    return m.group(1) if m else ""


def tekst_ekranu(adb: Adb) -> list[str]:
    """Teksty z hierarchii widoku (uiautomator). Plik zrzutu w /data/local/tmp i usuwany od razu: na telefonie nic
    nie zostaje."""
    try:
        adb.sh(f"uiautomator dump {ZRZUT_UI}", timeout=30)
        xml = adb.sh(f"cat {ZRZUT_UI}")
    except RuntimeError:
        return []
    finally:
        try:
            adb.sh(f"rm -f {ZRZUT_UI}", timeout=15)
        except RuntimeError:
            pass
    return [t for t in re.findall(r'text="([^"]+)"', xml) if t.strip()]


def _czas_urzadzenia(adb: Adb) -> int | None:
    """Sekundy od 1970 na zegarze urządzenia (`date +%s`): od tej chwili czytamy bufor logów."""
    try:
        v = _ostatnia(adb.sh("date +%s", timeout=20))
    except RuntimeError:
        return None
    return int(v) if v.isdigit() else None


def awarie(adb: Adb, pakiet: str | None = None, od: int | None = None) -> list[str]:
    """Awarie z bufora crash i main. Bez `pakiet` (urządzenie jednorazowe po `logcat -c`) wszystkie, jak dotąd. Z nim
    (telefon właściciela) tylko testowanej aplikacji (jej pakiet, ReactNativeJS, FATAL EXCEPTION z jej procesem)
    i od chwili `od` (zegar urządzenia), bez czyszczenia bufora i bez awarii innych aplikacji właściciela w raporcie."""
    if pakiet is None:
        linie = adb.sh("logcat -d -b crash -b main -v brief *:E", timeout=30).splitlines()
        return [l[:240] for l in linie if AWARIA_RE.search(l)][:8]
    linie = adb.sh("logcat -d -b crash -b main -v epoch *:E", timeout=30).splitlines()
    wynik = []
    for i, l in enumerate(linie):
        czas = re.match(r"^\s*(\d{9,11})(?:\.\d+)?\s", l)
        if od is not None and czas and int(czas.group(1)) < od:
            continue
        if not AWARIA_RE.search(l):
            continue
        nastepna = linie[i + 1] if i + 1 < len(linie) else ""
        if pakiet in l or "ReactNativeJS" in l or f"Process: {pakiet}," in nastepna:
            wynik.append(l[:240])
    return wynik[:8]


def zrzut(adb: Adb, plik: Path) -> Path:
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_bytes(adb.run("exec-out", "screencap", "-p", binarnie=True, timeout=30))
    return plik


def _przyznane(adb: Adb, pakiet: str) -> list[str]:
    """Przyznane uprawnienia czasu działania (sekcja „runtime permissions” w `dumpsys package`); bez tej sekcji
    (starsze Androidy) wszystkie przyznane."""
    out = adb.sh(f"dumpsys package {pakiet}")
    m = re.search(r"runtime permissions:\s*\n((?:[ \t]+\S.*\n?)*)", out)
    zakres = m.group(1) if m else out
    return sorted(set(re.findall(r"([A-Za-z0-9_.]+\.permission\.[A-Za-z0-9_]+): granted=true", zakres)))


def _ma_siec(adb: Adb) -> bool:
    try:
        return bool(re.search(r"\b1 (?:packets )?received", adb.sh("ping -c 1 -W 2 1.1.1.1", timeout=10)))
    except RuntimeError:                 # ping bez odpowiedzi kończy się kodem ≠ 0
        return False


def scenariusz(adb: Adb, id_: str, cel: str, outdir: Path, urz: dict | None = None) -> dict:
    """Jeden test wrogi. `urz` = urzadzenie_testowe(adb); bez niego urządzenie jednorazowe (jak w kontenerze)."""
    urz = urz or {"jednorazowe": True, "przez_siec": False, "dlaczego": "urządzenie jednorazowe"}
    jednorazowe = urz["jednorazowe"]
    expo_go = cel.startswith(("exp://", "exps://"))
    pakiet = EXPO_GO if expo_go else cel
    r = {"id": id_, "warstwa": "android", "status": "ok", "obserwacje": {}, "dlaczego": "", "zrzuty": []}
    zm = Zmiany(adb, id_)
    od = None

    def uruchom_i_patrz(etykieta: str) -> None:
        otworz(adb, cel)
        time.sleep(CZEKAJ_S)
        r["zrzuty"].append(str(zrzut(adb, outdir / f"{id_}-{etykieta}.png")))

    def wartosci(*nazwy: str) -> dict[str, tuple[str, bool]] | None:
        """{ustawienie: (obecna wartość, odczytana)} albo None (wtedy test `not_run`: bez odczytu nie zmieniamy, bo
        nie umielibyśmy przywrócić)."""
        v = {n: odczytaj(adb, n, jednorazowe) for n in nazwy}
        brak = [OPISY[n] for n, (x, _) in v.items() if x is None]
        if brak:
            r.update(status="not_run", dlaczego=f"nie odczytam obecnej wartości ({', '.join(brak)}), więc jej na "
                     "telefonie nie zmieniam: nie umiałbym jej przywrócić")
            return None
        return v

    def zmien(v: dict, ustawienie: str, polecenia: list[str]) -> None:
        wartosc, odczytana = v[ustawienie]
        zm.zmien(ustawienie, wartosc, polecenia, sprawdz=odczytana)

    try:
        if jednorazowe:
            adb.sh("logcat -c")
        else:
            od = _czas_urzadzenia(adb)                   # bufor logów właściciela zostaje
        if id_ == "start":
            uruchom_i_patrz("ekran")
        elif id_ == "duza-czcionka":
            if not (v := wartosci("font_scale")):
                return r
            zmien(v, "font_scale", ["settings put system font_scale 2.0"])
            adb.sh(f"am force-stop {pakiet}")
            uruchom_i_patrz("ekran")
        elif id_ == "maly-ekran":
            if not (v := wartosci("wm_size", "wm_density")):
                return r
            zmien(v, "wm_size", ["wm size 720x1280"])
            zmien(v, "wm_density", ["wm density 320"])
            adb.sh(f"am force-stop {pakiet}")
            uruchom_i_patrz("ekran")
        elif id_ == "ciemny":
            if not (v := wartosci("noc")):
                return r
            zmien(v, "noc", ["cmd uimode night yes"])
            uruchom_i_patrz("ekran")
        elif id_ == "offline":
            if urz.get("przez_siec"):
                r.update(status="not_run", dlaczego="adb łączy się z telefonem przez Wi-Fi: tryb samolotowy odciąłby "
                         "sam adb (i flotę od telefonu); test offline przez kabel USB albo na emulatorze")
                return r
            # danych komórkowych nie ruszamy wcale: tryb samolotowy wyłącza radio, a _ma_siec sprawdza brak sieci.
            # Przy dwóch kartach SIM ustawienie jest per karta (mobile_data<subId>), a `svc data` zmienia kartę
            # domyślną: odczyt klucza bez numeru brał 1 i przywrócenie włączało dane, które właściciel miał wyłączone
            if not (v := wartosci("samolot", "wifi")):
                return r
            if v["samolot"][0] != "1":
                zmien(v, "samolot", ["cmd connectivity airplane-mode enable"])
            if v["wifi"][0] == "1":
                zmien(v, "wifi", ["svc wifi disable"])
            time.sleep(2)
            if _ma_siec(adb):
                r.update(status="not_run", dlaczego="urządzenie nie odcina sieci (np. Redroid po ethernecie): sprawdź na telefonie")
                return r
            uruchom_i_patrz("ekran")
            r["obserwacje"]["pasek_brak_sieci"] = any("Brak internetu" in t for t in tekst_ekranu(adb))
            if not r["obserwacje"]["pasek_brak_sieci"]:
                r.update(status="blad", dlaczego="bez sieci brak komunikatu „Brak internetu”")
        elif id_ == "uprawnienia":
            if expo_go:
                r.update(status="not_run", dlaczego="w Expo Go uprawnienia należą do Expo Go, nie do aplikacji: test na buildzie")
                return r
            odebrane = []
            for p in _przyznane(adb, pakiet):
                try:
                    zm.zmien("uprawnienie", f"{pakiet} {p}", [f"pm revoke {pakiet} {p}"])
                except RuntimeError as e:
                    if re.search(r"changeable|SecurityException|not a runtime", str(e), re.I):
                        continue                         # uprawnienie z instalacji: nie da się go odebrać
                    raise
                odebrane.append(p)
            r["obserwacje"]["odebrane"] = odebrane
            uruchom_i_patrz("ekran")
        elif id_ == "wstecz":
            uruchom_i_patrz("przed")
            adb.sh("input keyevent KEYCODE_BACK")
            time.sleep(1)
            adb.sh("input keyevent KEYCODE_BACK")
            time.sleep(1.5)
            r["zrzuty"].append(str(zrzut(adb, outdir / f"{id_}-po.png")))
        elif id_ == "smierc-procesu":
            uruchom_i_patrz("przed")
            adb.sh("input keyevent KEYCODE_HOME")
            time.sleep(1)
            adb.sh(f"am kill {pakiet}")
            time.sleep(1)
            uruchom_i_patrz("po")
        elif id_ == "swieza-instalacja":
            if expo_go:
                r.update(status="not_run", dlaczego="czyszczenie danych Expo Go wylogowałoby właściciela: test na buildzie")
                return r
            if not jednorazowe:
                r.update(status="not_run", dlaczego=f"{urz.get('dlaczego') or 'telefon'}: wyczyszczenia danych aplikacji "
                         "(pm clear) nie da się cofnąć, więc robię je tylko na emulatorze albo telefonie testowym "
                         "(właściciel oznacza go: `jarvo android on --telefon-testowy`)")
                return r
            adb.sh(f"pm clear {pakiet}")
            uruchom_i_patrz("ekran")
        bledy = awarie(adb, None if jednorazowe else pakiet, od)
        tekst = tekst_ekranu(adb) if id_ not in ("wstecz",) else ["-"]
        r["obserwacje"].update(awarie=bledy, tekst_na_ekranie=len(tekst), na_wierzchu=na_wierzchu(adb))
        if bledy:
            r.update(status="blad", dlaczego="awaria aplikacji (log crash / ReactNativeJS)")
        elif not tekst and id_ != "wstecz":
            r.update(status="blad", dlaczego="pusty ekran (brak tekstu w hierarchii widoku)")
    except RuntimeError as e:
        r.update(status="blad", dlaczego=f"adb: {e}")
    finally:
        nie = zm.przywroc()
        if nie:
            r["nieprzywrocone"] = nie
            r.update(status="blad", dlaczego="; ".join(x for x in (r["dlaczego"], "nie przywróciłem: " + ", ".join(nie)) if x))
    return r


def wrogie(adb: Adb, cel: str, outdir: Path, tylko: list[str] | None = None) -> dict:
    adb.polacz()
    if adb.zalegle:
        raise TelefonZmieniony("na telefonie są jeszcze ustawienia zmienione przez przerwany test: "
                               f"{', '.join(adb.zalegle)}; nowy test odczytałby je jako ustawienia właściciela. "
                               "Najpierw `urzadzenie.py przywroc` (telefon musi odpowiadać).")
    outdir.mkdir(parents=True, exist_ok=True)
    info = status(adb)
    if cel.startswith(("exp://", "exps://")) and not info["expo_go"]:
        raise BrakUrzadzenia("na urządzeniu nie ma Expo Go (zainstaluj: `npx expo start --android` w katalogu aplikacji)")
    urz = info["telefon"]
    wyniki = [scenariusz(adb, s, cel, outdir, urz) for s in (tylko or SCENARIUSZE) if s in SCENARIUSZE]
    licz = lambda s: sum(1 for w in wyniki if w["status"] == s)  # noqa: E731
    zmienione = [x for w in wyniki for x in w.get("nieprzywrocone", [])]
    raport = {"urzadzenie": info, "cel": cel, "wyniki": wyniki, "telefon_zmieniony": zmienione,
              "podsumowanie": f"android {info['android']}: {licz('ok')} ok, {licz('blad')} błędów, {licz('not_run')} bez pomiaru"}
    (outdir / "wrogie.json").write_text(json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
    return raport


def _komunikat_zmian(zmienione: list[str]) -> str:
    return ("UWAGA: na telefonie zostały zmienione ustawienia, których nie przywróciłem: " + ", ".join(zmienione)
            + ". Powiedz o tym właścicielowi; przywróci je `urzadzenie.py przywroc`, gdy telefon znów odpowiada "
            "(albo `jarvo android off`), a w ostateczności właściciel w ustawieniach telefonu.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    sub.add_parser("zainstaluj").add_argument("apk")
    sub.add_parser("otworz").add_argument("cel")
    sub.add_parser("zrzut").add_argument("plik")
    lg = sub.add_parser("logi")
    lg.add_argument("--pakiet")
    lg.add_argument("--linie", type=int, default=200)
    w = sub.add_parser("wrogie")
    w.add_argument("cel")
    w.add_argument("outdir")
    w.add_argument("--tylko")
    sub.add_parser("przywroc")
    args = ap.parse_args(argv)
    adb = Adb()
    try:
        if args.cmd == "status":
            info = status(adb)
            print(json.dumps(info, ensure_ascii=False, indent=2) if args.json else
                  f"✓ {info['serial']}: Android {info['android']} (SDK {info['sdk']}), {info['model']}, {info['ekran']} "
                  f"@{info['gestosc']} dpi, Expo Go: {'tak' if info['expo_go'] else 'nie'}, {info['telefon']['dlaczego']}")
            return 4 if adb.zalegle else 0
        adb.polacz()
        if args.cmd == "przywroc":
            if adb.zalegle:
                print(_komunikat_zmian(adb.zalegle), file=sys.stderr)
                return 4
            print("Przywrócone: " + ", ".join(adb.przywrocone_zalegle) if adb.przywrocone_zalegle else
                  "Nic do przywrócenia: urządzenie ma ustawienia sprzed testów.")
        elif args.cmd == "zainstaluj":
            print(adb.run("install", "-r", "-g", args.apk, timeout=300).strip())
        elif args.cmd == "otworz":
            print(otworz(adb, args.cel))
        elif args.cmd == "zrzut":
            print(zrzut(adb, Path(args.plik)).as_posix())
        elif args.cmd == "logi":
            out = adb.sh("logcat -d -v brief *:W", timeout=30).splitlines()
            print("\n".join([l for l in out if not args.pakiet or args.pakiet in l or "ReactNativeJS" in l][-args.linie:]))
        elif args.cmd == "wrogie":
            r = wrogie(adb, args.cel, Path(args.outdir), args.tylko.split(",") if args.tylko else None)
            print(r["podsumowanie"])
            if r["telefon_zmieniony"]:
                print(_komunikat_zmian(r["telefon_zmieniony"]), file=sys.stderr)
                return 4
            return 1 if any(x["status"] == "blad" for x in r["wyniki"]) else 0
        return 0
    except BrakUrzadzenia as e:
        zalegle = [opis(x) for x in zalegle_przywrocenia(adb)] if adb.serial else []
        print(f"✗ {e}" + (f"\nUwaga: zaległe przywrócenia ustawień z przerwanego testu ({', '.join(zalegle)}) wykona "
                          "następne polecenie, gdy telefon będzie podłączony." if zalegle else ""), file=sys.stderr)
        return 3
    except TelefonZmieniony as e:
        print(f"✗ {e}", file=sys.stderr)
        return 4
    except RuntimeError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwane (zmienione ustawienia przywrócone albo zapisane w dzienniku przywróceń).", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

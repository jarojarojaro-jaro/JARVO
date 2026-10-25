#!/usr/bin/env python3
"""Telefon, 3D i ManimGX na żywo w instalacji natywnej (docs/NATYWNIE.md etap E11: F08, E11, E13, M04, U04, U05).

    python -X utf8 -B tests/live/natywnie_telefon_3d.py --wyniki <katalog> [--korzen <JARVO_ROOT>]
        [--akceptuje-licencje-sdk] [--dopusc "punkt=powód;…"] [--limit SEKUNDY] [--raport-e2e [KATALOG]]
        [--punkty adb,android,scrcpy,przywracanie,cad,film,manimgx,doctor]

Sprawdza zainstalowaną wersję Jarva (kod z `<program>/current.json`), tak jak użyje jej właściciel i flota:
  adb           platform-tools przy pierwszym użyciu (vendor/natywne.yaml, `kiedy: przy-uzyciu`) przez jarvo/android.py
                `on --akceptuje-licencje`, potem `adb version` = 37.0.1 z instalacji. Licencję Android SDK akceptuje
                właściciel: test robi to tylko z --akceptuje-licencje-sdk (bez flagi adb, android i scrcpy są
                pominięte z powodem); Linux arm64: Google nie wydaje platform-tools (pominięte z powodem z manifestu)
  android       `jarvo android status --json` (włączony, lista urządzeń; na runnerze zwykle pusta), `off` (wyłączony,
                serwer adb zatrzymany), urzadzenie.py floty: kod 3 z radą `jarvo android on` przy wyłączonym telefonie
  scrcpy        scrcpy przy pierwszym użyciu, `scrcpy --version` (bez okna); `ekran` bez urządzenia kończy się kodem 1
                bez okna (tylko gdy adb nie widzi żadnego urządzenia); Linux arm64: pominięte
  przywracanie  urzadzenie.py floty (kopia w profilu Twórcy aplikacji) na atrapie telefonu właściciela (ATRAPA_TELEFONU:
                adb ze stanem telefonu w pliku): `wrogie` zostawia każde ustawienie (czcionka, ekran, tryb ciemny,
                tryb samolotowy, Wi-Fi, dane, uprawnienia) takie, jakie było, bez `pm clear`, `logcat -c` i plików na
                telefonie; telefon odłączony w trakcie testu offline = kod 4 i wpisy w <stan>/android-przywroc.json,
                a po podłączeniu `urzadzenie.py przywroc` przywraca wszystko (bez prawdziwego telefonu i bez sieci)
  cad           `cad.py zainstaluj` (venv cad i Three.js przy pierwszym użyciu), kostka 20 mm z otworem → STEP, STL,
                GLB, raport (20 × 20 × 20 mm, poprawny) i PNG podglądu w chrome-headless-shell z instalacji
  film          `cad.py obrot`: 1 s, 12 kl./s, 360 × 360 → MP4 (ffmpeg z instalacji)
  manimgx       ManimGX przy pierwszym użyciu (program `manimgx` z bin-floty, a bez niego ten sam kod jarvo/manimgx.py
                Pythonem z instalacji): przed instalacją `--version` nic nie pobiera, tylko mówi, ile pobierze i jak
                zainstalować za zgodą właściciela (kod 127); `--jarvo-zainstaluj`, potem `--version` = 0.1.1 i scena
                1 s 640 × 360 z polskim tekstem (MP4 i storyboard); render bez GPU na Windows i macOS jest
                niesprawdzony: `--dopusc manimgx=…`
  doctor        jarvo/android.sprawdzenia (telefon i ekran w `jarvo doctor`): bez błędów
Każdy punkt: ok, blad, uwaga (błąd dopuszczony przez --dopusc) albo pominiete (z powodem). Kod wyjścia 1, gdy któryś
ma stan blad (2: złe argumenty albo brak instalacji); raport JSON na stdout i w <wyniki>/raport.json (punkty z czasem,
czas całości, limit), pliki (PNG, MP4, logi poleceń) w <wyniki>. --limit: czas całego testu w sekundach; polecenia
dostają tylko to, co zostało, a punkty po jego końcu są pominięte z powodem, więc raport powstaje, zanim zewnętrzny
limit czasu przerwie proces.
--raport-e2e: punkty także w <artefakty>/raport.json testu natywnie_e2e.py (id `e11-<punkt>`, ten sam katalog co jego
--artefakty, domyślnie $JARVO_E2E_ARTEFAKTY albo $RUNNER_TEMP/natywnie-artefakty), więc widać je w jego podsumowaniu.
Polecenia skilli idą w środowisku procesów floty (jarvo/srodowisko.py, Python venvu narzędzi = @@PY@@). Na koniec
telefon testowy wyłączony (`off`), a venvy i narzędzia przy pierwszym użyciu zostają w instalacji (to ich normalny
stan). Sama biblioteka standardowa (dowolny Python 3.11+); okien nie otwiera, sieci używa tylko do pobrań z sumą.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from jarvo import sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PUNKTY = ("adb", "android", "scrcpy", "przywracanie", "cad", "film", "manimgx", "doctor")
KOSTKA = """from build123d import *

BOK = 20     # mm
OTWOR = 6    # mm, otwór na wylot

with BuildPart() as kostka:
    Box(BOK, BOK, BOK)
    fillet(kostka.edges(), radius=1.5)
    Cylinder(OTWOR / 2, BOK, mode=Mode.SUBTRACT)

wynik = kostka.part
"""
SCENA = """from manimgx import *


class Proba(Scene):
    def construct(self):
        napis = Text("Zażółć gęślą jaźń", font="Noto Sans", font_size=40)
        kolo = Circle(radius=1.0, color=BLUE).next_to(napis, DOWN)
        self.play(Write(napis), run_time=0.5)
        self.play(Create(kolo), run_time=0.5)
"""

# Atrapa adb z telefonem: stan telefonu w pliku JSON (ATRAPA_TELEFON), dziennik wywołań (ATRAPA_LOG, opcjonalnie).
# Rozumie polecenia urzadzenie.py i pakiet.py (zrzuty do sklepów); nieznane polecenie powłoki = błąd, więc nowa zmiana
# ustawień bez obsługi w atrapie nie przejdzie po cichu. „zerwij_po”: telefon odłącza się po tym poleceniu (kabel
# wyjęty w trakcie testu), „odmawia”: polecenia, które telefon odrzuca. Używają jej też tests/test_mobile_android.py.
ATRAPA_TELEFONU = r'''
import json, os, re, sys, time

PLIK = os.environ["ATRAPA_TELEFON"]
args = sys.argv[1:]
with open(PLIK, encoding="utf-8") as f:
    s = json.load(f)
if os.environ.get("ATRAPA_LOG"):
    with open(os.environ["ATRAPA_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": args, "home": os.environ.get("HOME"), "mdns": os.environ.get("ADB_MDNS"),
                            "log": os.environ.get("ANDROID_ADB_LOG_PATH")}) + "\n")


def koniec(tekst="", kod=0, blad=""):
    with open(PLIK, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    if tekst:
        sys.stdout.write(tekst if tekst.endswith("\n") else tekst + "\n")
    if blad:
        sys.stderr.write(blad + "\n")
    sys.exit(kod)


serial = None
if args[:1] == ["-s"]:
    serial, args = args[1], args[2:]
if args == ["version"]:
    koniec("Android Debug Bridge version 1.0.41\nVersion 37.0.1-15733141\nInstalled as adb")
if args in (["start-server"], ["kill-server"]):
    koniec("* daemon started successfully" if args == ["start-server"] else "")
if args[:1] == ["devices"]:
    koniec("List of devices attached\n" + (f"{s['serial']}\tdevice usb:1-1 model:{s.get('model', 'Pixel_8')}\n"
                                          if s["podlaczony"] else ""))
if args[:1] in (["connect"], ["disconnect"]):
    koniec(f"connected to {args[1]}" if args[0] == "connect" else "")
if serial is not None and (serial != s["serial"] or not s["podlaczony"]):
    koniec(kod=1, blad=f"adb: device '{serial}' not found")
if args == ["get-state"]:
    koniec("device")
if args[:2] == ["exec-out", "screencap"]:
    sys.stdout.buffer.write(b"\x89PNG\r\n\x1a\n" + bytes(64))
    koniec()
if args[:1] == ["install"]:
    koniec("Success")
if args[:1] != ["shell"] or len(args) < 2:
    koniec(kod=1, blad=f"atrapa: nie znam {args}")
p = " ".join(args[1:])
s.setdefault("polecenia", []).append(p)
if p in s.get("odmawia", []):
    koniec(kod=1, blad=f"Exception occurred while executing: {p}")
upr = s.setdefault("uprawnienia", {})
out = ""
m = re.fullmatch(r"(settings put system font_scale|wm size|wm density|cmd uimode night|cmd connectivity airplane-mode"
                 r"|svc wifi|svc data|settings put global sysui_demo_allowed|pm revoke|pm grant) (.+)", p)
if p == "settings get system font_scale":
    out = s["font_scale"]
elif p == "settings delete system font_scale":
    s["font_scale"] = "null"
elif p in ("wm size", "wm density"):
    co = p.split()[1]
    out = f"Physical {co}: {'1080x2400' if co == 'size' else '420'}"
    out += f"\nOverride {co}: {s['wm_' + co]}" if s["wm_" + co] != "-" else ""
elif p == "cmd uimode night":
    out = f"Night mode: {s['noc']}"
elif p == "settings get global airplane_mode_on":
    out = s["samolot"]
elif p == "settings get global wifi_on":
    out = s["wifi"]
elif p == "settings get global mobile_data":
    out = s["dane"]
elif p == "settings get global sysui_demo_allowed":
    out = s.get("demo_zgoda", "null")
elif p == "settings delete global sysui_demo_allowed":
    s["demo_zgoda"] = "null"
elif m:
    co, v = m.groups()
    if co == "settings put system font_scale":
        s["font_scale"] = v
    elif co in ("wm size", "wm density"):
        s["wm_" + co.split()[1]] = "-" if v == "reset" else v
    elif co == "cmd uimode night":
        s["noc"] = v
        out = f"Night mode: {v}"
    elif co == "cmd connectivity airplane-mode":
        s["samolot"] = "1" if v == "enable" else "0"
    elif co == "svc wifi":
        s["wifi"] = "1" if v == "enable" else "0"
    elif co == "svc data":
        s["dane"] = "1" if v == "enable" else "0"
    elif co == "settings put global sysui_demo_allowed":
        s["demo_zgoda"] = v
    else:
        pakiet, _, nazwa = v.partition(" ")
        if upr.get(nazwa) in (None, "instalacja"):
            koniec(kod=255, blad=f"Exception occurred while executing '{co.split()[1]}':\njava.lang.SecurityException: "
                                f"Permission {nazwa} requested by {pakiet} is not a changeable permission type")
        upr[nazwa] = co == "pm grant"
elif p.startswith("am broadcast -a com.android.systemui.demo"):
    s["demo"] = "command exit" not in p
elif p.startswith("dumpsys package "):
    out = ("Packages:\n  Package [" + p.split()[2] + "]:\n    install permissions:\n"
           + "".join(f"      {k}: granted=true\n" for k, v in upr.items() if v == "instalacja")
           + "    User 0: ceDataInode=1 installed=true\n      runtime permissions:\n"
           + "".join(f"        {k}: granted={'true' if v else 'false'}, flags=[ USER_SET ]\n"
                     for k, v in upr.items() if v != "instalacja"))
elif p.startswith("pm clear "):
    s["dane_wyczyszczone"] = True
    out = "Success"
elif p.startswith("pm list packages"):
    out = "package:" + p.split()[-1]
elif p.startswith("getprop "):
    out = {"ro.build.version.release": "15", "ro.build.version.sdk": "35", "ro.product.model": "Pixel 8",
           "ro.kernel.qemu": s.get("qemu", ""), "ro.boot.qemu": ""}.get(p.split()[1], "")
elif p == "date +%s":
    out = str(int(time.time()))
elif p == "logcat -c":
    s["logcat_wyczyszczony"] = True
elif p.startswith("logcat -d"):
    out = "\n".join(s.get("logcat", []))
elif p.startswith("uiautomator dump "):
    s.setdefault("pliki", []).append(p.split()[2])
    out = "UI hierchary dumped to: " + p.split()[2]
elif p.startswith("cat "):
    if p.split()[1] not in s.get("pliki", []):
        koniec(kod=1, blad="cat: No such file or directory")
    teksty = ["Start", "Salon Ola"] + (["Brak internetu"] if s["samolot"] == "1" else [])
    out = "".join(f'<node text="{t}"/>' for t in teksty)
elif p.startswith("rm -f "):
    s["pliki"] = [x for x in s.get("pliki", []) if x != p.split()[2]]
elif p.startswith("dumpsys activity"):
    out = "  mResumedActivity: ActivityRecord{1 u0 " + s.get("pakiet", "pl.jarvo.proba") + "/.MainActivity t9}"
elif p.startswith("ping "):
    if s["samolot"] == "1" or (s["wifi"] == "0" and s["dane"] == "0"):
        koniec(kod=1, blad="connect: Network is unreachable")
    out = "1 packets transmitted, 1 received, 0% packet loss"
elif not p.startswith(("monkey ", "am start ", "am force-stop ", "am kill ", "input keyevent ")):
    koniec(kod=1, blad=f"atrapa: nieznane polecenie {p!r}")
if s.get("zerwij_po") == p:
    s["podlaczony"] = False
    s["zerwij_po"] = None
koniec(out)
'''
# telefon właściciela w atrapie: ustawienia inne niż domyślne (dane komórkowe wyłączone, np. w roamingu)
TELEFON = {"serial": "R58TEST0001", "podlaczony": True, "model": "Pixel_8", "pakiet": "pl.jarvo.proba",
           "font_scale": "1.15", "wm_size": "1080x2000", "wm_density": "-", "noc": "auto", "samolot": "0",
           "wifi": "1", "dane": "0", "demo_zgoda": "null",
           "uprawnienia": {"android.permission.CAMERA": True, "android.permission.POST_NOTIFICATIONS": False,
                           "android.permission.INTERNET": "instalacja"}}
USTAWIENIA_TELEFONU = ("font_scale", "wm_size", "wm_density", "noc", "samolot", "wifi", "dane", "demo_zgoda",
                       "uprawnienia")


class Niepowodzenie(Exception):
    pass


class Pominiete(Exception):
    pass


def musi(warunek, opis: str) -> None:
    if not warunek:
        raise Niepowodzenie(opis)


def json_z(tekst: str):
    """Ostatni obiekt JSON wypisany z wcięciem (`--json`): od ostatniego wiersza „{” bez wcięcia; postęp pobierania
    z stderr jest w tym samym pliku przed nim."""
    wiersze = tekst.splitlines()
    poczatki = [i for i, w in enumerate(wiersze) if w.rstrip() == "{"]
    musi(poczatki, f"brak JSON w wyjściu: {tekst[-300:]}")
    return json.loads("\n".join(wiersze[poczatki[-1]:]))


def _dopuszczenia(tekst: str) -> dict[str, str]:
    wynik = {}
    for kawalek in filter(None, (x.strip() for x in (tekst or "").split(";"))):
        nazwa, _, powod = kawalek.partition("=")
        wynik[nazwa.strip()] = powod.strip() or "dopuszczone"
    return wynik


def roznice_telefonu(przed: dict, po: dict) -> list[str]:
    """Ustawienia atrapy telefonu, które test zostawił inne niż przed nim."""
    return [f"{k}: {przed.get(k)!r} → {po.get(k)!r}" for k in USTAWIENIA_TELEFONU if przed.get(k) != po.get(k)]


# ---------------------------------------------------------------- instalacja i polecenia

class Proba:
    def __init__(self, a: argparse.Namespace):
        baza = {k: v for k, v in os.environ.items() if not k.upper().startswith(("JARVO_", "HERMES_"))}
        korzen = a.korzen or os.environ.get("JARVO_ROOT")
        if korzen:
            baza["JARVO_ROOT"] = korzen
        self.u = sciezki.uklad(baza)
        biez = srodowisko.biezace(self.u)
        if not biez.get("app"):
            raise SystemExit(f"brak instalacji natywnej w {self.u.root} (program/current.json)")
        self.app = Path(biez["app"])
        self.narz = srodowisko.narzedzia(self.u)
        self.baza = {**baza, "JARVO_ROOT": str(self.u.root), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        self.env = srodowisko.srodowisko(self.u, self.baza)          # jak procesy floty (brama, terminal agenta)
        self.wyniki = Path(a.wyniki).resolve()
        self.wyniki.mkdir(parents=True, exist_ok=True)
        self.platforma = sciezki.platforma()
        self.dopusc = _dopuszczenia(a.dopusc)
        self.licencja = bool(a.akceptuje_licencje_sdk)
        self.punkty: list[dict] = []
        self.py313 = self._python("python313")
        self.start = time.monotonic()
        self.limit = float(a.limit or 0)

    def pozostalo(self) -> float | None:
        """Sekundy do końca --limit (None = bez limitu)."""
        return None if not self.limit else self.limit - (time.monotonic() - self.start)

    def _python(self, nazwa: str) -> Path:
        k = Path(str((self.narz.get(nazwa) or {}).get("katalog") or ""))
        p = k / ("python.exe" if WINDOWS else "bin/python3")
        return p if p.is_file() else Path(sys.executable)

    def py_floty(self) -> Path:
        """@@PY@@ skilli: Python venvu narzędzi z instalacji."""
        p = Path(str((srodowisko.narzedzia(self.u).get("venv-narzedzia") or {}).get("python") or ""))
        if not p.is_file():
            raise Niepowodzenie("brak venvu narzędzi w instalacji (narzedzia.json: venv-narzedzia)")
        return p

    def uruchom(self, nazwa: str, argv: list, *, env: dict | None = None, czas: float = 600,
                cwd: Path | None = None) -> tuple[int, str]:
        """Polecenie z wyjściem do pliku (serwer adb dziedziczy uchwyty: potok nie dostałby końca), log w wynikach.
        Limit czasu: `czas`, ale nie dłużej niż do końca --limit."""
        zostalo = self.pozostalo()
        if zostalo is not None:
            if zostalo <= 5:
                raise Niepowodzenie(f"koniec czasu testu (--limit {self.limit:.0f} s) przed: {nazwa}")
            czas = min(czas, zostalo - 5)
        log = self.wyniki / f"{nazwa}.log"
        with open(log, "ab") as f:
            f.write(f"\n=== {time.strftime('%H:%M:%S')} {' '.join(str(x) for x in argv)}\n".encode("utf-8"))
            f.flush()
            start = f.tell()
            try:
                p = subprocess.run([str(x) for x in argv], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
                                   env=env or self.env, cwd=str(cwd or self.wyniki), timeout=czas,
                                   creationflags=NO_WINDOW)
                kod = p.returncode
            except subprocess.TimeoutExpired:
                kod = 124
        with open(log, "rb") as f:
            f.seek(start)
            return kod, f.read().decode("utf-8", errors="replace").replace("\r\n", "\n")

    def android(self, *argv: str, czas: float = 300) -> tuple[int, str]:
        return self.uruchom("android", [self.py313, "-I", "-X", "utf8", self.app / "jarvo" / "android.py", *argv],
                            env={**self.baza}, czas=czas)

    def punkt(self, nazwa: str, f: Callable[[], str]) -> None:
        t0 = time.monotonic()
        zostalo = self.pozostalo()
        try:
            if zostalo is not None and zostalo <= 5:
                raise Pominiete(f"koniec czasu testu (--limit {self.limit:.0f} s)")
            opis, stan = f(), "ok"
        except Pominiete as e:
            opis, stan = str(e), "pominiete"
        except Niepowodzenie as e:
            opis, stan = str(e), ("uwaga" if nazwa in self.dopusc else "blad")
            if nazwa in self.dopusc:
                opis += f" (dopuszczone: {self.dopusc[nazwa]})"
        except Exception as e:  # noqa: BLE001 - błąd testu też trafia do raportu
            opis, stan = f"{type(e).__name__}: {e}", "blad"
        w = {"nazwa": nazwa, "stan": stan, "opis": opis, "czas_s": round(time.monotonic() - t0, 1)}
        self.punkty.append(w)
        print(f"[{stan}] {nazwa}: {opis} ({w['czas_s']} s)", file=sys.stderr, flush=True)

    # -------------------------------------------------------------- punkty

    def brak_platformy(self, narzedzie: str) -> str | None:
        """Powód `brak` z manifestu tej wersji dla tej platformy albo None."""
        lock = json.loads((self.app / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
        p = ((lock["narzedzia"].get(narzedzie) or {}).get("pliki") or {}).get(self.platforma) or {}
        return p.get("brak")

    def bez_licencji(self) -> None:
        if not self.licencja:
            raise Pominiete("bez --akceptuje-licencje-sdk: licencję Android SDK (platform-tools, adb w scrcpy) "
                            "akceptuje właściciel, więc test niczego od Google nie pobiera")

    def adb(self) -> str:
        if (powod := self.brak_platformy("platform-tools")) and not shutil.which("adb"):
            raise Pominiete(f"platform-tools na {self.platforma}: {powod}")
        self.bez_licencji()
        kod, out = self.android("on", "--akceptuje-licencje")
        musi(kod == 0, f"jarvo android on: kod {kod}: {out[-400:]}")
        musi("włączony" in out, f"on bez potwierdzenia: {out[-300:]}")
        w = srodowisko.narzedzia(self.u).get("platform-tools") or {}
        if not w and self.platforma == "linux-arm64":
            adb = shutil.which("adb")
        else:
            musi(w.get("wersja") == "37.0.1", f"narzedzia.json bez platform-tools 37.0.1: {w}")
            adb = str(Path(w["katalog"]) / ("adb.exe" if WINDOWS else "adb"))
        kod, out = self.uruchom("adb", [adb, "version"])
        musi(kod == 0 and (re.search(r"Version 37\.0\.1", out) or self.platforma == "linux-arm64"),
             f"adb version: kod {kod}: {out[-300:]}")
        musi("ADB_MDNS" in json.loads((self.u.stan / "srodowisko.json").read_text(encoding="utf-8"))
             or self.platforma == "linux-arm64", "srodowisko.json bez ADB_MDNS z wpisu platform-tools")
        return f"{adb}: {out.strip().splitlines()[1] if len(out.strip().splitlines()) > 1 else out.strip()}"

    def stan_androida(self) -> dict:
        kod, out = self.android("status", "--json", czas=120)
        musi(kod == 0, f"jarvo android status: kod {kod}: {out[-300:]}")
        return json_z(out)

    def urzadzenie_py(self) -> Path:
        """urzadzenie.py floty (kopia w profilu Twórcy aplikacji), a bez floty z kodu instalacji."""
        urz = self.u.dane / "profiles" / "jarvo-mobile" / "scripts" / "urzadzenie.py"
        return urz if urz.is_file() else self.app / "profiles" / "jarvo-mobile" / "scripts" / "urzadzenie.py"

    def android_punkt(self) -> str:
        if not (self.u.stan / "android.json").is_file():
            raise Pominiete("brak <stan>/android.json (punkt adb pominięty albo nieudany)")
        s = self.stan_androida()
        musi(s["wlaczony"] and s["podglad_hq"].startswith("wyłączony"), f"status po on: {s}")
        urzadzenia = s.get("urzadzenia") or []
        kod, out = self.android("off")
        musi(kod == 0, f"jarvo android off: kod {kod}: {out[-300:]}")
        musi(not self.stan_androida()["wlaczony"], "po off telefon dalej włączony")
        kod, out = self.uruchom("urzadzenie", [self.py_floty(), "-X", "utf8", self.urzadzenie_py(), "status"], czas=120)
        musi(kod == 3 and "jarvo android on" in out, f"urzadzenie.py przy wyłączonym telefonie: kod {kod}: {out[-300:]}")
        return f"on → włączony ({len(urzadzenia)} urządzeń), off → wyłączony, urzadzenie.py: kod 3 z radą"

    def scrcpy(self) -> str:
        if powod := self.brak_platformy("scrcpy"):
            raise Pominiete(f"scrcpy na {self.platforma}: {powod}")
        self.bez_licencji()
        from jarvo import przy_uzyciu                     # pakiet z tego repo, manifest z kodu instalacji (app)
        w = przy_uzyciu.narzedzie(self.u, "scrcpy", app=self.app, log=lambda t: print(t, file=sys.stderr))
        program = przy_uzyciu.program_narzedzia(w, "scrcpy")
        musi(program is not None, f"brak programu scrcpy w {w.get('katalog')}")
        kod, out = self.uruchom("scrcpy", [program, "--version"], czas=60)
        musi(kod == 0 and "scrcpy 5.0.1" in out, f"scrcpy --version: kod {kod}: {out[-300:]}")
        opis = f"scrcpy 5.0.1 ({program})"
        if (self.u.stan / "android.json").is_file():
            kod, out = self.android("on", "--akceptuje-licencje")
            s = self.stan_androida()
            if not s.get("urzadzenia"):                     # okno tylko z urządzeniem: bez niego sprawdzamy odmowę
                kod, out = self.android("ekran")
                musi(kod == 1 and "brak gotowego urządzenia" in out, f"ekran bez urządzenia: kod {kod}: {out[-300:]}")
                opis += "; ekran bez urządzenia: kod 1, bez okna"
            self.android("off")
        return opis

    def przywracanie(self) -> str:
        """urzadzenie.py floty na atrapie telefonu właściciela: każde ustawienie wraca, także po zerwanym połączeniu."""
        sys.path.insert(0, str(REPO / "tests"))
        import atrapy                                     # tests/atrapy.py: program z kodu Pythona (Windows: .cmd)
        katalog = self.wyniki / "telefon-atrapa"
        katalog.mkdir(exist_ok=True)
        adb = atrapy.program(katalog / "bin", "adb", ATRAPA_TELEFONU)
        stan = katalog / "telefon.json"
        dziennik = self.u.stan / "android-przywroc.json"
        musi(not dziennik.exists(), f"{dziennik} przed testem: zaległe przywrócenia z innej próby")
        env = {**self.env, "JARVO_ADB": str(adb), "JARVO_ANDROID_ADB": TELEFON["serial"], "ATRAPA_TELEFON": str(stan),
               "ATRAPA_LOG": str(katalog / "adb.jsonl"), "JARVO_ANDROID_CZEKAJ": "0"}
        urz = [self.py_floty(), "-X", "utf8", self.urzadzenie_py()]

        stan.write_text(json.dumps(TELEFON), encoding="utf-8")
        kod, out = self.uruchom("przywracanie", [*urz, "wrogie", TELEFON["pakiet"], katalog / "wrogie"], env=env,
                                czas=300)
        po = json.loads(stan.read_text(encoding="utf-8"))
        musi(kod == 0, f"urzadzenie.py wrogie na atrapie: kod {kod}: {out[-600:]}")
        musi(not roznice_telefonu(TELEFON, po), f"telefon po testach inny niż przed: {roznice_telefonu(TELEFON, po)}")
        raport = json.loads((katalog / "wrogie" / "wrogie.json").read_text(encoding="utf-8"))
        st = {w["id"]: w["status"] for w in raport["wyniki"]}
        musi(st.get("swieza-instalacja") == "not_run" and not po.get("dane_wyczyszczone"),
             f"pm clear na telefonie właściciela: {st}")
        musi(st.get("offline") == "ok" and "svc data enable" not in po["polecenia"],
             f"offline: {st.get('offline')}, dane komórkowe włączone mimo wyłączonych przed testem?")
        musi("logcat -c" not in po["polecenia"] and not po.get("pliki")
             and not any("/sdcard" in x for x in po["polecenia"]), "ślad na telefonie (logcat -c, pliki)")
        musi(not dziennik.exists(), f"po udanych testach zostały wpisy w {dziennik}")
        ok = sum(1 for v in st.values() if v == "ok")

        stan.write_text(json.dumps({**TELEFON, "zerwij_po": "svc wifi disable"}), encoding="utf-8")
        kod, out = self.uruchom("przywracanie", [*urz, "wrogie", TELEFON["pakiet"], katalog / "wrogie-zerwany",
                                                 "--tylko", "offline"], env=env, czas=300)
        po = json.loads(stan.read_text(encoding="utf-8"))
        musi(kod == 4 and "tryb samolotowy" in out, f"zerwane połączenie: kod {kod} (ma być 4): {out[-600:]}")
        musi(po["samolot"] == "1" and po["wifi"] == "0", f"atrapa nie zerwała połączenia po svc wifi disable: {po}")
        zalegle = json.loads(dziennik.read_text(encoding="utf-8")).get(TELEFON["serial"]) or []
        musi({w["ustawienie"] for w in zalegle} == {"samolot", "wifi"}, f"dziennik przywróceń: {zalegle}")
        po["podlaczony"] = True                           # kabel z powrotem
        stan.write_text(json.dumps(po), encoding="utf-8")
        kod, out = self.uruchom("przywracanie", [*urz, "przywroc"], env=env, czas=120)
        po = json.loads(stan.read_text(encoding="utf-8"))
        musi(kod == 0 and "Przywrócone" in out, f"urzadzenie.py przywroc: kod {kod}: {out[-400:]}")
        musi(not roznice_telefonu(TELEFON, po), f"po przywroc telefon inny niż przed: {roznice_telefonu(TELEFON, po)}")
        musi(not dziennik.exists(), f"po przywroc zostały wpisy w {dziennik}")
        return (f"wrogie na telefonie właściciela (atrapa): {ok} ok, ustawienia jak przed testem, bez pm clear, logcat -c "
                "i plików; zerwane połączenie: kod 4 i 2 wpisy w dzienniku, przywroc po podłączeniu: telefon jak przed")

    def cad(self) -> str:
        cad = self.cad_py()
        kod, out = self.uruchom("cad", [self.py_floty(), "-X", "utf8", cad, "zainstaluj", "--json"], czas=1800)
        musi(kod == 0, f"cad.py zainstaluj: kod {kod}: {out[-600:]}")
        stan = json_z(out)["stan"]
        musi((stan.get("silnik") or {}).get("build123d") == "0.13.0", f"silnik: {stan.get('silnik')}")
        katalog = self.wyniki / "cad"
        katalog.mkdir(exist_ok=True)
        (katalog / "kostka.py").write_text(KOSTKA, encoding="utf-8")
        kod, out = self.uruchom("cad", [self.py_floty(), "-X", "utf8", cad, "zbuduj", katalog / "kostka.py", "-o",
                                        katalog, "--formaty", "step,stl,glb", "--podglad", "--json"], czas=900,
                                cwd=katalog)
        musi(kod == 0, f"cad.py zbuduj: kod {kod}: {out[-600:]}")
        r = json_z(out)
        musi(r["wymiary_mm"] == [20.0, 20.0, 20.0] and r["poprawny"] and r["bryly"] == 1, f"raport: {r}")
        for f in ("step", "stl", "glb"):
            musi(Path(r["pliki"][f]["plik"]).stat().st_size > 1000, f"{f} pusty")
        png = katalog / "kostka.png"
        musi(png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size > 5000, "brak PNG podglądu")
        sposob = (stan.get("podglad") or {}).get("sposob")
        return (f"build123d 0.13.0, kostka 20 × 20 × 20 mm: STEP, STL ({r['pliki']['stl'].get('trojkaty')} trójkątów), "
                f"GLB i PNG ({png.stat().st_size // 1024} KB, podgląd: {sposob})")

    def film(self) -> str:
        glb = self.wyniki / "cad" / "kostka.glb"
        if not glb.is_file():
            raise Pominiete("brak kostka.glb z punktu cad")
        mp4 = self.wyniki / "cad" / "obrot.mp4"
        kod, out = self.uruchom("cad", [self.py_floty(), "-X", "utf8", self.cad_py(), "obrot", glb, "-o", mp4,
                                        "--sekundy", "1", "--fps", "12", "--rozmiar", "360x360", "--json"], czas=900)
        musi(kod == 0 and mp4.is_file() and mp4.stat().st_size > 1000, f"cad.py obrot: kod {kod}: {out[-400:]}")
        r = json_z(out)
        return f"{r['klatek']} klatek w {r['render_s']} s, {mp4.stat().st_size // 1024} KB"

    def cad_py(self) -> Path:
        """cad.py z floty (skill zainstalowany w profilu Twórcy aplikacji), a bez floty z kodu instalacji."""
        flota = self.u.dane / "profiles" / "jarvo-mobile" / "skills" / "design" / "warsztat-3d" / "scripts" / "cad.py"
        return flota if flota.is_file() else self.app / "shared" / "skills" / "warsztat-3d" / "scripts" / "cad.py"

    def manimgx(self) -> str:
        program = self.u.bin_floty / ("manimgx.exe" if WINDOWS else "manimgx")
        if program.is_file():
            argv, skad = [program], "bin-floty"
        else:
            argv, skad = [self.py313, "-I", "-S", "-X", "utf8", self.app / "jarvo" / "manimgx.py"], \
                "jarvo/manimgx.py (bin-floty bez programu manimgx)"
        kod, out = self.uruchom("manimgx", [*argv, "--jarvo-stan"], czas=120)
        musi(kod == 0, f"manimgx --jarvo-stan: kod {kod}: {out[-400:]}")
        przed = json_z(out)
        pytanie = ""
        if not przed.get("gotowy"):                       # pierwsze użycie: najpierw zgoda, potem pobranie
            musi(przed.get("przy_uzyciu"), f"manimgx przed instalacją bez opisu pobrania: {przed}")
            kod, out = self.uruchom("manimgx", [*argv, "--version"], czas=120)
            musi(kod == 127 and "--jarvo-zainstaluj" in out, f"manimgx --version przed zgodą: kod {kod}: {out[-400:]}")
            kod, stan = self.uruchom("manimgx", [*argv, "--jarvo-stan"], czas=120)
            musi(kod == 0 and not json_z(stan).get("gotowy"), "manimgx --version zainstalował bez zgody")
            kod, out = self.uruchom("manimgx", [*argv, "--jarvo-zainstaluj"], czas=1800)
            musi(kod == 0, f"manimgx --jarvo-zainstaluj: kod {kod}: {out[-600:]}")
            pytanie = "; przed zgodą --version bez pobierania (kod 127 z radą), --jarvo-zainstaluj"
        kod, out = self.uruchom("manimgx", [*argv, "--version"], czas=600)
        musi(kod == 0 and "0.1.1" in out, f"manimgx --version: kod {kod}: {out[-600:]}")
        katalog = self.wyniki / "manimgx"
        katalog.mkdir(exist_ok=True)
        (katalog / "scena.py").write_text(SCENA, encoding="utf-8")
        mp4 = katalog / "out" / "proba.mp4"
        kod, out = self.uruchom("manimgx", [*argv, "render", "scena.py", "Proba", "-r", "640x360", "--fps", "30", "-o",
                                            "out/proba.mp4"], czas=900, cwd=katalog)
        musi(kod == 0 and mp4.is_file() and mp4.stat().st_size > 1000, f"manimgx render: kod {kod}: {out[-600:]}")
        musi((katalog / "out" / "proba.storyboard.png").is_file(), "brak storyboardu")
        cache = self.u.jarvo_dane / "cache" / "manimgx"
        musi(cache.is_dir(), f"brak MANIMGX_CACHE_DIR {cache}")
        czas = re.search(r"rendered in ([\d.]+) s", out)
        return (f"ManimGX 0.1.1 ({skad}{pytanie}), scena 1 s 640 × 360 w {czas.group(1) if czas else '?'} s, "
                f"cache w {cache}")

    def doctor(self) -> str:
        kod, out = self.uruchom("doctor", [self.py313, "-I", "-X", "utf8", "-c",
                                           "import json, sys; sys.path.insert(0, sys.argv[1]); from jarvo import android, "
                                           "przy_uzyciu; print(json.dumps(android.sprawdzenia(przy_uzyciu.uklad()), "
                                           "ensure_ascii=False))", self.app], env={**self.baza}, czas=120)
        musi(kod == 0, f"android.sprawdzenia: kod {kod}: {out[-300:]}")
        wyniki = json.loads(out[out.index("["):])
        zle = [w for w in wyniki if w["stan"] == "blad"]
        musi(not zle and {w["nazwa"] for w in wyniki} == {"telefon (adb)", "ekran telefonu"}, f"doctor: {wyniki}")
        return "; ".join(f"{w['nazwa']}: {w['stan']} ({w['opis']})" for w in wyniki)


def do_raportu_e2e(katalog: str | None, punkty: list[dict]) -> None:
    """Punkty w <artefakty>/raport.json testu natywnie_e2e.py (id e11-<punkt>): `podsumowanie` pokazuje je w CI."""
    tu = str(Path(__file__).resolve().parent)
    if tu not in sys.path:
        sys.path.insert(0, tu)
    import natywnie_e2e as e2e
    r = e2e.Raport(e2e.katalog_artefaktow(katalog or None))
    for p in punkty:
        ok = {"ok": True, "uwaga": True, "pominiete": None}.get(p["stan"], False)
        r.punkt(f"e11-{p['nazwa']}", f"E11 {p['nazwa']}", ok, ("uwaga: " if p["stan"] == "uwaga" else "") + p["opis"],
                czas_s=p["czas_s"])


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wyniki", required=True, help="katalog raportu, logów i plików (CI: artefakty)")
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    ap.add_argument("--akceptuje-licencje-sdk", action="store_true",
                    help="właściciel akceptuje licencję Android SDK (platform-tools i adb w scrcpy z dl.google.com)")
    ap.add_argument("--dopusc", default="", help="punkty, których błąd jest tylko uwagą: punkt=powód;…")
    ap.add_argument("--punkty", default=",".join(PUNKTY), help=f"podzbiór z: {', '.join(PUNKTY)}")
    ap.add_argument("--limit", type=float, default=0, help="czas całego testu w sekundach (0 = bez limitu)")
    ap.add_argument("--raport-e2e", nargs="?", const="", default=None, metavar="KATALOG",
                    help="punkty także w <artefakty>/raport.json testu natywnie_e2e.py")
    a = ap.parse_args(argv)
    wybrane = [x.strip() for x in a.punkty.split(",") if x.strip()]
    nieznane = set(wybrane) - set(PUNKTY)
    if nieznane:
        ap.error(f"nieznane punkty: {', '.join(sorted(nieznane))}")
    if a.limit < 0:
        ap.error("--limit: liczba sekund ≥ 0")
    try:
        p = Proba(a)
    except SystemExit as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 2
    funkcje = {"adb": p.adb, "android": p.android_punkt, "scrcpy": p.scrcpy, "przywracanie": p.przywracanie,
               "cad": p.cad, "film": p.film, "manimgx": p.manimgx, "doctor": p.doctor}
    try:
        for nazwa in PUNKTY:
            if nazwa in wybrane:
                p.punkt(nazwa, funkcje[nazwa])
    finally:
        if (p.u.stan / "android.json").is_file():          # telefon testowy zawsze wyłączony na koniec
            p.limit = 0
            p.android("off")
    raport = {"noga": os.environ.get("JARVO_E2E_NOGA") or p.platforma, "korzen": str(p.u.root),
              "app": str(p.app), "platforma": p.platforma, "czas": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "czas_s": round(time.monotonic() - p.start, 1), "limit_s": a.limit or None, "punkty": p.punkty,
              "wynik": "blad" if any(x["stan"] == "blad" for x in p.punkty) else "ok"}
    tekst = json.dumps(raport, ensure_ascii=False, indent=2)
    (p.wyniki / "raport.json").write_text(tekst + "\n", encoding="utf-8")
    if a.raport_e2e is not None:
        do_raportu_e2e(a.raport_e2e, p.punkty)
    print(tekst)
    return 1 if raport["wynik"] == "blad" else 0


if __name__ == "__main__":
    sys.exit(main())

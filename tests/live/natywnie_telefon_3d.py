#!/usr/bin/env python3
"""Telefon, 3D i ManimGX na żywo w instalacji natywnej (docs/NATYWNIE.md etap E11: F08, E11, E13, M04, U04, U05).

    python -X utf8 -B tests/live/natywnie_telefon_3d.py --wyniki <katalog> [--korzen <JARVO_ROOT>]
        [--dopusc "punkt=powód;…"] [--punkty adb,android,scrcpy,cad,film,manimgx,doctor]

Sprawdza zainstalowaną wersję Jarva (kod z `<program>/current.json`), tak jak użyje jej właściciel i flota:
  adb       platform-tools przy pierwszym użyciu (vendor/natywne.yaml, `kiedy: przy-uzyciu`) przez jarvo/android.py
            `on --akceptuje-licencje` (właściciel repo akceptuje licencję Android SDK dla CI), potem `adb version`
            = 37.0.1 z instalacji; Linux arm64: Google nie wydaje platform-tools (pominięte z powodem z manifestu)
  android   `jarvo android status --json` (włączony, lista urządzeń; na runnerze zwykle pusta), `off` (wyłączony,
            serwer adb zatrzymany), urzadzenie.py floty: kod 3 z radą `jarvo android on` przy wyłączonym telefonie
  scrcpy    scrcpy przy pierwszym użyciu, `scrcpy --version` (bez okna); `ekran` bez urządzenia kończy się kodem 1 bez
            okna (tylko gdy adb nie widzi żadnego urządzenia); Linux arm64: pominięte
  cad       `cad.py zainstaluj` (venv cad i Three.js przy pierwszym użyciu), kostka 20 mm z otworem → STEP, STL, GLB,
            raport (20 × 20 × 20 mm, poprawny) i PNG podglądu w chrome-headless-shell z instalacji
  film      `cad.py obrot`: 1 s, 12 kl./s, 360 × 360 → MP4 (ffmpeg z instalacji)
  manimgx   ManimGX przy pierwszym użyciu (program `manimgx` z bin-floty, a bez niego ten sam kod
            jarvo/manimgx.py Pythonem z instalacji), `--version` = 0.1.1 i scena 1 s 640 × 360 z polskim tekstem
            (MP4 i storyboard); render bez GPU na Windows i macOS w CI jest niesprawdzony: `--dopusc manimgx=…`
  doctor    jarvo/android.sprawdzenia (telefon i ekran w `jarvo doctor`): bez błędów
Każdy punkt: ok, blad, uwaga (błąd dopuszczony przez --dopusc) albo pominiete (z powodem). Kod wyjścia 1, gdy któryś
ma stan blad; raport JSON na stdout i w <wyniki>/raport.json, pliki (PNG, MP4, logi poleceń) w <wyniki>. Polecenia
skilli idą w środowisku procesów floty (jarvo/srodowisko.py, Python venvu narzędzi = @@PY@@). Na koniec telefon
testowy wyłączony (`off`), a venvy i narzędzia przy pierwszym użyciu zostają w instalacji (to ich normalny stan).
Sama biblioteka standardowa (dowolny Python 3.11+); okien nie otwiera, sieci używa tylko do pobrań z sumą.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from jarvo import sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PUNKTY = ("adb", "android", "scrcpy", "cad", "film", "manimgx", "doctor")
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
        self.punkty: list[dict] = []
        self.py313 = self._python("python313")

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
        """Polecenie z wyjściem do pliku (serwer adb dziedziczy uchwyty: potok nie dostałby końca), log w wynikach."""
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
        try:
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

    def adb(self) -> str:
        if (powod := self.brak_platformy("platform-tools")) and not shutil.which("adb"):
            raise Pominiete(f"platform-tools na {self.platforma}: {powod}")
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

    def android_punkt(self) -> str:
        if not (self.u.stan / "android.json").is_file():
            raise Pominiete("brak <stan>/android.json (punkt adb pominięty albo nieudany)")
        s = self.stan_androida()
        musi(s["wlaczony"] and s["podglad_hq"].startswith("wyłączony"), f"status po on: {s}")
        urzadzenia = s.get("urzadzenia") or []
        kod, out = self.android("off")
        musi(kod == 0, f"jarvo android off: kod {kod}: {out[-300:]}")
        musi(not self.stan_androida()["wlaczony"], "po off telefon dalej włączony")
        urz = self.u.dane / "profiles" / "jarvo-mobile" / "scripts" / "urzadzenie.py"      # kopia floty
        if not urz.is_file():
            urz = self.app / "profiles" / "jarvo-mobile" / "scripts" / "urzadzenie.py"
        kod, out = self.uruchom("urzadzenie", [self.py_floty(), "-X", "utf8", urz, "status"], czas=120)
        musi(kod == 3 and "jarvo android on" in out, f"urzadzenie.py przy wyłączonym telefonie: kod {kod}: {out[-300:]}")
        return f"on → włączony ({len(urzadzenia)} urządzeń), off → wyłączony, urzadzenie.py: kod 3 z radą"

    def scrcpy(self) -> str:
        if powod := self.brak_platformy("scrcpy"):
            raise Pominiete(f"scrcpy na {self.platforma}: {powod}")
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
        kod, out = self.uruchom("manimgx", [*argv, "--version"], czas=1800)
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
        return f"ManimGX 0.1.1 ({skad}), scena 1 s 640 × 360 w {czas.group(1) if czas else '?'} s, cache w {cache}"

    def doctor(self) -> str:
        kod, out = self.uruchom("doctor", [self.py313, "-I", "-X", "utf8", "-c",
                                           "import json, sys; sys.path.insert(0, sys.argv[1]); from jarvo import android, "
                                           "sciezki; print(json.dumps(android.sprawdzenia(sciezki.uklad()), "
                                           "ensure_ascii=False))", self.app], env={**self.baza}, czas=120)
        musi(kod == 0, f"android.sprawdzenia: kod {kod}: {out[-300:]}")
        wyniki = json.loads(out[out.index("["):])
        zle = [w for w in wyniki if w["stan"] == "blad"]
        musi(not zle and {w["nazwa"] for w in wyniki} == {"telefon (adb)", "ekran telefonu"}, f"doctor: {wyniki}")
        return "; ".join(f"{w['nazwa']}: {w['stan']} ({w['opis']})" for w in wyniki)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wyniki", required=True, help="katalog raportu, logów i plików (CI: artefakty)")
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    ap.add_argument("--dopusc", default="", help="punkty, których błąd jest tylko uwagą: punkt=powód;…")
    ap.add_argument("--punkty", default=",".join(PUNKTY), help=f"podzbiór z: {', '.join(PUNKTY)}")
    a = ap.parse_args(argv)
    p = Proba(a)
    wybrane = [x.strip() for x in a.punkty.split(",") if x.strip()]
    nieznane = set(wybrane) - set(PUNKTY)
    if nieznane:
        ap.error(f"nieznane punkty: {', '.join(sorted(nieznane))}")
    t0 = time.monotonic()
    funkcje = {"adb": p.adb, "android": p.android_punkt, "scrcpy": p.scrcpy, "cad": p.cad, "film": p.film,
               "manimgx": p.manimgx, "doctor": p.doctor}
    try:
        for nazwa in PUNKTY:
            if nazwa in wybrane:
                p.punkt(nazwa, funkcje[nazwa])
    finally:
        if (p.u.stan / "android.json").is_file():          # telefon testowy zawsze wyłączony na koniec
            p.android("off")
    raport = {"noga": os.environ.get("JARVO_E2E_NOGA") or p.platforma, "korzen": str(p.u.root),
              "app": str(p.app), "platforma": p.platforma, "czas": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "czas_s": round(time.monotonic() - t0, 1), "punkty": p.punkty,
              "wynik": "blad" if any(x["stan"] == "blad" for x in p.punkty) else "ok"}
    tekst = json.dumps(raport, ensure_ascii=False, indent=2)
    (p.wyniki / "raport.json").write_text(tekst + "\n", encoding="utf-8")
    print(tekst)
    return 1 if raport["wynik"] == "blad" else 0


if __name__ == "__main__":
    sys.exit(main())

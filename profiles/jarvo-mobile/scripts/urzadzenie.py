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

Urządzenie i adb:
- instalacja natywna (jest `<JARVO_ROOT>/program/current.json`): telefon włącza właściciel poleceniem
  `jarvo android on` (jarvo/android.py: platform-tools przy pierwszym użyciu po akceptacji licencji Google). adb
  z `<stan>/narzedzia.json` (wpis platform-tools; na Linuksie arm64 adb z systemu), stan i urządzenie z
  `<stan>/android.json`; bez wybranego urządzenia bierzemy jedyne gotowe z `adb devices`. `jarvo android off` =
  flota nie używa telefonu (kod 3). Serwer adb startuje z wyjściem do pliku (proces w tle dziedziczy uchwyty, potok by
  nie dostał końca), z ADB_MDNS=0 i kluczem adb właściciela (ADB_VENDOR_KEYS na macOS i Linuksie: terminal agenta ma
  inny HOME, a telefon zna tylko klucz właściciela),
- kontener: `JARVO_ANDROID_ADB` (domyślnie `jarvo-android:5555`, usługa floty `android` w sieci wewnętrznej; włącza
  ją właściciel: `jarvo android on`), adb z obrazu. Port adb nigdy nie wychodzi poza sieć floty.
`JARVO_ADB` i `JARVO_ANDROID_ADB` z otoczenia wygrywają w obu przypadkach.

Testy wrogie (każdy: ustawienie → uruchomienie → zrzut → awarie z bufora `crash` i błędy ReactNativeJS → przywrócenie
ustawień): start, duza-czcionka (font_scale 2.0), maly-ekran (720×1280, 320 dpi), ciemny, offline (tryb samolotowy;
`not_run`, gdy urządzenie nie umie odciąć sieci), uprawnienia (odebrane wszystkie przyznane), wstecz (dwa razy),
smierc-procesu (aplikacja w tle zabita i przywrócona), swieza-instalacja (dane wyczyszczone; nie dla Expo Go).
Wynik: <outdir>/wrogie.json + zrzuty. Kod 1, gdy którykolwiek test ma status `blad`; 3, gdy nie ma urządzenia.
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
from pathlib import Path

SERIAL_KONTENERA = "jarvo-android:5555"                # usługa floty `android` w sieci kontenera
WINDOWS = os.name == "nt"
EXPO_GO = "host.exp.exponent"
CZEKAJ_S = float(os.environ.get("JARVO_ANDROID_CZEKAJ", "6"))
SCENARIUSZE = ["start", "duza-czcionka", "maly-ekran", "ciemny", "offline", "uprawnienia", "wstecz", "smierc-procesu",
               "swieza-instalacja"]
AWARIA_RE = re.compile(r"FATAL EXCEPTION|ANR in|has stopped|przestała działać|Process: \S+, PID|ReactNativeJS.*(Error|Exception)", re.I)


class BrakUrzadzenia(Exception):
    pass


# ------------------------------------------------------------------ instalacja natywna (jarvo android, docs/NATYWNIE.md U04)

WLACZ = ("właściciel włącza go poleceniem `jarvo android on` (telefon z debugowaniem USB albo bezprzewodowym, "
         "emulator z Android Studio; docs/MOBILE.md §5)")


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
    """`<stan>/android.json` z `jarvo android on|off`: wlaczony, serial, wifi."""
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


def env_adb(korzen: Path) -> dict:
    """Otoczenie adb instalacji natywnej: zmienne z wpisu platform-tools (ADB_MDNS=0) i klucz adb właściciela."""
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (_platform_tools(korzen).get("env") or {}).items()})
    env.setdefault("ADB_MDNS", "0")
    klucz = klucz_wlasciciela()
    if klucz is not None and klucz.is_file():
        obecne = [x for x in env.get("ADB_VENDOR_KEYS", "").split(os.pathsep) if x]
        env["ADB_VENDOR_KEYS"] = os.pathsep.join(dict.fromkeys([*obecne, str(klucz)]))
    return env


class Adb:
    """Cienka warstwa nad adb (podmieniana w testach). Bez argumentów: urządzenie i adb z otoczenia, instalacji
    natywnej (jarvo android) albo kontenera (jarvo-android:5555, adb z obrazu)."""

    def __init__(self, serial: str | None = None, adb: str | None = None):
        self.korzen = korzen_natywny() if serial is None or adb is None else None
        natywny = (stan_natywny(self.korzen).get("serial") or None) if self.korzen else None
        self.serial = serial or os.environ.get("JARVO_ANDROID_ADB") or natywny or (
            None if self.korzen else SERIAL_KONTENERA)
        self.adb = adb or os.environ.get("JARVO_ADB") or (adb_natywny(self.korzen) if self.korzen else None) or "adb"
        self.env = env_adb(self.korzen) if self.korzen else None

    def run(self, *args: str, timeout: int = 60, binarnie: bool = False):
        r = subprocess.run([self.adb, "-s", self.serial, *args], capture_output=True, timeout=timeout, env=self.env)
        if r.returncode != 0 and not binarnie:
            raise RuntimeError(f"adb {' '.join(args)}: {r.stderr.decode(errors='replace').strip()[:300]}")
        return r.stdout if binarnie else r.stdout.decode(errors="replace")

    def sh(self, polecenie: str, timeout: int = 60) -> str:
        return self.run("shell", polecenie, timeout=timeout)

    def _serwer(self) -> None:
        """Serwer adb (instalacja natywna): start z wyjściem do pliku, bo proces w tle dziedziczy uchwyty polecenia,
        a potok nie dostałby końca (Windows); potem odnowienie połączenia Wi-Fi z `jarvo android on --wifi`."""
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
            subprocess.run([self.adb, "connect", wifi], capture_output=True, timeout=20, env=self.env)

    def _jedyne(self) -> str:
        """Jedyne gotowe urządzenie z `adb devices` (instalacja natywna bez wybranego urządzenia)."""
        r = subprocess.run([self.adb, "devices"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=20, env=self.env)
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
            subprocess.run([self.adb, "connect", self.serial], capture_output=True, timeout=20, env=self.env)
        stan = subprocess.run([self.adb, "-s", self.serial, "get-state"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=20, env=self.env)
        if stan.stdout.strip() != "device":
            if self.korzen is not None:
                raise BrakUrzadzenia(f"urządzenie {self.serial} niedostępne ({(stan.stderr or stan.stdout).strip()[:200]}); "
                                     f"{WLACZ}")
            raise BrakUrzadzenia(f"urządzenie {self.serial} niedostępne ({(stan.stderr or stan.stdout).strip()[:200]}); "
                                 "właściciel włącza je poleceniem `jarvo android on` (emulator przy KVM albo Redroid przy binderze, docs/MOBILE.md §5)")


def status(adb: Adb) -> dict:
    adb.polacz()
    rozm = adb.sh("wm size").strip().split()[-1]
    return {"serial": adb.serial, "android": adb.sh("getprop ro.build.version.release").strip(),
            "sdk": adb.sh("getprop ro.build.version.sdk").strip(), "model": adb.sh("getprop ro.product.model").strip(),
            "ekran": rozm, "gestosc": adb.sh("wm density").strip().split()[-1],
            "expo_go": EXPO_GO in adb.sh(f"pm list packages {EXPO_GO}")}


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
    try:
        adb.sh("uiautomator dump /sdcard/jarvo-ui.xml", timeout=30)
        xml = adb.sh("cat /sdcard/jarvo-ui.xml")
    except RuntimeError:
        return []
    return [t for t in re.findall(r'text="([^"]+)"', xml) if t.strip()]


def awarie(adb: Adb) -> list[str]:
    linie = adb.sh("logcat -d -b crash -b main -v brief *:E", timeout=30).splitlines()
    return [l[:240] for l in linie if AWARIA_RE.search(l)][:8]


def zrzut(adb: Adb, plik: Path) -> Path:
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_bytes(adb.run("exec-out", "screencap", "-p", binarnie=True, timeout=30))
    return plik


def _przyznane(adb: Adb, pakiet: str) -> list[str]:
    out = adb.sh(f"dumpsys package {pakiet}")
    return sorted(set(re.findall(r"(android\.permission\.[A-Z_]+): granted=true", out)))


def _ma_siec(adb: Adb) -> bool:
    try:
        return bool(re.search(r"\b1 (?:packets )?received", adb.sh("ping -c 1 -W 2 1.1.1.1", timeout=10)))
    except RuntimeError:                 # ping bez odpowiedzi kończy się kodem ≠ 0
        return False


def scenariusz(adb: Adb, id_: str, cel: str, outdir: Path) -> dict:
    expo_go = cel.startswith(("exp://", "exps://"))
    pakiet = EXPO_GO if expo_go else cel
    r = {"id": id_, "warstwa": "android", "status": "ok", "obserwacje": {}, "dlaczego": "", "zrzuty": []}
    przywroc: list[str] = []

    def uruchom_i_patrz(etykieta: str) -> None:
        otworz(adb, cel)
        time.sleep(CZEKAJ_S)
        r["zrzuty"].append(str(zrzut(adb, outdir / f"{id_}-{etykieta}.png")))

    try:
        adb.sh("logcat -c")
        if id_ == "start":
            uruchom_i_patrz("ekran")
        elif id_ == "duza-czcionka":
            adb.sh("settings put system font_scale 2.0")
            przywroc.append("settings put system font_scale 1.0")
            adb.sh(f"am force-stop {pakiet}")
            uruchom_i_patrz("ekran")
        elif id_ == "maly-ekran":
            adb.sh("wm size 720x1280")
            adb.sh("wm density 320")
            przywroc += ["wm size reset", "wm density reset"]
            adb.sh(f"am force-stop {pakiet}")
            uruchom_i_patrz("ekran")
        elif id_ == "ciemny":
            adb.sh("cmd uimode night yes")
            przywroc.append("cmd uimode night no")
            uruchom_i_patrz("ekran")
        elif id_ == "offline":
            adb.sh("cmd connectivity airplane-mode enable")
            adb.sh("svc wifi disable")
            adb.sh("svc data disable")
            przywroc += ["cmd connectivity airplane-mode disable", "svc wifi enable", "svc data enable"]
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
            perms = _przyznane(adb, pakiet)
            for p in perms:
                adb.sh(f"pm revoke {pakiet} {p}")
            r["obserwacje"]["odebrane"] = perms
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
            adb.sh(f"pm clear {pakiet}")
            uruchom_i_patrz("ekran")
        bledy = awarie(adb)
        tekst = tekst_ekranu(adb) if id_ not in ("wstecz",) else ["-"]
        r["obserwacje"].update(awarie=bledy, tekst_na_ekranie=len(tekst), na_wierzchu=na_wierzchu(adb))
        if bledy:
            r.update(status="blad", dlaczego="awaria aplikacji (log crash / ReactNativeJS)")
        elif not tekst and id_ != "wstecz":
            r.update(status="blad", dlaczego="pusty ekran (brak tekstu w hierarchii widoku)")
    except RuntimeError as e:
        r.update(status="blad", dlaczego=f"adb: {e}")
    finally:
        for p in przywroc:
            try:
                adb.sh(p)
            except RuntimeError:
                pass
    return r


def wrogie(adb: Adb, cel: str, outdir: Path, tylko: list[str] | None = None) -> dict:
    adb.polacz()
    outdir.mkdir(parents=True, exist_ok=True)
    info = status(adb)
    if cel.startswith(("exp://", "exps://")) and not info["expo_go"]:
        raise BrakUrzadzenia("na urządzeniu nie ma Expo Go (zainstaluj: `npx expo start --android` w katalogu aplikacji)")
    wyniki = [scenariusz(adb, s, cel, outdir) for s in (tylko or SCENARIUSZE) if s in SCENARIUSZE]
    licz = lambda s: sum(1 for w in wyniki if w["status"] == s)  # noqa: E731
    raport = {"urzadzenie": info, "cel": cel, "wyniki": wyniki,
              "podsumowanie": f"android {info['android']}: {licz('ok')} ok, {licz('blad')} błędów, {licz('not_run')} bez pomiaru"}
    (outdir / "wrogie.json").write_text(json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
    return raport


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
    args = ap.parse_args(argv)
    adb = Adb()
    try:
        if args.cmd == "status":
            info = status(adb)
            print(json.dumps(info, ensure_ascii=False, indent=2) if args.json else
                  f"✓ {info['serial']}: Android {info['android']} (SDK {info['sdk']}), {info['model']}, {info['ekran']} "
                  f"@{info['gestosc']} dpi, Expo Go: {'tak' if info['expo_go'] else 'nie'}")
            return 0
        adb.polacz()
        if args.cmd == "zainstaluj":
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
            return 1 if any(x["status"] == "blad" for x in r["wyniki"]) else 0
        return 0
    except BrakUrzadzenia as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

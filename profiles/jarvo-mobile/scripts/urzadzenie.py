#!/usr/bin/env python3
"""Telefon testowy z Androidem przez adb (warstwa 2 bramki aplikacji): instalacja, zrzuty, logi i testy wrogie na
prawdziwym systemie Android (emulator Google albo Redroid w usłudze floty, albo telefon podłączony przez adb).

    urzadzenie.py status [--json]                        # czy jest urządzenie, wersja Androida, ekran
    urzadzenie.py zainstaluj <plik.apk>
    urzadzenie.py otworz <pakiet | exp://…>               # aplikacja albo podgląd w Expo Go
    urzadzenie.py zrzut <plik.png>
    urzadzenie.py logi [--pakiet p] [--linie 200]
    urzadzenie.py wrogie <pakiet | exp://…> <outdir> [--tylko duza-czcionka,ciemny,…]

Urządzenie: `JARVO_ANDROID_ADB` (domyślnie `jarvo-android:5555`, usługa floty `android` w sieci wewnętrznej; włącza ją
właściciel: `jarvo android on`). Port adb nigdy nie wychodzi poza sieć floty.

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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ADB = os.environ.get("JARVO_ADB", "adb")
SERIAL = os.environ.get("JARVO_ANDROID_ADB", "jarvo-android:5555")
EXPO_GO = "host.exp.exponent"
CZEKAJ_S = float(os.environ.get("JARVO_ANDROID_CZEKAJ", "6"))
SCENARIUSZE = ["start", "duza-czcionka", "maly-ekran", "ciemny", "offline", "uprawnienia", "wstecz", "smierc-procesu",
               "swieza-instalacja"]
AWARIA_RE = re.compile(r"FATAL EXCEPTION|ANR in|has stopped|przestała działać|Process: \S+, PID|ReactNativeJS.*(Error|Exception)", re.I)


class BrakUrzadzenia(Exception):
    pass


class Adb:
    """Cienka warstwa nad adb (podmieniana w testach)."""

    def __init__(self, serial: str = SERIAL, adb: str = ADB):
        self.serial, self.adb = serial, adb

    def run(self, *args: str, timeout: int = 60, binarnie: bool = False):
        r = subprocess.run([self.adb, "-s", self.serial, *args], capture_output=True, timeout=timeout)
        if r.returncode != 0 and not binarnie:
            raise RuntimeError(f"adb {' '.join(args)}: {r.stderr.decode(errors='replace').strip()[:300]}")
        return r.stdout if binarnie else r.stdout.decode(errors="replace")

    def sh(self, polecenie: str, timeout: int = 60) -> str:
        return self.run("shell", polecenie, timeout=timeout)

    def polacz(self) -> None:
        if not shutil.which(self.adb) and not Path(self.adb).exists():
            raise BrakUrzadzenia("brak adb w obrazie floty (pakiet adb; obraz sprzed wersji z usługą android: `jarvo update`)")
        if ":" in self.serial:
            subprocess.run([self.adb, "connect", self.serial], capture_output=True, timeout=20)
        stan = subprocess.run([self.adb, "-s", self.serial, "get-state"], capture_output=True, text=True, timeout=20)
        if stan.stdout.strip() != "device":
            raise BrakUrzadzenia(f"urządzenie {self.serial} niedostępne ({(stan.stderr or stan.stdout).strip()[:200]}); "
                                 "właściciel włącza je poleceniem `jarvo android on` (wymaga KVM albo modułu binder_linux)")


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
            print(zrzut(adb, Path(args.plik)))
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

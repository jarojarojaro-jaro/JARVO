#!/usr/bin/env python3
"""Paczka npm przed `npx expo install`: czy to ta, o którą chodzi, i czy można jej zaufać w aplikacji ze sklepu.

    paczki.py sprawdz <app> <paczka> [<paczka> …] [--bez-sieci]   # przed instalacją każdej nowej paczki
    paczki.py zaleznosci <app> [--bez-sieci]                     # wszystkie zależności z package.json

Zaufane bez pytania rejestru: paczki z listy Expo SDK (`node_modules/expo/bundledNativeModules.json`, wersje dobiera
`expo install`), z szablonu JARVO i moduły profilu zgodności (`zgodnosc.py`). Każda inna:
- nazwa o jedną edycję od zaufanej albo popularnej (`expo-notifcations`) albo nazwa zakresu bez zakresu
  (`react-native-async-storage` zamiast `@react-native-async-storage/async-storage`): literówka albo podszycie → ✗,
- nie istnieje w rejestrze npm (nazwa zmyślona, którą ktoś może zarejestrować: slopsquatting) → ✗,
- młodsza niż 90 dni i poniżej 1000 pobrań tygodniowo → ✗ (wydmuszki, świeże przejęcia),
- skrypty instalacyjne (preinstall, install, postinstall) przy mniej niż 10 000 pobrań tygodniowo → ✗, przy
  popularnej ⚠; przestarzała (deprecated) → ⚠ z komunikatem autora,
- spoza listy Expo → ⚠: czy działa w Expo Go i na nowej architekturze, sprawdź w React Native Directory.
Rejestr nie odpowiada → „?” (nigdy „czysto”). Kod: 0 = można instalować, 1 = ✗ albo „?”, 2 = złe wejście.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402
import zgodnosc  # noqa: E402

SZABLON = TU.parent / "templates" / "expo-jarvo"
NAZWA_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$")
SKRYPTY = ("preinstall", "install", "postinstall")
# Popularne w aplikacjach React Native i Expo (poza listą Expo SDK): wzorce do wykrywania literówek i podszyć.
POPULARNE = """react react-dom react-native react-native-web expo expo-router @expo/vector-icons @react-navigation/native
@react-navigation/bottom-tabs @react-navigation/native-stack @react-navigation/stack @react-navigation/drawer
@react-native-async-storage/async-storage react-native-reanimated react-native-gesture-handler react-native-screens
react-native-safe-area-context react-native-svg react-native-webview react-native-maps react-native-mmkv
@shopify/flash-list lottie-react-native react-native-qrcode-svg @supabase/supabase-js firebase @react-native-firebase/app
@react-native-firebase/messaging zustand @tanstack/react-query axios date-fns dayjs zod i18next react-i18next nativewind
tailwindcss react-native-paper @gorhom/bottom-sheet react-native-vision-camera @stripe/stripe-react-native
react-native-purchases react-native-iap @sentry/react-native posthog-react-native react-hook-form lodash uuid
react-native-uuid expo-notifications expo-camera expo-location expo-image-picker expo-calendar expo-contacts
expo-file-system expo-secure-store expo-sqlite expo-video expo-audio expo-image expo-haptics expo-linking expo-constants
expo-updates expo-auth-session expo-apple-authentication expo-local-authentication expo-sharing expo-clipboard
expo-font expo-splash-screen expo-status-bar expo-system-ui expo-web-browser expo-localization expo-device
expo-application expo-blur expo-linear-gradient expo-sensors expo-media-library expo-document-picker expo-print
expo-mail-composer expo-sms expo-store-review expo-tracking-transparency expo-crypto expo-network expo-keep-awake
expo-task-manager expo-background-task expo-dev-client expo-symbols expo-glass-effect expo-maps""".split()


def odleglosc1(a: str, b: str) -> bool:
    """Czy nazwy różnią się dokładnie jedną edycją (wstawienie, usunięcie, zamiana, przestawienie sąsiadów)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        rozne = [i for i in range(len(a)) if a[i] != b[i]]
        return len(rozne) == 1 or (len(rozne) == 2 and rozne[1] == rozne[0] + 1 and a[rozne[0]] == b[rozne[1]]
                                   and a[rozne[1]] == b[rozne[0]])
    krotsza, dluzsza = sorted((a, b), key=len)
    return any(dluzsza[:i] + dluzsza[i + 1:] == krotsza for i in range(len(dluzsza)))


def nazwa_paczki(spec: str) -> str:
    """`expo-camera@~17.0.0` → `expo-camera`, `@scope/x@1` → `@scope/x`."""
    spec = spec.strip()
    i = spec.find("@", 1)
    return (spec[:i] if i > 0 else spec).lower()


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def zaufane(kat: Path | None = None) -> set[str]:
    """Lista Expo SDK z node_modules aplikacji (gdy jest), zależności szablonu JARVO i moduły profilu zgodności."""
    pkg = _json(SZABLON / "package.json")
    z = set(pkg.get("dependencies") or {}) | set(pkg.get("devDependencies") or {})
    z |= {m["modul"] for m in zgodnosc.UPRAWNIENIA.values() if m.get("modul")} | {"expo-apple-authentication"}
    if kat is not None:
        z |= set(_json(kat / "node_modules" / "expo" / "bundledNativeModules.json"))
    return z


def podszycie(nazwa: str, wzorce: set[str]) -> str | None:
    """Zaufana albo popularna nazwa, pod którą `nazwa` się podszywa (None = brak podobieństwa)."""
    if nazwa in wzorce:
        return None
    for w in sorted(wzorce):
        if odleglosc1(nazwa, w):
            return w
        if w.startswith("@") and "/" in w and not nazwa.startswith("@"):
            zakres, czesc = w[1:].split("/", 1)
            if nazwa in (zakres, f"{zakres}-{czesc}") and nazwa != czesc:
                return w
    return None


def rejestr(nazwa: str) -> dict:
    """{istnieje, pobrania, utworzony, skrypty, przestarzala, wersja}; istnieje=None, gdy rejestr nie odpowiedział."""
    q = urllib.parse.quote(nazwa, safe="@")
    try:
        dl = ml.json_z(f"https://api.npmjs.org/downloads/point/last-week/{nazwa}", pamiec_h=24)
        pobrania = dl.get("downloads") if isinstance(dl, dict) else None
        odp = ml.pobierz(f"https://registry.npmjs.org/{q}/latest", pamiec_h=6, naglowki={"Accept": "application/json"})
        if odp.kod == 404:
            return {"istnieje": False}
        if odp.kod != 200:
            return {"istnieje": None, "blad": f"HTTP {odp.kod}"}
        m = json.loads(odp.tresc)
        utworzony = None
        if pobrania is None or pobrania < 10_000:
            doc = ml.json_z(f"https://registry.npmjs.org/{q}", pamiec_h=24, naglowki={"Accept": "application/json"})
            utworzony = ((doc or {}).get("time") or {}).get("created") if isinstance(doc, dict) else None
    except (ConnectionError, ml.Blokada, ValueError) as e:
        return {"istnieje": None, "blad": str(e)[:200]}
    rownolegle = set(m.get("peerDependencies") or {})
    return {"istnieje": True, "pobrania": pobrania, "utworzony": utworzony, "wersja": m.get("version"),
            "natywna": bool(rownolegle & {"react-native", "expo"}),
            "skrypty": sorted(k for k in SKRYPTY if k in (m.get("scripts") or {})),
            "przestarzala": m.get("deprecated") or None}


def ocen(nazwa: str, kat: Path | None = None, siec: bool = True, dzis: dt.date | None = None) -> dict:
    """Werdykt dla jednej paczki: {paczka, wynik: ok|ostrz|blad|?, powody[]}."""
    nazwa = nazwa_paczki(nazwa)
    if not NAZWA_RE.match(nazwa):
        return {"paczka": nazwa, "wynik": "blad", "powody": ["to nie jest nazwa paczki npm"]}
    z = zaufane(kat)
    if nazwa in z:
        return {"paczka": nazwa, "wynik": "ok", "powody": ["lista Expo SDK albo szablon JARVO: `npx expo install` dobierze wersję"]}
    wzor = podszycie(nazwa, z | set(POPULARNE))
    if wzor:
        return {"paczka": nazwa, "wynik": "blad",
                "powody": [f"nazwa prawie jak {wzor}: literówka albo podszycie; chodziło o {wzor}?"]}
    if not siec:
        if nazwa in POPULARNE:
            return {"paczka": nazwa, "wynik": "ostrz", "powody": ["popularna, spoza listy Expo SDK; rejestru nie sprawdzono (--bez-sieci)"]}
        return {"paczka": nazwa, "wynik": "?", "powody": ["spoza listy Expo SDK, rejestru npm nie sprawdzono (--bez-sieci)"]}
    r = rejestr(nazwa)
    if r["istnieje"] is None:
        return {"paczka": nazwa, "wynik": "?", "powody": [f"rejestr npm nie odpowiedział ({r.get('blad', '?')}): nie oceniono"]}
    if r["istnieje"] is False:
        return {"paczka": nazwa, "wynik": "blad",
                "powody": ["nie ma jej w rejestrze npm: nazwa zmyślona? Ktoś może ją zarejestrować ze złośliwym kodem"]}
    pobrania, wiek = r.get("pobrania"), None
    if r.get("utworzony"):
        try:
            wiek = ((dzis or ml.DZIS) - dt.date.fromisoformat(r["utworzony"][:10])).days
        except ValueError:
            pass
    pob = f"{pobrania:,}".replace(",", " ") if isinstance(pobrania, int) else "?"
    if r.get("natywna"):
        wynik, powody = "ostrz", ["moduł React Native spoza listy Expo SDK: w React Native Directory sprawdź Expo Go i nową architekturę"]
    elif (pobrania or 0) >= 10_000:
        wynik, powody = "ok", [f"biblioteka JS, {pob} pobrań/tydz."]
    else:
        wynik, powody = "ostrz", [f"mało znana biblioteka JS ({pob} pobrań/tydz.): przejrzyj repozytorium i autora"]
    if wiek is not None and wiek < 90 and (pobrania is None or pobrania < 1000):
        wynik = "blad"
        powody.insert(0, f"nowa ({wiek} dni) i mało używana ({pob} pobrań/tydz.): nie do aplikacji w sklepie")
    if r.get("skrypty"):
        if pobrania is None or pobrania < 10_000:
            wynik = "blad"
            powody.insert(0, f"uruchamia skrypty przy instalacji ({', '.join(r['skrypty'])}) przy {pob} pobrań/tydz.")
        else:
            wynik = "ostrz" if wynik == "ok" else wynik
            powody.append(f"skrypty przy instalacji ({', '.join(r['skrypty'])}): popularna, ale przejrzyj, co robią")
    if r.get("przestarzala"):
        wynik = "ostrz" if wynik == "ok" else wynik
        powody.append(f"przestarzała: {str(r['przestarzala'])[:160]}")
    return {"paczka": nazwa, "wynik": wynik, "powody": powody, "wersja": r.get("wersja"), "pobrania": pobrania, "wiek_dni": wiek}


def zaleznosci(kat: Path, siec: bool = True) -> list[dict]:
    pkg = _json(kat / "package.json")
    nazwy = list(dict.fromkeys([*(pkg.get("dependencies") or {}), *(pkg.get("devDependencies") or {})]))
    return [ocen(n, kat, siec) for n in nazwy]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sprawdz")
    s.add_argument("app")
    s.add_argument("paczki", nargs="+")
    s.add_argument("--bez-sieci", action="store_true")
    z = sub.add_parser("zaleznosci")
    z.add_argument("app")
    z.add_argument("--bez-sieci", action="store_true")
    a = ap.parse_args(argv)
    kat = Path(a.app).resolve()
    if not (kat / "package.json").exists():
        print(f"✗ {kat}: brak package.json (to nie katalog aplikacji)", file=sys.stderr)
        return 2
    wyniki = [ocen(p, kat, not a.bez_sieci) for p in a.paczki] if a.cmd == "sprawdz" else zaleznosci(kat, not a.bez_sieci)
    znak = {"ok": "✓", "ostrz": "⚠", "blad": "✗", "?": "?"}
    for w in wyniki:
        if a.cmd == "zaleznosci" and w["wynik"] == "ok":
            continue
        print(f"{znak[w['wynik']]} {w['paczka']}: " + "; ".join(w["powody"]))
    zle = [w["paczka"] for w in wyniki if w["wynik"] in ("blad", "?")]
    print(f"{len(wyniki) - len(zle)}/{len(wyniki)} paczek do zaakceptowania" + (f"; nie instaluj: {', '.join(zle)}" if zle else ""))
    return 1 if zle else 0


if __name__ == "__main__":
    sys.exit(main())

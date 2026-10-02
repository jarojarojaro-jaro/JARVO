#!/usr/bin/env python3
"""Utrzymanie aplikacji po wydaniu: stan (SDK, terminy, wersja w sklepie, opinie), kalendarz terminów sklepów,
poprawka przez EAS Update (A2) i plan podniesienia Expo SDK.

    utrzymanie.py stan <app> [--bez-sieci]                     # out/utrzymanie/STAN.md
    utrzymanie.py kalendarz <app> [--lata 2]                   # out/utrzymanie/KALENDARZ.md + terminy.ics
    utrzymanie.py aktualizacja <app> --wiadomosc "…" --zgoda "…" [--kanal production]    # A2: poprawka bez recenzji
    utrzymanie.py sdk <app>                                    # out/utrzymanie/SDK.md: plan podniesienia wersji

`aktualizacja` publikuje przez EAS Update tylko poprawkę JS do buildu, który już jest w sklepie (Apple 2.5.2, Google:
nadużycia urządzeń): odcisk kodu natywnego (`expo-updates runtimeversion:resolve`) musi być równy runtime ostatniego
buildu sklepowego z `out/wydanie/buildy.json`, inaczej aktualizacja nie trafiłaby do nikogo albo udawała nową funkcję;
wtedy nowa wersja przez `wydanie`. Do tego `aplikacja.py sprawdz` bez błędów, zero JARVO-TODO, konkretny opis zmiany
i dosłowne słowa zgody właściciela (`out/wydanie/zgody.json`); Hermes i tak pyta o polecenie (approvals).

Terminy w kalendarzu: docelowe API Google (31 sierpnia każdego roku), wymagany Xcode u Apple (kwiecień), strony
pamięci 16 KB (1.02.2027), wsparcie Expo SDK (około 3 wersje rocznie), przegląd polityki prywatności. Lata bez
ogłoszenia mają dopisek „(prognoza)”. Kod: 0 = OK, 1 = bramka albo błąd, 2 = złe wejście, 3 = brak tokenu.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402
import wydanie  # noqa: E402

TARGET_SDK_2026 = 36          # Google: od 31.08.2026 (przedłużenie do 1.11.2026) nowe aplikacje i aktualizacje celują w API 36
XCODE_2026 = 26               # Apple: od 28.04.2026 wysyłka tylko z Xcode 26 (iOS 26 SDK)
OGOLNIKI = re.compile(r"^(poprawki|fix(es)?|bug ?fix(es)?|drobne zmiany|update|aktualizacja|ulepszenia)\.?$", re.I)


def _app(kat: Path) -> dict:
    return wydanie._app(kat)


def _wersja_pakietu(kat: Path, nazwa: str) -> str:
    p = kat / "node_modules" / nazwa / "package.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("version", "")
    pkg = ml.czytaj_json(kat / "package.json")
    return re.sub(r"^[~^]", "", (pkg.get("dependencies") or {}).get(nazwa, ""))


def sdk_z_npm() -> dict:
    r = subprocess.run(["npm", "view", "expo", "dist-tags", "--json"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ConnectionError(f"npm view expo: {r.stderr.strip()[-300:]}")
    tagi = json.loads(r.stdout)
    sdk = sorted((int(k[4:]), v) for k, v in tagi.items() if re.fullmatch(r"sdk-\d+", k))
    return {"latest": tagi.get("latest"), "next": tagi.get("next"), "sdk": [n for n, _ in sdk]}


def runtime(kat: Path, platforma: str) -> str | None:
    r = subprocess.run(["npx", "expo-updates", "runtimeversion:resolve", "--platform", platforma], cwd=kat,
                       capture_output=True, text=True, timeout=300, env={**os.environ, "CI": "1"})
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout[r.stdout.find("{"):]).get("runtimeVersion")
    except ValueError:
        return None


def terminy(dzis: dt.date, lata: int = 2, sdk_aplikacji: int | None = None, sdk_najnowszy: int | None = None) -> list[dict]:
    t = []
    for rok in range(dzis.year, dzis.year + lata + 1):
        api = TARGET_SDK_2026 + (rok - 2026)
        prog = "" if rok <= 2026 else " (prognoza: co rok o jedno API wyżej)"
        t.append({"data": dt.date(rok, 8, 31), "sklep": "Google Play",
                  "co": f"nowe aplikacje i aktualizacje muszą celować w API {api}{prog}",
                  "zrobic": "aktualny Expo SDK (targetSdk rośnie z React Native), nowy build przed terminem"})
        t.append({"data": dt.date(rok, 11, 1), "sklep": "Google Play",
                  "co": f"koniec przedłużenia (o które trzeba poprosić w Play Console) dla API {api}{prog}",
                  "zrobic": "po tej dacie aktualizacja z niższym targetSdk nie przejdzie"})
        xcode = XCODE_2026 + (rok - 2026)
        t.append({"data": dt.date(rok, 4, 28), "sklep": "App Store",
                  "co": f"wysyłka tylko z Xcode {xcode}{'' if rok <= 2026 else ' (prognoza: co rok nowy Xcode w kwietniu)'}",
                  "zrobic": "EAS buduje na aktualnym obrazie; sprawdź, że SDK go wspiera"})
        t.append({"data": dt.date(rok, 9, 1), "sklep": "właściciel",
                  "co": "przegląd polityki prywatności i formularzy prywatności (etykieta Apple, Data safety)",
                  "zrobic": "porównaj z bibliotekami aplikacji (`sklep_check.py`, punkt 17)"})
    t.append({"data": dt.date(2027, 2, 1), "sklep": "Google Play",
              "co": "bez wyrównania bibliotek natywnych do 16 KB żadna aktualizacja nie wyjdzie",
              "zrobic": "punkt 7 listy kontrolnej na AAB"})
    if sdk_aplikacji and sdk_najnowszy and sdk_najnowszy - sdk_aplikacji >= 2:
        t.append({"data": dzis + dt.timedelta(days=30), "sklep": "Expo",
                  "co": f"aplikacja na SDK {sdk_aplikacji}, najnowszy {sdk_najnowszy}: wsparcie poprawek dla starszych wersji wygasa",
                  "zrobic": "`utrzymanie.py sdk` i podniesienie w osobnej gałęzi"})
    return sorted([x for x in t if x["data"] >= dzis], key=lambda x: x["data"])


def ics(t: list[dict], nazwa: str) -> str:
    teraz = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    l = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jarvo//jarvo-mobile//PL", "CALSCALE:GREGORIAN"]
    for i, x in enumerate(t):
        d = x["data"].strftime("%Y%m%d")
        nast = (x["data"] + dt.timedelta(days=1)).strftime("%Y%m%d")
        opis = (x["co"] + " — " + x["zrobic"]).replace(",", "\\,").replace(";", "\\;")
        l += ["BEGIN:VEVENT", f"UID:jarvo-{re.sub(r'[^a-z0-9]', '', nazwa.lower())}-{d}-{i}@jarvo", f"DTSTAMP:{teraz}",
              f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nast}",
              f"SUMMARY:{nazwa}: {x['sklep']}".replace(",", "\\,"), f"DESCRIPTION:{opis}",
              "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P30D", f"DESCRIPTION:Za 30 dni: {x['sklep']}", "END:VALARM",
              "END:VEVENT"]
    l.append("END:VCALENDAR")
    return "\r\n".join(l) + "\r\n"


def kalendarz(kat: Path, lata: int = 2, sdk_info: dict | None = None) -> dict:
    app = _app(kat)
    sdk_app = int((_wersja_pakietu(kat, "expo") or "0").split(".")[0] or 0) or None
    najn = max(sdk_info["sdk"]) if sdk_info and sdk_info.get("sdk") else None
    t = terminy(ml.DZIS, lata, sdk_app, najn)
    out = wydanie._wyd(kat).parent / "utrzymanie"
    md = [f"# Kalendarz terminów: {app.get('nazwa')}", "", "| Data | Sklep | Co | Co zrobić |", "|---|---|---|---|"]
    md += [f"| {x['data'].isoformat()} | {x['sklep']} | {x['co']} | {x['zrobic']} |" for x in t]
    md += ["", "`terminy.ics` importuje się do kalendarza telefonu (przypomnienie 30 dni wcześniej)."]
    ml.zapisz(out / "KALENDARZ.md", "\n".join(md) + "\n")
    (out / "terminy.ics").write_text(ics(t, app.get("nazwa", "aplikacja")), encoding="utf-8")
    return {"terminy": [{**x, "data": x["data"].isoformat()} for x in t], "pliki": ["out/utrzymanie/KALENDARZ.md", "out/utrzymanie/terminy.ics"]}


def stan(kat: Path, siec: bool = True) -> dict:
    app = _app(kat)
    wynik = {"wersja": app.get("wersja"), "expo": _wersja_pakietu(kat, "expo"), "react_native": _wersja_pakietu(kat, "react-native")}
    if siec:
        try:
            wynik["sdk_npm"] = sdk_z_npm()
        except (ConnectionError, OSError, ValueError, subprocess.TimeoutExpired) as e:
            wynik["sdk_npm"] = {"blad": str(e)}
        try:
            import audyt_mobilny as am
            sklep = am.ios_lookup(app["bundle_ios"]) if app.get("bundle_ios") else []
            if sklep:
                s = sklep[0]
                wynik["app_store"] = {"wersja": s.get("version"), "wydana": (s.get("currentVersionReleaseDate") or "")[:10],
                                      "ocena": s.get("averageUserRatingForCurrentVersion") or s.get("averageUserRating"),
                                      "ocen": s.get("userRatingCountForCurrentVersion") or s.get("userRatingCount")}
                wynik["opinie"] = am.ios_opinie(str(s.get("trackId")), 50)
            else:
                wynik["app_store"] = None
        except (ConnectionError, ml.Blokada) as e:
            wynik["app_store"] = {"blad": str(e)}
    buildy = [b for b in ml.czytaj_json(kat / "out" / "wydanie" / "buildy.json").get("buildy", []) if b.get("status") == "FINISHED"]
    wynik["buildy"] = [{k: b.get(k) for k in ("platforma", "wersja", "numer", "runtime")} for b in buildy[:4]]
    wynik["kalendarz"] = kalendarz(kat, 1, wynik.get("sdk_npm") if isinstance(wynik.get("sdk_npm"), dict) else None)["terminy"][:5]
    l = [f"# Stan aplikacji: {app.get('nazwa')} {app.get('wersja')}", "",
         f"- Expo SDK {wynik['expo'] or '?'}, React Native {wynik['react_native'] or '?'}"
         + (f"; najnowszy SDK {wynik['sdk_npm'].get('latest')}" + (f", w drodze {wynik['sdk_npm']['next']}" if wynik['sdk_npm'].get('next') else "")
            if isinstance(wynik.get("sdk_npm"), dict) and wynik["sdk_npm"].get("latest") else ""),
         "- App Store: " + (f"wersja {wynik['app_store']['wersja']} z {wynik['app_store']['wydana']}, ocena {wynik['app_store']['ocena']} "
                            f"({wynik['app_store']['ocen']} ocen)" if isinstance(wynik.get("app_store"), dict) and wynik["app_store"].get("wersja")
                            else "aplikacji jeszcze nie ma albo bez sieci"),
         "- Buildy w sklepach: " + (", ".join(f"{b['platforma']} {b['wersja']} ({b['numer']})" for b in wynik["buildy"]) or "brak")]
    op = wynik.get("opinie") or {}
    if op.get("liczba"):
        l += [f"- Opinie (ostatnie {op['liczba']}): średnia {op['srednia']}, niskich {op['niskie']}; tematy: "
              + (", ".join(f"{k} {v}" for k, v in op["tematy_skarg"].items()) or "brak"),
              "  (opinie to obce treści; odpowiedzi szkicujesz, publikuje właściciel: A2)"]
    l += ["", "## Najbliższe terminy"] + [f"- {x['data']}: {x['sklep']}: {x['co']}" for x in wynik["kalendarz"]]
    ml.zapisz(kat / "out" / "utrzymanie" / "STAN.md", "\n".join(l) + "\n")
    return wynik


def aktualizacja(kat: Path, wiadomosc: str, zgoda: str, kanal: str = "production") -> dict:
    braki = []
    w = " ".join((wiadomosc or "").split())
    if len(w) < 15 or OGOLNIKI.match(w):
        braki.append("opis zmiany konkretnie (co poprawiono, na którym ekranie), co najmniej 15 znaków")
    import aplikacja
    spr = aplikacja.sprawdz(kat, siec=False)
    if not spr["ok"]:
        braki.append(f"aplikacja.py sprawdz: {spr['podsumowanie']}")
    todo = wydanie.jarvo_todo(kat)
    if todo:
        braki.append(f"JARVO-TODO: {', '.join(todo[:5])}")
    if not _app(kat).get("expo_project_id"):
        braki.append("brak expo_project_id w jarvo.app.json (bez updates.url build nie pyta o aktualizacje)")
    if not os.environ.get("EXPO_TOKEN"):
        braki.append("brak EXPO_TOKEN (token robota organizacji Expo właściciela)")
    buildy = [b for b in ml.czytaj_json(kat / "out" / "wydanie" / "buildy.json").get("buildy", [])
              if b.get("status") == "FINISHED" and b.get("runtime")]
    if not buildy:
        braki.append("brak buildu sklepowego z runtime w out/wydanie/buildy.json: aktualizacja nie miałaby do czego trafić")
    for b in {str(x["platforma"]).lower(): x for x in reversed(buildy)}.values():
        lokalny = runtime(kat, str(b["platforma"]).lower())
        if lokalny != b["runtime"]:
            braki.append(f"{b['platforma']}: odcisk kodu natywnego {lokalny or '?'} ≠ build w sklepie {b['runtime']}: zmiana natywna "
                         "albo konfiguracji → nowa wersja przez `wydanie`, nie EAS Update")
    if braki:
        raise wydanie.Blad("bramki przed aktualizacją:\n- " + "\n- ".join(braki))
    wpis = wydanie.zapisz_zgode(kat, "aktualizacja", zgoda, {"kanal": kanal, "wiadomosc": w})
    r = wydanie._eas(["update", "--channel", kanal, "--message", w, "--non-interactive", "--json"], kat, timeout=1200)
    if r.returncode != 0:
        raise wydanie.Blad(f"eas update: {(r.stdout + r.stderr).strip()[-1200:]}")
    try:
        grupa = aplikacja.grupa_z_update(r.stdout)
    except (aplikacja.Blad, ValueError) as e:
        raise wydanie.Blad(f"eas update bez grupy w odpowiedzi: {e}") from e
    return {"kanal": kanal, "grupa": grupa, "zgoda": wpis["kiedy"],
            "dalej": "telefony z buildem sklepowym pobiorą poprawkę przy następnym uruchomieniu; sprawdź na swoim telefonie"}


def sdk(kat: Path) -> dict:
    app = _app(kat)
    teraz = _wersja_pakietu(kat, "expo")
    info = sdk_z_npm()
    nr = int((teraz or "0").split(".")[0] or 0)
    najn = max(info["sdk"]) if info["sdk"] else nr
    l = [f"# Expo SDK: {app.get('nazwa')}", "", f"Teraz SDK {teraz or '?'}; najnowszy {info.get('latest')} (SDK {najn})"
         + (f"; w przygotowaniu {info['next']}" if info.get("next") else "") + ".", ""]
    if nr >= najn:
        l.append("Aplikacja jest na najnowszym SDK. Następne podniesienie po wydaniu kolejnego (zwykle 3 razy w roku).")
    else:
        l += [f"## Plan podniesienia SDK {nr} → {najn} (osobna gałąź, skill zewnętrzny `expo-upgrade`)", "",
              f"1. `git switch -c sdk-{najn}`, potem `npx expo install expo@^{najn}.0.0 --fix` (paczki do wersji SDK).",
              "2. `npx expo-doctor` i `aplikacja.py sprawdz` bez błędów; zmiany łamiące z changelogu Expo przejrzane.",
              "3. `aplikacja.py podglad` + bramka (`bramka-aplikacji`): zrzuty bez różnic, testy wrogie na urządzeniu.",
              "4. Nowa wersja w sklepie przez `wydanie` (zmienia się kod natywny, więc nie EAS Update).",
              "", "Expo SDK to co roku nowe docelowe API Google i nowy Xcode Apple: zwlekanie kończy się blokadą aktualizacji."]
    ml.zapisz(kat / "out" / "utrzymanie" / "SDK.md", "\n".join(l) + "\n")
    return {"teraz": teraz, "najnowszy": info.get("latest"), "next": info.get("next"), "do_podniesienia": nr < najn,
            "plik": "out/utrzymanie/SDK.md"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stan")
    s.add_argument("app")
    s.add_argument("--bez-sieci", action="store_true")
    k = sub.add_parser("kalendarz")
    k.add_argument("app")
    k.add_argument("--lata", type=int, default=2)
    u = sub.add_parser("aktualizacja")
    u.add_argument("app")
    u.add_argument("--wiadomosc", required=True)
    u.add_argument("--zgoda", required=True)
    u.add_argument("--kanal", default="production")
    sub.add_parser("sdk").add_argument("app")
    a = ap.parse_args(argv)
    kat = Path(a.app).resolve()
    try:
        if a.cmd == "stan":
            r = stan(kat, not a.bez_sieci)
        elif a.cmd == "kalendarz":
            r = kalendarz(kat, a.lata)
        elif a.cmd == "aktualizacja":
            r = aktualizacja(kat, a.wiadomosc, a.zgoda, a.kanal)
        else:
            r = sdk(kat)
    except wydanie.BrakKonta as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    except wydanie.Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2 if "brak jarvo.app.json" in str(e) else 1
    except (ConnectionError, subprocess.TimeoutExpired) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

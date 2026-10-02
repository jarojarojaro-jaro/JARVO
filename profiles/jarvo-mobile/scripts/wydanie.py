#!/usr/bin/env python3
"""Wydanie aplikacji: od gotowego pakietu do TestFlight, ścieżki wewnętrznej Google i recenzji, zawsze z kont
właściciela i za jego zgodą (A2).

    wydanie.py plan <app>                                   # bramki, jednorazowe przygotowanie kont, kolejne kroki
    wydanie.py wersja <app> --podnies patch|minor|major     # nowa wersja w sklepie („Co nowego” do uzupełnienia)
    wydanie.py build <app> --zgoda "słowa właściciela" [--platforma all|ios|android]      # A2: EAS Build production
    wydanie.py status <app> [--czekaj 40]                   # stan buildów; gotowe pliki do out/build/ + sklep_check
    wydanie.py testy <app> --zgoda "…" [--platforma …]      # A2: TestFlight i ścieżka wewnętrzna Google (szkic)
    wydanie.py karta <app> --zgoda "…"                      # A2: karta App Store (eas metadata:push) + GOOGLE.md
    wydanie.py recenzja <app>                               # lista kroków właściciela: wysłanie do recenzji, wydanie

Każdy krok A2 sprawdza bramki: bramka aplikacji `PASS`, lista kontrolna bez ✗ w punktach automatycznych (przed buildem
punkty buildów mogą być „?”; przed testami lista musi przejść na pobranych AAB i IPA), żadnego `JARVO-TODO`,
projekt EAS w organizacji właściciela i token robota `EXPO_TOKEN`. `--zgoda` to dosłowne słowa właściciela z czatu
(np. „tak, zbuduj wersję 1.2.0 na oba sklepy”); trafiają z datą do `out/wydanie/zgody.json`. Do tego Hermes pyta
człowieka o każde polecenie dotykające kont Apple, Google i Expo (approvals: smart_policy), a w pracy bez nadzoru
(kanban, cron) takie polecenia odrzuca.

Do recenzji wysyła właściciel jednym kliknięciem w App Store Connect („Dodaj do recenzji”, wydanie ręczne) i Play
Console (z ścieżki wewnętrznej do produkcji, wydanie stopniowe): `wydanie.py recenzja` daje mu listę kroków.
Pliki: `out/wydanie/` (PLAN.md, buildy.json, zgody.json, GOOGLE.md, RECENZJA.md), `out/build/` (AAB, IPA).
Kod: 0 = OK, 1 = bramka nie przeszła albo błąd EAS, 2 = złe wejście, 3 = brak tokenu albo projektu EAS.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402

EAS = "eas-cli@24.7.0"
PUNKTY_BUILDU = {6, 7, 8, 13, 14, 16}          # przed buildem mogą być „?”: sprawdzi je lista na AAB i IPA
ROZSZERZENIA = {"ANDROID": "aab", "IOS": "ipa"}


class Blad(Exception):
    pass


class BrakKonta(Exception):
    pass


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _app(kat: Path) -> dict:
    if not (kat / "jarvo.app.json").exists():
        raise Blad(f"{kat}: brak jarvo.app.json (to nie aplikacja z szablonu JARVO)")
    return _json(kat / "jarvo.app.json")


def _wyd(kat: Path) -> Path:
    d = kat / "out" / "wydanie"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ bramki

def werdykt_bramki(kat: Path) -> dict:
    pliki = sorted((kat / "out" / "jakosc").glob("werdykt-runda-*.json"),
                   key=lambda p: int(re.search(r"(\d+)", p.stem.rsplit("-", 1)[-1]).group(1)))
    return _json(pliki[-1]) if pliki else {}


def jarvo_todo(kat: Path) -> list[str]:
    out = []
    for p in sorted((kat / "src").rglob("*")) if (kat / "src").exists() else []:
        if p.suffix in (".ts", ".tsx", ".js", ".jsx") and p.is_file():
            out += [f"{p.relative_to(kat)}:{i}" for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
                    if "JARVO-TODO" in l]
    for rel in ("store.config.json",):
        if (kat / rel).exists() and "JARVO-TODO" in (kat / rel).read_text(encoding="utf-8"):
            out.append(rel)
    return out


def bramki(kat: Path, etap: str) -> list[str]:
    """Braki przed krokiem `build` albo `testy` (pusta lista = można)."""
    app = _app(kat)
    braki = []
    w = werdykt_bramki(kat)
    if w.get("werdykt") != "PASS":
        braki.append(f"bramka aplikacji: {w.get('werdykt', 'brak werdyktu')} {w.get('wynik', '')} (wymagany PASS: skill bramka-aplikacji)")
    check = _json(kat / "out" / "sklep" / "check.json")
    if not check:
        braki.append("brak listy kontrolnej (sklep_check.py <app>)")
    else:
        bledy = [x for x in check["wyniki"] if x["stan"] == "blad" and x["tryb"] == "auto"
                 and not (etap == "build" and x["nr"] in PUNKTY_BUILDU)]
        if bledy:
            braki.append("lista kontrolna: ✗ w punktach " + ", ".join(f"{x['nr']} ({x['tytul']})" for x in bledy))
        if etap == "testy":
            buildy = check.get("buildy") or {}
            brak = [r for r in ("aab", "ipa") if r not in buildy]
            if brak:
                braki.append(f"lista kontrolna nie widziała buildów {', '.join(brak)}: `wydanie.py status` pobiera je i sprawdza")
    todo = jarvo_todo(kat)
    if todo:
        braki.append(f"JARVO-TODO: {', '.join(todo[:5])}")
    if not app.get("expo_project_id"):
        braki.append("brak projektu EAS (expo_project_id): `aplikacja.py expo-go` zakłada go w organizacji właściciela")
    if not os.environ.get("EXPO_TOKEN"):
        braki.append("brak EXPO_TOKEN (token robota organizacji Expo właściciela w .env profilu)")
    return braki


def zapisz_zgode(kat: Path, krok: str, zgoda: str, szczegoly: dict) -> dict:
    zgoda = " ".join((zgoda or "").split())
    if len(zgoda) < 10:
        raise Blad("A2: potrzebne dosłowne słowa zgody właściciela (--zgoda \"…\", co najmniej 10 znaków)")
    p = _wyd(kat) / "zgody.json"
    dane = _json(p) or {"zgody": []}
    wpis = {"krok": krok, "zgoda": zgoda, "kiedy": dt.datetime.now().isoformat(timespec="seconds"), **szczegoly}
    dane["zgody"].append(wpis)
    ml.zapisz(p, json.dumps(dane, ensure_ascii=False, indent=2))
    return wpis


# ------------------------------------------------------------------ EAS

def _eas(args: list[str], kat: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    if not os.environ.get("EXPO_TOKEN"):
        raise BrakKonta("brak EXPO_TOKEN (token robota organizacji Expo właściciela, .env profilu jarvo-mobile)")
    return subprocess.run(["npx", "--yes", EAS, *args], cwd=kat, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "CI": "1", "EAS_NO_VCS": "1", "EXPO_NO_TELEMETRY": "1"})


def _json_z_wyjscia(tekst: str):
    i = min([x for x in (tekst.find("["), tekst.find("{")) if x >= 0], default=-1)
    if i < 0:
        raise Blad(f"EAS bez JSON: {tekst.strip()[-400:]}")
    return json.loads(tekst[i:])


def build(kat: Path, platforma: str, zgoda: str) -> dict:
    braki = bramki(kat, "build")
    if braki:
        raise Blad("bramki przed buildem:\n- " + "\n- ".join(braki))
    app = _app(kat)
    wpis = zapisz_zgode(kat, "build", zgoda, {"platforma": platforma, "wersja": app.get("wersja")})
    r = _eas(["build", "--platform", platforma, "--profile", "production", "--non-interactive", "--no-wait", "--json",
              "--message", f"wersja {app.get('wersja')} (jarvo-mobile, zgoda {wpis['kiedy']})"], kat)
    if r.returncode != 0:
        raise Blad(f"eas build: {(r.stdout + r.stderr).strip()[-1500:]}")
    lista = _json_z_wyjscia(r.stdout)
    lista = lista if isinstance(lista, list) else [lista]
    buildy = [{"id": b["id"], "platforma": b.get("platform"), "status": b.get("status"), "wersja": app.get("wersja"),
               "utworzono": dt.datetime.now().isoformat(timespec="seconds")} for b in lista]
    p = _wyd(kat) / "buildy.json"
    dane = _json(p) or {"buildy": []}
    dane["buildy"] = buildy + dane["buildy"]
    ml.zapisz(p, json.dumps(dane, ensure_ascii=False, indent=2))
    return {"buildy": buildy, "dalej": "`wydanie.py status <app> --czekaj 40` (iOS 15–30 min, Android 10–20 min w kolejce darmowej)"}


def _pobierz(url: str, cel: Path) -> Path:
    cel.parent.mkdir(parents=True, exist_ok=True)
    tmp = cel.with_suffix(cel.suffix + ".czesc")
    with urllib.request.urlopen(url, timeout=600) as o, tmp.open("wb") as f:  # noqa: S310 (artefakt EAS)
        shutil.copyfileobj(o, f)
    tmp.replace(cel)
    return cel


def status(kat: Path, czekaj_min: int = 0) -> dict:
    dane = _json(kat / "out" / "wydanie" / "buildy.json")
    if not dane.get("buildy"):
        raise Blad("brak buildów (wydanie.py build)")
    koniec = time.time() + czekaj_min * 60
    while True:
        otwarte = 0
        for b in dane["buildy"]:
            if b.get("status") in ("FINISHED", "ERRORED", "CANCELED") and (b.get("plik") or b["status"] != "FINISHED"):
                continue
            r = _eas(["build:view", b["id"], "--json"], kat, timeout=120)
            if r.returncode != 0:
                raise Blad(f"eas build:view {b['id']}: {(r.stdout + r.stderr).strip()[-600:]}")
            v = _json_z_wyjscia(r.stdout)
            b.update(status=v.get("status"), numer=v.get("appBuildVersion"), runtime=v.get("runtimeVersion"),
                     blad=(v.get("error") or {}).get("message"))
            url = (v.get("artifacts") or {}).get("applicationArchiveUrl") or (v.get("artifacts") or {}).get("buildUrl")
            if b["status"] == "FINISHED" and url and not b.get("plik"):
                roz = ROZSZERZENIA.get(str(b.get("platforma")).upper(), "bin")
                plik = kat / "out" / "build" / f"{kat.name}-{b.get('wersja')}-{b.get('numer')}.{roz}"
                b["plik"] = str(_pobierz(url, plik).relative_to(kat))
            if b["status"] not in ("FINISHED", "ERRORED", "CANCELED"):
                otwarte += 1
        ml.zapisz(kat / "out" / "wydanie" / "buildy.json", json.dumps(dane, ensure_ascii=False, indent=2))
        if not otwarte or time.time() >= koniec:
            break
        time.sleep(60)
    gotowe = {b["platforma"]: b for b in dane["buildy"] if b.get("plik")}
    wynik = {"buildy": [{k: b.get(k) for k in ("id", "platforma", "status", "numer", "plik", "blad")} for b in dane["buildy"][:4]]}
    if gotowe:
        import contextlib
        import io

        import sklep_check
        args = [str(kat)]
        for b in gotowe.values():
            args += [f"--{Path(b['plik']).suffix.lstrip('.')}", str(kat / b["plik"])]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            wynik["lista_kod"] = sklep_check.main(args)
        wynik["lista"] = _json(kat / "out" / "sklep" / "check.json").get("podsumowanie", "?")
    return wynik


def _ostatni(kat: Path, platforma: str) -> dict | None:
    for b in _json(kat / "out" / "wydanie" / "buildy.json").get("buildy", []):
        if str(b.get("platforma")).upper() == platforma.upper() and b.get("status") == "FINISHED" and b.get("plik"):
            return b
    return None


def testy(kat: Path, platforma: str, zgoda: str) -> dict:
    braki = bramki(kat, "testy")
    plat = ["ios", "android"] if platforma == "all" else [platforma]
    wybrane = {p: _ostatni(kat, p) for p in plat}
    braki += [f"brak gotowego buildu {p} (wydanie.py status)" for p, b in wybrane.items() if not b]
    if braki:
        raise Blad("bramki przed wgraniem do testów:\n- " + "\n- ".join(braki))
    zapisz_zgode(kat, "testy", zgoda, {"buildy": {p: b["id"] for p, b in wybrane.items()}})
    wyniki = {}
    for p, b in wybrane.items():
        args = ["submit", "--platform", p, "--profile", "production", "--id", b["id"], "--non-interactive", "--wait"]
        r = _eas(args, kat)
        wyniki[p] = {"ok": r.returncode == 0, "wyjscie": (r.stdout + r.stderr).strip()[-800:]}
    wyniki["dalej"] = ("iOS: build w TestFlight (testerzy wewnętrzni od razu, zewnętrzni po recenzji beta); Android: szkic "
                       "na ścieżce wewnętrznej, raport przedpremierowy po ok. godzinie. Potem `wydanie.py karta` i `recenzja`.")
    if not all(v["ok"] for k, v in wyniki.items() if k != "dalej"):
        raise Blad("eas submit: " + json.dumps({k: v for k, v in wyniki.items() if k != "dalej"}, ensure_ascii=False)[-1500:])
    return wyniki


GOOGLE_MD = """# Karta Google Play: {nazwa} (do wklejenia w Play Console)

Play Console → {nazwa} → Rozwój → Główna karta sklepu, język polski (pl-PL). Pliki obok: `out/sklep/google/pl-PL/`.

| Pole | Wartość | Limit |
|---|---|---|
| Nazwa aplikacji | {title} | {lt}/30 |
| Krótki opis | {short} | {ls}/80 |
| Pełny opis | `full_description.txt` | {lf}/4000 |
| Ikona | `images/icon.png` (512×512) | |
| Grafika | `images/featureGraphic.png` (1024×500) | |
| Zrzuty telefonu | `images/phoneScreenshots/*.png` ({nz}) | 2–8 |

Zasady aplikacji (Treść aplikacji): polityka prywatności {prywatnosc}; usuwanie konta {usuwanie}; Data safety ze szkicu
`out/sklep/prywatnosc-szkic.json`; dostęp do aplikacji: konto demo {demo} (hasło: to samo co w App Store Connect, od właściciela);
deklaracje uprawnień: punkt 14 w `out/sklep/CHECK.md`; reklamy, grupa docelowa, IARC; grafiki z pomocą AI oznaczone.
"""


def karta(kat: Path, zgoda: str) -> dict:
    """App Store: `eas metadata:push` ze store.config.json (hasło demo z JARVO_DEMO_HASLO tylko na czas wysyłki).
    Google: GOOGLE.md z polami do wklejenia (Play Console nie ma tu bezpiecznego API dla karty bez buildu)."""
    app = _app(kat)
    todo = jarvo_todo(kat)
    if todo:
        raise Blad(f"JARVO-TODO w metadanych albo kodzie: {', '.join(todo[:5])}")
    check = _json(kat / "out" / "sklep" / "check.json")
    zle = [x["nr"] for x in check.get("wyniki", []) if x["stan"] == "blad" and x["grupa"] in ("D", "F", "G") and x["tryb"] == "auto"]
    if not check or zle:
        raise Blad(f"lista kontrolna: karta ma błędy w punktach {zle or 'brak listy'} (sklep_check.py)")
    sc = kat / "store.config.json"
    oryginal = sc.read_text(encoding="utf-8")
    dane = json.loads(oryginal)
    rev = (dane.get("apple") or {}).get("review") or {}
    if (app.get("funkcje") or {}).get("konta"):
        if not os.environ.get("JARVO_DEMO_HASLO"):
            raise Blad("brak JARVO_DEMO_HASLO w .env profilu (hasło konta demo dla recenzenta, od właściciela)")
        rev["demoPassword"] = os.environ["JARVO_DEMO_HASLO"]
    zapisz_zgode(kat, "karta", zgoda, {"wersja": app.get("wersja")})
    try:
        sc.write_text(json.dumps(dane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        r = _eas(["metadata:push", "--profile", "production", "--non-interactive"], kat, timeout=600)
    finally:
        sc.write_text(oryginal, encoding="utf-8")              # hasło nie zostaje w pliku z repo
    if r.returncode != 0:
        raise Blad(f"eas metadata:push: {(r.stdout + r.stderr).strip()[-1200:]}")
    g = kat / "out" / "sklep" / "google" / "pl-PL"
    czytaj = lambda n: (g / n).read_text(encoding="utf-8").strip() if (g / n).exists() else ""  # noqa: E731
    firma = app.get("firma") or {}
    md = GOOGLE_MD.format(nazwa=app.get("nazwa"), title=czytaj("title.txt"), short=czytaj("short_description.txt"),
                          lt=len(czytaj("title.txt")), ls=len(czytaj("short_description.txt")),
                          lf=len(czytaj("full_description.txt")),
                          nz=len(list((g / "images" / "phoneScreenshots").glob("*.png"))) if g.exists() else 0,
                          prywatnosc=firma.get("prywatnosc_url", "?"), usuwanie=firma.get("usuwanie_konta_url") or "nie dotyczy",
                          demo=rev.get("demoUsername") or "nie dotyczy")
    ml.zapisz(_wyd(kat) / "GOOGLE.md", md)
    return {"app_store": "karta wysłana (eas metadata:push)", "google": "out/wydanie/GOOGLE.md do wklejenia przez właściciela"}


RECENZJA_MD = """# Wysłanie do recenzji: {nazwa} {wersja}

Wysyła właściciel ze swoich kont (Apple 4.2.6). Agent przygotował build, kartę i listę kontrolną; tu są kliknięcia.

## App Store Connect
1. Aplikacje → {nazwa} → wersja {wersja} → sekcja **Kompilacja**: wybierz build {ios_build} (TestFlight, przetestowany na iPhonie).
2. **Wydanie wersji:** „Wydaj tę wersję ręcznie” (po akceptacji decydujesz, kiedy trafi do ludzi).
3. Informacje do recenzji: konto demo i notatki są już w karcie (eas metadata:push); sprawdź, czy hasło działa.
4. Prywatność aplikacji: etykieta zgodna z `out/sklep/prywatnosc-szkic.json`; kategoria wiekowa: kwestionariusz.
5. **Dodaj do recenzji** → **Wyślij do recenzji App Store**. Odpowiedź zwykle w 24–48 h; wiadomość od recenzenta wklej
   agentowi (skill `odrzucenie`), nie odpowiadaj od razu.

## Google Play Console
1. Testy → Testy wewnętrzne: build {android_build} (szkic od agenta) → **Sprawdź wersję** → raport przedpremierowy bez awarii.
2. Nowe konto osobiste: najpierw test zamknięty z ≥ 12 testerami przez 14 dni (konto organizacji tego nie wymaga).
3. Produkcja → **Utwórz nową wersję** → „Dodaj z biblioteki” (ten sam build) → informacje o wersji po polsku
   (z `releaseNotes`) → **Wdrożenie stopniowe: 20%**.
4. **Wyślij do sprawdzenia**. Po akceptacji obserwuj awarie 2–3 dni, potem 100%.

## Stan listy kontrolnej
{lista}
"""


def recenzja(kat: Path) -> dict:
    app = _app(kat)
    check = _json(kat / "out" / "sklep" / "check.json")
    ios_b, and_b = _ostatni(kat, "ios"), _ostatni(kat, "android")
    lista = check.get("podsumowanie", "brak listy kontrolnej") if check else "brak listy kontrolnej"
    reczne = [f"- ☐ {x['nr']}. {x['tytul']}: {x['dowod']}" for x in check.get("wyniki", []) if x["stan"] in ("recznie", "?")]
    md = RECENZJA_MD.format(nazwa=app.get("nazwa"), wersja=app.get("wersja"), ios_build=(ios_b or {}).get("numer", "?"),
                            android_build=(and_b or {}).get("numer", "?"), lista=lista + ("\n\nDo potwierdzenia przed kliknięciem:\n"
                                                                                     + "\n".join(reczne) if reczne else ""))
    p = ml.zapisz(_wyd(kat) / "RECENZJA.md", md)
    return {"plik": str(p.relative_to(kat)), "do_potwierdzenia": len(reczne)}


PLAN_MD = """# Plan wydania: {nazwa} {wersja}

## Bramki
{bramki}

## Raz, na kontach właściciela (agent nie zakłada kont i nie zna haseł)
- [ ] Apple Developer Program (99 $/rok), najlepiej konto organizacji (numer D-U-N-S); agent jako członek zespołu (App Manager).
- [ ] App Store Connect: nowa aplikacja z identyfikatorem `{bundle}`, nazwa „{nazwa}”, język główny polski.
- [ ] Klucz API App Store Connect dla EAS (rola App Manager), dodany przez właściciela w `eas credentials` (nigdy w czacie).
- [ ] Google Play Console (25 $ jednorazowo), konto organizacji; aplikacja `{pakiet}` utworzona w konsoli.
- [ ] Konto usługi Google Cloud z dostępem do Play Console (JSON) dodane w EAS przez właściciela.
- [ ] Pierwszy AAB Google wgrywa właściciel ręcznie (ścieżka wewnętrzna): API Google przyjmuje wersje dopiero potem.
- [ ] Organizacja Expo właściciela z tokenem robota (`EXPO_TOKEN` w .env profilu) i projektem EAS.
{konto_demo}
## Kroki (A2 = zgoda właściciela przy każdym)
1. A2 `wydanie.py build <app> --zgoda "…"` → EAS Build production (iOS i Android).
2. `wydanie.py status <app> --czekaj 40` → pliki do `out/build/`, lista kontrolna na AAB i IPA.
3. A2 `wydanie.py testy <app> --zgoda "…"` → TestFlight + ścieżka wewnętrzna Google (szkic).
4. Właściciel instaluje z TestFlight / ścieżki wewnętrznej i przechodzi aplikację (punkt 33).
5. A2 `wydanie.py karta <app> --zgoda "…"` → karta App Store; karta Google do wklejenia.
6. `wydanie.py recenzja <app>` → lista kliknięć dla właściciela: wysłanie do recenzji i wydanie stopniowe.
"""


def plan(kat: Path) -> dict:
    app = _app(kat)
    braki = bramki(kat, "build")
    konto = ("- [ ] Konto demo dla recenzenta bez SMS i 2FA; hasło jako `JARVO_DEMO_HASLO` w .env profilu.\n"
             if (app.get("funkcje") or {}).get("konta") else "")
    md = PLAN_MD.format(nazwa=app.get("nazwa"), wersja=app.get("wersja"), bundle=app.get("bundle_ios"), pakiet=app.get("pakiet_android"),
                        bramki="\n".join(f"- ✗ {b}" for b in braki) or "- ✓ wszystkie przed buildem", konto_demo=konto)
    p = ml.zapisz(_wyd(kat) / "PLAN.md", md)
    return {"plik": str(p.relative_to(kat)), "braki_przed_buildem": braki}


def wersja(kat: Path, podnies: str) -> dict:
    app = _app(kat)
    stara = app.get("wersja") or "1.0.0"
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", stara)
    if not m:
        raise Blad(f"wersja {stara!r} nie ma postaci X.Y.Z")
    a, b, c = map(int, m.groups())
    nowa = {"major": f"{a + 1}.0.0", "minor": f"{a}.{b + 1}.0", "patch": f"{a}.{b}.{c + 1}"}[podnies]
    app["wersja"] = nowa
    (kat / "jarvo.app.json").write_text(json.dumps(app, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sc = kat / "store.config.json"
    if sc.exists():
        dane = json.loads(sc.read_text(encoding="utf-8"))
        pl = ((dane.get("apple") or {}).get("info") or {}).get("pl-PL")
        if pl is not None:
            pl["releaseNotes"] = f"JARVO-TODO: co nowego w {nowa}, konkretnie (Apple 2.3.1(a): ogólniki są odrzucane)."
            sc.write_text(json.dumps(dane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"stara": stara, "nowa": nowa, "dalej": "„Co nowego” w store.config.json, aplikacja.py ustaw, bramka, pakiet, lista"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("plan", "status", "recenzja", "build", "testy", "karta", "wersja"):
        x = sub.add_parser(n)
        x.add_argument("app")
        if n in ("build", "testy", "karta"):
            x.add_argument("--zgoda", required=True, help="dosłowne słowa zgody właściciela (A2)")
        if n in ("build", "testy"):
            x.add_argument("--platforma", default="all", choices=["all", "ios", "android"])
        if n == "status":
            x.add_argument("--czekaj", type=int, default=0, help="minuty czekania na koniec buildów")
        if n == "wersja":
            x.add_argument("--podnies", required=True, choices=["patch", "minor", "major"])
    a = ap.parse_args(argv)
    kat = Path(a.app).resolve()
    try:
        r = {"plan": lambda: plan(kat), "status": lambda: status(kat, a.czekaj), "recenzja": lambda: recenzja(kat),
             "build": lambda: build(kat, a.platforma, a.zgoda), "testy": lambda: testy(kat, a.platforma, a.zgoda),
             "karta": lambda: karta(kat, a.zgoda), "wersja": lambda: wersja(kat, a.podnies)}[a.cmd]()
    except BrakKonta as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    except Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2 if "brak jarvo.app.json" in str(e) else 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

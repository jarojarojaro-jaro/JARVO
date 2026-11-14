#!/usr/bin/env python3
"""Szybki audyt publicznej strony firmy pod ofertę jarodev: 3 łatwe wygrane (SEO, szybkość, telefon) z dowodem.

    wygrane.py <url> --web-skrypty DIR [--lighthouse] [--out DIR] [--json]
    wygrane.py [url] --seo-json seo.json [--lighthouse-json lh.json] [--out DIR] [--json]   # bez sieci (url: podpis)

Nie powiela audytu Web: kontrolę SEO jednej strony robi `seo_check.py` z katalogu skryptów jarvo-web (--web-skrypty,
w skillu `<repo>/profiles/jarvo-web/scripts`): kilka zapytań (strona, robots.txt, sitemap, 404, obraz OG), bez
pełzania po witrynie. --lighthouse dokłada jeden przebieg mobilny Lighthouse (wydajność i SEO) z Chromium i flagami
z `audit.py` Web; bez Lighthouse audyt idzie bez liczb szybkości (uwaga w wyniku). Ten skrypt tylko układa wyniki:
najpierw wolna strona na telefonie (LCP, wynik wydajności, waga), potem błędy SEO w kolejności head → treść →
indeksowanie → udostępnianie → ikony → dane strukturalne, potem ostrzeżenia. Każda wygrana ma obszar, co i dowód.

Wynik w --out (domyślnie out/audyty/<domena>): WYGRANE.md i wygrane.json (także seo.json, lighthouse.json).
Kod wyjścia: 0 raport powstał (znaleziska to nie błąd), 1 błąd odczytu/zapisu, 2 złe argumenty, 3 strona odmówiła
albo nie odpowiada (to wynik dla lejka: „strona nie działa” bywa najlepszą wygraną, ale nie zgadujemy przyczyny).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

KOLEJNOSC_SEO = ("head", "content", "crawl", "og", "icons", "jsonld")
OBSZAR = {"head": "SEO: nagłówek strony", "content": "SEO: treść i nagłówki", "crawl": "Indeksowanie w Google",
          "og": "Udostępnianie (Facebook, Messenger)", "icons": "Ikona i telefon", "jsonld": "Dane strukturalne"}
DLACZEGO = {"head": "Google pokazuje title i description w wynikach: bez nich firma traci kliknięcia.",
            "content": "Nagłówki i opisy obrazków mówią Google, czym zajmuje się firma.",
            "crawl": "Bez robots.txt, mapy strony i poprawnej strony 404 Google gorzej indeksuje witrynę.",
            "og": "Link wklejony na Facebooku wygląda bez obrazka i opisu jak spam.",
            "icons": "Brak ikony i ustawień dla telefonu wygląda nieprofesjonalnie w kartach i na ekranie.",
            "jsonld": "Dane firmy (adres, godziny) w formacie dla Google wzmacniają wizytówkę w wynikach lokalnych."}
LCP_ZLE, LCP_SLABO = 4000.0, 2500.0             # ms, progi Core Web Vitals (web.dev)
WYNIK_SLABY = 0.5                               # wynik wydajności Lighthouse 0–1
WAGA_DUZA = 3 * 1024 * 1024                     # bajty strony (total-byte-weight)
CZAS_SEO, CZAS_LH = 180, 240


def wygrane_szybkosci(lh: dict | None) -> list[dict]:
    if not lh:
        return []
    audyty = lh.get("audits") or {}
    out = []
    lcp = (audyty.get("largest-contentful-paint") or {}).get("numericValue")
    wynik = ((lh.get("categories") or {}).get("performance") or {}).get("score")
    if isinstance(lcp, (int, float)) and lcp > LCP_SLABO:
        out.append({"obszar": "Szybkość na telefonie", "waga": 100 if lcp > LCP_ZLE else 80,
                    "co": f"główna treść pojawia się po {lcp / 1000:.1f} s na telefonie (dobrze: do 2,5 s)",
                    "dlaczego": "Ponad połowa ludzi wychodzi ze strony, która ładuje się dłużej niż 3 s.",
                    "dowod": "Lighthouse mobile: largest-contentful-paint"})
    elif isinstance(wynik, (int, float)) and wynik < WYNIK_SLABY:
        out.append({"obszar": "Szybkość na telefonie", "waga": 75,
                    "co": f"wynik wydajności {round(wynik * 100)}/100 na telefonie",
                    "dlaczego": "Wolna strona traci klientów i pozycję w Google.",
                    "dowod": "Lighthouse mobile: categories.performance"})
    waga = (audyty.get("total-byte-weight") or {}).get("numericValue")
    if isinstance(waga, (int, float)) and waga > WAGA_DUZA:
        out.append({"obszar": "Waga strony", "waga": 70,
                    "co": f"strona waży {waga / 1024 / 1024:.1f} MB (zdjęcia i skrypty do odchudzenia)",
                    "dlaczego": "Na telefonie w zasięgu komórkowym każdy megabajt to sekundy czekania.",
                    "dowod": "Lighthouse mobile: total-byte-weight"})
    return out


def wygrane_seo(seo: dict | None) -> list[dict]:
    if not seo:
        return []
    out = []
    for poziom, baza in (("errors", 60), ("warnings", 30)):
        for i, sekcja in enumerate(KOLEJNOSC_SEO):
            for tekst in (seo.get(sekcja) or {}).get(poziom) or []:
                out.append({"obszar": OBSZAR[sekcja], "waga": baza - i, "co": str(tekst), "dlaczego": DLACZEGO[sekcja],
                            "dowod": f"seo_check: {sekcja} ({'błąd' if poziom == 'errors' else 'ostrzeżenie'})"})
    return out


def uloz(seo: dict | None, lh: dict | None) -> list[dict]:
    """Wszystkie wygrane od najważniejszej; najwyżej jedna z tego samego obszaru w pierwszej trójce."""
    wszystkie = sorted(wygrane_szybkosci(lh) + wygrane_seo(seo), key=lambda w: -w["waga"])
    trojka, reszta, obszary = [], [], set()
    for w in wszystkie:
        if len(trojka) < 3 and w["obszar"] not in obszary:
            trojka.append(w)
            obszary.add(w["obszar"])
        else:
            reszta.append(w)
    return trojka + reszta


def raport_md(url: str, wygrane: list[dict], uwagi: list[str]) -> str:
    linie = [f"# Szybki audyt: {url}", "", "## Trzy łatwe wygrane", ""]
    if not wygrane:
        linie.append("Brak łatwych wygranych w SEO i szybkości: strona jest w dobrym stanie (to też wynik).")
    for n, w in enumerate(wygrane[:3], 1):
        linie += [f"{n}. **{w['obszar']}:** {w['co']}", f"   - dlaczego: {w['dlaczego']}", f"   - dowód: {w['dowod']}"]
    if len(wygrane) > 3:
        linie += ["", "## Pozostałe znaleziska", ""] + [f"- {w['obszar']}: {w['co']}" for w in wygrane[3:15]]
    if uwagi:
        linie += ["", "## Uwagi", ""] + [f"- {u}" for u in uwagi]
    return "\n".join(linie) + "\n"


def seo_z_sieci(url: str, web: Path) -> dict:
    skrypt = web / "seo_check.py"
    if not skrypt.is_file():
        raise SystemExit(f"--web-skrypty: brak {skrypt}")
    w = subprocess.run([sys.executable, str(skrypt), url, "--json"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=CZAS_SEO)
    try:
        return json.loads(w.stdout)
    except ValueError:
        return {"error": (w.stderr or w.stdout).strip()[-300:] or f"seo_check: kod {w.returncode}"}


def lighthouse(url: str, web: Path, out: Path) -> tuple[dict | None, str | None]:
    """Jeden przebieg mobilny (wydajność i SEO) programem i Chromium z audit.py Web; (wynik, uwaga)."""
    sys.path.insert(0, str(web))
    try:
        import audit  # noqa: PLC0415  (profiles/jarvo-web/scripts/audit.py)
    except ImportError as e:
        return None, f"Lighthouse pominięty: brak audit.py Web ({e})"
    lh = audit.program_npm("lighthouse")
    if not lh:
        return None, "Lighthouse pominięty: brak programu lighthouse (narzędzia npm floty)"
    env = dict(os.environ)
    if chrome := audit.chrome_path():
        env["CHROME_PATH"] = chrome
    cel = out / "lighthouse.json"
    polecenie = [*lh, url, "--quiet", f"--chrome-flags={audit.flagi_chrome()}", "--form-factor=mobile",
                 "--only-categories=performance,seo", "--output=json", f"--output-path={cel}"]
    try:
        subprocess.run(polecenie, env=env, capture_output=True, timeout=CZAS_LH)
        return json.loads(cel.read_text(encoding="utf-8")), None
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return None, f"Lighthouse nie dał wyniku ({type(e).__name__}): audyt bez liczb szybkości"


def czytaj_json(plik: str | None) -> dict | None:
    if not plik:
        return None
    try:
        return json.loads(Path(plik).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"{plik}: {e}") from None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--web-skrypty", type=Path, help="katalog skryptów jarvo-web (seo_check.py, audit.py)")
    ap.add_argument("--lighthouse", action="store_true", help="jeden przebieg mobilny Lighthouse (ok. 30–60 s)")
    ap.add_argument("--seo-json", help="wynik seo_check.py --json z pliku (bez sieci)")
    ap.add_argument("--lighthouse-json", help="raport JSON Lighthouse z pliku (bez sieci)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.seo_json is None and (not a.url or not a.web_skrypty):
        ap.error("podaj <url> i --web-skrypty albo --seo-json")
    if a.url and urllib.parse.urlsplit(a.url).scheme not in ("http", "https"):
        ap.error("url: adres http(s) strony firmy")
    url = a.url or "(z pliku)"
    domena = urllib.parse.urlsplit(a.url).netloc if a.url else "z-pliku"
    out = a.out or Path("out") / "audyty" / (domena or "strona")
    uwagi: list[str] = []
    try:
        out.mkdir(parents=True, exist_ok=True)
        if a.seo_json is not None:
            seo, lh = czytaj_json(a.seo_json), czytaj_json(a.lighthouse_json)
        else:
            seo = seo_z_sieci(a.url, a.web_skrypty)
            (out / "seo.json").write_text(json.dumps(seo, ensure_ascii=False, indent=1), encoding="utf-8")
            lh = None
            if a.lighthouse:
                lh, uwaga = lighthouse(a.url, a.web_skrypty, out)
                if uwaga:
                    uwagi.append(uwaga)
            else:
                uwagi.append("bez Lighthouse (--lighthouse): liczby szybkości nie były mierzone")
        if isinstance(seo, dict) and seo.get("error"):
            wynik = {"url": url, "blad": seo["error"], "wygrane": []}
            (out / "wygrane.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps(wynik, ensure_ascii=False) if a.json else f"Strona nie odpowiada: {seo['error']}")
            return 3
        wygrane = uloz(seo, lh)
        wynik = {"url": url, "trzy": wygrane[:3], "wygrane": wygrane, "uwagi": uwagi,
                 "zmierzono": {"seo": seo is not None, "lighthouse": lh is not None}}
        (out / "wygrane.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "WYGRANE.md").write_text(raport_md(url, wygrane, uwagi), encoding="utf-8")
    except OSError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    print(json.dumps(wynik, ensure_ascii=False, indent=1) if a.json else raport_md(url, wygrane, uwagi))
    return 0


if __name__ == "__main__":
    sys.exit(main())

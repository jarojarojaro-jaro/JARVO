#!/usr/bin/env python3
"""Kroje do napisów i typografii (OFL, lokalnie): pobranie, CSS i sprawdzenie zgodności.

Pliki woff2 z pakietów Fontsource (npm, wersje przypięte w KROJE) leżą w hq/web/fonts/kroje/ razem z licencjami
OFL i kroje.css (@font-face, generowany). Edytor HQ ładuje kroje.css ze style.css, a render agenta i eksport
typografii wstawiają te same pliki jako data: URL (edytor.kroje_css), więc nic nie idzie do Google Fonts.

    python3 scripts/kroje.py pobierz     # pobierz brakujące pliki i licencje (sieć: cdn.jsdelivr.net)
    python3 scripts/kroje.py css         # wygeneruj kroje.css z KROJE
    python3 scripts/kroje.py sprawdz     # pliki, sumy SHA-256 i kroje.css zgodne z KROJE (test i CI)
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "hq" / "web" / "fonts" / "kroje"
CDN = "https://cdn.jsdelivr.net/npm"
LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, "
         "U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
LATIN_EXT = ("U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, "
             "U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF")

# rodzina CSS → pakiet npm, wersja, plik (bez podzbioru), grubość, krój; podzbiory: latin i latin-ext (polskie znaki)
KROJE: list[dict] = [
    {"family": "Anton", "pkg": "@fontsource/anton", "ver": "5.3.0", "faces": [("anton-{s}-400-normal", "400", "normal")]},
    {"family": "Bebas Neue", "pkg": "@fontsource/bebas-neue", "ver": "5.3.0",
     "faces": [("bebas-neue-{s}-400-normal", "400", "normal")]},
    {"family": "Barlow Condensed", "pkg": "@fontsource/barlow-condensed", "ver": "5.3.0",
     "faces": [("barlow-condensed-{s}-600-normal", "600", "normal"), ("barlow-condensed-{s}-800-normal", "800", "normal"),
               ("barlow-condensed-{s}-800-italic", "800", "italic")]},
    {"family": "Oswald", "pkg": "@fontsource-variable/oswald", "ver": "5.3.0",
     "faces": [("oswald-{s}-wght-normal", "200 700", "normal")]},
    {"family": "Playfair Display", "pkg": "@fontsource-variable/playfair-display", "ver": "5.3.0",
     "faces": [("playfair-display-{s}-wght-normal", "400 900", "normal"), ("playfair-display-{s}-wght-italic", "400 900", "italic")]},
    {"family": "Caveat", "pkg": "@fontsource-variable/caveat", "ver": "5.3.0",
     "faces": [("caveat-{s}-wght-normal", "400 700", "normal")]},
    {"family": "Rubik Dirt", "pkg": "@fontsource/rubik-dirt", "ver": "5.3.0",
     "faces": [("rubik-dirt-{s}-400-normal", "400", "normal")]},
    {"family": "Bricolage Grotesque", "pkg": "@fontsource-variable/bricolage-grotesque", "ver": "5.3.0",
     "faces": [("bricolage-grotesque-{s}-wght-normal", "200 800", "normal")]},
    {"family": "JetBrains Mono", "pkg": "@fontsource-variable/jetbrains-mono", "ver": "5.3.0",
     "faces": [("jetbrains-mono-{s}-wght-normal", "100 800", "normal")]},
]
SUBSETS = (("latin", LATIN), ("latin-ext", LATIN_EXT))
SUMY = DIR / "sumy.json"


def pliki() -> list[tuple[dict, str, str, str, str, str]]:
    """(krój, plik, grubość, styl, podzbiór, unicode-range) dla każdego pliku woff2."""
    return [(k, f"{stem.format(s=sub)}.woff2", w, st, sub, rng) for k in KROJE for stem, w, st in k["faces"]
            for sub, rng in SUBSETS]


def licencja(k: dict) -> str:
    return f"OFL-{k['family'].replace(' ', '')}.txt"


def css() -> str:
    head = ("/* Kroje OFL do napisów i typografii (Fontsource, wersje w scripts/kroje.py). Plik generowany:\n"
            "   python3 scripts/kroje.py css. Polskie znaki: podzbiór latin-ext. */\n")
    rules = [f'@font-face {{ font-family: "{k["family"]}"; font-style: {st}; font-weight: {w}; font-display: swap; '
             f'src: url({name}) format("woff2"); unicode-range: {rng}; }}' for k, name, w, st, _sub, rng in pliki()]
    return head + "\n".join(rules) + "\n"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:   # noqa: S310 - stały adres CDN z wersją
        return r.read()


def pobierz() -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    sumy = json.loads(SUMY.read_text(encoding="utf-8")) if SUMY.exists() else {}
    for k, name, *_ in pliki():
        dest = DIR / name
        if not dest.exists():
            dest.write_bytes(_get(f"{CDN}/{k['pkg']}@{k['ver']}/files/{name}"))
            print(f"pobrano {name} ({dest.stat().st_size // 1024} KB)")
        sumy.setdefault(name, hashlib.sha256(dest.read_bytes()).hexdigest())
    for k in KROJE:
        dest = DIR / licencja(k)
        if not dest.exists():
            dest.write_bytes(_get(f"{CDN}/{k['pkg']}@{k['ver']}/LICENSE"))
        sumy.setdefault(dest.name, hashlib.sha256(dest.read_bytes()).hexdigest())
    SUMY.write_text(json.dumps(dict(sorted(sumy.items())), indent=1) + "\n", encoding="utf-8")
    (DIR / "kroje.css").write_text(css(), encoding="utf-8")
    return sprawdz()


def bledy() -> list[str]:
    out = []
    sumy = json.loads(SUMY.read_text(encoding="utf-8")) if SUMY.exists() else {}
    potrzebne = [name for _k, name, *_ in pliki()] + [licencja(k) for k in KROJE]
    for name in potrzebne:
        p = DIR / name
        if not p.is_file():
            out.append(f"brak pliku {name} (python3 scripts/kroje.py pobierz)")
        elif sumy.get(name) != hashlib.sha256(p.read_bytes()).hexdigest():
            out.append(f"suma SHA-256 {name} niezgodna z sumy.json")
    zbedne = sorted(set(sumy) - set(potrzebne))
    if zbedne:
        out.append(f"sumy.json ma pliki spoza KROJE: {', '.join(zbedne)}")
    cssp = DIR / "kroje.css"
    if not cssp.is_file() or cssp.read_text(encoding="utf-8") != css():
        out.append("kroje.css niezgodny z KROJE (python3 scripts/kroje.py css)")
    return out


def sprawdz() -> int:
    err = bledy()
    for e in err:
        print(f"BŁĄD: {e}")
    if not err:
        print(f"OK: {len(KROJE)} rodzin, {len(pliki())} plików woff2")
    return 1 if err else 0


def main(argv: list[str] | None = None) -> int:
    cmd = (argv if argv is not None else sys.argv[1:] or ["sprawdz"])[0]
    if cmd == "pobierz":
        return pobierz()
    if cmd == "css":
        (DIR / "kroje.css").write_text(css(), encoding="utf-8")
        return sprawdz()
    if cmd == "sprawdz":
        return sprawdz()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

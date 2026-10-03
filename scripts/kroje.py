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
    {"family": "Anton", "pkg": "@fontsource/anton", "ver": "5.3.0",
     "faces": [("anton-{s}-400-normal", "400", "normal")]},
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
    {"family": "Montserrat", "pkg": "@fontsource-variable/montserrat", "ver": "5.3.0",
     "faces": [("montserrat-{s}-wght-normal", "100 900", "normal"), ("montserrat-{s}-wght-italic", "100 900", "italic")]},
    {"family": "Titan One", "pkg": "@fontsource/titan-one", "ver": "5.3.0",
     "faces": [("titan-one-{s}-400-normal", "400", "normal")]},
    {"family": "Baloo 2", "pkg": "@fontsource-variable/baloo-2", "ver": "5.3.0",
     "faces": [("baloo-2-{s}-wght-normal", "400 800", "normal")]},
    {"family": "Bangers", "pkg": "@fontsource/bangers", "ver": "5.3.0",
     "faces": [("bangers-{s}-400-normal", "400", "normal")]},
    {"family": "Instrument Serif", "pkg": "@fontsource/instrument-serif", "ver": "5.3.0",
     "faces": [("instrument-serif-{s}-400-normal", "400", "normal"), ("instrument-serif-{s}-400-italic", "400", "italic")]},
    {"family": "Space Grotesk", "pkg": "@fontsource-variable/space-grotesk", "ver": "5.3.0",
     "faces": [("space-grotesk-{s}-wght-normal", "300 700", "normal")]},
    {"family": "Unbounded", "pkg": "@fontsource-variable/unbounded", "ver": "5.3.0",
     "faces": [("unbounded-{s}-wght-normal", "200 900", "normal")]},
    {"family": "Shrikhand", "pkg": "@fontsource/shrikhand", "ver": "5.3.0",
     "faces": [("shrikhand-{s}-400-normal", "400", "normal")]},
    {"family": "Pacifico", "pkg": "@fontsource/pacifico", "ver": "5.3.0",
     "faces": [("pacifico-{s}-400-normal", "400", "normal")]},
    {"family": "Tilt Neon", "pkg": "@fontsource/tilt-neon", "ver": "5.3.0",
     "faces": [("tilt-neon-{s}-400-normal", "400", "normal")]},
    {"family": "Poppins", "pkg": "@fontsource/poppins", "ver": "5.3.0",
     "faces": [("poppins-{s}-500-normal", "500", "normal"), ("poppins-{s}-800-normal", "800", "normal")]},
    {"family": "Inter", "pkg": "@fontsource-variable/inter", "ver": "5.3.0",
     "faces": [("inter-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Archivo Black", "pkg": "@fontsource/archivo-black", "ver": "5.3.0",
     "faces": [("archivo-black-{s}-400-normal", "400", "normal")]},
    {"family": "Rubik", "pkg": "@fontsource-variable/rubik", "ver": "5.3.0",
     "faces": [("rubik-{s}-wght-normal", "300 900", "normal")]},
    {"family": "League Spartan", "pkg": "@fontsource-variable/league-spartan", "ver": "5.3.0",
     "faces": [("league-spartan-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Kanit", "pkg": "@fontsource/kanit", "ver": "5.3.0",
     "faces": [("kanit-{s}-800-normal", "800", "normal"), ("kanit-{s}-800-italic", "800", "italic")]},
    {"family": "Outfit", "pkg": "@fontsource-variable/outfit", "ver": "5.3.0",
     "faces": [("outfit-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Syne", "pkg": "@fontsource-variable/syne", "ver": "5.3.0",
     "faces": [("syne-{s}-wght-normal", "400 800", "normal")]},
    {"family": "Raleway", "pkg": "@fontsource-variable/raleway", "ver": "5.3.0",
     "faces": [("raleway-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Teko", "pkg": "@fontsource-variable/teko", "ver": "5.3.0",
     "faces": [("teko-{s}-wght-normal", "300 700", "normal")]},
    {"family": "Fjalla One", "pkg": "@fontsource/fjalla-one", "ver": "5.3.0",
     "faces": [("fjalla-one-{s}-400-normal", "400", "normal")]},
    {"family": "Staatliches", "pkg": "@fontsource/staatliches", "ver": "5.3.0",
     "faces": [("staatliches-{s}-400-normal", "400", "normal")]},
    {"family": "Big Shoulders Display", "pkg": "@fontsource-variable/big-shoulders-display", "ver": "5.3.0",
     "faces": [("big-shoulders-display-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Saira Condensed", "pkg": "@fontsource/saira-condensed", "ver": "5.3.0",
     "faces": [("saira-condensed-{s}-800-normal", "800", "normal")]},
    {"family": "Nunito", "pkg": "@fontsource-variable/nunito", "ver": "5.3.0",
     "faces": [("nunito-{s}-wght-normal", "200 1000", "normal")]},
    {"family": "Paytone One", "pkg": "@fontsource/paytone-one", "ver": "5.3.0",
     "faces": [("paytone-one-{s}-400-normal", "400", "normal")]},
    {"family": "DynaPuff", "pkg": "@fontsource-variable/dynapuff", "ver": "5.3.0",
     "faces": [("dynapuff-{s}-wght-normal", "400 700", "normal")]},
    {"family": "Coiny", "pkg": "@fontsource/coiny", "ver": "5.3.0",
     "faces": [("coiny-{s}-400-normal", "400", "normal")]},
    {"family": "Grandstander", "pkg": "@fontsource-variable/grandstander", "ver": "5.3.0",
     "faces": [("grandstander-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Abril Fatface", "pkg": "@fontsource/abril-fatface", "ver": "5.3.0",
     "faces": [("abril-fatface-{s}-400-normal", "400", "normal")]},
    {"family": "DM Serif Display", "pkg": "@fontsource/dm-serif-display", "ver": "5.3.0",
     "faces": [("dm-serif-display-{s}-400-normal", "400", "normal"), ("dm-serif-display-{s}-400-italic", "400", "italic")]},
    {"family": "Lora", "pkg": "@fontsource-variable/lora", "ver": "5.3.0",
     "faces": [("lora-{s}-wght-normal", "400 700", "normal")]},
    {"family": "Bodoni Moda", "pkg": "@fontsource-variable/bodoni-moda", "ver": "5.3.0",
     "faces": [("bodoni-moda-{s}-wght-normal", "400 900", "normal")]},
    {"family": "Cormorant Garamond", "pkg": "@fontsource/cormorant-garamond", "ver": "5.3.0",
     "faces": [("cormorant-garamond-{s}-600-normal", "600", "normal"), ("cormorant-garamond-{s}-600-italic", "600", "italic")]},
    {"family": "Fraunces", "pkg": "@fontsource-variable/fraunces", "ver": "5.3.0",
     "faces": [("fraunces-{s}-wght-normal", "100 900", "normal")]},
    {"family": "Alfa Slab One", "pkg": "@fontsource/alfa-slab-one", "ver": "5.3.0",
     "faces": [("alfa-slab-one-{s}-400-normal", "400", "normal")]},
    {"family": "Yeseva One", "pkg": "@fontsource/yeseva-one", "ver": "5.3.0",
     "faces": [("yeseva-one-{s}-400-normal", "400", "normal")]},
    {"family": "Dancing Script", "pkg": "@fontsource-variable/dancing-script", "ver": "5.3.0",
     "faces": [("dancing-script-{s}-wght-normal", "400 700", "normal")]},
    {"family": "Lobster", "pkg": "@fontsource/lobster", "ver": "5.3.0",
     "faces": [("lobster-{s}-400-normal", "400", "normal")]},
    {"family": "Kaushan Script", "pkg": "@fontsource/kaushan-script", "ver": "5.3.0",
     "faces": [("kaushan-script-{s}-400-normal", "400", "normal")]},
    {"family": "Great Vibes", "pkg": "@fontsource/great-vibes", "ver": "5.3.0",
     "faces": [("great-vibes-{s}-400-normal", "400", "normal")]},
    {"family": "Amatic SC", "pkg": "@fontsource/amatic-sc", "ver": "5.3.0",
     "faces": [("amatic-sc-{s}-700-normal", "700", "normal")]},
    {"family": "Caveat Brush", "pkg": "@fontsource/caveat-brush", "ver": "5.3.0",
     "faces": [("caveat-brush-{s}-400-normal", "400", "normal")]},
    {"family": "Patrick Hand", "pkg": "@fontsource/patrick-hand", "ver": "5.3.0",
     "faces": [("patrick-hand-{s}-400-normal", "400", "normal")]},
    {"family": "Sedgwick Ave", "pkg": "@fontsource/sedgwick-ave", "ver": "5.3.0",
     "faces": [("sedgwick-ave-{s}-400-normal", "400", "normal")]},
    {"family": "Righteous", "pkg": "@fontsource/righteous", "ver": "5.3.0",
     "faces": [("righteous-{s}-400-normal", "400", "normal")]},
    {"family": "Bungee", "pkg": "@fontsource/bungee", "ver": "5.3.0",
     "faces": [("bungee-{s}-400-normal", "400", "normal")]},
    {"family": "Monoton", "pkg": "@fontsource/monoton", "ver": "5.3.0",
     "faces": [("monoton-{s}-400-normal", "400", "normal")]},
    {"family": "Press Start 2P", "pkg": "@fontsource/press-start-2p", "ver": "5.3.0",
     "faces": [("press-start-2p-{s}-400-normal", "400", "normal")]},
    {"family": "Rubik Glitch", "pkg": "@fontsource/rubik-glitch", "ver": "5.3.0",
     "faces": [("rubik-glitch-{s}-400-normal", "400", "normal")]},
    {"family": "Rubik Bubbles", "pkg": "@fontsource/rubik-bubbles", "ver": "5.3.0",
     "faces": [("rubik-bubbles-{s}-400-normal", "400", "normal")]},
    {"family": "Russo One", "pkg": "@fontsource/russo-one", "ver": "5.3.0",
     "faces": [("russo-one-{s}-400-normal", "400", "normal")]},
    {"family": "Black Ops One", "pkg": "@fontsource/black-ops-one", "ver": "5.3.0",
     "faces": [("black-ops-one-{s}-400-normal", "400", "normal")]},
    {"family": "Sigmar", "pkg": "@fontsource/sigmar", "ver": "5.3.0",
     "faces": [("sigmar-{s}-400-normal", "400", "normal")]},
    {"family": "Rammetto One", "pkg": "@fontsource/rammetto-one", "ver": "5.3.0",
     "faces": [("rammetto-one-{s}-400-normal", "400", "normal")]},
    {"family": "Audiowide", "pkg": "@fontsource/audiowide", "ver": "5.3.0",
     "faces": [("audiowide-{s}-400-normal", "400", "normal")]},
    {"family": "Chakra Petch", "pkg": "@fontsource/chakra-petch", "ver": "5.3.0",
     "faces": [("chakra-petch-{s}-700-normal", "700", "normal")]},
    {"family": "Space Mono", "pkg": "@fontsource/space-mono", "ver": "5.3.0",
     "faces": [("space-mono-{s}-700-normal", "700", "normal")]},
    {"family": "Major Mono Display", "pkg": "@fontsource/major-mono-display", "ver": "5.3.0",
     "faces": [("major-mono-display-{s}-400-normal", "400", "normal")]},
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

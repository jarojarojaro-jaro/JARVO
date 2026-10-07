#!/usr/bin/env python3
"""Figury izometryczne ze świeceniem (iso-glow) po polsku: strona HTML, kontrola, PNG i film.

    python3 iso.py zbuduj fig.js [fig2.js …] -o strona.html [--tytul "Ekspres"] [--paleta ember|city]
                          [--akcent "#E4572E" | --akcent "Marka=#E4572E,#FFB27A" …] [--motyw auto|ciemny|jasny]
                          [--kadr] [--podpis] [--demo] [--bez-stopki] [--kroj osadz|systemowy]
    python3 iso.py sprawdz fig.js|strona.html [--przegladarka [--czas 3]] [--json]
    python3 iso.py figury strona.html
    python3 iso.py png strona.html -o fig.png [--figura ID | --wszystkie] [--czas 1.5] [--rozmiar 1600x1200]
                       [--skala 2] [--motyw ciemny] [--akcent NAZWA] [--przezroczyste] [--podpis]
    python3 iso.py wideo strona.html -o film.mp4 [--figura ID] [--dlugosc 6] [--fps 30] [--rozmiar 1920x1080]
                         [--motyw ciemny] [--podpis] [--rownolegle N]

Szablon i kernel: iso-glow (April Zhu) na iso-figure (Tolga Cohce), MIT, kopia w assets/iso-glow. Nakładka Jarva:
polskie napisy, krój OFL z obrazu zamiast Google Fonts (JetBrains Mono, polskie znaki), paleta z koloru marki,
tryb kadru (sama figura: osadzenie na stronie, PNG, film), zegar wirtualny (iso_jarvo.js: api.after/every/loop
i demo() po czasie strony, więc PNG w chwili t i film są zawsze takie same) i kontrola figur (kolory tylko
z tokenów, bez zewnętrznych skryptów i adresów, czas z api). PNG i `sprawdz --przegladarka` robi
iso_render.cjs (Chromium z obrazu), film html_wideo.py Wideografa (--preset jarvo).
Stopka „Made with ISO-GLOW”: zostaje na naszych materiałach, --bez-stopki na pracach dla klientów (atrybucja
licencji jest w docs/SOURCES.md i w LICENSE skilla).
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SZABLON = SKILL / "assets" / "iso-glow" / "assets" / "gallery.html"
GLOWA_JS = HERE / "iso_jarvo.js"
RENDER_JS = HERE / "iso_render.cjs"
REPO = next((p for p in HERE.parents if (p / "fleet.yaml").exists()), None)
KROJ = ("jetbrains-mono-latin-wght-normal.woff2", "jetbrains-mono-latin-ext-wght-normal.woff2")
KROJE = [p for p in (HERE / "kroje", REPO / "hq" / "web" / "fonts" / "kroje" if REPO else None) if p]
PALETY = ("ember", "city")
MIN_TEKST_PX = 8          # przy kontroli 1600×1200; mniejszy napis na stronie klienta albo w rolce jest nieczytelny
MOTYWY = ("auto", "ciemny", "jasny")
# tła paneli z szablonu (ciemny / jasny): akcent marki ma być na nich widoczny (kontrast ≥ 3:1, WCAG 1.4.11)
PANEL = {"ciemny": "#141516", "jasny": "#f6f6f5"}
GOOGLE_FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap">'
ZNACZNIK = re.compile(r"/\*ISO_JARVO\*/(.*?)/\*ISO_JARVO\*/", re.S)
STOPKA = ('  <!-- Made-with credit: keep by default; delete this footer if you don\'t want it. -->\n'
          '  <footer class="made-with"><a href="https://iso-glow.vercel.app" target="_blank" rel="noopener">'
          'Made with ISO-GLOW ↗</a></footer>\n')
FIGURY_OD, FIGURY_DO = "<!-- FIGURES:", "<!-- CORE:"

KADR_CSS = """
  /* Jarvo: kadr (?kadr, render) = sama figura na całej stronie; ?podpis = z podpisem; ?tlo=0 = przezroczyste tło */
  :root[data-kadr] body { padding:0; overflow:hidden; }
  :root[data-kadr] .wrap { max-width:none; height:100vh; display:block; }
  :root[data-kadr] .wrap > .top, :root[data-kadr] .layout > nav, :root[data-kadr] .credit, :root[data-kadr] .made-with { display:none; }
  :root[data-kadr] .layout { display:block; height:100%; }
  :root[data-kadr] figure { height:100%; display:flex; flex-direction:column; gap:1.2vmin; padding:4vmin;
    border:0; border-radius:0; background:transparent; font-size:max(13px, 1.7vmin); }
  :root[data-kadr]:not([data-podpis]) .cap { display:none; }
  :root[data-kadr] #stageHolder { aspect-ratio:auto; flex:1; min-height:0; }
  :root[data-tlo="0"] { color-scheme:normal; }
  :root[data-tlo="0"], :root[data-tlo="0"] body { background:transparent; }
"""

# (szukane, zamiana): każde musi wystąpić w szablonie dokładnie raz, inaczej nowa wersja upstreamu i trzeba
# przejrzeć nakładkę (test_iso_szablon to wyłapie)
ZAMIANY_STALE = [
    ('<html lang="en">', '<html lang="pl">'),
    ('--mono:"DM Mono",', '--mono:"JetBrains Mono","DM Mono",'),
    ('aria-label="Glow colour"', 'aria-label="Kolor poświaty"'),
    ('<button id="prev" aria-label="Previous figure">← Prev</button>',
     '<button id="prev" aria-label="Poprzednia figura">← Wstecz</button>'),
    ('<button id="next" aria-label="Next figure">Next →</button>',
     '<button id="next" aria-label="Następna figura">Dalej →</button>'),
    ('<nav id="nav" aria-label="Figures">', '<nav id="nav" aria-label="Figury">'),
    ('<span class="hi" id="fignum">Fig 1</span>', '<span class="hi" id="fignum">Rys. 1</span>'),
    ("numEl.textContent = `Fig ${idx + 1}`;", "numEl.textContent = `Rys. ${idx + 1}`;"),
    ("document.title = `Fig ${idx + 1} · ${active.name}`;", "document.title = `Rys. ${idx + 1} · ${active.name}`;"),
    ("No figures yet</p>", "Brak figur</p>"),
    ("numEl.textContent = 'Fig —';", "numEl.textContent = 'Rys. —';"),
    # czas figur przez __isoCzas (iso_jarvo.js): w przeglądarce zwykłe zegary, w renderze zegar wirtualny
    ("after: (ms, fn) => { const t = setTimeout(fn, ms);", "after: (ms, fn) => { const t = __isoCzas.after(fn, ms);"),
    ("every: (ms, fn) => { const t = setInterval(fn, ms);", "every: (ms, fn) => { const t = __isoCzas.every(fn, ms);"),
    ("fn(ts); requestAnimationFrame(f); };\n      requestAnimationFrame(f);",
     "fn(ts); __isoCzas.raf(f); };\n      __isoCzas.raf(f);"),
    ("clearTimeout(el._f1); clearTimeout(el._f2);\n      el._f1 = setTimeout(() => el.classList.remove('down'), 110); "
     "el._f2 = setTimeout(() => el.classList.remove('lit'), ms); },",
     "__isoCzas.clear(el._f1); __isoCzas.clear(el._f2);\n      el._f1 = __isoCzas.after(() => el.classList.remove('down'), 110); "
     "el._f2 = __isoCzas.after(() => el.classList.remove('lit'), ms); },"),
    ("power: on => { holder.classList.toggle('glow', !!on); },",
     "power: on => { holder.classList.toggle('glow', !!on); },\n"
     "    now: () => __isoCzas.now(),                 // Jarvo: czas strony w ms (w renderze wirtualny)\n"
     "    clear: id => __isoCzas.clear(id),           // Jarvo: zdejmij uchwyt z after / every"),
    ("timers.forEach(t => { clearTimeout(t); clearInterval(t); }); timers = [];",
     "timers.forEach(t => __isoCzas.clear(t)); timers = [];"),
    ("if (runDemo && handle.demo) setTimeout(() => handle.demo(), 120);",
     "if (runDemo && handle.demo) api.after(120, () => handle.demo());"),
    ("let saved = null; try { saved = localStorage.getItem(",
     "let saved = window.ISO_JARVO.akcent ? String(window.ISO_JARVO.akcent).toLowerCase() : null; "
     "if (!saved) try { saved = localStorage.getItem("),
    ("const start = FIGS.findIndex(f => f.id === location.hash.slice(1));",
     "const start = FIGS.findIndex(f => f.id === (location.hash.slice(1) || window.ISO_JARVO.figura));\n"
     "  window.__isoMount = () => mount(idx);\n"
     "  window.__isoFigury = () => FIGS.map(f => ({ id: f.id, name: f.name }));"),
    ("</style>\n</head>", KADR_CSS + "</style>\n</head>"),
]

# kontrola figur: (kod, wzorzec, komunikat); bledy blokują budowę, uwagi tylko mówią
BLEDY = [
    ("skrypt", re.compile(r"</script", re.I), "„</script” w kodzie figury zamyka stronę; rozbij napis ('<' + '/script')"),
    ("adres", re.compile(r"https?://(?!www\.w3\.org/)[^\s'\"`)]+"), "zewnętrzny adres: strona ma działać z dysku, bez sieci"),
    ("siec", re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts)\b|\bimport\s*\("),
     "pobieranie z sieci w figurze"),
    ("eval", re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|document\.write"), "eval / new Function / document.write"),
    ("kolor", re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\s*\("),
     "kolor wpisany na sztywno: tylko tokeny (var(--accent), var(--line)…), inaczej paleta marki i jasny motyw się sypią"),
]
UWAGI = [
    ("czas", re.compile(r"\b(setTimeout|setInterval|requestAnimationFrame)\s*\(|\b(performance|Date)\.now\s*\(|\bnew\s+Date\s*\("),
     "czas spoza api: PNG i film tego nie przewiną; użyj api.after / api.every / api.loop(ts) / api.now()"),
    ("losowosc", re.compile(r"\bMath\.random\s*\("), "Math.random: każdy render inny; weź stały wzór albo ziarno"),
    ("pamiec", re.compile(r"\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b"), "figura nie zapisuje nic w przeglądarce"),
]
ID_FIGURY = re.compile(r"\bid\s*:\s*['\"]([^'\"]+)['\"]")
NAZWA_FIGURY = re.compile(r"\bname\s*:\s*['\"]([^'\"]+)['\"]")


class Blad(Exception):
    pass


# ---------------------------------------------------------------- kolory (czyste funkcje)

def _hex(s: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", s.strip())
    if not m:
        raise Blad(f"kolor {s!r}: podaj #RRGGBB")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _str(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def _miks(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _luminancja(rgb) -> float:
    def kanal(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a, b) -> float:
    la, lb = sorted((_luminancja(a), _luminancja(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _do_kontrastu(kolor, tlo, cel, ku) -> tuple:
    """Miesza kolor w stronę `ku` (biel/czerń), aż ma kontrast ≥ cel z tłem."""
    for i in range(0, 21):
        k = _miks(kolor, ku, i / 20)
        if kontrast(k, tlo) >= cel:
            return k
    return ku


def akcent_marki(spec: str, nr: int = 1) -> list[str]:
    """'#E4572E' | 'Nazwa=#E4572E' | 'Nazwa=#E4572E,#FFB27A' → [nazwa, ciemny, ciemny_hi, jasny, jasny_hi].
    Kolor marki zostaje, chyba że ginie na panelu: wtedy jaśniejszy (ciemny motyw) albo ciemniejszy (jasny)."""
    nazwa, _, kolory = spec.rpartition("=")
    nazwa = nazwa.strip() or ("Marka" if nr == 1 else f"Marka {nr}")
    if not re.fullmatch(r"[\w ąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]{1,24}", nazwa):
        raise Blad(f"nazwa koloru {nazwa!r}: litery, cyfry, spacje (do 24)")
    czesci = [c for c in kolory.split(",") if c.strip()]
    if not 1 <= len(czesci) <= 2:
        raise Blad(f"akcent {spec!r}: jeden albo dwa kolory (#akcent,#jaśniejszy)")
    a = _hex(czesci[0])
    biel, czern = (255, 255, 255), (0, 0, 0)
    ciemny = _do_kontrastu(a, _hex(PANEL["ciemny"]), 3.0, biel)
    ciemny_hi = _hex(czesci[1]) if len(czesci) == 2 else _miks(ciemny, biel, 0.45)
    jasny = _do_kontrastu(a, _hex(PANEL["jasny"]), 3.0, czern)
    jasny_hi = _miks(jasny, biel, 0.18)
    return [nazwa, _str(ciemny), _str(ciemny_hi), _str(jasny), _str(jasny_hi)]


# ---------------------------------------------------------------- kontrola figur (bez przeglądarki)

def _bez_komentarzy(js: str) -> str:
    """Kod bez komentarzy (/* */ i // do końca linii poza napisami) — tak, żeby numery linii się zgadzały."""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c in "'\"`":
            j = i + 1
            while j < n and js[j] != c:
                j += 2 if js[j] == "\\" else 1
            out.append(js[i:j + 1])
            i = j + 1
        elif js.startswith("/*", i):
            j = js.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", js[i:j]))
            i = j
        elif js.startswith("//", i) and (i == 0 or js[i - 1] != ":"):
            j = js.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def kontrola(js: str, plik: str = "figura") -> dict:
    """Błędy (blokują budowę) i uwagi dla kodu figur (jeden plik z jednym albo kilkoma FIGS.push)."""
    kod = _bez_komentarzy(js)
    bledy, uwagi = [], []
    if "FIGS.push(" not in kod:
        bledy.append({"kod": "brak-figury", "plik": plik, "linia": 1, "opis": "brak FIGS.push({...}): to nie jest figura"})
    for lista, cel in ((BLEDY, bledy), (UWAGI, uwagi)):
        for k, wz, opis in lista:
            for m in wz.finditer(kod):
                linia = kod.count("\n", 0, m.start()) + 1
                cel.append({"kod": k, "plik": plik, "linia": linia, "opis": opis, "fragment": m.group(0)[:40]})
    ile_figur = kod.count("FIGS.push(")
    if ile_figur and kod.count("aria:") < ile_figur:
        uwagi.append({"kod": "aria", "plik": plik, "linia": 1, "opis": "figura bez aria: opisz, co to jest i jak tego użyć"})
    if ile_figur and len(re.findall(r"\bdemo\s*(\(|:)", kod)) < ile_figur:
        uwagi.append({"kod": "demo", "plik": plik, "linia": 1,
                      "opis": "figura bez demo(): film i PNG pokażą ją bez ruchu, a strona nie otworzy się zapalona"})
    return {"bledy": bledy, "uwagi": uwagi, "figury": figury_w_kodzie(kod)}


def figury_w_kodzie(js: str) -> list[dict]:
    """[{id, nazwa}] z kolejnych FIGS.push (pierwsze id: i name: po każdym)."""
    out = []
    for kawalek in js.split("FIGS.push(")[1:]:
        i, n = ID_FIGURY.search(kawalek), NAZWA_FIGURY.search(kawalek)
        out.append({"id": i.group(1) if i else "", "nazwa": n.group(1) if n else ""})
    return out


def figury_ze_strony(strona: str) -> str:
    """Kod figur ze zbudowanej strony (skrypty między komentarzem FIGURES a CORE szablonu)."""
    a, b = strona.find(FIGURY_OD), strona.find(FIGURY_DO)
    if a < 0 or b < 0:
        raise Blad("to nie jest strona z iso.py zbuduj (brak znaczników FIGURES / CORE szablonu)")
    a = strona.find("-->", a) + 3                  # sam komentarz FIGURES też mówi „<script>” i „FIGS.push”
    return "\n".join(re.findall(r"<script>(.*?)</script>", strona[a:b], re.S))


# ---------------------------------------------------------------- budowa strony

def _kroj_css() -> str:
    for d in KROJE:
        if all((d / f).exists() for f in KROJ):
            lacinka, ext = ((d / f).read_bytes() for f in KROJ)
            zakres = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, "
                      "U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD", "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, "
                      "U+02CE-02D7, U+02DD-02FF, U+1E00-1E9F, U+2020, U+20A0-20AB, U+20AD-20C0, U+2C60-2C7F, U+A720-A7FF")
            css = "".join(
                f'@font-face{{font-family:"JetBrains Mono";font-style:normal;font-weight:100 800;font-display:swap;'
                f'src:url(data:font/woff2;base64,{base64.b64encode(b).decode()}) format("woff2");unicode-range:{z}}}'
                for b, z in ((lacinka, zakres[0]), (ext, zakres[1])))
            return f"<style>/* JetBrains Mono, SIL OFL 1.1 (JetBrains) */{css}</style>"
    raise Blad("brak kroju JetBrains Mono (hq/web/fonts/kroje albo scripts/kroje); użyj --kroj systemowy")


def _js_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def zbuduj(figury: list[tuple[str, str]], tytul: str = "Figury", paleta: str | list = "ember", motyw: str = "auto",
           kadr: bool = False, podpis: bool = False, demo: bool = False, stopka: bool = True, kroj: str = "osadz",
           szablon: Path = SZABLON) -> tuple[str, dict]:
    """figury = [(nazwa pliku, kod JS)] → (strona HTML, raport kontroli). Błędy kontroli → Blad."""
    if not figury:
        raise Blad("podaj co najmniej jeden plik figury (.js z FIGS.push)")
    raport = {"bledy": [], "uwagi": [], "figury": []}
    for plik, js in figury:
        k = kontrola(js, plik)
        for klucz in raport:
            raport[klucz] += k[klucz]
    ids = [f["id"] for f in raport["figury"]]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        raport["bledy"].append({"kod": "id", "plik": "", "linia": 0, "opis": f"id figury {i!r} użyte dwa razy"})
    if raport["bledy"]:
        raise Blad("kontrola figur: " + "; ".join(f"{b['plik']}:{b['linia']} {b['opis']}" for b in raport["bledy"][:8]))
    if motyw not in MOTYWY:
        raise Blad(f"motyw {motyw!r} spoza {MOTYWY}")
    if isinstance(paleta, str) and paleta not in PALETY:
        raise Blad(f"paleta {paleta!r} spoza {PALETY} (albo --akcent z kolorem marki)")
    s = szablon.read_text(encoding="utf-8")
    ustawienia = {"kadr": kadr, "podpis": podpis, "motyw": motyw}
    glowa = ZNACZNIK.sub(lambda m: f"/*ISO_JARVO*/{_js_json(ustawienia)}/*ISO_JARVO*/",
                         GLOWA_JS.read_text(encoding="utf-8"), count=1)
    t = html.escape(tytul, quote=False)
    zamiany = list(ZAMIANY_STALE) + [
        ('<meta charset="utf-8">', '<meta charset="utf-8">\n<script>\n' + glowa.replace("</", "<\\/") + "</script>"),
        ("<title>Iso Figures</title>", f"<title>{t}</title>"),
        (GOOGLE_FONTS, _kroj_css() if kroj == "osadz" else ""),
        ("Iso figures</span>", f"{t}</span>"),
        ("window.GALLERY = { palette: 'ember', autoDemo: false, storageKey: 'iso-glow-accent' };",
         f"window.GALLERY = {{ palette: {_js_json(paleta)}, autoDemo: {'true' if demo else 'false'} || !!window.ISO_JARVO.demo, "
         "storageKey: 'jarvo-iso-akcent' };"),
        ("/* paste figure scripts here (see examples/) */",
         "\n</script>\n<script>\n".join(f"/* {Path(p).name} */\n{js.strip()}" for p, js in figury)),
    ]
    if not stopka:
        zamiany.append((STOPKA, ""))
    for stare, nowe in zamiany:
        ile = s.count(stare)
        if ile != 1:
            raise Blad(f"szablon iso-glow: {stare[:60]!r} występuje {ile}× (nowa wersja upstreamu? przejrzyj ZAMIANY w iso.py)")
        s = s.replace(stare, nowe, 1)
    return s, raport


# ---------------------------------------------------------------- przeglądarka (iso_render.cjs) i film (html_wideo.py)

def _rozmiar(s: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{2,5})x(\d{2,5})", s.strip().lower())
    if not m:
        raise Blad(f"rozmiar {s!r}: SZERxWYS, np. 1600x1200")
    return int(m.group(1)), int(m.group(2))


def _url(strona: Path, **q) -> str:
    from urllib.parse import urlencode
    query = {k: ("1" if v is True else v) for k, v in q.items() if v not in (None, False, "")}
    return strona.resolve().as_uri() + ("?" + urlencode(query) if query else "")


def _node(zadanie: dict) -> dict:
    node = shutil.which("node")
    if not node:
        raise Blad("brak node (w kontenerze Jarva jest w obrazie)")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(zadanie, f)
    try:
        p = subprocess.run([node, str(RENDER_JS), f.name], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(f.name)
    if p.returncode:
        raise Blad((p.stderr or p.stdout).strip()[-800:] or "iso_render.cjs: błąd")
    return json.loads(p.stdout.strip().splitlines()[-1])


def nazwy_png(out: Path, ids: list[str]) -> list[Path]:
    """Jedna figura → out; kilka → out-<id>.png obok."""
    if len(ids) == 1:
        return [out]
    return [out.with_name(f"{out.stem}-{i}{out.suffix or '.png'}") for i in ids]


def png(strona: Path, out: Path, figury: list[str] | None, czas: float, rozmiar: tuple[int, int], skala: float,
        motyw: str, akcent: str | None, alfa: bool, podpis: bool) -> dict:
    if not strona.exists():
        raise Blad(f"brak pliku {strona}")
    ids = figury or [""]
    out.parent.mkdir(parents=True, exist_ok=True)
    zadania = [{"url": _url(strona, render=True, figura=i or None, motyw=motyw, akcent=akcent, tlo=None if not alfa else "0",
                            podpis=podpis, demo=czas > 0),
                "out": str(o.resolve()), "w": rozmiar[0], "h": rozmiar[1], "skala": skala, "czas": czas, "alfa": alfa}
               for i, o in zip(ids, nazwy_png(out, ids))]
    return _node({"tryb": "png", "zadania": zadania})


def lista_figur(strona: Path) -> list[dict]:
    return figury_w_kodzie(_bez_komentarzy(figury_ze_strony(strona.read_text(encoding="utf-8"))))


def html_wideo() -> Path:
    dom = os.environ.get("HERMES_HOME")
    kandydaci = [os.environ.get("JARVO_HTML_WIDEO"), str(Path(dom) / "scripts" / "html_wideo.py") if dom else None]
    if REPO:
        kandydaci.append(str(REPO / "profiles" / "jarvo-wideo" / "scripts" / "html_wideo.py"))
    for k in filter(None, kandydaci):
        if Path(k).exists():
            return Path(k)
    raise Blad("film robi Wideograf (html_wideo.py): zleć mu `iso.py wideo` z tą stroną")


def polecenie_wideo(strona: Path, out: Path, figura: str | None, dlugosc: float, fps: float, rozmiar: tuple[int, int],
                    motyw: str, podpis: bool, rownolegle: int | None, skrypt: Path) -> list[str]:
    from urllib.parse import urlencode
    q = {"demo": "1", "motyw": motyw, **({"figura": figura} if figura else {}), **({"podpis": "1"} if podpis else {})}
    cmd = [sys.executable, str(skrypt), "wideo", str(strona), "--preset", "jarvo", "--query", urlencode(q),
           "--dlugosc", f"{dlugosc:g}", "--fps", f"{fps:g}", "--rozmiar", f"{rozmiar[0]}x{rozmiar[1]}", "-o", str(out)]
    if rownolegle:
        cmd += ["--rownolegle", str(rownolegle)]
    return cmd


# ---------------------------------------------------------------- CLI

def _wypisz_kontrole(r: dict) -> None:
    for b in r["bledy"]:
        print(f"✗ {b['plik']}:{b['linia']} [{b['kod']}] {b['opis']}" + (f" ({b['fragment']})" if b.get("fragment") else ""))
    for u in r["uwagi"]:
        print(f"! {u['plik']}:{u['linia']} [{u['kod']}] {u['opis']}" + (f" ({u['fragment']})" if u.get("fragment") else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("zbuduj", help="figury .js → jedna strona HTML (działa z dysku, bez sieci)")
    b.add_argument("figury", nargs="+", type=Path)
    b.add_argument("-o", "--wyjscie", type=Path, required=True)
    b.add_argument("--tytul", default="Figury")
    b.add_argument("--paleta", choices=PALETY, default="ember", help="ember (ciepłe, przedmioty) | city (miasto, budynki)")
    b.add_argument("--akcent", action="append", default=[], help="kolor marki: '#E4572E', 'Nazwa=#E4572E[,#jaśniejszy]' "
                   "(kilka razy = kilka kolorów do wyboru); zastępuje paletę")
    b.add_argument("--motyw", choices=MOTYWY, default="auto")
    b.add_argument("--kadr", action="store_true", help="sama figura na całej stronie (osadzenie w <iframe> na stronie klienta)")
    b.add_argument("--podpis", action="store_true", help="w kadrze także „Rys. N · nazwa” i odczyt")
    b.add_argument("--demo", action="store_true", help="figura od razu odgrywa demo() (otwiera się zapalona)")
    b.add_argument("--bez-stopki", action="store_true", help="bez „Made with ISO-GLOW” (prace dla klientów)")
    b.add_argument("--kroj", choices=["osadz", "systemowy"], default="osadz",
                   help="osadz = JetBrains Mono w pliku (~75 KB, polskie znaki), systemowy = krój mono systemu")
    s = sub.add_parser("sprawdz", help="kontrola figur (.js albo zbudowanej strony)")
    s.add_argument("plik", type=Path)
    s.add_argument("--przegladarka", action="store_true", help="też w Chromium: każda figura, demo, błędy JS, tekst poza kadrem")
    s.add_argument("--czas", type=float, default=3.0, help="sekundy demo w kontroli przeglądarką")
    s.add_argument("--json", action="store_true")
    f = sub.add_parser("figury", help="id i nazwy figur na stronie")
    f.add_argument("strona", type=Path)
    p = sub.add_parser("png", help="figura → PNG w chwili t (zegar strony)")
    p.add_argument("strona", type=Path)
    p.add_argument("-o", "--wyjscie", type=Path, required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--figura", action="append", help="id figury (kilka razy = kilka PNG); domyślnie pierwsza")
    g.add_argument("--wszystkie", action="store_true", help="każda figura osobno (seria ikon): <nazwa>-<id>.png")
    p.add_argument("--czas", type=float, default=0.0, help="sekunda demo (0 = stan startowy bez demo)")
    p.add_argument("--rozmiar", default="1600x1200", help="SZERxWYS: 1080x1080 post, 1080x1350 IG, 1200x630 OG")
    p.add_argument("--skala", type=float, default=1.0, help="gęstość pikseli (2 = ostrzej)")
    p.add_argument("--motyw", choices=MOTYWY, default="ciemny")
    p.add_argument("--akcent", help="nazwa koloru z palety strony (np. cyan, marka)")
    p.add_argument("--przezroczyste", action="store_true", help="PNG bez tła (ikony na stronę, nakładki)")
    p.add_argument("--podpis", action="store_true")
    w = sub.add_parser("wideo", help="figura z demo() → film (html_wideo.py Wideografa)")
    w.add_argument("strona", type=Path)
    w.add_argument("-o", "--wyjscie", type=Path, required=True)
    w.add_argument("--figura")
    w.add_argument("--dlugosc", type=float, default=6.0)
    w.add_argument("--fps", type=float, default=30.0)
    w.add_argument("--rozmiar", default="1920x1080", help="1920x1080 poziom, 1080x1920 rolka, 1080x1080 kwadrat")
    w.add_argument("--motyw", choices=MOTYWY, default="ciemny")
    w.add_argument("--podpis", action="store_true")
    w.add_argument("--rownolegle", type=int)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "zbuduj":
            paleta = [akcent_marki(x, i + 1) for i, x in enumerate(a.akcent)] if a.akcent else a.paleta
            figury = []
            for plik in a.figury:
                if not plik.exists():
                    raise Blad(f"brak pliku {plik}")
                figury.append((str(plik), plik.read_text(encoding="utf-8")))
            strona, r = zbuduj(figury, a.tytul, paleta, a.motyw, a.kadr, a.podpis, a.demo, not a.bez_stopki, a.kroj)
            a.wyjscie.parent.mkdir(parents=True, exist_ok=True)
            a.wyjscie.write_text(strona, encoding="utf-8")
            _wypisz_kontrole(r)
            print(json.dumps({"strona": str(a.wyjscie), "kb": round(len(strona.encode()) / 1024, 1),
                              "figury": r["figury"], "uwag": len(r["uwagi"]),
                              "paleta": paleta if isinstance(paleta, str) else [x[0] for x in paleta],
                              "stopka": not a.bez_stopki}, ensure_ascii=False))
            return 0
        if a.cmd == "figury":
            print(json.dumps(lista_figur(a.strona), ensure_ascii=False))
            return 0
        if a.cmd == "sprawdz":
            tekst = a.plik.read_text(encoding="utf-8")
            strona = a.plik.suffix.lower() in (".html", ".htm")
            r = kontrola(figury_ze_strony(tekst) if strona else tekst, a.plik.name)
            if a.przegladarka:
                if not strona:
                    raise Blad("--przegladarka: podaj zbudowaną stronę (.html z iso.py zbuduj)")
                r["przegladarka"] = _node({"tryb": "sprawdz", "url": _url(a.plik, render=True), "czas": a.czas})
                for fig in r["przegladarka"]["figury"]:
                    for e in fig["bledy"]:
                        r["bledy"].append({"kod": "js", "plik": fig["id"], "linia": 0, "opis": e[:300]})
                    if fig["start"]["elementow"] < 5:
                        r["bledy"].append({"kod": "pusta", "plik": fig["id"], "linia": 0, "opis": "figura nic nie narysowała"})
                    for t in fig["po_demo"]["poza"]:
                        r["uwagi"].append({"kod": "poza-kadrem", "plik": fig["id"], "linia": 0,
                                           "opis": f"tekst wychodzi poza kadr: {t!r} (dodaj punkt do iso.frame)"})
                    maly = fig["po_demo"]["najmniejszy_tekst_px"]
                    if maly is not None and maly < MIN_TEKST_PX:
                        r["uwagi"].append({"kod": "maly-tekst", "plik": fig["id"], "linia": 0,
                                           "opis": f"najmniejszy tekst {maly} px przy 1600×1200 (na stronie ~3× mniej): "
                                                   f"powiększ font-size albo zrezygnuj z napisu"})
                    if fig["po_demo"]["swieci"] == 0:
                        r["uwagi"].append({"kod": "ciemno", "plik": fig["id"], "linia": 0,
                                           "opis": f"po {a.czas:g} s demo nic nie świeci (.hot/.lit/.latched): film będzie martwy"})
                r["bledy"] += [{"kod": "js", "plik": "strona", "linia": 0, "opis": e[:300]}
                               for e in r["przegladarka"]["bledy"]]
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=2))
            else:
                for fig in (r.get("przegladarka") or {}).get("figury", []):
                    po = fig["po_demo"]
                    print(f"  {fig['id']}: {po['elementow']} elementów, świeci {po['swieci']}, najmniejszy tekst "
                          f"{po['najmniejszy_tekst_px']} px, odczyt „{po['odczyt']}”")
                _wypisz_kontrole(r)
                print(f"{'✗' if r['bledy'] else '✓'} {a.plik.name}: {len(r['figury'])} figur, "
                      f"{len(r['bledy'])} błędów, {len(r['uwagi'])} uwag")
            return 1 if r["bledy"] else 0
        if a.cmd == "png":
            ids = [f["id"] for f in lista_figur(a.strona)] if a.wszystkie else a.figura
            wynik = png(a.strona, a.wyjscie, ids, a.czas, _rozmiar(a.rozmiar), a.skala, a.motyw, a.akcent,
                        a.przezroczyste, a.podpis)
            for e in wynik["bledy"]:
                print(f"! strona: {e[:300]}", file=sys.stderr)
            print(json.dumps(wynik, ensure_ascii=False))
            return 1 if wynik["bledy"] else 0
        if a.cmd == "wideo":
            cmd = polecenie_wideo(a.strona, a.wyjscie, a.figura, a.dlugosc, a.fps, _rozmiar(a.rozmiar), a.motyw,
                                  a.podpis, a.rownolegle, html_wideo())
            return subprocess.run(cmd).returncode
    except Blad as e:
        print(f"iso: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())

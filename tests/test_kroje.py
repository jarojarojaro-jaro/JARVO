"""Kroje OFL do napisów i typografii: pliki z sumami, kroje.css, lista w edytorze i CSS z data: URL dla renderu."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hq" / "plugin"))
import edytor as ed  # noqa: E402

spec = importlib.util.spec_from_file_location("kroje", ROOT / "scripts" / "kroje.py")
kroje = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kroje)


def test_pliki_sumy_i_css_zgodne():
    assert kroje.bledy() == []


def test_kazdy_krój_ma_polskie_znaki_i_licencje():
    for k in kroje.KROJE:
        subs = {sub for kk, _n, _w, _s, sub, _r in kroje.pliki() if kk is k}
        assert subs == {"latin", "latin-ext"}, k["family"]
        lic = (kroje.DIR / kroje.licencja(k)).read_text(encoding="utf-8", errors="replace")
        assert "SIL OPEN FONT LICENSE" in lic.upper(), k["family"]


def test_lista_krojow_edytora_ma_pliki():
    js = (ROOT / "hq" / "web" / "src" / "44-napisy.js").read_text(encoding="utf-8")
    lista = js[js.index("const ED_FONTS"):js.index("];", js.index("const ED_FONTS"))]
    pierwsze = re.findall(r'\[\s*"([^"]+)"', lista)
    rodziny = {k["family"] for k in kroje.KROJE}
    systemowe = {"system-ui", "Georgia"}
    for css_font in pierwsze:
        glowna = css_font.split(",")[0].strip().strip("'\"")
        assert glowna in rodziny or glowna in systemowe, glowna


def _grubosci(family: str, styl: str) -> list[tuple[int, int]]:
    """Zakresy grubości plików kroju w danym stylu (np. [(100, 900)] albo [(500, 500), (800, 800)])."""
    k = next(k for k in kroje.KROJE if k["family"] == family)
    return [(int(w.split()[0]), int(w.split()[-1])) for _stem, w, st in k["faces"] if st == styl]


def test_kazdy_krój_do_wyboru_w_edytorze_bez_sztucznego_pogrubienia():
    """Każdy pobrany krój jest na liście zwykłych napisów (ED_FONTS) i typografii (TYPO_KROJE), a grubości z list
    mają swój plik: krój z jedną grubością nie dostaje 800 (przeglądarka pogrubiłaby go sztucznie)."""
    js = (ROOT / "hq" / "web" / "src" / "44-napisy.js").read_text(encoding="utf-8")
    lista = js[js.index("const ED_FONTS"):js.index("];", js.index("const ED_FONTS"))]
    wiersze = re.findall(r'\[\s*"([^"]+)", "([^"]+)", "(\w+)", (\d+), (\d+)\]', lista)
    assert wiersze and wiersze[0][0].startswith("system-ui")              # domyślny krój napisu bez zmian
    glowne = {w[0].split(",")[0].strip("'\" ") for w in wiersze}
    rodziny = {k["family"] for k in kroje.KROJE}
    assert rodziny <= glowne, rodziny - glowne
    grupy = [w[2] for w in wiersze]
    assert grupy == sorted(grupy, key=grupy.index) and len(set(grupy)) == 8    # każda grupa w jednym kawałku
    for css_font, _n, _g, bold, zwykly in wiersze:
        rodzina = css_font.split(",")[0].strip("'\" ")
        if rodzina in rodziny:
            for waga in (int(bold), int(zwykly)):
                assert any(a <= waga <= b for a, b in _grubosci(rodzina, "normal")), (rodzina, waga)
    typo = (ROOT / "hq" / "web" / "src" / "48-typografia.js").read_text(encoding="utf-8")
    tk = re.findall(r'^  \w+: \["\'([^\']+)\'[^"]*", (\d+), (true|false), "[^"]+", "(\w+)"\],', typo, re.M)
    assert len(tk) == len(ed.TYPO_KROJE) and {r for r, *_ in tk} == rodziny
    for rodzina, waga, kursywa, _g in tk:
        assert any(a <= int(waga) <= b for a, b in _grubosci(rodzina, "italic" if kursywa == "true" else "normal")), rodzina


def test_style_css_laduje_kroje_lokalnie():
    css = (ROOT / "hq" / "web" / "style.css").read_text(encoding="utf-8")
    assert '@import url("fonts/kroje/kroje.css");' in css
    assert css.index("fonts/kroje/kroje.css") < css.index("{")    # @import przed pierwszą regułą


def test_kroje_css_z_data_url():
    out = ed.kroje_css(kroje.DIR)
    assert out.count("@font-face") == len(kroje.pliki())
    assert out.count("url(data:font/woff2;base64,") == len(kroje.pliki())
    assert ed.kroje_css(None) == "" and ed.kroje_css(ROOT / "nie-ma") == ""
    tylko = ed.kroje_css(kroje.DIR, {"Anton", "Kanit"})                 # render: tylko kroje projektu
    assert tylko.count("@font-face") == 6 and 'font-family: "Anton"' in tylko and "Bebas" not in tylko
    assert ed.kroje_css(kroje.DIR, set()).count("@font-face") == 0


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_render_wybiera_kroje_projektu():
    """RODZINY_JS (projekt.strona) liczy rodziny tą samą funkcją wyboru kroju co rysowanie: napisy i typografia."""
    src = (ROOT / "profiles" / "jarvo-wideo" / "scripts" / "projekt.py").read_text(encoding="utf-8")
    rodziny_js = re.search(r'RODZINY_JS = """(.*?)"""', src, re.S).group(1)
    js = "".join((ROOT / "hq" / "web" / "src" / f).read_text(encoding="utf-8") + "\n" for f in ("44-napisy.js", "48-typografia.js"))
    plany = [{"texts": [{"text": "Zażółć", "font": "'Bungee', Impact, sans-serif"}, {"text": "x"}]},
             {"typo": {"motyw": "podcast", "bloki": [{"id": "b1", "start": 0, "end": 1, "slowa": [
                 {"t": 0, "tekst": "a", "waga": 1}, {"t": 0, "tekst": "b", "waga": 0}, {"t": 0, "tekst": "c", "waga": 1, "kroj": "bubbles"}]}]}}]
    r = subprocess.run(["node", "-e", js + f"\nconsole.log(JSON.stringify(({rodziny_js})({json.dumps(plany)}).sort()));"],
                       capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == ["Bungee", "Montserrat", "Rubik Bubbles", "system-ui"]


def test_render_agenta_bez_google_fonts():
    src = (ROOT / "profiles" / "jarvo-wideo" / "scripts" / "projekt.py").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in src and "kroje_css(KROJE, rodziny)" in src
    assert "fontLoad(textFont(t, H, W).font, t.text)" in src
    build = (ROOT / "scripts" / "build.py").read_text(encoding="utf-8")
    assert '"fonts" / "kroje", dest / "scripts" / "kroje"' in build


# Mapa znaków (cmap) z pliku woff2: tabele są skompresowane Brotli (node ma go w zlib, Python w stdlib nie),
# cmap nie ma transformacji, więc wystarczy katalog tabel i format 4/12. Sam podzbiór latin-ext w nazwie pliku
# nie wystarcza: Lilita One i Fredoka miały latin-ext bez „ą”, „ę”, „ś” (przeglądarka brała krój zastępczy).
CMAP_JS = r"""
const fs = require("fs"), zlib = require("zlib");
function cmap(buf) {
  let o = 12; const n = buf.readUInt16BE(o); o = 48;
  const b128 = () => { let v = 0; for (let i = 0; i < 5; i++) { const x = buf[o++]; v = v * 128 + (x & 127); if (!(x & 128)) return v; } };
  const dir = [];
  for (let i = 0; i < n; i++) {
    const f = buf[o++], tag = f & 63, ver = f >> 6;
    if (tag === 63) o += 4;
    const orig = b128(), tr = (tag === 10 || tag === 11) ? ver === 0 : ver !== 0;
    dir.push({ tag, len: tr ? b128() : orig });
  }
  const data = zlib.brotliDecompressSync(buf.subarray(o, o + buf.readUInt32BE(20)));
  let p = 0, t = null;
  for (const d of dir) { if (d.tag === 0) t = data.subarray(p, p + d.len); p += d.len; }
  const out = new Set(), recs = t.readUInt16BE(2);
  for (let r = 0; r < recs; r++) {
    const s = t.subarray(t.readUInt32BE(4 + r * 8 + 4)), fmt = s.readUInt16BE(0);
    if (fmt === 4) {
      const seg = s.readUInt16BE(6) / 2;
      for (let i = 0; i < seg; i++) {
        const end = s.readUInt16BE(14 + i * 2), start = s.readUInt16BE(16 + seg * 2 + i * 2);
        const delta = s.readInt16BE(16 + seg * 4 + i * 2), roOff = 16 + seg * 6 + i * 2, ro = s.readUInt16BE(roOff);
        for (let c = start; c <= end && c !== 0xffff; c++) {
          const g = ro ? s.readUInt16BE(roOff + ro + (c - start) * 2) : (c + delta) & 0xffff;
          if (g) out.add(c);
        }
      }
    } else if (fmt === 12) {
      for (let i = 0, k = s.readUInt32BE(12); i < k; i++) for (let c = s.readUInt32BE(16 + i * 12); c <= s.readUInt32BE(20 + i * 12); c++) out.add(c);
    }
  }
  return [...out];
}
const wynik = {};
for (const f of process.argv.slice(1)) wynik[f] = cmap(fs.readFileSync(f));
console.log(JSON.stringify(wynik));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_kazdy_kroj_ma_polskie_glify():
    pliki = [kroje.DIR / name for _k, name, *_ in kroje.pliki()]
    r = subprocess.run(["node", "-e", CMAP_JS, *map(str, pliki)], capture_output=True, text=True, check=True)
    mapy = json.loads(r.stdout)
    for k in kroje.KROJE:
        for stem, _w, _st in k["faces"]:
            znaki = set().union(*(mapy[str(kroje.DIR / f"{stem.format(s=sub)}.woff2")] for sub in ("latin", "latin-ext")))
            brak = [ch for ch in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ" if ord(ch) not in znaki]
            assert not brak, f"{k['family']} ({stem}): brak {''.join(brak)}"


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_napis_bierze_grubosc_z_listy_krojow():
    js = (ROOT / "hq" / "web" / "src" / "44-napisy.js").read_text(encoding="utf-8")
    prog = js + """
const f = (font, bold) => textFont({ font, bold, size: 64 }, 1920, 1080).font.split(" ")[0];
console.log(JSON.stringify([f("'Anton', Impact, sans-serif"), f("'Anton', Impact, sans-serif", false),
  f("'Barlow Condensed', 'Arial Narrow', sans-serif", false), f("'Nowy Krój', serif"), f("'Nowy Krój', serif", false), f(undefined)]));"""
    r = subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == ["400", "400", "600", "800", "500", "800"]

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


def test_style_css_laduje_kroje_lokalnie():
    css = (ROOT / "hq" / "web" / "style.css").read_text(encoding="utf-8")
    assert '@import url("fonts/kroje/kroje.css");' in css
    assert css.index("fonts/kroje/kroje.css") < css.index("{")    # @import przed pierwszą regułą


def test_kroje_css_z_data_url():
    out = ed.kroje_css(kroje.DIR)
    assert out.count("@font-face") == len(kroje.pliki())
    assert out.count("url(data:font/woff2;base64,") == len(kroje.pliki())
    assert ed.kroje_css(None) == "" and ed.kroje_css(ROOT / "nie-ma") == ""


def test_render_agenta_bez_google_fonts():
    src = (ROOT / "profiles" / "jarvo-wideo" / "scripts" / "projekt.py").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in src and "kroje_css(KROJE)" in src
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

"""Kroje OFL do napisów i typografii: pliki z sumami, kroje.css, lista w edytorze i CSS z data: URL dla renderu."""

import importlib.util
import re
import sys
from pathlib import Path

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

"""Branding dashboardu: nowe nazwy zmienionych plików (cache przeglądarki) i skórka terminala."""

from __future__ import annotations

import yaml

from conftest import REPO, load_script


def test_bust_cache_renames_changed_files_and_importers(tmp_path):
    pd = load_script("branding/patch_dashboard.py")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "i18n-AAAA11.js").write_text("export const brand = `TARS`;", encoding="utf-8")
    (assets / "page-BBBB22.js").write_text('import{b}from"./i18n-AAAA11.js";export default 1;', encoding="utf-8")
    (assets / "vendor-CCCC33.js").write_text("export const v = 1;", encoding="utf-8")
    (assets / "index-DDDD44.js").write_text('import"./page-BBBB22.js";const m=["assets/vendor-CCCC33.js"];', encoding="utf-8")
    index = tmp_path / "index.html"
    index.write_text('<script src="/assets/index-DDDD44.js"></script><link href="/assets/vendor-CCCC33.js">', encoding="utf-8")
    pd.CHANGED.clear()
    pd.CHANGED.add(assets / "i18n-AAAA11.js")
    assert pd.bust_cache(assets, index) == 3          # i18n + importujący ją page + importujący page index
    names = sorted(p.name for p in assets.iterdir())
    assert "vendor-CCCC33.js" in names                 # niezmieniony zostaje (cache dalej ważny)
    assert not any(n in names for n in ("i18n-AAAA11.js", "page-BBBB22.js", "index-DDDD44.js"))
    new_index = next(n for n in names if n.startswith("index-"))
    new_page = next(n for n in names if n.startswith("page-"))
    new_i18n = next(n for n in names if n.startswith("i18n-"))
    assert new_index in index.read_text(encoding="utf-8")
    assert new_page in (assets / new_index).read_text(encoding="utf-8")
    assert new_i18n in (assets / new_page).read_text(encoding="utf-8")
    assert "vendor-CCCC33.js" in (assets / new_index).read_text(encoding="utf-8")


def test_skin_and_profiles_use_tars_branding():
    skin = yaml.safe_load((REPO / "branding" / "skin-tars.yaml").read_text(encoding="utf-8"))
    assert skin["name"] == "tars" and skin["branding"]["agent_name"] == "TARS"
    for name in ["_host", "tars", "tars-sherlock", "tars-web", "tars-studio", "tars-reka"]:
        cfg = yaml.safe_load((REPO / "profiles" / name / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["display"]["skin"] == "tars", name
    ico = (REPO / "branding" / "favicon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00"                # prawdziwy plik ICO, nie SVG pod złą nazwą

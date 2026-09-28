"""Branding dashboardu: nowe nazwy zmienionych plików (cache przeglądarki) i skórka terminala."""

from __future__ import annotations

import yaml

from conftest import REPO, load_script


def test_bust_cache_renames_changed_files_and_importers(tmp_path):
    pd = load_script("branding/patch_dashboard.py")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "i18n-AAAA11.js").write_text("export const brand = `Jarvo`;", encoding="utf-8")
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
    assert skin["name"] == "tars" and skin["branding"]["agent_name"] == "Jarvo"
    for name in ["_host", "tars", "tars-sherlock", "tars-web", "tars-studio", "tars-reka"]:
        cfg = yaml.safe_load((REPO / "profiles" / name / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["display"]["skin"] == "tars", name
    ico = (REPO / "branding" / "favicon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00"                # prawdziwy plik ICO, nie SVG pod złą nazwą


FAKE_I18N = (
    "var s={af:`Afrikaans`,de:`Deutsch`,en:`English`};"
    "var d={common:{save:`Save`,cancel:`Cancel`},app:{nav:{sessions:`Sessions`}}},h={common:{save:`Speichern`}},"
    "k={en:d,zh:h,de:h},M=`hermes-locale`;"
    "function N(e){return Object.keys(k).includes(e)}"
    "function P(){try{let e=localStorage.getItem(M);if(e&&N(e))return e}catch{}return`en`}"
    "export{k as TR,P as initial};"
)


def test_add_polish_injects_locale_and_defaults(tmp_path):
    import json
    import subprocess

    pd = load_script("branding/patch_dashboard.py")
    chunk = tmp_path / "i18n-XYZ.mjs"
    chunk.write_text(FAKE_I18N, encoding="utf-8")
    index = tmp_path / "index.html"
    index.write_text('<html lang="en"><body></body></html>', encoding="utf-8")
    pl = tmp_path / "pl.json"
    pl.write_text(json.dumps({"common": {"save": "Zapisz"}, "app": {"nav": {"sessions": "Sesje"}}}), encoding="utf-8")
    pd.CHANGED.clear()
    assert pd.add_polish([chunk], index, pl) == 1
    assert pd.add_polish([chunk], index, pl) == 0            # drugi raz nic nie dopisuje
    assert 'lang="pl"' in index.read_text(encoding="utf-8")
    text = chunk.read_text(encoding="utf-8")
    assert "pl:`Polski`" in text
    # tłumaczenie scalone z angielskim: brakujący klucz = tekst angielski; polski domyślny bez wyboru
    probe = tmp_path / "probe.mjs"
    probe.write_text(
        f'import{{TR,initial}}from"./{chunk.name}";globalThis.localStorage={{getItem:()=>null}};'
        "console.log(JSON.stringify([TR.pl.common.save,TR.pl.common.cancel,TR.pl.app.nav.sessions,Object.keys(TR)[1],initial()]))",
        encoding="utf-8")
    out = subprocess.run(["node", str(probe)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["Zapisz", "Cancel", "Sesje", "pl", "pl"]


def test_polish_translation_covers_dashboard_sections():
    import json

    pl = json.loads((REPO / "branding" / "i18n" / "pl.json").read_text(encoding="utf-8"))
    for section in ("common", "app", "status", "sessions", "cron", "config", "env", "kanban", "achievements"):
        assert section in pl
    assert pl["app"]["nav"]["plugin_tars-hq"] == "Baza"
    # placeholdery zostają jak w oryginale
    assert "{count}" in pl["sessions"]["selectedCount"] and "{what}" in pl["common"]["loadFailed"]

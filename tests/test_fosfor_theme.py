"""Motywy Fosfor: jeden kolor → pełny motyw dashboardu Hermesa."""

import importlib.util
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_themes", REPO / "scripts" / "install_themes.py")
it = importlib.util.module_from_spec(spec)
spec.loader.exec_module(it)


def test_tokens_from_one_color():
    t = it.tokens("#89cff0")
    assert t["fos"] == "#89cff0"
    assert t["fos-bg"] == "#070a0c" and t["fos-lo"] == "#3e5d6c"


def test_install_writes_themes_and_sets_default(tmp_path):
    (tmp_path / "config.yaml").write_text("dashboard:\n  theme: default\nmodel: x\n", encoding="utf-8")
    assert it.main([str(REPO), str(tmp_path)]) == 0
    names = {p.stem for p in (tmp_path / "dashboard-themes").glob("*.yaml")}
    assert {"fosfor", "fosfor-bursztyn", "fosfor-zielen", "fosfor-biel"} <= names
    theme = yaml.safe_load((tmp_path / "dashboard-themes" / "fosfor.yaml").read_text(encoding="utf-8"))
    assert theme["palette"]["midground"] == "#89cff0"
    assert "--fos: #89cff0;" in theme["customCSS"] and len(theme["customCSS"]) < 32 * 1024
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["dashboard"]["theme"] == "fosfor" and cfg["model"] == "x"


def test_user_choice_is_kept(tmp_path):
    (tmp_path / "config.yaml").write_text("dashboard:\n  theme: fosfor-bursztyn\n", encoding="utf-8")
    it.main([str(REPO), str(tmp_path)])
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["dashboard"]["theme"] == "fosfor-bursztyn"


def test_fonts_are_bundled():
    css = (REPO / "hq" / "web" / "fonts" / "fosfor.css").read_text(encoding="utf-8")
    for name in ("VT323", "IBM Plex Mono"):
        assert name in css
    for ref in [l.split("url(")[1].split(")")[0] for l in css.splitlines() if "url(" in l]:
        assert (REPO / "hq" / "web" / "fonts" / ref).is_file()

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
    # drugi kolor do wyróżnień (cel karty): bursztyn, dla ciepłego fosforu błękit, albo z palety
    assert t["fos-alt"] == "#ffb000"
    assert it.tokens("#ffb000")["fos-alt"] == "#89cff0"
    assert it.tokens("#41ff7a", "#ff5577")["fos-alt"] == "#ff5577"


def test_install_writes_themes_and_sets_default(tmp_path):
    (tmp_path / "config.yaml").write_text("dashboard:\n  theme: default\nmodel: x\n", encoding="utf-8")
    assert it.main([str(REPO), str(tmp_path)]) == 0
    names = {p.stem for p in (tmp_path / "dashboard-themes").glob("*.yaml")}
    assert {"fosfor", "fosfor-bursztyn", "fosfor-zielen", "fosfor-biel"} <= names
    theme = yaml.safe_load((tmp_path / "dashboard-themes" / "fosfor.yaml").read_text(encoding="utf-8"))
    assert theme["palette"]["midground"] == "#89cff0"
    assert "--fos: #89cff0;" in theme["customCSS"] and len(theme["customCSS"]) < 32 * 1024
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["dashboard"]["theme"] == "jarvo" and cfg["model"] == "x"
    jarvo = yaml.safe_load((tmp_path / "dashboard-themes" / "jarvo.yaml").read_text(encoding="utf-8"))
    assert "--fos-line: #d4213d;" in jarvo["customCSS"] and "--fos: #f2f1e8;" in jarvo["customCSS"]
    assert jarvo["colorOverrides"]["primary"] == "#d4213d" and jarvo["palette"]["background"] == "#10131c"


def test_old_fosfor_switches_once_then_choice_is_kept(tmp_path):
    cfgp = tmp_path / "config.yaml"
    cfgp.write_text("dashboard:\n  theme: fosfor-biel\n", encoding="utf-8")
    it.main([str(REPO), str(tmp_path)])
    assert yaml.safe_load(cfgp.read_text(encoding="utf-8"))["dashboard"]["theme"] == "jarvo"
    cfgp.write_text("dashboard:\n  theme: fosfor-bursztyn\n", encoding="utf-8")   # użytkownik wrócił
    it.main([str(REPO), str(tmp_path)])
    assert yaml.safe_load(cfgp.read_text(encoding="utf-8"))["dashboard"]["theme"] == "fosfor-bursztyn"


def test_two_color_tokens():
    t = it.tokens("#F2F1E8", "#FF4D63", frame="#D4213D", fill="#D4213D", bg="#10131C")
    assert t["fos"] == "#f2f1e8" and t["fos-line"] == "#d4213d" and t["fos-fill-ink"] == "#f2f1e8"
    assert t["fos-bg"] == "#10131c" and "212, 33, 61" in t["fos-neon"]
    one = it.tokens("#89cff0")
    assert one["fos-neon"] == "transparent" and one["fos-fill"] == one["fos"] and one["fos-line"] == one["fos-mid"]


def test_fonts_are_bundled():
    css = (REPO / "hq" / "web" / "fonts" / "fosfor.css").read_text(encoding="utf-8")
    for name in ("VT323", "IBM Plex Mono"):
        assert name in css
    for ref in [l.split("url(")[1].split(")")[0] for l in css.splitlines() if "url(" in l]:
        assert (REPO / "hq" / "web" / "fonts" / ref).is_file()

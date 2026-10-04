"""zywy_schemat.py (Wideograf): formaty i motywy Jarva, strona z szablonu live-panel z krojami, film; `pomin` w buildzie."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-wideo" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
import zywy_schemat as zs  # noqa: E402

FLOTA = ROOT / "profiles" / "jarvo-wideo" / "skills" / "wideo" / "zywy-schemat" / "references" / "flota-jarva.json"
SZABLON = ('<!doctype html><html><head><style>#stage{}</style></head><body><div id="stage"></div>\n'
           '<!--LIVE_CONFIG-->\n<script>/* silnik */</script></body></html>')


def test_presets_expand_to_template_fields():
    cfg, uwagi = zs.rozwin({"canvas": {"preset": "ig", "duration": 20},
                            "theme": {"preset": "jarvo-jasny", "fontSize": 18, "colors": {"pk": "#000000"}},
                            "machines": {"seq": {"type": "cycle"}}})
    assert cfg["canvas"] == {"duration": 20, "width": 1080, "height": 1350}
    th = cfg["theme"]
    assert th["preset"] == "light-pastel" and th["fontSize"] == 18 and "Inter" in th["font"] and "opis" not in th
    assert th["colors"]["pk"] == "#000000" and th["colors"]["dim"] == "#5B6270"          # nadpisanie + kolor Jarva
    assert cfg["meta"]["lang"] == "pl"
    assert any("credit" in u for u in uwagi) and any("poglądow" in u for u in uwagi)
    cfg, uwagi = zs.rozwin({"canvas": {"preset": "4:5"}, "theme": {"preset": "terminal-dark"},
                            "credit": {"text": "Źródło: raport 2026"}, "machines": {"c": {}}})
    assert cfg["canvas"] == {"preset": "4:5"} and cfg["theme"] == {"preset": "terminal-dark"} and uwagi == []


def test_page_embeds_config_and_only_used_fonts(tmp_path):
    szablon = tmp_path / "template.html"
    szablon.write_text(SZABLON, encoding="utf-8")
    cfg = {"canvas": {"preset": "kwadrat"}, "theme": {"preset": "jarvo-ciemny"}, "credit": {"text": "liczby poglądowe"},
           "elements": [{"type": "text", "t": "</script><b>ż", "font": '"Space Grotesk", "Comic X", serif'}]}
    html, uwagi = zs.strona(cfg, szablon)
    assert '<script id="live-config" type="application/json">' in html and "<!--LIVE_CONFIG-->" not in html
    assert "<\\/script><b>ż" in html                                       # tekst nie zamyka znacznika skryptu
    rodziny = set(__import__("re").findall(r'font-family: "([^"]+)"', html))
    assert rodziny == {"JetBrains Mono", "Space Grotesk"} and "data:font/woff2;base64," in html
    assert any("Comic X" in u for u in uwagi)
    (tmp_path / "s.html").write_text(html, encoding="utf-8")
    assert zs.config_strony(tmp_path / "s.html")["canvas"] == {"width": 1080, "height": 1080}


def test_film_renders_with_preset_and_adds_silent_track(tmp_path, monkeypatch):
    szablon = tmp_path / "template.html"
    szablon.write_text(SZABLON, encoding="utf-8")
    strona = tmp_path / "s.html"
    strona.write_text(zs.strona({"canvas": {"preset": "ig", "duration": 12, "fps": 25}}, szablon, None)[0], encoding="utf-8")
    wywolania = []

    def run(cmd, **kw):
        wywolania.append(cmd)
        if "html_wideo.py" in cmd[1]:
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"v")
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr(zs.subprocess, "run", run)
    import wideo_lib
    monkeypatch.setattr(wideo_lib, "need", lambda narzedzie: narzedzie)
    assert zs.film(strona, tmp_path / "out" / "s.mp4") == 0
    wideo, audio = wywolania
    assert wideo[2:8] == ["wideo", str(strona), "--preset", "livepanel", "--dlugosc", "12"] and wideo[9] == "25"
    assert "anullsrc=r=48000:cl=stereo" in audio and audio[-1] == str(tmp_path / "out" / "s.mp4")
    assert not (tmp_path / "out" / "s.bez-audio.mp4").exists()


def test_fleet_example_is_valid_and_matches_fleet():
    cfg = json.loads(FLOTA.read_text(encoding="utf-8"))
    assert cfg["canvas"]["preset"] in zs.FORMATY and cfg["theme"]["preset"] in zs.MOTYWY
    assert "poglądow" in cfg["credit"]["text"] and zs.rozwin(cfg)[1] == []
    import fleetlib as fl
    tekst = json.dumps(cfg, ensure_ascii=False)
    assert f"{len(fl.load_fleet().active())} agentów" in tekst                 # liczba z fleet.yaml, nie z pamięci
    w, h = zs.FORMATY[cfg["canvas"]["preset"]][:2]
    for e in cfg["elements"]:                                                # treść w bezpiecznych marginesach (pomiar)
        if e["type"] in ("text", "box"):
            x0, x1 = e["x"], e["x"] + e.get("w", 0)
            assert x0 >= w * 0.06 - 1 and x1 <= w * 0.94 + 1, e.get("t") or e.get("lines", [{}])[0]


def test_build_skips_pomin_patterns(repo_copy, tmp_path):
    import build
    src = repo_copy / "shared/skills/zz"
    (src / "examples" / "a" / "screenshots").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: zz\ndescription: x\n---\n", encoding="utf-8")
    (src / "examples" / "a" / "config.json").write_text("{}", encoding="utf-8")
    (src / "examples" / "a" / "a.mp4").write_bytes(b"0")
    (src / "examples" / "a" / "screenshots" / "f.png").write_bytes(b"0")
    lock = {"sources": {"jarvo": {"type": "repo-tree", "license": "MIT", "notice": "Jarvo"}},
            "agents": {"jarvo-wideo": [{"source": "jarvo", "path": "shared/skills/zz", "dest": "video/zz",
                                        "pomin": ["*.mp4", "screenshots"]}]}}
    out = tmp_path / "skills"
    out.mkdir()
    build.vendor_skills("jarvo-wideo", out, lock, build.SourceResolver(lock, None, tmp_path, {}), [])
    d = out / "video/zz"
    assert (d / "examples/a/config.json").exists() and not (d / "examples/a/a.mp4").exists()
    assert not (d / "examples/a/screenshots").exists() and (d / "LICENSE-UPSTREAM").exists()


def test_validate_rejects_bad_pomin(repo_copy):
    import validate
    p = repo_copy / "vendor/skills.lock.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace('pomin: ["*.mp4", "screenshots"]', 'pomin: ["SKILL.md"]'),
                 encoding="utf-8")
    r = validate.Report()
    validate.check_lock(validate.fl.load_fleet(), {}, r)
    assert any("`pomin`" in e for e in r.errors)

"""malarz.py: katalog 35 stylów z kart skillu style-malarskie, tabele odcinków silnika, strony (wzór, film)
i port wycinania z zielonego tła."""

from __future__ import annotations

import json
import re
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "profiles/jarvo-wideo/scripts"))
import malarz as ml  # noqa: E402

SKILL = REPO / "profiles/jarvo-wideo/skills/wideo/style-malarskie"
IDS = ["01_cave", "02_egypt", "03_greek", "04_roman", "05_gothic", "06_renaissance", "08_impressionism", "09_postimp",
       "10_nouveau", "11_cubism", "12_bauhaus", "13_pop", "14_8bit", "15_raytrace", "16_2026", "17_ink", "18_klimt",
       "19_munch", "20_dunhuang", "21_kusama", "22_constructivism", "23_dali", "24_hopper", "25_ghibli", "26_vaporwave",
       "27_kirby", "28_monet", "29_seurat", "30_matisse", "31_haring", "32_rembrandt", "33_rubberhose",
       "34_shadowpuppet", "35_shinkai", "36_picasso_blue"]

GALERIA = """window.ERAS = [
 { id: '01_cave', name: '洞穴壁画', eighths: 5,
   counter: { year: -40000, roll: 0, x: R, y: 114 } },
 { id: '02_egypt', name: '古埃及壁画', eighths: 5, transition: { type: 'tiles', dur: 0.42 },
   counter: { year: -1350, roll: 0.4 } },
 { id: '09_postimp', name: '后印象派', eighths: 5, transition: { type: 'swirl', dur: 0.28, cx: 560, cy: 340 },
 { id: '16_2026', name: '2026', eighths: 6, transition: { type: 'iris', dur: 0.183 },
];"""


def test_katalog_35_kart_i_wybor():
    k = ml.katalog()
    assert [x["id"] for x in k] == IDS
    assert all(x["nazwa"] and x["do_czego"] and x["nie_do"] for x in k)
    assert all((SKILL / x["karta"]).exists() for x in k)
    wybor = (SKILL / "references/wybor.md").read_text(encoding="utf-8")
    assert set(re.findall(r"\(`(\d{2}_[a-z0-9_]+)`\) \|", wybor)) == set(IDS)      # każdy styl w tabeli wyboru
    tekst = "\n".join(p.read_text(encoding="utf-8") for p in SKILL.rglob("*.md"))
    assert "key_green.py" not in tekst.replace("port ich `key_green.py`", "").replace("`key_split.py` i `key_green.py`", "")
    assert "$PYTHON" not in tekst and "malarz.py nowy out/wideo/src --styl" not in tekst


def test_karta_sekcje(tmp_path):
    (tmp_path / "99_test.md").write_text("# Styl testowy, „cudzysłów” (`99_test`)\n\nOpis.\n\n## Do czego\n"
                                         "- Pierwsze: spot 5 s,\n  ciąg dalszy.\n- Drugie.\n\n## Nie do\n- Nic.\n\n## Cechy\n- x\n",
                                         encoding="utf-8")
    (tmp_path / "bez-tytulu.md").write_text("# Coś innego\n", encoding="utf-8")
    k = ml.katalog(tmp_path)
    assert k == [{"id": "99_test", "nazwa": "Styl testowy, „cudzysłów”", "do_czego": ["Pierwsze: spot 5 s, ciąg dalszy.", "Drugie."],
                  "nie_do": ["Nic."], "karta": "references/style/99_test.md"}]
    with pytest.raises(SystemExit, match="nieznany styl"):
        ml.styl("98_brak", tmp_path)


def test_odcinki_z_tabeli_silnika():
    o = ml.odcinki(GALERIA)
    assert [x["id"] for x in o] == ["01_cave", "02_egypt", "09_postimp", "16_2026"]
    assert o[0]["przejscie"] is None
    assert o[1]["przejscie"] == {"type": "tiles", "dur": 0.42}
    assert o[2]["przejscie"] == {"type": "swirl", "dur": 0.28, "cx": 560, "cy": 340}


def test_strona_wzoru_bez_postaci_autora(tmp_path):
    html = ml.strona_wzoru(tmp_path, "09_postimp", "eras_gallery.js").read_text(encoding="utf-8")
    assert "rig_huashu" not in html and 'const STYL = "09_postimp";' in html
    kolejnosc = ["/_lib/huashu/lib/fonts.js", "/_lib/huashu/lib/rig.js", "/_lib/jarvo/huashu_pl.js",
                 "/_lib/huashu/eras_gallery.js", "delete e.counter", "/_lib/huashu/transitions.js",
                 "/_lib/huashu/scenes/index.js", "/_lib/huashu/engine.js", "window.__seek"]
    assert [html.index(x) for x in kolejnosc] == sorted(html.index(x) for x in kolejnosc)
    galeria = ml.strona_wzoru(tmp_path, None, "eras_gallery.js").read_text(encoding="utf-8")
    assert "const STYL = null;" in galeria and "(t - i) * 10" in galeria


def test_nowy_film(tmp_path, monkeypatch):
    eng = tmp_path / "huashu" / "scripts" / "engine"
    (eng / "scenes").mkdir(parents=True)
    (eng / "eras_gallery.js").write_text(GALERIA, encoding="utf-8")
    for i in ("09_postimp", "16_2026", "02_egypt"):
        (eng / "scenes" / f"{i}.js").write_text(f"SCENES['{i}'] = {{ draw(c, lt, t) {{}} }};\n", encoding="utf-8")
    monkeypatch.setattr(ml, "silnik", lambda: eng)
    kat = tmp_path / "film"
    assert ml.main(["nowy", str(kat), "--styl", "09_postimp,16_2026", "--osemki", "6"]) == 0
    html = (kat / "index.html").read_text(encoding="utf-8")
    assert '<script src="eras.js"></script>' in html and "window.SCENE_DIR = 'sceny'" in html and "rig_huashu" not in html
    eras = (kat / "eras.js").read_text(encoding="utf-8")
    assert "{'id': '09_postimp', 'eighths': 6}," in eras                    # pierwszy odcinek bez przejścia
    assert "{'id': '16_2026', 'eighths': 6, 'transition': {'type': 'iris', 'dur': 0.183}}," in eras
    assert "window.PUNCH = 0.03;" in eras and "window.BPM = 128;" in eras
    scena = (kat / "sceny" / "16_2026.js").read_text(encoding="utf-8")
    assert scena.startswith("// Punkt startu: scena-wzór 16_2026 z huashu-art-motion (MIT")
    assert "FR = t * 60" in scena and "window.SIGNATURE" in scena and scena.endswith("SCENES['16_2026'] = { draw(c, lt, t) {} };\n")
    assert "FR = t * 60" not in (kat / "sceny" / "09_postimp.js").read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="nadpisz"):
        ml.main(["nowy", str(kat), "--styl", "09_postimp"])
    with pytest.raises(SystemExit, match="różnych id"):
        ml.main(["nowy", str(tmp_path / "x"), "--styl", "09_postimp,09_postimp"])
    with pytest.raises(SystemExit, match="nieznany styl"):
        ml.main(["nowy", str(tmp_path / "y"), "--styl", "07_ukiyoe"])
    # jeden styl: bez uderzenia kamery (nie ma przejścia)
    assert ml.main(["nowy", str(tmp_path / "jeden"), "--styl", "02_egypt"]) == 0
    assert "window.PUNCH = 0;" in (tmp_path / "jeden" / "eras.js").read_text(encoding="utf-8")


def test_wzor_zle_id():
    with pytest.raises(SystemExit, match="09_postimp"):
        ml.main(["wzor", "van-gogh"])


def test_wytnij_i_potnij(tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    tlo = np.zeros((120, 300, 3), np.uint8)
    tlo[...] = (0, 255, 0)
    tlo[20:60, 40:100] = (200, 30, 30)        # poza 1
    tlo[30:90, 180:260] = (30, 30, 200)       # poza 2
    Image.fromarray(tlo).save(tmp_path / "arkusz.png")
    meta = ml.wytnij([tmp_path / "arkusz.png"], tmp_path / "sprites", pad=2)
    assert meta["arkusz"] == {"x": 38, "y": 18, "w": 224, "h": 74, "kadr": [300, 120]}
    wyc = np.asarray(Image.open(tmp_path / "sprites" / "arkusz.png"))
    assert wyc.shape == (74, 224, 4) and wyc[0, 0, 3] == 0 and wyc[10, 10, 3] == 255
    assert json.loads((tmp_path / "sprites" / "sprites.json").read_text(encoding="utf-8"))["arkusz"]["x"] == 38
    pozy = ml.potnij(tmp_path / "arkusz.png", tmp_path / "klatki" / "chod")
    assert [(p["x0"], p["x1"], p["y0"], p["y1"]) for p in pozy] == [(40, 100, 20, 60), (180, 260, 30, 90)]
    assert (tmp_path / "klatki" / "chod_1.png").exists()
    jedna = ml.potnij(tmp_path / "arkusz.png", tmp_path / "klatki" / "druga", pick=1)
    assert len(jedna) == 1 and (tmp_path / "klatki" / "druga.png").exists()

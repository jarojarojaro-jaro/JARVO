"""Strefy platform w edytorze HQ: tekst pod interfejsem TikToka/Reels/Shorts jest wykrywany, kadr poziomy nie ma stref,
a nowy tekst i napisy w kadrze pionowym startują poza strefami (edytor i agent tak samo)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO, load_script

JS = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")


def test_kolizja_ze_strefami_w_przegladarce():
    if not shutil.which("node"):
        pytest.skip("brak node")
    kod = "\n".join(re.search(rf"^{wzor}.*?^}};?$", JS, re.S | re.M).group(0)
                    for wzor in (r"const ED_STREFY = \{", r"function strefyUI\(", r"const strefyKolizja = "))
    pudla = {
        "napis_na_dole": {"x0": 100, "y0": 1560, "x1": 980, "y1": 1660},     # y 0.84: pod opisem TikToka
        "napis_nad_opisem": {"x0": 100, "y0": 1290, "x1": 900, "y1": 1400},  # y 0.7: wolne na TikToku i Shorts
        "przy_prawej": {"x0": 600, "y0": 800, "x1": 1000, "y1": 900},        # kolumna przycisków
    }
    prog = kod + f"\nconst P = {json.dumps(pudla)};\nconst out = {{}};\n" + """
for (const pf of ["tiktok", "reels", "shorts"]) for (const k in P) out[pf + ":" + k] = strefyKolizja(P[k], 1080, 1920, pf);
out.poziomo = strefyKolizja(P.napis_na_dole, 1920, 1080, "tiktok");
out.post45 = strefyKolizja(P.napis_na_dole, 1080, 1350, "tiktok");
out.tabela = ED_STREFY;
out.wylaczone = strefyKolizja(P.napis_na_dole, 1080, 1920, "off");
console.log(JSON.stringify(out));"""
    w = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert w["tiktok:napis_na_dole"] == ["bottom"] and w["tiktok:napis_nad_opisem"] == []
    assert w["shorts:napis_nad_opisem"] == [] and w["reels:napis_nad_opisem"] == ["bottom"]   # Reels: dół 35%
    assert w["tiktok:przy_prawej"] == ["right"] and w["reels:przy_prawej"] == []
    assert w["poziomo"] == [] and w["wylaczone"] == [] and w["post45"] == []
    # te same liczby co kontrola Wideografa (wideo_lib.STREFY_UI: qa_wideo, pomiar)
    wl = load_script("profiles/jarvo-wideo/scripts/wideo_lib.py", "jarvo_wideo_lib_strefy_test")
    assert {k: (z["t"], z["b"], z["l"], z["r"]) for k, z in w["tabela"].items()} == wl.STREFY_UI


def test_agent_stawia_tekst_nad_opisem_w_pionie(tmp_path, monkeypatch):
    pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_strefy_test")
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    for (w, h), y in (((1080, 1920), pr.PION["y"]), ((1920, 1080), pr.TEXT_DEFAULT["y"])):
        zapis = {}
        proj = {"canvas": {"w": w, "h": h, "fps": 30}, "clips": [{"id": "a", "src": "f.mp4", "in": 0, "out": 10, "speed": 1}],
                "texts": [], "audio": []}
        monkeypatch.setattr(pr, "load", lambda f, proj=proj: proj)
        monkeypatch.setattr(pr, "save", lambda f, p: zapis.update(p=p))
        a = type("A", (), {"tekst": "Hej", "start": 1.0, "koniec": 3.0, "napis": False, "styl": None, "y": None,
                           "rozmiar": None, "kolor": None, "tlo": None, "kroj": None})()
        pr.cmd_dodaj_tekst(film, a)
        assert zapis["p"]["texts"][0]["y"] == y
    assert "const ED_PION = { y: 0.68, maxw: 0.74 };" in JS and pr.PION == {"y": 0.68, "maxw": 0.74}   # edytor = agent


def test_kontrola_wideografa_z_tej_samej_tabeli():
    """qa_wideo (arkusz) i pomiar (strefa_platformy) biorą strefy z wideo_lib.strefy_ui, nazwy platform skryptów też."""
    qa = load_script("profiles/jarvo-wideo/scripts/qa_wideo.py", "jarvo_qa_strefy_test")
    pm = load_script("profiles/jarvo-wideo/scripts/pomiar.py", "jarvo_pomiar_strefy_test")
    assert qa.zones(1080, 1920, "yt-short")[1] == (0, 1530, 1080, 389)                  # Shorts: dół 390 px
    assert qa.zones(1080, 1920) == qa.zones(1080, 1920, "tiktok") and qa.zones(1080, 1350) == []
    dol = dict(pm.strefy(1080, 1920, "ig-reel"))["dół (opis, konto, dźwięk)"]
    assert dol[1] == pytest.approx(1920 * 0.65)                                        # Reels: dół 35%
    assert [n for n, _ in pm.strefy(1920, 1080, None)] == ["margines kadru"] * 4

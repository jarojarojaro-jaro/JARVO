"""Narzędzie `schemat` (wiedza/plugin/schemat.py): SVG → PNG w rozmowie. Strona do zrzutu bez sieci i skryptów,
rozmiar z width/height albo viewBox, wynik z linią MEDIA:. Prawdziwy Chromium: test w kontenerze (docs/WIEDZA.md)."""

from __future__ import annotations

import json
import shutil
import stat

import pytest

from conftest import load_script

s = load_script("wiedza/plugin/schemat.py", "jarvo_schemat_test")

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="520"><text x="10" y="40">Jak działa skarbiec</text></svg>'


def test_wymiary():
    assert s.wymiary(SVG) == (1200, 520)
    assert s.wymiary('<svg viewBox="0 0 4000 1000">') == (2400, 600)            # za duży: w dół, proporcje bez zmian
    assert s.wymiary('<svg width="100" height="50">') == (400, 200)             # za mały: w górę
    assert s.wymiary('<svg width="600">') == (1200, 800) and s.wymiary("<svg>") == (1200, 800)
    assert s.wymiary('<svg width="600" viewBox="0 0 300 100">') == (600, 200)


def test_strona_bez_sieci_i_skryptow():
    html = s.strona('<svg width="5000" height="1000" onload="x()"><script>fetch("//zly")</script><rect/></svg>',
                    *s.wymiary('<svg width="5000" height="1000">'))
    assert "default-src 'none'" in html and "<script" not in html
    assert '<svg width="2400" height="480" viewBox="0 0 5000 1000"' in html     # viewBox: skala bez przycinania
    assert 'width="5000"' not in html
    assert s.slug("Jak działa skarbiec wiedzy?") == "jak-dziala-skarbiec-wiedzy" and s.slug("???") == "schemat"


def test_obsluz_z_udawanym_chromium(tmp_path, monkeypatch):
    fake = tmp_path / "chromium"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in --screenshot=*) printf "%0200d" 0 > "${a#--screenshot=}";; esac; done\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("JARVO_CHROMIUM", str(fake))
    monkeypatch.setenv("JARVO_SCHEMATY_DIR", str(tmp_path / "schematy"))
    w = json.loads(s.obsluz({"svg": SVG, "tytul": "Jak działa skarbiec"}))
    assert w["ok"] and w["media"] == f"MEDIA:{w['plik']}" and w["plik"].endswith("-jak-dziala-skarbiec.png")
    assert w["rozmiar"] == "1200×520" and (tmp_path / "schematy").is_dir()
    assert "error" in json.loads(s.obsluz({"svg": "to nie svg", "tytul": "x"}))
    assert "maks." in json.loads(s.obsluz({"svg": "<svg>" + "x" * s.MAX_ZNAKOW, "tytul": "x"}))["error"]
    monkeypatch.setenv("JARVO_CHROMIUM", str(tmp_path / "nie-ma"))
    assert "Nie udało się" in json.loads(s.obsluz({"svg": SVG, "tytul": "x"}))["error"]


@pytest.mark.skipif(not shutil.which("chromium"), reason="brak Chromium (test w kontenerze)")
def test_prawdziwy_chromium(tmp_path):
    png = s.renderuj(SVG, "test", tmp_path)
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

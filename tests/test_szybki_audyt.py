"""szybki_audyt.py: szybki audyt z lokalnej kopii strony (raport.md + audyt.json), bez przeglądarki."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

from conftest import REPO

SKRYPT = REPO / "profiles/jarvo-web/scripts/szybki_audyt.py"
HEAD = ('<html lang="pl"><head><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>{title}</title>{desc}<link rel="canonical" href="https://example.com/{trasa}"></head>')
OPIS = '<meta name="description" content="Opis strony testowej, który ma długość mieszczącą się w zalecanym zakresie.">'


@pytest.fixture
def strona(tmp_path):
    k = tmp_path / "public_html"
    (k / "img").mkdir(parents=True)
    (k / "index.html").write_text(
        HEAD.format(title="Strona główna przykładowej firmy z Krakowa", desc=OPIS, trasa="")
        + '<body><main><h1>Witaj</h1><h2>Oferta</h2><img src="img/logo.png" alt="Logo firmy">'
          '<a href="o-nas.html">O nas</a></main></body></html>', encoding="utf-8")
    (k / "o-nas.html").write_text(
        HEAD.format(title="O nas: przykładowa firma z Krakowa od 1999", desc="", trasa="o-nas")
        + '<body><main><h1>O nas</h1><h1>Zespół</h1><img src="img/zespol.png">'
          '<a href="cennik.html">Cennik</a><a href="/">Start</a></main></body></html>', encoding="utf-8")
    (k / "img/logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 2000)
    (k / "img/zespol.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 400 * 1024)
    (k / ".strona.json").write_text('{"domena": "example.com"}', encoding="utf-8")
    return k


def uruchom(katalog, out, *argv, env=None):
    r = subprocess.run([sys.executable, str(SKRYPT), str(katalog), "--out", str(out), *argv],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return r, json.loads((out / "audyt.json").read_text(encoding="utf-8")), (out / "raport.md").read_text(encoding="utf-8")


def test_wylapuje_problemy_fixtury(strona, tmp_path):
    out = tmp_path / "out"
    r, a, raport = uruchom(strona, out, "--bez-zrzutow")
    assert r.returncode == 0, r.stderr
    assert a["domena"] == "example.com" and a["strony"] == 2
    assert a["naglowki"]["wiele_h1"] == [{"plik": "o-nas.html", "h1": 2}]
    assert a["alt"]["bez_alt"] == 1 and a["alt"]["strony"][0]["plik"] == "o-nas.html"
    assert a["tytuly"]["bez_description"] == ["o-nas.html"]
    assert [x["plik"] for x in a["obrazy"]["ponad_300kb"]] == ["img/zespol.png"]
    assert a["linki"]["martwe"] == [{"plik": "o-nas.html", "href": "cennik.html"}]
    statusy = {w["obszar"]: w["status"] for w in a["wiersze"]}
    assert statusy["Obrazy (waga i format)"] == statusy["Linki wewnętrzne"] == statusy["Alt w obrazkach"] == "blad"
    assert statusy["Nagłówki H1/H2"] == "uwaga"

    for obszar in ("Title i description", "Nagłówki H1/H2", "Alt w obrazkach", "Obrazy (waga i format)",
                   "Waga strony głównej", "Telefon i komputer (przewijanie w bok)", "Indeksowanie",
                   "Udostępnianie (Open Graph)", "Linki wewnętrzne"):
        assert re.search(rf"^\| {re.escape(obszar)}.*\| (✅|⚠️|❌) \|", raport, re.M), obszar
    poprawki = raport.split("## 5 najważniejszych poprawek", 1)[1]
    numerowane = re.findall(r"^\d+\. ", poprawki, re.M)
    assert len(numerowane) == len(a["poprawki"]) == 5
    assert "cennik.html" in poprawki and "img/zespol.png" in poprawki
    assert "stron: 2" in raport.splitlines()[2]


def test_mniej_problemow_mniej_poprawek(strona, tmp_path):
    (strona / "o-nas.html").unlink()
    (strona / "img/zespol.png").unlink()
    glowna = strona / "index.html"
    glowna.write_text(glowna.read_text(encoding="utf-8").replace('<a href="o-nas.html">O nas</a>', ""), encoding="utf-8")
    r, a, raport = uruchom(strona, tmp_path / "out", "--bez-zrzutow")
    assert r.returncode == 0
    assert a["linki"]["martwe"] == [] and a["obrazy"]["ponad_300kb"] == []
    assert len(re.findall(r"^\d+\. ", raport.split("## 5 najważniejszych poprawek", 1)[1], re.M)) \
        == len(a["poprawki"]) < 5


def test_bez_przegladarki_raport_mowi_o_pominietych_zrzutach(strona, tmp_path):
    pusty = tmp_path / "bin"
    pusty.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("CHROME_PATH", "NODE_PATH")}
    env["PATH"] = str(pusty)                                  # bez node = bez przeglądarki
    r, a, raport = uruchom(strona, tmp_path / "out", env=env)
    assert r.returncode == 0, r.stderr
    assert "pominiete" in a["responsywnosc"]
    assert "Zrzuty pominięte" in raport
    assert re.search(r"^\| Telefon i komputer.*\| ⚠️ \| nie sprawdzone", raport, re.M)


def test_brak_katalogu_to_blad(tmp_path):
    r = subprocess.run([sys.executable, str(SKRYPT), str(tmp_path / "nie-ma"), "--out", str(tmp_path / "out")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and not (tmp_path / "out" / "raport.md").exists()

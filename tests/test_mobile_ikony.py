"""Twórca aplikacji: ikony z logo (kafelek, wielokolorowe, jednobarwne), zrzuty bez łapania animacji, .gitignore szablonu.

Testy ikon uruchamiają ikony.cjs i potrzebują `sharp` (obraz floty); bez niego są pomijane (na hoście), w kontenerze
idą naprawdę.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "profiles" / "jarvo-mobile"
IKONY = MOBILE / "scripts" / "ikony.cjs"
CZERWONY = "#D4213D"


def _sharp() -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", "require('sharp')"], capture_output=True, cwd=MOBILE / "scripts").returncode == 0


wymaga_sharp = pytest.mark.skipif(not _sharp(), reason="brak node albo sharp (obraz floty)")


def _ikony(tmp_path: Path, logo: str, nazwa: str) -> dict:
    plik = tmp_path / f"{nazwa}.svg"
    plik.write_text(logo, encoding="utf-8")
    out = tmp_path / nazwa
    r = subprocess.run(["node", str(IKONY), "--out", str(out), "--kolor", CZERWONY, "--logo", str(plik), "--litery", "J"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    wynik = json.loads(r.stdout.strip().splitlines()[-1])
    wynik["out"] = out
    return wynik


def _piksele(png: Path, punkty: list[tuple[float, float]]) -> list[str]:
    """Kolory (#RRGGBB) w punktach podanych ułamkami szerokości i wysokości."""
    prog = f"""const sharp = require('sharp');
(async () => {{ const {{ data, info }} = await sharp({json.dumps(str(png))}).removeAlpha().raw().toBuffer({{ resolveWithObject: true }});
  const p = {json.dumps(punkty)}.map(([x, y]) => {{ const i = (Math.floor(y * (info.height - 1)) * info.width + Math.floor(x * (info.width - 1))) * 3;
    return '#' + [data[i], data[i + 1], data[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase(); }});
  console.log(JSON.stringify(p)); }})();"""
    r = subprocess.run(["node", "-e", prog], capture_output=True, text=True, cwd=MOBILE / "scripts", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@wymaga_sharp
def test_logo_kafelek_na_cala_ikone(tmp_path):
    """Logo z własnym tłem ikony (jak favicon Jarvo) idzie na całą ikonę zamiast białego kwadratu w środku."""
    kafel = f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" rx="80" fill="{CZERWONY}"/>
      <rect x="150" y="170" width="212" height="172" fill="#F2F1E8"/><rect x="200" y="220" width="40" height="70" fill="#B8FF3D"/></svg>"""
    w = _ikony(tmp_path, kafel, "kafel")
    assert any("gotowy kafelek" in u for u in w["uwagi"]) and not any("przemalowane" in u for u in w["uwagi"])
    rog, srodek, oko = _piksele(w["out"] / "icon.png", [(0.01, 0.01), (0.5, 0.5), (0.43, 0.49)])
    assert rog == CZERWONY and srodek == "#F2F1E8" and oko == "#B8FF3D"
    tlo, = _piksele(w["out"] / "android-icon-background.png", [(0.5, 0.5)])
    assert tlo == CZERWONY


@wymaga_sharp
def test_logo_wielokolorowe_nie_jest_przemalowane(tmp_path):
    # paski ciemnego i jasnego różu: średnio zlewają się z karminowym tłem, ale każdy kolor jest inny niż średnia
    wielo = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">
      <rect x="40" y="40" width="160" height="320" fill="#7A1020"/><rect x="200" y="40" width="160" height="320" fill="#F29AA8"/></svg>"""
    w = _ikony(tmp_path, wielo, "wielo")
    assert any("wielokolorowe" in u for u in w["uwagi"]) and not any("przemalowane" in u for u in w["uwagi"])
    lewy, prawy = _piksele(w["out"] / "icon.png", [(0.4, 0.5), (0.6, 0.5)])
    assert (lewy, prawy) == ("#7A1020", "#F29AA8")   # kolory znaku zostają


@wymaga_sharp
def test_logo_jednobarwne_w_kolorze_tla_przemalowane(tmp_path):
    jedno = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><circle cx="100" cy="100" r="80" fill="#B53949"/></svg>"""
    w = _ikony(tmp_path, jedno, "jedno")
    assert any("przemalowane na #FFFFFF" in u for u in w["uwagi"])
    srodek, rog = _piksele(w["out"] / "icon.png", [(0.5, 0.5), (0.02, 0.02)])
    assert srodek == "#FFFFFF" and rog == CZERWONY


def test_zrzuty_z_ograniczonym_ruchem():
    """Animacje wejścia nie mogą trafić na zrzut w połowie (blade karty): kontekst przeglądarki z reducedMotion."""
    assert "reducedMotion: 'reduce'" in (MOBILE / "scripts" / "zrzuty.cjs").read_text(encoding="utf-8")


def test_szablon_nie_wersjonuje_wynikow_kontroli():
    ign = (MOBILE / "templates" / "expo-jarvo" / ".gitignore").read_text(encoding="utf-8").splitlines()
    for wpis in ("/out/zrzuty/", "/out/jakosc/", "/out/expo-go/"):
        assert wpis in ign, wpis
    assert "/out/" not in ign                        # historia wydań i odrzuceń zostaje w repo aplikacji

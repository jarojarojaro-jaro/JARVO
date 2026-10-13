"""Warsztat 3D (shared/skills/warsztat-3d): cad.py, cad_model.py, przypięcie silnika w obrazie.

Część z prawdziwym silnikiem (build123d) i podglądem (node + three + Chromium) idzie tylko tam, gdzie są
(kontener Jarva albo JARVO_CAD_PYTHON / NODE_PATH lokalnie); reszta działa bez nich.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import REPO, load_script

SKILL = REPO / "shared" / "skills" / "warsztat-3d"
cad = load_script("shared/skills/warsztat-3d/scripts/cad.py")
model = load_script("shared/skills/warsztat-3d/scripts/cad_model.py")


def args(**kw):
    baza = dict(model=None, out=None, nazwa=None, formaty="step,stl,glb,3mf", dokladnosc=0.05, material="pla",
                gestosc=None, mimo_bledow=False)
    return argparse.Namespace(**(baza | kw))


def widok(**kw):
    baza = dict(rozmiar="1600x1200", kat=35, wysokosc=25, kolor=None, tlo=None, przezroczyste=False, siatka=False,
                bez_krawedzi=False, skala=1)
    return argparse.Namespace(**(baza | kw))


def test_zadanie_modelu_formaty_material_nazwa(tmp_path):
    m = tmp_path / "uchwyt.py"
    m.write_text("wynik = None\n")
    z = cad.zadanie_modelu(args(model=str(m), out=str(tmp_path / "out"), formaty="STL, glb,stl"))
    assert z["formaty"] == ["stl", "glb"] and z["nazwa"] == "uchwyt" and z["gestosc"] == 1.24 and z["material"] == "pla"
    z = cad.zadanie_modelu(args(model=str(m), out="o", material="petg"))
    assert z["gestosc"] == 1.27
    z = cad.zadanie_modelu(args(model=str(m), out="o", gestosc=7.85))
    assert z["gestosc"] == 7.85 and z["material"] is None
    for zle in (dict(formaty="obj"), dict(nazwa="zła nazwa"), dict(nazwa="../x"), dict(gestosc=99.0),
                dict(dokladnosc=0.0), dict(model=str(tmp_path / "brak.py")), dict(model=str(tmp_path))):
        with pytest.raises(cad.Blad):
            cad.zadanie_modelu(args(**({"model": str(m), "out": "o"} | zle)))


def test_opcje_widoku_i_walidacja():
    w = cad.opcje_widoku(widok(kolor="#e4572e", siatka=True))
    assert w["kolor"] == "#E4572E" and w["tlo"] == "#F4F4F2" and w["siatka"] and w["krawedzie"] and (w["w"], w["h"]) == (1600, 1200)
    assert cad.opcje_widoku(widok(przezroczyste=True))["tlo"] is None
    assert cad.opcje_widoku(widok(kat=395))["kat"] == 35
    for zle in (dict(tlo="#fff", przezroczyste=True), dict(kolor="red"), dict(rozmiar="10x10"), dict(rozmiar="5000x100"),
                dict(wysokosc=90), dict(skala=5)):
        with pytest.raises(cad.Blad):
            cad.opcje_widoku(widok(**zle))


def test_obrot_bez_przezroczystosci_i_ffmpeg(tmp_path):
    with pytest.raises(cad.Blad, match="przezroczyst"):
        cad.obrot(tmp_path / "m.glb", tmp_path / "o.mp4", cad.opcje_widoku(widok(przezroczyste=True)), 6, 30)
    with pytest.raises(cad.Blad):
        cad.obrot(tmp_path / "m.glb", tmp_path / "o.mp4", cad.opcje_widoku(widok()), 0.5, 30)
    cmd = cad.polecenie_ffmpeg(30, Path("/x/o.mp4"), "/t/k%05d.png")
    assert cmd[0] == "ffmpeg" and cmd[cmd.index("-framerate") + 1] == "30" and "yuv420p" in cmd and cmd[-1] == "/x/o.mp4"
    with pytest.raises(cad.Blad, match="glb"):
        cad._glb(str(tmp_path / "brak.glb"))
    (tmp_path / "m.gltf").write_text("{}")
    with pytest.raises(cad.Blad, match=".glb"):
        cad._glb(str(tmp_path / "m.gltf"))


def _falszywy_python(tmp_path: Path, raport: dict | None, stderr: str = "") -> str:
    """Skrypt udający python z venvu CAD: ignoruje argumenty i wypisuje raport (albo błąd)."""
    p = tmp_path / "fake-python"
    tresc = "#!/bin/sh\n"
    if stderr:
        tresc += f"echo {json.dumps(stderr)} >&2\n"
    if raport is not None:
        tresc += "echo 'Fontconfig warning: cos'\n" + f"echo '{json.dumps(raport)}'\n"
    tresc += "exit 1\n" if stderr else "exit 0\n"
    p.write_text(tresc)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_zbuduj_zapisuje_raport_i_material(tmp_path):
    m = tmp_path / "czesc.py"
    m.write_text("wynik = None\n")
    zad = cad.zadanie_modelu(args(model=str(m), out=str(tmp_path / "out"), material="petg"))
    rap = {"model": str(m), "bledy": [], "ostrzezenia": [], "wymiary_mm": [10, 20, 30], "objetosc_mm3": 6000.0,
           "masa_g": 7.6, "gestosc_g_cm3": 1.27, "bryly": 1, "poprawny": True, "pliki": {}}
    r = cad.zbuduj(zad, python=_falszywy_python(tmp_path, rap))
    assert r["material"] == "petg" and r["wymiary_mm"] == [10, 20, 30]
    zapisany = json.loads(Path(r["raport"]).read_text(encoding="utf-8"))
    assert zapisany["masa_g"] == 7.6 and Path(r["raport"]).name == "czesc.json"
    r = cad.zbuduj(zad, python=_falszywy_python(tmp_path, None, stderr="ModuleNotFoundError: build123d"))
    assert r["bledy"] and "build123d" in r["bledy"][0]


def test_brak_silnika_ma_jasny_blad(monkeypatch):
    monkeypatch.setenv("JARVO_CAD_PYTHON", "/nie/ma/python")
    monkeypatch.setattr(cad, "CAD_PYTHON", "/nie/ma/tez")
    with pytest.raises(cad.Blad, match="venvs/cad"):
        cad.cad_python()


def test_uwagi_i_nazwy_czesci():
    ok = {"poprawny": True, "bryly": 1, "objetosc_mm3": 100.0, "wymiary_mm": [10, 10, 10]}
    assert model.uwagi(ok) == ([], [])
    b, o = model.uwagi(ok | {"poprawny": False, "bryly": 2})
    assert any("niepoprawny" in t for t in b) and any("2 osobne bryły" in t for t in o)
    assert model.uwagi(ok | {"bryly": 2, "czesci": [{}, {}]})[1] == []       # zestaw części: bez ostrzeżenia
    assert any("brak bryły" in t for t in model.uwagi(ok | {"bryly": 0, "wymiary_mm": [0, 0, 0]})[0])
    assert model.uwagi(ok | {"bryly": 0, "wymiary_mm": [0, 0, 0]})[1] == []  # puste: bez uwagi o milimetrach
    assert any("milimetrach" in t for t in model.uwagi(ok | {"wymiary_mm": [0.06, 0.04, 0.03]})[1])
    assert any("> 5 m" in t for t in model.uwagi(ok | {"wymiary_mm": [6000, 10, 10]})[1])

    class C:
        def __init__(self, label=""):
            self.label = label
    assert model.nazwy_czesci([C("dno"), C("Pokrywa górna"), C()]) == ["dno", "Pokrywa-g-rna", "czesc3"]
    assert model.nazwy_czesci([C("noga"), C("noga")]) == ["noga-1", "noga-2"]


def test_cad_model_blokuje_siec():
    kod = (f"import sys; sys.path.insert(0, {str(SKILL / 'scripts')!r}); import cad_model, socket\n"
           "cad_model.zablokuj_siec()\n"
           "for f in (lambda: socket.create_connection(('example.com', 443)), lambda: socket.getaddrinfo('example.com', 80),\n"
           "          lambda: socket.socket().connect(('127.0.0.1', 9))):\n"
           "    try:\n        f(); print('POLACZONO')\n    except PermissionError as e:\n        print('BLOK', e)\n")
    p = subprocess.run([sys.executable, "-I", "-c", kod], capture_output=True, text=True, timeout=30)
    assert p.stdout.count("BLOK") == 3 and "POLACZONO" not in p.stdout
    assert socket.create_connection is not model._odmow                          # w tym procesie bez zmian


def test_skill_przyklady_i_strona_podgladu():
    tekst = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(tekst.split("---")[1])
    assert meta["name"] == "warsztat-3d" and meta["metadata"]["jarvo"]["autonomy"] == "A0"
    for ref in re.findall(r"`((?:references|assets)/[^`]+)`", tekst):
        assert (SKILL / ref).exists(), ref
    for przyklad in (SKILL / "assets" / "przyklady").glob("*.py"):
        kod = przyklad.read_text(encoding="utf-8")
        assert re.search(r"^wynik = ", kod, re.M) and "requests" not in kod and "pcbway" not in kod, przyklad.name
    html = (SKILL / "scripts" / "cad_podglad.html").read_text(encoding="utf-8")
    assert "https://" not in html and "http://" not in html                   # bez CDN: three z /three/ (page.route)
    assert "window.__ustaw" in html and "window.__ready = true" in html
    cjs = (SKILL / "scripts" / "cad_render.cjs").read_text(encoding="utf-8")
    assert "route.abort()" in cjs and "cad.jarvo" in cjs
    lock = yaml.safe_load((REPO / "vendor" / "skills.lock.yaml").read_text(encoding="utf-8"))
    for agent in ("jarvo-web", "jarvo-wideo", "jarvo-mobile"):
        assert {"source": "jarvo", "path": "shared/skills/warsztat-3d", "dest": "design/warsztat-3d"} in lock["agents"][agent]
        tb = yaml.safe_load((REPO / "profiles" / agent / "toolbox.yaml").read_text(encoding="utf-8"))
        assert {"build123d", "three"} <= {t["name"] for t in tb["tools"]}


def test_obraz_przypina_silnik_sumami_bez_zbednych_paczek():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(line for line in docker.splitlines() if not line.lstrip().startswith("#"))
    run = next(r for r in code.split("\nRUN ") if "/opt/jarvo/venvs/cad" in r)
    for flaga in ("--no-config", "--no-deps", "--require-hashes", "--only-binary :all:", "--compile-bytecode",
                  "requirements-cad.txt", "--python 3.12"):
        assert flaga in run, flaga
    assert "export_step" in run and "p.3mf" in run and "require.resolve('three')" in run
    lock = (REPO / "infra" / "python" / "requirements-cad.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([a-z0-9-]+)==(\S+)(?: ;[^\\]*)? \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+)", lock, re.M)
    names = {n: v for n, v, _h in pins}
    assert len(pins) == len(re.findall(r"^[a-z0-9-]+==", lock, re.M))           # każda paczka ma sumy
    assert names["build123d"] == "0.13.0" and names["cadquery-ocp-novtk"].startswith("8.0.")
    assert {"lib3mf", "py-lib3mf", "scikit-learn", "ipython", "threejs-materials"} <= set(names)   # oba warianty lib3mf
    assert not {"sympy", "mpmath", "jedi", "parso"} & set(names)
    pkg = json.loads((REPO / "infra" / "node" / "package.json").read_text(encoding="utf-8"))
    narz = (REPO / "profiles" / "jarvo-wideo" / "scripts" / "narzedzia.py").read_text(encoding="utf-8")
    assert f"three@{pkg['dependencies']['three']}" in narz                       # ta sama wersja co /_lib/three Wideografa


# ------------------------------------------------------------------ z prawdziwym silnikiem i przeglądarką

def _silnik() -> str | None:
    for k in (os.environ.get("JARVO_CAD_PYTHON"), cad.CAD_PYTHON):
        if k and Path(k).exists():
            return k
    return None


def _podglad_dostepny() -> bool:
    if not shutil.which("node"):
        return False
    p = subprocess.run(["node", "-e", "require.resolve('three'); require('playwright-core')"], capture_output=True)
    return p.returncode == 0 and (Path("/etc/hermes/agent-browser-executable-path").exists()
                                  or bool(os.environ.get("CHROME_PATH")))


@pytest.mark.skipif(_silnik() is None, reason="brak venvu CAD (kontener Jarva albo JARVO_CAD_PYTHON)")
def test_przyklady_buduja_sie_naprawde(tmp_path):
    for nazwa, bryly, czesci in (("katownik", 1, None), ("obudowa", 2, ["dno", "pokrywa"])):
        zad = cad.zadanie_modelu(args(model=str(SKILL / "assets" / "przyklady" / f"{nazwa}.py"), out=str(tmp_path)))
        r = cad.zbuduj(zad)
        assert not r["bledy"] and r["poprawny"] and r["bryly"] == bryly, r
        assert not r["ostrzezenia"], r["ostrzezenia"]
        assert {"step", "stl", "glb", "3mf"} <= set(r["pliki"])
        assert all(Path(v["plik"]).stat().st_size > 1000 for v in r["pliki"].values())
        if czesci:
            assert [c["nazwa"] for c in r["czesci"]] == czesci and f"stl:{czesci[0]}" in r["pliki"]
    assert (tmp_path / "katownik.step").read_text(errors="ignore").startswith("ISO-10303-21")
    zly = tmp_path / "zly.py"
    zly.write_text("from build123d import *\nwynik = Box(10, 10, 10)\nimport urllib.request\n"
                   "urllib.request.urlopen('https://example.com')\n")
    r = cad.zbuduj(cad.zadanie_modelu(args(model=str(zly), out=str(tmp_path))))
    assert r["bledy"] and "bez sieci" in r["bledy"][0] and "linia 4" in r["bledy"][0]


@pytest.mark.skipif(_silnik() is None or not _podglad_dostepny(), reason="brak silnika CAD albo node/three/Chromium")
def test_podglad_png_naprawde(tmp_path):
    r = cad.zbuduj(cad.zadanie_modelu(args(model=str(SKILL / "assets" / "przyklady" / "katownik.py"), out=str(tmp_path),
                                           formaty="glb")))
    png = tmp_path / "k.png"
    w = cad.podglad(Path(r["pliki"]["glb"]["plik"]), png, cad.opcje_widoku(widok(rozmiar="400x300")))
    assert not w["bledy"] and w["info"]["wymiary_mm"] == [60, 40, 36]
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size > 5000

"""Warsztat 3D (shared/skills/warsztat-3d): cad.py, cad_model.py, cad_render.py, przypięcie silnika w obrazie
i instalacja natywna (venv cad i Three.js przy pierwszym użyciu, docs/NATYWNIE.md E11).

Część z prawdziwym silnikiem (build123d) i podglądem idzie tylko tam, gdzie są: kontener Jarva (node + three +
Chromium), instalacja natywna albo JARVO_CAD_PYTHON z CHROME_PATH i JARVO_THREE_DIR (Playwright dla Pythona w tym
interpreterze albo w JARVO_TOOLS_PYTHON); reszta działa bez nich. Na żywo w instalacji: tests/live/natywnie_telefon_3d.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import atrapy
import pytest
import yaml

from conftest import REPO, load_script

SKILL = REPO / "shared" / "skills" / "warsztat-3d"
cad = load_script("shared/skills/warsztat-3d/scripts/cad.py")
model = load_script("shared/skills/warsztat-3d/scripts/cad_model.py")
render = load_script("shared/skills/warsztat-3d/scripts/cad_render.py")


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
    m.write_text("wynik = None\n", encoding="utf-8")
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
    # ścieżka wyniku idzie do ffmpeg w zapisie systemu (na Windows „\x\o.mp4”)
    assert cmd[0] == "ffmpeg" and cmd[cmd.index("-framerate") + 1] == "30" and "yuv420p" in cmd
    assert cmd[-1] == str(Path("/x/o.mp4"))
    with pytest.raises(cad.Blad, match="glb"):
        cad._glb(str(tmp_path / "brak.glb"))
    (tmp_path / "m.gltf").write_text("{}", encoding="utf-8")
    with pytest.raises(cad.Blad, match=".glb"):
        cad._glb(str(tmp_path / "m.gltf"))


def _falszywy_python(tmp_path: Path, raport: dict | None, stderr: str = "") -> str:
    """Atrapa pythona z venvu CAD (tests/atrapy.py): ignoruje argumenty i wypisuje raport (albo błąd)."""
    kod = "import sys\n"
    if stderr:
        kod += f"print({stderr!r}, file=sys.stderr)\n"
    if raport is not None:
        kod += "print('Fontconfig warning: cos')\n" + f"print({json.dumps(raport)!r})\n"
    kod += "sys.exit(1)\n" if stderr else "sys.exit(0)\n"
    return str(atrapy.program(tmp_path, "fake-python", kod))


def test_zbuduj_zapisuje_raport_i_material(tmp_path):
    m = tmp_path / "czesc.py"
    m.write_text("wynik = None\n", encoding="utf-8")
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
    # -X utf8: -I pomija PYTHONUTF8, a na Windows potok miałby stronę kodową ANSI (komunikat ma polskie litery)
    p = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", kod], capture_output=True, text=True, encoding="utf-8",
                       timeout=30)
    assert p.stdout.count("BLOK") == 3 and "POLACZONO" not in p.stdout, p.stderr
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


# ------------------------------------------------------------------ instalacja natywna (E11): silnik i Three.js przy użyciu

class AtrapaPrzyUzyciu:
    """Atrapa jarvo/przy_uzyciu.py: venv cad i narzędzie three „instalowane” do katalogu tymczasowego."""

    class BladPrzyUzyciu(RuntimeError):
        pass

    def __init__(self, tmp: Path, *, venv: bool = False, three: bool = False, blad: str = ""):
        self.tmp, self.blad = tmp, blad
        self.wywolania: list[str] = []
        self.python = tmp / "venvs" / "cad-abc" / "python.exe"
        self.three = tmp / "narzedzia" / "three" / "0.186.1"
        if venv:
            self._venv()
        if three:
            self._three()

    def _venv(self):
        self.python.parent.mkdir(parents=True, exist_ok=True)
        self.python.write_bytes(b"")

    def _three(self):
        for rel in ("build/three.module.js", "examples/jsm/loaders/GLTFLoader.js"):
            (self.three / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.three / rel).write_text("//", encoding="utf-8")

    def gotowy_venv(self, _u, nazwa):
        assert nazwa == "cad"
        return {"python": str(self.python), "katalog": str(self.python.parent)} if self.python.is_file() else None

    def venv(self, _u, nazwa, log=print):
        self.wywolania.append(f"venv {nazwa}")
        if self.blad:
            raise self.BladPrzyUzyciu(self.blad)
        log("venv cad: pierwsze użycie")
        self._venv()
        return self.gotowy_venv(_u, nazwa)

    def gotowe_narzedzie(self, _u, nazwa):
        return {"katalog": str(self.three)} if nazwa == "three" and self.three.is_dir() else None

    def narzedzie(self, _u, nazwa, log=print):
        self.wywolania.append(f"narzedzie {nazwa}")
        if self.blad:
            raise self.BladPrzyUzyciu(self.blad)
        self._three()
        return {"katalog": str(self.three)}

    def wpis(self, _u, _nazwa):
        return None

    def opis_venvu(self, _u, nazwa):
        return {"venv": nazwa, "pobranie_mb": 215, "venv_mb": 597, "paczek": 56}

    def app_instalacji(self, _u):
        return REPO

    def rozmiar_mb(self, _app, nazwa):
        return 4.6 if nazwa == "three" else None


@pytest.fixture
def natywnie(monkeypatch, tmp_path):
    """Instalacja natywna bez silnika w obrazie: JARVO_CAD_PYTHON i ścieżki obrazu wskazują w próżnię."""
    monkeypatch.delenv("JARVO_CAD_PYTHON", raising=False)
    monkeypatch.delenv("JARVO_THREE_DIR", raising=False)
    monkeypatch.delenv("JARVO_NARZEDZIA", raising=False)
    monkeypatch.setenv("NODE_PATH", "")
    monkeypatch.setattr(cad, "CAD_PYTHON", str(tmp_path / "nie-ma" / "python"))
    monkeypatch.setattr(cad, "THREE_KONTENER", str(tmp_path / "nie-ma" / "three"))

    def ustaw(**kw) -> AtrapaPrzyUzyciu:
        pu = AtrapaPrzyUzyciu(tmp_path, **kw)
        monkeypatch.setattr(cad, "_przy_uzyciu", lambda: (pu, object()))
        return pu
    return ustaw


def test_przy_uzyciu_tylko_w_instalacji_natywnej(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVO_ROOT", raising=False)
    assert cad._przy_uzyciu() == (None, None)                                 # kontener: silnik w obrazie
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path))
    assert cad._przy_uzyciu() == (None, None)                                 # bez current.json
    (tmp_path / "program").mkdir()
    (tmp_path / "program" / "current.json").write_text(json.dumps({"app": ""}), encoding="utf-8")
    monkeypatch.delenv("JARVO_REPO", raising=False)
    monkeypatch.chdir(REPO)                                                   # w katalogu bieżącym jest jarvo/
    assert cad._przy_uzyciu() == (None, None)                                 # pusta ścieżka: nie z katalogu bieżącego
    monkeypatch.setenv("JARVO_REPO", ".")
    assert cad._przy_uzyciu() == (None, None)                                 # względna też nie
    monkeypatch.delenv("JARVO_REPO")
    (tmp_path / "program" / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    pu, u = cad._przy_uzyciu()
    assert pu.__name__ == "jarvo.przy_uzyciu" and Path(u.root) == tmp_path and u.stan == tmp_path / "stan"


def test_silnik_natywnie_instaluje_sie_przy_pierwszym_uzyciu(natywnie, capsys):
    pu = natywnie()
    with pytest.raises(cad.Blad, match="pierwsze `cad.py zbuduj`"):
        cad.cad_python(instaluj=False)
    assert pu.wywolania == []
    assert cad.cad_python() == str(pu.python) and pu.wywolania == ["venv cad"]
    assert "pierwsze użycie" in capsys.readouterr().err                       # postęp na stderr, stdout dla raportu
    assert cad.cad_python() == str(pu.python) and pu.wywolania == ["venv cad"]   # drugi raz bez instalacji
    pu.python.unlink()
    natywnie(blad="brak sieci")
    with pytest.raises(cad.Blad, match="silnik CAD: brak sieci"):
        cad.cad_python()


def test_three_kolejnosc_zrodel_i_pobranie_przy_uzyciu(natywnie, monkeypatch, tmp_path):
    def paczka(k: Path) -> Path:
        for rel in ("build/three.module.js", "examples/jsm/loaders/GLTFLoader.js"):
            (k / rel).parent.mkdir(parents=True, exist_ok=True)
            (k / rel).write_text("//", encoding="utf-8")
        return k

    pu = natywnie()
    with pytest.raises(cad.Blad, match="Three.js"):
        cad.three_root(instaluj=False)
    (tmp_path / "niepelny" / "three").mkdir(parents=True)                      # katalog bez plików paczki: pomijany
    z_node = paczka(tmp_path / "node_modules" / "three")
    monkeypatch.setenv("NODE_PATH", os.pathsep.join([str(tmp_path / "niepelny"), str(tmp_path / "node_modules")]))
    assert cad.three_root() == z_node and pu.wywolania == []                  # paczka z NODE_PATH: bez pobierania
    monkeypatch.setenv("NODE_PATH", "")
    assert cad.three_root() == pu.three and pu.wywolania == ["narzedzie three"]
    wlasny = paczka(tmp_path / "wlasny-three")
    monkeypatch.setenv("JARVO_THREE_DIR", str(wlasny))
    assert cad.three_root() == pu.three                     # instalacja: wersja z manifestu, nie zmienna sprzed restartu
    monkeypatch.setattr(cad, "_przy_uzyciu", lambda: (None, None))
    assert cad.three_root() == wlasny                                          # bez instalacji natywnej: zmienna


def test_silnik_natywnie_wygrywa_ze_zmienna_sprzed_aktualizacji(natywnie, monkeypatch, tmp_path):
    """Po aktualizacji locka JARVO_CAD_PYTHON bramy wskazuje jeszcze stary venv: instalacja natywna bierze venv dla
    locka tej wersji (gotowy albo instalowany teraz), a sama zmienna liczy się tylko poza nią."""
    stary = tmp_path / "venvs" / "cad-stary" / "python.exe"
    stary.parent.mkdir(parents=True)
    stary.write_bytes(b"")
    monkeypatch.setenv("JARVO_CAD_PYTHON", str(stary))
    pu = natywnie()
    assert cad.cad_python() == str(pu.python) and pu.wywolania == ["venv cad"]
    monkeypatch.setattr(cad, "_przy_uzyciu", lambda: (None, None))
    assert cad.cad_python() == str(stary)


def test_render_node_w_obrazie_python_natywnie(monkeypatch):
    wywolane = []
    monkeypatch.setattr(cad, "_node", lambda z, limit=900, node=None: wywolane.append(("node", node)) or {"ok": 1})
    monkeypatch.setattr(cad, "_python", lambda z, limit=900: wywolane.append(("python", None)) or {"ok": 1})
    monkeypatch.delenv("JARVO_CAD_RENDER", raising=False)
    monkeypatch.setattr(cad, "node_podglad", lambda: "/usr/bin/node")
    cad.render({"tryb": "png"})
    monkeypatch.setattr(cad, "node_podglad", lambda: None)
    cad.render({"tryb": "png"})
    monkeypatch.setenv("JARVO_CAD_RENDER", "python")
    monkeypatch.setattr(cad, "node_podglad", lambda: pytest.fail("python wymuszony: bez sprawdzania Node"))
    cad.render({"tryb": "png"})
    assert wywolane == [("node", "/usr/bin/node"), ("python", None), ("python", None)]
    monkeypatch.setenv("JARVO_CAD_RENDER", "node")
    monkeypatch.setattr(cad, "node_podglad", lambda: None)
    with pytest.raises(cad.Blad, match="JARVO_CAD_RENDER=node"):
        cad.render({"tryb": "png"})


def test_podglad_python_przekazuje_chromium_i_three(natywnie, monkeypatch, tmp_path):
    pu = natywnie(three=True)
    chrome = tmp_path / "chrome-headless-shell.exe"
    chrome.write_bytes(b"")
    monkeypatch.setenv("CHROME_PATH", str(chrome))
    zlecone = {}

    def uruchom(argv, zadanie, limit, nazwa):
        zlecone.update(argv=argv, zadanie=zadanie, nazwa=nazwa)
        return {"plik": zadanie.get("out"), "bledy": []}
    monkeypatch.setattr(cad, "_uruchom_render", uruchom)
    monkeypatch.setattr(cad, "python_playwright", lambda: sys.executable)
    cad._python({"tryb": "png", "out": "x.png"})
    assert zlecone["argv"][:2] == [sys.executable, "-I"] and zlecone["argv"][-1] == str(cad.RENDER_PY)
    assert zlecone["zadanie"]["chrome"] == str(chrome) and zlecone["zadanie"]["three"] == str(pu.three)
    monkeypatch.delenv("CHROME_PATH")
    monkeypatch.setattr(cad, "PRZEGLADARKA_KONTENER", tmp_path / "nie-ma")
    with pytest.raises(cad.Blad, match="CHROME_PATH"):
        cad._python({"tryb": "png"})
    monkeypatch.setattr(cad, "python_playwright", lambda: None)
    with pytest.raises(cad.Blad, match="Playwright"):
        cad._python({"tryb": "png"})


def test_stan_mowi_co_pobierze_pierwsze_uzycie(natywnie, monkeypatch, tmp_path):
    natywnie()
    chrome = tmp_path / "chrome.exe"
    chrome.write_bytes(b"")
    monkeypatch.setenv("CHROME_PATH", str(chrome))
    monkeypatch.setattr(cad, "node_podglad", lambda: None)
    monkeypatch.setattr(cad, "python_playwright", lambda: sys.executable)
    monkeypatch.setattr(cad, "program_ffmpeg", lambda: str(tmp_path / "ffmpeg.exe"))
    r = cad.stan()
    assert r["silnik"] is None and r["silnik_przy_uzyciu"]["pobranie_mb"] == 215
    assert r["podglad"]["sposob"] == "python" and r["podglad"]["three_przy_uzyciu_mb"] == 4.6
    assert cad.stan_gotowy(r) and "pobierze się przy pierwszym" in cad._opis_stanu(r)
    assert not cad.stan_gotowy({**r, "ffmpeg": None})
    assert not cad.stan_gotowy({**r, "silnik_przy_uzyciu": None})


def test_cad_render_adresy_bez_sieci_i_piaskownica(tmp_path):
    three = tmp_path / "three"
    (three / "build").mkdir(parents=True)
    z = {"glb": str(tmp_path / "m.glb"), "three": str(three)}
    assert render.plik_adresu("http://cad.jarvo/", z) == render.TU / "cad_podglad.html"
    assert render.plik_adresu("http://cad.jarvo/model.glb", z) == Path(z["glb"])
    assert render.plik_adresu("http://cad.jarvo/three/build/three.module.js", z) == (three / "build" /
                                                                                    "three.module.js").resolve()
    assert render.plik_adresu("http://cad.jarvo/three/../../sekret.txt", z) is None          # poza paczką three
    assert render.plik_adresu("http://cad.jarvo/three/%2e%2e/%2e%2e/sekret.txt", z) is None
    assert render.plik_adresu("https://example.com/three/build/three.module.js", z) is None   # inny host
    assert render.plik_adresu("http://cad.jarvo/inne", z) is None
    assert not render.bez_piaskownicy("win32") and not render.bez_piaskownicy("darwin")
    o = render.opcje({"tryb": "obrot", "w": 10, "h": 20, "kat": 5, "wysokosc": 25, "tlo": "#FFFFFF"})
    assert o["obrot"] and o["w"] == 10 and "three" not in o
    html = (SKILL / "scripts" / "cad_podglad.html").read_text(encoding="utf-8")
    assert '"/three/build/three.module.js"' in html                            # te same adresy co page.route


def test_ffmpeg_pelna_sciezka_z_instalacji():
    cmd = cad.polecenie_ffmpeg(24, Path("o.mp4"), "k%05d.png", "C:/Jarvo/ffmpeg/bin/ffmpeg.exe")
    assert cmd[0] == "C:/Jarvo/ffmpeg/bin/ffmpeg.exe" and cmd[cmd.index("-framerate") + 1] == "24"


# ------------------------------------------------------------------ z prawdziwym silnikiem i przeglądarką

def _silnik() -> str | None:
    for k in (os.environ.get("JARVO_CAD_PYTHON"), cad.CAD_PYTHON):
        if k and Path(k).exists():
            return k
    return None


def _podglad_dostepny() -> bool:
    """Podgląd z obrazu (node + three + playwright-core) albo natywny (Playwright dla Pythona, CHROME_PATH, three)."""
    if shutil.which("node"):
        p = subprocess.run(["node", "-e", "require.resolve('three'); require('playwright-core')"], capture_output=True)
        if p.returncode == 0 and (Path("/etc/hermes/agent-browser-executable-path").exists()
                                  or bool(os.environ.get("CHROME_PATH"))):
            return True
    try:
        cad.three_root(instaluj=False)
    except cad.Blad:
        return False
    return bool(cad.python_playwright() and cad.przegladarka())


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
    assert (tmp_path / "katownik.step").read_text(encoding="utf-8", errors="ignore").startswith("ISO-10303-21")
    zly = tmp_path / "zly.py"
    zly.write_text("from build123d import *\nwynik = Box(10, 10, 10)\nimport urllib.request\n"
                   "urllib.request.urlopen('https://example.com')\n", encoding="utf-8")
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

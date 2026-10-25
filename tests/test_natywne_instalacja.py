"""Instalator natywny kompletny (docs/NATYWNIE.md: c3, c4, H05, S01, S11, F12, E05; etap E4): narzędzia, venvy,
modele, Tesseract z pixi, programy floty, klucz API bramy, środowisko procesów i flota po jednym poleceniu.

Na atrapach programów (tests/atrapy.py: uv, pixi) i plikach z serwera na 127.0.0.1 (porty 19100–19199): kolejność
narzędzi z manifestu dla każdej platformy, venv z locka z sumą (uv venv + uv pip install --require-hashes --no-deps,
--torch-backend z manifestu), drugi przebieg bez uv i bez sieci, modele z JARVO-ZRODLO.txt i znacznikiem, Tesseract
z pixi.lock (konfiguracje obok języków z modelu, języki paczki usunięte), koło programów floty odtwarzalne bajt w bajt,
trampoliny uv kopiowane do bin-floty (Windows) albo skrypty sh z exec (POSIX), wejście programów floty (skrypt
infra/bin aktywnej wersji, zmienne z srodowisko.json bez nadpisywania), środowisko z buildu i narzędzi (JARVO_HERMES_BIN
tylko z plikiem), klucze configu profili z install_fleet.py --ustawienia-profili bez zmian w drugim przebiegu, klucz
i port API w <dane>/.env oraz doctor bramy. Pełny przebieg instalatora z gitem i Node z manifestu, venvem, modelem
i Tesseractem na atrapach modułów, z restartem usług przez nadzorcę, gdy zmieniła się tylko flota.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, WINDOWS

sys.path.insert(0, str(REPO))
from jarvo import bin_floty, cli, flota, instalator, manifest, modele, programy_floty, sciezki  # noqa: E402
from jarvo import srodowisko, tesseract, venvy  # noqa: E402
import install_fleet  # noqa: E402  (scripts/ w sys.path z conftest)

import test_natywne_cli as tc  # noqa: E402  (atrapy modułów i stanowisko instalatora)

LOCK = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
stanowisko = tc.stanowisko                                       # fixture z testów instalatora
serwer = tc.serwer


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def uklad(root: Path) -> sciezki.Uklad:
    u = sciezki.Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                      logi=root / "logi", cache=root / "cache", build=root / "build")
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    return u


# ---------------------------------------------------------------- narzędzia z manifestu

@pytest.mark.parametrize("platforma", sciezki.PLATFORMY)
def test_narzedzia_instalacji_z_manifestu_w_kolejnosci(platforma):
    narz = LOCK["narzedzia"]
    nazwy = instalator.narzedzia_instalacji(narz, platforma)
    assert nazwy[:3] == ["uv", "python313", "python312"]
    reszta = nazwy[3:]
    if platforma.startswith("windows"):
        assert reszta[:2] == ["git", "node"]                     # Windows: git z Git Bash przed Node.js
        reszta = reszta[2:]
    else:
        assert "git" not in nazwy and reszta[0] == "node"        # macOS i Linux: git z systemu (manifest: brak)
        reszta = reszta[1:]
    assert reszta == sorted(reszta)
    assert "camoufox" not in nazwy and "scrcpy" not in nazwy     # kiedy: przy-uzyciu
    for n in nazwy:                                              # każde ma plik dla platformy (bez `brak`)
        assert "url" in manifest.plik(narz, n, platforma)
    assert ("lightpanda" in nazwy) is (not platforma.startswith("windows"))
    assert ("ffmpeg-macos" in nazwy) is (platforma == "macos-arm64")
    assert {"pixi", "chrome-headless-shell", "pandoc", "qpdf", "exiftool", "ripgrep", "jq"} <= set(nazwy)


def test_narzedzia_instalacji_pomija_brak_i_przy_uzyciu():
    wpis = {"url": "https://x/a.zip", "sha256": "0" * 64}
    narz = {"z": {"pliki": {"linux-x64": wpis}}, "node": {"pliki": {"linux-x64": wpis}},
            "uv": {"kiedy": "instalacja", "pliki": {"linux-x64": wpis}},
            "brak": {"pliki": {"linux-x64": {"brak": "nie ma"}}},
            "leniwy": {"kiedy": "przy-uzyciu", "pliki": {"linux-x64": wpis}}, "obcy": {"pliki": {}}}
    assert instalator.narzedzia_instalacji(narz, "linux-x64") == ["uv", "node", "z"]


# ---------------------------------------------------------------- venvy

ATRAPA_UV = r'''
import json, os, sys, zipfile
from pathlib import Path
a = sys.argv[1:]
with open(os.environ["ATRAPA_UV_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps(a) + "\n")
if a[0] == "venv":
    kat = Path(a[-1])
    py = kat / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_bytes(b"atrapa pythona")
    (kat / "pyvenv.cfg").write_text("home = atrapa\n", encoding="utf-8")
elif a[:2] == ["pip", "install"]:
    if os.environ.get("ATRAPA_UV_KOD"):
        print("error: Hash mismatch for `numpy`")
        sys.exit(int(os.environ["ATRAPA_UV_KOD"]))
    plik = a[-1]
    if plik.endswith(".whl"):                    # koło programów floty: trampoliny jak uv (Scripts/<nazwa>.exe)
        py = Path(a[a.index("--python") + 1])
        with zipfile.ZipFile(plik) as z:
            punkty = next(n for n in z.namelist() if n.endswith("entry_points.txt"))
            for linia in z.read(punkty).decode().splitlines():
                if " = " in linia:
                    nazwa = linia.split(" = ")[0]
                    if nazwa in ("python", "python3", "pythonw"):            # jak uv 0.12.13
                        print(f"Caused by: Scripts must not use the reserved name `{nazwa}`, got: `{nazwa}`")
                        sys.exit(2)
                    (py.parent / (nazwa + (".exe" if os.name == "nt" else ""))).write_bytes(
                        b"MZ trampolina " + nazwa.encode() + b" " + str(py).encode())
    print("Installed 1 package")
'''


@pytest.fixture
def uv(tmp_path, monkeypatch):
    log = tmp_path / "uv.log"
    monkeypatch.setenv("ATRAPA_UV_LOG", str(log))
    monkeypatch.delenv("ATRAPA_UV_KOD", raising=False)
    program = atrapy.program(tmp_path / "uv-bin", "uv", ATRAPA_UV)

    def wywolania() -> list[list[str]]:
        return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
    return program, wywolania


def _lock(app: Path, tresc: str = "numpy==2.5.4 --hash=sha256:" + "a" * 64 + "\n") -> dict:
    p = app / "infra" / "python" / "natywne" / "narzedzia.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tresc, encoding="utf-8")
    return {"python": "python312", "lock": "infra/python/natywne/narzedzia.lock", "sha256": _sha(p.read_bytes()),
            "paczek": 1, "kiedy": "instalacja"}


def test_venv_z_locka_z_sumami_i_drugi_przebieg_bez_uv(tmp_path, uv):
    program_uv, wywolania = uv
    u, app = uklad(tmp_path / "j"), tmp_path / "app"
    wpis = _lock(app)
    python = tmp_path / "py312" / "python.exe"
    python.parent.mkdir()
    python.write_bytes(b"")
    spis, zmiana = venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(program_uv), python=python,
                                    log=lambda _t: None)
    kat = u.program / "venvs" / f"narzedzia-{wpis['sha256'][:12]}"
    assert zmiana and spis["katalog"] == str(kat) and spis["python"] == str(venvy.python_venvu(kat))
    assert spis["env"] == {"JARVO_TOOLS_PYTHON": str(venvy.python_venvu(kat))}
    assert spis["bin"] == [str(venvy.bin_venvu(kat))]                       # yt-dlp, trafilatura w PATH floty
    w = wywolania()
    assert w[0][:4] == ["venv", "--no-config", "--python", str(python)] and w[0][-1] == str(kat)
    pip = w[1]
    assert pip[:3] == ["pip", "install", "--no-config"] and pip[pip.index("--python") + 1] == str(spis["python"])
    assert {"--no-deps", "--require-hashes", "--compile-bytecode"} <= set(pip)
    assert pip[pip.index("--only-binary") + 1] == ":all:" and pip[-2:] == ["-r", str(app / wpis["lock"])]
    assert "--torch-backend" not in pip
    assert json.loads((kat / venvy.ZNACZNIK).read_text(encoding="utf-8"))["lock_sha256"] == wpis["sha256"]
    # drugi przebieg: znacznik zgodny, bez uv
    spis2, zmiana2 = venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(program_uv), python=python,
                                      log=lambda _t: None)
    assert spis2 == spis and not zmiana2 and len(wywolania()) == 2
    # venv bez znacznika (przerwana instalacja): od nowa; torch_backend z manifestu
    (kat / venvy.ZNACZNIK).unlink()
    (kat / "resztka.txt").write_text("x", encoding="utf-8")
    venvy.zainstaluj(u, app, "ocr", {**wpis, "torch_backend": "cpu"}, uv=Path(program_uv), python=python,
                     log=lambda _t: None)
    pip = wywolania()[-1]
    assert pip[pip.index("--torch-backend") + 1] == "cpu"
    ocr = u.program / "venvs" / f"ocr-{wpis['sha256'][:12]}"
    assert venvy.wpis_spisu("ocr", wpis, ocr)["env"] == {"JARVO_OCR_PYTHON": str(venvy.python_venvu(ocr))}
    assert venvy.wpis_spisu("ocr", wpis, ocr)["bin"] == []


def test_venv_odmawia_zmienionego_locka_i_bledu_uv(tmp_path, uv, monkeypatch):
    program_uv, wywolania = uv
    u, app = uklad(tmp_path / "j"), tmp_path / "app"
    wpis = _lock(app)
    python = tmp_path / "python.exe"
    python.write_bytes(b"")
    (app / wpis["lock"]).write_text("numpy==9.9.9\n", encoding="utf-8")       # lock bez `natywne.py generuj`
    with pytest.raises(venvy.BladVenvu, match="natywne.py generuj"):
        venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(program_uv), python=python, log=lambda _t: None)
    assert wywolania() == []
    wpis = _lock(app)
    monkeypatch.setenv("ATRAPA_UV_KOD", "2")
    with pytest.raises(venvy.BladVenvu, match="suma pliku z PyPI nie zgadza się"):
        venvy.zainstaluj(u, app, "narzedzia", wpis, uv=Path(program_uv), python=python, log=lambda _t: None)
    assert not (venvy.katalog(u, "narzedzia", wpis) / venvy.ZNACZNIK).exists()


def test_venvy_do_instalacji_z_manifestu():
    assert set(venvy.do_instalacji(LOCK["venvy"])) == {"narzedzia", "ocr", "claude-seo"}
    for nazwa, wpis in LOCK["venvy"].items():                   # locki w repo mają sumy z manifestu
        assert _sha((REPO / wpis["lock"]).read_bytes()) == wpis["sha256"], nazwa


# ---------------------------------------------------------------- modele

def test_model_z_sumami_zrodlem_i_drugi_przebieg_bez_sieci(tmp_path, serwer):
    www, adres = serwer
    pliki = {"meski/model.onnx": b"wagi" * 100, "LICENSE": b"CC-BY-SA-4.0\n"}
    for rel, dane in pliki.items():
        (www / rel.replace("/", "_")).write_bytes(dane)
    model = {"zrodlo": "atrapa-tts", "rewizja": "9" * 40, "licencja": "CC-BY-SA-4.0", "rola": "lektor",
             "katalog": "matcha-pl", "pliki": [{"cel": rel, "url": f"{adres}/{rel.replace('/', '_')}",
                                                "sha256": _sha(d), "rozmiar": len(d)} for rel, d in pliki.items()]}
    kat_modeli = tmp_path / "dane" / "jarvo" / "models"
    spis, zmiana = modele.zainstaluj("matcha-pl", model, kat_modeli, log=lambda _t: None, pasek=False)
    kat = kat_modeli / "matcha-pl"
    assert zmiana and (kat / "meski" / "model.onnx").read_bytes() == pliki["meski/model.onnx"]
    assert spis == {"wersja": "9" * 12, "katalog": str(kat), "bin": [], "env": {"JARVO_TTS_MATCHA_DIR": str(kat)}}
    zrodlo = (kat / modele.ZRODLO).read_text(encoding="utf-8")
    assert "atrapa-tts" in zrodlo and "9" * 40 in zrodlo and "CC-BY-SA-4.0" in zrodlo
    for p in list(www.iterdir()):                                # bez sieci: pliki zniknęły z serwera
        p.unlink()
    spis2, zmiana2 = modele.zainstaluj("matcha-pl", model, kat_modeli, log=lambda _t: None, pasek=False)
    assert spis2 == spis and not zmiana2
    assert modele.do_instalacji(LOCK["modele"]) == [n for n, m in LOCK["modele"].items()
                                                    if m.get("kiedy", "instalacja") == "instalacja"]
    assert {"matcha-pl", "paradee", "indra-ocr", "tessdata-fast"} <= set(modele.do_instalacji(LOCK["modele"]))
    assert "parakeet" not in modele.do_instalacji(LOCK["modele"])          # przy pierwszym użyciu


def test_model_ze_zla_suma_zatrzymuje(tmp_path, serwer):
    www, adres = serwer
    (www / "plik").write_bytes(b"podmieniony")
    model = {"rewizja": "1" * 40, "katalog": "m", "pliki": [{"cel": "plik", "url": f"{adres}/plik",
                                                             "sha256": _sha(b"oryginal"), "rozmiar": 8}]}
    with pytest.raises(modele.BladModelu, match="suma sha256 się nie zgadza|nie udało się pobrać"):
        modele.zainstaluj("m", model, tmp_path / "models", log=lambda _t: None, pasek=False)
    assert not (tmp_path / "models" / "m" / modele.ZNACZNIK).exists()


# ---------------------------------------------------------------- Tesseract z pixi

ATRAPA_PIXI = r'''
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
with open(os.environ["ATRAPA_PIXI_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": a, "env": {k: os.environ.get(k) for k in (
        "PIXI_NO_TELEMETRY", "PIXI_NO_CONFIG", "PIXI_CACHE_DIR", "PIXI_HOME")}}) + "\n")
kat = Path(a[a.index("--manifest-path") + 1]).parent
env = kat / ".pixi" / "envs" / "default"
if os.name == "nt":        # jak conda-forge tesseract 5.5.3 na Windows: konfiguracje i języki w dwóch katalogach
    tess, konfig, jezyki = (env / "Library" / "bin" / "tesseract.exe", env / "Library" / "share" / "tessdata",
                            env / "share" / "tessdata")
else:
    tess, konfig, jezyki = env / "bin" / "tesseract", env / "share" / "tessdata", env / "share" / "tessdata"
tess.parent.mkdir(parents=True, exist_ok=True)
tess.write_bytes(b"atrapa tesseracta")
(konfig / "configs").mkdir(parents=True, exist_ok=True)
(konfig / "configs" / "tsv").write_text("tessedit_create_tsv 1\n", encoding="utf-8")
(konfig / "pdf.ttf").write_bytes(b"kroj")
jezyki.mkdir(parents=True, exist_ok=True)
for j in ("pol", "eng", "deu", "san"):
    (jezyki / f"{j}.traineddata").write_bytes(b"j" * 1000)
print("The default environment has been installed.")
'''


def _projekt_pixi(app: Path) -> None:
    for rel in tesseract.PLIKI_PROJEKTU:
        src = REPO / tesseract.PROJEKT / rel
        cel = app / tesseract.PROJEKT / rel
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_bytes(src.read_bytes())


@pytest.mark.parametrize("platforma", ["windows-x64", "windows-arm64", "linux-x64"])
def test_tesseract_z_pixi_lock_konfiguracje_obok_jezykow(tmp_path, monkeypatch, platforma):
    log = tmp_path / "pixi.log"
    monkeypatch.setenv("ATRAPA_PIXI_LOG", str(log))
    monkeypatch.setenv("PIXI_HOME", "zly")                        # zmienne pixi właściciela nie przechodzą
    pixi = atrapy.program(tmp_path / "pixi-bin", "pixi", ATRAPA_PIXI)
    u, app = uklad(tmp_path / "j"), tmp_path / "app"
    _projekt_pixi(app)
    modele_dir = u.jarvo_dane / "models"
    spis, zmiana = tesseract.zainstaluj(u, app, pixi=Path(pixi), env_narzedzia={"PIXI_NO_TELEMETRY": "1"},
                                        platforma=platforma, modele=modele_dir, log=lambda _t: None)
    kat = tesseract.katalog(u, app)
    assert zmiana and spis["program"] == str(tesseract.program(kat)) and spis["bin"] == []
    assert spis["env"] == {"TESSDATA_PREFIX": str(modele_dir / "tessdata-fast")} and spis["wersja"] == "5.5.3"
    wpisy = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    a = wpisy[0]["argv"]
    assert a[:2] == ["install", "--locked"] and a[a.index("--manifest-path") + 1] == str(kat / "pixi.toml")
    assert (a[-2:] == ["--platform", "win-64"]) is (platforma == "windows-arm64")
    assert wpisy[0]["env"] == {"PIXI_NO_TELEMETRY": "1", "PIXI_NO_CONFIG": "1",
                               "PIXI_CACHE_DIR": str(u.cache / "pixi"), "PIXI_HOME": str(u.cache / "pixi-home")}
    assert (kat / "pixi.lock").read_bytes() == (REPO / tesseract.PROJEKT / "pixi.lock").read_bytes()
    jezyki = modele_dir / "tessdata-fast"
    assert (jezyki / "configs" / "tsv").is_file() and (jezyki / "pdf.ttf").is_file()
    for tessdata in tesseract.katalogi_tessdata(kat):                      # języki z modelu, nie z paczki
        assert not list(tessdata.glob("*.traineddata"))
    # drugi przebieg: bez pixi
    spis2, zmiana2 = tesseract.zainstaluj(u, app, pixi=Path(pixi), env_narzedzia={}, platforma=platforma,
                                          modele=modele_dir, log=lambda _t: None)
    assert spis2 == spis and not zmiana2 and len(log.read_text(encoding="utf-8").splitlines()) == 1


# ---------------------------------------------------------------- programy floty

def test_kolo_programow_odtwarzalne_z_punktami_wejscia():
    nazwa, kolo = bin_floty.zbuduj_kolo()
    assert (nazwa, kolo) == bin_floty.zbuduj_kolo()                          # te same bajty: drugi przebieg bez uv
    assert nazwa == "jarvo_programy_floty-1.0-py3-none-any.whl"
    with zipfile.ZipFile(__import__("io").BytesIO(kolo)) as z:
        punkty = z.read("jarvo_programy_floty-1.0.dist-info/entry_points.txt").decode()
        modul = z.read("jarvo_programy_floty.py")
        assert b"\r\n" not in modul and b"def uruchom_skrypt" in modul
        rekord = z.read("jarvo_programy_floty-1.0.dist-info/RECORD").decode()
    for program in ("jarvo-python3", "jarvo-tts", "jarvo-stt", "jarvo-klucz", "jarvo-tesseract"):
        assert re.search(rf"^{program} = jarvo_programy_floty:\w+$", punkty, re.M)
    assert not re.search(r"^(python3?|tesseract) = ", punkty, re.M)       # uv: nazwa python3 zastrzeżona
    assert "jarvo_programy_floty.py,sha256=" in rekord


def test_programy_floty_w_bin_floty(tmp_path, uv):
    program_uv, wywolania = uv
    u = uklad(tmp_path / "j")
    venv_py = venvy.python_venvu(u.program / "venvs" / "narzedzia-abc")
    venv_py.parent.mkdir(parents=True)
    venv_py.write_bytes(b"")
    tess = tmp_path / "tess" / ("tesseract.exe" if WINDOWS else "tesseract")
    tess.parent.mkdir()
    tess.write_bytes(b"")
    zmiany = bin_floty.przygotuj(u, venv_python=venv_py, uv=Path(program_uv), tesseract=tess, log=lambda _t: None)
    nazwy = {bin_floty.nazwa_pliku(n) for n in ("python3", "jarvo-tts", "jarvo-stt", "jarvo-klucz", "tesseract")}
    assert nazwy <= {p.name for p in u.bin_floty.iterdir()} and zmiany
    if WINDOWS:                                   # trampoliny uv z venvu narzędzi (koło bez sieci)
        pip = wywolania()[0]
        assert {"--offline", "--no-index", "--no-deps", "--reinstall"} <= set(pip) and pip[-1].endswith(".whl")
        assert (u.bin_floty / "jarvo-stt.exe").read_bytes() == (venv_py.parent / "jarvo-stt.exe").read_bytes()
        assert (u.bin_floty / "python3.exe").read_bytes() == (venv_py.parent / "jarvo-python3.exe").read_bytes()
        assert not (venv_py.parent / "python3.exe").exists()          # w Scripts (PATH floty) bez drugiego python3
    else:                                         # skrypty sh z exec
        tekst = (u.bin_floty / "jarvo-tts").read_text(encoding="utf-8")
        assert tekst.startswith("#!/bin/sh\n") and f"exec {venv_py}" in tekst and "jarvo-tts" in tekst
        assert os.access(u.bin_floty / "python3", os.X_OK) and wywolania() == []
        assert (u.bin_floty / "jarvo_programy_floty.py").read_bytes() == bin_floty._zrodlo()
    # drugi przebieg: nic; bez Tesseracta shim znika
    assert bin_floty.przygotuj(u, venv_python=venv_py, uv=Path(program_uv), tesseract=tess,
                               log=lambda _t: None) == []
    assert len(wywolania()) == (1 if WINDOWS else 0)
    assert bin_floty.przygotuj(u, venv_python=venv_py, uv=Path(program_uv), tesseract=None,
                               log=lambda _t: None) == [f"-{bin_floty.nazwa_pliku('tesseract')}"]
    assert bin_floty.sprawdz(u) == {"python3": True, "jarvo-tts": True, "jarvo-stt": True, "jarvo-klucz": True,
                                    "tesseract": False}


@pytest.mark.posix_only
def test_python3_floty_na_posix_to_python_venvu(tmp_path):
    u = uklad(tmp_path / "j")
    bin_floty.przygotuj(u, venv_python=Path(sys.executable), log=lambda _t: None)
    r = subprocess.run([str(u.bin_floty / "python3"), "-c", "import sys; print(sys.executable)"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and Path(r.stdout.strip()).name.startswith("python")


def _instalacja_programow(tmp_path: Path) -> Path:
    """<program> z current.json, kod Jarva ze skryptem infra/bin/jarvo-tts i <stan>/srodowisko.json."""
    root = tmp_path / "Jarvo"
    program = root / "program"
    app = program / "app" / "abc"
    skrypt = app / "infra" / "bin" / "jarvo-tts"
    skrypt.parent.mkdir(parents=True)
    skrypt.write_text("import json, os, sys\nfrom pathlib import Path\n"
                      "Path(os.environ['ATRAPA_WYNIK']).write_text(json.dumps({'argv': sys.argv, 'plik': __file__, "
                      "'model': os.environ.get('JARVO_TTS_MODEL_DIR'), 'stary': os.environ.get('STARA')}))\n"
                      "sys.exit(3)\n", encoding="utf-8")
    (program / "current.json").write_text(json.dumps({"app": str(app)}), encoding="utf-8")
    (root / "stan").mkdir()
    (root / "stan" / "srodowisko.json").write_text(json.dumps({
        "JARVO_TTS_MODEL_DIR": str(root / "dane" / "jarvo" / "models" / "paradee"), "STARA": "z pliku",
        "PATH": str(program / "bin-floty")}), encoding="utf-8")
    (program / "bin-floty").mkdir()
    return program


def test_wejscie_programow_floty_uruchamia_skrypt_aktywnej_wersji(tmp_path, monkeypatch):
    program = _instalacja_programow(tmp_path)
    wynik = tmp_path / "wynik.json"
    monkeypatch.setenv("ATRAPA_WYNIK", str(wynik))
    monkeypatch.setenv("STARA", "z otoczenia")                              # zmienna z otoczenia zostaje
    monkeypatch.delenv("JARVO_TTS_MODEL_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", [str(program / "bin-floty" / "jarvo-tts"), "--sprawdz"])
    zapisany_argv = list(sys.argv)
    assert programy_floty.jarvo_tts() == 3
    w = json.loads(wynik.read_text(encoding="utf-8"))
    assert w["argv"][1:] == ["--sprawdz"] and Path(w["plik"]).name == "jarvo-tts"
    assert w["model"].endswith("paradee") and w["stary"] == "z otoczenia"
    assert str(program / "bin-floty") in os.environ["PATH"].split(os.pathsep)
    assert zapisany_argv[0].endswith("jarvo-tts")
    # z katalogu Scripts venvu (trzy poziomy niżej) ten sam <program>
    assert programy_floty.katalog_programu(str(program / "venvs" / "narzedzia-x" / "Scripts" / "jarvo-tts")) == \
        program
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "gdzies" / "jarvo-stt")])
    monkeypatch.setattr(programy_floty, "__file__", str(tmp_path / "x.py"))
    assert programy_floty.jarvo_stt() == 1                                  # bez current.json: komunikat i kod 1


def test_wejscie_python3_i_tesseract_z_instalacji(tmp_path, monkeypatch, capfd):
    program = _instalacja_programow(tmp_path)
    (program.parent / "stan" / "narzedzia.json").write_text(json.dumps(
        {"venv-narzedzia": {"python": sys.executable}, "tesseract": {"program": str(tmp_path / "brak.exe")}}),
        encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(program / "bin-floty" / "python3"), "-c", "import sys; sys.exit(7)"])
    assert programy_floty.python3() == 7
    monkeypatch.setattr(sys, "argv", [str(program / "bin-floty" / "tesseract"), "--version"])
    assert programy_floty.tesseract() == 1 and "nie ma go w tej instalacji" in capfd.readouterr().err
    assert programy_floty.main([]) == 2 and programy_floty.main(["nieznany"]) == 1


# ---------------------------------------------------------------- środowisko procesów

def test_srodowisko_z_buildu_narzedzi_i_venvow(tmp_path):
    u = uklad(tmp_path / "j")
    checkout = u.program / "hermes" / "abc"
    (u.build / "host").mkdir(parents=True)
    (u.build / "host" / "srodowisko.json").write_text(json.dumps({
        "HERMES_LOCAL_STT_COMMAND": '"C:/j/program/bin-floty/jarvo-stt.exe" {input_path}', "PATH": "zly",
        "PYTHONPATH": "zly", "API_SERVER_KEY": "sekret", "HERMES_HOME": "zly", "liczba": 1}), encoding="utf-8")
    narz = {"exiftool": {"bin": [], "env": {"EXIFTOOL_HOME": "E"}},
            "venv-narzedzia": {"python": "P", "bin": [str(tmp_path / "venv-bin")], "env": {"JARVO_TOOLS_PYTHON": "P"}},
            "venv-ocr": {"python": "O", "bin": [], "env": {"JARVO_OCR_PYTHON": "O"}}}
    env = srodowisko.srodowisko(u, {"PATH": "C:\\owner", "JARVO_HERMES_BIN": "cudzy"},
                                biez={"app": "A", "hermes": str(checkout)}, narz=narz)
    assert env["HERMES_LOCAL_STT_COMMAND"].endswith("{input_path}") and env["HERMES_HOME"] == str(u.dane)
    assert env["JARVO_TOOLS_PYTHON"] == "P" and env["JARVO_OCR_PYTHON"] == "O" and env["EXIFTOOL_HOME"] == "E"
    assert "PYTHONPATH" not in env and "API_SERVER_KEY" not in env and "zly" not in env["PATH"]
    assert env["PATH"].split(os.pathsep)[:2] == [str(u.bin_floty), str(tmp_path / "venv-bin")]
    assert "JARVO_HERMES_BIN" not in env                                    # nie ma pliku: bez zmiennej (i cudzej)
    hermes_bin = checkout / ".venv" / ("Scripts/hermes.exe" if WINDOWS else "bin/hermes")
    hermes_bin.parent.mkdir(parents=True)
    hermes_bin.write_bytes(b"")
    env = srodowisko.srodowisko(u, {}, biez={"hermes": str(checkout)}, narz=narz)
    assert env["JARVO_HERMES_BIN"] == str(hermes_bin)
    # srodowisko.json: zmienne narzędzi i buildu (także bez przedrostków Jarva), bez sekretów i PATH właściciela
    srodowisko.zapisz(u, srodowisko.srodowisko(u, {}, narz=narz), narz=narz)
    zapis = json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))
    assert {"EXIFTOOL_HOME", "JARVO_TOOLS_PYTHON", "HERMES_LOCAL_STT_COMMAND", "JARVO_WEJSCIE_DIR"} <= set(zapis)
    assert "API_SERVER_KEY" not in zapis and "C:\\owner" not in zapis["PATH"]


# ---------------------------------------------------------------- install_fleet.py: klucze configu profili

def test_ustawienia_profili_w_tym_samym_przebiegu_bez_zmian_drugi_raz(tmp_path):
    dane, build = tmp_path / "dane", tmp_path / "build"
    plik = tmp_path / "ustawienia.json"
    plik.write_text(json.dumps({"wszystkie": {"updates.check": False},
                                "profile": {"jarvo": {"terminal.shell_init_files": ["C:/j/stan/powloka/jarvo.sh"]}}}),
                    encoding="utf-8")
    a = install_fleet.parser().parse_args(["--dane", str(dane), "--build", str(build), "--natywnie",
                                           "--bez-sekretow", "--ustawienia-profili", str(plik)])
    f = install_fleet.Flota(a, wypisz=lambda _t: None)
    config = dane / "profiles" / "jarvo" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("model:\n  default: x\nterminal:\n  home_mode: profile\n", encoding="utf-8")
    f.ustaw_klucze_profilu("jarvo", config)
    import yaml
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert cfg["updates"] == {"check": False} and cfg["model"] == {"default": "x"}
    assert cfg["terminal"] == {"home_mode": "profile", "shell_init_files": ["C:/j/stan/powloka/jarvo.sh"]}
    assert b"\r\n" not in config.read_bytes()
    przed = config.stat().st_mtime_ns
    f.ustaw_klucze_profilu("jarvo", config)                                # ta sama wartość: bez zapisu
    assert config.stat().st_mtime_ns == przed
    other = dane / "profiles" / "jarvo-web" / "config.yaml"
    other.parent.mkdir(parents=True)
    other.write_text("model: {}\n", encoding="utf-8")
    f.ustaw_klucze_profilu("jarvo-web", other)
    assert "shell_init_files" not in other.read_text(encoding="utf-8")
    assert yaml.safe_load(other.read_text(encoding="utf-8"))["updates"] == {"check": False}


def test_flota_przekazuje_ustawienia_profili(tmp_path):
    u = uklad(tmp_path / "Jarvo")
    (u.build / "BUILD.json").write_text(json.dumps({"agents": [{"agent": "jarvo"}, {"agent": "jarvo-web"}]}),
                                        encoding="utf-8")
    assert flota.agenci_buildu(u) == ["jarvo", "jarvo-web"]
    ust = flota.ustawienia_profili(u, ["jarvo"])
    assert ust["wszystkie"] == {"updates.check": False}
    assert ust["profile"] == ({"jarvo": {"terminal.shell_init_files": [str(u.stan / "powloka" / "jarvo.sh")]}}
                              if WINDOWS else {})
    argv = flota.argv_instalacji(u, tmp_path / "app", Path(sys.executable), pierwsza=False, wznow_rutyny=False,
                                 ustawienia=u.stan / "x.json")
    assert argv[argv.index("--ustawienia-profili") + 1] == str(u.stan / "x.json")


# ---------------------------------------------------------------- klucz i port API bramy

def test_ustaw_w_env_i_port_api(tmp_path):
    tekst = "# komentarz\nOPENROUTER_API_KEY=sk\nAPI_SERVER_PORT=1\nAPI_SERVER_PORT=2\n"
    nowy = instalator.ustaw_w_env(tekst, "API_SERVER_PORT", "19161")
    assert nowy == "# komentarz\nOPENROUTER_API_KEY=sk\nAPI_SERVER_PORT=19161\n"
    assert instalator.ustaw_w_env("", "A", "1") == "A=1\n" and instalator.ustaw_w_env("B=2", "A", "1") == "B=2\nA=1\n"
    u = uklad(tmp_path / "j")
    assert instalator.port_api(u, {}) == 8642
    (u.dane / ".env").write_text("API_SERVER_PORT=19000\n", encoding="utf-8")
    assert instalator.port_api(u, {}) == 19000                              # zapisany wygrywa z domyślnym
    assert instalator.port_api(u, {"JARVO_API_PORT": "19161"}) == 19161     # jawna zmienna wygrywa
    assert instalator.port_api(u, {"JARVO_API_PORT": "zly"}) == 19000
    assert not instalator.klucz_api_dobry("krotki") and not instalator.klucz_api_dobry("changeme")
    assert instalator.klucz_api_dobry("a" * 64)


def test_doctor_brama_api(tmp_path):
    u = tc._zainstalowane(tmp_path)
    ot = tc._ot(tmp_path, env={"JARVO_API_PORT": "19161"})
    assert cli.sprawdz_brame(u, ot, {"uslugi": {}})["stan"] == "blad"      # bez klucza
    (u.dane / ".env").write_text("API_SERVER_KEY=" + "b" * 64 + "\n", encoding="utf-8")
    assert cli.sprawdz_brame(u, ot, None)["stan"] == "uwaga"                # serwis nie działa
    adresy = []

    def zapytaj(url, czas):
        adresy.append(url)
        return 200, {"status": "ok", "platform": "hermes-agent", "version": "0.21.5"}
    ot = tc._ot(tmp_path, env={"JARVO_API_PORT": "19161"}, zapytaj_http=zapytaj)
    w = cli.sprawdz_brame(u, ot, {"uslugi": {"brama": {"stan": "dziala"}}})
    assert w["stan"] == "ok" and adresy == ["http://127.0.0.1:19161/health"]
    ot = tc._ot(tmp_path, env={"JARVO_API_PORT": "19161"}, zapytaj_http=lambda url, czas: None)
    w = cli.sprawdz_brame(u, ot, {"uslugi": {"brama": {"stan": "dziala"}}})
    assert w["stan"] == "blad" and "jarvo logs brama" in w["rada"]
    assert dict(cli._porty(u, ot.env))["API bramy"] == 19161


def test_doctor_narzedzia_programy_i_git_z_manifestu(tmp_path):
    u = tc._zainstalowane(tmp_path)
    venv_py = venvy.python_venvu(u.program / "venvs" / "narzedzia-abc")
    venv_py.parent.mkdir(parents=True)
    venv_py.write_bytes(b"")
    git = u.program / "narzedzia" / "git" / "2.56.0"
    (git / "cmd").mkdir(parents=True)
    (git / "cmd" / ("git.exe" if WINDOWS else "git")).write_bytes(b"")
    narz = json.loads((u.stan / "narzedzia.json").read_text(encoding="utf-8"))
    narz.update({"venv-narzedzia": venvy.wpis_spisu("narzedzia", {"sha256": "a" * 64}, venv_py.parent.parent),
                 "model-paradee": {"wersja": "8f34", "katalog": str(tmp_path / "brak-modelu"), "bin": [], "env": {}},
                 "git": {"wersja": "2.56.0.windows.3", "katalog": str(git), "bin": [str(git / "cmd")],
                         "env": {"HERMES_GIT_BASH_PATH": str(git / "bin" / "bash.exe")}}})
    (u.stan / "narzedzia.json").write_text(json.dumps(narz), encoding="utf-8")
    wyniki = {w["nazwa"]: w for w in cli.sprawdz_narzedzia(u)}
    assert wyniki["narzędzia"]["stan"] == "blad" and "model-paradee" in wyniki["narzędzia"]["opis"]
    assert wyniki["programy floty"]["stan"] == "blad" and "python3" in wyniki["programy floty"]["opis"]
    g = cli.sprawdz_git(u, tc._ot(tmp_path))
    if WINDOWS:                                  # bez Git Bash narzędzie terminal agentów nie zadziała
        assert g["stan"] == "blad" and "Git Bash" in g["opis"]
        (git / "bin").mkdir()
        (git / "bin" / "bash.exe").write_bytes(b"")
        assert cli.sprawdz_git(u, tc._ot(tmp_path))["stan"] == "ok"
    else:                                        # POSIX: programy floty bez uv (skrypty sh)
        assert g["stan"] == "ok" and "2.56.0" in g["opis"]
        bin_floty.przygotuj(u, venv_python=venv_py, uv=None, log=lambda _t: None)
        assert {w["nazwa"]: w for w in cli.sprawdz_narzedzia(u)}["programy floty"]["stan"] == "ok"


def test_instalacja_bez_manifestu_konczy_sie_komunikatem(tmp_path, stanowisko):
    s = stanowisko
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    (app / manifest.LOCK).unlink()
    assert tc._instaluj(s, app) == 1
    assert any("manifest narzędzi" in x and "nieczytelny" in x for x in s["log"])


# ---------------------------------------------------------------- pełny przebieg instalatora na atrapach modułów

class AtrapaVenvow:
    def __init__(self):
        self.wywolania = []

    def zainstaluj(self, u, app, nazwa, wpis, *, uv, python, log=print):
        self.wywolania.append((nazwa, Path(uv), Path(python)))
        kat = u.program / "venvs" / f"{nazwa}-{wpis['sha256'][:12]}"
        py = venvy.python_venvu(kat)
        nowy = not py.is_file()
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_bytes(b"")
        return venvy.wpis_spisu(nazwa, wpis, kat), nowy


class AtrapaModeli:
    def zainstaluj(self, nazwa, model, katalog_modeli, *, log=print, pasek=True):
        kat = Path(katalog_modeli) / model["katalog"]
        nowy = not kat.is_dir()
        kat.mkdir(parents=True, exist_ok=True)
        return modele.wpis_spisu(nazwa, model, kat), nowy


class AtrapaTesseracta:
    def __init__(self):
        self.wywolania = []

    def zainstaluj(self, u, app, *, pixi, env_narzedzia, platforma, modele, log=print):
        self.wywolania.append((Path(pixi), platforma))
        kat = u.program / "narzedzia" / "tesseract" / "abc"
        prog = tesseract.program(kat)
        nowy = not prog.is_file()
        prog.parent.mkdir(parents=True, exist_ok=True)
        prog.write_bytes(b"")
        return {"wersja": "5.5.3", "katalog": str(kat), "program": str(prog), "bin": [],
                "env": {"TESSDATA_PREFIX": str(Path(modele) / "tessdata-fast")}}, nowy

    def sprawdz(self, tess, tessdata, czas=60):
        return True, "eng, osd, pol"


class AtrapaProgramow:
    def __init__(self):
        self.wywolania = []

    def przygotuj(self, u, *, venv_python, uv=None, tesseract=None, log=print):
        self.wywolania.append((Path(venv_python), tesseract))
        u.bin_floty.mkdir(parents=True, exist_ok=True)
        cel = u.bin_floty / bin_floty.nazwa_pliku("python3")
        if cel.is_file():
            return []
        cel.write_bytes(b"")
        return [cel.name]


def _pelna_aplikacja(tmp_path: Path, adres: str, www: Path) -> Path:
    """Kod Jarva z manifestem atrap: uv, Pythony, git (Windows), node i pixi, venv narzędzi i model."""
    app = tc._aplikacja(tmp_path, adres, www, nazwa="pelna")
    lock = json.loads((app / manifest.LOCK).read_text(encoding="utf-8"))
    archiwa = {"git": tc._tar_gz({"git/cmd/git.exe": b"git", "git/bin/bash.exe": b"bash"}),
               "node": tc._tar_gz({"node/npm.cmd": b"npm", "node/npm": b"npm", "node/node.exe": b"node"}),
               "pixi": tc._tar_gz({"pixi/pixi.exe": b"pixi", "pixi/pixi": b"pixi"})}
    for nazwa, dane in archiwa.items():
        (www / f"pelna-{nazwa}.tar.gz").write_bytes(dane)
        wpis = {"url": f"{adres}/pelna-{nazwa}.tar.gz", "sha256": _sha(dane), "rozmiar": len(dane), "format": "tar.gz",
                "usun_poziom": 1, "bin": ["cmd" if nazwa == "git" else "."],
                **({"env": {"HERMES_GIT_BASH_PATH": "{katalog}/bin/bash.exe"}} if nazwa == "git" else {})}
        pliki = {p: wpis for p in sciezki.PLATFORMY}
        if nazwa == "git":
            pliki.update({p: {"brak": "git z systemu"} for p in ("macos-arm64", "linux-x64", "linux-arm64")})
        lock["narzedzia"][nazwa] = {"wersja": "1.0", "kiedy": "instalacja", "pliki": pliki}
    lock["venvy"] = {"narzedzia": {"python": "python312", "lock": "x.lock", "sha256": "c" * 64, "kiedy": "instalacja"},
                     "cad": {"python": "python312", "lock": "y.lock", "sha256": "d" * 64, "kiedy": "przy-uzyciu"}}
    lock["modele"] = {"paradee": {"rewizja": "8" * 40, "katalog": "paradee", "kiedy": "instalacja", "pliki": []}}
    (app / manifest.LOCK).write_text(json.dumps(lock), encoding="utf-8")
    for rel in tesseract.PLIKI_PROJEKTU:
        p = app / tesseract.PROJEKT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# atrapa\n", encoding="utf-8")
    return app


def test_pelna_instalacja_z_flota_i_restart_uslug_przez_nadzorce(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    v, t, p = AtrapaVenvow(), AtrapaTesseracta(), AtrapaProgramow()
    s["moduly"].update({"venvy": v, "modele": AtrapaModeli(), "tesseract": t, "bin_floty": p})
    s["env"] = {"JARVO_API_PORT": "19161"}
    app = _pelna_aplikacja(tmp_path, s["adres"], s["www"])
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    kroki = re.findall(r"^\[[#-]+\] +\d+/\d+  (.+)$", log, re.M)
    pierwsze = ["Sprawdzenie komputera", "Katalogi", "uv", "Python 3.13", "Python 3.12"]
    assert kroki[:5] == pierwsze
    reszta = kroki[5:]
    assert reszta[:2] == (["git i Git Bash", "Node.js i npm"] if WINDOWS else ["Node.js i npm", "pixi"])
    assert "Venv narzedzia" in kroki and "Venv cad" not in kroki and "Model paradee" in kroki
    assert kroki.index("Model paradee") < kroki.index("Tesseract") < kroki.index("Spis narzędzi")
    assert kroki.index("Klucz API bramy") < kroki.index("Przełączenie wersji") < kroki.index("Programy floty") \
        < kroki.index("Flota") < kroki.index("Środowisko procesów")
    narz = srodowisko.narzedzia(u)
    assert {"venv-narzedzia", "model-paradee", "tesseract", "node", "pixi"} <= set(narz)
    h = s["hermes"].wywolania[0]
    if WINDOWS:                                      # git z manifestu, nie z PATH
        assert h[2] == Path(narz["git"]["katalog"]) / "cmd" / "git.exe"
    assert v.wywolania[0][2] == u.program / "narzedzia" / "python312" / "3.12.15" / (
        "python.exe" if WINDOWS else "bin/python3")
    assert p.wywolania[0][0] == Path(narz["venv-narzedzia"]["python"])
    assert p.wywolania[0][1] == Path(narz["tesseract"]["program"])
    assert instalator.czytaj_env(u.dane / ".env")["API_SERVER_PORT"] == "19161"
    zapis = json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))
    assert zapis["TESSDATA_PREFIX"].endswith("tessdata-fast") and zapis["JARVO_TOOLS_PYTHON"]
    assert json.loads((u.stan / "ustawienia.json").read_text(encoding="utf-8"))["JARVO_API_PORT"] == "19161"
    # serwis działa, zmieniła się tylko flota: restart bramy i panelu przez nadzorcę (bez zatrzymania całości)
    s["flota"].zmiany = ["profil jarvo-web"]
    zatrzymania = s["nadzorca"].zatrzymania
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    assert s["nadzorca"].restarty == ["brama", "panel"] and s["nadzorca"].zatrzymania == zatrzymania
    assert "    po restarcie gotowe: brama, panel" in s["log"] and s["flota"].potwierdzenia[-1] == "0123456789abcdef"
    # trzeci: nic do zrobienia
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    assert "Gotowe. Zmiany w tym przebiegu: brak." in s["log"] and s["nadzorca"].restarty == ["brama", "panel"]


def test_instalacja_bez_venvu_narzedzi_pomija_programy_floty(tmp_path, stanowisko):
    s = stanowisko
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    assert tc._instaluj(s, app) == 0
    assert "    ta wersja nie ma venvu narzędzi: programy floty pominięte" in s["log"]


def test_blad_floty_konczy_instalacje_czytelnie(tmp_path, stanowisko):
    s = stanowisko
    s["flota"].blad = "build floty nie przeszedł (kod 3)"
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    assert tc._instaluj(s, app) == 1
    assert any("BŁĄD w kroku „Flota”: build floty nie przeszedł (kod 3)" in x for x in s["log"])


def test_ten_sam_port_panelu_i_api_odmowa(tmp_path, stanowisko):
    s = stanowisko
    s["env"] = {"JARVO_API_PORT": "19199"}                                  # _ot: JARVO_PANEL_PORT=19199
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    assert tc._instaluj(s, app) == 1
    assert any("panel i API bramy nie mogą mieć tego samego portu" in x for x in s["log"])

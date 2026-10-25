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

Miejsce (c3 pkt 11, Z31): potrzeba liczona z manifestu (rozmiary plików, pobranie_mb i venv_mb, pixi.lock, modele;
Hermes i flota ze stałych) tylko dla brakujących części, bilans na każdym dysku, odmowa przed zapisaniem czegokolwiek
z innymi dyskami i gotowym poleceniem (PowerShell i bash); system plików: polecane tylko dyski z ochroną dostępu
(punkty montowania Linuksa i macOS bez FAT, exFAT, NTFS i noowners, dyski stałe Windows z NTFS), a korzeń na
woluminie bez niej = odmowa w kroku 1 (działająca instalacja: uwaga); sprzątanie po udanej instalacji (archiwa tego
przebiegu i stare, świeże pliki innych procesów zostają, cache uv przez `uv cache clean`, cache pixi, stare wersje
narzędzi, node_modules frontu zaraz po budowie, bez wchodzenia w junction workspace'u npm) pod zamkami instalatorów
trzymanymi przez drugi proces, i drugi przebieg bez sieci bez zmian; zajęte miejsce bez liczenia dowiązań dwa razy.
"""
from __future__ import annotations

import contextlib
import hashlib
import inspect
import json
import os
import re
import stat
import subprocess
import sys
import threading
import time
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import atrapy
from conftest import REPO, WINDOWS

sys.path.insert(0, str(REPO))
from jarvo import bin_floty, cli, flota, instalator, manifest, modele, programy_floty, sciezki  # noqa: E402
from jarvo import hermes, przy_uzyciu, srodowisko, tesseract, venvy  # noqa: E402
import install_fleet  # noqa: E402  (scripts/ w sys.path z conftest)

import test_natywne_cli as tc  # noqa: E402  (atrapy modułów i stanowisko instalatora)
import test_natywne_hermes as th  # noqa: E402  (atrapy git, uv i npm dla frontu Hermesa)

LOCK = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))
stanowisko = tc.stanowisko                                       # fixture z testów instalatora
serwer = tc.serwer
atrapa = th.atrapa                                               # fixture z testów Hermesa
MB, GB = instalator.MB, instalator.GB


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
    (git / "cmd" / ("git.exe" if WINDOWS else "git")).chmod(0o755)    # POSIX: _bin bierze tylko plik wykonywalny
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


# ---------------------------------------------------------------- miejsce: potrzeba z manifestu, dyski, sprzątanie

def _app_miejsca(tmp_path: Path) -> Path:
    """Kod Jarva z manifestem do liczenia miejsca: trzy narzędzia instalacji (zip, tar.xz i pixi), Camoufox przy
    pierwszym użyciu, Lightpanda `brak`, venv, model, prawdziwy projekt pixi Tesseracta (rozmiary paczek z pixi.lock),
    pin Hermesa i fleet.yaml."""
    app = tmp_path / "app-miejsce"

    def plik(rozmiar: int, format: str, **dodatki) -> dict:
        return {"url": "https://example.invalid/plik", "sha256": "1" * 64, "rozmiar": rozmiar, "format": format,
                **dodatki}
    narz = {
        "uv": {"wersja": "0.12.13", "pliki": {p: plik(10 * MB, "zip") for p in sciezki.PLATFORMY}},
        "node": {"wersja": "26.12.1", "pliki": {p: plik(20 * MB, "tar.xz") for p in sciezki.PLATFORMY}},
        "pixi": {"wersja": "0.83.0", "pliki": {p: plik(5 * MB, "zip") for p in sciezki.PLATFORMY}},
        "camoufox": {"wersja": "152", "kiedy": "przy-uzyciu",
                     "pliki": {p: plik(100 * MB, "zip") for p in sciezki.PLATFORMY}},
        "lightpanda": {"wersja": "1.0.0", "pliki": {p: {"brak": "nie ma wydania"} for p in sciezki.PLATFORMY}},
    }
    venvy_ = {"narzedzia": {"python": "python312", "lock": "x.lock", "sha256": "c" * 64, "kiedy": "instalacja",
                            "pobranie_mb": {"windows-x64": 100, "linux-x64": 200}, "venv_mb": 400},
              "cad": {"python": "python312", "lock": "y.lock", "sha256": "d" * 64, "kiedy": "przy-uzyciu",
                      "pobranie_mb": {"linux-x64": 50}}}
    modele_ = {"lektor": {"rewizja": "8" * 40, "katalog": "lektor", "kiedy": "instalacja",
                          "pliki": [{"cel": "a.bin", "url": "https://x/a", "sha256": "2" * 64, "rozmiar": MB},
                                    {"cel": "b.bin", "url": "https://x/b", "sha256": "3" * 64, "rozmiar": 2 * MB}]},
               "parakeet": {"rewizja": "9" * 40, "katalog": "parakeet", "kiedy": "przy-uzyciu",
                            "pliki": [{"cel": "c.onnx", "url": "https://x/c", "sha256": "4" * 64, "rozmiar": 30 * MB}]}}
    (app / "vendor").mkdir(parents=True)
    (app / manifest.LOCK).write_text(json.dumps({"version": 1, "hermes": dict(tc.HERMES_PIN), "narzedzia": narz,
                                                 "venvy": venvy_, "modele": modele_}), encoding="utf-8")
    for rel in tesseract.PLIKI_PROJEKTU:
        cel = app / tesseract.PROJEKT / rel
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_bytes((REPO / tesseract.PROJEKT / rel).read_bytes())
    (app / "fleet.yaml").write_text("agents: []\n", encoding="utf-8")
    return app


def _mb(potrzeby, opis: str) -> tuple[float, float]:
    p = next(x for x in potrzeby if x.opis.startswith(opis))
    return round(p.szczyt / MB, 3), round(p.zostaje / MB, 3)


def test_potrzebne_miejsce_z_manifestu_tylko_brakujace_czesci(tmp_path):
    app = _app_miejsca(tmp_path)
    u = uklad(tmp_path / "j")
    p = instalator.potrzebne_miejsce(u, app, "linux-x64")
    assert _mb(p, "archiwa narzędzi (3)") == (35, 0)                         # pobrane pliki: tylko w trakcie
    assert _mb(p, "narzędzia (3)") == (10 * 3.0 + 20 * 4.5 + 5 * 3.0,) * 2   # zip × 3, tar.xz × 4,5
    assert _mb(p, "venvy (1)") == (800, 800)                                 # venv_mb 400 × pobranie 200/100 (Windows)
    assert _mb(p, "cache uv venvów") == (pytest.approx(800 * venvy.WSP_CACHE), 0)
    assert _mb(p, "modele (1)") == (3, 3)                                    # parakeet: przy pierwszym użyciu
    cache, srod, zostaje = tesseract.miejsce(app, "linux-x64")
    assert _mb(p, "cache pixi") == (round(cache / MB, 3), 0) and _mb(p, "Tesseract") == (round(srod / MB, 3),
                                                                                         round(zostaje / MB, 3))
    # Hermes i flota ze stałych w kodzie: prawdziwy manifest nie ma pól miejsca (gdy dojdą, potrzebne_miejsce ma je
    # czytać, a ten warunek trzeba zmienić razem z nim)
    h, f = instalator.HERMES_MB, instalator.FLOTA_MB
    assert not [k for k in LOCK["hermes"] if "miejsce" in k] and not [
        k for w in LOCK["narzedzia"].values() for pl in (w.get("pliki") or {}).values() for k in pl if "rozpak" in k]
    assert _mb(p, "Hermes") == (h["checkout"],) * 2 and _mb(p, "cache uv Hermesa") == (h["cache_uv"], 0)
    assert _mb(p, "node_modules frontu") == (h["node_modules"], 0) and _mb(p, "front panelu") == (h["front"],) * 2
    assert _mb(p, "źródła skilli") == (f["zrodla"],) * 2 and _mb(p, "build floty") == (f["build"],) * 2
    assert _mb(p, "profile floty") == (f["profile"],) * 2
    assert not [x for x in p if "camoufox" in x.opis.lower() or "cad" in x.opis]
    # części, które już są: znacznik sumy uv, venv, model, Tesseract, Hermes z frontem, źródła skilli i profile
    (u.program / "narzedzia" / "uv" / "0.12.13").mkdir(parents=True)
    (u.program / "narzedzia" / "uv" / "0.12.13" / ".jarvo-suma").write_text("1" * 64 + "\n", encoding="utf-8")
    wpis = manifest.venvy(app)["narzedzia"]
    kat = venvy.katalog(u, "narzedzia", wpis)
    venvy.python_venvu(kat).parent.mkdir(parents=True)
    venvy.python_venvu(kat).write_bytes(b"")
    (kat / venvy.ZNACZNIK).write_text(json.dumps({"lock_sha256": wpis["sha256"]}), encoding="utf-8")
    model = manifest.modele(app)["lektor"]
    kat = modele.katalog(u.jarvo_dane / "models", model)
    kat.mkdir(parents=True)
    for plik in model["pliki"]:
        (kat / plik["cel"]).write_bytes(b"\0" * plik["rozmiar"])
    (kat / modele.ZNACZNIK).write_text(json.dumps(modele._znacznik(model)), encoding="utf-8")
    kat = tesseract.katalog(u, app)
    tesseract.program(kat).parent.mkdir(parents=True)
    tesseract.program(kat).write_bytes(b"")
    (kat / tesseract.ZNACZNIK).write_text(json.dumps({"lock_sha256": _sha((app / tesseract.PROJEKT / "pixi.lock")
                                                                         .read_bytes())}), encoding="utf-8")
    checkout = hermes.katalog_checkoutu(u, tc.PIN)
    checkout.mkdir(parents=True)
    (checkout / hermes.ZNACZNIK).write_text(json.dumps({"commit": tc.PIN}), encoding="utf-8")
    (u.cache / "build" / "skille@0123456789ab").mkdir(parents=True)
    (u.dane / "profiles").mkdir()
    p = instalator.potrzebne_miejsce(u, app, "linux-x64")
    assert [x.opis for x in p] == ["archiwa narzędzi (2)", "narzędzia (2)", "node_modules frontu",
                                   "front panelu i cache npm"]             # front tego pinu jeszcze niezbudowany
    (checkout / hermes.ZNACZNIK_WEB).write_text(json.dumps({"commit": tc.PIN}), encoding="utf-8")
    assert [x.opis for x in instalator.potrzebne_miejsce(u, app, "linux-x64")] == ["archiwa narzędzi (2)",
                                                                                   "narzędzia (2)"]
    assert len(instalator.potrzebne_miejsce(u, app, "linux-x64", wszystko=True)) == 14   # jak na pustym dysku
    assert instalator.miejsce_przy_uzyciu(app, "linux-x64") == int(100 * MB * 3.0) + int(50 * venvy.WSP_VENVU * MB) \
        + 30 * MB


@pytest.mark.parametrize("platforma", sciezki.PLATFORMY)
def test_potrzeba_prawdziwego_manifestu_na_kazdej_platformie(tmp_path, platforma):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "j")})
    potrzeby = instalator.potrzebne_miejsce(u, REPO, platforma)
    szczyt, zostaje = sum(p.szczyt for p in potrzeby), sum(p.zostaje for p in potrzeby)
    assert 6 * GB < szczyt < 16 * GB and 3 * GB < zostaje < szczyt - 2 * GB, (instalator.gb(szczyt),
                                                                              instalator.gb(zostaje))
    assert {p.opis.split(" (")[0] for p in potrzeby} == {
        "archiwa narzędzi", "narzędzia", "venvy", "cache uv venvów", "modele", "cache pixi", "Tesseract", "Hermes",
        "cache uv Hermesa", "node_modules frontu", "front panelu i cache npm", "narzędzia npm floty",
        "cache npm narzędzi floty", "źródła skilli floty", "build floty", "profile floty"}
    assert not u.root.exists()                                              # liczenie niczego nie zakłada


def test_bilans_dyskow_sumuje_na_jednym_dysku_i_dzieli_na_dwa(tmp_path):
    u = sciezki.Uklad(root=tmp_path / "j", program=tmp_path / "j" / "program", dane=tmp_path / "j" / "dane",
                      stan=tmp_path / "j" / "stan", logi=tmp_path / "xdg" / "logi", cache=tmp_path / "xdg" / "cache",
                      build=tmp_path / "j" / "build")
    potrzeby = [instalator.Potrzeba("program", u.program, 2 * GB, GB),
                instalator.Potrzeba("cache", u.cache, GB, 0)]
    jeden = instalator.Otoczenie(dysk=lambda p: "C", wolne_miejsce=lambda p: 50 * GB)
    b = instalator.bilans_dyskow(u, potrzeby, jeden)
    assert len(b) == 1 and b[0]["korzen"] and b[0]["potrzeba"] == int(3 * GB * 1.1) + instalator.ZAPAS_MB * MB
    assert b[0]["zostaje"] == GB and b[0]["wolne"] == 50 * GB
    dwa = instalator.Otoczenie(dysk=lambda p: "X" if "xdg" in str(p) else "C",
                               wolne_miejsce=lambda p: GB if "xdg" in str(p) else 50 * GB)
    korzen, cache = instalator.bilans_dyskow(u, potrzeby, dwa)
    assert korzen["korzen"] and korzen["potrzeba"] == int(2 * GB * 1.1) + instalator.ZAPAS_MB * MB
    assert not cache["korzen"] and cache["potrzeba"] == int(GB * 1.1) and cache["wolne"] == GB
    # pełny tylko dysk cache (XDG): JARVO_ROOT na dysku korzenia przeniesie tam cache, więc ten dysk się nadaje
    dwa.dyski = lambda: [tmp_path / "j"]
    assert [k["punkt"] for k in instalator.inne_dyski(u, 3 * GB, dwa, pelne={cache["dysk"]})] == [str(tmp_path / "j")]
    assert instalator.inne_dyski(u, 3 * GB, dwa) == []                    # domyślnie bez dysku korzenia i cache

    def bez_dysku(p):
        raise OSError("brak")
    assert instalator.bilans_dyskow(u, [], instalator.Otoczenie(wolne_miejsce=bez_dysku))[0]["wolne"] is None


def _dyski_atrapa(tmp_path: Path, wolne: dict[str, int]) -> dict:
    """Atrapa dysków Otoczenia: każdy klucz `wolne` poza „korzen” to katalog tmp_path/<nazwa> na osobnym dysku
    z tyle wolnego, a reszta (korzeń instalacji) to dysk „korzen”."""
    def ktory(p) -> str:
        p = Path(os.path.abspath(p))
        return next((n for n in wolne if n != "korzen" and (tmp_path / n) in (p, *p.parents)), "korzen")
    return {"dysk": ktory, "wolne_miejsce": lambda p: wolne[ktory(p)],
            "dyski": lambda: [tmp_path / n for n in wolne if n != "korzen"]}


def test_brak_miejsca_odmowa_przed_zapisem_z_innymi_dyskami_i_poleceniem(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])          # z pinem Hermesa: ok. 2 GB z frontem
    log: list[str] = []
    ot = s["otoczenie"](**_dyski_atrapa(tmp_path, {"korzen": GB, "duzy": 500 * GB, "maly": 2 * GB}))
    assert instalator.instaluj(u, app, log=log.append, otoczenie=ot) == 1
    tekst = "\n".join(log)
    assert re.search(r"BŁĄD w kroku „Sprawdzenie komputera”: na dysku .+ jest 1,0 GB wolnego miejsca, a instalacja "
                     r"Jarva potrzebuje na nim ok\. [\d,]+ GB \(w trakcie", tekst), tekst
    assert "Niczego nie zainstalowałem." in tekst and "Instalację można uruchomić ponownie" not in tekst
    assert f"Wystarczy miejsca na: {tmp_path / 'duzy'} (500,0 GB wolnego)." in tekst
    assert str(tmp_path / "maly") not in tekst                                   # za mały na całą instalację
    assert instalator.polecenie_instalacji(str(tmp_path / "duzy" / ("Jarvo" if WINDOWS else "jarvo"))) in tekst
    assert not u.root.exists() and s["hermes"].wywolania == [] and not s["w_tle"]
    # bez dysku z miejscem: ile zwolnić i przykład polecenia; pliki bootstrapu w korzeniu zostają nietknięte
    (u.program / "app" / "abc").mkdir(parents=True)
    (u.program / "app" / "abc" / "start.py").write_bytes(b"x" * 1000)
    przed = tc._migawka(u.root)
    log.clear()
    ot = s["otoczenie"](**_dyski_atrapa(tmp_path, {"korzen": GB, "maly": 2 * GB}))
    assert instalator.instaluj(u, app, log=log.append, otoczenie=ot) == 1
    tekst = "\n".join(log)
    assert "Nie znalazłem innego dysku lokalnego z ok." in tekst and "co najmniej" in tekst and "JARVO_ROOT" in tekst
    assert f"Pliki programu startowego (0,00 GB: uv, Python i kod Jarva) są w {u.root}" in tekst
    assert tc._migawka(u.root) == przed and not u.logi.exists()


def test_brak_miejsca_przy_aktualizacji_zostawia_dzialajaca_wersje(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    assert tc._instaluj(s, tc._aplikacja(tmp_path, s["adres"], s["www"])) == 0
    przed = srodowisko.biezace(u)
    nowa = tc._aplikacja(tmp_path, s["adres"], s["www"], nazwa="app2", sha="a" * 40, commit="b" * 40)
    log: list[str] = []
    ot = s["otoczenie"](**_dyski_atrapa(tmp_path, {"korzen": GB, "duzy": 500 * GB}))
    assert instalator.instaluj(u, nowa, log=log.append, otoczenie=ot) == 1
    tekst = "\n".join(log)
    assert "ta aktualizacja Jarva potrzebuje na nim ok." in tekst and "Działająca wersja zostaje bez zmian." in tekst
    assert "Wystarczy miejsca" not in tekst and "Niczego nie zainstalowałem" not in tekst
    assert srodowisko.biezace(u) == przed and s["nadzorca"].zatrzymania == 0 and s["nadzorca"].dziala


def test_polecenie_instalacji_powershell_i_bash():
    baza = "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/jarvo/bootstrap"
    assert cli.BOOTSTRAP == baza
    assert instalator.polecenie_instalacji("D:\\Jarvo", windows=True) == \
        f"$env:JARVO_ROOT = 'D:\\Jarvo'; irm {baza}/install.ps1 | iex"
    assert instalator.polecenie_instalacji("D:\\O'Brien\\Jarvo", windows=True).startswith(
        "$env:JARVO_ROOT = 'D:\\O''Brien\\Jarvo';")                         # apostrof podwojony w PowerShellu
    assert instalator.polecenie_instalacji("/mnt/dane/jarvo", windows=False) == \
        f"curl -fsSL {baza}/install.sh | JARVO_ROOT=/mnt/dane/jarvo bash"
    assert "JARVO_ROOT='/mnt/moje dane/jarvo' bash" in instalator.polecenie_instalacji("/mnt/moje dane/jarvo",
                                                                                         windows=False)


def test_punkty_montowania_linuksa_i_macos_tylko_z_ochrona_dostepu():
    proc = ("/dev/nvme0n1p2 / ext4 rw,relatime,errors=remount-ro 0 0\n"
            "/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077 0 0\n"           # FAT: bez uprawnień właściciela
            "/dev/sda1 /media/ola/Dysk\\040Dane ext4 rw,nosuid 0 0\n"
            "/dev/sdc1 /media/ola/PENDRIVE vfat rw,nosuid,nodev,uid=1000 0 0\n"
            "/dev/sdd1 /media/ola/USB exfat rw,nosuid,nodev 0 0\n"
            "/dev/sde2 /mnt/windows ntfs3 rw,relatime,uid=1000 0 0\n"
            "/dev/sdf1 /media/ola/WD fuseblk rw,nosuid,nodev,user_id=0,allow_other 0 0\n"   # ntfs-3g i exfat-fuse
            "/dev/sdb1 /mnt/archiwum xfs ro,relatime 0 0\n"
            "/dev/sdg1 /mnt/dane btrfs rw,relatime,subvol=/ 0 0\n"
            "/dev/loop3 /snap/core/17 squashfs ro,nodev 0 0\n"
            "tmpfs /tmp tmpfs rw 0 0\n"
            "server:/eksport /mnt/nfs nfs4 rw 0 0\n"
            "dane/jarvo /tank zfs rw,xattr 0 0\n")
    assert instalator.punkty_linux(proc) == ["/", "/media/ola/Dysk Dane", "/mnt/dane", "/tank"]
    w = {x.punkt: x for x in instalator.woluminy_linux(proc)}
    assert w["/media/ola/Dysk Dane"].typ == "ext4" and "nosuid" in w["/media/ola/Dysk Dane"].opcje
    mount = ("/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
             "/dev/disk3s5 on /System/Volumes/Data (apfs, local, journaled, nobrowse, protect, root data)\n"
             "devfs on /dev (devfs, local, nobrowse)\n"
             "map auto_home on /System/Volumes/Data/home (autofs, automounted, nobrowse)\n"
             "/dev/disk5s1 on /Volumes/Dane (apfs, local, nodev, nosuid, journaled, noowners)\n"   # dysk zewnętrzny
             "/dev/disk6s1 on /Volumes/Moje Zdjęcia (exfat, local, nodev, nosuid, noowners)\n"
             "/dev/disk7s1 on /Volumes/Projekty (apfs, local, nodev, nosuid, journaled)\n"   # właściciele włączeni
             "/dev/disk8s2 on /Volumes/Stary (hfs, local, journaled)\n"
             "/dev/disk9s1 on /Volumes/KARTA (msdos, local, nodev, nosuid)\n"
             "//ola@nas/wspolne on /Volumes/wspolne (smbfs, nodev, nosuid, mounted by ola)\n")
    assert instalator.punkty_macos(mount) == ["/Volumes/Projekty", "/Volumes/Stary"]
    w = {x.punkt: x for x in instalator.woluminy_macos(mount)}
    assert w["/Volumes/Dane"].typ == "apfs" and "noowners" in w["/Volumes/Dane"].opcje
    assert "/System/Volumes/Data/home" not in w                             # urządzenie ze spacją (autofs)


def test_bez_ochrony_i_polecany_na_trzech_systemach():
    W = instalator.Wolumin
    # Windows: NTFS i ReFS na dysku stałym; FAT32 i exFAT bez ACL (także dysk USB, który zgłasza się jako stały)
    assert instalator.bez_ochrony(W("C:\\", "C:\\", "NTFS", frozenset({"staly", "acl"})), "windows") is None
    for typ in ("NTFS", "ReFS"):
        assert instalator.polecany(W("D:\\", "D:\\", typ, frozenset({"staly", "acl"})), "windows")
    for typ in ("exFAT", "FAT32"):
        usb = W("F:\\", "F:\\", typ, frozenset({"staly"}))
        assert "nie przechowuje uprawnień (ACL)" in instalator.bez_ochrony(usb, "windows")
        assert not instalator.polecany(usb, "windows")
    for opcje in ({"sieciowy", "acl"}, {"wymienny", "acl"}):               # NTFS na serwerze albo na pendrivie
        w = W("Z:\\", "Z:\\", "NTFS", frozenset(opcje))
        assert instalator.bez_ochrony(w, "windows") is None and not instalator.polecany(w, "windows")
    # macOS: wolumin danych z katalogiem domowym (nobrowse) tylko jako katalog domowy; noowners, exfat i msdos nigdy
    dane = W("/dev/disk3s5", "/System/Volumes/Data", "apfs", frozenset({"local", "journaled", "nobrowse"}))
    assert instalator.bez_ochrony(dane, "macos") is None and not instalator.polecany(dane, "macos")
    assert instalator.polecany(dane, "macos", systemowy=True)
    zewn = W("/dev/disk5s1", "/Volumes/Dane", "apfs", frozenset({"local", "nodev", "journaled", "noowners"}))
    assert "noowners" in instalator.bez_ochrony(zewn, "macos") and not instalator.polecany(zewn, "macos")
    for typ in ("exfat", "msdos"):
        assert "nie przechowuje uprawnień właściciela" in instalator.bez_ochrony(W("/dev/disk6s1", "/Volumes/X", typ),
                                                                                "macos")
    smb = W("//ola@nas/x", "/Volumes/x", "smbfs", frozenset({"nodev"}))
    assert instalator.bez_ochrony(smb, "macos") is None and not instalator.polecany(smb, "macos")
    # Linux: ext4 i inne z LOKALNE_FS na /dev/…; FAT, exFAT i NTFS bez uprawnień; sieciowe i w pamięci nie do polecenia
    assert instalator.polecany(W("/dev/sda1", "/mnt/d", "ext4", frozenset({"rw"})), "linux")
    for typ in ("vfat", "exfat", "ntfs3", "ntfs", "fuseblk", "msdos"):
        w = W("/dev/sdb1", "/media/x", typ, frozenset({"rw"}))
        assert "nie przechowuje uprawnień właściciela" in instalator.bez_ochrony(w, "linux") and \
            not instalator.polecany(w, "linux")
    for w in (W("srv:/e", "/mnt/nfs", "nfs4", frozenset({"rw"})), W("tmpfs", "/tmp", "tmpfs", frozenset({"rw"})),
              W("/dev/sdc1", "/mnt/ro", "xfs", frozenset({"ro"}))):
        assert instalator.bez_ochrony(w, "linux") is None and not instalator.polecany(w, "linux")


@pytest.mark.windows_only
def test_dyski_lokalne_windows_to_dyski_stale_z_ntfs(tmp_path):
    dyski = instalator.dyski_lokalne()
    systemowy = os.environ.get("SystemDrive", "C:").upper()
    assert all(re.fullmatch(r"[A-Z]:\\", str(d)) for d in dyski) and Path(systemowy + "\\") in dyski
    for d in dyski:
        w = instalator.wolumin_windows(d)
        assert w.typ.lower() in instalator.WINDOWS_FS and {"staly", "acl"} <= w.opcje, w
    w = instalator.wolumin(tmp_path / "nie-ma" / "jarvo")              # korzeń, którego jeszcze nie ma
    assert w is not None and instalator.bez_ochrony(w) is None and instalator.polecany(w)
    brak = next((f"{c}:\\" for c in "QRSTUVWXYZ" if not os.path.exists(f"{c}:\\")), None)
    assert brak is None or instalator.wolumin(Path(brak) / "jarvo") is None   # dysku nie ma: nie wiadomo
    assert instalator.punkt_dysku(Path(systemowy + "\\") / "nie-ma" / "jarvo") == systemowy + "\\"


@pytest.mark.posix_only
def test_dyski_lokalne_posix_z_katalogiem_domowym(tmp_path):
    woluminy = instalator._woluminy()
    dyski = instalator.dyski_lokalne()
    dom = instalator.wolumin_posix(Path.home(), woluminy)
    # katalog domowy, gdy jego wolumin jest lokalny i z ochroną dostępu (w kontenerze z overlay: nie wiadomo, więc nie)
    assert (Path.home() in dyski) == (dom is not None and instalator.polecany(dom, systemowy=True))
    if sys.platform == "darwin":                                          # APFS bez noowners (/System/Volumes/Data)
        mount = instalator.systemowy("mount")
        opis = (f"dom={dom!r} st_dev={os.stat(Path.home()).st_dev} mount={mount!r}\n"
                + (instalator._uruchom([mount]).stdout if mount else ""))
        assert dyski and dyski[0] == Path.home(), opis
    punkty = {w.punkt: w for w in woluminy}                               # ostatnie montowanie w punkcie
    for d in dyski:
        if d != Path.home():
            assert instalator.polecany(punkty[str(d)]) and not any(z.isspace() for z in str(d))
    assert len(set(dyski)) == len(dyski)
    w = instalator.wolumin(tmp_path)
    assert w is None or instalator.bez_ochrony(w) is None                  # testy nie biegną na FAT ani noowners
    assert instalator.punkt_dysku("/nie-ma/jarvo") == "/"


@pytest.mark.linux_only
def test_woluminy_z_prawdziwego_proc_self_mounts():
    woluminy = instalator._woluminy()
    korzen = next(w for w in woluminy if w.punkt == "/")                      # każdy Linux ma wpis dla „/”
    w = instalator.wolumin("/")
    if korzen.urzadzenie.startswith("/dev/"):                                  # dysk; w kontenerze overlay: None
        assert w is not None and os.stat(w.punkt).st_dev == os.stat("/").st_dev
    else:
        assert w is None or os.stat(w.punkt).st_dev == os.stat("/").st_dev
    assert all(isinstance(x.opcje, frozenset) and x.typ for x in woluminy)


def test_dysk_bez_ochrony_odmowa_przed_zapisem_a_dzialajaca_instalacja_z_uwaga(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    exfat = (instalator.Wolumin("E:\\", "E:\\", "exFAT", frozenset({"staly"})) if WINDOWS else
             instalator.Wolumin("/dev/sdb1", "/media/ola/USB", "exfat", frozenset({"rw"})))
    log: list[str] = []
    ot = s["otoczenie"](wolumin=lambda p: exfat, **_dyski_atrapa(tmp_path, {"korzen": 500 * GB, "duzy": 400 * GB}))
    assert instalator.instaluj(u, app, log=log.append, otoczenie=ot) == 1
    tekst = "\n".join(log)
    assert re.search(r"BŁĄD w kroku „Sprawdzenie komputera”: korzeń .+ leży na dysku .+ \(exFAT\), a tam system "
                     r"plików exFAT nie przechowuje uprawnień", tekst, re.I), tekst
    assert "Niczego nie zainstalowałem." in tekst and "Instalację można uruchomić ponownie" not in tekst
    assert f"Wystarczy miejsca na: {tmp_path / 'duzy'} (400,0 GB wolnego)." in tekst
    assert instalator.polecenie_instalacji(str(tmp_path / "duzy" / ("Jarvo" if WINDOWS else "jarvo"))) in tekst
    assert not u.root.exists() and s["hermes"].wywolania == [] and not s["w_tle"]
    # działająca instalacja na takim woluminie (sprzed tej kontroli): aktualizacja idzie dalej, z uwagą
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    log.clear()
    assert instalator.instaluj(u, app, log=log.append, otoczenie=ot) == 0, "\n".join(log)
    assert any(x.startswith("Uwaga: korzeń") and "ochrona dostępu do plików Jarva nie działa" in x for x in log), log
    # wolumin nieznany (np. katalog domowy na NFS): instalator nie odmawia
    assert instalator.instaluj(u, app, log=log.append, otoczenie=s["otoczenie"](wolumin=lambda p: None)) == 0


def test_komunikat_dysku_bez_ochrony_macos_noowners_i_bez_innego_dysku(tmp_path):
    u = uklad(tmp_path / "j")
    w = instalator.Wolumin("/dev/disk5s1", "/Volumes/Dane", "apfs", frozenset({"local", "journaled", "noowners"}))
    ot = instalator.Otoczenie(**_dyski_atrapa(tmp_path, {"korzen": 500 * GB, "maly": GB}))
    tekst = instalator.komunikat_dysku_bez_ochrony(u, _app_miejsca(tmp_path), "macos-arm64", w,
                                                   instalator.bez_ochrony(w, "macos"), ot)
    assert "opcja noowners" in tekst and "sudo diskutil enableOwnership /Volumes/Dane" in tekst
    assert "Nie znalazłem innego dysku lokalnego z ok." in tekst and "na którym Jarvo zachowa ochronę dostępu" in tekst
    assert "JARVO_ROOT" in tekst and "co najmniej" not in tekst                # zwalnianie miejsca tu nie pomoże


def test_gb_po_polsku_i_opis_zajetego():
    assert (instalator.gb(11.44 * GB), instalator.gb(0.72 * GB), instalator.gb(0)) == ("11,4", "0,72", "0,00")
    assert instalator.opis_zajetego({"program": int(4.1 * GB), "dane": int(0.3 * GB), "cache": 0,
                                     "build": 4 * MB, "inne": 0}) == "4,4 GB (program 4,1, dane 0,30)"


def _dowiazanie_katalogu(cel: Path, link: Path) -> None:
    """Junction na Windows (tak npm linkuje workspace'y, a install_fleet.py wtyczki), symlink na POSIX."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        import _winapi
        _winapi.CreateJunction(str(cel), str(link))
    else:
        os.symlink(cel, link, target_is_directory=True)


def test_zajete_miejsce_czesci_bez_wchodzenia_w_dowiazania(tmp_path):
    u = uklad(tmp_path / "j")
    pliki = {u.program / "a.bin": 1000, u.cache / "b.bin": 2000, u.dane / "c.bin": 300, u.stan / "d.json": 50,
             u.build / "plugins" / "hq" / "e.js": 400}
    for p, n in pliki.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * n)
    _dowiazanie_katalogu(u.build / "plugins" / "hq", u.dane / "plugins" / "hq")       # jak wtyczki floty (H27)
    os.link(u.program / "a.bin", u.program / "a-twarde.bin")
    z = instalator.zajete_miejsce(u)
    # twarde dowiązanie raz na POSIX; os.scandir na Windows nie podaje numeru pliku, więc tam dwa razy (górna granica)
    assert z == {"program": 2000 if WINDOWS else 1000, "dane": 300, "cache": 2000, "build": 400, "inne": 50}
    assert instalator.rozmiar_katalogu(tmp_path / "nie-ma") == 0
    # tyle zwolni usunięcie: plik z drugim twardym dowiązaniem (cache pixi a środowisko Tesseracta) nic nie zwalnia
    assert instalator.rozmiar_katalogu(u.program, wlasne=True) == 0
    assert instalator.rozmiar_katalogu(u.cache, wlasne=True) == 2000


@contextlib.contextmanager
def _zamki_drugiego_procesu(*sciezki: Path):
    """Zamki instalatorów (przenosne.Zamek) trzymane przez drugi proces, jak przez drugi instalator, aż do końca
    bloku."""
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); from jarvo.przenosne import Zamek\n"
           "zamki = [Zamek(p) for p in sys.argv[2:]]   # odwołania zostają: zamknięty plik zwolniłby zamek\n"
           "for z in zamki:\n    z.__enter__()\nprint('trzymam', flush=True)\nsys.stdin.read()\n")
    proc = subprocess.Popen([sys.executable, "-I", "-c", kod, str(REPO), *map(str, sciezki)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "trzymam"
        yield
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


def test_sprzatnij_pobrane_zostawia_swieze_pliki_innych_procesow(tmp_path):
    u = uklad(tmp_path / "j")
    pobrane = u.cache / "pobrane"
    pobrane.mkdir()
    teraz = time.time()
    stare = teraz - instalator.SWIEZE_S - 60
    pliki = {"a" * 16 + "-uv.zip": teraz,                    # archiwum tego przebiegu: od razu, choć świeże
             "a" * 16 + "-uv.zip.czesc": teraz,              # świeże .czesc zostaje zawsze (pobieranie w toku)
             "b" * 16 + "-chrome-win64.zip": teraz,          # świeże archiwum innego procesu: zaraz je rozpakuje
             "b" * 16 + "-chrome-win64.zip.czesc": teraz,
             "c" * 16 + "-stara-wersja.zip": stare,          # archiwum starej wersji
             "d" * 16 + "-przerwane.tar.gz.czesc": stare,    # resztka przerwanego pobrania
             "jarvo-" + "e" * 40 + ".tar.gz": stare}         # kod Jarva z przerwanej aktualizacji
    for nazwa, t in pliki.items():
        (pobrane / nazwa).write_bytes(b"x")
        os.utime(pobrane / nazwa, (t, t))
    (pobrane / "katalog").mkdir()
    os.utime(pobrane / "katalog", (stare, stare))
    logi: list[str] = []
    # drugi proces właśnie instaluje narzędzie przy pierwszym użyciu: nic nie znika, bez czekania na zamek
    with _zamki_drugiego_procesu(u.stan / przy_uzyciu.ZAMEK):
        assert instalator.sprzatnij_pobrane(u, {"a" * 16}, logi.append, teraz=teraz) is False
    assert len(list(pobrane.iterdir())) == len(pliki) + 1
    assert logi == ["archiwa w <cache>/pobrane zostają do następnej instalacji: trwa instalacja narzędzia przy "
                    "pierwszym użyciu"]
    logi.clear()
    assert instalator.sprzatnij_pobrane(u, {"a" * 16}, logi.append, teraz=teraz) is True
    assert sorted(p.name for p in pobrane.iterdir()) == ["a" * 16 + "-uv.zip.czesc", "b" * 16 + "-chrome-win64.zip",
                                                         "b" * 16 + "-chrome-win64.zip.czesc"]
    assert logi == [f"w {pobrane} zostają świeże pliki, które pobiera albo rozpakowuje inny proces (3): usunie je "
                    "następne sprzątanie"]
    # po SWIEZE_S następne sprzątanie usuwa resztę
    assert instalator.sprzatnij_pobrane(u, set(), logi.append, teraz=teraz + instalator.SWIEZE_S + 1) is True
    assert list(pobrane.iterdir()) == []


class AtrapaCacheUv:
    """venvy.sprzatnij_cache bez prawdziwego uv: czyści <cache>/uv jak `uv cache clean`."""

    def __init__(self):
        self.wywolania: list[Path] = []

    def sprzatnij_cache(self, u, uv, *, log=print):
        self.wywolania.append(Path(uv))
        instalator.usun_zawartosc(u.cache / "uv")
        log("cache uv: Removed 1 file (2.0MiB)")
        return True


def test_sprzatanie_po_udanej_instalacji_i_drugi_przebieg_bez_sieci(tmp_path, stanowisko):
    s, u = stanowisko, stanowisko["u"]
    cache_uv = AtrapaCacheUv()
    s["moduly"].update({"venvy": cache_uv, "tesseract": tesseract})       # prawdziwe sprzątanie cache pixi
    app = tc._aplikacja(tmp_path, s["adres"], s["www"])
    # z poprzedniej próby: koła w cache uv i paczki w cache pixi (znikają), źródła skilli i cache npm (zostają),
    # resztka starej wersji uv, której pobieracz nie usunął (zajęty plik), i świeże pobieranie innego procesu
    # (przeglądarka komputera Jarva przy starcie usługi: zostaje do następnego sprzątania)
    obce = "f" * 16 + "-chrome-win64.zip.czesc"
    pliki = {"cache/uv/archive-v0/a/kolo.bin": 2 * MB, "cache/pixi/pkgs/tesseract/eng.traineddata": 2 * MB,
             "cache/build/skille@0123456789ab/SKILL.md": 10, "cache/npm/_cacache/index": 10,
             "program/narzedzia/uv/0.12.12.stary-1/uv.exe": 10, f"cache/pobrane/{obce}": 10}
    for rel, n in pliki.items():
        (u.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (u.root / rel).write_bytes(b"x" * n)
    os.chmod(u.root / "cache/pixi/pkgs/tesseract/eng.traineddata", stat.S_IREAD)
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    assert [p.name for p in (u.cache / "pobrane").iterdir()] == [obce]      # archiwa uv i obu Pythonów znikają
    assert f"w {u.cache / 'pobrane'} zostają świeże pliki, które pobiera albo rozpakowuje inny proces (1)" in log
    assert not list((u.cache / "uv").rglob("*.bin")) and not (u.cache / "pixi").exists()
    assert not (u.program / "narzedzia" / "uv" / "0.12.12.stary-1").exists()
    assert (u.root / "cache/build/skille@0123456789ab/SKILL.md").is_file()
    assert (u.root / "cache/npm/_cacache/index").is_file()
    assert re.search(r"^Sprzątanie: zwolnione [\d,]+ GB \(archiwa narzędzi 0,\d\d GB, cache uv 0,00 GB, cache pixi "
                     r"0,00 GB, stara wersja uv 0,00 GB\)$", log, re.M), log
    assert re.search(r"^Miejsce: Jarvo zajmuje [\d,]+ GB.*; wolne [\d,]+ GB na dysku .+$", log, re.M)
    assert cache_uv.wywolania == [u.program / "narzedzia" / "uv" / "0.12.13" / ("uv.exe" if WINDOWS else "uv")]
    assert log.index("Sprzątanie:") < log.index("Gotowe. Zmiany w tym przebiegu:")
    # drugi przebieg bez sieci: plików na serwerze już nie ma, ale nic nie trzeba pobierać ani sprzątać
    for p in s["www"].iterdir():
        p.unlink()
    przed = tc._migawka(u.root)
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    assert "Gotowe. Zmiany w tym przebiegu: brak." in s["log"]
    assert not [x for x in s["log"] if x.startswith("Sprzątanie")] and any(x.startswith("Miejsce:") for x in s["log"])
    assert tc._migawka(u.root) == przed and len(cache_uv.wywolania) == 1


def test_front_bez_node_modules_po_budowie_a_zrodla_web_zostaja(atrapa, tmp_path):
    u = th._uklad(tmp_path)
    checkout = atrapa.instaluj(u)
    logi: list[str] = []
    dist = hermes.web_dist(u, checkout, npm=atrapa.npm, log=logi.append, jarva=False)
    assert (dist / "index.html").is_file()
    assert json.loads((checkout / hermes.ZNACZNIK_WEB).read_text(encoding="utf-8"))["commit"] == th.COMMIT
    assert not (checkout / "node_modules").exists()                       # npm ci atrapy zakłada je w korzeniu
    assert any(x.startswith("Hermes: usunięte node_modules (") for x in logi)
    # node_modules z instalacji sprzed sprzątania, z junction workspace'u (node_modules/web → web): znika bez
    # budowy, a źródła web zostają
    (checkout / "web" / "node_modules" / "vite").mkdir(parents=True)
    (checkout / "web" / "node_modules" / "vite" / "index.js").write_text("x", encoding="utf-8")
    (checkout / "node_modules" / "react").mkdir(parents=True)
    _dowiazanie_katalogu(checkout / "web", checkout / "node_modules" / "web")
    atrapa.wyczysc()
    logi.clear()
    assert hermes.web_dist(u, checkout, npm=tmp_path / "nie-ma-npm", log=logi.append, jarva=False) == dist
    assert atrapa.wpisy() == [] and not (checkout / "node_modules").exists()
    assert not (checkout / "web" / "node_modules").exists() and (checkout / "web" / "package.json").is_file()
    assert any(x.startswith("Hermes: usunięte web/node_modules (") for x in logi)
    logi.clear()
    hermes.web_dist(u, checkout, npm=tmp_path / "nie-ma-npm", log=logi.append, jarva=False)
    assert not [x for x in logi if "usunięte" in x]


def test_front_przy_drugim_instalatorze_bez_czekania_i_z_latkami_jarva(atrapa, tmp_path, monkeypatch):
    u = th._uklad(tmp_path)
    checkout = atrapa.instaluj(u)
    dist = hermes.web_dist(u, checkout, npm=atrapa.npm, log=lambda _t: None, jarva=False)
    # resztki node_modules przy gotowym froncie, a hermes.lock trzyma drugi instalator: zostają, bez czekania
    (checkout / "node_modules" / "react").mkdir(parents=True)
    logi: list[str] = []
    with _zamki_drugiego_procesu(u.stan / "hermes.lock"):
        assert hermes.web_dist(u, checkout, npm=tmp_path / "nie-ma-npm", log=logi.append, jarva=False) == dist
    assert (checkout / "node_modules" / "react").is_dir()
    assert "Hermes: node_modules zostają do następnego przebiegu (drugi instalator właśnie używa checkoutu)" in logi
    # front zbudował drugi instalator, gdy ten czekał na zamek: wynik to i tak kopia z łatkami Jarva, nie goły dist
    latane = tmp_path / "web-dist-z-latkami"
    monkeypatch.setattr(hermes, "dist_jarva", lambda u_, d, log=print, **kw: latane if d == dist else None)
    sprawdzil = threading.Event()
    prawdziwy = hermes._program

    def program(sciezka, nazwa):                     # web_dist sprawdził znacznik i szuka npm, zaraz weźmie zamek
        sprawdzil.set()
        return prawdziwy(sciezka, nazwa)
    monkeypatch.setattr(hermes, "_program", program)
    (checkout / hermes.ZNACZNIK_WEB).unlink()
    atrapa.wyczysc()
    wynik: list = []
    with _zamki_drugiego_procesu(u.stan / "hermes.lock"):
        watek = threading.Thread(target=lambda: wynik.append(hermes.web_dist(u, checkout, npm=atrapa.npm,
                                                                             log=lambda _t: None)))
        watek.start()
        assert sprawdzil.wait(30)
        (checkout / hermes.ZNACZNIK_WEB).write_text(json.dumps({"commit": th.COMMIT}), encoding="utf-8")
    watek.join(60)
    assert wynik == [latane] and atrapa.wpisy("npm") == []


def test_venvy_miejsce_z_manifestu():
    wpis = {"pobranie_mb": {"windows-x64": 100, "linux-x64": 150}, "venv_mb": 400}
    assert venvy.miejsce(wpis, "windows-x64") == (400 * MB, pytest.approx(400 * venvy.WSP_CACHE * MB, abs=10))
    assert venvy.miejsce(wpis, "linux-x64")[0] == 600 * MB                    # venv_mb × pobranie platformy / Windows
    assert venvy.miejsce(wpis, "macos-arm64")[0] == 600 * MB                  # bez platformy: największe pobranie
    assert venvy.miejsce({"pobranie_mb": {"linux-x64": 100}}, "linux-x64")[0] == int(100 * venvy.WSP_VENVU * MB)
    assert venvy.miejsce({}, "linux-x64") == (0, 0)
    for nazwa, w in LOCK["venvy"].items():
        for p in sciezki.PLATFORMY:
            v, c = venvy.miejsce(w, p)
            assert 100 * MB < v < 3 * GB and 0 < c < v, (nazwa, p)


ATRAPA_UV_CACHE = r'''
import json, os, shutil, sys
with open(os.environ["ATRAPA_UV_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cache": os.environ.get("UV_CACHE_DIR"),
                        "python": os.environ.get("UV_PYTHON")}) + "\n")
if os.environ.get("ATRAPA_UV_KOD"):
    print("error: cache in use", file=sys.stderr)
    sys.exit(int(os.environ["ATRAPA_UV_KOD"]))
shutil.rmtree(os.environ["UV_CACHE_DIR"])
print("Clearing cache at: " + os.environ["UV_CACHE_DIR"])
print("Removed 2 files (2.0MiB)")
'''


def test_venvy_sprzatnij_cache_to_uv_cache_clean(tmp_path, monkeypatch):
    dziennik = tmp_path / "uv-cache.log"
    monkeypatch.setenv("ATRAPA_UV_LOG", str(dziennik))
    monkeypatch.delenv("ATRAPA_UV_KOD", raising=False)
    monkeypatch.setenv("UV_PYTHON", "obcy-python")                        # z otoczenia właściciela: nie przechodzi
    uv = atrapy.program(tmp_path / "uv-bin", "uv", ATRAPA_UV_CACHE)
    u = uklad(tmp_path / "j")
    (u.cache / "uv" / "archive-v0").mkdir(parents=True)
    (u.cache / "uv" / "archive-v0" / "a.bin").write_bytes(b"x" * 100)
    logi: list[str] = []
    # drugi instalator buduje venv albo instaluje Hermesa (trzeci krok uv sync --offline bierze koła z cache): uv nie
    # rusza, cache zostaje, bez czekania; zamki to te same pliki, które biorą venvy.zainstaluj i hermes.zainstaluj
    assert venvy.ZAMKI_CACHE == (venvy.ZAMEK, "hermes.lock")
    assert "u.stan / ZAMEK" in inspect.getsource(venvy.zainstaluj)
    assert 'u.stan / "hermes.lock"' in inspect.getsource(hermes.zainstaluj)
    for zamek in venvy.ZAMKI_CACHE:
        with _zamki_drugiego_procesu(u.stan / zamek):
            assert venvy.sprzatnij_cache(u, uv, log=logi.append) is False
        assert logi[-1] == ("cache uv zostaje do następnej instalacji (drugi instalator właśnie buduje venv albo "
                            "instaluje Hermesa)")
        assert not dziennik.exists() and (u.cache / "uv" / "archive-v0" / "a.bin").is_file()
    logi.clear()
    assert venvy.sprzatnij_cache(u, uv, log=logi.append) is True
    w = json.loads(dziennik.read_text(encoding="utf-8").splitlines()[-1])
    assert w["argv"] == ["cache", "clean", "--no-config"] and w["python"] is None
    assert os.path.normcase(w["cache"]) == os.path.normcase(str(u.cache / "uv"))
    assert not (u.cache / "uv").exists() and logi == ["cache uv: Removed 2 files (2.0MiB)"]
    monkeypatch.setenv("ATRAPA_UV_KOD", "2")
    (u.cache / "uv").mkdir()
    assert venvy.sprzatnij_cache(u, uv, log=logi.append) is False
    assert logi[-1] == "cache uv zostaje do następnej instalacji (uv cache clean: kod 2, error: cache in use)"


@pytest.mark.parametrize("platforma", sciezki.PLATFORMY)
def test_tesseract_miejsce_z_rozmiarow_paczek_pixi_lock(platforma):
    razem, sam = tesseract.rozmiary_paczek(REPO, platforma)
    assert 100 * MB < razem < GB and 100 * MB < sam < razem                  # paczka tesseract to głównie języki
    cache, srod, zostaje = tesseract.miejsce(REPO, platforma)
    assert cache == int(razem * tesseract.WSP_CONDA)               # rozpakowane paczki w cache pixi
    assert srod == zostaje and 0 < zostaje < cache / 2              # środowisko dzieli pliki z cache, bez języków
    if platforma == "windows-arm64":
        assert (razem, sam) == tesseract.rozmiary_paczek(REPO, "windows-x64")   # paczki win-64 w emulacji (I27)
    assert tesseract.rozmiary_paczek(REPO / "nie-ma", platforma) == (0, 0)


def test_tesseract_sprzatnij_cache_pixi(tmp_path):
    u = uklad(tmp_path / "j")
    assert tesseract.sprzatnij_cache(u, log=lambda _t: None) is False        # bez cache: nic do zrobienia
    plik = u.cache / "pixi" / "pkgs" / "tesseract-5.5.3" / "share" / "tessdata" / "eng.traineddata"
    plik.parent.mkdir(parents=True)
    plik.write_bytes(b"x")
    os.chmod(plik, stat.S_IREAD)                                               # tylko do odczytu, jak w paczkach
    logi: list[str] = []
    # drugi instalator właśnie robi `pixi install` (ten sam zamek co tesseract.zainstaluj): cache zostaje, bez czekania
    assert "u.stan / ZAMEK" in inspect.getsource(tesseract.zainstaluj)
    with _zamki_drugiego_procesu(u.stan / tesseract.ZAMEK):
        assert tesseract.sprzatnij_cache(u, log=logi.append) is False
    assert plik.is_file() and logi == ["Tesseract: cache paczek pixi zostaje do następnej instalacji (drugi instalator "
                                       "właśnie instaluje Tesseracta)"]
    logi.clear()
    assert tesseract.sprzatnij_cache(u, log=logi.append) is True and not (u.cache / "pixi").exists()
    assert logi == ["Tesseract: cache paczek pixi usunięty (środowisko zostaje, znacznik pomija pixi w kolejnym "
                    "przebiegu)"]


# ---------------------------------------------------------------- narzędzia npm floty i ManimGX w programach floty

ATRAPA_NPM = r'''
import json, os, sys
from pathlib import Path
with open(os.environ["ATRAPA_NPM_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "cache": os.environ.get("npm_config_cache")}) + "\n")
Path(os.environ["npm_config_cache"], "_cacache").mkdir(parents=True, exist_ok=True)
Path(os.environ["npm_config_cache"], "_cacache", "paczki.bin").write_bytes(b"t" * 3000)       # paczki z rejestru
for p in ("hyperframes", "inspo-mcp", "lighthouse", "playwright-core", "sharp", "three"):
    Path("node_modules", p).mkdir(parents=True, exist_ok=True)
    Path("node_modules", p, "package.json").write_text("{}", encoding="utf-8")
Path("node_modules", ".bin").mkdir(exist_ok=True)
for n in ("hyperframes", "hyperframes.cmd"):
    Path("node_modules", ".bin", n).write_text("atrapa", encoding="utf-8")
'''


def _app_z_node_floty(tmp_path: Path, adres: str, www: Path) -> Path:
    """Kod Jarva jak _pelna_aplikacja, z infra/node tej wersji (node_floty.py i lock) i z Node.js z manifestu, którego
    npm to atrapa `npm ci` (paczki z SPRAWDZ w node_modules, paczki „z rejestru” w cache npm)."""
    app = _pelna_aplikacja(tmp_path, adres, www)
    (app / "infra" / "node").mkdir(parents=True)
    for plik in ("node_floty.py", "package.json", "package-lock.json"):
        (app / "infra" / "node" / plik).write_bytes((REPO / "infra" / "node" / plik).read_bytes())
    npm = {"node/npm_atrapa.py": ATRAPA_NPM.encode(), "node/node.exe": b"node",
           "node/npm.cmd": f'@"{sys.executable}" "%~dp0npm_atrapa.py" %*\r\n'.encode(),
           "node/npm": f"#!{sys.executable}\n{ATRAPA_NPM}".encode()}
    dane = tc._tar_gz(npm)
    (www / "npm-node.tar.gz").write_bytes(dane)
    lock = json.loads((app / manifest.LOCK).read_text(encoding="utf-8"))
    wpis = {"url": f"{adres}/npm-node.tar.gz", "sha256": _sha(dane), "rozmiar": len(dane), "format": "tar.gz",
            "usun_poziom": 1, "bin": ["."]}
    lock["narzedzia"]["node"] = {"wersja": "26.12.1", "kiedy": "instalacja",
                                 "pliki": {p: wpis for p in sciezki.PLATFORMY}}
    (app / manifest.LOCK).write_text(json.dumps(lock), encoding="utf-8")
    return app


def test_narzedzia_npm_floty_krok_instalatora_i_drugi_przebieg(tmp_path, stanowisko, monkeypatch):
    """Krok „Narzędzia npm floty” (kontrola-17, bloker): po Node.js i Tesseracie, przed spisem narzędzi; npm ci z locka
    infra/node npm-em z Node.js z manifestu, wpis node-floty w narzedzia.json (NODE_PATH, .bin w PATH, prefix npm dla
    `npx hyperframes`) i w srodowisko.json, cache npm narzędzi sprzątnięty po instalacji, miejsce policzone przed.
    Drugi przebieg: bez npm, bez sieci, „Zmiany: brak”."""
    s, u = stanowisko, stanowisko["u"]
    s["moduly"].update({"venvy": AtrapaVenvow(), "modele": AtrapaModeli(), "tesseract": AtrapaTesseracta(),
                        "bin_floty": AtrapaProgramow()})
    zapis = tmp_path / "npm.jsonl"
    monkeypatch.setenv("ATRAPA_NPM_LOG", str(zapis))
    app = _app_z_node_floty(tmp_path, s["adres"], s["www"])
    potrzeby = {p.opis: p for p in instalator.potrzebne_miejsce(u, app, sciezki.platforma())}
    assert potrzeby["narzędzia npm floty"].zostaje == instalator.NODE_FLOTY_MB["katalog"] * MB
    assert potrzeby["cache npm narzędzi floty"].zostaje == 0 and potrzeby["cache npm narzędzi floty"].gdzie == u.cache
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    log = "\n".join(s["log"])
    kroki = re.findall(r"^\[[#-]+\] +\d+/\d+  (.+)$", log, re.M)
    assert kroki.index("Tesseract") < kroki.index("Narzędzia npm floty") == kroki.index("Spis narzędzi") - 1
    assert kroki.index("Node.js i npm") < kroki.index("Narzędzia npm floty")
    nf = instalator.modul_node_floty(app)
    kat = u.program / "node-floty" / nf.suma_locka()[:12]
    narz = srodowisko.narzedzia(u)["node-floty"]
    assert narz["katalog"] == str(kat) and narz["bin"] == [str(kat / "node_modules" / ".bin")]
    zapisane = json.loads((u.stan / "srodowisko.json").read_text(encoding="utf-8"))
    assert zapisane["NODE_PATH"] == str(kat / "node_modules")
    assert zapisane["npm_config_prefix"] == str(kat / "npm-prefix")
    assert str(kat / "node_modules" / ".bin") in zapisane["PATH"].split(os.pathsep)
    wywolania = [json.loads(x) for x in zapis.read_text(encoding="utf-8").splitlines()]
    assert len(wywolania) == 1 and wywolania[0]["argv"][:2] == ["ci", "--ignore-scripts"]
    assert Path(wywolania[0]["cache"]) == u.cache / "npm-floty" and not (u.cache / "npm-floty").exists()
    assert "    narzędzia npm floty: zainstalowane" in log and "cache npm narzędzi floty 0,00 GB" in log
    assert "narzędzia npm floty" in re.search(r"^Gotowe\. Zmiany w tym przebiegu: (.+)\.$", log, re.M).group(1)
    assert not [p for p in instalator.potrzebne_miejsce(u, app, sciezki.platforma()) if "npm narzędzi" in p.opis
                or p.opis == "narzędzia npm floty"]                       # gotowy katalog tego locka: 0
    for p in s["www"].iterdir():                                       # drugi przebieg bez sieci
        p.unlink()
    assert tc._instaluj(s, app) == 0, "\n".join(s["log"])
    assert "Gotowe. Zmiany w tym przebiegu: brak." in s["log"]
    assert "    narzędzia npm floty: już są" in "\n".join(s["log"])
    assert len(zapis.read_text(encoding="utf-8").splitlines()) == 1


def test_narzedzia_npm_floty_tylko_z_lockiem_i_npm_z_manifestu(tmp_path, stanowisko):
    """Kod bez infra/node (starsza wersja, atrapy testów): bez kroku; prawdziwy manifest ma Node.js na każdej
    platformie, więc krok jest wszędzie tuż przed spisem narzędzi; Node.js bez npm: błąd z radą, bez npm z PATH."""
    s = stanowisko

    def kroki(app, platforma="linux-x64"):
        inst = instalator._Instalacja(s["u"], app, s["otoczenie"](), s["log"].append, autostart=False,
                                      web_lokalnie=False, start=False, bez_path=False, platforma=platforma)
        return inst, [n for n, _f in inst.kroki()]
    _inst, bez = kroki(_pelna_aplikacja(tmp_path, s["adres"], s["www"]))
    assert "Narzędzia npm floty" not in bez and "Node.js i npm" in bez
    for platforma in sciezki.PLATFORMY:
        inst, z = kroki(REPO, platforma)
        assert z.index("Narzędzia npm floty") == z.index("Spis narzędzi") - 1, platforma
    inst.narz = {"node": {"katalog": str(tmp_path / "node-bez-npm"), "bin": [str(tmp_path / "node-bez-npm")]}}
    with pytest.raises(instalator.BladInstalacji, match="npm z Node.js z manifestu"):
        inst.node_floty()


def test_programy_floty_maja_manimgx_z_kodu_tej_wersji(tmp_path, stanowisko):
    """Krok „Programy floty”: `manimgx` (jarvo/manimgx.py tej wersji, M04) w bin-floty dla Pythona 3.13 z instalacji,
    obok nakładki agent-browsera; program działa (`--jarvo-stan` bez ManimGX: JSON, kod 0), a drugi raz niczego nie
    zapisuje. Bez Pythona 3.13 albo bez jarvo/manimgx.py w kodzie wersji: bez programu."""
    s = stanowisko
    inst = instalator._Instalacja(s["u"], REPO, s["otoczenie"](), s["log"].append, autostart=False, web_lokalnie=False,
                                  start=False, bez_path=False, platforma=sciezki.platforma())
    inst.narz = {"python313": {"katalog": str(Path(sys.base_prefix))}}
    if not inst._bin_narzedzia("python313").is_file():
        pytest.skip(f"brak {inst._bin_narzedzia('python313')} (Python w innym układzie niż z manifestu)")
    s["u"].bin_floty.mkdir(parents=True, exist_ok=True)
    program = s["u"].bin_floty / ("manimgx.exe" if WINDOWS else "manimgx")
    assert inst._manimgx() == [str(program)] and inst._manimgx() == []
    env = {k: v for k, v in os.environ.items() if not k.startswith(("JARVO_", "MANIMGX_"))}
    r = subprocess.run([str(program), "--jarvo-stan"], capture_output=True, text=True, encoding="utf-8", env=env,
                       cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stderr
    stan = json.loads(r.stdout)
    assert isinstance(stan["gotowy"], bool) and stan["cache"]        # bez instalacji natywnej: stan, bez pobierania
    inst.narz = {}
    assert inst._manimgx() == []
    inst.narz = {"python313": {"katalog": str(Path(sys.base_prefix))}}
    inst.app = tmp_path / "bez-manimgx"
    assert inst._manimgx() == []

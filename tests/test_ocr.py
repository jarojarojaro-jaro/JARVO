"""Wspólny skill odczyt-ekranu: ocr.py (Indra OCR, zapas Tesseract), obraz i przypisanie we flocie."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "shared" / "skills" / "odczyt-ekranu"
OCR = SKILL / "scripts" / "ocr.py"
spec = importlib.util.spec_from_file_location("ocr_jarvo", OCR)
ocr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr)

AGENCI = ("jarvo", "jarvo-sherlock", "jarvo-web", "jarvo-studio", "jarvo-wideo", "jarvo-ads", "jarvo-reka",
          "jarvo-mobile", "jarvo-lowca")


def _linia(tekst, ramka=(100, 10, 400, 40), pewnosc=0.95):
    return {"tekst": tekst, "ramka": list(ramka), "pewnosc": pewnosc}


# ------------------------------------------------------------------ szukanie napisu

def test_szukaj_bez_wielkosci_liter_i_ogonkow_z_ramka_i_srodkiem():
    strony = [{"strona": 1, "linie": [_linia("Anuluj"), _linia("Źródło: Łódź, ul. Żółta 5", (0, 50, 250, 80))]}]
    t = ocr.szukaj(strony, "zrodlo")
    assert len(t) == 1 and t[0]["tekst"] == "Źródło" and t[0]["linia"].startswith("Źródło")
    assert t[0]["ramka"][0] == 0 and t[0]["ramka"][2] < 250 and t[0]["ramka"][1:4:2] == [50, 80]
    assert t[0]["srodek"] == [round(t[0]["ramka"][2] / 2), 65]
    assert ocr.szukaj(strony, "LODZ")[0]["tekst"] == "Łódź"
    assert ocr.szukaj(strony, "zolta  5")[0]["tekst"] == "Żółta 5"          # wiele spacji jak jedna
    assert ocr.szukaj(strony, "Zapisz") == []


def test_szukaj_kazde_wystapienie_i_pusta_fraza():
    strony = [{"strona": 2, "linie": [_linia("OK ok OK", (0, 0, 80, 10))]}]
    t = ocr.szukaj(strony, "ok")
    assert [x["ramka"][0] for x in t] == [0, 30, 60] and {x["strona"] for x in t} == {2}
    with pytest.raises(ocr.Blad):
        ocr.szukaj(strony, "   ")


def test_zakres_stron():
    assert ocr.zakres_stron("1-3,5", 10) == [0, 1, 2, 4]
    assert ocr.zakres_stron("4-", 6) == [3, 4, 5]
    assert ocr.zakres_stron("2,2,9", 3) == [1]
    assert ocr.zakres_stron(None, 80) == list(range(ocr.MAKS_STRON))
    with pytest.raises(ocr.Blad):
        ocr.zakres_stron("pierwsza", 3)


def test_tsv_tesseracta_sklada_slowa_w_linie():
    naglowek = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    w = [naglowek,
         "5\t1\t1\t1\t1\t1\t10\t20\t50\t15\t96\tFaktura",
         "5\t1\t1\t1\t1\t2\t70\t18\t40\t17\t90\tnr",
         "4\t1\t1\t1\t2\t0\t10\t40\t100\t15\t-1\t",
         "5\t1\t1\t1\t2\t1\t10\t40\t60\t15\t80\t1234",
         "5\t1\t1\t1\t2\t2\t80\t40\t10\t15\t95\t "]
    linie = ocr._tsv_linie("\n".join(w))
    assert [ln["tekst"] for ln in linie] == ["Faktura nr", "1234"]
    assert linie[0]["ramka"] == [10, 18, 110, 35] and linie[0]["pewnosc"] == 0.93
    assert linie[1]["pewnosc"] == 0.8


# ------------------------------------------------------------------ silniki i wybór

def test_auto_bez_indry_czyta_tesseract_i_mowi_to(monkeypatch, tmp_path):
    obraz = tmp_path / "z.png"
    obraz.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(ocr, "_indra", lambda: None)
    monkeypatch.setattr(ocr, "czytaj_tesseract",
                        lambda plik, strony, dpi, jezyk, tmp: [{"strona": 1, "zrodlo": "ocr", "obrot": 0,
                                                               "linie": [_linia("Zapisz")], "markdown": None}])
    a = Namespace(silnik="auto", strony=None, dpi=200.0, watki=2, wzory=False, jezyk="pol+eng", czas=None)
    r = ocr.odczytaj(obraz, a, tmp_path)
    assert r["silnik"] == "tesseract" and "Indry OCR" in r["uwagi"][0]
    a.silnik = "indra"
    with pytest.raises(ocr.Blad, match="Indra OCR"):
        ocr.odczytaj(obraz, a, tmp_path)


def test_brak_pliku_to_blad_po_polsku(tmp_path, capsys):
    assert ocr.main([str(tmp_path / "nie-ma.png")]) == 1
    assert "nie ma pliku" in capsys.readouterr().err


def test_siec_zablokowana_w_czasie_odczytu():
    kod = (f"import importlib.util, socket; s = importlib.util.spec_from_file_location('o', {str(OCR)!r}); "
           "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); m.zablokuj_siec()\n"
           "try:\n    socket.create_connection(('example.com', 443), timeout=2)\nexcept PermissionError as e:\n"
           "    print('blokada', e)\n")
    # -X utf8: -I pomija PYTHONUTF8, a na Windows potok miałby stronę kodową ANSI (komunikat ma polskie litery)
    out = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", kod], capture_output=True, text=True,
                         encoding="utf-8", timeout=60).stdout
    assert out.startswith("blokada") and "bez sieci" in out


@pytest.mark.posix_only
def test_przejscie_do_venvu_ocr_na_posix_przez_execv(tmp_path, monkeypatch):
    """POSIX: przeskok do venvu OCR jak dotąd przez os.execv (ten sam proces), bez -X utf8."""
    import atrapy
    py = atrapy.program(tmp_path, "ocr-python", "pass" + chr(10))
    monkeypatch.setattr(ocr, "_indra", lambda: None)
    monkeypatch.setenv("JARVO_OCR_PYTHON", str(py))
    wolania = []

    def execv(p, argv):
        wolania.append((p, argv))
        raise SystemExit(0)
    monkeypatch.setattr(ocr.os, "execv", execv)
    with pytest.raises(SystemExit):
        ocr._do_venvu(["zrzut.png", "--szukaj", "Zapisz"])
    p, argv = wolania[0]
    assert p == str(py) and argv[:2] == [str(py), "-I"] and argv[2].endswith("ocr.py")
    assert argv[3:] == ["zrzut.png", "--szukaj", "Zapisz"]


@pytest.mark.windows_only
def test_przejscie_do_venvu_ocr_oddaje_kod_i_wyjscie(tmp_path, monkeypatch, capfd):
    """Windows: ten sam skrypt w venvie OCR w nowym procesie (execv odpina tam proces), z jego kodem wyjścia."""
    import atrapy
    py = atrapy.program(tmp_path, "ocr-python", "import sys\nprint('venv', *sys.argv[1:])\nsys.exit(5)\n")
    monkeypatch.setattr(ocr, "_indra", lambda: None)
    monkeypatch.setenv("JARVO_OCR_PYTHON", str(py))
    with pytest.raises(SystemExit) as e:
        ocr._do_venvu(["zrzut.png", "--szukaj", "Zapisz"])
    assert e.value.code == 5
    out = capfd.readouterr().out
    assert out.split()[:2] == ["venv", "-I"] and "ocr.py" in out and "zrzut.png --szukaj Zapisz" in out
    assert "-X utf8" in out                                      # Windows: wynik w UTF-8 mimo -I
    monkeypatch.setenv("JARVO_OCR_PYTHON", sys.executable)        # już w venvie: bez przeskoku i bez pętli
    ocr._do_venvu(["zrzut.png"])


# ------------------------------------------------------------------ obraz, lock, flota, dokumenty

def test_obraz_przypina_indre_i_modele_sumami_bez_huggingface_hub():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(line for line in docker.splitlines() if not line.lstrip().startswith("#"))
    run = next(r for r in code.split("\nRUN ") if "/opt/jarvo/venvs/ocr" in r)
    for flaga in ("--no-config", "--no-deps", "--require-hashes", "--only-binary :all:", "requirements-ocr.txt",
                  "--python 3.12", "sha256sum -c", "JARVO-ZRODLO.txt", "HF_HUB_OFFLINE=1"):
        assert flaga in run, flaga
    url = re.search(r"ARG INDRA_OCR_URL=(\S+)", docker).group(1)
    assert url.endswith("/resolve/ed345c7f158eddbc7dee0c6a7269afb75a94f7e8")
    pobierane = set(re.search(r"for f in ([^;]+); do", run).group(1).replace("\\\n", " ").split())
    sprawdzane = set(re.findall(r'\$d/([\w.]+)"', run.split("sha256sum -c")[0]))
    assert pobierane == sprawdzane and {"det.onnx", "rec.onnx", "order.onnx", "meta.json", "LICENSE"} <= pobierane
    assert "ENV INDRA_OCR_MODEL_DIR=/opt/jarvo/models/indra-ocr" in docker
    lock = (REPO / "infra" / "python" / "requirements-ocr.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([a-z0-9-]+)==(\S+)(?: ;[^\\]*)? \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n?)+)", lock, re.M)
    names = {n: v for n, v, _h in pins}
    assert len(pins) == len(re.findall(r"^[a-z0-9-]+==", lock, re.M))
    assert names["indra-ocr"] == "0.3.2" and names["onnxruntime"] == "1.31.0"
    assert {"numpy", "opencv-python-headless", "pypdfium2"} <= set(names)
    assert not {"huggingface-hub", "hf-xet", "httpx2", "requests", "fsspec", "tqdm"} & set(names)
    assert "d55ad2be54c45df80e977626bcf0d64cf6df7aa20eecf608f90669c90057eed2" in lock


def test_skill_u_kazdego_agenta_z_narzedziem_i_wpisem():
    lock = yaml.safe_load((REPO / "vendor" / "skills.lock.yaml").read_text(encoding="utf-8"))
    for agent in AGENCI:
        assert {"source": "jarvo", "path": "shared/skills/odczyt-ekranu", "dest": "pliki/odczyt-ekranu"} in lock["agents"][agent]
        tb = yaml.safe_load((REPO / "profiles" / agent / "toolbox.yaml").read_text(encoding="utf-8"))
        assert "indra-ocr" in {t["name"] for t in tb["tools"]}
        assert "odczyt-ekranu" in (REPO / "profiles" / agent / "CHANGELOG.md").read_text(encoding="utf-8")
    meta = yaml.safe_load((SKILL / "SKILL.md").read_text(encoding="utf-8").split("---")[1])
    assert meta["name"] == "odczyt-ekranu" and len(meta["description"]) <= 60
    assert "$HERMES_HOME/skills/pliki/odczyt-ekranu/scripts/ocr.py" in (SKILL / "SKILL.md").read_text(encoding="utf-8")
    zr = yaml.safe_load((REPO / "vendor" / "zrodla.yaml").read_text(encoding="utf-8"))["zrodla"]
    assert zr["indra"]["status"] == "uzywane" and "OpenRAIL" in zr["indra-ocr-modele"]["notatka"]


# ------------------------------------------------------------------ z prawdziwym silnikiem (kontener albo venv OCR)

def _python_ocr() -> str | None:
    import os
    for k in (os.environ.get("JARVO_OCR_PYTHON"), ocr.OCR_PYTHON):
        if k and Path(k).is_file():
            return k
    return None


@pytest.mark.skipif(_python_ocr() is None or ocr.katalog_modeli() is None, reason="brak venvu OCR i modeli Indry")
def test_prawdziwy_odczyt_i_szukanie(tmp_path):
    py = _python_ocr()
    obraz = tmp_path / "z.png"
    subprocess.run([py, "-I", "-c", "import cv2, numpy as n; im = n.full((200, 900), 255, n.uint8); "
                    "cv2.putText(im, 'Zapisz zmiany', (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 4); "
                    f"cv2.imwrite({str(obraz)!r}, im)"], check=True)
    r = subprocess.run([sys.executable, str(OCR), str(obraz), "--szukaj", "zapisz"], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    w = json.loads(r.stdout)
    assert w["silnik"] == "indra" and w["trafienia"] and 40 <= w["trafienia"][0]["srodek"][0] <= 400
    if shutil.which("tesseract"):
        r = subprocess.run([sys.executable, str(OCR), str(obraz), "--silnik", "tesseract"], capture_output=True,
                           text=True, encoding="utf-8", timeout=120)
        assert "Zapisz" in r.stdout

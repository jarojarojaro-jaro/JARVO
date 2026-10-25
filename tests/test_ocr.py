"""Wspólny skill odczyt-ekranu: ocr.py (Indra OCR, zapas Tesseract), obraz i przypisanie we flocie.

Natywnie (docs/NATYWNIE.md E05, E10, B13): obraz dla Indry przez np.fromfile + cv2.imdecode (polskie znaki w ścieżce
na Windows), Tesseract z obrazem na wejściu i TSV przez `-c tessedit_create_tsv=1`, strony PDF przez pypdfium2 zamiast
Ghostscriptu, programy pełną ścieżką i bez okna konsoli. Testy z prawdziwym silnikiem biegną tam, gdzie jest venv OCR
z modelami (JARVO_OCR_PYTHON, INDRA_OCR_MODEL_DIR: obraz Jarva albo środowisko procesów instalacji natywnej).
"""

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


def test_brak_pliku_to_blad_po_polsku(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ocr, "_do_venvu", lambda argv: None)      # w środowisku Jarva: bez przejścia do venvu OCR
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


# ------------------------------------------------------------------ natywnie: programy, Tesseract, obrazy i PDF

def test_programy_pelna_sciezka_i_bez_okna(monkeypatch, tmp_path):
    wolane = []
    monkeypatch.setattr(ocr.shutil, "which", lambda n: str(tmp_path / f"{n}.exe"))
    monkeypatch.setattr(ocr.subprocess, "run", lambda cmd, **k: wolane.append((cmd, k)) or
                        subprocess.CompletedProcess(cmd, 0, b"List of available languages (3):\neng\nosd\npol\n", b""))
    assert ocr.jezyki_tesseracta("pol+eng+deu") == "pol+eng"
    cmd, kw = wolane[0]
    assert cmd == [str(tmp_path / "tesseract.exe"), "--list-langs"] and kw["stdin"] == subprocess.DEVNULL
    assert kw["creationflags"] == (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def test_tesseract_dostaje_obraz_przez_wejscie_i_tsv_przez_c(monkeypatch, tmp_path):
    """B13: Tesseract ma wąskie API ścieżek, więc obraz idzie przez stdin; TSV przez -c (konfiguracja `tsv` bywa
    nie do znalezienia przy TESSDATA_PREFIX bez katalogu configs)."""
    kat = tmp_path / "Michał Żółć"
    kat.mkdir()
    obraz = kat / "faktura_październik.png"
    obraz.write_bytes(b"\x89PNG\r\n\x1a\nobraz")
    wolane = []
    tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           "5\t1\t1\t1\t1\t1\t10\t20\t50\t15\t96\tFaktura\n")

    def proc(cmd, timeout, **kw):
        wolane.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, tsv.encode(), b"")
    monkeypatch.setattr(ocr.shutil, "which", lambda n: "/x/tesseract" if n == "tesseract" else None)
    monkeypatch.setattr(ocr, "_proc", proc)
    monkeypatch.setattr(ocr, "jezyki_tesseracta", lambda chce: "pol+eng")
    strony = ocr.czytaj_tesseract(obraz, None, 200.0, "pol+eng", tmp_path)
    cmd, kw = wolane[0]
    assert cmd[:3] == ["tesseract", "stdin", "stdout"] and str(obraz) not in cmd
    assert cmd[cmd.index("-c") + 1] == "tessedit_create_tsv=1" and "--dpi" not in cmd
    assert kw["input"] == obraz.read_bytes()
    assert strony == [{"strona": 1, "zrodlo": "ocr", "obrot": 0, "markdown": None,
                       "linie": [{"tekst": "Faktura", "ramka": [10, 20, 60, 35], "pewnosc": 0.96}]}]


def test_pdf_dla_tesseracta_przez_pypdfium2_albo_blad(monkeypatch, tmp_path):
    pdf = tmp_path / "skan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    wolane = []
    monkeypatch.setattr(ocr.shutil, "which", lambda n: "/x/tesseract" if n == "tesseract" else None)
    monkeypatch.setattr(ocr, "jezyki_tesseracta", lambda chce: "pol")
    monkeypatch.setattr(ocr, "_proc", lambda cmd, timeout, **kw: wolane.append((cmd, kw)) or
                        subprocess.CompletedProcess(cmd, 0, b"", b""))
    monkeypatch.setattr(ocr, "_pdfium", lambda: object())
    monkeypatch.setattr(ocr, "strony_pdf_pypdfium", lambda plik, strony, dpi: [(2, b"P5 strona 2"), (5, b"P5 5")])
    strony = ocr.czytaj_tesseract(pdf, "2,5", 150.0, "pol", tmp_path)
    assert [s["strona"] for s in strony] == [2, 5] and [kw["input"] for _, kw in wolane] == [b"P5 strona 2", b"P5 5"]
    assert wolane[0][0][wolane[0][0].index("--dpi") + 1] == "150"        # PGM nie niesie rozdzielczości
    monkeypatch.setattr(ocr, "_pdfium", lambda: None)                    # bez pypdfium2 i bez Ghostscriptu
    with pytest.raises(ocr.Blad, match="pypdfium2"):
        ocr.czytaj_tesseract(pdf, None, 150.0, "pol", tmp_path)


def test_pgm_z_tablicy_szarosci():
    class Szarosc:
        shape = (2, 3)

        def tobytes(self):
            return bytes(range(6))
    assert ocr._pgm(Szarosc()) == b"P5\n3 2\n255\n" + bytes(range(6))


def test_indra_czyta_obraz_z_pamieci_a_pdf_przez_convert(monkeypatch, tmp_path):
    """Obraz trafia do Indry jako tablica z obrazy_pliku (np.fromfile + imdecode), a nie przez cv2.imread ścieżki."""
    class Strona:
        source, note, markdown, rotation = "ocr", "", "Zapisz", 0
        lines = [type("L", (), {"box": [1, 2, 30, 12], "text": "Zapisz", "conf": 0.9})()]

    class Konwerter:
        ocr = staticmethod(lambda obraz: Strona())

        def convert(self, plik, max_pages=0):
            return [(0, Strona())]
    wolane = []
    monkeypatch.setattr(ocr, "_indra", lambda: type("I", (), {"load": staticmethod(lambda *a, **k: Konwerter())}))
    monkeypatch.setattr(ocr, "katalog_modeli", lambda: tmp_path)
    monkeypatch.setattr(ocr, "zablokuj_siec", lambda: None)
    monkeypatch.setattr(ocr, "obrazy_pliku", lambda plik: wolane.append(plik) or ["klatka1", "klatka2"])
    obraz = tmp_path / "Michał Żółć" / "zrzut.png"
    obraz.parent.mkdir()
    obraz.write_bytes(b"\x89PNG")
    strony = ocr.czytaj_indra(obraz, None, 200.0, 2, False)
    assert wolane == [obraz] and [s["strona"] for s in strony] == [1, 2]
    assert strony[0]["linie"] == [{"tekst": "Zapisz", "ramka": [1, 2, 30, 12], "pewnosc": 0.9}]
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    assert ocr.czytaj_indra(pdf, None, 200.0, 2, False)[0]["zrodlo"] == "ocr" and wolane == [obraz]


def test_pdf_poznany_po_naglowku_w_pierwszych_1024_bajtach(monkeypatch, tmp_path):
    """Regresja z E8: PDF z bajtami przed „%PDF-” (puste linie, nagłówek z poczty) to dalej PDF, jak w Indrze
    (is_pdf) i PDFium; wcześniej trafiał do obrazy_pliku i kończył się „to nie jest PDF ani obraz”."""
    for nazwa, poczatek, jest in (("zwykly.pdf", b"", True), ("crlf.pdf", b"\r\n\r\n", True),
                                  ("mime.pdf", b"Content-Type: application/pdf\r\n\r\n", True),
                                  ("daleko.pdf", b" " * 1018, True), ("za-daleko.pdf", b" " * 1020, False)):
        p = tmp_path / nazwa
        p.write_bytes(poczatek + b"%PDF-1.4\n1 0 obj\n")
        assert ocr._pdf(p) is jest, nazwa
    png = tmp_path / "zrzut.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ocr._pdf(png) is False
    png.write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\x10tEXtOpis\0%PDF-1.4 w opisie")    # napis w metadanych to nie PDF
    assert ocr._pdf(png) is False
    for sygnatura in (b"\xff\xd8\xff\xe0", b"GIF89a", b"II*\x00", b"RIFF\0\0\0\0WEBPVP8 "):
        png.write_bytes(sygnatura + b" %PDF-1.4")
        assert ocr._pdf(png) is False, sygnatura
    # Tesseract: taki PDF idzie stronami z pypdfium2, a nie surowymi bajtami na wejście (Leptonica by go odrzuciła)
    wolane = []
    monkeypatch.setattr(ocr.shutil, "which", lambda n: "/x/tesseract" if n == "tesseract" else None)
    monkeypatch.setattr(ocr, "jezyki_tesseracta", lambda chce: "pol")
    monkeypatch.setattr(ocr, "_proc", lambda cmd, timeout, **kw: wolane.append(kw["input"]) or
                        subprocess.CompletedProcess(cmd, 0, b"", b""))
    monkeypatch.setattr(ocr, "_pdfium", lambda: object())
    monkeypatch.setattr(ocr, "strony_pdf_pypdfium", lambda plik, strony, dpi: [(1, b"P5 strona")])
    ocr.czytaj_tesseract(tmp_path / "crlf.pdf", None, 200.0, "pol", tmp_path)
    assert wolane == [b"P5 strona"]


def test_indra_czyta_pdf_z_bajtami_przed_naglowkiem_przez_convert(monkeypatch, tmp_path):
    class Strona:
        source, note, markdown, rotation = "text", "", "", 0
        lines = [type("L", (), {"box": [0, 0, 10, 10], "text": "Faktura", "conf": None})()]

    class Konwerter:
        def convert(self, plik, max_pages=0):
            return [(0, Strona())]
    monkeypatch.setattr(ocr, "_indra", lambda: type("I", (), {"load": staticmethod(lambda *a, **k: Konwerter())}))
    monkeypatch.setattr(ocr, "katalog_modeli", lambda: tmp_path)
    monkeypatch.setattr(ocr, "zablokuj_siec", lambda: None)
    monkeypatch.setattr(ocr, "obrazy_pliku", lambda plik: pytest.fail("PDF poszedł jak obraz"))
    pdf = tmp_path / "Michał Żółć" / "faktura_październik.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"\r\n\r\n%PDF-1.7\n")
    assert ocr.czytaj_indra(pdf, None, 200.0, 2, False)[0]["zrodlo"] == "text"


def test_indra_bez_telemetrii_onnxruntime(monkeypatch, tmp_path):
    """Koło onnxruntime na Windows ma dostawcę telemetrii ETW (vendor/zrodla.yaml): ocr.py wyłącza zdarzenia przed
    załadowaniem Indry; brak onnxruntime albo starsze API nie przeszkadza."""
    wylaczone = []
    ort = type(sys)("onnxruntime")
    ort.disable_telemetry_events = lambda: wylaczone.append(True)
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    ocr.bez_telemetrii()
    assert wylaczone == [True]
    monkeypatch.setitem(sys.modules, "onnxruntime", type(sys)("onnxruntime"))   # bez funkcji: bez błędu
    ocr.bez_telemetrii()
    kolejnosc = []
    monkeypatch.setattr(ocr, "bez_telemetrii", lambda: kolejnosc.append("telemetria"))
    monkeypatch.setattr(ocr, "zablokuj_siec", lambda: kolejnosc.append("siec"))
    monkeypatch.setattr(ocr, "katalog_modeli", lambda: tmp_path)
    monkeypatch.setattr(ocr, "obrazy_pliku", lambda plik: [])
    monkeypatch.setattr(ocr, "_indra", lambda: type("I", (), {"load": staticmethod(
        lambda *a, **k: kolejnosc.append("load") or object())}))
    (tmp_path / "z.png").write_bytes(b"\x89PNG")
    ocr.czytaj_indra(tmp_path / "z.png", None, 200.0, 2, False)
    assert kolejnosc == ["siec", "telemetria", "load"]


@pytest.mark.windows_only
def test_windows_bez_sciezek_obrazu(monkeypatch):
    """`\\opt\\jarvo\\…` na bieżącym dysku może założyć każdy zalogowany użytkownik: na Windows ani Pythona venvu, ani
    modeli z domyślnych ścieżek obrazu."""
    assert ocr.OCR_PYTHON is None and ocr.MODELE is None
    monkeypatch.setattr(ocr, "_indra", lambda: None)
    monkeypatch.delenv("JARVO_OCR_PYTHON", raising=False)
    monkeypatch.delenv("INDRA_OCR_MODEL_DIR", raising=False)
    monkeypatch.setattr(ocr.subprocess, "run", lambda *a, **k: pytest.fail("uruchomił Pythona spoza instalacji"))
    ocr._do_venvu(["zrzut.png"])
    assert ocr.katalog_modeli() is None


@pytest.mark.posix_only
def test_posix_sciezki_obrazu():
    assert ocr.OCR_PYTHON == "/opt/jarvo/venvs/ocr/bin/python" and ocr.MODELE == "/opt/jarvo/models/indra-ocr"


def test_stan_mowi_czym_pdf_idzie_do_tesseracta(monkeypatch):
    monkeypatch.setattr(ocr, "_pdfium", lambda: type("P", (), {"PYPDFIUM_INFO": "5.14.0"}))
    monkeypatch.setattr(ocr, "jezyki_tesseracta", lambda chce: "pol+eng")
    assert ocr.stan()["pdf_dla_tesseracta"] == "pypdfium2 5.14.0"
    monkeypatch.setattr(ocr, "_pdfium", lambda: None)
    monkeypatch.setattr(ocr.shutil, "which", lambda n: None)
    assert ocr.stan()["pdf_dla_tesseracta"] is None


def _zrob_obraz(py: str, cel: Path, napis: str) -> None:
    """Obraz z napisem przez OpenCV z venvu OCR; bajty zapisuje Python (cv2.imwrite nie zna polskich ścieżek)."""
    kod = ("import cv2, numpy as n, sys; im = n.full((200, 1100), 255, n.uint8); "
           f"cv2.putText(im, {napis!r}, (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 4); "
           "ok, b = cv2.imencode('.png', im); open(sys.argv[1], 'wb').write(b.tobytes())")
    subprocess.run([py, "-I", "-c", kod, str(cel)], check=True, timeout=120)


@pytest.mark.skipif(_python_ocr() is None or ocr.katalog_modeli() is None, reason="brak venvu OCR i modeli Indry")
def test_prawdziwy_odczyt_pliku_z_polskimi_znakami(tmp_path):
    """„faktura_październik.png” w katalogu „Michał Żółć”: Indra (i Tesseract, gdy jest) czytają napis."""
    kat = tmp_path / "Michał Żółć"
    kat.mkdir()
    obraz = kat / "faktura_październik.png"
    _zrob_obraz(_python_ocr(), obraz, "Faktura 2026")
    silniki = ["indra", *(["tesseract"] if shutil.which("tesseract") else [])]
    for silnik in silniki:
        r = subprocess.run([sys.executable, str(OCR), str(obraz), "--silnik", silnik, "--format", "json"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert r.returncode == 0, (silnik, r.stderr)
        w = json.loads(r.stdout)
        tekst = " ".join(ln["tekst"] for s in w["strony"] for ln in s["linie"])
        assert w["silnik"] == silnik and "Faktura" in tekst and "2026" in tekst, (silnik, tekst)


@pytest.mark.skipif(_python_ocr() is None or ocr.katalog_modeli() is None, reason="brak venvu OCR i modeli Indry")
def test_prawdziwy_pdf_z_bajtami_przed_naglowkiem(tmp_path):
    """PDF z „\\r\\n\\r\\n” przed „%PDF-” (np. zapisany z poczty): Indra czyta warstwę tekstu, Tesseract stronę
    wyrenderowaną przez pypdfium2 (w E8 kończyło się to kodem 1: „to nie jest PDF ani obraz”)."""
    from test_konwertuj import pdf_z_tekstem
    kat = tmp_path / "Michał Żółć"
    czysty = pdf_z_tekstem(kat / "czysty.pdf")
    pdf = kat / "faktura_październik.pdf"
    pdf.write_bytes(b"\r\n\r\n" + czysty.read_bytes())
    silniki = ["indra", *(["tesseract"] if shutil.which("tesseract") else [])]
    for silnik in silniki:
        r = subprocess.run([sys.executable, str(OCR), str(pdf), "--silnik", silnik, "--format", "json"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert r.returncode == 0, (silnik, r.stderr)
        tekst = " ".join(ln["tekst"] for s in json.loads(r.stdout)["strony"] for ln in s["linie"])
        assert "Faktura" in tekst and "2026" in tekst, (silnik, tekst)


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

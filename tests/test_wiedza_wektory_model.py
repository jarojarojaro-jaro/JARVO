"""Usługa wektorów z prawdziwym modelem multilingual-e5-small (wiedza/wektory.py, docs/WIEDZA.md §7): sumy plików
modelu zgodne z przypięciem w manifeście, usługa jako osobny proces (2 wątki onnxruntime), nadrabianie wektorów po
starcie i `ocena` silników na zestawie syntetycznym tests/data/wiedza-ocena.json.

Test jest pomijany, gdy nie ma modelu albo Pythona z numpy, onnxruntime i tokenizers. Gdzie szuka:
model: JARVO_TEST_E5_DIR, model instalacji (<dane>/jarvo/models/e5-small), <katalog tymczasowy>/wektory/model;
Python: JARVO_TEST_WEKTORY_PYTHON, venv narzędzi instalacji (narzedzia.json), <katalog tymczasowy>/wektory (venv),
bieżący interpreter.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402
from jarvo import sciezki, srodowisko  # noqa: E402

PLIKI = ("model_quantized.onnx", "tokenizer.json")
WATKI = 2                                    # zasada właściciela: ONNX w testach najwyżej na 2 wątkach


def _model() -> Path | None:
    kandydaci = [os.environ.get("JARVO_TEST_E5_DIR") or ""]
    try:
        kandydaci.append(str(sciezki.uklad().jarvo_dane / "models" / "e5-small"))
    except sciezki.BladUkladu:
        pass
    kandydaci.append(str(Path(tempfile.gettempdir()) / "wektory" / "model"))
    return next((Path(k) for k in kandydaci if k and all((Path(k) / p).is_file() for p in PLIKI)), None)


def _python() -> str | None:
    kandydaci = [os.environ.get("JARVO_TEST_WEKTORY_PYTHON") or ""]
    try:
        kandydaci.append(str((srodowisko.narzedzia(sciezki.uklad()).get("venv-narzedzia") or {}).get("python") or ""))
    except sciezki.BladUkladu:
        pass
    venv = Path(tempfile.gettempdir()) / "wektory"
    kandydaci += [str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")), sys.executable]
    for k in dict.fromkeys(k for k in kandydaci if k and Path(k).is_file()):
        r = subprocess.run([k, "-I", "-B", "-c", "import numpy, onnxruntime, tokenizers"], capture_output=True, timeout=120)
        if r.returncode == 0:
            return k
    return None


@pytest.fixture(scope="module")
def prawdziwy():
    model = _model()
    if model is None:
        pytest.skip("brak plików modelu e5-small (JARVO_TEST_E5_DIR)")
    python = _python()
    if python is None:
        pytest.skip("brak Pythona z numpy, onnxruntime i tokenizers (JARVO_TEST_WEKTORY_PYTHON)")
    return model, python


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def test_sumy_modelu_jak_w_manifescie(prawdziwy):
    model, _python = prawdziwy
    pin = json.loads((REPO / "vendor" / "natywne.lock.json").read_text(encoding="utf-8"))["modele"]["e5-small"]
    pliki = {p["cel"]: p for p in pin["pliki"]}
    for nazwa in PLIKI:
        assert (model / nazwa).stat().st_size == pliki[nazwa]["rozmiar"], nazwa
        assert _sha256(model / nazwa) == pliki[nazwa]["sha256"], nazwa


def test_usluga_z_modelem_nadrabia_wektory_i_ocena_wybiera_silnik(prawdziwy, tmp_path):
    model, python = prawdziwy
    dane = json.loads((REPO / "tests" / "data" / "wiedza-ocena.json").read_text(encoding="utf-8"))
    sk = w.Skarbiec(tmp_path / "knowledge", tmp_path / "state")
    sk.root.mkdir(parents=True)
    for n in dane["notatki"]:
        fm = {"typ": n["typ"], "tagi": [], "utworzono": "2026-11-01", "zmieniono": "2026-11-01", "status": "aktualna",
              "zrodlo": "syntetyczne", **({"agent": n["agent"]} if n.get("agent") else {}),
              **({"aliasy": n["aliasy"]} if n.get("aliasy") else {})}
        sk.zapisz_plik(n["sciezka"], w.sklej(fm, f"# {n['tytul']}\n\n**{n['streszczenie']}**\n\n{n['tresc']}\n"))
    log = open(tmp_path / "wektory.log", "w", encoding="utf-8")
    proc = subprocess.Popen([python, "-I", "-B", "-X", "utf8", str(REPO / "wiedza" / "wektory.py"), "serwuj", "--model", str(model),
                             "--stan", str(sk.stan), "--skarbiec", str(sk.root), "--watki", str(WATKI)],
                            stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "OMP_NUM_THREADS": str(WATKI)})
    ix = w.Indeks(sk)
    try:
        koniec = time.monotonic() + 120
        while time.monotonic() < koniec:                                  # gotowa i nadrobiła wektory skarbca
            k = w.KlientWektorow(sk.stan, 5.0)
            if k.dostepny and k.zdrowie() and ix.db.execute("SELECT count(*) FROM wektory").fetchone()[0] == len(dane["notatki"]):
                break
            assert proc.poll() is None, (tmp_path / "wektory.log").read_text(encoding="utf-8")
            time.sleep(0.5)
        else:
            pytest.fail("usługa nie nadrobiła wektorów w 120 s: " + (tmp_path / "wektory.log").read_text(encoding="utf-8"))
        k = w.KlientWektorow(sk.stan, 5.0)
        assert k.model.startswith("multilingual-e5-small@") and k.zdrowie()["wymiar"] == 384
        v = k.osadz(["query: gdzie leży kod strony?"])[0]
        assert len(v) == 384 and abs(sum(x * x for x in v) - 1.0) < 1e-3
        ix.odswiez()
        assert ix.odswiez_wektory(k)["nowe"] == 0                         # usługa już wszystko osadziła
        wyniki = {}
        for silnik in w.SILNIKI:
            r = w.ocena(ix, dane["zestaw"], wektory=None if silnik == "slowa" else k, silnik=silnik)
            assert r["silniki"] == {silnik: len(dane["zestaw"])}, r["silniki"]
            wyniki[silnik] = r
        n = len(dane["zestaw"])
        assert wyniki["wektory"]["trafione"] >= round(0.85 * n), wyniki["wektory"]["trafione"]
        assert wyniki["wektory"]["trafione"] > wyniki["slowa"]["trafione"]
        domyslny = wyniki[w.SILNIK]                                       # wybór pomiarem: najlepszy na zestawie
        assert all((domyslny["trafione"], domyslny["mrr"]) >= (r["trafione"], r["mrr"]) for r in wyniki.values())
    finally:
        ix.zamknij()
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(30)
        log.close()
    if os.name != "nt":                                                    # łagodne zatrzymanie sprząta plik z tokenem
        assert proc.returncode == 0 and not (sk.stan / w.WEKTORY_STAN).exists()

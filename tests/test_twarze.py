"""twarze.py: dekodowanie wyjść YuNet (bez modelu), siatka próbek i odcinki."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from conftest import load_script

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-wideo" / "scripts"))
T = load_script("profiles/jarvo-wideo/scripts/twarze.py")


def test_decode_yunet_outputs_with_nms_and_padding():
    np = pytest.importorskip("numpy")
    wyj = {}
    for s in (8, 16, 32):
        n = (640 // s) ** 2
        wyj[f"cls_{s}"] = np.zeros((1, n, 1), np.float32)
        wyj[f"obj_{s}"] = np.zeros((1, n, 1), np.float32)
        wyj[f"bbox_{s}"] = np.zeros((1, n, 4), np.float32)
        wyj[f"kps_{s}"] = np.zeros((1, n, 10), np.float32)

    def twarz(s, r, c, wynik, w, h):
        i = r * (640 // s) + c
        wyj[f"cls_{s}"][0, i, 0] = wyj[f"obj_{s}"][0, i, 0] = wynik
        wyj[f"bbox_{s}"][0, i] = [0.5, 0.5, math.log(w / s), math.log(h / s)]
        wyj[f"kps_{s}"][0, i] = [0.25, 0.25] * 5
    twarz(8, 10, 20, 0.9, 32, 40)          # twarz: środek (164, 84), 32×40, wynik √(0,9·0,9) = 0,9
    twarz(8, 10, 21, 0.8, 32, 40)          # ta sama twarz z sąsiedniej komórki: NMS ją zdejmuje
    twarz(16, 30, 5, 0.95, 48, 48)         # środek y = 488 w dopełnieniu (klatka 640×360): odpada
    twarz(32, 2, 2, 0.5, 64, 64)           # za mała pewność
    out = T.dekoduj(wyj, 640, 360)
    assert len(out) == 1
    x0, y0, x1, y1, p = out[0][:5]
    assert (x0, y0, x1, y1) == pytest.approx((148, 64, 180, 104)) and p == pytest.approx(0.9)
    assert out[0][5:7] == pytest.approx([(20 + 0.25) * 8, (10 + 0.25) * 8])


def test_grid_and_segments():
    assert T.siatka(1.2, 3.0) == [1.5, 2.0, 2.5, 3.0]
    assert T.siatka(2.0, 2.4) == [2.0]
    assert T.rozmiar(1920, 1080) == (640, 360) and T.rozmiar(720, 1280) == (360, 640)
    assert T.odcinki_arg("10-35.5, 60-80") == [(10.0, 35.5), (60.0, 80.0)]
    with pytest.raises(SystemExit):
        T.odcinki_arg("5-3")
    assert T.pamiec_path(Path("/x/podcast.mp4")) == Path("/x/podcast.twarze.json")

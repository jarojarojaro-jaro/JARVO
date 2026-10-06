"""kadry.py wzor: rozbiór ruchu filmu-wzoru (starty przejść, siatka, mapa ruchu, klatki kluczowe)."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "profiles/jarvo-wideo/scripts"))
import kadry  # noqa: E402

OSEMKA_128_60 = 60 * 60 / 128 / 2        # ósemka przy 128 BPM w 60 kl./s = 14,0625 klatki


def test_starty_przejsc_z_przerwa():
    r = [0.1, 0.2, 12, 30, 8, 0.3, 0.2, 0.1, 9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 22, 0.2]
    assert kadry.starty_przejsc(r) == [2, 21]                      # start w 8 za blisko poprzedniego (przerwa 12)
    assert kadry.starty_przejsc(r, przerwa=3) == [2, 8, 21]
    assert kadry.starty_przejsc(r, prog=10) == [2, 21]
    assert kadry.starty_przejsc([]) == []


def test_siatka_najwiekszy_krok_i_odstajace():
    jednostki = [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15, 16]          # odcinki coraz krótsze
    dobre = [round(10 + k * OSEMKA_128_60) for k in jednostki]
    starty = sorted(dobre + [47, 120])                               # dwa duże ruchy w ujęciu wzięte za przejście
    s = kadry.siatka(starty, 60.0, bpm_muzyki=128)
    assert abs(s["krok_klatek"] - OSEMKA_128_60) < 0.03 and abs(s["bpm_gdy_osemka"] - 128) < 0.3
    assert s["odstajace"] == [starty.index(47), starty.index(120)]
    assert s["max_blad_klatek"] <= 0.6 and abs(s["t0_klatka"] - 10) < 0.5
    dobre_jedn = [k for i, k in enumerate(s["jednostki"]) if i not in s["odstajace"]]
    assert dobre_jedn == jednostki and s["odcinki_w_krokach"][:2] == [2, 1]
    assert s["krok_w_muzyce"] == "ósemka przy 128 BPM" and s["pewna"]
    bez = kadry.siatka(starty, 60.0, bpm_muzyki=100, proby=20)
    assert bez["krok_w_muzyce"] is None and bez["przypadek"] <= 0.05 and bez["pewna"]   # 14 startów na siatce: nie przypadek
    assert "krok_w_muzyce" not in kadry.siatka(starty, 60.0, proby=5)


def test_siatka_bez_wspolnego_rytmu():
    assert kadry.siatka([10, 40, 70], 30.0) is None                  # za mało startów
    # kilka startów bez rytmu: jakaś siatka zawsze się znajdzie, ale losowe układy dają równie duży krok
    s = kadry.siatka([0, 37, 50, 101, 118, 190], 30.0, proby=20)
    assert s["przypadek"] > 0.05 and s["pewna"] is False
    gesto = kadry.siatka([0, 37, 50, 101, 118, 190, 233, 260, 331, 349, 402, 447, 501, 530, 588, 640], 30.0)
    assert gesto["krok_klatek"] < 8 and gesto["przypadek"] == 1.0 and not gesto["pewna"]   # okno 3 kl. przy kroku ~6


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="bez ffmpeg")
def test_rozbior_na_filmie(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL.Image")
    w, h, fps = 160, 90, 30
    klatki = []
    for i in range(90):                                              # trzy odcinki po 1 s, ostre cięcia
        f = np.zeros((h, w, 3), np.uint8)
        f[...] = [(200, 40, 40), (40, 160, 60), (40, 60, 200)][i // 30]
        if 30 <= i < 60:                                             # w drugim odcinku jedzie kwadrat
            x = 10 + (i - 30) * 3
            f[30:50, x:x + 20] = 255
        klatki.append(f.tobytes())
    film = tmp_path / "wzor.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
                    "-i", "-", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", str(film)],
                   input=b"".join(klatki), check=True)
    out = tmp_path / "rozbior"
    out.mkdir()
    info = {"video": {"width": w, "height": h, "fps": fps}}
    r = kadry.rozbior(film, out, info)
    assert [p["klatka"] for p in r["przejscia"]] == [29, 59] and r["klatek"] == 90
    assert all((out / "przejscia" / f"P0{i}.jpg").exists() for i in (1, 2))
    ruch = [o["ruch_proc"] for o in r["odcinki"]]
    assert ruch[0] == 0 and ruch[1] > 5 and ruch[2] == 0
    assert [o["ref"] is not None for o in r["odcinki"]] == [True] * 3 and r["mapy_ruchu"] and r["kluczowe"]
    assert r["siatka"] is None and r["bez_zmian_proc"] > 50

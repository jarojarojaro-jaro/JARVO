"""qa_wideo.py, kontrola klatek (wzorce za cinetic forensics, MIT): skoki, zamrożenia, duchy, drgania, pasy, szew pętli."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "profiles/jarvo-wideo/scripts"))
import qa_wideo as qa  # noqa: E402

np = pytest.importorskip("numpy")
H, W = 270, 480
RNG = np.random.default_rng(0)
_Y, _X = np.mgrid[0:H, 0:W + 400]
TEKSTURA = (127 + 100 * np.sin(_X / 23.0) * np.cos(_Y / 31.0)).astype(np.uint8)   # gładka jak zdjęcie, nie szum


def panorama(n: int, v: int = 3) -> list:
    return [TEKSTURA[:, i * v:i * v + W].copy() for i in range(n)]


def stale(n: int, kolor: int = 60) -> list:
    return [np.full((H, W), kolor, np.uint8) for _ in range(n)]


def z(klatki):
    return qa.zmiany(iter(klatki))


def test_gladki_ruch_czysty():
    w = z(panorama(40))
    assert qa.skoki(w["d"], w["dr"], w["p"]) == ([], []) and qa.zamrozenia(w["d"]) == [] and w["duchy"] == []
    assert w["n"] == 40 and len(w["d"]) == 40 and len(w["dr"][0]) == 9


def test_zamrozenie_takze_z_szumem_kodera():
    k = panorama(40)
    szum = (RNG.random(k[19].shape) < 0.2) * RNG.choice([-1, 1], k[19].shape)        # koder: ±1 na 20% pikseli
    kopia = np.clip(k[19].astype(np.int16) + szum, 0, 255).astype(np.uint8)
    for klatki in (k[:20] + [k[19]] + k[20:], k[:20] + [kopia] + k[20:]):
        assert qa.zamrozenia(z(klatki)["d"]) == [20]
    assert qa.zamrozenia(z(stale(30))["d"]) == []                      # stojąca scena to nie zacięcie


def test_duch_tak_szybki_element_i_krawedzie_ruchu_nie():
    k = stale(30)
    k[15] = k[15].copy()
    k[15][100:140, 200:240] = 240
    w = z(k)
    assert w["duchy"] == [15]
    assert qa.skoki(w["d"], w["dr"], w["p"], pomin={15, 16})[0] == []
    lot = stale(30)                                                    # klocek przelatuje: co klatkę 60 px dalej
    for i in range(12, 18):
        lot[i] = lot[i].copy()
        lot[i][100:140, 60 * (i - 12):60 * (i - 12) + 40] = 240
    assert z(lot)["duchy"] == []
    cienkie = stale(30)                                                # cienkie linie (krawędzie ruchu ręki)
    cienkie[15] = cienkie[15].copy()
    cienkie[15][::6, 100:300] = 240
    assert z(cienkie)["duchy"] == []
    pan = panorama(30)                                                 # duch na panoramie dalej jest duchem
    pan[15] = pan[15].copy()
    pan[15][100:150, 200:260] = 255
    assert qa.duch(*(x.astype(np.uint8) for x in pan[14:17]))


def test_skok_ciecie_i_rozlozony_ruch():
    k = stale(30)
    for i in range(30):
        x = 20 if i < 15 else 220
        k[i] = k[i].copy()
        k[i][30:60, x:x + 40] = 220
    w = z(k)
    assert qa.skoki(w["d"], w["dr"], w["p"]) == ([(15, None)], [])
    assert qa.skoki(w["d"], w["dr"], w["p"], ciecia=[15]) == ([], [15])        # zadeklarowane cięcie
    c = z(stale(15) + stale(15, 200))
    assert qa.skoki(c["d"], c["dr"], c["p"]) == ([], [15])                     # cały kadr = cięcie
    maly = stale(30)                                                           # mały element w jednym regionie
    for i in range(15, 30):
        maly[i] = maly[i].copy()
        maly[i][10:30, 10:30] = 200
    m = z(maly)
    assert qa.skoki(m["d"], m["dr"], m["p"]) == ([(15, 0)], [])
    wjazd = stale(30)                                                          # zalanie w 4 klatkach: zamierzone
    for i in range(15, 30):
        wjazd[i] = wjazd[i].copy()
        wjazd[i][:, :min(W, 120 * (i - 14))] = 200
    j = z(wjazd)
    assert qa.skoki(j["d"], j["dr"], j["p"])[0] == []


def test_schody_kandydaci_a_gladki_ruch_nie():
    schodki = [TEKSTURA[:, i // 3:i // 3 + W].copy() for i in range(60)]
    kand = qa.schody(z(schodki)["dr"], 30)
    assert {r for _, _, r in kand} == set(range(9)) and min(f for f, _, _ in kand) == 1
    assert max(f for _, f, _ in kand) == 59                            # ostatnie okno sięga końca filmu
    assert qa.schody(z(panorama(60, 1))["dr"], 30) == []


def test_przesuniecie_z_ulamkiem_piksela():
    a = TEKSTURA[:128, :128].astype(np.float32)
    ky, kx = np.fft.fftfreq(128)[:, None], np.fft.fftfreq(128)[None, :]
    for dy, dx in ((1.0, 0.0), (0.0, 2.0), (0.5, -0.5)):
        b = np.real(np.fft.ifft2(np.fft.fft2(a) * np.exp(-2j * np.pi * (ky * dy + kx * dx))))
        wy, wx = qa.przesuniecie(a, b)
        assert wy == pytest.approx(dy, abs=0.2) and wx == pytest.approx(dx, abs=0.2)


def test_pasy_na_stopniach_nie_na_ziarnie_szumie_i_plaskim():
    pion = np.tile(np.round(np.linspace(20, 40, 1080)).astype(np.uint8)[:, None], (1, 1920))
    poziom = np.tile(np.round(np.linspace(100, 108, 1920)).astype(np.uint8), (1080, 1))
    assert qa.pasy_klatki(pion) > 0.9 and qa.pasy_klatki(poziom) > qa.PASY_UDZIAL
    ziarno = np.clip(pion + RNG.integers(-1, 2, pion.shape), 0, 255).astype(np.uint8)
    plamki = np.full((1080, 1920), 90, np.uint8)
    plamki[RNG.random(plamki.shape) < 0.01] = 91
    for k in (ziarno, plamki, np.full((1080, 1920), 90, np.uint8), (RNG.random((1080, 1920)) * 255).astype(np.uint8)):
        assert qa.pasy_klatki(k) == 0.0


def test_szew_petli():
    import math
    petla = [TEKSTURA[:, round(60 + 40 * math.sin(2 * math.pi * i / 60)):][:, :W].copy() for i in range(60)]
    zmiana, prog = qa.szew(z(petla))
    assert zmiana <= prog
    zmiana, prog = qa.szew(z(panorama(60)))
    assert zmiana > prog


def test_ciecia_z_argumentu_i_rozmiar_analizy():
    assert qa.ciecia_z_argumentu("3.2, 7.5-7.8,") == [(3.2, 3.2), (7.5, 7.8)] and qa.ciecia_z_argumentu(None) == []
    assert qa._rozmiar(1920, 1080) == (480, 270) and qa._rozmiar(1080, 1920) == (270, 480)


def test_bez_numpy_stara_kontrola_i_ostrzezenie(monkeypatch, tmp_path):
    info = {"duration": 10.0, "size": 1 << 20, "format_name": "mov",
            "video": {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p"},
            "audio": {"codec": "aac", "sample_rate": 48000, "channels": 2}}
    monkeypatch.setattr(qa.wl, "probe", lambda p: info)
    monkeypatch.setattr(qa, "analyze", lambda p, a: {"czarne": [], "zamrozone": [], "cisze": [], "lufs": -14.0,
                                                     "true_peak": -2.0, "lra": 5.0})
    monkeypatch.setattr(qa, "moov_first", lambda p: True)
    monkeypatch.setattr(qa, "gray_frames", lambda p: ([], 30.0))
    monkeypatch.setattr(qa, "numpy_jest", lambda: False)
    r = qa.check(tmp_path / "f.mp4", None, None, False, None)
    assert any("pominięta: ten Python nie ma numpy" in w for w in r["ostrzezenia"]) and "klatki" not in r["metryki"]
    monkeypatch.setattr(qa, "numpy_jest", lambda: True)
    monkeypatch.setattr(qa, "kontrola_klatek", lambda *a: (["duch: x"], [], {"duchy": 1}))
    r = qa.check(tmp_path / "f.mp4", None, None, False, None, petla=True, ciecia=[(1.0, 1.0)])
    assert not r["ok"] and r["bledy"] == ["duch: x"] and r["metryki"]["klatki"] == {"duchy": 1}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_film_z_powtorzona_klatka_i_zla_petla(tmp_path):
    k = panorama(60)
    k = k[:30] + [k[29]] + k[31:]
    plik = tmp_path / "f.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", "30",
                          "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(plik)], stdin=subprocess.PIPE)
    p.communicate(b"".join(x.tobytes() for x in k))
    bledy, ostrz, m = qa.kontrola_klatek(plik, W, H, 30.0, 2.0, z_kodu=True, petla=True)
    assert m["zamrozenia"] == 1 and any("zamrożona klatka" in b for b in bledy)
    assert any("szew pętli" in b for b in bledy) and m["duchy"] == 0

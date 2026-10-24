"""krytyka.py (Wideograf): martwy takt, szew pętli, ocena rundy."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

S = Path(__file__).resolve().parents[1] / "profiles" / "jarvo-wideo" / "scripts"
sys.path.insert(0, str(S))
import krytyka  # noqa: E402

needs_ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")


def _film(path: Path, expr: str, dur: float = 6) -> Path:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"{expr}{':' if '=' in expr else '='}s=160x120:d={dur}:r=15",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@needs_ff
def test_dead_beat_detected(tmp_path):
    still = _film(tmp_path / "s.mp4", "color=c=red")
    r = krytyka.martwe(still, 2.5)
    assert not r["ok"] and r["martwe"][0]["sek"] >= 2.5
    moving = _film(tmp_path / "m.mp4", "testsrc2")
    assert krytyka.martwe(moving, 2.5)["ok"]


@needs_ff
def test_puls_flags_slow_stretches(tmp_path):
    still = _film(tmp_path / "s.mp4", "color=c=red", 8)
    r = krytyka.puls(still, 3.0, 1.5)
    assert not r["ok"] and r["wolne"] and r["wolne_s"] >= 6
    moving = _film(tmp_path / "m.mp4", "testsrc2", 8)
    assert krytyka.puls(moving, 3.0, 1.5)["ok"]


@needs_ff
def test_fps_filmu(tmp_path):
    # wcześniej zawsze 30 (szukało klucza, którego wideo_lib.probe nie zwraca): pasek i ciecia brały złe klatki
    assert krytyka.eval_fps(_film(tmp_path / "f.mp4", "testsrc2", 1)) == 15


@needs_ff
def test_loop_seam(tmp_path):
    assert krytyka.petla(_film(tmp_path / "c.mp4", "color=c=blue"), None)["ok"]
    assert not krytyka.petla(_film(tmp_path / "t.mp4", "testsrc2"), None)["ok"]


def test_round_scoring(tmp_path):
    k = tmp_path / "k.json"
    k.write_text(json.dumps({"runda": 1, "osie": {o: 8 for o in krytyka.OSIE},
                             "problemy": [{"t": 1.0, "problem": "x", "poprawka": "y"}]}), encoding="utf-8")
    assert krytyka.ocena(k)["ok"]
    k.write_text(json.dumps({"runda": 2, "osie": {**{o: 9 for o in krytyka.OSIE}, "kompozycja": 6}, "problemy": [{"problem": "bez czasu"}]}), encoding="utf-8")
    r = krytyka.ocena(k)
    assert not r["ok"] and r["ponizej_8"] == {"kompozycja": 6} and r["problemy_bez_czasu"] == 1


def test_assety_hex_palette():
    import assety
    assert assety.hex_("rgb(212, 33, 61)") == "#D4213D"
    assert assety.hex_("rgba(0, 0, 0, 0.2)") is None           # półprzezroczyste nakładki nie są kolorem marki
    assert assety.hex_("transparent") is None


def test_maskotka_blink_is_deterministic():
    import maskotka
    assert maskotka.mrug(0.0) == 1.0
    t = maskotka.MRUGNIECIA_CO - 0.7 + 0.07          # środek mrugnięcia
    assert maskotka.mrug(t) < 0.2 and maskotka.mrug(t) == maskotka.mrug(t + maskotka.MRUGNIECIA_CO)


# ---------------------------------------------------------------- ciecia: obraz i liczby każdego cięcia
try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
needs_ff_pil = pytest.mark.skipif(not (shutil.which("ffmpeg") and HAS_PIL), reason="brak ffmpeg albo Pillow")


def test_slowo_przeciete_i_ciasne():
    slowa = [[0.0, 0.4, "Ala"], [0.5, 0.9, "ma"], [1.2, 1.6, "kota"]]
    assert [(s["slowo"], s["rodzaj"]) for s in krytyka.slowa_na_granicy(slowa, 0.7, "koniec klipu")] == [("ma", "przeciete")]
    assert [(s["slowo"], s["rodzaj"]) for s in krytyka.slowa_na_granicy(slowa, 0.92, "koniec klipu")] == [("ma", "ciasno")]
    assert krytyka.slowa_na_granicy(slowa, 1.05, "koniec klipu") == []         # w pauzie, z zapasem: dobre cięcie
    assert [s["rodzaj"] for s in krytyka.slowa_na_granicy(slowa, 1.18, "początek klipu")] == ["ciasno"]


def test_trzask_to_skok_w_gladkiej_fali():
    from array import array
    import math as m

    def fala(skok_fazy: float) -> array:
        sr = krytyka.SR
        return array("h", (int(0.8 * 32767 * m.sin(2 * m.pi * 440 * i / sr + (skok_fazy if i >= sr else 0))) for i in range(2 * sr)))
    assert krytyka.trzask(fala(m.pi / 2), 1.0)["trzask"]                        # fala skacze o ćwierć okresu: klik
    gladka = krytyka.trzask(fala(0), 1.0)
    assert not gladka["trzask"] and gladka["krotnosc"] < 1.5
    cisza = array("h", [0] * krytyka.SR * 2)
    cisza[krytyka.SR] = 4000                                                    # pojedynczy kolec w ciszy też słychać
    assert krytyka.trzask(cisza, 1.0)["trzask"]


def test_ciecia_z_projektu(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    for f in (a, b):
        f.write_bytes(b"x")
    (tmp_path / "a.mowa.json").write_text(json.dumps({"words": [[1.0, 1.5, "dzień"], [3.9, 4.2, "dobry"]]}), encoding="utf-8")
    proj = {"canvas": {"w": 320, "h": 240, "fps": 25},
            "clips": [{"id": "c1", "src": str(a), "in": 0, "out": 2}, {"id": "c2", "src": str(a), "in": 2, "out": 4},
                      {"id": "c3", "src": str(b), "in": 0, "out": 2, "transition": {"type": "fade", "dur": 0.4}},
                      {"id": "c4", "src": str(a), "in": 5, "out": 6}]}
    lista, slowa = krytyka.ciecia_projektu(proj)
    # c1 → c2 to tylko podział (ten sam materiał gra dalej): nie jest cięciem
    assert [(c["t"], c["przed"], c["za"]) for c in lista] == [(4.0, "c2", "c3"), (6.0, "c3", "c4")]
    assert [(s["slowo"], s["rodzaj"], s["strona"]) for s in lista[0]["slowa"]] == [("dobry", "przeciete", "koniec klipu")]
    assert lista[1]["przejscie"] == {"type": "fade", "d": 0.4} and lista[1]["slowa"] == []
    assert [w[2] for w in slowa] == ["dzień", "dobry"] and slowa[1][:2] == [3.9, 4.0]   # przecięte słowo widać do cięcia


def _sklej(tmp_path: Path, nazwa: str, wideo: str, kawalki: list[tuple[float, float]], audio: str) -> Path:
    """Film z kawałków jednego źródła (twarde cięcia bez zaniku), dźwięk w PCM, żeby kodek nie wygładzał skoku."""
    src = tmp_path / f"{nazwa}-src.mov"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", wideo, "-f", "lavfi", "-i", audio,
                    "-shortest", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(src)], check=True)
    fc = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}];"
                 for i, (a, b) in enumerate(kawalki))
    fc += "".join(f"[v{i}][a{i}]" for i in range(len(kawalki))) + f"concat=n={len(kawalki)}:v=1:a=1[v][a]"
    out = tmp_path / f"{nazwa}.mov"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(out)], check=True)
    return out


@needs_ff_pil
def test_obraz_ciecia_trzask_i_zmiana_ujecia(tmp_path):
    from PIL import Image
    film = _sklej(tmp_path, "f", "testsrc2=s=320x180:r=25:d=4", [(0, 1), (2.52, 3.52)],
                  "aevalsrc=0.8*sin(2*PI*440*t):s=48000:d=4")
    r = krytyka.ciecia(film, tmp_path / "c", czasy=[1.0])
    c = r["ciecia"][0]
    assert not r["ok"] and c["dzwiek"]["trzask"] and any("trzask" in p for p in c["problemy"])
    assert Image.open(c["obraz"]).size[0] > 1300                     # 8 klatek + fala + słowa na jednym obrazie
    # bez --czasy i projektu: cięcie z obrazu (testsrc2 przeskakuje o 1,5 s, filtr scene je widzi)
    auto = krytyka.ciecia(film, tmp_path / "a", prog_sceny=0.05)
    assert any(abs(x["t"] - 1.0) < 0.05 for x in auto["ciecia"])


@needs_ff_pil
def test_przeskok_ten_sam_kadr(tmp_path):
    # to samo ujęcie (szare tło, kwadrat jedzie w prawo), wycięta sekunda: kwadrat przeskakuje, tło stoi
    wideo = "color=c=gray:s=160x120:r=25:d=4[t];color=c=white:s=20x20:r=25:d=4[k];[t][k]overlay=x='10+t*30':y=50"
    film = _sklej(tmp_path, "p", wideo, [(0, 1), (2, 3)], "anullsrc=r=48000:cl=mono")
    c = krytyka.ciecia(film, tmp_path / "c", czasy=[1.0])["ciecia"][0]
    assert c["rodzaj"] == "przeskok" and any("przybliżenie" in u for u in c["uwagi"]), c
    assert not c["problemy"]                                        # przeskok to uwaga, nie błąd


def test_tempo_przestoj_to_ani_mowy_ani_nowej_rzeczy():
    fps = 10.0
    d = [0.2] * 100                                  # 10 s spokojnego obrazu
    for t in (1.0, 3.0, 5.0, 7.0, 9.0):              # nowa rzecz co 2 s
        d[int(t * fps) - 1] = 5.0
    r = krytyka.tempo_z(d, fps, [])
    assert r["ok"] and not [p for p in r["przestoje"] if p["poziom"] == "błąd"]
    d2 = [0.2] * 100
    d2[9] = 5.0                                      # jedna rzecz w 1. sekundzie, potem nic
    r = krytyka.tempo_z(d2, fps, [(1.0, 4.0)])       # lektor mówi tylko 1–4 s
    assert not r["ok"]
    assert r["przestoje"][0]["od"] == 4.1 and r["przestoje"][0]["poziom"] == "błąd"
    assert any(l["poziom"] == "błąd" for l in r["luki_obrazu"])          # 9 s bez nowej rzeczy
    # pod mową spokojny obraz to nie przestój, ale luka obrazu > 6 s dalej jest błędem
    r = krytyka.tempo_z(d2, fps, [(0.0, 10.0)])
    assert not r["przestoje"] and not r["ok"]


def test_tempo_plansza_koncowa_do_2_s_jest_ok():
    fps = 10.0
    d = [0.2] * 60
    for t in (0.5, 2.0, 3.5):
        d[int(t * fps) - 1] = 5.0
    r = krytyka.tempo_z(d, fps, [(0.0, 4.2)])        # od 4,2 s do końca (6 s) spokojna plansza 1,8 s
    assert r["ok"] and not r["przestoje"] and not r["luki_obrazu"]
    assert r["nowe_rzeczy_na_10s"] == 5.0


def test_mowa_z_srt_i_json(tmp_path):
    srt = tmp_path / "f.srt"
    srt.write_text("1\n00:00:00,800 --> 00:00:04,403\nKażdy worek.\n\n2\n00:00:04,500 --> 00:00:06,000\nDalej.\n",
                   encoding="utf-8")
    assert krytyka.mowa_z_pliku(srt) == [(0.8, 6.0)]               # przerwa 0,1 s to dalej mowa
    js = tmp_path / "m.json"
    js.write_text(json.dumps({"slowa": [[0.0, 0.4, "Ala"], [0.5, 0.9, "ma"], [2.0, 2.5, "kota"]]}), encoding="utf-8")
    assert krytyka.mowa_z_pliku(js) == [(0.0, 0.9), (2.0, 2.5)]
    js.write_text(json.dumps([{"start": 1, "end": 2}, {"od": 3, "do": 4}]), encoding="utf-8")
    assert krytyka.mowa_z_pliku(js) == [(1.0, 2.0), (3.0, 4.0)]


@needs_ff
def test_tempo_na_filmie_i_srt_obok(tmp_path):
    still = _film(tmp_path / "s.mp4", "color=c=red", 7)            # 7 s jednej planszy
    r = krytyka.tempo(still)
    assert not r["ok"] and r["mowa"].startswith("brak") and r["przestoje"][0]["poziom"] == "błąd"
    (tmp_path / "s.srt").write_text("1\n00:00:00,000 --> 00:00:07,000\nCały czas mówię.\n", encoding="utf-8")
    r = krytyka.tempo(still)                                        # SRT obok filmu bierze sam
    assert r["mowa"].endswith("s.srt") and not r["przestoje"]
    assert not r["ok"] and r["luki_obrazu"][0]["poziom"] == "błąd"  # lektor mówi, ale 7 s nic nowego

"""Dźwięk w edytorze HQ: narastanie i wyciszanie (fadeIn / fadeOut) klipu i audio oraz pasy audio na osi.
Podgląd (43-dzwiek.js zanikGain) i eksport (afade curve=tri w edytor.build_command) mają tę samą głośność; test mierzy ją
w prawdziwym pliku z ffmpeg. Wideograf: projekt.py dodaj-audio --narastanie/--wyciszanie i dzwiek."""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_dzwiek_test")
JS = (REPO / "hq" / "web" / "src" / "43-dzwiek.js").read_text(encoding="utf-8")
HAS_NODE = bool(shutil.which("node"))
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def node(prog: str):
    r = subprocess.run(["node", "-e", JS + "\n" + prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_zanik_i_pasy_w_podgladzie():
    w = node("""console.log(JSON.stringify({
      g: [[-0.1, 4, 1, 0], [0, 4, 1, 0], [0.25, 4, 1, 0], [2, 4, 1, 2], [3.5, 4, 1, 2], [4.2, 4, 0, 1], [4.2, 4, 0, 0], [1, 4, 30, 0]]
        .map(([r, d, fi, fo]) => +zanikGain(r, d, fi, fo).toFixed(4)),
      max: [zanikMax(4), zanikMax(40)],
      pasy: pasyAudio([{ id: 'm', start: 0, in: 0, out: 10 }, { id: 'l', start: 2, in: 0, out: 3 }, { id: 'e1', start: 3, in: 0, out: 1 },
                       { id: 'e2', start: 5, in: 0, out: 1 }, { id: 'e3', start: 10, in: 0, out: 1 }]),
      pusto: pasyAudio([]) }));""")
    # przed narastaniem cisza, w połowie narastania 0,25, bez zaniku pełna głośność; zanik najwyżej połowa elementu
    assert w["g"] == [0, 0, 0.25, 1, 0.25, 0, 1, 0.5]
    assert w["max"] == [2, 10]
    assert w["pasy"] == {"pas": {"m": 0, "l": 1, "e1": 2, "e2": 1, "e3": 0}, "n": 3}
    assert w["pusto"] == {"pas": {}, "n": 1}


def test_normalize_zanik_w_granicach(tmp_path):
    for n in ("a.mp4", "m.mp3"):
        (tmp_path / n).write_bytes(b"x")
    p = ed.normalize({"clips": [{"src": str(tmp_path / "a.mp4"), "in": 0, "out": 4, "speed": 2, "fadeIn": 5, "fadeOut": 0.5},
                                {"src": str(tmp_path / "a.mp4"), "in": 0, "out": 4}],
                      "audio": [{"src": str(tmp_path / "m.mp3"), "start": 3, "in": 0, "out": 60, "fadeIn": 1, "fadeOut": 20}]},
                     lambda s: Path(s) if Path(s).is_file() else None)
    a, b = p["clips"]
    assert (a["fade_in"], a["fade_out"]) == (1.0, 0.5)              # klip 2 s na osi: narastanie najwyżej 1 s
    assert "fade_in" not in b
    m = p["audio"][0]
    assert m["out"] == 3.0 and (m["fade_in"], m["fade_out"]) == (1.0, 1.5)   # muzyka ucięta do końca filmu (6 s)
    cmd = " ".join(ed.build_command(p, {str(tmp_path / "a.mp4"): True}, [], tmp_path / "o.mp4"))
    assert "afade=t=in:st=0:d=1:curve=tri,afade=t=out:st=1.5:d=0.5:curve=tri[a0]" in cmd
    assert "afade=t=in:st=0:d=1:curve=tri,afade=t=out:st=1.5:d=1.5:curve=tri,adelay=3000|3000[m0]" in cmd
    assert len(ed.normalize({"clips": [{"src": str(tmp_path / "a.mp4")}], "audio": [{"src": str(tmp_path / "m.mp3"), "out": 1}] * 40},
                            lambda s: Path(s) if Path(s).is_file() else None)["audio"]) == ed.MAX_AUDIO == 32


def _rms(film: Path, okna: list[tuple[float, float]]) -> list[float]:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(film), "-map", "0:a", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = struct.unpack(f"<{len(raw) // 4}f", raw)
    return [math.sqrt(sum(v * v for v in x[int(a * 8000):int(b * 8000)]) / max(1, int(b * 8000) - int(a * 8000))) for a, b in okna]


@pytest.mark.skipif(not (HAS_FF and HAS_NODE), reason="brak ffmpeg albo node")
def test_eksport_ma_te_sama_glosnosc_co_podglad(tmp_path):
    """Muzyka 4 s z narastaniem 1 s i wyciszaniem 2 s pod wyciszonym klipem: głośność w pliku = zanikGain z podglądu."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=4:r=25",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4", "-shortest", str(tmp_path / "v.mp4")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=500:d=6", "-ac", "2", str(tmp_path / "m.wav")], check=True)
    p = ed.normalize({"canvas": {"w": 64, "h": 64, "fps": 25}, "clips": [{"src": str(tmp_path / "v.mp4"), "in": 0, "out": 4, "muted": True}],
                      "audio": [{"src": str(tmp_path / "m.wav"), "start": 0, "in": 0, "out": 6, "volume": 0.5, "fadeIn": 1, "fadeOut": 2}]},
                     lambda s: Path(s) if Path(s).is_file() else None)
    out = tmp_path / "o.mp4"
    r = subprocess.run(ed.build_command(p, {}, [], out), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    chwile = [0.25, 0.5, 0.75, 1.5, 2.5, 3.0, 3.5]
    okna = [(t - 0.02, t + 0.02) for t in chwile]
    pelna = _rms(out, [(1.2, 1.8)])[0]
    zmierzone = [x / pelna for x in _rms(out, okna)]
    oczekiwane = node(f"console.log(JSON.stringify({json.dumps(chwile)}.map((t) => zanikGain(t, 4, 1, 2))))")
    assert pelna == pytest.approx(0.125 * 0.5 / math.sqrt(2), rel=0.1)   # sine w ffmpeg ma amplitudę 1/8, × głośność 0,5
    for t, z, o in zip(chwile, zmierzone, oczekiwane):
        assert z == pytest.approx(o, abs=0.06), (t, z, o)


@pytest.fixture
def pr(tmp_path, monkeypatch):
    mod = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_dzwiek_test")
    stan = {"p": {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "texts": [],
                  "clips": [{"id": "c", "src": "a.mp4", "kind": "video", "in": 0, "out": 6, "speed": 1}],
                  "audio": [{"id": "m", "src": "m.mp3", "start": 2, "in": 0, "out": 30, "volume": 1}]}}
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    monkeypatch.setattr(mod, "load", lambda f: json.loads(json.dumps(stan["p"])))
    monkeypatch.setattr(mod, "save", lambda f, p: stan.update(p=json.loads(json.dumps(p))))
    mod.stan, mod.film = stan, str(film)
    return mod


def test_projekt_dzwiek(pr, capsys):
    assert pr.main(["dzwiek", pr.film, "m", "--glosnosc", "0.3", "--narastanie", "1", "--wyciszanie", "5"]) == 0
    assert pr.stan["p"]["audio"][0] == {"id": "m", "src": "m.mp3", "start": 2, "in": 0, "out": 30, "volume": 0.3, "fadeIn": 1.0, "fadeOut": 2.0}
    assert "wyciszanie 2.0 s" in capsys.readouterr().out          # muzyka gra 4 s do końca filmu: najwyżej połowa
    assert pr.main(["dzwiek", pr.film, "m", "--narastanie", "0"]) == 0
    assert "fadeIn" not in pr.stan["p"]["audio"][0] and pr.stan["p"]["audio"][0]["fadeOut"] == 2.0
    assert pr.main(["dzwiek", pr.film, "c", "--wycisz", "--wyciszanie", "0.5"]) == 0
    c = pr.stan["p"]["clips"][0]
    assert c["muted"] is True and c["fadeOut"] == 0.5
    with pytest.raises(SystemExit, match="dotyczy klipu"):
        pr.main(["dzwiek", pr.film, "m", "--wycisz"])
    assert pr.main(["pokaz", pr.film]) == 0
    assert "wyciszanie 0.5 s" in capsys.readouterr().out

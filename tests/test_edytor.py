"""Edytor filmów HQ: walidacja projektu, polecenie ffmpeg i prawdziwy eksport (gdy jest ffmpeg)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("edytor", ROOT / "hq" / "plugin" / "edytor.py")
ed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ed)

HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _files(tmp: Path) -> dict[str, Path]:
    out = {}
    for n in ("a.mp4", "b.webm", "m.mp3", "i.png", "x.txt"):
        (tmp / n).write_bytes(b"x")
        out[n] = tmp / n
    return out


def _resolver(tmp: Path):
    def resolve(raw: str):
        p = Path(raw)
        return p if p.is_file() and tmp in p.parents else None
    return resolve


def test_normalize_limits_and_defaults(tmp_path):
    f = _files(tmp_path)
    p = ed.normalize({"canvas": {"w": 1081, "h": 1919, "fps": 29},
                      "clips": [{"src": str(f["a.mp4"]), "in": 1, "out": 3, "speed": 9, "volume": 5},
                                {"src": str(f["i.png"]), "in": 0, "out": 2, "speed": 3}],
                      "texts": [{"start": 0.5, "end": 99}, {"start": 1, "end": 1.01}],
                      "audio": [{"src": str(f["m.mp3"]), "start": 1, "in": 0, "out": 60, "volume": 0.5}]},
                     _resolver(tmp_path))
    assert p["canvas"] == {"w": 1080, "h": 1918, "fps": 30}
    a, img = p["clips"]
    assert a["speed"] == 4 and a["volume"] == 2          # przycięte do dozwolonych zakresów
    assert img["kind"] == "image" and img["speed"] == 1.0
    assert p["duration"] == pytest.approx(2 / 4 + 2)
    assert p["texts"] == [{"start": 0.5, "end": p["duration"], "i": 0}]   # za krótki napis odpada (i = numer w projekcie)
    assert p["audio"][0]["out"] == pytest.approx(p["duration"] - 1)   # muzyka nie wychodzi poza film


@pytest.mark.parametrize("clips, msg", [
    ([], "pusta"),
    ([{"src": "/etc/passwd", "in": 0, "out": 1}], "spoza"),
    ([{"src": "TXT", "in": 0, "out": 1}], "spoza"),
    ([{"src": "A", "in": 2, "out": 2.01}], "krótszy"),
])
def test_normalize_rejects(tmp_path, clips, msg):
    f = _files(tmp_path)
    for c in clips:
        c["src"] = {"TXT": str(f["x.txt"]), "A": str(f["a.mp4"])}.get(c["src"], c["src"])
    with pytest.raises(ed.ProjectError, match=msg):
        ed.normalize({"clips": clips}, _resolver(tmp_path))


def test_atempo_chain():
    assert ed._atempo(1) == ""
    assert ed._atempo(4) == "atempo=2.0,atempo=2.000000"
    assert ed._atempo(0.25) == "atempo=0.5,atempo=0.500000"


def test_command_is_argument_list(tmp_path):
    f = _files(tmp_path)
    p = ed.normalize({"clips": [{"src": str(f["a.mp4"]), "in": 0, "out": 2, "muted": True},
                                {"src": str(f["b.webm"]), "in": 1, "out": 3, "speed": 2, "fit": "cover"}],
                      "texts": [{"start": 0, "end": 1}],
                      "audio": [{"src": str(f["m.mp3"]), "start": 0.5, "in": 0, "out": 9}]}, _resolver(tmp_path))
    png = tmp_path / "t.png"
    cmd = ed.build_command(p, {str(f["b.webm"]): True}, [png], tmp_path / "o.mp4")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in graph and "anullsrc" in graph        # wyciszony klip = cisza
    assert "crop=" in graph and "atempo=2" in graph
    assert "between(t,0,1)" in graph and "amix=inputs=2" in graph and "adelay=500|500" in graph
    assert cmd[-1] == str(tmp_path / "o.mp4") and str(png) in cmd


def test_export_name_never_overwrites(tmp_path):
    v = tmp_path / "film.mp4"
    v.write_bytes(b"x")
    assert ed.export_name(v).name == "film-edycja.mp4"
    (tmp_path / "film-edycja.mp4").write_bytes(b"x")
    assert ed.export_name(v).name == "film-edycja-2.mp4"
    assert ed.export_name(tmp_path / "film-edycja.mp4").name == "film-edycja-2.mp4"


def test_parse_progress():
    assert ed.parse_progress("frame=10\nout_time_us=2500000\nprogress=continue\n") == 2.5
    assert ed.parse_progress("out_time_us=N/A\n") is None


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_real_export(tmp_path):
    run = lambda *a: subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)
    run("-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=3", "-f", "lavfi", "-i", "sine=d=3", "-shortest",
        "-pix_fmt", "yuv420p", str(tmp_path / "a.mp4"))
    run("-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1", str(tmp_path / "i.png"))
    run("-f", "lavfi", "-i", "color=c=white@0.5:s=360x640,format=rgba", "-frames:v", "1", str(tmp_path / "t.png"))
    run("-f", "lavfi", "-i", "sine=f=220:d=5", str(tmp_path / "m.mp3"))
    p = ed.normalize({"canvas": {"w": 360, "h": 640, "fps": 25},
                      "clips": [{"src": str(tmp_path / "a.mp4"), "in": 0.5, "out": 2.5, "speed": 2},
                                {"src": str(tmp_path / "i.png"), "in": 0, "out": 1, "fit": "cover"}],
                      "texts": [{"start": 0.2, "end": 1.5}],
                      "audio": [{"src": str(tmp_path / "m.mp3"), "start": 0, "in": 0, "out": 5, "volume": 0.3}]},
                     _resolver(tmp_path))
    out = tmp_path / "o.mp4"
    r = subprocess.run(ed.build_command(p, {str(tmp_path / "a.mp4"): True}, [tmp_path / "t.png"], out),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    info = ed.probe(out)
    assert (info["w"], info["h"], info["audio"]) == (360, 640, True)
    assert info["duration"] == pytest.approx(2.0, abs=0.1)


def test_parse_srt():
    srt = "﻿1\r\n00:00:01,000 --> 00:00:02,500\r\n<i>Cześć</i> wszystkim\r\n\r\n2\n00:00:03.5 --> 00:00:03,000\nzły czas\n\n3\n00:01:00,000 --> 00:01:02,000\nDwie\nlinie\n"
    assert ed.parse_srt(srt) == [{"start": 1.0, "end": 2.5, "text": "Cześć wszystkim"},
                                 {"start": 60.0, "end": 62.0, "text": "Dwie\nlinie"}]


def test_auto_srt_next_to_source(tmp_path):
    assert ed.auto_srt_path(tmp_path / "film.mp4") == tmp_path / "film.auto.srt"


def test_stt_bin_from_env(tmp_path, monkeypatch):
    fake = tmp_path / "stt"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("JARVO_STT_BIN", str(fake))
    assert ed.stt_bin() == str(fake)
    monkeypatch.setenv("JARVO_STT_BIN", str(tmp_path / "brak"))
    assert ed.stt_bin() is None


def test_fillers():
    assert all(ed.is_filler(w) for w in ("yyy", "Yyy,", "eee", "mmm", "hmm", "ehm", "uhm"))
    assert not any(ed.is_filler(w) for w in ("ale", "tak", "my", "e-mail", "mama"))


def test_parse_silences_with_trailing_silence():
    log = ("[silencedetect @ 0x1] silence_start: 2.001\n[silencedetect @ 0x1] silence_end: 3.5 | silence_duration: 1.49\n"
           "[silencedetect @ 0x1] silence_start: -0.01\n[silencedetect @ 0x1] silence_end: 0.02 | silence_duration: 0.03\n"
           "[silencedetect @ 0x1] silence_start: 9.0\n")
    assert ed.parse_silences(log, 10.0) == [[2.001, 3.5], [9.0, 10.0]]   # zbyt krótka cisza odpada


def test_lines_from_words_break_on_pause_and_sentence_skip_fillers():
    words = [[0, 0.3, "Cześć,"], [0.3, 0.5, "yyy"], [0.6, 0.9, "tu"], [0.9, 1.2, "Jarvo."], [1.3, 1.5, "Dalej"], [2.5, 2.9, "idziemy"]]
    assert [x["text"] for x in ed.lines_from_words(words)] == ["Cześć, tu Jarvo.", "Dalej", "idziemy"]
    data = ed.speech_data(words, [[1.5, 2.5]], 3.0)
    assert data["fillers"] == [1] and data["silences"] == [[1.5, 2.5]]


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_real_proxy_and_silences(tmp_path):
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=4",
                    "-f", "lavfi", "-i", "sine=d=4,volume='if(between(t,1,2.5),0,1)':eval=frame", "-shortest",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    out = tmp_path / "p.webm"
    r = subprocess.run(ed.proxy_command(src, out), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    info = ed.probe(out)
    assert info["vcodec"] == "vp9" and info["h"] == 360
    log = subprocess.run(["ffmpeg", "-nostdin", "-i", str(src), "-vn", "-af", f"silencedetect=noise={ed.SILENCE_DB}dB:d={ed.SILENCE_MIN}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    (a, b), = ed.parse_silences(log, 4.0)
    assert a == pytest.approx(1.0, abs=0.05) and b == pytest.approx(2.5, abs=0.05)


def test_cover_focus_and_zoom_filter(tmp_path):
    f = _files(tmp_path)
    base = {"src": str(f["a.mp4"]), "in": 0, "out": 2, "fit": "cover"}
    p = ed.normalize({"canvas": {"w": 1080, "h": 1920},
                      "clips": [base, {**base, "fx": 0.2, "fy": 0.9, "zoom": 1.5}, {**base, "fx": 7, "zoom": 0.1}]},
                     _resolver(tmp_path))
    c0, c1, c2 = p["clips"]
    assert (c0["fx"], c0["fy"], c0["zoom"]) == (0.5, 0.5, 1)          # stare projekty: kadr jak dotąd (środek)
    assert (c2["fx"], c2["zoom"]) == (1, 1)                            # wartości spoza zakresu przycięte
    assert ed.cover_filter(1080, 1920, c0) == ("scale=1080:1920:force_original_aspect_ratio=increase,"
                                               "crop=1080:1920:(iw-1080)*0.5:(ih-1920)*0.5")
    assert ed.cover_filter(1080, 1920, c1) == ("scale=1620:2880:force_original_aspect_ratio=increase,"
                                               "crop=1080:1920:(iw-1080)*0.2:(ih-1920)*0.9")


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_real_export_focus_picks_side_of_frame(tmp_path):
    """Poziome źródło: lewa połowa czerwona, prawa niebieska. Pion 9:16 z fx=0 widzi czerwień, z fx=1 błękit."""
    src = tmp_path / "szer.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=red:s=320x180:d=1",
                    "-f", "lavfi", "-i", "color=blue:s=320x180:d=1", "-filter_complex",
                    "[0:v]crop=160:180:0:0[l];[1:v]crop=160:180:0:0[r];[l][r]hstack,format=yuv420p",
                    str(src)], check=True)
    colors = {}
    for fx in (0.0, 1.0):
        p = ed.normalize({"canvas": {"w": 90, "h": 160, "fps": 25},
                          "clips": [{"src": str(src), "in": 0, "out": 0.5, "fit": "cover", "fx": fx}]}, _resolver(tmp_path))
        out = tmp_path / f"o{fx}.mp4"
        r = subprocess.run(ed.build_command(p, {}, [], out), capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        rgb = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-frames:v", "1", "-vf", "scale=1:1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        colors[fx] = tuple(rgb[:3])
    assert colors[0.0][0] > 150 and colors[0.0][2] < 90       # czerwony
    assert colors[1.0][2] > 150 and colors[1.0][0] < 90       # niebieski


# ------------------------------------------------------------------ napisy karaoke

KAR = {"start": 10.0, "end": 12.0, "text": "Trzy błędy w cenach", "hl": "#FFE14D",
       "words": [[0, 0.4, "Trzy"], [0.5, 0.9, "błędy"], [1.0, 1.1, "w"], [1.2, 1.9, "cenach"]]}


def test_karaoke_rule_matches_editor():
    assert ed.karaoke_words(KAR) == ["Trzy", "błędy", "w", "cenach"]
    assert ed.karaoke_words({**KAR, "text": "Trzy błędy w cenach!"}) == ["Trzy", "błędy", "w", "cenach!"]   # literówka
    assert ed.karaoke_words({**KAR, "text": "Dwa błędy"}) is None          # inna liczba słów: zwykły napis
    assert ed.karaoke_words({**KAR, "hl": ""}) is None                    # karaoke wyłączone


def test_karaoke_windows_cover_the_caption():
    w = ed.karaoke_windows(KAR, 10.0, 12.0)
    assert w == [(10.0, 10.5, 0), (10.5, 11.0, 1), (11.0, 11.2, 2), (11.2, 12.0, 3)]
    # czasy spoza napisu przycięte, malejące traktowane jak rosnące
    odd = {**KAR, "words": [[0, 1, "a"], [5, 6, "b"], [0.2, 0.3, "c"], [9, 9, "d"]], "text": "a b c d"}
    assert ed.karaoke_windows(odd, 10.0, 12.0) == [(10.0, 12.0, 0)]


def test_karaoke_layer_and_command(tmp_path):
    f = _files(tmp_path)
    p = ed.normalize({"canvas": {"w": 1080, "h": 1920},
                      "clips": [{"src": str(f["a.mp4"]), "in": 0, "out": 20}],
                      "texts": [{"start": 1, "end": 3, "text": "tytuł"}, KAR]}, _resolver(tmp_path))
    assert "kara" not in p["texts"][0] and len(p["texts"][1]["kara"]) == 4
    words = {1: [tmp_path / f"w{j}.png" for j in range(4)]}
    blank = ed.blank_png(tmp_path / "pusty.png", 8, 4)
    assert blank.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") and b"IHDR" in blank.read_bytes()
    lst = ed.karaoke_concat(p, words, blank, tmp_path / "k.ffconcat").read_text(encoding="utf-8").splitlines()
    assert lst[0] == "ffconcat version 1.0"
    assert lst[1:5] == [f"file '{blank}'", "duration 10.000", f"file '{words[1][0]}'", "duration 0.500"]
    assert lst[-3:] == [f"file '{blank}'", "duration 8.000", f"file '{blank}'"]   # przerwa do końca + powtórka
    cmd = ed.build_command(p, {}, [tmp_path / "t0.png", tmp_path / "t1.png"], tmp_path / "o.mp4",
                           karaoke=tmp_path / "k.ffconcat")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert str(tmp_path / "t0.png") in cmd and str(tmp_path / "t1.png") not in cmd   # karaoke nie jako zwykły napis
    assert "concat" in cmd and "eof_action=pass" in graph


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_real_export_karaoke_layer(tmp_path):
    """Dwa słowa = dwa obrazy (czerwony, niebieski). W czasie słowa 1 kadr jest czerwony, słowa 2 niebieski,
    po napisie widać film (zielony): warstwa idzie jednym wejściem ffmpeg."""
    run = lambda *a: subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)
    run("-f", "lavfi", "-i", "color=green:s=64x64:r=25:d=3", "-pix_fmt", "yuv420p", str(tmp_path / "g.mp4"))
    for name, col in (("r", "red"), ("b", "blue")):
        run("-f", "lavfi", "-i", f"color={col}:s=64x64", "-frames:v", "1", str(tmp_path / f"{name}.png"))
    t = {"start": 0.0, "end": 2.0, "text": "raz dwa", "hl": "#ff0", "words": [[0, 0.9, "raz"], [1.0, 1.9, "dwa"]]}
    p = ed.normalize({"canvas": {"w": 64, "h": 64, "fps": 25}, "clips": [{"src": str(tmp_path / "g.mp4"), "in": 0, "out": 3}],
                      "texts": [t]}, _resolver(tmp_path))
    layer = ed.karaoke_concat(p, {0: [tmp_path / "r.png", tmp_path / "b.png"]},
                              ed.blank_png(tmp_path / "pusty.png", 64, 64), tmp_path / "k.ffconcat")
    out = tmp_path / "o.mp4"
    r = subprocess.run(ed.build_command(p, {}, [tmp_path / "r.png"], out, karaoke=layer), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    def rgb(ts):
        return tuple(subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(ts), "-i", str(out), "-frames:v", "1",
                                     "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    capture_output=True, check=True).stdout[:3])
    red, blue, green = rgb(0.5), rgb(1.5), rgb(2.5)
    assert red[0] > 150 and red[2] < 90
    assert blue[2] > 150 and blue[0] < 90
    assert green[1] > 90 and green[0] < 90 and green[2] < 90


def test_karaoke_js_rule_same_as_python(tmp_path):
    """karaokeWords / karaokeIndex z 44-napisy.js dają te same słowa i okna co edytor.py."""
    if not shutil.which("node"):
        pytest.skip("brak node")
    js = (Path(__file__).resolve().parents[1] / "hq" / "web" / "src" / "44-napisy.js").read_text(encoding="utf-8")
    prog = js + f"""
const t = {json.dumps(KAR)};
console.log(JSON.stringify({{w: karaokeWords(t).map((x) => x[2]),
  idx: [9.9, 10.2, 10.5, 10.95, 11.15, 11.5, 13].map((s) => karaokeIndex(t, s)),
  off: karaokeWords({{...t, text: "Dwa błędy"}}), plain: karaokeIndex({{...t, hl: ""}}, 11)}}));"""
    out = json.loads(subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert out["w"] == ed.karaoke_words(KAR)
    assert out["idx"] == [0, 0, 1, 1, 2, 3, 3]
    assert out["off"] is None and out["plain"] == -1

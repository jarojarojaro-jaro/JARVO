"""Wideograf: projekt.py pracuje na tym samym projekcie co edytor HQ (<film>.edycja.json)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("projekt", ROOT / "profiles" / "jarvo-wideo" / "scripts" / "projekt.py")
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
ed = pr.ed

HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
pytestmark = pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")


@pytest.fixture()
def film(tmp_path):
    f = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=4",
                    "-f", "lavfi", "-i", "sine=d=4", "-shortest", "-pix_fmt", "yuv420p", str(f)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=600:d=2", str(tmp_path / "lektor.wav")], check=True)
    return f


def proj(f):
    return json.loads(ed.project_path(f).read_text(encoding="utf-8"))


def test_new_project_from_film_and_add_items(film, capsys):
    assert pr.main(["dodaj-audio", str(film), str(film.with_name("lektor.wav")), "--start", "0.5", "--glosnosc", "0.8", "--wycisz-film"]) == 0
    assert pr.main(["dodaj-tekst", str(film), "Cześć", "--start", "0", "--koniec", "9", "--styl", "box"]) == 0
    p = proj(film)
    assert p["canvas"] == {"w": 320, "h": 240, "fps": 25} and p["clips"][0]["muted"] is True
    assert p["audio"][0]["start"] == 0.5 and p["audio"][0]["out"] == pytest.approx(2.0, abs=0.05)
    assert p["texts"][0]["end"] == pytest.approx(4.0) and p["texts"][0]["style"] == "box"   # przycięte do długości filmu
    assert p["rev"] == 2 and p["zmienil"]["kto"] == "jarvo-wideo"                              # edytor wie, kto zmienił
    assert pr.main(["sprawdz", str(film)]) == 0


def test_keeps_user_edit_and_removes_by_id(film):
    # montaż „użytkownika”: dwa klipy z cięciem, tempo 2× na drugim
    pr.save(film, {"version": 1, "canvas": {"w": 320, "h": 240, "fps": 25}, "texts": [], "audio": [],
                   "clips": [{"id": "c1", "src": str(film), "kind": "video", "in": 0, "out": 1},
                             {"id": "c2", "src": str(film), "kind": "video", "in": 2, "out": 4, "speed": 2}]})
    assert pr.total(proj(film)) == pytest.approx(2.0)
    pr.main(["dodaj-klip", str(film), str(film), "--od", "0", "--do", "1", "--pozycja", "0"])
    assert [c["id"] for c in proj(film)["clips"]][1:] == ["c1", "c2"]
    assert pr.main(["usun", str(film), "c1"]) == 0 and len(proj(film)["clips"]) == 2


def test_captions_from_speech_follow_cuts(film):
    ed.speech_path(film).write_text(json.dumps(ed.speech_data(
        [[0.1, 0.5, "Raz"], [0.5, 0.9, "dwa."], [2.2, 2.6, "Trzy"], [2.6, 3.0, "cztery."]], [], 4.0)), encoding="utf-8")
    pr.save(film, {"version": 1, "canvas": {"w": 320, "h": 240, "fps": 25}, "texts": [], "audio": [],
                   "clips": [{"id": "a", "src": str(film), "kind": "video", "in": 0, "out": 1},
                             {"id": "b", "src": str(film), "kind": "video", "in": 2, "out": 4}]})
    assert pr.main(["napisy", str(film)]) == 0
    caps = [(round(x["start"], 2), x["text"]) for x in proj(film)["texts"] if x.get("cap")]
    assert caps == [(0.1, "Raz dwa."), (1.2, "Trzy cztery.")]      # drugi klip zaczyna się na osi w 1.0 s


def _has_playwright():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_playwright(), reason="render napisów potrzebuje playwright (narzedzia.py instaluj html)")
def test_render_same_engine(film, capsys):
    pr.main(["dodaj-tekst", str(film), "Test", "--start", "0", "--koniec", "2"])
    assert pr.main(["render", str(film)]) == 0
    out = film.with_name("film-edycja.mp4")
    assert out.is_file() and f"MEDIA:{out}" in capsys.readouterr().out


def test_kadr_sets_focus_and_zoom(film, capsys):
    """Pion z poziomego: klip „Wypełnij” z punktem skupienia i przybliżeniem; wartości spoza zakresu przycięte."""
    assert pr.main(["dodaj-klip", str(film), str(film), "--od", "0", "--do", "1", "--wypelnij", "--fx", "0.3"]) == 0
    c = proj(film)["clips"][-1]
    assert (c["fit"], c["fx"]) == ("cover", 0.3)
    assert pr.main(["kadr", str(film), c["id"], "--fy", "0.2", "--zoom", "9"]) == 0
    c = next(x for x in proj(film)["clips"] if x["id"] == c["id"])
    assert (c["fx"], c["fy"], c["zoom"]) == (0.3, 0.2, 3.0)
    assert pr.main(["sprawdz", str(film)]) == 0
    with pytest.raises(SystemExit, match="nie ma klipu"):
        pr.main(["kadr", str(film), "brak"])


def test_captions_karaoke_keep_word_times(film):
    """--karaoke: napisy ze słów dostają czasy słów (od początku linii) i kolor aktywnego słowa."""
    ed.speech_path(film).write_text(json.dumps(ed.speech_data(
        [[0.1, 0.5, "Raz"], [0.6, 0.9, "dwa."], [2.2, 2.6, "Trzy"], [2.7, 3.0, "cztery."]], [], 4.0)), encoding="utf-8")
    assert pr.main(["napisy", str(film), "--karaoke"]) == 0
    caps = [x for x in proj(film)["texts"] if x.get("cap")]
    assert caps[0]["hl"] == pr.KARAOKE_HL and caps[0]["words"] == [[0.0, 0.4, "Raz"], [0.5, 0.8, "dwa."]]
    p = ed.normalize(proj(film), pr.resolve)
    assert [len(x.get("kara") or []) for x in p["texts"]] == [2, 2]
    assert pr.main(["napisy", str(film), "--karaoke", "#00FF00"]) == 0
    assert all(x["hl"] == "#00FF00" for x in proj(film)["texts"] if x.get("cap"))


@pytest.mark.skipif(not _has_playwright(), reason="render napisów potrzebuje playwright (narzedzia.py instaluj html)")
def test_render_karaoke(film, capsys):
    ed.speech_path(film).write_text(json.dumps(ed.speech_data(
        [[0.1, 0.5, "Raz"], [0.6, 0.9, "dwa."], [2.2, 2.6, "Trzy"], [2.7, 3.0, "cztery."]], [], 4.0)), encoding="utf-8")
    pr.main(["napisy", str(film), "--karaoke"])
    assert pr.main(["render", str(film), "--out", str(film.with_name("kar.mp4"))]) == 0
    assert ed.probe(film.with_name("kar.mp4"))["duration"] == pytest.approx(4.0, abs=0.15)

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
def test_loop_seam(tmp_path):
    assert krytyka.petla(_film(tmp_path / "c.mp4", "color=c=blue"), None)["ok"]
    assert not krytyka.petla(_film(tmp_path / "t.mp4", "testsrc2"), None)["ok"]


def test_round_scoring(tmp_path):
    k = tmp_path / "k.json"
    k.write_text(json.dumps({"runda": 1, "osie": {o: 8 for o in krytyka.OSIE},
                             "problemy": [{"t": 1.0, "problem": "x", "poprawka": "y"}]}))
    assert krytyka.ocena(k)["ok"]
    k.write_text(json.dumps({"runda": 2, "osie": {**{o: 9 for o in krytyka.OSIE}, "kompozycja": 6}, "problemy": [{"problem": "bez czasu"}]}))
    r = krytyka.ocena(k)
    assert not r["ok"] and r["ponizej_8"] == {"kompozycja": 6} and r["problemy_bez_czasu"] == 1

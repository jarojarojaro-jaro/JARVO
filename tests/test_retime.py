"""retime.py (Wideograf): mapa czasu, wstrzyknięcie osłony na timeline, przeliczenie scen i audio."""
import json
import re

import pytest

from conftest import load_script

rt = load_script("profiles/jarvo-wideo/scripts/retime.py", "retime")

HTML = """<html><body>
<div id="root" data-composition-id="main" data-start="0" data-width="1920" data-height="1080" data-duration="40">
<section class="clip" id="s1" data-start="0" data-duration="10.5"><div class="sc"></div></section>
<section class="clip" id="s2" data-start="10" data-duration="30"><div class="sc"></div></section>
<audio id="a" src="x.wav" data-start="0" data-duration="40"></audio></div>
<script>
const TOTAL = 40;
const tl = gsap.timeline({ paused: true });
tl.to(clock, { t: TOTAL, duration: TOTAL, ease: "none" }, 0);
tl.fromTo("#a", { x: 0 }, { x: 5, duration: 1 }, 12);
window.__timelines["main"] = tl;
</script></body></html>"""


def test_timemap_piecewise_and_clamp():
    tm = rt.Timemap([[1, 0], [11, 5], [21, 10]])
    assert tm(11) == 5 and tm(6) == pytest.approx(2.5)
    assert tm(0) == 0            # przed pierwszą kotwicą 1:1, ale nigdy < 0
    assert tm(25) == pytest.approx(14)   # po ostatniej 1:1
    with pytest.raises(SystemExit):
        rt.Timemap([[5, 3], [4, 4]])


def test_inject_wraps_timeline_and_keeps_clock_raw():
    out = rt.inject(HTML, [[10, 4]], 0.85, 22.5)
    assert "const ANCH = [[10, 4]]" in out and "const _tl = gsap.timeline" in out
    assert "_tl.to(clock," in out                       # zegar HUD po surowej osi
    assert 'window.__timelines["main"] = _tl;' in out    # rejestrowany jest prawdziwy timeline
    assert "const TOTAL = 22.5;" in out
    with pytest.raises(SystemExit):
        rt.inject(out, [[1, 1]], 0.85, 10)               # drugi retime na wyniku odrzucony


def test_structure_scenes_audio_and_root():
    tm = rt.Timemap([[10, 4], [40, 22.5]])
    out, rep = rt.patch_structure(HTML, tm, 22.5, 0.55)
    assert [r["start"] for r in rep] == [0.0, 4.0]
    assert rep[0]["dlugosc"] == pytest.approx(4.55, abs=0.01)   # do startu następnej + nakładka
    assert rep[1]["dlugosc"] == pytest.approx(18.5)
    assert 'data-composition-id="main" data-start="0" data-width="1920" data-height="1080" data-duration="22.5"' in out
    assert re.search(r'<audio[^>]*data-duration="22.5"', out)


def test_cli_end_to_end(tmp_path):
    src, k, dst = tmp_path / "index.v1.html", tmp_path / "k.json", tmp_path / "index.html"
    src.write_text(HTML, encoding="utf-8")
    k.write_text(json.dumps({"kotwice": [[10, 4], [40, 22.5]], "koniec": 22.5}), encoding="utf-8")
    assert rt.main([str(src), "--kotwice", str(k), "-o", str(dst)]) == 0
    assert "const ANCH" in dst.read_text(encoding="utf-8")
    assert rt.main(["mapuj", str(k), "10", "40"]) == 0

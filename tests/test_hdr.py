"""HDR z telefonu → zwykły obraz (SDR): rozpoznanie w probe (edytor.hdr, wideo_lib.probe), łańcuch zscale + tonemap
(edytor.sdr_filter) w eksporcie i podglądzie edytora HQ, w montażu, napisach i kontroli przed oddaniem."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_hdr_test")
sys.path.insert(0, str(REPO / "profiles" / "jarvo-wideo" / "scripts"))
import montaz  # noqa: E402
import qa_wideo  # noqa: E402
import wideo_lib as wl  # noqa: E402

HLG = {"codec_type": "video", "color_transfer": "arib-std-b67", "color_primaries": "bt2020", "color_space": "bt2020nc",
       "color_range": "tv"}
DV = {**HLG, "side_data_list": [{"side_data_type": "DOVI configuration record", "dv_profile": 8,
                                 "dv_bl_signal_compatibility_id": 4}]}


def _ff_zscale() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return " zscale " in r.stdout and " tonemap " in r.stdout


def test_rozpoznanie_hdr():
    assert ed.hdr(HLG) == {"rodzaj": "HLG", "tonemap": True, "trc": "arib-std-b67", "prim": "bt2020", "mat": "bt2020nc",
                           "range": "tv", "uwaga": None}
    assert ed.hdr({**HLG, "color_transfer": "smpte2084"})["rodzaj"] == "HDR10 (PQ)"
    iphone = ed.hdr(DV)                                         # iPhone: Dolby Vision 8.4 z warstwą HLG
    assert iphone["rodzaj"] == "Dolby Vision (profil 8)" and iphone["trc"] == "arib-std-b67" and iphone["tonemap"]
    goly = ed.hdr({"side_data_list": DV["side_data_list"]})   # warstwa bazowa bez znaczników → PQ, gama BT.2020
    assert goly["trc"] == "smpte2084" and goly["prim"] == "bt2020" and goly["mat"] == "bt2020nc"
    assert "profil 5" in ed.hdr({"side_data_list": [{"side_data_type": "DOVI configuration record", "dv_profile": 5}]})["uwaga"]
    b2020 = ed.hdr({"color_transfer": "bt2020-10", "color_primaries": "bt2020", "color_space": "bt2020nc"})
    assert b2020["rodzaj"] == "BT.2020 (SDR)" and not b2020["tonemap"] and b2020["trc"] == "bt2020-10"
    assert ed.hdr({**HLG, "color_range": "pc"})["range"] == "pc"
    for zwykly in ({"color_transfer": "bt709", "color_primaries": "bt709", "color_space": "bt709"}, {},
                   {"side_data_list": [{"rotation": -90}]}):
        assert ed.hdr(zwykly) is None


def test_lancuch_sdr():
    f = ed.sdr_filter(ed.hdr(HLG))
    assert f.startswith("zscale=tin=arib-std-b67:pin=bt2020:min=bt2020nc:rin=tv:t=linear:npl=100,format=gbrpf32le")
    assert f"tonemap=tonemap={ed.TONEMAP}" in f and "desat=0" in ed.TONEMAP
    assert f.endswith("zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    g = ed.sdr_filter(ed.hdr({"color_transfer": "bt2020-10", "color_primaries": "bt2020"}))
    assert "tonemap" not in g and "zscale=p=bt709" in g          # BT.2020 SDR: tylko gama, bez przyciemniania bieli
    assert ed.sdr_filter(None) == ""


def _projekt(tmp_path: Path, fit: str = "cover", kolor: dict | None = None):
    a = tmp_path / "iphone.mov"
    a.write_bytes(b"x")
    b = tmp_path / "zwykly.mp4"
    b.write_bytes(b"x")
    res = lambda s: Path(s) if Path(s).is_file() else None   # noqa: E731
    clips = [{"src": str(a), "in": 0, "out": 2, "fit": fit, **({"color": kolor} if kolor else {})},
             {"src": str(b), "in": 0, "out": 2}]
    return ed.normalize({"clips": clips}, res), str(a), str(b)


def test_eksport_przelicza_po_kadrze_przed_kolorem(tmp_path):
    sdr = ed.sdr_filter(ed.hdr(DV))
    p, a, b = _projekt(tmp_path, kolor={"look": "cieply", "contrast": 10})
    cmd = ed.build_command(p, {a: True, b: True}, [], tmp_path / "o.mp4", sdr={a: sdr, b: ""})
    g = cmd[cmd.index("-filter_complex") + 1]
    v0, v1 = g.split("[v0]")[0], g.split("[v0]")[1].split("[v1]")[0]
    assert v0.index("crop=") < v0.index("zscale=tin=arib-std-b67") < v0.index("tonemap=") < v0.index("lutrgb") < v0.index("setsar")
    assert "zscale" not in v1                                                    # zwykły klip bez zmian
    p, a, b = _projekt(tmp_path, fit="blur")
    g = ed.build_command(p, {a: True, b: True}, [], tmp_path / "o.mp4", sdr={a: sdr})[4:]
    g = g[g.index("-filter_complex") + 1].split("[v0]")[0]
    assert g.index("overlay=") < g.index("zscale=")                             # rozmyte tło: po złożeniu kadru
    bez = ed.build_command(p, {a: True, b: True}, [], tmp_path / "o.mp4")       # stare wywołania bez `sdr` działają
    assert "zscale" not in " ".join(bez)


def test_podglad_i_auto_kolor_po_przeliczeniu(tmp_path):
    src = tmp_path / "iphone.mov"
    src.write_bytes(b"x")
    sdr = ed.sdr_filter(ed.hdr(HLG))
    vf = ed.proxy_command(src, tmp_path / "p.webm", sdr=sdr)
    vf = vf[vf.index("-vf") + 1]
    assert vf.index("scale=-2:") < vf.index("zscale=") < vf.rindex("format=yuv420p")
    assert ed.proxy_key(src) != ed.proxy_key(src, sdr)                          # stara kopia HDR nie wraca do podglądu
    assert "zscale" not in " ".join(ed.proxy_command(src, tmp_path / "p.webm"))
    m = ed.kolor_pomiar_cmd(src, 0, 3, sdr=sdr)
    m = m[m.index("-vf") + 1]
    assert m.index("scale=320") < m.index("zscale=") < m.index("signalstats")   # „Auto” mierzy obraz po przeliczeniu
    js = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")
    assert re.search(r"function canPlayVideo\(m\) \{\n.*\n\s*if \(m && m\.kind === \"video\" && m\.hdr\) return false;", js)
    api = (REPO / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    assert '"vcodec", "hdr")' in api and "sdr=sdr)" in api


def _ffprobe_json(stream: dict) -> str:
    return json.dumps({"streams": [{"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 2160,
                                    "r_frame_rate": "30/1", "pix_fmt": "yuv420p10le", **stream},
                                   {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2}],
                       "format": {"duration": "12.5", "size": "1000", "format_name": "mov"}})


def test_wideo_lib_probe_i_sdr(monkeypatch, capsys):
    out = {"json": _ffprobe_json(DV)}

    def run(cmd, **kw):
        assert "color_transfer" in cmd[4] and "dv_profile" in cmd[4]
        return subprocess.CompletedProcess(cmd, 0, out["json"], "")
    monkeypatch.setattr(wl, "run", run)
    v = wl.probe(Path("/x/iphone.mov"))["video"]
    assert v["hdr"] == "Dolby Vision (profil 8)" and v["sdr"] == ed.sdr_filter(ed.hdr(DV)) and v["hdr_uwaga"] is None
    assert wl.sdr(Path("/x/iphone.mov")).startswith("zscale=") and "HDR (Dolby Vision" in capsys.readouterr().err
    out["json"] = _ffprobe_json({"color_transfer": "bt709"})
    assert wl.probe(Path("/x/a.mp4"))["video"]["hdr"] is None and wl.sdr(Path("/x/a.mp4")) == ""
    assert wl.z_sdr("scale=1:1", "") == "scale=1:1" and wl.z_sdr("", "zscale") == "zscale"


def test_montaz_i_kontrola(monkeypatch, tmp_path):
    sdr = ed.sdr_filter(ed.hdr(HLG))
    info = {"duration": 10.0, "size": 2 << 20, "format_name": "mov",
            "video": {"codec": "hevc", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p10le",
                      "hdr": "HLG", "hdr_uwaga": None, "sdr": sdr},
            "audio": {"codec": "aac", "sample_rate": 48000, "channels": 2}}
    monkeypatch.setattr(wl, "probe", lambda p: info)
    cmds = []
    monkeypatch.setattr(wl, "run", lambda cmd, **kw: cmds.append(cmd))
    montaz.cut(tmp_path / "a.mov", [(0, 2), (4, 6)], tmp_path / "o.mp4")
    montaz.reframe(tmp_path / "a.mov", tmp_path / "p.mp4", "9:16", 0.5, "przytnij")
    fc_cut, fc_kadr = (c[c.index("-filter_complex") + 1] for c in cmds)
    assert f"[vc]{sdr},{wl.TV_RANGE}[v]" in fc_cut
    assert fc_kadr.index("crop=") < fc_kadr.index("zscale=") < fc_kadr.index("format=yuv420p[v]")
    monkeypatch.setattr(qa_wideo, "analyze", lambda p, a: {"czarne": [], "zamrozone": [], "cisze": [], "lufs": -14.0,
                                                           "true_peak": -2.0, "lra": 5.0})
    monkeypatch.setattr(qa_wideo, "gray_frames", lambda p: ([], 30.0))
    monkeypatch.setattr(qa_wideo, "moov_first", lambda p: True)
    wynik = qa_wideo.check(tmp_path / "o.mp4", None, None, False, None)
    assert not wynik["ok"] and any("film w HDR (HLG)" in e for e in wynik["bledy"])


@pytest.mark.skipif(not _ff_zscale(), reason="ffmpeg z zscale i tonemap (obraz Hermesa)")
def test_hlg_po_montazu_ma_kolor(tmp_path):
    """Syntetyczny HLG (jak iPhone) z obrazu testowego: dziś (sama zamiana na yuv420p) obraz jest sprany, po
    przeliczeniu nasycenie wraca blisko oryginału."""
    def sat(plik: Path) -> float:
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(plik), "-vf", "signalstats,metadata=print:file=-",
                            "-frames:v", "1", "-f", "null", "-"], capture_output=True, text=True)
        return float(re.search(r"SATAVG=([\d.]+)", r.stdout).group(1))
    sdr = tmp_path / "sdr.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-colorspace", "bt709", str(sdr)], check=True)
    hlg = tmp_path / "hlg.mov"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(sdr), "-vf",
                    "zscale=tin=bt709:pin=bt709:min=bt709:rin=tv:t=arib-std-b67:p=bt2020:m=bt2020nc:r=tv:npl=203,format=yuv420p10le",
                    "-c:v", "libx265", "-x265-params", "log-level=error", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                    "-colorspace", "bt2020nc", "-color_range", "tv", str(hlg)], check=True)
    assert wl.probe(hlg)["video"]["hdr"] == "HLG"
    sprany = tmp_path / "sprany.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(hlg), "-vf", wl.TV_RANGE, str(sprany)], check=True)
    out = montaz.cut(hlg, [(0, 1)], tmp_path / "out.mp4")
    assert wl.probe(out)["video"]["hdr"] is None
    s0, s_dzis, s_po = sat(sdr), sat(sprany), sat(out)
    assert s_dzis < 0.5 * s0 and s_po > 0.85 * s0, (s0, s_dzis, s_po)

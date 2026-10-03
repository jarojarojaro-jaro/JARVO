"""Korekcja koloru klipu: jeden przepis (krzywa na kanał z 5 punktów + macierz nasycenia) w podglądzie edytora HQ
(49-kolor.js, filtr SVG) i w eksporcie (edytor.kolor_filter: lutrgb + colorchannelmixer), a Wideograf ustawia go
przez projekt.py kolor."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_kolor_test")
pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_kolor_test")
JS = (REPO / "hq" / "web" / "src" / "49-kolor.js").read_text(encoding="utf-8")
HAS_NODE = bool(shutil.which("node"))
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

KOLORY = [{"look": k, **ed.kolor_domyslne(k)} for k in ed.KOLOR_STYLE] + [
    {"brightness": 40, "contrast": -30, "saturation": 55, "temperature": -70},
    {"look": "kinowy", "brightness": -100, "temperature": 100},
    {"contrast": 12.6, "saturation": "x", "temperature": 500, "look": "nie-ma"},     # zaokrąglenie, zły typ, zakres, zły styl
    {"saturation": -100}, {}, None, "cieply",
]


def test_przepis_ten_sam_w_podgladzie():
    """kolorNorm, kolorDomyslne i kolorTabele w 49-kolor.js liczą to samo co Python (te same liczby filtra SVG)."""
    if not HAS_NODE:
        pytest.skip("brak node")
    prog = (f"const K = {json.dumps(KOLORY)}; console.log(JSON.stringify({{n: K.map(kolorNorm), t: K.map(kolorTabele), "
            f"d: {json.dumps(list(ed.KOLOR_STYLE))}.map(kolorDomyslne), style: ED_KOLOR_STYLE, "
            f"suwaki: ED_KOLOR_SUWAKI.map(([k]) => k), m: kolorMacierz(0.7)}}));")
    r = subprocess.run(["node", "-e", JS + "\n" + prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    js = json.loads(r.stdout)
    assert js["style"] == ed.KOLOR_STYLE and js["suwaki"] == list(ed.KOLOR_SUWAKI)
    assert js["n"] == [ed.kolor_norm(k) for k in KOLORY]
    assert js["d"] == [ed.kolor_domyslne(k) for k in ed.KOLOR_STYLE]
    py = [(lambda t: t and {**t[0], "s": t[1]})(ed.kolor_tabele(k)) for k in KOLORY]
    assert js["t"] == py
    assert [x for w in js["m"] for x in w] == pytest.approx([x for w in ed.kolor_macierz(0.7) for x in w])


def test_przepis_kierunki():
    assert ed.kolor_tabele(None) is None and ed.kolor_tabele({"look": "nie-ma"}) is None
    assert ed.kolor_norm({"contrast": 12.6, "temperature": 500}) == {"contrast": 13, "temperature": 100}
    tab, s = ed.kolor_tabele({"look": "cieply", **ed.kolor_domyslne("cieply")})
    assert tab["r"][2] > tab["g"][2] > tab["b"][2] and s < 1                     # ciepły: czerwień w górę, błękit w dół
    tab, s = ed.kolor_tabele({"look": "czb", **ed.kolor_domyslne("czb")})
    assert s == 0                                                               # czarno-biały: bez nasycenia
    tab, _ = ed.kolor_tabele({"look": "wyblakly", **ed.kolor_domyslne("wyblakly")})
    assert tab["r"][0] > 0.05                                                   # wyblakły: uniesiona czerń
    tab, _ = ed.kolor_tabele({"brightness": 50})
    assert tab["g"] == [0.1, 0.35, 0.6, 0.85, 1.0]


def _files(tmp_path: Path) -> Path:
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    return f


def test_kolor_w_projekcie_i_poleceniu(tmp_path):
    a = str(_files(tmp_path))
    res = lambda s: Path(s) if Path(s).is_file() else None   # noqa: E731
    p = ed.normalize({"clips": [{"src": a, "in": 0, "out": 2, "color": {"look": "cieply", "contrast": 10, "saturation": -6, "temperature": 30}},
                                {"src": a, "in": 2, "out": 4, "color": {"saturation": 0}},
                                {"src": a, "in": 4, "out": 6, "fit": "blur", "color": {"saturation": -100}}]}, res)
    assert p["clips"][0]["color"] == {"look": "cieply", "contrast": 10, "saturation": -6, "temperature": 30}
    assert "color" not in p["clips"][1]                                         # same zera = bez korekty
    cmd = ed.build_command(p, {a: True}, [], tmp_path / "o.mp4")
    g = cmd[cmd.index("-filter_complex") + 1]
    v0 = g.split("[v0]")[0]
    assert "force_original_aspect_ratio=decrease,pad=" in v0 and ",lutrgb=r='if(lt(val,63.75)," in v0
    assert v0.index("pad=") < v0.index("lutrgb") < v0.index("colorchannelmixer") < v0.index("setsar=1")   # kolor po kadrze
    v1 = g.split("[v0]")[1].split("[v1]")[0]
    assert "lutrgb" not in v1 and "colorchannelmixer" not in v1
    v2 = g.split("[v1]")[1].split("[v2]")[0]
    assert "lutrgb" not in v2 and "colorchannelmixer=rr=0.213000" in v2       # tylko nasycenie: sama macierz
    assert v2.index("overlay=(W-w)/2:(H-h)/2") < v2.index("colorchannelmixer")   # rozmyte tło też w kolorze


def test_auto_z_pomiaru():
    log = "\n".join(f"[Parsed_metadata_3 @ 0x1] lavfi.signalstats.{k}={v}" for k, v in
                    (("YAVG", 60), ("YLOW", 30), ("YHIGH", 110), ("SATAVG", 10.5)) * 3)
    w = ed.kolor_z_pomiaru(log)
    assert w["color"] == {"brightness": 30, "contrast": 30, "saturation": 15}     # ciemny, płaski, wyblakły: najwyżej +30
    ok = log.replace("YAVG=60", "YAVG=115").replace("YLOW=30", "YLOW=30").replace("YHIGH=110", "YHIGH=200").replace("SATAVG=10.5", "SATAVG=30")
    assert ed.kolor_z_pomiaru(ok)["color"] is None                              # dobrze naświetlony: bez zmian
    assert ed.kolor_z_pomiaru("brak pomiaru") is None


def _przepis(rgb: tuple[int, int, int], kol: dict) -> list[float]:
    """Piksel przez przepis (krzywa jak feFuncX table, potem macierz jak feColorMatrix), wartości 0–255."""
    tab, s = ed.kolor_tabele(kol)

    def lut(ys, v):
        x = v / 63.75
        i = min(3, int(x))
        return ys[i] + (ys[i + 1] - ys[i]) * (x - i)
    c = [lut(tab[ch], v) for ch, v in zip("rgb", rgb)]
    m = ed.kolor_macierz(s)
    return [max(0.0, min(1.0, sum(m[i][j] * c[j] for j in range(3)))) * 255 for i in range(3)]


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
@pytest.mark.parametrize("kol", [{"look": "cieply", **ed.kolor_domyslne("cieply")}, {"look": "wyblakly", **ed.kolor_domyslne("wyblakly")},
                                 {"brightness": -20, "contrast": 40, "saturation": 60, "temperature": -50}])
def test_filtr_ffmpeg_liczy_jak_przepis(tmp_path, kol):
    """lutrgb + colorchannelmixer w RGB (bez YUV): każdy piksel jak przepis, z dokładnością zaokrągleń 8 bitów."""
    probki = [(20, 20, 20), (200, 140, 110), (70, 140, 210), (90, 160, 60), (128, 128, 128), (250, 245, 235)]
    raw = tmp_path / "in.rgb"
    raw.write_bytes(bytes(v for px in probki for v in px))
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{len(probki)}x1", "-i", str(raw),
                          "-vf", f"{ed.kolor_filter(kol)},format=rgb24", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    for k, px in enumerate(probki):
        assert list(out[3 * k:3 * k + 3]) == pytest.approx(_przepis(px, kol), abs=2.5), px


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_auto_mierzy_film_i_zdjecie(tmp_path):
    """Pomiar pod „Auto” działa na klipie z filmu i ze zdjęcia (zdjęcie bez -ss/-t: jedna klatka)."""
    f, img = tmp_path / "ciemny.mp4", tmp_path / "ciemny.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=2,eq=brightness=-0.3:contrast=0.6",
                    "-pix_fmt", "yuv420p", str(f)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(f), "-frames:v", "1", str(img)], check=True)
    for src, a, b in ((f, 0.5, 1.5), (img, 0, 3)):
        r = subprocess.run(ed.kolor_pomiar_cmd(src, a, b), capture_output=True, text=True)
        w = ed.kolor_z_pomiaru(r.stderr)
        assert r.returncode == 0 and w and w["color"]["brightness"] > 0, (src, r.stderr[-300:])


@pytest.fixture()
def film(tmp_path):
    f = tmp_path / "film.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=3,eq=brightness=-0.3:contrast=0.6",
                    "-pix_fmt", "yuv420p", str(f)], check=True)
    return f


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_wideograf_ustawia_kolor(film, capsys):
    assert pr.main(["dodaj-klip", str(film), str(film), "--od", "1", "--do", "2"]) == 0
    c1, c2 = (c["id"] for c in pr.load(film)["clips"])
    assert pr.main(["kolor", str(film), c1, "--styl", "cieply", "--kontrast", "20"]) == 0
    assert pr.load(film)["clips"][0]["color"] == {"look": "cieply", "contrast": 20, "saturation": -6, "temperature": 30}
    assert pr.main(["pokaz", str(film)]) == 0 and "kolor cieply (kontrast +20, nasycenie -6, temperatura +30)" in capsys.readouterr().out
    # Auto na ciemnym, płaskim filmie: jaśniej i z kontrastem, styl zostaje
    assert pr.main(["kolor", str(film), c1, "--auto"]) == 0
    k = pr.load(film)["clips"][0]["color"]
    assert k["look"] == "cieply" and k["brightness"] > 0 and k["contrast"] > 0 and "temperature" not in k
    assert pr.main(["kolor", str(film), "--wszystkie", "--styl", "czb", "--podglad"]) == 0
    out = capsys.readouterr().out
    assert all(c.get("color", {}).get("look") == "czb" for c in pr.load(film)["clips"])
    jpg = Path(out.split("MEDIA:")[1].strip())
    w = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "json", str(jpg)],
                                  capture_output=True, text=True).stdout)["streams"][0]
    assert w["height"] == 540 and w["width"] == 2 * 720                        # przed | po obok siebie
    assert pr.main(["kolor", str(film), c2, "--usun"]) == 0 and "color" not in pr.load(film)["clips"][1]
    assert pr.main(["sprawdz", str(film)]) == 0

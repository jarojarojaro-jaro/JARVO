"""Przejścia między klipami: ta sama oś w podglądzie (49-przejscia.js) i w eksporcie (edytor.py), film nie krótszy,
każde przejście składa się w ffmpeg, a podgląd (przejscieStyl) pokazuje te same kolory co gotowy film."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, load_script

ed = load_script("hq/plugin/edytor.py", "jarvo_edytor_przejscia_test")
JS = (REPO / "hq" / "web" / "src" / "49-przejscia.js").read_text(encoding="utf-8")
HAS_NODE = bool(shutil.which("node"))
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def node(prog: str):
    r = subprocess.run(["node", "-e", JS + "\n" + prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def klip(a, b, tr=None, speed=1, src="a.mp4"):
    c = {"src": src, "in": a, "out": b, "speed": speed}
    if tr is not None:
        c["transition"] = tr
    return c


OSIE = [
    # 30 fps: 0,5 s → 16 klatek (parzysta liczba), ostatni klip bez przejścia mimo pola
    ([klip(0, 2, {"type": "fade", "dur": 0.5}), klip(0, 3, {"type": "blur"})], 30),
    # krótszy sąsiad (0,3 s) ogranicza przejście; tempo 2× skraca klip na osi
    ([klip(0, 4, {"type": "slideleft", "dur": 2}), klip(1, 1.3), klip(0, 4, {"type": "zoomin", "dur": 1.2}, speed=2), klip(0, 1)], 25),
    # zła nazwa, pusta długość, za krótko na 2 klatki, długość spoza zakresu
    ([klip(0, 2, {"type": "dissolve"}), klip(0, 2, {"type": "fade", "dur": None}), klip(0, 0.05, {"type": "fade"}),
      klip(0, 9, {"type": "circleopen", "dur": 99}), klip(0, 9)], 24),
    ([klip(0, 2, {"type": "pixelize", "dur": "0.3"}), klip(0, 2, {"type": "fadewhite", "dur": 0.1}), klip(0, 2)], 60),
]


def test_os_przejsc_ta_sama_w_podgladzie_i_eksporcie():
    oczek = [ed.przejscia_osi(c, f) for c, f in OSIE]
    assert oczek[0] == [{"type": "fade", "d": 16 / 30}, None]
    assert oczek[1] == [{"type": "slideleft", "d": 6 / 25}, None, {"type": "zoomin", "d": 24 / 25}, None]
    # zła nazwa; sąsiad 0,05 s (za mało na dwie klatki) po obu stronach; długość 99 s → 3 s
    assert oczek[2] == [None, None, None, {"type": "circleopen", "d": 3.0}, None]
    assert oczek[3] == [{"type": "pixelize", "d": 18 / 60}, {"type": "fadewhite", "d": 6 / 60}, None]
    if not HAS_NODE:
        pytest.skip("brak node")
    assert node(f"console.log(JSON.stringify({json.dumps(OSIE)}.map(([c, f]) => przejsciaOsi(c, f))));") == oczek


def test_normalize_przejscie_i_dlugosc_filmu(tmp_path):
    for n in ("a.mp4", "b.mp4"):
        (tmp_path / n).write_bytes(b"x")
    res = lambda s: (tmp_path / Path(s).name) if (tmp_path / Path(s).name).is_file() else None
    p = ed.normalize({"canvas": {"w": 320, "h": 240, "fps": 25},
                      "clips": [klip(0, 2, {"type": "wipeleft", "dur": 0.4, "x": 1}, src=str(tmp_path / "a.mp4")),
                                klip(1, 3, {"type": "nie-ma"}, src=str(tmp_path / "b.mp4"))]}, res)
    assert p["clips"][0]["transition"] == {"type": "wipeleft", "dur": 0.4} and "transition" not in p["clips"][1]
    assert p["przejscia"] == [{"type": "wipeleft", "d": 0.4}, None]
    assert p["duration"] == pytest.approx(4.0)       # przejście nie skraca filmu


def test_okno_przejscia_na_srodku_ciecia():
    if not HAS_NODE:
        pytest.skip("brak node")
    r = node("""const segs = [{start: 0, end: 2}, {start: 2, end: 5}, {start: 5, end: 6}];
const trs = [{type: "fade", d: 1}, null, null];
console.log(JSON.stringify([1.4, 1.5, 2, 2.49, 2.5, 4.9].map((t) => przejscieW(segs, trs, t))));""")
    assert r[0] is None and r[1]["q"] == pytest.approx(0) and r[2]["q"] == pytest.approx(0.5)
    assert r[3]["q"] == pytest.approx(0.99) and r[4] is None and r[5] is None
    assert r[2]["i"] == 0 and r[2]["T"] == 2


def test_styl_css_warstw():
    if not HAS_NODE:
        pytest.skip("brak node")
    r = node("""console.log(JSON.stringify([
  przejscieCss(przejscieStyl("slideleft", 0.25).a, 10), przejscieCss(przejscieStyl("wipeleft", 0.25).b, 10),
  przejscieCss(przejscieStyl("blur", 0.5).a, 20), przejscieCss(przejscieStyl("circleopen", 0.5).b, 10).maskImage.slice(0, 40),
  przejscieStyl("pixelize", 0.5).piksel, przejscieStyl("fadewhite", 0.3).tlo, przejscieStyl("zoomin", 0.2).a.sc > 1]));""")
    assert r[0]["transform"] == "translate(-25%, 0%)" and r[0]["opacity"] == ""
    assert r[1]["clipPath"] == "inset(0% 0% 0% 75%)"
    assert r[2]["filter"] == "blur(10px)"
    assert r[3].startswith("radial-gradient(circle farthest-corner")
    assert r[4] == pytest.approx(0.05) and r[5] == "#fff" and r[6] is True


# ------------------------------------------------------------------ prawdziwy eksport

def _media(tmp: Path) -> dict[str, Path]:
    """A: lewa połowa czerwona, prawa zielona (dźwięk 440 Hz); B: niebieska / żółta (660 Hz); 200×200, 25 fps, 3 s."""
    def zrob(name, c1, c2, f):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color={c1}:s=100x200:d=3:r=25",
                        "-f", "lavfi", "-i", f"color={c2}:s=100x200:d=3:r=25", "-f", "lavfi", "-i", f"sine=f={f}:d=3",
                        "-filter_complex", "[0][1]hstack,format=yuv420p[v]", "-map", "[v]", "-map", "2:a", "-shortest",
                        str(tmp / name)], check=True)
        return tmp / name
    return {"a": zrob("a.mp4", "red", "green", 440), "b": zrob("b.mp4", "blue", "yellow", 660)}


def _projekt(m: dict, typ: str, d: float = 1.0) -> dict:
    # A 0–1,5 s (zapas 1,5 s za cięciem), B 0,5–2 s (zapas 0,5 s przed cięciem): przejście 1 s ma materiał po obu stronach
    return ed.normalize({"canvas": {"w": 200, "h": 200, "fps": 25},
                         "clips": [{"src": str(m["a"]), "in": 0, "out": 1.5, "transition": {"type": typ, "dur": d}},
                                   {"src": str(m["b"]), "in": 0.5, "out": 2}]},
                        lambda s: Path(s) if Path(s).is_file() else None)


def _render(p: dict, out: Path) -> None:
    has = {str(c["src"]): True for c in p["clips"]}
    r = subprocess.run(ed.build_command(p, has, [], out), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]


def _klatki(film: Path, nr: list[int]) -> dict[int, bytes]:
    out = {}
    for k in nr:
        out[k] = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(film), "-vf", f"select=eq(n\\,{k}),format=rgb24",
                                 "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return out


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_kazde_przejscie_sklada_sie_i_nie_skraca_filmu(tmp_path):
    m = _media(tmp_path)
    for typ in ed.PRZEJSCIA:
        out = tmp_path / f"{typ}.mp4"
        _render(_projekt(m, typ, 0.4), out)
        info = ed.probe(out)
        assert info["duration"] == pytest.approx(3.0, abs=0.05), typ
        assert info["audio"], typ


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_przejscia_w_grupach_i_brak_materialu(tmp_path):
    """Trzy klipy: cięcie bez przejścia (concat), potem rozmycie; B bez zapasu przed sobą (in=0: pierwsza klatka stoi),
    plansza (obraz) na końcu. Film trwa tyle co suma klipów, a klatka w środku przejścia jest mieszanką."""
    m = _media(tmp_path)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=white:s=64x64", "-frames:v", "1",
                    str(tmp_path / "w.png")], check=True)
    p = ed.normalize({"canvas": {"w": 200, "h": 200, "fps": 25},
                      "clips": [{"src": str(m["a"]), "in": 0, "out": 1}, {"src": str(m["b"]), "in": 0, "out": 1,
                                                                          "transition": {"type": "blur", "dur": 0.8}},
                                {"src": str(tmp_path / "w.png"), "in": 0, "out": 1.2}]},
                     lambda s: Path(s) if Path(s).is_file() else None)
    out = tmp_path / "o.mp4"
    cmd = ed.build_command(p, {str(m["a"]): True, str(m["b"]): True}, [], out)
    graf = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2" in graf and "xfade=transition=fade" in graf and "gblur@pb1" in graf and "acrossfade" in graf
    _render(p, out)
    info = ed.probe(out)
    assert info["duration"] == pytest.approx(3.2, abs=0.05)
    k = _klatki(out, [25, 30, 50, 79])
    px = lambda f, x, y: f[(y * 200 + x) * 3:(y * 200 + x) * 3 + 3]
    assert px(k[25], 20, 100)[2] > 200 and px(k[25], 20, 100)[0] < 60     # B (niebieski) od razu po cięciu A|B
    assert min(px(k[50], 20, 100)) > 60                                      # środek rozmycia: niebieski z bielą
    assert min(px(k[79], 100, 100)) > 230                                    # koniec: sama plansza


# podgląd (przejscieStyl w przeglądarce) = film: kolory w siatce punktów klatki w środku przejścia
RASTER_JS = r"""
const KOL = { a: [[255, 0, 0], [0, 128, 0]], b: [[0, 0, 255], [255, 255, 0]] };
function warstwa(o, kol, u, v) {               // [r,g,b,alfa] warstwy w punkcie ekranu (u,v)
  const sc = o.sc || 1, cu = (u - (o.dx || 0) - 0.5) / sc + 0.5, cv = (v - (o.dy || 0) - 0.5) / sc + 0.5;
  if (cu < 0 || cu >= 1 || cv < 0 || cv >= 1) return [0, 0, 0, 0];
  let al = o.op === undefined ? 1 : o.op;
  if (o.clip) { const [t, r, b, l] = o.clip; if (cv < t || cu >= 1 - r || cv >= 1 - b || cu < l) return [0, 0, 0, 0]; }
  if (o.mask) {
    const x = o.mask.lin ? cu : Math.hypot(cu - 0.5, cv - 0.5) / Math.hypot(0.5, 0.5);
    const v2 = o.mask.lin || o.mask.rad, k = Math.min(9.999, Math.max(0, x * 10)), i = Math.floor(k);
    al *= v2[i] + (v2[i + 1] - v2[i]) * (k - i);
  }
  return [...kol[cu < 0.5 ? 0 : 1], al];
}
function kolor(typ, q, u, v) {
  const s = przejscieStyl(typ, q), tlo = s.tlo === "#fff" ? [255, 255, 255] : [0, 0, 0];
  let c = tlo;
  for (const [o, kol] of [[s.a, KOL.a], [s.b, KOL.b]]) {
    const [r, g, b, al] = warstwa(o, kol, u, v);
    c = [r * al + c[0] * (1 - al), g * al + c[1] * (1 - al), b * al + c[2] * (1 - al)];
  }
  return c;
}
const pyt = JSON.parse(process.argv[1]);
console.log(JSON.stringify(pyt.map(([typ, q, u, v]) => [-0.03, 0, 0.03].flatMap((e) => [kolor(typ, q, u + e, v), kolor(typ, q, u, v + e)]))));
"""

# (typ, klatki w oknie 1 s przy 25 fps: q = k/25, zakresy u pominięte: rozmycie przy granicy kolorów)
PODGLAD = [("fade", [6, 19], []), ("fadeblack", [3, 6, 19], []), ("fadewhite", [6, 19], []), ("slideleft", [6, 19], []),
           ("slideright", [6], []), ("slideup", [6, 19], []), ("slidedown", [6], []), ("coverleft", [6, 19], []),
           ("coverright", [6], []), ("wipeleft", [6, 19], []), ("wiperight", [6, 19], []), ("smoothleft", [6, 13, 19], []),
           ("circleopen", [6, 13, 19], []), ("zoomin", [6], []), ("pixelize", [6, 19], []), ("blur", [6, 19], [(0.36, 0.64)])]


@pytest.mark.skipif(not (HAS_FF and HAS_NODE), reason="brak ffmpeg albo node")
def test_podglad_pokazuje_to_samo_co_film(tmp_path):
    m = _media(tmp_path)
    pkt = [(u / 10 + 0.05, v / 10 + 0.05) for u in range(10) for v in range(10)]
    bledy = []
    for typ, ks, pomin in PODGLAD:
        out = tmp_path / f"{typ}.mp4"
        _render(_projekt(m, typ), out)
        klatki = _klatki(out, [25 + k for k in ks])            # okno przejścia: 1,0–2,0 s osi = klatki 25–49
        pyt = [(typ, k / 25, u, v) for k in ks for u, v in pkt]
        r = subprocess.run(["node", "-e", JS + "\n" + RASTER_JS, json.dumps(pyt)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        for (typ_, q, u, v), warianty in zip(pyt, json.loads(r.stdout)):
            if any(a <= u <= b for a, b in pomin):
                continue
            f = klatki[25 + round(q * 25)]
            x, y = int(u * 200), int(v * 200)
            film = f[(y * 200 + x) * 3:(y * 200 + x) * 3 + 3]
            if not any(max(abs(c - z) for c, z in zip(film, w)) <= 34 for w in warianty):
                bledy.append(f"{typ_} q={q:.2f} ({u:.2f},{v:.2f}): film {tuple(film)}, podgląd {[round(c) for c in warianty[0]]}")
    assert not bledy, "\n".join(bledy[:20])


def test_projekt_przejscie(tmp_path, monkeypatch, capsys):
    """Agent ustawia, zmienia i zdejmuje przejście tak, jak edytor (pole transition klipu przed cięciem)."""
    pr = load_script("profiles/jarvo-wideo/scripts/projekt.py", "jarvo_projekt_przejscie_test")
    film = tmp_path / "film.mp4"
    film.write_bytes(b"x")
    stan = {"p": {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "texts": [], "audio": [],
                  "clips": [{"id": "a", "src": "a.mp4", "in": 0, "out": 2, "speed": 1},
                            {"id": "b", "src": "a.mp4", "in": 2, "out": 2.2, "speed": 1},
                            {"id": "c", "src": "a.mp4", "in": 3, "out": 6, "speed": 1}]}}
    monkeypatch.setattr(pr, "load", lambda f: json.loads(json.dumps(stan["p"])))
    monkeypatch.setattr(pr, "save", lambda f, p: stan.update(p=p))

    def run(*argv):
        assert pr.main(["przejscie", str(film), *argv]) == 0
        return capsys.readouterr().out

    out = run("a", "--typ", "slideleft", "--dlugosc", "0.8")
    assert stan["p"]["clips"][0]["transition"] == {"type": "slideleft", "dur": 0.8}
    assert "slideleft 0.20 s" in out                       # klip b ma 0,2 s: przejście skraca się do niego
    run("--wszystkie", "--typ", "blur")
    assert [c.get("transition") for c in stan["p"]["clips"]] == [{"type": "blur", "dur": 0.8}, {"type": "blur", "dur": 0.5}, None]
    run("b", "--usun")
    assert "transition" not in stan["p"]["clips"][1]
    with pytest.raises(SystemExit, match="ostatnim"):
        pr.main(["przejscie", str(film), "c"])
    assert pr.main(["pokaz", str(film)]) == 0
    assert "↳ przejście blur 0.20 s (1.90–2.10)" in capsys.readouterr().out


def test_ciecie_zostawia_przejscie_na_prawej_czesci():
    """Tnij (split) i wycinanie mowy (cutTimeline) w edytorze: przejście zostaje tylko na ostatnim kawałku klipu."""
    src = (REPO / "hq" / "web" / "src" / "45-edytor.js").read_text(encoding="utf-8")
    assert "[{ ...c, out: cut, transition: undefined }, right]" in src
    assert "transition: k === pieces.length - 1 ? s.c.transition : undefined" in src

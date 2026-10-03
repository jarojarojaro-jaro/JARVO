"""Typografia Wideografa: reżyser z reguł (typografia.py), plan w projekcie (edytor.normalize_typo), warstwy
eksportu (typo_concat, build_command) i renderer 48-typografia.js (te same dane w edytorze HQ i w renderze)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "profiles" / "jarvo-wideo" / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("typografia", SCRIPTS / "typografia.py")
ty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ty)
ed = ty.ed
JS = (ROOT / "hq" / "web" / "src" / "48-typografia.js").read_text(encoding="utf-8")
HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAS_NODE = bool(shutil.which("node"))


def mowa(tekst: str, start: float = 0.2, dl: float = 0.32, przerwa: float = 0.04, pauzy: dict | None = None,
         glosne: tuple = ()) -> list[dict]:
    """Słowa jak z analizy mowy: [{a, b, tekst, z}] po kolei; `pauzy` = {numer słowa: dłuższa cisza przed nim}."""
    out, t = [], start
    for i, w in enumerate(tekst.split()):
        t += (pauzy or {}).get(i, 0.0)
        out.append({"a": round(t, 3), "b": round(t + dl, 3), "tekst": w, "z": 2.5 if i in glosne else 0.0})
        t += dl + przerwa
    return out


def teksty(grupy) -> list[str]:
    return [" ".join(w["tekst"] for w in g) for g in grupy]


def przygotuj(slowa):
    slowa = [dict(w) for w in slowa]
    ty.ustaw_wagi(slowa)
    return slowa


# ---------------------------------------------------------------- frazy i wagi

def test_frazy_koniec_zdania_dzieli_zawsze():
    g = ty.frazy(przygotuj(mowa("Słuchaj. Nie kupuj kolejnego kursu.")), [])
    assert teksty(g)[0] == "Słuchaj."
    assert "Słuchaj." not in " ".join(teksty(g)[1:])


def test_frazy_nie_koncza_sie_na_slowie_funkcyjnym_ani_nie():
    for zdanie in ("Zostaw łapkę w górę i zasubskrybuj kanał.", "Większość bólu pleców nie bierze się z wieku.",
                   "Dziś mam kolejkę na dwa miesiące."):
        for blok in ty.frazy(przygotuj(mowa(zdanie)), [])[:-1]:
            ost = ty.czyste(blok[-1]["tekst"])
            assert ost not in ty.KONIEC_ZLY, (zdanie, teksty([blok]))


def test_frazy_liczba_zostaje_z_rzeczownikiem_a_sie_z_czasownikiem():
    g = teksty(ty.frazy(przygotuj(mowa("Jeden telefon do klienta powie więcej niż 100 slajdów.")), []))
    assert any("100 slajdów" in b for b in g), g
    g = teksty(ty.frazy(przygotuj(mowa("To naprawdę bierze się z siedzenia.")), []))
    assert not any(b.startswith("się") for b in g), g


def test_frazy_ciecie_ujecia_i_dluga_cisza_dziela():
    slowa = przygotuj(mowa("raz dwa trzy cztery", pauzy={2: 1.2}))
    assert teksty(ty.frazy(slowa, [])) == ["raz dwa", "trzy cztery"]
    slowa = przygotuj(mowa("alfa beta gamma delta"))
    ciecie = (slowa[0]["b"] + slowa[1]["a"]) / 2
    assert teksty(ty.frazy(slowa, [ciecie]))[0] == "alfa"


def test_frazy_limit_slow_w_bloku():
    slowa = przygotuj(mowa(" ".join(["słowo"] * 23)))
    for tempo, lim in ty.TEMPO.items():
        assert all(len(b) <= lim["slow"] + 1 for b in ty.frazy(slowa, [], tempo))
    assert sum(len(b) for b in ty.frazy(slowa, [])) == 23


def test_wagi_slowa_funkcyjne_liczby_i_glosnosc():
    s = przygotuj(mowa("w przyszłym tygodniu 2000 zł", glosne=(2,)))
    w = {x["tekst"]: x["waga"] for x in s}
    assert w["w"] == 0 and w["przyszłym"] >= 1
    assert w["2000"] == 3 and w["tygodniu"] >= 2


def test_jedno_uderzenie_w_bloku_i_zawsze_punkt_skupienia():
    blok = przygotuj(mowa("TERAZ 100 ZŁOTYCH!", glosne=(0, 1, 2)))
    ty.popraw_wagi_bloku(blok)
    assert [w["waga"] for w in blok] == [2, 3, 2]        # uderzenie na liczbie, jednostka obok mniejsza
    blok = przygotuj(mowa("i w to"))
    ty.popraw_wagi_bloku(blok)
    assert max(w["waga"] for w in blok) >= 2


def test_rytm_uderzen_co_trzeci_blok_bez_sasiadow():
    grupy = [przygotuj(mowa(f"zwykłe słowo{chr(97 + i)} tutaj")) for i in range(9)]
    for g in grupy:
        ty.popraw_wagi_bloku(g)
    ty.rytm_uderzen(grupy)
    z = [any(w["waga"] == 3 for w in g) for g in grupy]
    assert sum(z) == round(9 * ty.UDERZENIA)
    assert not any(a and b for a, b in zip(z, z[1:]))
    for g in grupy:                                  # za dużo uderzeń: słabsze wracają do 2
        g[-1]["waga"] = 3
    ty.rytm_uderzen(grupy)
    assert sum(any(w["waga"] == 3 for w in g) for g in grupy) <= round(round(9 * ty.UDERZENIA) * 1.4)


def test_linie_uderzenie_samo_jednostka_przy_liczbie():
    blok = przygotuj(mowa("tylko 2000 zł miesięcznie"))
    ty.popraw_wagi_bloku(blok)
    li = ty.linie(blok)
    assert li[1] == li[2]                            # „2000 zł” w jednej linii
    assert li[0] != li[1]


# ---------------------------------------------------------------- plan

def plan(tekst="Słuchaj. Nie kupuj kolejnego kursu za dwa tysiące złotych. Najpierw sprawdź, czy ktoś w ogóle chce "
         "twój produkt. Jeden telefon do klienta powie więcej niż 100 slajdów.", motyw="kino", W=1080, H=1920):
    slowa = mowa(tekst, pauzy={1: 0.3, 9: 0.5, 19: 0.4})
    total = slowa[-1]["b"] + 1.0
    return ty.zbuduj_plan(slowa, [], W, H, total, motyw), total


def test_plan_bloki_po_kolei_bez_nakladania():
    p, total = plan()
    b = p["bloki"]
    assert p["motyw"] == "kino" and len(b) >= 6
    assert [x["id"] for x in b] == [f"b{i + 1:02d}" for i in range(len(b))]
    for x, y in zip(b, b[1:]):
        assert x["end"] <= y["start"] + 1e-6
    assert all(0 <= x["start"] < x["end"] <= total for x in b)
    assert all(x["uklad"] in ed.TYPO_UKLADY and x["uklad"] != "za" for x in b)   # „za” tylko z maską osoby
    assert all(w["t"] <= w["k"] <= x["end"] - x["start"] + 1e-6 for x in b for w in x["slowa"])


def test_plan_rozmaitosc_ukladow_i_wyjscia():
    p, _ = plan()
    u = [x["uklad"] for x in p["bloki"]]
    assert len(set(u)) >= 3
    assert not any(a == b == c for a, b, c in zip(u, u[1:], u[2:]))
    ciagla = [x for x, y in zip(p["bloki"], p["bloki"][1:]) if y["start"] - x["end"] < 0.1]
    assert ciagla and all(x["wyjscie"] == "ciecie" for x in ciagla)   # ciągła mowa: twarde cięcie, bez zjadania słowa


def test_plan_ten_sam_dla_tego_samego_ziarna():
    assert plan()[0] == plan()[0]
    slowa = mowa("raz dwa trzy cztery pięć sześć siedem osiem dziewięć dziesięć jedenaście dwanaście")
    a = ty.zbuduj_plan(slowa, [], 1080, 1920, 6, ziarno=1)
    b = ty.zbuduj_plan(slowa, [], 1080, 1920, 6, ziarno=2)
    assert [x["uklad"] for x in a["bloki"]] != [x["uklad"] for x in b["bloki"]] or a == b


def test_plan_poziomy_kadr_nizej_i_wezej():
    p, _ = plan(W=1920, H=1080)
    assert all(x["y"] >= 0.6 and x["w"] <= 0.6 for x in p["bloki"])


def test_chwile_arkusza_przed_wyjsciem_i_po_ostatnim_slowie():
    p, _ = plan()
    t = ty.chwile_arkusza(p, 50)
    for b, c in zip(p["bloki"], t):
        assert b["start"] + b["slowa"][-1]["t"] <= c + 1e-6 <= b["end"]
    assert len(ty.chwile_arkusza(p, 3)) == 3


# ---------------------------------------------------------------- poprawki reżyserskie (popraw)

def test_zastosuj_pola_bloku_i_slowa():
    p, total = plan()
    nowy, uwagi = ty.zastosuj(p, {"motyw": "ulica", "akcent": "#2ECC40", "bloki": [
        {"blok": "b02", "uklad": "skos", "rot": -8, "warstwa": "tyl",
         "slowa": {"0": {"tekst": "NIE", "kolor": "#FFFFFF", "waga": 3, "kroj": "playfairI", "styl": "3d"}}},
        {"blok": "b99", "uklad": "3d"}]}, total)
    b = next(x for x in nowy["bloki"] if x["id"] == "b02")
    assert (nowy["motyw"], nowy["akcent"], b["uklad"], b["rot"], b["warstwa"]) == ("ulica", "#2ECC40", "skos", -8, "tyl")
    assert b["slowa"][0] | {"t": 0, "k": 0, "linia": 0} == {"t": 0, "k": 0, "linia": 0, "tekst": "NIE", "kolor": "#FFFFFF",
                                                            "waga": 3, "kroj": "playfairI", "styl": "3d"}
    assert any("b99" in u for u in uwagi)
    assert p["motyw"] == "kino"                      # wejście bez zmian (kopia)


def test_zastosuj_polacz_podziel_usun_i_ostrzezenie():
    p, total = plan()
    b1, b2 = p["bloki"][1], p["bloki"][2]
    n1, n2 = len(b1["slowa"]), len(b2["slowa"])
    nowy, _ = ty.zastosuj(p, {"bloki": [{"polacz": [b2["id"], b1["id"]]}]}, total)
    m = next(x for x in nowy["bloki"] if x["id"] == b1["id"])
    assert len(m["slowa"]) == n1 + n2 and m["end"] == b2["end"]
    assert m["slowa"][n1]["t"] == pytest.approx(b2["start"] - b1["start"], abs=0.002)
    assert all(x["id"] != b2["id"] for x in nowy["bloki"])

    nowy, uwagi = ty.zastosuj(p, {"bloki": [{"blok": b1["id"], "podziel": 1}]}, total)
    a = next(x for x in nowy["bloki"] if x["id"] == b1["id"])
    c = next(x for x in nowy["bloki"] if x["id"] == b1["id"] + "b")
    assert len(a["slowa"]) == 1 and len(c["slowa"]) == n1 - 1 and a["end"] <= c["start"]
    assert c["slowa"][0]["t"] == 0 and c["slowa"][0]["linia"] == 0
    assert c["start"] == pytest.approx(b1["start"] + b1["slowa"][1]["t"], abs=0.002)
    _, uwagi = ty.zastosuj(p, {"bloki": [{"blok": b1["id"], "podziel": 0}, {"polacz": ["b01"]}]}, total)
    assert len(uwagi) == 2

    nowy, uwagi = ty.zastosuj(p, {"bloki": [{"blok": "b01", "usun": True},
                                            {"blok": "b03", "slowa": {"0": {"waga": 3}, "1": {"waga": 3}}}]}, total)
    assert all(x["id"] != "b01" for x in nowy["bloki"])
    assert any("jedno uderzenie" in u for u in uwagi)


# ---------------------------------------------------------------- plan w projekcie (edytor.py)

def test_normalize_typo_zakresy_i_nieznane_wartosci():
    raw = {"motyw": "disco", "akcent": "red", "bloki": [
        {"id": "b2", "start": 3, "end": 2.5, "slowa": [{"tekst": "x"}]},           # za krótki: wypada
        {"id": "b1", "start": -1, "end": 99, "uklad": "spirala", "x": 7, "y": -2, "w": 0.01, "rot": 90, "tilt": -90,
         "rozmiar": 9, "warstwa": "gdzies", "wejscie": "wybuch", "wyjscie": "smuga",
         "slowa": [{"tekst": "  Ąę " + "x" * 60, "waga": 7, "t": -1, "k": 0.5, "glebia": 2, "kolor": "#12345G",
                    "kroj": "comic", "styl": "3d", "wielkie": "tak", "skala": 10}, {"tekst": "  "}, "zle"]},
        "zle", {"slowa": "x"}]}
    p = ed.normalize_typo(raw, 10)
    assert p == {"motyw": "czysty", "bloki": [
        {"id": "b1", "start": 0, "end": 10, "uklad": "kolumna", "x": 1, "y": 0, "w": 0.15, "rot": 45, "tilt": -45,
         "rozmiar": 3, "warstwa": "przod", "wyjscie": "smuga",
         "slowa": [{"t": 0, "k": 0.5, "tekst": ("Ąę " + "x" * 60)[:40], "waga": 3, "linia": 0, "styl": "3d", "skala": 3}]}]}
    assert ed.normalize_typo(None, 5) == {"motyw": "czysty", "bloki": []}


def test_typo_concat_lista_demuxera(tmp_path):
    blank, png = tmp_path / "pusty.png", tmp_path / "k.png"
    assert ed.typo_concat([(1.0, None), (2.0, None)], blank, tmp_path / "x.ffconcat") is None
    d = ed.typo_concat([(0.5, None), (0.0001, png), (0.04, png), (1.0, None)], blank, tmp_path / "x.ffconcat")
    lines = d.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "ffconcat version 1.0"
    assert lines[1:] == [f"file '{blank}'", "duration 0.5000", f"file '{png}'", "duration 0.0400",
                         f"file '{blank}'", "duration 1.0000", f"file '{blank}'"]


def _png_rgba(path: Path, w: int, h: int, rgba: tuple[int, int, int, int]) -> Path:
    row = b"\x00" + bytes(rgba) * w
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(row * h)) + chunk(b"IEND", b""))
    return path


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_eksport_z_warstwa_typografii(tmp_path):
    """Warstwa z concat: czerwona klatka tylko w 2. sekundzie, reszta przezroczysta (film zostaje niebieski)."""
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=160x90:r=25:d=3",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    p = ed.normalize({"canvas": {"w": 160, "h": 90, "fps": 25}, "clips": [{"src": str(src), "in": 0, "out": 3}],
                      "texts": [], "audio": []}, lambda raw: Path(raw) if Path(raw) == src else None)
    assert p["typo"] == {"motyw": "czysty", "bloki": []}         # projekt bez planu: pusta typografia
    blank = ed.blank_png(tmp_path / "pusty.png", 160, 90)
    red = _png_rgba(tmp_path / "r.png", 160, 90, (255, 0, 0, 255))
    lista = ed.typo_concat([(1.0, None), (1.0, red), (1.0, None)], blank, tmp_path / "przod.ffconcat")
    out = tmp_path / "o.mp4"
    cmd = ed.build_command(p, {str(src): False}, [], out, typo={"przod": lista})
    assert "-reinit_filter" in cmd and str(lista) in cmd
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    def kolor(t):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-vf",
                              "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return tuple(raw[:3])
    assert kolor(0.5)[2] > 150 and kolor(0.5)[0] < 80
    assert kolor(1.5)[0] > 150 and kolor(1.5)[2] < 80
    assert kolor(2.5)[2] > 150


# ---------------------------------------------------------------- renderer JS (ten sam w edytorze i w renderze)

def test_js_i_python_te_same_listy():
    m = re.search(r"const TYPO_MOTYWY = \{(.*?)\n\};", JS, re.S).group(1)
    assert tuple(re.findall(r"^  (\w+): \{", m, re.M)) == ed.TYPO_MOTYWY
    assert dict(zip(ed.TYPO_MOTYWY, map(int, re.findall(r"skos: (\d+)", m)))) == ty.SKOS
    assert tuple(json.loads(re.search(r"const TYPO_UKLADY = (\[.*?\]);", JS).group(1))) == ed.TYPO_UKLADY
    assert tuple(json.loads(re.search(r"const TYPO_STYLE = (\[.*?\]);", JS).group(1))) == ed.TYPO_STYLE
    wej = re.search(r"const TYPO_WEJSCIA = \{(.*?)\};", JS).group(1)
    assert tuple(re.findall(r"(\w+):", wej)) == ed.TYPO_WEJSCIA
    wyj = dict((k, float(v)) for k, v in re.findall(r"(\w+): ([\d.]+)", re.search(r"const TYPO_WYJSCIA = \{(.*?)\};", JS).group(1)))
    assert tuple(wyj) == ed.TYPO_WYJSCIA and wyj == ty.WYJSCIE_CZAS
    kroje = re.search(r"const TYPO_KROJE = \{(.*?)\n\};", JS, re.S).group(1)
    assert tuple(re.findall(r"^  (\w+): \[", kroje, re.M)) == ed.TYPO_KROJE
    for motyw in ed.TYPO_MOTYWY:                     # motywy wskazują kroje, które istnieją
        blok = re.search(rf"^  {motyw}: \{{(.*?)\}},?$", m, re.S | re.M).group(1)
        for k in re.findall(r"(?:kroj|maly|drugi): \"(\w+)\"", blok):
            assert k in ed.TYPO_KROJE, (motyw, k)


def node(prog: str):
    r = subprocess.run(["node", "-e", JS + "\n" + prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_js_odcinki_eksportu_po_kolei_i_tylko_zmiany():
    P = {"typo": {"motyw": "czysty", "bloki": [
        {"id": "b1", "start": 0.5, "end": 1.5, "uklad": "kolumna", "warstwa": "przod", "wyjscie": "ciecie",
         "slowa": [{"t": 0, "k": 0.3, "tekst": "raz", "waga": 1, "linia": 0}, {"t": 0.5, "k": 0.8, "tekst": "dwa", "waga": 3, "linia": 1}]},
        {"id": "b2", "start": 2.0, "end": 2.6, "uklad": "za", "warstwa": "tyl", "wejscie": "ciecie", "wyjscie": "ciecie",
         "slowa": [{"t": 0, "k": 0.4, "tekst": "TYŁ", "waga": 3, "linia": 0}]}]}}
    o = node(f"const P = {json.dumps(P)};\nconsole.log(JSON.stringify({{przod: typoOdcinki(P, 10, 3, 'przod'), "
             f"tyl: typoOdcinki(P, 10, 3, 'tyl'), pusto: typoPodpis(P, 0.2), aktywne: typoAktywne(P, 1.1).map(b => b.id)}}));")
    for segs in (o["przod"], o["tyl"]):
        assert segs[0]["od"] == 0 and segs[-1]["do"] == 30
        assert all(a["do"] == b["od"] and a["podpis"] != b["podpis"] for a, b in zip(segs, segs[1:]))
    assert o["pusto"] == "" and o["aktywne"] == ["b1"]
    przod = [s for s in o["przod"] if s["podpis"]]
    assert przod[0]["od"] == 5 and przod[-1]["do"] == 15           # blok 0,5–1,5 s przy 10 kl./s
    assert len(przod) < 15                                         # klatki stałe łączą się w odcinki
    assert [s for s in o["tyl"] if s["podpis"]] == [{"od": 20, "do": 26, "podpis": "b2:F:0"}]


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_js_uklad_wypelnia_szerokosc_i_uderzenie_najwieksze():
    ctx = ("const ctx = { font: '', measureText(t) { const px = parseFloat(this.font.match(/([\\d.]+)px/)[1]); "
           "return { width: Array.from(t).length * px * 0.55 }; } };")
    b = {"id": "b1", "start": 0, "end": 2, "uklad": "kolumna", "x": 0.5, "y": 0.6, "w": 0.7,
         "slowa": [{"t": 0, "tekst": "tylko", "waga": 0, "linia": 0}, {"t": 0.3, "tekst": "dziś", "waga": 1, "linia": 0},
                   {"t": 0.6, "tekst": "taniej", "waga": 3, "linia": 1}]}
    dlugi = {**b, "slowa": [{"t": i * 0.1, "tekst": "bardzodlugiesłowo" * 2, "waga": 2, "linia": i} for i in range(6)]}
    o = node(ctx + f"\nconst P = {{typo: {{motyw: 'czysty'}}}};\nconst u = typoUklad(ctx, {json.dumps(b)}, P, 1080, 1920);"
             f"\nconst d = typoUklad(ctx, {json.dumps(dlugi)}, P, 1080, 1920);"
             "\nconsole.log(JSON.stringify({w: u.w, px: u.slowa.map(s => s.px), kolor: u.slowa.map(s => typoSlowo(s.src, typoMotyw(P), 'kolumna').kolor), "
             "dw: d.w, dh: d.h}));")
    assert o["w"] == pytest.approx(0.7 * 1080, rel=0.02)           # blok z uderzeniem wypełnia szerokość bloku
    assert o["px"][2] > o["px"][1] > o["px"][0]
    assert o["kolor"] == ["#FFFFFF", "#FFFFFF", "#FFD400"]         # akcent tylko na uderzeniu
    assert o["dw"] <= 0.7 * 1080 + 1 and o["dh"] <= 0.3 * 1920 * 1.01   # długi blok: w szerokości i limicie wysokości


# ---------------------------------------------------------------- przyjęcie klatek z edytora (plugin_api)

def test_klatki_typografii_z_przegladarki(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import base64
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from conftest import load_script
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_typo_test")
    png = "data:image/png;base64," + base64.b64encode(_png_rgba(tmp_path / "k.png", 4, 4, (255, 0, 0, 255)).read_bytes()).decode()
    webp = "data:image/webp;base64," + base64.b64encode(b"RIFF\x10\x00\x00\x00WEBPVP8L" + b"\x00" * 8).decode()
    proj = {"canvas": {"w": 4, "h": 4, "fps": 10}, "duration": 2.0}
    out = api._typo_warstwy({"przod": [[0, 5, None], [5, 6, png], [6, 7, webp], [7, 20, None]]}, proj, tmp_path)
    lista = out["przod"].read_text(encoding="utf-8")
    assert "typo-przod-00001.png" in lista and "typo-przod-00002.webp" in lista and "duration 1.3000" in lista
    assert api._typo_warstwy(None, proj, tmp_path) == {} and api._typo_warstwy({"tyl": []}, proj, tmp_path) == {}
    for zle in ([[0, 5, None], [6, 7, png]],                     # dziura w osi
                [[0, 30, png]],                                  # poza filmem
                [[0, 1, "data:image/gif;base64,R0lG"]],          # nie PNG / WebP
                [[0, 1, "data:image/webp;base64," + base64.b64encode(b"GIF89a").decode()]],   # nagłówek kłamie
                [[0, 1, None, 1]]):                              # zły odcinek
        with pytest.raises(api.ed.ProjectError):
            api._typo_warstwy({"przod": zle}, proj, tmp_path)


def test_build_kopiuje_renderer_obok_skryptow():
    """Wideograf renderuje typografię tym samym plikiem co edytor: build kopiuje go jako edytor_typografia.js."""
    build = (ROOT / "scripts" / "build.py").read_text(encoding="utf-8")
    assert '"48-typografia.js", dest / "scripts" / "edytor_typografia.js"' in build
    assert ty.TYPO_JS is not None and ty.TYPO_JS.name in ("edytor_typografia.js", "48-typografia.js")
    assert ty.pr.TYPO_JS is not None

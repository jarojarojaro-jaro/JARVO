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


def _ma_webp() -> bool:
    if not HAS_FF:
        return False
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return "libwebp" in r.stdout


@pytest.mark.skipif(not _ma_webp(), reason="brak ffmpeg z libwebp")
def test_eksport_warstwa_webp_z_pusta_webp(tmp_path):
    """Edytor wysyła klatki WebP i pustą klatkę WebP: lista concat w jednym formacie, warstwa jest w filmie."""
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=160x90:r=25:d=3",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    p = ed.normalize({"canvas": {"w": 160, "h": 90, "fps": 25}, "clips": [{"src": str(src), "in": 0, "out": 3}],
                      "texts": [], "audio": []}, lambda raw: Path(raw) if Path(raw) == src else None)

    def webp(kolor: str, dest: Path) -> Path:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color={kolor}:s=160x90,format=rgba",
                        "-frames:v", "1", "-c:v", "libwebp", "-lossless", "1", str(dest)], check=True)
        return dest
    lista = ed.typo_concat([(1.0, None), (1.0, webp("red", tmp_path / "r.webp")), (1.0, None)],
                           webp("black@0.0", tmp_path / "pusty.webp"), tmp_path / "przod.ffconcat")
    out = tmp_path / "o.mp4"
    r = subprocess.run(ed.build_command(p, {str(src): False}, [], out, typo={"przod": lista}), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    def kolor(t):
        return tuple(subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-vf",
                                     "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True,
                                    check=True).stdout[:3])
    assert kolor(0.5)[2] > 150 and kolor(1.5)[0] > 150 and kolor(1.5)[2] < 80 and kolor(2.5)[2] > 150


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
    out = api._typo_warstwy({"przod": [[0, 5, None], [5, 6, png], [6, 20, None]]}, proj, tmp_path)
    lista = out["przod"].read_text(encoding="utf-8")
    assert "typo-przod-00001.png" in lista and "typo-pusty.png" in lista and "duration 1.4000" in lista
    out = api._typo_warstwy({"tyl": [[0, 5, None], [5, 6, webp], [6, 20, None]], "przod": [[0, 20, webp]], "pusty": webp},
                            proj, tmp_path)                        # WebP z edytora: pusta klatka też WebP
    lista = out["tyl"].read_text(encoding="utf-8")
    assert "typo-tyl-00001.webp" in lista and "typo-pusty.webp" in lista and "typo-pusty.png" not in lista
    assert "typo-przod-00000.webp" in out["przod"].read_text(encoding="utf-8")
    assert api._typo_warstwy(None, proj, tmp_path) == {} and api._typo_warstwy({"tyl": []}, proj, tmp_path) == {}
    for mieszane in ({"przod": [[0, 5, None], [5, 6, webp], [6, 20, None]]},          # WebP z pustą PNG: concat gubi warstwę
                     {"przod": [[0, 5, png], [5, 6, webp], [6, 20, None]], "pusty": webp},
                     {"przod": [[0, 20, png]], "pusty": webp}):
        with pytest.raises(api.ed.ProjectError, match="różnych formatach"):
            api._typo_warstwy(mieszane, proj, tmp_path)
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


# ---------------------------------------------------------------- maska osoby: napis za osobą (maska.py, MODNet)

def blok(slowa: list[tuple[str, int]], start: float = 1.0, krok: float = 0.4, dl: float | None = None) -> dict:
    """Blok planu: słowa co `krok` s, koniec po ostatnim + 0,35 s (albo `dl`)."""
    s = [{"t": round(i * krok, 3), "k": round(i * krok + 0.3, 3), "tekst": t, "waga": w, "linia": 0}
         for i, (t, w) in enumerate(slowa)]
    return {"id": "b05", "start": start, "end": round(start + (dl or len(s) * krok + 0.35), 3), "uklad": "kolumna",
            "x": 0.46, "y": 0.64, "w": 0.7, "rot": 3.0, "tilt": 0.0, "warstwa": "przod", "wyjscie": "zanik", "slowa": s}


GLOWA = {"osoba": [0.3, 0.3, 0.7, 1.0], "glowa": [0.4, 0.3, 0.6, 0.5], "pokrycie": 0.3}


def test_czesc_za_uderzenie_z_jednostka_i_malymi_slowami():
    assert ty.czesc_za(blok([("w", 0), ("pięć", 3), ("minut", 2)])) == (0, 3)              # „W PIĘĆ MINUT” całe
    assert ty.czesc_za(blok([("Wstań", 1), ("co", 0), ("trzydzieści", 3), ("minut", 2)])) == (1, 3)  # jednostka za długa
    assert ty.czesc_za(blok([("W", 0), ("przyszłym", 3), ("tygodniu", 2), ("pokażę", 2)])) == (0, 2)
    assert ty.czesc_za(blok([("bez", 1), ("uderzenia", 2)])) is None
    assert ty.czesc_za(blok([("Konstantynopolitańczykowianeczka", 3)])) is None               # nie zmieści się
    assert ty.czesc_za(blok([("dziś", 1), ("TANIEJ", 3)], krok=0.2)) is None                  # „dziś” nie do przeczytania
    assert ty.czesc_za(blok([("TANIEJ", 3)], dl=0.4)) is None                                 # za krótko za osobą


def test_za_osoba_glowa_wyrazna_i_napis_czytelny():
    b = blok([("w", 0), ("pięć", 3), ("minut", 2)])
    assert ty.za_osoba(b, GLOWA, 1080, 1920)
    assert not ty.za_osoba(b, {**GLOWA, "glowa": [0.1, 0.3, 0.9, 0.6]}, 1080, 1920)          # zbliżenie: głowa na pół kadru
    assert not ty.za_osoba(b, {**GLOWA, "glowa": [0.4, 0.05, 0.6, 0.3]}, 1080, 1920)         # nad głową brak miejsca
    assert not ty.za_osoba(b, {**GLOWA, "pokrycie": 0.9}, 1080, 1920)
    assert not ty.za_osoba(b, {"osoba": None, "glowa": None, "pokrycie": 0}, 1080, 1920)
    assert not ty.za_osoba(blok([("bez", 1), ("uderzenia", 2)]), GLOWA, 1080, 1920)


def test_wydziel_za_czesci_po_kolei_osoba_przed_uderzeniem():
    b = blok([("Wstań", 1), ("co", 0), ("trzydzieści", 3), ("minut", 2)], krok=0.5)
    przed, za, po = ty.wydziel_za(b, 1, 3, GLOWA["glowa"], 1080, 1920)
    assert [c["id"] for c in (przed, za, po)] == ["b05", "b05b", "b05c"]
    assert [w["tekst"] for w in przed["slowa"]] == ["Wstań"] and przed["wyjscie"] == "ciecie"
    assert przed["end"] < za["start"] == pytest.approx(1.5) and za["end"] == po["end"] == b["end"]   # uderzenie do końca frazy
    assert po["start"] == pytest.approx(2.5) and po["slowa"][0]["t"] == 0 and za["slowa"][0]["t"] == 0
    assert za["warstwa"] == "tyl" and za["uklad"] == "za" and za["rot"] == 0
    assert {w["linia"] for w in za["slowa"]} == {0} and all("glebia" not in w for w in za["slowa"])
    assert za["x"] == pytest.approx(0.5) and za["w"] <= 0.94 and 0.3 - 0.01 <= za["y"] <= 0.5     # nad środkiem głowy
    assert po["warstwa"] == przed["warstwa"] == "przod" and po["y"] > za["y"]                     # reszta pod napisem
    bok = ty.wydziel_za(b, 1, 3, [0.78, 0.3, 0.9, 0.45], 1080, 1920)[1]
    assert bok["x"] == 0.7 and bok["x"] + bok["w"] / 2 <= 0.98                                    # głowa z boku: napis w kadrze


def test_uloz_z_maska_omija_twarz_i_za_osoba_rzadko():
    slowa = [("w", 0), ("pięć", 3), ("minut", 2)]
    bloki = [{**blok(slowa if i % 2 == 0 else [("tylko", 1), ("dziś", 2)], start=i * 2.0), "id": f"b{i + 1:02d}"}
             for i in range(8)]
    plan = ed.normalize_typo({"motyw": "kino", "bloki": bloki}, 20)
    srodek = lambda b: round((b["start"] + b["end"]) / 2, 3)  # noqa: E731
    twarz = {"osoba": [0.25, 0.4, 0.75, 1.0], "glowa": [0.38, 0.4, 0.62, 0.62], "pokrycie": 0.3}
    opisy = [{"t": srodek(b), **(twarz if i != 7 else {"osoba": None, "glowa": None, "pokrycie": 0})}
             for i, b in enumerate(plan["bloki"])]
    nowy = ty.uloz_z_maska(plan, opisy, 1080, 1920, 20)
    za = [b for b in nowy["bloki"] if b["warstwa"] == "tyl"]
    assert 1 <= len(za) <= round(8 / 6)                                   # najwyżej co szósty blok
    for b in nowy["bloki"]:
        if b["warstwa"] == "przod" and b["id"] != "b08":
            bw, bh = ty.rozmiar_bloku(b, b["w"], 1080, 1920)
            r = [b["x"] - bw / 2, b["y"] - bh / 2, b["x"] + bw / 2, b["y"] + bh / 2]
            assert ty._wspolne(r, twarz["glowa"]) < 0.25 * ty._pole(twarz["glowa"]), b   # nie na twarzy
            assert r[1] >= 0.13 and r[3] <= 0.81                                          # strefa bezpieczna pionu
    b08 = next(b for b in nowy["bloki"] if b["id"] == "b08")
    assert (b08["x"], b08["y"]) == (plan["bloki"][7]["x"], plan["bloki"][7]["y"])        # bez osoby: miejsce zwykłe
    bez = ty.uloz_z_maska(plan, [{"t": srodek(b), "osoba": None, "glowa": None, "pokrycie": 0} for b in plan["bloki"]],
                          1080, 1920, 20)
    assert bez == plan


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_maska_klucz_ten_sam_w_js_i_pythonie():
    projekty = [
        {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "clips": [
            {"src": "/a/b.mp4", "in": 1.2, "out": 5, "speed": 1.5, "fit": "cover", "fx": 0.3, "fy": 0.61, "zoom": 1.25},
            {"src": "/a/c.mp4", "in": 0, "out": 2.0004, "fit": "blur"}, {"src": "/a/d.png", "in": 0, "out": 3}]},
        {"canvas": {"w": 1920.0, "h": 1080, "fps": 29.97}, "clips": [{"src": "x.mp4", "out": "4", "speed": None, "fit": "zle"}]},
        {"clips": []},
    ]
    js = node(f"console.log(JSON.stringify({json.dumps(projekty)}.map(maskaKlucz)));")
    assert js == [ed.maska_klucz(p) for p in projekty]
    assert ed.maska_klucz(projekty[0]) != ed.maska_klucz({**projekty[0], "clips": projekty[0]["clips"][:2]})


def _maska_film(tmp_path: Path, n: int, w: int = 32, h: int = 18, klatki=None):
    """Film 160×90 (2 s, 25 kl./s), projekt i sylwetki: lewa połowa kadru to „osoba” (alfa 255), prawa tło."""
    src = tmp_path / "workspaces" / "film.mp4"
    src.parent.mkdir(parents=True, exist_ok=True)
    raw = {"canvas": {"w": 160, "h": 90, "fps": 25}, "clips": [{"src": str(src), "in": 0, "out": 2}], "texts": [],
           "audio": [], "typo": {"bloki": [{"id": "b1", "start": 0.4, "end": 1.6, "uklad": "za", "warstwa": "tyl",
                                            "slowa": [{"t": 0, "k": 0.3, "tekst": "ZA", "waga": 3, "linia": 0}]}]}}
    d = ed.maska_dir(src)
    d.mkdir()
    row = b"\x00" + bytes((255, 255, 255, 255)) * (w // 2) + bytes((255, 255, 255, 0)) * (w - w // 2)
    chunk = lambda t, x: struct.pack(">I", len(x)) + t + x + struct.pack(">I", zlib.crc32(t + x) & 0xFFFFFFFF)  # noqa: E731
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(row * h)) + chunk(b"IEND", b""))
    klatki = list(range(n)) if klatki is None else klatki
    for k in klatki:
        (d / f"k{k:06d}.png").write_bytes(png)
    (d / "indeks.json").write_text(json.dumps({"klucz": ed.maska_klucz(raw), "fps": 25, "w": w, "h": h,
                                               "klatki": klatki}), encoding="utf-8")
    return src, raw


def test_maska_concat_tylko_bloki_za_osoba_i_aktualna_os(tmp_path):
    src, raw = _maska_film(tmp_path, 50, klatki=list(range(10, 41)))
    p = {**raw, "duration": 2.0, "typo": ed.normalize_typo(raw["typo"], 2.0)}
    lista = ed.maska_concat(src, raw, p, tmp_path)
    lines = lista.read_text(encoding="utf-8").splitlines()
    pliki = [x for x in lines if x.startswith("file")]
    assert pliki[0].endswith("maska-pusta.png'") and "k000010.png" in pliki[1] and "k000040.png" in pliki[-3]
    czas = sum(float(x.split()[1]) for x in lines if x.startswith("duration"))
    assert czas == pytest.approx(2.0, abs=0.001)
    assert lines[2] == "duration 0.4000"                                   # do bloku za osobą: pusta klatka
    inna_os = {**raw, "clips": [{**raw["clips"][0], "out": 1.9}]}          # zmiana klipów: sylwetki nie pasują
    assert ed.maska_concat(src, inna_os, p, tmp_path) is None
    assert ed.maska_concat(src, raw, {**p, "typo": {"bloki": []}}, tmp_path) is None
    assert ed.maska_indeks(src, {**raw, "canvas": {**raw["canvas"], "fps": 30}}) is None


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_eksport_osoba_przed_napisem_za_nia(tmp_path):
    """Blok „tyl” (czerwony na cały kadr) i sylwetka na lewej połowie: po lewej film (osoba przed napisem),
    po prawej napis; bez sylwetek cały kadr czerwony."""
    src, raw = _maska_film(tmp_path, 50)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=160x90:r=25:d=2",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    p = ed.normalize(raw, lambda r: Path(r) if Path(r) == src else None)
    blank = ed.blank_png(tmp_path / "pusty.png", 160, 90)
    red = _png_rgba(tmp_path / "r.png", 160, 90, (255, 0, 0, 255))
    tyl = ed.typo_concat([(0.4, None), (1.2, red), (0.4, None)], blank, tmp_path / "tyl.ffconcat")
    maska = ed.maska_concat(src, raw, p, tmp_path)
    assert maska is not None

    def kolory(out: Path, t: float):
        def kolor(x: int):
            return tuple(subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                                         "-vf", f"crop=20:20:{x}:35,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                        capture_output=True, check=True).stdout[:3])
        return kolor(20), kolor(120)                                       # środek lewej i prawej połowy

    out = tmp_path / "o.mp4"
    cmd = ed.build_command(p, {str(src): False}, [], out, typo={"tyl": tyl}, maska=maska)
    assert any("alphamerge" in x for x in cmd)
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    lewa, prawa = kolory(out, 1.0)
    assert lewa[2] > 150 and lewa[0] < 80                                  # osoba (film) przed napisem
    assert prawa[0] > 150 and prawa[2] < 80                                # napis za osobą widać obok
    assert kolory(out, 0.2)[1][2] > 150                                    # przed blokiem: sam film
    bez = tmp_path / "bez.mp4"
    subprocess.run(ed.build_command(p, {str(src): False}, [], bez, typo={"tyl": tyl}), check=True, capture_output=True)
    assert kolory(bez, 1.0)[0][0] > 150                                    # bez sylwetek napis zasłania wszystko


def test_edit_maska_indeks_dla_edytora(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import asyncio
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from conftest import load_script
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_maska_test")
    src, raw = _maska_film(tmp_path, 3)
    src.write_bytes(b"\x00")
    monkeypatch.setattr(api.ROOTS, "jarvo_dir", tmp_path)
    o = asyncio.run(api.edit_maska(str(src)))
    assert o == {"dir": str(ed.maska_dir(src)), "klucz": ed.maska_klucz(raw), "fps": 25, "klatki": [0, 1, 2]}
    (ed.maska_dir(src) / "indeks.json").unlink()
    assert asyncio.run(api.edit_maska(str(src))) == {}
    with pytest.raises(api.HTTPException):
        asyncio.run(api.edit_maska(str(tmp_path.parent / "poza.mp4")))


# ---------------------------------------------------------------- maska.py (bez modelu: kształt danych)

_mspec = importlib.util.spec_from_file_location("maska", SCRIPTS / "maska.py")
ma = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(ma)


def test_maska_rozmiar_i_dopasowanie_jak_eksport():
    assert ma.rozmiar(1080, 1920) == (288, 512) and ma.rozmiar(1920, 1080) == (512, 288)
    assert all(v % 32 == 0 for v in ma.rozmiar(1000, 1000))
    assert ma.dopasowanie({"fit": "cover", "fx": 0.3}, 288, 512) == ed.cover_filter(288, 512, {"zoom": 1, "fx": 0.3, "fy": 0.5, "fit": "cover"})
    assert ma.dopasowanie({}, 288, 512).startswith("scale=288:512:force_original_aspect_ratio=decrease,pad=288:512")
    assert ma.MODEL_URL.startswith("https://huggingface.co/") and re.fullmatch(r"[0-9a-f]{64}", ma.MODEL_SHA256)
    assert "/resolve/903cc06311b3b12071edfa1b42b534e4a31c718a/" in ma.MODEL_URL           # przypięta wersja, nie main


def test_maska_opis_glowy_bez_reki_i_png_z_alfa(tmp_path):
    np = pytest.importorskip("numpy")
    a = np.zeros((100, 60), dtype=np.float32)
    a[20:40, 25:35] = 1.0                       # głowa
    a[40:100, 12:48] = 1.0                      # ramiona i tułów
    a[22:30, 45:50] = 1.0                       # uniesiona dłoń obok głowy
    o = ma.opis_alfy(a)
    assert o["osoba"] == [0.2, 0.2, 0.833, 1.0]
    g = o["glowa"]
    assert g[0] == pytest.approx(25 / 60, abs=0.02) and g[2] == pytest.approx(35 / 60, abs=0.02)   # dłoń nie poszerza głowy
    assert g[1] == 0.2 and 0.35 <= g[3] <= 0.45
    assert ma.opis_alfy(np.zeros((10, 10)))["osoba"] is None
    p = ma.png_alfa(a, tmp_path / "k.png")
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", b[16:24]) == (60, 100) and b[25] == 6   # RGBA
    dane = zlib.decompress(b[b.index(b"IDAT") + 4:b.index(b"IEND") - 8])
    assert len(dane) == 100 * (1 + 60 * 4) and dane[30 * 241 + 1 + 30 * 4 + 3] == 255 and dane[1 + 3] == 0

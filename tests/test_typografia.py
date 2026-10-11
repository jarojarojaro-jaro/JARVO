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
    assert p["odstep"] == "tusz"                    # nowy plan: linie bloku bez stykania liter
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
    assert ed.normalize_typo({"odstep": "tusz"}, 5)["odstep"] == "tusz"
    assert "odstep" not in ed.normalize_typo({"odstep": "ciasno"}, 5)     # stary plan bez pola: układ jak dawniej


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
    assert tuple(ty.MOTYW_CECHY) == ed.TYPO_MOTYWY
    for motyw, cechy in ty.MOTYW_CECHY.items():      # wyjście motywu, styl słów i uderzenia jak w rendererze
        blok = re.search(rf"^  {motyw}: \{{(.*?)\}},?$", m, re.S | re.M).group(1)
        pole = lambda k, d=None: (re.findall(rf"\b{k}: \"(\w+)\"", blok) or [d])[0]  # noqa: E731
        assert (pole("wyjscie"), pole("styl", "wypelnij"), pole("hit")) == (cechy["ciecie"], cechy["styl"], cechy["hit"]), motyw
        assert {cechy["styl"], cechy["hit"]} <= set(ed.TYPO_STYLE) and {cechy["ciecie"], cechy["zwykle"]} <= set(ed.TYPO_WYJSCIA)
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


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_js_odstep_z_tuszu_male_slowo_nad_duzym():
    """„the / WAY”: małe słowo nad uderzeniem. Plan z odstep=tusz rozsuwa linie, aż tusz liter dzieli co najmniej
    12% mniejszego słowa; plan bez pola (stare filmy) zostaje piksel w piksel jak dawniej."""
    ctx = ("const ctx = { font: '', measureText(t) { const px = parseFloat(this.font.match(/([\\d.]+)px/)[1]); "
           "const ogonek = /[gjpqyĄĘ,]/.test(t) ? 0.24 : 0.02, kreska = /[ŻŹŚĆŃÓ]/.test(t) ? 0.95 : 0.72; "
           "return { width: Array.from(t).length * px * 0.55, actualBoundingBoxAscent: px * kreska, "
           "actualBoundingBoxDescent: px * ogonek }; } };")
    b = {"id": "b1", "start": 0, "end": 2, "uklad": "kolumna", "x": 0.5, "y": 0.6, "w": 0.7,
         "slowa": [{"t": 0, "tekst": "jutro, gdy", "waga": 0, "linia": 0}, {"t": 0.3, "tekst": "ŻÓŁW", "waga": 3, "linia": 1},
                   {"t": 0.6, "tekst": "przyjdzie", "waga": 1, "linia": 2}]}
    js = (ctx + f"\nconst b = {json.dumps(b)};\nconst stary = typoUklad(ctx, b, {{typo: {{motyw: 'plakat'}}}}, 1080, 1920);"
          "\nconst nowy = typoUklad(ctx, b, {typo: {motyw: 'plakat', odstep: 'tusz'}}, 1080, 1920);"
          "\nconst tusz = (u) => u.slowa.map((s) => { ctx.font = typoFont(s.kroj, s.px); const m = ctx.measureText(s.tekst);"
          " return [s.y - m.actualBoundingBoxAscent, s.y + m.actualBoundingBoxDescent, s.px]; });"
          "\nconsole.log(JSON.stringify({stary: tusz(stary), nowy: tusz(nowy), sy: stary.slowa.map(s => [s.x, s.y, s.px]),"
          " h: [stary.h, nowy.h]}));")
    o = node(js)
    (g0, d0, p0), (g1, d1, p1), (g2, d2, p2) = o["stary"]
    assert d0 > g1                                                  # bez zasady: ogonki „jutro, gdy” wchodzą w Ż
    (g0, d0, p0), (g1, d1, p1), (g2, d2, p2) = o["nowy"]
    assert g1 - d0 >= 0.12 * min(p0, p1) - 0.01 and g2 - d1 >= 0.12 * min(p1, p2) - 0.01
    assert o["h"][1] > o["h"][0]                                    # blok trochę wyższy, tylko tyle, ile trzeba
    stary = node(ctx + f"\nconst b = {json.dumps(b)};\nconst u = typoUklad(ctx, b, {{typo: {{motyw: 'plakat'}}}}, 1080, 1920);"
                 "\nconsole.log(JSON.stringify(u.slowa.map(s => [s.x, s.y, s.px])));")
    assert stary == o["sy"]                                         # stare plany: ten sam układ


def test_js_odstep_z_tuszu_slowa_w_linii():
    """„SCROLL a BACK” w jednej linii: pochylony krój wystaje za szerokość słowa, obrys dokłada swoje.
    Z odstep=tusz tusz sąsiednich słów (z obrysem) dzieli co najmniej 12% mniejszego słowa; stare plany bez zmian."""
    ctx = ("const ctx = { font: '', measureText(t) { const px = parseFloat(this.font.match(/([\\d.]+)px/)[1]); "
           "const w = Array.from(t).length * px * 0.55; return { width: w, actualBoundingBoxLeft: px * 0.12, "
           "actualBoundingBoxRight: w + px * 0.2, actualBoundingBoxAscent: px * 0.72, actualBoundingBoxDescent: px * 0.02 }; } };")
    b = {"id": "b1", "start": 0, "end": 2, "uklad": "kolumna", "x": 0.5, "y": 0.5, "w": 0.9,
         "slowa": [{"t": 0, "tekst": "SCROLL", "waga": 3, "linia": 0, "styl": "obrys"},
                   {"t": 0.3, "tekst": "a", "waga": 0, "linia": 0, "styl": "obrys"},
                   {"t": 0.6, "tekst": "BACK", "waga": 3, "linia": 0, "styl": "obrys"}]}
    js = (ctx + f"\nconst b = {json.dumps(b)};"
          "\nconst ink = (u) => u.slowa.map((s) => { ctx.font = typoFont(s.kroj, s.px); const m = ctx.measureText(s.tekst);"
          " return [s.x - m.actualBoundingBoxLeft, s.x + m.actualBoundingBoxRight, s.px]; });"
          "\nconst stary = typoUklad(ctx, b, {typo: {motyw: 'plakat'}}, 1080, 1920);"
          "\nconst nowy = typoUklad(ctx, b, {typo: {motyw: 'plakat', odstep: 'tusz'}}, 1080, 1920);"
          "\nconsole.log(JSON.stringify({stary: ink(stary), nowy: ink(nowy), w: [stary.w, nowy.w]}));")
    o = node(js)
    (l0, r0, p0), (l1, r1, p1), (l2, r2, p2) = o["stary"]
    assert l1 - r0 < 0.12 * min(p0, p1)                             # bez zasady: „a” prawie wchodzi w „SCROLL”
    (l0, r0, p0), (l1, r1, p1), (l2, r2, p2) = o["nowy"]
    halo = 0.09                                                     # obrys po obu stronach
    assert l1 - r0 >= (0.12 + halo) * min(p0, p1) + halo * p0 - 0.01
    assert l2 - r1 >= (0.12 + halo) * min(p1, p2) + halo * p2 - 0.01
    assert o["w"][1] <= 0.9 * 1080 + 0.01                           # dalej mieści się w szerokości bloku

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


def _projekt_typo(tmp_path: Path, bloki: list[dict]) -> Path:
    """Film (pusty plik wystarczy: projekt ma klipy) i projekt z planem typografii, jak po poprawkach w edytorze."""
    src = tmp_path / "film.mp4"
    src.write_bytes(b"")
    raw = {"version": 1, "canvas": {"w": 1080, "h": 1920, "fps": 30}, "texts": [], "audio": [],
           "clips": [{"id": "c1", "src": str(src), "kind": "video", "in": 0, "out": 6, "speed": 1}],
           "typo": {"motyw": "czysty", "bloki": bloki}}
    ed.project_path(src).write_text(json.dumps(raw), encoding="utf-8")
    return src


def test_plan_nie_nadpisuje_planu_z_poprawkami(tmp_path, monkeypatch):
    """Gotowy plan mógł poprawić człowiek w HQ: `plan` odmawia, od nowa tylko z --nowy."""
    src = _projekt_typo(tmp_path, [blok([("Moje", 1), ("POPRAWKI", 3)])])
    przed = ed.project_path(src).read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="--nowy"):
        ty.main(["plan", str(src)])
    assert ed.project_path(src).read_text(encoding="utf-8") == przed
    monkeypatch.setattr(ty, "slowa_osi", lambda proj: ([], []))
    with pytest.raises(SystemExit, match="brak mowy"):          # z --nowy przechodzi dalej (tu: film bez mowy)
        ty.main(["plan", str(src), "--nowy"])


def test_sylwetki_tylko_dla_blokow_za_osoba(tmp_path, monkeypatch, capsys):
    """Blok przestawiony za osobę w edytorze: `sylwetki` liczy maskę tylko dla bloków warstwy „tyl”."""
    przod = blok([("Zwykły", 1)], start=0.5)
    tyl = {**blok([("ZA", 3)], start=2.0), "id": "b2", "uklad": "za", "warstwa": "tyl"}
    src = _projekt_typo(tmp_path, [przod, tyl])
    wolania = []
    monkeypatch.setattr(ty, "maska", lambda film, *args: wolania.append(args) or "ok")
    assert ty.main(["sylwetki", str(src)]) == 0
    assert len(wolania) == 1 and wolania[0][0] == "klatki" and wolania[0][2] == "2.000"
    assert "Sylwetki: 1 z 1" in capsys.readouterr().out
    monkeypatch.setattr(ty, "maska", lambda film, *args: None)   # bez modelu: kod błędu i wyjaśnienie
    assert ty.main(["sylwetki", str(src)]) == 1
    assert "maska niedostępna" in capsys.readouterr().out
    (tmp_path / "bez").mkdir()
    src2 = _projekt_typo(tmp_path / "bez", [przod])
    assert ty.main(["sylwetki", str(src2)]) == 0 and "Brak bloków za osobą" in capsys.readouterr().out


# ---------------------------------------------------------------- paleta z kadru

def klatka(fn, w: int = 54, h: int = 96) -> bytes:
    """Mała klatka RGB z funkcji (x, y w 0–1) → (r, g, b)."""
    return bytes(c for y in range(h) for x in range(w) for c in fn(x / w, y / h))


def plaza(x, y):           # niebo, morze, piasek (jak nagranie z Mikołajem na plaży)
    return (74, 144, 217) if y < 0.45 else (40, 170, 200) if y < 0.6 else (225, 205, 170)


def mikolaj(x, y):         # ta sama plaża z osobą (skóra) i małą czerwoną czapką
    if 0.35 < x < 0.65 and 0.12 < y < 0.17:
        return (200, 20, 30)
    if 0.35 < x < 0.65 and 0.17 < y < 0.75:
        return (205, 150, 120)
    return plaza(x, y)


def barwa(hexa: str) -> int:
    return next(h for h, d, j, _s in ty.KOLORY.values() if hexa.upper() in (d.upper(), j.upper()))


@pytest.mark.parametrize("scena, oczekiwane", [
    (plaza, ["#B3122E", "#A87A12"]),                                   # niebieskie → ciemna czerwień i złoto
    (mikolaj, ["#B3122E", "#A87A12"]),
    (lambda x, y: (60, 140, 50) if y < 0.7 else (90, 70, 40), ["#BE185D", "#6D28D9"]),   # zieleń → róż, fiolet
    (lambda x, y: (190, 30, 40), ["#1D4ED8", "#15803D"]),              # czerwień → niebieski, zieleń
])
def test_paleta_z_kontrastu_ze_scena(scena, oczekiwane):
    assert ty.dobierz_palete(ty.analiza_kadru([klatka(scena)])) == oczekiwane


def test_paleta_dwa_rozne_kolory_i_marka_pierwsza():
    for scena in (plaza, lambda x, y: (128, 128, 125), lambda x, y: (170, 110, 60), lambda x, y: (150, 40, 200)):
        an = ty.analiza_kadru([klatka(scena)])
        a, b = ty.dobierz_palete(an)
        assert ty._barwa_d(barwa(a), barwa(b)) >= ty.PALETA_ROZNICA      # nigdy jeden kolor dwa razy
        m, d = ty.dobierz_palete(an, "#E30613")
        assert m == "#E30613" and ty._barwa_d(barwa(d), 357) >= ty.PALETA_ROZNICA


def test_paleta_nie_bierze_barwy_sceny_ani_skory():
    an = ty.analiza_kadru([klatka(mikolaj)])
    assert an["skora"] > 0.1 and an["barwnosc"] > 0.2
    for k in ty.dobierz_palete(an):
        assert ty._barwa_d(barwa(k), 210) >= 90                         # nie niebieski na niebie
        assert not 12 <= barwa(k) <= 38                                  # nie pomarańczowy przy skórze


def plan_z_uderzeniami(n: int) -> dict:
    return {"motyw": "czysty", "bloki": [
        {"id": f"b{i}", "start": i * 1.0, "end": i * 1.0 + 0.9, "uklad": "kolumna", "x": 0.5, "y": 0.6, "w": 0.7,
         "rot": 0, "tilt": 0, "warstwa": "przod",
         "slowa": [{"t": 0, "k": 0.3, "tekst": "to", "waga": 0, "linia": 0},
                   {"t": 0.3, "k": 0.6, "tekst": f"MOCNE{i}", "waga": 3, "linia": 1}]} for i in range(n)]}


def test_pokoloruj_uderzenia_na_zmiane_i_wariant_z_tla():
    jasne = ty.pokoloruj(plan_z_uderzeniami(5), ["#B3122E", "#A87A12"], {f"b{i}": 0.55 for i in range(5)})
    assert jasne["paleta"] == ["#B3122E", "#A87A12"]                    # jasne niebo: warianty ciemne
    assert [b["slowa"][1]["kolor"] for b in jasne["bloki"]] == ["#B3122E", "#A87A12", "#B3122E", "#A87A12", "#B3122E"]
    assert all("kolor" not in b["slowa"][0] for b in jasne["bloki"])   # małe słowa zostają białe
    ciemne = ty.pokoloruj(plan_z_uderzeniami(3), ["#B3122E", "#A87A12"], {f"b{i}": 0.02 for i in range(3)})
    assert ciemne["paleta"] == ["#FF5A5F", "#F2C94C"]                   # ciemna scena: warianty jasne
    assert not any(w.get("styl") == "tlo" for b in ciemne["bloki"] for w in b["slowa"])


def test_pokoloruj_wazne_slowo_w_co_drugim_bloku_bez_uderzenia():
    plan = plan_z_uderzeniami(5)
    for i in (1, 2, 3):                                                # bloki 1–3 bez uderzenia, z ważnym słowem
        plan["bloki"][i]["slowa"][1]["waga"] = 2
    plan["bloki"][2]["slowa"].append({"t": 0.6, "k": 0.8, "tekst": "najdłuższe", "waga": 2, "linia": 1})
    out = ty.pokoloruj(plan, ["#B3122E", "#A87A12"], {})
    kolory = [[w.get("kolor") for w in b["slowa"]] for b in out["bloki"]]
    assert kolory == [[None, "#B3122E"], [None, "#A87A12"], [None, None, None], [None, "#B3122E"], [None, "#A87A12"]]


def test_pokoloruj_plytka_tylko_przy_slabym_kontrascie_i_nie_rusza_poprawek():
    plan = plan_z_uderzeniami(3)
    plan["bloki"][2]["slowa"][1]["kolor"] = "#FFFFFF"                  # poprawka człowieka zostaje
    out = ty.pokoloruj(plan, ["#B3122E", "#A87A12"], {"b0": 0.12, "b1": 0.6, "b2": 0.6})
    assert out["bloki"][0]["slowa"][1] == {**plan["bloki"][0]["slowa"][1], "kolor": "#B3122E", "plyta": True}
    assert "plyta" not in out["bloki"][1]["slowa"][1] and "styl" not in out["bloki"][1]["slowa"][1]
    assert out["bloki"][2]["slowa"][1]["kolor"] == "#FFFFFF"
    assert ed.normalize_typo(out, 10)["bloki"][0]["slowa"][1]["plyta"] is True     # znacznik przechodzi walidację
    assert "plyta" not in ed.normalize_typo({"bloki": [{**out["bloki"][0], "slowa": [{"tekst": "x", "plyta": "tak"}]}]}, 10)["bloki"][0]["slowa"][0]


def test_zmien_palete_przenosi_slowa_i_normalize_ja_trzyma():
    plan = ty.pokoloruj(plan_z_uderzeniami(3), ["#B3122E", "#A87A12"], {})
    nowy = ty.zmien_palete(plan, ["#1d4ed8", "#A87A12"])
    assert [b["slowa"][1]["kolor"] for b in nowy["bloki"]] == ["#1D4ED8", "#A87A12", "#1D4ED8"]
    norm = ed.normalize_typo({**nowy, "paleta": ["#1d4ed8", "zły", "#A87A12", "#111111", "#222222", "#333333"]}, 10)
    assert norm["paleta"] == ["#1D4ED8", "#A87A12", "#111111", "#222222"]
    assert "paleta" not in ed.normalize_typo({"paleta": "#B3122E"}, 10)
    po, _ = ty.zastosuj(nowy, {"paleta": ["#BE185D", "#A87A12"]}, 10)    # popraw: paleta jak w edytorze
    assert [b["slowa"][1]["kolor"] for b in po["bloki"]] == ["#BE185D", "#A87A12", "#BE185D"]


def test_jasnosc_pod_blokiem():
    W, H = 54, 96
    rgb = klatka(lambda x, y: (255, 255, 255) if y < 0.5 else (0, 0, 0), W, H)
    gora = ty.jasnosc_pod(rgb, W, H, {"x": 0.5, "y": 0.2, "w": 0.6, "slowa": [{"tekst": "ab", "linia": 0}]}, 1080, 1920)
    dol = ty.jasnosc_pod(rgb, W, H, {"x": 0.5, "y": 0.8, "w": 0.6, "slowa": [{"tekst": "ab", "linia": 0}]}, 1080, 1920)
    assert gora > 0.95 and dol < 0.05


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_renderer_akcent_z_palety_i_napis_na_plytce():
    o = node("console.log(JSON.stringify([typoMotyw({typo: {motyw: 'czysty', paleta: ['#B3122E', '#A87A12']}}).akcent,"
             " typoMotyw({typo: {motyw: 'czysty', akcent: '#E30613', paleta: ['#B3122E']}}).akcent,"
             " typoMotyw({typo: {motyw: 'czysty'}}).akcent, typoJasnosc('#B3122E'), typoJasnosc('#F2C94C')]));")
    assert o[:3] == ["#B3122E", "#E30613", "#FFD400"]                  # marka > paleta z kadru > motyw
    assert abs(o[3] - ty.luminancja(*ty._hex_rgb("#B3122E"))) < 1e-6   # ta sama luminancja co w Pythonie
    assert abs(o[4] - ty.luminancja(*ty._hex_rgb("#F2C94C"))) < 1e-6
    assert "plyta ? (typoJasnosc(plyta) > 0.36" in JS                   # ciemna płytka → biały napis


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_renderer_styl_z_motywu_plytka_i_obrys():
    """Styl słowa: ręczny > płytka przy słabym kontraście > styl motywu; w motywie z obrysem płytki nie ma."""
    o = node("const S = (w, motyw, uklad) => typoSlowo(w, typoMotyw({typo: {motyw}}), uklad || 'kolumna').styl;"
             "console.log(JSON.stringify([S({tekst: 'a', waga: 1}, 'czysty'), S({tekst: 'a', waga: 3}, 'kino'),"
             " S({tekst: 'a', waga: 1}, 'podcast'), S({tekst: 'a', waga: 3}, 'vlog'), S({tekst: 'a', waga: 3, plyta: true}, 'czysty'),"
             " S({tekst: 'a', waga: 3, plyta: true}, 'podcast'), S({tekst: 'a', waga: 3, plyta: true}, 'czysty', 'za'),"
             " S({tekst: 'a', waga: 3, plyta: true, styl: '3d'}, 'czysty'), S({tekst: 'a', waga: 2, plyta: true}, 'vlog')]));")
    assert o == ["wypelnij", "3d", "obrys", "3d", "tlo", "obrys", "wypelnij", "3d", "obrys"]
    assert 'g.strokeStyle = typoJasnosc(fill) > 0.18 ? "#0B0B0B" : "#FFFFFF"' in JS          # ciemne słowo: biały obrys



@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_motyw_show_skok_i_styl():
    """Show (napisy z programu rozrywkowego): skok od zera ze szczytem 1,15 w 5. klatce, styl show bez płytki."""
    o = node("const S = (w, uklad) => typoSlowo(w, typoMotyw({typo: {motyw: 'show'}}), uklad || 'kolumna').styl;"
             "const k = [0, 5 / 30, 8 / 30, 0.4].map((t) => +typoSkok(t).toFixed(3));"
             "console.log(JSON.stringify([k, S({tekst: 'a', waga: 1}), S({tekst: 'a', waga: 3, plyta: true}),"
             " typoMieszaj('#FFFFFF', '#000000', 0.5), typoMotyw({typo: {motyw: 'show'}}).wejscie,"
             " typoJasnosc('#000000'), typoJasnosc('#fff'), typoJasnosc('zly'), typoCiemniej('#000', 0.5)]));")
    k, zwykle, plyta, szary, wejscie, czarny, bialy, zly, ciemny = o
    assert k[0] == 0 and 1.14 <= k[1] <= 1.16 and abs(k[2] - 1) < 0.03 and abs(k[3] - 1) < 0.015
    assert (zwykle, plyta, szary, wejscie) == ("show", "show", "rgb(128,128,128)", "skok")
    assert (czarny, bialy, zly, ciemny) == (0, 1, 1, "rgb(0,0,0)")      # czarne słowo nie jest brane za białe


def test_blok_wzorcowy_przed_osoba_z_uderzeniem():
    plan = ed.normalize_typo({"bloki": [
        blok([("raz", 1)], start=0.5),
        {**blok([("ZA", 3), ("tym", 0)], start=2.0), "id": "b2", "uklad": "za", "warstwa": "tyl"},
        {**blok([("to", 0), ("jest", 1), ("TANIEJ", 3)], start=4.0), "id": "b3"},
        {**blok([("dwa", 1), ("słowa", 2)], start=6.0), "id": "b4"}]}, 10)
    assert ty.blok_wzorcowy(plan)["id"] == "b3"
    plan["bloki"][2]["slowa"][2]["kroj"] = "titan"                     # ręczny krój: motyw go nie zmieni
    assert ty.blok_wzorcowy(plan)["id"] == "b4"


def test_polecenie_style_ten_sam_blok_w_kazdym_motywie(tmp_path, monkeypatch, capsys):
    src = _projekt_typo(tmp_path, [blok([("raz", 1)], start=0.5), {**blok([("to", 0), ("DZIAŁA", 3)], start=3.0), "id": "b2"}])
    import narzedzia
    monkeypatch.setattr(narzedzia, "wymagaj_playwright", lambda *a: None)
    wolania = []
    monkeypatch.setattr(ty.pr, "arkusz_typografii", lambda proj, plan, chwile, out, film, warianty=None:
                        wolania.append((plan, chwile, out, warianty)))
    assert ty.main(["style", str(src)]) == 0
    plan, chwile, out, warianty = wolania[-1]
    assert [p for p, _ in warianty] == ["czysty (teraz)", *ed.TYPO_MOTYWY[1:]]
    assert {q["motyw"] for _, q in warianty} == set(ed.TYPO_MOTYWY)
    assert all([b["id"] for b in q["bloki"]] == ["b2"] for _, q in warianty)          # tylko blok wzorcowy
    assert len(chwile) == 1 and 3.0 < chwile[0] < plan["bloki"][1]["end"] and out.name.endswith(".style.jpg")
    assert "MEDIA:" in capsys.readouterr().out
    assert ty.main(["style", str(src), "--blok", "b05", "--motywy", "podcast,neon"]) == 0
    assert [p for p, _ in wolania[-1][3]] == ["podcast", "neon"] and wolania[-1][3][0][1]["bloki"][0]["id"] == "b05"
    with pytest.raises(SystemExit, match="nie ma motywu: disco"):
        ty.main(["style", str(src), "--motywy", "podcast,disco"])
    with pytest.raises(SystemExit, match="nie ma bloku b99"):
        ty.main(["style", str(src), "--blok", "b99"])


def test_polecenie_paleta_zmienia_kolory_nie_uklad(tmp_path, monkeypatch):
    film = tmp_path / "f.mp4"
    film.write_bytes(b"x")
    plan = ed.normalize_typo({**plan_z_uderzeniami(3), "akcent": "#E7C583"}, 10)
    plan["bloki"][1]["slowa"][1]["kolor"] = "#FFFFFF"                  # kolor człowieka
    proj = {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "clips": [], "typo": plan}
    zapis = {}
    monkeypatch.setattr(ty.pr, "load", lambda f: json.loads(json.dumps(proj)))
    monkeypatch.setattr(ty.pr, "total", lambda p: 10.0)
    monkeypatch.setattr(ty.pr, "save", lambda f, p: zapis.update(p))
    monkeypatch.setattr(ty, "probki_kadru", lambda p, pl: ([klatka(plaza)], {b["id"]: 0.5 for b in pl["bloki"]}))
    assert ty.main(["paleta", str(film), "--bez-akcentu"]) == 0
    po = zapis["typo"]
    assert "akcent" not in po and po["paleta"] == ["#B3122E", "#A87A12"]
    assert [b["slowa"][1].get("kolor") for b in po["bloki"]] == ["#B3122E", "#FFFFFF", "#A87A12"]
    assert [(b["x"], b["y"], b["uklad"]) for b in po["bloki"]] == [(b["x"], b["y"], b["uklad"]) for b in plan["bloki"]]
    proj["typo"] = po                                                    # druga paleta: słowa idą za nią
    assert ty.main(["paleta", str(film), "--paleta", "#1D4ED8,#BE185D"]) == 0
    assert [b["slowa"][1].get("kolor") for b in zapis["typo"]["bloki"]] == ["#1D4ED8", "#FFFFFF", "#BE185D"]


# ---------------------------------------------------------------- kontrola napisów (typoKontrola, typografia.py sprawdz)

@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_js_kontrola_tusz_styk_i_pokrycie():
    """Pomiary kontroli na maskach z ręki: ramka tuszu, styk bliżej niż r (okno kwadratowe), część pod sylwetką."""
    prog = """
const w = 40, h = 20, M = (pola) => { const m = new Uint8Array(w * h); for (const [x0, y0, x1, y1] of pola)
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) m[y * w + x] = 1; return m; };
const a = M([[2, 2, 10, 8]]), b = M([[13, 2, 20, 8]]), c = M([[11, 2, 12, 8]]), s = M([[0, 5, 40, 20]]);
const R = (m) => typoRamkaTuszu(m, w, h);
console.log(JSON.stringify({ramka: R(a), pusta: R(new Uint8Array(w * h)),
  styk3: typoStyk(a, R(a), b, R(b), w, h, 3), styk4: typoStyk(a, R(a), b, R(b), w, h, 4),
  sasiad: typoStyk(a, R(a), c, R(c), w, h, 2), oddalony: typoStyk(c, R(c), b, R(b), w, h, 1),
  pokrycie: typoPokrycie(a, s), bez: typoPokrycie(new Uint8Array(w * h), s),
  pelna: typoChwilaPelna({start: 1, end: 3, wyjscie: 'zanik', slowa: [{t: 0}, {t: 0.5}]}, typoMotyw({})),
  krotki: typoChwilaPelna({start: 1, end: 1.7, wyjscie: 'zanik', slowa: [{t: 0}, {t: 0.5}]}, typoMotyw({}))}));
"""
    o = node(prog)
    assert o["ramka"] == {"x0": 2, "y0": 2, "x1": 10, "y1": 8} and o["pusta"] is None
    assert o["styk3"] is False and o["styk4"] is True            # odstęp 3 puste kolumny: styk dopiero przy r = 4
    assert o["sasiad"] is True and o["oddalony"] is False
    assert o["pokrycie"] == pytest.approx(0.5) and o["bez"] == 0
    assert o["pelna"] == pytest.approx(1.8) and o["krotki"] == pytest.approx(1.51)   # 0,3 s po ostatnim słowie, przed wyjściem


def test_strefy_kontroli_z_wideo_lib():
    pion = ty.strefy_kontroli(540, 960, "tiktok")
    assert [z["k"] for z in pion] == ["góra", "dół", "lewy", "prawy"]
    assert pion[1]["y0"] == pytest.approx(960 * (1 - 0.252)) and pion[1]["nazwa"][1] == "bottom"
    assert ty.strefy_kontroli(540, 960, "brak") == [] and ty.strefy_kontroli(960, 540, "tiktok") == []


def test_polecenie_sprawdz_bledy_kod_wyjscia_i_arkusz(tmp_path, monkeypatch, capsys):
    src = _projekt_typo(tmp_path, [blok([("raz", 1)], start=0.5), {**blok([("to", 0), ("DZIAŁA", 3)], start=3.0), "id": "b2"}])
    import narzedzia
    monkeypatch.setattr(narzedzia, "wymagaj_playwright", lambda *a: None)
    wynik = {"bloki": 2, "problemy": [
        {"poziom": "blad", "kod": "poza-kadrem", "blok": "b1", "t": 0.6, "opis": ["„raz” wychodzi poza kadr", "x"]},
        {"poziom": "uwaga", "kod": "strefa", "blok": "b2", "t": 3.3, "opis": ["„to DZIAŁA” pod interfejsem", "y"]}]}
    wolania, arkusze = [], []
    monkeypatch.setattr(ty, "kontrola", lambda film, proj, plan, platforma: wolania.append(platforma) or wynik)
    monkeypatch.setattr(ty.pr, "arkusz_typografii", lambda proj, plan, chwile, out, film, warianty=None: arkusze.append((chwile, out)))
    assert ty.main(["sprawdz", str(src), "--arkusz"]) == 1
    out = capsys.readouterr().out
    assert "błędy 1 · uwagi 1" in out and "✗" in out and "⚠" in out and "MEDIA:" in out
    assert wolania == ["tiktok"] and arkusze[-1][0] == [0.6] and arkusze[-1][1].name.endswith(".kontrola.jpg")
    wynik["problemy"] = wynik["problemy"][1:]                          # same uwagi: kod 0, arkusz z chwilami uwag
    assert ty.main(["sprawdz", str(src), "--strefa", "reels", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["problemy"][0]["kod"] == "strefa" and wolania[-1] == "reels"
    wynik["problemy"] = []
    assert ty.main(["sprawdz", str(src), "--arkusz", str(tmp_path / "k.jpg")]) == 0
    assert "bez problemów" in capsys.readouterr().out and len(arkusze) == 1   # bez problemów nie ma arkusza


def test_kontrola_w_przegladarce(tmp_path):
    """Cała kontrola w Chromium: blok poza kadrem, bloki na sobie, stykające się litery, za osobą bez sylwetek, strefa."""
    pytest.importorskip("playwright.sync_api")
    w = lambda t, tekst, waga, linia: {"t": t, "k": t + 0.3, "tekst": tekst, "waga": waga, "linia": linia}  # noqa: E731
    b = lambda i, start, x, y, slowa, **kw: {"id": i, "start": start, "end": start + 1.5, "uklad": "kolumna", "x": x, "y": y,  # noqa: E731
                                             "w": 0.6, "warstwa": "przod", "wyjscie": "ciecie", "slowa": slowa, **kw}
    plan = ed.normalize_typo({"motyw": "czysty", "bloki": [
        b("b01", 0, 0.97, 0.4, [w(0, "WYJEŻDŻA", 3, 0)]),
        b("b02", 2, 0.5, 0.45, [w(0, "pierwszy", 2, 0)]), b("b03", 2.2, 0.5, 0.47, [w(0, "drugi", 2, 0)]),
        b("b04", 4, 0.5, 0.4, [w(0, "jogging", 2, 0), w(0.2, "ŹÓŁĆ", 3, 1)], w=0.8),
        b("b05", 6, 0.5, 0.4, [w(0, "spokojnie", 1, 0), w(0.2, "tutaj", 1, 1)]),
        b("b06", 8, 0.5, 0.2, [w(0, "ZA", 3, 0)], uklad="za", warstwa="tyl", w=0.9),
        b("b07", 10, 0.5, 0.9, [w(0, "nisko", 2, 0)])]}, 12.0)
    film = tmp_path / "f.mp4"
    proj = {"canvas": {"w": 1080, "h": 1920, "fps": 30}, "clips": []}
    try:
        wynik = ty.kontrola(film, proj, plan, "tiktok")
    except Exception as exc:  # noqa: BLE001 - brak przeglądarki w tym środowisku
        pytest.skip(f"przeglądarka niedostępna: {exc}")
    kody = {(x["kod"], x["blok"]) for x in wynik["problemy"]}
    assert {("poza-kadrem", "b01"), ("bloki-na-sobie", "b03"), ("slowa-sie-stykaja", "b04"),
            ("brak-sylwetek", "b06"), ("strefa", "b07")} <= kody
    assert not any(blok == "b05" for _, blok in kody) and wynik["bloki"] == 7


# ---------------------------------------------------------------- wirtualna kamera z głębią (typo.kamera, z)

def _w(t: float, tekst: str, waga: int) -> dict:
    return {"t": t, "k": round(t + 0.3, 3), "tekst": tekst, "waga": waga, "linia": 0}


def _plan_kamery(styl: str = "dynamiczna", **kam) -> dict:
    return ed.normalize_typo({"motyw": "czysty", "kamera": {"styl": styl, **kam}, "bloki": [
        {"id": "b1", "start": 0.2, "end": 1.6, "x": 0.7, "slowa": [_w(0, "raz", 1), _w(0.4, "DWA", 3)]},
        {"id": "b2", "start": 1.7, "end": 3.0, "slowa": [_w(0, "spokojnie", 1)]},
        {"id": "b3", "start": 3.1, "end": 4.5, "x": 0.3, "slowa": [_w(0, "dalej", 1)]},
        {"id": "b4", "start": 4.6, "end": 5.0, "slowa": [_w(0, "krótko", 1)]},
        {"id": "b5", "start": 5.1, "end": 6.4, "uklad": "za", "warstwa": "tyl", "slowa": [_w(0, "ZA", 3)]},
        {"id": "b6", "start": 6.5, "end": 7.6, "z": 0.6, "slowa": [_w(0, "blisko", 2)],
         "kamera": {"ruch": "przesuniecie", "kierunek": "gora", "sila": 1}}]}, 8.0)


def test_kamera_w_planie_bezpieczna_i_zgodna_wstecz():
    stary = ed.normalize_typo({"motyw": "czysty", "bloki": [blok([("raz", 1)])]}, 10)
    assert "kamera" not in stary and "z" not in stary["bloki"][0]           # stary plan: bez kamery i głębi
    assert ed.kamera_filter(stary, 30) == "" and ed.kamera_odcinki(stary) == []
    p = ed.normalize_typo({"kamera": {"styl": "lot", "przyslona": 7, "ostrosc": "?"}, "bloki": [
        {**blok([("a", 1), ("b", 3)]), "z": 9, "kamera": {"ruch": "najazd", "sila": "x", "krzywa": "?", "slowo": 5},
         "slowa": [{**_w(0, "a", 1), "z": 0.1}, _w(0.4, "b", 3)]},
        {**blok([("c", 1)], start=3), "id": "b6", "kamera": {"ruch": "wir"}},
        {**blok([("d", 1)], start=5), "id": "b7", "kamera": {"ruch": "przesuniecie", "kierunek": "skos", "slowo": True}}]}, 10)
    assert p["kamera"] == {"styl": "brak", "przyslona": 1.0, "ostrosc": "napis"}
    b1, b6, b7 = p["bloki"]
    assert b1["z"] == 3.0 and b1["slowa"][0]["z"] == 0.3
    assert b1["kamera"] == {"ruch": "najazd", "sila": 0.5, "krzywa": "plynnie"}   # słowa 5 nie ma
    assert "kamera" not in b6 and b7["kamera"] == {"ruch": "przesuniecie", "sila": 0.5, "krzywa": "plynnie", "kierunek": "prawo"}
    assert ed.kamera_z({"warstwa": "tyl"}) == 1.3 and ed.kamera_z({"warstwa": "przod"}) == 0.8 and ed.kamera_z(b1) == 3.0


def test_kamera_ruchy_ze_stylu_i_wlasne():
    p = _plan_kamery("dynamiczna")
    ruchy = [(b["id"], r["ruch"], r.get("krzywa"), r.get("kierunek")) for b, r in ed.kamera_ruchy(p)]
    assert ruchy == [("b1", "najazd", "uderzenie", None),        # uderzenie: szybki najazd od słowa
                     ("b2", "odjazd", "plynnie", None),           # po najeździe odjazd
                     ("b3", "przesuniecie", "plynnie", "lewo"),   # spokojny blok po lewej: kamera w lewo, blok do środka
                     ("b5", "najazd", "plynnie", None),           # b4 za krótki; za osobą: najazd
                     ("b6", "przesuniecie", "plynnie", "gora")]   # własny ruch bloku
    spok = [(b["id"], r["ruch"]) for b, r in ed.kamera_ruchy(_plan_kamery("spokojna"))]
    assert spok == [("b1", "najazd"), ("b3", "odjazd"), ("b5", "najazd"), ("b6", "przesuniecie")]   # trzyma najazd 2,5 s
    assert [b["id"] for b, _ in ed.kamera_ruchy(_plan_kamery("brak"))] == ["b6"]    # bez stylu: tylko własne ruchy
    brak = json.loads(json.dumps(p))
    brak["bloki"][0]["kamera"] = {"ruch": "brak"}
    assert [(b["id"], r["ruch"]) for b, r in ed.kamera_ruchy(brak)][:2] == [("b2", "przesuniecie"), ("b3", "przesuniecie")]
    # „brak” wyłącza ruch bloku, więc kamera nie jest w głębi i następny spokojny blok dostaje przesunięcie


def test_kamera_odcinki_film_zawsze_wypelnia_kadr():
    odc = ed.kamera_odcinki(_plan_kamery("dynamiczna"))
    assert odc[0]["a"] == pytest.approx(0.2 + 0.4 - ed.TYPO_LEAD) and odc[0]["b"] == pytest.approx(odc[0]["a"] + 0.4)
    assert all(a["c"] <= b["a"] for a, b in zip(odc, odc[1:]))
    for t in [i / 20 for i in range(170)]:
        z, x, y = ed.kamera_stan(odc, t)
        assert 0 <= z <= ed.KAMERA_ZMAX + 1e-9 and abs(x) <= z / 2 + 1e-9 and abs(y) <= z / 2 + 1e-9, t
    assert ed.kamera_stan(odc, 0.1) == (0.0, 0.0, 0.0)                              # przed pierwszym ruchem spoczynek
    assert ed.kamera_stan(odc, 1.2)[0] == pytest.approx(0.04 + 0.12 * 0.6)          # po najeździe stoi w głębi
    assert ed.kamera_stan(odc, 3.05) == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)    # odjazd do spoczynku
    z, x, _y = ed.kamera_stan(odc, 4.55)
    assert x == pytest.approx(-(0.015 + 0.05 * 0.6)) and z >= 2 * abs(x)            # przesunięcie z najazdem
    pusty = ed.normalize_typo({"kamera": {"styl": "brak"}, "bloki": [{**blok([("a", 1)]), "kamera": {"ruch": "odjazd", "sila": 1}}]}, 10)
    o = ed.kamera_odcinki(pusty)[0]                                                   # odjazd ze spoczynku: skok, potem odjazd
    assert o["s0"][0] == pytest.approx(0.16) and o["s1"] == (0.0, 0.0, 0.0)
    assert ed.kamera_stan([o], o["a"] - 0.01) == (0.0, 0.0, 0.0) and ed.kamera_stan([o], o["a"])[0] == pytest.approx(0.16)


def _ewaluuj_ffmpeg(wyr: str, n: int) -> float:
    """Mały ewaluator wyrażeń z kamera_filter (podzbiór składni ffmpeg: + - * /, gte, clip, min, st/ld, ;)."""
    toks = re.findall(r"\d+\.\d+|\d+|[a-z]+|[-+*/(),;]", wyr)
    pos, rej = 0, {}

    def peek():
        return toks[pos] if pos < len(toks) else None

    def eat(x=None):
        nonlocal pos
        t = toks[pos]
        assert x is None or t == x, (t, x)
        pos += 1
        return t

    def seq():
        v = expr()
        while peek() == ";":
            eat(";")
            v = expr()
        return v

    def expr():
        v = term()
        while peek() in ("+", "-"):
            v = v + term() if eat() == "+" else v - term()
        return v

    def term():
        v = factor()
        while peek() in ("*", "/"):
            v = v * factor() if eat() == "*" else v / factor()
        return v

    def factor():
        t = peek()
        if t == "-":
            eat()
            return -factor()
        if t == "(":
            eat("(")
            v = seq()
            eat(")")
            return v
        if re.match(r"\d", t):
            return float(eat())
        name = eat()
        if name == "in":
            return float(n)
        eat("(")
        args = [seq()]
        while peek() == ",":
            eat(",")
            args.append(seq())
        eat(")")
        if name == "st":
            rej[int(args[0])] = args[1]
            return args[1]
        if name == "ld":
            return rej[int(args[0])]
        return {"gte": lambda a, b: float(a >= b), "clip": lambda v, a, b: min(b, max(a, v)), "min": min}[name](*args)

    return seq()


def test_kamera_filter_ffmpeg_wyrazenia():
    """Płaska suma odcinków w wyrażeniu ffmpeg daje w każdej klatce ten sam stan, co kamera_stan (i 48-typografia.js)."""
    p = _plan_kamery("dynamiczna")
    f = ed.kamera_filter(p, 30)
    assert f.startswith("perspective=") and "eval=frame" in f and "enable='between(t," in f and f.count("'") % 2 == 0
    odc = ed.kamera_odcinki(p)
    for t in (0.1, 0.7, 1.2, 2.2, 3.8, 5.7, 7.1, 7.9):
        n = round(t * 30 - 0.5)
        z, x, y = ed.kamera_stan(odc, (n + 0.5) / 30)
        for wsp, cel in (((0.5, 1, 0), 0.5 * z + x), ((-0.5, 1, 0), -0.5 * z + x), ((-0.5, 0, 1), -0.5 * z + y)):
            assert _ewaluuj_ffmpeg(ed._kamera_suma(odc, wsp, 30), n) == pytest.approx(cel, abs=1e-4), (t, wsp)


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_kamera_js_i_python_te_same_ruchy():
    """Odcinki kamery liczy edytor.py (ruch filmu w ffmpeg) i 48-typografia.js (napisy): te same liczby."""
    for styl in ("spokojna", "dynamiczna"):
        p = _plan_kamery(styl)
        chwile = [i / 10 for i in range(80)]
        o = node(f"const T = {json.dumps(p)};\nconsole.log(JSON.stringify({{odc: typoKameraOdcinki(T), "
                 f"stan: {json.dumps(chwile)}.map((t) => typoKameraStanOdc(typoKameraOdcinki(T), t))}}));")
        py = ed.kamera_odcinki(p)
        assert len(o["odc"]) == len(py)
        for a, b in zip(o["odc"], py):
            assert (a["a"], a["b"], a["c"]) == pytest.approx((b["a"], b["b"], b["c"])) and a["krzywa"] == b["krzywa"]
            assert a["s0"] == pytest.approx(list(b["s0"]), abs=1e-5) and a["s1"] == pytest.approx(list(b["s1"]), abs=1e-5)
        for t, s in zip(chwile, o["stan"]):
            assert s == pytest.approx(list(ed.kamera_stan(py, t)), abs=1e-5), (styl, t)
    stale = re.search(r"const TYPO_KAMERA = \{ z: \{ przod: ([\d.]+), tyl: ([\d.]+) \}, zmax: ([\d.]+), sila: \{ spokojna: ([\d.]+), "
                      r"dynamiczna: ([\d.]+) \}, uderzenie: ([\d.]+),\s+minBlok: ([\d.]+), trzymaj: ([\d.]+),", JS)
    assert tuple(map(float, stale.groups())) == (ed.KAMERA_Z["przod"], ed.KAMERA_Z["tyl"], ed.KAMERA_ZMAX,
                                                 ed.KAMERA_SILA["spokojna"], ed.KAMERA_SILA["dynamiczna"],
                                                 ed.KAMERA_UDERZENIE, ed.KAMERA_MIN_BLOK, ed.KAMERA_TRZYMAJ)
    assert float(re.search(r"const TYPO_LEAD = ([\d.]+);", JS).group(1)) == ed.TYPO_LEAD
    for nazwa, py in (("TYPO_KAMERY", ed.TYPO_KAMERY), ("TYPO_RUCHY", ed.TYPO_RUCHY), ("TYPO_KIERUNKI", ed.TYPO_KIERUNKI),
                      ("TYPO_KRZYWE", ed.TYPO_KRZYWE), ("TYPO_OSTROSC", ed.TYPO_OSTROSC)):
        assert tuple(json.loads(re.search(rf"const {nazwa} = (\[.*?\]);", JS).group(1))) == py


@pytest.mark.skipif(not HAS_NODE, reason="brak node")
def test_kamera_js_rzut_ostrosc_i_podpis():
    """Rzut: w spoczynku napis stoi jak w planie, przy najeździe bliższy rośnie i ucieka od środka bardziej niż film;
    ostrość idzie za najnowszym blokiem; podpis klatki eksportu zmienia się z kamerą, a bez kamery jest jak dawniej."""
    p = _plan_kamery("dynamiczna", przyslona=0.5)
    o = node(f"const P = {{typo: {json.dumps(p)}}};\nconst k0 = {{z: 0, x: 0, y: 0, f: 1, a: 0.5}}, k1 = {{z: 0.2, x: 0, y: 0, f: 0.8, a: 0.5}};"
             "\nconst ctx = {font: '', measureText(t) { return {width: Array.from(t).length * 30}; }};"
             "\nconsole.log(JSON.stringify({spoczynek: typoRzut(k0, 0.7, 0.3, 0.8), blisko: typoRzut(k1, 0.7, 0.5, 0.6),"
             " film: typoRzut(k1, 0.7, 0.5, 1), rozm: [typoRozmycie(k1, 0.8, false), typoRozmycie(k1, 1.3, false), typoRozmycie(k1, 3, true)],"
             " ostr: [0.1, 0.3, 1.0, 1.8, 2.5].map((t) => typoKamera(P, t).f),"
             " podpis: [0.7, 0.8, 1.25].map((t) => typoPodpis(P, t, 'przod')), bez: typoKamera({typo: {bloki: []}}, 1),"
             " css: [typoKameraCss(k0), typoKameraCss(k1)], ramka: typoRamka(ctx, P.typo.bloki[0], P, 1080, 1920, 1.2),"
             " ramka0: typoRamka(ctx, P.typo.bloki[0], P, 1080, 1920)}));")
    assert o["spoczynek"]["x"] == pytest.approx(0.7) and o["spoczynek"]["y"] == pytest.approx(0.3) and o["spoczynek"]["s"] == 1
    assert o["blisko"]["s"] > o["film"]["s"] > 1 and o["blisko"]["x"] > o["film"]["x"] > 0.7      # paralaksa
    assert o["rozm"][0] == 0 and 0 < o["rozm"][1] <= 6 * 0.5 and o["rozm"][2] > o["rozm"][1]     # ostrość na 0,8
    f = o["ostr"]
    assert f[0] == 1 and f[1] == pytest.approx(0.8) and f[3] == pytest.approx(0.8) and f[4] == pytest.approx(0.8)
    assert o["podpis"][1] != o["podpis"][2] and "~" in o["podpis"][1]           # kamera w ruchu: inna klatka
    assert o["bez"] is None and o["css"][0] == "" and o["css"][1].startswith("scale(1.25")
    assert o["ramka"]["s"] > 1 and o["ramka"]["cx"] > o["ramka0"]["cx"] and o["ramka0"]["s"] == 1
    bez = {**p}
    bez.pop("kamera")
    stary = node(f"const P = {{typo: {json.dumps(bez)}}};\nconsole.log(JSON.stringify(typoPodpis(P, 1.2, 'przod')));")
    assert "~" not in stary                                                         # bez kamery podpis jak dawniej


@pytest.mark.skipif(not HAS_FF, reason="brak ffmpeg")
def test_eksport_kamera_przesuwa_film_i_sylwetke(tmp_path):
    """Przesunięcie kamery w prawo (film: lewa połowa czarna, prawa biała): granica jedzie w lewo; sylwetka osoby
    jedzie z filmem, więc napis „za osobą” widać tam, gdzie osoby już nie ma."""
    src, raw = _maska_film(tmp_path, 50)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=black:s=160x90:r=25:d=2",
                    "-vf", "drawbox=x=80:y=0:w=80:h=90:color=white:t=fill", "-pix_fmt", "yuv420p", str(src)], check=True)
    raw["typo"]["kamera"] = {"styl": "brak"}
    raw["typo"]["bloki"][0]["kamera"] = {"ruch": "przesuniecie", "kierunek": "prawo", "sila": 1}
    p = ed.normalize(raw, lambda r: Path(r) if Path(r) == src else None)
    blank = ed.blank_png(tmp_path / "pusty.png", 160, 90)
    red = _png_rgba(tmp_path / "r.png", 160, 90, (255, 0, 0, 255))
    tyl = ed.typo_concat([(0.4, None), (1.2, red), (0.4, None)], blank, tmp_path / "tyl.ffconcat")
    maska = ed.maska_concat(src, raw, p, tmp_path)
    out = tmp_path / "o.mp4"
    cmd = ed.build_command(p, {str(src): False}, [], out, typo={"tyl": tyl}, maska=maska)
    graf = cmd[cmd.index("-filter_complex") + 1]
    assert graf.count("perspective=") == 2 and "[vc]perspective=" in graf      # film i sylwetka przez tę samą kamerę
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    def kolor(t: float, x: int):
        return tuple(subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                                     "-vf", f"crop=4:20:{x}:35,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    capture_output=True, check=True).stdout[:3])
    assert max(kolor(0.2, 72)) < 60                           # przed ruchem: lewa połowa czarna (osoba, bez napisu)
    assert kolor(1.5, 72)[0] > 150 and kolor(1.5, 72)[2] < 80  # po przesunięciu tu już nie ma osoby: widać napis za nią
    assert max(kolor(1.5, 20)) < 60                           # osoba (lewa część filmu) dalej przed napisem
    assert min(kolor(1.9, 72)) > 200                          # po bloku kamera stoi: tu już prawa (biała) część filmu


def test_kamera_w_przegladarce_najazd_i_spoczynek():
    """Chromium: kamera w spoczynku bez rozmycia rysuje piksel w piksel jak plan bez kamery; najazd powiększa napis
    (tusz szerszy), a rozmycie z głębi ostrości miękczy słowo daleko od płaszczyzny ostrości."""
    pytest.importorskip("playwright.sync_api")
    b = {"id": "b1", "start": 0.0, "end": 2.0, "x": 0.5, "y": 0.5, "w": 0.6, "slowa": [_w(0, "KAMERA", 3)],
         "kamera": {"ruch": "najazd", "sila": 1, "krzywa": "plynnie"}}
    bez = ed.normalize_typo({"motyw": "czysty", "bloki": [b]}, 3.0)
    ostra = ed.normalize_typo({"motyw": "czysty", "kamera": {"styl": "brak", "przyslona": 0}, "bloki": [b]}, 3.0)
    stoi = ed.normalize_typo({"motyw": "czysty", "kamera": {"styl": "brak", "przyslona": 0},
                              "bloki": [{**b, "kamera": {"ruch": "brak"}}]}, 3.0)
    rozm = ed.normalize_typo({"motyw": "czysty", "kamera": {"styl": "brak", "przyslona": 1, "ostrosc": "osoba"},
                              "bloki": [{**b, "z": 0.5, "kamera": {"ruch": "brak"}}]}, 3.0)
    js = """async ([plany, t]) => {
        const out = [];
        for (const T of plany) {
            const c = document.createElement("canvas"); c.width = 270; c.height = 480;
            const g = c.getContext("2d", { willReadFrequently: true });
            typoRysuj(g, { typo: T }, 270, 480, t);
            const d = g.getImageData(0, 0, 270, 480).data;
            let x0 = 270, x1 = -1, ostre = 0, suma = 0;
            for (let i = 0; i < 270 * 480; i++) {
                const a = d[i * 4 + 3];
                if (a >= 160) { const x = i % 270; if (x < x0) x0 = x; if (x > x1) x1 = x; }
                if (a >= 250) ostre++;
                suma += d[i * 4] + d[i * 4 + 3];
            }
            out.push({ w: x1 - x0, ostre, suma });
        }
        return out;
    }"""
    try:
        with ty.pr.strona([{"typo": bez}]) as page:
            spoczynek = page.evaluate(js, [[bez, stoi, rozm], 1.0])
            ruch = page.evaluate(js, [[bez, ostra], 1.9])
    except Exception as exc:  # noqa: BLE001 - brak przeglądarki w tym środowisku
        pytest.skip(f"przeglądarka niedostępna: {exc}")
    assert spoczynek[0] == spoczynek[1]                          # w spoczynku i bez rozmycia: jak plan bez kamery
    assert ruch[1]["w"] > ruch[0]["w"] * 1.1                     # najazd: blok z = 0,8 rośnie (×1,25)
    assert spoczynek[2]["ostre"] < spoczynek[0]["ostre"] * 0.7   # z = 0,5 przy ostrości na osobie: rozmyte


# ---------------------------------------------------------------- kamera w reżyserii (typografia.py)

def test_plan_z_kamera_i_glebia_blokow():
    p, _ = plan(motyw="kino")
    assert p["kamera"] == {"styl": "spokojna", "przyslona": 0.5, "ostrosc": "napis"}          # auto: z motywu
    assert all(0.6 <= b["z"] < 1 for b in p["bloki"])                                         # przed osobą
    mocne = [b["z"] for b in p["bloki"] if any(w["waga"] == 3 for w in b["slowa"])]
    assert min(mocne) <= min(b["z"] for b in p["bloki"] if not any(w["waga"] == 3 for w in b["slowa"]))
    assert plan(motyw="energia")[0]["kamera"]["styl"] == "dynamiczna" and ed.kamera_ruchy(p)
    slowa = mowa("raz dwa trzy cztery pięć sześć")
    assert "kamera" not in ty.zbuduj_plan(slowa, [], 1080, 1920, 6, kamera="brak")           # bez kamery: jak dawniej
    assert set(ty.KAMERA_MOTYWU) == set(ed.TYPO_MOTYWY) and set(ty.KAMERA_MOTYWU.values()) <= set(ed.TYPO_KAMERY)


def test_za_osoba_dalej_niz_osoba():
    b = {**blok([("w", 0), ("PIĘĆ", 3), ("minut", 2), ("dziś", 1)]), "z": 0.75}
    czesci = ty.wydziel_za(b, 0, 3, GLOWA["glowa"], 1080, 1920)
    assert [(c["warstwa"], c["z"]) for c in czesci] == [("tyl", 1.3), ("przod", 0.75)]


def test_zastosuj_kamera_planu_i_bloku():
    p, total = plan()
    nowy, uwagi = ty.zastosuj(p, {"kamera": {"styl": "dynamiczna", "przyslona": 0.8, "obce": 1}, "bloki": [
        {"blok": "b01", "z": 0.6, "kamera": {"ruch": "najazd", "sila": 0.9, "krzywa": "uderzenie", "slowo": 0}},
        {"blok": "b02", "kamera": {"ruch": "obrot"}},
        {"blok": "b03", "warstwa": "tyl"},
        {"blok": "b04", "warstwa": "tyl", "z": 0.7}]}, total)
    assert nowy["kamera"] == {"styl": "dynamiczna", "przyslona": 0.8, "ostrosc": "napis"}
    b = {x["id"]: x for x in nowy["bloki"]}
    assert b["b01"]["z"] == 0.6 and b["b01"]["kamera"] == {"ruch": "najazd", "sila": 0.9, "krzywa": "uderzenie", "slowo": 0}
    assert "kamera" not in b["b02"] and any("b02" in u and "odrzucony" in u for u in uwagi)
    assert "z" not in b["b03"] and ed.kamera_z(b["b03"]) == 1.3                  # za osobą: głębia z warstwy
    assert any("b04" in u and "nie pasuje" in u for u in uwagi)                  # jawna głębia przed osobą za osobą
    bez, _ = ty.zastosuj(nowy, {"kamera": None, "bloki": [{"blok": "b01", "kamera": None, "z": None}]}, total)
    assert "kamera" not in bez and "kamera" not in bez["bloki"][0] and "z" not in bez["bloki"][0]


def test_polecenie_kamera_i_pokaz(tmp_path, capsys):
    src = _projekt_typo(tmp_path, [blok([("raz", 1), ("DWA", 3)]), {**blok([("spokojnie", 1)], start=3.0), "id": "b06"}])
    assert ty.main(["kamera", str(src), "--styl", "dynamiczna", "--przyslona", "0.3", "--ostrosc", "osoba"]) == 0
    out = capsys.readouterr().out
    assert "Kamera dynamiczna, przysłona 0.3, ostrość osoba" in out and "b05 najazd" in out
    zapis = json.loads(ed.project_path(src).read_text(encoding="utf-8"))["typo"]
    assert zapis["kamera"] == {"styl": "dynamiczna", "przyslona": 0.3, "ostrosc": "osoba"}
    assert ty.main(["pokaz", str(src)]) == 0
    out = capsys.readouterr().out
    assert "kamera: najazd 0.6 uderzenie od słowa 1 (styl)" in out and " z 0.80" in out
    assert ty.main(["kamera", str(src), "--bez"]) == 0
    assert "kamera" not in json.loads(ed.project_path(src).read_text(encoding="utf-8"))["typo"]
    assert ty.main(["kamera", str(src)]) == 0                                    # bez opcji: styl z motywu
    assert json.loads(ed.project_path(src).read_text(encoding="utf-8"))["typo"]["kamera"]["styl"] == "spokojna"


def test_ruch_kamery_przy_cieciu_i_laczeniu(tmp_path):
    """Cięcie bloku nie dubluje ruchu kamery: zostaje w części ze słowem startu; łączenie bierze ruch pierwszego,
    a bez niego drugiego od jego słowa. Ta sama reguła w HQ (typoRuchPodzial, typoRuchPolacz)."""
    r = {"ruch": "najazd", "sila": 0.5, "krzywa": "uderzenie", "slowo": 3}
    assert ty.ruch_podzial(r, 2) == (None, {**r, "slowo": 1})
    assert ty.ruch_podzial(r, 4) == (r, None)
    assert ty.ruch_podzial({"ruch": "odjazd"}, 1) == ({"ruch": "odjazd"}, None)
    assert ty.ruch_polacz(None, {"ruch": "przesuniecie", "kierunek": "lewo"}, 3) == {"ruch": "przesuniecie", "kierunek": "lewo", "slowo": 3}
    assert ty.ruch_polacz(None, {"ruch": "brak"}, 3) is None
    assert ty.ruch_polacz({"ruch": "odjazd"}, {"ruch": "najazd"}, 3) == {"ruch": "odjazd"}
    if HAS_NODE:                                         # HQ liczy to samo (funkcje wycięte z 45-edytor.js)
        src = (ROOT / "hq/web/src/45-edytor.js").read_text(encoding="utf-8")
        fns = "\n".join(re.search(rf"^function {fn}\(.*?^\}}", src, re.S | re.M).group(0)
                        for fn in ("typoRuchPodzial", "typoRuchPolacz"))
        prog = (f"const r = {json.dumps(r)};\nconsole.log(JSON.stringify([typoRuchPodzial(r, 2), typoRuchPodzial(r, 4), "
                "typoRuchPolacz(undefined, {ruch: 'przesuniecie', kierunek: 'lewo'}, 3), typoRuchPolacz(undefined, {ruch: 'brak'}, 3)]));")
        out = subprocess.run(["node", "-e", fns + "\n" + prog], capture_output=True, text=True, check=True).stdout
        assert json.loads(out) == [[None, {**r, "slowo": 1}], [r, None],
                                   {"ruch": "przesuniecie", "kierunek": "lewo", "slowo": 3}, None]
    plan = {"bloki": [{"id": "b1", "start": 0, "end": 2, "slowa": [{"tekst": t, "t": k * 0.4, "k": k * 0.4 + 0.3, "linia": 0}
                                                              for k, t in enumerate("raz dwa trzy cztery".split())],
                       "kamera": dict(r)}]}
    nowy, _ = ty.zastosuj(ed.normalize_typo(plan, 3), {"bloki": [{"blok": "b1", "podziel": 2}]}, 3)
    po = {b["id"]: b.get("kamera") for b in nowy["bloki"]}
    assert po["b1"] is None and po["b1b"]["slowo"] == 1
    nowy, _ = ty.zastosuj(nowy, {"bloki": [{"polacz": ["b1", "b1b"]}]}, 3)
    assert nowy["bloki"][0]["kamera"]["slowo"] == 3

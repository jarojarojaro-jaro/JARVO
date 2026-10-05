"""assety.py: marka ze strony (role kolorów, rogi, charakter ruchu, CSS) i zrzut do filmu (kafle, cele, wycinki)."""

from __future__ import annotations

import json

import pytest

from conftest import load_script

A = load_script("profiles/jarvo-wideo/scripts/assety.py")

# surowe zliczenia jak z MARKA_JS na jasnej stronie piekarni: opisy przygaszone mają więcej znaków niż ciemny tekst
PIEKARNIA = {
    "strona": "rgb(251, 246, 238)",
    "powierzchnie": [["rgb(251, 246, 238)", 900000], ["rgb(243, 232, 218)", 500000], ["rgb(255, 255, 255)", 300000],
                     ["rgb(43, 29, 18)", 150000]],
    "teksty": [["rgb(122, 102, 86)", 900], ["rgb(43, 29, 18)", 400], ["rgb(194, 65, 12)", 120], ["rgba(0, 0, 0, 0.3)", 999]],
    "przyciski": [["rgb(194, 65, 12)", "rgb(255, 255, 255)", 6], ["rgb(37, 99, 235)", "rgb(255, 255, 255)", 1]],
    "pola": [["rgb(255, 253, 249)", 3]],
    "obramowania": [["rgb(234, 223, 208)", 9], ["rgb(194, 65, 12)", 1]],
    "linki": [["rgb(122, 102, 86)", 3]],
    "kroj": {"h1": {"font": "Fraunces", "px": 64, "waga": 700, "interlinia": "1.08", "odstep": "-1px", "wielkie": False},
             "tekst": {"font": "Inter", "px": 18, "waga": 400, "interlinia": "1.60", "odstep": "normal", "wielkie": False}},
    "promienie": {"przycisk": [["12px", "55", 6]], "karta": [["16px", 6]], "pole": [["10px", 3]]},
    "cienie": [["rgba(43, 29, 18, 0.06) 0px 6px 18px 0px", 6]],
    "szerokosci": [[1140, 4], [542, 2]],
    "szer_okna": 1440,
}


def test_role_kolorow_piekarnia():
    k = A.role_kolorow(PIEKARNIA)
    assert k["strona"] == "#FBF6EE" and k["powierzchnia"] == "#F3E8DA" and k["pole"] == "#FFFDF9"
    assert k["tekst"] == "#2B1D12"                    # najmocniejszy z częstych, nie najczęstszy (opisy są przygaszone)
    assert k["przygaszony"] == "#7A6656"              # nasycony akcent z cen nie jest „przygaszony”
    assert k["akcent"] == "#C2410C" and k["akcent_tekst"] == "#FFFFFF" and k["obramowanie"] == "#EADFD0"
    assert k["zgadniete"] == []


def test_role_kolorow_zgadniete_i_ciemna_strona():
    k = A.role_kolorow({"strona": "rgb(10, 10, 12)", "teksty": [["rgb(240, 240, 240)", 50]]})
    assert k["tekst"] == "#F0F0F0" and k["akcent"] == "#F0F0F0"       # bez przycisków i linków akcentem jest tekst
    assert set(k["zgadniete"]) == {"przygaszony", "powierzchnia", "akcent", "obramowanie"}
    assert A.kontrast(k["akcent_tekst"], k["akcent"]) >= 3
    pusta = A.role_kolorow({})
    assert pusta["strona"] == "#FFFFFF" and pusta["tekst"] == "#111111" and "strona" in pusta["zgadniete"]


def test_promienie_pigulka_i_charakter():
    assert A.promienie(PIEKARNIA) == {"przycisk": 12, "karta": 16, "pole": 10}
    pig = A.promienie({"promienie": {"przycisk": [["50%", "40", 3], ["24px", "48", 2]], "karta": [["8px 4px", 1]]}})
    assert pig == {"przycisk": 999, "karta": 8}       # „50%” pomijamy, 24 px przy 48 px wysokości = pigułka
    kolory = A.role_kolorow(PIEKARNIA)
    assert A.podpowiedz_charakteru(kolory, PIEKARNIA["kroj"], A.promienie(PIEKARNIA))["nazwa"] == "przyjazny"
    szary = dict(kolory, akcent="#1F2937")
    assert A.podpowiedz_charakteru(szary, {"h1": {"font": "Playfair Display", "waga": 600}}, {"przycisk": 0})["nazwa"] == "luksus"
    assert A.podpowiedz_charakteru(szary, {"h1": {"font": "Inter", "waga": 600}}, {"przycisk": 4})["nazwa"] == "zaufanie"
    assert A.podpowiedz_charakteru(szary, {"h1": {"font": "Inter", "waga": 500}}, {"przycisk": 12})["nazwa"] == "spokojny"
    zywy = dict(kolory, akcent="#FF2D87")
    assert A.podpowiedz_charakteru(zywy, {"h1": {"font": "Inter", "waga": 600}}, {"przycisk": 999})["nazwa"] == "zabawny"
    assert A.podpowiedz_charakteru(zywy, {"h1": {"font": "Inter", "waga": 900}}, {"przycisk": 6})["nazwa"] == "odwazny"


def test_marka_i_css():
    m = A.marka(PIEKARNIA)
    assert m["szerokosc_tresci"] == 1140 and m["cien_karty"].startswith("rgba(43, 29, 18")
    css = A.marka_css(m)
    for linia in ("--marka-strona: #FBF6EE;", "--marka-akcent: #C2410C;", "--marka-akcent-tekst: #FFFFFF;",
                  '--marka-font-naglowek: "Fraunces";', "--marka-h1-px: 64px;", "--marka-promien-przycisk: 12px;",
                  "--marka-cien-karty: rgba(43, 29, 18, 0.06) 0px 6px 18px 0px;"):
        assert linia in css
    assert "charakter ruchu: przyjazny" in css and css.count("{") == css.count("}") == 1


def test_kafle_i_wycinki():
    assert A.kafle(2561, 2) == [(0, 2561)]
    assert A.kafle(13000, 2) == [(0, 6000), (6000, 6000), (12000, 1000)]
    assert A.kafle(4479, 3) == [(0, 4000), (4000, 479)]
    assert A.kafle(0, 2) == [(0, 1)]
    cele = ([{"id": "logo-1", "typ": "logo", "w": 120, "h": 30},
             {"id": "naglowek-1", "typ": "naglowek", "poziom": 2, "w": 300, "h": 40},
             {"id": "naglowek-2", "typ": "naglowek", "poziom": 1, "w": 600, "h": 140}]
            + [{"id": f"przycisk-{i}", "typ": "przycisk", "w": 100, "h": 40} for i in range(1, 6)]
            + [{"id": "obraz-1", "typ": "obraz", "w": 500, "h": 300}, {"id": "cena-1", "typ": "cena", "w": 2, "h": 2}])
    assert A.wybierz_wycinki(cele) == ["logo-1", "naglowek-2", "przycisk-1", "przycisk-2", "przycisk-3"]


def test_wlasne_wycinki_i_cli(capsys):
    assert A.wlasne_wycinki("cta=.btn-primary, plan=#cennik .karta") == {"cta": ".btn-primary", "plan": "#cennik .karta"}
    assert A.wlasne_wycinki("") == {}
    with pytest.raises(SystemExit, match="nazwa=selektor"):
        A.wlasne_wycinki("zły wycinek=.x")
    with pytest.raises(SystemExit):
        A.main(["http://127.0.0.1:1/", "--wycinki", "cta=.btn"])          # --wycinki tylko z --film
    assert "--wycinki działa z --film" in capsys.readouterr().err


STRONA = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Test</title><style>
body{margin:0;background:#fbf6ee;color:#2b1d12;font:18px sans-serif}
header{position:fixed;top:0;left:0;right:0;height:60px;background:#fff}
main{padding:80px 40px}.btn{background:#c2410c;color:#fff;padding:12px 20px;border-radius:12px;display:inline-block}
.card{background:#fff;border-radius:16px;padding:20px;width:300px;height:160px;margin:20px 0}
.cookie{position:fixed;bottom:0;left:0;right:0;background:#111;color:#fff;padding:20px}
</style></head><body><header><a href="/" class="logo"><svg width="30" height="30"><circle cx="15" cy="15" r="14" fill="#c2410c"/></svg></a></header>
<main><h1>Chleb co rano</h1><p>Zamów do 20:00.</p><a class="btn" href="#">Zamów</a>
<article class="card"><h3>Żytni</h3><div class="price">18 zł</div></article>
<div style="height:2600px"></div><p id="dol">koniec</p></main>
<div class="cookie">Używamy plików cookie. <button>Akceptuję</button></div></body></html>"""


def test_film_w_przegladarce(tmp_path, capsys):
    pytest.importorskip("playwright.sync_api")
    (tmp_path / "index.html").write_text(STRONA, encoding="utf-8")
    out = tmp_path / "assets"
    assert A.main([(tmp_path / "index.html").as_uri(), "--out", str(out), "--film", "--wycinki", "dol=#dol"]) == 0
    w = json.loads(capsys.readouterr().out)
    assert w["marka"]["kolory"]["akcent"] == "#C2410C"
    u = json.loads((out / "film" / "uklad.json").read_text(encoding="utf-8"))
    d = u["strony"]["start"]["desktop"]
    assert d["dpr"] == 2 and d["szer"] == 1920 and d["przygotowanie"]["ukryte"] >= 1 and d["przygotowanie"]["przypiete"] >= 1
    ids = {c["id"]: c for c in d["cele"]}
    assert ids["naglowek-1"]["tekst"] == "Chleb co rano" and ids["naglowek-1"].get("wycinek")
    n = ids["naglowek-1"]["napis"]                                   # h1 na całą szerokość, napis krótki: ramka tekstu
    assert n["x"] == ids["naglowek-1"]["x"] and n["w"] < ids["naglowek-1"]["w"] / 2 and ids["cena-1"]["napis"]["w"] < 100
    assert ids["cena-1"]["tekst"] == "18 zł" and ids["dol"]["y"] > 2600 and ids["dol"].get("wycinek")
    assert all((out / "film" / k["plik"]).exists() for k in d["kafle"] + d["pusta"]) and d["pusta"]
    assert (out / "marka.css").read_text(encoding="utf-8").count("--marka-") >= 8

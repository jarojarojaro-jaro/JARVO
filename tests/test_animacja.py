"""HQ: animacja HTML z podglądem na żywo: schemat parametrów, zapis, stan pomiaru, mostek, biblioteki /_lib/."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


an = _load("animacja_test", ROOT / "hq" / "plugin" / "animacja.py")
core = _load("jarvo_hq_core", ROOT / "hq" / "plugin" / "hq_core.py")
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-wideo" / "scripts"))
import pomiar as pm  # noqa: E402

SCHEMAT = {"pola": [
    {"klucz": "tlo", "typ": "kolor", "etykieta": "Tło", "wartosc": "#0b1220"},
    {"klucz": "tytul", "typ": "tekst", "etykieta": "Tytuł", "wartosc": "Kawa z palarni Jarvo"},
    {"klucz": "tempo", "typ": "liczba", "etykieta": "Tempo", "min": 0.5, "max": 2, "krok": 0.05, "wartosc": 1},
    {"klucz": "wejscie", "typ": "krzywa", "etykieta": "Wejście", "wartosc": [0.16, 1, 0.3, 1]},
    {"klucz": "logo", "typ": "przelacznik", "etykieta": "Logo", "wartosc": True},
    {"klucz": "styl", "typ": "wybor", "etykieta": "Styl", "opcje": ["pelny", "minimal"], "wartosc": "pelny"}]}


@pytest.fixture
def anim(tmp_path):
    d = tmp_path / "out" / "wideo" / "src" / "kawa"
    d.mkdir(parents=True)
    (d / "index.html").write_text("<script>window.__seek = (t) => {}; window.__ready = true;</script>", encoding="utf-8")
    (d / "parametry.json").write_text(json.dumps(SCHEMAT, ensure_ascii=False), encoding="utf-8")
    return d / "index.html"


def test_rozpoznanie_animacji(tmp_path, anim):
    strona = tmp_path / "strona.html"
    strona.write_text("<h1>Zwykła strona</h1>", encoding="utf-8")
    assert an.to_animacja(anim) and not an.to_animacja(strona) and not an.to_animacja(tmp_path / "brak.html")
    (anim.parent / "parametry.json").unlink()
    assert an.to_animacja(anim)                                   # sam __seek wystarcza
    assert core.file_entry(anim, tmp_path)["anim"] is True and "anim" not in core.file_entry(strona, tmp_path)


def test_schemat_i_wartosci(anim):
    p = an.wczytaj(anim)
    assert [f["klucz"] for f in p["pola"]] == ["tlo", "tytul", "tempo", "wejscie", "logo", "styl"]
    assert p["pola"][0]["wartosc"] == "#0B1220" and p["pola"][2]["krok"] == 0.05
    zle = [({"pola": [{"klucz": "1x", "typ": "kolor", "wartosc": "#000000"}]}, "klucz"),
           ({"pola": [{"klucz": "a", "typ": "film", "wartosc": 1}]}, "typ"),
           ({"pola": [{"klucz": "a", "typ": "liczba", "min": 2, "max": 1, "wartosc": 1}]}, "min < max"),
           ({"pola": [{"klucz": "a", "typ": "liczba", "min": 0, "max": 1, "wartosc": 3}]}, "poza zakresem"),
           ({"pola": [{"klucz": "a", "typ": "wybor", "opcje": ["x"], "wartosc": "x"}]}, "2 opcji"),
           ({"pola": [{"klucz": "a", "typ": "krzywa", "wartosc": [2, 0, 0, 1]}]}, "x1, x2"),
           ({"pola": [{"klucz": "a", "typ": "kolor", "wartosc": "red"}, ]}, "#RRGGBB"),
           ({"pola": [{"klucz": "a", "typ": "tekst", "wartosc": "x"}, {"klucz": "a", "typ": "tekst", "wartosc": "y"}]}, "różne"),
           ({"lista": []}, "pola")]
    for dane, komunikat in zle:
        with pytest.raises(an.ParamError, match=komunikat):
            an.schemat(dane)
    (anim.parent / "parametry.json").write_text("{zepsuty", encoding="utf-8")
    assert an.wczytaj(anim)["pola"] == [] and an.wczytaj(anim)["blad"]


def test_zapis_tylko_pol_ze_schematu(anim):
    pola = an.zapisz(anim, {"tlo": "#ff0000", "tempo": 1.5, "wejscie": [0.34, 1.56, 0.64, 1], "logo": False})
    zapis = json.loads((anim.parent / "parametry.json").read_text(encoding="utf-8"))
    wart = {f["klucz"]: f["wartosc"] for f in zapis["pola"]}
    assert wart["tlo"] == "#FF0000" and wart["tempo"] == 1.5 and wart["logo"] is False and wart["tytul"] == "Kawa z palarni Jarvo"
    assert zapis["pola"][2]["max"] == 2 and [f["klucz"] for f in pola][0] == "tlo"
    for zle, msg in (({"nowe": 1}, "nieznane"), ({"tempo": 9}, "poza zakresem"), ({"styl": "inny"}, "jedna z opcji"),
                     ({"tytul": "x" * 401}, "400"), ({}, "brak wartości"), ({"logo": "tak"}, "tak/nie")):
        with pytest.raises(an.ParamError, match=msg):
            an.zapisz(anim, zle)
    assert json.loads((anim.parent / "parametry.json").read_text(encoding="utf-8")) == zapis      # odrzucenie niczego nie zmienia


def test_stan_pomiaru_i_nieaktualnosc_po_zapisie(anim, monkeypatch):
    assert an.pomiar(anim) is None
    monkeypatch.setitem(sys.modules, "jarvo_hq_pomiar", pm)
    ust = {"dlugosc": 6}
    raport = {"kiedy": "2026-10-02T10:00:00", "odcisk": pm.odcisk(anim, ust), "ustawienia": ust,
              "pokrycie": {"pelne": True, "tryb": "pelny", "hz": 10, "do": 6}, "werdykt": {"ok": True, "bledy": 0},
              "ustalenia": [{"kod": "martwy_odcinek", "waga": "ostrz", "opis": "stoi", "poprawka": "ruch", "od": 3, "do": 6},
                            {"kod": "kontrast", "waga": "blad", "opis": "1.7:1", "poprawka": "tło", "od": 1, "do": 1.1, "wyjatek": "celowo"}]}
    (anim.parent / "pomiar.json").write_text(json.dumps(raport), encoding="utf-8")
    s = an.pomiar(anim)
    assert s["aktualny"] and s["powody"] == [] and [u["kod"] for u in s["ustalenia"]] == ["martwy_odcinek", "kontrast"]
    an.zapisz(anim, {"tempo": 1.25})                            # zmiana parametrów = pomiar nieaktualny
    s = an.pomiar(anim)
    assert not s["aktualny"] and "zmieniły się" in s["powody"][0]


def test_most_i_wstrzykniecie():
    assert an.wstrzyknij_most(b"<html><body><p>x</p></BODY></html>").endswith(b'<script src="/_jarvo/most.js"></script></BODY></html>')
    assert an.wstrzyknij_most(b"<p>bez body</p>").endswith(b'<script src="/_jarvo/most.js"></script>')
    js = an.MOST_JS
    assert "e.source !== parent" in js and 'd.jarvo !== "hq"' in js and "__setParams" in js and "__params" in js
    assert "postMessage" in js and "eval(" not in js and "innerHTML" not in js


def test_biblioteki_lib_tylko_z_node_modules(tmp_path):
    nm = tmp_path / "node_modules"
    (nm / "gsap" / "dist").mkdir(parents=True)
    (nm / "gsap" / "dist" / "gsap.min.js").write_text("gsap", encoding="utf-8")
    (nm / ".bin").mkdir()
    (nm / ".bin" / "x").write_text("x", encoding="utf-8")
    (tmp_path / "sekret.txt").write_text("tajne", encoding="utf-8")
    (nm / "link").symlink_to(tmp_path / "sekret.txt")
    assert core.lib_file("gsap/dist/gsap.min.js", nm) == (nm / "gsap" / "dist" / "gsap.min.js").resolve()
    for zle in ("../sekret.txt", ".bin/x", "link", "gsap", "", "gsap/dist/brak.js"):
        assert core.lib_file(zle, nm) is None, zle


def test_plugin_ma_modul_animacji_i_pomiaru(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import hqbuild
    dash = hqbuild.build_plugin(tmp_path / "jarvo-hq")
    assert (dash / "animacja.py").is_file() and (dash / "pomiar.py").is_file()
    js = (dash / "dist" / "index.js").read_text(encoding="utf-8")
    assert "// ---- 47-animacja.js" in js and "AnimCtx.Provider" in js

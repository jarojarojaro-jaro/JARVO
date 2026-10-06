"""gramatyka.py: spec gramatyki explainera (szablony, słowa lektora → at, kontrola liczb i tekstu) i strona klipu."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "profiles/jarvo-wideo/scripts"))
import gramatyka as gm  # noqa: E402

OS = {"dlugosc": 20, "lektor": "lektor.wav", "chwile": {"start": 0, "u2": 5.0, "u2.koniec": 12.0},
      "zdania": [{"slowa": [{"tekst": "Najpierw", "start": 0.2, "koniec": 0.6}, {"tekst": "ranking,", "start": 2.0, "koniec": 2.4}]},
                 {"slowa": [{"tekst": "W", "start": 5.1, "koniec": 5.2}, {"tekst": "2022", "start": 5.3, "koniec": 5.8},
                            {"tekst": "przychody", "start": 6.0, "koniec": 6.5}, {"tekst": "wzrosły", "start": 6.6, "koniec": 7.0},
                            {"tekst": "Ranking", "start": 9.0, "koniec": 9.5}, {"tekst": "rekordowy", "start": 10.0, "koniec": 10.5},
                            {"tekst": "ranking.", "start": 11.0, "koniec": 11.4}]}]}


def zapisz(tmp_path, spec: dict, os_: dict | None = None, fakty: dict | None = None, katalog: str = "klip"):
    d = tmp_path / katalog
    d.mkdir(parents=True, exist_ok=True)
    if os_ is not None:
        (tmp_path / "os_czasu.json").write_text(json.dumps(os_), encoding="utf-8")
    if fakty is not None:
        (tmp_path / "fakty.json").write_text(json.dumps(fakty, ensure_ascii=False), encoding="utf-8")
    plik = d / "spec.json"
    plik.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return plik


@pytest.mark.parametrize("nazwa", sorted(gm.GRAMATYKI))
@pytest.mark.parametrize("fmt", sorted(gm.FORMATY))
def test_szablon_przechodzi_sprawdzenie(tmp_path, nazwa, fmt):
    out = tmp_path / nazwa / "spec.json"
    assert gm.main(["szablon", nazwa, "--format", fmt, "-o", str(out)]) == 0
    spec = json.loads(out.read_text(encoding="utf-8"))
    r = gm.rozwiaz(spec, out)
    assert r["bledy"] == [] and r["spec"]["grammar"] == gm.GRAMATYKI[nazwa]["id"]
    assert not [o for o in r["ostrzezenia"] if "pion" in o or "upDown" in o]
    assert {q["kind"] for q in spec["cues"]} <= set(gm.GRAMATYKI[nazwa]["kinds"])
    if fmt == "9:16":
        assert (spec["width"], spec["height"], spec["safe"]) == (1080, 1920, {"top": 140, "bottom": 700})
    else:
        assert spec["safe"] == {"bottom": 250}                       # nad pasem napisów lektora (wideo_lib.PAS_NAPISOW)


def test_szablon_nie_nadpisuje(tmp_path):
    out = tmp_path / "s.json"
    gm.main(["szablon", "vox", "-o", str(out)])
    with pytest.raises(SystemExit, match="nadpisz"):
        gm.main(["szablon", "vox", "-o", str(out)])
    with pytest.raises(SystemExit, match="nieznana gramatyka"):
        gm.main(["szablon", "prowadzacy", "-o", str(tmp_path / "p.json")])


def test_slowo_lektora_w_oknie_klipu(tmp_path):
    spec = {"grammar": "kurzgesagt", "od": "u2", "do": "u2.koniec", "cues": [
        {"at": 0, "kind": "title", "text": "Tytuł"},
        {"slowo": "2022", "kind": "point", "text": "Punkt"},
        {"slowo": "ranking", "nth": 2, "offset": -0.2, "kind": "point", "text": "Drugi"},   # w oknie: 9,0 i 11,0
        {"slowo": "rekord*", "kind": "highlight"},
        {"slowo": "przychody wzrosły", "kind": "enter", "dur": 1}]}
    r = gm.rozwiaz(spec, zapisz(tmp_path, spec, OS))
    assert r["bledy"] == [], r["bledy"]
    assert r["spec"]["duration"] == 7.0 and r["od"] == 5.0
    assert [q["at"] for q in r["spec"]["cues"]] == [0, 0.3, 5.8, 5.0, 1.0]
    assert all(not set(q) & {"slowo", "nth", "offset"} for q in r["spec"]["cues"])
    assert not set(r["spec"]) & set(gm.DODATKI)


def test_slowo_bledy(tmp_path):
    spec = {"grammar": "vox", "duration": 4, "cues": [{"slowo": "ranking", "nth": 3, "kind": "point"},
                                                       {"slowo": "przychody", "kind": "point"}]}
    r = gm.rozwiaz(spec, zapisz(tmp_path, spec, OS))
    assert len(r["bledy"]) == 2 and "nie pada w lektorze" in r["bledy"][0] and "Najpierw ranking," in r["bledy"][0]
    spec = {"grammar": "vox", "duration": 4, "od": "u9", "cues": [{"slowo": "x", "kind": "point"}]}
    r = gm.rozwiaz(spec, zapisz(tmp_path / "bez", spec))
    assert any("chwila lektora" in b for b in r["bledy"]) and any("bez os_czasu" in b for b in r["bledy"])


def test_rodzaje_czasy_i_zasady(tmp_path):
    spec = {"grammar": "t3_finance_chart", "duration": 5, "width": 1080, "height": 1920,
            "data": {"title": "Tytuł", "source": "Źródło: dane przykładowe", "upDown": "cn",
                     "series": [{"label": "A", "value": 3}]},
            "cues": [{"at": 0, "kind": "title"}, {"at": 0.1, "kind": "pie"}, {"at": 6, "kind": "bar"},
                     {"at": 0.5, "kind": "number", "data": {"value": 3}}, {"at": 1, "kind": "highlight", "dur": 2},
                     {"at": 2, "kind": "highlight"}, {"kind": "bar"}]}
    r = gm.rozwiaz(spec, zapisz(tmp_path, spec))
    b, o = " | ".join(r["bledy"]), " | ".join(r["ostrzezenia"])
    assert "nie zna rodzaju „pie”" in b and "po końcu klipu" in b and "brak `at`" in b
    assert "pas napisów" in o and "upDown „cn”" in o and "tylko pierwszy `highlight`" in o
    assert "przewinięta" in o and "`dur` jest tu ignorowane" in o and "jeden punkt uwagi" in o
    assert r["spec"]["data"]["upDown"] == "cn"            # świadomy wybór zostaje, tylko ostrzeżenie
    spec = {"grammar": "wykresy", "duration": 3, "data": {"series": []}, "cues": [{"at": 0, "kind": "title"}]}
    assert gm.rozwiaz(spec, zapisz(tmp_path / "us", spec))["spec"]["data"]["upDown"] == "us"
    r = gm.rozwiaz({"grammar": "prowadzacy", "duration": 3, "cues": [{"at": 0, "kind": "title"}]}, tmp_path / "x.json")
    assert any("nie ma klipu" in b for b in r["bledy"])


def test_tekst_obrazy_i_liczby(tmp_path):
    fakty = {"fakty": [{"tekst": "Przychody 2022: 130,5 mln zł", "zrodla": [1]}], "niepewne": ["16,4 mln"]}
    spec = {"grammar": "prezentacja", "duration": 6, "data": {"title": "收入"}, "cues": [
        {"at": 0, "kind": "title"}, {"at": 1, "kind": "card", "text": "Przychody 130,5 mln zł", "image": "brak.png"},
        {"at": 2, "kind": "card", "text": "Było 16,4 mln", "image": "../obok.png"},
        {"at": 3, "kind": "number", "data": {"value": 42.5}, "text": "x"}]}
    (tmp_path / "obok.png").write_bytes(b"png")
    r = gm.rozwiaz(spec, zapisz(tmp_path, spec, fakty=fakty))
    b, o = " | ".join(r["bledy"]), " | ".join(r["ostrzezenia"])
    assert "chiński znak" in b and "brak obrazu brak.png" in b and "spoza katalogu spec" in b
    assert "„16,4 mln” jest na liście niepewnych" in b and "„42,5” bez źródła" in o and "130,5" not in b + o
    # dane przykładowe: liczb nie sprawdzamy
    spec2 = {"grammar": "kinetyczna", "duration": 4, "cues": [{"at": 1, "kind": "number", "data": {"value": 77},
                                                               "text": "dane przykładowe"}]}
    # (jedyne ostrzeżenie: spec bez `safe` wchodzi w pas napisów lektora)
    assert gm.rozwiaz(spec2, zapisz(tmp_path / "p", spec2, fakty=fakty))["ostrzezenia"] == [
        "poziom bez `safe.bottom` ≥ 250: pas napisów lektora (y 830–1005 px) wejdzie na treść"]


def test_strona_klipu(tmp_path, monkeypatch):
    spec = {"grammar": "historyjka", "duration": 2, "postac": {"koszulka": "#C0392B"},
            "cues": [{"at": 0.2, "kind": "point", "text": "Zażółć </script> jaźń"}]}
    plik = zapisz(tmp_path, spec)
    r = gm.rozwiaz(json.loads(plik.read_text(encoding="utf-8")), plik)
    out = gm.strona(plik, r, alfa=True)
    html = out.read_text(encoding="utf-8")
    assert out == plik.with_suffix(".html")
    assert html.index("/_lib/huashu/lib/fonts.js") < html.index("/_lib/huashu/lib/toon.js") < html.index("/_lib/jarvo/huashu_pl.js") \
        < html.index("window.CLIP_SPEC") < html.index("/_lib/huashu/clip.js")
    assert 'window.POSTAC = {"koszulka": "#C0392B"}' in html and "<\\/script>" in html and "</script> jaźń" not in html
    dane = json.loads(html.split("window.CLIP_SPEC = ", 1)[1].split(";\n</script>", 1)[0].replace("<\\/", "</"))
    assert dane["grammar"] == "y4_storytime" and dane["alpha"] is True and "postac" not in dane
    assert "background:transparent" in html and "VO_ENV" not in html


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="brak ffmpeg")
def test_usta_z_obwiedni_lektora(tmp_path):
    wav = tmp_path / "lektor.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=1", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-filter_complex", "[1]atrim=0:1[c];[0][c]concat=n=2:v=0:a=1",
                    "-ar", "44100", str(wav)], check=True)
    os_ = {**OS, "lektor": "lektor.wav"}
    spec = {"grammar": "historyjka", "duration": 2, "fps": 10, "cues": [{"at": 0, "kind": "point", "text": "Hej"}]}
    plik = zapisz(tmp_path, spec, os_)
    r = gm.rozwiaz(spec, plik)
    html = gm.strona(plik, r).read_text(encoding="utf-8")
    env = json.loads(html.split("window.VO_ENV = ", 1)[1].split(";\n", 1)[0])
    assert env["fps"] == 10 and len(env["a"]) == 20
    assert min(env["a"][:9]) > 0.5 and max(env["a"][11:]) < 0.05      # głos w 1. sekundzie, cisza w 2.


def test_wzor_prowadzacego_bez_filmu(capsys):
    assert gm.main(["wzor", "prowadzacy"]) == 2
    assert "spacex_lin" in capsys.readouterr().out

"""Brief do filmu Sherlocka (fakty.py): szablon, kontrola liczb z rejestrem źródeł i ten sam zapis liczb co u Wideografa."""

from __future__ import annotations

import json
import sys

import pytest

from conftest import load_script

fakty = load_script("profiles/jarvo-sherlock/scripts/fakty.py")
sources = load_script("profiles/jarvo-sherlock/scripts/sources.py")
wl = sys.modules.get("wideo_lib") or load_script("profiles/jarvo-wideo/scripts/wideo_lib.py", "wideo_lib")

GUS = "W 2025 roku piekarnie sprzedały 3 500 000 bochenków. Średnio klient czekał 7 minut."
BLOG = "Podobno 40% klientów wychodzi z kolejki."


def brief(**zmiany) -> dict:
    b = {"temat": "Kolejka w piekarni", "dlugosc_s": 90, "przeslanie": "Kolejka rośnie przez zmienność, nie przez piekarza.",
         "sytuacja": "Wchodzisz do piekarni o siódmej, przed tobą dziesięć osób.",
         "liczby": [{"id": "L1", "wartosc": "3,5 mln", "jednostka": "bochenków", "twierdzenie": "W 2025 sprzedano 3,5 mln bochenków.",
                     "zrodla": [1], "tier": "A", "skala": "jeden co 9 sekund", "data": "2025"},
                    {"id": "L2", "wartosc": "7", "jednostka": "minut", "twierdzenie": "Klient czeka średnio 7 minut.",
                     "zrodla": [1, 2], "tier": "A", "skala": "tyle, co zaparzenie kawy", "data": "2025"},
                    {"id": "L3", "wartosc": "12", "jednostka": "osób", "twierdzenie": "W szczycie stoi 12 osób.",
                     "zrodla": [1], "tier": "A", "skala": "-", "data": "2025"}],
         "analogie": [{"analogia": "lejek", "pasuje": "przepustowość", "psuje_sie": "ludzie nie są płynem"},
                      {"analogia": "autostrada", "pasuje": "korek z falą", "psuje_sie": "w piekarni nikt nie zmienia pasa"},
                      {"analogia": "kasa w sklepie", "pasuje": "jedno okienko", "psuje_sie": "–"}],
         "slowniczek": [{"termin": "Little's law", "prosto": "ile osób stoi = jak szybko przychodzą × jak długo czekają",
                         "wymowa": "prawo Littla"}],
         "niepewne": ["40% klientów wychodzi z kolejki [3]"]}
    b.update(zmiany)
    return b


@pytest.fixture()
def rejestr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gus.txt").write_text(GUS, encoding="utf-8")
    (tmp_path / "blog.txt").write_text(BLOG, encoding="utf-8")
    sources.main(["add", "https://stat.gov.pl/piekarnie", "--tier", "A", "--tekst", "gus.txt"])
    sources.main(["add", "https://media.example/kolejki", "--tier", "B"])              # [2] tylko wynik wyszukiwania
    sources.main(["add", "https://blog.example/kolejka", "--tier", "D", "--tekst", "blog.txt"])
    return tmp_path / "out" / "zrodla.json"


def test_szablon_i_niewypelnione_pola(tmp_path, capsys):
    out = tmp_path / "out" / "fakty.json"
    assert fakty.main(["szablon", "-o", str(out), "--temat", "Kolejki", "--dlugosc", "120"]) == 0
    with pytest.raises(SystemExit):
        fakty.main(["szablon", "-o", str(out)])                       # nie nadpisuje bez --nadpisz
    b = json.loads(out.read_text(encoding="utf-8"))
    assert b["temat"] == "Kolejki" and b["dlugosc_s"] == 120 and b["wersja"] == fakty.WERSJA
    capsys.readouterr()
    assert fakty.main(["sprawdz", str(out), "--json"]) == 1
    w = json.loads(capsys.readouterr().out)
    assert any(x.startswith("sytuacja: niewypełnione") for x in w["bledy"])
    assert any("liczby[0].wartosc" in x for x in w["bledy"]) and w["zakres_liczb"] == "8–10"


def test_liczby_z_rejestrem(rejestr):
    w = fakty.sprawdz(brief(), rejestr)
    assert w["bledy"] == ["liczba L3: wartości „12” nie ma w tekście źródeł [1]: popraw liczbę albo źródło"]
    assert w["liczby"] == 3 and w["wymowa"] == 1 and w["niepewne"] == 1 and w["zakres_liczb"] == "3–6"
    zle = brief(liczby=[
        {"id": "L1", "wartosc": "40%", "twierdzenie": "40% wychodzi", "zrodla": [3]},
        {"id": "L1", "wartosc": "7", "twierdzenie": "czeka 7 minut", "zrodla": [2]},
        {"id": "L3", "wartosc": "3,5 mln", "twierdzenie": "sprzedaż", "zrodla": [1], "tier": "A+"},
        {"id": "L4", "wartosc": "siedem", "twierdzenie": "czeka", "zrodla": [9]},
        {"id": "L5", "wartosc": "7", "twierdzenie": "czeka", "zrodla": "1"},
        {"id": "L6", "wartosc": "7", "twierdzenie": "czeka", "zrodla": [2, 1], "tier": "A"}],
        analogie=[{"analogia": "lejek", "pasuje": "x"}])
    b = " | ".join(fakty.sprawdz(zle, rejestr)["bledy"])
    assert "liczba L1: tylko źródła D" in b and "liczba L1: „id” się powtarza" in b
    assert "źródła [2] nieprzeczytane" in b and "liczba L3: tier A–D" in b
    assert "liczba L4: „wartosc” cyframi" in b and "źródeł [9] nie ma w rejestrze" in b
    assert "liczba L5: „zrodla” to lista" in b and "analogia #1: brak „psuje_sie”" in b
    assert "L6" not in b                                               # jedno przeczytane źródło A wystarczy
    tier = fakty.sprawdz(brief(liczby=[{**brief()["liczby"][0], "zrodla": [3], "wartosc": "40%", "tier": "A"}]), rejestr)
    assert any("tylko źródła D" in x for x in tier["bledy"])
    o = " | ".join(fakty.sprawdz(brief(liczby=[{"id": "L1", "wartosc": "3,5 mln", "twierdzenie": "x", "zrodla": [1]}],
                                       analogie=[], dlugosc_s=200), rejestr)["ostrzezenia"])
    assert "bez „skala”" in o and "bez „data”" in o and "analogie: 0" in o and "liczby: 1, na film 200 s potrzeba 10–16" in o


def test_cli_rejestr_obok_briefu_i_bez_rejestru(rejestr, tmp_path, capsys):
    plik = tmp_path / "out" / "fakty.json"
    dobry = brief()
    dobry["liczby"] = dobry["liczby"][:2]
    plik.write_text(json.dumps(dobry, ensure_ascii=False), encoding="utf-8")
    assert fakty.main(["sprawdz", str(plik)]) == 0                    # rejestr out/zrodla.json obok briefu
    assert "✓" in capsys.readouterr().out
    inny = tmp_path / "inny" / "fakty.json"
    inny.parent.mkdir()
    inny.write_text(json.dumps(brief()), encoding="utf-8")
    assert fakty.main(["sprawdz", str(inny), "--json"]) == 0           # bez rejestru: tylko ostrzeżenie
    w = json.loads(capsys.readouterr().out)
    assert w["rejestr"] is None and any("bez rejestru" in o for o in w["ostrzezenia"])


@pytest.mark.parametrize("tekst", ["W 2024 roku 3,5 mln bochenków, czyli 3 500 000; 12.480 zł; 1,234 users; 40% i 7 tys. osób",
                                   "3 500 i 3 500 · 0,75 · 2 mld · 15 milionów"])
def test_ten_sam_zapis_liczb_co_wideograf(tekst):
    assert fakty.liczby(tekst) == wl.liczby_w_tekscie(tekst)


def test_fakty_sherlocka_pokrywaja_lektora_wideografa():
    pewne, niepewne = wl.liczby_faktow(brief())
    assert wl.sprawdz_liczby("Sprzedano 3 500 000 bochenków, czekasz 7 minut, a 40% odchodzi", pewne, niepewne) == [("40", "niepewna")]

"""Demo strony Wideografa: scenariusz (walidacja, domeny, hasła), oś napisów i SRT; nagranie tylko po udanej próbie."""

from __future__ import annotations

import json

import pytest

from conftest import load_script

D = load_script("profiles/jarvo-wideo/scripts/demo_strony.py")

SC = {"url": "http://127.0.0.1:4321/", "rozmiar": [1280, 720], "domeny": ["nova.pl"],
      "kroki": [{"napis": "Zamówienie w 20 sekund"}, {"klik": "text=Cennik"}, {"wpisz": "#email", "tekst": "a@example.com"},
                {"wybierz": "select#plan", "opcja": "Firma"}, {"przewin": 600}, {"idz": "https://sklep.nova.pl/koszyk"},
                {"czekaj": 1.5}, {"napis": ""}]}


def test_valid_scenario():
    assert D.sprawdz_scenariusz(SC, env={}) == []


def test_scenario_errors():
    zly = {"url": "ftp://x", "rozmiar": [10, 10], "tempo": 9, "skala": 5,
           "kroki": [{"skok": 1}, {"klik": ""}, {"wpisz": "#p", "tekst": "x"}, {"wpisz": "#haslo", "tekst": "Tajne123"},
                     {"wpisz": "#h", "tekst_env": "DEMO_HASLO"}, {"wybierz": "select"}, {"idz": "https://obca-strona.pl/"}]}
    bledy = "\n".join(D.sprawdz_scenariusz(zly, env={}))
    for fragment in ("url:", "rozmiar", "tempo", "skala", "nieznany typ", "klik wymaga selektora", "hasło tylko przez tekst_env",
                     "brak zmiennej środowiskowej DEMO_HASLO", "wybierz wymaga pola opcja", "poza stroną"):
        assert fragment in bledy, fragment
    assert D.sprawdz_scenariusz({**SC, "kroki": [{"wpisz": "#h", "tekst_env": "DEMO_HASLO"}]}, env={"DEMO_HASLO": "x"}) == []


def test_domains():
    assert D.dozwolony("/blog", SC) and D.dozwolony("http://localhost:9120/x", SC)
    assert D.dozwolony("https://nova.pl/", SC) and D.dozwolony("https://sklep.nova.pl/", SC)
    assert not D.dozwolony("https://github.com/x", SC) and not D.dozwolony("https://evilnova.pl/", SC)


def test_subtitle_timeline_and_srt():
    zd = [{"t": 0.5, "typ": "napis", "tekst": "Zamówienie w 20 sekund"}, {"t": 3.0, "typ": "klik"},
          {"t": 6.2, "typ": "napis", "tekst": "Krok 2: cennik"}, {"t": 9.0, "typ": "napis", "tekst": ""},
          {"t": 10.0, "typ": "napis", "tekst": "Koniec"}]
    os_ = D.os_z_krokow(zd, koniec=12.0)
    assert os_ == [(0.5, 6.2, "Zamówienie w 20 sekund"), (6.2, 9.0, "Krok 2: cennik"), (10.0, 12.0, "Koniec")]
    s = D.srt(os_)
    assert s.startswith("1\n00:00:00,500 --> 00:00:06,200\nZamówienie w 20 sekund\n") and "3\n00:00:10,000 --> 00:00:12,000" in s


def test_pacing_and_labels():
    assert D.pauza({"klik": "x"}, "klik", 1.5) == pytest.approx(3.0)
    assert D.pauza({"klik": "x", "pauza": 0.5}, "klik", 2.0) == pytest.approx(1.0)
    assert D.etykieta({"klik": "text=Cennik"}) == "klik text=Cennik"
    assert D.etykieta({"klik": "a", "etykieta": "menu"}) == "menu"


def test_record_refuses_without_rehearsal(tmp_path, monkeypatch):
    plik = tmp_path / "demo.json"
    plik.write_text(json.dumps(SC), encoding="utf-8")
    monkeypatch.setattr(D, "ensure_playwright", lambda: None)
    monkeypatch.setattr(D, "proba", lambda sc: ["krok 2 (klik text=Cennik): nie widać elementu"])
    monkeypatch.setattr(D, "graj", lambda *a, **k: pytest.fail("nagranie mimo nieudanej próby"))
    with pytest.raises(SystemExit, match="próba nieudana"):
        D.main(["nagraj", str(plik), "-o", str(tmp_path / "demo.mp4")])

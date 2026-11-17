"""hq/plugin/lustro.py: teksty do tematu (🖥 prośba ≤ 300, odpowiedź po 4000), token z .env, sendMessage do atrapy
Bot API (bez tokenu w błędzie), kolejka w rozmowy.db: jedna wysyłka (lustro_at), 3 próby, nie_doszlo, wyłączone lustro."""
from __future__ import annotations

import json

import pytest

from atrapa_telegrama import AtrapaTelegrama
from conftest import load_script

lu = load_script("hq/plugin/lustro.py", "jarvo_test_lustro")
rz = load_script("hq/plugin/rozmowy.py", "jarvo_test_lustro_rozmowy")
TOKEN = "123456:TEST-token-atrapy"


@pytest.fixture
def tg(monkeypatch):
    a = AtrapaTelegrama()
    monkeypatch.setenv("JARVO_TELEGRAM_API", a.adres)
    yield a
    a.zamknij()


class Hub:
    def __init__(self):
        self.zdarzenia = []

    def nadaj(self, typ, dane, watek_id=None):
        self.zdarzenia.append((typ, dane))


def test_wiadomosci_tna_prosbe_i_odpowiedz():
    assert lu.wiadomosci("  ala\n ma  kota ", "ok") == ["🖥 ala ma kota", "ok"]
    dluga = lu.wiadomosci("x" * 500, "")
    assert len(dluga) == 1 and len(dluga[0]) == 2 + 300 and dluga[0].endswith("…")
    odp = ("linia\n" * 1500).strip()
    czesci = lu.wiadomosci("", odp)
    assert all(len(c) <= 4000 for c in czesci) and "\n".join(czesci) == odp
    assert lu.wiadomosci("", "") == []


def test_token_z_env(tmp_path):
    assert lu.token(tmp_path) == ""
    (tmp_path / ".env").write_text(f"INNY=1\nexport TELEGRAM_BOT_TOKEN=\"{TOKEN}\"\n", encoding="utf-8")
    assert lu.token(tmp_path) == TOKEN


def test_wyslij_do_tematu_i_blad_bez_tokenu(tg):
    assert lu.wyslij(TOKEN, "-1001", "7", "hej") == 1
    assert lu.wyslij(TOKEN, "-1001", "1", "general") == 2
    assert tg.wyslane[0] == {"token": TOKEN, "chat_id": "-1001", "message_thread_id": 7, "text": "hej",
                             "disable_web_page_preview": True}
    assert "message_thread_id" not in tg.wyslane[1]                     # General: bez wątku
    tg.awaria = 1
    with pytest.raises(lu.BladLustra) as e:
        lu.wyslij(TOKEN, "-1001", "7", "x")
    assert TOKEN not in str(e.value) and "chat not found" in str(e.value)


@pytest.fixture
def swiat(tmp_path):
    db = rz.Rozmowy(tmp_path / "rozmowy.db")
    db.migruj()
    db.zsynchronizuj_rozmowcow([
        {"klucz": "f:jarvo", "zrodlo": "flota", "zaplecze": "hermes", "profil": "jarvo", "nazwa": "Jarvo", "kolejnosc": 1,
         "czat": "-1001", "watek_tg": "1"},
        {"klucz": "f:bez", "zrodlo": "flota", "zaplecze": "hermes", "profil": "bez", "nazwa": "Bez tematu", "kolejnosc": 2},
        {"klucz": "s:op", "zrodlo": "sesje", "zaplecze": "omp", "wpis": "op", "nazwa": "Operator", "kolejnosc": 0,
         "czat": "-1001", "watek_tg": "5"}])
    (tmp_path / ".env").write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\n", encoding="utf-8")
    zegar = [1000.0]
    hub = Hub()
    lustro = lu.Lustro(db, tmp_path, hub, zegar=lambda: zegar[0])
    return db, lustro, hub, zegar


def _przebieg(db, klucz, tekst="sprawdź pogodę"):
    wid = db.rozmowca(klucz)["watek_id"]
    e = db.dodaj_wpis(wid, rodzaj="wlasciciel", tekst=tekst)
    return db.dodaj_przebieg(watek_id=wid, wpis_id=e["id"], agent=db.rozmowca(klucz)["cel"])


def test_jedna_wysylka_po_koncu(swiat, tg):
    db, lustro, _hub, _z = swiat
    p = _przebieg(db, "f:jarvo")
    assert lustro.po_koncu(p, "gotowe", "Słonecznie.") is True
    assert lustro.po_koncu(db.przebieg(p["id"]), "gotowe", "Słonecznie.") is False    # już w kolejce
    assert lustro.runda() == 1 and lustro.runda() == 0
    assert tg.teksty() == ["🖥 sprawdź pogodę", "Słonecznie."]
    p2 = db.przebieg(p["id"])
    assert p2["lustro_at"] and json.loads(p2["lustro"]) == {"stan": "ok", "message_id": 2}
    # restart: nowa instancja nie wysyła drugi raz
    assert lu.Lustro(db, lustro.dane, None).runda() == 0 and len(tg.wyslane) == 2


def test_bez_lustra_bez_tematu_omp_i_blad(swiat, tg):
    db, lustro, _hub, _z = swiat
    assert lustro.po_koncu(_przebieg(db, "f:bez"), "gotowe", "x") is False          # brak tematu
    assert lustro.po_koncu(_przebieg(db, "s:op"), "gotowe", "x") is False           # omp: lustro robi skrzynka
    assert lustro.po_koncu(_przebieg(db, "f:jarvo"), "blad", "x") is False
    db.zmien_rozmowce("f:jarvo", lustro=False)
    assert lustro.po_koncu(_przebieg(db, "f:jarvo"), "gotowe", "x") is False
    assert lustro.runda() == 0 and tg.wyslane == []


def test_trzy_proby_potem_nie_doszlo(swiat, tg):
    db, lustro, hub, zegar = swiat
    p = _przebieg(db, "f:jarvo")
    lustro.po_koncu(p, "gotowe", "odp")
    tg.awaria = 10
    assert lustro.runda() == 0
    assert lustro.runda() == 0                                   # następna próba dopiero po 30 s
    for _ in range(2):
        zegar[0] += lu.ODSTEP_S
        lustro.runda()
    assert json.loads(db.przebieg(p["id"])["lustro"]) == {"stan": "nie_doszlo", "proby": 3}
    assert hub.zdarzenia == [("przebieg.lustro", {"przebieg_id": p["id"], "watek_id": p["watek_id"], "stan": "nie_doszlo"})]
    zegar[0] += 999
    tg.awaria = 0
    assert lustro.runda() == 0 and tg.wyslane == []


def test_brak_tokenu_to_tez_proba(swiat, tg):
    db, lustro, _hub, zegar = swiat
    (lustro.dane / ".env").unlink()
    p = _przebieg(db, "f:jarvo")
    lustro.po_koncu(p, "gotowe", "odp")
    lustro.runda()
    assert json.loads(db.przebieg(p["id"])["lustro"])["proby"] == 1 and tg.wyslane == []

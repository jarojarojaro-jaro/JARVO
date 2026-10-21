"""Lista agentów aplikacji (hq/plugin/agenci.py): flota z fleet.json, agenci testowi z agenci.json tylko z
`"test": true`, profilem `test-e2e-*` i przy JARVO_E2E=1; uchwyty bez kolizji; pamięć po mtime."""
import json
import os

import pytest

import hqbuild
from conftest import load_script

ag = load_script("hq/plugin/agenci.py", "jarvo_test_agenci")
wz = load_script("hq/plugin/wzmianki.py", "jarvo_test_wzmianki_agenci")


@pytest.fixture
def pliki(tmp_path):
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(hqbuild.fleet_json()), encoding="utf-8")
    agenci = tmp_path / "agenci.json"
    agenci.write_text(json.dumps({
        "test-e2e-a": {"handle": "teste2ea", "nazwa": "Test A", "test": True},
        "test-e2e-j": {"handle": "teste2ej", "nazwa": "Test Jarvo", "test": True},
        "test-e2e-x": {"handle": "web", "nazwa": "Kolizja", "test": True},           # uchwyt floty: odpada
        "wlasny-ksiegowa": {"handle": "ksiegowa", "nazwa": "Księgowa", "stan": "aktywny"},   # etap 8: jeszcze nie
        "jarvo-zly": {"handle": "zly", "test": True},                                 # nie test-e2e-*: odpada
    }), encoding="utf-8")
    return fleet, agenci


def test_bez_e2e_tylko_flota(pliki):
    a = ag.Agenci(*pliki, e2e=lambda: False)
    nazwy = a.nazwy()
    assert nazwy[0] == "jarvo" and "jarvo-web" in nazwy and not any(n.startswith("test-") for n in nazwy)
    web = a.agent("jarvo-web")
    assert web["handle"] == "web" and web["aliasy"] == ["web", "jarvo-web"] and web["nazwa"] == "Web"
    assert web["stan"] == "aktywny" and web["wlasny"] is False and web["test"] is False
    with pytest.raises(ValueError):
        a.profil("test-e2e-a")
    assert not a.moze_koordynowac("test-e2e-j") and a.moze_koordynowac("jarvo")


def test_z_e2e_agenci_testowi(pliki):
    a = ag.Agenci(*pliki, e2e=lambda: True)
    testowi = [x for x in a.lista() if x["test"]]
    assert [x["name"] for x in testowi] == ["test-e2e-a", "test-e2e-j"]
    assert a.profil("test-e2e-a") == "test-e2e-a" and a.moze_koordynowac("test-e2e-j")
    assert a.nazwy_wyswietlane()["test-e2e-a"] == "Test A"
    mapa = wz.mapa_aliasow(a.lista())
    assert mapa["teste2ea"] == "test-e2e-a" and mapa["web"] == "jarvo-web" and "ksiegowa" not in mapa
    for zly in ("../x", "Test", "wlasny-ksiegowa", "jarvo-zly"):
        with pytest.raises(ValueError):
            a.profil(zly)


def test_pamiec_po_mtime_i_brak_plikow(pliki, tmp_path):
    fleet, agenci = pliki
    a = ag.Agenci(fleet, agenci, e2e=lambda: True)
    assert len([x for x in a.lista() if x["test"]]) == 2
    agenci.write_text(json.dumps({"test-e2e-b": {"handle": "teste2eb", "test": True}}), encoding="utf-8")
    os.utime(agenci, ns=(1, 1))
    assert [x["name"] for x in a.lista() if x["test"]] == ["test-e2e-b"]
    pusta = ag.Agenci(tmp_path / "nie.json", tmp_path / "nie2.json", e2e=lambda: True)
    assert pusta.lista() == [] and pusta.moze_koordynowac("jarvo")


def test_e2e_z_env(monkeypatch):
    monkeypatch.setenv("JARVO_E2E", "1")
    assert ag.e2e()
    monkeypatch.setenv("JARVO_E2E", "0")
    assert not ag.e2e()

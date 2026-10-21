"""Uchwyty agentów (`handle` we fleet.yaml): walidator wymaga ich u aktywnych agentów i pilnuje formatu, słów
zarezerwowanych i jednoznaczności aliasów; fleet.json z HQ i fleet.json skarbca niosą uchwyt dalej."""
import re
from pathlib import Path

import fleetlib as fl
import hqbuild
import validate

REPO = Path(__file__).resolve().parents[1]


def _bledy(tmp_path, zamiana: tuple[str, str] | None = None, dopisz: str = "") -> list[str]:
    tekst = (REPO / "fleet.yaml").read_text(encoding="utf-8")
    if zamiana:
        assert zamiana[0] in tekst
        tekst = tekst.replace(zamiana[0], zamiana[1], 1)
    if dopisz:
        tekst = tekst.replace("\nshared:", dopisz + "\nshared:", 1)
    plik = tmp_path / "fleet.yaml"
    plik.write_text(tekst, encoding="utf-8")
    r = validate.Report()
    validate.check_uchwyty(fl.load_fleet(plik), r)
    return r.errors


def test_flota_ma_poprawne_uchwyty(tmp_path):
    assert _bledy(tmp_path) == []


def test_brak_uchwytu_u_aktywnego(tmp_path):
    assert any("jarvo-web: brak `handle`" in e for e in _bledy(tmp_path, ("    handle: web\n", "")))


def test_uchwyt_nie_ascii_i_za_dlugi(tmp_path):
    assert any("musi pasować" in e for e in _bledy(tmp_path, ("handle: lowca\n", "handle: łowca\n")))
    assert any("musi pasować" in e for e in _bledy(tmp_path, ("handle: web\n", "handle: w" + "e" * 16 + "\n")))
    assert any("musi pasować" in e for e in _bledy(tmp_path, ("handle: web\n", "handle: 1web\n")))


def test_uchwyt_zarezerwowany(tmp_path):
    assert any("słowo zarezerwowane" in e for e in _bledy(tmp_path, ("handle: web\n", "handle: file\n")))


def test_kolizja_uchwytow_i_aliasow(tmp_path):
    assert any("należy już do jarvo-web" in e for e in _bledy(tmp_path, ("handle: studio\n", "handle: web\n")))
    # alias z hq_short innego agenta: „Wideograf” → wideograf
    assert any("wideograf" in e and "należy już do" in e
               for e in _bledy(tmp_path, ("handle: studio\n", "handle: wideograf\n")))
    # dodatkowy alias z pola `aliasy`
    assert any("'web'" in e for e in _bledy(tmp_path, ("handle: ads\n", "handle: ads\n    aliasy: [Web]\n")))


def test_planowany_bez_uchwytu_nie_przeszkadza(tmp_path):
    wpis = ("\n  - name: jarvo-nowy\n    kind: specialist\n    title: \"Nowy\"\n    description: >-\n      x\n"
            "    model_tier: strong\n    telegram_topic: nowy\n    status: planned\n")
    assert _bledy(tmp_path, dopisz=wpis) == []


def test_fleet_json_niesie_uchwyt_i_aliasy():
    dane = hqbuild.fleet_json()
    web = next(a for a in dane["agents"] if a["name"] == "jarvo-web")
    assert web["handle"] == "web" and web["aliasy"] == ["web", "jarvo-web"]
    assert all(re.fullmatch(r"[a-z][a-z0-9]{1,15}", a["handle"]) for a in dane["agents"])


def test_nowy_agent_dostaje_uchwyt():
    tekst = (REPO / "scripts" / "new-agent.py").read_text(encoding="utf-8")
    assert "handle: {uchwyt}" in tekst

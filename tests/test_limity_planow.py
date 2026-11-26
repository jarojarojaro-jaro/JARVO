"""Limity planów w pasku panelu (hq/plugin/limity.py): raport `omp usage --json` → okna 5 h i tygodnia konta."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("jarvo_hq_limity_test", Path(__file__).parents[1] / "hq" / "plugin" / "limity.py")
limity = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(limity)


def test_okna_konta_bez_okien_jednego_modelu_i_z_kredytow():
    dane = {"reports": [
        {"provider": "anthropic", "metadata": {"subscriptionPlan": "Max 5x"}, "limits": [
            {"window": {"id": "7d", "resetsAt": 1_800_000_000_000}, "scope": {"tier": "fable"}, "amount": {"usedFraction": 0.9}},
            {"window": {"id": "7d", "resetsAt": 1_800_000_000_000}, "scope": {}, "amount": {"usedFraction": 0.18}},
            {"window": {"id": "5h", "resetsAt": 1_790_000_000_500}, "scope": {}, "amount": {"usedFraction": 0.07}}]},
        {"provider": "commandcode", "limits": [
            {"window": {"id": "5h"}, "scope": {}, "amount": {"used": 7, "limit": 14, "unit": "credits"}},
            {"scope": {"windowId": "balance"}, "amount": {"remaining": 0}}]},
        {"provider": "bez-okien", "limits": [{"scope": {}, "amount": {"remaining": 3}}]},
    ]}
    claude, cc = limity.z_raportow(dane)
    assert claude == {"id": "anthropic", "nazwa": "Claude", "plan": "Max 5x", "okna": [
        {"id": "5h", "procent": 7.0, "reset": 1_790_000_000.5}, {"id": "7d", "procent": 18.0, "reset": 1_800_000_000.0}]}
    assert cc["okna"] == [{"id": "5h", "procent": 50.0, "reset": None}] and cc["plan"] is None


def test_bez_omp_pusto_i_jedno_zapytanie_na_okres(monkeypatch):
    assert limity.Limity(program=lambda: None).pobierz()["dostawcy"] == []
    wywolania = []
    l = limity.Limity(program=lambda: "omp")
    monkeypatch.setattr(l, "_zapytaj", lambda: wywolania.append(1) or [])
    l.pobierz(); l.pobierz()
    assert len(wywolania) == 1


def test_konto_floty_command_code_zamiast_konta_z_omp(monkeypatch):
    """26.11: omp miał stare konto Command Code (0%), a flota pracuje na nowym (GOAT): pasek pokazuje konto floty."""
    cc = limity.z_commandcode({"windowLimits": {"fiveHour": {"used": 0.13, "cap": 14, "resetAt": 1_795_711_938_940},
                                                "weekly": {"used": 7.34, "cap": 35}}},
                              {"data": {"planId": "individual-goat"}})
    assert cc == {"id": "commandcode", "nazwa": "Command Code", "plan": "GOAT", "okna": [
        {"id": "5h", "procent": 0.9, "reset": 1_795_711_938.94}, {"id": "7d", "procent": 21.0, "reset": None}]}
    assert limity.z_commandcode({"windowLimits": {}}, None) is None
    l = limity.Limity(program=lambda: "omp", flota=lambda: [cc])
    monkeypatch.setattr(l, "_omp", lambda: [{"id": "commandcode", "plan": None, "okna": []}, {"id": "anthropic", "okna": []}])
    assert [(d["id"], d.get("plan")) for d in l.pobierz()["dostawcy"]] == [("commandcode", "GOAT"), ("anthropic", None)]

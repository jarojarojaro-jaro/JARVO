"""Runner evals: sprawdzenia deterministyczne i format scenariuszy."""

from __future__ import annotations

import fleetlib as fl
from conftest import REPO, load_script

evals = load_script("scripts/run-evals.py")


def test_deterministic_checks():
    scn = {"check": {"cards_assignees_include": ["tars-web", "tars-studio"], "cards_max": 2}}
    cards = [{"assignee": "tars-web"}, {"assignee": "tars-sherlock"}, {"assignee": "tars-web"}]
    fails = evals.deterministic(scn, "ok", cards)
    assert "brak karty dla tars-studio" in fails
    assert "utworzono 3 kart > 2" in fails
    assert evals.deterministic({"check": {"response_equals": "[SILENT]"}}, " [SILENT]\n", []) == []
    assert evals.deterministic({"check": {"response_equals": "[SILENT]"}}, "Jasne!", [])


def test_checks_reference_real_agents():
    active = {a.name for a in fl.load_fleet().active()}
    for path in (REPO / "evals").glob("*/scenarios.yaml"):
        for scn in fl.load_yaml(path)["scenarios"]:
            for agent in (scn.get("check") or {}).get("cards_assignees_include") or []:
                assert agent in active, f"{path.parent.name}/{scn['id']}: {agent}"


def test_dry_run_lists_all(capsys, monkeypatch):
    monkeypatch.setenv("TARS_EVAL_ALLOW_PROD", "1")
    assert evals.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    total = sum(len(fl.load_yaml(p)["scenarios"]) for p in (REPO / "evals").glob("*/scenarios.yaml"))
    assert out.strip().endswith(f"{total} scenariuszy")

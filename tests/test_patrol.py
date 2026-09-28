"""Patrol Jarva: wykrywanie anomalii na tablicy, deduplikacja alertów i tryb cichy (zero tokenów)."""

from __future__ import annotations

import json

from conftest import load_script

patrol = load_script("profiles/jarvo/scripts/patrol.py")

NOW = 1_800_000_000.0
MIN = 60

INDEX = """# Misje Jarvo

## Aktywne
| ID | Tytuł | Status | Karty |
|---|---|---|---|
| M-260926-nova | Launch serum Nova | w toku | t_aa01, t_aa02 |
| M-260926-done | Stara misja | w toku | t_bb01 |
| Z-260926-szybkie | Szybkie pytanie | w toku | t_cc01, t_dead |

## Zamknięte
| M-260901-old | Archiwum | zamknięta | t_zz99 |
"""


def board(**overrides):
    tasks = [
        {"id": "t_aa01", "title": "Research rynku", "status": "blocked", "assignee": "jarvo-sherlock",
         "created_at": NOW - 90 * MIN},
        {"id": "t_aa02", "title": "Landing", "status": "ready", "assignee": "jarvo-web", "created_at": NOW - 45 * MIN},
        {"id": "t_bb01", "title": "Stary raport", "status": "done", "assignee": "jarvo-reka", "created_at": NOW - 900 * MIN},
        {"id": "t_cc01", "title": "Szybka odpowiedź", "status": "review", "assignee": "jarvo-reka",
         "created_at": NOW - 200 * MIN},
        {"id": "t_ee01", "title": "Pętla", "status": "triage", "assignee": "jarvo-studio", "created_at": NOW - 5 * MIN},
        {"id": "t_ff01", "title": "Długi render", "status": "running", "assignee": "jarvo-studio",
         "started_at": NOW - 300 * MIN, "created_at": NOW - 310 * MIN},
        {"id": "t_gg01", "title": "Świeża karta", "status": "ready", "assignee": "jarvo-web", "created_at": NOW - 2 * MIN},
    ]
    events = {
        "t_aa01": [{"kind": "blocked", "created_at": NOW - 30 * MIN,
                    "payload": {"kind": "needs_input", "reason": "Który rynek: PL czy UE?"}}],
        "t_cc01": [{"kind": "review_requested", "created_at": NOW - 100 * MIN, "payload": {"implementer": "jarvo-reka"}}],
    }
    data = {"tasks": tasks, "events": events, "diagnostics": [], "index": INDEX}
    data.update(overrides)
    return data


def kinds(anomalies):
    return sorted(a["kind"] for a in anomalies)


def test_parse_index_only_active_section():
    rows = patrol.parse_index(INDEX)
    assert [r["id"] for r in rows] == ["M-260926-nova", "M-260926-done", "Z-260926-szybkie"]
    assert rows[0]["cards"] == ["t_aa01", "t_aa02"]
    assert rows[0]["title"] == "Launch serum Nova"


def test_analyze_detects_all_anomaly_kinds():
    found = patrol.analyze(board(), NOW)
    assert kinds(found) == sorted([
        "blocked", "ready_stale", "review_stale", "triage", "running_long",
        "mission_ready", "mission_inconsistent",
    ])
    blocked = next(a for a in found if a["kind"] == "blocked")
    assert blocked["block_kind"] == "needs_input"
    assert "Który rynek" in blocked["message"]
    assert blocked["since_min"] == 30


def test_fresh_ready_card_is_not_stale():
    found = patrol.analyze(board(), NOW)
    assert not any(a.get("task_id") == "t_gg01" for a in found)


def test_ready_age_counts_from_last_event():
    data = board()
    data["events"]["t_aa02"] = [{"kind": "promoted", "created_at": NOW - 3 * MIN}]
    assert not any(a.get("task_id") == "t_aa02" for a in patrol.analyze(data, NOW))


def test_diagnostics_become_anomalies():
    data = board(diagnostics=[{"task_id": "t_aa02", "severity": "error", "code": "spawn_failed",
                               "message": "profil nie istnieje"}])
    diag = [a for a in patrol.analyze(data, NOW) if a["kind"] == "diagnostic"]
    assert diag and diag[0]["severity"] == "error" and "profil nie istnieje" in diag[0]["message"]


def test_realert_window_and_forgetting_resolved():
    found = patrol.analyze(board(), NOW)
    first = patrol.select_new(found, {}, NOW)
    assert len(first) == len(found)
    state = patrol.update_state({}, first, found, NOW)
    # godzinę później: nic nowego
    assert patrol.select_new(found, state, NOW + 3600) == []
    # po oknie ponownego alertu: znów wszystko
    later = NOW + (patrol.REALERT_HOURS + 1) * 3600
    assert len(patrol.select_new(found, state, later)) == len(found)
    # rozwiązane anomalie znikają ze stanu
    trimmed = patrol.update_state(state, [], found[:1], NOW + 60)
    assert set(trimmed) == {found[0]["key"]}


def test_new_block_on_same_card_realerts():
    found = patrol.analyze(board(), NOW)
    state = patrol.update_state({}, found, found, NOW)
    data = board()
    data["events"]["t_aa01"].append({"kind": "blocked", "created_at": NOW + 5 * MIN,
                                     "payload": {"kind": "capability", "reason": "brak klucza API"}})
    again = patrol.select_new(patrol.analyze(data, NOW + 10 * MIN), state, NOW + 10 * MIN)
    assert [a["kind"] for a in again] == ["blocked"]


def run_main(tmp_path, data, capsys, now=NOW):
    fixture = tmp_path / "board.json"
    fixture.write_text(json.dumps(data), encoding="utf-8")
    patrol.main(["--fixture", str(fixture), "--now", str(now), "--state", str(tmp_path / "state.json")])
    out = capsys.readouterr().out.strip().splitlines()
    return out, json.loads(out[-1])


def test_main_wakes_then_stays_silent(tmp_path, capsys):
    out, verdict = run_main(tmp_path, board(), capsys)
    assert verdict["wakeAgent"] is True
    assert out[0].startswith("PATROL FLOTY:")
    assert len(verdict["context"]["anomalies"]) == 7
    _, verdict2 = run_main(tmp_path, board(), capsys, now=NOW + 10 * MIN)
    assert verdict2 == {"wakeAgent": False}
    # 30 min później świeża karta t_gg01 staje się zaległa: budzi tylko ona
    _, verdict3 = run_main(tmp_path, board(), capsys, now=NOW + 30 * MIN)
    assert [a["task_id"] for a in verdict3["context"]["anomalies"]] == ["t_gg01"]


def test_main_quiet_board_costs_zero_tokens(tmp_path, capsys):
    _, verdict = run_main(tmp_path, {"tasks": [], "events": {}, "diagnostics": [], "index": ""}, capsys)
    assert verdict == {"wakeAgent": False}


def test_main_broken_input_wakes_with_error(tmp_path, capsys):
    patrol.main(["--fixture", str(tmp_path / "brak.json"), "--now", str(NOW), "--state", str(tmp_path / "s.json")])
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert verdict["wakeAgent"] is True and "patrol_error" in verdict["context"]

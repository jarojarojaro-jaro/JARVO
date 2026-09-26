"""Dane do porannego briefu i przeglądu tygodnia: liczniki, blokady, jakość snajperów."""

from __future__ import annotations

import json

from conftest import load_script

report = load_script("profiles/tars/scripts/fleet_report.py")

NOW = 1_800_000_000.0
H = 3600


def data():
    tasks = [
        {"id": "t_1", "title": "Audyt", "status": "done", "assignee": "tars-web", "completed_at": NOW - 2 * H},
        {"id": "t_2", "title": "Research", "status": "done", "assignee": "tars-sherlock", "completed_at": NOW - 5 * H},
        {"id": "t_3", "title": "Stare", "status": "done", "assignee": "tars-web", "completed_at": NOW - 50 * H},
        {"id": "t_4", "title": "Czeka", "status": "blocked", "assignee": "tars-studio"},
        {"id": "t_5", "title": "W toku", "status": "running", "assignee": "tars-web"},
        {"id": "t_6", "title": "Archiwum", "status": "archived", "assignee": "tars-web"},
    ]
    shows = {
        # recenzja jest przypisana do TARS-a, ale jakość liczymy wykonawcy (payload.implementer)
        "t_1": {"events": [{"kind": "review_requested", "payload": {"implementer": "tars-web"}}]},
        "t_2": {"events": [
            {"kind": "review_requested", "payload": {"implementer": "tars-sherlock"}},
            {"kind": "changes_requested", "payload": {}},
            {"kind": "review_requested", "payload": {"implementer": "tars-sherlock"}},
        ]},
        "t_4": {"events": [{"kind": "blocked", "payload": {"kind": "needs_input", "reason": "Jaki budżet?"}}]},
    }
    return {"tasks": tasks, "shows": shows,
            "index": "## Aktywne\n| M-260926-nova | Nova | w toku | t_1 |\n| Z-1 | x | w toku | t_5 |\n"}


def test_summarize_daily_window():
    s = report.summarize(data(), NOW, report.DAY)
    assert [t["id"] for t in s["finished"]] == ["t_1", "t_2"]
    assert s["blocked"] == [{"id": "t_4", "title": "Czeka", "assignee": "tars-studio", "status": "blocked",
                             "reason": "Jaki budżet?"}]
    assert [t["id"] for t in s["in_flight"]] == ["t_5"]
    assert "archived" not in s["counts"]
    assert len(s["active_missions"]) == 2


def test_quality_per_implementer():
    q = report.summarize(data(), NOW, report.DAY)["quality"]
    assert q["tars-web"] == {"done": 1, "changes_requested": 0, "first_pass": 1, "reviews": 1}
    assert q["tars-sherlock"] == {"done": 1, "changes_requested": 1, "first_pass": 0, "reviews": 2}


def test_weekly_window_includes_older():
    s = report.summarize(data(), NOW, 7 * report.DAY)
    assert {t["id"] for t in s["finished"]} == {"t_1", "t_2", "t_3"}


def run(tmp_path, capsys, payload, mode):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    report.main(["--mode", mode, "--fixture", str(f), "--now", str(NOW)])
    return capsys.readouterr().out.strip().splitlines()


def test_empty_day_is_silent(tmp_path, capsys):
    out = run(tmp_path, capsys, {"tasks": [], "shows": {}, "index": ""}, "daily")
    assert json.loads(out[-1]) == {"wakeAgent": False}


def test_empty_week_still_reports(tmp_path, capsys):
    out = run(tmp_path, capsys, {"tasks": [], "shows": {}, "index": ""}, "weekly")
    assert json.loads(out[-1]) == {"wakeAgent": True}


def test_daily_with_work_wakes(tmp_path, capsys):
    out = run(tmp_path, capsys, data(), "daily")
    assert out[0].startswith("DANE DO RAPORTU (daily")
    assert json.loads(out[-1]) == {"wakeAgent": True}

"""Pomocnik aktualizacji: wykrywanie nowych commitów na gałęzi (git, bez Dockera)."""

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("updater", REPO / "scripts" / "updater.py")
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def test_check_counts_new_commits(tmp_path, monkeypatch):
    origin, clone = tmp_path / "origin", tmp_path / "clone"
    origin.mkdir()
    sh(origin, "git", "init", "-q", "-b", "main")
    sh(origin, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start")
    sh(tmp_path, "git", "clone", "-q", str(origin), str(clone))
    for msg in ("Motyw", "Klucze"):
        sh(origin, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", msg)
    monkeypatch.setattr(up, "ROOT", clone)
    state = up.check({"mode": "local", "state": "done"})
    assert state["branch"] == "main" and state["behind"] == 2
    assert [c["subject"] for c in state["commits"]] == ["Klucze", "Motyw"]
    assert state["state"] == "done" and state["error"] is None


def test_host_path_only_fleet_outputs(tmp_path):
    data = tmp_path / "data" / "hermes"
    out = data / "jarvo" / "missions" / "M-1" / "web" / "out"
    out.mkdir(parents=True)
    (out / "index.html").write_text("x", encoding="utf-8")
    (data / "profiles" / "jarvo").mkdir(parents=True)
    (data / "profiles" / "jarvo" / ".env").write_text("KEY=1", encoding="utf-8")
    assert up.host_path("/opt/data/jarvo/missions/M-1/web/out/index.html", str(data)) == (out / "index.html").resolve()
    assert up.host_path("/opt/data/jarvo/missions/M-1/web/out", str(data)) == out.resolve()
    assert up.host_path("/opt/data/profiles/jarvo/.env", str(data)) is None          # klucze: nigdy
    assert up.host_path("/opt/data/jarvo/missions/../../profiles/jarvo/.env", str(data)) is None
    assert up.host_path("/etc/passwd", str(data)) is None
    assert up.host_path("/opt/data/jarvo/missions/M-1/nie-ma.html", str(data)) is None


def test_take_requests_parses_both(monkeypatch):
    out = 'update-request\tupdate\nreveal-request\t{"path": "/opt/data/jarvo/missions/M-1/out/a.html", "at": 1}\n'
    monkeypatch.setattr(up, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, out, ""))
    assert up.take_requests() == ("update", "/opt/data/jarvo/missions/M-1/out/a.html")
    monkeypatch.setattr(up, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "reveal-request\tzepsute\n", ""))
    assert up.take_requests() == (None, None)


def test_restart_keeps_done_state(tmp_path, monkeypatch):
    """Po samorestarcie (nowa wersja pomocnika) stan „done” wraca z env, żeby dashboard się odświeżył."""
    seen = {}
    monkeypatch.setenv("JARVO_UPDATER_STATE", '{"state": "done", "finished_at": 5, "current": "abc1234"}')
    monkeypatch.setattr(up, "take_requests", lambda: (None, None))
    monkeypatch.setattr(up, "host_info", lambda: {"explorer": False, "data_host": "/x", "data_win": None})
    monkeypatch.setattr(up, "check", lambda base: {**base, "behind": 0, "checked_at": 1})
    monkeypatch.setattr(up, "put_state", lambda st: seen.update(st) or True)
    assert up.main(["--once", "--mode", "local"]) == 0
    assert seen["state"] == "done" and seen["finished_at"] == 5 and seen["current"] == "abc1234"
    assert "JARVO_UPDATER_STATE" not in up.os.environ

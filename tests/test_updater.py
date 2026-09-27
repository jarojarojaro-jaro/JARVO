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

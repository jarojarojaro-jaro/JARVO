"""Migracja instalacji sprzed zmiany nazwy (TARS → Jarvo): host i dane w kontenerze, idempotentnie."""

from __future__ import annotations

import json
import sqlite3
import stat

from conftest import load_script

mj = load_script("scripts/migrate_jarvo.py")


def test_host_moves_local_dir_and_rewrites_env(tmp_path, monkeypatch):
    monkeypatch.setattr(mj, "stop_old_stack", lambda: None)
    old = tmp_path / "tars-local"
    (old / "compose").mkdir(parents=True)
    (old / "secrets").mkdir()
    (old / "compose" / ".env").write_text(
        f"TARS_DATA={old}/data\nTARS_SECRETS={old}/secrets\nTARS_BIND_IP=127.0.0.1\nDASHBOARD_USER=tars\n")
    (old / "compose" / "tars.env").write_text("TARS_MODEL_PROVIDER=\n")
    (old / "secrets" / "tars-web.env").write_text("OPENROUTER_API_KEY=x\n")
    (old / "secrets" / "host.env").write_text("TARS_SHARE_KEYS=1\n")
    compose, build = mj.migrate_host(old / "compose", old / "build")
    new = tmp_path / "jarvo-local"
    assert not old.exists() and compose == new / "compose" and build == new / "build"
    env = (compose / ".env").read_text()
    assert f"JARVO_DATA={new}/data" in env and "TARS_" not in env and "DASHBOARD_USER=jarvo" in env
    assert (compose / "jarvo.env").read_text() == "JARVO_MODEL_PROVIDER=\n"
    assert (new / "secrets" / "jarvo-web.env").exists() and "JARVO_SHARE_KEYS" in (new / "secrets" / "host.env").read_text()
    # drugi raz (stary pomocnik podaje starą ścieżkę): nic nie psuje, wskazuje nowe miejsce
    assert mj.migrate_host(old / "compose", None)[0] == new / "compose"


def test_container_renames_profiles_data_cron_kanban(tmp_path):
    data = tmp_path / "data"
    (data / "tars" / "workspaces" / "tars-web").mkdir(parents=True)
    (data / "tars" / "missions").mkdir()
    (data / "jarvo" / "state").mkdir(parents=True)             # gateway zdążył utworzyć nowy katalog
    for p in ("tars", "tars-web"):
        (data / "profiles" / p / "cron").mkdir(parents=True)
        (data / "profiles" / p / ".env").write_text("TARS_X=1\nAPI_SERVER_KEY=k\n")
    (data / "profiles" / "tars" / "cron" / "jobs.json").write_text(
        json.dumps({"jobs": [{"id": "tars-patrol"}, {"id": "mine"}]}))
    con = sqlite3.connect(data / "kanban.db")
    con.execute("CREATE TABLE tasks (id INTEGER, assignee TEXT)")
    con.executemany("INSERT INTO tasks VALUES (?,?)", [(1, "tars-web"), (2, "tars"), (3, "inny")])
    con.commit(); con.close()
    (data / "plugins" / "tars-hq").mkdir(parents=True)
    fake = tmp_path / "hermes"                                  # `hermes profile rename` zastąpione mv
    fake.write_text('#!/bin/sh\n[ "$1" = profile ] && mv "' + str(data) + '/profiles/$3" "' + str(data) + '/profiles/$4"\nexit 0\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    mj.migrate_container(data, str(fake))
    assert not (data / "tars").exists() and (data / "jarvo" / "missions").is_dir() and (data / "jarvo" / "state").is_dir()
    assert (data / "jarvo" / "workspaces" / "jarvo-web").is_dir()
    assert sorted(p.name for p in (data / "profiles").iterdir()) == ["jarvo", "jarvo-web"]
    jobs = json.loads((data / "profiles" / "jarvo" / "cron" / "jobs.json").read_text())["jobs"]
    assert [j["id"] for j in jobs] == ["mine"]
    assert (data / "profiles" / "jarvo-web" / ".env").read_text().startswith("JARVO_X=1")
    rows = sqlite3.connect(data / "kanban.db").execute("SELECT assignee FROM tasks ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["jarvo-web", "jarvo", "inny"]
    assert not (data / "plugins" / "tars-hq").exists()
    mj.migrate_container(data, str(fake))                       # idempotentnie


def test_new_name_only_touches_old_prefix():
    assert mj.new_name("tars-web") == "jarvo-web" and mj.new_name("tars") == "jarvo"
    assert mj.new_name("starsze") == "starsze" and mj.new_name("tarsier") == "tarsier"

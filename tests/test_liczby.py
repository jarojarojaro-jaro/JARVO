"""Liczby floty (profiles/jarvo/scripts/liczby.py): jedna definicja jakości dla HQ i przeglądu tygodnia, eskalacje,
awarie, cisza i tokeny z tablicy i sesji."""

from __future__ import annotations

import json
import sqlite3

from conftest import load_script

liczby = load_script("profiles/jarvo/scripts/liczby.py", "jarvo_liczby_test")
core = load_script("hq/plugin/hq_core.py", "jarvo_hq_core_liczby_test")

NOW = 1_800_000_000.0
D = 86400


def kanban(path):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT, status TEXT, priority INTEGER,
            created_at INTEGER, started_at INTEGER, completed_at INTEGER, workspace_path TEXT, result TEXT,
            last_heartbeat_at INTEGER, current_run_id INTEGER, session_id TEXT, block_kind TEXT, skills TEXT,
            last_failure_error TEXT);
        CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT,
            payload TEXT, created_at INTEGER);
        CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT, status TEXT,
            started_at INTEGER, ended_at INTEGER, last_heartbeat_at INTEGER, outcome TEXT);
    """)
    c.executemany("INSERT INTO tasks (id, title, assignee, status, created_at, completed_at) VALUES (?,?,?,?,?,?)", [
        ("t_web", "Strona", "jarvo-web", "done", NOW - 20 * D, NOW - D),        # poprawka sprzed okna 7 dni
        ("t_sh", "Research", "jarvo-sherlock", "done", NOW - 2 * D, NOW - D),   # przyjęta za 1. razem
        ("t_sam", "Bez recenzji", "jarvo-reka", "done", NOW - 2 * D, NOW - D),  # nie liczy się jako „za 1. razem”
        ("t_blk", "Czeka", "jarvo-studio", "blocked", NOW - D, None),
        ("t_run", "Cisza", "jarvo-wideo", "running", NOW - D, None),
    ])
    ev = [("t_web", "review_requested", {"implementer": "jarvo-web"}, NOW - 15 * D),
          ("t_web", "changes_requested", {}, NOW - 14 * D),
          ("t_web", "review_requested", {"implementer": "jarvo-web"}, NOW - 2 * D),
          ("t_sh", "review_requested", {"implementer": "jarvo-sherlock"}, NOW - D),
          ("t_blk", "blocked", {"kind": "needs_input", "reason": ""}, NOW - D),
          ("t_x", "blocked", {"kind": "capability", "reason": "to dla jarvo-ads"}, NOW - D),
          ("t_x", "gave_up", {"failures": 2}, NOW - D)]
    c.executemany("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                  [(t, k, json.dumps(p), at) for t, k, p, at in ev])
    c.executemany("INSERT INTO task_runs (task_id, profile, status, started_at, ended_at, last_heartbeat_at, outcome) "
                  "VALUES (?,?,?,?,?,?,?)", [
                      ("t_web", "jarvo-web", "done", NOW - 3 * D, NOW - 3 * D, None, "crashed"),
                      ("t_web", "jarvo-web", "done", NOW - 2 * D, NOW - 2 * D, None, "review_requested"),
                      ("t_run", "jarvo-wideo", "running", NOW - 3 * 3600, None, NOW - 2 * 3600, None)])
    c.commit()
    c.close()


def sesje(path, wiersze):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE sessions (id TEXT, started_at REAL, input_tokens INT, output_tokens INT, "
              "cache_read_tokens INT, cache_write_tokens INT, reasoning_tokens INT)")
    c.executemany("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)", wiersze)
    c.commit()
    c.close()


def dane(tmp_path):
    kanban(tmp_path / "kanban.db")
    (tmp_path / "profiles" / "jarvo-web").mkdir(parents=True)
    sesje(tmp_path / "profiles" / "jarvo-web" / "state.db",
          [("a", NOW - D, 1000, 200, 5000, 0, 50), ("stara", NOW - 30 * D, 9, 9, 9, 9, 9)])
    return tmp_path


def test_jakosc_liczy_wykonawce_i_poprawki_sprzed_okna(tmp_path):
    w = liczby.policz(dane(tmp_path), NOW, 7)
    assert w["jakosc"]["jarvo-web"] == {"done": 1, "reviews": 2, "first_pass": 0, "changes_requested": 1, "with_changes": 1}
    assert w["jakosc"]["jarvo-sherlock"]["first_pass"] == 1
    assert w["jakosc"]["jarvo-reka"] == {"done": 1, "reviews": 0, "first_pass": 0, "changes_requested": 0, "with_changes": 0}
    assert w["za_1_razem"] == {"przyjete": 1, "zrobione": 3, "procent": 33}


def test_eskalacje_awarie_cisza_tokeny(tmp_path):
    w = liczby.policz(dane(tmp_path), NOW, 7)
    assert w["eskalacje"] == {"needs_input": 1, "capability": 1, "inne": 0, "gave_up": 1}
    assert w["awarie"] == {"crashed": 1}
    assert w["cisza"] == {"bez_sygnalu": ["t_run"], "blokady_bez_powodu": ["t_blk"]}
    assert w["tokeny"]["jarvo-web"] == {"sesje": 1, "wejscie": 1000, "wyjscie": 200, "cache_odczyt": 5000,
                                        "cache_zapis": 0, "rozumowanie": 50}
    assert w["tokeny_na_karte"] == {"jarvo-web": 6250}
    assert any("za 1. razem: 1/3 (33%)" in ln for ln in liczby.opis(w))


def test_hq_liczy_tak_samo_jak_przeglad_tygodnia(tmp_path):
    """HQ widzi poprawkę sprzed 7 dni (wcześniej liczył tylko zdarzenia z okna i kartę bez recenzji jako przyjętą)."""
    board = core.read_board(dane(tmp_path) / "kanban.db", NOW)
    assert core.agent_stats("jarvo-web", board, NOW) == {"done_7d": 1, "first_pass_7d": 0, "changes_7d": 1}
    assert core.agent_stats("jarvo-reka", board, NOW) == {"done_7d": 1, "first_pass_7d": 0, "changes_7d": 0}
    w = liczby.policz(tmp_path, NOW, 7)
    for a in ("jarvo-web", "jarvo-sherlock", "jarvo-reka"):
        s = core.agent_stats(a, board, NOW)
        assert (s["done_7d"], s["first_pass_7d"]) == (w["jakosc"][a]["done"], w["jakosc"][a]["first_pass"])


def test_brak_tablicy_i_cli(tmp_path, capsys):
    assert liczby.policz(tmp_path, NOW, 7)["za_1_razem"] == {"przyjete": 0, "zrobione": 0, "procent": None}
    dane(tmp_path)
    assert liczby.main(["--dane", str(tmp_path), "--teraz", str(NOW)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("Liczby floty") and json.loads(out[-1])["okno_dni"] == 7

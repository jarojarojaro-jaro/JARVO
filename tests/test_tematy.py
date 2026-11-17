"""hq/plugin/tematy.py: temat rozmówcy z telegram-grupy.json, klucz trasy bramy, sesja tematu z gateway_routing
(tylko odczyt) i z sessions.json, rotacja (prev_session_id), temat bez sesji."""
from __future__ import annotations

import json
import sqlite3

import pytest

from conftest import load_script

t = load_script("hq/plugin/tematy.py", "jarvo_test_tematy")
CZAT = "-1001234567890"


def grupy(dane, **kw):
    p = dane / "jarvo" / "state" / "telegram-grupy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"grupy": kw}), encoding="utf-8")


def trasy(db, wpisy):
    db.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE IF NOT EXISTS gateway_routing (scope TEXT NOT NULL DEFAULT '', session_key TEXT NOT NULL, "
              "entry_json TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY (scope, session_key))")
    for k, v in wpisy.items():
        c.execute("INSERT OR REPLACE INTO gateway_routing VALUES ('/x', ?, ?, 1)", (k, json.dumps(v)))
    c.commit()
    c.close()


def test_temat_general_i_po_nazwie(tmp_path):
    grupy(tmp_path, **{CZAT: {"od": "2026-11-17", "watki": {"7": {"nazwa": "JARODEV"}, "9": {"nazwa": "Kernel"}}},
                       "-1009": {"od": "2026-01-01", "watki": {"3": {"nazwa": "JARODEV"}}}, "zly": {"od": "z"}})
    assert t.temat(tmp_path, "general", "Jarvo") == (CZAT, "1")
    assert t.temat(tmp_path, "jarodev", "Jarodev") == (CZAT, "7")          # najnowsza grupa wygrywa
    assert t.temat(tmp_path, "", "kernel") == (CZAT, "9")
    assert t.temat(tmp_path, "operator", "Operator") is None
    assert t.temat(tmp_path / "brak", "general", "Jarvo") is None


def test_klucze_trasy_i_walidacja():
    assert t.klucze_trasy("jarvo", CZAT, "1") == [f"agent:jarvo:telegram:group:{CZAT}:1", f"agent:jarvo:telegram:group:{CZAT}"]
    assert t.klucze_trasy("jarvo-jarodev", CZAT, "7") == [f"agent:jarvo-jarodev:telegram:group:{CZAT}:7"]
    for zle in (("Jarvo", CZAT, "1"), ("jarvo", "123", "1"), ("jarvo", CZAT, "x' OR 1")):
        with pytest.raises(ValueError):
            t.klucze_trasy(*zle)
    assert t.sesja_panelu("jarvo-jarodev") == "jarvo_r_jarvo-jarodev"
    with pytest.raises(ValueError):
        t.sesja_panelu("../x")


def test_sesja_tematu_z_bazy_profilu_i_rotacja(tmp_path):
    db = tmp_path / "profiles" / "jarvo-jarodev" / "state.db"
    k = f"agent:jarvo-jarodev:telegram:group:{CZAT}:7"
    trasy(db, {k: {"session_id": "s1"}})
    assert t.sesja_tematu(tmp_path, "jarvo-jarodev", CZAT, "7") == {"session_id": "s1", "prev_session_id": None,
                                                                    "was_auto_reset": False}
    trasy(db, {k: {"session_id": "s2", "prev_session_id": "s1", "was_auto_reset": True}})
    assert t.sesja_tematu(tmp_path, "jarvo-jarodev", CZAT, "7")["prev_session_id"] == "s1"
    assert t.sesja_tematu(tmp_path, "jarvo-jarodev", CZAT, "8") is None       # temat bez sesji


def test_sesja_tematu_general_w_bazie_hosta_i_lustro_json(tmp_path):
    trasy(tmp_path / "state.db", {f"agent:jarvo:telegram:group:{CZAT}": {"session_id": "g1"}})
    assert t.sesja_tematu(tmp_path, "jarvo", CZAT, "1")["session_id"] == "g1"     # General także bez wątku
    inny = tmp_path / "inny"
    (inny / "sessions").mkdir(parents=True)
    (inny / "sessions" / "sessions.json").write_text(json.dumps(
        {f"agent:jarvo:telegram:group:{CZAT}:1": {"session_id": "j1"}, "zly": "{"}), encoding="utf-8")
    assert t.sesja_tematu(inny, "jarvo", CZAT, "1")["session_id"] == "j1"
    (inny / "state.db").write_bytes(b"to nie jest sqlite")                         # zła baza: zapasowo lustro
    assert t.sesja_tematu(inny, "jarvo", CZAT, "1")["session_id"] == "j1"


def test_baza_tylko_do_odczytu(tmp_path):
    db = tmp_path / "state.db"
    trasy(db, {f"agent:jarvo:telegram:group:{CZAT}:1": {"session_id": "g1"}})
    przed = db.stat().st_mtime_ns
    t.sesja_tematu(tmp_path, "jarvo", CZAT, "1")
    assert db.stat().st_mtime_ns == przed and not (tmp_path / "state.db-wal").exists()

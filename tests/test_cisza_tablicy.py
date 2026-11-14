"""Cisza tablicy: po `kanban_create` z Telegrama Hermes nie wysyła surowych komunikatów karty, tylko budzi Jarva."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cisza_tablicy", ROOT / "wiedza" / "plugin" / "cisza_tablicy.py")
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)


@pytest.fixture
def baza(tmp_path, monkeypatch):
    plik = tmp_path / "kanban.db"
    with sqlite3.connect(plik) as c:
        c.execute("CREATE TABLE kanban_notify_subs (task_id TEXT, platform TEXT, chat_id TEXT, delivery_mode TEXT)")
        c.executemany("INSERT INTO kanban_notify_subs VALUES (?, ?, ?, ?)", [
            ("t_1", "telegram", "100", "notify+wake"),
            ("t_1", "api_server", "hq", "notify+wake"),       # czat HQ: wybudzenie to dostarczenie, bez zmian
            ("t_2", "telegram", "100", "notify+wake"),        # inna karta
        ])

    @contextlib.contextmanager
    def connect_closing(db_path=None, *, board=None):
        conn = sqlite3.connect(plik)
        try:
            yield conn
        finally:
            conn.close()

    hermes_cli = types.ModuleType("hermes_cli")
    kbc = types.ModuleType("hermes_cli.kanban_db_connect")
    kbc.connect_closing = connect_closing
    hermes_cli.kanban_db_connect = kbc
    monkeypatch.setitem(sys.modules, "hermes_cli", hermes_cli)
    monkeypatch.setitem(sys.modules, "hermes_cli.kanban_db_connect", kbc)
    return plik


def tryby(plik):
    with sqlite3.connect(plik) as c:
        return dict(((t, p), m) for t, p, m in c.execute(
            "SELECT task_id, platform, delivery_mode FROM kanban_notify_subs"))


def test_karta_z_telegrama_budzi_jarva_bez_surowego_komunikatu(baza):
    """14.11: „⏸ [default] @jarvo-operator Kanban t_… blocked: …$HOME…” szło na Telegram obok wiadomości Jarva."""
    ct.po_narzedziu("kanban_create", {"title": "x"}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": True}))
    assert tryby(baza) == {("t_1", "telegram"): "wake", ("t_1", "api_server"): "notify+wake",
                           ("t_2", "telegram"): "notify+wake"}


def test_inne_narzedzia_i_nieudane_tworzenie_bez_zmian(baza):
    przed = tryby(baza)
    ct.po_narzedziu("kanban_show", {}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": True}))
    ct.po_narzedziu("kanban_create", {}, json.dumps({"ok": False, "error": "x"}))
    ct.po_narzedziu("kanban_create", {}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": False}))
    ct.po_narzedziu("kanban_create", {}, "nie json")
    assert tryby(baza) == przed

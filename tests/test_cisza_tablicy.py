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


def budzenie(karta="t_87d11e3a", status="blocked; needs attention", tytul="Pilot ankiet: DataAnnotation"):
    return (f"[kanban] Task {karta} {status}.\nTitle: {tytul}\nAssignee: @jarvo\nBoard: default\n\n"
            "Check the result or decide the next step.\n\nThis is an automatic task-status notification, ...")


def zablokuj(plik, karta, payload):
    with sqlite3.connect(plik) as c:
        c.execute("CREATE TABLE IF NOT EXISTS task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, "
                  "run_id INTEGER, kind TEXT, payload TEXT, created_at INTEGER)")
        c.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, 'blocked', ?, 1)",
                  (karta, json.dumps(payload)))


POWOD = "DataAnnotation: Cloudflare nie przepuszcza Komputera ani telefonu, kliknij raz na telefonie albo przez VNC"


def test_budzenie_o_blokadzie_rozpoznane():
    assert ct.blokada_z_budzenia(budzenie()) == ("t_87d11e3a", "Pilot ankiet: DataAnnotation", "default")
    assert ct.blokada_z_budzenia(budzenie(status="completed, blocked; needs attention"))[0] == "t_87d11e3a"
    assert ct.blokada_z_budzenia(budzenie(status="completed")) is None
    assert ct.blokada_z_budzenia("Zablokowane? [kanban] Task t_1 blocked; needs attention.") is None


@pytest.mark.parametrize("odpowiedz", ["[SILENT]", " [SILENT]\n", "[SILENT] karta czeka", "Zapisane.\n[SILENT]"])
def test_blokada_needs_input_nigdy_nie_konczy_sie_cisza(baza, odpowiedz):
    """17.11: „przez godzinę klikał w kółko i nie dał mi znać”. Budzenie o karcie z needs_input: przypomnienie
    w turze, a odpowiedź-cisza zamieniona na zdanie dla właściciela (Hermes na Telegramie milczy: tryb `wake`)."""
    zablokuj(baza, "t_87d11e3a", {"kind": "needs_input", "reason": POWOD})
    kontekst = ct.przed_tura(session_id="s1", turn_id="u7", user_message=budzenie())
    assert "nigdy nie kończy się [SILENT]" in kontekst["context"] and POWOD in kontekst["context"]
    assert ct.po_odpowiedzi(response_text=odpowiedz, session_id="s1", turn_id="u7") == \
        f"Zadanie „Pilot ankiet: DataAnnotation” czeka na Ciebie: {POWOD}"
    assert ct.po_odpowiedzi(response_text="[SILENT]", session_id="s1", turn_id="u7") is None    # raz na turę


def test_odpowiedz_jarva_i_inne_blokady_bez_zmian(baza):
    zablokuj(baza, "t_87d11e3a", {"kind": "needs_input", "reason": POWOD})
    ct.przed_tura(session_id="s1", turn_id="u1", user_message=budzenie())
    assert ct.po_odpowiedzi(response_text="Cloudflare nie przepuszcza: kliknij raz na telefonie.", session_id="s1",
                            turn_id="u1") is None
    ct.przed_tura(session_id="s1", turn_id="u2", user_message=budzenie())
    assert ct.po_odpowiedzi(response_text="[SILENT]", session_id="s1", turn_id="u3") is None    # inna tura
    assert ct.po_odpowiedzi(response_text="[SILENT]", session_id="s2", turn_id="u2") is None    # inna sesja
    zablokuj(baza, "t_2", {"kind": "capability", "reason": "to praca Weba"})
    assert ct.przed_tura(session_id="s3", turn_id="u4", user_message=budzenie(karta="t_2")) is None
    assert ct.po_odpowiedzi(response_text="[SILENT]", session_id="s3", turn_id="u4") is None
    assert ct.przed_tura(session_id="s4", turn_id="u5", user_message="Zrób raport") is None

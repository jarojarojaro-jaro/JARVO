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
    monkeypatch.delenv("TELEGRAM_HOME_CHANNEL", raising=False)
    monkeypatch.delenv("TELEGRAM_HOME_CHANNEL_THREAD_ID", raising=False)
    with sqlite3.connect(plik) as c:            # kolumny jak hermes_cli/kanban_db.py (kanban_notify_subs)
        c.execute("CREATE TABLE kanban_notify_subs (task_id TEXT NOT NULL, platform TEXT NOT NULL, chat_id TEXT NOT NULL, "
                  "thread_id TEXT NOT NULL DEFAULT '', user_id TEXT, chat_type TEXT, delivery_mode TEXT NOT NULL "
                  "DEFAULT 'notify', delivery_metadata TEXT, PRIMARY KEY (task_id, platform, chat_id, thread_id))")
        c.executemany("INSERT INTO kanban_notify_subs (task_id, platform, chat_id, user_id, chat_type, delivery_mode, "
                      "delivery_metadata) VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ("t_1", "telegram", "100", "100", "dm", "notify+wake", '{"chat_type": "dm"}'),
            ("t_1", "api_server", "hq", None, None, "notify+wake", None),   # czat HQ: wybudzenie to dostarczenie
            ("t_2", "telegram", "100", "100", "dm", "notify+wake", None),   # inna karta
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


def subskrypcje(plik):
    with sqlite3.connect(plik) as c:
        return sorted(c.execute("SELECT task_id, platform, chat_id, thread_id, chat_type, delivery_mode, "
                                "delivery_metadata FROM kanban_notify_subs"))


def test_karta_z_dm_budzi_jarva_w_jego_domu(baza, monkeypatch):
    """17.11: dom Jarva to temat General grupy Jarvo HQ; karta założona z rozmowy w DM budzi Jarva w sesji General
    (klucz jak wiadomość z General: „group”, wątek „1”), więc wynik i needs_input trafiają tam, nie do DM."""
    monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1004309644955")
    ct.po_narzedziu("kanban_create", {"title": "x"}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": True}))
    assert subskrypcje(baza) == [
        ("t_1", "api_server", "hq", "", None, "notify+wake", None),
        ("t_1", "telegram", "-1004309644955", "1", "group", "wake", None),
        ("t_2", "telegram", "100", "", "dm", "notify+wake", None)]


def test_dom_juz_subskrybuje_a_dm_wypada(baza, monkeypatch):
    """Karta już ma subskrypcję domu (np. dziedziczoną z rodzica): wiersz z DM po prostu znika, bez błędu klucza."""
    monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1004309644955")
    with sqlite3.connect(baza) as c:
        c.execute("INSERT INTO kanban_notify_subs (task_id, platform, chat_id, thread_id, chat_type, delivery_mode) "
                  "VALUES ('t_1', 'telegram', '-1004309644955', '1', 'group', 'wake')")
    ct.po_narzedziu("kanban_create", {}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": True}))
    assert [w[:4] for w in subskrypcje(baza) if w[0] == "t_1"] == [
        ("t_1", "api_server", "hq", ""), ("t_1", "telegram", "-1004309644955", "1")]


def test_dom_w_dm_albo_brak_nie_przenosi(baza, monkeypatch):
    """Bez grupy dom Jarva to DM: subskrypcje zostają tam, gdzie były (tylko cisza tablicy)."""
    monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "100")
    assert ct.dom_jarva() is None
    ct.po_narzedziu("kanban_create", {}, json.dumps({"ok": True, "task_id": "t_1", "subscribed": True}))
    assert ("t_1", "telegram", "100", "", "dm", "wake", '{"chat_type": "dm"}') in subskrypcje(baza)
    monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1004309644955")
    monkeypatch.setenv("TELEGRAM_HOME_CHANNEL_THREAD_ID", "5")
    assert ct.dom_jarva() == ("-1004309644955", "5")


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

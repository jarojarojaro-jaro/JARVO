"""Wiersze budzenia kanbana (hq/plugin/budzenia.py): szablon z /opt/hermes/locales/en.yaml (sprawdzony w obrazie)."""
from conftest import load_script

bz = load_script("hq/plugin/budzenia.py", "jarvo_test_budzenia")

SZABLON = "[kanban] Task {task_id} {status}.\nTitle: {title}\nAssignee: @{assignee}\nBoard: {board}\n\nCheck the result or decide the next step."


def test_zakonczona_z_wynikiem():
    tekst = SZABLON.format(task_id="t_ab12", status="completed", title="Stopka. Wersja 2", assignee="jarvo-web",
                           board="default") + "\nResult: Stopka gotowa"
    assert bz.czy_budzenie(tekst)
    b = bz.parsuj(tekst)
    assert b == {"task_id": "t_ab12", "status": "completed", "status_pl": "zakończona", "status_en": "completed",
                 "ton": "ok", "tytul": "Stopka. Wersja 2", "wykonawca": "jarvo-web", "tablica": "default",
                 "wynik": "Stopka gotowa"}


def test_statusy_i_nieznany():
    for status, (pl, ton) in bz.STATUSY.items():
        b = bz.parsuj(SZABLON.format(task_id="t_1", status=status, title="X", assignee="a", board="b"))
        assert (b["status_pl"], b["ton"], b["status_en"]) == (pl, ton, bz.STATUSY_EN[status])
    b = bz.parsuj(SZABLON.format(task_id="t_1", status="exploded", title="X", assignee="a", board="b"))
    assert b["status_pl"] == "exploded" and b["ton"] == "info"
    uwagi = SZABLON.format(task_id="t_2", status="review requested changes (BLOCK); implementation is not approved",
                           title="Y", assignee="a", board="b") + "\nReview feedback: brak testów"
    assert bz.parsuj(uwagi)["uwagi"] == "brak testów"


def test_zwykly_tekst_to_nie_budzenie():
    for t in ("[kanban] coś", "Task t_1 completed.", "", None, "  [kanban] Task t_1 completed.\nTitle: x"):
        assert not bz.czy_budzenie(t) and bz.parsuj(t) is None

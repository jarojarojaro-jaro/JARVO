"""Zgoda właściciela z karty kanbana (komputer/zgoda_karty.py, docs/KOMPUTER.md §6) i jej powiadomienie z bramki
(komputer/jarvo_cua.py)."""
from __future__ import annotations

import json
import sqlite3
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from komputer import jarvo_cua, zgoda_karty  # noqa: E402
from komputer.zgoda_karty import zgoda_z_tresci  # noqa: E402

WSZYSTKIE = frozenset({"platnosc", "wysylka", "publikacja", "usuniecie_konta", "konto"})


@pytest.mark.parametrize("linia, zgody", [
    ("ZGODA WŁAŚCICIELA: platnosc — „kup domenę jarvo.pl” (2026-11-13)", {"platnosc"}),
    ("ZGODA WŁAŚCICIELA: Płatność, wysyłka — „kup i wyślij fakturę” (2026-11-13)", {"platnosc", "wysylka"}),
    ("ZGODA WŁAŚCICIELA: publikacja,usunięcie konta — „opublikuj i skasuj stare konto” (2026-11-13)",
     {"publikacja", "usuniecie_konta"}),
    ("zgoda właściciela: USUNIECIE_KONTA — „usuń konto testowe” (2026-11-13)", {"usuniecie_konta"}),
    ("ZGODA WLASCICIELA: konto — „załóż konto i zaakceptuj regulamin” (2026-11-13)", {"konto"}),
    ("ZGODA WŁAŚCICIELA: wszystko — „rób, co trzeba” (2026-11-13)", WSZYSTKIE),
    ("- ZGODA WŁAŚCICIELA: wysylka – \"wyślij formularz\" (2026-11-13)", {"wysylka"}),
])
def test_linia_zgody(linia, zgody):
    assert zgoda_z_tresci(f"Zlecenie: domena.\n\n{linia}\nDoD: domena kupiona.") == frozenset(zgody)


@pytest.mark.parametrize("tresc", [
    None, "", "Kup domenę jarvo.pl, płatność do 60 zł.",
    "ZGODA WŁAŚCICIELA: platnosc",                                              # bez cytatu i daty
    "ZGODA WŁAŚCICIELA: platnosc — „kup” ",                                     # bez daty
    "ZGODA WŁAŚCICIELA: platnosc — „kup” (2026-13-45)",                         # zła data
    "ZGODA WŁAŚCICIELA: platnosc — „” (2026-11-13)",                            # pusty cytat
    "ZGODA WŁAŚCICIELA: platnosc, przelewy — „kup” (2026-11-13)",               # nieznana kategoria
    "ZGODA WŁAŚCICIELA: — „kup” (2026-11-13)",                                  # bez kategorii
    "Właściciel pisze: ZGODA WŁAŚCICIELA: platnosc — „kup” (2026-11-13)",       # nie na początku linii
    "ZGODA WŁAŚCICIELA: platnosc — „kup” (2026-11-13) i coś jeszcze",           # coś po dacie
])
def test_bez_zgody(tresc):
    assert zgoda_z_tresci(tresc) == frozenset()


def test_kilka_linii_sie_sumuje_a_zla_nie_psuje_dobrej():
    tresc = ("ZGODA WŁAŚCICIELA: platnosc — „kup” (2026-11-13)\r\n"
             "ZGODA WŁAŚCICIELA: wysylka, coś — „wyślij” (2026-11-13)\r\n"
             "ZGODA WŁAŚCICIELA: publikacja — „opublikuj” (2026-11-14)\n")
    assert zgoda_z_tresci(tresc) == frozenset({"platnosc", "publikacja"})


def _baza(sciezka, karty: dict) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(sciezka)
    con.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT)")
    con.executemany("INSERT INTO tasks VALUES (?, ?)", list(karty.items()))
    con.commit()
    con.close()


def test_tresc_karty_tylko_do_odczytu(tmp_path, monkeypatch):
    for k in ("HERMES_KANBAN_DB", "HERMES_KANBAN_HOME", "HERMES_HOME", "HERMES_KANBAN_BOARD"):
        monkeypatch.delenv(k, raising=False)
    dane = tmp_path / "dane"
    _baza(dane / "kanban.db", {"t_1": "treść 1"})
    _baza(dane / "kanban" / "boards" / "sklep" / "kanban.db", {"t_2": "treść 2"})
    baza = zgoda_karty.sciezka_kanbana(dane)
    assert zgoda_karty.tresc_karty("t_1", baza) == "treść 1"
    assert zgoda_karty.tresc_karty("t_2", zgoda_karty.sciezka_kanbana(dane, "sklep")) == "treść 2"
    assert zgoda_karty.sciezka_kanbana(dane, "../x") is None
    assert zgoda_karty.tresc_karty("nie_ma", baza) is None
    assert zgoda_karty.tresc_karty("t_1'; --", baza) is None
    assert zgoda_karty.tresc_karty("t_1", tmp_path / "brak.db") is None
    # bez bazy: z otoczenia pracownika Hermesa (HERMES_HOME profilu, tablica)
    assert zgoda_karty.tresc_karty("t_1") is None
    monkeypatch.setenv("HERMES_HOME", str(dane / "profiles" / "jarvo-operator"))
    assert zgoda_karty.tresc_karty("t_1") == "treść 1"
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "sklep")
    assert zgoda_karty.tresc_karty("t_2") == "treść 2"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(dane / "kanban.db"))
    assert zgoda_karty.tresc_karty("t_1") == "treść 1"
    # odczyt nie zmienia bazy (tryb ro)
    przed = (dane / "kanban.db").read_bytes()
    zgoda_karty.tresc_karty("t_1", baza)
    assert (dane / "kanban.db").read_bytes() == przed


def test_bramka_podaje_karte_pracownika(monkeypatch):
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    assert jarvo_cua.powiadomienie_karty() == b""
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_abc123")
    msg = json.loads(jarvo_cua.powiadomienie_karty())
    assert msg == {"jsonrpc": "2.0", "method": "notifications/jarvo/karta",
                   "params": {"karta": "t_abc123", "tablica": "default"}}
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "Sklep")
    assert json.loads(jarvo_cua.powiadomienie_karty())["params"]["tablica"] == "sklep"
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t 1\n{")
    assert jarvo_cua.powiadomienie_karty() == b""

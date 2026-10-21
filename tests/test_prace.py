"""Praca floty do `praca.json` (hq/plugin/prace.py): karty `running` z kanban.db tylko do odczytu, liczenie
przebiegów, kart i obcych tur, zapis atomowy; brak albo zepsuta baza = pusta lista, nie wyjątek."""
import json
import sqlite3

from conftest import load_script

pr = load_script("hq/plugin/prace.py", "jarvo_test_prace")


def _kanban(sciezka, karty):
    conn = sqlite3.connect(sciezka)
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, assignee TEXT, status TEXT, started_at REAL)")
    conn.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)", karty)
    conn.commit()
    conn.close()


def test_karty_w_toku_tylko_running_i_bez_zmian_w_bazie(tmp_path):
    baza = tmp_path / "kanban.db"
    _kanban(baza, [("t_2", "Logo", "jarvo-studio", "running", 20.0), ("t_1", "Stopka", "jarvo-web", "running", 10.0),
                   ("t_3", "Stara", "jarvo-web", "done", 5.0), ("t_4", None, None, "running", 30.0)])
    przed = baza.read_bytes()
    assert pr.karty_w_toku(baza) == [{"task_id": "t_1", "tytul": "Stopka", "wykonawca": "jarvo-web"},
                                     {"task_id": "t_2", "tytul": "Logo", "wykonawca": "jarvo-studio"},
                                     {"task_id": "t_4", "tytul": "", "wykonawca": ""}]
    assert baza.read_bytes() == przed


def test_karty_bez_bazy_albo_z_zepsuta_baza(tmp_path):
    assert pr.karty_w_toku(tmp_path / "nie-ma.db") == []
    zla = tmp_path / "zla.db"
    zla.write_bytes(b"to nie jest sqlite" * 50)
    assert pr.karty_w_toku(zla) == []
    pusta = tmp_path / "pusta.db"
    sqlite3.connect(pusta).close()                     # baza bez tabeli tasks
    assert pr.karty_w_toku(pusta) == []
    assert pr.karty_w_toku(tmp_path) == []             # katalog zamiast pliku


def test_praca_liczy_i_opisuje_bez_tresci():
    przebiegi = [{"agent": "jarvo-web", "payload": {"prosba": "tajna treść"}}, {"agent": "jarvo"}]
    karty = [{"task_id": "t_1", "tytul": "Stopka", "wykonawca": "jarvo-studio"}, {"tytul": "X", "wykonawca": ""}]
    obce = [{"agent": "jarvo", "platforma": "telegram"}]
    d = pr.praca(przebiegi, karty, obce, nazwy={"jarvo-web": "Web", "jarvo": "Jarvo", "jarvo-studio": "Studio"},
                 teraz=123.0)
    assert d == {"aktywne": 5, "at": 123.0, "opis": ["Web: rozmowa", "Jarvo: rozmowa", "Studio: karta „Stopka”",
                                                    "?: karta „X”", "Jarvo: tura (telegram)"]}
    assert "tajna" not in json.dumps(d, ensure_ascii=False)
    duzo = pr.praca([{"agent": "a"}] * 20, [], [], teraz=1.0)
    assert duzo["aktywne"] == 20 and len(duzo["opis"]) == pr.OPIS_MAKS
    assert pr.praca([], [], [], teraz=1.0) == {"aktywne": 0, "opis": [], "at": 1.0}


def test_zapisz_atomowo(tmp_path):
    cel = tmp_path / "state" / "praca.json"
    pr.zapisz(cel, {"aktywne": 1, "opis": ["Web: rozmowa"], "at": 1.0})
    pr.zapisz(cel, {"aktywne": 0, "opis": [], "at": 2.0})
    assert json.loads(cel.read_text(encoding="utf-8")) == {"aktywne": 0, "opis": [], "at": 2.0}
    assert [p.name for p in cel.parent.iterdir()] == ["praca.json"]          # bez plików tymczasowych

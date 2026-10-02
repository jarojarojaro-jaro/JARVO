"""Przegląd tygodnia jako strona (profiles/jarvo/scripts/raport_strona.py): HTML bez modelu z danych fleet_report,
bez skryptów i sieci, tytuły kart escapowane; zapis w workspaces/jarvo/raporty i podpięcie w trybie weekly."""

from __future__ import annotations

import json

from conftest import load_script

rs = load_script("profiles/jarvo/scripts/raport_strona.py", "jarvo_raport_strona_test")
report = load_script("profiles/jarvo/scripts/fleet_report.py", "jarvo_fleet_report_strona_test")

NOW = 1_800_000_000.0
DANE = {
    "finished": [{"id": "t_1", "title": "Strona <b>Nova</b>", "assignee": "jarvo-web"}],
    "blocked": [{"id": "t_2", "title": "Kampania", "assignee": "jarvo-studio", "reason": None}],
    "in_flight": [],
    "quality": {"jarvo-web": {"done": 4, "first_pass": 3, "changes_requested": 1}},
    "liczby": {"za_1_razem": {"przyjete": 3, "zrobione": 4, "procent": 75},
               "eskalacje": {"needs_input": 1, "capability": 0}, "awarie": {"crashed": 1},
               "cisza": {"bez_sygnalu": ["t_9"], "blokady_bez_powodu": []},
               "tokeny": {"jarvo-web": {"sesje": 3, "wejscie": 1_200_000, "wyjscie": 30_000},
                          "jarvo": {"sesje": 9, "wejscie": 400_000, "wyjscie": 8_000}}},
    "prosty_polski": {"wiadomosci": 20, "w_normie": 18, "najczestsze": ["za długie zdanie ×2"]},
}


def test_strona_liczby_i_bezpieczenstwo():
    html = rs.strona(DANE, "2026-09-25", "2026-10-02")
    assert "default-src 'none'" in html and "<script" not in html and "<b>Nova</b>" not in html
    assert "Strona &lt;b&gt;Nova&lt;/b&gt;" in html                      # tytuł karty to dane od agenta
    assert "75%" in html and "18/20" in html and "1,2 mln" in html and "bez powodu" in html
    assert "Awarie pracownika: crashed 1" in html and "Bez sygnału życia: t_9" in html
    tokeny = html[html.index("Tokeny na agenta"):]
    assert tokeny.index(">web<") < tokeny.index(">jarvo<")                # malejąco


def test_strona_pustych_danych():
    html = rs.strona({}, "2026-09-25", "2026-10-02")
    assert "Nic w tym tygodniu." in html and "Brak danych o tokenach." in html and "Do uwagi" not in html


def test_zapisz_bez_serwera_podgladu(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "_jarvo_link", lambda: None)
    w = rs.zapisz(DANE, NOW, tmp_path / "raporty")
    assert w["link"] is None and w["plik"].endswith(".html") and "Tydzień floty" in open(w["plik"], encoding="utf-8").read()


def test_weekly_dokleja_strone(tmp_path, monkeypatch, capsys):
    """Tryb weekly na żywych danych: strona w `strona`; pusty tydzień bez strony; błąd zapisu nie psuje raportu."""
    tydzien = {"tasks": [{"id": "t_1", "title": "Audyt", "status": "done", "assignee": "jarvo-web", "completed_at": NOW - 3600}],
               "shows": {}, "index": ""}
    monkeypatch.setattr(report, "load_live", lambda _w: tydzien)
    monkeypatch.setattr(report.liczby, "policz", lambda *_a: {})
    monkeypatch.setattr(report.prosty, "tydzien", lambda *_a: {})
    monkeypatch.setattr(report.raport_strona, "zapisz", lambda dane, now: {"plik": "/x/tydzien.html", "link": "http://h/t/"})
    report.main(["--mode", "weekly", "--now", str(NOW)])
    out = capsys.readouterr().out
    assert '"link": "http://h/t/"' in out and json.loads(out.strip().splitlines()[-1]) == {"wakeAgent": True}

    def blad(*_a):
        raise OSError("dysk pełny")
    monkeypatch.setattr(report.raport_strona, "zapisz", blad)
    report.main(["--mode", "weekly", "--now", str(NOW)])
    assert '"blad": "dysk pełny"' in capsys.readouterr().out
    monkeypatch.setattr(report, "load_live", lambda _w: {"tasks": [], "shows": {}, "index": ""})
    report.main(["--mode", "weekly", "--now", str(NOW)])
    assert '"strona"' not in capsys.readouterr().out

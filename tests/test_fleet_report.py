"""Dane do porannego briefu i przeglądu tygodnia: liczniki, blokady, jakość snajperów."""

from __future__ import annotations

import json

from conftest import load_script

report = load_script("profiles/jarvo/scripts/fleet_report.py")

NOW = 1_800_000_000.0
H = 3600


def data():
    tasks = [
        {"id": "t_1", "title": "Audyt", "status": "done", "assignee": "jarvo-web", "completed_at": NOW - 2 * H},
        {"id": "t_2", "title": "Research", "status": "done", "assignee": "jarvo-sherlock", "completed_at": NOW - 5 * H},
        {"id": "t_3", "title": "Stare", "status": "done", "assignee": "jarvo-web", "completed_at": NOW - 50 * H},
        {"id": "t_4", "title": "Czeka", "status": "blocked", "assignee": "jarvo-studio"},
        {"id": "t_5", "title": "W toku", "status": "running", "assignee": "jarvo-web"},
        {"id": "t_6", "title": "Archiwum", "status": "archived", "assignee": "jarvo-web"},
    ]
    shows = {
        # recenzja jest przypisana do Jarva, ale jakość liczymy wykonawcy (payload.implementer)
        "t_1": {"events": [{"kind": "review_requested", "payload": {"implementer": "jarvo-web"}}]},
        "t_2": {"events": [
            {"kind": "review_requested", "payload": {"implementer": "jarvo-sherlock"}},
            {"kind": "changes_requested", "payload": {}},
            {"kind": "review_requested", "payload": {"implementer": "jarvo-sherlock"}},
        ]},
        "t_4": {"events": [{"kind": "blocked", "payload": {"kind": "needs_input", "reason": "Jaki budżet?"}}]},
    }
    return {"tasks": tasks, "shows": shows,
            "index": "## Aktywne\n| M-260926-nova | Nova | w toku | t_1 |\n| Z-1 | x | w toku | t_5 |\n"}


def test_summarize_daily_window():
    s = report.summarize(data(), NOW, report.DAY)
    assert [t["id"] for t in s["finished"]] == ["t_1", "t_2"]
    assert s["blocked"] == [{"id": "t_4", "title": "Czeka", "assignee": "jarvo-studio", "status": "blocked",
                             "reason": "Jaki budżet?"}]
    assert [t["id"] for t in s["in_flight"]] == ["t_5"]
    assert "archived" not in s["counts"]
    assert len(s["active_missions"]) == 2


def test_quality_per_implementer():
    q = report.summarize(data(), NOW, report.DAY)["quality"]
    assert q["jarvo-web"] == {"done": 1, "changes_requested": 0, "first_pass": 1, "reviews": 1, "with_changes": 0}
    assert q["jarvo-sherlock"] == {"done": 1, "changes_requested": 1, "first_pass": 0, "reviews": 2, "with_changes": 1}


def test_weekly_window_includes_older():
    s = report.summarize(data(), NOW, 7 * report.DAY)
    assert {t["id"] for t in s["finished"]} == {"t_1", "t_2", "t_3"}


def run(tmp_path, capsys, payload, mode):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    report.main(["--mode", mode, "--fixture", str(f), "--now", str(NOW)])
    return capsys.readouterr().out.strip().splitlines()


def test_empty_day_is_silent(tmp_path, capsys):
    out = run(tmp_path, capsys, {"tasks": [], "shows": {}, "index": ""}, "daily")
    assert json.loads(out[-1]) == {"wakeAgent": False}


def test_empty_week_still_reports(tmp_path, capsys):
    out = run(tmp_path, capsys, {"tasks": [], "shows": {}, "index": ""}, "weekly")
    assert json.loads(out[-1]) == {"wakeAgent": True}


def test_daily_with_work_wakes(tmp_path, capsys):
    out = run(tmp_path, capsys, data(), "daily")
    assert out[0].startswith("DANE DO RAPORTU (daily")
    assert json.loads(out[-1]) == {"wakeAgent": True}


def _uklad(tmp_path, monkeypatch):
    """Instalacja w tmp: <root>/dane (HERMES_HOME profilu jarvo) i <root>/stan; Kernel tylko przez JARVO_KERNEL_STAN."""
    for k in ("JARVO_DATA_DIR", "JARVO_STATE_DIR", "JARVO_KNOWLEDGE_DIR", "JARVO_MISSIONS_DIR"):
        monkeypatch.delenv(k, raising=False)
    dane = tmp_path / "dane"
    (dane / "profiles" / "jarvo").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(dane / "profiles" / "jarvo"))
    monkeypatch.setenv("JARVO_KERNEL_STAN", str(tmp_path / "kernel" / "stan.json"))
    return dane


def _zapisz(plik, obj):
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(json.dumps(obj), encoding="utf-8")


TERAZ = report.dt.datetime(2026, 11, 15, 7, 50)


def test_agenci_biznesowi_pelne_dane(tmp_path, monkeypatch):
    dane = _uklad(tmp_path, monkeypatch)
    _zapisz(dane / "jarvo" / "state" / "wiedza-agenci.json",
            {"jarvo": {"title": "Jarvo: szef floty"}, "jarvo-sklep": {"marka": "sklep"}, "jarvo-x": {"marka": "xmarka"}})
    wpisy = [{"id": "L-0001", "status": "nowy", "utworzono": "2026-11-15T06:00:00"},
             {"id": "L-0002", "status": "szkic", "utworzono": "2026-11-12T10:00:00"},
             {"id": "L-0003", "status": "szkic", "utworzono": "2026-10-01T10:00:00"},
             {"id": "L-0004", "status": "klient", "utworzono": "zła data"}]
    _zapisz(dane / "jarvo" / "workspaces" / "jarvo-sklep" / "lejek" / "lejek.json", {"nastepny": 5, "wpisy": wpisy})
    _zapisz(dane / "profiles" / "jarvo-sklep" / "cron" / "jobs.json",
            {"jobs": [{"id": "sklep-dzien", "enabled": False, "state": "paused"}, {"id": "inna", "enabled": True}]})
    _zapisz(tmp_path / "stan" / "telefon.json", {"profile": {"jarvo-sklep": "fb"}})
    (dane / "jarvo" / "knowledge" / "brands" / "sklep").mkdir(parents=True)
    (dane / "jarvo" / "knowledge" / "brands" / "sklep" / "BRAND.md").write_text("# Sklep\n", encoding="utf-8")
    _zapisz(tmp_path / "kernel" / "stan.json",
            {"zwiad_dzien": "2026-11-14", "zwiad_ostatni": TERAZ.timestamp() - 9 * H, "zwiad_pozycje": 87})
    sekcja = report.agenci_biznesowi(TERAZ)
    assert sekcja["szkice"] == {"jarvo-sklep": ["L-0002", "L-0003"]}
    assert sekcja["linie"] == [
        "jarvo-sklep (sklep): lejek 4 (szkic 2, nowy 1, klient 1); nowe 24 h: 1, 7 dni: 2; "
        "czeka na zgodę: 2 (L-0002, L-0003); rutyny: wstrzymane 1/2 (sklep-dzien); telefon: fb; brand kit: jest",
        "jarvo-x (xmarka): lejek: nie założony; rutyny: brak cron/jobs.json; telefon: brak przydziału; "
        "brand kit: brak brands/xmarka/BRAND.md",
        "Kernel: ostatni zwiad 2026-11-14 22:50, 87 pozycji",
    ]


def test_agenci_biznesowi_braki_nie_przerywaja(tmp_path, monkeypatch):
    dane = _uklad(tmp_path, monkeypatch)
    # bez wiedza-agenci.json i bez stanu Kernela: jedna linia o braku, Kernel pominięty po cichu
    assert report.agenci_biznesowi(TERAZ)["linie"] == [
        "brak state/wiedza-agenci.json (zasiew wiedzy po buildzie): nie wiem, którzy agenci są biznesowi"]
    _zapisz(dane / "jarvo" / "state" / "wiedza-agenci.json", {"jarvo": {}})
    assert report.agenci_biznesowi(TERAZ)["linie"] == ["brak aktywnych agentów z marką"]
    _zapisz(dane / "jarvo" / "state" / "wiedza-agenci.json", {"jarvo-sklep": {"marka": "sklep"}})
    lejek = dane / "jarvo" / "workspaces" / "jarvo-sklep" / "lejek" / "lejek.json"
    lejek.parent.mkdir(parents=True)
    lejek.write_text("{nie json", encoding="utf-8")
    _zapisz(tmp_path / "stan" / "telefon.json", {"profile": "zły wpis"})
    (tmp_path / "kernel").mkdir()
    (tmp_path / "kernel" / "stan.json").write_text("[]", encoding="utf-8")
    assert report.agenci_biznesowi(TERAZ)["linie"] == [
        "jarvo-sklep (sklep): lejek: plik nieczytelny; rutyny: brak cron/jobs.json; telefon: brak przydziału; "
        "brand kit: brak brands/sklep/BRAND.md",
        "Kernel: stan.json nieczytelny"]
    _zapisz(lejek, {"nastepny": 1, "wpisy": []})
    _zapisz(tmp_path / "kernel" / "stan.json", {"gpu_wlaczony": True})
    assert report.agenci_biznesowi(TERAZ)["linie"][0].startswith(
        "jarvo-sklep (sklep): lejek 0 (pusty); nowe 24 h: 0, 7 dni: 0; czeka na zgodę: 0;")
    assert report.agenci_biznesowi(TERAZ)["linie"][1] == "Kernel: brak zapisanego zwiadu"


def test_szkice_do_zgody_budza_brief():
    cichy = {"finished": [], "blocked": [], "in_flight": [], "kopalnia": {}}
    assert report.pusto(cichy)
    assert not report.pusto({**cichy, "szkice_do_zgody": {"jarvo-sklep": ["L-0002"]}})

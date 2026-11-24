"""`jarvo stan`: stan instalacji jednym poleceniem (jarvo/stan.py). Dane z katalogu testu i atrapy programów systemu:
wstrzymana rutyna nie udaje włączonej, zegary tylko właściciela, port w sieci odróżniony od lokalnego, zadania
otwarte z tytułem, własne polecenia z opisem, a błąd jednej części nie zabiera reszty."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import sciezki, stan  # noqa: E402

TERAZ = time.mktime((2026, 11, 24, 14, 0, 0, 0, 0, -1))
DOM_ZEGAROW = str(Path.home() / ".config" / "systemd" / "user")


def iso(przesuniecie_s: float) -> str:
    """Pora względem TERAZ w strefie maszyny testu, w zapisie jobs.json (ISO ze strefą)."""
    return datetime.fromtimestamp(TERAZ + przesuniecie_s).astimezone().isoformat()


@pytest.fixture
def u(tmp_path):
    uk = sciezki.Uklad(root=tmp_path, program=tmp_path / "program", dane=tmp_path / "dane", stan=tmp_path / "stan",
                       logi=tmp_path / "logi", cache=tmp_path / "cache", build=tmp_path / "build")
    for profil, zadania in {
        "jarvo": [{"id": "jarvo-patrol", "name": "Patrol floty", "enabled": True, "state": "scheduled",
                   "schedule_display": "every 30m", "last_status": "ok",
                   "last_run_at": iso(-17 * 60), "next_run_at": iso(17 * 3600 + 50 * 60)}],
        "jarvo-translator": [{"id": "translator-dzien", "name": "Translator: dzień pracy", "enabled": False,
                              "state": "paused", "schedule": {"kind": "cron", "expr": "10 9 * * 1-5"},
                              "paused_at": iso(-5 * 86400), "paused_reason": "czeka na\nprzegląd", "next_run_at": None}],
    }.items():
        kat = uk.dane / "profiles" / profil
        (kat / "cron").mkdir(parents=True)
        (kat / "cron" / "jobs.json").write_text(json.dumps({"jobs": zadania}), encoding="utf-8")
        (kat / "config.yaml").write_text("model:\n  default: dostawca/model-x\ndelegation:\n  max_concurrent_children: 3\n",
                                         encoding="utf-8")
    (uk.dane / "config.yaml").write_text("kanban:\n  max_in_progress: 3\n  max_in_progress_per_profile: 2\n",
                                         encoding="utf-8")
    c = sqlite3.connect(uk.dane / "kanban.db")
    c.execute("create table tasks (id text, status text, assignee text, title text, created_at real)")
    c.executemany("insert into tasks values (?,?,?,?,?)", [
        ("t_1", "running", "jarvo-web", "Strona  główna\nailokalne", 2.0), ("t_2", "done", "jarvo", "Stare", 1.0)])
    c.commit()
    c.close()
    return uk


def atrapa(argv: list[str]) -> str:
    """systemctl, ss i crontab bez dotykania komputera."""
    if argv[:3] == ["systemctl", "--user", "list-timers"]:
        return json.dumps([
            {"unit": "kopia.timer", "activates": "kopia.service", "last": (TERAZ - 3600) * 1e6, "next": (TERAZ + 60) * 1e6},
            {"unit": "obcy.timer", "activates": "obcy.service", "last": 0, "next": (TERAZ + 60) * 1e6}])
    if argv[:3] == ["systemctl", "--user", "show"]:
        return (f"Id=kopia.timer\nDescription=Kopia co godzinę\nFragmentPath={DOM_ZEGAROW}/kopia.timer\n\n"
                "Id=obcy.timer\nDescription=Systemowy\nFragmentPath=/usr/lib/systemd/user/obcy.timer\n\n"
                "Id=kopia.service\nDescription=Kopia na GitHub\n\n"
                "Id=jarvo.service\nCPUQuotaPerSecUSec=3s\n")
    if argv[0] == "ss":
        return ('LISTEN 0 128 100.64.0.1:9119 0.0.0.0:* users:(("hermes",pid=999999991,fd=5))\n'
                'LISTEN 0 128 127.0.0.1:8642 0.0.0.0:* users:(("hermes",pid=999999991,fd=6))\n'
                "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n")
    return ""


def raport(u, *tematy) -> str:
    return stan.raport(u, None, tematy, wolaj_=atrapa, teraz=TERAZ)


def test_rutyny_wszystkich_profili_wstrzymana_bez_terminu_a_zegary_tylko_wlasciciela(u):
    r = raport(u, "rutyny")
    assert "Jarvo stan · wtorek 2026-11-24 14:00" in r
    assert "jarvo: Patrol floty · every 30m · włączona · ostatnio dziś 13:43 (ok) · następnie jutro 07:50" in r
    assert "jarvo-translator: Translator: dzień pracy · 10 9 * * 1-5 · wstrzymana od 19.11 (czeka na przegląd), sama nie ruszy\n" in r
    assert "kopia.timer · Kopia co godzinę · uruchamia: Kopia na GitHub · ostatnio dziś 13:00 · następnie dziś 14:01" in r
    assert "obcy.timer" not in r
    assert "crontab użytkownika: pusty" in r


def test_flota_modele_limity_i_otwarte_zadania_z_tytulem_w_jednej_linii(u):
    r = raport(u, "flota")
    assert "agenci (2) na dostawca/model-x: jarvo, jarvo-translator" in r
    assert "limity: zadań naraz najwyżej 3, na jednego agenta 2, podagentów Jarva naraz 3" in r
    assert "lista zadań: w toku 1, zakończone 1" in r
    assert "t_1 · w toku · jarvo-web · Strona główna ailokalne" in r
    assert "Stare" not in r


def test_porty_odrozniaja_siec_od_komputera_i_pomijaja_cudze_procesy(u):
    r = raport(u, "porty")
    assert "9119 · w sieci · hermes" in r
    assert "8642 · tylko ten komputer · hermes" in r
    assert "\n22 " not in r


def test_wlasne_polecenia_z_opisem_z_pierwszego_komentarza(u):
    assert "brak; skrypt zapisany w" in raport(u, "polecenia")
    kat = stan.katalog_polecen(u)
    kat.mkdir(parents=True)
    (kat / "strony").write_text("#!/bin/sh\n# czy strony odpowiadają: kod HTTP i czas każdej\ncurl …\n", encoding="utf-8")
    (kat / ".ukryty").write_text("# nie\n", encoding="utf-8")
    r = raport(u, "polecenia")
    assert f"{kat / 'strony'} · czy strony odpowiadają: kod HTTP i czas każdej" in r
    assert ".ukryty" not in r


def test_blad_jednej_czesci_nie_zabiera_reszty(u, monkeypatch):
    monkeypatch.setitem(stan.CZESCI, "porty", ("porty", lambda *_a: 1 / 0))
    r = raport(u, "porty", "wiedza", "flota")
    assert "## porty: porty\n(nie udało się odczytać: ZeroDivisionError" in r
    assert "Brak skarbca" in r and "szkic staje się" not in r
    assert "agenci (2)" in r


def test_inna_nazwa_tematu_dziala_a_nieznany_daje_caly_stan_bez_bledu(u, capsys, monkeypatch):
    wolane = []
    monkeypatch.setattr(stan, "raport", lambda _u, _ot, tematy: wolane.append(tematy) or "RAPORT")
    assert stan.polecenie_stan(u, SimpleNamespace(tematy=["Zadania", "flota", "kopia"]), [], None) == 0
    assert stan.polecenie_stan(u, SimpleNamespace(tematy=["nieznany"]), [], None) == 0
    assert wolane == [("flota", "rutyny"), ()]
    assert "(tematu nieznany nie ma; tematy: serwis, rutyny" in capsys.readouterr().out


def test_poczekalnia_i_raporty_rutyn(u):
    assert "nic nie czeka" in raport(u, "poczekalnia")
    kat = u.dane / "profiles" / "jarvo" / "pending" / "skills"
    kat.mkdir(parents=True)
    (kat / "ab12.json").write_text(json.dumps({"id": "ab12", "subsystem": "skills", "summary": "patch on\nposty",
                                               "created_at": TERAZ - 3600}), encoding="utf-8")
    assert "czeka 1, najnowsze:\n  jarvo · skills · ab12 · patch on posty · czeka od dziś 13:00" in raport(u, "poczekalnia")
    (u.jarvo_dane / "state").mkdir(parents=True)
    c = sqlite3.connect(u.jarvo_dane / "state" / "raporty.db")
    c.execute("create table raporty (id text, profil text, rodzaj text, nazwa text, ts real, tekst text, blad integer)")
    c.execute("insert into raporty values ('r1','jarvo','rutyna','Poranny brief',?,'…',1)", (TERAZ - 86400,))
    c.commit()
    c.close()
    assert "  wczoraj 14:00 · jarvo · Poranny brief · BŁĄD" in raport(u, "raporty")

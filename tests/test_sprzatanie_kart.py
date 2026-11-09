"""Sprzątanie scope'ów pracowników kart: zatrzymujemy tylko przebiegi zakończone dawniej niż zapas."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import sprzatanie_kart  # noqa: E402

TERAZ = 1_800_000_000.0


def _baza(sciezka: Path, karty: list[tuple], przebiegi: list[tuple]) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sciezka) as c:
        c.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT, completed_at INTEGER)")
        c.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, ended_at INTEGER)")
        c.executemany("INSERT INTO tasks VALUES (?, ?, ?)", karty)
        c.executemany("INSERT INTO task_runs VALUES (?, ?, ?)", przebiegi)


class _Systemd:
    """Atrapa `systemctl --user`: list-units zwraca podane scope'y, stop zapisuje nazwę."""

    def __init__(self, scope: list[str]):
        self.scope, self.zatrzymane = scope, []

    def __call__(self, argv, **kw):
        if "list-units" in argv:
            wyjscie = "".join(f"{s} loaded active running [systemd-run] hermes\n" for s in self.scope)
            return subprocess.CompletedProcess(argv, 0, wyjscie, "")
        if "stop" in argv:
            assert "--no-block" in argv            # pętla nadzorcy nie może czekać na SIGKILL po 90 s
            self.zatrzymane.append(argv[-1])
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)


def _sprzataj(dane: Path, scope: list[str], monkeypatch) -> list[str]:
    monkeypatch.setattr(sprzatanie_kart, "_systemctl", lambda: "/usr/bin/systemctl")
    systemd = _Systemd(scope)
    wynik = sprzatanie_kart.sprzataj(dane, teraz=TERAZ, uruchom=systemd)
    assert [n for n, _ in wynik] == systemd.zatrzymane
    return systemd.zatrzymane


def test_zatrzymuje_tylko_przebiegi_zakonczone_dawniej_niz_zapas(tmp_path, monkeypatch):
    _baza(tmp_path / "kanban.db",
          karty=[("t_aa", "running", None), ("t_bb", "done", TERAZ - 3600)],
          przebiegi=[(122, "t_aa", TERAZ - 600),          # stary przebieg karty, która dalej pracuje (run 123)
                     (123, "t_aa", None),                  # trwa
                     (130, "t_bb", TERAZ - 60),            # skończył się przed chwilą: w zapasie
                     (131, "t_bb", TERAZ - 121)])          # tuż za zapasem 120 s
    scope = ["hermes-worker-kanban-t_aa-run-122.scope", "hermes-worker-kanban-t_aa-run-123.scope",
             "hermes-worker-kanban-t_bb-run-130.scope", "hermes-worker-kanban-t_bb-run-131.scope",
             "hermes-worker-kanban-t_cc-run-140.scope",    # karty nie ma w żadnej bazie
             "hermes-worker-cron-abc-exec-1.scope"]        # nie karta
    assert _sprzataj(tmp_path, scope, monkeypatch) == [
        "hermes-worker-kanban-t_aa-run-122.scope", "hermes-worker-kanban-t_bb-run-131.scope"]


def test_przebieg_bez_numeru_tylko_po_zamknietej_karcie(tmp_path, monkeypatch):
    _baza(tmp_path / "kanban.db",
          karty=[("t_aa", "archived", TERAZ - 900), ("t_bb", "running", None), ("t_cc", "blocked", TERAZ - 900)],
          przebiegi=[])
    scope = [f"hermes-worker-kanban-{k}-run-missing.scope" for k in ("t_aa", "t_bb", "t_cc")]
    assert _sprzataj(tmp_path, scope, monkeypatch) == ["hermes-worker-kanban-t_aa-run-missing.scope"]


def test_karta_z_innej_tablicy(tmp_path, monkeypatch):
    _baza(tmp_path / "kanban.db", karty=[], przebiegi=[])
    _baza(tmp_path / "kanban" / "boards" / "strony" / "kanban.db",
          karty=[("t_dd", "done", TERAZ - 900)], przebiegi=[(7, "t_dd", TERAZ - 900)])
    assert _sprzataj(tmp_path, ["hermes-worker-kanban-t_dd-run-7.scope"], monkeypatch) == [
        "hermes-worker-kanban-t_dd-run-7.scope"]


def test_bez_bazy_kanbana_nic_nie_robi(tmp_path, monkeypatch):
    assert _sprzataj(tmp_path, ["hermes-worker-kanban-t_aa-run-1.scope"], monkeypatch) == []

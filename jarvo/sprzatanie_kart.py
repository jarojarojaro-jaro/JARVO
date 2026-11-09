"""Sprzątanie po kartach kanbana (Linux).

Hermes uruchamia pracownika karty w `systemd-run --user --scope` o nazwie
`hermes-worker-kanban-<karta>-run-<przebieg>.scope`. Scope kończy się dopiero z ostatnim procesem, więc serwer,
przeglądarka albo `node` puszczone przez agenta w tle przeżywały kartę (podgląd `http.server` działał 16 h po
końcu karty). Nadzorca co kilka minut woła `sprzataj()`: zatrzymuje scope przebiegu, który baza kanbana zna jako
zakończony (`task_runs.ended_at`) dawniej niż `ZAPAS` sekund. Trwającego przebiegu (bez `ended_at`) i karty, której
nie ma w żadnej bazie, nie dotyka; scope bez numeru przebiegu (`run-missing`) tylko po karcie done/archived.
"""

from __future__ import annotations

import contextlib
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Callable

WZOR_SCOPE = re.compile(r"hermes-worker-kanban-(t_[0-9a-f]+)-run-(\d+|missing)\.scope")
ZAPAS = 120.0                  # sekundy po końcu przebiegu: agent kończy zapisy, Hermes zamyka sesję
STANY_ZAMKNIETE = ("done", "archived")


def bazy_kanbana(dane: Path) -> list[Path]:
    """kanban.db tablicy domyślnej (korzeń danych) i tablic w kanban/boards/<tablica>/."""
    bazy = [dane / "kanban.db", *sorted((dane / "kanban" / "boards").glob("*/kanban.db"))]
    return [b for b in bazy if b.is_file()]


def koniec_przebiegu(bazy: list[Path], karta: str, przebieg: str) -> float | None:
    """Czas końca przebiegu (epoch) albo None: przebieg trwa, karty nie ma albo bazy nie da się odczytać."""
    for baza in bazy:
        try:
            with contextlib.closing(sqlite3.connect(f"{baza.as_uri()}?mode=ro", uri=True, timeout=2)) as c:
                if przebieg == "missing":
                    w = c.execute("SELECT status, completed_at FROM tasks WHERE id = ?", (karta,)).fetchone()
                    if w is None:
                        continue
                    return float(w[1]) if w[0] in STANY_ZAMKNIETE and w[1] else None
                w = c.execute("SELECT ended_at FROM task_runs WHERE id = ? AND task_id = ?",
                              (int(przebieg), karta)).fetchone()
                if w is None:
                    continue
                return float(w[0]) if w[0] else None
        except (sqlite3.Error, ValueError):
            continue
    return None


def _systemctl() -> str | None:
    return shutil.which("systemctl", path="/usr/bin:/bin")


def scope_kart(uruchom: Callable = subprocess.run) -> list[str]:
    """Działające scope'y pracowników kart (nazwy jednostek)."""
    systemctl = _systemctl()
    if systemctl is None:
        return []
    try:
        r = uruchom([systemctl, "--user", "list-units", "--type=scope", "--state=active", "--plain", "--no-legend",
                     "--no-pager", "hermes-worker-kanban-*"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode:
        return []
    return [linia.split()[0] for linia in r.stdout.splitlines() if linia.strip()]


def sprzataj(dane: Path, *, teraz: float | None = None, zapas: float = ZAPAS,
             uruchom: Callable = subprocess.run) -> list[tuple[str, float]]:
    """Zatrzymuje (`systemctl --user stop --no-block`) scope'y zakończonych przebiegów kart.
    Zwraca [(nazwa scope, ile sekund po końcu przebiegu)] dla zatrzymanych."""
    bazy = bazy_kanbana(dane)
    systemctl = _systemctl()
    if not bazy or systemctl is None:
        return []
    teraz = time.time() if teraz is None else teraz
    zatrzymane = []
    for nazwa in scope_kart(uruchom):
        m = WZOR_SCOPE.fullmatch(nazwa)
        if m is None:
            continue
        koniec = koniec_przebiegu(bazy, m[1], m[2])
        if koniec is None or teraz - koniec < zapas:
            continue
        try:
            r = uruchom([systemctl, "--user", "stop", "--no-block", nazwa], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            zatrzymane.append((nazwa, teraz - koniec))
    return zatrzymane

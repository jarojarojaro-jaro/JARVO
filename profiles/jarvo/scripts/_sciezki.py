"""Katalogi Jarva dla rutyn i raportów (docs/NATYWNIE.md H06, F01): ścieżki z HERMES_HOME, a nie /opt na sztywno.

Cron Hermesa uruchamia skrypt rutyny z HERMES_HOME profilu (`<dane>/profiles/jarvo`), więc `<dane>` leży dwa katalogi
wyżej; JARVO_DATA_DIR to `<dane>/jarvo` (jarvo/srodowisko.py, HQ). Zmienne JARVO_*_DIR wygrywają (instalacja natywna
i kontener je ustawiają). Bez HERMES_HOME i bez zmiennych: układ kontenera (/opt/data, /opt/jarvo/build).

Moduł pomocniczy (nazwa z „_”): build.py nie liczy go jako skryptu agenta. Skrypty importują go po dopisaniu swojego
katalogu do sys.path (cron i tak zaczyna od katalogu skryptu, testy ładują skrypt po ścieżce).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

KONTENER = Path("/opt/data")


def dane() -> Path:
    """`<dane>` = HERMES_HOME Jarva (kanban.db, state.db, profiles/), także z HERMES_HOME profilu."""
    h = os.environ.get("HERMES_HOME")
    if h:
        p = Path(h)
        return p.parent.parent if p.parent.name == "profiles" else p
    j = os.environ.get("JARVO_DATA_DIR")
    return Path(j).parent if j else KONTENER


def jarvo() -> Path:
    """`<dane>/jarvo`: skarbiec, misje, stan, katalogi robocze, evals."""
    return Path(os.environ.get("JARVO_DATA_DIR") or dane() / "jarvo")


def misje() -> Path:
    return Path(os.environ.get("JARVO_MISSIONS_DIR") or jarvo() / "missions")


def stan() -> Path:
    return Path(os.environ.get("JARVO_STATE_DIR") or jarvo() / "state")


def skarbiec() -> Path:
    return Path(os.environ.get("JARVO_KNOWLEDGE_DIR") or jarvo() / "knowledge")


def build() -> Path:
    """Build floty: JARVO_BUILD_DIR, natywnie `<root>/build` obok `<root>/dane` (docs/NATYWNIE.md c1), w kontenerze
    /opt/jarvo/build."""
    if os.environ.get("JARVO_BUILD_DIR"):
        return Path(os.environ["JARVO_BUILD_DIR"])
    d = dane()
    obok = d.parent / "build"
    return obok if d != KONTENER and d.name == "dane" and obok.is_dir() else Path("/opt/jarvo/build")


def hermes() -> str:
    """Polecenie hermes pełną ścieżką: JARVO_HERMES_BIN (natywnie `<checkout>/.venv/Scripts/hermes.exe`) albo z PATH;
    na Windows nakładka bywa plikiem .cmd, którego CreateProcess nie znajdzie po samej nazwie."""
    prog = os.environ.get("JARVO_HERMES_BIN") or "hermes"
    return shutil.which(prog) or prog

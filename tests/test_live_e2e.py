"""Test aplikacji Jarvo na żywo (scripts/jarvo-e2e.sh, tests/live/jarvo_e2e.cjs; docs/HQ.md §2c, „Aplikacja”) z pytest.

Tylko na życzenie: z JARVO_E2E=1 w env pytest. W kontenerze jarvo-hermes (jako hermes) uruchamia skrypt wprost,
na komputerze z piaskownicą przez `docker exec -u hermes jarvo-hermes` (kontener musi działać z JARVO_E2E=1, który
sandbox-up.sh wpisuje do compose/.env). Bez JARVO_E2E=1 albo bez kontenera (CI, zwykły przebieg pytest) test jest
pomijany; tam to samo sprawdzają testy jednostkowe powłoki, loadera i ochrony zapisu.

    JARVO_E2E=1 python3 -m pytest -q -p no:cacheprovider tests/test_live_e2e.py
"""
from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess

import pytest

from conftest import REPO

KONTENER = "jarvo-hermes"
SKRYPT = "scripts/jarvo-e2e.sh"


def _polecenie(etap: str) -> list[str] | str:
    """Polecenie uruchomienia albo powód pominięcia (str)."""
    if os.environ.get("JARVO_E2E") != "1":
        return "na życzenie: JARVO_E2E=1 (piaskownica z sandbox-up.sh)"
    if getpass.getuser() == "hermes":                       # w kontenerze
        if not shutil.which("node") or not os.environ.get("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD"):
            return "brak node albo hasła dashboardu w env kontenera"
        return ["bash", str(REPO / SKRYPT), etap]
    if not shutil.which("docker"):
        return "brak dockera i to nie kontener jarvo-hermes"
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", KONTENER], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        return f"kontener {KONTENER} nie działa"
    return ["docker", "exec", "-u", "hermes", KONTENER, "sh", "-c",
            "PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH NODE_PATH=/opt/jarvo/node/node_modules "
            f"bash /opt/jarvo/repo/{SKRYPT} {etap}"]


# etap1: punkty 1–9; etap3: 3a (1–9), 3b (10–13: kompozytor, Markdown, adresat, zgoda) i 3c (14–23: start, gotowość,
# bez przyklejania, załączniki, Stop i Ponów, odświeżenie, 5 kart, aktualizacja, wylogowanie, klawiatura) w kolejności
# przebiegu; etap2: 1–16, osobno
PUNKTY = {"etap1": [str(i) for i in range(1, 10)],
          "etap3": ["1", "2", "3", "4", "14", "15", "10", "11", "12", "16", "13", "17", "18", "19", "5", "6", "23", "7",
                    "20", "21", "22", "8", "9"]}


@pytest.mark.parametrize("etap", ["etap1", "etap3"])
def test_aplikacja_na_zywo(etap):
    polecenie = _polecenie(etap)
    if isinstance(polecenie, str):
        pytest.skip(polecenie)
    r = subprocess.run(polecenie, capture_output=True, text=True, timeout=1800)
    assert "{" in r.stdout, r.stderr[-2000:]
    raport = json.loads(r.stdout[r.stdout.index("{"):])
    nieudane = [f"{w['id']} {w['nazwa']}: {w.get('blad', '')}" for w in raport["wyniki"] if not w["ok"]]
    assert r.returncode == 0 and raport["ok"] is True, "\n".join(nieudane) or r.stderr[-2000:]
    assert raport["etap"] == etap and [w["id"] for w in raport["wyniki"]] == PUNKTY[etap]

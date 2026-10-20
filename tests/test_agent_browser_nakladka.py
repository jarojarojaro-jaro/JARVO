"""Nakładka infra/bin/agent-browser: demon agent-browsera bez serwera podglądu (docs/TOOLBOX.md)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import REPO

NAKLADKA = REPO / "infra" / "bin" / "agent-browser"

# udawana binarka agent-browsera: zapisuje wywołania (argumenty i wejście) i odpowiada jak 0.38.1
UDAWANA = """#!/bin/bash
printf '%s\\n' "$*" >> "$LOG"
if [[ " $* " == *" stream disable "* ]]; then
  case "${STAN:-wylaczony}" in
    wlaczony) echo '{"success":true,"data":{"disabled":true},"error":null}' ;;
    wylaczony) echo '{"success":false,"data":null,"error":"Streaming is not enabled for this session"}' ;;
    blad) echo '{"success":false,"data":null,"error":"Failed to connect to daemon"}'; exit 1 ;;
  esac
  exit 0
fi
wejscie=$(cat)
[[ -n $wejscie ]] && printf 'stdin:%s\\n' "$wejscie" >> "$LOG"
echo '{"success":true,"data":{"title":"x"},"error":null}'
"""


@pytest.fixture
def ab(tmp_path: Path):
    binarka = tmp_path / "agent-browser-linux-x64"
    binarka.write_text(UDAWANA, encoding="utf-8")
    binarka.chmod(0o755)
    log = tmp_path / "wywolania.log"

    def uruchom(*args: str, stan: str = "wylaczony", wejscie: str = "") -> tuple[subprocess.CompletedProcess, list[str]]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_BROWSER_")}
        env.update(JARVO_AGENT_BROWSER_BIN=str(binarka), LOG=str(log), STAN=stan)
        p = subprocess.run(["bash", str(NAKLADKA), *args], input=wejscie, capture_output=True, text=True, env=env, timeout=10)
        wyw = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        log.unlink(missing_ok=True)
        return p, wyw

    return uruchom


def test_wylacza_podglad_przed_poleceniem_z_tymi_samymi_flagami(ab):
    # dokładnie tak woła Hermes (tools/browser_tool_session.py): flagi sesji, --json, polecenie
    p, wyw = ab("--session", "s1", "--engine", "lightpanda", "--json", "open", "https://example.com", stan="wlaczony")
    assert p.returncode == 0 and json.loads(p.stdout)["success"] is True
    assert wyw == ["--session s1 --engine lightpanda --json --json stream disable",
                   "--session s1 --engine lightpanda --json open https://example.com"]
    p, wyw = ab("--session", "s1", "--headed", "--json", "get", "title")             # już wyłączony: polecenie idzie
    assert p.returncode == 0 and wyw[0] == "--session s1 --headed --json --json stream disable"
    p, wyw = ab("open", "https://example.com", "--session", "s2", "--idle-timeout", "5000")   # flagi po poleceniu też
    assert wyw[0] == "--session s2 --idle-timeout 5000 --json stream disable"


def test_wejscie_trafia_do_polecenia(ab):
    p, wyw = ab("--session", "s1", "--json", "batch", wejscie='[["get","title"]]')
    assert p.returncode == 0 and wyw[-1] == 'stdin:[["get","title"]]'


def test_nie_puszcza_polecenia_gdy_podgladu_nie_da_sie_wylaczyc(ab):
    p, wyw = ab("--session", "s1", "--json", "open", "https://example.com", stan="blad")
    assert p.returncode == 1 and json.loads(p.stdout)["success"] is False
    assert "nie poszło dalej" in json.loads(p.stdout)["error"]
    assert not any("open" in w for w in wyw)


@pytest.mark.parametrize("polecenie", [["stream", "enable"], ["stream", "enable", "--port", "9223"], ["dashboard", "start"], ["mcp"]])
def test_serwery_bez_hasla_odrzucone(ab, polecenie):
    p, wyw = ab("--session", "s1", "--json", *polecenie)
    assert p.returncode == 1 and json.loads(p.stdout)["success"] is False and wyw == []
    p, wyw = ab(*polecenie)                                                        # bez --json: komunikat na stderr
    assert p.returncode == 1 and p.stdout == "" and "agent-browser:" in p.stderr and wyw == []


@pytest.mark.parametrize("args", [["--version"], ["--help"], ["install"], ["doctor", "--offline"], ["session", "list"], []])
def test_polecenia_bez_demona_bez_wylaczania(ab, args):
    p, wyw = ab(*args)
    assert p.returncode == 0 and wyw == [" ".join(args)]


def test_stream_status_i_close_tez_najpierw_wylaczaja(ab):
    # pominięte uruchomiłyby demona z serwerem podglądu
    for args in (["--session", "s1", "stream", "status"], ["--session", "s1", "close"]):
        p, wyw = ab(*args, stan="wlaczony")
        assert wyw[0] == "--session s1 --json stream disable" and wyw[1] == " ".join(args)


def test_hermes_znajduje_nakladke_pierwsza():
    docker = (REPO / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert NAKLADKA.stat().st_mode & 0o111
    assert "COPY --chmod=0755 infra/bin/ /opt/jarvo/bin/" in docker
    assert 'ENV PATH="/opt/jarvo/bin:' in docker                 # przed node_modules/.bin z natywną binarką
    assert "ln -sf /opt/jarvo/bin/agent-browser /usr/local/bin/agent-browser" in docker

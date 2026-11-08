"""`jarvo telefon on|off|status` (jarvo/telefon.py, docs/MOBILE.md „Telefon przez PHONEUSE”): serwer MCP PHONEUSE
w zainstalowanych profilach jarvo (odczyt) i jarvo-operator (pełny).

Bez telefonu i bez Hermesa: instalacja to katalog tymczasowy z `program/current.json` (kod tego repo), PHONEUSE to
katalog z pustym `tools/phone_mcp.py`, Python serwera to atrapa (tests/atrapy.py), która drukuje wersję mcp, a YAML
profili pisze prawdziwy kod install_fleet.ustaw_klucze_profilu Pythonem testów (zamiast Pythona Hermesa). Restart bramy
to atrapa, która zapisuje wywołania.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import atrapy
import pytest
import yaml

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import android, rece, sciezki, telefon  # noqa: E402

PROFILE = ("jarvo", "jarvo-operator")
CONFIG = "model:\n  default: x\nmcp_servers: {}\n"


@pytest.fixture
def inst(tmp_path, monkeypatch):
    root = tmp_path / "Jarvo"
    u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    for agent in PROFILE:
        p = u.dane / "profiles" / agent / "config.yaml"
        p.parent.mkdir(parents=True)
        p.write_text(CONFIG, encoding="utf-8")
    phoneuse = tmp_path / "PHONEUSE"
    (phoneuse / "tools").mkdir(parents=True)
    (phoneuse / "tools" / "phone_mcp.py").write_text("# atrapa\n", encoding="utf-8")
    python = atrapy.program(tmp_path / "venv", "python", 'print("2.3.0")\n')
    adb = tmp_path / "pt" / "adb"
    for z in (*rece.ZNACZNIKI_FLOTY, "HERMES_HOME"):
        monkeypatch.delenv(z, raising=False)
    restarty: list = []
    monkeypatch.setattr(telefon, "_python_hermesa", lambda _u: Path(sys.executable))
    monkeypatch.setattr(telefon, "zrestartuj_brame", lambda _u: restarty.append(1) or "zrestartowana")
    monkeypatch.setattr(android, "adb", lambda _u: adb)
    return argparse.Namespace(u=u, phoneuse=phoneuse, python=python, adb=adb, restarty=restarty, tmp=tmp_path)


def jarvo(inst, *argv: str) -> int:
    p = argparse.ArgumentParser()
    telefon.dodaj_polecenia(p.add_subparsers())
    a = p.parse_args(["telefon", *argv])
    return a.funkcja(inst.u, a)


def wlacz(inst, *extra: str) -> int:
    return jarvo(inst, "on", "--phoneuse", str(inst.phoneuse), "--python", str(inst.python), *extra)


def wpis(inst, agent: str):
    cfg = yaml.safe_load((inst.u.dane / "profiles" / agent / "config.yaml").read_text(encoding="utf-8"))
    return (cfg.get("mcp_servers") or {}).get("phone")


def kanban(db: Path, karty: list[tuple[str, str, str, str]]) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE tasks (id TEXT, title TEXT, assignee TEXT, status TEXT, started_at INTEGER)")
    c.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, 1)", karty)
    c.commit()
    c.close()


def test_on_wpisuje_serwer_odczyt_dla_szefa_i_restartuje_raz(inst):
    assert wlacz(inst, "--telefon", "pixel") == 0
    st = telefon.stan_telefonu(inst.u)
    assert st["wlaczony"] is True and st["telefon"] == "pixel"
    assert st["serwer"] == str(inst.phoneuse / "tools" / "phone_mcp.py")
    szef, operator = wpis(inst, "jarvo"), wpis(inst, "jarvo-operator")
    assert szef["tools"] == {"include": ["list_phones", "ping", "screen", "shot", "wait"]}
    assert "tools" not in operator                                   # Operator: wszystkie narzędzia, także act i batch
    for w in (szef, operator):
        assert w["command"] == str(inst.python) and w["args"] == [st["serwer"]]
        assert w["env"] == {"ADB": str(inst.adb), "PHONEUSE_PHONE": "pixel"}
        assert (w["trust"], w["timeout"], w["lazy"], w["resources"], w["prompts"]) == ("full", 360, True, False, False)
    assert inst.restarty == [1]
    assert wlacz(inst, "--telefon", "pixel") == 0                   # to samo drugi raz: bez restartu bramy
    assert inst.restarty == [1]
    s = telefon.opis_stanu(inst.u)                                   # status czyta YAML profili tym samym kodem
    assert s["sdk"] == "2.3.0" and s["adb"] == str(inst.adb) and s["profile"]["jarvo"]["tools"] == szef["tools"]


def test_on_bez_serwera_albo_sdk_niczego_nie_zmienia(inst, capsys):
    bez_sdk = atrapy.program(inst.tmp / "stary", "python", "import sys\nsys.stderr.write(\"No module named 'mcp'\\n\")\n"
                                                           "sys.exit(1)\n")
    sdk1 = atrapy.program(inst.tmp / "sdk1", "python", 'print("1.9.4")\n')
    assert jarvo(inst, "on", "--phoneuse", str(inst.tmp / "nie-ma"), "--python", str(inst.python)) == 1
    assert "phone_mcp.py" in capsys.readouterr().err
    for py in (bez_sdk, sdk1, inst.tmp / "brak" / "python"):
        assert jarvo(inst, "on", "--phoneuse", str(inst.phoneuse), "--python", str(py)) == 1
        assert "mcp_setup.py" in capsys.readouterr().err                 # rada: venv z SDK od PHONEUSE
    assert wlacz(inst, "--telefon", "zly;nazwa") == 2
    assert not (inst.u.stan / telefon.STAN).exists() and inst.restarty == []
    assert all(wpis(inst, a) is None for a in PROFILE)


def test_karta_w_toku_na_innej_tablicy_wstrzymuje_restart(inst, capsys):
    kanban(inst.u.dane / "kanban.db", [("t_1", "Stara", "jarvo-web", "done")])
    kanban(inst.u.dane / "kanban" / "boards" / "klient" / "kanban.db", [("t_2", "Formularz", "jarvo-operator", "running")])
    assert wlacz(inst) == 0
    out = capsys.readouterr().out
    assert inst.restarty == [] and "Formularz" in out and "jarvo serwis --restart brama" in out
    assert wpis(inst, "jarvo-operator")["command"] == str(inst.python)  # config i tak zmieniony: zadziała po restarcie


def test_off_wylacza_wpis_a_bez_wpisu_nic_nie_dopisuje(inst):
    assert jarvo(inst, "off") == 0                                      # nigdy nie włączony: profile bez śladu phone
    assert all(wpis(inst, a) is None for a in PROFILE) and inst.restarty == []
    assert wlacz(inst) == 0 and inst.restarty == [1]
    assert jarvo(inst, "off") == 0
    assert telefon.stan_telefonu(inst.u)["wlaczony"] is False and telefon.klucze_profili(inst.u) == {}
    assert all(wpis(inst, a)["enabled"] is False for a in PROFILE) and inst.restarty == [1, 1]


@pytest.mark.parametrize("zmienna", ["HERMES_KANBAN_TASK", "HERMES_CRON_SESSION", "JARVO_DATA_DIR"])
def test_on_i_off_tylko_wlasciciel(inst, monkeypatch, capsys, zmienna):
    monkeypatch.setenv(zmienna, "1")
    assert wlacz(inst) == 1 and jarvo(inst, "off") == 1
    assert capsys.readouterr().err.count("tylko właściciel") == 2
    assert not (inst.u.stan / telefon.STAN).exists() and inst.restarty == []
    assert jarvo(inst, "status") == 0                                    # podgląd może każdy


def test_doctor_widzi_zniknieta_instalacje_phoneuse(inst):
    assert [w["stan"] for w in telefon.sprawdzenia(inst.u)] == ["ok"]   # wyłączony: opcjonalny
    assert wlacz(inst) == 0
    assert [w["stan"] for w in telefon.sprawdzenia(inst.u)] == ["ok"]
    (inst.phoneuse / "tools" / "phone_mcp.py").unlink()
    w = telefon.sprawdzenia(inst.u)[0]
    assert w["stan"] == "uwaga" and "phone_mcp.py" in w["opis"]

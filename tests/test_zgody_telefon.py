"""Strażnik zgód: jedno zadanie = jeden telefon floty i blokada prywatnego numeru właściciela (26.11)."""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("jarvo_zgody_plugin_telefon", REPO / "zgody" / "plugin" / "__init__.py")
z = importlib.util.module_from_spec(_spec)
sys.modules["jarvo_zgody_plugin_telefon"] = z
_spec.loader.exec_module(z)

IP = {"first": "100.99.0.1", "second": "100.99.0.2", "third": "100.99.0.3"}
NUMER_TESTOWY = "600100200"          # fikcyjny numer tylko dla testu


@pytest.fixture
def straz(tmp_path, monkeypatch):
    home = tmp_path / "dane" / "profiles" / "jarvo"
    home.mkdir(parents=True)
    monkeypatch.setattr(z, "_hermes_home", lambda: home)
    monkeypatch.setattr(z, "_decyzja", lambda tool_name, args, task_id: None)
    monkeypatch.setattr(z, "_mapa_ip", lambda: {ip: n for n, ip in IP.items()})
    monkeypatch.setattr(z, "_TELEFON_ZADANIA", collections.OrderedDict())
    monkeypatch.setattr(z, "_NUMERY_CACHE", {})
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("PHONEUSE_ONLY", raising=False)
    return home


def hak(narzedzie, sesja="s1", **args):
    return z.straznik_zgod(tool_name=narzedzie, args=args, task_id="t", session_id=sesja)


def zablokowane(w):
    return bool(w) and w["action"] == "block"


def test_mcp_przeskok_w_zadaniu_blokowany(straz):
    assert hak("mcp__phone__act", cmd="tap") is None              # brak phone = first
    w = hak("mcp__phone__act", phone="third", cmd="tap")
    assert zablokowane(w) and "telefonie first" in w["message"]


def test_inne_zadanie_zaczyna_od_zera(straz, monkeypatch):
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None
    assert hak("mcp__phone__act", sesja="s2", phone="third", cmd="tap") is None
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_nowa")
    assert hak("mcp__phone__act", phone="second", cmd="tap") is None


def test_adb_akcja_na_innym_telefonie_blokowana(straz):
    assert hak("terminal", command=f"adb -s {IP['first']}:5555 shell input tap 1 2") is None
    assert zablokowane(hak("terminal", command=f"adb -s {IP['third']}:5555 shell am start -a android.intent.action.VIEW"))


def test_petla_akcji_po_dwoch_telefonach_blokowana(straz):
    polecenie = f"for N in first:{IP['first']} third:{IP['third']}; do adb -s ${{N#*:}}:5555 shell input keyevent 3; done"
    assert zablokowane(hak("terminal", command=polecenie))


def test_odczyt_nie_wiaze_i_nie_blokuje(straz):
    """27.11: Jarvo sprawdzał, czy na którymś telefonie jest OLX, a strażnik blokował odczyt wszystkich telefonów."""
    assert hak("mcp__phone__act", phone="third", cmd="tap") is None
    assert hak("mcp__phone__list_phones") is None
    assert hak("mcp__phone__ping", phone="second") is None
    assert hak("mcp__phone__screen", phone="first") is None
    polecenie = f"for S in {IP['first']} {IP['third']}; do adb -s $S:5555 shell pm list packages | grep olx; done"
    assert hak("terminal", command=polecenie) is None
    assert hak("terminal", command="ls 100.99.0.1") is None        # bez adb nie dotyczy telefonu


def test_wiazanie_rozmowy_wygasa(straz, monkeypatch):
    zegar = [1000.0]
    monkeypatch.setattr(z.time, "monotonic", lambda: zegar[0])
    assert hak("mcp__phone__act", phone="first", cmd="tap") is None
    zegar[0] += 1801
    assert hak("mcp__phone__act", phone="third", cmd="tap") is None


def test_prywatny_numer_blokowany(straz):
    plik = straz.parent.parent / "jarvo" / "konfig" / "prywatne-numery.json"
    assert hak("mcp__phone__act", cmd="type", text="+48 600 100 200") is None        # brak pliku = nic
    plik.parent.mkdir(parents=True)
    plik.write_text(json.dumps({"sha256_9": [hashlib.sha256(NUMER_TESTOWY.encode()).hexdigest()]}), encoding="utf-8")
    w = hak("mcp__phone__act", cmd="type", text="+48 600 100 200")
    assert zablokowane(w) and "prywatny numer JARO" in w["message"]
    assert zablokowane(hak("browser_type", text="0048-600.100(200)"))
    assert hak("mcp__phone__act", sesja="s9", cmd="type", text="+48 600 100 201") is None


def test_mapa_z_telefon_json(tmp_path, monkeypatch):
    home = tmp_path / "root" / "dane" / "profiles" / "jarvo"
    home.mkdir(parents=True)
    stan = tmp_path / "root" / "stan"
    stan.mkdir()
    (stan / "telefon.json").write_text(json.dumps({"adresy": {n: f"{ip}:5555" for n, ip in IP.items()}}),
                                       encoding="utf-8")
    monkeypatch.setattr(z, "_hermes_home", lambda: home)
    monkeypatch.setattr(z, "_MAPA", {"t": 0.0, "ip": {}})
    assert z._mapa_ip() == {ip: n for n, ip in IP.items()}


@pytest.mark.parametrize("polecenie", [
    '$A -s $S shell "pm clear com.android.chrome"',
    "adb -s 100.99.0.1:5555 shell cmd package uninstall com.x",
    "adb uninstall com.x",
    "for S in a b; do adb -s $S shell sh -c 'rm -rf /sdcard/Download'; done",
    "adb shell settings delete global x",
    "adb reboot recovery",
    "adb -s $S shell cmd connectivity airplane-mode enable",
    "adb shell settings put global airplane_mode_on 1",
    "adb shell svc wifi disable",
    "adb shell 'cmd wifi set-wifi-enabled disabled'",
])
def test_adb_niszczace_blokowane(straz, polecenie):
    w = hak("terminal", command=polecenie)
    assert zablokowane(w) and "tylko na wyraźne polecenie JARO" in w["message"]


@pytest.mark.parametrize("polecenie", [
    '$A -s $S shell "pm list packages"',
    "adb -s 100.99.0.1:5555 shell am start -n com.android.chrome/.Main",
    "adb -s $S shell cmd connectivity airplane-mode disable",
])
def test_adb_odczyt_i_start_przechodza(straz, polecenie):
    assert hak("terminal", command=polecenie) is None

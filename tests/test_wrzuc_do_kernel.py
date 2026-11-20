"""Ręczne wrzucanie do skrzynki sesji (profiles/jarvo/scripts/wrzuc_do_kernel.py): cel z sesje.json, bez stałych ID."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SKRYPT = Path(__file__).resolve().parents[1] / "profiles/jarvo/scripts/wrzuc_do_kernel.py"
spec = importlib.util.spec_from_file_location("wrzuc_do_kernel", SKRYPT)
wk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wk)


def _uklad(tmp_path: Path, monkeypatch, sesje: dict) -> Path:
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "dane" / "jarvo"))
    konfig = tmp_path / "dane" / "jarvo" / "konfig"
    konfig.mkdir(parents=True)
    (konfig / "sesje.json").write_text(json.dumps(sesje), encoding="utf-8")
    return tmp_path


def test_domyslnie_kernel_z_watkiem_z_konfiguracji(tmp_path, monkeypatch, capsys):
    skrz = tmp_path / "kernel" / "skrzynka"
    _uklad(tmp_path, monkeypatch, {
        "gpu": {"nazwa": "Kernel", "skrzynka": str(skrz), "czat": "-1001", "watek": "7"},
        "sklep": {"nazwa": "Sklep", "profil": "jarvo-sklep"}})
    assert wk.main(["305:https://x.com/a/status/1", "306:drugi link"]) == 0
    pliki = sorted((skrz / "nowe").glob("*.json"))
    assert [p.name.rsplit("-", 1)[1] for p in pliki] == ["305.json", "306.json"]
    m = json.loads(pliki[0].read_text(encoding="utf-8"))
    assert m["dopisek"] == "gpu" and m["nazwa"] == "Kernel" and m["tekst"] == "https://x.com/a/status/1"
    assert (m["chat_id"], m["watek"], m["message_id"], m["zrodlo"]) == ("-1001", "7", "305", "reczne")
    assert not list((skrz / "nowe").glob(".*.tmp"))
    assert "Kernel · 305: zapisane" in capsys.readouterr().out


def test_ta_sama_wiadomosc_drugi_raz_nie_wchodzi(tmp_path, monkeypatch, capsys):
    skrz = tmp_path / "op"
    (skrz / "zrobione").mkdir(parents=True)
    (skrz / "zrobione" / "20261114-041000-318.json").write_text("{}", encoding="utf-8")
    _uklad(tmp_path, monkeypatch, {"op": {"nazwa": "Operator", "skrzynka": str(skrz)}})
    assert wk.main(["--sesja", "OP", "318:już było", "321:nowe"]) == 0
    assert [p.name.rsplit("-", 1)[1] for p in (skrz / "nowe").glob("*.json")] == ["321.json"]
    m = json.loads(next((skrz / "nowe").glob("*.json")).read_text(encoding="utf-8"))
    assert (m["dopisek"], m["chat_id"], m["watek"]) == ("op", "", "")
    assert "318: już jest" in capsys.readouterr().out


@pytest.mark.parametrize("sesje, argumenty, fraza", [
    ({"sklep": {"nazwa": "Sklep", "profil": "jarvo-sklep"}}, ["1:x"], "o nazwie „Kernel”"),
    ({"sklep": {"nazwa": "Sklep", "profil": "jarvo-sklep"}}, ["--sesja", "sklep", "1:x"], "nie ma skrzynki"),
    ({"gpu": {"nazwa": "Kernel", "skrzynka": "kernel/skrzynka"}}, ["1:x"], "bezwzględną"),
    ({"gpu": {"nazwa": "Kernel", "skrzynka": "/tmp/k"}}, ["bez-dwukropka"], "zły argument"),
    ({"gpu": {"nazwa": "Kernel", "skrzynka": "/tmp/k"}}, ["../x:tekst"], "zły argument"),
])
def test_bledy_bez_zapisu(tmp_path, monkeypatch, capsys, sesje, argumenty, fraza):
    _uklad(tmp_path, monkeypatch, sesje)
    assert wk.main(argumenty) == 1
    assert fraza in capsys.readouterr().err


def test_bez_konfiguracji(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "brak"))
    assert wk.main(["1:x"]) == 1
    assert "sesje.json" in capsys.readouterr().err

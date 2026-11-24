"""Budzenie agenta, gdy jego podagenci w tle skończyli (hq/plugin/obserwator.py `_podagenci`). 24.11 Jarvo dał
pracę 3 podagentom `delegate_task` z czatu panelu i skończył turę; Hermes przez api_server zapisuje wynik
podagentów bez budzenia modelu, więc Jarvo nie wrócił z raportem, a właściciel nie widział pracy."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from conftest import load_script

obserwator = load_script("hq/plugin/obserwator.py", "jarvo_test_podagenci_obserwator")


class Db:
    def __init__(self, przebiegi):
        self.przebiegi = przebiegi
        self.wpisy = []

    def przebiegi_z_podagentami(self, od):
        return [p for p in self.przebiegi if p.get("kroki")]

    def przebiegi_watku(self, wid):
        return [p for p in self.przebiegi if p["watek_id"] == wid]

    def dodaj_wpis(self, wid, **pola):
        w = {"id": f"e{len(self.wpisy)}", "watek_id": wid, **pola}
        self.wpisy.append(w)
        return w


class Rejestr:
    def __init__(self):
        self.zlecone = []

    def zlec(self, **pola):
        self.zlecone.append(pola)
        return {"id": f"p{len(self.zlecone)}"}


def _manifest(home, did, stany):
    k = home / "profiles" / "jarvo" / "cache" / "delegation" / "live" / did
    k.mkdir(parents=True, exist_ok=True)
    (k / "manifest.json").write_text(json.dumps({"delegation_id": did, "tasks": [
        {"index": i, "goal": f"Paczka {i + 4}", "status": s} for i, s in enumerate(stany)]}), encoding="utf-8")
    return k


def _obserwator(tmp_path, przebiegi):
    db, rej = Db(przebiegi), Rejestr()
    hub = SimpleNamespace(nadaj=lambda *a, **k: None)
    o = obserwator.Obserwator(db=db, czytnik=None, rejestr=rej, hub=hub, agenci=None, home=tmp_path,
                              jarvo_dir=tmp_path / "jarvo")
    return o, db, rej


def test_podagenci_budza_agenta_raz_po_koncu_wszystkich(tmp_path):
    tura = {"id": "r1", "watek_id": "w1", "agent": "jarvo", "utworzony_at": 1.0, "lancuch_id": "l1",
            "kroki": [{"narzedzie": "delegate_task", "podglad": "{\"delegation_id\": \"deleg_83f69bbe\"}"}]}
    o, db, rej = _obserwator(tmp_path, [tura])
    _manifest(tmp_path, "deleg_83f69bbe", ["completed", "running", "completed"])
    asyncio.run(o._podagenci(100.0))
    assert rej.zlecone == []                                     # jeden jeszcze pracuje

    _manifest(tmp_path, "deleg_83f69bbe", ["completed", "completed", "failed"])
    asyncio.run(o._podagenci(200.0))
    assert len(rej.zlecone) == 1
    z = rej.zlecone[0]
    assert z["agent"] == "jarvo" and z["watek_id"] == "w1" and z["zrodlo"] == "system" and z["lancuch_id"] == "l1"
    assert z["prosba"].startswith("[podagenci] Delegacja deleg_83f69bbe: 3 z 3 skończonych.") and "Paczka 5" in z["prosba"]
    assert db.wpisy[0]["dane"]["typ"] == "podagenci" and z["wpis_id"] == db.wpisy[0]["id"]

    asyncio.run(o._podagenci(300.0))
    assert len(rej.zlecone) == 1                                 # bez drugiego budzenia


def test_podagenci_nie_budza_gdy_agent_juz_pracowal_po_ich_koncu(tmp_path):
    k = _manifest(tmp_path, "deleg_1a2b3c4d", ["completed"])
    mtime = (k / "manifest.json").stat().st_mtime
    tura = {"id": "r1", "watek_id": "w1", "agent": "jarvo", "utworzony_at": 1.0,
            "kroki": [{"narzedzie": "delegate_task", "podglad": "deleg_1a2b3c4d"}]}
    pozniej = {"id": "r2", "watek_id": "w1", "agent": "jarvo", "utworzony_at": mtime + 5, "kroki": []}
    o, db, rej = _obserwator(tmp_path, [tura, pozniej])
    asyncio.run(o._podagenci(100.0))
    assert rej.zlecone == [] and db.wpisy == []


def test_restart_bramy_konczy_podagentow_bez_konca_w_manifescie_i_budzi_agenta(tmp_path):
    """24.11 13:22: wgranie zrestartowało bramę w trakcie pracy trzech podagentów; Hermes nie dopisał końca do
    manifestu, panel pokazywał „0 z 3 gotowe” bez końca, a Jarvo nie wiedział, że praca stoi."""
    import os
    k = _manifest(tmp_path, "deleg_494badc9", ["running", "running", "running"])
    (k / "task-0.log").write_text("13:22:44 tool     | -> vision_analyze(...)\n", encoding="utf-8")
    (k / "task-1.log").write_text("13:22:49 final    | status=interrupted duration=415.95s summary: …\n", encoding="utf-8")
    for p in k.iterdir():
        os.utime(p, (1000.0, 1000.0))
    tura = {"id": "r1", "watek_id": "w1", "agent": "jarvo", "utworzony_at": 1.0,
            "kroki": [{"narzedzie": "delegate_task", "podglad": "deleg_494badc9"}]}
    o, db, rej = _obserwator(tmp_path, [tura])

    (tmp_path / "gateway.pid").write_text("1", encoding="utf-8")
    os.utime(tmp_path / "gateway.pid", (900.0, 900.0))           # brama sprzed ostatniego zapisu: praca trwa
    d = obserwator.stan_delegacji(k)
    assert [z["stan"] for z in d["zadania"]] == ["running", "interrupted", "running"] and not d["koniec"]
    asyncio.run(o._podagenci(100.0))
    assert rej.zlecone == []

    os.utime(tmp_path / "gateway.pid", (1100.0, 1100.0))         # brama wstała po ostatnim zapisie
    d = obserwator.stan_delegacji(k)
    assert [z["stan"] for z in d["zadania"]] == ["interrupted"] * 3 and d["koniec"] and d["przerwana"]
    asyncio.run(o._podagenci(200.0))
    assert len(rej.zlecone) == 1 and "Restart bramy przerwał" in rej.zlecone[0]["prosba"]
    assert db.wpisy[0]["tekst"] == "Podagenci przerwani restartem: 3 z 3 skończonych"

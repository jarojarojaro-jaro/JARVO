"""Podagenci w tle w panelu (hq/plugin/trasy_rozmow.py `GET /rozmowy/{id}/podagenci` i dziennik podagenta,
obserwator.py `delegacje_przebiegow`, `ogon_dziennika`). 24.11 właściciel nie widział pracy podagentów Jarva: trasa
składa stan z manifestu Hermesa, dziennik tylko z katalogu tej delegacji i przez `ochrona.utajnij`."""
from __future__ import annotations

import json
import os
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import test_silnik_rozmow as T  # noqa: E402

M, P = T.M, T.P
DID = "deleg_83f69bbe"
KLUCZ = "sk-ant-" + "a" * 40


@pytest.fixture
def swiat(tmp_path):
    s = T.Swiat(tmp_path)
    yield s
    s.zamknij()


def _live(home, agent="test-e2e-a"):
    return home / "profiles" / agent / "cache" / "delegation" / "live"


def _manifest(home, did, stany, agent="test-e2e-a"):
    k = _live(home, agent) / did
    k.mkdir(parents=True, exist_ok=True)
    (k / "manifest.json").write_text(json.dumps({"delegation_id": did, "started_at": 1700000000, "tasks": [
        {"index": i, "goal": f"Paczka {i + 4}", "status": s} for i, s in enumerate(stany)]}), encoding="utf-8")
    return k


def _watek_z_delegacja(swiat, did=DID, *, at=None, agent="test-e2e-a"):
    db = swiat.sil.db
    w = db.utworz_watek(tytul="Podagenci")
    e = db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="zrób paczki")
    p = db.dodaj_przebieg(watek_id=w["id"], wpis_id=e["id"], agent=agent, stan="gotowe", utworzony_at=at or time.time(),
                          kroki=[{"narzedzie": "delegate_task", "podglad": json.dumps({"delegation_id": did})}])
    return w["id"], p["id"]


def test_trasa_podaje_delegacje_ze_stanem_zadan(swiat):
    _manifest(swiat.home, DID, ["completed", "running", "failed"])
    wid, pid = _watek_z_delegacja(swiat)
    r = swiat.k.get(f"{P}/rozmowy/{wid}/podagenci")
    assert r.status_code == 200, r.text
    (d,) = r.json()["delegacje"]
    assert (d["id"], d["agent"], d["przebieg_id"], d["start"]) == (DID, "test-e2e-a", pid, 1700000000.0)
    assert (d["gotowe"], d["razem"], d["koniec"]) == (2, 3, False)
    assert [(z["nr"], z["cel"], z["stan"], z["koniec"]) for z in d["zadania"]] == [
        (0, "Paczka 4", "completed", True), (1, "Paczka 5", "running", False), (2, "Paczka 6", "failed", True)]


def test_bez_manifestu_albo_starsza_niz_doba_brak_delegacji(swiat):
    wid, _ = _watek_z_delegacja(swiat)                                   # brak manifestu
    assert swiat.k.get(f"{P}/rozmowy/{wid}/podagenci").json() == {"delegacje": []}
    _manifest(swiat.home, "deleg_0123abcd", ["completed"])
    stary, _ = _watek_z_delegacja(swiat, "deleg_0123abcd", at=time.time() - 2 * 86400)
    assert swiat.k.get(f"{P}/rozmowy/{stary}/podagenci").json() == {"delegacje": []}


def test_dziennik_ostatnie_linie_utajnione(swiat):
    k = _manifest(swiat.home, DID, ["running"])
    (k / "task-0.log").write_text("".join(f"linia {i}\n" for i in range(100)) + f"klucz {KLUCZ}\n", encoding="utf-8")
    wid, _ = _watek_z_delegacja(swiat)
    r = swiat.k.get(f"{P}/rozmowy/{wid}/podagenci/{DID}/0")
    assert r.status_code == 200, r.text
    linie = r.json()["linie"]
    assert len(linie) == 40 and linie[0] == "linia 61" and linie[-2] == "linia 99"
    assert KLUCZ not in linie[-1] and M.ochrona.UKRYTE in linie[-1]
    assert swiat.k.get(f"{P}/rozmowy/{wid}/podagenci/{DID}/1").json() == {"linie": []}   # jeszcze bez dziennika


@pytest.mark.parametrize("did, nr", [("..", "0"), ("deleg_83f69bbe%2F..", "0"), (DID, "..%2Fmanifest.json"),
                                     (DID, "-1"), (DID, "0.log"), ("deleg_ffffffff", "0"), ("%2Fetc", "passwd")])
def test_dziennik_odrzuca_obce_sciezki(swiat, did, nr):
    _manifest(swiat.home, DID, ["running"])
    wid, _ = _watek_z_delegacja(swiat)
    r = swiat.k.get(f"{P}/rozmowy/{wid}/podagenci/{did}/{nr}")
    assert r.status_code == 404, (did, nr, r.status_code)


def test_dziennik_delegacji_innego_watku_to_404(swiat):
    k = _manifest(swiat.home, DID, ["running"])
    (k / "task-0.log").write_text("tajne\n", encoding="utf-8")
    _watek_z_delegacja(swiat)
    inny = swiat.sil.db.utworz_watek(tytul="obcy")["id"]
    assert swiat.k.get(f"{P}/rozmowy/{inny}/podagenci/{DID}/0").status_code == 404


@pytest.mark.wymaga_symlinku
def test_dowiazania_poza_katalog_delegacji(swiat, tmp_path):
    obcy = tmp_path / "obcy"
    obcy.mkdir()
    (obcy / "sekret.txt").write_text("tajne\n", encoding="utf-8")
    k = _manifest(swiat.home, DID, ["running"])
    os.symlink(obcy / "sekret.txt", k / "task-0.log")
    assert M.obserwator.ogon_dziennika(k, 0) is None
    (obcy / "manifest.json").write_text(json.dumps({"tasks": [{"goal": "x", "status": "running"}]}), encoding="utf-8")
    os.symlink(obcy, _live(swiat.home) / "deleg_abcdef12")
    assert M.obserwator.katalog_delegacji(swiat.home, "test-e2e-a", "deleg_abcdef12") is None
    wid, _ = _watek_z_delegacja(swiat)
    assert swiat.k.get(f"{P}/rozmowy/{wid}/podagenci/{DID}/0").status_code == 404


def test_katalog_delegacji_tylko_dobre_id_i_profil(tmp_path):
    for agent, did in (("../x", DID), ("Jarvo", DID), ("jarvo", "deleg_XYZ"), ("jarvo", "../deleg_83f69bbe"), ("", DID)):
        assert M.obserwator.katalog_delegacji(tmp_path, agent, did) is None, (agent, did)
    assert M.obserwator.katalog_delegacji(tmp_path, "jarvo", DID) == _live(tmp_path, "jarvo") / DID

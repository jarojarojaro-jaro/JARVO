"""Kanał Aktualizacje (hq/plugin/raporty.py, docs/HQ.md „Aktualizacje”): raport z zapisu przebiegu crona Hermesa
(odpowiedź, wyjście skryptu, błąd; cisza pominięta), trwałe archiwum ponad retencję Hermesa, filtr po rodzaju, strony,
nieprzeczytane, trasy GET /raporty i POST /raporty/przeczytane, zdarzenia strumienia."""
from __future__ import annotations

import json
import os

import pytest
from conftest import load_script

R = load_script("hq/plugin/raporty.py", "jarvo_test_raporty")

NAGLOWEK = "# Cron Job: {nazwa}\n\n**Job ID:** {id}\n**Run Time:** 2026-11-18 07:50:58\n**Schedule:** 50 7 * * *\n\n"


def _agent(nazwa, jid, odpowiedz, prompt="## Prompt\n\nSkill z sekcją ## Response w treści\n\n"):
    return NAGLOWEK.format(nazwa=nazwa, id=jid) + prompt + f"## Response\n\n{odpowiedz}\n"


def _skrypt(nazwa, jid, reszta):
    return (f"# Cron Job: {nazwa}\n\n**Job ID:** {jid}\n**Run Time:** 2026-11-18 07:15:49\n"
            f"**Mode:** no_agent (script)\n{reszta}")


def _zapisz(dane, zadanie, stem, tresc, ts, profil="jarvo"):
    p = dane / "profiles" / profil / "cron" / "output" / zadanie / f"{stem}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tresc, encoding="utf-8")
    os.utime(p, (ts, ts))
    os.utime(p.parent, (ts, ts))
    return p


def test_raport_z_zapisu_przebiegu():
    r = R.raport(_agent("Poranny brief", "jarvo-daily-brief", "☀️ Brief B-2026-11-18 · Dzień dobry.\n1. decyzja"))
    assert r == {"nazwa": "Poranny brief", "tekst": "☀️ Brief B-2026-11-18 · Dzień dobry.\n1. decyzja", "blad": False}
    for cichy in ("[SILENT]", "`[SILENT]`", "Nic nowego.\n[SILENT]", "[SILENT]\nnic", "SILENT", "NO_REPLY", "no reply."):
        assert R.raport(_agent("Patrol floty", "jarvo-patrol", cichy)) is None, cichy
    assert R.raport(_agent("Patrol floty", "jarvo-patrol", "Uwaga: [SILENT] w środku zdania to treść"))["tekst"]
    assert R.raport(_skrypt("Nowe wersje", "jarvo-new-versions", "\n---\n\nHermes v0.13 → v0.14\n")) == {
        "nazwa": "Nowe wersje", "tekst": "Hermes v0.13 → v0.14", "blad": False}
    assert R.raport(_skrypt("Nowe wersje", "jarvo-new-versions", "**Status:** silent (empty output)\n")) is None
    assert R.raport(_skrypt("Nowe wersje", "x", "**Status:** silent (wakeAgent=false)\n")) is None
    blad = R.raport(_skrypt("Świeżość wiedzy", "x", "**Status:** script failed\n\nTraceback: KeyError\n"))
    assert blad == {"nazwa": "Świeżość wiedzy", "tekst": "Traceback: KeyError", "blad": True}
    brama = NAGLOWEK.format(nazwa="Patrol floty", id="jarvo-patrol") + "Script gate returned `wakeAgent=false` — agent skipped.\n"
    assert R.raport(brama) is None
    awaria = NAGLOWEK.format(nazwa="Patrol floty", id="jarvo-patrol") + "## Error\n\n```\nRuntimeError: model\n```\n"
    assert R.raport(awaria) == {"nazwa": "Patrol floty", "tekst": "RuntimeError: model", "blad": True}


@pytest.fixture
def arch(tmp_path):
    dane = tmp_path / "dane"
    zegar = [1000.0]
    a = R.Archiwum(dane, tmp_path / "jarvo" / "state" / "raporty.db",
                   utajnij=lambda t: t.replace("sk-tajny", "[ukryte]"), zegar=lambda: zegar[0])
    return a, dane, zegar


def test_archiwum_zbiera_raz_i_trzyma_ponad_retencje(arch):
    a, dane, _ = arch
    assert a.lista() == {"raporty": [], "rodzaje": [], "nieprzeczytane": 0, "przeczytane_do": 0.0, "dalej": None}
    assert not a.plik.exists()                       # odczyt nie zakłada archiwum
    _zapisz(dane, "jarvo-daily-brief", "2026-11-17_07-50-56", _agent("Poranny brief", "jarvo-daily-brief", "Brief 17"), 1_000)
    _zapisz(dane, "jarvo-daily-brief", "2026-11-18_07-50-58", _agent("Poranny brief", "jarvo-daily-brief", "Brief 18 sk-tajny"), 3_000)
    _zapisz(dane, "jarvo-patrol", "2026-11-18_07-01-00", _agent("Patrol floty", "jarvo-patrol", "[SILENT]"), 2_000)
    p = _zapisz(dane, "jarvo-patrol", "2026-11-18_07-32-54", _agent("Patrol floty", "jarvo-patrol", "✅ Misja zamknięta"), 2_500)
    nowe = a.zbierz()
    assert [(n["rodzaj"], n["tekst"]) for n in sorted(nowe, key=lambda n: n["ts"])] == [
        ("jarvo-daily-brief", "Brief 17"), ("jarvo-patrol", "✅ Misja zamknięta"), ("jarvo-daily-brief", "Brief 18 [ukryte]")]
    assert nowe[0]["id"].startswith("jarvo/jarvo-") and a.zbierz() == []
    p.unlink()                                       # Hermes przyciął stare zapisy (cron.output_retention)
    os.utime(p.parent, (2_600, 2_600))
    assert a.zbierz() == []
    lista = a.lista()
    assert [r["tekst"] for r in lista["raporty"]] == ["Brief 18 [ukryte]", "✅ Misja zamknięta", "Brief 17"]
    assert all(r["nowy"] and r["profil"] == "jarvo" and r["blad"] is False for r in lista["raporty"])
    assert lista["rodzaje"] == [{"rodzaj": "jarvo-daily-brief", "nazwa": "Poranny brief", "liczba": 2, "ostatni": 3000.0},
                                {"rodzaj": "jarvo-patrol", "nazwa": "Patrol floty", "liczba": 1, "ostatni": 2500.0}]
    assert lista["nieprzeczytane"] == 3


def test_filtr_strony_i_przeczytane(arch):
    a, dane, _ = arch
    for i in range(5):
        _zapisz(dane, "jarvo-patrol", f"p{i}", _agent("Patrol floty", "jarvo-patrol", f"patrol {i}"), 100 + i)
    _zapisz(dane, "jarvo-weekly-review", "w0", _agent("Przegląd tygodnia", "jarvo-weekly-review", "tydzień"), 200)
    _zapisz(dane, "jarvo-new-versions", "n0", _skrypt("Nowe wersje", "jarvo-new-versions", "\n---\n\nnowa wersja\n"), 150,
            profil="jarvo-kernel")
    a.zbierz()
    s1 = a.lista(rodzaj="jarvo-patrol", limit=2)
    assert [r["tekst"] for r in s1["raporty"]] == ["patrol 4", "patrol 3"] and s1["dalej"] == 103.0
    s2 = a.lista(rodzaj="jarvo-patrol", przed=s1["dalej"], limit=2)
    assert [r["tekst"] for r in s2["raporty"]] == ["patrol 2", "patrol 1"]
    assert a.lista(rodzaj="jarvo-patrol", przed=101.0, limit=2)["dalej"] is None
    assert a.lista()["raporty"][1]["profil"] == "jarvo-kernel"
    assert a.przeczytane(150.0) == {"nieprzeczytane": 1, "przeczytane_do": 150.0}
    assert a.przeczytane(10.0)["przeczytane_do"] == 150.0           # stara karta nie cofa znacznika
    assert a.przeczytane(9e9)["przeczytane_do"] == 200.0            # nie dalej niż najnowszy raport
    assert a.licznik() == {"nieprzeczytane": 0, "przeczytane_do": 200.0}
    assert [r["nowy"] for r in a.lista()["raporty"]] == [False] * 7


def test_runda_co_30_s_z_nowymi(arch):
    a, dane, zegar = arch
    _zapisz(dane, "jarvo-daily-brief", "b1", _agent("Poranny brief", "jarvo-daily-brief", "Brief"), 500)
    zegar[0] = 2000.0
    r = a.runda()
    assert r["nieprzeczytane"] == 1 and r["nowe"][0]["nazwa"] == "Poranny brief" and "tekst" not in r["nowe"][0]
    _zapisz(dane, "jarvo-daily-brief", "b2", _agent("Poranny brief", "jarvo-daily-brief", "Brief 2"), 600)
    zegar[0] = 2010.0
    assert a.runda() is None                         # przed upływem 30 s nic nie czyta
    zegar[0] = 2031.0
    assert a.runda()["nieprzeczytane"] == 2
    zegar[0] = 2070.0
    assert a.runda() is None                         # nic nowego: brak zdarzenia


class Hub:
    def __init__(self):
        self.zdarzenia = []

    def nadaj(self, typ, dane, **_kw):
        self.zdarzenia.append((typ, dane))


def test_trasy(arch):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    a, dane, _ = arch
    _zapisz(dane, "jarvo-daily-brief", "b1", _agent("Poranny brief", "jarvo-daily-brief", "Brief"), 500)
    _zapisz(dane, "jarvo-patrol", "p1", _agent("Patrol floty", "jarvo-patrol", "Patrol"), 400)
    a.zbierz()
    hub, router = Hub(), fastapi.APIRouter()
    R.dolacz(router, archiwum=a, hub=hub)
    app = fastapi.FastAPI()
    app.include_router(router)
    c = TestClient(app)
    d = c.get("/raporty").json()
    assert [r["nazwa"] for r in d["raporty"]] == ["Poranny brief", "Patrol floty"] and d["nieprzeczytane"] == 2
    assert [r["nazwa"] for r in c.get("/raporty", params={"rodzaj": "jarvo-patrol"}).json()["raporty"]] == ["Patrol floty"]
    assert c.get("/raporty", params={"rodzaj": "../x"}).json()["blad"]["kod"] == "zle_dane"
    assert c.get("/raporty", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    r = c.post("/raporty/przeczytane", content=json.dumps({"do": 500}))
    assert r.json() == {"nieprzeczytane": 0, "przeczytane_do": 500.0}
    assert hub.zdarzenia == [("raporty.licznik", {"nieprzeczytane": 0, "przeczytane_do": 500.0})]
    assert c.post("/raporty/przeczytane", content="[]").status_code == 422
    assert c.post("/raporty/przeczytane", content=json.dumps({"do": "jutro"})).status_code == 422

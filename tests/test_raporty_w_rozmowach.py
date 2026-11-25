"""Raport rutyny rozmówcy floty w jego wątku (hq/plugin/rozmowcy.py `raporty`, scalanie `_wpisy`): 25.11 poranny raport
Bigshota (skrypt `no_agent`, `attach_to_session`, temat 623) był tylko w Aktualizacjach. Temat bez trasy bramy (nikt
w nim jeszcze nie pisał) nie ma sesji, więc lustro Hermesa `[Cron delivery: …]` przepada; wtedy raport idzie do wątku
rozmówcy jako pozycja `rutyna` raz, cisza nigdy, temat z trasą zostaje lustru (bez dubla), koordynator bez zmian.
Prawdziwe rozmowy.db, archiwum raportów i tematy; brama i przeglądarka to atrapy."""
import json
import os

import pytest

from conftest import load_script

rz = load_script("hq/plugin/rozmowy.py", "jarvo_test_rwr_rozmowy")
rp = load_script("hq/plugin/raporty.py", "jarvo_test_rwr_raporty")
tm = load_script("hq/plugin/tematy.py", "jarvo_test_rwr_tematy")
ag = load_script("hq/plugin/agenci.py", "jarvo_test_rwr_agenci")
rc = load_script("hq/plugin/rozmowcy.py", "jarvo_test_rwr_rozmowcy")
sc = load_script("hq/plugin/scalanie.py", "jarvo_test_rwr_scalanie")

CZAT = "-1004309644955"
FLOTA = [{"name": "jarvo", "nazwa": "Jarvo", "temat_tg": "general"},
         {"name": "jarvo-hacker", "nazwa": "Hacker", "temat_tg": "hacker"},
         {"name": "jarvo-bigshort", "nazwa": "Bigshort", "temat_tg": "bigshort"}]


class Agenci:
    def rozmowcy(self, wpisy=None):
        return ag.rozmowcy_floty([dict(a) for a in FLOTA])


class Hub:
    def __init__(self):
        self.zdarzenia, self.otwarte = [], set()

    def nadaj(self, typ, dane, watek_id=None):
        self.zdarzenia.append((typ, dane))

    def subskrybowane_watki(self):
        return self.otwarte


class Czytnik:                                     # wątki rozmówców bez członków: oś to same wpisy
    def linia(self, agent, sesje):
        raise AssertionError("brak członków, brak sesji do czytania")


def _zapisz(dane, profil, zadanie, stem, tresc, ts):
    p = dane / "profiles" / profil / "cron" / "output" / zadanie / f"{stem}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(tresc, encoding="utf-8")
    os.utime(p, (ts, ts))
    return p


def _skrypt(nazwa, wyjscie):
    return (f"# Cron Job: {nazwa}\n\n**Job ID:** x\n**Run Time:** 2026-11-25 08:35:30\n"
            f"**Mode:** no_agent (script)\n\n---\n\n{wyjscie}\n")


@pytest.fixture
def swiat(tmp_path):
    dane = tmp_path / "dane"
    grupy = dane / "jarvo" / "state" / "telegram-grupy.json"
    grupy.parent.mkdir(parents=True)
    grupy.write_text(json.dumps({"grupy": {CZAT: {"od": "2026-11-20", "watki": {
        "623": {"nazwa": "BIGSHORT"}, "624": {"nazwa": "HACKER"}}}}}), encoding="utf-8")
    # Hacker ma już trasę bramy w temacie 624 (właściciel tam pisał): lustro Hermesa ląduje w jego sesji
    lustro = dane / "profiles" / "jarvo-hacker" / "sessions" / "sessions.json"
    lustro.parent.mkdir(parents=True)
    lustro.write_text(json.dumps({f"agent:jarvo-hacker:telegram:group:{CZAT}:624": {"session_id": "s_hacker"}}),
                      encoding="utf-8")
    zegar = [1_764_000_000.0]
    db = rz.Rozmowy(tmp_path / "state" / "rozmowy.db", zegar=lambda: zegar[0])
    db.migruj()
    hub = Hub()
    s = rc.Serwis(db=db, agenci=Agenci(), hub=hub, dane=dane, tematy=tm, zegar=lambda: zegar[0])
    s.synchronizuj()
    arch = rp.Archiwum(dane, tmp_path / "state" / "raporty.db", zegar=lambda: zegar[0])
    yield {"dane": dane, "db": db, "hub": hub, "s": s, "arch": arch, "zegar": zegar}
    db.zamknij()


def _watek(db, klucz):
    return db.rozmowca(klucz)["watek_id"]


def test_raport_rutyny_bez_sesji_tematu_raz_w_watku_rozmowcy(swiat):
    dane, db, hub, s, arch, zegar = (swiat[k] for k in ("dane", "db", "hub", "s", "arch", "zegar"))
    ts = zegar[0] - 60
    _zapisz(dane, "jarvo-bigshort", "bigshort-terminy", "2026-11-25_08-35-30",
            _skrypt("Terminy", "📅 Terminy na dziś\n1. VAT do 25.11"), ts)
    _zapisz(dane, "jarvo-bigshort", "bigshort-terminy", "2026-11-24_08-35-30", _skrypt("Terminy", "[SILENT]"), ts - 86400)
    _zapisz(dane, "jarvo-hacker", "hacker-patrol", "2026-11-25_08-00-00", _skrypt("Patrol", "🛡 2 nowe CVE"), ts)
    _zapisz(dane, "jarvo", "jarvo-daily-brief", "2026-11-25_07-50-00", _skrypt("Poranny brief", "☀️ Brief"), ts)

    zdarzenie = arch.runda(po_nowych=s.raporty)
    assert len(zdarzenie["nowe"]) == 3                       # Aktualizacje: wszystkie raporty poza ciszą

    big = _watek(db, "f:jarvo-bigshort")
    poz = sc.os_watku(db, Czytnik(), big)["pozycje"]
    assert [(p["rodzaj"], p["agent"], p["rutyna"], p["tekst"]) for p in poz] == [
        ("rutyna", "jarvo-bigshort", {"nazwa": "Terminy"}, "📅 Terminy na dziś\n1. VAT do 25.11")]
    assert poz[0]["ts"] == ts
    w = db.watek(big)
    assert w["nieprzeczytane"] == 1 and w["podglad"].startswith("Bigshort · Terminy: 📅 Terminy na dziś")
    assert ("watek.os", {"watek_id": big, "agent": "jarvo-bigshort"}) in hub.zdarzenia
    assert [d["watek"]["nieprzeczytane"] for t, d in hub.zdarzenia if t == "watek.zmiana"] == [1]
    # agent nie ma raportu w swojej sesji panelu: blok kontekstu niesie go linią systemu z plikiem raportu
    kontekst = sc.pozycje_kontekstu(db, Czytnik(), big)
    assert kontekst[0]["rodzaj"] == "system" and kontekst[0]["tekst"].startswith("raport rutyny „Terminy”: 📅")
    assert kontekst[0]["pliki"][0].endswith("profiles/jarvo-bigshort/cron/output/bigshort-terminy/2026-11-25_08-35-30.md")

    # temat z trasą bramy (lustro Hermesa już na osi) i koordynator: bez wpisu
    for klucz in ("f:jarvo-hacker", "f:jarvo"):
        assert db.wpisy(_watek(db, klucz)) == []

    # raporty z doby po restarcie silnika (te same raporty jeszcze raz): bez dubla i bez nowego sygnału
    przed = len(hub.zdarzenia)
    assert s.raporty(arch.lista(od=ts - 86400)["raporty"]) == 0
    assert len(sc.os_watku(db, Czytnik(), big)["pozycje"]) == 1 and len(hub.zdarzenia) == przed


def test_raport_w_otwartym_watku_bez_nieprzeczytanych_i_po_ostatnim_wpisie(swiat):
    dane, db, hub, s, arch, zegar = (swiat[k] for k in ("dane", "db", "hub", "s", "arch", "zegar"))
    big = _watek(db, "f:jarvo-bigshort")
    db.dodaj_wpis(big, rodzaj="wlasciciel", tekst="co nowego?", at=zegar[0])
    hub.otwarte.add(big)
    _zapisz(dane, "jarvo-bigshort", "bigshort-terminy", "a", _skrypt("Terminy", "1. ZUS"), zegar[0] - 30)
    assert s.raporty(arch.zbierz()) == 1
    poz = sc.os_watku(db, Czytnik(), big)["pozycje"]
    assert [p["rodzaj"] for p in poz] == ["wlasciciel", "rutyna"]     # czas rośnie z kolejnością wpisów
    assert db.watek(big)["nieprzeczytane"] == 0

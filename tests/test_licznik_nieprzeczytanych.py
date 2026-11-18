"""Licznik nieprzeczytanych rozmówcy (uwaga właściciela 18.11: „nagle czerwona kropka z numerkiem 20, a przyszła jedna
wiadomość”): tura z wieloma krokami narzędzi to jedna wiadomość. omp: czytnik_omp.odpowiedzi i rozmowcy._os_omp;
Hermes: czytnik.wiadomosci_po i obserwator._wiadomosci (całość na silniku: tests/test_obserwator.py)."""
from __future__ import annotations

import json
import sqlite3
import time
from types import SimpleNamespace

import pytest

import atrapa_bramy
from conftest import load_script

cz_omp = load_script("hq/plugin/czytnik_omp.py", "jarvo_test_licznik_czytnik_omp")
czytnik = load_script("hq/plugin/czytnik.py", "jarvo_test_licznik_czytnik")
rozmowcy = load_script("hq/plugin/rozmowcy.py", "jarvo_test_licznik_rozmowcy")
obserwator = load_script("hq/plugin/obserwator.py", "jarvo_test_licznik_obserwator")
scalanie = load_script("hq/plugin/scalanie.py", "jarvo_test_licznik_scalanie")
budzenia = load_script("hq/plugin/budzenia.py", "jarvo_test_licznik_budzenia")

KROKI = 20


@pytest.fixture(autouse=True)
def _czysto():
    cz_omp.zapomnij()


# ----------------------------------------------------------------------------------------------- omp

def msg(i, rodzic, rola, tresc):
    return {"type": "message", "id": i, "parentId": rodzic, "timestamp": f"t{i}", "message": {"role": rola, "content": tresc}}


def dopisz(plik, *wpisy):
    with plik.open("a", encoding="utf-8") as f:
        for w in wpisy:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")


def tura(plik, rodzic, prosba, odp, *, co_krok=lambda: None):
    """Tura omp jak w pliku sesji: prośba, KROKI wywołań narzędzi (każde z wynikiem, część z tekstem przy wywołaniu),
    odpowiedź. `co_krok` woła się po każdym dopisanym wpisie (runda pętli rozmówców w trakcie tury)."""
    n = len(plik.read_text(encoding="utf-8").splitlines()) if plik.exists() else 0
    u = f"u{n}"
    dopisz(plik, msg(u, rodzic, "user", [{"type": "text", "text": prosba}]))
    co_krok()
    r = u
    for k in range(KROKI):
        tresc = [{"type": "toolCall", "id": f"c{n}_{k}", "name": "bash", "intent": f"Krok {k}", "arguments": {}}]
        if k % 5 == 0:                                       # komentarz przy narzędziu (stopReason toolUse)
            tresc.insert(0, {"type": "text", "text": f"Sprawdzam {k}…"})
        dopisz(plik, msg(f"a{n}_{k}", r, "assistant", tresc))
        co_krok()
        dopisz(plik, msg(f"r{n}_{k}", f"a{n}_{k}", "toolResult", [{"type": "text", "text": "wynik"}]))
        co_krok()
        r = f"r{n}_{k}"
    dopisz(plik, msg(f"f{n}", r, "assistant", [{"type": "text", "text": odp}]))
    co_krok()
    return f"f{n}"


def plik_sesji(tmp_path):
    p = tmp_path / "2026_s1.jsonl"
    dopisz(p, {"type": "session", "version": 3, "id": "s1", "timestamp": "t", "cwd": "/tmp"})
    return p


TG = "[Telegram · op · 2026-11-18 · wiadomość 1/1]\nsprawdź dysk"
PANEL = "[Panel · op · 2026-11-18 · #p_abc · wiadomość 1/1]\nsprawdź dysk"


def test_odpowiedzi_omp_tura_z_krokami_to_jedna(tmp_path):
    p = plik_sesji(tmp_path)
    lisc = tura(p, None, TG, "Dysk w porządku.")
    assert cz_omp.odpowiedzi(p) == 1
    lisc = tura(p, lisc, PANEL, "Gotowe.")                 # tura z panelu: liczy ją koniec przebiegu, nie plik
    assert cz_omp.odpowiedzi(p) == 1
    tura(p, lisc, "z terminala", "Zrobione.")
    assert cz_omp.odpowiedzi(p) == 2
    assert cz_omp.odpowiedzi(tmp_path / "brak.jsonl") is None


class Hub:
    def __init__(self, otwarte=()):
        self.zdarzenia, self.otwarte = [], set(otwarte)

    def nadaj(self, typ, dane, watek_id=None):
        self.zdarzenia.append((typ, dane))

    def subskrybowane_watki(self):
        return self.otwarte


class Db:
    def __init__(self):
        self.nieprzeczytane = 0

    def aktywnosc(self, wid, *, at, nieprzeczytane_plus=0, **_):
        self.nieprzeczytane += nieprzeczytane_plus
        return {"id": wid, "aktywnosc_at": at, "nieprzeczytane": self.nieprzeczytane}


def test_os_omp_tura_z_dwudziestoma_krokami_daje_jedna_nieprzeczytana(tmp_path):
    p = plik_sesji(tmp_path)
    hub, db = Hub(), Db()
    s = rozmowcy.Serwis(db=db, agenci=None, hub=hub, dane=tmp_path, tematy=None,
                        omp=SimpleNamespace(plik_sesji=lambda w: p), czytnik_omp=cz_omp)
    r = {"klucz": "s:op", "watek_id": "w1"}
    s._os_omp(r, None)                                      # pierwszy odczyt: tylko stan
    runda = lambda: s._os_omp(r, None)                      # noqa: E731  runda pętli po każdym wpisie
    lisc = tura(p, None, TG, "Dysk w porządku.", co_krok=runda)
    assert db.nieprzeczytane == 1
    assert sum(t == "watek.os" for t, _ in hub.zdarzenia) > KROKI          # oś na żywo dalej po każdym kroku
    assert [d["watek"]["nieprzeczytane"] for t, d in hub.zdarzenia if t == "watek.zmiana"] == [1]
    tura(p, lisc, PANEL, "Gotowe.", co_krok=runda)
    assert db.nieprzeczytane == 1                            # z panelu: koniec przebiegu, nie plik


def test_os_omp_nowy_plik_sesji_nie_liczy_calej_historii(tmp_path):
    p = plik_sesji(tmp_path)
    tura(p, None, TG, "stara")
    db, cel = Db(), {"p": tmp_path / "brak.jsonl"}
    s = rozmowcy.Serwis(db=db, agenci=None, hub=Hub(), dane=tmp_path, tematy=None,
                        omp=SimpleNamespace(plik_sesji=lambda w: cel["p"]), czytnik_omp=cz_omp)
    r = {"klucz": "s:op", "watek_id": "w1"}
    s._os_omp(r, None)
    cel["p"] = p
    s._os_omp(r, None)
    assert db.nieprzeczytane == 0


# ----------------------------------------------------------------------------------------------- Hermes

def test_wiadomosci_po_hermes_bez_krokow(tmp_path):
    db = atrapa_bramy.baza_profilu(tmp_path / "state.db")
    c = sqlite3.connect(db)
    c.execute("INSERT INTO sessions (id, source, started_at) VALUES ('s', 'telegram', ?)", (time.time(),))

    def w(rola, tresc, **pola):
        dane = {"session_id": "s", "role": rola, "content": tresc, "timestamp": time.time(), **pola}
        return c.execute(f"INSERT INTO messages ({', '.join(dane)}) VALUES ({', '.join('?' * len(dane))})",
                         tuple(dane.values())).lastrowid

    przed = w("assistant", "stara odpowiedź", display_order=1)
    w("user", "z telefonu: sprawdź build", display_order=2)
    for k in range(KROKI):
        tc = json.dumps([{"id": f"c{k}", "type": "function", "function": {"name": "terminal", "arguments": "{}"}}])
        w("assistant", "Sprawdzam…" if k % 5 == 0 else "", tool_calls=tc, display_order=3 + 2 * k)
        w("tool", "wynik", tool_call_id=f"c{k}", display_order=4 + 2 * k)
    w("assistant", "Automatyczna kontynuacja", display_kind="auto_continue")
    w("assistant", "stara odpowiedź (podmiana)", display_order=1)          # ta sama pozycja co przed `po_id`
    w("assistant", "Build zielony.", display_order=100)
    c.commit()
    c.close()
    assert czytnik.wiadomosci_po(db, ["s"], przed) == [("user", "z telefonu: sprawdź build"),
                                                        ("assistant", "Build zielony.")]


def test_obserwator_liczy_odpowiedz_i_rutyne_nie_cisze_ani_wlasciciela():
    o = obserwator.Obserwator(db=None, czytnik=None, rejestr=None, hub=None, agenci=None, home="/tmp", jarvo_dir="/tmp",
                              budzenia=budzenia, scalanie=scalanie)
    assert o._wiadomosci([("user", "z telefonu"), ("assistant", "Build zielony.")]) == 1
    assert o._wiadomosci([("user", "[kanban] Task t_1 completed."), ("assistant", "[SILENT]")]) == 0
    assert o._wiadomosci([("user", "[Cron delivery: Patrol floty]\n✅ gotowe")]) == 1
    assert o._wiadomosci([]) == 0

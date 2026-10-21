"""Wątek silnika rozmów (hq/plugin/silnik.py): jeden silnik na proces, trzy restarty po awarii i stan `awaria`
(w dzienniku i /health tylko nazwa typu wyjątku), `wykonaj` odporne na anulowanie wołającego. Plus drobne reguły
rejestru (hq/plugin/przebiegi.py): `message.interim` z `already_streamed` pomijany, `pending_steer` dzielony na
całe dopiski (jedyny podział albo żaden)."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import test_silnik_rozmow as T  # noqa: E402

M, P, czekaj = T.M, T.P, T.czekaj


def _agenci():
    return SimpleNamespace(nazwy=lambda: [], nazwy_wyswietlane=lambda: {})


def test_jeden_silnik_na_proces(monkeypatch):
    pusty = __import__("types").ModuleType(M.silnik.STRAZNIK)       # setitem: po teście wraca poprzedni stan
    pusty.silnik = None
    monkeypatch.setitem(__import__("sys").modules, M.silnik.STRAZNIK, pusty)
    a, b = object(), object()
    assert M.silnik.instancja() is None
    assert M.silnik.zarejestruj(a) is a
    assert M.silnik.zarejestruj(b) is a and M.silnik.instancja() is a


def test_trzy_restarty_potem_awaria(tmp_path, monkeypatch):
    monkeypatch.setattr(M.silnik, "RESTARTY", (0.0, 0.0, 0.0))
    proby = {"n": 0}

    class Zepsute:
        def __init__(self, *_a, **_k):
            proby["n"] += 1
            raise RuntimeError("treść właściciela, której nie wolno logować")

    m = SimpleNamespace(**{**vars(M), "rozmowy": SimpleNamespace(Rozmowy=Zepsute)})
    logi: list[str] = []
    s = M.silnik.Silnik(moduly=m, home=tmp_path, jarvo_dir=tmp_path / "jarvo", api_base="http://brama.test",
                        agenci=_agenci(), hub=M.strumien.Hub(), log=logi.append, obserwator=False)
    s.start(czekaj=10)
    s.watek.join(5)
    assert proby["n"] == 4 and s.stan == "awaria" and not s.dziala()
    assert s.zdrowie()["silnik"] == "awaria" and s.zdrowie()["silnik_blad"] == "RuntimeError"
    assert sum("silnik padł" in x for x in logi) == 4 and sum("/3" in x for x in logi) == 3
    assert any("po 3 restartach" in x for x in logi)
    assert not any("właściciela" in x for x in logi)
    koro = asyncio.sleep(0)
    with pytest.raises(M.silnik.SilnikNiedostepny):
        s.wykonaj(koro)


@pytest.mark.parametrize("env,oczekiwany", [("3", 3), (" 4 ", 4), ("0", 1), ("99", 32), ("abc", None),
                                            ("-2", None), ("", None), ("²", None), ("٣", None)])
def test_limit_ze_srodowiska(tmp_path, monkeypatch, env, oczekiwany):
    monkeypatch.setenv("JARVO_HQ_MAX_PRZEBIEGOW", env)
    s = M.silnik.Silnik(moduly=M, home=tmp_path, jarvo_dir=tmp_path / "jarvo", api_base="http://brama.test",
                        agenci=_agenci(), hub=M.strumien.Hub(), obserwator=False)
    assert s.limit == (oczekiwany or M.przebiegi.LIMIT)


@pytest.fixture
def swiat(tmp_path):
    s = T.Swiat(tmp_path)
    yield s
    s.zamknij()


def test_anulowanie_wolajacego_nie_przerywa_operacji_silnika(swiat):
    zrobione = []

    async def operacja():
        await asyncio.sleep(0.3)
        zrobione.append(True)
        return 1

    async def wolajacy():
        zad = asyncio.ensure_future(swiat.sil.wykonaj(operacja()))
        await asyncio.sleep(0.05)
        zad.cancel()                                   # klient się rozłączył
        with pytest.raises(asyncio.CancelledError):
            await zad

    asyncio.run(wolajacy())
    czekaj(lambda: zrobione, 3, "operacja silnika dokończona")


def test_interim_juz_wyslany_pomijany(swiat):
    pid = swiat.nowy("@teste2ea [wolno:3] strona")["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    rej = swiat.sil.rejestr

    async def zdarzenia():
        rej._zdarzenie(pid, {"event": "message.interim", "text": "to już było w deltach", "already_streamed": True,
                             "timestamp": time.time()})
        rej._zdarzenie(pid, {"event": "message.interim", "text": "Sprawdzam pliki…", "timestamp": time.time()})

    asyncio.run_coroutine_threadsafe(zdarzenia(), swiat.sil.loop).result(5)
    komentarze = [d["tekst"] for _t, d in swiat.ramki("przebieg.komentarz") if d.get("id") == pid]
    assert komentarze == ["Sprawdzam pliki…"]


def test_linie_pending_steer_calymi_dopiskami():
    podzial, linie = M.przebiegi.Rejestr._podzial, M.przebiegi.Rejestr._linie
    assert linie("  ok \n") == ["ok"] and linie("") == [] and linie(None) == []
    # „ok” wrócił, „dodaj NIP” (dwa razy) też: jedyny podział
    assert podzial(["dodaj NIP", "ok", "dodaj NIP"], [["dodaj NIP"], ["ok"], ["dodaj NIP"]]) == {0, 1, 2}
    # fragment linii nie jest dopiskiem: „ok” i „usuń” nie wróciły jako całe teksty
    assert podzial(["ok, usuń repo"], [["ok"], ["usuń"]]) is None
    # dopisek wieloliniowy wraca całością albo wcale
    assert podzial(["a", "b", "c"], [["a"], ["b", "c"]]) == {0, 1}
    assert podzial(["a", "b"], [["a"], ["b", "c"]]) is None
    # dwa takie same teksty, wrócił jeden: nie wiadomo który
    assert podzial(["x"], [["x"], ["x"]]) is None
    assert podzial([], [["a"], []]) == set()


def test_zamkniecie_konczy_porzadki_obserwatora(swiat):
    """Porządki obserwatora (przypinanie, sprzątanie) w toku przy zamknięciu silnika: anulowane i dokończone przed
    zamknięciem pętli (bez „Task was destroyed but it is pending” i bez zapisu w trakcie zamykania)."""
    obs = swiat.sil.obserwator

    async def wiszace():
        obs._porzadki = asyncio.get_running_loop().create_task(asyncio.sleep(60))
        return obs._porzadki

    zadanie = asyncio.run_coroutine_threadsafe(wiszace(), swiat.sil.loop).result(5)
    swiat.sil.zamknij()
    assert zadanie.cancelled()

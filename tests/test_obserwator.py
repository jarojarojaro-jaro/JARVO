"""Obserwator plików silnika (hq/plugin/obserwator.py) na atrapie bramy: rodowód po kompresji z rotacją (sesja
potomna = nowy `sesja_tip` i notka), ponowne przypięcie sesji z `przypieta = 0`, dobowe sprzątanie odpina sesje
wątków usuniętych na stałe, nowy wiersz spoza aplikacji = podpowiedź osi i nieprzeczytane."""
from __future__ import annotations

import asyncio
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import test_silnik_rozmow as T  # noqa: E402

P, czekaj = T.P, T.czekaj


@pytest.fixture
def swiat(tmp_path):
    s = T.Swiat(tmp_path)
    yield s
    s.zamknij()


def na_silniku(swiat, fn):
    async def _f():
        return fn()
    return asyncio.run_coroutine_threadsafe(_f(), swiat.sil.loop).result(10)


def _gotowy_watek(swiat, tekst="@teste2ea pierwsza"):
    out = swiat.nowy(tekst)
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "gotowe")
    return wid, swiat.p(pid)["sesja_id"]


def test_rodowod_po_kompresji(swiat):
    wid, sid = _gotowy_watek(swiat)
    dziecko = sid + "_k1"
    swiat.brama._zapisz("test-e2e-a", "UPDATE sessions SET end_reason = 'compression', ended_at = ? WHERE id = ?",
                        (time.time(), sid))
    swiat.brama._zapisz("test-e2e-a", "INSERT INTO sessions (id, source, parent_session_id, started_at) "
                        "VALUES (?, 'api_server', ?, ?)", (dziecko, sid, time.time()))
    czekaj(lambda: (swiat.sil.db.czlonek(wid, "test-e2e-a") or {}).get("sesja_tip") == dziecko, 10, "sesja_tip")
    rodowod = [s["sesja_id"] for s in swiat.sil.db.sesje_watku(wid, agent="test-e2e-a")]
    assert rodowod == [sid, dziecko]
    wpisy = swiat.sil.db.wpisy(wid)
    assert any((w.get("dane") or {}).get("typ") == "kompresja" for w in wpisy)
    # następna wiadomość idzie już do sesji potomnej
    q = swiat.wyslij(wid, "@teste2ea dalej").json()["przebiegi"][0]["id"]
    assert swiat.do_stanu(q, "gotowe")["sesja_id"] == dziecko


def test_ponowne_przypiecie_sesji(swiat):
    wid, sid = _gotowy_watek(swiat)
    assert swiat.brama.sesja("test-e2e-a", sid)["pinned"] == 1
    swiat.brama._zapisz("test-e2e-a", "UPDATE sessions SET pinned = 0 WHERE id = ?", (sid,))
    na_silniku(swiat, lambda: swiat.sil.db.ustaw_przypieta("test-e2e-a", sid, False))
    obs = swiat.sil.obserwator
    na_silniku(swiat, lambda: setattr(obs, "_przypinanie_at", 0.0))
    czekaj(lambda: swiat.brama.sesja("test-e2e-a", sid)["pinned"] == 1, 10, "ponownie przypięta w Hermesie")
    czekaj(lambda: not swiat.sil.db.sesje_czlonkow(nieprzypiete=True), 5, "przypieta = 1 w rozmowy.db")


def test_sprzatanie_odpina_sesje_usunietych_watkow(swiat):
    wid, sid = _gotowy_watek(swiat)
    assert swiat.k.delete(f"{P}/rozmowy/{wid}").status_code == 204            # do kosza

    def postarz():
        with swiat.sil.db._tx() as c:
            c.execute("UPDATE watki SET usuniety_at = ? WHERE id = ?", (time.time() - 31 * 86400, wid))
        swiat.sil.db.ustaw_meta("sprzatanie_at", "0")
        swiat.sil.obserwator._przypinanie_at = 0.0

    na_silniku(swiat, postarz)
    czekaj(lambda: swiat.brama.sesja("test-e2e-a", sid)["pinned"] == 0, 10, "odpięta w Hermesie")
    assert swiat.sil.db.watek(wid) is None
    nagrobki = [s for s in swiat.sil.db.sesje_czlonkow("test-e2e-a") if s["sesja_id"] == sid]
    assert nagrobki and nagrobki[0]["watek_id"] is None and not nagrobki[0]["przypieta"]
    assert swiat.sil.db.usun_nagrobki("test-e2e-a") == 1
    assert not swiat.sil.db.sesje_czlonkow("test-e2e-a")


def test_obcy_wiersz_daje_podpowiedz_i_nieprzeczytane(swiat):
    wid, sid = _gotowy_watek(swiat)
    przed = swiat.sil.db.watek(wid)["nieprzeczytane"]
    swiat.brama._wiersz("test-e2e-a", sid, "user", "pytanie z telegramu")
    czekaj(lambda: any(d["watek_id"] == wid for _t, d in swiat.ramki("watek.os")), 5, "watek.os")
    czekaj(lambda: swiat.sil.db.watek(wid)["nieprzeczytane"] > przed, 5, "nieprzeczytane")

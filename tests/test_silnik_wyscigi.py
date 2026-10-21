"""Wyścigi silnika rozmów (hq/plugin/przebiegi.py, strumien.py, trasy_rozmow.py, obserwator.py) z przeglądu etapu 2:
każdy test odtwarza przeplot, który wcześniej psuł stan, i sprawdza zachowanie po poprawce (docs/HQ.md §2d).
Świat (atrapa bramy, prawdziwy silnik i trasy) z tests/test_silnik_rozmow.py."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

pytest.importorskip("fastapi")

import test_silnik_rozmow as T  # noqa: E402

M, P, czekaj = T.M, T.P, T.czekaj


@pytest.fixture
def swiat(tmp_path):
    s = T.Swiat(tmp_path)
    yield s
    s.zamknij()


def na_silniku(swiat, coro, timeout=20):
    return asyncio.run_coroutine_threadsafe(coro, swiat.sil.loop).result(timeout)


liczone, po_cyklach = T._liczone, T._po_cyklach


def stoi(swiat, pid, stan, powod=None, czas=1.5):
    """Przebieg trwa w (stan, powod) przez `czas` sekund."""
    koniec = time.monotonic() + czas
    while time.monotonic() < koniec:
        p = swiat.p(pid)
        assert p["stan"] == stan and (powod is None or p.get("powod") == powod), (p["stan"], p.get("powod"))
        time.sleep(0.1)
    return swiat.p(pid)


def _dzierzawa_b(swiat):
    """Wątek z członkiem b, którego sesję trzyma obca tura: jego przebieg czeka w kolejka(tura), więc każda runda
    dyspozytora sprawdza dzierżawę (await w trakcie rundy)."""
    u = swiat.nowy("@teste2eb pierwsza")
    uid, ub = u["watek"]["id"], u["przebiegi"][0]["id"]
    swiat.do_stanu(ub, "gotowe")
    swiat.brama.dzierzawa("test-e2e-b", swiat.p(ub)["sesja_id"], sekund=120)
    r = swiat.wyslij(uid, "@teste2eb druga").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(r)["powod"] == "tura", opis="r kolejka(tura)")
    return r


# ----------------------------------------------------------------------------------------------- dopisz

def test_dopisz_gdy_tura_konczy_sie_w_trakcie_steera(swiat):
    """Tura celu kończy się, zanim steer wróci z bramy: `dopisany` rozstrzyga się sam (tu: tekst wszedł do tury)."""
    out = swiat.nowy("@teste2ea [wolno:0.6] strona")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    brama = swiat.sil.brama
    oryginal = brama.dopisz

    async def dopisz_wolno(agent, run_id, tekst):
        odp = await oryginal(agent, run_id, tekst)
        for _ in range(100):
            if swiat.sil.db.przebieg(pid)["stan"] == "gotowe":
                break
            await asyncio.sleep(0.05)
        return odp

    brama.dopisz = dopisz_wolno
    r = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"})
    assert r.status_code == 200, r.text
    q = r.json()["przebieg"]["id"]
    assert swiat.do_stanu(q, "wlaczony")["dopisany_do"] == pid
    assert any(d["id"] == q for _t, d in swiat.ramki("przebieg.koniec"))
    w = swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]
    assert w["status"] != "pracuje" and not w["przebiegi_aktywne"]


def test_dopisz_ten_sam_klucz_jeden_steer(swiat):
    out = swiat.nowy("@teste2ea [wolno:3] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    r1 = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP", "klucz": "kkk1"})
    r2 = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP", "klucz": "kkk1"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["przebieg"]["id"] == r2.json()["przebieg"]["id"]
    steery = [z for z in swiat.brama.dziennik if z["sciezka"].endswith("/steer")]
    dopisane = [p for p in swiat.sil.db.przebiegi_watku(out["watek"]["id"]) if p.get("dopisany_do") == pid]
    assert len(steery) == 1 and len(dopisane) == 1


def test_stop_po_dopisku_nie_wysyla_go_sam(swiat):
    """Steer jeszcze nie wszedł do tury (wraca w `pending_steer`), a właściciel nacisnął Stop: dopisek czeka
    w kolejka(wstrzymane), nie rusza sam."""
    out = swiat.nowy("@teste2ea [wolno:4] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    swiat.brama.przebiegi[swiat.p(pid)["run_id"]].koncowka = True
    q = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"}).json()["przebieg"]["id"]
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    swiat.do_stanu(pid, "zatrzymane")
    swiat.do_stanu(q, "kolejka")
    stoi(swiat, q, "kolejka", "wstrzymane", czas=2.0)


def test_dopisek_jako_wiersz_steer_nie_jest_obca_wiadomoscia(swiat):
    """Hermes zapisuje steer jako wiersz `steer` owinięty znacznikiem: obserwator nie liczy go jako nieprzeczytanej
    wiadomości spoza aplikacji."""
    out = swiat.nowy("@teste2ea [wolno:2] strona")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    cykle = liczone(swiat.sil.obserwator, "cykl")
    q = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"}).json()["przebieg"]["id"]
    swiat.do_stanu(q, "wlaczony")
    swiat.do_stanu(pid, "gotowe")
    assert any(r.get("display_kind") == "steer" or "OUT-OF-BAND" in str(r.get("content"))
               for r in swiat.brama.wiersze("test-e2e-a")), "wiersz steer w state.db"
    po_cyklach(cykle, 2, "dwa pełne cykle obserwatora po wierszu steer")
    w = swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]
    assert "spoza aplikacji" not in (w.get("podglad") or "")


# ----------------------------------------------------------------------------------------------- stop

def test_stop_wstrzymane_nie_nadpisane_przez_runde(swiat):
    """Stop w trakcie rundy dyspozytora (runda czeka na sondę dzierżawy): wstrzymany przebieg zostaje wstrzymany."""
    rej = swiat.sil.rejestr
    oryg_runda = rej._runda

    async def nic():
        return None

    _dzierzawa_b(swiat)
    t = swiat.nowy("@teste2ea [wolno:6] długie")
    p0 = t["przebiegi"][0]["id"]
    swiat.do_stanu(p0, "pracuje")
    rej._runda = nic
    time.sleep(2.5)
    q = swiat.wyslij(t["watek"]["id"], "@teste2ea następne").json()["przebiegi"][0]["id"]
    wszedl, pusc = threading.Event(), threading.Event()
    oryg_dz = swiat.sil.czytnik.dzierzawa

    def dz(profil, sesje, teraz):
        if profil == "test-e2e-b":
            wszedl.set()
            pusc.wait(5)
        return oryg_dz(profil, sesje, teraz)

    swiat.sil.czytnik.dzierzawa = dz
    fut = asyncio.run_coroutine_threadsafe(oryg_runda(), swiat.sil.loop)
    try:
        assert wszedl.wait(5)
        assert swiat.k.post(f"{P}/przebiegi/{p0}/stop").status_code == 202
        assert swiat.p(q)["powod"] == "wstrzymane"
    finally:
        pusc.set()
        fut.result(10)
        swiat.sil.czytnik.dzierzawa = oryg_dz
        rej._runda = oryg_runda
    assert (swiat.p(q)["stan"], swiat.p(q)["powod"]) == ("kolejka", "wstrzymane")
    swiat.do_stanu(p0, "zatrzymane")
    stoi(swiat, q, "kolejka", "wstrzymane", czas=2.0)


def test_stop_w_wysylaniu_i_429_nie_wysyla(swiat):
    brama = swiat.sil.brama
    oryginal = brama.start
    stan = {"n": 0}
    wszedl, pusc = threading.Event(), threading.Event()

    async def start(agent, **kw):
        stan["n"] += 1
        if stan["n"] == 1:
            wszedl.set()
            while not pusc.is_set():
                await asyncio.sleep(0.02)
            raise M.brama.BladBramy("limit", "busy", status=429, ponow_za=0.3, typ="rate_limit_exceeded")
        return await oryginal(agent, **kw)

    brama.start = start
    pid = swiat.nowy("@teste2ea [wolno:2] nie wysyłaj tego")["przebiegi"][0]["id"]
    assert wszedl.wait(5)
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    pusc.set()
    assert swiat.do_stanu(pid, "zatrzymane", "gotowe", "przerwane", "blad", czas=15)["stan"] == "zatrzymane"
    time.sleep(1.0)
    assert stan["n"] == 1 and not swiat.brama.runs("test-e2e-a")


def test_stop_w_wysylaniu_brama_niedostepna_po_dotarciu(swiat):
    """POST mógł dotrzeć (przerwane czytanie odpowiedzi): jedna powtórka z tym samym kluczem znajduje przebieg
    w bramie, a silnik go zatrzymuje."""
    brama = swiat.sil.brama
    oryginal = brama.start
    wszedl, pusc = threading.Event(), threading.Event()
    stan = {"n": 0}

    async def start(agent, **kw):
        stan["n"] += 1
        odp = await oryginal(agent, **kw)
        if stan["n"] == 1:
            wszedl.set()
            while not pusc.is_set():
                await asyncio.sleep(0.02)
            raise M.brama.BladBramy("niedostepna", "read timeout", dotarlo=True)
        return odp

    brama.start = start
    pid = swiat.nowy("@teste2ea [wolno:5] dotarło")["przebiegi"][0]["id"]
    assert wszedl.wait(5)
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    pusc.set()
    assert swiat.do_stanu(pid, "zatrzymane", "gotowe", "blad", czas=15)["stan"] == "zatrzymane"
    runs = list(swiat.brama.przebiegi.values())
    assert len(runs) == 1 and stan["n"] == 2                        # powtórka trafiła w ten sam przebieg
    czekaj(lambda: runs[0].status != "running", 10, "przebieg bramy zatrzymany")


def test_usun_trwale_w_wysylaniu_zatrzymuje_przebieg_bramy(swiat):
    brama = swiat.sil.brama
    oryginal = brama.start
    wszedl, pusc = threading.Event(), threading.Event()

    async def start(agent, **kw):
        wszedl.set()
        while not pusc.is_set():
            await asyncio.sleep(0.02)
        return await oryginal(agent, **kw)

    brama.start = start
    wid = swiat.nowy("@teste2ea [wolno:3] usuń mnie")["watek"]["id"]
    assert wszedl.wait(5)
    r = swiat.k.delete(f"{P}/rozmowy/{wid}", params={"trwale": 1, "praca": "zatrzymaj"})
    assert r.status_code == 204
    pusc.set()
    czekaj(lambda: swiat.brama.przebiegi and all(x.stop.is_set() or x.status != "running"
                                                 for x in swiat.brama.przebiegi.values()), 10, "stop sieroty")


def test_stop_ponawiany_po_bledzie_bramy(swiat, monkeypatch):
    monkeypatch.setattr(M.przebiegi, "STOP_PONOW_S", 0.3)
    pid = swiat.nowy("@teste2ea [wolno:8] długo")["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    brama = swiat.sil.brama
    oryginal = brama.stop
    proby = {"n": 0}

    async def stop(agent, run_id):
        proby["n"] += 1
        if proby["n"] == 1:
            raise M.brama.BladBramy("niedostepna", "connect")
        return await oryginal(agent, run_id)

    brama.stop = stop
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    assert swiat.do_stanu(pid, "zatrzymane", czas=10)["stan"] == "zatrzymane"
    assert proby["n"] >= 2


# ----------------------------------------------------------------------------------------------- Ponów, archiwum

def test_ponow_dwa_razy_jeden_nowy_przebieg(swiat):
    out = swiat.nowy("@teste2ea [czekaj] zadanie Y")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "przyjety")
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    swiat.do_stanu(pid, "zatrzymane")
    a = swiat.k.post(f"{P}/przebiegi/{pid}/ponow")
    b = swiat.k.post(f"{P}/przebiegi/{pid}/ponow")
    assert a.status_code == 202 and b.status_code == 202
    assert a.json()["przebieg"]["id"] == b.json()["przebieg"]["id"]
    assert len([p for p in swiat.sil.db.przebiegi_watku(out["watek"]["id"]) if p.get("ponowienie_z") == pid]) == 1


def test_archiwum_bez_wyboru_nie_rusza_kolejki(swiat):
    out = swiat.nowy("@teste2ea [wolno:3] w toku")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    drugi = swiat.wyslij(wid, "@teste2ea następne").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(drugi)["powod"] == "zajety_agent")
    r = swiat.k.patch(f"{P}/rozmowy/{wid}", json={"archiwum": True})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "praca_trwa"
    assert swiat.p(drugi)["stan"] == "kolejka"
    assert swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]["archiwum"] == 0


def test_anulowanie_kolejki_wysyla_koniec(swiat):
    out = swiat.nowy("@teste2ea [wolno:3] w toku")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    drugi = swiat.wyslij(wid, "@teste2ea następne").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(drugi)["powod"] == "zajety_agent")
    r = swiat.k.patch(f"{P}/rozmowy/{wid}", json={"archiwum": True, "praca": "zostaw"})
    assert r.status_code == 200, r.text
    assert swiat.p(drugi)["stan"] == "anulowane"
    czekaj(lambda: any(d["id"] == drugi for _t, d in swiat.ramki("przebieg.koniec")), 5, "koniec")


# ----------------------------------------------------------------------------------------------- dyspozytor, 429

def test_budzenie_w_trakcie_rundy_nie_ginie(swiat, monkeypatch):
    """Nowa wiadomość w trakcie rundy (runda czeka 0,6 s na sondę dzierżawy) budzi kolejną rundę od razu. Odpytanie
    co 30 s: zgubione budzenie = ~30 s czekania, więc próg 10 s rozróżnia to z zapasem na wolną maszynę."""
    monkeypatch.setattr(M.przebiegi, "ODPYTANIE_S", 30.0)
    _dzierzawa_b(swiat)
    oryg_dz = swiat.sil.czytnik.dzierzawa

    def dz(profil, sesje, teraz):
        if profil == "test-e2e-b":
            time.sleep(0.6)
        return oryg_dz(profil, sesje, teraz)

    swiat.sil.czytnik.dzierzawa = dz
    czasy = []
    for i in range(4):
        time.sleep(0.25 * i)
        t0 = time.monotonic()
        q = swiat.nowy(f"@teste2ea szybko {i}")["przebiegi"][0]["id"]
        czekaj(lambda: swiat.p(q)["stan"] != "kolejka", 40)
        czasy.append(time.monotonic() - t0)
    assert max(czasy) < 10.0, czasy                       # jedna runda + jedna sonda, bez czekania na odpytanie


def test_budzet_429_od_pierwszej_odmowy(swiat):
    """Wiadomość czekała w kolejce dłużej niż budżet 429: pierwsza odmowa bramy to jeszcze nie błąd."""
    out = swiat.nowy("@teste2ea [wolno:1] pierwsza")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    q = swiat.wyslij(wid, "@teste2ea druga").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(q)["powod"] == "zajety_agent")

    async def postarz():
        with swiat.sil.db._tx() as c:
            c.execute("UPDATE przebiegi SET utworzony_at = ? WHERE id = ?", (time.time() - 660, q))

    na_silniku(swiat, postarz())
    swiat.brama.limit_429 = 1
    swiat.do_stanu(pid, "gotowe")
    p = swiat.do_stanu(q, "blad", "gotowe", czas=15)
    assert p["stan"] == "gotowe" and p["proby"] >= 2


def test_limit_domyslny_z_rdzeni():
    ld = M.przebiegi.limit_domyslny
    assert [ld(c) for c in (1, 2, 4, 8, 16, 64)] == [2, 3, 5, 8, 8, 8]
    assert 1 <= M.przebiegi.LIMIT <= 8


# ----------------------------------------------------------------------------------------------- zgody

def test_odpowiedz_na_zgode_nie_kasuje_nowszej_prosby(swiat):
    pid = swiat.nowy("@teste2ea [zgoda] usuń pliki")["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "czeka_na_zgode")
    rid = swiat.p(pid)["zgoda"]["request_id"]
    brama, rej = swiat.sil.brama, swiat.sil.rejestr

    async def zgoda(agent, run_id, wybor, request_id):
        # brama przyjęła odpowiedź A, agent wykonał polecenie i prosi o B, zanim wróciła nasza odpowiedź HTTP
        # (atrapa zostaje przy A, więc nie wyśle już nic, co by B nadpisało)
        rej._prosba_o_zgode(swiat.sil.db.przebieg(pid), {"request_id": "req_drugi", "command": "rm -rf /tmp/b",
                                                          "choices": ["once", "deny"], "timestamp": time.time()})
        return {"ok": True}

    brama.zgoda = zgoda
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "once", "request_id": rid})
    assert r.status_code == 200
    p = swiat.p(pid)
    assert p["stan"] == "czeka_na_zgode" and p["zgoda"]["request_id"] == "req_drugi"


# ----------------------------------------------------------------------------------------------- obserwator

def test_obserwator_patrzy_w_trakcie_przypinania(swiat):
    out = swiat.nowy("@teste2ea pierwsza")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "gotowe")
    sid = swiat.p(pid)["sesja_id"]
    obs, brama = swiat.sil.obserwator, swiat.sil.brama
    wszedl, pusc, _oryginal = blokada(swiat, brama, "zmien_sesje")     # przypinanie wisi, aż test je puści

    async def przygotuj():
        swiat.sil.db.ustaw_przypieta("test-e2e-a", sid, False)
        obs._przypinanie_at = 0

    try:
        na_silniku(swiat, przygotuj())
        assert wszedl.wait(10), "przypinanie się zaczęło"
        przed = len([1 for _t, d in swiat.ramki("watek.os") if d["watek_id"] == wid])
        swiat.brama._wiersz("test-e2e-a", sid, "user", "[kanban] wake row from outside the app")
        # obserwator patrzy dalej, choć przypinanie wciąż czeka (bez `pusc`): oś przychodzi w trakcie
        czekaj(lambda: len([1 for _t, d in swiat.ramki("watek.os") if d["watek_id"] == wid]) > przed, 8,
               "watek.os w trakcie przypinania")
        assert not pusc.is_set() and not obs._porzadki.done()
    finally:
        pusc.set()


# ----------------------------------------------------------------------------------------------- migawki i strumień

def _ramki(pol):
    out = []
    for r in list(pol.kolejka):
        linie = r.decode().splitlines()
        pola = dict(x.split(": ", 1) for x in linie if ": " in x)
        out.append((pola.get("id"), pola.get("event"), pola.get("data")))
    return out


def test_reset_ma_id_wiec_ponowne_polaczenie_nie_zapetla():
    async def go():
        hub = M.strumien.Hub()
        pol = hub.polacz("k_test0001", ["w_x"], "abcdef.40")           # kursor sprzed restartu dashboardu
        r = _ramki(pol)
        assert [e for _i, e, _d in r] == ["hello", "reset"]
        nowy = r[1][0]
        assert nowy and nowy.startswith(hub.epoka + ".")
        hub.rozlacz("k_test0001", pol)
        pol = hub.polacz("k_test0001", ["w_x"], nowy)                  # przeglądarka wysyła id z resetu
        assert [e for _i, e, _d in _ramki(pol)] == ["hello", "kursor"]
        hub.rozlacz("k_test0001", pol)
    asyncio.run(go())


def test_subskrypcje_przezywaja_ponowne_polaczenie():
    async def go():
        hub = M.strumien.Hub()
        pol = hub.polacz("k_test0001", ["w_a"], None)
        assert hub.subskrybuj("k_test0001", watki=["w_a", "w_b"])
        s1 = hub.nadaj("przebieg.delta", {"tekst": "1"}, watek_id="w_b")
        hub.rozlacz("k_test0001", pol)
        hub.nadaj("przebieg.delta", {"tekst": "2"}, watek_id="w_b")             # w przerwie
        pol2 = hub.polacz("k_test0001", ["w_a"], f"{hub.epoka}.{s1}")           # ten sam URL, Last-Event-ID
        hub.nadaj("przebieg.delta", {"tekst": "3"}, watek_id="w_b")             # po połączeniu
        await asyncio.sleep(0.01)
        teksty = [d for _i, e, d in _ramki(pol2) if e == "przebieg.delta"]
        assert len(teksty) == 2 and '"2"' in teksty[0] and '"3"' in teksty[1]
    asyncio.run(go())


def _seq(kursor):
    return int(kursor.rsplit(".", 1)[1])


def test_migawka_przebiegu_bez_oczekujacej_delty(swiat):
    pid = swiat.nowy("@teste2ea [wolno:3] abcdefghijklmnopqrstuvwxyz0123456789")["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    rej = swiat.sil.rejestr

    async def lap():
        for _ in range(400):
            dz = rej._dzienniki.get(pid)
            if dz is not None and dz.oczekuje and dz.tekst:
                return rej.widok(swiat.sil.db.przebieg(pid))
            await asyncio.sleep(0.005)
        return None

    snap = na_silniku(swiat, lap(), 10)
    assert snap is not None
    swiat.do_stanu(pid, "gotowe")
    pozniej = ""
    for s_, _t, _w, r in list(swiat.hub._bufor):
        linie = r.decode().splitlines()
        d = T.json.loads(linie[2].split(": ", 1)[1])
        if linie[1].split(": ", 1)[1] == "przebieg.delta" and d["id"] == pid and s_ > _seq(snap["seq"]):
            pozniej += d["tekst"]
    assert snap["tekst_dotad"] + pozniej == swiat.delty(pid)


def test_migawka_watku_kursor_przed_odczytem(swiat):
    """Przebieg kończy się w trakcie odczytu migawki (po liście aktywnych, przed kartami): `seq` migawki jest sprzed
    odczytu, więc `przebieg.koniec` ma większy seq i klient go nie odrzuci jako „już w migawce”."""
    out = swiat.nowy("@teste2ea [czekaj] krótko")             # tura czeka na zwolnienie: aktywny przy odczycie
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    run_id = czekaj(lambda: swiat.p(pid).get("run_id"), opis="run_id")
    db = swiat.sil.db
    oryg = db.karty_watku

    def wolno(w):
        swiat.brama.zwolnij(run_id)                             # tura kończy się w trakcie odczytu migawki
        czekaj(lambda: (db.przebieg(pid) or {}).get("stan") == "gotowe", 15, "koniec w trakcie odczytu")
        return oryg(w)

    db.karty_watku = wolno
    try:
        snap = swiat.k.get(f"{P}/rozmowy/{wid}").json()
    finally:
        db.karty_watku = oryg
    assert any(p["id"] == pid for p in snap["watek"]["przebiegi_aktywne"])
    koniec = [s for s, _t, _w, r in list(swiat.hub._bufor) if b"przebieg.koniec" in r and pid.encode() in r]
    assert koniec and koniec[0] > _seq(snap["seq"])            # klient nie odrzuci końca jako „już w migawce”


# ----------------------------------------------------------------------------------------------- druga runda przeglądu

def blokada(swiat, cel, nazwa, *, potem=None):
    """Podmienia `cel.nazwa` (metodę bramy) na wersję, która czeka na `pusc` (wątek testu), a potem robi `potem`
    (domyślnie: oryginał). Zwraca (wszedl, pusc, oryginal)."""
    oryginal = getattr(cel, nazwa)
    wszedl, pusc = threading.Event(), threading.Event()

    async def zablokowana(*a, **kw):
        wszedl.set()
        await asyncio.to_thread(pusc.wait, 15)
        if potem is not None:
            return await potem(*a, **kw)
        return await oryginal(*a, **kw)

    setattr(cel, nazwa, zablokowana)
    return wszedl, pusc, oryginal


def odrzuc_steer(*_a, **_kw):
    raise M.brama.BladBramy("nieaktywny", "run_not_accepting_steer", status=409, typ="run_not_accepting_steer")


async def _odrzuc_steer(*a, **kw):
    odrzuc_steer()


def test_podzial_pending_steer():
    pod = M.przebiegi.Rejestr._podzial
    assert pod(["tak", "nie"], [["tak"], ["tak", "nie"]]) == {1}          # dostarczony „tak”, wrócił „tak\nnie”
    assert pod(["a", "b"], [["a"], ["b"]]) == {0, 1}
    assert pod([], [["a"], ["b"]]) == set()
    assert pod(["a", "b"], [["a", "b"], ["a"], ["b"]]) is None               # dwa podziały: nie wiadomo, który
    assert pod(["x"], [["a"]]) is None                                     # obce linie: brak podziału
    assert pod(["ok", "ok"], [["ok"], ["ok"], ["ok"]]) is None


def test_dopisz_pending_dzielony_calymi_dopiskami(swiat):
    """„tak” wszedł do tury, „tak\\nnie” wrócił w pending_steer: wraca drugi dopisek, nie pierwszy."""
    out = swiat.nowy("@teste2ea [wolno:3] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    q1 = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "tak"}).json()["przebieg"]["id"]
    swiat.brama.przebiegi[swiat.p(pid)["run_id"]].koncowka = True
    q2 = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "tak\nnie"}).json()["przebieg"]["id"]
    swiat.do_stanu(pid, "gotowe")
    assert swiat.do_stanu(q1, "wlaczony", "kolejka", "gotowe")["stan"] == "wlaczony"
    assert swiat.do_stanu(q2, "gotowe", "wlaczony", czas=15)["stan"] == "gotowe"     # wysłany jako nowa tura
    wejscia = [z["cialo"]["input"] for z in swiat.brama.runs("test-e2e-a")]
    assert len(wejscia) == 2 and "tak\nnie" in str(wejscia[1])


def test_koniec_bez_statusu_nie_wlacza_dopisku(swiat):
    """Cel kończy się bez statusu bramy (`zgubione`): dopisek, który nie trafił do tury, czeka na właściciela;
    ten, którego wiersz `steer` jest w state.db, jest włączony."""
    out = swiat.nowy("@teste2ea [wolno:6] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    dostarczony = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj REGON"}).json()["przebieg"]["id"]
    swiat.brama.przebiegi[swiat.p(pid)["run_id"]].koncowka = True
    czeka = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"}).json()["przebieg"]["id"]
    rej = swiat.sil.rejestr

    async def zgub():
        rej._koniec(swiat.sil.db.przebieg(pid), "zgubione")

    na_silniku(swiat, zgub())
    assert swiat.do_stanu(dostarczony, "wlaczony", "kolejka")["stan"] == "wlaczony"
    assert swiat.do_stanu(czeka, "kolejka", "wlaczony")["powod"] == "wstrzymane"
    stoi(swiat, czeka, "kolejka", "wstrzymane", czas=1.5)


def test_stop_gubi_niedostarczony_steer(swiat):
    """Hermes przy twardym przerwaniu (backoff po błędzie API) gubi niedostarczony steer i nie oddaje go
    w pending_steer: dopisek nie jest `wlaczony`, czeka w kolejka(wstrzymane)."""
    out = swiat.nowy("@teste2ea [wolno:6] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    run = swiat.brama.przebiegi[swiat.p(pid)["run_id"]]
    run.koncowka = True
    q = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"}).json()["przebieg"]["id"]
    run.oczekujace.clear()                                          # clear_interrupt(hard_cancel=True)
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    swiat.do_stanu(pid, "zatrzymane")
    assert swiat.do_stanu(q, "kolejka", "wlaczony")["powod"] == "wstrzymane"


def test_stop_po_dostarczonym_steerze_wlacza_go(swiat):
    out = swiat.nowy("@teste2ea [wolno:6] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    q = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"}).json()["przebieg"]["id"]
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    swiat.do_stanu(pid, "zatrzymane")
    assert swiat.do_stanu(q, "wlaczony", "kolejka")["stan"] == "wlaczony"     # wiersz `steer` jest w state.db


def test_dopisz_z_kolejki_odrzucony_po_stopie_zostaje_wstrzymany(swiat):
    out = swiat.nowy("@teste2ea [wolno:4] pierwsza")
    wid, p0 = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(p0, "pracuje")
    q = swiat.wyslij(wid, "@teste2ea druga").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(q)["powod"] == "zajety_agent")
    wszedl, pusc, _o = blokada(swiat, swiat.sil.brama, "dopisz", potem=_odrzuc_steer)
    fut = asyncio.run_coroutine_threadsafe(swiat.sil.rejestr.dopisz_kolejke(q), swiat.sil.loop)
    assert wszedl.wait(5)
    assert swiat.k.post(f"{P}/przebiegi/{p0}/stop").status_code == 202
    pusc.set()
    with pytest.raises(M.przebiegi.Blad):
        fut.result(10)
    swiat.do_stanu(p0, "zatrzymane")
    assert (swiat.p(q)["stan"], swiat.p(q)["powod"]) == ("kolejka", "wstrzymane")
    stoi(swiat, q, "kolejka", "wstrzymane", czas=2.5)


def test_archiwum_z_dopiskiem_w_drodze(swiat):
    """Archiwum z „zatrzymaj”, gdy steer wiadomości z kolejki jest w drodze: bez 409, kolejka anulowana, praca
    zatrzymana, wątek w archiwum; dopisek po odmowie bramy czeka wstrzymany."""
    out = swiat.nowy("@teste2ea [wolno:6] w toku")
    wid, a = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(a, "pracuje")
    b = swiat.wyslij(wid, "@teste2ea druga").json()["przebiegi"][0]["id"]
    c = swiat.wyslij(wid, "@teste2ea trzecia").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(c)["powod"] == "zajety_agent")
    wszedl, pusc, _o = blokada(swiat, swiat.sil.brama, "dopisz", potem=_odrzuc_steer)
    fut = asyncio.run_coroutine_threadsafe(swiat.sil.rejestr.dopisz_kolejke(c), swiat.sil.loop)
    assert wszedl.wait(5)
    r = swiat.k.patch(f"{P}/rozmowy/{wid}", json={"archiwum": True, "praca": "zatrzymaj"})
    assert r.status_code == 200, r.text
    assert r.json()["watek"]["archiwum"] == 1 and swiat.p(b)["stan"] == "anulowane"
    pusc.set()
    with pytest.raises(M.przebiegi.Blad):
        fut.result(10)
    swiat.do_stanu(a, "zatrzymane")
    assert (swiat.p(c)["stan"], swiat.p(c)["powod"]) == ("kolejka", "wstrzymane")


def test_stop_w_trakcie_tworzenia_sesji_nie_wysyla(swiat):
    wszedl, pusc, _o = blokada(swiat, swiat.sil.brama, "utworz_sesje")
    out = swiat.nowy("@teste2ea [wolno:2] nie wysyłaj")
    pid = out["przebiegi"][0]["id"]
    assert wszedl.wait(5)
    assert swiat.p(pid)["stan"] == "wysylanie"
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    pusc.set()
    assert swiat.do_stanu(pid, "zatrzymane", "gotowe", "przyjety", "pracuje")["stan"] == "zatrzymane"
    time.sleep(0.5)
    assert not swiat.brama.runs("test-e2e-a")
    assert not [w for w in swiat.brama.wiersze("test-e2e-a") if w["role"] == "user"]


def test_usun_trwale_gdy_stop_nie_doszedl_ponawia_bez_wiersza(swiat, monkeypatch):
    monkeypatch.setattr(M.przebiegi, "STOP_PONOW_S", 0.3)
    out = swiat.nowy("@teste2ea [wolno:10] długo")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    run = swiat.brama.przebiegi[swiat.p(pid)["run_id"]]
    brama = swiat.sil.brama
    oryginal = brama.stop
    proby = {"n": 0}

    async def stop(agent, run_id):
        proby["n"] += 1
        if proby["n"] == 1:
            raise M.brama.BladBramy("niedostepna", "connect")
        return await oryginal(agent, run_id)

    brama.stop = stop
    r = swiat.k.delete(f"{P}/rozmowy/{wid}", params={"trwale": 1, "praca": "zatrzymaj"})
    assert r.status_code == 204 and swiat.p(pid) is None
    czekaj(lambda: run.stop.is_set(), 10, "stop przebiegu bez wiersza")
    czekaj(lambda: pid not in swiat.sil.rejestr._stop_proby, 5, "koniec ponawiania")
    assert proby["n"] >= 2


def test_drugi_stop_wysyla_od_razu_po_wyczerpaniu_prob(swiat, monkeypatch):
    monkeypatch.setattr(M.przebiegi, "STOP_PONOW_S", 0.1)
    monkeypatch.setattr(M.przebiegi, "STOP_PROBY", 2)
    monkeypatch.setattr(M.przebiegi, "STOP_PONOW_WOLNO_S", 600.0)
    pid = swiat.nowy("@teste2ea [wolno:10] długo")["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    brama = swiat.sil.brama
    oryginal = brama.stop
    stan = {"n": 0, "psuj": True}

    async def stop(agent, run_id):
        stan["n"] += 1
        if stan["psuj"]:
            raise M.brama.BladBramy("niedostepna", "connect")
        return await oryginal(agent, run_id)

    brama.stop = stop
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    czekaj(lambda: stan["n"] >= 2, 5, "dwie próby")
    time.sleep(0.5)
    n = stan["n"]
    assert n == 2 and swiat.p(pid)["stan"] == "zatrzymywanie"           # szybkie próby wyczerpane
    stan["psuj"] = False
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202  # właściciel naciska Stop jeszcze raz
    assert swiat.do_stanu(pid, "zatrzymane")["stan"] == "zatrzymane"
    assert stan["n"] == n + 1


def test_ponawianie_stopu_nie_wstrzymuje_kontroli(swiat, monkeypatch):
    monkeypatch.setattr(M.przebiegi, "STOP_PONOW_S", 0.2)
    x = swiat.nowy("@teste2ea [wolno:10] długo")["przebiegi"][0]["id"]
    swiat.do_stanu(x, "pracuje")
    brama = swiat.sil.brama
    proby = {"n": 0}

    async def wolny_stop(agent, run_id):
        proby["n"] += 1
        if proby["n"] > 1:                                        # ponowienia wiszą 10 s (limit czasu httpx)
            await asyncio.sleep(10)
        raise M.brama.BladBramy("niedostepna", "timeout")

    brama.stop = wolny_stop
    r = swiat.k.post(f"{P}/przebiegi/{x}/stop")                       # pierwszy stop: od razu błąd bramy
    assert r.status_code == 202
    czekaj(lambda: proby["n"] >= 2, 10, "ponowienie stopu w drodze")
    y = swiat.nowy("@teste2eb [zgoda] usuń")["przebiegi"][0]["id"]
    swiat.do_stanu(y, "czeka_na_zgode")
    rej = swiat.sil.rejestr

    async def szybko():                                           # wygasa za 0,3 s
        p = swiat.sil.db.przebieg(y)
        rej._zmien(p, zgoda={**p["zgoda"], "wygasa_at": time.time() + 0.3})

    na_silniku(swiat, szybko())
    t0 = time.monotonic()
    czekaj(lambda: (swiat.p(y).get("zgoda") or {}).get("wygasla"), 10, "wygaśnięcie zgody")
    assert time.monotonic() - t0 < 6.0                            # kontrola nie stała na ponawianym stopie (10 s)
    assert x in rej._stop_w_locie                                 # ponowienie wciąż wisi w tle


def test_ponow_po_anulowanym_ponowieniu_tworzy_nowe(swiat):
    out = swiat.nowy("@teste2ea [czekaj] zadanie")
    wid, a = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(a, "przyjety")
    assert swiat.k.post(f"{P}/przebiegi/{a}/stop").status_code == 202
    swiat.do_stanu(a, "zatrzymane")
    zajety = swiat.wyslij(wid, "@teste2ea [wolno:6] inne").json()["przebiegi"][0]["id"]
    swiat.do_stanu(zajety, "pracuje")
    r = swiat.k.post(f"{P}/przebiegi/{a}/ponow").json()["przebieg"]["id"]
    czekaj(lambda: swiat.p(r)["powod"] == "zajety_agent")
    assert swiat.k.post(f"{P}/przebiegi/{r}/anuluj").status_code == 200
    drugie = swiat.k.post(f"{P}/przebiegi/{a}/ponow")
    assert drugie.status_code == 202
    r2 = drugie.json()["przebieg"]
    assert r2["id"] != r and r2["stan"] == "kolejka" and r2["ponowienie_z"] == a


def test_ponow_po_nieudanym_ponowieniu_tworzy_nowe(swiat):
    out = swiat.nowy("@teste2ea [czekaj] zadanie")
    wid, a = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(a, "przyjety")
    swiat.k.post(f"{P}/przebiegi/{a}/stop")
    swiat.do_stanu(a, "zatrzymane")
    zajety = swiat.wyslij(wid, "@teste2ea [wolno:6] inne").json()["przebiegi"][0]["id"]
    swiat.do_stanu(zajety, "pracuje")
    r = swiat.k.post(f"{P}/przebiegi/{a}/ponow").json()["przebieg"]["id"]
    rej = swiat.sil.rejestr

    async def nieudane():
        rej._koniec(swiat.sil.db.przebieg(r), "blad", blad={"kod": "model", "komunikat": "x"})

    na_silniku(swiat, nieudane())
    r2 = swiat.k.post(f"{P}/przebiegi/{a}/ponow").json()["przebieg"]
    assert r2["id"] != r and r2["stan"] in M.przebiegi.STANY_AKTYWNE
    assert swiat.k.post(f"{P}/przebiegi/{a}/ponow").json()["przebieg"]["id"] == r2["id"]   # trwa: to samo


def test_czeka_na_ture_po_zgubieniu_przebiegu_w_bramie(swiat):
    """Brama zgubiła przebieg (restart: 404), a nasza tura nigdy nie przyszła: strażnik kończy go jako `zgubione`
    zamiast trzymać członka w `czeka_na_ture` na zawsze."""
    out = swiat.nowy("@teste2ea [czekaj] tura")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "przyjety")
    rej = swiat.sil.rejestr

    async def czeka():
        rej._przejdz(swiat.sil.db.przebieg(pid), "czeka_na_ture")

    na_silniku(swiat, czeka())
    run = swiat.brama.przebiegi.pop(swiat.p(pid)["run_id"])
    swiat.brama.loop.call_soon_threadsafe(run.kolejka.put_nowait, None)          # strumień zerwany
    czekaj(lambda: swiat.p(pid)["odlaczony"], 5, "odłączony")
    zegar = rej.zegar
    try:
        for przesun in (200, 400, 800):
            rej.zegar = lambda p=przesun: time.time() + p
            na_silniku(swiat, rej.straznik())
            if swiat.p(pid)["stan"] == "zgubione":
                break
    finally:
        rej.zegar = zegar
    assert swiat.p(pid)["stan"] == "zgubione"
    q = swiat.wyslij(wid, "@teste2ea dalej").json()["przebiegi"][0]["id"]
    assert swiat.do_stanu(q, "gotowe", czas=15)["stan"] == "gotowe"


def test_dziennik_przebiegu_usunietego_watku_sprzatany(swiat):
    out = swiat.nowy("@teste2ea [wolno:1.5] krótko")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    run = swiat.brama.przebiegi[swiat.p(pid)["run_id"]]
    assert swiat.k.delete(f"{P}/rozmowy/{wid}", params={"trwale": 1, "praca": "zostaw"}).status_code == 204
    czekaj(lambda: run.status == "completed", 10, "koniec w bramie")
    rej = swiat.sil.rejestr
    assert pid in rej._dzienniki
    na_silniku(swiat, rej.straznik())
    assert pid not in rej._dzienniki


def test_budzet_429_od_nowa_po_dlugim_czekaniu(swiat):
    """429 po długim czekaniu z innego powodu nie kończy wiadomości błędem: budżet liczy odmowy jedna po drugiej."""
    swiat.brama.limit_429 = 1
    pid = swiat.nowy("@teste2ea pierwsza")["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(pid)["powod"] == "limit", 5, "kolejka(limit)")
    rej = swiat.sil.rejestr

    async def postarz():                       # pierwsza odmowa 15 min temu, potem długo czekał (np. obca tura)
        rej._pierwszy_429[pid] = (time.time() - 900, time.time() - 800)
        swiat.brama.limit_429 = 1

    na_silniku(swiat, postarz())
    p = swiat.do_stanu(pid, "gotowe", "blad", czas=15)
    assert p["stan"] == "gotowe" and p["proby"] >= 3


def test_zgoda_po_usunieciu_watku_to_404(swiat):
    out = swiat.nowy("@teste2ea [zgoda] usuń pliki")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "czeka_na_zgode")
    rid = swiat.p(pid)["zgoda"]["request_id"]

    async def zgoda(agent, run_id, wybor, request_id):
        swiat.sil.db.usun(wid, trwale=True)
        return {"ok": True}

    swiat.sil.brama.zgoda = zgoda
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "once", "request_id": rid})
    assert r.status_code == 404 and r.json()["blad"]["kod"] == "brak"


# ----------------------------------------------------------------------------------------------- trzecia runda przeglądu

def _start_z_konfliktem(swiat):
    """POST dotarł do bramy (tura trwa), ale odpowiedź to 409 `idempotency_key_conflict`: przebieg bez `run_id`
    czeka na nasz wiersz w state.db, a potem jest turą „tylko z osi czasu”."""
    brama = swiat.sil.brama
    oryginal = brama.start

    async def start_konflikt(agent, *, cialo_, idem):
        await oryginal(agent, cialo_=cialo_, idem=idem)
        raise M.brama.BladBramy("konflikt", "idempotency_key_conflict", status=409, typ="idempotency_key_conflict")

    brama.start = start_konflikt


def test_stop_tury_tylko_z_osi_czasu_nie_wisi(swiat):
    """Stop przebiegu bez `run_id` (po 409 konfliktu klucza): stopu nie da się wysłać do bramy, ale przebieg nie
    zostaje w `zatrzymywanie` na zawsze: kończy się z osi czasu, gdy tura się skończy, i zwalnia członka i limit."""
    _start_z_konfliktem(swiat)
    out = swiat.nowy("@teste2ea [wolno:2] strona")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    assert not swiat.do_stanu(pid, "pracuje").get("run_id")
    q = swiat.wyslij(wid, "@teste2ea następna").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(q)["powod"] == "zajety_agent", opis="q w kolejce za turą")
    r = swiat.k.post(f"{P}/przebiegi/{pid}/stop")
    assert r.status_code == 202 and r.json()["przebieg"]["stan"] == "zatrzymywanie"
    czekaj(lambda: any(w["role"] == "assistant" for w in swiat.brama.wiersze("test-e2e-a")), 10, "odpowiedź w state.db")
    p = swiat.do_stanu(pid, "gotowe", "zatrzymane", "zgubione", czas=10)
    assert p["stan"] == "gotowe" and p["stop_lokalny"]                 # tura skończyła się z odpowiedzią
    assert swiat.sil.rejestr.aktywne_liczba() == 0                      # miejsce w limicie wolne
    assert (swiat.p(q)["stan"], swiat.p(q)["powod"]) == ("kolejka", "wstrzymane")     # Stop wstrzymał kolejkę
    assert swiat.k.post(f"{P}/przebiegi/{q}/wyslij").status_code == 200
    assert swiat.do_stanu(q, "gotowe", "blad", czas=15)["stan"] == "gotowe"


def test_stop_w_czasie_konfliktu_klucza_nie_przechodzi_do_pracy(swiat):
    """Stop, gdy przebieg czeka w `wysylanie` na nasz wiersz po 409 konfliktu: kontrola po znalezieniu wiersza
    przenosi go do `zatrzymywanie` (nie do `pracuje`), a koniec tury kończy go z osi czasu."""
    _start_z_konfliktem(swiat)
    rej, czytnik = swiat.sil.rejestr, swiat.sil.czytnik
    nasz, widac = czytnik.nasz_wiersz, threading.Event()
    czytnik.nasz_wiersz = lambda *a, **kw: nasz(*a, **kw) if widac.is_set() else None
    pid = swiat.nowy("@teste2ea [wolno:2] strona")["przebiegi"][0]["id"]
    czekaj(lambda: pid in rej._konflikty, 5, "konflikt klucza")
    assert swiat.p(pid)["stan"] == "wysylanie"
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").status_code == 202
    widac.set()
    p = swiat.do_stanu(pid, "zatrzymywanie", "pracuje", "gotowe")
    assert p["stan"] == "zatrzymywanie" and p["stop_lokalny"] and p["user_msg_id"]
    assert swiat.do_stanu(pid, "gotowe", "zgubione", czas=15)["stan"] == "gotowe"
    assert "pracuje" not in swiat.stany(pid)


def test_tura_z_osi_czasu_bez_odpowiedzi_konczy_straznik(swiat):
    """Tura bez `run_id` skończyła się bez odpowiedzi (przerwana): strażnik kończy ją jak każdą zgubioną (bez
    dzierżawy i bez nowych wierszy przez 10 min), zamiast trzymać członka w `pracuje` na zawsze."""
    _start_z_konfliktem(swiat)
    pid = swiat.nowy("@teste2ea [przerwij] zadanie")["przebiegi"][0]["id"]
    assert not swiat.do_stanu(pid, "pracuje").get("run_id")
    rej = swiat.sil.rejestr
    zegar = rej.zegar
    try:
        for przesun in (200, 400, 800):
            rej.zegar = lambda p=przesun: time.time() + p
            na_silniku(swiat, rej.straznik())
    finally:
        rej.zegar = zegar
    assert swiat.p(pid)["stan"] == "zgubione"


def test_dopisek_sprzed_restartu_bez_steera_nie_jest_wlaczony(swiat):
    """Wiersz `dopisany` zapisany przed steerem, a proces padł, zanim steer doszedł do bramy: po restarcie koniec
    celu bez `pending_steer` nie znaczy, że agent go dostał. Brak wiersza `steer` w state.db = `kolejka(wstrzymane)`."""
    out = swiat.nowy("@teste2ea [wolno:3] strona")
    pid = out["przebiegi"][0]["id"]
    p = swiat.do_stanu(pid, "pracuje")

    async def wiersz():                                 # to, co zostawia `Rejestr.dopisz` przed `await brama.dopisz`
        return swiat.sil.db.dodaj_przebieg(watek_id=p["watek_id"], wpis_id=None, agent=p["agent"], rola="rozmowa",
                                           zrodlo="wlasciciel", lancuch_id=p["lancuch_id"], stan="dopisany", powod="",
                                           dopisany_do=pid, payload={"prosba": "dodaj NIP", "obrazy": []})

    q = na_silniku(swiat, wiersz())["id"]
    swiat.restart()
    swiat.do_stanu(pid, "gotowe", czas=15)
    assert not [z for z in swiat.brama.dziennik if z["sciezka"].endswith("/steer")]
    qq = swiat.do_stanu(q, "wlaczony", "kolejka", czas=10)
    assert (qq["stan"], qq["powod"]) == ("kolejka", "wstrzymane")
    stoi(swiat, q, "kolejka", "wstrzymane", czas=1.5)


def test_dopisek_sprzed_restartu_dostarczony_jest_wlaczony(swiat):
    """Ten sam restart, ale steer doszedł przed nim (wiersz `steer` w state.db): po końcu celu `wlaczony`."""
    out = swiat.nowy("@teste2ea [wolno:3] strona")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    q = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj REGON"}).json()["przebieg"]["id"]
    swiat.restart()
    swiat.do_stanu(pid, "gotowe", czas=15)
    assert swiat.do_stanu(q, "wlaczony", "kolejka", czas=10)["stan"] == "wlaczony"

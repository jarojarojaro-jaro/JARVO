"""Silnik rozmów aplikacji (hq/plugin/silnik.py, przebiegi.py, trasy_rozmow.py, brama.py, scalanie.py, obserwator.py)
z atrapą bramy Hermesa (tests/atrapa_bramy.py): prawdziwy wątek silnika, prawdziwe trasy FastAPI, state.db profili ze
schematem z obrazu. Pokrycie: przejścia stanów, kolejka członka, powtórka strumienia, restart silnika (odłączony),
wygaśnięcie zgody, dopisz (steer), stop i wstrzymane, oba warianty Ponów, limit globalny i 429, limit obrazów."""
from __future__ import annotations

import asyncio
import base64
import json
import secrets
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import atrapa_bramy  # noqa: E402
from conftest import load_script  # noqa: E402

M = SimpleNamespace(**{n: load_script(f"hq/plugin/{p}.py", f"jarvo_test_sr_{n}") for n, p in (
    ("hq_core", "hq_core"), ("ochrona", "ochrona"), ("agenci", "agenci"), ("rozmowy", "rozmowy"),
    ("czytnik", "czytnik"), ("kontekst", "kontekst"), ("wzmianki", "wzmianki"), ("budzenia", "budzenia"),
    ("scalanie", "scalanie"), ("brama", "brama"), ("strumien", "strumien"), ("przebiegi", "przebiegi"),
    ("prace", "prace"), ("karty", "karty"), ("obserwator", "obserwator"), ("silnik", "silnik"))})
trasy = load_script("hq/plugin/trasy_rozmow.py", "jarvo_test_sr_trasy")
P = "/api/plugins/jarvo-hq"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
AGENCI_TESTOWI = {"test-e2e-a": {"handle": "teste2ea", "nazwa": "Test A", "test": True},
                  "test-e2e-b": {"handle": "teste2eb", "nazwa": "Test B", "test": True}}


def czekaj(warunek, czas: float = 10.0, opis: str = ""):
    koniec = time.monotonic() + czas
    while time.monotonic() < koniec:
        wynik = warunek()
        if wynik:
            return wynik
        time.sleep(0.05)
    raise AssertionError(f"nie doczekałem się: {opis or warunek}")


def _liczone(cel, nazwa):
    """Liczy zakończone wywołania korutyny pętli (runda dyspozytora, cykl obserwatora): test czeka na pełne cykle,
    a nie śpi „na oko” (pod obciążeniem sen nie gwarantuje ani jednego cyklu)."""
    oryginal = getattr(cel, nazwa)
    licznik = [0]

    async def liczona(*a, **kw):
        try:
            return await oryginal(*a, **kw)
        finally:
            licznik[0] += 1

    setattr(cel, nazwa, liczona)
    return lambda: licznik[0]


def _po_cyklach(ile_teraz, n=2, opis="cykle", czas=15.0):
    """`n` pełnych cykli od teraz (cykl w toku się nie liczy: mógł zacząć się przed zmianą)."""
    start = ile_teraz()
    czekaj(lambda: ile_teraz() >= start + n + 1, czas, opis)


class Swiat:
    """Dom Hermesa w katalogu tymczasowym, atrapa bramy, silnik, trasy i klient HTTP."""

    def __init__(self, tmp, *, limit: int = 8):
        self.home = tmp / "data"
        self.jarvo = self.home / "jarvo"
        (self.jarvo / "state").mkdir(parents=True)
        klucze = {}
        for a in ("jarvo", "test-e2e-a", "test-e2e-b"):
            klucze[a] = secrets.token_hex(8)
            (self.home / "profiles" / a).mkdir(parents=True)
            (self.home / "profiles" / a / ".env").write_text(f"API_SERVER_KEY={klucze[a]}\n", encoding="utf-8")
            atrapa_bramy.baza_profilu(self.home / "profiles" / a / "state.db")
        (self.home / "profiles" / "test-e2e-a" / "config.yaml").write_text(
            "model: x\napprovals:\n  mode: manual\n  timeout: 2\n", encoding="utf-8")
        fleet = tmp / "fleet.json"
        fleet.write_text(json.dumps({"agents": [{"name": "jarvo", "handle": "jarvo", "aliasy": ["jarvo"],
                                                 "short": "Jarvo"}]}), encoding="utf-8")
        (self.jarvo / "state" / "agenci.json").write_text(json.dumps(AGENCI_TESTOWI), encoding="utf-8")
        self.agenci = M.agenci.Agenci(fleet, self.jarvo / "state" / "agenci.json", e2e=lambda: True)
        self.brama = atrapa_bramy.AtrapaBramy(self.home, klucze)
        self.hub = M.strumien.Hub(zycie=1.5, ping=0.5)
        self.logi: list[str] = []
        self.limit = limit
        self.sil = self._silnik()
        app = FastAPI()
        router = APIRouter(route_class=M.ochrona.Trasa)
        trasy.dolacz(router, m=M, silnik=lambda: self.sil, hub=self.hub, agenci=self.agenci,
                     inbox=self.jarvo / "inbox", log=self.logi.append)
        app.include_router(router, prefix=P)
        self.k = TestClient(app, headers={"X-Jarvo-Request": "1"})

    def _silnik(self):
        s = M.silnik.Silnik(moduly=M, home=self.home, jarvo_dir=self.jarvo, api_base="http://brama.test",
                            agenci=self.agenci, hub=self.hub, log=self.logi.append, limit=self.limit,
                            http=httpx.AsyncClient(transport=self.brama.transport()), odstep_odpytania=0.2)
        s.start(czekaj=10)
        assert s.dziala(), s.blad
        return s

    def restart(self):
        self.sil.zamknij()
        self.sil = self._silnik()

    def zamknij(self):
        self.sil.zamknij()
        self.brama.zamknij()

    # ---- skróty
    def nowy(self, tekst: str, **kw) -> dict:
        r = self.k.post(f"{P}/rozmowy", json={"wiadomosc": {"tekst": tekst, "klucz": secrets.token_hex(6), **kw}})
        assert r.status_code == 201, r.text
        return r.json()

    def wyslij(self, wid: str, tekst: str, **kw):
        return self.k.post(f"{P}/rozmowy/{wid}/wiadomosci", json={"tekst": tekst, "klucz": secrets.token_hex(6), **kw})

    def p(self, pid: str) -> dict:
        return self.sil.db.przebieg(pid)

    def do_stanu(self, pid: str, *stany, czas: float = 10.0) -> dict:
        return czekaj(lambda: (lambda p: p if p["stan"] in stany else None)(self.p(pid)), czas,
                      f"{pid} → {stany} (jest {self.p(pid)['stan']}/{self.p(pid).get('powod')})")

    def ramki(self, typ: str | None = None) -> list[tuple[str, dict]]:
        out = []
        with self.hub._lock:
            bufor = list(self.hub._bufor)
        for _s, _t, _w, ramka in bufor:
            linie = ramka.decode().splitlines()
            t = linie[1].split(": ", 1)[1]
            d = json.loads(linie[2].split(": ", 1)[1])
            if typ is None or t == typ:
                out.append((t, d))
        return out

    def stany(self, pid: str) -> list[str]:
        out: list[str] = []
        for _t, d in self.ramki("przebieg.stan"):
            if d["przebieg"]["id"] == pid and (not out or out[-1] != d["przebieg"]["stan"]):
                out.append(d["przebieg"]["stan"])
        return out

    def delty(self, pid: str) -> str:
        return "".join(d["tekst"] for _t, d in self.ramki("przebieg.delta") if d["id"] == pid)


@pytest.fixture
def swiat(tmp_path):
    s = Swiat(tmp_path)
    yield s
    s.zamknij()


@pytest.fixture
def swiat_limit1(tmp_path):
    s = Swiat(tmp_path, limit=1)
    yield s
    s.zamknij()


# ----------------------------------------------------------------------------------------------- przejścia

def test_rozmowa_od_wyslania_do_odpowiedzi(swiat):
    out = swiat.nowy("@teste2ea ala ma kota")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    assert out["watek"]["tytul"] == "ala ma kota" and out["wpis"]["adresaci"] == ["test-e2e-a"]
    assert out["wpis"]["tryb"] == "bezposrednio" and out["przebiegi"][0]["stan"] == "kolejka"
    p = swiat.do_stanu(pid, "gotowe")
    assert swiat.stany(pid) == ["kolejka", "wysylanie", "przyjety", "pracuje", "gotowe"]
    assert swiat.delty(pid) == "Odpowiedź: ala ma kota"
    sid = f"jarvo_{wid}_test-e2e-a"
    assert p["sesja_id"] == sid
    assert swiat.sil.czytnik.nasz_wiersz("test-e2e-a", [sid], p["payload_sha"], p["wyslany_at"] - 2)
    sesja = swiat.brama.sesja("test-e2e-a", sid)
    assert sesja["pinned"] == 1 and sesja["title"] == "Jarvo · ala ma kota · Test A"
    # oś czasu: wpis właściciela i odpowiedź agenta; nasz wiersz użytkownika ukryty (payload_sha)
    os_ = swiat.k.get(f"{P}/rozmowy/{wid}/os").json()
    rodzaje = [(x["rodzaj"], x.get("agent")) for x in os_["pozycje"]]
    assert ("wlasciciel", None) in rodzaje and ("agent", "test-e2e-a") in rodzaje
    assert not any(x["rodzaj"] == "obca" for x in os_["pozycje"])
    agent = next(x for x in os_["pozycje"] if x["rodzaj"] == "agent")
    assert agent["tekst"] == "Odpowiedź: ala ma kota" and agent["id"].startswith("m:test-e2e-a:")
    w = swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]
    assert w["podglad"].startswith("Test A: Odpowiedź") and w["status"] == "cisza"
    assert w["czlonkowie_pelni"][0]["sesja_id"] == sid
    # ten sam klucz = ta sama odpowiedź, bez drugiej wysyłki
    klucz = secrets.token_hex(6)
    r1 = swiat.k.post(f"{P}/rozmowy/{wid}/wiadomosci", json={"tekst": "@teste2ea raz", "klucz": klucz}).json()
    r2 = swiat.k.post(f"{P}/rozmowy/{wid}/wiadomosci", json={"tekst": "@teste2ea raz", "klucz": klucz}).json()
    assert r1["wpis"]["id"] == r2["wpis"]["id"] and [x["id"] for x in r1["przebiegi"]] == [x["id"] for x in r2["przebiegi"]]
    swiat.do_stanu(r1["przebiegi"][0]["id"], "gotowe")
    assert len(swiat.brama.runs("test-e2e-a")) == 2
    assert any("przebieg" in linia and "→gotowe" in linia for linia in swiat.logi)


def test_rownolegle_i_kolejka_czlonka(swiat):
    out = swiat.nowy("@teste2ea @teste2eb [wolno:1] razem")
    wid = out["watek"]["id"]
    pa, pb = (x["id"] for x in out["przebiegi"])
    czekaj(lambda: swiat.p(pa)["stan"] == "pracuje" and swiat.p(pb)["stan"] == "pracuje", opis="obaj pracują naraz")
    assert "Ta sama wiadomość poszła też do: Test B" in swiat.brama.runs("test-e2e-a")[0]["cialo"]["input"]
    drugi = swiat.wyslij(wid, "@teste2ea potem").json()["przebiegi"][0]["id"]
    swiat.do_stanu(drugi, "kolejka")
    czekaj(lambda: swiat.p(drugi)["powod"] == "zajety_agent", opis="zajety_agent")
    swiat.do_stanu(pa, "gotowe")
    swiat.do_stanu(drugi, "gotowe")
    assert swiat.p(drugi)["wyslany_at"] >= swiat.p(pa)["zakonczony_at"]
    # blok kontekstu: b dostaje odpowiedź a i swoją prośbę z etykietą
    swiat.do_stanu(pb, "gotowe")
    trzeci = swiat.wyslij(wid, "@teste2eb a teraz ty").json()["przebiegi"][0]["id"]
    swiat.do_stanu(trzeci, "gotowe")
    wejscie = swiat.brama.runs("test-e2e-b")[-1]["cialo"]["input"]
    assert "Odpowiedź: potem" in wejscie and "[Wiadomość właściciela" in wejscie and wejscie.endswith("a teraz ty")
    # blok kontekstu ukryty na osi (cały wiersz użytkownika = nasz payload_sha)
    os_ = swiat.k.get(f"{P}/rozmowy/{wid}/os").json()["pozycje"]
    assert not any(x["rodzaj"] == "obca" for x in os_)
    assert [x["agent"] for x in os_ if x["rodzaj"] == "agent"].count("test-e2e-b") == 2


def test_strumien_powtorka_od_kursora(swiat):
    od = swiat.hub.kursor()
    out = swiat.nowy("@teste2ea [wolno:0.5] strumień")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "gotowe")

    def czytaj(kursor: str) -> list[tuple[str | None, str, dict]]:
        r = swiat.k.get(f"{P}/strumien", params={"klient": "k_test0001", "watki": wid, "od": kursor})
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
        assert r.headers["x-accel-buffering"] == "no"
        ramki = []
        for blok in r.text.split("\n\n"):
            pola = dict(linia.split(": ", 1) for linia in blok.splitlines() if ": " in linia and not linia.startswith(":"))
            if "event" in pola:
                ramki.append((pola.get("id"), pola["event"], json.loads(pola["data"])))
        return ramki

    ramki = czytaj(od)
    assert ramki[0][1] == "hello" and ramki[0][2]["epoka"] == swiat.hub.epoka
    tekst = "".join(d["tekst"] for _i, t, d in ramki if t == "przebieg.delta" and d["id"] == pid)
    assert tekst == "Odpowiedź: strumień"
    # wznowienie od środka: nic nie ginie i nic się nie powtarza
    srodek = next(i for i, t, d in ramki if t == "przebieg.delta")
    reszta = czytaj(srodek)
    pierwsza = "".join(d["tekst"] for i, t, d in ramki if t == "przebieg.delta" and i <= srodek)
    druga = "".join(d["tekst"] for _i, t, d in reszta if t == "przebieg.delta")
    assert pierwsza + druga == "Odpowiedź: strumień"
    # obca epoka = reset
    reset = czytaj("ffffff.3")
    assert ("reset", {"powod": "epoka"}) in [(t, d) for _i, t, d in reset]


# ----------------------------------------------------------------------------------------------- restart, Ponów

def test_restart_silnika_przebieg_odlaczony(swiat):
    out = swiat.nowy("@teste2ea [wolno:2] długa praca")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    drugi = swiat.wyslij(wid, "@teste2ea po restarcie").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(drugi)["powod"] == "zajety_agent")
    swiat.restart()
    p = swiat.do_stanu(pid, "gotowe")
    assert p["odlaczony"] == 1
    assert swiat.sil.rejestr.widok(p)["tekst_dotad"].startswith("Odpowiedź: długa praca")
    swiat.do_stanu(drugi, "gotowe")                     # kolejka rusza sama po restarcie, bez otwartej karty
    assert len(swiat.brama.runs("test-e2e-a")) == 2


def test_przerwane_ponow_wysyla_krotka_kontynuacje(swiat):
    out = swiat.nowy("@teste2ea [przerwij] zadanie X")
    pid = out["przebiegi"][0]["id"]
    p = swiat.do_stanu(pid, "przerwane")
    czekaj(lambda: swiat.p(pid)["user_msg_id"] or True)
    r = swiat.k.post(f"{P}/przebiegi/{pid}/ponow")
    assert r.status_code == 202, r.text
    q = r.json()["przebieg"]
    assert q["ponowienie_z"] == pid
    swiat.do_stanu(q["id"], "gotowe")
    wejscia = [x["cialo"]["input"] for x in swiat.brama.runs("test-e2e-a")]
    assert sum("zadanie X" in w for w in wejscia) == 1          # treść właściciela raz w sumie
    assert wejscia[-1] == M.przebiegi.KONTYNUACJA.format(powod="praca przerwana")
    assert p["blad"] is None


def test_blad_z_przyczyna_szczegolami_i_karta_do_ponowienia(swiat):
    out = swiat.nowy("@teste2ea [blad] zadanie Z")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "blad")
    b = swiat.p(pid)["blad"]
    # krótka przyczyna po polsku dla właściciela, surowy błąd Hermesa w „Szczegóły”
    assert b["komunikat"] == "Model przestał odpowiadać" and b["szczegoly"] == "model error"
    assert b["powod_hermesa"] == "model_error"
    # migawka wątku niesie nieudany przebieg: karta z „Ponów” przetrwa przeładowanie strony
    w = swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]
    assert [x["id"] for x in w["przebiegi_do_ponowienia"]] == [pid]
    q = swiat.k.post(f"{P}/przebiegi/{pid}/ponow").json()["przebieg"]
    assert q["ponowienie_z"] == pid
    w = swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]
    assert w["przebiegi_do_ponowienia"] == []           # ponowiony: karta „Ponów” znika po przeładowaniu


def test_blad_nieznanej_przyczyny_mowi_prosto(swiat):
    out = swiat.nowy("@teste2ea [czekaj] zadanie N")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "przyjety")
    swiat.sil.rejestr._koniec_ze_statusu(swiat.p(pid), {"status": "failed", "turn_exit_reason": "cos_nowego",
                                                          "error": "boom"})
    b = swiat.p(pid)["blad"]
    assert b["komunikat"] == "Praca się nie udała" and b["komunikat_en"] == "The work failed"
    assert b["szczegoly"] == "cos_nowego · boom" and b["powod_hermesa"] == "cos_nowego"


def test_ponow_bez_zapisanej_tury_wysyla_calosc(swiat):
    out = swiat.nowy("@teste2ea [czekaj] zadanie Y")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "przyjety")
    r = swiat.k.post(f"{P}/przebiegi/{pid}/stop")
    assert r.status_code == 202
    swiat.do_stanu(pid, "zatrzymane")
    assert not swiat.p(pid)["user_msg_id"]
    q = swiat.k.post(f"{P}/przebiegi/{pid}/ponow").json()["przebieg"]
    swiat.do_stanu(q["id"], "przyjety", "pracuje", "gotowe")
    wejscia = [x["cialo"]["input"] for x in swiat.brama.runs("test-e2e-a")]
    assert len(wejscia) == 2 and all("zadanie Y" in w for w in wejscia)
    run2 = swiat.p(q["id"])["run_id"]
    swiat.brama.zwolnij(run2)
    swiat.do_stanu(q["id"], "gotowe")
    wiersze = [w for w in swiat.brama.wiersze("test-e2e-a") if w["role"] == "user" and "zadanie Y" in w["content"]]
    assert len(wiersze) == 1
    # Ponów działa tylko z blad/przerwane/zgubione/zatrzymane
    assert swiat.k.post(f"{P}/przebiegi/{q['id']}/ponow").json()["blad"]["kod"] == "nieaktywny"


# ----------------------------------------------------------------------------------------------- limity

def test_limit_globalny_i_429(swiat_limit1):
    s = swiat_limit1
    a = s.nowy("@teste2ea [wolno:1] pierwszy")["przebiegi"][0]["id"]
    s.do_stanu(a, "pracuje", "przyjety")
    b = s.nowy("@teste2eb drugi")["przebiegi"][0]["id"]
    czekaj(lambda: s.p(b)["stan"] == "kolejka" and s.p(b)["powod"] == "limit", opis="kolejka(limit)")
    s.do_stanu(a, "gotowe")
    s.do_stanu(b, "gotowe")
    s.brama.limit_429 = 1
    c = s.nowy("@teste2ea trzeci")["przebiegi"][0]["id"]
    czekaj(lambda: s.p(c)["powod"] == "limit" or s.p(c)["stan"] == "gotowe", opis="429 → kolejka(limit)")
    s.do_stanu(c, "gotowe", czas=15)
    assert s.p(c)["proby"] >= 2


def test_obrazy_i_limit_rozmiaru(swiat):
    dane = "data:image/png;base64," + base64.b64encode(PNG).decode()
    out = swiat.nowy("@teste2ea popatrz", obrazy=[{"nazwa": "zrzut.svg", "dane": dane}])
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    obraz = out["wpis"]["obrazy"][0]
    assert obraz["mime"] == "image/png" and obraz["path"].endswith(".png") and "dane" not in obraz
    swiat.do_stanu(pid, "gotowe")
    wejscie = swiat.brama.runs("test-e2e-a")[0]["cialo"]["input"]
    czesci = wejscie[0]["content"]
    assert czesci[1]["type"] == "image_url" and czesci[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert f"📎 {obraz['path']}" in czesci[0]["text"]
    wiersz = next(w for w in swiat.brama.wiersze("test-e2e-a") if w["role"] == "user")
    assert wiersz["content"].endswith("\n[screenshot]")
    assert not any(x["rodzaj"] == "obca" for x in swiat.k.get(f"{P}/rozmowy/{wid}/os").json()["pozycje"])
    # 7,5 MB zakodowanych obrazów: 413 za_duze, zanim cokolwiek pójdzie do bramy
    ile = len(swiat.brama.dziennik)
    duzy = "data:image/png;base64," + "A" * 7_500_000
    r = swiat.wyslij(wid, "@teste2ea duży", obrazy=[{"nazwa": "a.png", "dane": duzy}])
    assert r.status_code == 413 and r.json()["blad"]["kod"] == "za_duze"
    svg = "data:image/svg+xml;base64," + base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'/>").decode()
    r = swiat.wyslij(wid, "@teste2ea svg", obrazy=[{"nazwa": "a.svg", "dane": svg}])
    assert r.status_code == 415 and r.json()["blad"]["kod"] == "zly_obraz"
    assert len(swiat.brama.dziennik) == ile


# ----------------------------------------------------------------------------------------------- zgoda, stop, dopisz

def test_zgoda_odpowiedz_i_wygasniecie(swiat):
    out = swiat.nowy("@teste2ea [zgoda] usuń pliki")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "czeka_na_zgode")
    z = swiat.k.get(f"{P}/przebiegi/{pid}").json()["przebieg"]["zgoda"]
    assert z["wybory"] == ["once", "session", "deny"] and z["ryzyko"] == "Agent chce usunąć pliki"
    assert swiat.k.get(f"{P}/rozmowy/{wid}").json()["watek"]["status"] == "czeka"
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "zawsze", "request_id": z["request_id"]})
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zly_wybor"
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "deny", "request_id": z["request_id"]})
    assert r.status_code == 200, r.text
    swiat.do_stanu(pid, "gotowe")
    assert swiat.sil.rejestr.widok(swiat.p(pid))["tekst_dotad"].startswith("zgoda:deny")
    # druga prośba bez odpowiedzi: po 2 s (approvals.timeout profilu) wygasa, przebieg wraca do pracuje
    drugi = swiat.wyslij(wid, "@teste2ea [zgoda] znowu").json()["przebiegi"][0]["id"]
    swiat.do_stanu(drugi, "czeka_na_zgode")
    rid = swiat.p(drugi)["zgoda"]["request_id"]
    p = czekaj(lambda: (lambda q: q if (q.get("zgoda") or {}).get("wygasla") else None)(swiat.p(drugi)), 8, "wygasła")
    assert p["stan"] == "pracuje"
    run = swiat.brama.przebiegi[p["run_id"]]
    assert run.status == "waiting_for_approval"                 # brama dalej czeka, aplikacja nie
    r = swiat.k.post(f"{P}/przebiegi/{drugi}/zgoda", json={"wybor": "once", "request_id": rid})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "zgoda_wygasla"
    assert swiat.k.post(f"{P}/przebiegi/{drugi}/stop").status_code == 202
    swiat.do_stanu(drugi, "zatrzymane")


def test_zgoda_brama_odmawia_pierwsza(swiat):
    # Hermes liczy ten sam approvals.timeout i zwykle odmawia przed kontrolą co 1 s (bez approval.responded):
    # zdarzenie pracy tuż przed wygasa_at to wygaśnięcie (zgoda.wygasla), a nie „pracuje” z wyczyszczoną zgodą
    swiat.brama.czas_zgody = 1.6
    out = swiat.nowy("@teste2ea [zgoda] usuń pliki")
    pid = out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "czeka_na_zgode")
    rid = swiat.p(pid)["zgoda"]["request_id"]
    p = swiat.do_stanu(pid, "gotowe", czas=15)
    assert [d["zgoda"]["wygasla"] for _t, d in swiat.ramki("przebieg.zgoda") if d["id"] == pid] == [False, True]
    assert p["zgoda"]["wygasla"] is True
    assert swiat.sil.rejestr.widok(p)["tekst_dotad"].startswith("zgoda:czas")
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zgoda", json={"wybor": "once", "request_id": rid})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "zgoda_wygasla"
    assert any("czas na zgodę minął" in x for x in swiat.logi)

def test_dopisz_w_trakcie_pracy(swiat):
    out = swiat.nowy("@teste2ea [wolno:2] strona")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    r = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "dodaj NIP"})
    assert r.status_code == 200, r.text
    q = r.json()["przebieg"]
    assert q["stan"] == "dopisany" and q["dopisany_do"] == pid
    swiat.do_stanu(pid, "gotowe")
    swiat.do_stanu(q["id"], "wlaczony")
    assert "dopisane: dodaj NIP" in swiat.brama.przebiegi[swiat.p(pid)["run_id"]].odpowiedz
    wpis = swiat.sil.db.wpis(swiat.p(q["id"])["wpis_id"])
    assert wpis["dane"] == {"dopisane_do": pid}
    os_ = swiat.k.get(f"{P}/rozmowy/{wid}/os").json()["pozycje"]
    assert not any(x["rodzaj"] in ("obca", "dopisano") for x in os_)      # nasz steer pokazuje wpis, nie wiersz
    # dopisz, gdy agent nie pracuje: 409 (UI proponuje kolejkę)
    r = swiat.k.post(f"{P}/przebiegi/{pid}/dopisz", json={"tekst": "za późno"})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "nieaktywny"


def test_stop_wstrzymuje_kolejke_i_wyslij_teraz(swiat):
    out = swiat.nowy("@teste2ea [wolno:3] długie")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    drugi = swiat.wyslij(wid, "@teste2ea następne").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(drugi)["powod"] == "zajety_agent")
    r = swiat.k.post(f"{P}/przebiegi/{pid}/zatrzymaj")
    assert r.status_code == 202 and r.json()["przebieg"]["stan"] in ("zatrzymywanie", "zatrzymane")
    swiat.do_stanu(pid, "zatrzymane")
    assert swiat.p(drugi)["stan"] == "kolejka" and swiat.p(drugi)["powod"] == "wstrzymane"
    M.przebiegi.ODPYTANIE_S, odpytanie = 0.3, M.przebiegi.ODPYTANIE_S     # częstsze rundy: szybszy test
    try:
        _po_cyklach(_liczone(swiat.sil.rejestr, "_runda"), 3, "trzy pełne rundy dyspozytora")   # nie rusza go
    finally:
        M.przebiegi.ODPYTANIE_S = odpytanie
    assert swiat.p(drugi)["stan"] == "kolejka" and not swiat.p(drugi).get("run_id")
    assert swiat.k.post(f"{P}/przebiegi/{pid}/stop").json()["blad"]["kod"] == "nieaktywny"
    r = swiat.k.post(f"{P}/przebiegi/{drugi}/wyslij")
    assert r.status_code == 200, r.text
    swiat.do_stanu(drugi, "gotowe")
    # anuluj działa tylko w kolejce
    assert swiat.k.post(f"{P}/przebiegi/{drugi}/anuluj").json()["blad"]["kod"] == "nieaktywny"


def test_czeka_na_dzierzawe_obcej_tury(swiat):
    out = swiat.nowy("@teste2ea pierwsza")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "gotowe")
    sid = swiat.p(pid)["sesja_id"]
    swiat.brama.dzierzawa("test-e2e-a", sid)                 # budzenie kartą trzyma sesję
    drugi = swiat.wyslij(wid, "@teste2ea po budzeniu").json()["przebiegi"][0]["id"]
    czekaj(lambda: swiat.p(drugi)["powod"] == "tura", opis="kolejka(tura)")
    M.przebiegi.ODPYTANIE_S, odpytanie = 0.3, M.przebiegi.ODPYTANIE_S
    try:
        _po_cyklach(_liczone(swiat.sil.rejestr, "_runda"), 2, "dwie pełne rundy dyspozytora")
    finally:
        M.przebiegi.ODPYTANIE_S = odpytanie
    assert swiat.p(drugi)["stan"] == "kolejka"
    swiat.brama.zwolnij_dzierzawe("test-e2e-a", sid)
    swiat.sil.rejestr.zmiana_stanu("test-e2e-a")
    swiat.do_stanu(drugi, "gotowe")


def test_strumien_urwany_przechodzi_na_odpytywanie(swiat):
    pid = swiat.nowy("@teste2ea [urwij] krótko")["przebiegi"][0]["id"]
    p = swiat.do_stanu(pid, "gotowe")
    assert p["odlaczony"] == 1
    assert swiat.sil.rejestr.widok(p)["tekst_dotad"] == "…Odpowiedź: krótko"


# ----------------------------------------------------------------------------------------------- trasy i praca

def test_trasy_bledy_i_walidacja(swiat):
    k = swiat.k
    assert k.get(f"{P}/rozmowy/w_zly").json()["blad"]["kod"] == "brak"
    assert k.get(f"{P}/przebiegi/p_00000000000000000000a").status_code == 404
    r = k.post(f"{P}/rozmowy", json={"koordynator": "nieznany"})
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zly_koordynator"
    wid = k.post(f"{P}/rozmowy", json={"tytul": "Pusta"}).json()["watek"]["id"]
    assert swiat.wyslij(wid, "   ").json()["blad"]["kod"] == "pusta_tresc"
    r = swiat.wyslij(wid, "x", adresaci=["jarvo-nikt"])
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "nieznany_agent"
    r = swiat.wyslij(wid, "x", zalaczniki=["/etc/passwd"])
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zla_sciezka"
    r = k.post(f"{P}/rozmowy/{wid}/wiadomosci", json={"tekst": "x" * 32_001, "klucz": "a"})
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zle_dane"
    r = k.post(f"{P}/rozmowy/{wid}/wiadomosci", content="x=1", headers={"Content-Type": "text/plain",
                                                                         "Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403 and r.json()["blad"]["kod"] == "csrf"
    # lista, zmiana, kosz, przywrócenie
    assert [w["id"] for w in k.get(f"{P}/rozmowy").json()["watki"]] == [wid]
    w = k.patch(f"{P}/rozmowy/{wid}", json={"tytul": "Nowy  tytuł", "przypiety": True}).json()["watek"]
    assert w["tytul"] == "Nowy tytuł" and w["przypiety"] == 1 and w["tytul_zrodlo"] == "wlasciciel"
    assert k.delete(f"{P}/rozmowy/{wid}").status_code == 204
    assert k.get(f"{P}/rozmowy").json()["watki"] == []
    assert [w["id"] for w in k.get(f"{P}/rozmowy", params={"filtr": "kosz"}).json()["watki"]] == [wid]
    assert swiat.wyslij(wid, "@teste2ea x").json()["blad"]["kod"] == "w_koszu"
    assert k.post(f"{P}/rozmowy/{wid}/przywroc").json()["watek"]["usuniety_at"] is None


def test_archiwum_z_praca_wymaga_wyboru_i_praca_json(swiat):
    out = swiat.nowy("@teste2ea [wolno:3] w toku")
    wid, pid = out["watek"]["id"], out["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    praca = swiat.jarvo / "state" / "praca.json"
    dane = czekaj(lambda: praca.exists() and (lambda d: d if d["aktywne"] >= 1 else None)(json.loads(praca.read_text())),
                  opis="praca.json z pracą")
    assert dane["opis"] == ["Test A: rozmowa"]
    r = swiat.k.patch(f"{P}/rozmowy/{wid}", json={"archiwum": True})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "praca_trwa"
    assert r.json()["blad"]["przebiegi"][0]["id"] == pid
    r = swiat.k.patch(f"{P}/rozmowy/{wid}", json={"archiwum": True, "praca": "zatrzymaj"})
    assert r.status_code == 200 and r.json()["watek"]["archiwum"] == 1
    swiat.do_stanu(pid, "zatrzymane")
    czekaj(lambda: json.loads(praca.read_text())["aktywne"] == 0, opis="praca.json bez pracy")
    zdrowie = swiat.sil.zdrowie()
    assert zdrowie["silnik"] == "ok" and zdrowie["obserwator"]["bledy"] == 0


def test_karty_pracy_z_tablicy(swiat):
    """GET /karty i /karty/{id} (karty.py): stan przekazania z tablicy kanbana dla żywej karty w wątku."""
    import sqlite3
    conn = sqlite3.connect(swiat.home / "kanban.db")
    conn.executescript("""
    CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, assignee TEXT, status TEXT, created_at INTEGER, started_at INTEGER,
      completed_at INTEGER, last_heartbeat_at INTEGER, current_run_id INTEGER, result TEXT);
    CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT, status TEXT, started_at INTEGER,
      ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT);
    CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT, payload TEXT,
      created_at INTEGER);
    INSERT INTO tasks VALUES ('t_0000abcd', 'Audyt', 'jarvo', 'done', 1, 2, 9, 8, NULL, NULL);
    INSERT INTO task_runs VALUES (1, 't_0000abcd', 'test-e2e-a', 'review', 2, 5, 'review_requested', 'Raport z 5 problemami.',
      '{"artifacts": ["out/audyt.md"]}');
    INSERT INTO task_runs VALUES (2, 't_0000abcd', 'jarvo', 'done', 6, 9, 'completed', 'Zatwierdzam.', NULL);
    """)
    conn.commit()
    conn.close()
    k = swiat.k.get(f"{P}/karty", params={"id": "t_0000abcd,t_nieznana0,zle"}).json()["karty"]
    assert list(k) == ["t_0000abcd"]
    assert k["t_0000abcd"]["etap"] == "gotowe" and k["t_0000abcd"]["agent"] == "test-e2e-a"
    assert k["t_0000abcd"]["podsumowanie"] == "Raport z 5 problemami." and k["t_0000abcd"]["ocena"] == "Zatwierdzam."
    karta = swiat.k.get(f"{P}/karty/t_0000abcd").json()["karta"]
    assert [p["rola"] for p in karta["przebieg"]] == ["praca", "ocena"]
    assert swiat.k.get(f"{P}/karty/t_ffffffff").status_code == 404
    assert swiat.k.get(f"{P}/karty/zle-id").status_code == 404
    assert swiat.k.get(f"{P}/karty", headers={"Sec-Fetch-Site": "same-site"}).status_code == 403

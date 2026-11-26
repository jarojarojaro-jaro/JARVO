"""Centrum (krok 1b/1d) od końca do końca w silniku: czterech rozmówców (Operator i Kernel na omp, Jarvo i Jarodev na
Hermesie), atrapa bramy Hermesa (tests/atrapa_bramy.py), atrapa `omp` z prawdziwą skrzynką (`jarvo sesja … skrzynka`
w wątku testu, tests/atrapa_omp.py) i atrapa Bot API Telegrama (tests/atrapa_telegrama.py).

Wymaganie właściciela: jedna historia na rozmówcę w panelu, Telegramie i terminalu, na żywo, bez dubli, ten sam stan
niezależnie od kanału. Sprawdzamy oba kierunki (Telegram → panel, panel → Telegram) dla rozmówcy Hermesa i omp."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
pytest.importorskip("fcntl")
if os.name == "nt":
    pytest.skip("sesje omp z blokadą: Linux i macOS", allow_module_level=True)

from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import atrapa_bramy  # noqa: E402
import atrapa_omp  # noqa: E402
from atrapa_telegrama import AtrapaTelegrama  # noqa: E402
from conftest import load_script  # noqa: E402

M = SimpleNamespace(**{n: load_script(f"hq/plugin/{n}.py", f"jarvo_test_cs_{n}") for n in (
    "hq_core", "ochrona", "agenci", "rozmowy", "czytnik", "kontekst", "wzmianki", "budzenia", "scalanie", "brama",
    "strumien", "przebiegi", "prace", "karty", "obserwator", "tematy", "lustro", "omp_sesje", "czytnik_omp", "rozmowcy",
    "silnik", "komendy")})
trasy = load_script("hq/plugin/trasy_rozmow.py", "jarvo_test_cs_trasy")
P = "/api/plugins/jarvo-hq"
CZAT = "-1001234567890"
TOKEN = "123456:TEST-token-atrapy"
SESJA_OP, SESJA_GPU = "0a0b0c0d-op", "0a0b0c0d-gpu"


def czekaj(warunek, czas: float = 15.0, opis: str = ""):
    koniec = time.monotonic() + czas
    while time.monotonic() < koniec:
        wynik = warunek()
        if wynik:
            return wynik
        time.sleep(0.05)
    raise AssertionError(f"nie doczekałem się: {opis or warunek}")


class Telegram:
    """Wysyłka skrzynki omp do tematu (zamiast `jarvo telegram wyslij`)."""

    def __init__(self):
        self.wyslane: list[tuple[str, str, str]] = []

    def __call__(self, tekst, czat, watek):
        self.wyslane.append((tekst, czat, watek))
        return True


class Centrum:
    def __init__(self, tmp, monkeypatch):
        from jarvo import sesje_omp as so
        self.so = so
        dom = tmp / "dom"
        self.home = dom / "dane"
        self.jarvo = self.home / "jarvo"
        (self.jarvo / "state").mkdir(parents=True)
        (self.jarvo / "konfig").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(dom))
        k = tmp / "atrapa"
        monkeypatch.setenv("ATRAPA_OMP", str(k))
        monkeypatch.setenv("JARVO_OMP", str(atrapa_omp.zrob(k)))
        self.atrapa_omp = k
        self.tg_api = AtrapaTelegrama()
        monkeypatch.setenv("JARVO_TELEGRAM_API", self.tg_api.adres)
        monkeypatch.setattr(M.rozmowcy, "TEMAT_S", 0.2)
        M.omp_sesje._dzierzawy.clear()
        so.rdzen._dzierzawy.clear()
        monkeypatch.setattr(so, "BEZCZYNNA_S", 0.0)    # pętla testu woła skrzynki po kolei: bez czekania na ruch
        M.czytnik_omp.zapomnij()
        (self.home / ".env").write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\n", encoding="utf-8")
        klucze = {}
        for a in ("jarvo", "jarvo-jarodev"):
            klucze[a] = secrets.token_hex(8)
            (self.home / "profiles" / a).mkdir(parents=True)
            (self.home / "profiles" / a / ".env").write_text(f"API_SERVER_KEY={klucze[a]}\n", encoding="utf-8")
            db = atrapa_bramy.baza_profilu(self.home / "profiles" / a / "state.db")
            c = sqlite3.connect(db)
            c.execute("CREATE TABLE gateway_routing (scope TEXT NOT NULL DEFAULT '', session_key TEXT NOT NULL, "
                      "entry_json TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY (scope, session_key))")
            c.commit()
            c.close()
        fleet = tmp / "fleet.json"
        fleet.write_text(json.dumps({"agents": [
            {"name": "jarvo", "handle": "jarvo", "short": "Jarvo", "telegram_topic": "general"},
            {"name": "jarvo-jarodev", "handle": "jarodev", "short": "Jarodev", "telegram_topic": "jarodev"},
            {"name": "jarvo-web", "handle": "web", "short": "Web"}]}), encoding="utf-8")
        (self.jarvo / "state" / "telegram-grupy.json").write_text(json.dumps({"grupy": {CZAT: {
            "od": "2026-11-17", "watki": {"7": {"nazwa": "JARODEV"}, "5": {"nazwa": "OPERATOR"}, "11": {"nazwa": "KERNEL"}}}}}),
            encoding="utf-8")
        sesje = {}
        for klucz, nazwa, sid, kol, watek in (("op", "Operator", SESJA_OP, 0, "5"), ("gpu", "Kernel", SESJA_GPU, 2, "11")):
            (dom / klucz / "sesje").mkdir(parents=True)
            sesje[klucz] = {"nazwa": nazwa, "skrzynka": f"~/{klucz}/skrzynka", "czat": CZAT, "watek": watek,
                            "panel": {"zaplecze": "omp", "sesje": f"~/{klucz}/sesje", "sesja": sid, "cwd": str(tmp),
                                      "opis": f"{nazwa} opis", "kolejnosc": kol, "potwierdzenia": klucz == "op"}}
        (self.jarvo / "konfig" / "sesje.json").write_text(json.dumps(sesje), encoding="utf-8")
        self.agenci = M.agenci.Agenci(fleet, self.jarvo / "state" / "agenci.json", e2e=lambda: True)
        self.brama = atrapa_bramy.AtrapaBramy(self.home, klucze)
        self.hub = M.strumien.Hub(zycie=1.5, ping=0.5)
        self.logi: list[str] = []
        self.sil = M.silnik.Silnik(moduly=M, home=self.home, jarvo_dir=self.jarvo, api_base="http://brama.test",
                                   agenci=self.agenci, hub=self.hub, log=self.logi.append, limit=8,
                                   http=httpx.AsyncClient(transport=self.brama.transport()), odstep_odpytania=0.2)
        self.sil.start(czekaj=10)
        assert self.sil.dziala(), self.sil.blad
        app = FastAPI()
        router = APIRouter(route_class=M.ochrona.Trasa)
        trasy.dolacz(router, m=M, silnik=lambda: self.sil, hub=self.hub, agenci=self.agenci,
                     inbox=self.jarvo / "inbox", log=self.logi.append)
        app.include_router(router, prefix=P)
        self.k = TestClient(app, headers={"X-Jarvo-Request": "1"})
        # usługa skrzynki (`jarvo sesja <klucz> skrzynka`): w teście pętla w wątku
        self.tg = Telegram()
        self._stop = threading.Event()
        self._skrzynka = threading.Thread(target=self._petla_skrzynki, daemon=True)
        self._skrzynka.start()

    def _petla_skrzynki(self):
        while not self._stop.is_set():
            for w in self.so.rdzen.wpisy(self.home).values():
                try:
                    self.so.skrzynka(w, self.tg)
                except Exception as e:                 # pragma: no cover (widać w teście)
                    self.logi.append(f"skrzynka: {e!r}")
            self._stop.wait(0.1)

    def zamknij(self):
        self._stop.set()
        self._skrzynka.join(5)
        self.sil.zamknij()
        self.brama.zamknij()
        self.tg_api.zamknij()

    # ---- skróty
    def rozmowcy(self) -> dict:
        return {r["klucz"]: r for r in self.k.get(f"{P}/rozmowcy").json()["rozmowcy"]}

    def wid(self, klucz: str) -> str:
        return self.rozmowcy()[klucz]["watek_id"]

    def os(self, klucz: str) -> list[dict]:
        r = self.k.get(f"{P}/rozmowy/{self.wid(klucz)}/os")
        assert r.status_code == 200, r.text
        return r.json()["pozycje"]

    def wyslij(self, klucz: str, tekst: str) -> dict:
        r = self.k.post(f"{P}/rozmowy/{self.wid(klucz)}/wiadomosci", json={"tekst": tekst, "klucz": secrets.token_hex(6)})
        assert r.status_code == 202, r.text
        return r.json()

    def do_stanu(self, pid: str, *stany, czas: float = 20.0) -> dict:
        return czekaj(lambda: (lambda p: p if p["stan"] in stany else None)(self.sil.db.przebieg(pid)), czas,
                      f"{pid} → {stany}")

    def ramki(self, typ: str) -> list[dict]:
        out = []
        with self.hub._lock:
            bufor = list(self.hub._bufor)
        for _s, _t, _w, ramka in bufor:
            linie = ramka.decode().splitlines()
            if linie[1].split(": ", 1)[1] == typ:
                out.append(json.loads(linie[2].split(": ", 1)[1]))
        return out

    def tura_z_telegrama_hermes(self, profil: str, watek: str, sid: str, tekst: str, odp: str):
        """Brama Hermesa przyjmuje wiadomość w temacie: trasa tematu → sesja, wiersz właściciela i odpowiedź."""
        db = self.home / "profiles" / profil / "state.db"
        c = sqlite3.connect(db)
        try:
            if not c.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone():
                c.execute("INSERT INTO sessions (id, source, started_at, chat_id, thread_id) VALUES (?, 'telegram', ?, ?, ?)",
                          (sid, time.time(), CZAT, watek))
            klucz = f"agent:{profil}:telegram:group:{CZAT}:{watek}"
            c.execute("INSERT OR REPLACE INTO gateway_routing VALUES (?, ?, ?, ?)",
                      (str(self.home), klucz, json.dumps({"session_id": sid}), time.time()))
            c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
                      (sid, tekst, time.time()))
            c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'assistant', ?, ?)",
                      (sid, odp, time.time() + 0.01))
            c.commit()
        finally:
            c.close()

    def tura_z_telegrama_omp(self, klucz: str, tekst: str):
        """Hak jarvo-sesje kładzie wiadomość z tematu do skrzynki wpisu."""
        w = self.so.rdzen.wpisy(self.home)[klucz]
        w.katalogi()
        self.so.rdzen.zapisz_atomowo(w.nowe / f"tg-{secrets.token_hex(3)}.json", {
            "dopisek": klucz, "tekst": tekst, "czas": "2026-11-17 12:00:00", "chat_id": CZAT, "watek": w.watek,
            "media": []})


@pytest.fixture
def c(tmp_path, monkeypatch):
    swiat = Centrum(tmp_path, monkeypatch)
    yield swiat
    swiat.zamknij()


def _wlasciciel(os_, tekst):
    return [x for x in os_ if x["rodzaj"] == "wlasciciel" and tekst in (x.get("tekst") or "")]


def _agent(os_, tekst):
    return [x for x in os_ if x["rodzaj"] == "agent" and tekst in (x.get("tekst") or "")]


def test_czterech_rozmowcow_w_kolejnosci_i_app(c):
    r = c.k.get(f"{P}/rozmowcy").json()["rozmowcy"]
    assert [x["nazwa"] for x in r] == ["Operator", "Jarvo", "Kernel", "Jarodev"]
    assert [x["klucz"] for x in r] == ["s:op", "f:jarvo", "s:gpu", "f:jarvo-jarodev"]
    jarvo, op = r[1], r[0]
    assert jarvo["zaplecze"] == "hermes" and jarvo["temat"] is True and jarvo["lustro"] is True
    assert op["zaplecze"] == "omp" and op["potwierdzenia"] is True and op["opis"] == "Operator opis"
    assert all(x["watek_id"] for x in r)
    czekaj(lambda: all(x["stan"] == "wolny" for x in c.rozmowcy().values()), opis="stan wolny u wszystkich")
    # lista rozmów (Inne rozmowy) nie zawiera wątków rozmówców; nie da się ich usunąć ani zarchiwizować
    lista = c.k.get(f"{P}/rozmowy").json()
    assert not any(w.get("rozmowca") for w in lista.get("watki", []))
    assert c.k.delete(f"{P}/rozmowy/{jarvo['watek_id']}").status_code == 409
    assert c.k.patch(f"{P}/rozmowy/{jarvo['watek_id']}", json={"archiwum": True}).status_code == 409
    # PATCH /rozmowcy: lustro i kolejność, zdarzenie rozmowcy.lista
    z = c.k.patch(f"{P}/rozmowcy/f:jarvo", json={"lustro": False}).json()["rozmowca"]
    assert z["lustro"] is False and c.ramki("rozmowcy.lista")
    assert c.k.patch(f"{P}/rozmowcy/f:nie", json={"lustro": False}).status_code == 404
    assert c.k.patch(f"{P}/rozmowcy/..", json={"lustro": False}).status_code == 404


def test_hermes_telegram_do_panelu_i_panel_do_telegrama(c):
    # 1. Telegram → panel: wiadomość w temacie JARODEV, sesja tematu staje się sesją wątku (przejęcie)
    c.tura_z_telegrama_hermes("jarvo-jarodev", "7", "tg-dev-1", "z telefonu: sprawdź build", "Build zielony.")
    os_ = czekaj(lambda: (lambda o: o if _agent(o, "Build zielony.") else None)(c.os("f:jarvo-jarodev")),
                 opis="oś z tematu")
    (moja,) = _wlasciciel(os_, "z telefonu: sprawdź build")
    assert moja["zrodlo"] == "telegram" and moja["agent"] is None
    assert len(_agent(os_, "Build zielony.")) == 1 and not any(x["rodzaj"] == "obca" for x in os_)
    assert c.tg_api.wyslane == []                         # Telegram → panel nie wraca do Telegrama
    # 2. panel → Telegram: ta sama sesja tematu, lustro „🖥 prośba” + odpowiedź, jeden raz
    pid = c.wyslij("f:jarvo-jarodev", "a z panelu: wdrażamy?")["przebiegi"][0]["id"]
    p = c.do_stanu(pid, "gotowe")
    assert p["sesja_id"] == "tg-dev-1" and p["agent"] == "jarvo-jarodev"
    czekaj(lambda: len(c.tg_api.wyslane) >= 2, opis="lustro w temacie")
    time.sleep(2.5)                                        # następna runda pętli rozmówców nie wysyła drugi raz
    assert c.tg_api.teksty() == ["🖥 a z panelu: wdrażamy?", "Odpowiedź: a z panelu: wdrażamy?"]
    assert {w["chat_id"] for w in c.tg_api.wyslane} == {CZAT} and {w["message_thread_id"] for w in c.tg_api.wyslane} == {7}
    os_ = c.os("f:jarvo-jarodev")
    assert len(_wlasciciel(os_, "a z panelu: wdrażamy?")) == 1 and len(_agent(os_, "Odpowiedź: a z panelu")) == 1
    assert len(_wlasciciel(os_, "z telefonu")) == 1 and not any(x["rodzaj"] == "obca" for x in os_)
    # wejście agenta bez bloku kontekstu (jeden rozmówca nic nie przegapia)
    assert c.brama.runs("jarvo-jarodev")[-1]["cialo"]["input"] == "a z panelu: wdrażamy?"
    # 3. rotacja sesji tematu (/new): linia „Nowa sesja”, kolejna wysyłka idzie do nowej sesji
    db = c.home / "profiles" / "jarvo-jarodev" / "state.db"
    k = sqlite3.connect(db)
    k.execute("INSERT INTO sessions (id, source, started_at) VALUES ('tg-dev-2', 'telegram', ?)", (time.time(),))
    k.execute("UPDATE gateway_routing SET entry_json = ?", (json.dumps({"session_id": "tg-dev-2", "prev_session_id": "tg-dev-1"}),))
    k.commit()
    k.close()
    czekaj(lambda: any(x["rodzaj"] == "system" and "Nowa sesja" in (x.get("tekst") or "") for x in c.os("f:jarvo-jarodev")),
           opis="linia Nowa sesja")
    pid = c.wyslij("f:jarvo-jarodev", "po resecie")["przebiegi"][0]["id"]
    assert c.do_stanu(pid, "gotowe")["sesja_id"] == "tg-dev-2"


def test_hermes_temat_bez_sesji_zaczyna_sesje_panelu(c):
    pid = c.wyslij("f:jarvo", "pierwsza z panelu")["przebiegi"][0]["id"]
    assert c.do_stanu(pid, "gotowe")["sesja_id"] == "jarvo_r_jarvo"
    czekaj(lambda: len(c.tg_api.wyslane) >= 2, opis="lustro General")
    assert "message_thread_id" not in c.tg_api.wyslane[0]


def test_hermes_tura_z_telegrama_daje_stan_pracuje(c):
    c.tura_z_telegrama_hermes("jarvo", "1", "tg-j-1", "hej", "cześć")
    czekaj(lambda: c.sil.db.czlonek(c.wid("f:jarvo"), "jarvo"), opis="członek z sesji tematu")
    c.brama.dzierzawa("jarvo", "tg-j-1", platforma="telegram")
    czekaj(lambda: c.rozmowcy()["f:jarvo"]["stan"] == "pracuje", opis="pracuje (tura z Telegrama)")
    assert any(e["klucz"] == "f:jarvo" and e["stan"] == "pracuje" for e in c.ramki("rozmowca.stan"))
    c.brama.zwolnij_dzierzawe("jarvo", "tg-j-1")
    czekaj(lambda: c.rozmowcy()["f:jarvo"]["stan"] == "wolny", opis="wolny")


def test_omp_panel_do_telegrama_i_telegram_do_panelu(c):
    # 1. panel → skrzynka → tura omp → odpowiedź w panelu i lustro w temacie OPERATOR
    out = c.wyslij("s:op", "sprawdź dysk")
    pid = out["przebiegi"][0]["id"]
    p = c.do_stanu(pid, "gotowe")
    assert p["zaplecze"] == "omp"
    czekaj(lambda: len(c.tg.wyslane) >= 2, opis="lustro omp")
    assert c.tg.wyslane == [("🖥 sprawdź dysk", CZAT, "5"), ("Operator\n\nGotowe, zrobione.", CZAT, "5")]
    os_ = czekaj(lambda: (lambda o: o if _agent(o, "Gotowe, zrobione.") else None)(c.os("s:op")), opis="oś omp")
    assert len(_wlasciciel(os_, "sprawdź dysk")) == 1                 # wpis panelu, bez dubla z pliku sesji
    assert _agent(os_, "Gotowe, zrobione.")[0]["przebieg_id"] == pid   # żywy dymek przebiegu znika (bez dubla w UI)
    assert any(x["rodzaj"] == "kroki" and x["kroki"][0]["detail"] == "Sprawdzam GPU" for x in os_)
    assert "SEKRET" not in json.dumps(os_)
    # 2. Telegram → skrzynka → ta sama sesja; panel widzi dymek 📱 na żywo (watek.os), bez lustra 🖥
    przed = len(c.ramki("watek.os"))
    c.tura_z_telegrama_omp("op", "z telefonu: restart?")
    os_ = czekaj(lambda: (lambda o: o if _wlasciciel(o, "z telefonu: restart?") else None)(c.os("s:op")),
                 opis="dymek z Telegrama")
    (tg,) = _wlasciciel(os_, "z telefonu: restart?")
    assert tg["zrodlo"] == "telegram"
    czekaj(lambda: len(c.ramki("watek.os")) > przed, opis="watek.os na żywo")
    czekaj(lambda: len(c.tg.wyslane) >= 3, opis="odpowiedź do tematu")
    assert c.tg.wyslane[2] == ("Operator\n\nGotowe, zrobione.", CZAT, "5")
    assert len(_agent(c.os("s:op"), "Gotowe, zrobione.")) == 2 and len(_wlasciciel(c.os("s:op"), "sprawdź dysk")) == 1
    # Telegram omp nie idzie przez lustro panelu (Bot API atrapy pusty)
    assert c.tg_api.wyslane == []


def test_omp_szczegoly_kroku(c):
    """Rozwinięty krok sesji omp (GET /rozmowy/{id}/krok): argumenty i wynik z pliku sesji na żądanie (oś ich nie
    niesie), sekrety ukryte, odczyt tylko z panelu, krok z obcego wątku i zły adres = 404."""
    pid = c.wyslij("s:op", "sprawdź dysk")["przebiegi"][0]["id"]
    c.do_stanu(pid, "gotowe")
    os_ = czekaj(lambda: (lambda o: o if _agent(o, "Gotowe, zrobione.") else None)(c.os("s:op")), opis="oś omp")
    (krok,) = [k for x in os_ if x["rodzaj"] == "kroki" for k in x["kroki"]]
    assert krok["ref"].startswith("o:") and krok["ref"].endswith(":c1") and "SEKRET" not in json.dumps(os_)
    url = f"{P}/rozmowy/{c.wid('s:op')}/krok"
    r = c.k.get(url, params={"ref": krok["ref"]})
    assert r.status_code == 200, r.text
    k = r.json()["krok"]
    assert (k["narzedzie"], k["intencja"], k["argumenty"]) == ("bash", "Sprawdzam GPU",
                                                              [{"klucz": "command", "wartosc": "cat SEKRET"}])
    assert k["wynik"] == "SEKRET" and k["gotowy"] and not k["blad"] and not k["przyciete"]
    assert c.k.get(url, params={"ref": krok["ref"]}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    for wid, ref in ((c.wid("s:gpu"), krok["ref"]), (c.wid("s:op"), "o:brak:c1"), (c.wid("s:op"), "o:../x:c1"),
                     (c.wid("s:op"), "h:jarvo:rozmowa:c1")):
        r = c.k.get(f"{P}/rozmowy/{wid}/krok", params={"ref": ref})
        assert r.status_code == 404 and r.json()["blad"]["kod"] == "brak", (ref, r.status_code)
    # krok z sekretami dopisany do pliku sesji tak jak zapisuje omp (JSON bez spacji): w panelu ukryte
    plik = c.home.parent / "op" / "sesje" / f"2026_{SESJA_OP}.jsonl"
    lisc = (c.atrapa_omp / f"lisc_{SESJA_OP}").read_text()
    token, haslo = "ghp_" + "Q" * 36, "Tajne123haslo"
    with plik.open("a") as f:
        for e in ({"type": "message", "id": "s1a", "parentId": lisc, "timestamp": "2026-11-20T10:00:00Z", "message": {
                      "role": "assistant", "content": [
                          {"type": "thinking", "thinking": f"Użyję {token}"},
                          {"type": "toolCall", "id": "c7", "name": "bash", "intent": "Pobieram",
                           "arguments": {"command": f"curl -H 'Authorization: Bearer {haslo}' https://x"}}]}},
                  {"type": "message", "id": "s1r", "parentId": "s1a", "timestamp": "2026-11-20T10:00:02Z", "message": {
                      "role": "toolResult", "toolCallId": "c7", "toolName": "bash",
                      "content": [{"type": "text", "text": f"PASSWORD={haslo}\nGH_TOKEN={token}"}], "isError": False}}):
            f.write(json.dumps(e, separators=(",", ":")) + "\n")
    (krok,) = [k for x in c.os("s:op") if x["rodzaj"] == "kroki" for k in x["kroki"] if k["ref"].endswith(":c7")]
    r = c.k.get(url, params={"ref": krok["ref"]})
    assert r.status_code == 200 and token not in r.text and haslo not in r.text, r.text
    k = r.json()["krok"]
    assert k["wynik"] == "PASSWORD=[ukryte]\nGH_TOKEN=[ukryte]" and k["mysl"] == "Użyję [ukryte]" and k["czas_ms"] == 2000


def test_omp_terminal_kolejka_i_potwierdzenie(c):
    # sesja trzymana w terminalu (dzierżawa omp): stan `terminal`, wiadomość czeka, potem tura rusza sama
    (c.atrapa_omp / "held.json").write_text(json.dumps([SESJA_GPU]))
    czekaj(lambda: c.rozmowcy()["s:gpu"]["stan"] == "terminal", opis="w terminalu")
    pid = c.wyslij("s:gpu", "[plan] zrestartuj bramę")["przebiegi"][0]["id"]
    czekaj(lambda: (lambda p: (p["stan"], p["powod"]))(c.sil.db.przebieg(pid)) == ("przyjety", "terminal"),
           opis="w skrzynce, sesja w terminalu")
    time.sleep(1.0)
    assert c.sil.db.przebieg(pid)["stan"] == "przyjety"
    czekaj(lambda: c.rozmowcy()["s:gpu"]["czeka"] == 1, opis="1 wiadomość czeka")
    assert any(e["klucz"] == "s:gpu" and e["stan"] == "terminal" for e in c.ramki("rozmowca.stan"))
    (c.atrapa_omp / "held.json").write_text("[]")
    c.do_stanu(pid, "gotowe", czas=30)
    os_ = czekaj(lambda: (lambda o: o if _agent(o, "Plan: restart bramy.") else None)(c.os("s:gpu")), opis="plan")
    (plan,) = _agent(os_, "Plan: restart bramy.")
    assert plan["czeka_na_tak"] is True and "[[czeka-na-tak]]" not in plan["tekst"]
    czekaj(lambda: c.rozmowcy()["s:gpu"]["stan"] == "wolny", opis="wolny po turze")


def test_omp_enter_w_trakcie_tury_dopisuje(c, monkeypatch):
    """Enter w trakcie tury sesji omp (`tryb_kolejki: "dopisz"`): wiadomość idzie do skrzynki przez `omp_sesje.dopisz`
    (steer RPC), przebieg `dopisany` → `wlaczony`; gdy skrzynka puści ją jako własną turę (tryb `kolejka`), przebieg
    idzie `przyjety` → koniec jak zwykła wiadomość. Skrzynka zastąpiona atrapą stanów (bez procesu omp)."""
    om = M.omp_sesje
    stany, dopiski = {}, []

    def wyslij(w, tekst, klucz, media=(), lustro=True):
        stany[klucz] = {"stan": "pracuje", "tura": "t1"}
        return {"nowy": True}

    def dopisz(w, tekst, klucz, media=(), lustro=True):
        if not stany:                       # bez tury: panel kładzie dopisek, skrzynka bierze go jak zwykłą wiadomość
            return wyslij(w, tekst, klucz, media, lustro)
        tryb = "kolejka" if "osobno" in tekst else "steer"
        dopiski.append((tekst, tryb))
        stany[klucz] = {"stan": "wlaczony", "tura": "t1"} if tryb == "steer" else {"stan": "kolejka"}
        return {"nowy": True, "tryb": tryb}

    monkeypatch.setattr(om, "wyslij", wyslij)
    monkeypatch.setattr(om, "przebieg", lambda w, klucz: stany.get(klucz, {"stan": "brak"}))
    monkeypatch.setattr(om, "ogon", lambda w, tura, od=0: ([], od))
    monkeypatch.setattr(om, "dopisz", dopisz, raising=False)
    wid = c.wid("s:op")
    pid = c.wyslij("s:op", "długa praca")["przebiegi"][0]["id"]
    c.do_stanu(pid, "pracuje")

    def enter(tekst):
        r = c.k.post(f"{P}/rozmowy/{wid}/wiadomosci", json={"tekst": tekst, "klucz": secrets.token_hex(6),
                                                             "tryb_kolejki": "dopisz"})
        assert r.status_code == 202, r.text
        return r.json()

    d = enter("i jeszcze to")
    (q,) = d["przebiegi"]
    assert q["stan"] == "dopisany" and q["dopisany_do"] == pid and d["wpis"]["dane"]["dopisane_do"] == pid
    assert "i jeszcze to" in dopiski[0][0] and not d["ostrzezenia"]
    c.do_stanu(q["id"], "wlaczony")
    d = enter("osobno proszę")
    (q2,) = d["przebiegi"]
    assert q2["stan"] == "przyjety" and not q2.get("dopisany_do") and "dopisane_do" not in d["wpis"]["dane"]
    stany[q2["id"]] = {"stan": "gotowe", "odpowiedz": "ok"}
    c.do_stanu(q2["id"], "gotowe")
    stany[pid] = {"stan": "gotowe", "odpowiedz": "zrobione"}
    c.do_stanu(pid, "gotowe")

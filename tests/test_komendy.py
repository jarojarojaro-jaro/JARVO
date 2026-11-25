"""Komendy po „/” w panelu (hq/plugin/komendy.py, docs/HQ.md „Komendy”): komenda czy zwykły tekst (wektory wspólne
z 33-komendy.js), komenda nigdy nie idzie do agenta (409 `komenda` na trasie wiadomości), `/model` (lista z bramy,
wybór sesji w ciele `/v1/runs`, `--global` przez zapis profilu, omp przez model.json skrzynki), `/new` (rotacja sesji),
`/stop`, `/usage`, nieznana i niedostępna komenda, powtórka z tym samym kluczem; z atrapą bramy i prawdziwym silnikiem;
`/compact` i komendy skrzynki omp, licznik rozmowy (`GET /rozmowy/{id}/licznik`) i `/context`."""
from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import APIRouter  # noqa: E402

import test_silnik_rozmow as T  # noqa: E402

M, P, czekaj = T.M, T.P, T.czekaj
K = M.komendy
WEKTORY = json.loads((Path(__file__).resolve().parent / "data" / "komendy.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------------- komenda czy tekst

@pytest.mark.parametrize("tekst,oczekiwane", WEKTORY["komendy"])
def test_komenda_rozpoznana(tekst, oczekiwane):
    assert K.parsuj(tekst) == tuple(oczekiwane)


@pytest.mark.parametrize("tekst", WEKTORY["tekst"])
def test_zwykly_tekst_to_nie_komenda(tekst):
    assert K.parsuj(tekst) is None


def test_katalog_hermesa_dzialajace_najpierw_reszta_rejestru_z_powodem():
    rejestr = [{"nazwa": "new", "aliasy": ["reset"], "opis_en": "x"}, {"nazwa": "retry", "aliasy": [], "opis_en": "Retry"},
               {"nazwa": "commands", "aliasy": [], "opis_en": "Browse"}]
    kat = K.katalog("hermes", rejestr)
    nazwy = [c["nazwa"] for c in kat]
    assert nazwy[:5] == ["model", "new", "stop", "usage", "status"] and nazwy.count("new") == 1
    assert "commands" not in nazwy                       # alias /help panelu, nie druga pozycja
    retry = next(c for c in kat if c["nazwa"] == "retry")
    assert not retry["dziala"] and not retry["panel"] and retry["powod"]
    compact = next(c for c in kat if c["nazwa"] == "compact")
    assert not compact["dziala"] and "kompresji" in compact["powod"] and "compress" in compact["aliasy"]
    assert next(c for c in kat if c["nazwa"] == "context")["dziala"]
    omp = {c["nazwa"]: c for c in K.katalog("omp", rejestr, [{"nazwa": "compact", "opis": "x"},
                                                              {"nazwa": "export", "opis": "Eksport sesji"}])}
    assert "retry" not in omp and not omp["new"]["dziala"] and omp["model"]["dziala"] and omp["compact"]["dziala"]
    assert omp["export"]["dziala"] and not omp["export"]["panel"]       # komenda zgłoszona przez skrzynkę


def test_znajdz_model():
    d = K.dostawcy_bramy({"providers": [
        {"slug": "openai-codex", "name": "OpenAI Codex", "is_current": True, "models": ["gpt-5.4", "gpt-5.4-mini"]},
        {"slug": "openrouter", "name": "OpenRouter", "models": ["openai/gpt-5.4", "anthropic/claude-opus-5"]},
        {"slug": "custom:lan", "name": "LAN", "models": ["qwen"], "total_models": 40},
        {"slug": "anthropic", "name": "Anthropic", "models": ["claude-opus-5"], "authenticated": False},
        {"slug": "nous", "name": "Nous", "models": [], "source": "canonical"}]})
    assert [x["slug"] for x in d] == ["openai-codex", "openrouter", "custom:lan"]   # bez wylogowanych i szkieletów
    assert K.znajdz_model(d, "GPT-5.4")[0] == {"model": "gpt-5.4", "provider": "openai-codex", "nazwa": "OpenAI Codex"}
    assert K.znajdz_model(d, "openrouter/openai/gpt-5.4")[0]["provider"] == "openrouter"   # dostawca/model
    assert K.znajdz_model(d, "openai/gpt-5.4")[0]["provider"] == "openrouter"              # nazwa z ukośnikiem
    assert K.znajdz_model(d, "opus")[0]["model"] == "anthropic/claude-opus-5"
    wybor, kandydaci = K.znajdz_model(d, "gpt")
    assert wybor is None and len(kandydaci) == 3
    assert K.znajdz_model(d, "llama-70b", "custom:lan")[0] == {"model": "llama-70b", "provider": "custom:lan", "nazwa": "LAN"}
    assert K.znajdz_model(d, "nie-ma")[0] is None and K.znajdz_model(d, "nie-ma")[1] == []


def test_argumenty_modelu():
    a = K.argumenty_modelu("opus --provider anthropic --global")
    assert (a.cel, a.dostawca, a.globalnie, a.bledy) == ("opus", "anthropic", True, [])
    assert K.argumenty_modelu("x --once").bledy == ["--once"]
    assert K.argumenty_modelu("--provider=openrouter").dostawca == "openrouter"


# ----------------------------------------------------------------------------------------------- trasy z silnikiem

@pytest.fixture
def swiat(tmp_path):
    s = T.Swiat(tmp_path)
    s.zapisy = []
    router = APIRouter(route_class=M.ochrona.Trasa)
    wyk = K.Wykonawca(m=M, rejestr=lambda: [{"nazwa": "retry", "aliasy": [], "opis_en": "Retry"}],
                      zapis_globalny=lambda profil, dostawca, model: s.zapisy.append((profil, dostawca, model)),
                      okno=lambda profil, wybrany: {"model": (wybrany or {}).get("model") or "gpt-5.4",
                                                    "provider": "openai-codex", "okno": 100_000})
    K.dolacz(router, m=M, trasy=T.trasy, silnik=lambda: s.sil, agenci=s.agenci, hub=s.hub, log=s.logi.append, wykonawca=wyk)
    s.k.app.include_router(router, prefix=P)
    yield s
    s.zamknij()


def _komenda(s, tekst: str, watek: str | None = None, **kw) -> dict:
    r = s.k.post(f"{P}/komendy", json={"tekst": tekst, "klucz": kw.pop("klucz", secrets.token_hex(6)), "watek": watek, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _watek_po_turze(s, tekst: str = "cześć") -> tuple[str, dict]:
    odp = s.nowy(tekst)
    s.do_stanu(odp["przebiegi"][0]["id"], "gotowe")
    return odp["watek"]["id"], odp


def test_wiadomosc_z_komenda_nie_idzie_do_agenta(swiat):
    wid, _ = _watek_po_turze(swiat)
    przed = len(swiat.brama.runs())
    for tekst in ("/model opus", "  /new", "@teste2ea /stop", "/nieznana"):
        r = swiat.wyslij(wid, tekst)
        assert r.status_code == 409 and r.json()["blad"]["kod"] == "komenda", (tekst, r.text)
    r = swiat.k.post(f"{P}/rozmowy", json={"wiadomosc": {"tekst": "/model", "klucz": secrets.token_hex(6)}})
    assert r.status_code == 409 and r.json()["blad"]["kod"] == "komenda"
    r = swiat.wyslij(wid, "//model to zwykły tekst")                          # „//” = wiadomość do agenta
    assert r.status_code == 202
    swiat.do_stanu(r.json()["przebiegi"][0]["id"], "gotowe")
    assert len(swiat.brama.runs()) == przed + 1


def test_model_lista_zmiana_sesji_i_cialo_przebiegu(swiat):
    wid, _ = _watek_po_turze(swiat)
    odp = _komenda(swiat, "/model", wid)
    w = odp["wynik"]
    assert w["ok"] and "gpt-5.4" in w["wynik"] and "domyślny agenta" in w["wynik"] and "Nous" not in w["wynik"]
    assert {(x["provider"], x["model"]) for x in w["wybor"]} == {("openai-codex", "gpt-5.4"), ("openai-codex", "gpt-5.4-mini"),
                                                                 ("anthropic", "claude-opus-5"), ("anthropic", "claude-sonnet-5")}
    assert next(x for x in w["wybor"] if x["model"] == "gpt-5.4")["biezacy"]
    wpis = odp["wpis"]
    assert wpis["rodzaj"] == "system" and wpis["dane"]["typ"] == "komenda" and wpis["dane"]["polecenie"] == "/model"
    assert any(d["wpis"]["id"] == wpis["id"] for _t, d in swiat.ramki("watek.wpis"))

    w = _komenda(swiat, "/model opus", wid)["wynik"]
    assert w["ok"] and "claude-opus-5" in w["wynik"]
    assert swiat.sil.db.model_czlonka(wid, "jarvo") == {"model": "claude-opus-5", "provider": "anthropic"}
    r = swiat.wyslij(wid, "dalej")
    assert r.status_code == 202
    pid = r.json()["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "gotowe")
    cialo = swiat.brama.runs("jarvo")[-1]["cialo"]
    assert (cialo["model"], cialo["provider"]) == ("claude-opus-5", "anthropic")
    assert "Model tej rozmowy" not in json.dumps(cialo["input"], ensure_ascii=False)   # wynik komendy poza kontekstem
    assert swiat.p(pid)["payload"]["model"] == {"model": "claude-opus-5", "provider": "anthropic"}

    w = _komenda(swiat, "/model gpt", wid)["wynik"]                          # kilka pasuje: wybór zamiast zgadywania
    assert not w["ok"] and len(w["wybor"]) == 2
    w = _komenda(swiat, "/model gpt-5.4", wid)["wynik"]                      # domyślny agenta: wybór rozmowy znika
    assert w["ok"] and swiat.sil.db.model_czlonka(wid, "jarvo") is None
    r = swiat.wyslij(wid, "jeszcze")
    swiat.do_stanu(r.json()["przebiegi"][0]["id"], "gotowe")
    assert "model" not in swiat.brama.runs("jarvo")[-1]["cialo"]


def test_model_global_i_bez_rozmowy(swiat):
    w = _komenda(swiat, "/model sonnet")["wynik"]                            # ekran startu: bez wątku
    assert not w["ok"] and "--global" in w["wynik"]
    odp = _komenda(swiat, "/model claude-sonnet-5 --global", agent="jarvo")
    assert odp["wynik"]["ok"] and odp["wpis"] is None
    assert swiat.zapisy == [(swiat.home / "profiles" / "jarvo", "anthropic", "claude-sonnet-5")]
    assert not _komenda(swiat, "/model x --once")["wynik"]["ok"]


def test_new_zaczyna_nowa_sesje(swiat):
    wid, _ = _watek_po_turze(swiat)
    stara = swiat.sil.db.czlonek(wid, "jarvo")["sesja_tip"]
    w = _komenda(swiat, "/new", wid)["wynik"]
    assert w["ok"] and "Nowa sesja" in w["wynik"]
    nowa = swiat.sil.db.czlonek(wid, "jarvo")["sesja_tip"]
    assert nowa != stara and nowa.startswith(f"jarvo_{wid}_jarvo_n")
    assert [x["powod"] for x in swiat.sil.db.sesje_watku(wid, agent="jarvo")] == ["start", "rotacja"]
    assert swiat.brama.sesja("jarvo", nowa)
    r = swiat.wyslij(wid, "od nowa")
    swiat.do_stanu(r.json()["przebiegi"][0]["id"], "gotowe")
    assert swiat.brama.runs("jarvo")[-1]["cialo"]["session_id"] == nowa


def test_stop_i_usage(swiat):
    wid, _ = _watek_po_turze(swiat)
    assert "Nic teraz nie pracuje" in _komenda(swiat, "/stop", wid)["wynik"]["wynik"]
    r = swiat.wyslij(wid, "[wolno:6] długa praca")
    pid = r.json()["przebiegi"][0]["id"]
    swiat.do_stanu(pid, "pracuje")
    w = _komenda(swiat, "/stop", wid)["wynik"]
    assert w["ok"] and "Zatrzymuję" in w["wynik"]
    swiat.do_stanu(pid, "zatrzymane")
    w = _komenda(swiat, "/usage", wid)["wynik"]
    assert w["ok"] and "1 tur" in w["wynik"]           # atrapa: usage tylko z ukończonej tury (1 + 1 token)
    w = _komenda(swiat, "/status", wid)["wynik"]
    assert w["ok"] and "gpt-5.4" in w["wynik"] and "Nic teraz nie pracuje" in w["wynik"]


def test_nieznana_niedostepna_i_powtorka(swiat):
    wid, _ = _watek_po_turze(swiat)
    w = _komenda(swiat, "/foo", wid)["wynik"]
    assert not w["ok"] and "Nie znam komendy" in w["wynik"]
    w = _komenda(swiat, "/retry", wid)["wynik"]                              # z rejestru Hermesa: powód zamiast ciszy
    assert not w["ok"] and "Telegram" in w["wynik"]
    w = _komenda(swiat, "/compact", wid)["wynik"]
    assert not w["ok"] and "kompresji" in w["wynik"]
    klucz = secrets.token_hex(6)
    a = _komenda(swiat, "/help", wid, klucz=klucz)
    b = _komenda(swiat, "/help", wid, klucz=klucz)
    assert a["wpis"]["id"] == b["wpis"]["id"] and "/model" in a["wynik"]["wynik"]
    komendy = [x for x in swiat.sil.db.wpisy(wid) if (x.get("dane") or {}).get("typ") == "komenda"]
    assert len(komendy) == 4
    assert swiat.k.post(f"{P}/komendy", json={"tekst": "zwykły tekst", "klucz": secrets.token_hex(6)}).status_code == 422
    kat = swiat.k.get(f"{P}/komendy", params={"watek": wid}).json()
    assert kat["zaplecze"] == "hermes" and kat["agent"] == "jarvo" and kat["komendy"][0]["nazwa"] == "model"
    assert swiat.k.get(f"{P}/komendy", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


# ----------------------------------------------------------------------------------------------- omp

def _wpis_omp(tmp_path):
    sesje = tmp_path / "sesje"
    sesje.mkdir()
    linie = [{"type": "session", "id": "s1", "version": 3},
             {"type": "message", "id": "a", "parentId": None, "message": {
                 "role": "assistant", "provider": "anthropic", "model": "claude-opus-5",
                 "usage": {"input": 10, "output": 20, "cacheRead": 100, "cacheWrite": 5, "cost": {"total": 0.25}}}},
             {"type": "message", "id": "b", "parentId": "a", "message": {
                 "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-5",
                 "usage": {"input": 1, "output": 2, "cacheRead": 300, "cacheWrite": 0, "cost": {"total": 0.05}}}}]
    (sesje / "2026_abcdef-1234.jsonl").write_text("\n".join(json.dumps(x) for x in linie) + "\n", encoding="utf-8")
    return M.omp_sesje.Wpis(klucz="op", nazwa="Operator", skrzynka=tmp_path / "skrzynka", sesje=sesje,
                            sesja="abcdef-1234", omp_arg=["--no-context-files", "--model", "anthropic/claude-sonnet-5"])


def test_omp_model_usage_i_niedostepne(tmp_path):
    w = _wpis_omp(tmp_path)
    modele = [{"model": "anthropic/claude-opus-5", "provider": "anthropic", "nazwa": "Claude Opus 5"},
              {"model": "anthropic/claude-sonnet-5", "provider": "anthropic", "nazwa": "Claude Sonnet 5"},
              {"model": "commandcode/opus-mini", "provider": "commandcode", "nazwa": "Opus mini"}]
    wyk = K.Wykonawca(m=M, lista_omp=lambda: modele, rejestr=lambda: [])
    k = K.Kontekst(sil=None, watek=None, agent="op", nazwa="Operator", zaplecze="omp", wpis_omp=w)
    run = lambda tekst: asyncio.run(wyk.wykonaj(k, *K.parsuj(tekst))).dane()  # noqa: E731

    d = run("/model")
    assert d["ok"] and "anthropic/claude-sonnet-5" in d["wynik"] and len(d["wybor"]) == 3
    d = run("/model opus")                                                     # dwa pasują: wybór
    assert not d["ok"] and len(d["wybor"]) == 2
    d = run("/model claude-opus-5")
    assert d["ok"] and M.omp_sesje.model_skrzynki(w) == "anthropic/claude-opus-5"
    assert M.omp_sesje.argumenty_tury(w) == ["--no-context-files", "--model", "anthropic/claude-opus-5"]
    run("/model anthropic/claude-sonnet-5")                                   # model z omp_arg: wybór panelu znika
    assert M.omp_sesje.model_skrzynki(w) == "" and M.omp_sesje.argumenty_tury(w) == w.omp_arg

    s = M.omp_sesje.podsumowanie_sesji(w)
    assert (s["odpowiedzi"], s["wejscie"], s["wyjscie"], s["kontekst"], s["model"]) == (2, 11, 22, 301, "claude-sonnet-5")
    assert round(s["koszt"], 2) == 0.30
    k.watek = {"id": "w_x"}
    k.sil = type("S", (), {"db": type("D", (), {"przebiegi_watku": lambda self, wid, aktywne=False: []})()})()
    d = run("/usage")
    assert d["ok"] and "2 odpowiedzi" in d["wynik"] and "$0.30" in d["wynik"]
    for tekst, slowo in (("/new", "sesje.json"), ("/model x --global", "omp_arg")):
        d = run(tekst)
        assert not d["ok"] and slowo in d["wynik"], tekst


def test_omp_compact_komendy_skrzynki_i_licznik(tmp_path, monkeypatch):
    """`/compact` (alias `/compress`) i komendy zgłoszone przez skrzynkę idą do skrzynki sesji omp (`komenda` +
    `wynik_komendy`); dłuższa niż `czekaj_s` kończy się drugim wpisem (`po_czasie`); licznik i `/context` z
    `omp_sesje.licznik`."""
    w = _wpis_omp(tmp_path)
    om = M.omp_sesje
    wyniki, komendy = {}, []
    monkeypatch.setattr(om, "komenda", lambda w_, nazwa, args, klucz: komendy.append((nazwa, args, klucz)) or {"nowy": True},
                        raising=False)
    monkeypatch.setattr(om, "wynik_komendy", lambda w_, klucz: wyniki.get(klucz, {"stan": "pracuje", "wynik": "", "blad": None}),
                        raising=False)
    monkeypatch.setattr(om, "komendy_omp", lambda w_: [{"nazwa": "compact", "opis": "x"}, {"nazwa": "export", "opis": "Eksport"}],
                        raising=False)
    monkeypatch.setattr(om, "licznik", lambda w_: {"model": "anthropic/claude-opus-5", "kontekst": 50_000, "okno": 200_000,
                                                   "procent": 25.0, "wejscie": 10, "wyjscie": 20, "cache_odczyt": 100,
                                                   "cache_zapis": 5, "koszt": 0.3, "czas": 1.0}, raising=False)
    wyk = K.Wykonawca(m=M, lista_omp=lambda: [], rejestr=lambda: [], czekaj_s=0.3, odstep_s=0.05, maks_s=2)
    zadania, po = [], []
    sil = SimpleNamespace(rejestr=SimpleNamespace(zadanie=lambda coro: zadania.append(asyncio.ensure_future(coro))))
    k = K.Kontekst(sil=sil, watek={"id": "w_x"}, agent="op", nazwa="Operator", zaplecze="omp", wpis_omp=w, klucz="kC1",
                   po_czasie=po.append)

    async def scenariusz():
        wyniki["kC1"] = {"stan": "gotowe", "wynik": "120k na 20k tokenów", "blad": None}
        d1 = (await wyk.wykonaj(k, *K.parsuj("/compress skup się na GPU"))).dane()
        k.klucz = "kC2"
        d2 = (await wyk.wykonaj(k, *K.parsuj("/compact"))).dane()          # dłużej niż czekaj_s: wynik drugim wpisem
        k.klucz = "kC2b"
        d2b = (await wyk.wykonaj(k, *K.parsuj("/compact"))).dane()         # drugie kliknięcie w trakcie: bez drugiej kompresji
        wyniki["kC2"] = {"stan": "blad", "wynik": "", "blad": "lock held"}
        await asyncio.gather(*zadania)
        k.klucz, wyniki["kC3"] = "kC3", {"stan": "gotowe", "wynik": "plik.md", "blad": None}
        d3 = (await wyk.wykonaj(k, *K.parsuj("/export"))).dane()
        pomoc = (await wyk.wykonaj(k, "help", "")).dane()
        return d1, d2, d2b, d3, pomoc, await wyk.licznik(k), (await wyk.wykonaj(k, "context", "")).dane()

    d1, d2, d2b, d3, pomoc, lic, ctx = asyncio.run(scenariusz())
    assert komendy[0] == ("compact", "skup się na GPU", "kC1")
    assert d1["ok"] and "skompresowany" in d1["wynik"] and "120k" in d1["wynik"]
    assert d2["ok"] and "trwa" in d2["wynik"] and len(po) == 1
    assert "już trwa" in d2b["wynik"] and [c[2] for c in komendy].count("kC2b") == 0
    assert not po[0].ok and "lock held" in po[0].dane()["wynik"]
    assert komendy[2][0] == "export" and "plik.md" in d3["wynik"] and "/export" in pomoc["wynik"]
    assert lic["zaplecze"] == "omp" and lic["procent"] == 25.0 and lic["okno"] == 200_000 and not lic["szacunek"]
    assert ctx["ok"] and "50 000" in ctx["wynik"] and "25%" in ctx["wynik"] and "$0.30" in ctx["wynik"]
    assert "—" not in json.dumps([d1, d2, d3, pomoc, ctx], ensure_ascii=False)


def test_omp_effort_i_fast_w_model_json(tmp_path, monkeypatch):
    """omp: `/effort` przyjmuje poziomy modelu z katalogu omp (`thinking` + `off`) i zapisuje je w model.json skrzynki
    (obok modelu), `/fast` przełącza; licznik bierze okno z katalogu, gdy skrzynka go nie zna."""
    w = _wpis_omp(tmp_path)
    (tmp_path / "skrzynka").mkdir()
    katalog = [{"model": "anthropic/claude-sonnet-5", "provider": "anthropic", "nazwa": "Sonnet", "okno": 1_000_000,
                "myslenie": ["low", "high", "max"]}]
    wyk = K.Wykonawca(m=M, lista_omp=lambda: katalog, rejestr=lambda: [])
    wyk._czytaj_katalog_omp()
    k = K.Kontekst(sil=None, watek={"id": "w_x"}, agent="op", nazwa="Operator", zaplecze="omp", wpis_omp=w)
    run = lambda tekst: asyncio.run(wyk.wykonaj(k, *K.parsuj(tekst))).dane()  # noqa: E731
    lic = asyncio.run(wyk.licznik(k))
    assert lic["model"] == "anthropic/claude-sonnet-5" and lic["okno"] == 1_000_000 and lic["procent"] == 0.0
    assert not run("/effort medium")["ok"]                                    # sonnet w katalogu: low, high, max
    assert run("/effort high")["ok"] and M.omp_sesje.opcje_skrzynki(w)["myslenie"] == "high"
    assert run("/fast")["ok"] and M.omp_sesje.opcje_skrzynki(w)["fast"] is True
    assert asyncio.run(wyk.licznik(k))["wysilek"] == "high"
    assert run("/fast off")["ok"] and M.omp_sesje.opcje_skrzynki(w) == {"myslenie": "high", "fast": False}
    o = asyncio.run(wyk.opcje(k))
    assert o["poziomy"] == ["off", "low", "high", "max"] and o["modele"][0]["biezacy"]
    assert o["grupy"] == [{"slug": "anthropic", "nazwa": "Claude", "rodzaj": "subskrypcja"}]   # wybierak dzieli na subskrypcje


def test_licznik_i_context_hermes(swiat):
    """Licznik rozmowy z Hermesem: liczniki i koszt z wierszy `sessions` rodowodu członka (większe niż suma `usage`
    przebiegów), kontekst szacowany z treści sesji, okno z metadanych modelu; tylko z panelu."""
    wid, _ = _watek_po_turze(swiat)
    d = swiat.k.get(f"{P}/rozmowy/{wid}/licznik").json()["licznik"]
    assert d["zaplecze"] == "hermes" and d["szacunek"] and d["wejscie"] == 1 and d["wyjscie"] == 1 and d["kontekst"] > 0
    assert d["model"] == "gpt-5.4" and d["okno"] == 100_000 and d["procent"] == round(100 * d["kontekst"] / 100_000, 1)
    sid = swiat.sil.db.czlonek(wid, "jarvo")["sesja_tip"]
    c = sqlite3.connect(swiat.home / "profiles" / "jarvo" / "state.db")
    c.execute("UPDATE sessions SET input_tokens = 500, cache_read_tokens = 70, estimated_cost_usd = 0.12 WHERE id = ?", (sid,))
    c.commit()
    c.close()
    d = swiat.k.get(f"{P}/rozmowy/{wid}/licznik").json()["licznik"]
    assert (d["wejscie"], d["wyjscie"], d["cache_odczyt"], d["koszt"]) == (500, 1, 70, 0.12)
    assert swiat.k.get(f"{P}/rozmowy/{wid}/licznik", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert swiat.k.get(f"{P}/rozmowy/w_nie_ma/licznik").status_code == 404
    w = _komenda(swiat, "/ctx", wid)["wynik"]
    assert w["ok"] and "≈" in w["wynik"] and "100 000" in w["wynik"] and "$0.12" in w["wynik"]


def test_effort_fast_i_opcje_stopki_hermes(swiat):
    """`/effort` (alias `/thinking`, `/reasoning`) i `/fast` dla członka rozmowy z Hermesem: wybór w `meta` rozmowy,
    przebieg wysyła go w `model_options` ciała `/v1/runs`; licznik i `GET /rozmowy/{id}/opcje` (stopka) pokazują
    bieżący wysiłek, poziomy i modele z bramy."""
    wid, _ = _watek_po_turze(swiat)
    w = _komenda(swiat, "/effort", wid)["wynik"]
    assert w["ok"] and "domyślny" in w["wynik"] and "`xhigh`" in w["wynik"]
    assert not _komenda(swiat, "/effort bardzo", wid)["wynik"]["ok"]
    assert _komenda(swiat, "/thinking high", wid)["wynik"]["ok"]
    assert not _komenda(swiat, "/fast on", wid)["wynik"]["ok"]            # atrapa: model bez trybu szybkiego
    assert _komenda(swiat, "/fast off", wid)["wynik"]["ok"]
    r = swiat.wyslij(wid, "dalej")
    swiat.do_stanu(r.json()["przebiegi"][0]["id"], "gotowe")
    cialo = swiat.brama.runs("jarvo")[-1]["cialo"]
    assert cialo["model_options"] == {"reasoning_effort": "high", "fast": False} and "model" not in cialo
    d = swiat.k.get(f"{P}/rozmowy/{wid}/licznik").json()["licznik"]
    assert (d["wysilek"], d["fast"], d["fast_dostepny"]) == ("high", False, False)
    o = swiat.k.get(f"{P}/rozmowy/{wid}/opcje").json()["opcje"]
    assert o["wysilek"] == "high" and "max" in o["poziomy"] and any(m["model"] == "gpt-5.4" for m in o["modele"])
    assert _komenda(swiat, "/reasoning domyslny", wid)["wynik"]["ok"] and _komenda(swiat, "/fast domyslny", wid)["wynik"]["ok"]
    r = swiat.wyslij(wid, "jeszcze")
    swiat.do_stanu(r.json()["przebiegi"][0]["id"], "gotowe")
    assert "model_options" not in swiat.brama.runs("jarvo")[-1]["cialo"]

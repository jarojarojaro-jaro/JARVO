"""Klient bramy Hermesa (hq/plugin/brama.py): mapowanie błędów, klucze z .env profili, adresy `/p/<profil>`,
sesje (409 = ta sama, zajęty tytuł), stałe ciało przebiegu, parser SSE bramy. Plus haki silnika (silnik.py):
`zahacz_uvicorn` i plik dziennika 0600."""
import asyncio
import json
import logging
import os
import stat
import sys
import types

import pytest

from conftest import load_script

httpx = pytest.importorskip("httpx")
br = load_script("hq/plugin/brama.py", "jarvo_test_brama")
sil = load_script("hq/plugin/silnik.py", "jarvo_test_brama_silnik")


def _odp(status, cialo=None, **kw):
    return httpx.Response(status, json=cialo if cialo is not None else {}, **kw)


def test_blad_odpowiedzi_mapuje_kody():
    def e(status, kod="", **kw):
        return br.blad_odpowiedzi(_odp(status, {"error": {"message": "m", "code": kod}}, **kw))
    assert (e(429, headers={"Retry-After": "7"}).kod, e(429, headers={"Retry-After": "7"}).ponow_za) == ("limit", 7.0)
    assert e(429, headers={"Retry-After": "zle"}).ponow_za == 1.0
    assert [e(s).kod for s in (401, 403, 502, 503, 504, 404, 400, 413, 422)] == [
        "klucz", "klucz", "niedostepna", "niedostepna", "niedostepna", "brak", "odrzucone", "odrzucone", "odrzucone"]
    assert (e(409, "run_not_active").kod, e(409, "run_not_accepting_steer").kod) == ("nieaktywny", "nieaktywny")
    k = e(409, "idempotency_key_conflict")
    assert (k.kod, k.typ, k.status) == ("konflikt", "idempotency_key_conflict", 409)
    assert br.blad_odpowiedzi(httpx.Response(500, text="<html>")).kod == "odrzucone"


def test_klucze_z_env_i_pamiec(tmp_path):
    (tmp_path / "profiles" / "jarvo-web").mkdir(parents=True)
    (tmp_path / ".env").write_text("API_SERVER_KEY=domyslny\n")
    env = tmp_path / "profiles" / "jarvo-web" / ".env"
    env.write_text("# komentarz\nexport API_SERVER_KEY='k1'\nINNY=x\n")
    teraz = [0.0]
    kl = br.Klucze(tmp_path, ttl=60, zegar=lambda: teraz[0])
    assert (kl("default"), kl("jarvo-web"), kl("brak-profilu")) == ("domyslny", "k1", None)
    env.write_text("API_SERVER_KEY=k2\n")
    assert kl("jarvo-web") == "k1"                       # pamięć 60 s
    teraz[0] = 61
    assert kl("jarvo-web") == "k2"
    with pytest.raises(ValueError):
        kl("../etc")


def test_adresy_profili_sesje_i_cialo():
    zadania = []

    def obsluz(r: httpx.Request):
        zadania.append((r.method, str(r.url), r.headers.get("authorization"), r.headers.get("idempotency-key"),
                        r.content))
        if r.url.path.endswith("/api/sessions") and json.loads(r.content)["title"] == "Zajęty":
            return _odp(400, {"error": {"code": "invalid_title"}})
        if r.url.path.endswith("/api/sessions"):
            return _odp(409, {"error": {"code": "session_exists"}})
        return _odp(202, {"run_id": "run_1", "status": "started"})

    async def main():
        kb = br.KlientBramy("http://brama:8642/", {"jarvo-web": "kw", "default": "kd"}.get,
                            http=httpx.AsyncClient(transport=httpx.MockTransport(obsluz)))
        assert kb.cel("jarvo-web")[0] == "http://brama:8642/p/jarvo-web" and kb.cel("default")[0] == "http://brama:8642"
        with pytest.raises(br.BladBramy) as e:
            kb.cel("jarvo-api")
        assert e.value.kod == "klucz"
        with pytest.raises(br.BladBramy):
            kb.cel("Zła/Nazwa")
        assert await kb.utworz_sesje("jarvo-web", "s_1", "Rozmowa") == "s_1"            # 409 = ta sama sesja
        assert await kb.utworz_sesje("jarvo-web", "s_2", "Zajęty") == "s_2"             # druga próba z sufiksem
        c = br.cialo("s_1", [{"role": "user", "content": "hej"}], br.AUTOR_JARVO)
        assert br.cialo_sha(c) == br.cialo_sha(json.loads(br.cialo_json(c)))
        assert await kb.start("jarvo-web", cialo_=c, idem="jarvo-p_1") == {"run_id": "run_1", "status": "started"}
        with pytest.raises(br.BladBramy) as e:
            await kb.start("jarvo-web", cialo_=br.cialo("s_1", "x" * br.CIALO_MAX), idem="jarvo-p_2")
        assert e.value.typ == "za_duze"
        await kb.zamknij()
    asyncio.run(main())
    assert zadania[0][:3] == ("POST", "http://brama:8642/p/jarvo-web/api/sessions", "Bearer kw")
    assert json.loads(zadania[2][4])["title"].startswith("Zajęty · ")
    oczekiwane = br.cialo_json(br.cialo("s_1", [{"role": "user", "content": "hej"}], br.AUTOR_JARVO))
    assert zadania[3][3] == "jarvo-p_1" and zadania[3][4] == oczekiwane
    assert len(zadania) == 4                                                           # za duże ciało: bez POST


def test_zdarzenia_sse_bramy():
    surowe = (b": keepalive\n\n"
              b'data: {"event": "message.delta", "delta": "A"}\n\n'
              b'data: {"event": "tool.started",\ndata: "tool": "terminal"}\n\n'
              b"data: nie-json\n\n"
              b'data:{"event": "run.completed", "output": "ok"}\n\n')

    async def main():
        kb = br.KlientBramy("http://b", lambda _a: "k", http=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=surowe, headers={"content-type": "text/event-stream"}))))
        out = [ev async for ev in kb.zdarzenia("jarvo-web", "run_1")]
        kb2 = br.KlientBramy("http://b", lambda _a: "k", http=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: _odp(404, {"error": {"code": "run_not_found"}}))))
        with pytest.raises(br.BladBramy) as e:
            [ev async for ev in kb2.zdarzenia("jarvo-web", "run_x")]
        return out, e.value.kod
    out, kod = asyncio.run(main())
    assert [ev["event"] for ev in out] == ["message.delta", "tool.started", "run.completed"]
    assert out[1]["tool"] == "terminal" and kod == "brak"


def test_hak_uvicorn_i_dziennik_0600(tmp_path, monkeypatch):
    wolania = []

    class Server:
        def handle_exit(self, sig, frame):
            wolania.append(("uvicorn", sig))

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(Server=Server))
    assert sil.zahacz_uvicorn(lambda: wolania.append("zamknij"))
    assert sil.zahacz_uvicorn(lambda: wolania.append("zamknij2"))       # drugi import: bez podwójnego owinięcia
    Server().handle_exit(15, None)
    assert wolania == ["zamknij2", ("uvicorn", 15)]

    log = logging.getLogger("jarvo.hq")
    monkeypatch.setattr(log, "handlers", [])
    monkeypatch.setattr(log, "_jarvo_gotowy", False, raising=False)
    plik = tmp_path / "logs" / "jarvo-hq.log"
    sil.ustaw_dziennik(plik)
    try:
        log.info("jarvo-hq: test")
        assert stat.S_IMODE(os.stat(plik).st_mode) == 0o600 and "jarvo-hq: test" in plik.read_text()
        assert sil.ustaw_dziennik(plik) is log and len(log.handlers) == 2
    finally:
        for h in log.handlers:
            h.close()

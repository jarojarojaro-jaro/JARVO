"""Podgląd na żywo (hq/plugin/podglad_zywo.py, docs/HQ.md „Podgląd na żywo”): parser protokołu scrcpy-server 5.0.1
i pamięć GOP na sztucznym strumieniu, nowy widz dostaje sesję, konfigurację i klatkę kluczową jako pierwsze, widz
w tyle czeka na klatkę kluczową, strumień gaśnie 10 s po ostatnim widzu, WebSocket bez poświadczeń panelu = odmowa,
telefon „w pracy” z plików PhoneUse .busy, klatki Komputera i bezpieczne argumenty kroków (czytnik_omp).

Bez telefonu, adb i Hermesa: źródła to atrapy (async generatory), WebSocket przez TestClient Starlette, uwierzytelnienie
Hermesa z atrapą hermes_cli.web_server_chat. Próba na prawdziwym telefonie jest ręczna (notatki w opisie zmiany).
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import struct
import sys
import time
import types

import pytest

from conftest import REPO


def zaladuj(nazwa: str, plik: str):
    spec = importlib.util.spec_from_file_location(nazwa, REPO / "hq" / "plugin" / plik)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pz = zaladuj("jarvo_hq_podglad_zywo_test", "podglad_zywo.py")
czytnik_omp = zaladuj("jarvo_hq_czytnik_omp_test", "czytnik_omp.py")

SPS_PPS = b"\x00\x00\x00\x01\x67\x42\xc0\x1f\xaa" + b"\x00\x00\x00\x01\x68\xce\x3c\x80"
KLUCZOWA = b"\x00\x00\x00\x01\x65" + b"\x11" * 40
ZWYKLA = b"\x00\x00\x00\x01\x41" + b"\x22" * 12


def naglowek_urzadzenia(nazwa: str = "RMX3834") -> bytes:
    return b"\x00" + nazwa.encode().ljust(64, b"\0") + struct.pack(">I", 0x68323634)


def sesja(w: int, h: int) -> bytes:
    return struct.pack(">III", 0x80000000, w, h)


def pakiet(dane: bytes, *, konfig=False, klucz=False, pts=0) -> bytes:
    pierwsze = pz.FLAGA_KONFIG if konfig else (pts | (pz.FLAGA_KLUCZ if klucz else 0))
    return struct.pack(">QI", pierwsze, len(dane)) + dane


STRUMIEN = (naglowek_urzadzenia() + sesja(576, 1280) + pakiet(SPS_PPS, konfig=True)
            + pakiet(KLUCZOWA, klucz=True, pts=1000) + pakiet(ZWYKLA, pts=17666) + pakiet(ZWYKLA, pts=34333)
            + sesja(1280, 576) + pakiet(SPS_PPS, konfig=True) + pakiet(KLUCZOWA, klucz=True, pts=51000))


def rozbierz(ramka: bytes) -> tuple[int, float, int, bytes]:
    typ, czas, pts = struct.unpack(">Bdq", ramka[:17])
    return typ, czas, pts, ramka[17:]


# ---------------------------------------------------------------------------------------------- parser i GOP

@pytest.mark.parametrize("krok", [1, 7, 64, 4096])
def test_parser_scrcpy_501_dowolny_podzial(krok):
    p = pz.ParserScrcpy()
    zd = []
    for i in range(0, len(STRUMIEN), krok):
        zd += p.dodaj(STRUMIEN[i:i + krok])
    assert zd == [("urzadzenie", "RMX3834"), ("kodek", "h264"), ("sesja", 576, 1280),
                  ("pakiet", True, False, 0, SPS_PPS), ("pakiet", False, True, 1000, KLUCZOWA),
                  ("pakiet", False, False, 17666, ZWYKLA), ("pakiet", False, False, 34333, ZWYKLA),
                  ("sesja", 1280, 576), ("pakiet", True, False, 0, SPS_PPS), ("pakiet", False, True, 51000, KLUCZOWA)]
    assert not p.bufor


def test_parser_odmowa_telefonu_i_zly_pakiet():
    with pytest.raises(pz.BladProtokolu, match="wyłączył obraz"):
        pz.ParserScrcpy().dodaj(b"\x00" + b"x".ljust(64, b"\0") + b"\x00\x00\x00\x00")
    p = pz.ParserScrcpy(bajt_proby=False)
    p.dodaj(b"x".ljust(64, b"\0") + struct.pack(">I", 0x68323634))
    with pytest.raises(pz.BladProtokolu):
        p.dodaj(struct.pack(">QI", 5, pz.MAKS_PAKIET + 1))


def test_gop_od_ostatniej_kluczowej_i_limit():
    g = pz.Gop(maks=100)
    assert g.na_start() == []
    g.nowa_sesja("S1")
    g.dodaj(pz.DELTA, b"d0")                       # przed klatką kluczową: bez znaczenia dla nowego widza
    g.dodaj(pz.KONFIG, b"C")
    assert g.na_start() == ["S1", b"C"]
    g.dodaj(pz.KLUCZ, b"K1")
    g.dodaj(pz.DELTA, b"d1")
    assert g.na_start() == ["S1", b"C", b"K1", b"d1"]
    g.dodaj(pz.KLUCZ, b"K2")
    assert g.na_start() == ["S1", b"C", b"K2"]
    g.dodaj(pz.DELTA, b"x" * 200)                  # ponad limit: czekamy na następną kluczową
    assert g.na_start() == ["S1", b"C"]
    g.dodaj(pz.DELTA, b"d3")
    assert g.na_start() == ["S1", b"C"]
    g.nowa_sesja("S2")                             # obrót: nowa sesja kasuje starą konfigurację
    assert g.na_start() == ["S2"]


# ---------------------------------------------------------------------------------------------- strumień i widzowie

async def _zbierz(widz: pz.Widz, ile: int) -> list:
    return [await asyncio.wait_for(widz.wez(), 2) for _ in range(ile)]


def zrodlo_atrapa(zdarzenia: list, czekaj: asyncio.Event | None = None, licznik: dict | None = None):
    async def gen():
        if licznik is not None:
            licznik["starty"] = licznik.get("starty", 0) + 1
        try:
            for ev in zdarzenia:
                if ev == "czekaj":
                    await czekaj.wait()
                    continue
                yield ev
            await asyncio.Event().wait()
        finally:
            if licznik is not None:
                licznik["stopy"] = licznik.get("stopy", 0) + 1
    return gen


def zdarzenia_telefonu() -> list:
    return [e for e in pz.ParserScrcpy().dodaj(STRUMIEN[:-len(pakiet(KLUCZOWA)) - len(pakiet(SPS_PPS)) - 12])
            if e[0] in ("sesja", "pakiet")]


def test_nowy_widz_najpierw_sesja_konfiguracja_i_klatka_kluczowa():
    async def proba():
        dalej = asyncio.Event()
        ev = zdarzenia_telefonu()                     # sesja, konfig, kluczowa, 2 zwykłe
        s = pz.Strumien("second", zrodlo_atrapa(ev[:3] + ["czekaj"] + ev[3:], czekaj=dalej), wygaszenie=60)
        a = pz.Widz()
        s.dolacz(a)
        wa = await _zbierz(a, 5)                       # stan, sesja, konfig, kluczowa, stan „dziala”
        assert json.loads(wa[0])["stan"] == "laczy"
        assert json.loads(wa[1]) == {"typ": "sesja", "u": "second", "w": 576, "h": 1280, "kodek": "h264"}
        assert [rozbierz(x)[0] for x in wa[2:4]] == [pz.KONFIG, pz.KLUCZ]
        assert rozbierz(wa[2])[3] == SPS_PPS and rozbierz(wa[3])[2:] == (1000, KLUCZOWA)
        assert abs(rozbierz(wa[3])[1] - time.time() * 1000) < 5000      # czas odbioru na serwerze w ms
        dalej.set()
        await asyncio.sleep(0)
        # drugi widz w środku GOP: stan, sesja, konfiguracja, kluczowa i zwykłe od niej, a potem dalej na żywo
        b = pz.Widz()
        s.dolacz(b)
        wb = await _zbierz(b, 4)
        assert json.loads(wb[0])["stan"] == "dziala"
        assert json.loads(wb[1])["w"] == 576
        assert [rozbierz(x)[0] for x in wb[2:]] == [pz.KONFIG, pz.KLUCZ]
        s.odlacz(a)
        s.odlacz(b)
        s.zatrzymaj()
    asyncio.run(proba())


def test_widz_w_tyle_czeka_na_klatke_kluczowa_z_konfiguracja():
    w = pz.Widz(maks=100)
    w.wideo(pz.KLUCZ, b"K" * 60, b"C")
    w.wideo(pz.DELTA, b"d" * 60, b"C")                 # ponad limit: zaległości precz, czekamy na kluczową
    assert w.czeka_na_klucz and w.kolejka.empty() and w.bajty == 0
    w.wideo(pz.DELTA, b"d", b"C")
    assert w.kolejka.empty()
    w.wideo(pz.KLUCZ, b"K2", b"C")
    assert [w.kolejka.get_nowait() for _ in range(2)] == [b"C", b"K2"] and not w.czeka_na_klucz


def test_strumien_gasnie_10_s_po_ostatnim_widzu(monkeypatch):
    assert pz.WYGASZENIE == 10.0

    async def proba():
        licznik: dict = {}
        petla = asyncio.get_running_loop()
        opoznienia = []
        prawdziwe = petla.call_later

        def call_later(d, f, *a):
            opoznienia.append(d)
            return prawdziwe(0.05 if d == pz.WYGASZENIE else d, f, *a)
        monkeypatch.setattr(petla, "call_later", call_later)
        s = pz.Strumien("first", zrodlo_atrapa(zdarzenia_telefonu(), licznik=licznik))
        a = pz.Widz()
        s.dolacz(a)
        await asyncio.sleep(0.01)
        assert licznik == {"starty": 1} and s.dziala
        s.odlacz(a)
        assert [d for d in opoznienia if d >= 1] == [pz.WYGASZENIE]     # krótsze to asyncio.sleep testu
        s.dolacz(a)                                    # wrócił przed czasem: ten sam strumień, bez nowego startu
        await asyncio.sleep(0.1)
        assert s.dziala and licznik == {"starty": 1}
        b = pz.Widz()
        s.dolacz(b)
        s.odlacz(a)
        await asyncio.sleep(0.1)
        assert s.dziala                                # ktoś jeszcze patrzy
        s.odlacz(b)
        await asyncio.sleep(0.02)
        assert s.dziala                                # przed upływem wygaszenia dalej leci
        await asyncio.sleep(0.1)
        assert not s.dziala and licznik == {"starty": 1, "stopy": 1}
        assert s.gop.na_start() == []
    asyncio.run(proba())


def test_blad_zrodla_stan_dla_widzow_i_ponowienie(monkeypatch):
    async def proba():
        monkeypatch.setattr(pz.asyncio, "sleep", _szybki_sen)
        proby = {"n": 0}

        async def gen():
            proby["n"] += 1
            if proby["n"] == 1:
                raise pz.BladZrodla("adb: device offline")
            yield ("stan", "laczy", "")
            await asyncio.Event().wait()
        s = pz.Strumien("third", gen, wygaszenie=60)
        a = pz.Widz()
        s.dolacz(a)
        stany = [json.loads(x)["stan"] for x in await _zbierz(a, 3)]
        assert stany == ["laczy", "poza_siecia", "laczy"] and proby["n"] == 2
        s.odlacz(a)
        s.zatrzymaj()
    asyncio.run(proba())


_prawdziwy_sen = asyncio.sleep


async def _szybki_sen(t, *a):
    await _prawdziwy_sen(min(t, 0.001), *a)


def test_klatki_komputera_long_poll():
    pytanie = []
    odp = iter([{"ok": True, "klatka": {"nr": 3, "dane": base64.b64encode(b"\xff\xd8jpeg").decode(), "szer_css": 1280,
                                        "wys_css": 800, "tytul": "Strona", "url": "https://x.pl/"}},
                {"ok": True, "klatka": {"nr": 3, "bez_zmian": True}},
                {"ok": True, "klatka": {"nr": 4, "dane": base64.b64encode(b"\xff\xd8drugi").decode()}},
                {"ok": False, "blad": "przeglądarka Jarva właśnie startuje"}])

    def zapytaj(p):
        pytanie.append(dict(p))
        return next(odp)

    async def proba():
        out = []
        with pytest.raises(pz.BladZrodla, match="startuje"):
            async for ev in pz.zrodlo_komputera(zapytaj):
                out.append(ev)
        return out
    out = asyncio.run(proba())
    assert out[0] == ("stan", "laczy", "")
    assert out[1] == ("jpeg", b"\xff\xd8jpeg", {"nr": 3, "w_css": 1280, "h_css": 800, "tytul": "Strona", "url": "https://x.pl/"})
    assert out[2][1] == b"\xff\xd8drugi"
    assert [p["po"] for p in pytanie] == [None, 3, 3, 4] and all(p["polecenie"] == "klatka" and p["czekaj"] > 0 for p in pytanie)


# ---------------------------------------------------------------------------------------------- WebSocket

def aplikacja(podglad, autoryzuj=None):
    from fastapi import APIRouter, FastAPI
    app, r = FastAPI(), APIRouter()
    if autoryzuj is None:
        pz.dolacz(r, podglad=podglad)
    else:
        pz.dolacz(r, podglad=podglad, autoryzuj=autoryzuj)
    app.include_router(r, prefix="/api/plugins/jarvo-hq")
    return app


def test_websocket_bez_poswiadczen_odmowa(monkeypatch):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    adres = "/api/plugins/jarvo-hq/podglad/ws"
    # bez Hermesa (moduł niedostępny) każda próba jest odmową, zanim cokolwiek ruszy
    monkeypatch.setitem(sys.modules, "hermes_cli.web_server_chat", None)
    with pytest.raises(WebSocketDisconnect) as e, TestClient(aplikacja(pz.Podglad())).websocket_connect(adres + "?token=x"):
        pass
    assert e.value.code == 4401
    # z Hermesem: te same zasady co WebSockety dashboardu (token sesji w ?token= i Host/Origin/klient)
    hermes = types.ModuleType("hermes_cli.web_server_chat")
    hermes._ws_auth_ok = lambda ws: ws.query_params.get("token") == "sesja-panelu"
    hermes._ws_request_is_allowed = lambda ws: ws.headers.get("origin", "http://127.0.0.1:9119") == "http://127.0.0.1:9119"
    monkeypatch.setitem(sys.modules, "hermes_cli.web_server_chat", hermes)
    klient = TestClient(aplikacja(pz.Podglad()))
    for zly in (adres, adres + "?token=zly"):
        with pytest.raises(WebSocketDisconnect) as e, klient.websocket_connect(zly):
            pass
        assert e.value.code == 4401
    with pytest.raises(WebSocketDisconnect), klient.websocket_connect(adres + "?token=sesja-panelu",
                                                                      headers={"origin": "http://zly.example"}):
        pass
    with klient.websocket_connect(adres + "?token=sesja-panelu") as ws:
        assert json.loads(ws.receive_text())["typ"] == "witaj"


def test_websocket_patrz_ping_i_obraz_telefonu():
    from fastapi.testclient import TestClient
    zrodla = []

    def zrodlo_telefonu(uid):
        zrodla.append(uid)
        return zrodlo_atrapa(zdarzenia_telefonu())()

    p = pz.Podglad(zrodlo_telefonu=zrodlo_telefonu, wygaszenie=60)
    with TestClient(aplikacja(p, autoryzuj=lambda ws: True)).websocket_connect("/api/plugins/jarvo-hq/podglad/ws") as ws:
        witaj = json.loads(ws.receive_text())
        assert witaj["typ"] == "witaj" and witaj["telefony"] == [] and "czas" in witaj
        ws.send_text(json.dumps({"typ": "ping", "t": 123}))
        pong = json.loads(ws.receive_text())
        assert pong["typ"] == "pong" and pong["t"] == 123 and pong["s"] > 0
        ws.send_text(json.dumps({"typ": "patrz", "u": "second"}))
        tekstowe, binarne = [], []
        while len(binarne) < 4:
            m = ws.receive()
            if m.get("text") is not None:
                tekstowe.append(json.loads(m["text"]))
            else:
                binarne.append(rozbierz(m["bytes"]))
        assert [t["typ"] for t in tekstowe[:2]] == ["stan", "sesja"]
        assert [b[0] for b in binarne] == [pz.KONFIG, pz.KLUCZ, pz.DELTA, pz.DELTA]
        ws.send_text(json.dumps({"typ": "patrz", "u": "../zle"}))     # zła nazwa: bez zmian
        ws.send_text(json.dumps({"typ": "ping", "t": 1}))
        assert json.loads(ws.receive_text())["typ"] == "pong"
    assert zrodla == ["second"] and set(p.strumienie) == {"second"}


# ---------------------------------------------------------------------------------------------- PhoneUse i kroki

def test_telefon_w_pracy_z_plikow_busy(tmp_path):
    t = pz.Telefony(tools=tmp_path, python=sys.executable, dom=None, stan_phoneuse=tmp_path)
    assert t.zajety() is None
    teraz = time.time()
    for nazwa, wiek in (("first", 5), ("second", 1), ("third", 300)):
        f = tmp_path / f"{nazwa}.busy"
        f.touch()
        os.utime(f, (teraz - wiek, teraz - wiek))
    (tmp_path / "first.heal").touch()
    assert t.zajety(teraz) == "second"
    assert t.zajety(teraz + 3) == "second"
    assert t.zajety(teraz + 60) is None                # nikt nie działał od OKNO_AGENTA s


def test_telefony_z_konfiguracji_jarva(tmp_path):
    assert pz.Telefony.z_konfiguracji(tmp_path, {}) is None
    (tmp_path / "telefon.json").write_text(json.dumps({"wlaczony": True, "serwer": "/x/PHONEUSE/tools/phone_mcp.py",
                                                       "python": "/x/py", "dom": "/home/w",
                                                       "profile": {"jarvo-translator": "second", "zly": "../x"}}))
    t = pz.Telefony.z_konfiguracji(tmp_path, {})
    assert (str(t.tools), t.python, t.dom) == ("/x/PHONEUSE/tools", "/x/py", "/home/w")
    assert str(t.stan_phoneuse) == "/home/w/.phoneuse/state" and t.przydzialy == {"jarvo-translator": "second"}


def test_podglad_bez_instalacji_natywnej_mowi_niedostepny(monkeypatch):
    monkeypatch.setattr(pz.asyncio, "sleep", _szybki_sen)
    p = pz.Podglad.z_otoczenia({})

    async def proba():
        s = p.strumien("first")
        a = pz.Widz()
        s.dolacz(a)
        wiad = [json.loads(x) for x in await _zbierz(a, 2)]
        s.odlacz(a)
        s.zatrzymaj()
        return wiad
    assert [w["stan"] for w in asyncio.run(proba())] == ["laczy", "niedostepny"]


def test_argumenty_urzadzenia_tylko_bezpieczne_pola():
    a = czytnik_omp.argumenty_urzadzenia
    assert a("mcp__phone__act", {"phone": "second", "cmd": "tap", "args": {"x": 540, "y": 1200, "text": "hasło"}}) == \
        {"phone": "second", "cmd": "tap", "x": 540, "y": 1200}
    assert a("mcp__phone_act", json.dumps({"phone": "third", "cmd": "type", "args": {"text": "kod 1234", "index": 7}})) == \
        {"phone": "third", "cmd": "type", "index": 7}
    assert a("mcp__phone__batch", {"phone": "first", "steps": [{"cmd": "type", "text": "x"}, {"cmd": "tap", "x": 1, "y": 2}]}) == \
        {"cmd": "batch", "phone": "first", "x": 1, "y": 2}
    assert a("mcp__phone__screen", {}) == {"cmd": "screen"}
    assert a("mcp__phone__act", {"phone": "../x", "cmd": "Tap; rm"}) == {}
    assert a("computer_use", {"action": "click", "coordinate": [100, 200], "text": "sekret"}) == {"cmd": "click", "x": 100, "y": 200}
    assert a("komputer", {"action": "type", "text": "hasło"}) == {"cmd": "type"}
    assert a("terminal", {"command": "ls"}) is None
    assert a("mcp__phone__list_phones", {}) is None

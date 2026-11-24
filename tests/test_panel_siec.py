"""Panel w sieci Tailscale (hq/plugin/siec.py, jarvo/panel_siec.py, docs/HQ.md „Panel w sieci”): ustawienia, klucz
jednorazowy, sesje, bramka przed aplikacją Hermesa (zły Host = 400, dobry bez sesji = logowanie, z sesją jak
loopback), kompresja, polecenia `jarvo panel siec …` i `jarvo panel klucz`, status i doctor.

Bez sieci i bez Hermesa: bramkę wołamy wprost jako ASGI z atrapą aplikacji, a dostawcę logowania z atrapą
hermes_cli.dashboard_auth.base. Próba z prawdziwym Hermesem (loopback bez hasła obok trybu sieci) jest na końcu:
tylko z JARVO_TEST_HERMES_SRC (checkout Hermesa z venvem .venv).
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import cli, panel_siec, rece, sciezki  # noqa: E402

PORT = 9119
ADRES = "100.102.239.120"
NAZWA = "server.tail37f4b1.ts.net"


def zaladuj():
    spec = importlib.util.spec_from_file_location("jarvo_hq_siec_test", REPO / "hq" / "plugin" / "siec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s = zaladuj()


@pytest.fixture
def sc(tmp_path):
    sc = s.Sciezki(tmp_path / "jarvo")
    s.nowy_sekret(sc)
    s.zapisz_ustawienia(sc, wlaczony=True, adres=ADRES, nazwa=NAZWA)
    return sc


# ---------------------------------------------------------------- atrapa aplikacji Hermesa i wołanie ASGI

DUZY_JS = b"console.log('jarvo');\n" * 20000
LOGOWANIE = b"<html><body><form class=\"provider-form\" data-provider=\"jarvo\"></form></body></html>"


class Aplikacja:
    """Zapisuje scope; odpowiada jak dashboard Hermesa w trybie loopback (index.html z tokenem dla nieznanych ścieżek)."""

    def __init__(self):
        self.wolania: list[dict] = []

    async def __call__(self, scope, receive, send):
        self.wolania.append(scope)
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
            return
        sciezka = scope["path"]
        if sciezka == "/login":
            typ, tresc, dalej = b"text/html; charset=utf-8", LOGOWANIE, False
        elif sciezka == "/assets/app.js":
            typ, tresc, dalej = b"text/javascript; charset=utf-8", DUZY_JS, False
        elif sciezka == "/api/strumien":
            typ, tresc, dalej = b"text/event-stream", b"data: x\n\n" * 300, True
        elif sciezka.startswith("/api/"):
            typ, tresc, dalej = b"application/json", b'{"ok":true}', False
        else:                                         # SPA: index.html z tokenem sesji trybu loopback
            typ, tresc, dalej = b"text/html", b"<script>window.__HERMES_SESSION_TOKEN__='t'</script>", False
        naglowki = [(b"content-type", typ), (b"etag", b'"e1"')]
        if not dalej:
            naglowki.append((b"content-length", str(len(tresc)).encode()))
        await send({"type": "http.response.start", "status": 200, "headers": naglowki})
        if dalej:
            await send({"type": "http.response.body", "body": tresc[:100], "more_body": True})
            tresc = tresc[100:]
        await send({"type": "http.response.body", "body": tresc})


def wolaj(bramka, sciezka="/", *, metoda="GET", host=f"{ADRES}:{PORT}", naglowki=(), ws=False, zapytanie=b""):
    """(status, nagłówki [(k, v)], treść) albo dla WebSocket lista wysłanych wiadomości."""
    h = [(b"host", host.encode())] if host is not None else []
    h += [(k.encode(), v.encode()) for k, v in naglowki]
    scope = {"type": "websocket" if ws else "http", "method": metoda, "path": sciezka, "query_string": zapytanie,
             "headers": h, "client": ("100.82.234.54", 51000), "server": (ADRES, PORT), "scheme": "http"}
    wyslane: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(w):
        wyslane.append(w)

    asyncio.run(bramka(scope, receive, send))
    if ws:
        return wyslane
    start = next(w for w in wyslane if w["type"] == "http.response.start")
    return start["status"], start["headers"], b"".join(w.get("body", b"") for w in wyslane
                                                       if w["type"] == "http.response.body")


def naglowek(naglowki, nazwa: bytes) -> list[bytes]:
    return [v for k, v in naglowki if k.lower() == nazwa]


def bramka(sc, app=None):
    return s.Bramka(app or Aplikacja(), s.Sesje(sc), {ADRES, NAZWA}, f"127.0.0.1:{PORT}")


def zalogowany(sc) -> tuple[dict, str]:
    kod, _ = s.wydaj_klucz(sc)
    sesja = s.Sesje(sc).zaloguj(kod)
    return sesja, f"{s.CIASTKO_AT}={sesja['at']}; {s.CIASTKO_RT}={sesja['rt']}"


# ---------------------------------------------------------------- ustawienia, klucz, sesje

def test_ustawienia_tylko_konkretny_adres(tmp_path):
    sc = s.Sciezki(tmp_path / "jarvo")
    assert s.ustawienia(sc)["wlaczony"] is False                      # brak pliku = wyłączony
    for zly in ("0.0.0.0", "::", "127.0.0.1", "::1", "localhost", "nie-ip", ""):
        s.zapisz_ustawienia(sc, wlaczony=True, adres=zly)
        assert s.ustawienia(sc)["wlaczony"] is False, zly
    s.zapisz_ustawienia(sc, wlaczony=True, adres=ADRES, nazwa="Zła Nazwa!")
    u = s.ustawienia(sc)
    assert u["wlaczony"] is True and u["adres"] == ADRES and u["nazwa"] == ""
    if os.name != "nt":
        assert sc.ustawienia.stat().st_mode & 0o777 == 0o600


def test_klucz_dziala_raz_i_na_dysku_jest_tylko_skrot(sc):
    kod, wygasa = s.wydaj_klucz(sc, 600)
    assert s.WZOR_KLUCZA.fullmatch(kod) and wygasa > time.time()
    pliki = list(sc.klucze.iterdir())
    assert [p.name for p in pliki] == [s.skrot(kod)]
    assert kod not in pliki[0].read_text(encoding="utf-8")
    if os.name != "nt":
        assert sc.klucze.stat().st_mode & 0o777 == 0o700 and pliki[0].stat().st_mode & 0o777 == 0o600
    sesje = s.Sesje(sc)
    assert sesje.zaloguj(kod.lower()) is not None                      # wielkość liter bez znaczenia
    assert sesje.zaloguj(kod) is None                                  # drugi raz nie
    assert not list(sc.klucze.iterdir())
    assert sesje.zaloguj("JRV-0000-0000-0000") is None and sesje.zaloguj("hasło") is None


def test_klucz_wygasly_i_limit_waznych(sc, monkeypatch):
    kod, _ = s.wydaj_klucz(sc, 60)
    teraz = time.time()
    monkeypatch.setattr(s.time, "time", lambda: teraz + 61)
    assert s.Sesje(sc).zaloguj(kod) is None
    monkeypatch.setattr(s.time, "time", lambda: teraz)
    kody = [s.wydaj_klucz(sc)[0] for _ in range(s.NAJWIECEJ_KLUCZY + 2)]
    assert len(list(sc.klucze.iterdir())) == s.NAJWIECEJ_KLUCZY
    assert s.Sesje(sc).zaloguj(kody[-1]) is not None


def test_klucz_bez_sekretu_nie_jest_zuzywany(sc):
    kod, _ = s.wydaj_klucz(sc)
    sc.sekret.unlink()
    assert s.Sesje(sc).zaloguj(kod) is None and len(list(sc.klucze.iterdir())) == 1


def test_sesja_dostep_odswiezenie_i_wylogowanie(sc):
    sesje = s.Sesje(sc)
    sesja, _ = zalogowany(sc)
    assert sesje.sprawdz(sesja["at"])["kto"] == "wlasciciel"
    assert sesje.sprawdz(sesja["rt"]) is None                          # token odświeżenia to nie dostęp
    assert sesje.odswiez(sesja["at"]) is None
    assert sesje.odswiez(sesja["rt"])["at"]
    zmieniony = sesja["at"][:-2] + ("AA" if not sesja["at"].endswith("AA") else "BB")
    assert sesje.sprawdz(zmieniony) is None
    time.sleep(0.01)
    s.nowy_sekret(sc)                                                  # jarvo panel siec wyloguj
    assert sesje.sprawdz(sesja["at"]) is None and sesje.odswiez(sesja["rt"]) is None


# ---------------------------------------------------------------- bramka

@pytest.mark.parametrize("host", ["evil.example:9119", "127.0.0.1:9119", "localhost:9119", f"{ADRES}.nip.io",
                                  f"http://{ADRES}", f"{ADRES}:x", "", None])
def test_zly_host_400_przed_wszystkim(sc, host):
    app = Aplikacja()
    _, ciastka = zalogowany(sc)
    status, _, tresc = wolaj(bramka(sc, app), "/api/sessions", host=host, naglowki=[("cookie", ciastka)])
    assert status == 400 and b"Invalid Host header" in tresc and app.wolania == []
    assert wolaj(bramka(sc, app), "/api/ws", host=host, ws=True) == [{"type": "websocket.close", "code": 1008}]


@pytest.mark.parametrize("host", [f"{ADRES}:{PORT}", ADRES, f"{NAZWA}:{PORT}", NAZWA.upper()])
def test_dobry_host_bez_sesji_wymaga_logowania(sc, host):
    app = Aplikacja()
    b = bramka(sc, app)
    status, _, tresc = wolaj(b, "/api/sessions", host=host)
    assert status == 401 and json.loads(tresc)["jarvo"] == "panel-siec"
    status, h, _ = wolaj(b, "/jarvo", host=host, zapytanie=b"tab=czat")
    assert status == 302 and naglowek(h, b"location") == [b"/login?next=%2Fjarvo%3Ftab%3Dczat"]
    assert wolaj(b, "/", host=host)[0] == 302
    assert wolaj(b, "/api/plugins/jarvo-hq/rozmowy", host=host, metoda="POST")[0] == 401
    assert wolaj(b, "/api/ws", host=host, ws=True) == [{"type": "websocket.close", "code": 1008}]
    assert wolaj(b, "/api/x", host=host, naglowki=[("cookie", f"{s.CIASTKO_AT}=podrobka")])[0] == 401
    assert app.wolania == []


def test_z_sesja_zadanie_idzie_jak_lokalne(sc):
    app = Aplikacja()
    _, ciastka = zalogowany(sc)
    status, _, tresc = wolaj(bramka(sc, app), "/api/sessions", metoda="POST", naglowki=[
        ("cookie", ciastka), ("origin", f"http://{ADRES}:{PORT}"), ("x-forwarded-for", "127.0.0.1"),
        ("forwarded", "for=127.0.0.1"), ("x-forwarded-host", "localhost"), ("sec-fetch-site", "same-origin")])
    assert status == 200 and tresc == b'{"ok":true}'
    h = dict(app.wolania[0]["headers"])
    assert h[b"host"] == b"127.0.0.1:9119" and h[b"origin"] == b"http://127.0.0.1:9119"
    assert b"x-forwarded-for" not in h and b"forwarded" not in h and b"x-forwarded-host" not in h
    assert h[b"sec-fetch-site"] == b"same-origin" and h[b"cookie"] == ciastka.encode()
    assert app.wolania[0]["client"][0] == "100.82.234.54"              # limity logowania widzą prawdziwy adres


def test_obcy_origin_403(sc):
    app = Aplikacja()
    _, ciastka = zalogowany(sc)
    for origin in ("http://evil.example", f"http://{ADRES}.evil.example", "http://127.0.0.1:9119", "null"):
        assert wolaj(bramka(sc, app), "/api/x", metoda="POST", naglowki=[("cookie", ciastka),
                                                                         ("origin", origin)])[0] == 403, origin
    assert wolaj(bramka(sc, app), "/login", naglowki=[("origin", "http://evil.example")])[0] == 403
    assert app.wolania == []


def test_z_https_strona_po_http_idzie_na_https_a_api_i_serve_nie(sc):
    app = Aplikacja()
    _, ciastka = zalogowany(sc)
    b = s.Bramka(app, s.Sesje(sc), {ADRES, NAZWA}, f"127.0.0.1:{PORT}", https=NAZWA)
    status, h, _ = wolaj(b, "/login", zapytanie=b"next=%2Fjarvo", naglowki=[("sec-fetch-dest", "document")])
    assert status == 302 and naglowek(h, b"location") == [f"https://{NAZWA}/login?next=%2Fjarvo".encode()]
    assert wolaj(b, "/jarvo", naglowki=[("accept", "text/html")])[0] == 302          # Safari bez Sec-Fetch
    assert wolaj(b, "/api/x", naglowki=[("cookie", ciastka), ("sec-fetch-dest", "document")])[0] == 200
    assert wolaj(b, "/jarvo", naglowki=[("cookie", ciastka), ("sec-fetch-dest", "document"),
                                        ("x-forwarded-proto", "https")])[0] == 200    # przez tailscale serve
    assert wolaj(b, "/assets/app.js", naglowki=[("cookie", ciastka), ("sec-fetch-dest", "script")])[0] == 200


def test_odswiezenie_samym_rt_ustawia_nowe_ciasteczka(sc):
    app = Aplikacja()
    sesja, _ = zalogowany(sc)
    status, h, _ = wolaj(bramka(sc, app), "/jarvo", naglowki=[("cookie", f"__Host-{s.CIASTKO_RT}={sesja['rt']}")])
    assert status == 200 and len(app.wolania) == 1
    nowe = b" ".join(naglowek(h, b"set-cookie")).decode()
    assert f"{s.CIASTKO_AT}=" in nowe and f"{s.CIASTKO_RT}=" in nowe and "HttpOnly" in nowe and "Path=/" in nowe
    at = nowe.split(f"{s.CIASTKO_AT}=")[1].split(";")[0]
    assert s.Sesje(sc).sprawdz(at) is not None


def test_websocket_z_sesja_jak_z_petli_zwrotnej(sc):
    app = Aplikacja()
    sesja, _ = zalogowany(sc)
    wyslane = wolaj(bramka(sc, app), "/api/ws", ws=True, naglowki=[
        ("cookie", f"{s.CIASTKO_RT}={sesja['rt']}"), ("origin", f"http://{NAZWA}:{PORT}")])
    assert wyslane == [{"type": "websocket.accept"}]
    scope = app.wolania[0]
    assert scope["client"][0] == "127.0.0.1" and dict(scope["headers"])[b"host"] == b"127.0.0.1:9119"
    assert dict(scope["headers"])[b"origin"] == b"http://127.0.0.1:9119"


@pytest.fixture
def strona(tmp_path, monkeypatch):
    """logowanie.html jak w buildzie wtyczki (scripts/hqbuild.py), obok „wtyczki” w tmp."""
    sys.path.insert(0, str(REPO / "scripts"))
    import hqbuild
    plik = tmp_path / hqbuild.LOGOWANIE_SIECI
    plik.write_bytes(hqbuild.strona_logowania_sieci())
    monkeypatch.setattr(s, "STRONA_LOGOWANIA", plik)
    return plik.read_bytes()


def test_strona_logowania_jarva_bez_hermesa(sc, strona):
    """GET /login podaje bramka: strona Jarva (wygląd jarvo.pl), bez wołania Hermesa i bez innych plików."""
    app = Aplikacja()
    status, h, tresc = wolaj(bramka(sc, app), "/login", zapytanie=b"next=%2Fjarvo")
    assert status == 200 and tresc == s.ze_znacznikami(strona) and app.wolania == []
    assert naglowek(h, b"content-type") == [b"text/html; charset=utf-8"] and naglowek(h, b"cache-control") == [b"no-store"]
    assert naglowek(h, b"content-length") == [str(len(tresc)).encode()]
    tekst = tresc.decode("utf-8")
    assert 'data-provider="jarvo"' in tekst and "/auth/password-login" in tekst and "klucz=" in tekst
    assert "Klucz jednorazowy" in tekst and "jarvo panel klucz" in tekst and 'lang="pl"' in tekst
    for obce in ("Hermes Agent", "Nous", "Public bind", "Auth required", "Choose a sign-in", "@@"):
        assert obce not in tekst, obce
    assert tekst.count("data:font/woff2;base64,") == 4 and 'aria-label="JARVO"' in tekst     # kroje i logo w pliku
    zasoby = set(re.findall(r'(?:src|href)="([^"]*)"', tekst)) | set(re.findall(r"url\((?!data:)([^)]*)\)", tekst))
    assert zasoby == {"/favicon.svg", "/jarvo-aplikacja.webmanifest", "/jarvo-ikona-180.png"}   # publiczne pliki
    status, h, spakowane = wolaj(bramka(sc), "/login", naglowki=[("accept-encoding", "gzip")])
    assert naglowek(h, b"content-encoding") == [b"gzip"] and gzip.decompress(spakowane) == s.ze_znacznikami(strona)
    assert wolaj(bramka(sc, app), "/auth/password-login", metoda="POST")[0] == 200 and len(app.wolania) == 1


def test_aplikacja_na_ekranie_telefonu(sc, tmp_path, monkeypatch):
    """Panel jako aplikacja na ekranie iPhone'a: manifest i ikona bez sesji (ekran dodaje je przed logowaniem),
    strona panelu z sesją ma znaczniki w <head> i poprawną długość; Hermes nie jest wołany o pliki aplikacji."""
    ikona = tmp_path / "ikona-180.png"
    ikona.write_bytes(b"\x89PNG-ikona")
    monkeypatch.setattr(s, "IKONY", {"/jarvo-ikona-180.png": ikona, "/jarvo-ikona-512.png": tmp_path / "brak.png"})
    app = Aplikacja()
    b = bramka(sc, app)
    status, h, tresc = wolaj(b, "/jarvo-aplikacja.webmanifest")
    m = json.loads(tresc)
    assert status == 200 and m["display"] == "standalone" and m["start_url"] == "/jarvo"
    assert wolaj(b, "/jarvo-ikona-180.png")[2] == b"\x89PNG-ikona" and wolaj(b, "/jarvo-ikona-512.png")[0] == 404
    assert app.wolania == []
    _, ciastka = zalogowany(sc)
    monkeypatch.setattr(Aplikacja, "__call__", _strona_z_head)
    status, h, tresc = wolaj(b, "/jarvo", naglowki=[("cookie", ciastka)])
    assert status == 200 and tresc.startswith(b"<html><head>" + s.ZNACZNIKI_APLIKACJI)
    assert naglowek(h, b"content-length") == [str(len(tresc)).encode()]


async def _strona_z_head(self, scope, receive, send):
    tresc = b"<html><head><title>Jarvo</title></head><body></body></html>"
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/html"), (b"content-length", str(len(tresc)).encode())]})
    await send({"type": "http.response.body", "body": tresc})


def test_bez_pliku_strona_logowania_hermesa(sc, tmp_path, monkeypatch):
    monkeypatch.setattr(s, "STRONA_LOGOWANIA", tmp_path / "brak.html")
    app = Aplikacja()
    status, _, tresc = wolaj(bramka(sc, app), "/login")
    assert status == 200 and tresc == LOGOWANIE and [w["path"] for w in app.wolania] == ["/login"]


def test_bez_sesji_zadna_strona_spa_z_tokenem(sc):
    """Brak pliku w /fonts/ Hermes odsyła jako index.html z tokenem sesji loopbacku: bez sesji = 404."""
    b = bramka(sc)
    for sciezka in ("/fonts/brak.woff2", "/ds-assets/x", "/favicon.svg", "/assets/brak.js"):
        status, _, tresc = wolaj(b, sciezka)
        assert status == 404 and b"__HERMES_SESSION_TOKEN__" not in tresc, sciezka
    assert wolaj(b, "/assets/app.js")[0] == 200


def test_gzip_dla_plikow_a_strumien_bez_zmian(sc):
    app = Aplikacja()
    b = bramka(sc, app)
    _, ciastka = zalogowany(sc)
    status, h, tresc = wolaj(b, "/assets/app.js", naglowki=[("accept-encoding", "gzip, br")])
    assert status == 200 and naglowek(h, b"content-encoding") == [b"gzip"]
    assert gzip.decompress(tresc) == DUZY_JS and naglowek(h, b"content-length") == [str(len(tresc)).encode()]
    assert len(tresc) < len(DUZY_JS) // 10
    assert wolaj(b, "/assets/app.js", naglowki=[("accept-encoding", "gzip")])[2] == tresc   # z pamięci
    status, h, tresc = wolaj(b, "/assets/app.js")
    assert naglowek(h, b"content-encoding") == [] and tresc == DUZY_JS
    status, h, tresc = wolaj(b, "/api/strumien", naglowki=[("cookie", ciastka), ("accept-encoding", "gzip")])
    assert status == 200 and naglowek(h, b"content-encoding") == [] and tresc.startswith(b"data: x")


# ---------------------------------------------------------------- dostawca logowania Hermesa (atrapa base.py)

@pytest.fixture
def hermes_base(monkeypatch):
    base = types.ModuleType("hermes_cli.dashboard_auth.base")

    class DashboardAuthProvider:
        pass

    class InvalidCredentialsError(Exception):
        pass

    class RefreshExpiredError(Exception):
        pass

    @dataclass(frozen=True)
    class Session:
        user_id: str
        email: str
        display_name: str
        org_id: str
        provider: str
        expires_at: int
        access_token: str
        refresh_token: str

    for k, v in dict(DashboardAuthProvider=DashboardAuthProvider, InvalidCredentialsError=InvalidCredentialsError,
                     RefreshExpiredError=RefreshExpiredError, Session=Session).items():
        setattr(base, k, v)
    for nazwa in ("hermes_cli", "hermes_cli.dashboard_auth"):
        monkeypatch.setitem(sys.modules, nazwa, types.ModuleType(nazwa))
    monkeypatch.setitem(sys.modules, "hermes_cli.dashboard_auth.base", base)
    return base


def test_dostawca_jarvo_dla_hermesa(sc, hermes_base):
    d = s.dostawca_hermesa(s.Sesje(sc))
    assert d.name == "jarvo" and d.supports_password is True
    kod, _ = s.wydaj_klucz(sc)
    sesja = d.complete_password_login(username="cokolwiek", password=kod)
    assert sesja.provider == "jarvo" and sesja.access_token and sesja.refresh_token
    with pytest.raises(hermes_base.InvalidCredentialsError):
        d.complete_password_login(username="jarvo", password=kod)
    assert d.verify_session(access_token=sesja.access_token).user_id == "wlasciciel"
    assert d.verify_session(access_token="zly") is None
    assert d.refresh_session(refresh_token=sesja.refresh_token).access_token
    with pytest.raises(hermes_base.RefreshExpiredError):
        d.refresh_session(refresh_token=sesja.access_token)
    # ciasteczko od Hermesa (dostawca jarvo) otwiera bramkę: jeden format tokenów
    status, _, _ = wolaj(bramka(sc), "/jarvo", naglowki=[("cookie", f"{s.CIASTKO_AT}={sesja.access_token}")])
    assert status == 200


# ---------------------------------------------------------------- polecenia jarvo panel …

@pytest.fixture
def inst(tmp_path, monkeypatch):
    u = sciezki.uklad({"JARVO_ROOT": str(tmp_path / "Jarvo")})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    for z in (*rece.ZNACZNIKI_FLOTY, "HERMES_HOME", "JARVO_PANEL_PORT"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setattr(panel_siec, "CZEKANIE_NA_PANEL", 0.0)
    proba = {"wynik": ("brak", "nikt nie odpowiada")}
    monkeypatch.setattr(panel_siec, "sprawdz_nasluch", lambda ust, port, ot=None: proba["wynik"])
    monkeypatch.setattr(panel_siec, "tailscale", lambda: {"adres": ADRES, "nazwa": NAZWA, "zrodlo": "tailscale status"})
    return argparse.Namespace(u=u, proba=proba)


def jarvo(inst, *argv: str) -> int:
    with cli._po_polsku():
        a = cli._parser().parse_args(["panel", *argv])
    return a.funkcja(inst.u, a, [], None)


def test_parser_panel_bez_zmian_i_podpolecenia():
    with cli._po_polsku():
        p = cli._parser()
        assert p.parse_args(["panel"]).funkcja is cli.polecenie_panel
        assert p.parse_args(["panel", "--bez-przegladarki"]).bez_przegladarki is True
        assert p.parse_args(["panel", "siec"]).funkcja is panel_siec.polecenie_status
        assert p.parse_args(["panel", "siec", "on", "--adres", ADRES]).funkcja is panel_siec.polecenie_on
        assert p.parse_args(["panel", "klucz", "--waznosc", "30m"]).waznosc == "30m"


def test_on_klucz_status_off(inst, capsys):
    assert jarvo(inst, "klucz") == 1 and "wyłączony" in capsys.readouterr().err
    assert jarvo(inst, "siec", "on") == 0
    out = capsys.readouterr().out
    assert f"http://{ADRES}:9119/jarvo i http://{NAZWA}:9119/jarvo" in out and "jarvo panel klucz" in out
    sc = panel_siec.sciezki(inst.u)
    sekret = sc.sekret.read_text(encoding="utf-8").strip()
    assert len(bytes.fromhex(sekret)) == 32 and sekret not in out
    if os.name != "nt":
        assert sc.sekret.stat().st_mode & 0o777 == 0o600
    assert jarvo(inst, "klucz", "--waznosc", "30m") == 0
    out = capsys.readouterr().out
    kod = next(w for w in out.split() if s.WZOR_KLUCZA.fullmatch(w))
    assert f"http://{ADRES}:9119/login?next=%2Fjarvo#klucz={kod}" in out
    assert f"http://{NAZWA}:9119/login?next=%2Fjarvo#klucz={kod}" in out
    assert [p.name for p in sc.klucze.iterdir()] == [s.skrot(kod)]
    assert s.Sesje(s.Sciezki(inst.u.jarvo_dane)).zaloguj(kod) is not None
    jarvo(inst, "siec", "on")                                         # drugie `on`: ten sam sekret (sesje zostają)
    assert sc.sekret.read_text(encoding="utf-8").strip() == sekret
    assert jarvo(inst, "siec", "wyloguj") == 0 and sc.sekret.read_text(encoding="utf-8").strip() != sekret
    capsys.readouterr()
    assert jarvo(inst, "siec", "status", "--json") == 0
    r = json.loads(capsys.readouterr().out)
    assert r["wlaczony"] is True and r["adres"] == ADRES and r["proba"] == "brak" and r["tailscale"]["adres"] == ADRES
    assert jarvo(inst, "siec", "off") == 0 and s.ustawienia(sc)["wlaczony"] is False
    assert jarvo(inst, "klucz") == 1


def test_on_z_adresem_i_zle_wartosci(inst, capsys):
    assert jarvo(inst, "siec", "on", "--adres", "0.0.0.0") == 1
    assert jarvo(inst, "siec", "on", "--adres", "100.64.0.7", "--nazwa", "zła nazwa") == 1
    assert jarvo(inst, "klucz", "--waznosc", "dużo") == 1                 # wyłączony: najpierw on
    assert jarvo(inst, "siec", "on", "--adres", "100.64.0.7") == 0
    u = s.ustawienia(panel_siec.sciezki(inst.u))
    assert u["adres"] == "100.64.0.7" and u["nazwa"] == ""
    assert jarvo(inst, "klucz", "--waznosc", "dużo") == 2


@pytest.mark.parametrize("zmienna", ["HERMES_KANBAN_TASK", "HERMES_CRON_SESSION", "JARVO_DATA_DIR"])
def test_tylko_wlasciciel_wlacza_i_wydaje_klucz(inst, monkeypatch, capsys, zmienna):
    monkeypatch.setenv(zmienna, "1")
    assert jarvo(inst, "siec", "on") == 1 and jarvo(inst, "klucz") == 1 and jarvo(inst, "siec", "wyloguj") == 1
    assert capsys.readouterr().err.count("odmowa") == 3
    assert not panel_siec.sciezki(inst.u).ustawienia.exists()
    assert jarvo(inst, "siec", "status") == 0                          # podgląd może każdy


def test_status_i_doctor(inst):
    assert [w["stan"] for w in panel_siec.sprawdzenia(inst.u)] == ["ok"]          # wyłączony: opcjonalny
    assert "wyłączony" in panel_siec.opis_do_statusu(panel_siec.do_statusu(inst.u))
    assert jarvo(inst, "siec", "on") == 0
    w = panel_siec.sprawdzenia(inst.u)[0]
    assert w["stan"] == "uwaga" and "nie odpowiada" in w["opis"] and "tailscale status" in w["rada"]
    inst.proba["wynik"] = ("bramka", "odpowiada, bez sesji 401 (logowanie kluczem)")
    assert panel_siec.sprawdzenia(inst.u)[0]["stan"] == "ok"
    opis = panel_siec.opis_do_statusu(panel_siec.do_statusu(inst.u))
    assert opis.startswith(f"http://{ADRES}:9119/jarvo i http://{NAZWA}:9119/jarvo (słucha")
    r = {"root": "/r", "zainstalowane": False, "serwis": {"dziala": True}, "autostart": {}, "porty": {},
         "panel": "http://127.0.0.1:9119/jarvo", "panel_siec": panel_siec.do_statusu(inst.u)}
    assert f"  w sieci:    http://{ADRES}:9119/jarvo" in cli.opis_statusu(r)
    inst.proba["wynik"] = ("otwarty", "odpowiada 200 bez logowania")
    assert panel_siec.sprawdzenia(inst.u)[0]["stan"] == "blad"
    panel_siec.sciezki(inst.u).sekret.unlink()
    assert panel_siec.sprawdzenia(inst.u)[0]["stan"] == "blad"


def test_sprawdz_nasluch_rozpoznaje_bramke():
    ust = {"adres": ADRES, "nazwa": ""}
    ot = types.SimpleNamespace(zapytaj_http=lambda url, czas: (401, {"jarvo": "panel-siec"}))
    assert panel_siec.sprawdz_nasluch(ust, PORT, ot)[0] == "bramka"
    ot.zapytaj_http = lambda url, czas: (200, {"hermes_home": "/x"})
    assert panel_siec.sprawdz_nasluch(ust, PORT, ot)[0] == "otwarty"
    ot.zapytaj_http = lambda url, czas: (401, {"detail": "Unauthorized"})          # cudzy serwer
    assert panel_siec.sprawdz_nasluch(ust, PORT, ot)[0] == "inny"
    ot.zapytaj_http = lambda url, czas: None
    assert panel_siec.sprawdz_nasluch(ust, PORT, ot)[0] == "brak"


def test_tailscale_status_json():
    dane = {"BackendState": "Running", "Self": {"TailscaleIPs": [ADRES, "fd7a:115c:a1e0::4e01:efde"],
                                                "DNSName": NAZWA + "."},
            "CurrentTailnet": {"MagicDNSEnabled": True}}
    assert panel_siec.z_tailscale_status(dane) == {"adres": ADRES, "nazwa": NAZWA, "zrodlo": "tailscale status"}
    dane["CurrentTailnet"]["MagicDNSEnabled"] = False
    assert panel_siec.z_tailscale_status(dane)["nazwa"] == ""
    with pytest.raises(panel_siec.BladSieci, match="nie jest połączony"):
        panel_siec.z_tailscale_status({"BackendState": "Stopped"})


def test_wtyczka_hq_ma_siec_py(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    import hqbuild
    assert "siec.py" in hqbuild.PLUGIN_FILES
    api = (REPO / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    assert 'siec = _load("jarvo_hq_siec", "siec.py")' in api and "siec.zahacz(core.JARVO_DIR" in api


# ---------------------------------------------------------------- próba z prawdziwym Hermesem (opcjonalna)

HERMES_SRC = os.environ.get("JARVO_TEST_HERMES_SRC")
PROBA_HERMESA = r'''
import json, os, sys, tempfile, importlib.util
from pathlib import Path
home = Path(sys.argv[2]); os.environ["HERMES_HOME"] = str(home)
spec = importlib.util.spec_from_file_location("siec", sys.argv[1]); s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
from starlette.testclient import TestClient
from hermes_cli import web_server as ws
from hermes_cli.dashboard_auth.registry import register_global_provider
ws.app.state.bound_host = "127.0.0.1"; ws.app.state.auth_required = False
ws.app.state.trusted_public_hosts = frozenset()
sc = s.Sciezki(home / "jarvo"); s.nowy_sekret(sc)
sesje = s.Sesje(sc); register_global_provider(s.dostawca_hermesa(sesje))
wynik = {}
lok = TestClient(ws.app, base_url="http://127.0.0.1:9119")
wynik["loopback_status"] = lok.get("/api/status").status_code
wynik["loopback_index_token"] = "__HERMES_SESSION_TOKEN__" in lok.get("/jarvo").text
wynik["loopback_zly_host"] = lok.get("/api/status", headers={"host": "100.102.239.120:9119"}).status_code
b = s.Bramka(ws.app, sesje, {"100.102.239.120"}, "127.0.0.1:9119")
siec = TestClient(b, base_url="http://100.102.239.120:9119", follow_redirects=False)
wynik["siec_zly_host"] = siec.get("/api/status", headers={"host": "evil.example:9119"}).status_code
wynik["siec_bez_sesji"] = siec.get("/api/status").status_code
wynik["siec_strona_bez_sesji"] = siec.get("/jarvo").status_code
wynik["logowanie_formularz"] = 'data-provider="jarvo"' in siec.get("/login").text
kod, _ = s.wydaj_klucz(sc)
r = siec.post("/auth/password-login", json={"provider": "jarvo", "username": "jarvo", "password": kod, "next": "/jarvo"})
wynik["logowanie"] = [r.status_code, r.json().get("next")]
wynik["drugi_raz"] = siec.post("/auth/password-login", json={"provider": "jarvo", "username": "jarvo",
                               "password": kod, "next": ""}).status_code
strona = siec.get("/jarvo")
wynik["strona"] = [strona.status_code, "__HERMES_SESSION_TOKEN__" in strona.text]
token = strona.text.split('__HERMES_SESSION_TOKEN__="')[1].split('"')[0]
wynik["api_z_tokenem"] = siec.get("/api/sessions", headers={"X-Hermes-Session-Token": token}).status_code
print(json.dumps(wynik))
'''


@pytest.mark.skipif(not HERMES_SRC, reason="ustaw JARVO_TEST_HERMES_SRC (checkout Hermesa z .venv), aby sprawdzić "
                                           "bramkę na prawdziwym dashboardzie")
def test_prawdziwy_hermes_loopback_bez_hasla_a_siec_z_kluczem(tmp_path):
    python = Path(HERMES_SRC) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    r = subprocess.run([str(python), "-c", PROBA_HERMESA, str(REPO / "hq" / "plugin" / "siec.py"),
                        str(tmp_path / "dane")], capture_output=True, text=True, cwd=HERMES_SRC, timeout=300,
                       env={**os.environ, "PYTHONPATH": HERMES_SRC, "HERMES_HOME": str(tmp_path / "dane")})
    assert r.returncode == 0, r.stderr[-3000:]
    w = json.loads(r.stdout.strip().splitlines()[-1])
    assert w["loopback_status"] == 200 and w["loopback_index_token"] is True      # loopback bez hasła jak dotąd
    assert w["loopback_zly_host"] == 400 and w["siec_zly_host"] == 400
    assert w["siec_bez_sesji"] == 401 and w["siec_strona_bez_sesji"] == 302 and w["logowanie_formularz"] is True
    assert w["logowanie"] == [200, "/jarvo"] and w["drugi_raz"] == 401
    assert w["strona"] == [200, True] and w["api_z_tokenem"] == 200


def test_proba_czyta_tresc_401_z_prawdziwego_http(tmp_path):
    """17.11 na żywo: zapytaj_http gubił treść odpowiedzi 401, więc doctor pisał „nie od bramki”, choć bramka działała."""
    import http.server
    import json as _json
    import threading

    from jarvo import instalator

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            b = _json.dumps({"error": "unauthenticated", "jarvo": "panel-siec"}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass

    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    try:
        kod, tresc = instalator.zapytaj_http(f"http://127.0.0.1:{s.server_port}/api/status", 3.0)
    finally:
        s.shutdown()
    assert kod == 401 and tresc["jarvo"] == "panel-siec"

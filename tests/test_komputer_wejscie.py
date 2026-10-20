"""Wejście Komputera Jarva (infra/komputer/wejscie.py, docs/KOMPUTER.md §6) z udawanym sterownikiem ekranu:
rozmowa MCP przez cua.sock (i przez bramkę floty), odmowy przed sterownikiem, ukrywanie sekretów, ster.sock."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "infra" / "komputer"))
import wejscie  # noqa: E402

KLUCZ = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"
STEROWNIK = textwrap.dedent('''
    import json, sys
    log = open(sys.argv[1], "a")
    KLUCZ = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"
    STAN = {"snapshot_id": "s1", "pid": 7, "window_id": 3, "screenshot_width": 800, "elements": [
        {"element_index": 0, "role": "document web", "label": "Sklep", "frame": {"x": 0, "y": 0, "w": 800, "h": 600}},
        {"element_index": 1, "parent_index": 4, "role": "entry", "label": "E-mail", "element_token": "s1:1"},
        {"element_index": 2, "parent_index": 4, "role": "push button", "label": "Dodaj do koszyka"},
        {"element_index": 3, "parent_index": 4, "role": "push button", "label": "Zapłać 129 zł"},
        {"element_index": 4, "parent_index": 0, "role": "form", "label": ""},
        {"element_index": 5, "parent_index": 4, "role": "password text", "label": "Hasło", "value": "tajne"},
        {"element_index": 6, "parent_index": 0, "role": "paragraph", "label": "Klucz " + KLUCZ}]}
    def pisz(m):
        sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    for linia in sys.stdin:
        m = json.loads(linia)
        if "id" not in m:
            continue
        metoda, i = m.get("method"), m["id"]
        log.write(json.dumps(m) + "\\n"); log.flush()
        if metoda == "initialize":
            pisz({"jsonrpc": "2.0", "id": i, "result": {"instructions": "sterownik", "capabilities": {}}})
        elif metoda == "tools/list":
            pisz({"jsonrpc": "2.0", "id": i, "result": {"tools": [{"name": n} for n in
                  ("click", "type_text", "get_window_state", "page", "clipboard_read", "mouse_button_down")]}})
        elif metoda == "ping":   # obca odpowiedź (id spoza żądań agenta) też idzie przez ukrywanie
            pisz({"jsonrpc": "2.0", "id": "obce", "result": {"content": [{"type": "text", "text": KLUCZ}]}})
            pisz({"jsonrpc": "2.0", "id": i, "error": {"code": 1, "message": "zły klucz " + KLUCZ}})
        elif metoda == "tools/call":
            nazwa = m["params"]["name"]
            sc = STAN if nazwa == "get_window_state" else {"ok": True}
            pisz({"jsonrpc": "2.0", "id": i, "result": {
                "content": [{"type": "text", "text": f"{nazwa} gotowe, {KLUCZ}"}], "structuredContent": sc}})
''')


class Dostepnosc:
    """Bez AT-SPI: fokus podany przez test, punkt na ekranie nieznany."""
    dziala = False
    fokus_pola: dict | None = None

    def fokus(self, pid):
        return self.fokus_pola

    def w_punkcie(self, pid, x, y, formularz=False):
        return None


@pytest.fixture
def komputer(monkeypatch):
    katalog = tempfile.mkdtemp(prefix="jw")            # krótka ścieżka: gniazdo unix ma limit ~100 znaków
    sterownik = os.path.join(katalog, "sterownik.py")
    with open(sterownik, "w", encoding="utf-8") as f:
        f.write(STEROWNIK)
    wywolania = os.path.join(katalog, "wywolania.jsonl")
    stan = os.path.join(katalog, "stan")
    for nazwa, wartosc in {"CUA": os.path.join(katalog, "cua.sock"), "STER": os.path.join(katalog, "ster.sock"),
                           "STAN": stan, "DZIENNIK": os.path.join(stan, "dziennik.jsonl"),
                           "PAUZA": os.path.join(stan, "pauza"), "LIMIT_DZIALAN": 6,
                           "STEROWNIK": [sys.executable, "-I", sterownik, wywolania]}.items():
        monkeypatch.setattr(wejscie, nazwa, wartosc)
    monkeypatch.setattr(wejscie, "Dostepnosc", Dostepnosc)
    w = wejscie.Wejscie()
    threading.Thread(target=w.start, daemon=True).start()
    for _ in range(100):
        if os.path.exists(wejscie.CUA) and os.path.exists(wejscie.STER):
            break
        time.sleep(0.02)

    class K:
        sciezka = katalog
        wejscie = w

        @staticmethod
        def do_sterownika() -> list[dict]:
            try:
                with open(wywolania, encoding="utf-8") as f:
                    return [json.loads(x) for x in f]
            except FileNotFoundError:
                return []

    yield K
    for s in list(w.sesje):
        s.zamknij()
    shutil.rmtree(katalog, ignore_errors=True)


class Klient:
    def __init__(self, sciezka: str):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(10)
        self.s.connect(sciezka)
        self.f = self.s.makefile("rb")
        self.n = 0

    def wyslij(self, msg) -> None:
        self.s.sendall((msg if isinstance(msg, bytes) else json.dumps(msg).encode()) + b"\n")

    def czytaj(self) -> dict:
        return json.loads(self.f.readline())

    def rpc(self, metoda: str, params: dict | None = None) -> dict:
        self.n += 1
        self.wyslij({"jsonrpc": "2.0", "id": self.n, "method": metoda, "params": params or {}})
        while True:
            m = self.czytaj()
            if m.get("id") == self.n:
                return m

    def narzedzie(self, nazwa: str, args: dict) -> dict:
        return self.rpc("tools/call", {"name": nazwa, "arguments": args})["result"]

    def zamknij(self) -> None:
        self.f.close()                  # makefile trzyma deskryptor: bez tego wejście nie zobaczy końca połączenia
        self.s.close()


def ster(sciezka: str, polecenie: str, **kw) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(sciezka)
    s.sendall((json.dumps({"polecenie": polecenie, **kw}) + "\n").encode())
    dane = b""
    while not dane.endswith(b"\n"):
        k = s.recv(65536)
        if not k:
            break
        dane += k
    s.close()
    return json.loads(dane)


def kod(wynik: dict) -> str:
    return str((wynik.get("structuredContent") or {}).get("code") or ("blad" if wynik.get("isError") else "ok"))


def zasada(wynik: dict) -> str:
    return str((wynik.get("structuredContent") or {}).get("rule") or "")


def test_gniazda_tylko_dla_grupy():
    katalog = tempfile.mkdtemp(prefix="jw")
    try:
        s = wejscie.Wejscie._gniazdo(None, os.path.join(katalog, "x.sock"))
        assert oct(os.stat(os.path.join(katalog, "x.sock")).st_mode & 0o777) == "0o660"
        s.close()
    finally:
        shutil.rmtree(katalog)


def test_rozmowa_mcp_odmowy_i_ukrywanie(komputer):
    k = Klient(wejscie.CUA)
    init = k.rpc("initialize", {"protocolVersion": "2025-06-18"})
    assert init["result"]["instructions"].startswith("sterownik") and "Komputer Jarva" in init["result"]["instructions"]
    narzedzia = {t["name"] for t in k.rpc("tools/list")["result"]["tools"]}
    assert narzedzia == {"click", "type_text", "get_window_state"}

    stan = k.narzedzie("get_window_state", {"pid": 7, "window_id": 3})
    calosc = json.dumps(stan, ensure_ascii=False)
    assert KLUCZ not in calosc and "tajne" not in calosc and wejscie.zasady.ZNACZNIK in calosc

    # odmowy nie dochodzą do sterownika
    przed = len(komputer.do_sterownika())
    assert kod(k.narzedzie("page", {"action": "execute_javascript"})) == "zablokowane"
    assert kod(k.narzedzie("click", {"pid": 7, "window_id": 3, "element_token": "s1:3"})) == "wymaga_czlowieka"
    assert zasada(k.narzedzie("click", {"element_token": "obca:3"})) == "nieznany_cel"
    assert zasada(k.narzedzie("click", {"pid": 7, "x": 10, "y": 10})) == "punkt_w_tle"
    assert zasada(k.narzedzie("double_click", {"pid": 7, "x": 10, "y": 10})) == "nieznany_cel"   # punkt bez AT-SPI
    w = k.narzedzie("type_text", {"pid": 7, "window_id": 3, "element_token": "s1:1", "text": "a@b.pl\n"})
    assert zasada(w) == "formularz_wrazliwy"                     # Enter w polu formularza z „Zapłać”
    assert zasada(k.narzedzie("type_text", {"pid": 7, "text": "abc"})) == "brak_fokusu"
    Dostepnosc.fokus_pola = {"rola": "password text", "nazwa": "Hasło"}
    try:
        assert zasada(k.narzedzie("type_text", {"pid": 7, "text": "tajne"})) == "pole_wrazliwe"
    finally:
        Dostepnosc.fokus_pola = None
    assert len(komputer.do_sterownika()) == przed

    # dozwolone idą do sterownika, a ich odpowiedź traci sekrety
    w = k.narzedzie("click", {"pid": 7, "window_id": 3, "element_token": "s1:2"})
    assert kod(w) == "ok" and KLUCZ not in json.dumps(w)
    assert komputer.do_sterownika()[-1]["params"]["name"] == "click"
    k.zamknij()


def test_protokol_tylko_pojedyncze_znane_wiadomosci(komputer):
    k = Klient(wejscie.CUA)
    k.wyslij(b"{nie json")
    assert k.czytaj()["error"]["code"] == -32700
    k.wyslij([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    assert k.czytaj()["error"]["code"] == -32600
    assert k.rpc("resources/list")["error"]["code"] == -32601
    assert k.rpc("tools/call", {"name": "click", "arguments": ["s1:3"]})["error"]["code"] == -32602
    # obca odpowiedź sterownika i komunikat błędu też bez sekretów
    k.n += 1
    k.wyslij({"jsonrpc": "2.0", "id": k.n, "method": "ping"})
    odp = [k.czytaj(), k.czytaj()]
    assert KLUCZ not in json.dumps(odp) and {m["id"] for m in odp} == {"obce", k.n}
    k.zamknij()


def test_powtorzone_id_odrzucone(komputer):
    k = Klient(wejscie.CUA)
    k.rpc("initialize")
    msg = {"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {
        "name": "get_window_state", "arguments": {"pid": 7, "window_id": 3}}}
    drugie = {**msg, "params": {"name": "click", "arguments": {"element_token": "s1:2"}}}
    k.s.sendall((json.dumps(msg) + "\n" + json.dumps(drugie) + "\n").encode())    # razem: pierwsze jeszcze w toku
    odp = [k.czytaj(), k.czytaj()]
    assert sorted(("error" in m) for m in odp) == [False, True]
    assert next(m for m in odp if "error" in m)["error"]["code"] == -32600
    assert KLUCZ not in json.dumps(odp)
    k.zamknij()


def test_pauza_limit_i_dziennik(komputer, monkeypatch):
    k = Klient(wejscie.CUA)
    k.rpc("initialize")
    k.narzedzie("get_window_state", {"pid": 7, "window_id": 3})
    odp = ster(wejscie.STER, "pauza")
    assert (odp["ok"], odp["wstrzymane"], odp["sesje"], odp["pauza"]["kto"]) == (True, True, 1, "wlasciciel")
    assert os.path.exists(wejscie.PAUZA)                       # pauza przetrwa restart wejścia
    assert wejscie.Ekran(Dostepnosc()).wstrzymane
    assert kod(k.narzedzie("click", {"element_token": "s1:2"})) == "wstrzymane"
    assert kod(k.narzedzie("get_window_state", {"pid": 7, "window_id": 3})) == "ok"
    # agent floty (inny uid) pauzy nie zdejmie
    with monkeypatch.context() as m:
        m.setattr(wejscie, "wolno_wznowic", lambda uid: False)
        odp = ster(wejscie.STER, "wznow")
    assert odp["ok"] is False and odp["wstrzymane"] is True and "jarvo komputer wznow" in odp["blad"]
    assert ster(wejscie.STER, "wznow")["wstrzymane"] is False and not os.path.exists(wejscie.PAUZA)

    Dostepnosc.fokus_pola = {"rola": "entry", "nazwa": "Uwagi"}
    try:
        wyniki = [kod(k.narzedzie("type_text", {"pid": 7, "text": "Proszę o fakturę"})) for _ in range(7)]
    finally:
        Dostepnosc.fokus_pola = None
    assert wyniki[:6] == ["ok"] * 6 and wyniki[6] == "zablokowane"          # LIMIT_DZIALAN = 6 w teście

    wpisy = ster(wejscie.STER, "dziennik", n=200)["wpisy"]
    decyzje = {w["decyzja"] for w in wpisy}
    assert {"pauza", "wznow", "wstrzymane", "tak", "odmowa", "ukryte"} <= decyzje
    assert any(w.get("zasada") == "limit" for w in wpisy) and any(w.get("zasada") == "wznow_z_floty" for w in wpisy)
    plik = open(wejscie.DZIENNIK, encoding="utf-8").read()
    assert "Proszę o fakturę" not in plik and KLUCZ not in plik and '"znaki": 16' in plik
    assert ster(wejscie.STER, "co?")["ok"] is False
    k.zamknij()
    assert len(wejscie.Dziennik().ostatnie) == len(open(wejscie.DZIENNIK, encoding="utf-8").readlines())


def test_bramka_floty_pompuje_do_wejscia(komputer):
    """Hermes woła `jarvo_cua.py mcp`: bramka przepuszcza bajty do cua.sock i z powrotem."""
    p = subprocess.Popen([sys.executable, "-I", str(REPO / "komputer" / "jarvo_cua.py"), "mcp"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env={**os.environ, "JARVO_KOMPUTER_GNIAZDO": wejscie.CUA})
    try:
        wejscie_msg = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                       {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                           "name": "clipboard_read", "arguments": {}}}]
        wyjscie, _ = p.communicate("".join(json.dumps(m) + "\n" for m in wejscie_msg).encode(), timeout=20)
    finally:
        if p.poll() is None:
            p.kill()
    odp = {m["id"]: m for m in map(json.loads, wyjscie.splitlines())}
    assert p.returncode == 0
    assert "Komputer Jarva" in odp[1]["result"]["instructions"]
    assert odp[2]["result"]["structuredContent"]["code"] == "zablokowane"


def test_prosba_operatora_to_pauza_z_powodem(komputer, monkeypatch):
    """Operator oddaje ekran właścicielowi: pauza od floty z powodem; wznawia tylko właściciel."""
    k = Klient(wejscie.CUA)
    k.rpc("initialize")
    k.narzedzie("get_window_state", {"pid": 7, "window_id": 3})
    with monkeypatch.context() as m:
        m.setattr(wejscie, "wolno_wznowic", lambda uid: False)
        odp = ster(wejscie.STER, "pauza", powod="Zaloguj się do panelu\nsklepu, klucz " + KLUCZ)
        assert odp["pauza"]["kto"] == "flota" and "\n" not in odp["pauza"]["powod"]
        assert KLUCZ not in json.dumps(odp) and odp["pauza"]["opis"].startswith("Operator czeka na właściciela: Zaloguj")
        w = k.narzedzie("click", {"element_token": "s1:2"})
        assert kod(w) == "wstrzymane" and "Zaloguj się do panelu" in w["content"][0]["text"]
        assert w["structuredContent"]["next_step"] == "wait_for_owner"
        assert ster(wejscie.STER, "wznow")["wstrzymane"] is True
    assert "Zaloguj" not in open(wejscie.DZIENNIK, encoding="utf-8").read()       # powód tylko w stanie, nie w dzienniku
    # pauzy właściciela flota nie nadpisze swoją prośbą
    ster(wejscie.STER, "pauza", powod="przerwa")
    with monkeypatch.context() as m:
        m.setattr(wejscie, "wolno_wznowic", lambda uid: False)
        assert ster(wejscie.STER, "pauza", powod="inna prośba")["pauza"]["kto"] == "wlasciciel"
    assert ster(wejscie.STER, "stan")["pauza"]["opis"] == "właściciel zatrzymał Komputer: przerwa"
    assert ster(wejscie.STER, "wznow")["wstrzymane"] is False and "pauza" not in ster(wejscie.STER, "stan")
    # stary plik pauzy z K2 (sama data) dalej wstrzymuje
    with open(wejscie.PAUZA, "w", encoding="utf-8") as f:
        f.write("2026-10-19T10:00:00+00:00\n")
    assert wejscie.Ekran(Dostepnosc()).powod_pauzy == "właściciel zatrzymał Komputer"
    k.zamknij()


def test_ekranem_steruje_jedna_sesja_naraz(komputer, monkeypatch):
    a, b = Klient(wejscie.CUA), Klient(wejscie.CUA)
    for k in (a, b):
        k.rpc("initialize")
        k.narzedzie("get_window_state", {"pid": 7, "window_id": 3})          # patrzeć wolno obu
    assert kod(a.narzedzie("click", {"element_token": "s1:2"})) == "ok"
    w = b.narzedzie("click", {"element_token": "s1:2"})
    assert zasada(w) == "zajete" and w["structuredContent"]["next_step"] == "wait_and_retry"
    assert kod(b.narzedzie("get_window_state", {"pid": 7, "window_id": 3})) == "ok"
    assert kod(a.narzedzie("click", {"element_token": "s1:2"})) == "ok"
    a.zamknij()                                                             # koniec sesji zwalnia ekran
    for _ in range(300):
        if len(komputer.wejscie.sesje) == 1:
            break
        time.sleep(0.02)
    assert kod(b.narzedzie("click", {"element_token": "s1:2"})) == "ok"
    c = Klient(wejscie.CUA)
    c.rpc("initialize")
    c.narzedzie("get_window_state", {"pid": 7, "window_id": 3})
    assert zasada(c.narzedzie("click", {"element_token": "s1:2"})) == "zajete"
    monkeypatch.setattr(wejscie, "ZAJETE_S", 0)                             # sesja bez działań oddaje ekran
    assert kod(c.narzedzie("click", {"element_token": "s1:2"})) == "ok"
    b.zamknij()
    c.zamknij()


def test_wtyczka_operatora_przez_ster(komputer, monkeypatch):
    """Wtyczka jarvo-komputer (komputer/plugin, docs/KOMPUTER.md §7): stan, dziennik i prośba do właściciela
    przez prawdziwe wejście; wznowić nie umie, bez gniazda mówi, jak włączyć Komputer."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvo_komputer_plugin", REPO / "komputer" / "plugin" / "__init__.py")
    pl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pl)
    monkeypatch.setattr(pl, "STER", wejscie.STER)
    monkeypatch.setattr(wejscie, "wolno_wznowic", lambda uid: False)         # agent we flocie, nie właściciel
    narzedzia = []

    class Ctx:
        def register_tool(self, **kw):
            narzedzia.append(kw)

    pl.register(Ctx())
    assert [n["name"] for n in narzedzia] == ["komputer"] and narzedzia[0]["toolset"] == "komputer"
    assert narzedzia[0]["schema"]["parameters"]["properties"]["akcja"]["enum"] == ["stan", "dziennik", "oddaj"]
    obsluz = narzedzia[0]["handler"]
    stan = json.loads(obsluz({"akcja": "stan"}))
    assert stan["ok"] and stan["dziala"] and not stan["wstrzymane"] and "pauza" not in stan
    assert not stan["drzewo_dostepnosci"] and "som" in stan["uwaga"]
    assert "blad" in json.loads(obsluz({"akcja": "oddaj", "prosba": "zrób"}))     # prośba bez treści
    assert "blad" in json.loads(obsluz({"akcja": "wznow"}))
    odp = json.loads(obsluz({"akcja": "oddaj", "prosba": "Zaloguj się do panelu sklepu,\nkliknij Dalej"}))
    assert odp["wstrzymane"] and odp["kto_wstrzymal"].startswith("Operator") and "capture" in odp["dalej"]
    assert odp["pauza"] == "Operator czeka na właściciela: Zaloguj się do panelu sklepu, kliknij Dalej"
    assert ster(wejscie.STER, "stan")["wstrzymane"] is True                   # narzędzie nie wysyła wznow
    wpisy = json.loads(obsluz({"akcja": "dziennik", "n": 5}))["wpisy"]
    assert wpisy and wpisy[-1]["decyzja"] == "pauza" and wpisy[-1]["kto"] == "flota" and len(wpisy) <= 5
    assert json.loads(obsluz({"akcja": "dziennik", "n": True}))["ok"]            # zła liczba → domyślne 20
    monkeypatch.setattr(wejscie, "wolno_wznowic", lambda uid: True)
    ster(wejscie.STER, "pauza", powod="przerwa")                               # właściciel zatrzymał wcześniej
    monkeypatch.setattr(wejscie, "wolno_wznowic", lambda uid: False)
    odp = json.loads(obsluz({"akcja": "oddaj", "prosba": "kliknij Zapłać w Ekranie HQ"}))
    assert odp["kto_wstrzymal"] == "właściciel" and odp["dalej"].startswith("Właściciel już wstrzymał")
    monkeypatch.setattr(pl, "STER", os.path.join(komputer.sciezka, "brak.sock"))
    wyl = json.loads(obsluz({"akcja": "stan"}))
    assert wyl["ok"] is False and wyl["dziala"] is False and "jarvo komputer on" in wyl["blad"]


# --- AT-SPI i okna X11 bez pulpitu: udawane obiekty


class _Stany:
    def __init__(self, stany):
        self.stany = set(stany)

    def contains(self, s):
        return s in self.stany

    def get_states(self):
        return [type("S", (), {"value_nick": s})() for s in self.stany]


class Acc:
    """Udawany element AT-SPI: rola, nazwa, dzieci, stany, prostokąt na ekranie."""

    def __init__(self, rola, nazwa="", dzieci=(), stany=("showing",), ramka=(0, 0, 0, 0), pid=7, tag=""):
        self.rola, self.nazwa, self.dzieci, self.rodzic = rola, nazwa, list(dzieci), None
        self.stany, self.ramka, self.pid, self.tag = set(stany), ramka, pid, tag
        for d in self.dzieci:
            d.rodzic = self

    def get_role_name(self):
        return self.rola

    def get_name(self):
        return self.nazwa

    def get_parent(self):
        return self.rodzic

    def get_child_count(self):
        return len(self.dzieci)

    def get_child_at_index(self, i):
        return self.dzieci[i]

    def get_state_set(self):
        return _Stany(self.stany)

    def get_attributes(self):
        return {"tag": self.tag} if self.tag else {}

    def get_process_id(self):
        return self.pid

    def get_extents(self, _uklad):
        return type("R", (), dict(zip(("x", "y", "width", "height"), self.ramka)))()

    def get_accessible_at_point(self, x, y, _uklad):
        for d in self.dzieci:
            rx, ry, rw, rh = d.ramka
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return d
        return None

    def get_application(self):
        a = self
        while a is not None and a.rola != "application":
            a = a.rodzic
        return a

    def clear_cache(self):
        self.wyczyszczone = getattr(self, "wyczyszczone", 0) + 1


class _Atspi:
    class StateType:
        FOCUSED, SHOWING = "focused", "showing"

    class CoordType:
        SCREEN = 0

    pulpit = None

    @classmethod
    def get_desktop(cls, _i):
        return cls.pulpit


class _GLib:
    PRIORITY_HIGH = 0
    zawies = False

    @classmethod
    def idle_add(cls, fn, priority=None):
        if not cls.zawies:
            fn()


def _dostepnosc(pulpit=None, zawies=False):
    d = wejscie.Dostepnosc.__new__(wejscie.Dostepnosc)
    d.dziala, d._fokus, d._lock = True, {}, threading.Lock()
    _Atspi.pulpit, _GLib.zawies = pulpit, zawies
    d.Atspi, d.GLib = _Atspi, _GLib
    return d


def _w_formularzu(pole, *, przyciski=("Zapłać 129 zł",), glebokosc=1, wypelniacz=0):
    zagniezdzone = pole
    for _ in range(glebokosc - 1):
        zagniezdzone = Acc("section", dzieci=[zagniezdzone])
    reszta = [Acc("section", dzieci=[Acc("paragraph") for _ in range(100)]) for _ in range(wypelniacz // 100)]
    forma = Acc("form", dzieci=[zagniezdzone, *reszta, *(Acc("push button", n) for n in przyciski)])
    return Acc("document web", dzieci=[forma])


def test_formularz_przeszukany_do_konca_albo_nieznany(monkeypatch):
    d = _dostepnosc()
    pole = Acc("entry", "E-mail")
    _w_formularzu(pole, glebokosc=13, wypelniacz=600)    # dawniej: 12 poziomów i 300 elementów, potem „bez formularza”
    assert d._formularz(pole) == {"w_formularzu": True, "formularz": [{"rola": "push button", "nazwa": "Zapłać 129 zł"}]}
    szukaj = Acc("entry", "Szukaj")
    Acc("document web", dzieci=[Acc("section", dzieci=[szukaj])])
    assert d._formularz(szukaj) == {"w_formularzu": False, "formularz": []}
    # przegląd ucięty limitem: formularz nieznany (Enter sprawdzi właściciel), nie „bez przycisków”
    monkeypatch.setattr(wejscie, "MAKS_FORMULARZ", 50)
    assert d._formularz(pole) is None
    monkeypatch.setattr(wejscie, "MAKS_FORMULARZ", 3000)
    monkeypatch.setattr(wejscie, "MAKS_DZIECI", 50)
    assert d._formularz(pole) is None
    monkeypatch.setattr(wejscie, "MAKS_PRZODKOWIE", 5)
    assert d._formularz(pole) is None


def test_formularz_przez_collection_jednym_zapytaniem():
    d = _dostepnosc()

    class Regula:
        @staticmethod
        def new(*a):
            return "regula"

    d.Atspi = type("A", (_Atspi,), {"MatchRule": Regula, "StateSet": type("SS", (), {"new": staticmethod(list)}),
                                     "CollectionMatchType": type("M", (), {"ALL": 0, "ANY": 1}),
                                     "Role": type("R", (), {"PUSH_BUTTON": 42}),
                                     "CollectionSortOrder": type("O", (), {"CANONICAL": 0})})
    pole = Acc("entry", "E-mail")
    dok = _w_formularzu(pole, przyciski=())
    forma = dok.dzieci[0]
    forma.get_matches = lambda regula, porz, ile, wglab: [Acc("push button", "Kup teraz"), Acc("push button", "")]
    assert d._formularz(pole)["formularz"] == [{"rola": "push button", "nazwa": "Kup teraz"}]


def test_fokus_sprawdzany_na_zywo():
    d = _dostepnosc()
    pole = Acc("entry", "Uwagi", stany=("showing", "focused", "multi-line", "editable"), tag="textarea")
    app = Acc("application", "Chromium", dzieci=[_w_formularzu(pole)])
    d._fokus[7] = (d._opis(pole), pole)
    f = d.fokus(7)
    assert f["nazwa"] == "Uwagi" and f["w_formularzu"] and f["stany"] == ["editable", "multi-line"]
    assert app.wyczyszczone == 1                     # stany czytane od programu, nie z pamięci libatspi
    # Tab przeniósł fokus, zanim doszło zdarzenie: pole już nie ma stanu focused, więc fokus nieznany
    pole.stany.discard("focused")
    assert d.fokus(7) is wejscie.zasady.NIEZNANY
    # utrata fokusu (zdarzenie z detail1=0) czyści pamięć tego programu
    zdarzenie = type("E", (), {"detail1": 0, "source": pole})()
    d._zdarzenie(zdarzenie)
    assert d.fokus(7) is None


def test_atspi_bez_odpowiedzi_albo_z_bledem_to_cel_nieznany():
    d = _dostepnosc(zawies=True)
    assert d._w_glib(lambda: {"ok": 1}, czas=0.05) is wejscie.BLAD
    d = _dostepnosc()
    assert d._w_glib(lambda: 1 / 0) is wejscie.BLAD
    d.dziala = False
    assert d._w_glib(lambda: {"ok": 1}) is wejscie.BLAD
    d = _dostepnosc(zawies=True)
    pole = Acc("entry", "E-mail", stany=("showing", "focused"))
    d._fokus[7] = (d._opis(pole), pole)
    assert d.fokus(7) is wejscie.zasady.NIEZNANY


def test_w_punkcie_tylko_w_oknie_celu():
    zaplac = Acc("push button", "Zapłać", ramka=(600, 400, 100, 30))
    popup = Acc("frame", "Płatność – Chromium", dzieci=[zaplac], ramka=(500, 300, 400, 300))
    glowne = Acc("frame", "Sklep – Chromium", dzieci=[Acc("paragraph", "Opis", ramka=(0, 0, 1440, 900))],
                 ramka=(0, 0, 1440, 900))
    ukryte = Acc("frame", "", ramka=(500, 300, 400, 300), stany=())
    app = Acc("application", "Chromium", dzieci=[glowne, popup, ukryte])
    d = _dostepnosc(Acc("desktop", dzieci=[app]))
    # punkt (620, 410) leży w obu oknach: liczy się okno celu, nie pierwsze z listy
    assert d.w_punkcie(7, 620, 410, (500, 300, 400, 300))["nazwa"] == "Zapłać"
    assert d.w_punkcie(7, 620, 410, (0, 0, 1440, 900))["nazwa"] == "Opis"
    assert d.w_punkcie(8, 620, 410, (500, 300, 400, 300)) is None           # inny proces
    assert d.w_punkcie(7, 620, 410, (10, 10, 400, 300)) is None             # żadne okno nie pasuje
    drugie = Acc("frame", "Drugie – Chromium", ramka=(500, 300, 400, 300))
    app.dzieci.append(drugie)
    assert d.w_punkcie(7, 620, 410, (500, 300, 400, 300)) is None           # dwa pasujące, bez tytułu
    assert d.w_punkcie(7, 620, 410, (500, 300, 400, 300), "Płatność – Chromium")["nazwa"] == "Zapłać"
    # libatspi nie widzi nowych okien bez zdarzeń: pamięć programu czyszczona przy każdym pytaniu
    assert app.wyczyszczone == 5                     # wszystkie pytania o program 7 (bez pytania o 8)


class _X11:
    def __init__(self, geometria=(500, 300, 800, 600), wierzch=True):
        self.g, self.wierzch, self.pytania = geometria, wierzch, []

    def geometria(self, okno):
        return self.g

    def ekran(self):
        return (1440, 900)

    def na_wierzchu(self, x, y, okno):
        self.pytania.append((x, y, okno))
        return self.wierzch


class _DostepnoscPunkt:
    dziala = True

    def __init__(self, wynik=None, kolejne=None):
        self.wynik = wynik if wynik is not None else {"rola": "push button", "nazwa": "Zapłać 129 zł"}
        self.kolejne = list(kolejne or [])            # odpowiedzi po kolei (Chromium: zgadywanie, potem trafienie)
        self.pytania = []

    def w_punkcie(self, pid, x, y, ramka, tytul="", formularz=False):
        self.pytania.append((pid, x, y, ramka, tytul))
        return self.kolejne.pop(0) if self.kolejne else self.wynik


def _kontekst(monkeypatch, x11=None, dostepnosc=None, pid_okna=7):
    ekran = type("E", (), {})()
    ekran.x11, ekran.dostepnosc = x11 or _X11(), dostepnosc or _DostepnoscPunkt()
    ekran.wstrzymane, ekran.powod_pauzy = False, ""
    ctx = wejscie.KontekstSesji(ekran)
    monkeypatch.setattr(ctx, "pid_okna", lambda okno: pid_okna)
    monkeypatch.setattr(ctx, "_tytul", lambda okno: "Sklep – Chromium")
    monkeypatch.setattr(ctx, "aktywne_okno", lambda: 3)
    monkeypatch.setattr(wejscie.time, "sleep", lambda s: None)
    return ctx


NA_WIERZCHU = {"pid": 7, "window_id": 3, "delivery_mode": "foreground"}   # klik w punkt w aktywnym oknie 3


def test_klik_w_punkt_sprawdzany_tam_gdzie_kliknie_sterownik(monkeypatch):
    ctx = _kontekst(monkeypatch)
    args = {**NA_WIERZCHU, "x": 100, "y": 50}
    assert ctx.cel("click", args)["nazwa"] == "Zapłać 129 zł"
    # początek okna na żywo z X11 (okno nie w rogu ekranu), nie z elementu 0 migawki
    assert ctx.ekran.dostepnosc.pytania[-1] == (7, 600.0, 350.0, (500, 300, 800, 600), "Sklep – Chromium")
    assert wejscie.zasady.ocen("click", args, ctx).decyzja == wejscie.zasady.CZLOWIEK
    # zrzut zmniejszony (800 → 400 px): sterownik mnoży x i y przez 2 dla tego procesu
    ctx.zapamietaj("get_window_state", {"pid": 7, "window_id": 3}, {"pid": 7, "window_id": 3, "screenshot_width": 400})
    ctx.cel("click", args)
    assert ctx.ekran.dostepnosc.pytania[-1][1:3] == (700.0, 400.0)
    ctx.zapamietaj("get_window_state", {"pid": 7, "window_id": 3}, {"pid": 7, "window_id": 3, "screenshot_width": 800})
    ctx.cel("click", args)
    assert ctx.ekran.dostepnosc.pytania[-1][1:3] == (600.0, 350.0)


@pytest.mark.parametrize("przypadek", ["inny_proces", "poza_oknem", "przykryte", "okienko_nieznane",
                                       "pulpit", "bez_okna", "atspi_nic", "brak_geometrii"])
def test_klik_w_punkt_niepewny_to_odmowa(monkeypatch, przypadek):
    x11 = _X11(wierzch={"przykryte": False, "okienko_nieznane": None}.get(przypadek, True),
               geometria=None if przypadek == "brak_geometrii" else (500, 300, 800, 600))
    dost = _DostepnoscPunkt()
    if przypadek == "atspi_nic":
        dost.w_punkcie = lambda *a, **k: None
    ctx = _kontekst(monkeypatch, x11=x11, dostepnosc=dost, pid_okna=8 if przypadek == "inny_proces" else 7)
    args = {"pid": 7, "window_id": 3, "x": 900 if przypadek == "poza_oknem" else 100, "y": 50}
    if przypadek == "pulpit":
        args["scope"] = "desktop"
    if przypadek == "bez_okna":
        del args["window_id"]
    assert ctx.cel("click", args) is wejscie.zasady.NIEZNANY
    # podwójny klik idzie zdarzeniem do okna: też sprawdzany w punkcie
    w = wejscie.zasady.ocen("double_click", args, ctx)
    assert w.decyzja == wejscie.zasady.ODMOWA and w.kod == "nieznany_cel"


def test_element_w_punkcie_dopiero_po_dwoch_zgodnych_odpowiedziach(monkeypatch):
    """Chromium najpierw zgaduje z drzewa (bez warstw), a trafienie silnika strony daje przy następnym pytaniu."""
    tekst, zaplac = {"rola": "document web", "nazwa": "Sklep"}, {"rola": "push button", "nazwa": "Zapłać teraz"}
    dost = _DostepnoscPunkt(kolejne=[tekst, zaplac, zaplac])
    ctx = _kontekst(monkeypatch, dostepnosc=dost)
    args = {**NA_WIERZCHU, "x": 100, "y": 50}
    assert ctx.cel("click", args) == zaplac and len(dost.pytania) == 3
    assert wejscie.zasady.ocen("click", args, _kontekst(monkeypatch, dostepnosc=_DostepnoscPunkt(
        kolejne=[tekst, zaplac, zaplac]))).kod == "przycisk_wrazliwy"
    # zgodne od razu: dwa pytania
    dost = _DostepnoscPunkt()
    assert _kontekst(monkeypatch, dostepnosc=dost).cel("click", args)["nazwa"] == "Zapłać 129 zł"
    assert len(dost.pytania) == 2
    # trzy różne odpowiedzi: cel nieznany
    dost = _DostepnoscPunkt(kolejne=[tekst, zaplac, {"rola": "link", "nazwa": "Regulamin"}])
    assert _kontekst(monkeypatch, dostepnosc=dost).cel("click", args) is wejscie.zasady.NIEZNANY


def test_migawka_mowi_czy_pole_jest_w_formularzu(monkeypatch):
    ctx = _kontekst(monkeypatch)
    ctx.zapamietaj("get_window_state", {"pid": 7, "window_id": 3}, {"snapshot_id": "s", "pid": 7, "window_id": 3, "elements": [
        {"element_index": 0, "role": "document web"},
        {"element_index": 1, "parent_index": 0, "role": "form"},
        {"element_index": 2, "parent_index": 1, "role": "entry", "label": "E-mail"},
        {"element_index": 3, "parent_index": 1, "role": "push button", "label": "Zapłać"},
        {"element_index": 4, "parent_index": 0, "role": "entry", "label": "Szukaj"},
        {"element_index": 5, "parent_index": 99, "role": "entry", "label": "Sierota"}]})
    assert ctx.cel("type_text", {"element_token": "s:2"})["w_formularzu"] is True
    assert ctx.cel("type_text", {"element_token": "s:4"})["w_formularzu"] is False
    assert ctx.cel("type_text", {"element_token": "s:5"}).get("formularz_nieznany") is True


class _Xlib:
    """Udawany libX11 dla okna.X11: drzewo okien (rodzice) i okno, które serwer X wskazuje w punkcie."""

    KORZEN = 1

    def __init__(self, rodzice, w_punkcie, podreczne=(), niewidoczne=()):
        self.rodzice, self.w_punkcie = rodzice, w_punkcie
        self.podreczne, self.niewidoczne, self.punkty = set(podreczne), set(niewidoczne), []

    def XQueryTree(self, d, okno, korzen, rodzic, dzieci, n):
        if okno not in self.rodzice:
            return 0
        rodzic._obj.value, n._obj.value = self.rodzice[okno], 0
        return 1

    def XTranslateCoordinates(self, d, z, do, x, y, gx, gy, dziecko):
        assert z == do == self.KORZEN
        self.punkty.append((x, y))
        dziecko._obj.value = self.w_punkcie(x, y)
        return 1

    def XGetWindowAttributes(self, d, okno, a):
        a._obj.map_state = 0 if okno in self.niewidoczne else wejscie.okna.MAPA_WIDOCZNE
        a._obj.override_redirect = int(okno in self.podreczne)
        return 1

    def XFree(self, p):
        pass


def _x11(xlib):
    x = wejscie.okna.X11.__new__(wejscie.okna.X11)
    x._zapytaj = lambda fn: fn(xlib, 0, _Xlib.KORZEN)
    return x


def test_okno_na_wierzchu_tak_jak_widzi_je_serwer_x():
    # klient 30 w ramce menedżera okien 20; w punkcie (100, 100) jest ta ramka, w (700, 500) okienko podręczne 40,
    # a nakładka sterownika z kursorem agenta (przezroczysta dla kliknięć) nie pojawia się w odpowiedzi serwera
    rodzice = {30: 20, 20: 1, 40: 1, 50: 1}
    xlib = _Xlib(rodzice, lambda x, y: 40 if x > 600 else 20, podreczne={40})
    x = _x11(xlib)
    assert x.na_wierzchu(100.7, 100.2, 30) is True and xlib.punkty[-1] == (100, 100)
    assert x.na_wierzchu(700, 500, 30) is False
    # inne zwykłe okno nad punktem
    assert _x11(_Xlib(rodzice, lambda x, y: 50)).na_wierzchu(100, 100, 30) is False
    # okna nie ma (zamknięte) albo jest samo okienkiem podręcznym albo niewidoczne
    assert _x11(_Xlib(rodzice, lambda x, y: 20)).na_wierzchu(100, 100, 99) is None
    assert _x11(_Xlib(rodzice, lambda x, y: 40, podreczne={40})).na_wierzchu(700, 500, 40) is False
    assert _x11(_Xlib(rodzice, lambda x, y: 20, niewidoczne={20})).na_wierzchu(100, 100, 30) is False

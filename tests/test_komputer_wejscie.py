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
    assert zasada(k.narzedzie("click", {"pid": 7, "x": 10, "y": 10})) == "nieznany_cel"   # punkt bez AT-SPI
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

"""Komputer Jarva natywnie bez przeglądarki (docs/NATYWNIE.md J03, J04, J09, N13): wejście z twardymi zasadami
(komputer/wejscie_natywne.py) na atrapie sterownika CDP, kanały usługi, bramka floty w trybie natywnym
(komputer/jarvo_cua.py: potok albo gniazdo, PID usługi), wtyczka Operatora i polecenie `jarvo komputer`.

Bramka idzie osobnym procesem tą samą drogą co Hermes (`python -I jarvo_cua.py mcp`, JARVO_ROOT w otoczeniu).
Kanały: potok nazwany z DACL właściciela na Windows, gniazdo 0600 na macOS i Linuksie, więc testy biegną wszędzie.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO))
from jarvo import komputer as jk  # noqa: E402
from jarvo import sciezki  # noqa: E402
from komputer import kanal, wejscie_natywne  # noqa: E402

zasady = wejscie_natywne.zasady
BRAMKA = REPO / "komputer" / "jarvo_cua.py"
KLUCZ = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890"
PID = 4242


def _elementy(zmiana: bool = False) -> list[dict]:
    el = [{"element_index": 0, "role": "document web", "label": "Sklep", "depth": 0},
          {"element_index": 1, "parent_index": 0, "role": "form", "label": "", "depth": 1},
          {"element_index": 2, "parent_index": 1, "role": "entry", "label": "E-mail", "depth": 2},
          {"element_index": 3, "parent_index": 1, "role": "push button", "label": "Dodaj do koszyka", "depth": 2},
          {"element_index": 4, "parent_index": 1, "role": "push button", "label": "Zapłać 129 zł", "depth": 2},
          {"element_index": 5, "parent_index": 1, "role": "password text", "label": "Hasło", "value": "tajne",
           "depth": 2},
          {"element_index": 6, "parent_index": 0, "role": "paragraph", "label": "Klucz " + KLUCZ, "depth": 1}]
    if zmiana:                                  # strona dodała przycisk na początku formularza: numery się przesuwają
        el = el[:2] + [{"element_index": 2, "parent_index": 1, "role": "push button", "label": "Baner", "depth": 2}] + [
            {**e, "element_index": e["element_index"] + 1} for e in el[2:]]
    return el


class Sterownik:
    """Atrapa sterownika CDP: te same metody, z których korzysta wejście (MCP i opis celu dla zasad)."""

    pid = PID

    def __init__(self) -> None:
        self.wywolania: list[tuple[str, dict]] = []
        self.fokus_pola: dict | None = None
        self.zmiana = False
        self.migawki: dict[str, list[dict]] = {}
        self.n = 0
        self.podglady: list[tuple] = []
        self.wlasciciel: list[dict] = []
        self.wolny_klik = 0.0                    # s: klik w sterowniku trwa (kolejka sesji)
        self.koniec_kliku = 0.0
        self.czasy_fokusu: list[float] = []

        class B:
            @staticmethod
            def dziala() -> bool:
                return True
        self.b = B()

    def aktywne_okno(self):
        return 3

    def okno(self, nr):
        return object() if nr == 3 else None

    def obsluz_mcp(self, msg: dict, konfig: dict) -> dict | None:
        ident, metoda = msg.get("id"), msg.get("method")
        if ident is None:
            return None
        if metoda == "initialize":
            return {"jsonrpc": "2.0", "id": ident, "result": {"instructions": "sterownik", "capabilities": {}}}
        if metoda == "tools/list":
            return {"jsonrpc": "2.0", "id": ident, "result": {"tools": [{"name": n} for n in (
                "click", "type_text", "press_key", "hotkey", "get_window_state", "page", "clipboard_read",
                "mouse_button_down")]}}
        nazwa, args = msg["params"]["name"], msg["params"].get("arguments") or {}
        self.wywolania.append((nazwa, args))
        if nazwa == "click" and self.wolny_klik:
            time.sleep(self.wolny_klik)
            self.koniec_kliku = time.monotonic()
        if nazwa == "get_window_state":
            self.n += 1
            sid = f"s{self.n}"
            elementy = _elementy(self.zmiana and args.get("include_screenshot") is False)
            for e in elementy:
                e["element_token"] = f"{sid}:{e['element_index']}"
            self.migawki[sid] = elementy
            sc = {"snapshot_id": sid, "pid": PID, "window_id": 3, "elements": elementy}
        else:
            sc = {"ok": True, "effect": "unverifiable", "path": "cdp"}
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "content": [{"type": "text", "text": f"{nazwa} gotowe, {KLUCZ}"}], "structuredContent": sc}}

    def opis_elementu(self, sid, indeks):
        e = next((x for x in self.migawki.get(sid, []) if str(x["element_index"]) == str(indeks)), None)
        if e is None:
            return None
        przyciski = [{"rola": x["role"], "nazwa": x["label"]} for x in self.migawki[sid] if x["role"] == "push button"]
        return {"rola": e["role"], "nazwa": e["label"], "atrybuty": {}, "przodkowie": [{"rola": "form", "nazwa": ""}],
                "w_formularzu": e.get("parent_index") == 1, "formularz": przyciski, "stany": ["editable"]}

    def opis_w_punkcie(self, nr, x, y):
        return None

    def fokus(self, nr):
        self.czasy_fokusu.append(time.monotonic())
        return self.fokus_pola

    def podglad(self, po=None, czekaj=1.0, jakosc=None, maks=None):
        self.podglady.append((po, czekaj, jakosc, maks))
        if po == 7:
            return {"nr": 7, "okno": 3, "bez_zmian": True, "aktywne": 3}
        return {"nr": 7, "okno": 3, "typ": "image/jpeg", "dane": "/9j/AA==", "szer_css": 1440, "wys_css": 900,
                "aktywne": 3, "okna": [{"window_id": 3, "title": "Sklep", "url": "https://sklep.example/"}]}

    def wejscie_wlasciciela(self, z):
        self.wlasciciel.append(z)
        return {"ok": True}


@pytest.fixture
def usluga():
    """Usługa Komputera bez przeglądarki: wejście natywne na atrapie sterownika i oba kanały w tym procesie."""
    root = Path(tempfile.mkdtemp(prefix="jk"))         # krótka ścieżka: gniazdo unix ma limit ok. 100 bajtów
    stan = kanal.katalog_stanu(root)
    stan.mkdir(parents=True)
    token = "token-wlasciciela-testowy"
    (stan / "wlasciciel.klucz").write_text(token, encoding="utf-8")
    (stan / "usluga.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    polecenia: list = []
    w = wejscie_natywne.WejscieNatywne(root / "dane" / "jarvo" / "komputer", token,
                                       lambda co, p: polecenia.append(co) or {"ok": True, "co": co})
    w.sterownik = Sterownik()
    serwery = [kanal.Serwer(kanal.adres(root, "ster"), w.obsluz_ster, "ster").start(),
               kanal.Serwer(kanal.adres(root, "cua"), w.obsluz_cua, "cua").start()]

    class U:
        pass
    u = U()
    u.root, u.wejscie, u.token, u.polecenia, u.sterownik = root, w, token, polecenia, w.sterownik
    yield u
    for s in serwery:
        s.zamknij()
    shutil.rmtree(root, ignore_errors=True)


def env_natywny(root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "JARVO_KOMPUTER_GNIAZDO"}
    env["JARVO_ROOT"] = str(root)
    return env


class Klient:
    def __init__(self, root: Path):
        self.p = subprocess.Popen([sys.executable, "-I", str(BRAMKA), "mcp"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_natywny(root))
        self.n = 0

    def rpc(self, metoda, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": metoda, **({"params": params} if params is not None else {})}
        self.p.stdin.write((json.dumps(msg) + "\n").encode())
        self.p.stdin.flush()
        while True:
            linia = self.p.stdout.readline()
            assert linia, self.p.stderr.read().decode()[:400]
            odp = json.loads(linia)
            if odp.get("id") == self.n:
                return odp

    def narzedzie(self, nazwa, args):
        return self.rpc("tools/call", {"name": nazwa, "arguments": args}).get("result") or {}

    def zamknij(self):
        self.p.stdin.close()
        self.p.wait(timeout=20)


def _bramka(*args, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(BRAMKA), *args], capture_output=True, text=True,
                          encoding="utf-8", env=env_natywny(root), timeout=30)


def test_manifest_natywny_wola_pythona_z_bramka(tmp_path):
    m = json.loads(_bramka("manifest", root=tmp_path).stdout)
    assert m["backend"] == "cdp" and m["binary_version"] == "0.21.0"
    wyw = m["mcp_invocation"]
    assert Path(wyw["command"]).name.lower().startswith("python") and wyw["args"][-2:] == [str(BRAMKA), "mcp"]
    assert wyw["args"][:3] == ["-I", "-X", "utf8"]


def test_bramka_natywna_bez_uslugi_mowi_jak_wlaczyc(tmp_path):
    for czas, kod in (("mcp", 69), ("status", 1)):
        r = _bramka(czas, root=tmp_path)
        assert r.returncode == kod and "jarvo komputer on" in r.stderr


def test_rozmowa_mcp_przez_brame_z_twardymi_zasadami(usluga):
    k = Klient(usluga.root)
    try:
        init = k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "test", "version": "1"}})
        assert "Komputer Jarva" in init["result"]["instructions"]
        narzedzia = {t["name"] for t in k.rpc("tools/list")["result"]["tools"]}
        assert {"click", "type_text", "get_window_state"} <= narzedzia
        assert not {"page", "clipboard_read", "mouse_button_down"} & narzedzia
        assert k.narzedzie("page", {})["structuredContent"]["code"] == "zablokowane"

        stan = k.narzedzie("get_window_state", {"pid": PID, "window_id": 3})
        calosc = json.dumps(stan, ensure_ascii=False)
        assert KLUCZ not in calosc and "[ukryte przez Komputer Jarva]" in calosc and '"tajne"' not in calosc
        el = {e["label"]: e for e in stan["structuredContent"]["elements"]}
        przed = len(usluga.sterownik.wywolania)
        w = k.narzedzie("click", {"pid": PID, "window_id": 3, "element_token": el["Zapłać 129 zł"]["element_token"]})
        assert w["structuredContent"]["code"] == "wymaga_czlowieka"
        assert len(usluga.sterownik.wywolania) == przed               # odmowa nie dotarła do sterownika
        w = k.narzedzie("click", {"pid": PID, "window_id": 3, "element_token": el["Dodaj do koszyka"]["element_token"]})
        assert not w.get("isError")
        nazwy = [n for n, _ in usluga.sterownik.wywolania]
        assert nazwy[-2:] == ["get_window_state", "click"]            # świeża migawka przed działaniem na element
        assert usluga.sterownik.wywolania[-1][1]["element_token"].startswith(f"s{usluga.sterownik.n}:")

        pisz = {"pid": PID, "window_id": 3, "delivery_mode": "foreground"}
        assert k.narzedzie("type_text", {**pisz, "text": "abc"})["structuredContent"]["rule"] == "brak_fokusu"
        usluga.sterownik.fokus_pola = {"rola": "password text", "nazwa": "Hasło", "atrybuty": {}, "przodkowie": []}
        assert k.narzedzie("type_text", {**pisz, "text": "abc"})["structuredContent"]["code"] == "wymaga_czlowieka"
        usluga.sterownik.fokus_pola = {"rola": "entry", "nazwa": "Uwagi", "atrybuty": {}, "przodkowie": [],
                                       "w_formularzu": False, "formularz": []}
        assert k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "v"]})["structuredContent"]["rule"] == "schowek"
        assert k.narzedzie("hotkey", {**pisz, "keys": ["ctrl", "l"]})["structuredContent"]["rule"] == \
            "skrot_przegladarki"
        assert not k.narzedzie("type_text", {**pisz, "text": "Proszę o fakturę"}).get("isError")

        usluga.sterownik.zmiana = True                                # strona zmieniła się od migawki agenta
        w = k.narzedzie("click", {"pid": PID, "window_id": 3, "element_token": el["Dodaj do koszyka"]["element_token"]})
        assert w["structuredContent"]["rule"] == "element_zmieniony"
    finally:
        k.zamknij()
    dziennik = json.dumps(list(usluga.wejscie.dziennik.ostatnie), ensure_ascii=False)
    assert "Proszę o fakturę" not in dziennik and "czlowiek" in dziennik


def test_ster_pauza_wznowienie_tylko_z_tokenem(usluga):
    adres = kanal.adres(usluga.root, "ster")
    assert kanal.zapytaj(adres, {"polecenie": "stan"})["ok"]
    odp = kanal.zapytaj(adres, {"polecenie": "pauza", "powod": "Zaloguj się do panelu sklepu"})
    assert odp["wstrzymane"] and odp["pauza"]["kto"] == "flota"
    odp = kanal.zapytaj(adres, {"polecenie": "wznow"})
    assert odp["ok"] is False and odp["wstrzymane"] is True
    odp = kanal.zapytaj(adres, {"polecenie": "wznow", "token": "zly"})
    assert odp["ok"] is False and odp["wstrzymane"] is True
    odp = kanal.zapytaj(adres, {"polecenie": "pauza", "token": usluga.token, "powod": "przerwa"})
    assert odp["pauza"]["kto"] == "wlasciciel"
    odp = kanal.zapytaj(adres, {"polecenie": "pauza", "powod": "prośba floty"})   # nie nadpisze pauzy właściciela
    assert odp["pauza"]["kto"] == "wlasciciel"
    assert kanal.zapytaj(adres, {"polecenie": "wznow", "token": usluga.token})["wstrzymane"] is False
    for co in ("stop", "okno", "wyczysc"):
        assert kanal.zapytaj(adres, {"polecenie": co})["ok"] is False
    assert kanal.zapytaj(adres, {"polecenie": "stop", "token": usluga.token})["co"] == "stop"
    assert [c for c in usluga.polecenia if c != "stan"] == ["stop"]
    wpisy = kanal.zapytaj(adres, {"polecenie": "dziennik", "n": 50})["wpisy"]
    assert any(w.get("zasada") == "wznow_bez_tokenu" for w in wpisy)
    assert "panelu sklepu" not in json.dumps(wpisy, ensure_ascii=False)


def test_ekran_hq_klatka_przejmij_i_wejscie_tylko_wlasciciel(usluga):
    """J10: podgląd, „Przejmij” i wejście właściciela tylko z tokenem; wejście tylko przy pauzie właściciela, a w
    dzienniku rodzaj działania bez treści (tekstu, znaków, ścieżki adresu); „Oddaj” to wznow."""
    adres = kanal.adres(usluga.root, "ster")
    for co in ("klatka", "przejmij", "wejscie"):
        odp = kanal.zapytaj(adres, {"polecenie": co})
        assert odp["ok"] is False and "właściciel" in odp["blad"]
    assert not usluga.sterownik.podglady and not usluga.sterownik.wlasciciel
    odp = kanal.zapytaj(adres, {"polecenie": "klatka", "token": usluga.token, "po": 3, "czekaj": 0.2},
                        maks=16 << 20)
    assert odp["ok"] and odp["klatka"]["typ"] == "image/jpeg" and odp["przejete"] is False
    assert usluga.sterownik.podglady[-1][:2] == (3, 0.2)
    assert kanal.zapytaj(adres, {"polecenie": "klatka", "token": usluga.token, "po": 7})["klatka"]["bez_zmian"]
    klik = {"typ": "klik", "x": 0.5, "y": 0.5}
    odp = kanal.zapytaj(adres, {"polecenie": "wejscie", "token": usluga.token, "zdarzenie": klik})
    assert odp["ok"] is False and "przejmij" in odp["blad"] and not usluga.sterownik.wlasciciel
    # prośba Operatora (pauza floty): przejęcie zastępuje ją pauzą właściciela
    kanal.zapytaj(adres, {"polecenie": "pauza", "powod": "Zaloguj się do sklepu"})
    odp = kanal.zapytaj(adres, {"polecenie": "przejmij", "token": usluga.token})
    assert odp["wstrzymane"] and odp["pauza"]["kto"] == "wlasciciel" and odp["przejete"] is True
    k = Klient(usluga.root)
    try:
        k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "t", "version": "1"}})
        el = {e["label"]: e for e in k.narzedzie("get_window_state", {"pid": PID, "window_id": 3})[
            "structuredContent"]["elements"]}
        w = k.narzedzie("click", {"pid": PID, "window_id": 3, "element_token": el["Dodaj do koszyka"]["element_token"]})
        assert w["structuredContent"]["code"] == "wstrzymane" and "przejął ekran" in w["content"][0]["text"]
    finally:
        k.zamknij()
    zdarzenia = [klik, {"typ": "tekst", "tekst": "tajne-haslo"}, {"typ": "klawisz", "klawisz": "a"},
                 {"typ": "klawisz", "klawisz": "Return"}, {"typ": "klawisz", "klawisz": "a", "modyfikatory": ["ctrl"]},
                 {"typ": "adres", "url": "https://bank.example/logowanie?token=abc"},
                 {"typ": "mysz", "zdarzenie": "mouseMoved", "x": 0.1, "y": 0.1}]
    for z in zdarzenia:
        assert kanal.zapytaj(adres, {"polecenie": "wejscie", "token": usluga.token, "zdarzenie": z})["ok"]
    assert usluga.sterownik.wlasciciel == zdarzenia
    wpisy = kanal.zapytaj(adres, {"polecenie": "dziennik", "n": 100})["wpisy"]
    tekst = json.dumps(wpisy, ensure_ascii=False)
    assert "tajne-haslo" not in tekst and "token=abc" not in tekst and "logowanie" not in tekst
    wlasciciela = [w for w in wpisy if w.get("narzedzie") == "wlasciciel"]
    assert [w["typ"] for w in wlasciciela] == ["klik", "tekst", "klawisz", "klawisz", "klawisz", "adres"]
    assert [w.get("klawisze") for w in wlasciciela[2:5]] == ["znak", "Return", "ctrl+a"]
    assert wlasciciela[1]["znaki"] == len("tajne-haslo") and wlasciciela[5]["cel"] == "bank.example"
    assert any(w.get("decyzja") == "przejmij" for w in wpisy)
    assert kanal.zapytaj(adres, {"polecenie": "wznow", "token": usluga.token})["wstrzymane"] is False   # „Oddaj”
    odp = kanal.zapytaj(adres, {"polecenie": "wejscie", "token": usluga.token, "zdarzenie": klik})
    assert odp["ok"] is False                                     # po oddaniu ekranu znowu tylko agent


def test_dzialanie_oceniane_po_poprzednim(usluga):
    """Wiadomości wysłane jedna za drugą bez czekania: zasady oceniają pisanie dopiero po kliknięciu, które jeszcze
    było w kolejce sterownika (fokus po kliknięciu, a nie przed nim)."""
    st = usluga.sterownik
    st.wolny_klik = 0.6
    st.fokus_pola = {"rola": "entry", "nazwa": "Uwagi", "atrybuty": {}, "przodkowie": [], "w_formularzu": False,
                     "formularz": []}
    k = Klient(usluga.root)
    try:
        k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "t", "version": "1"}})
        el = {e["label"]: e for e in k.narzedzie("get_window_state", {"pid": PID, "window_id": 3})[
            "structuredContent"]["elements"]}
        przed = len(st.czasy_fokusu)
        for ident, nazwa, args in ((101, "click", {"pid": PID, "window_id": 3,
                                                   "element_token": el["E-mail"]["element_token"]}),
                                   (102, "type_text", {"pid": PID, "window_id": 3, "delivery_mode": "foreground",
                                                       "text": "abc"})):
            k.p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": ident, "method": "tools/call",
                                         "params": {"name": nazwa, "arguments": args}}) + "\n").encode())
        k.p.stdin.flush()
        odp = {}
        while len(odp) < 2:
            m = json.loads(k.p.stdout.readline())
            odp[m.get("id")] = m
        assert not odp[101]["result"].get("isError") and not odp[102]["result"].get("isError")
        assert len(st.czasy_fokusu) > przed and st.czasy_fokusu[-1] >= st.koniec_kliku > 0
    finally:
        k.zamknij()


def test_pauza_trwa_po_restarcie_wejscia(usluga):
    adres = kanal.adres(usluga.root, "ster")
    kanal.zapytaj(adres, {"polecenie": "pauza", "token": usluga.token, "powod": "test"})
    nowe = wejscie_natywne.WejscieNatywne(usluga.root / "dane" / "jarvo" / "komputer", "inny")
    assert nowe.ekran.wstrzymane and nowe.ekran.pauza["kto"] == "wlasciciel"


def _wtyczka():
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvo_test_wtyczka_natywna", REPO / "komputer" / "plugin" /
                                                  "__init__.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_wtyczka_operatora_natywnie(usluga, monkeypatch):
    monkeypatch.delenv("JARVO_KOMPUTER_GNIAZDO", raising=False)
    monkeypatch.setenv("JARVO_ROOT", str(usluga.root))
    w = _wtyczka()
    stan = json.loads(w.obsluz({"akcja": "stan"}))
    assert stan["ok"] and stan["dziala"] and stan["drzewo_dostepnosci"] is True and not stan["wstrzymane"]
    odp = json.loads(w.obsluz({"akcja": "oddaj", "prosba": "Zaloguj się do panelu sklepu i daj znać"}))
    assert odp["wstrzymane"] and odp["kto_wstrzymal"].startswith("Operator")
    assert json.loads(w.obsluz({"akcja": "dziennik", "n": 5}))["ok"]


def test_wtyczka_natywnie_bez_uslugi(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVO_KOMPUTER_GNIAZDO", raising=False)
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path))
    stan = json.loads(_wtyczka().obsluz({"akcja": "stan"}))
    assert stan["ok"] is False and "jarvo komputer on" in stan["blad"]


def _uklad(root: Path) -> sciezki.Uklad:
    return sciezki.Uklad(root=root, program=root / "program", dane=root / "dane", stan=root / "stan",
                         logi=root / "logi", cache=root / "cache", build=root / "build")


def _cli(argv: list[str], root: Path) -> tuple[int, str]:
    wyjscie = io.StringIO()
    with redirect_stdout(wyjscie):
        kod = jk.main(argv, u=_uklad(root))
    return kod, wyjscie.getvalue()


def test_jarvo_komputer_przy_dzialajacej_usludze(usluga):
    kod, tekst = _cli(["status"], usluga.root)
    assert kod == 0 and "Komputer Jarva: działa" in tekst
    kod, tekst = _cli(["pauza", "obiad"], usluga.root)
    assert kod == 0 and "wstrzymany" in tekst and usluga.wejscie.ekran.pauza["kto"] == "wlasciciel"
    kod, tekst = _cli(["status", "--json"], usluga.root)
    assert json.loads(tekst)["wstrzymane"] is True
    kod, tekst = _cli(["wznow"], usluga.root)
    assert kod == 0 and not usluga.wejscie.ekran.wstrzymane
    kod, tekst = _cli(["dziennik", "5"], usluga.root)
    assert kod == 0 and "ster" in tekst
    kod, tekst = _cli(["wyczysc", "--tak"], usluga.root)
    assert kod == 0 and [c for c in usluga.polecenia if c != "stan"][-1] == "wyczysc"


def test_jarvo_komputer_bez_uslugi(tmp_path):
    kod, tekst = _cli(["status"], tmp_path)
    assert kod == 1 and "nie działa" in tekst
    assert _cli(["pauza"], tmp_path)[0] == 1
    assert _cli(["off"], tmp_path)[0] == 0
    assert jk.main(["nieznane"], u=_uklad(tmp_path)) == 2
    (tmp_path / "dane" / "jarvo" / "komputer" / "profil").mkdir(parents=True)
    assert _cli(["wyczysc", "--tak"], tmp_path)[0] == 0
    assert not (tmp_path / "dane" / "jarvo" / "komputer" / "profil").exists()


def test_nakladka_bramki_i_ustawienia(tmp_path):
    u = _uklad(tmp_path)
    p = jk.nakladka_bramki(u, REPO, Path(sys.executable))
    tresc = p.read_text(encoding="utf-8")
    assert str(REPO / "komputer" / "jarvo_cua.py") in tresc and str(sys.executable) in tresc
    if os.name == "nt":
        assert p.name == "jarvo-cua.cmd" and tresc.isascii() == str(REPO).isascii() and "%*" in tresc
        wynik = subprocess.run([str(p), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=30)
    else:
        assert os.access(p, os.X_OK) and '"$@"' in tresc
        wynik = subprocess.run([str(p), "--version"], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert wynik.returncode == 0 and "bramka Jarvo" in wynik.stdout
    assert jk.zapisz_ustawienia(u, okno=True)["okno"] is True and jk.ustawienia(u)["okno"] is True


def test_on_bez_przegladarki_w_manifescie(tmp_path, monkeypatch, capsys):
    """Manifest bez wpisu `chrome-komputer` (przed etapem E10 w vendor/natywne.yaml): jasny błąd, nic nie startuje."""
    from jarvo import instalator, manifest
    monkeypatch.setattr(jk, "wpis_przegladarki", lambda app: (_ for _ in ()).throw(manifest.BrakNarzedzia(
        "chrome-komputer: nie ma w manifeście")))
    ot = instalator.Otoczenie(env={k: v for k, v in os.environ.items() if not k.startswith("JARVO_KOMPUTER_CHROME")},
                              uruchom_w_tle=lambda *a: pytest.fail("bez przeglądarki usługa nie startuje"))
    assert jk.main(["on"], u=_uklad(tmp_path), ot=ot) == 1
    assert "nie ma przeglądarki Komputera" in capsys.readouterr().err


def test_on_startuje_usluge_w_tle_z_nakladka(tmp_path, monkeypatch):
    from jarvo import instalator
    chrome = tmp_path / "chrome.exe"
    chrome.write_bytes(b"x")
    uruchomione = []

    def w_tle(argv, env, log):
        uruchomione.append((argv, env, log))
        return os.getpid()
    monkeypatch.setattr(jk, "_czekaj_na_start", lambda u, ot, pid, czas: {"ok": True, "sesje": 0})
    ot = instalator.Otoczenie(env={**os.environ, "JARVO_KOMPUTER_CHROME_PROBA": str(chrome)}, uruchom_w_tle=w_tle)
    with redirect_stdout(io.StringIO()):
        assert jk.main(["on", "--okno"], u=_uklad(tmp_path), ot=ot) == 0
    argv, env, log = uruchomione[0]
    assert argv[1:4] == ["-I", "-X", "utf8"] and argv[4].endswith(os.path.join("komputer", "usluga.py"))
    assert argv[5:] == ["--korzen", str(tmp_path), "--okno", "--przegladarka", str(chrome)]
    assert env["JARVO_ROOT"] == str(tmp_path)
    assert log.name == "komputer.log" and not any(k.upper().endswith("_KEY") for k in env)
    assert jk.ustawienia(_uklad(tmp_path))["wlaczony"] is True
    assert (tmp_path / "program" / "bin-floty" / ("jarvo-cua.cmd" if os.name == "nt" else "jarvo-cua")).is_file()


def test_pin_przegladarki_z_manifestu_i_odswiez(tmp_path, monkeypatch, capsys):
    """J01, J12: `on` bierze pin `chrome-komputer` z manifestu tej wersji Jarva; ten sam pin = bez pobierania, nowy pin
    (po `jarvo update`) = pobranie z sumą; `odswiez` mówi, czy przeglądarka jest aktualna."""
    from jarvo import instalator
    u = _uklad(tmp_path)
    pin = {"wersja": "156.0.8078.47", "sha256": "a" * 64}
    pobrania: list = []

    def wpis(app):
        return pin["wersja"], {"url": "https://example.invalid/chrome.zip", "sha256": pin["sha256"], "rozmiar": 10,
                               "format": "zip", "env": {"JARVO_KOMPUTER_CHROME": "{katalog}/chrome-win64/chrome.exe"}}

    def zainstaluj(nazwa, wersja, plik, narzedzia, pobrane, **_):
        katalog = narzedzia / nazwa / wersja
        if (katalog / ".jarvo-suma").is_file() and (katalog / ".jarvo-suma").read_text().strip() == plik["sha256"]:
            return katalog
        pobrania.append(wersja)
        (katalog / "chrome-win64").mkdir(parents=True, exist_ok=True)
        (katalog / "chrome-win64" / "chrome.exe").write_bytes(b"x")
        (katalog / ".jarvo-suma").write_text(plik["sha256"] + "\n", encoding="utf-8")
        return katalog
    monkeypatch.setattr(jk, "wpis_przegladarki", wpis)
    monkeypatch.setattr(jk.pobieracz, "zainstaluj", zainstaluj)
    env = {k: v for k, v in os.environ.items() if not k.startswith("JARVO_KOMPUTER_CHROME")}
    pierwszy = jk.przegladarka_do_startu(u, REPO, env, log=lambda t: None)
    assert pierwszy.endswith(os.path.join("156.0.8078.47", "chrome-win64", "chrome.exe")) and pobrania == ["156.0.8078.47"]
    assert jk.ustawienia(u)["sha256"] == "a" * 64 and jk.przegladarka_aktualna(u, *wpis(REPO))
    assert jk.przegladarka_do_startu(u, REPO, env, log=lambda t: None) == pierwszy and len(pobrania) == 1
    ot = instalator.Otoczenie(env=env)
    assert jk.main(["odswiez"], u=u, ot=ot) == 0 and "aktualna" in capsys.readouterr().out
    pin.update(wersja="157.0.8100.5", sha256="b" * 64)                  # jarvo update przyniósł nowy pin CfT
    assert not jk.przegladarka_aktualna(u, *wpis(REPO))
    assert jk.main(["odswiez"], u=u, ot=ot) == 0 and pobrania[-1] == "157.0.8100.5"
    assert jk.ustawienia(u)["wersja"] == "157.0.8100.5" and "157.0.8100.5" in jk.ustawienia(u)["chrome"]
    # zmienna próby wygrywa z manifestem, ale musi wskazywać istniejący plik
    proba = tmp_path / "chs.exe"
    proba.write_bytes(b"x")
    assert jk.przegladarka_do_startu(u, REPO, {**env, "JARVO_KOMPUTER_CHROME_PROBA": str(proba)}) == str(proba)
    with pytest.raises(jk.pobieracz.BladPobierania):
        jk.przegladarka_do_startu(u, REPO, {**env, "JARVO_KOMPUTER_CHROME_PROBA": str(tmp_path / "nie-ma.exe")})


def test_kanal_i_dziennik_bez_sekretow_w_powodzie_pauzy(usluga):
    adres = kanal.adres(usluga.root, "ster")
    kanal.zapytaj(adres, {"polecenie": "pauza", "powod": f"wklej klucz {KLUCZ} tutaj\nnowa linia"})
    pauza = kanal.zapytaj(adres, {"polecenie": "stan"})["pauza"]
    assert KLUCZ not in json.dumps(pauza) and "\n" not in pauza["powod"]


def test_sesje_rownolegle_jedna_przy_ekranie(usluga):
    k1, k2 = Klient(usluga.root), Klient(usluga.root)
    try:
        for k in (k1, k2):
            k.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "t", "version": "1"}})
        el1 = {e["label"]: e for e in k1.narzedzie("get_window_state", {"pid": PID, "window_id": 3})[
            "structuredContent"]["elements"]}
        assert not k1.narzedzie("click", {"pid": PID, "window_id": 3,
                                          "element_token": el1["Dodaj do koszyka"]["element_token"]}).get("isError")
        el2 = {e["label"]: e for e in k2.narzedzie("get_window_state", {"pid": PID, "window_id": 3})[
            "structuredContent"]["elements"]}
        w = k2.narzedzie("click", {"pid": PID, "window_id": 3,
                                   "element_token": el2["Dodaj do koszyka"]["element_token"]})
        assert w["structuredContent"]["rule"] == "zajete"
    finally:
        k1.zamknij()
        k2.zamknij()
    for _ in range(50):
        if not usluga.wejscie.sesje:
            break
        time.sleep(0.1)
    assert not usluga.wejscie.sesje


def test_brama_w_kontenerze_bez_zmian(tmp_path):
    """JARVO_KOMPUTER_GNIAZDO (kontener) ma pierwszeństwo przed JARVO_ROOT: manifest i gniazdo jak dotąd."""
    env = {**os.environ, "JARVO_ROOT": str(tmp_path), "JARVO_KOMPUTER_GNIAZDO": "/nie/ma/cua.sock"}
    m = json.loads(subprocess.run([sys.executable, "-I", str(BRAMKA), "manifest"], capture_output=True, text=True,
                                  encoding="utf-8", env=env, timeout=30).stdout)
    assert m["backend"] == "cua-driver" and m["mcp_invocation"] == {"command": str(BRAMKA), "args": ["mcp"]}


def test_ster_odpowiada_na_wiele_klientow_naraz(usluga):
    adres = kanal.adres(usluga.root, "ster")
    wyniki: list = []
    watki = [threading.Thread(target=lambda: wyniki.append(kanal.zapytaj(adres, {"polecenie": "stan"})["ok"]))
             for _ in range(8)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(10)
    assert wyniki == [True] * 8


def test_migracja_z_kontenera_bez_profilu(tmp_path):
    """J16: z wolumenu jarvo-komputer-dom pobrane pliki (bez programów), dziennik i pauza; profilu nie."""
    dom = tmp_path / "pulpit"
    (dom / "Pobrane").mkdir(parents=True)
    (dom / "Pobrane" / "faktura.pdf").write_bytes(b"%PDF")
    (dom / "Pobrane" / "instalator.exe").write_bytes(b"MZ")
    (dom / ".jarvo").mkdir()
    (dom / ".jarvo" / "dziennik.jsonl").write_text('{"t": "2", "decyzja": "tak"}\n', encoding="utf-8")
    (dom / ".jarvo" / "dziennik.jsonl.1").write_text('{"t": "1", "decyzja": "czlowiek"}\n', encoding="utf-8")
    (dom / ".jarvo" / "pauza").write_text('{"kto": "wlasciciel", "powod": ""}\n', encoding="utf-8")
    (dom / ".config" / "chromium" / "Default").mkdir(parents=True)
    (dom / ".config" / "chromium" / "Default" / "Cookies").write_bytes(b"x")
    u = _uklad(tmp_path / "korzen")
    assert jk.przenies_z_kontenera(u, dom) == {"pobrane": 1, "odrzucone": 1, "dziennik": 2, "pauza": True}
    k = jk.katalogi(u)
    assert (k["pobrane"] / "faktura.pdf").is_file() and not (k["pobrane"] / "instalator.exe").exists()
    assert k["dziennik"].read_text(encoding="utf-8").splitlines()[0] == '{"t": "1", "decyzja": "czlowiek"}'
    assert not k["profil"].exists()
    assert jk.przenies_z_kontenera(u, dom) == {"pobrane": 0, "odrzucone": 1, "dziennik": 0, "pauza": False}

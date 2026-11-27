"""Pulpit serwera (docs/PULPIT.md): zasady silnika, wynik dla modelu, zamek pulpitu, rozmowa z silnikiem i build.

Bez ekranu: części silnika, które potrzebują X11 (Gdk, Wnck, AT-SPI, XTEST), zastępują atrapy; prawdziwy ekran
sprawdza próba na żywo z docs/PULPIT.md.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
import textwrap

import pytest

from conftest import REPO

import build
import fleetlib as fl

sys.path.insert(0, str(REPO / "pulpit" / "plugin"))
import silnik  # noqa: E402


def _wtyczka():
    spec = importlib.util.spec_from_file_location("jarvo_pulpit_test", REPO / "pulpit" / "plugin" / "__init__.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def wtyczka(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVO_ROOT", str(tmp_path / "root"))
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    return _wtyczka()


# ------------------------------------------------------------------------------------------------ zasady silnika

def test_platnosc_tylko_ze_zgoda():
    przycisk = {"rola": "push button", "nazwa": "Kup teraz za 129 zł", "przodkowie": []}
    with pytest.raises(silnik.Odmowa, match="ZGODA WŁAŚCICIELA"):
        silnik.sprawdz_klik(przycisk, zgoda=lambda: False)
    silnik.sprawdz_klik(przycisk, zgoda=lambda: True)
    silnik.sprawdz_klik({"rola": "push button", "nazwa": "Eksportuj", "przodkowie": []}, zgoda=lambda: False)
    # przodek z rolą działania też się liczy (napis w środku przycisku)
    w_srodku = {"rola": "label", "nazwa": "129 zł", "przodkowie": [{"rola": "push button", "nazwa": "Zapłać"}]}
    with pytest.raises(silnik.Odmowa):
        silnik.sprawdz_klik(w_srodku, zgoda=lambda: False)
    silnik.sprawdz_klik(None, zgoda=lambda: False)


def test_pisanie_karty_i_sekretow():
    pole = {"rola": "text", "nazwa": "Numer karty", "atrybuty": {}}
    with pytest.raises(silnik.Odmowa, match="dane karty"):
        silnik.sprawdz_pisanie("1234", pole, zgoda=lambda: False)
    silnik.sprawdz_pisanie("1234", pole, zgoda=lambda: True)
    with pytest.raises(silnik.Odmowa, match="numer karty"):
        silnik.sprawdz_pisanie("4111 1111 1111 1111", {"rola": "text", "nazwa": "Uwagi"}, zgoda=lambda: False)
    with pytest.raises(silnik.Odmowa, match="token"):
        silnik.sprawdz_pisanie("ghp_" + "a" * 36, None, zgoda=lambda: True)
    silnik.sprawdz_pisanie("Zażółć gęślą jaźń 123", {"rola": "text", "nazwa": "Tytuł"}, zgoda=lambda: False)


def test_zgoda_z_zadania_agenta(tmp_path, monkeypatch):
    import sqlite3
    baza = tmp_path / "kanban.db"
    con = sqlite3.connect(baza)
    con.execute("CREATE TABLE tasks (id TEXT, body TEXT)")
    con.execute("INSERT INTO tasks VALUES ('t_1', ?)",
                ("Kup domenę\nZGODA WŁAŚCICIELA: platnosc — „kup domenę za 49 zł” (2026-11-27)",))
    con.execute("INSERT INTO tasks VALUES ('t_2', 'bez zgody')")
    con.commit()
    con.close()
    monkeypatch.setenv("HERMES_KANBAN_DB", str(baza))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    assert silnik.zgoda_platnosci()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_2")
    assert not silnik.zgoda_platnosci()
    monkeypatch.delenv("HERMES_KANBAN_TASK")
    assert not silnik.zgoda_platnosci()


@pytest.mark.parametrize("kombinacja", ["ctrl+alt+t", "Alt+F2", "super+l", "ctrl+alt+Delete", "alt+F3",
                                        "control+shift+Escape", "win+t", "ctrl+alt+BackSpace"])
def test_skroty_zakazane(kombinacja):
    with pytest.raises(silnik.Odmowa):
        silnik.skrot(kombinacja)


def test_skroty_dozwolone():
    assert silnik.skrot("ctrl+s") == (["Control_L"], ["s"])
    assert silnik.skrot("ctrl+shift+e") == (["Control_L", "Shift_L"], ["e"])
    assert silnik.skrot("alt+F4") == (["Alt_L"], ["F4"])
    assert silnik.skrot("Return") == ([], ["Return"])
    assert silnik.skrot("enter") == ([], ["Return"])
    assert silnik.skrot("ctrl++") == (["Control_L"], ["+"])
    with pytest.raises(silnik.Odmowa):
        silnik.skrot("ctrl+a+b")


def test_okna_zakazane_i_awarii():
    assert silnik.TERMINALE.search("Xfce4-terminal xfce4-terminal")
    assert silnik.TERMINALE.search("Xfrun4 xfrun4")
    assert not silnik.TERMINALE.search("Gimp-3.2 gimp")
    assert silnik.OKNA_AWARII.search("Apport-gtk apport-gtk")


def test_lista_elementow_i_zmiana():
    e = {"n": 3, "rola": "push button", "nazwa": "Zapisz", "wartosc": None, "stany": ["fokus"], "x": 640, "y": 360}
    assert silnik.linia_elementu(e) == "[3] przycisk „Zapisz” (fokus) @640,360"
    pole = {"n": 7, "rola": "text", "nazwa": "", "wartosc": "Zażółć", "stany": [], "x": 1, "y": 2}
    assert silnik.linia_elementu(pole) == "[7] pole tekstu = „Zażółć” @1,2"
    assert silnik.zmiana(b"\x00" * 100, b"\x00" * 100) == 0.0
    assert silnik.zmiana(b"\x00" * 100, b"\x00" * 90 + b"\xff" * 10) == pytest.approx(0.1)


def test_appimage_po_znaczniku(tmp_path):
    a = tmp_path / "kdenlive"
    a.write_bytes(b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\x00" * 20)
    b = tmp_path / "zwykly"
    b.write_bytes(b"\x7fELF\x02\x01\x01\x00\x00\x00\x00" + b"\x00" * 20)
    assert silnik.appimage(str(a)) and not silnik.appimage(str(b)) and not silnik.appimage(str(tmp_path / "brak"))


class _AtrapaSilnika(silnik.Silnik):
    """Silnik bez ekranu: kroki wołają atrapy akcji."""

    def __init__(self):
        self.wolane = []

    def klik(self, a):
        self.wolane.append(("klik", a.get("numer")))
        if a.get("numer") == 99:
            raise silnik.Odmowa("płatność")
        return {"ok": True, "tekst": f"ok klik [{a.get('numer')}]"}

    def pisz(self, a):
        self.wolane.append(("pisz", a.get("tekst")))
        return {"ok": True, "tekst": "ok wpisane"}

    def czekaj(self, a):
        return {"ok": False, "blad": "czas minął"}


def test_kroki_paragon_i_stop_na_odmowie():
    s = _AtrapaSilnika()
    w = s.obsluz({"akcja": "kroki", "kroki": [{"akcja": "klik", "numer": 1}, {"akcja": "pisz", "tekst": "a"},
                                              {"akcja": "klik", "numer": 99}, {"akcja": "pisz", "tekst": "b"}]})
    assert w["ok"] and w["tekst"].splitlines() == ["1. ok klik [1]", "2. ok wpisane",
                                                   "3. ODMOWA klik: płatność; paczka stoi"]
    assert s.wolane == [("klik", 1), ("pisz", "a"), ("klik", 99)]
    w = _AtrapaSilnika().obsluz({"akcja": "kroki", "kroki": [{"akcja": "czekaj"}, {"akcja": "klik", "numer": 1}]})
    assert w["tekst"] == "1. BŁĄD czekaj: czas minął; paczka stoi"
    w = _AtrapaSilnika().obsluz({"akcja": "kroki", "kroki": [{"akcja": "zobacz"}]})
    assert "ODMOWA" in w["tekst"]
    assert _AtrapaSilnika().obsluz({"akcja": "kroki", "kroki": []})["odmowa"]
    assert not _AtrapaSilnika().obsluz({"akcja": "rm"})["ok"]


# ------------------------------------------------------------------------------------------------ wtyczka

def test_wynik_obraz_jako_multimodal(wtyczka, tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    b64 = base64.b64encode(b"\xff\xd8\xff jpeg").decode()
    w = wtyczka.wynik({"ok": True, "tekst": "lista", "obraz": b64, "szer": 1280, "wys": 720})
    assert w["_multimodal"] is True and w["content"][0]["type"] == "text"
    assert w["content"][1]["image_url"]["url"] == f"data:image/jpeg;base64,{b64}"
    assert "zrzut: " in w["text_summary"] and w["meta"]["szer"] == 1280
    zrzuty = list((tmp_path / "hh" / "cache" / "images").glob("pulpit_*.jpg"))
    assert len(zrzuty) == 1 and zrzuty[0].read_bytes() == b"\xff\xd8\xff jpeg"
    monkeypatch.setattr(wtyczka, "_obraz_natywnie", lambda: False)
    tekst = wtyczka.wynik({"ok": True, "tekst": "lista", "obraz": b64})
    assert isinstance(tekst, str) and "vision_analyze" in tekst
    assert wtyczka.wynik({"ok": False, "odmowa": True, "blad": "płatność"}) == "ODMOWA: płatność"
    assert wtyczka.wynik({"ok": True, "tekst": "ok klik"}) == "ok klik"


def test_zamek_pulpitu(wtyczka, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/x/profiles/jarvo-wideo")
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_9")
    assert wtyczka.zajmij("a", teraz=1000.0) is None
    assert wtyczka.zajmij("a", teraz=1010.0) is None                  # to samo zadanie działa dalej
    powod = wtyczka.zajmij("b", teraz=1050.0)
    assert powod and "jarvo-wideo (zadanie t_9)" in powod and "40 s temu" in powod and "80 s" in powod
    assert wtyczka.zajmij("b", teraz=1010.0 + wtyczka.ZAJETE_S + 1) is None    # po ciszy inne zadanie przejmuje


def test_obsluz_zajete_i_zla_akcja(wtyczka, monkeypatch):
    monkeypatch.setattr(wtyczka, "zajmij", lambda klucz: "pulpit zajęty: test")
    assert wtyczka.obsluz({"akcja": "klik", "numer": 1}, session_id="s") == "ODMOWA: pulpit zajęty: test"
    assert wtyczka.obsluz({"akcja": "rm"}).startswith("BŁĄD pulpit: akcja")


def test_rozmowa_z_silnikiem_atrapa(wtyczka, tmp_path, monkeypatch):
    """Wtyczka ↔ silnik: wiersz gotowości, polecenie z id i odpowiedź; zobacz wraca jako obraz."""
    atrapa = tmp_path / "silnik.py"
    atrapa.write_text(textwrap.dedent("""
        import json, sys
        print(json.dumps({"ok": True, "gotowy": True}), flush=True)
        for linia in sys.stdin:
            p = json.loads(linia)
            a = p["argumenty"]
            odp = {"ok": True, "tekst": "akcja " + a["akcja"], "id": p["id"]}
            if a["akcja"] == "zobacz":
                odp.update(obraz="QUJD", szer=1280, wys=720)
            print(json.dumps(odp, ensure_ascii=False), flush=True)
    """), encoding="utf-8")
    monkeypatch.setattr(wtyczka, "SILNIK", atrapa)
    monkeypatch.setattr(wtyczka, "PYTHON_SYSTEMU", sys.executable)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    try:
        assert wtyczka.obsluz({"akcja": "okna"}) == "akcja okna"
        w = wtyczka.obsluz({"akcja": "zobacz"}, session_id="s1")
        assert w["_multimodal"] and w["content"][1]["image_url"]["url"].endswith("QUJD")
        assert wtyczka.obsluz({"akcja": "klik", "numer": 3}, session_id="s1") == "akcja klik"
    finally:
        wtyczka._koniec()


def test_program_z_manifestu_bez_instalacji(wtyczka):
    with pytest.raises(RuntimeError, match="brak instalacji natywnej"):
        wtyczka.program_z_manifestu("kdenlive")


def test_schemat_i_manifest_wtyczki(wtyczka):
    assert fl.load_yaml(REPO / "pulpit" / "plugin" / "plugin.yaml")["provides_tools"] == ["pulpit"]
    akcje = wtyczka.SCHEMAT["parameters"]["properties"]["akcja"]["enum"]
    assert set(akcje) == set(silnik.Silnik.AKCJE) | {"kroki"}
    assert wtyczka.DZIALANIA <= set(akcje) and "zobacz" not in wtyczka.DZIALANIA
    assert set(wtyczka.Z_MANIFESTU) == set(silnik.ZEWNETRZNE)
    natywne = fl.load_yaml(REPO / "vendor" / "natywne.yaml")["narzedzia"]
    for nazwa in silnik.ZEWNETRZNE:
        plik = natywne[nazwa]["pliki"]["linux-x64"]
        assert natywne[nazwa]["kiedy"] == "przy-uzyciu" and plik["nazwa_pliku"] == nazwa and plik["bin"] == ["."]


# ------------------------------------------------------------------------------------------------ flota i build

def test_kto_ma_pulpit():
    fleet = fl.load_fleet(nakladka=None)
    assert {a.name for a in fleet.active() if a.pulpit} == {"jarvo", "jarvo-studio", "jarvo-wideo"}


def test_build_linux_wlacza_pulpit_tylko_z_flaga(tmp_path):
    fleet = fl.load_fleet(nakladka=None)
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    resolver = build.SourceResolver({"sources": {}, "agents": {}}, None, tmp_path / ".cache", {})
    dane, program = "/home/ola/.local/share/jarvo/dane", "/home/ola/.local/share/jarvo/program"
    env = {"TELEGRAM_OWNER_ID": "1", "TELEGRAM_HQ_CHAT_ID": "-100"}
    for system in ("linux", "windows"):
        u = build.Uklad(nazwa="natywny", system=system, dane=dane, repo=program + "/app/1", build="/tmp/b",
                        narzedzia=program + "/narzedzia-floty", bin=program + "/bin-floty",
                        py=f"{program}/venvs/n/bin/python", dom="/home/ola",
                        node_modules=program + "/node-floty/node_modules", chrome=program + "/chrome")
        out = tmp_path / system
        out.mkdir()
        original = build.build_cron
        build.build_cron = lambda *a, **k: 0
        try:
            for name in ("jarvo-wideo", "jarvo-web"):
                build.build_agent(fleet, fleet.agent(name), out, {"sources": {}, "agents": {}}, resolver, protocol,
                                  u.build, env, None, [], uklad=u)
        finally:
            build.build_cron = original
        wideo, web = (fl.load_yaml(out / n / "config.yaml") for n in ("jarvo-wideo", "jarvo-web"))
        assert ("jarvo-pulpit" in wideo["plugins"]["enabled"]) == (system == "linux")
        assert "jarvo-pulpit" not in web["plugins"]["enabled"]
        for plat, ts in wideo["platform_toolsets"].items():
            assert ("pulpit" in ts) == (system == "linux" and plat != "cron"), (system, plat)
        assert not any("pulpit" in ts for ts in web["platform_toolsets"].values())

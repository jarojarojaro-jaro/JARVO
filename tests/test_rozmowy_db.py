"""Magazyn rozmów (hq/plugin/rozmowy.py): migracja 1 z pełnym schematem, pragmy, kopie przed migracją, wątki,
członkowie i rodowód sesji, wpisy idempotentne po kluczu, przebiegi, przekazy, karty, sprzątanie i import
starych rozmów Bazy (`hq-sessions.json`) idempotentny per sesja."""
import json
import os
import sqlite3
import stat
import threading

import pytest

import stan_hermesa
from conftest import load_script

rz = load_script("hq/plugin/rozmowy.py", "jarvo_test_rozmowy")


class Zegar:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def plus(self, s):
        self.t += s
        return self.t


@pytest.fixture
def zegar():
    return Zegar()


@pytest.fixture
def db(tmp_path, zegar):
    d = rz.Rozmowy(tmp_path / "state" / "rozmowy.db", zegar=zegar)
    d.migruj()
    yield d
    d.zamknij()


def _kolumny(conn, tabela):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


# ------------------------------------------------------------------------------------------- schemat i migracje

def test_migracja_1_ma_pelny_schemat(db):
    c = sqlite3.connect(db.sciezka)
    tabele = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"watki", "czlonkowie", "sesje", "wpisy", "przebiegi", "przekazy", "karty", "blokady_kart", "meta",
            "migracje"} <= tabele
    assert {"koordynator", "kanal", "ostatni_agenci", "tytul_szukaj", "nieprzeczytane"} <= _kolumny(c, "watki")
    assert {"rola", "tury", "odczyt_id", "widzial_at", "sesja_tip"} <= _kolumny(c, "czlonkowie")
    assert {"rola", "przypieta", "rodzic_id", "powod"} <= _kolumny(c, "sesje")
    assert {"lancuch_id", "lancuch_zrodlo", "hop", "przekaz_z", "nadzorowany", "nadzor_stan", "nadzor_przez",
            "nadzor_zgoda", "nadzor_zgoda_przez", "nadzor_dla", "zrodlo", "rola", "user_msg_id", "cialo_sha",
            "payload_sha", "idem", "ponowienie_z", "dopisany_do", "stop_lokalny"} <= _kolumny(c, "przebiegi")
    assert {"klucz", "akcja", "spoznione", "z_przebiegu", "przebieg_id"} <= _kolumny(c, "przekazy")
    indeksy = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"watki_lista", "sesje_watek", "wpisy_czas", "przebiegi_aktywne", "przebiegi_watek", "przebiegi_sha",
            "przebiegi_lancuch", "przebiegi_nadzor", "karty_watek"} <= indeksy
    assert c.execute("PRAGMA user_version").fetchone()[0] == 1
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert [r[0] for r in c.execute("SELECT wersja FROM migracje")] == [1]
    c.close()
    assert stat.S_IMODE(os.stat(db.sciezka).st_mode) == 0o600
    assert db.meta("utworzono") is not None


def test_pragmy_polaczenia(db):
    c = db._conn
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert c.execute("PRAGMA synchronous").fetchone()[0] == 1          # NORMAL


def test_migracja_powtorna_nic_nie_robi_i_nowsza_wersja_odmawia(db, tmp_path):
    assert db.migruj() == 1
    assert not list(db.sciezka.parent.glob("*.bak-v*"))
    db._conn.execute("PRAGMA user_version = 7")
    with pytest.raises(RuntimeError, match="nowszą"):
        db.migruj()


def test_kopia_przed_migracja_zostaja_dwie(tmp_path, zegar, monkeypatch):
    d = rz.Rozmowy(tmp_path / "r.db", zegar=zegar)
    d.migruj()
    w = d.utworz_watek(tytul="Stary")
    dodatkowe = ["CREATE TABLE x2 (a);", "CREATE TABLE x3 (a);", "CREATE TABLE x4 (a);"]
    for n in range(2, 5):
        monkeypatch.setattr(rz, "MIGRACJE", (rz.MIGRACJA_1, *dodatkowe[:n - 1]))
        assert d.migruj() == n
    kopie = sorted(p.name for p in tmp_path.glob("r.db.bak-v*"))
    assert kopie == ["r.db.bak-v2", "r.db.bak-v3"]
    stara = sqlite3.connect(tmp_path / "r.db.bak-v3")
    assert stara.execute("PRAGMA user_version").fetchone()[0] == 3
    assert stara.execute("SELECT tytul FROM watki WHERE id = ?", (w["id"],)).fetchone()[0] == "Stary"
    stara.close()
    assert stat.S_IMODE(os.stat(tmp_path / "r.db.bak-v3").st_mode) == 0o600
    d.zamknij()


def test_nieudana_migracja_cofa_calosc(tmp_path, zegar, monkeypatch):
    d = rz.Rozmowy(tmp_path / "r.db", zegar=zegar)
    monkeypatch.setattr(rz, "MIGRACJE", (rz.MIGRACJA_1 + "\nCREATE TABLE watki (x);",))
    with pytest.raises(sqlite3.OperationalError):
        d.migruj()
    assert d.wersja() == 0
    assert d._conn.execute("SELECT count(*) FROM sqlite_master WHERE name = 'watki'").fetchone()[0] == 0
    d.zamknij()


# ------------------------------------------------------------------------------------------- wątki

def test_watek_i_lista(db, zegar):
    a = db.utworz_watek(tytul="Strona dla piekarni")
    zegar.plus(10)
    b = db.utworz_watek(tytul="Łódź i żółw")
    zegar.plus(10)
    c = db.utworz_watek(tytul="Trzeci")
    assert a["id"].startswith("w_") and len(a["id"]) == 23 and a["koordynator"] == "jarvo" and a["czlonkowie"] == []
    assert a["status"] == "cisza" and a["ostatni_agenci"] == [] and a["przypiety"] is False
    db.zmien(a["id"], przypiety=True)
    watki, dalej = db.lista()
    assert [w["id"] for w in watki] == [a["id"], c["id"], b["id"]] and dalej is None
    # stronicowanie przez strefę przypiętych
    strona1, dalej = db.lista(limit=1)
    assert [w["id"] for w in strona1] == [a["id"]] and dalej[2] == 1
    strona2, dalej = db.lista(limit=1, przed=dalej)
    strona3, dalej3 = db.lista(limit=1, przed=rz.kursor_tekst(dalej))
    assert [w["id"] for w in strona2 + strona3] == [c["id"], b["id"]] and dalej3 is None
    # szukanie bez polskich znaków i wielkości liter
    assert [w["id"] for w in db.lista(q="LODZ")[0]] == [b["id"]]
    assert db.lista(q="100%")[0] == []
    with pytest.raises(ValueError):
        db.lista(przed="zly")


def test_szukanie_w_tekscie_wlasciciela_nie_systemu(db):
    w = db.utworz_watek()
    db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="@web Popraw STOPKĘ", tresc="Popraw STOPKĘ", adresaci=["jarvo-web"])
    db.dodaj_wpis(w["id"], rodzaj="system", tekst="ukryte słowo", dane={"typ": "kompresja"})
    assert [x["id"] for x in db.lista(q="stopke")[0]] == [w["id"]]
    assert db.lista(q="ukryte")[0] == []


def test_filtry_archiwum_kosz_test(db, zegar):
    a = db.utworz_watek(tytul="A")
    b = db.utworz_watek(tytul="B")
    t = db.utworz_watek(tytul="próba", rodzaj="test")
    db.zmien(a["id"], archiwum=True)
    db.usun(b["id"])
    assert db.lista()[0] == []
    assert [w["id"] for w in db.lista(filtr="archiwum")[0]] == [a["id"]]
    assert [w["id"] for w in db.lista(filtr="kosz")[0]] == [b["id"]]
    assert db.watek(t["id"])["rodzaj"] == "test"
    db.przywroc(b["id"])
    assert [w["id"] for w in db.lista()[0]] == [b["id"]]


def test_zmien_tytul_i_pola(db):
    w = db.utworz_watek()
    assert w["tytul_zrodlo"] == "auto"
    w = db.zmien(w["id"], tytul="  Nowy   tytuł  " + "x" * 200)
    assert w["tytul"].startswith("Nowy tytuł x") and len(w["tytul"]) == rz.TYTUL_MAX and w["tytul_zrodlo"] == "wlasciciel"
    with pytest.raises(ValueError):
        db.zmien(w["id"], koordynator="ktos")


def test_aktywnosc_nieprzeczytane_archiwum_ostatni_agenci(db, zegar):
    w = db.utworz_watek()
    db.zmien(w["id"], archiwum=True)
    t = zegar.plus(5)
    w = db.aktywnosc(w["id"], at=t, podglad="Gotowe  " + "a" * 300, nieprzeczytane_plus=1, status="cisza",
                     agent="jarvo-web")
    assert w["archiwum"] is False and w["nieprzeczytane"] == 1 and w["aktywnosc_at"] == t
    assert len(w["podglad"]) == rz.PODGLAD_MAX and w["podglad"].endswith("…")
    db.aktywnosc(w["id"], at=t - 100, agent="jarvo")              # czas nie cofa sortowania
    w = db.aktywnosc(w["id"], at=t, agent="jarvo-studio")
    assert w["aktywnosc_at"] == t and w["ostatni_agenci"] == ["jarvo-studio", "jarvo"]
    db.przeczytane(w["id"], t - 1)
    assert db.watek(w["id"])["nieprzeczytane"] == 1
    db.przeczytane(w["id"], t)
    assert db.watek(w["id"])["nieprzeczytane"] == 0 and db.watek(w["id"])["przeczytane_at"] == t
    assert db.aktywnosc("w_nie_ma", at=t) is None


def test_tytul_z_tresci():
    assert rz.tytul_z_tresci("  Zrób   stronę  ") == "Zrób stronę"
    dlugi = "Przygotuj kompletną stronę internetową dla piekarni rodzinnej z Krakowa z menu i mapą dojazdu"
    t = rz.tytul_z_tresci(dlugi)
    assert len(t) <= rz.TYTUL_AUTO and t.endswith("…") and dlugi.startswith(t[:-1])
    assert rz.tytul_z_tresci("", obrazy=1, at=0).startswith("Obraz z ")
    assert rz.tytul_z_tresci("") == ""


# ------------------------------------------------------------------------------------------- członkowie i sesje

def test_czlonkowie_i_rodowod_sesji(db, zegar):
    w = db.utworz_watek()
    assert db.zapewnij_czlonka(w["id"], "jarvo-web")["sesja_id"] is None
    m = db.ustaw_sesje(w["id"], "jarvo-web", "s1", przypieta=True)
    assert (m["sesja_id"], m["sesja_tip"]) == ("s1", "s1")
    zegar.plus(1)
    m = db.ustaw_sesje(w["id"], "jarvo-web", "s2", powod="kompresja", rodzic="s1")
    assert (m["sesja_id"], m["sesja_tip"]) == ("s1", "s2")
    nadzor = db.ustaw_sesje(w["id"], "jarvo", "n1", rola="nadzor")
    db.zmien_czlonka(w["id"], "jarvo", "nadzor", tury_plus=40)
    nadzor = db.ustaw_sesje(w["id"], "jarvo", "n2", rola="nadzor", powod="rotacja", rodzic="n1")
    assert nadzor["tury"] == 0 and nadzor["sesja_tip"] == "n2"
    assert db.watek(w["id"])["czlonkowie"] == ["jarvo-web"]                   # nadzór nie jest członkiem rozmowy
    assert [s["sesja_id"] for s in db.sesje_watku(w["id"], agent="jarvo-web")] == ["s1", "s2"]
    assert db.sesje_watku(w["id"], agent="jarvo-web")[1]["rodzic_id"] == "s1"
    assert db.watek_sesji("jarvo", "n2") == (w["id"], "nadzor")
    assert db.watek_sesji("jarvo", "obca") is None
    assert {s["sesja_id"] for s in db.sesje_czlonkow(nieprzypiete=True)} == {"s2", "n1", "n2"}
    db.ustaw_przypieta("jarvo-web", "s2", True)
    assert {s["sesja_id"] for s in db.sesje_czlonkow("jarvo-web", nieprzypiete=True)} == set()
    m = db.zmien_czlonka(w["id"], "jarvo-web", widzial_at=50, odczyt_id=7)
    m = db.zmien_czlonka(w["id"], "jarvo-web", widzial_at=40, odczyt_id=3)    # znaczniki tylko rosną
    assert (m["widzial_at"], m["odczyt_id"]) == (50, 7)


def test_sesja_nalezy_do_jednego_watku(db):
    a, b = db.utworz_watek(), db.utworz_watek()
    db.ustaw_sesje(a["id"], "jarvo-web", "s1")
    with pytest.raises(ValueError, match="innego wątku"):
        db.ustaw_sesje(b["id"], "jarvo-web", "s1")


# ------------------------------------------------------------------------------------------- wpisy

def test_wpisy_seq_idempotencja_i_obrazy(db, zegar):
    w = db.utworz_watek()
    e1 = db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="@web ala", tresc="ala", adresaci=["jarvo-web"],
                       tryb="bezposrednio", klucz="k1", obrazy=[{"path": "/opt/data/inbox/a.png", "mime": "image/png"}])
    assert e1["seq"] == 1 and e1["powtorzony"] is False and e1["id"].startswith("e_") and e1["szukaj"] == "@web ala"
    assert e1["adresaci"] == ["jarvo-web"] and e1["obrazy"][0]["path"].endswith("a.png") and e1["dane"] == {}
    again = db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="inne", klucz="k1")
    assert again["id"] == e1["id"] and again["powtorzony"] is True and again["tekst"] == "@web ala"
    zegar.plus(1)
    e2 = db.dodaj_wpis(w["id"], rodzaj="system", dane={"typ": "dolaczyl", "agent": "jarvo-web"})
    assert e2["seq"] == 2 and e2["szukaj"] == ""
    with pytest.raises(ValueError, match="data URL"):
        db.dodaj_wpis(w["id"], rodzaj="wlasciciel", obrazy=[{"path": "data:image/png;base64,AAAA"}])
    with pytest.raises(sqlite3.IntegrityError):
        db.dodaj_wpis(w["id"], rodzaj="inny")
    assert [e["seq"] for e in db.wpisy(w["id"])] == [1, 2]
    assert [e["seq"] for e in db.wpisy(w["id"], limit=1)] == [2]                # najnowsze, w kolejności rosnącej
    assert [e["seq"] for e in db.wpisy(w["id"], przed_at=e2["utworzony_at"])] == [1]
    assert [e["seq"] for e in db.wpisy(w["id"], po_at=e1["utworzony_at"])] == [2]
    assert db.wpis_po_kluczu(w["id"], "k1")["id"] == e1["id"]


def test_klucz_jest_per_watek(db):
    a, b = db.utworz_watek(), db.utworz_watek()
    assert not db.dodaj_wpis(a["id"], rodzaj="wlasciciel", klucz="k")["powtorzony"]
    assert not db.dodaj_wpis(b["id"], rodzaj="wlasciciel", klucz="k")["powtorzony"]


def test_rownolegle_wpisy_z_watku_silnika(db):
    """Jedno połączenie piszące chronione blokadą: zapisy z kilku wątków nie gubią seq ani klucza."""
    w = db.utworz_watek()
    bledy = []

    def pisz(n):
        try:
            for i in range(20):
                db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst=f"{n}-{i}", klucz=f"{n}-{i % 10}")
        except Exception as exc:  # pragma: no cover - to byłby błąd
            bledy.append(exc)

    watki = [threading.Thread(target=pisz, args=(n,)) for n in range(4)]
    for t in watki:
        t.start()
    for t in watki:
        t.join()
    assert not bledy
    seq = [e["seq"] for e in db.wpisy(w["id"], limit=500)]
    assert seq == list(range(1, 41))


def test_odczyt_z_innego_watku_ma_wlasne_polaczenie(db):
    w = db.utworz_watek(tytul="z innego")
    wynik = {}
    t = threading.Thread(target=lambda: wynik.update(w=db.watek(w["id"]), lista=db.lista()))
    t.start()
    t.join()
    assert wynik["w"]["tytul"] == "z innego" and len(wynik["lista"][0]) == 1


# ------------------------------------------------------------------------------------------- przebiegi i przekazy

def test_przebiegi(db, zegar):
    w = db.utworz_watek()
    e = db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="@web ala")
    p = db.dodaj_przebieg(watek_id=w["id"], wpis_id=e["id"], agent="jarvo-web", nadzorowany=True,
                          payload={"prosba": "ala"})
    assert p["stan"] == "kolejka" and p["powod"] == "start" and p["lancuch_id"] == e["id"] and p["hop"] == 0
    assert p["idem"] == "jarvo-" + p["id"] and p["nadzorowany"] is True and p["payload"] == {"prosba": "ala"}
    zegar.plus(1)
    p = db.zmien_przebieg(p["id"], stan="wysylanie", wyslany_at=zegar(), payload_sha="abc", sesja_id="s1",
                          kroki=[{"nazwa": "terminal", "ms": 120}])
    assert p["kroki"][0]["ms"] == 120
    d = db.dodaj_przebieg(watek_id=w["id"], agent="jarvo-studio", zrodlo="przekaz", lancuch_id=e["id"], hop=1,
                          przekaz_z=p["id"])
    assert [x["id"] for x in db.przebiegi_aktywne()] == [p["id"], d["id"]]
    assert [x["id"] for x in db.przebiegi_lancucha(e["id"])] == [p["id"], d["id"]]
    nasze = db.nasze_wiersze(w["id"])
    assert set(nasze) == {p["id"]} and nasze[p["id"]]["payload_sha"] == "abc" and nasze[p["id"]]["aktywny"]
    db.zmien_przebieg(p["id"], stan="gotowe", zakonczony_at=zegar(), nadzor_stan="czeka")
    assert [x["id"] for x in db.przebiegi_watku(w["id"], aktywne=True)] == [d["id"]]
    assert [x["id"] for x in db.do_nadzoru(w["id"])] == [p["id"]]
    with pytest.raises(ValueError):
        db.dodaj_przebieg(watek_id=w["id"], agent="x")                       # bez łańcucha
    with pytest.raises(ValueError):
        db.zmien_przebieg(p["id"], cos=1)
    with pytest.raises(sqlite3.IntegrityError):
        db.zmien_przebieg(p["id"], stan="nieznany")


def test_przekaz_idempotentny(db):
    w = db.utworz_watek()
    k = "jarvo:s1:call_1"
    a = db.dodaj_przekaz(klucz=k, watek_id=w["id"], akcja="przekaz", od_agenta="jarvo", do_agenta="jarvo-web",
                         tresc="popraw", stan="przyjety", pliki=["/opt/data/a.txt"])
    b = db.dodaj_przekaz(klucz=k, watek_id=w["id"], akcja="przekaz", od_agenta="jarvo", tresc="inna",
                         stan="odrzucony")
    assert a == b and a["pliki"] == ["/opt/data/a.txt"] and a["spoznione"] is False
    with pytest.raises(ValueError):
        db.dodaj_przekaz(watek_id=w["id"])


def test_karty_blokady_meta(db):
    w = db.utworz_watek()
    assert db.przypnij_karte("t_1", w["id"], "jarvo-web") is True
    assert db.przypnij_karte("t_1", w["id"], "jarvo-web") is False
    db.zmien_karte("t_1", stan="running")
    assert db.karty_watku(w["id"])[0]["ostatni_stan"] == "running"
    assert db.zablokuj_karte("t_1", "watek_usuniety") is True
    assert db.zablokuj_karte("t_1", "watek_usuniety") is False
    assert db.meta("kanban_event_id", "0") == "0"
    db.ustaw_meta("kanban_event_id", 12)
    db.ustaw_meta("kanban_event_id", 13)
    assert db.meta("kanban_event_id") == "13"


# ------------------------------------------------------------------------------------------- kosz i sprzątanie

def test_usun_na_stale_zostawia_nagrobki(db):
    w = db.utworz_watek()
    db.ustaw_sesje(w["id"], "jarvo-web", "s1", przypieta=True)
    e = db.dodaj_wpis(w["id"], rodzaj="wlasciciel", tekst="x")
    db.dodaj_przebieg(watek_id=w["id"], wpis_id=e["id"], agent="jarvo-web")
    db.przypnij_karte("t_1", w["id"], "jarvo-web")
    sesje = db.usun(w["id"], trwale=True)
    assert [s["sesja_id"] for s in sesje] == ["s1"]
    assert db.watek(w["id"]) is None and db.wpisy(w["id"]) == [] and db.przebiegi_watku(w["id"]) == []
    (nagrobek,) = db.sesje_czlonkow("jarvo-web")
    assert nagrobek["watek_id"] is None and db.watek_sesji("jarvo-web", "s1") is None
    assert db._conn.execute("SELECT watek_id FROM karty WHERE task_id = 't_1'").fetchone()[0] is None


def test_sprzataj(db, zegar):
    stary = db.utworz_watek(tytul="stary")
    db.ustaw_sesje(stary["id"], "jarvo-web", "s-stara", przypieta=True)
    swiezy = db.utworz_watek(tytul="świeży")
    e = db.dodaj_wpis(swiezy["id"], rodzaj="wlasciciel", tekst="x")
    p = db.dodaj_przebieg(watek_id=swiezy["id"], wpis_id=e["id"], agent="jarvo-web", payload={"prosba": "x"})
    db.zmien_przebieg(p["id"], stan="gotowe", zakonczony_at=zegar())
    db.przypnij_karte("t_done", swiezy["id"], "jarvo-web")
    db.zmien_karte("t_done", stan="done")
    db.zablokuj_karte("t_done", "watek_usuniety")
    db.usun(stary["id"])
    zegar.plus(29 * 86400)
    db.usun(swiezy["id"])
    wynik = db.sprzataj()
    assert wynik["usuniete"] == [] and wynik["payload_wyzerowane"] == 0
    zegar.plus(2 * 86400)
    wynik = db.sprzataj()
    assert wynik["usuniete"] == [stary["id"]] and wynik["do_odpiecia"] == [{"agent": "jarvo-web", "sesja_id": "s-stara"}]
    assert db.watek(swiezy["id"]) is not None
    assert db._conn.execute("SELECT count(*) FROM blokady_kart").fetchone()[0] == 0
    zegar.plus(60 * 86400)
    db.przywroc(swiezy["id"])
    assert db.sprzataj()["payload_wyzerowane"] == 1 and db.przebieg(p["id"])["payload"] is None


def test_zdrowie(db):
    z = db.zdrowie()
    assert z == {"db_ok": True, "wersja": 1, "watki": 0, "przebiegi_aktywne": 0, "kolejka": 0, "sesje_nieprzypiete": 0}


# ------------------------------------------------------------------------------------------- import Bazy

@pytest.fixture
def profile(tmp_path):
    root = tmp_path / "profiles"
    for profil, sesje in (("test-e2e-a", {"sa": "Cześć z Bazy"}), ("test-e2e-b", {})):
        (root / profil).mkdir(parents=True)
        stan_hermesa.zbuduj(root / profil / "state.db", sesje_uzytkownika=sesje)
    return root


def test_import_hq_sessions_idempotentny(db, tmp_path, profile):
    plik = tmp_path / "hq-sessions.json"
    plik.write_text(json.dumps({"test-e2e-a": "sa", "test-e2e-b": "s-pusta", "test-e2e-c": "x", "jarvo": "None",
                                "jarvo-web": "", "../zly": "sa", "test-e2e-d": "s-nie-ma"}), encoding="utf-8")
    zawartosc = plik.read_bytes()
    stany = {p: (p / "state.db").read_bytes() for p in profile.iterdir()}
    agenci = {"test-e2e-a": "Test A", "test-e2e-b": "Test B", "jarvo": "Jarvo", "jarvo-web": "Web",
              "test-e2e-d": "Test D"}
    logi = []
    wynik = rz.migruj_hq_sessions(db, plik, profile, agenci=agenci, log=logi.append)
    assert len(wynik["zaimportowane"]) == 1
    assert wynik["pominiete"] == {"test-e2e-b": "pusta_sesja", "test-e2e-c": "nieznany_agent", "jarvo": "brak_sesji",
                                  "jarvo-web": "brak_sesji", "../zly": "nieznany_agent", "test-e2e-d": "pusta_sesja"}
    w = db.watek(wynik["zaimportowane"][0])
    assert (w["rodzaj"], w["tytul"], w["tytul_zrodlo"]) == ("import", "Rozmowa z Test A (Baza)", "import")
    assert w["aktywnosc_at"] == 2000.0 and w["czlonkowie"] == ["test-e2e-a"]
    assert db.czlonek(w["id"], "test-e2e-a")["sesja_tip"] == "sa"
    assert db.sesje_watku(w["id"])[0]["powod"] == "import"
    assert len(logi) == 2                                           # agenci spoza floty: raz na proces
    # drugi przebieg nic nie dodaje i nie loguje drugi raz
    wynik2 = rz.migruj_hq_sessions(db, plik, profile, agenci=agenci, log=logi.append)
    assert wynik2["zaimportowane"] == [] and wynik2["pominiete"]["test-e2e-a"] == "juz_zaimportowana"
    assert len(db.lista()[0]) == 1 and len(logi) == 2
    # plik i state.db profili bez zmian
    assert plik.read_bytes() == zawartosc
    assert all((p / "state.db").read_bytes() == stany[p] for p in profile.iterdir())


def test_import_brak_pliku_i_zly_json(db, tmp_path, profile):
    assert rz.migruj_hq_sessions(db, tmp_path / "nie-ma.json", profile, agenci={}) == {"zaimportowane": [],
                                                                                       "pominiete": {}}
    zly = tmp_path / "zly.json"
    zly.write_text("[1, 2]", encoding="utf-8")
    assert rz.migruj_hq_sessions(db, zly, profile, agenci={})["zaimportowane"] == []


def test_import_agenci_z_fleet_json(db, tmp_path, profile):
    plik = tmp_path / "hq-sessions.json"
    plik.write_text(json.dumps({"test-e2e-a": "sa"}), encoding="utf-8")
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps({"agents": [{"name": "test-e2e-a", "short": "Atest"}]}), encoding="utf-8")
    assert rz.agenci_z_fleet_json(fleet) == {"test-e2e-a": "Atest"}
    wynik = rz.migruj_hq_sessions(db, plik, profile, fleet_json=fleet)
    assert db.watek(wynik["zaimportowane"][0])["tytul"] == "Rozmowa z Atest (Baza)"


def test_sciezki_domyslne_jak_hq_core():
    assert rz.SCIEZKA.name == "rozmowy.db" and rz.SCIEZKA.parent.name == "state"
    assert rz.HQ_SESJE.name == "hq-sessions.json" and rz.PROFILE.name == "profiles"

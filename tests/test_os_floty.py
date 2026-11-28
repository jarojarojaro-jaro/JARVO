"""Oś zadań floty (hq/plugin/os_floty.py, docs/HQ.md „Oś floty”): zbieracz na prawdziwych sqlite w tmp (przebiegi
panelu, kanban, raporty rutyn, skrzynka omp, tury Telegrama przez czytnik, telefon-zadania.json), przyrost i koniec
wpisów, brak źródeł, kolejność dnia, trasy GET /flota/os, `jarvo flota os` i blok „Teraz we flocie” haka."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import types
from pathlib import Path

import pytest
from conftest import REPO, load_script

OS = load_script("hq/plugin/os_floty.py", "jarvo_test_os_floty")
ROZ = load_script("hq/plugin/rozmowy.py", "jarvo_test_os_floty_rozmowy")
RAP = load_script("hq/plugin/raporty.py", "jarvo_test_os_floty_raporty")
OMP = load_script("hq/plugin/omp_sesje.py", "jarvo_test_os_floty_omp")
TERAZ = load_script("wiedza/plugin/flota_teraz.py", "jarvo_test_flota_teraz")

T0 = time.mktime((2026, 11, 28, 10, 0, 0, 0, 0, -1))        # 28.11 10:00 czasu lokalnego


def _godz(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


class Czytnik:
    """Atrapa czytnika panelu: dzierżawy tur (Telegram), ostatni wiersz właściciela, odpowiedź tury."""

    def __init__(self):
        self.dzierzawy: dict[str, list[dict]] = {"jarvo-hacker": [
            {"sesja_id": "TG1", "platforma": "telegram", "od": T0 + 200, "do": T0 + 9999},
            {"sesja_id": "API", "platforma": "api_server", "od": T0 + 200, "do": T0 + 9999}]}
        self.odpowiedzi = {("jarvo", "S1", 5): "Oferty w tabeli", ("jarvo-hacker", "TG1", 10): "Poczta sprawdzona"}

    def dzierzawy_profilu(self, agent, teraz):
        return list(self.dzierzawy.get(agent, []))

    def ostatni_uzytkownika(self, agent, sesje):
        return ("Sprawdź pocztę od sk-tajny", "")

    def stan_sesji(self, agent, sesje):
        return {"max_id": 10, "skompaktowane": 0}

    def odpowiedz_tury(self, agent, sesje, po_id):
        return self.odpowiedzi.get((agent, sesje[0], po_id), "")


def _zapisz_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _przebieg(c, id_, *, agent="jarvo", stan="gotowe", t=T0, wpis=None, zaplecze="hermes", **inne):
    d = {"id": id_, "watek_id": "w1", "wpis_id": wpis, "agent": agent, "lancuch_id": id_, "stan": stan,
         "utworzony_at": t, "idem": f"i-{id_}", "zaplecze": zaplecze, **inne}
    c.execute(f"INSERT INTO przebiegi ({', '.join(d)}) VALUES ({', '.join('?' * len(d))})", list(d.values()))


@pytest.fixture
def swiat(tmp_path):
    dane = tmp_path / "dane"
    state = dane / "jarvo" / "state"
    r = ROZ.Rozmowy(state / "rozmowy.db")
    r.migruj()
    r.zamknij()
    c = sqlite3.connect(state / "rozmowy.db")
    c.execute("INSERT INTO watki (id, utworzony_at, aktywnosc_at) VALUES ('w1', ?, ?)", (T0, T0))
    c.execute("INSERT INTO watki (id, utworzony_at, aktywnosc_at) VALUES ('w2', ?, ?)", (T0, T0))
    c.execute("INSERT INTO czlonkowie (watek_id, agent, sesja_id, dodany_at) VALUES ('w1', 'jarvo', 'S1', ?)", (T0,))
    for i, (eid, tekst) in enumerate((("e1", "Znajdź 5 ofert OLX na telefonie\nszczegóły niżej"),
                                      ("e2", "Wyślij testowy SMS"))):
        c.execute("INSERT INTO wpisy (id, watek_id, seq, rodzaj, tekst, utworzony_at) VALUES (?, 'w1', ?, 'wlasciciel', ?, ?)",
                  (eid, i, tekst, T0))
    _przebieg(c, "p1", stan="pracuje", t=T0 + 60, wpis="e1", sesja_id="S1", user_msg_id=5,
              kroki=json.dumps([{"narzedzie": "terminal"}, {"komentarz": "patrzę"}, {"narzedzie": "mcp__phone__tap"}]))
    _przebieg(c, "p2", agent="s:op", zaplecze="omp", t=T0, wpis="e2", zakonczony_at=T0 + 30)
    _przebieg(c, "p3", stan="wlaczony", t=T0 + 90, dopisany_do="p1", payload=json.dumps({"prosba": "i jeszcze ceny"}))
    _przebieg(c, "p4", agent="jarvo-web", stan="blad", t=T0 + 10, zakonczony_at=T0 + 20,
              payload=json.dumps({"prosba": "Postaw stronę"}),
              blad=json.dumps({"kod": "model", "komunikat": "Praca się nie udała", "szczegoly": "max_iterations"}))
    # druga sesja tego samego profilu (28.11: SMS Jarva obok testu OLX na telefonie first)
    _przebieg(c, "p6", stan="pracuje", t=T0 + 300, sesja_id="S2", watek_id="w2",
              payload=json.dumps({"prosba": "Wyślij SMS do Michała"}))
    c.execute("INSERT INTO karty (task_id, watek_id, agent_zrodlo, utworzona_at) VALUES ('t1', 'w1', 'jarvo', ?)", (T0,))
    c.commit()
    c.close()

    k = sqlite3.connect(dane / "kanban.db")
    k.executescript("""
        CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, assignee TEXT, status TEXT NOT NULL,
          created_by TEXT, created_at INTEGER NOT NULL, started_at INTEGER, completed_at INTEGER, result TEXT,
          last_failure_error TEXT, session_id TEXT, block_kind TEXT);
        CREATE TABLE task_links (parent_id TEXT NOT NULL, child_id TEXT NOT NULL, PRIMARY KEY (parent_id, child_id));
        CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, status TEXT NOT NULL,
          started_at INTEGER NOT NULL, ended_at INTEGER, outcome TEXT, summary TEXT, error TEXT);
        CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, run_id INTEGER,
          kind TEXT NOT NULL, payload TEXT, created_at INTEGER NOT NULL);""")
    karty = [("t1", "Strona OLX", "Zrób stronę", "jarvo-web", "running", "jarvo", T0 + 100, None, "S1", None),
             ("t2", "Plan strony", "", "jarvo", "done", "operator", T0 + 50, T0 + 80, None, None),
             ("t3", "Hasło do panelu", "", "jarvo-ads", "blocked", None, T0 + 120, None, None, "needs_input"),
             ("t4", "Render filmu", "", "jarvo-wideo", "archived", "jarvo", T0 + 130, None, None, None)]
    for t in karty:
        k.execute("INSERT INTO tasks (id, title, body, assignee, status, created_by, created_at, completed_at, session_id, "
                  "block_kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", t)
        k.execute("INSERT INTO task_events (task_id, kind, created_at) VALUES (?, 'created', ?)", (t[0], t[6]))
    k.execute("INSERT INTO task_links VALUES ('t2', 't1')")
    k.execute("INSERT INTO task_runs (task_id, status, started_at, ended_at, outcome, summary) "
              "VALUES ('t2', 'done', ?, ?, 'completed', 'Plan gotowy')", (T0 + 51, T0 + 80))
    k.execute("INSERT INTO task_runs (task_id, status, started_at, ended_at, outcome, error) "
              "VALUES ('t4', 'crashed', ?, ?, 'crashed', 'ffmpeg padł')", (T0 + 131, T0 + 140))
    k.commit()
    k.close()

    rp = sqlite3.connect(state / "raporty.db")
    rp.executescript(RAP.SCHEMAT)
    rp.execute("INSERT INTO raporty VALUES ('jarvo/jarvo-daily-brief/a', 'jarvo', 'jarvo-daily-brief', 'Poranny brief', ?, "
               "'Brief dnia', 0)", (T0 - 7200,))
    rp.execute("INSERT INTO raporty VALUES ('jarvo-web/patrol/b', 'jarvo-web', 'patrol', 'Patrol', ?, 'padł', 1)", (T0 - 3600,))
    rp.commit()
    rp.close()

    sk = tmp_path / "op" / "skrzynka"
    (tmp_path / "op" / "sesje").mkdir(parents=True)
    _zapisz_json(dane / "jarvo" / "konfig" / "sesje.json", {"op": {
        "nazwa": "Operator", "skrzynka": str(sk), "panel": {"zaplecze": "omp", "sesje": str(tmp_path / "op" / "sesje"),
                                                             "sesja": "abcdef123456"}}})
    _zapisz_json(sk / "zrobione" / "panel-p2.json", {"zrodlo": "panel", "klucz": "p2", "odpowiedz": "SMS wysłany"})
    _zapisz_json(sk / "zrobione" / "20261128-093000-482.json", {
        "nazwa": "Operator", "tekst": "Sprawdź telefon first", "czas": "2026-11-28 09:30:00", "message_id": "482",
        "sekundy": 120, "tura": "20261128-093005-aaaaaa", "odpowiedz": "Telefon działa"})
    _zapisz_json(sk / "zrobione" / "20261128-080000-czuwanie.json", {
        "nazwa": "czuwanie", "tekst": "Czuwanie (skrypt): serwer wstał", "czas": "2026-11-28T08:00:00", "sekundy": 7,
        "tura": "20261128-080001-bbbbbb", "odpowiedz": "Przyjąłem"})
    _zapisz_json(sk / "bledy" / "20261128-070000-operator.json", {
        "nazwa": "Kernel", "tekst": "[Operator] zbadaj kartę", "czas": "2026-11-28 07:00:00", "zrodlo": "operator",
        "blad": "kod 1"})
    _zapisz_json(sk / "nowe" / "20261128-110000-500.json", {
        "nazwa": "Operator", "tekst": "Zrób zrzut ekranu", "czas": "2026-11-28 11:00:00", "message_id": "500"})
    _zapisz_json(sk / "nowe" / "20261128-110500-501.json", {
        "nazwa": "Operator", "tekst": "A potem następne", "czas": "2026-11-28 11:05:00", "message_id": "501"})
    _zapisz_json(sk / "stan.json", {"tura": {"id": "20261128-110005-cccccc", "pid": os.getpid(), "start": T0 + 3605,
                                             "klucze": []}})

    telefony = tmp_path / "stan" / "telefon-zadania.json"
    _zapisz_json(telefony, {"first": {"klucz": "sesja:S1", "t": T0 + 3650},
                            "pulpit": {"klucz": "karta:t1", "t": T0 + 3600},
                            "second": {"klucz": "sesja:TG1", "t": T0 + 3690},
                            "third": {"klucz": "sesja:STARA", "t": T0 - 5000}})
    zegar = [T0 + 3700]
    cz = Czytnik()
    z = OS.Zbieracz(state / "os-floty.db", dane=dane, rozmowy_db=state / "rozmowy.db", kanban_db=dane / "kanban.db",
                    raporty_db=state / "raporty.db", telefony=telefony, omp=OMP, czytnik=cz,
                    agenci=lambda: ["jarvo", "jarvo-hacker", "jarvo-web"], dom=tmp_path,
                    utajnij=lambda t: str(t).replace("sk-tajny", "[ukryte]"), zegar=lambda: zegar[0])
    yield types.SimpleNamespace(z=z, dane=dane, state=state, sk=sk, telefony=telefony, zegar=zegar, cz=cz,
                                plik=state / "os-floty.db")
    z.zamknij()


def _w(s, id_):
    return OS.wpis(s.plik, id_)


def test_zbieracz_wszystkie_zrodla(swiat):
    s = swiat
    zmiany = s.z.zbierz()
    assert len(zmiany) == len({z["id"] for z in zmiany}) >= 15
    assert all("prompt" not in z and "wynik_pelny" not in z for z in zmiany)
    p1 = _w(s, "p:p1")
    assert (p1["rodzaj"], p1["agent"], p1["zlecil"], p1["kanal"], p1["stan"]) == ("panel", "jarvo", "JARO", "panel", "w_toku")
    assert p1["tytul"] == "Znajdź 5 ofert OLX na telefonie" and p1["prompt"].endswith("szczegóły niżej")
    assert p1["wywolania"] == 2 and p1["zasoby"] == ["telefon:first"] and p1["watek_id"] == "w1" and p1["koniec_at"] is None
    assert p1["klucz"] == "sesja:S1" and _w(s, "p:p6")["klucz"] == "sesja:S2" and _w(s, "p:p6")["zasoby"] == []
    assert _w(s, "p:p2")["klucz"] is None                                # sesja omp: bez klucza strażnika
    p3 = _w(s, "p:p3")                                  # dopisek do trwającej tury: w toku razem z nią
    assert p3["stan"] == "w_toku" and p3["rodzic"] == "p:p1" and p3["tytul"] == "i jeszcze ceny"
    p2 = _w(s, "p:p2")
    assert (p2["agent"], p2["stan"], p2["wynik"], p2["koniec_at"]) == ("op", "gotowe", "SMS wysłany", T0 + 30)
    p4 = _w(s, "p:p4")
    assert p4["stan"] == "blad" and p4["wynik"] == "Praca się nie udała max_iterations" and p4["agent"] == "jarvo-web"
    k1 = _w(s, "k:t1")
    assert (k1["rodzaj"], k1["agent"], k1["zlecil"], k1["kanal"], k1["stan"]) == ("karta", "jarvo-web", "jarvo", "lista", "w_toku")
    assert k1["rodzic"] == "k:t2" and k1["watek_id"] == "w1" and k1["zasoby"] == ["pulpit"] and k1["start_at"] == T0 + 100
    assert k1["klucz"] == "karta:t1"
    assert (_w(s, "k:t2")["stan"], _w(s, "k:t2")["wynik"], _w(s, "k:t2")["zlecil"]) == ("gotowe", "Plan gotowy", "Operator")
    assert (_w(s, "k:t3")["stan"], _w(s, "k:t3")["zlecil"]) == ("pytanie", "JARO")
    assert (_w(s, "k:t4")["stan"], _w(s, "k:t4")["wynik"], _w(s, "k:t4")["koniec_at"]) == ("blad", "ffmpeg padł", T0 + 140)
    assert _w(s, "r:jarvo-web/patrol/b")["klucz"] is None
    r = _w(s, "r:jarvo-web/patrol/b")
    assert (r["rodzaj"], r["zlecil"], r["kanal"], r["stan"], r["start_at"], r["koniec_at"]) == \
        ("rutyna", "rutyna", "cron", "blad", T0 - 3600, T0 - 3600)
    assert _w(s, "r:jarvo/jarvo-daily-brief/a")["tytul"] == "Poranny brief"
    o = _w(s, "o:op:20261128-093000-482")
    assert (o["rodzaj"], o["agent"], o["zlecil"], o["kanal"], o["stan"], o["wynik"]) == \
        ("omp", "op", "JARO", "telegram", "gotowe", "Telefon działa")
    assert _godz(o["start_at"]) == "09:30" and o["koniec_at"] == time.mktime((2026, 11, 28, 9, 30, 5, 0, 0, -1)) + 120
    assert o["klucz"] is None
    cz = _w(s, "o:op:20261128-080000-czuwanie")
    assert (cz["zlecil"], cz["kanal"]) == ("rutyna", "cron")
    bl = _w(s, "o:op:20261128-070000-operator")
    assert (bl["stan"], bl["zlecil"], bl["kanal"], bl["wynik"]) == ("blad", "Operator", "terminal", "kod 1")
    assert _w(s, "o:op:20261128-110000-500")["stan"] == "w_toku"          # w trwającej turze
    assert _w(s, "o:op:20261128-110500-501") is None                     # czeka na następną turę
    assert OS.wpis(s.plik, "o:op:panel-p2") is None                      # panel to już przebieg p2
    tg = _w(s, f"t:jarvo-hacker:TG1:{int(T0 + 200)}")
    assert (tg["rodzaj"], tg["zlecil"], tg["kanal"], tg["stan"], tg["zasoby"]) == \
        ("telegram", "JARO", "telegram", "w_toku", ["telefon:second"])
    assert tg["prompt"] == "Sprawdź pocztę od [ukryte]" and tg["klucz"] == "sesja:TG1"   # utajnione przed zapisem
    assert _w(s, "p:p3")["klucz"] == "sesja:S1"                          # dopisek bez sesji: sesja członka wątku
    assert not [z for z in zmiany if z["id"].startswith("t:jarvo-hacker:API")]
    assert s.z.zbierz() == []                                            # nic nowego: brak zdarzenia


def test_przyrost_koniec_i_historia(swiat):
    s = swiat
    s.z.zbierz()
    c = sqlite3.connect(s.state / "rozmowy.db")
    c.execute("UPDATE przebiegi SET stan = 'gotowe', zakonczony_at = ? WHERE id = 'p1'", (T0 + 3690,))
    c.execute("DELETE FROM przebiegi WHERE id = 'p2'")                  # rozmowa usunięta: wpis osi zostaje
    _przebieg(c, "p5", agent="jarvo-hacker", stan="kolejka", t=T0 + 3695, payload=json.dumps({"prosba": "Nowe"}))
    c.commit()
    c.close()
    k = sqlite3.connect(s.dane / "kanban.db")
    k.execute("UPDATE tasks SET status = 'done', completed_at = ?, result = 'Strona stoi' WHERE id = 't1'", (T0 + 3698,))
    k.execute("INSERT INTO task_events (task_id, kind, created_at) VALUES ('t1', 'completed', ?)", (T0 + 3698,))
    k.commit()
    k.close()
    rp = sqlite3.connect(s.state / "raporty.db")
    rp.execute("INSERT INTO raporty VALUES ('jarvo/x/c', 'jarvo', 'x', 'Wieczorny', ?, 'ok', 0)", (T0 + 3000,))
    rp.commit()
    rp.close()
    nowa = s.sk / "nowe" / "20261128-110000-500.json"
    _zapisz_json(s.sk / "zrobione" / nowa.name, {**json.loads(nowa.read_text(encoding="utf-8")), "odpowiedz": "Zrzut zrobiony",
                                                  "sekundy": 30, "tura": "20261128-110005-cccccc"})
    nowa.unlink()
    _zapisz_json(s.sk / "stan.json", {"tura": None})
    s.cz.dzierzawy = {}
    s.zegar[0] = T0 + 3720
    zmiany = {z["id"]: z for z in s.z.zbierz()}
    assert set(zmiany) == {"p:p1", "p:p3", "p:p5", "k:t1", "r:jarvo/x/c", "o:op:20261128-110000-500",
                           f"t:jarvo-hacker:TG1:{int(T0 + 200)}"}
    p1 = _w(s, "p:p1")
    assert (p1["stan"], p1["koniec_at"], p1["wynik"], p1["zasoby"]) == ("gotowe", T0 + 3690, "Oferty w tabeli", ["telefon:first"])
    assert _w(s, "p:p3")["stan"] == "gotowe"
    assert _w(s, "p:p2")["wynik"] == "SMS wysłany"
    assert (_w(s, "k:t1")["stan"], _w(s, "k:t1")["wynik"], _w(s, "k:t1")["zasoby"]) == ("gotowe", "Strona stoi", ["pulpit"])
    assert _w(s, "o:op:20261128-110000-500")["wynik"] == "Zrzut zrobiony"
    tg = _w(s, f"t:jarvo-hacker:TG1:{int(T0 + 200)}")
    assert (tg["stan"], tg["koniec_at"], tg["wynik"]) == ("gotowe", T0 + 3720, "Poczta sprawdzona")
    assert zmiany["p:p5"]["stan"] == "w_toku" and zmiany["p:p5"]["zmieniono_at"] == T0 + 3720


def test_omp_tura_zgubiona_konczy_wpis(swiat):
    s = swiat
    s.z.zbierz()
    (s.sk / "nowe" / "20261128-110000-500.json").unlink()                 # ani w zrobione, ani w bledy
    _zapisz_json(s.sk / "stan.json", {"tura": None})
    s.z.zbierz()
    w = _w(s, "o:op:20261128-110000-500")
    assert (w["stan"], w["koniec_at"]) == ("przerwane", T0 + 3700)


def test_brak_zrodel_nie_przeszkadza(tmp_path):
    z = OS.Zbieracz(tmp_path / "os.db", dane=tmp_path / "brak", rozmowy_db=tmp_path / "brak.db",
                    kanban_db=tmp_path / "brak2.db", raporty_db=tmp_path / "brak3.db", telefony=tmp_path / "t.json",
                    omp=OMP, czytnik=None, agenci=None, dom=tmp_path)
    assert z.zbierz() == []
    assert OS.lista(tmp_path / "os.db", "2026-11-28")["zadania"] == []
    assert OS.lista(tmp_path / "nie-ma.db", "2026-11-28") == {"dzien": "2026-11-28", "dni": [], "zadania": []}
    assert OS.wpis(tmp_path / "nie-ma.db", "p:x") is None
    z.zamknij()
    assert oct((tmp_path / "os.db").stat().st_mode & 0o777) == "0o600"


def test_kolejnosc_dnia_filtr_i_dni(swiat):
    s = swiat
    s.z.zbierz()
    d = OS.lista(s.plik, "2026-11-28", teraz=T0 + 3700)
    stany = [z["stan"] for z in d["zadania"]]
    otwarte = [z for z in d["zadania"] if z["stan"] in ("w_toku", "pytanie")]
    assert stany[:len(otwarte)] == [z["stan"] for z in otwarte]           # w toku i pytania na górze
    assert [z["start_at"] for z in otwarte] == sorted(z["start_at"] for z in otwarte)
    reszta = [z["start_at"] for z in d["zadania"][len(otwarte):]]
    assert reszta == sorted(reszta, reverse=True)
    assert d["dni"] == ["2026-11-28"] and d["dzien"] == "2026-11-28"
    assert {z["agent"] for z in OS.lista(s.plik, "2026-11-28", "op", teraz=T0)["zadania"]} == {"op"}
    assert OS.lista(s.plik, "2026-11-27", teraz=T0)["zadania"] == []
    with pytest.raises(ValueError):
        OS.lista(s.plik, "28.11.2026")


def test_runda_co_5_s(swiat):
    s = swiat
    assert s.z.runda()                                                    # pierwszy obieg: zmiany
    s.zegar[0] += 2
    assert s.z.runda() is None                                            # przed upływem 5 s nic nie czyta
    s.zegar[0] += 4
    assert s.z.runda() is None                                            # nic nowego


def test_trasy(swiat):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    s = swiat
    s.z.zbierz()
    router = fastapi.APIRouter()
    OS.dolacz(router, plik=s.plik)
    app = fastapi.FastAPI()
    app.include_router(router)
    c = TestClient(app)
    d = c.get("/flota/os", params={"dzien": "2026-11-28"}).json()
    assert d["dzien"] == "2026-11-28" and "p:p1" in [z["id"] for z in d["zadania"]]
    assert all("prompt" not in z for z in d["zadania"]) and isinstance(d["zadania"][0]["zasoby"], list)
    assert {z["agent"] for z in c.get("/flota/os", params={"dzien": "2026-11-28", "agent": "jarvo-web"}).json()["zadania"]} \
        == {"jarvo-web"}
    w = c.get("/flota/os/p:p1").json()["zadanie"]
    assert w["prompt"].startswith("Znajdź") and w["zasoby"] == ["telefon:first"]
    assert c.get("/flota/os/o:op:20261128-093000-482").status_code == 200
    assert c.get("/flota/os/p:nie-ma").status_code == 404
    assert c.get("/flota/os/..%2F..").status_code == 404
    assert c.get("/flota/os", params={"dzien": "jutro"}).json()["blad"]["kod"] == "zle_dane"
    assert c.get("/flota/os", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_cli_flota_os(swiat, capsys):
    from jarvo import cli, os_floty_cli
    s = swiat
    s.z.zbierz()
    u = types.SimpleNamespace(jarvo_dane=s.dane / "jarvo")
    a = cli._parser().parse_args(["flota", "os", "--dzien", "2026-11-28"])
    assert a.funkcja is os_floty_cli.polecenie_flota
    assert a.funkcja(u, a, [], None) == 0
    out = capsys.readouterr().out
    assert "Oś floty 2026-11-28" in out and "Teraz (w toku i pytania):" in out
    assert "jarvo-web ← jarvo (lista)  Strona OLX [pulpit]  #k:t1" in out and "Wyślij testowy SMS" in out
    a = cli._parser().parse_args(["flota", "os", "--pelne", "p:p1"])
    assert a.funkcja(u, a, [], None) == 0
    out = capsys.readouterr().out
    assert "Prompt:\nZnajdź 5 ofert OLX na telefonie\nszczegóły niżej" in out and "zasoby: telefon:first" in out
    a = cli._parser().parse_args(["flota", "os", "--dzien", "2026-11-28", "--agent", "op", "--json"])
    assert a.funkcja(u, a, [], None) == 0
    assert {z["agent"] for z in json.loads(capsys.readouterr().out)["zadania"]} == {"op"}
    a = cli._parser().parse_args(["flota", "os", "--pelne", "p:nie-ma"])
    assert a.funkcja(u, a, [], None) == 1


def test_blok_teraz_we_flocie(swiat):
    s = swiat
    s.z.zbierz()
    teraz = T0 + 3700
    blok = TERAZ.blok(s.plik, s.telefony, "jarvo", {"sesja:S1"}, teraz)
    linie = blok.splitlines()
    assert linie[0] == TERAZ.NAGLOWEK and len(linie) <= TERAZ.MAKS_LINII
    assert "jarvo-web · Strona OLX · od 10:01 · pulpit" in linie
    assert "jarvo-ads · Hasło do panelu (czeka na odpowiedź) · od 10:02" in linie
    assert any(x.startswith("jarvo-hacker · Sprawdź pocztę od [ukryte] · od 10:03 · telefon:second") for x in linie)
    assert "jarvo (twoja inna rozmowa) · Wyślij SMS do Michała · od 10:05" in linie
    assert not any("Znajdź 5 ofert" in x or "i jeszcze ceny" in x for x in linie)   # własna sesja S1 (i jej dopisek)
    assert not any("telefon:first" in x for x in linie)                  # telefon własnej sesji
    assert not any("third" in x for x in linie)                          # krok sprzed 10 min: wolny
    # cudza sesja na telefonie first (Jarvo z innego profilu): urządzenie zajęte
    blok = TERAZ.blok(s.plik, s.telefony, "jarvo-web", set(), teraz)
    assert "jarvo · Znajdź 5 ofert OLX na telefonie · od 10:01 · telefon:first" in blok.splitlines()
    # karta widzi wszystko poza sobą, z pulpitem karty też nie
    blok = TERAZ.blok(s.plik, s.telefony, "jarvo-web", {"karta:t1"}, teraz)
    assert "Strona OLX" not in blok and "pulpit" not in blok
    assert TERAZ.blok(s.plik.with_name("brak.db"), s.telefony.with_name("brak.json"), "jarvo", set(), teraz) == ""
    start = time.perf_counter()
    for _ in range(20):
        TERAZ.blok(s.plik, s.telefony, "jarvo", {"sesja:S1"}, teraz)
    assert (time.perf_counter() - start) / 20 < 0.05                    # rząd milisekund (zapas na wolny CI)


def test_dwie_sesje_jednego_profilu(swiat):
    """28.11: test OLX i SMS Jarva to dwie sesje profilu `jarvo`; druga sesja widzi pierwszą z zajętym telefonem
    (zasób dopasowany po kluczu `sesja:<id>` z telefon-zadania.json), a pierwsza drugą bez telefonu."""
    s = swiat
    s.z.zbierz()
    teraz = T0 + 3700
    linie = TERAZ.blok(s.plik, s.telefony, "jarvo", {"sesja:S2"}, teraz).splitlines()
    assert "jarvo (twoja inna rozmowa) · Znajdź 5 ofert OLX na telefonie · od 10:01 · telefon:first" in linie
    assert "jarvo (twoja inna rozmowa) · i jeszcze ceny · od 10:01 · telefon:first" in linie   # dopisek tej sesji
    assert not any("Wyślij SMS do Michała" in x for x in linie)
    assert not any(x.startswith("telefon:first ·") for x in linie)      # telefon przy zadaniu, nie osobno
    # strażnik przeniósł first na sesję S2: zasób dochodzi do jej wpisu, u S1 zostaje z historii
    _zapisz_json(s.telefony, {"first": {"klucz": "sesja:S2", "t": T0 + 3710}})
    s.zegar[0] = T0 + 3715
    assert [z["id"] for z in s.z.zbierz()] == ["p:p6"]
    assert _w(s, "p:p6")["zasoby"] == ["telefon:first"]
    linie = TERAZ.blok(s.plik, s.telefony, "jarvo", {"sesja:S1"}, T0 + 3715).splitlines()
    assert "jarvo (twoja inna rozmowa) · Wyślij SMS do Michała · od 10:05 · telefon:first" in linie


def test_migracja_starej_bazy_bez_klucza(swiat):
    """Baza osi sprzed kolumny `klucz` (pierwszy kształt kontraktu): kolumna dochodzi przy otwarciu, stare wpisy
    zostają, otwarte dostają klucz w następnym obiegu."""
    s = swiat
    stary = sqlite3.connect(s.plik)
    stary.executescript(OS.SCHEMAT.replace("  klucz TEXT,\n", ""))
    stary.execute("INSERT INTO zadania (id, rodzaj, agent, zlecil, kanal, tytul, stan, start_at, zmieniono_at) "
                  "VALUES ('p:historia', 'panel', 'jarvo', 'JARO', 'panel', 'Stare zadanie', 'gotowe', ?, ?)", (T0 - 9e4, T0))
    stary.execute("INSERT INTO zadania (id, rodzaj, agent, zlecil, kanal, tytul, stan, start_at, zmieniono_at) "
                  "VALUES ('p:p1', 'panel', 'jarvo', 'JARO', 'panel', 'Znajdź 5 ofert', 'w_toku', ?, ?)", (T0 + 60, T0))
    stary.commit()
    assert "klucz" not in {r[1] for r in stary.execute("PRAGMA table_info(zadania)")}
    stary.close()
    s.z.zbierz()
    c = sqlite3.connect(s.plik)
    assert "klucz" in {r[1] for r in c.execute("PRAGMA table_info(zadania)")}
    assert "zadania_klucz" in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    c.close()
    assert _w(s, "p:historia")["tytul"] == "Stare zadanie" and _w(s, "p:historia")["klucz"] is None
    assert (_w(s, "p:p1")["klucz"], _w(s, "p:p1")["zasoby"]) == ("sesja:S1", ["telefon:first"])


def test_modul_bez_zaleznosci_hermesa():
    """CLI i hak ładują moduły po ścieżce (bez pakietu, bez FastAPI w chwili importu)."""
    src = (REPO / "hq" / "plugin" / "os_floty.py").read_text(encoding="utf-8")
    assert "from __future__ import annotations" not in src                # adnotacje tras = klasy FastAPI
    assert "import fastapi" not in src.split("def dolacz")[0]

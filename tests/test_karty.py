"""Karty pracy w wątku (hq/plugin/karty.py): stan przekazań z tablicy kanbana i z sesji pracowników, na danych
w kształcie pierwszej sesji właściciela (Web, Sherlock, Łowca) i bez sieci."""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hq" / "plugin"))
spec = importlib.util.spec_from_file_location("jarvo_hq_karty", REPO / "hq" / "plugin" / "karty.py")
karty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(karty)
import hq_core as core  # noqa: E402

T0 = 1_792_975_800


def kanban(path: Path, tasks, runs, events) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, assignee TEXT, status TEXT NOT NULL, created_at INTEGER,
      started_at INTEGER, completed_at INTEGER, last_heartbeat_at INTEGER, current_run_id INTEGER, result TEXT);
    CREATE TABLE task_runs (id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT, status TEXT, started_at INTEGER,
      ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT);
    CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT,
      payload TEXT, created_at INTEGER);
    """)
    conn.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)", tasks)
    conn.executemany("INSERT INTO task_runs VALUES (?,?,?,?,?,?,?,?,?)", runs)
    conn.executemany("INSERT INTO task_events (task_id, run_id, kind, payload, created_at) VALUES (?,?,?,?,?)",
                     [(t, r, k, json.dumps(p) if p is not None else None, c) for t, r, k, p, c in events])
    conn.commit()
    conn.close()
    return path


def sesje(path: Path, wiersze) -> Path:
    """state.db pracownika: sesje kanbana i ich wiadomości."""
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at REAL);
    CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
      tool_calls TEXT, tool_call_id TEXT, tool_name TEXT, timestamp REAL, display_kind TEXT);
    """)
    for sid, tytul, start, wiadomosci in wiersze:
        conn.execute("INSERT INTO sessions VALUES (?, 'kanban', ?, ?)", (sid, tytul, start))
        for m in wiadomosci:
            conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp) "
                         "VALUES (?,?,?,?,?,?,?)", (sid, m.get("role"), m.get("content"), json.dumps(m["tool_calls"])
                                                     if m.get("tool_calls") else None, m.get("tool_call_id"),
                                                     m.get("tool_name"), m.get("ts", start + 5)))
    conn.commit()
    conn.close()
    return path


def wywolanie(nazwa, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": nazwa, "arguments": json.dumps(args)}}


AUDYT, KONK, LEADY = "[Z-1] Szybki audyt strony", "[Z-1] 3 konkurentów", "[Z-1] 10 firm"


def swiat(tmp_path):
    db = kanban(tmp_path / "kanban.db", [
        ("t_e4911a62", AUDYT, "jarvo", "running", T0, T0 + 10, None, T0 + 200, 20, None),
        ("t_2d67cf6c", KONK, "jarvo", "done", T0, T0 + 10, T0 + 500, T0 + 480, None, None),
        ("t_06f3c3fc", LEADY, "jarvo-lowca", "running", T0, T0 + 10, None, T0 + 900, 19, None),
        ("t_00000aaa", "[Z-1] Grafiki", "jarvo-studio", "blocked", T0, None, None, None, None, None),
        ("t_00000bbb", "[Z-1] Stopka", "jarvo-web", "ready", T0, None, None, None, None, None),
    ], [
        (17, "t_e4911a62", "jarvo-web", "review", T0 + 10, T0 + 180, "review_requested", "Audyt gotowy: 5 problemów.",
         json.dumps({"artifacts": ["D:/Jarvo/dane/jarvo/missions/Z-1/audyt/out/audyt.md"]})),
        (20, "t_e4911a62", "jarvo", "running", T0 + 190, None, None, None, None),
        (18, "t_2d67cf6c", "jarvo-sherlock", "review", T0 + 10, T0 + 300, "review_requested", "3 konkurentów ze źródłami.",
         json.dumps({"artifacts": ["D:/x/konkurencja.md"]})),
        (21, "t_2d67cf6c", "jarvo", "done", T0 + 310, T0 + 500, "completed", "Recenzja: zatwierdzam, 3 źródła sprawdzone.",
         None),
        (19, "t_06f3c3fc", "jarvo-lowca", "running", T0 + 10, None, None, None, None),
    ], [
        ("t_06f3c3fc", 19, "heartbeat", {"note": "Rozumiem zlecenie: 10 firm z sygnałem zakupu."}, T0 + 20),
        ("t_06f3c3fc", 19, "heartbeat", None, T0 + 900),
        ("t_e4911a62", 17, "review_requested", {"summary": "Audyt gotowy", "reviewer": "jarvo"}, T0 + 180),
        ("t_2d67cf6c", 21, "completed", {"summary": "Recenzja: zatwierdzam"}, T0 + 500),
        ("t_00000aaa", None, "blocked", {"reason": "Potrzebne logo w SVG"}, T0 + 50),
    ])
    profile = tmp_path / "profiles"
    (profile / "jarvo-lowca").mkdir(parents=True)
    (profile / "jarvo").mkdir()
    sesje(profile / "jarvo-lowca" / "state.db", [
        ("s-stara", "[Z-0] inna karta", T0 - 4000, [{"role": "assistant", "tool_calls": [wywolanie("web_search", {"query": "stare"})]}]),
        ("s-lowca", LEADY, T0 + 15, [
            {"role": "assistant", "tool_calls": [wywolanie("skill_view", {"name": "lista-leadow"})]},
            {"role": "tool", "tool_call_id": "c1", "content": "{}"},
            {"role": "assistant", "content": "Zaczynam od przetargów.", "tool_calls": [
                wywolanie("terminal", {"command": "python przetargi.py bzp --od 2026-10-12 --szukaj AI"}, "c2")]},
        ]),
    ])
    sesje(profile / "jarvo" / "state.db", [
        ("s-sedzia", AUDYT, T0 + 192, [{"role": "assistant", "content": "Sprawdzam raport na zimno.",
                                        "tool_calls": [wywolanie("read_file", {"path": "out/audyt.md"})]}]),
    ])

    def state_db(profil):
        p = profile / profil / "state.db"
        return p if p.exists() else None
    return db, state_db


def test_stan_kart_pierwszej_sesji(tmp_path):
    db, state_db = swiat(tmp_path)
    ids = ["t_e4911a62", "t_2d67cf6c", "t_06f3c3fc", "t_00000aaa", "t_00000bbb", "t_nieznana1", "zle id", "t_e4911a62"]
    k = karty.stan_kart(db, ids, recenzent="jarvo", state_db=state_db, etykieta=core.tool_label)
    assert set(k) == {"t_e4911a62", "t_2d67cf6c", "t_06f3c3fc", "t_00000aaa", "t_00000bbb"}
    audyt = k["t_e4911a62"]
    # wykonawcą jest Web, choć karta jest teraz przypisana sędziemu: sędzia sprawdza (etap „ocena”)
    assert audyt["agent"] == "jarvo-web" and audyt["przypisany"] == "jarvo" and audyt["etap"] == "ocena"
    assert audyt["podsumowanie"] == "Audyt gotowy: 5 problemów." and audyt["proby"] == 1 and audyt["koniec"] is None
    assert audyt["pliki"] == ["D:/Jarvo/dane/jarvo/missions/Z-1/audyt/out/audyt.md"] and audyt["ocena"] == ""
    assert audyt["teraz"]["verb"] == "czyta" and audyt["teraz"]["detail"] == "out/audyt.md"          # krok sędziego
    konk = k["t_2d67cf6c"]
    assert konk["etap"] == "gotowe" and konk["agent"] == "jarvo-sherlock" and konk["koniec"] == T0 + 500
    assert konk["podsumowanie"] == "3 konkurentów ze źródłami." and konk["ocena"].startswith("Recenzja: zatwierdzam")
    assert konk["teraz"] is None and konk["pliki"] == ["D:/x/konkurencja.md"]
    leady = k["t_06f3c3fc"]
    assert leady["etap"] == "pracuje" and leady["notatka"] == "Rozumiem zlecenie: 10 firm z sygnałem zakupu."
    assert leady["teraz"]["verb"] == "terminal" and "przetargi.py bzp" in leady["teraz"]["detail"]  # nie stara sesja
    assert leady["ostatnio"] == T0 + 900
    assert k["t_00000aaa"]["etap"] == "zablokowana" and k["t_00000aaa"]["powod"] == "Potrzebne logo w SVG"
    assert k["t_00000bbb"]["etap"] == "czeka" and k["t_00000bbb"]["agent"] == "jarvo-web"


def test_etapy_kart():
    e = karty._etap
    assert e("review", "jarvo", "jarvo-web", "jarvo", "review_requested") == "do_oceny"
    assert e("running", "jarvo-web", "jarvo-web", "jarvo", "changes_requested") == "poprawki"
    assert e("ready", "jarvo-web", "jarvo-web", "jarvo", "changes_requested") == "poprawki"
    assert e("blocked", "jarvo-web", "jarvo-web", "jarvo", "gave_up") == "porzucona"
    assert e("archived", "jarvo-web", "jarvo-web", "jarvo", None) == "gotowe"
    assert e("running", "jarvo", "jarvo", "jarvo", None) == "pracuje"                 # karta samego Jarva


def test_przebieg_karty_wykonawca_i_sedzia(tmp_path):
    db, state_db = swiat(tmp_path)

    def wiadomosci(sciezka, sesja):
        return core.read_session_messages(sciezka, sesja)[1]
    p = karty.przebieg(db, "t_e4911a62", recenzent="jarvo", state_db=state_db, wiadomosci=wiadomosci,
                       aktywnosc=core.activity_from_messages)
    assert [(x["profil"], x["rola"]) for x in p] == [("jarvo-web", "praca"), ("jarvo", "ocena")]
    assert p[0]["kroki"] == []                                                     # sesji Weba nie ma w danych
    assert [k["kind"] for k in p[1]["kroki"]] == ["say", "tool"] and p[1]["kroki"][1]["verb"] == "czyta"
    p = karty.przebieg(db, "t_06f3c3fc", recenzent="jarvo", state_db=state_db, wiadomosci=wiadomosci,
                       aktywnosc=core.activity_from_messages)
    kroki = p[0]["kroki"]
    assert [k.get("verb") or k["kind"] for k in kroki] == ["czyta skill", "say", "terminal"]
    assert kroki[0]["status"] == "done" and kroki[2]["status"] == "running"
    assert karty.przebieg(db, "zle", recenzent="jarvo", state_db=state_db, wiadomosci=wiadomosci,
                          aktywnosc=core.activity_from_messages) == []


def test_bez_tablicy_i_utajnianie(tmp_path):
    assert karty.stan_kart(tmp_path / "nie-ma.db", ["t_e4911a62"], recenzent="jarvo", state_db=lambda p: None,
                           etykieta=core.tool_label) == {}
    db, state_db = swiat(tmp_path)
    k = karty.stan_kart(db, ["t_06f3c3fc"], recenzent="jarvo", state_db=state_db, etykieta=core.tool_label,
                        utajnij=lambda t: t.replace("10 firm", "[ukryte]"))
    assert k["t_06f3c3fc"]["notatka"] == "Rozumiem zlecenie: [ukryte] z sygnałem zakupu."
    assert karty.poprawne_id([f"t_{i:08x}" for i in range(60)]) == [f"t_{i:08x}" for i in range(karty.NAJWIECEJ)]

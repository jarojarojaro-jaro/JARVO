"""TARS HQ: logika stanu floty na prawdziwych bazach SQLite w schemacie Hermesa."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from conftest import load_script

core = load_script("hq/plugin/hq_core.py", "tars_hq_core_test")

NOW = 1_800_000_000.0
MIN = 60

FLEET = [
    {"name": "tars", "kind": "orchestrator", "title": "Main Judge", "emoji": "🛰️", "room": "bridge", "short": "TARS"},
    {"name": "tars-sherlock", "kind": "specialist", "title": "Detektyw", "emoji": "🔎", "room": "study", "short": "Sherlock"},
    {"name": "tars-web", "kind": "specialist", "title": "Web", "emoji": "🌐", "room": "devlab", "short": "Web"},
    {"name": "tars-studio", "kind": "specialist", "title": "Studio", "emoji": "🎬", "room": "atelier", "short": "Studio"},
    {"name": "tars-reka", "kind": "generalist", "title": "Ręka", "emoji": "🦾", "room": "workshop", "short": "Ręka"},
]


def make_kanban(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, assignee TEXT, status TEXT NOT NULL,
      priority INTEGER DEFAULT 0, created_by TEXT, created_at INTEGER NOT NULL, started_at INTEGER, completed_at INTEGER,
      workspace_kind TEXT NOT NULL DEFAULT 'scratch', workspace_path TEXT, result TEXT, last_heartbeat_at INTEGER,
      current_run_id INTEGER, session_id TEXT, block_kind TEXT, skills TEXT, last_failure_error TEXT);
    CREATE TABLE task_links (parent_id TEXT NOT NULL, child_id TEXT NOT NULL, PRIMARY KEY (parent_id, child_id));
    CREATE TABLE task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, author TEXT NOT NULL,
      body TEXT NOT NULL, created_at INTEGER NOT NULL);
    CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, run_id INTEGER,
      kind TEXT NOT NULL, payload TEXT, created_at INTEGER NOT NULL);
    CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, profile TEXT, status TEXT NOT NULL,
      started_at INTEGER NOT NULL);
    """)
    n = int(NOW)
    tasks = [
        # id, title, assignee, status, created, started, completed, heartbeat, run, session, block_kind, workspace
        ("t_a1", "Research konkurencji", "tars-sherlock", "running", n - 3600, n - 600, None, n - 20, 1, "sess-sher", None, None),
        ("t_a2", "Landing Ziarno", "tars-web", "review", n - 3600, n - 1200, None, n - 400, 2, None, None, None),
        ("t_a3", "Grafiki IG", "tars-studio", "blocked", n - 3600, None, None, None, None, None, "needs_input", None),
        ("t_a4", "Film Reels", "tars-studio", "ready", n - 3600, None, None, None, None, None, None, None),
        ("t_a5", "Złożenie pakietu", "tars-reka", "todo", n - 3600, None, None, None, None, None, None, None),
        ("t_a6", "Cennik PDF", "tars-reka", "done", n - 9000, n - 8000, n - 7000, None, None, None, None, None),
        ("t_a7", "Stara karta", "tars-reka", "done", n - 30 * 86400, None, n - 29 * 86400, None, None, None, None, None),
        ("t_a8", "Dostęp do Cloudflare", "tars-web", "blocked", n - 3600, None, None, None, None, None, "capability", None),
    ]
    conn.executemany("""INSERT INTO tasks (id, title, assignee, status, created_at, started_at, completed_at,
        last_heartbeat_at, current_run_id, session_id, block_kind, workspace_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", tasks)
    conn.executemany("INSERT INTO task_runs (id, task_id, profile, status, started_at) VALUES (?,?,?,?,?)",
                     [(1, "t_a1", "tars-sherlock", "running", n - 600), (2, "t_a2", "tars", "running", n - 60)])
    events = [
        ("t_a1", "created", {}, n - 3600), ("t_a1", "spawned", {}, n - 600),
        ("t_a2", "review_requested", {"implementer": "tars-web"}, n - 400),
        ("t_a3", "blocked", {"kind": "needs_input", "reason": "Która data otwarcia: 12 czy 19?"}, n - 900),
        ("t_a8", "blocked", {"kind": "capability", "reason": "brak tokenu Cloudflare"}, n - 800),
        ("t_a6", "completed", {}, n - 7000), ("t_a6", "changes_requested", {}, n - 7500),
        ("t_a1", "commented", {}, n - 100),
    ]
    conn.executemany("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                     [(t, k, json.dumps(p), c) for t, k, p, c in events])
    conn.execute("INSERT INTO task_comments (task_id, author, body, created_at) VALUES ('t_a1', 'tars', 'Skup się na Kazimierzu', ?)", (n - 100,))
    conn.execute("INSERT INTO task_links VALUES ('t_a3', 't_a4')")
    conn.commit()
    conn.close()


def make_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, started_at REAL);
    CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
      content TEXT, tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, display_kind TEXT);
    """)
    conn.execute("INSERT INTO sessions VALUES ('sess-sher', 'cli', ?)", (NOW - 600,))
    rows = [
        ("user", "Karta t_a1: research konkurencji kawiarni", None, None, None, NOW - 600),
        ("assistant", "", json.dumps([{"id": "c1", "function": {"name": "web_search", "arguments": json.dumps({"query": "kawiarnie specialty Kraków"})}}]), None, None, NOW - 590),
        ("tool", '{"results": []}', None, "c1", "web_search", NOW - 580),
        ("assistant", "Mam 3 źródła, sprawdzam ceny.", json.dumps([{"id": "c2", "function": {"name": "web_extract", "arguments": {"url": "https://example.com/ceny"}}}]), None, None, NOW - 500),
        ("tool", "Error: timeout", None, "c2", "web_extract", NOW - 490),
        ("assistant", "", json.dumps([{"id": "c3", "function": {"name": "write_file", "arguments": json.dumps({"path": "out/RAPORT.md", "content": "..."})}}]), None, None, NOW - 30),
    ]
    conn.executemany("INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp) VALUES ('sess-sher',?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO messages (session_id, role, content, timestamp, active) VALUES ('sess-sher','assistant','stare',?,0)", (NOW - 700,))
    conn.commit()
    conn.close()


@pytest.fixture
def home(tmp_path):
    make_kanban(tmp_path / "kanban.db")
    (tmp_path / "profiles" / "tars-sherlock").mkdir(parents=True)
    make_state_db(tmp_path / "profiles" / "tars-sherlock" / "state.db")
    return tmp_path


INDEX = """# Misje
## Aktywne
| ID | Tytuł | Status | Karty |
|---|---|---|---|
| M-260926-ziarno | Otwarcie Ziarno | w toku | t_a1, t_a2, t_a3, t_a6, t_dead |
## Zamknięte
| M-1 | x | zamknięta | t_a7 |
"""


def test_read_board_window_and_workers(home):
    board = core.read_board(home / "kanban.db", NOW)
    ids = {t["id"] for t in board["tasks"]}
    assert "t_a7" not in ids                     # zakończona 29 dni temu, poza oknem
    assert {"t_a1", "t_a2", "t_a3", "t_a6"} <= ids
    worker = {t["id"]: t["worker"] for t in board["tasks"]}
    assert worker["t_a1"] == "tars-sherlock" and worker["t_a2"] == "tars"
    assert board["events"][0]["payload"] == {} or isinstance(board["events"][0]["payload"], dict)


def test_missing_board_is_safe(tmp_path):
    assert core.read_board(tmp_path / "brak.db", NOW) == {"tasks": [], "events": [], "ok": False}


def test_build_state_statuses(home):
    board = core.read_board(home / "kanban.db", NOW)
    tool = {"tool": "web_search", "icon": "search", "verb": "szuka", "detail": "kawiarnie"}
    st = core.build_state(FLEET, board, INDEX, NOW, {"t_a1": tool})
    by = {a["name"]: a for a in st["agents"]}
    assert by["tars-sherlock"]["status"] == "working" and by["tars-sherlock"]["tool"] == tool
    assert by["tars"]["status"] == "working"                     # TARS właśnie ocenia t_a2 (run profilu tars)
    assert by["tars-web"]["status"] == "blocked"                # blokada ma pierwszeństwo przed oceną
    assert by["tars-studio"]["status"] == "blocked" and "12 czy 19" in by["tars-studio"]["reason"]
    assert by["tars-reka"]["status"] == "queued" and by["tars-reka"]["counts"]["done_today"] == 1
    assert st["board"]["blocked"] == 2 and st["board"]["ready"] == 2 and st["board"]["running"] == 1


def test_decisions_only_needs_input(home):
    st = core.build_state(FLEET, core.read_board(home / "kanban.db", NOW), INDEX, NOW)
    assert [d["task_id"] for d in st["decisions"]] == ["t_a3"]    # capability (t_a8) to nie decyzja właściciela
    assert st["decisions"][0]["reason"].startswith("Która data")


def test_missions_progress(home):
    st = core.build_state(FLEET, core.read_board(home / "kanban.db", NOW), INDEX, NOW)
    m = st["missions"][0]
    assert m["id"] == "M-260926-ziarno" and m["total"] == 5 and m["done"] == 1
    assert m["missing"] == ["t_dead"]
    assert len(st["missions"]) == 1                              # sekcja „Zamknięte” pominięta


def test_feed_is_recent_first_and_translated(home):
    st = core.build_state(FLEET, core.read_board(home / "kanban.db", NOW), INDEX, NOW)
    kinds = [f["kind"] for f in st["feed"]]
    assert "commented" not in kinds                              # szum pomijamy
    assert st["feed"][0]["ts"] >= st["feed"][-1]["ts"]
    blocked = next(f for f in st["feed"] if f["task_id"] == "t_a3")
    assert blocked["text"] == "zablokowana" and blocked["tone"] == "bad"


def test_judge_sees_review_queue(home):
    board = core.read_board(home / "kanban.db", NOW)
    cards = core.agent_cards("tars", board["tasks"], "tars")
    assert [c["id"] for c in cards["judging"]] == ["t_a2"]
    assert [c["id"] for c in cards["running"]] == ["t_a2"]
    web = core.agent_cards("tars-web", board["tasks"], "tars")
    assert [c["id"] for c in web["review"]] == ["t_a2"] and web["running"] == []


def test_heartbeat_quiet_flag(home):
    board = core.read_board(home / "kanban.db", NOW + 3600)
    cards = core.agent_cards("tars-sherlock", board["tasks"], "tars")
    assert core.derive_status("tars-sherlock", cards, NOW + 3600)["quiet"] is True


def test_session_activity(home):
    sid, msgs = core.read_session_messages(home / "profiles/tars-sherlock/state.db", "sess-sher")
    assert sid == "sess-sher" and all(m.get("content") != "stare" for m in msgs)   # nieaktywne pominięte
    items = core.activity_from_messages(msgs)
    kinds = [(i["kind"], i.get("tool"), i.get("status")) for i in items]
    assert kinds[0][0] == "brief"
    assert ("tool", "web_search", "done") in kinds
    assert ("tool", "web_extract", "error") in kinds             # „Error: …” = błąd narzędzia
    assert kinds[-1] == ("tool", "write_file", "running")        # ostatnie wywołanie jeszcze bez wyniku
    search = next(i for i in items if i.get("tool") == "web_search")
    assert search["verb"] == "szuka" and search["detail"] == "kawiarnie specialty Kraków"
    assert any(i["kind"] == "say" and "3 źródła" in i["text"] for i in items)


def test_session_lookup_by_start_time(home):
    sid, msgs = core.read_session_messages(home / "profiles/tars-sherlock/state.db", None, since=NOW - 601)
    assert sid == "sess-sher" and msgs


def test_tool_label_fallbacks():
    assert core.tool_label("kanban_foo_bar")["verb"] == "kanban: foo bar"
    assert core.tool_label("browser_scroll")["icon"] == "browser"
    long = core.tool_label("terminal", {"command": "x" * 500})
    assert len(long["detail"]) <= 140 and long["detail"].endswith("…")
    assert core.tool_label("web_search", "nie-json")["detail"] == "nie-json"


def test_safe_path_and_outputs(tmp_path):
    tars = tmp_path / "tars"
    out = tars / "workspaces" / "tars-web" / "out"
    out.mkdir(parents=True)
    (out / "hero.png").write_bytes(b"png")
    (out / "RAPORT.md").write_text("# r", encoding="utf-8")
    (tars / "workspaces" / "tars-web" / "node_modules").mkdir()
    (tars / "workspaces" / "tars-web" / "node_modules" / "x.js").write_text("", encoding="utf-8")
    secret = tmp_path / "profiles" / ".env"
    secret.parent.mkdir()
    secret.write_text("KEY=1", encoding="utf-8")
    link = out / "link.env"
    os.symlink(secret, link)
    roots = core.Roots(tars_dir=tars)

    assert core.safe_path(str(out / "hero.png"), roots) == (out / "hero.png").resolve()
    assert core.safe_path(str(out / ".." / ".." / ".." / ".." / "profiles" / ".env"), roots) is None
    assert core.safe_path(str(link), roots) is None              # symlink na zewnątrz nie przejdzie
    assert core.safe_path(str(tars / "workspaces"), roots) is None   # katalog to nie plik
    assert core.safe_path("", roots) is None

    files = core.list_outputs([tars / "workspaces" / "tars-web", tmp_path / "profiles"], roots)
    names = {f["name"] for f in files}
    assert {"hero.png", "RAPORT.md"} <= names and "x.js" not in names and ".env" not in names
    assert next(f for f in files if f["name"] == "hero.png")["kind"] == "image"


def test_agent_stats(home):
    board = core.read_board(home / "kanban.db", NOW)
    s = core.agent_stats("tars-reka", board["tasks"], board["events"], NOW)
    assert s == {"done_7d": 1, "first_pass_7d": 0, "changes_7d": 1}


def test_task_detail(home):
    t = core.read_task_detail(home / "kanban.db", "t_a1")
    assert t["title"] == "Research konkurencji" and t["comments"][0]["body"] == "Skup się na Kazimierzu"
    assert [e["kind"] for e in t["events"]][:2] == ["created", "spawned"]
    assert core.read_task_detail(home / "kanban.db", "t_nope") is None
    assert core.read_task_detail(home / "kanban.db", "t_a4")["parents"] == ["t_a3"]


def test_load_fleet(tmp_path):
    p = tmp_path / "fleet.json"
    p.write_text(json.dumps({"agents": [{"name": "tars"}, {"title": "bez nazwy"}]}), encoding="utf-8")
    assert core.load_fleet(p) == [{"name": "tars"}]
    assert core.load_fleet(tmp_path / "brak.json") == []


# ------------------------------------------------------------------ build pluginu

def test_hq_plugin_build(tmp_path):
    import shutil
    import subprocess
    import hqbuild

    dash = hqbuild.build_plugin(tmp_path / "tars-hq")
    for rel in ("manifest.json", "plugin_api.py", "hq_core.py", "fleet.json", "dist/index.js", "dist/style.css", "dist/LICENSE-htm"):
        assert (dash / rel).exists(), rel
    manifest = json.loads((dash / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "tars-hq" and manifest["api"] == "plugin_api.py" and manifest["tab"]["path"] == "/base" and manifest["tab"]["position"] == "before:chat"
    js = (dash / "dist" / "index.js").read_text(encoding="utf-8")
    for src in sorted((Path(hqbuild.HQ) / "web" / "src").glob("*.js")):
        assert f"// ---- {src.name}" in js
    assert "__HERMES_PLUGINS__.register(PLUGIN, App)" in js
    if shutil.which("node"):
        assert subprocess.run(["node", "--check", str(dash / "dist" / "index.js")], capture_output=True).returncode == 0
    fleet = json.loads((dash / "fleet.json").read_text(encoding="utf-8"))
    names = [a["name"] for a in fleet["agents"]]
    assert names[0] == fleet["orchestrator"] == "tars"
    tars = fleet["agents"][0]
    assert tars["room"] == "bridge" and tars["short"] == "TARS" and ["Szczerość", 90] in tars["personality"]
    assert all(a["model"].count("/") == 1 for a in fleet["agents"])


def test_hq_demo_build(tmp_path):
    import hqbuild
    out = hqbuild.build_demo(tmp_path / "demo")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert html.startswith('<meta charset="utf-8">') and "<title>TARS HQ</title>" in html[:400]
    assert "<html" not in html and "<body" not in html            # szkielet dodaje platforma artefaktów
    assert (out / "fleet.js").read_text(encoding="utf-8").startswith("window.TARS_HQ_FLEET = ")


def test_personality_parsing():
    import hqbuild
    assert hqbuild.personality("## Osobowość\nParametry: szczerość 90%, humor 60%, zwięzłość 85%. Reszta.") == \
        [["Szczerość", 90], ["Humor", 60], ["Zwięzłość", 85]]
    assert hqbuild.personality("## Osobowość\nSzczerość 95%, humor 30%. Chłodny.") == [["Szczerość", 95], ["Humor", 30]]
    assert hqbuild.personality("brak sekcji") == []


# ------------------------------------------------------------ helpery plugin_api

def test_plugin_api_helpers(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    api = load_script("hq/plugin/plugin_api.py", "tars_hq_plugin_api_test")
    assert api.session_id_from({"object": "hermes.session", "session": {"id": "api_1_x"}}) == "api_1_x"
    assert api.session_id_from({"id": "s2"}) == "s2" and api.session_id_from({}) is None
    msgs = api.chat_messages([
        {"role": "user", "content": "Zrób landing"},
        {"role": "assistant", "content": "", "tool_calls": json.dumps([{"function": {"name": "kanban_create", "arguments": "{\"title\": \"Landing\"}"}}])},
        {"role": "tool", "content": "ok"},
        {"role": "assistant", "content": "Założyłem kartę."},
        {"role": "user", "content": "ukryte", "display_kind": "hidden"},
    ])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["text"] == "Założyłem kartę." and msgs[1]["tools"][0]["verb"] == "zakłada kartę"
    env = tmp_path / "profiles" / "tars" / ".env"
    env.parent.mkdir(parents=True)
    env.write_text('# c\nAPI_SERVER_KEY="abc123abc123abc123"\nexport X=1\n', encoding="utf-8")
    base, key = api._api_target("tars")
    assert base.endswith("/p/tars") and key == "abc123abc123abc123"


# ------------------------------------------------------------ regresje z przeglądu

def test_judge_reads_own_session_not_implementers(home):
    board = core.read_board(home / "kanban.db", NOW)
    t = next(x for x in board["tasks"] if x["id"] == "t_a2")      # tars-web, ocenia tars
    assert core.worker_session(t) == (None, NOW - 60)              # szukamy sesji TARS-a od startu jego runu
    sher = next(x for x in board["tasks"] if x["id"] == "t_a1")
    assert core.worker_session(sher)[0] == "sess-sher"


def test_fallback_skips_chat_sessions(home):
    db = home / "profiles/tars-sherlock/state.db"
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO sessions VALUES ('chat-hq', 'api_server', ?)", (NOW - 10,))
    conn.commit(); conn.close()
    sid, _ = core.read_session_messages(db, None, since=NOW - 601)
    assert sid == "sess-sher"


def test_old_block_reason_and_old_mission_cards(home):
    conn = sqlite3.connect(home / "kanban.db")
    conn.execute("UPDATE task_events SET created_at = ? WHERE task_id = 't_a3'", (int(NOW) - 30 * 86400,))
    conn.commit(); conn.close()
    board = core.read_board(home / "kanban.db", NOW, extra_ids=["t_a7"])
    st = core.build_state(FLEET, board, INDEX.replace("t_a6, t_dead", "t_a6, t_a7"), NOW)
    assert st["decisions"][0]["reason"].startswith("Która data")
    m = st["missions"][0]
    assert m["missing"] == [] and m["done"] == 2                  # t_a7 zakończona 29 dni temu liczy się


def test_outputs_prune_heavy_dirs(tmp_path):
    tars = tmp_path / "tars"
    ws = tars / "workspaces" / "tars-web"
    (ws / "out").mkdir(parents=True)
    (ws / "out" / "a.png").write_bytes(b"x")
    nm = ws / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    for i in range(50):
        (nm / f"f{i}.js").write_text("", encoding="utf-8")
    files = core.list_outputs([ws], core.Roots(tars_dir=tars))
    assert [f["name"] for f in files] == ["a.png"]


def test_gave_up_card_is_a_failed_decision(home):
    import json, sqlite3
    conn = sqlite3.connect(home / "kanban.db")
    conn.execute("UPDATE tasks SET status = 'blocked', block_kind = NULL WHERE id = 't_a2'")
    conn.execute("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                 ("t_a2", "gave_up", json.dumps({"failures": 2, "error": "Traceback…\nError: Unknown skill(s): x"}), NOW - 5))
    conn.commit(); conn.close()
    st = core.build_state(FLEET, core.read_board(home / "kanban.db", NOW), INDEX, NOW)
    failed = [d for d in st["decisions"] if d.get("kind") == "failed"]
    assert [d["task_id"] for d in failed] == ["t_a2"]
    assert failed[0]["reason"] == "Error: Unknown skill(s): x" and failed[0]["failures"] == 2


# --------------------------------------------------------------------------- okno karty

ZIARNO_BRIEF = """CEL: Jednostronicowy landing HTML dla kawiarni „Ziarno”.
KONTEKST: „Ziarno” — specialty coffee w Krakowie, otwarcie 19.10.2026.
Ma działać offline jako pojedynczy plik.
WEJŚCIA: brand kit /opt/data/tars/knowledge/brands/ziarno/brand.md (nazwa, paleta).
DoD:
- pojedynczy plik index.html, poprawny HTML5,
- responsywny (poprawnie wygląda na mobile),
WYJŚCIA: out/index.html
GRANICE: autonomia A1 (bez publikacji/wdrożenia); budżet ~45 min; nie ruszać innych plików."""


def test_parse_brief_sections():
    b = core.parse_brief(ZIARNO_BRIEF)
    assert b["cel"] == "Jednostronicowy landing HTML dla kawiarni „Ziarno”."
    assert b["kontekst"].endswith("pojedynczy plik.") and "\n" in b["kontekst"]
    assert b["dod"].startswith("- pojedynczy plik index.html")
    assert b["wyjscia"] == "out/index.html" and b["granice"].startswith("autonomia A1")
    assert "intro" not in b
    # warianty z markdownem i bez polskich znaków
    b = core.parse_brief("Karta dla Studia.\n\n**CEL:** grafika 4:5\n**Wyjscia:** out/post.png, out/post-9x16.png")
    assert b == {"intro": "Karta dla Studia.", "cel": "grafika 4:5", "wyjscia": "out/post.png, out/post-9x16.png"}
    # zlecenie bez sekcji: GUI pokazuje je w całości
    assert core.parse_brief("Zrób research konkurencji.") == {}
    assert core.parse_brief(None) == {}


def test_expected_outputs_from_wyjscia():
    assert core.expected_outputs("out/index.html") == ["out/index.html"]
    assert core.expected_outputs("pliki w out/: raport.md (raport), out/dane.csv; out/raport.md") == \
        ["raport.md", "out/dane.csv", "out/raport.md"]
    assert core.expected_outputs("patrz https://ziarno.pl/menu.html") == []
    assert core.expected_outputs(None) == []


def test_task_outputs_marks_expected_file(tmp_path):
    tars = tmp_path / "tars"
    ws = tars / "missions" / "M-1" / "web"
    (ws / "out").mkdir(parents=True)
    (ws / "README.md").write_text("cel", encoding="utf-8")
    (ws / "out" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (ws / "out" / "shot-375.png").write_bytes(b"png")
    os.utime(ws / "out" / "index.html", (NOW - 600, NOW - 600))      # starszy niż zrzut, a i tak pierwszy
    files = core.task_outputs({"workspace_path": str(ws), "body": ZIARNO_BRIEF}, core.Roots(tars_dir=tars))
    assert files[0]["rel"] == "out/index.html" and files[0]["main"] and files[0]["kind"] == "html"
    assert [f["name"] for f in files[1:]] == ["shot-375.png", "README.md"]
    assert not any(f["main"] for f in files[1:])
    assert core.task_outputs({"workspace_path": None, "body": ZIARNO_BRIEF}, core.Roots(tars_dir=tars)) == []


def test_site_root_and_file(tmp_path):
    tars = tmp_path / "tars"
    roots = core.Roots(tars_dir=tars)
    ws = tars / "missions" / "M-1" / "web"
    (ws / "out" / "img").mkdir(parents=True)
    (ws / "out" / "index.html").write_text("<h1>x</h1>", encoding="utf-8")
    (ws / "out" / "img" / "logo.png").write_bytes(b"png")
    (ws / "out" / ".env").write_text("SECRET=1", encoding="utf-8")
    (ws / "site" / "dist" / "blog").mkdir(parents=True)
    (ws / "site" / "dist" / "blog" / "index.html").write_text("post", encoding="utf-8")
    (ws / "notes.html").write_text("n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s", encoding="utf-8")
    (ws / "out" / "leak").symlink_to(tmp_path / "secret.txt")

    root = core.site_root((ws / "out" / "index.html").resolve(), roots)
    assert root == (ws / "out").resolve()
    # zbudowany serwis: od najbliższego dist/, żeby działały ścieżki /assets/…
    assert core.site_root((ws / "site" / "dist" / "blog" / "index.html").resolve(), roots) == (ws / "site" / "dist").resolve()
    assert core.site_root((ws / "notes.html").resolve(), roots) == ws.resolve()

    assert core.site_file(root, "index.html", roots) == (ws / "out" / "index.html").resolve()
    assert core.site_file(root, "", roots) == (ws / "out" / "index.html").resolve()        # katalog → index.html
    assert core.site_file(root, "img/logo.png", roots) == (ws / "out" / "img" / "logo.png").resolve()
    assert core.site_file(root, "../notes.html", roots) is None                          # poza stroną
    assert core.site_file(root, ".env", roots) is None                                   # ukryte pliki
    assert core.site_file(root, "leak", roots) is None                                   # symlink na zewnątrz
    assert core.site_file(root, "img/..%2f..%2fnotes.html", roots) is None

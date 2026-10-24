"""Jarvo HQ: logika stanu floty na prawdziwych bazach SQLite w schemacie Hermesa."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import fleetlib as fl
from conftest import REPO, load_script

core = load_script("hq/plugin/hq_core.py", "jarvo_hq_core_test")

NOW = 1_800_000_000.0
MIN = 60

FLEET = [
    {"name": "jarvo", "kind": "orchestrator", "title": "Main Judge", "emoji": "🛰️", "room": "bridge", "short": "Jarvo"},
    {"name": "jarvo-sherlock", "kind": "specialist", "title": "Detektyw", "emoji": "🔎", "room": "study", "short": "Sherlock"},
    {"name": "jarvo-web", "kind": "specialist", "title": "Web", "emoji": "🌐", "room": "devlab", "short": "Web"},
    {"name": "jarvo-studio", "kind": "specialist", "title": "Studio", "emoji": "🎬", "room": "atelier", "short": "Studio"},
    {"name": "jarvo-reka", "kind": "generalist", "title": "Ręka", "emoji": "🦾", "room": "workshop", "short": "Ręka"},
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
        ("t_a1", "Research konkurencji", "jarvo-sherlock", "running", n - 3600, n - 600, None, n - 20, 1, "sess-sher", None, None),
        ("t_a2", "Landing Ziarno", "jarvo-web", "review", n - 3600, n - 1200, None, n - 400, 2, None, None, None),
        ("t_a3", "Grafiki IG", "jarvo-studio", "blocked", n - 3600, None, None, None, None, None, "needs_input", None),
        ("t_a4", "Film Reels", "jarvo-studio", "ready", n - 3600, None, None, None, None, None, None, None),
        ("t_a5", "Złożenie pakietu", "jarvo-reka", "todo", n - 3600, None, None, None, None, None, None, None),
        ("t_a6", "Cennik PDF", "jarvo-reka", "done", n - 9000, n - 8000, n - 7000, None, None, None, None, None),
        ("t_a7", "Stara karta", "jarvo-reka", "done", n - 30 * 86400, None, n - 29 * 86400, None, None, None, None, None),
        ("t_a8", "Dostęp do Cloudflare", "jarvo-web", "blocked", n - 3600, None, None, None, None, None, "capability", None),
    ]
    conn.executemany("""INSERT INTO tasks (id, title, assignee, status, created_at, started_at, completed_at,
        last_heartbeat_at, current_run_id, session_id, block_kind, workspace_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", tasks)
    conn.executemany("INSERT INTO task_runs (id, task_id, profile, status, started_at) VALUES (?,?,?,?,?)",
                     [(1, "t_a1", "jarvo-sherlock", "running", n - 600), (2, "t_a2", "jarvo", "running", n - 60)])
    events = [
        ("t_a1", "created", {}, n - 3600), ("t_a1", "spawned", {}, n - 600),
        ("t_a2", "review_requested", {"implementer": "jarvo-web"}, n - 400),
        ("t_a3", "blocked", {"kind": "needs_input", "reason": "Która data otwarcia: 12 czy 19?"}, n - 900),
        ("t_a8", "blocked", {"kind": "capability", "reason": "brak tokenu Cloudflare"}, n - 800),
        ("t_a6", "completed", {}, n - 7000), ("t_a6", "changes_requested", {}, n - 7500),
        ("t_a1", "commented", {}, n - 100),
    ]
    conn.executemany("INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                     [(t, k, json.dumps(p), c) for t, k, p, c in events])
    conn.execute("INSERT INTO task_comments (task_id, author, body, created_at) VALUES ('t_a1', 'jarvo', 'Skup się na Kazimierzu', ?)", (n - 100,))
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
    (tmp_path / "profiles" / "jarvo-sherlock").mkdir(parents=True)
    make_state_db(tmp_path / "profiles" / "jarvo-sherlock" / "state.db")
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
    assert worker["t_a1"] == "jarvo-sherlock" and worker["t_a2"] == "jarvo"
    assert board["events"][0]["payload"] == {} or isinstance(board["events"][0]["payload"], dict)


def test_missing_board_is_safe(tmp_path):
    assert core.read_board(tmp_path / "brak.db", NOW) == {"tasks": [], "events": [], "ok": False}


def test_build_state_statuses(home):
    board = core.read_board(home / "kanban.db", NOW)
    tool = {"tool": "web_search", "icon": "search", "verb": "szuka", "detail": "kawiarnie"}
    st = core.build_state(FLEET, board, INDEX, NOW, {"t_a1": tool})
    by = {a["name"]: a for a in st["agents"]}
    assert by["jarvo-sherlock"]["status"] == "working" and by["jarvo-sherlock"]["tool"] == tool
    assert by["jarvo"]["status"] == "working"                     # Jarvo właśnie ocenia t_a2 (run profilu jarvo)
    assert by["jarvo-web"]["status"] == "blocked"                # blokada ma pierwszeństwo przed oceną
    assert by["jarvo-studio"]["status"] == "blocked" and "12 czy 19" in by["jarvo-studio"]["reason"]
    assert by["jarvo-reka"]["status"] == "queued" and by["jarvo-reka"]["counts"]["done_today"] == 1
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
    cards = core.agent_cards("jarvo", board["tasks"], "jarvo")
    assert [c["id"] for c in cards["judging"]] == ["t_a2"]
    assert [c["id"] for c in cards["running"]] == ["t_a2"]
    web = core.agent_cards("jarvo-web", board["tasks"], "jarvo")
    assert [c["id"] for c in web["review"]] == ["t_a2"] and web["running"] == []


def test_heartbeat_quiet_flag(home):
    board = core.read_board(home / "kanban.db", NOW + 3600)
    cards = core.agent_cards("jarvo-sherlock", board["tasks"], "jarvo")
    assert core.derive_status("jarvo-sherlock", cards, NOW + 3600)["quiet"] is True


def test_session_activity(home):
    sid, msgs = core.read_session_messages(home / "profiles/jarvo-sherlock/state.db", "sess-sher")
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
    sid, msgs = core.read_session_messages(home / "profiles/jarvo-sherlock/state.db", None, since=NOW - 601)
    assert sid == "sess-sher" and msgs


def test_tool_label_fallbacks():
    assert core.tool_label("kanban_foo_bar")["verb"] == "kanban: foo bar"
    assert core.tool_label("browser_scroll")["icon"] == "browser"
    long = core.tool_label("terminal", {"command": "x" * 500})
    assert len(long["detail"]) <= 140 and long["detail"].endswith("…")
    assert core.tool_label("web_search", "nie-json")["detail"] == "nie-json"


def _wyniki_i_sekret(tmp_path):
    jarvo = tmp_path / "jarvo"
    out = jarvo / "workspaces" / "jarvo-web" / "out"
    out.mkdir(parents=True)
    (out / "hero.png").write_bytes(b"png")
    (out / "RAPORT.md").write_text("# r", encoding="utf-8")
    (jarvo / "workspaces" / "jarvo-web" / "node_modules").mkdir()
    (jarvo / "workspaces" / "jarvo-web" / "node_modules" / "x.js").write_text("", encoding="utf-8")
    secret = tmp_path / "profiles" / ".env"
    secret.parent.mkdir()
    secret.write_text("KEY=1", encoding="utf-8")
    return jarvo, out, secret


def test_safe_path_and_outputs(tmp_path):
    jarvo, out, _secret = _wyniki_i_sekret(tmp_path)
    roots = core.Roots(jarvo_dir=jarvo)

    assert core.safe_path(str(out / "hero.png"), roots) == (out / "hero.png").resolve()
    assert core.safe_path(str(out / ".." / ".." / ".." / ".." / "profiles" / ".env"), roots) is None
    assert core.safe_path(str(jarvo / "workspaces"), roots) is None   # katalog to nie plik
    assert core.safe_path("", roots) is None

    files = core.list_outputs([jarvo / "workspaces" / "jarvo-web", tmp_path / "profiles"], roots)
    names = {f["name"] for f in files}
    assert {"hero.png", "RAPORT.md"} <= names and "x.js" not in names and ".env" not in names
    hero = next(f for f in files if f["name"] == "hero.png")
    assert hero["kind"] == "image" and hero["rel"] == "out/hero.png"          # dla przeglądarki zawsze z „/”
    assert hero["path"] == (out / "hero.png").resolve().as_posix() and "\\" not in hero["path"]


@pytest.mark.wymaga_symlinku
def test_safe_path_symlink_na_zewnatrz(tmp_path):
    jarvo, out, secret = _wyniki_i_sekret(tmp_path)
    link = out / "link.env"
    os.symlink(secret, link)
    assert core.safe_path(str(link), core.Roots(jarvo_dir=jarvo)) is None    # symlink na zewnątrz nie przejdzie


def test_safe_path_alias_opt_data_i_git_bash(tmp_path):
    """Instalacja natywna: stare ścieżki /opt/data/… (rozmowy sprzed przejścia) wskazują pod faktyczny korzeń danych,
    a na korzeniu z literą dysku także zapis Git Bash /c/…; poza katalogi floty dalej nic nie wychodzi."""
    jarvo, out, _secret = _wyniki_i_sekret(tmp_path)
    roots = core.Roots(jarvo_dir=jarvo, korzen=tmp_path)
    hero = (out / "hero.png").resolve()
    assert core.safe_path("/opt/data/jarvo/workspaces/jarvo-web/out/hero.png", roots) == hero
    assert core.safe_path("/opt/data/profiles/.env", roots) is None
    assert core.safe_path("/opt/data/jarvo/workspaces/../../profiles/.env", roots) is None
    assert core.sciezki.na_dysk("/opt/data/jarvo/x", "/opt/data") == "/opt/data/jarvo/x"      # kontener: bez zmian
    assert core.sciezki.na_dysk("/c/Users/ja/x.png", "C:/Users/ja/dane") == "C:/Users/ja/x.png"
    assert core.sciezki.na_dysk("/c/Users/ja/x.png", "/home/ja/dane") == "/c/Users/ja/x.png"
    if os.name == "nt":
        msys = "/" + hero.drive[0].lower() + hero.as_posix()[2:]
        assert core.safe_path(msys, core.Roots(jarvo_dir=jarvo, korzen=tmp_path)) == hero


def test_agent_stats(home):
    board = core.read_board(home / "kanban.db", NOW)
    s = core.agent_stats("jarvo-reka", board, NOW)
    assert s == {"done_7d": 1, "first_pass_7d": 0, "changes_7d": 1}


def test_task_detail(home):
    t = core.read_task_detail(home / "kanban.db", "t_a1")
    assert t["title"] == "Research konkurencji" and t["comments"][0]["body"] == "Skup się na Kazimierzu"
    assert [e["kind"] for e in t["events"]][:2] == ["created", "spawned"]
    assert core.read_task_detail(home / "kanban.db", "t_nope") is None
    assert core.read_task_detail(home / "kanban.db", "t_a4")["parents"] == ["t_a3"]


def test_load_fleet(tmp_path):
    p = tmp_path / "fleet.json"
    p.write_text(json.dumps({"agents": [{"name": "jarvo"}, {"title": "bez nazwy"}]}), encoding="utf-8")
    assert core.load_fleet(p) == [{"name": "jarvo"}]
    assert core.load_fleet(tmp_path / "brak.json") == []


# ------------------------------------------------------------------ build pluginu

def test_hq_plugin_build(tmp_path):
    import shutil
    import subprocess
    import hqbuild

    dash = hqbuild.build_plugin(tmp_path / "jarvo-hq")
    for rel in ("manifest.json", "plugin_api.py", "hq_core.py", "ochrona.py", "animacja.py", "pomiar.py", "konwertuj.py", "fleet.json",
                "dist/index.js", "dist/LICENSE-htm", "dist/fonts/fosfor.css"):
        assert (dash / rel).exists(), rel
    assert not (dash / "dist" / "style.css").exists()        # style tylko na /jarvo, przez loader (zasoby/app-<h>.css)
    # figura floty: iso.py ze szablonem, licencją iso-glow i krojem OFL (bez przykładów)
    iso = dash / "izometria"
    for rel in ("scripts/iso.py", "scripts/iso_flota.js", "scripts/iso_jarvo.js", "assets/iso-glow/LICENSE",
                "assets/iso-glow/assets/gallery.html", *(f"scripts/kroje/{k}" for k in fl.ISO_KROJE)):
        assert (iso / rel).exists(), rel
    assert not (iso / "assets" / "przyklady").exists() and not list(iso.rglob("__pycache__"))
    manifest = json.loads((dash / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "jarvo-hq" and manifest["api"] == "plugin_api.py" and manifest["tab"]["path"] == "/jarvo" and manifest["tab"]["position"] == "before:chat"
    assert manifest["label"] == "Jarvo" and "css" not in manifest
    # dist/index.js to mały loader; pakiet aplikacji leży w zasoby/app-<hash>.js i wystawia window.__JARVO_APP__
    loader = (dash / "dist" / "index.js").read_text(encoding="utf-8")
    assert len(loader.encode("utf-8")) <= hqbuild.LOADER_MAX and '__HERMES_PLUGINS__.register("jarvo-hq", Jarvo)' in loader
    app = sorted((dash / "dist" / "zasoby").glob("app-*.js"))
    assert len(app) == 1 and app[0].name in loader
    js = app[0].read_text(encoding="utf-8")
    for src in sorted((Path(hqbuild.HQ) / "web" / "src").glob("*.js")):
        assert f"// ---- {src.name}" in js
    assert "window.__JARVO_APP__ = { App: AppJarvo, StaraBaza, wersja: 2 }" in js and "__HERMES_PLUGINS__.register(" not in js
    if shutil.which("node"):
        for f in (dash / "dist" / "index.js", app[0]):
            assert subprocess.run(["node", "--check", str(f)], capture_output=True).returncode == 0, f
    fleet = json.loads((dash / "fleet.json").read_text(encoding="utf-8"))
    names = [a["name"] for a in fleet["agents"]]
    assert names[0] == fleet["orchestrator"] == "jarvo"
    jarvo = fleet["agents"][0]
    assert jarvo["room"] == "bridge" and jarvo["short"] == "Jarvo" and ["Szczerość", 90] in jarvo["personality"]
    assert all(a["model"] for a in fleet["agents"])


def test_hq_demo_build(tmp_path):
    import hqbuild
    out = hqbuild.build_demo(tmp_path / "demo")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert html.startswith('<meta charset="utf-8">') and "<title>Jarvo HQ</title>" in html[:400]
    assert "<html" not in html and "<body" not in html            # szkielet dodaje platforma artefaktów
    assert (out / "fleet.js").read_text(encoding="utf-8").startswith("window.JARVO_HQ_FLEET = ")


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
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_test")
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
    env = tmp_path / "profiles" / "jarvo" / ".env"
    env.parent.mkdir(parents=True)
    env.write_text('# c\nAPI_SERVER_KEY="abc123abc123abc123"\nexport X=1\n', encoding="utf-8")
    base, key = api._api_target("jarvo")
    assert base.endswith("/p/jarvo") and key == "abc123abc123abc123"



def test_plugin_flota_strona(tmp_path, monkeypatch):
    """Centrala → Jak działa usługa: strona figury floty z fleet.json pluginu, przebudowana po zmianie floty."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import hqbuild
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_flota")
    plik = tmp_path / "fleet.json"
    fl.write_json(plik, hqbuild.fleet_json())
    strona = api.flota_strona(plik).decode("utf-8")
    assert "<title>Flota Jarvo</title>" in strona and '"nazwa": "Sherlock"' in strona and "fonts.googleapis" not in strona
    assert '"Jarvo"' in strona and api.flota_strona(plik) is api.flota_strona(plik)      # pamiętana
    dane = json.loads(plik.read_text(encoding="utf-8"))
    dane["agents"] = dane["agents"][:3]
    fl.write_json(plik, dane)
    import os
    os.utime(plik, ns=(1, 2))                                   # inna data pliku = inna flota
    assert '"nazwa": "Studio"' not in api.flota_strona(plik).decode("utf-8")


# ------------------------------------------------------------ regresje z przeglądu

def test_judge_reads_own_session_not_implementers(home):
    board = core.read_board(home / "kanban.db", NOW)
    t = next(x for x in board["tasks"] if x["id"] == "t_a2")      # jarvo-web, ocenia jarvo
    assert core.worker_session(t) == (None, NOW - 60)              # szukamy sesji Jarva od startu jego runu
    sher = next(x for x in board["tasks"] if x["id"] == "t_a1")
    assert core.worker_session(sher)[0] == "sess-sher"


def test_fallback_skips_chat_sessions(home):
    db = home / "profiles/jarvo-sherlock/state.db"
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
    jarvo = tmp_path / "jarvo"
    ws = jarvo / "workspaces" / "jarvo-web"
    (ws / "out").mkdir(parents=True)
    (ws / "out" / "a.png").write_bytes(b"x")
    nm = ws / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    for i in range(50):
        (nm / f"f{i}.js").write_text("", encoding="utf-8")
    files = core.list_outputs([ws], core.Roots(jarvo_dir=jarvo))
    assert [f["name"] for f in files] == ["a.png"]


def test_outputs_skip_mask_frames_next_to_film(tmp_path):
    """Sylwetki osoby (`<film>.maska/`, setki PNG) to dane edytora, nie wyniki: nie wypychają filmów z listy."""
    jarvo = tmp_path / "jarvo"
    out = jarvo / "workspaces" / "jarvo-wideo" / "out" / "typo"
    (out / "film.maska").mkdir(parents=True)
    (out / "film.mp4").write_bytes(b"x")
    for i in range(30):
        (out / "film.maska" / f"k{i:06d}.png").write_bytes(b"x")
    (out / "film.maska" / "indeks.json").write_text("{}", encoding="utf-8")
    files = core.list_outputs([jarvo / "workspaces" / "jarvo-wideo"], core.Roots(jarvo_dir=jarvo), limit=5)
    assert [f["name"] for f in files] == ["film.mp4"]


def test_outputs_scan_limit_stops_whole_walk(tmp_path, monkeypatch):
    """Po SCAN_MAX plików przejście kończy się całe: kolejne katalogi nie są już listowane."""
    jarvo = tmp_path / "jarvo"
    dirs = []
    for k in range(3):
        d = jarvo / "workspaces" / f"a{k}"
        for j in range(4):
            (d / f"s{j}").mkdir(parents=True, exist_ok=True)
            (d / f"s{j}" / "x.txt").write_text("x", encoding="utf-8")
        dirs.append(d)
    monkeypatch.setattr(core, "SCAN_MAX", 3)
    listed = []
    real_walk = os.walk
    monkeypatch.setattr(core.os, "walk", lambda d: ((listed.append(r), (r, s, n))[1] for r, s, n in real_walk(d)))
    files = core.list_outputs(dirs, core.Roots(jarvo_dir=jarvo))
    assert len(files) == 3 and len(listed) <= 5


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
WEJŚCIA: brand kit /opt/data/jarvo/knowledge/brands/ziarno/brand.md (nazwa, paleta).
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
    jarvo = tmp_path / "jarvo"
    ws = jarvo / "missions" / "M-1" / "web"
    (ws / "out").mkdir(parents=True)
    (ws / "README.md").write_text("cel", encoding="utf-8")
    (ws / "out" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (ws / "out" / "shot-375.png").write_bytes(b"png")
    os.utime(ws / "out" / "index.html", (NOW - 600, NOW - 600))      # starszy niż zrzut, a i tak pierwszy
    files = core.task_outputs({"workspace_path": str(ws), "body": ZIARNO_BRIEF}, core.Roots(jarvo_dir=jarvo))
    assert files[0]["rel"] == "out/index.html" and files[0]["main"] and files[0]["kind"] == "html"
    assert [f["name"] for f in files[1:]] == ["shot-375.png", "README.md"]
    assert not any(f["main"] for f in files[1:])
    assert core.task_outputs({"workspace_path": None, "body": ZIARNO_BRIEF}, core.Roots(jarvo_dir=jarvo)) == []


def _strona(tmp_path):
    jarvo = tmp_path / "jarvo"
    ws = jarvo / "missions" / "M-1" / "web"
    (ws / "out" / "img").mkdir(parents=True)
    (ws / "out" / "index.html").write_text("<h1>x</h1>", encoding="utf-8")
    (ws / "out" / "img" / "logo.png").write_bytes(b"png")
    (ws / "out" / ".env").write_text("SECRET=1", encoding="utf-8")
    (ws / "site" / "dist" / "blog").mkdir(parents=True)
    (ws / "site" / "dist" / "blog" / "index.html").write_text("post", encoding="utf-8")
    (ws / "notes.html").write_text("n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s", encoding="utf-8")
    return core.Roots(jarvo_dir=jarvo), ws


@pytest.mark.wymaga_symlinku
def test_site_file_symlink_na_zewnatrz(tmp_path):
    roots, ws = _strona(tmp_path)
    (ws / "out" / "leak").symlink_to(tmp_path / "secret.txt")
    root = core.site_root((ws / "out" / "index.html").resolve(), roots)
    assert core.site_file(root, "leak", roots) is None                                   # symlink na zewnątrz


def test_site_root_and_file(tmp_path):
    roots, ws = _strona(tmp_path)

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
    assert core.site_file(root, "img/..%2f..%2fnotes.html", roots) is None


# --------------------------------------------------------------------------- załączniki czatu

def test_upload_names_and_targets(tmp_path):
    assert core.safe_upload_name("zdjęcie z telefonu (1).JPG") == "zdjęcie_z_telefonu_1.jpg"
    assert core.safe_upload_name("../../profiles/.env") == "plik.env"      # bez katalogów i bez ukrycia
    assert core.safe_upload_name("C:\\Users\\ja\\Pulpit\\foto.png") == "foto.png"
    assert core.safe_upload_name("") == "plik"
    t1 = core.upload_target(tmp_path, "foto.png", NOW)
    assert t1.parent.parent == tmp_path and t1.name == "foto.png"
    t1.parent.mkdir(parents=True)
    t1.write_bytes(b"x")
    assert core.upload_target(tmp_path, "foto.png", NOW).name == "foto-2.png"


@pytest.mark.wymaga_symlinku
def test_upload_target_wiszace_dowiazanie_zajmuje_nazwe(tmp_path):
    t1 = core.upload_target(tmp_path, "foto.png", NOW)
    t1.parent.mkdir(parents=True)
    t1.write_bytes(b"x")
    (t1.parent / "foto-2.png").symlink_to(tmp_path / "nie-ma")              # wiszące dowiązanie też zajmuje nazwę
    assert core.upload_target(tmp_path, "foto.png", NOW).name == "foto-3.png"


def test_konwerter_katalog_zip_i_opcje(tmp_path):
    import zipfile
    kat = core.konwerter_katalog(tmp_path, NOW)
    assert kat.parent.parent == tmp_path and kat.name == "konwerter"         # inbox/<data>/konwerter (katalog podglądu)
    kat.mkdir(parents=True)
    (kat / "a").mkdir()
    pliki = [kat / "umowa-01.png", kat / "umowa-02.png", kat / "a" / "umowa-01.png", kat / "notatka.txt"]
    for p in pliki:
        p.write_bytes(b"x" * 100)
    z = core.spakuj(pliki, kat / "umowa-png.zip")
    with zipfile.ZipFile(z) as zz:
        assert zz.namelist() == ["umowa-01.png", "umowa-02.png", "umowa-01-2.png", "notatka.txt"]   # bez katalogów, bez zderzeń
        assert zz.getinfo("umowa-01.png").compress_type == zipfile.ZIP_STORED
        assert zz.getinfo("notatka.txt").compress_type == zipfile.ZIP_DEFLATED
    assert core.spakuj(pliki[:1], kat / "umowa-png.zip").name == "umowa-png-2.zip"        # istniejący ZIP zostaje
    assert core.konwerter_opcje({"jakosc": "75", "rozmiar": " 720p ", "strony": "", "dpi": 9999}) == \
        {"jakosc": 75, "rozmiar": "720p", "dpi": 600}
    assert core.konwerter_opcje({}) == {}
    for zle in ({"jakosc": 0}, {"jakosc": "dużo"}, {"rozmiar": "x" * 41}):
        with pytest.raises(ValueError):
            core.konwerter_opcje(zle)


def test_konwerter_bledy_bez_flag_cli():
    assert core.konwerter_blad("Złe --strony „abc”: np. 1-3,5 albo 4-") == "Złe strony „abc”: np. 1-3,5 albo 4-"
    assert core.konwerter_blad("Nie znam formatu „xyz”. Formaty: python3 konwertuj.py --formaty") == "Nie znam formatu „xyz”."
    assert core.konwerter_blad("Z PDF nie zrobisz Worda: sam tekst daje --na txt.") == "Z PDF nie zrobisz Worda: sam tekst daje format TXT."
    assert core.konwerter_blad("Żeby go zmniejszyć, podaj --rozmiar albo --jakosc.") == "Żeby go zmniejszyć, podaj rozmiar albo jakość."


def test_konwerter_w_hq():
    """Karta Konwerter w Centrali: te same trasy w pluginie i w przeglądarce, ten sam konwertuj.py co skill floty."""
    root = Path(__file__).resolve().parent.parent
    api = (root / "hq" / "plugin" / "plugin_api.py").read_text(encoding="utf-8")
    for route in ('"/konwerter/upload"', '"/konwerter/cele"', '"/konwerter"', '"/konwerter/job/{jid}"'):
        assert f"@router.{'get' if 'cele' in route or 'job' in route else 'post'}({route})" in api, route
    assert "core.KONWERTER_MAX" in api and "_konw.lock" in api and "core.safe_path" in api
    web = (root / "hq" / "web" / "src" / "10-api.js").read_text(encoding="utf-8")
    for call in ("/konwerter/upload", "/konwerter/cele?path=", "/konwerter`", "/konwerter/job/"):
        assert call in web, call
    assert "<${Konwerter} onOpenFile=${onOpenFile}/>" in (root / "hq" / "web" / "src" / "60-hud.js").read_text(encoding="utf-8")
    mock = (root / "hq" / "web" / "demo" / "mock.js").read_text(encoding="utf-8")
    assert all(f"{m}:" in mock for m in ("konwUpload", "konwCele", "konwStart", "konwJob"))
    # metadane: ostrzeżenie po wrzuceniu, przycisk „Usuń metadane”, raport co usunięto
    assert '"metadane": meta and meta["wrazliwe"]' in api and '"czysc": meta is not None' in api
    assert "k.usun_metadane(s, katalog=out_dir) if czysc" in api and "k.DOKUMENTY_META" in api
    assert '"removed": [' in api and '"uwagi": w.get("uwagi", [])' in api and "metadane, uwagi, czysc:" in mock
    karta = (root / "hq" / "web" / "src" / "55-konwerter.js").read_text(encoding="utf-8")
    assert "usun_metadane: true" in karta and "zadanie.removed" in karta and "f.czysc" in karta
    assert "konwUwagi(f.uwagi)" in karta and "konwUwagi(r.uwagi)" in karta   # komentarze w treści dokumentu
    import re
    from conftest import load_script
    blok = re.search(r"const KONW_META = bilingual\(\{(.*?)\}\);", karta, re.S)[1]
    wrazliwe = [k for k, _, _ in load_script("shared/skills/konwersja-plikow/scripts/konwertuj.py").WRAZLIWE]
    assert re.findall(r"(\w+): \[", blok) == wrazliwe          # te same kategorie w karcie i w konwerterze


def test_compose_message_and_user_text():
    msg = core.compose_message("Co tu jest?", ["/opt/data/jarvo/inbox/2026-09-28/foto.png"])
    assert msg.startswith("Co tu jest?\n\nZałączniki")
    assert msg.endswith("📎 /opt/data/jarvo/inbox/2026-09-28/foto.png")
    assert core.compose_message("  ", ["/a.png"]).startswith("(bez komentarza)")
    assert core.compose_message("sam tekst", []) == "sam tekst"
    # historia gatewaya: znaczniki obrazów znikają, gdy zdjęcia są w liniach 📎
    assert core.user_text(msg + "\n[screenshot]\n[screenshot]") == msg
    assert core.user_text("[screenshot]") == "[screenshot]"
    # treść jako lista części (tekst + obraz) albo jej zapis JSON
    parts = [{"type": "text", "text": "hej"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}]
    assert core.message_text(parts) == "hej"
    assert core.message_text(json.dumps(parts)) == "hej"
    assert core.message_text("[nie json") == "[nie json"


def test_preview_links_shared_file(tmp_path):
    links = tmp_path / "state" / "preview-links.json"
    site = tmp_path / "jarvo" / "missions" / "M-1" / "web" / "out"
    t1 = core.link_for(links, site, NOW)
    assert core.link_for(links, site, NOW + 3600) == t1                  # ten sam katalog → ten sam link
    assert core.link_root(links, t1, NOW + 60) == site
    assert core.link_root(links, t1, NOW + core.LINK_TTL + 1) is None   # wygasł
    assert core.link_root(links, "zly-token", NOW) is None
    t2 = core.link_for(links, site, NOW + core.LINK_TTL * 0.6)           # mniej niż pół terminu → nowy
    assert t2 != t1
    assert json.loads(links.read_text(encoding="utf-8"))[t1]["root"] == site.as_posix()   # katalog zawsze z „/”


# --------------------------------------------------------------------------- przenośne pomocniki (przenosne.py)
PRZENOSNE = REPO / "hq" / "plugin" / "przenosne.py"
DRUGI_PROCES = """import importlib.util, sys
spec = importlib.util.spec_from_file_location("p", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
try:
    with p.zamek(sys.argv[2], czekaj=False):
        print("wolna")
except BlockingIOError:
    print("zajeta")
"""


def test_zamek_miedzy_procesami_i_czekanie(tmp_path):
    """Blokada pliku linków (fcntl na POSIX, msvcrt na Windows): drugi proces nie wejdzie, póki pierwszy trzyma;
    `czekaj=True` czeka na zwolnienie, także w tym samym procesie (osobne otwarcie pliku)."""
    import threading
    import time
    plik = tmp_path / "linki.lock"

    def drugi() -> str:
        return subprocess.run([sys.executable, "-c", DRUGI_PROCES, str(PRZENOSNE), str(plik)], capture_output=True,
                              text=True, encoding="utf-8", timeout=60).stdout.strip()

    wejscie = []

    def watek():
        with core.przenosne.zamek(plik):
            wejscie.append(time.monotonic())

    with core.przenosne.zamek(plik):
        assert drugi() == "zajeta"
        w = threading.Thread(target=watek)
        start = time.monotonic()
        w.start()
        time.sleep(0.4)
        assert not wejscie                                                  # czeka
    w.join(10)
    assert wejscie and wejscie[0] - start >= 0.3
    assert plik.exists()


def test_zastap_czeka_na_czytajacego(tmp_path):
    """Zapis atomowy (plik linków, .env): na Windows plik otwarty właśnie do czytania nie da się podmienić
    (WinError 5/32), więc `zastap` ponawia, aż czytający go zamknie; na POSIX podmiana idzie od razu."""
    import threading
    cel, nowy = tmp_path / "preview-links.json", tmp_path / "preview-links.tmp"
    cel.write_text("stary", encoding="utf-8")
    nowy.write_text("nowy", encoding="utf-8")
    czytany = open(cel, "rb")
    threading.Timer(0.3, czytany.close).start()
    core.przenosne.zastap(nowy, cel)
    czytany.close()
    assert cel.read_text(encoding="utf-8") == "nowy" and not nowy.exists()


def test_uruchom_w_watku_wynik_linie_limit_i_anulowanie():
    """Podprocesy tras w wątkach (dashboard na Windows nie ma podprocesów asyncio): kod i wyjście, stdout linia po
    linii, limit czasu zabija program i kończy się asyncio.TimeoutError, anulowane zadanie też zabija program."""
    import asyncio
    import time
    p = core.przenosne
    kod, out, err = asyncio.run(p.uruchom([sys.executable, "-c", "import sys; print('ok'); print('blad', file=sys.stderr); sys.exit(3)"]))
    assert (kod, out.strip(), err.strip()) == (3, b"ok", b"blad")
    petla = asyncio.SelectorEventLoop()         # pętla dashboardu Hermesa na Windows: tam asyncio nie ma podprocesów
    try:
        assert petla.run_until_complete(p.uruchom([sys.executable, "-c", "print('selektor')"]))[1].strip() == b"selektor"
    finally:
        petla.close()
    linie = []
    kod, out, err = asyncio.run(p.uruchom([sys.executable, "-c", "print('a'); print('b'); print('c')"], na_linie=linie.append))
    assert kod == 0 and out == b"" and [x.strip() for x in linie] == [b"a", b"b", b"c"]
    kod, out, _ = asyncio.run(p.uruchom([sys.executable, "-c", "import sys; print('x', file=sys.stderr)"], stderr=p.STDOUT))
    assert kod == 0 and out.strip() == b"x"

    procesy = []
    start = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(p.uruchom([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.5, przy_starcie=procesy.append))
    assert time.monotonic() - start < 30 and procesy[0].poll() is not None    # zabity i skończony przed wyjątkiem

    async def anuluj():
        zadanie = asyncio.create_task(p.uruchom([sys.executable, "-c", "import time; time.sleep(60)"],
                                                przy_starcie=procesy.append))
        await asyncio.sleep(0.5)
        zadanie.cancel()
        with pytest.raises(asyncio.CancelledError):
            await zadanie
    asyncio.run(anuluj())
    assert procesy[1].wait(timeout=30) is not None
    with pytest.raises(OSError):                                            # brak programu: od razu, jak przy asyncio
        asyncio.run(p.uruchom([str(Path(sys.executable).with_name("nie-ma-takiego-programu"))]))


def test_tryb_pliku_tylko_dla_wlasciciela(tmp_path):
    """Sekret (.env, rozmowy.db, dziennik HQ): na POSIX chmod 0600; na Windows ACL bez wpisów dziedziczonych
    i z pełnym dostępem właściciela (icacls), bo os.chmod ustawia tam tylko „tylko do odczytu”."""
    p = core.przenosne
    katalog = tmp_path / "sekrety"
    katalog.mkdir()
    if os.name == "nt":           # wpis dziedziczony dla Wszystkich: plik w katalogu go dostaje, ochrona ma go zdjąć
        r = subprocess.run([p._system32("icacls.exe"), str(katalog), "/grant", "*S-1-1-0:(OI)(CI)R"], capture_output=True)
        assert r.returncode == 0, r.stdout
    plik = katalog / ".env"
    plik.write_text("KLUCZ=x\n", encoding="utf-8")
    os.chmod(plik, 0o644)
    assert not p.tylko_dla_wlasciciela(plik)
    assert p.tryb_pliku(plik, 0o600) and p.tylko_dla_wlasciciela(plik)
    assert plik.read_text(encoding="utf-8") == "KLUCZ=x\n"                 # właściciel dalej czyta i pisze
    plik.write_text("KLUCZ=y\n", encoding="utf-8")
    if os.name != "nt":
        assert stat.S_IMODE(plik.stat().st_mode) == 0o600
    jawny = katalog / "stan.json"                                           # tryb z prawami innych: bez ACL
    jawny.write_text("{}", encoding="utf-8")
    assert p.tryb_pliku(jawny, 0o644) and not p.tylko_dla_wlasciciela(jawny)


# --------------------------------------------------------------------------- ścieżki danych (sciezki.py)
WIN = "C:/Users/Michał Żółć/AppData/Local/Jarvo/dane"


def test_sciezki_wzorzec_alias_i_korzen_natywny():
    """Ścieżki danych w tekście: /opt/data zawsze (stare rozmowy), korzeń natywny z literą dysku (dowolna wielkość,
    „\\” i „/”, Git Bash), spacje tylko w korzeniu; w kontenerze (korzeń = alias) to samo wyrażenie co dawniej."""
    s = core.sciezki
    reszta = r"[^\s,;\"'<>()\[\]{}]+"
    assert s.wzorzec(reszta, "/opt/data").pattern == f"(?:/opt/data/{reszta})"
    assert s.wzorzec(reszta, None).pattern == s.wzorzec(reszta, "/opt/data/").pattern
    w = s.wzorzec(reszta, WIN.replace("/", "\\"))
    tekst = (f"zapisane: {WIN}/jarvo/workspaces/web/a.html, c:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\jarvo\\inbox\\b.png "
             "i /c/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/missions/M-1/RAPORT.md; stare /opt/data/jarvo/x.txt "
             "obok D:/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/c.png i C:/Users/Michał/d.png")
    assert w.findall(tekst) == [f"{WIN}/jarvo/workspaces/web/a.html",
                                "c:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\jarvo\\inbox\\b.png",
                                "/c/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/missions/M-1/RAPORT.md",
                                "/opt/data/jarvo/x.txt"]
    posix = s.wzorzec(reszta, "/home/ola/.jarvo/dane")                     # macOS i Linux: separator tylko „/”
    assert posix.findall("/home/ola/.jarvo/dane/jarvo/a.png i /home/ola/.jarvo/dane\\jarvo\\b.png") == [
        "/home/ola/.jarvo/dane/jarvo/a.png"]
    assert s.korzen_danych("/x/dane/profiles/jarvo-web") == Path("/x/dane") and s.jako_tekst("C:\\x\\dane\\") == "C:/x/dane"
    assert s.na_dysk("/opt/data/jarvo/inbox/a.png", WIN) == f"{WIN}/jarvo/inbox/a.png"
    assert s.na_dysk("/opt/database/x", WIN) == "/opt/database/x" and s.na_dysk("C:/x", WIN) == "C:/x"


def test_update_state_stalled_when_helper_silent(tmp_path, monkeypatch):
    """Pomocnik zniknął w trakcie aktualizacji: panel pokazuje „utknęła”, nie wieczne „aktualizuję”."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import time
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_upd")
    upd = tmp_path / "update.json"
    monkeypatch.setattr(api, "UPDATE_FILE", upd)
    monkeypatch.setattr(api, "UPDATE_REQUEST", tmp_path / "update-request")
    now = time.time()
    upd.write_text(json.dumps({"state": "updating", "started_at": now - 1800, "beat": now - 20}), encoding="utf-8")
    assert api._update_state()["state"] == "updating"          # znak życia świeży: trwa
    upd.write_text(json.dumps({"state": "updating", "started_at": now - 1800}), encoding="utf-8")
    st = api._update_state()
    assert st["state"] == "stalled" and not st["online"] and st["silent_for"] >= 1800
    upd.write_text(json.dumps({"state": "idle", "checked_at": now - 3600}), encoding="utf-8")
    (tmp_path / "update-request").write_text("update", encoding="utf-8")
    assert api._update_state()["state"] == "stalled"           # prośba czeka na nieobecnego pomocnika


def test_update_gdy_wolne_i_praca(tmp_path, monkeypatch):
    """POST /update `{action, gdy}` (docs/HQ.md „Aktualizacja”): stan ma pracę floty z praca.json, `gdy: wolne` bez
    silnika = 503 `silnik`, zła treść = 422/400 w kształcie `blad`, `cancel` zawsze 200, zwykłe `update` pisze prośbę."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import time
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("JARVO_HQ_SILNIK", "0")
    api = load_script("hq/plugin/plugin_api.py", "jarvo_hq_plugin_api_upd_gdy")
    upd, req, praca = tmp_path / "update.json", tmp_path / "update-request", tmp_path / "praca.json"
    monkeypatch.setattr(api, "UPDATE_FILE", upd)
    monkeypatch.setattr(api, "UPDATE_REQUEST", req)
    monkeypatch.setattr(api, "PRACA_FILE", praca)
    now = time.time()
    praca.write_text(json.dumps({"aktywne": 2, "opis": ["Web: karta „Stopka”", "Studio: rozmowa"], "at": now}))
    upd.write_text(json.dumps({"state": "behind", "behind": 3, "checked_at": now - 10}), encoding="utf-8")
    st = api._update_state()
    assert st["praca"] == {"aktywne": 2, "opis": ["Web: karta „Stopka”", "Studio: rozmowa"]} and st["po_pracy"] is None
    praca.write_text(json.dumps({"aktywne": 2, "opis": [], "at": now - 600}))
    assert api._update_state()["praca"]["aktywne"] == 0                      # stary plik = brak wiedzy o pracy
    app = FastAPI()
    app.include_router(api.router, prefix="/api/plugins/jarvo-hq")
    k = TestClient(app, headers={"X-Jarvo-Request": "1"})
    u = "/api/plugins/jarvo-hq/update"
    assert k.post(u, json={"action": "update", "gdy": "wolne"}).json()["blad"]["kod"] == "silnik"
    assert not req.exists()
    assert k.post(u, json={"action": "x"}).status_code == 400
    r = k.post(u, content=b"[1]", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["blad"]["kod"] == "zle_dane"
    assert k.post(u, json={"action": "cancel"}).status_code == 200
    r = k.post(u, json={"action": "update"})
    assert r.status_code == 202 and req.read_text() == "update"
    upd.write_text(json.dumps({"state": "updating", "beat": time.time()}), encoding="utf-8")
    r = k.post(u, json={"action": "update"})
    assert r.status_code == 409 and r.json()["detail"] == "Aktualizacja już trwa."
    upd.write_text(json.dumps({"state": "idle", "checked_at": now - 3600}), encoding="utf-8")
    assert k.post(u, json={"action": "check"}).json()["blad"]["kod"] == "pomocnik"


# scripts/updater.py to pomocnik hosta instalacji z Dockerem (deploy.sh w bashu, grupa procesów): kod tylko kontenerowy
@pytest.mark.posix_only
def test_updater_heartbeat_and_timeout(tmp_path, monkeypatch):
    up = load_script("scripts/updater.py", "jarvo_updater_test")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "deploy.sh").write_text("echo start; sleep 30; echo koniec\n")
    writes = []
    monkeypatch.setattr(up, "ROOT", tmp_path)
    monkeypatch.setattr(up, "put_state", lambda s: writes.append(dict(s)) or True)
    monkeypatch.setattr(up, "check", lambda s: dict(s))
    monkeypatch.setattr(up, "UPDATE_TIMEOUT", 1)
    real_event = up.threading.Event
    class Fast(real_event):
        def wait(self, timeout=None):
            return super().wait(min(timeout or 0, 0.3))
    monkeypatch.setattr(up.threading, "Event", Fast)
    args = type("A", (), {"compose": None, "build": None})()
    t0 = __import__("time").time()
    final = up.update(args, {"state": "idle"})
    assert __import__("time").time() - t0 < 15                 # zawieszony deploy przerwany
    assert final["state"] == "failed" and "Przerwano" in final["log"]
    assert any(w.get("beat") for w in writes)                    # znak życia bez nowych linii logu
    assert writes[-1]["state"] == "failed"                       # ostatni zapis to wynik, nie „updating”

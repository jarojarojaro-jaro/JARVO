"""TARS HQ: logika stanu floty dla GUI (bez FastAPI i bez importów Hermesa, więc da się ją testować).

Źródła danych (wszystko tylko do odczytu):
  - tablica kanban: $HERMES_HOME/kanban.db (SQLite, tryb ro),
  - transkrypcje pracowników: $HERMES_HOME/profiles/<agent>/state.db (SQLite, tryb ro),
  - dziennik misji: /opt/data/tars/missions/INDEX.md,
  - wyniki: katalogi robocze kart (tasks.workspace_path) i /opt/data/tars/workspaces/<agent>/.

Zapisów tu nie ma. Rozmowy idą przez API gatewaya (plugin_api.py), decyzje przez TARS-a.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
TARS_DIR = Path(os.environ.get("TARS_DATA_DIR", str(HOME / "tars")))
MISSIONS_INDEX = Path(os.environ.get("TARS_MISSIONS_DIR", str(TARS_DIR / "missions"))) / "INDEX.md"

OPEN = {"triage", "todo", "ready", "running", "blocked", "review", "scheduled"}
HEARTBEAT_STALE_S = 180          # pracownik bez sygnału dłużej niż 3 min = „cisza”
FEED_LIMIT = 40
ACTIVITY_LIMIT = 40
OUTPUT_LIMIT = 60

# Pliki, które GUI może pokazać (podgląd wyników agentów). Wszystko inne jest poza zasięgiem.
PREVIEW_ROOTS = ("workspaces", "missions", "knowledge", "inbox")   # inbox: pliki wysłane w czacie HQ

KIND_BY_EXT = {
    **{e: "image" for e in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg")},
    **{e: "video" for e in (".mp4", ".webm", ".mov")},
    ".pdf": "pdf", ".md": "text", ".txt": "text", ".csv": "text", ".json": "text", ".srt": "text",
    ".html": "html", ".htm": "html", ".zip": "archive", ".docx": "doc", ".xlsx": "doc", ".pptx": "doc",
}


# ----------------------------------------------------------------------------- fleet

def load_fleet(path: Path) -> list[dict]:
    """fleet.json generowany przez scripts/build.py (kolejność = kolejność we fleet.yaml)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [a for a in data.get("agents", []) if a.get("name")]


# ------------------------------------------------------------------------- sqlite

def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw) if raw else {}
        return val if isinstance(val, dict) else {"value": val}
    except (TypeError, ValueError):
        return {"text": str(raw)}


TASK_COLS = ("id", "title", "body", "assignee", "status", "priority", "created_at", "started_at",
             "completed_at", "workspace_path", "result", "last_heartbeat_at", "current_run_id",
             "session_id", "block_kind", "skills", "last_failure_error")


def read_board(db_path: Path, now: float, window_s: int = 7 * 86400, extra_ids: Iterable[str] = ()) -> dict:
    """Karty otwarte + zakończone w oknie czasu (+ extra_ids, np. karty misji), zdarzenia, profil
    i start bieżącego runu, ostatnia blokada każdej zablokowanej karty (bez względu na wiek)."""
    conn = _connect_ro(db_path)
    if conn is None:
        return {"tasks": [], "events": [], "ok": False}
    try:
        cols = _columns(conn, "tasks")
        sel = ", ".join(c for c in TASK_COLS if c in cols)
        since = int(now - window_s)
        rows = conn.execute(
            f"SELECT {sel} FROM tasks WHERE status IN ({','.join('?' * len(OPEN))}) "
            f"OR COALESCE(completed_at, created_at) >= ?", (*OPEN, since)).fetchall()
        tasks = [dict(r) for r in rows]
        have = {t["id"] for t in tasks}
        extra = [i for i in dict.fromkeys(extra_ids) if i not in have]
        if extra:
            q = f"SELECT {sel} FROM tasks WHERE id IN ({','.join('?' * len(extra))})"
            tasks += [dict(r) for r in conn.execute(q, extra)]
        runs: dict[int, dict] = {}
        run_ids = [t["current_run_id"] for t in tasks if t.get("current_run_id")]
        if run_ids and "task_runs" in _tables(conn):
            q = f"SELECT id, profile, started_at FROM task_runs WHERE id IN ({','.join('?' * len(run_ids))})"
            runs = {r["id"]: dict(r) for r in conn.execute(q, run_ids)}
        for t in tasks:
            run = runs.get(t.get("current_run_id")) or {}
            t["worker"] = run.get("profile") or None
            t["run_started_at"] = run.get("started_at")
        events = [dict(r) for r in conn.execute(
            "SELECT task_id, kind, payload, created_at FROM task_events WHERE created_at >= ? "
            "ORDER BY created_at DESC, id DESC LIMIT 400", (since,))]
        blocked = [t["id"] for t in tasks if t.get("status") == "blocked"]
        if blocked:
            seen_blocked = {e["task_id"] for e in events if e["kind"] == "blocked"}
            missing = [b for b in blocked if b not in seen_blocked]
            for tid in missing:
                row = conn.execute("SELECT task_id, kind, payload, created_at FROM task_events WHERE task_id = ? "
                                   "AND kind = 'blocked' ORDER BY created_at DESC, id DESC LIMIT 1", (tid,)).fetchone()
                if row:
                    events.append(dict(row))
        for e in events:
            e["payload"] = _payload(e.get("payload"))
        return {"tasks": tasks, "events": events, "ok": True}
    finally:
        conn.close()


def read_task_detail(db_path: Path, task_id: str) -> dict | None:
    conn = _connect_ro(db_path)
    if conn is None:
        return None
    try:
        cols = _columns(conn, "tasks")
        sel = ", ".join(c for c in TASK_COLS if c in cols)
        row = conn.execute(f"SELECT {sel} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        task = dict(row)
        task["events"] = [{**dict(r), "payload": _payload(r["payload"])} for r in conn.execute(
            "SELECT kind, payload, created_at FROM task_events WHERE task_id = ? ORDER BY created_at, id", (task_id,))]
        if "task_comments" in _tables(conn):
            task["comments"] = [dict(r) for r in conn.execute(
                "SELECT author, body, created_at FROM task_comments WHERE task_id = ? ORDER BY created_at, id",
                (task_id,))]
        parents = conn.execute("SELECT parent_id FROM task_links WHERE child_id = ?", (task_id,)).fetchall() \
            if "task_links" in _tables(conn) else []
        task["parents"] = [r["parent_id"] for r in parents]
        return task
    finally:
        conn.close()


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


# ------------------------------------------------------------------------ activity

TOOL_LABELS = {
    # nazwa narzędzia → (ikona, czasownik); ikony mapuje frontend
    "web_search": ("search", "szuka"), "web_extract": ("page", "czyta stronę"), "web_crawl": ("page", "przegląda stronę"),
    "terminal": ("terminal", "terminal"), "execute_code": ("terminal", "liczy w Pythonie"),
    "read_file": ("file", "czyta"), "write_file": ("write", "pisze"), "patch": ("write", "poprawia"),
    "search_files": ("search", "przeszukuje pliki"),
    "browser_navigate": ("browser", "otwiera"), "browser_snapshot": ("browser", "ogląda stronę"),
    "browser_click": ("browser", "klika"), "browser_type": ("browser", "wpisuje"), "browser_vision": ("eye", "patrzy na stronę"),
    "vision_analyze": ("eye", "ogląda obraz"), "image_generate": ("image", "generuje obraz"), "video_generate": ("video", "generuje wideo"),
    "text_to_speech": ("audio", "nagrywa głos"),
    "skill_view": ("book", "czyta skill"), "skills_list": ("book", "przegląda skille"),
    "memory": ("memory", "zapisuje w pamięci"), "session_search": ("memory", "szuka w historii"),
    "todo": ("check", "planuje kroki"), "clarify": ("question", "dopytuje"),
    "delegate_task": ("team", "deleguje podzadanie"),
    "kanban_create": ("card", "zakłada kartę"), "kanban_comment": ("card", "komentuje kartę"),
    "kanban_complete": ("done", "zamyka kartę"), "kanban_block": ("block", "blokuje kartę"),
    "kanban_request_review": ("review", "oddaje do oceny"), "kanban_request_changes": ("review", "odsyła do poprawki"),
    "kanban_list": ("card", "przegląda tablicę"), "kanban_show": ("card", "czyta kartę"),
    "cronjob": ("clock", "ustawia rutynę"),
}


# te same czasowniki po angielsku (HQ po angielsku, gdy dashboard ma inny język niż polski)
TOOL_VERBS_EN = {
    "web_search": "searching", "web_extract": "reading page", "web_crawl": "browsing site", "terminal": "terminal",
    "execute_code": "running Python", "read_file": "reading", "write_file": "writing", "patch": "editing",
    "search_files": "searching files", "browser_navigate": "opening", "browser_snapshot": "viewing page",
    "browser_click": "clicking", "browser_type": "typing", "browser_vision": "looking at page",
    "vision_analyze": "looking at image", "image_generate": "generating image", "video_generate": "generating video",
    "text_to_speech": "recording voice", "skill_view": "reading skill", "skills_list": "browsing skills",
    "memory": "saving to memory", "session_search": "searching history", "todo": "planning steps", "clarify": "asking",
    "delegate_task": "delegating subtask", "kanban_create": "creating card", "kanban_comment": "commenting on card",
    "kanban_complete": "closing card", "kanban_block": "blocking card", "kanban_request_review": "sending for review",
    "kanban_request_changes": "requesting changes", "kanban_list": "checking the board", "kanban_show": "reading card",
    "cronjob": "setting a routine",
}


def tool_label(name: str | None, args: Any = None) -> dict:
    """Czytelny opis wywołania narzędzia: ikona, czasownik i krótki szczegół z argumentów."""
    name = name or "?"
    icon, verb = TOOL_LABELS.get(name, ("tool", name.replace("_", " ")))
    verb_en = TOOL_VERBS_EN.get(name, name.replace("_", " "))
    if name.startswith("kanban_") and name not in TOOL_LABELS:
        icon, verb = "card", "kanban: " + name[7:].replace("_", " ")
        verb_en = verb
    if name.startswith("browser_") and name not in TOOL_LABELS:
        icon = "browser"
    args = _payload(args) if not isinstance(args, dict) else args
    detail = ""
    for key in ("query", "url", "path", "command", "code", "prompt", "title", "name", "summary", "reason", "goal", "text"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            detail = " ".join(val.split())
            break
    if len(detail) > 140:
        detail = detail[:137] + "…"
    return {"tool": name, "icon": icon, "verb": verb, "verb_en": verb_en, "detail": detail}


def activity_from_messages(messages: Iterable[dict], limit: int = ACTIVITY_LIMIT) -> list[dict]:
    """Wiadomości sesji (format Hermesa/OpenAI) → oś zdarzeń „co agent robi” (najnowsze na końcu)."""
    items: list[dict] = []
    pending: dict[str, dict] = {}
    for m in messages:
        role = m.get("role")
        ts = m.get("timestamp")
        if role == "assistant":
            calls = m.get("tool_calls")
            if isinstance(calls, str):
                try:
                    calls = json.loads(calls)
                except ValueError:
                    calls = []
            text = (m.get("content") or "").strip() if isinstance(m.get("content"), str) else ""
            if text:
                items.append({"ts": ts, "kind": "say", "text": _clip(text, 600)})
            for c in calls or []:
                fn = c.get("function") or {}
                item = {"ts": ts, "kind": "tool", **tool_label(fn.get("name") or c.get("name"), fn.get("arguments")),
                        "status": "running"}
                items.append(item)
                if c.get("id"):
                    pending[c["id"]] = item
        elif role == "tool":
            item = pending.get(m.get("tool_call_id") or "")
            content = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
            failed = bool(re.match(r'^\s*(\{"error"|error:|BLOCKED:)', content or "", re.I))
            if item is not None:
                item["status"] = "error" if failed else "done"
                item["result"] = _clip(content or "", 240)
            else:
                items.append({"ts": ts, "kind": "tool", **tool_label(m.get("tool_name")),
                              "status": "error" if failed else "done", "result": _clip(content or "", 240)})
        elif role == "user" and isinstance(m.get("content"), str) and m.get("display_kind") != "hidden":
            items.append({"ts": ts, "kind": "brief", "text": _clip(m["content"], 400)})
    return items[-limit:]


def _clip(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def read_session_messages(state_db: Path, session_id: str | None, since: float | None = None,
                          limit: int = 120) -> tuple[str | None, list[dict]]:
    """Ostatnie wiadomości sesji pracownika. Bez session_id: najnowsza sesja rozpoczęta po `since`."""
    conn = _connect_ro(state_db)
    if conn is None:
        return None, []
    try:
        tables = _tables(conn)
        if "messages" not in tables:
            return None, []
        if not session_id and "sessions" in tables and since:
            scols = _columns(conn, "sessions")
            if "started_at" in scols:
                # tylko sesje pracowników: bez rozmów (API/HQ, Telegram) i rutyn crona
                src = " AND COALESCE(source, '') NOT IN ('api_server', 'tars-hq', 'telegram', 'cron')" \
                    if "source" in scols else ""
                row = conn.execute(f"SELECT id FROM sessions WHERE started_at >= ?{src} ORDER BY started_at DESC LIMIT 1",
                                   (since - 5,)).fetchone()
                session_id = row["id"] if row else None
        if not session_id:
            return None, []
        mcols = _columns(conn, "messages")
        want = [c for c in ("role", "content", "tool_calls", "tool_call_id", "tool_name", "timestamp", "display_kind")
                if c in mcols]
        where = "session_id = ?" + (" AND active = 1" if "active" in mcols else "")
        rows = conn.execute(f"SELECT {', '.join(want)} FROM messages WHERE {where} ORDER BY id DESC LIMIT ?",
                            (session_id, limit)).fetchall()
        return session_id, [dict(r) for r in reversed(rows)]
    except sqlite3.Error:
        return session_id, []
    finally:
        conn.close()


# -------------------------------------------------------------------------- missions

_ROW = re.compile(r"^\|\s*(?P<id>[MZ]-[^|]+?)\s*\|(?P<rest>.*)\|\s*$")


def parse_missions(index_md: str) -> list[dict]:
    """Wiersze sekcji „## Aktywne” dziennika misji (ten sam format co patrol TARS-a)."""
    rows, section = [], None
    for line in index_md.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section != "aktywne":
            continue
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group("rest").split("|")]
        rows.append({"id": m.group("id").strip(), "title": cells[0] if cells else "",
                     "status": cells[1] if len(cells) > 1 else "",
                     "cards": re.findall(r"t_[0-9a-f]+", cells[2]) if len(cells) > 2 else []})
    return rows


# ----------------------------------------------------------------------------- state

EVENT_TEXT = {
    "created": "nowa karta", "promoted": "gotowa do pracy", "promoted_manual": "gotowa do pracy",
    "claimed": "bierze kartę", "spawned": "zaczyna pracę", "completed": "zakończył kartę",
    "blocked": "zablokowana", "unblocked": "odblokowana", "review_requested": "oddaje do oceny",
    "changes_requested": "odesłana do poprawki", "commented": "komentarz", "archived": "zarchiwizowana",
    "timed_out": "przekroczony czas", "gave_up": "porzucona po błędach", "stale": "brak sygnału od pracownika",
    "reclaimed": "przejęta ponownie", "edited": "edycja karty", "scheduled": "zaplanowana",
}
EVENT_TEXT_EN = {
    "created": "new card", "promoted": "ready to work", "promoted_manual": "ready to work",
    "claimed": "takes the card", "spawned": "starts working", "completed": "finished the card",
    "blocked": "blocked", "unblocked": "unblocked", "review_requested": "sends for review",
    "changes_requested": "sent back for changes", "commented": "comment", "archived": "archived",
    "timed_out": "timed out", "gave_up": "gave up after errors", "stale": "no signal from worker",
    "reclaimed": "taken again", "edited": "card edited", "scheduled": "scheduled",
}
FEED_KINDS = {"created", "promoted", "spawned", "completed", "blocked", "unblocked", "review_requested",
              "changes_requested", "timed_out", "gave_up", "stale"}
TONE = {"completed": "good", "blocked": "bad", "gave_up": "bad", "timed_out": "bad", "stale": "warn",
        "changes_requested": "warn", "review_requested": "info"}


def _last_event(events: list[dict], task_id: str, kind: str) -> dict | None:
    return next((e for e in events if e["task_id"] == task_id and e["kind"] == kind), None)


def agent_cards(name: str, tasks: list[dict], orchestrator: str) -> dict[str, list[dict]]:
    """Karty agenta według stanu. Orkiestrator (sędzia) ma dodatkowo kolejkę „do oceny”."""
    out: dict[str, list[dict]] = {k: [] for k in ("running", "ready", "review", "blocked", "triage", "done", "judging")}
    for t in tasks:
        st = t.get("status")
        mine = t.get("assignee") == name
        if st == "running" and (t.get("worker") or t.get("assignee")) == name:
            out["running"].append(t)
        elif st in ("running", "review") and t.get("worker") == name and not mine:
            # cudza karta, którą ten profil właśnie wykonuje (np. TARS jako sędzia w torze review)
            out["running"].append(t)
        elif st == "running" and mine and t.get("worker") and t["worker"] != name:
            # karta agenta, którą w tej chwili wykonuje inny profil (np. TARS ją ocenia)
            out["review"].append(t)
        elif mine and st in ("ready", "todo", "scheduled"):
            out["ready"].append(t)
        elif mine and st in ("review", "blocked", "triage", "done"):
            out[st].append(t)
        if name == orchestrator and st == "review":
            out["judging"].append(t)
    for k in out:
        out[k].sort(key=lambda t: -(t.get("completed_at") or t.get("started_at") or t.get("created_at") or 0))
    return out


def derive_status(name: str, cards: dict[str, list[dict]], now: float) -> dict:
    """Stan pokoju: working | judging | blocked | review | queued | idle (+ nagłówek po polsku)."""
    if cards["running"]:
        t = cards["running"][0]
        hb = t.get("last_heartbeat_at") or t.get("started_at")
        quiet = bool(hb and now - hb > HEARTBEAT_STALE_S)
        return {"status": "working", "headline": t.get("title") or "", "task_id": t["id"],
                "since": t.get("started_at"), "quiet": quiet}
    if cards["blocked"]:
        t = cards["blocked"][0]
        return {"status": "blocked", "headline": t.get("title") or "", "task_id": t["id"],
                "block_kind": t.get("block_kind"), "since": t.get("created_at")}
    if cards["judging"]:
        return {"status": "judging", "headline": f"Do oceny: {len(cards['judging'])}", "task_id": cards["judging"][0]["id"]}
    if cards["review"]:
        t = cards["review"][0]
        return {"status": "review", "headline": t.get("title") or "", "task_id": t["id"]}
    if cards["ready"]:
        return {"status": "queued", "headline": f"W kolejce: {len(cards['ready'])}", "task_id": cards["ready"][0]["id"]}
    return {"status": "idle", "headline": "", "task_id": None}


def worker_session(t: dict) -> tuple[str | None, float | None]:
    """(session_id, od kiedy) sesji tego, kto teraz pracuje nad kartą. session_id karty należy do
    wykonawcy; gdy kartę trzyma inny profil (np. TARS-sędzia), szukamy jego sesji po starcie runu."""
    if t.get("worker") and t["worker"] != t.get("assignee"):
        return None, t.get("run_started_at") or t.get("started_at")
    return t.get("session_id"), t.get("run_started_at") or t.get("started_at")


def card_brief(t: dict) -> dict:
    return {k: t.get(k) for k in ("id", "title", "status", "assignee", "worker", "created_at", "started_at",
                                  "completed_at", "block_kind", "priority")}


def build_state(fleet: list[dict], board: dict, index_md: str, now: float,
                activity_by_task: dict[str, dict] | None = None) -> dict:
    tasks, events = board.get("tasks", []), board.get("events", [])
    orchestrator = next((a["name"] for a in fleet if a.get("kind") == "orchestrator"), "tars")
    by_id = {t["id"]: t for t in tasks}
    day_ago = now - 86400
    agents = []
    for a in fleet:
        cards = agent_cards(a["name"], tasks, orchestrator)
        st = derive_status(a["name"], cards, now)
        cur = (activity_by_task or {}).get(st.get("task_id") or "")
        if cur and st["status"] == "working":
            st["tool"] = cur
        if st["status"] == "blocked":
            ev = _last_event(events, st["task_id"], "blocked")
            st["reason"] = (ev or {}).get("payload", {}).get("reason")
        agents.append({
            **{k: a.get(k) for k in ("name", "title", "emoji", "kind", "room", "label", "short", "model_tier", "autonomy_max", "en")},
            **st,
            "counts": {"running": len(cards["running"]), "ready": len(cards["ready"]), "review": len(cards["review"]),
                       "blocked": len(cards["blocked"]), "judging": len(cards["judging"]),
                       "done_today": sum(1 for t in cards["done"] if (t.get("completed_at") or 0) >= day_ago)},
        })

    board_counts = {s: sum(1 for t in tasks if t.get("status") == s)
                    for s in ("triage", "ready", "running", "review", "blocked")}
    board_counts["ready"] += sum(1 for t in tasks if t.get("status") in ("todo", "scheduled"))
    board_counts["done_today"] = sum(1 for t in tasks if t.get("status") == "done" and (t.get("completed_at") or 0) >= day_ago)

    decisions = []
    for t in tasks:
        if t.get("status") != "blocked":
            continue
        # karta porzucona po błędach (pracownik padał): pokazujemy przyczynę i „Ponów”, nie pytanie
        gave = _last_event(events, t["id"], "gave_up")
        blk = _last_event(events, t["id"], "blocked")
        if gave and (not blk or (gave.get("created_at") or 0) >= (blk.get("created_at") or 0)):
            gp = gave.get("payload", {})
            err = str(gp.get("error") or "").strip().splitlines()
            decisions.append({"task_id": t["id"], "title": t.get("title"), "assignee": t.get("assignee"),
                              "kind": "failed", "failures": gp.get("failures"),
                              "reason": (err[-1] if err else "")[:300],
                              "since": gave.get("created_at") or t.get("created_at")})
            continue
        if t.get("block_kind") in (None, "", "needs_input"):
            ev = blk or {}
            p = ev.get("payload", {})
            if p.get("kind") not in (None, "needs_input"):
                continue
            decisions.append({"task_id": t["id"], "title": t.get("title"), "assignee": t.get("assignee"),
                              "reason": p.get("reason") or "", "since": ev.get("created_at") or t.get("created_at")})
    decisions.sort(key=lambda d: d.get("since") or 0)

    missions = []
    for m in parse_missions(index_md):
        cards = [by_id.get(c) for c in m["cards"]]
        present = [card_brief(c) for c in cards if c]
        done = sum(1 for c in present if c["status"] in ("done", "archived"))
        missions.append({**m, "cards": present, "missing": [c for c in m["cards"] if c not in by_id],
                         "done": done, "total": len(m["cards"])})

    feed = []
    for e in events:
        if e["kind"] not in FEED_KINDS:
            continue
        t = by_id.get(e["task_id"], {})
        who = t.get("worker") if e["kind"] == "spawned" and t.get("worker") else t.get("assignee")
        feed.append({"ts": e["created_at"], "kind": e["kind"], "tone": TONE.get(e["kind"], "neutral"),
                     "agent": who, "task_id": e["task_id"], "title": t.get("title") or e["task_id"],
                     "text": EVENT_TEXT.get(e["kind"], e["kind"]), "text_en": EVENT_TEXT_EN.get(e["kind"], e["kind"])})
        if len(feed) >= FEED_LIMIT:
            break

    return {"ts": now, "board_ok": board.get("ok", True), "agents": agents, "board": board_counts,
            "decisions": decisions, "missions": missions, "feed": feed}


# --------------------------------------------------------------------------- outputs

@dataclass
class Roots:
    tars_dir: Path = TARS_DIR

    def allowed(self) -> list[Path]:
        return [(self.tars_dir / r).resolve() for r in PREVIEW_ROOTS]


def safe_path(raw: str, roots: Roots) -> Path | None:
    """Ścieżka pliku do podglądu, tylko wewnątrz dozwolonych katalogów (bez ../ i symlinków na zewnątrz)."""
    if not raw or "\x00" in raw:
        return None
    try:
        p = Path(raw).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    for root in roots.allowed():
        try:
            p.relative_to(root)
        except ValueError:
            continue
        return p if p.is_file() else None
    return None


SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".cache", "archiwum", ".astro", "dist-cache"}
SCAN_MAX = 5000   # twardy limit plików na jedno zapytanie (duże projekty)


def list_outputs(dirs: Iterable[Path], roots: Roots, limit: int = OUTPUT_LIMIT) -> list[dict]:
    """Pliki wynikowe (najpierw katalogi out/), najnowsze pierwsze, bez plików roboczych.
    Katalogi robocze (node_modules, .git…) są pomijane już przy przechodzeniu drzewa."""
    seen, files = set(), []
    allowed = roots.allowed()
    scanned = 0
    for d in dirs:
        try:
            d = d.resolve()
        except OSError:
            continue
        if not d.is_dir() or not any(_within(d, r) for r in allowed):
            continue
        for root, subdirs, names in os.walk(d):
            subdirs[:] = [s for s in subdirs if s not in SKIP_DIRS and not s.startswith(".")]
            for n in names:
                scanned += 1
                if scanned > SCAN_MAX:
                    break
                p = Path(root) / n
                if n.startswith(".") or p in seen or p.is_symlink():
                    continue
                seen.add(p)
                try:
                    st = p.stat()
                except OSError:
                    continue
                rel = p.relative_to(d)
                files.append({"path": str(p), "name": n, "rel": str(rel), "size": st.st_size,
                              "mtime": st.st_mtime, "kind": KIND_BY_EXT.get(p.suffix.lower(), "other"),
                              "in_out": "out" in rel.parts})
    files.sort(key=lambda f: (not f["in_out"], -f["mtime"]))
    return files[:limit]


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------------- załączniki czatu
ATTACH_MARK = "📎 "            # linia wiadomości ze ścieżką załącznika (czytelna dla agenta i dla GUI)
UPLOAD_MAX = 50 * 1024 * 1024


def safe_upload_name(raw: str | None) -> str:
    """Nazwa pliku z przeglądarki → bezpieczna nazwa w inbox (bez katalogów, ukrycia i znaków innych niż litery, cyfry, „._-”)."""
    name = Path(str(raw or "").replace("\\", "/")).name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._-")[:80] or "plik"
    ext = re.sub(r"[^A-Za-z0-9]", "", ext)[:8].lower()
    return f"{stem}.{ext}" if ext else stem


def upload_target(inbox: Path, raw_name: str | None, now: float) -> Path:
    """Wolna ścieżka w inbox/<data>/ (plik.png, plik-2.png…)."""
    day = inbox / time.strftime("%Y-%m-%d", time.localtime(now))
    name = safe_upload_name(raw_name)
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    p, n = day / name, 1
    while p.exists():
        n += 1
        p = day / (f"{stem}-{n}.{ext}" if ext else f"{stem}-{n}")
    return p


def file_entry(p: Path, base: Path | None = None) -> dict:
    st = p.stat()
    return {"path": str(p), "name": p.name, "rel": str(p.relative_to(base)) if base else p.name, "size": st.st_size,
            "mtime": st.st_mtime, "kind": KIND_BY_EXT.get(p.suffix.lower(), "other"), "in_out": False}


def message_text(content: Any) -> str:
    """Tekst wiadomości z historii gatewaya: zwykły napis albo lista części (tekst + obrazy)."""
    if isinstance(content, str):
        s = content.strip()
        if not (s.startswith("[") and '"type"' in s):
            return content
        try:
            content = json.loads(s)
        except ValueError:
            return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") in ("text", "input_text") and p.get("text"))
    return ""


_IMAGE_PLACEHOLDER = re.compile(r"^\[(?:screenshot|image|obraz)\]\s*$", re.M | re.I)


def user_text(content: Any) -> str:
    """Wiadomość użytkownika do dymka: bez znaczników obrazów, którymi gateway zastępuje wysłane zdjęcia
    (te same zdjęcia GUI pokazuje z linii 📎)."""
    text = message_text(content)
    if ATTACH_MARK.strip() in text:
        text = _IMAGE_PLACEHOLDER.sub("", text).rstrip()
    return text


def compose_message(text: str, attachments: list[str]) -> str:
    """Wiadomość do agenta: tekst + ścieżki załączników (agent czyta pliki swoimi narzędziami)."""
    text = (text or "").strip()
    if not attachments:
        return text
    lines = "\n".join(ATTACH_MARK + a for a in attachments)
    head = text or "(bez komentarza)"
    return f"{head}\n\nZałączniki (pliki na dysku floty):\n{lines}"


# ------------------------------------------------------------------------- zlecenie karty
# Format zlecenia z dispatch-playbook TARS-a: CEL / KONTEKST / WEJŚCIA / DoD / WYJŚCIA / GRANICE.
BRIEF_KEYS = {"cel": "cel", "kontekst": "kontekst", "wejścia": "wejscia", "wejscia": "wejscia",
              "dod": "dod", "wyjścia": "wyjscia", "wyjscia": "wyjscia", "granice": "granice"}
_BRIEF_LINE = re.compile(r"^\s*(?:[-*#>]+\s*)?\**\s*(" + "|".join(BRIEF_KEYS) + r")\s*\**\s*:\**\s*(.*)$", re.I)
_OUT_PATH = re.compile(r"(?<![\w/])((?:[\w.-]+/)*[\w-][\w.-]*\.[A-Za-z0-9]{1,5})\b")


def parse_brief(body: str | None) -> dict:
    """Zlecenie karty → sekcje (cel, kontekst, wejscia, dod, wyjscia, granice). Tekst przed pierwszą
    sekcją trafia do `intro`. Zlecenie bez sekcji: pusty słownik (GUI pokazuje je w całości)."""
    sections: dict[str, list[str]] = {}
    key = "intro"
    for line in (body or "").splitlines():
        m = _BRIEF_LINE.match(line)
        if m:
            key = BRIEF_KEYS[m.group(1).lower()]
            sections.setdefault(key, [])
            if m.group(2).strip():
                sections[key].append(m.group(2).rstrip())
            continue
        sections.setdefault(key, []).append(line.rstrip())
    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    out = {k: v for k, v in out.items() if v}
    return out if set(out) - {"intro"} else {}


def expected_outputs(wyjscia: str | None) -> list[str]:
    """Nazwy plików z sekcji WYJŚCIA (np. „out/index.html”), w kolejności, bez powtórzeń."""
    seen: list[str] = []
    text = re.sub(r"\S+://\S+|www\.\S+", " ", wyjscia or "")     # adresy stron to nie pliki
    for m in _OUT_PATH.finditer(text):
        p = m.group(1).lstrip("./")
        if p not in seen:
            seen.append(p)
    return seen


def task_outputs(task: dict, roots: Roots, limit: int = 12) -> list[dict]:
    """Pliki wynikowe karty z jej katalogu roboczego; pliki wymienione w WYJŚCIA mają `main`."""
    ws = task.get("workspace_path")
    if not ws:
        return []
    files = list_outputs([Path(ws)], roots, limit=200)
    wanted = expected_outputs(parse_brief(task.get("body")).get("wyjscia"))
    for f in files:
        rel = f["rel"].replace(os.sep, "/")
        f["main"] = any(rel == w or rel.endswith("/" + w) or f["name"] == w for w in wanted)
    files.sort(key=lambda f: (not f["main"], not f["in_out"], -f["mtime"]))
    return files[:limit]


# ------------------------------------------------------------------------ „Odpal” (podgląd stron)
# Katalogi, od których liczymy stronę: ścieżki absolutne (/assets/…) w zbudowanym serwisie działają.
SITE_DIRS = {"out", "dist", "build", "public", "site", "_site", "www"}


def site_root(file: Path, roots: Roots) -> Path:
    """Katalog serwowany jako strona dla pliku: najbliższy przodek o nazwie z SITE_DIRS (do 4 poziomów
    w górę, nie wyżej niż dozwolone katalogi), inaczej katalog pliku."""
    allowed = roots.allowed()
    for d in list(file.parents)[:4]:
        if not any(_within(d, r) and d != r for r in allowed):
            break
        if d.name.lower() in SITE_DIRS:
            return d
    return file.parent


# Linki podglądu wspólne dla dashboardu („▶ Odpal”) i agentów (scripts/tars_link.py): token → katalog strony.
LINKS_FILE = TARS_DIR / "state" / "preview-links.json"
LINK_TTL = 7 * 86400
LINKS_MAX = 500


def links_load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def link_for(path: Path, root: Path, now: float, ttl: float = LINK_TTL) -> str:
    """Token dla katalogu strony (ten sam, póki ważny jeszcze co najmniej pół terminu). Zapis pod blokadą,
    bo dashboard i agenci dopisują do tego samego pliku."""
    import fcntl
    import secrets

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = {t: v for t, v in links_load(path).items()
                if isinstance(v, dict) and float(v.get("exp", 0)) > now}
        for tok, v in data.items():
            if v.get("root") == str(root) and float(v["exp"]) - now > ttl / 2:
                return tok
        tok = secrets.token_urlsafe(18)
        data[tok] = {"root": str(root), "exp": now + ttl}
        if len(data) > LINKS_MAX:   # najstarsze wypadają
            data = dict(sorted(data.items(), key=lambda kv: kv[1]["exp"])[-LINKS_MAX:])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
    return tok


def link_root(path: Path, token: str, now: float) -> Path | None:
    v = links_load(path).get(token) if token else None
    if not isinstance(v, dict) or float(v.get("exp", 0)) <= now:
        return None
    return Path(v["root"])


def site_file(root: Path, rel: str, roots: Roots) -> Path | None:
    """Plik strony pod `root` dla ścieżki z adresu (katalog → index.html). Bez plików ukrytych,
    bez wyjścia poza `root` i poza dozwolone katalogi (także przez symlinki)."""
    parts = [p for p in rel.split("/") if p]
    if any(p.startswith(".") or "\x00" in p or "\\" in p for p in parts):
        return None
    try:
        p = root.joinpath(*parts).resolve(strict=True)
        if p.is_dir():
            p = (p / "index.html").resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not _within(p, root.resolve()) or not p.is_file():
        return None
    return p if safe_path(str(p), roots) else None


def agent_stats(name: str, tasks: list[dict], events: list[dict], now: float) -> dict:
    """Jakość z ostatnich 7 dni: karty zamknięte, przyjęte za pierwszym razem, poprawki."""
    week = now - 7 * 86400
    done = [t for t in tasks if t.get("assignee") == name and t.get("status") == "done"
            and (t.get("completed_at") or 0) >= week]
    changes = {e["task_id"] for e in events if e["kind"] == "changes_requested"}
    first_pass = sum(1 for t in done if t["id"] not in changes)
    return {"done_7d": len(done), "first_pass_7d": first_pass,
            "changes_7d": sum(1 for t in done if t["id"] in changes)}


def now_ts() -> float:
    return time.time()

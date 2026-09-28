#!/usr/bin/env python3
"""Patrol floty Jarvo: sprawdza tablicę kanban i dziennik misji BEZ modelu.

Uruchamiany przez cron Hermesa (skrypt przed turą agenta). Wypisuje czytelny raport anomalii,
a w ostatniej linii JSON dla schedulera:
    {"wakeAgent": false}                      → cisza, zero tokenów
    {"wakeAgent": true, "context": {...}}     → Jarvo dostaje raport i działa (skill `patrol`)

Ta sama anomalia nie budzi Jarva częściej niż co JARVO_PATROL_REALERT_HOURS (domyślnie 12 h).

Tryb testowy: --fixture plik.json (tasks/events/diagnostics/index) zamiast wywołań `hermes`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MISSIONS_DIR = Path(os.environ.get("JARVO_MISSIONS_DIR", "/opt/data/jarvo/missions"))
STATE_FILE = Path(os.environ.get("JARVO_PATROL_STATE", "/opt/data/jarvo/state/patrol.json"))

READY_STALE_MIN = int(os.environ.get("JARVO_PATROL_READY_STALE_MIN", "20"))
REVIEW_STALE_MIN = int(os.environ.get("JARVO_PATROL_REVIEW_STALE_MIN", "60"))
RUNNING_STALE_MIN = int(os.environ.get("JARVO_PATROL_RUNNING_STALE_MIN", "240"))
REALERT_HOURS = float(os.environ.get("JARVO_PATROL_REALERT_HOURS", "12"))
TRIAGE_ALWAYS = True

OPEN_STATUSES = {"triage", "todo", "ready", "running", "blocked", "review", "scheduled"}


# ------------------------------------------------------------------ data access

def _hermes(*args: str) -> str:
    cmd = [os.environ.get("JARVO_HERMES_BIN", "hermes"), *args]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} → {res.returncode}: {res.stderr.strip()[:300]}")
    return res.stdout


def load_live() -> dict:
    tasks = json.loads(_hermes("kanban", "list", "--json") or "[]")
    events: dict[str, list] = {}
    for t in tasks:
        if t.get("status") in {"blocked", "review", "running", "triage", "ready"}:
            show = json.loads(_hermes("kanban", "show", t["id"], "--json"))
            events[t["id"]] = show.get("events", [])
    try:
        diag_raw = json.loads(_hermes("kanban", "diagnostics", "--json", "--severity", "warning") or "[]")
    except Exception as exc:  # diagnostyka nie może zatrzymać patrolu
        diag_raw = [{"task_id": None, "diagnostics": [{"severity": "warning", "message": f"diagnostics failed: {exc}"}]}]
    diagnostics = []
    for block in diag_raw if isinstance(diag_raw, list) else [diag_raw]:
        for d in block.get("diagnostics", []) or []:
            d = dict(d)
            d.setdefault("task_id", block.get("task_id"))
            diagnostics.append(d)
    index_file = MISSIONS_DIR / "INDEX.md"
    index = index_file.read_text(encoding="utf-8") if index_file.exists() else ""
    return {"tasks": tasks, "events": events, "diagnostics": diagnostics, "index": index}


# --------------------------------------------------------------------- analysis

_ROW = re.compile(r"^\|\s*(?P<id>[MZ]-[^|]+?)\s*\|(?P<rest>.*)\|\s*$")


def parse_index(index_md: str) -> list[dict]:
    """Wiersze sekcji „## Aktywne” z INDEX.md: id, tytuł, status, karty."""
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
        title = cells[0] if cells else ""
        status = cells[1] if len(cells) > 1 else ""
        cards = re.findall(r"t_[0-9a-f]+", cells[2]) if len(cells) > 2 else []
        rows.append({"id": m.group("id").strip(), "title": title, "status": status, "cards": cards})
    return rows


def _last_event(events: list, kind: str) -> dict | None:
    matching = [e for e in events if e.get("kind") == kind]
    return max(matching, key=lambda e: e.get("created_at") or 0) if matching else None


def analyze(data: dict, now: float) -> list[dict]:
    """Zwraca listę anomalii: {key, severity, kind, task_id?, mission?, message}."""
    tasks = {t["id"]: t for t in data.get("tasks", [])}
    events = data.get("events", {})
    out: list[dict] = []

    def add(key, severity, kind, message, **extra):
        out.append({"key": key, "severity": severity, "kind": kind, "message": message, **extra})

    for tid, t in tasks.items():
        status = t.get("status")
        title = t.get("title", "")
        who = t.get("assignee") or "?"
        evs = events.get(tid, [])
        if status == "blocked":
            ev = _last_event(evs, "blocked") or {}
            payload = ev.get("payload") or {}
            since = ev.get("created_at") or t.get("created_at") or now
            add(f"blocked:{tid}:{int(since)}", "high", "blocked",
                f"Zablokowana: „{title}” ({who}), powód: {payload.get('reason') or 'brak'}",
                task_id=tid, block_kind=payload.get("kind"), since_min=int((now - since) / 60))
        elif status == "triage":
            add(f"triage:{tid}", "high", "triage",
                f"W triage (pętla blokad albo brak specyfikacji): „{title}” ({who})", task_id=tid)
        elif status == "ready":
            # od ostatniego zdarzenia (np. promocja z todo), nie od utworzenia karty
            last = max([e.get("created_at") or 0 for e in evs] + [t.get("created_at") or 0]) or now
            age = (now - last) / 60
            if age > READY_STALE_MIN:
                add(f"ready:{tid}", "medium", "ready_stale",
                    f"Gotowa od {int(age)} min i nikt jej nie podjął: „{title}” ({who}). Dispatcher/gateway działa?",
                    task_id=tid)
        elif status == "review":
            ev = _last_event(evs, "review_requested") or {}
            since = ev.get("created_at") or t.get("started_at") or t.get("created_at") or now
            age = (now - since) / 60
            if age > REVIEW_STALE_MIN:
                add(f"review:{tid}:{int(since)}", "medium", "review_stale",
                    f"Recenzja czeka {int(age)} min: „{title}” ({who})", task_id=tid)
        elif status == "running":
            started = t.get("started_at") or t.get("created_at") or now
            limit = (t.get("max_runtime_seconds") or RUNNING_STALE_MIN * 60) / 60
            age = (now - started) / 60
            if age > max(limit, RUNNING_STALE_MIN):
                add(f"running:{tid}:{int(started)}", "medium", "running_long",
                    f"Pracuje od {int(age)} min (limit {int(limit)}): „{title}” ({who})", task_id=tid)

    for d in data.get("diagnostics", []):
        msg = d.get("message") or d.get("summary") or json.dumps(d, ensure_ascii=False)[:200]
        add(f"diag:{d.get('task_id')}:{d.get('code') or msg[:40]}", d.get("severity", "warning"),
            "diagnostic", f"Diagnostyka Hermesa: {msg}", task_id=d.get("task_id"))

    for m in parse_index(data.get("index", "")):
        cards = m["cards"]
        if not cards:
            continue
        missing = [c for c in cards if c not in tasks]
        statuses = [tasks[c].get("status") for c in cards if c in tasks]
        if statuses and all(s in {"done", "archived"} for s in statuses) and not missing:
            add(f"mission_done:{m['id']}", "high", "mission_ready",
                f"Misja {m['id']} („{m['title']}”): wszystkie karty zakończone, brak raportu końcowego.",
                mission=m["id"])
        if missing:
            add(f"mission_missing:{m['id']}:{','.join(missing)}", "low", "mission_inconsistent",
                f"Misja {m['id']}: w INDEX są karty, których nie ma na tablicy: {', '.join(missing)}",
                mission=m["id"])
    return out


def select_new(anomalies: list[dict], state: dict, now: float) -> list[dict]:
    fresh = []
    for a in anomalies:
        last = state.get(a["key"])
        if last is None or (now - last) > REALERT_HOURS * 3600:
            fresh.append(a)
    return fresh


def update_state(state: dict, reported: list[dict], anomalies: list[dict], now: float) -> dict:
    live_keys = {a["key"] for a in anomalies}
    new_state = {k: v for k, v in state.items() if k in live_keys}   # zapominamy rozwiązane
    for a in reported:
        new_state[a["key"]] = now
    return new_state


def render(anomalies: list[dict]) -> str:
    order = {"critical": 0, "high": 1, "error": 1, "medium": 2, "warning": 2, "low": 3}
    lines = [f"PATROL FLOTY: {len(anomalies)} sygnałów wymaga uwagi"]
    for a in sorted(anomalies, key=lambda a: order.get(a["severity"], 9)):
        lines.append(f"- [{a['severity']}] {a['message']}")
    return "\n".join(lines)


# ------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="JSON z tasks/events/diagnostics/index (testy)")
    ap.add_argument("--now", type=float, default=None)
    ap.add_argument("--state", default=str(STATE_FILE))
    args = ap.parse_args(argv)

    now = args.now or time.time()
    try:
        data = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else load_live()
    except Exception as exc:
        # Patrol, który sam nie działa, to też sygnał, ale nie budzimy modelu w pętli:
        print(f"PATROL: błąd odczytu tablicy: {exc}")
        print(json.dumps({"wakeAgent": True, "context": {"patrol_error": str(exc)[:500]}}))
        return 0

    state_path = Path(args.state)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except Exception:
        state = {}

    anomalies = analyze(data, now)
    fresh = select_new(anomalies, state, now)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(update_state(state, fresh, anomalies, now), indent=1), encoding="utf-8")

    if not fresh:
        print(json.dumps({"wakeAgent": False}))
        return 0
    print(render(fresh))
    print(json.dumps({"wakeAgent": True, "context": {"anomalies": fresh}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

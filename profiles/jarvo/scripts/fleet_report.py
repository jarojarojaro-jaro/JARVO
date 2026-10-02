#!/usr/bin/env python3
"""Zbiera dane do porannego briefu (--mode daily) i przeglądu tygodnia (--mode weekly).

Skrypt przed turą crona: wypisuje zwięzły kontekst (bez modelu), a ostatnia linia to JSON
dla schedulera. Brief budzi Jarva zawsze, gdy jest cokolwiek do powiedzenia; pusty dzień → cisza.

Tryb testowy: --fixture plik.json z {"tasks": [...], "shows": {id: show_json}, "index": "..."}.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liczby  # noqa: E402  (ta sama definicja jakości co w Jarvo HQ)

MISSIONS_DIR = Path(os.environ.get("JARVO_MISSIONS_DIR", "/opt/data/jarvo/missions"))
DAY = 86400


def _hermes(*args: str) -> str:
    res = subprocess.run([os.environ.get("JARVO_HERMES_BIN", "hermes"), *args],
                         capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip()[:300])
    return res.stdout


def load_live(window_s: int) -> dict:
    tasks = json.loads(_hermes("kanban", "list", "--json", "--archived") or "[]")
    now = time.time()
    shows = {}
    for t in tasks:
        recent = (t.get("completed_at") or 0) > now - window_s or t.get("status") not in {"done", "archived"}
        if recent:
            shows[t["id"]] = json.loads(_hermes("kanban", "show", t["id"], "--json"))
    index_file = MISSIONS_DIR / "INDEX.md"
    return {"tasks": tasks, "shows": shows, "index": index_file.read_text(encoding="utf-8") if index_file.exists() else ""}


def summarize(data: dict, now: float, window_s: int) -> dict:
    tasks = data["tasks"]
    shows = data.get("shows", {})
    by_status = Counter(t.get("status") for t in tasks if t.get("status") != "archived")
    finished = [t for t in tasks if (t.get("completed_at") or 0) > now - window_s and t.get("status") == "done"]
    blocked = [t for t in tasks if t.get("status") == "blocked"]
    in_flight = [t for t in tasks if t.get("status") in {"ready", "running", "review", "todo", "triage"}]

    quality = liczby.jakosc(finished, {t["id"]: (shows.get(t["id"]) or {}).get("events", []) for t in finished})

    def brief(t):
        return {"id": t["id"], "title": t.get("title"), "assignee": t.get("assignee"), "status": t.get("status")}

    blocked_info = []
    for t in blocked:
        evs = (shows.get(t["id"]) or {}).get("events", [])
        reason = next((e.get("payload", {}).get("reason") for e in reversed(evs) if e.get("kind") == "blocked"), None)
        blocked_info.append({**brief(t), "reason": reason})

    return {
        "window_hours": int(window_s / 3600),
        "counts": dict(by_status),
        "finished": [brief(t) for t in finished],
        "blocked": blocked_info,
        "in_flight": [brief(t) for t in in_flight],
        "quality": quality,
        "active_missions": [ln for ln in data.get("index", "").splitlines() if ln.startswith("| M-") or ln.startswith("| Z-")][:20],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    ap.add_argument("--fixture")
    ap.add_argument("--now", type=float)
    args = ap.parse_args(argv)
    window = DAY if args.mode == "daily" else 7 * DAY
    now = args.now or time.time()
    try:
        data = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else load_live(window)
    except Exception as exc:
        print(f"RAPORT: błąd odczytu tablicy: {exc}")
        print(json.dumps({"wakeAgent": True, "context": {"report_error": str(exc)[:300]}}))
        return 0

    summary = summarize(data, now, window)
    if args.mode == "weekly" and not args.fixture:
        # sześć liczb z tablicy i sesji (0 tokenów): eskalacje, awarie, cisza i tokeny obok jakości
        summary["liczby"] = liczby.policz(liczby.dane_domyslne(), now, 7)
    empty = not (summary["finished"] or summary["blocked"] or summary["in_flight"])
    if args.mode == "daily" and empty:
        print(json.dumps({"wakeAgent": False}))
        return 0
    print(f"DANE DO RAPORTU ({args.mode}, ostatnie {summary['window_hours']} h):")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps({"wakeAgent": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

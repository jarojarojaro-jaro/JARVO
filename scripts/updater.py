#!/usr/bin/env python3
"""Pomocnik aktualizacji TARS: przycisk „Aktualizuj” w dashboardzie bez dawania kontenerowi dostępu do Dockera.

    python3 scripts/updater.py [--compose DIR] [--build DIR] [--once]

Działa na HOŚCIE (VPS albo WSL), obok kontenera, jako użytkownik z dostępem do dockera i do repo:
- co TARS_UPDATE_CHECK sekund (domyślnie 60) robi `git fetch` gałęzi repo i zapisuje stan dla
  dashboardu (ile commitów brakuje i jakie) do <HERMES_HOME>/tars/state/update.json w kontenerze,
- co kilka sekund sprawdza, czy dashboard poprosił o aktualizację (plik update-request); wtedy uruchamia
  scripts/deploy.sh (git pull + budowa obrazu, gdy trzeba + instalacja floty) i raportuje postęp.
Dashboard nigdy nie wykonuje poleceń: może tylko poprosić o `check` albo `update` tej samej gałęzi.
Uruchamiany przez scripts/local-up.sh (lokalnie) albo usługę systemd tars-updater (VPS, bootstrap-vps.sh).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = os.environ.get("TARS_CONTAINER", "tars-hermes")
STATE_DIR = "/opt/data/tars/state"
CHECK_EVERY = int(os.environ.get("TARS_UPDATE_CHECK", "60"))
# TARS_AUTO_UPDATE=1: nowa wersja instaluje się sama, bez klikania w dashboardzie
AUTO_UPDATE = os.environ.get("TARS_AUTO_UPDATE", "0") == "1"
POLL_EVERY = 5
LOG_TAIL = 40


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git(*args: str) -> str:
    r = run(["git", "-C", str(ROOT), *args])
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or f"git {' '.join(args)} nie powiodło się")
    return r.stdout.strip()


def put_state(state: dict) -> bool:
    """Zapis stanu do kontenera (docker exec: żadnych wspólnych katalogów ani uprawnień na hoście)."""
    body = json.dumps(state, ensure_ascii=False)
    r = run(["docker", "exec", "-i", "-u", "hermes", CONTAINER, "sh", "-c",
             f"mkdir -p {STATE_DIR} && cat > {STATE_DIR}/update.json.tmp && mv {STATE_DIR}/update.json.tmp {STATE_DIR}/update.json"],
            input=body)
    return r.returncode == 0


def take_request() -> str | None:
    """Prośba z dashboardu (`check` albo `update`); usuwana przy odczycie."""
    r = run(["docker", "exec", "-u", "hermes", CONTAINER, "sh", "-c",
             f"f={STATE_DIR}/update-request; [ -f $f ] && cat $f && rm -f $f"])
    if r.returncode != 0:
        return None
    req = r.stdout.strip().split()[0] if r.stdout.strip() else ""
    return req if req in ("check", "update") else None


def check(base: dict) -> dict:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    git("fetch", "-q", "origin", branch)
    current, latest = git("rev-parse", "HEAD"), git("rev-parse", f"origin/{branch}")
    log = git("log", "--format=%h%x09%s", f"HEAD..origin/{branch}")
    commits = [dict(zip(("sha", "subject"), line.split("\t", 1))) for line in log.splitlines() if "\t" in line]
    return {**base, "branch": branch, "current": current[:7], "latest": latest[:7], "behind": len(commits),
            "commits": commits[:20], "checked_at": time.time(), "error": None}


def update(args, state: dict) -> dict:
    put_state({**state, "state": "updating", "started_at": time.time(), "log": ""})
    env = dict(os.environ)
    if args.compose:
        env["TARS_COMPOSE_DIR"] = args.compose
    if args.build:
        env["TARS_BUILD"] = args.build
    lines: list[str] = []
    proc = subprocess.Popen(["bash", str(ROOT / "scripts" / "deploy.sh")], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last_push = 0.0
    for line in proc.stdout:  # postęp na żywo (ogon logu), co kilka sekund
        lines.append(line.rstrip())
        if time.time() - last_push > 5:
            put_state({**state, "state": "updating", "log": "\n".join(lines[-LOG_TAIL:])})
            last_push = time.time()
    ok = proc.wait() == 0
    # kontener mógł zostać odtworzony: czekamy, aż znów przyjmie zapis stanu
    final = {**check(state), "state": "done" if ok else "failed", "finished_at": time.time(),
             "log": "\n".join(lines[-LOG_TAIL:])}
    for _ in range(60):
        if put_state(final):
            break
        time.sleep(5)
    return final


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compose", help="katalog compose (.env, tars.env); domyślnie jak w deploy.sh")
    ap.add_argument("--build", help="katalog build; domyślnie jak w deploy.sh")
    ap.add_argument("--mode", default="vps", choices=["vps", "local"])
    ap.add_argument("--repo", help="repo do aktualizacji (domyślnie to, z którego uruchomiono skrypt)")
    ap.add_argument("--once", action="store_true", help="jedno sprawdzenie i wyjście (test)")
    args = ap.parse_args(argv)
    global ROOT
    if args.repo:
        ROOT = Path(args.repo).resolve()
    state: dict = {"mode": args.mode, "state": "idle", "updater_pid": os.getpid(), "auto": AUTO_UPDATE}
    next_check = 0.0
    while True:
        try:
            req = take_request()
            if req is None and AUTO_UPDATE and state.get("behind", 0) > 0 and state.get("state") != "failed":
                req = "update"
            if req == "update":
                state = update(args, state)
                next_check = time.time() + CHECK_EVERY
            elif req == "check" or time.time() >= next_check:
                # „done”/„failed” zostają do następnej aktualizacji (panel pokazuje „odśwież” albo błąd)
                keep = state.get("state") if state.get("state") in ("done", "failed") else "idle"
                state = {**check(state), "state": keep}
                put_state(state)
                next_check = time.time() + CHECK_EVERY
        except Exception as exc:  # brak sieci, kontener w trakcie restartu… spróbujemy za chwilę
            state = {**state, "error": str(exc)[:300], "checked_at": time.time()}
            put_state(state)
            next_check = time.time() + 60
        if args.once:
            return 0
        time.sleep(POLL_EVERY)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

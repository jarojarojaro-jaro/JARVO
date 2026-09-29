#!/usr/bin/env python3
"""Pomocnik hosta Jarvo: przycisk „Aktualizuj” i „Pokaż w folderze” w dashboardzie bez dawania kontenerowi
dostępu do Dockera ani do hosta.

    python3 scripts/updater.py [--compose DIR] [--build DIR] [--once]

Działa na HOŚCIE (VPS albo WSL), obok kontenera, jako użytkownik z dostępem do dockera i do repo:
- co JARVO_UPDATE_CHECK sekund (domyślnie 60) robi `git fetch` gałęzi repo i zapisuje stan dla
  dashboardu (ile commitów brakuje i jakie) do <HERMES_HOME>/jarvo/state/update.json w kontenerze,
- co kilka sekund sprawdza, czy dashboard poprosił o aktualizację (plik update-request); wtedy uruchamia
  scripts/deploy.sh (git pull + budowa obrazu, gdy trzeba + instalacja floty) i raportuje postęp.
- lokalnie w WSL otwiera Eksplorator Windows na pliku wynikowym (plik reveal-request z samą ścieżką;
  pomocnik przelicza ją na ścieżkę hosta i sprawdza, że leży w katalogach wyników floty).
Dashboard nigdy nie wykonuje poleceń: może tylko poprosić o `check` albo `update` tej samej gałęzi
albo o pokazanie pliku wyników w Eksploratorze.
Uruchamiany przez scripts/local-up.sh (lokalnie) albo usługę systemd jarvo-updater (VPS, bootstrap-vps.sh).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = os.environ.get("JARVO_CONTAINER", "jarvo-hermes")
STATE_DIR = "/opt/data/jarvo/state"
CHECK_EVERY = int(os.environ.get("JARVO_UPDATE_CHECK", "60"))
# JARVO_AUTO_UPDATE=1: nowa wersja instaluje się sama, bez klikania w dashboardzie
AUTO_UPDATE = os.environ.get("JARVO_AUTO_UPDATE", "0") == "1"
POLL_EVERY = 2   # prośby z dashboardu (folder ma się otworzyć od razu)
LOG_TAIL = 40
# zawieszony deploy (np. build bez sieci) nie może blokować panelu w nieskończoność
UPDATE_TIMEOUT = int(os.environ.get("JARVO_UPDATE_TIMEOUT", str(45 * 60)))
DATA_IN = "/opt/data"
# tylko wyniki floty (jak podgląd plików w HQ): nigdy klucze, profile ani konfiguracja
REVEAL_ROOTS = ("jarvo/workspaces", "jarvo/missions", "jarvo/knowledge", "jarvo/inbox")


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


def take_requests() -> tuple[str | None, str | None]:
    """Prośby z dashboardu: aktualizacja (`check`/`update`) i ścieżka do pokazania; usuwane przy odczycie."""
    r = run(["docker", "exec", "-u", "hermes", CONTAINER, "sh", "-c",
             f"cd {STATE_DIR} 2>/dev/null || exit 0; for f in update-request reveal-request; do "
             f"[ -f $f ] && printf '%s\\t' $f && tr -d '\\n\\t' < $f && echo && rm -f $f; done; true"])
    if r.returncode != 0:
        return None, None
    upd = rev = None
    for line in r.stdout.splitlines():
        name, _, body = line.partition("\t")
        if name == "update-request":
            word = body.strip().split()[0] if body.strip() else ""
            upd = word if word in ("check", "update") else None
        elif name == "reveal-request":
            try:
                rev = str(json.loads(body).get("path") or "") or None
            except ValueError:
                rev = None
    return upd, rev


def host_info() -> dict:
    """Katalog danych kontenera na hoście i czy da się otworzyć Eksplorator (WSL)."""
    r = run(["docker", "inspect", CONTAINER, "--format",
             '{{range .Mounts}}{{if eq .Destination "' + DATA_IN + '"}}{{.Source}}{{end}}{{end}}'])
    data_host = r.stdout.strip() if r.returncode == 0 else ""
    explorer = bool(data_host and shutil.which("explorer.exe") and shutil.which("wslpath"))
    data_win = None
    if explorer:
        w = run(["wslpath", "-w", data_host])
        data_win = w.stdout.strip() if w.returncode == 0 else None
    return {"explorer": explorer, "data_host": data_host or None, "data_win": data_win}


def host_path(path: str, data_host: str) -> Path | None:
    """Ścieżka z kontenera (/opt/data/…) → plik na hoście, tylko w katalogach wyników floty."""
    if not path.startswith(DATA_IN + "/") or "\x00" in path:
        return None
    base = Path(data_host).resolve()
    p = (base / path[len(DATA_IN) + 1:]).resolve()
    if not p.exists() or not any(p.is_relative_to(base / r) for r in REVEAL_ROOTS):
        return None
    return p


def reveal(path: str, host: dict) -> None:
    """Eksplorator Windows z zaznaczonym plikiem (albo otwartym katalogiem)."""
    if not host.get("explorer"):
        return
    p = host_path(path, host["data_host"])
    if p is None:
        print(f"reveal: odrzucona ścieżka {path!r}", file=sys.stderr)
        return
    w = run(["wslpath", "-w", str(p)])
    if w.returncode != 0:
        return
    arg = f"/select,{w.stdout.strip()}" if p.is_file() else w.stdout.strip()
    # explorer.exe zwraca 1 także po sukcesie; nie czekamy na okno
    subprocess.Popen(["explorer.exe", arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
        env["JARVO_COMPOSE_DIR"] = args.compose
    if args.build:
        env["JARVO_BUILD"] = args.build
    lines: list[str] = []
    started = time.time()
    proc = subprocess.Popen(["bash", str(ROOT / "scripts" / "deploy.sh")], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    done = threading.Event()

    def beat() -> None:
        # znak życia co 15 s także bez nowych linii (długi build); po limicie czasu przerywamy deploy
        while not done.wait(15):
            if time.time() - started > UPDATE_TIMEOUT:
                lines.append(f"Przerwano: aktualizacja trwała ponad {UPDATE_TIMEOUT // 60} min.")
                os.killpg(proc.pid, signal.SIGTERM)
                return
            put_state({**state, "state": "updating", "started_at": started, "beat": time.time(),
                       "log": "\n".join(lines[-LOG_TAIL:])})

    t = threading.Thread(target=beat, daemon=True)
    t.start()
    for line in proc.stdout:  # postęp na żywo (ogon logu)
        lines.append(line.rstrip())
    ok = proc.wait() == 0
    done.set()
    t.join(timeout=60)   # ostatni znak życia nie może nadpisać wyniku
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
    ap.add_argument("--compose", help="katalog compose (.env, jarvo.env); domyślnie jak w deploy.sh")
    ap.add_argument("--build", help="katalog build; domyślnie jak w deploy.sh")
    ap.add_argument("--mode", default="vps", choices=["vps", "local"])
    ap.add_argument("--repo", help="repo do aktualizacji (domyślnie to, z którego uruchomiono skrypt)")
    ap.add_argument("--once", action="store_true", help="jedno sprawdzenie i wyjście (test)")
    args = ap.parse_args(argv)
    global ROOT
    if args.repo:
        ROOT = Path(args.repo).resolve()
    state: dict = {"mode": args.mode, "state": "idle", "updater_pid": os.getpid(), "auto": AUTO_UPDATE}
    try:  # po samorestarcie (niżej): stan „done” zostaje, żeby dashboard sam się odświeżył
        state.update(json.loads(os.environ.pop("JARVO_UPDATER_STATE", "") or os.environ.pop("TARS_UPDATER_STATE", "") or "{}"), updater_pid=os.getpid())
    except ValueError:
        pass
    me = Path(__file__).resolve()
    my_code = me.read_bytes()
    next_check = 0.0
    while True:
        try:
            if not (state.get("host") or {}).get("data_host"):
                state["host"] = host_info()
            req, rev = take_requests()
            if rev:
                reveal(rev, state["host"])
            if req is None and AUTO_UPDATE and state.get("behind", 0) > 0 and state.get("state") != "failed":
                req = "update"
            if req == "update":
                state = update(args, state)
                next_check = time.time() + CHECK_EVERY
                if state.get("state") == "done" and me.read_bytes() != my_code:
                    # aktualizacja zmieniła też tego pomocnika: wczytujemy nową wersję (ten sam PID)
                    os.environ["JARVO_UPDATER_STATE"] = json.dumps(state, ensure_ascii=False)
                    os.execv(sys.executable, [sys.executable, str(me), *argv])
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

#!/usr/bin/env python3
"""Migracja instalacji ze starej nazwy (TARS) na Jarvo. Idempotentna: drugi raz nic nie robi.

    python3 scripts/migrate_jarvo.py host --compose DIR [--build DIR]   # host (deploy.sh, local-up.sh)
    python3 scripts/migrate_jarvo.py container [--data /opt/data]        # w kontenerze (install-fleet.sh)

host: stare kontenery tars-* w dół, katalog ~/tars-local → ~/jarvo-local albo /srv/tars → /srv/jarvo (VPS: root),
      compose/tars.env → jarvo.env, klucze TARS_* → JARVO_* i ścieżki w plikach env, sekrety tars*.env →
      jarvo*.env, usługa systemd tars-updater → jarvo-updater. Na końcu wypisuje (do `eval`) nowe ścieżki:
      JARVO_COMPOSE_DIR=… i JARVO_BUILD=….
container: /opt/data/tars → /opt/data/jarvo (scalanie), katalogi robocze agentów, profile Hermesa
      (`hermes profile rename`: sesje, pamięć i trasy przechodzą z profilem), rutyny o starych ID, klucze
      TARS_* w .env profili, przypisania kart kanbana, stary plugin tars-hq i skórka tars.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

OLD, NEW = "tars", "jarvo"
OLD_ROOTS = {"tars": "jarvo", "tars-local": "jarvo-local"}          # /srv/tars, ~/tars-local
OLD_CONTAINERS = ["tars-hermes", "tars-searxng", "tars-valkey", "tars-uptime-kuma", "tars-beszel", "tars-beszel-agent"]
OLD_NETWORK = "tars_tars-net"
OLD_UNIT = Path("/etc/systemd/system/tars-updater.service")
NEW_UNIT = Path("/etc/systemd/system/jarvo-updater.service")
ENV_KEY = re.compile(r"^(\s*(?:export\s+)?)TARS_", re.M)


def log(msg: str) -> None:
    print(f"  migracja Jarvo: {msg}", file=sys.stderr)


def new_name(name: str) -> str:
    """tars → jarvo, tars-web → jarvo-web, tars.env → jarvo.env; inne nazwy bez zmian."""
    if name == OLD or name.startswith((OLD + "-", OLD + ".", OLD + "_")):
        return NEW + name[len(OLD):]
    return name


def merge_move(src: Path, dst: Path) -> None:
    """src → dst; gdy dst istnieje, przenosi to, czego w dst nie ma (rekurencyjnie), a pusty src usuwa."""
    if not src.exists():
        return
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return
    if src.is_dir() and dst.is_dir():
        for child in list(src.iterdir()):
            merge_move(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            log(f"zostawiam {src} (konflikty z {dst}, sprawdź ręcznie)")
    else:
        log(f"zostawiam {src}: {dst} już istnieje")


def rewrite_env_text(text: str, old_root: Path | None, new_root: Path | None) -> str:
    text = ENV_KEY.sub(lambda m: m.group(1) + "JARVO_", text)
    if old_root and new_root:
        text = re.sub(re.escape(str(old_root)) + r"(?=/|$|\s|\")", str(new_root), text, flags=re.M)
    text = re.sub(r"^DASHBOARD_USER=tars\s*$", "DASHBOARD_USER=jarvo", text, flags=re.M)
    text = text.replace("/opt/tars/", "/opt/jarvo/").replace("/opt/data/tars/", "/opt/data/jarvo/")
    return text


def rewrite_env_file(path: Path, old_root: Path | None = None, new_root: Path | None = None) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    new = rewrite_env_text(text, old_root, new_root)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


# ------------------------------------------------------------------------------------------ host

def stop_old_stack() -> None:
    if not shutil.which("docker"):
        return
    names = run(["docker", "ps", "-a", "--format", "{{.Names}}"]).stdout.split()
    old = [n for n in OLD_CONTAINERS if n in names]
    if old:
        log(f"zatrzymuję stare kontenery: {' '.join(old)}")
        run(["docker", "rm", "-f", *old])
    run(["docker", "network", "rm", OLD_NETWORK])


def stop_old_updater(root: Path) -> None:
    pid_file = root / "updater.pid"
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        log(f"zatrzymany stary pomocnik aktualizacji (PID {pid})")
    except (OSError, ValueError):
        pass
    if OLD_UNIT.exists() and os.geteuid() == 0:
        run(["systemctl", "disable", "--now", "tars-updater"])


def migrate_unit(old_root: Path, new_root: Path) -> None:
    if not OLD_UNIT.exists() or os.geteuid() != 0:
        return
    text = OLD_UNIT.read_text(encoding="utf-8").replace(str(old_root), str(new_root))
    text = re.sub(r"(?<![A-Za-z])tars(?![a-z])", "jarvo", text)
    NEW_UNIT.write_text(text, encoding="utf-8")
    OLD_UNIT.unlink()
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "jarvo-updater"])
    log("usługa systemd: tars-updater → jarvo-updater (start: sudo systemctl start jarvo-updater)")


def migrate_host(compose: Path, build: Path | None) -> tuple[Path, Path | None]:
    root = compose.parent
    if root.name in OLD_ROOTS:
        new_root = root.parent / OLD_ROOTS[root.name]
        if root.exists() and not new_root.exists():
            if not os.access(root.parent, os.W_OK):
                raise SystemExit(f"Migracja na Jarvo wymaga przeniesienia {root} → {new_root} (uprawnienia roota).\n"
                                 f"Uruchom raz: sudo python3 {Path(__file__).resolve()} host --compose {compose}\n"
                                 f"a potem: cd {new_root}/repo && bash scripts/deploy.sh")
            stop_old_updater(root)
            stop_old_stack()
            log(f"{root} → {new_root}")
            root.rename(new_root)
            migrate_unit(root, new_root)
        if new_root.exists():
            compose = new_root / compose.name
            if build is not None and str(build).startswith(str(root) + "/"):
                build = new_root / build.relative_to(root)
            old_root = root
        else:
            new_root = old_root = None
    else:
        new_root = old_root = None
    stop_old_stack()          # instalacje w innych katalogach: stare kontenery tars-* trzymałyby porty 9119/9120
    if compose.is_dir():
        legacy = compose / "tars.env"
        if legacy.exists() and not (compose / "jarvo.env").exists():
            legacy.rename(compose / "jarvo.env")
        for f in (compose / ".env", compose / "jarvo.env"):
            if f.exists() and rewrite_env_file(f, old_root, new_root):
                log(f"klucze i ścieżki: {f}")
        secrets = None
        env = compose / ".env"
        if env.exists():
            m = re.search(r"^JARVO_SECRETS=(.+)$", env.read_text(encoding="utf-8"), re.M)
            secrets = Path(m.group(1).strip()) if m else None
        if secrets and secrets.is_dir() and os.access(secrets, os.W_OK):
            for f in sorted(secrets.glob("tars*.env")):
                target = secrets / new_name(f.name)
                if not target.exists():
                    f.rename(target)
                    log(f"sekrety: {f.name} → {target.name}")
            for f in secrets.glob("*.env"):
                rewrite_env_file(f)
    return compose, build


# ------------------------------------------------------------------------------------- container

def rename_profiles(data: Path, hermes: str) -> list[str]:
    done = []
    profiles = data / "profiles"
    if not profiles.is_dir():
        return done
    for old in sorted(profiles.iterdir()):
        new = new_name(old.name)
        if not old.is_dir() or new == old.name:
            continue
        if (profiles / new).exists():
            log(f"profil {old.name}: {new} już istnieje, zostawiam stary (sprawdź i usuń ręcznie)")
            continue
        r = run([hermes, "profile", "rename", old.name, new])
        if r.returncode != 0 and old.exists() and not (profiles / new).exists():
            log(f"hermes profile rename {old.name} nie wyszedł ({(r.stderr or r.stdout).strip()[:200]}); przenoszę katalog")
            old.rename(profiles / new)
        done.append(f"{old.name} → {new}")
    return done


def drop_old_cron(data: Path) -> int:
    n = 0
    for jobs_file in (data / "profiles").glob(f"{NEW}*/cron/jobs.json"):
        try:
            payload = json.loads(jobs_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else payload
        keep = [j for j in jobs if not str(j.get("id", "")).startswith(OLD + "-")]
        if len(keep) != len(jobs):
            n += len(jobs) - len(keep)
            if isinstance(payload, dict):
                payload["jobs"] = keep
            else:
                payload = keep
            jobs_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return n


def kanban_assignees(data: Path) -> int:
    db = data / "kanban.db"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(str(db), timeout=10)
        with con:
            cur = con.execute("UPDATE tasks SET assignee = ? || substr(assignee, ?) "
                              "WHERE assignee = ? OR assignee LIKE ?", (NEW, len(OLD) + 1, OLD, OLD + "-%"))
        con.close()
        return cur.rowcount
    except sqlite3.Error as exc:
        log(f"kanban: pomijam ({exc})")
        return 0


def migrate_container(data: Path, hermes: str) -> None:
    merge_move(data / OLD, data / NEW)
    ws = data / NEW / "workspaces"
    if ws.is_dir():
        for d in list(ws.iterdir()):
            if new_name(d.name) != d.name:
                merge_move(d, ws / new_name(d.name))
    renamed = rename_profiles(data, hermes)
    if renamed:
        log("profile: " + ", ".join(renamed))
    if (n := drop_old_cron(data)):
        log(f"usunięte rutyny o starych ID: {n} (nowe instaluje build)")
    for env in [data / ".env", *(data / "profiles").glob("*/.env")]:
        if env.exists():
            rewrite_env_file(env)
    if (n := kanban_assignees(data)):
        log(f"kanban: przypisania kart {n}")
    old_plugin = data / "plugins" / (OLD + "-hq")
    if old_plugin.exists():
        run([hermes, "plugins", "disable", OLD + "-hq"])
        shutil.rmtree(old_plugin, ignore_errors=True)
        log("usunięty stary plugin tars-hq (nowy: jarvo-hq)")
    for skin in [data / "skins" / f"{OLD}.yaml", *(data / "profiles").glob(f"*/skins/{OLD}.yaml")]:
        skin.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("host")
    h.add_argument("--compose", required=True)
    h.add_argument("--build")
    c = sub.add_parser("container")
    c.add_argument("--data", default="/opt/data")
    c.add_argument("--hermes", default="hermes")
    a = ap.parse_args(argv)
    if a.cmd == "host":
        compose, build = migrate_host(Path(a.compose).expanduser(), Path(a.build).expanduser() if a.build else None)
        print(f"JARVO_COMPOSE_DIR={shlex.quote(str(compose))}")
        if build is not None:
            print(f"JARVO_BUILD={shlex.quote(str(build))}")
        return 0
    migrate_container(Path(a.data), a.hermes)
    return 0


if __name__ == "__main__":
    sys.exit(main())

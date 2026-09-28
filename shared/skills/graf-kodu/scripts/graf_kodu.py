#!/usr/bin/env python3
"""Mapa kodu (graf wywołań) dla dużego, istniejącego repo: kto woła funkcję, co się posypie po zmianie.

    graf_kodu.py indeks <repo>                        # zbuduj albo odśwież mapę (na początku zadania i po większych zmianach)
    graf_kodu.py kto-wola <repo> <funkcja> [--glebokosc 2]   # wywołujący (skąd się tu trafia)
    graf_kodu.py co-wola <repo> <funkcja> [--glebokosc 2]    # wywoływane (co ta funkcja uruchamia)
    graf_kodu.py szukaj <repo> <wzorzec> [--rodzaj Function|Class|Method]
    graf_kodu.py architektura <repo>                  # języki, pakiety, trasy HTTP, najgorętsze miejsca
    graf_kodu.py wplyw <repo>                         # zmiany z git diff → dotknięte funkcje i ryzyko
    graf_kodu.py surowo <narzędzie> [argumenty…]      # dowolne narzędzie codebase-memory-mcp (np. query_graph)

Silnik: codebase-memory-mcp (MIT, DeusData) w przypiętej wersji, pobierany przy pierwszym użyciu
(~41 MB, po rozpakowaniu ~300 MB) z sumą SHA-256. Wszystko lokalnie: bez klucza API, bez tokenów modelu,
bez procesu w tle (obserwator plików i UI wyłączone). Mapa i ustawienia leżą w katalogu narzędzi floty.

Graf to wskazówka, nie wyrocznia: nazwy rozwiązuje statycznie, więc przy dwóch funkcjach o tej samej nazwie
w różnych modułach może pomylić wywołania, a importów dynamicznych nie widzi. Przed zmianą potwierdź w pliku.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "0.11.0"
SHA256 = {   # checksums.txt wydania v0.11.0 (statyczne buildy „portable”: działają na każdym glibc)
    "amd64": "1f9e8293eb2bc5c05cfa27a7e8fc033da6d729ffad525ccfcdaa3fd606306683",
    "arm64": "d62eeb224d5ee3eba3070938ec62cf1033f10b041ec1c4b2fb67f7aef390cc7b",
}
URL = "https://github.com/DeusData/codebase-memory-mcp/releases/download/v{v}/codebase-memory-mcp-linux-{a}-portable.tar.gz"


def home() -> Path:
    """Katalog narzędzia na trwałym dysku floty (przeżywa aktualizacje obrazu)."""
    env = os.environ.get("JARVO_GRAF_KODU")
    if env:
        return Path(env)
    # jak narzedzia.py: wspólny katalog narzędzi floty (HERMES_HOME profilu to nie jest katalog danych floty)
    root = os.environ.get("JARVO_NARZEDZIA") or ("/opt/data/jarvo/narzedzia" if Path("/opt/data/jarvo").is_dir()
                                                 else str(Path.home() / ".cache" / "jarvo-narzedzia"))
    return Path(root) / "graf-kodu"


def arch() -> str:
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "amd64"
    if m in ("aarch64", "arm64"):
        return "arm64"
    raise SystemExit(f"graf kodu: nieobsługiwana architektura {m}")


def binary() -> Path:
    """Program w przypiętej wersji; pobierany raz, zweryfikowany sumą SHA-256."""
    b = home() / VERSION / "codebase-memory-mcp"
    if b.is_file():
        return b
    a = arch()
    url = URL.format(v=VERSION, a=a)
    print(f"graf kodu: pobieram codebase-memory-mcp {VERSION} ({a}, ~41 MB)…", file=sys.stderr)
    try:
        data = urllib.request.urlopen(url, timeout=300).read()
    except OSError as exc:
        raise SystemExit(f"graf kodu: nie pobrano programu ({exc}); bez sieci pracuj zwykłym wyszukiwaniem (grep)")
    if hashlib.sha256(data).hexdigest() != SHA256[a]:
        raise SystemExit("graf kodu: suma SHA-256 się nie zgadza, nie instaluję (plik podmieniony albo uszkodzony)")
    b.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = next(m for m in tar.getmembers() if Path(m.name).name == "codebase-memory-mcp" and m.isfile())
        tmp = b.with_name(".codebase-memory-mcp.part")
        tmp.write_bytes(tar.extractfile(member).read())
        for extra in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            m = next((x for x in tar.getmembers() if Path(x.name).name == extra and x.isfile()), None)
            if m:
                (b.parent / extra).write_bytes(tar.extractfile(m).read())
    tmp.chmod(0o755)
    tmp.replace(b)
    for key, val in (("watcher_enabled", "false"), ("auto_index", "false"), ("ui_enabled", "false")):
        run(["config", "set", key, val], quiet=True)   # nic w tle: mapa tylko na żądanie
    return b


def env() -> dict:
    h = home()
    (h / "home").mkdir(parents=True, exist_ok=True)
    # własny HOME: program nie dopisuje się do konfiguracji agentów (Hermes, Claude…) i nie rusza ~/.cache floty
    return {**os.environ, "HOME": str(h / "home"), "CBM_CACHE_DIR": str(h / "cache")}


def run(args: list[str], quiet: bool = False) -> subprocess.CompletedProcess:
    b = home() / VERSION / "codebase-memory-mcp"
    r = subprocess.run([str(b), *args], capture_output=True, text=True, env=env(), timeout=1800)
    if not quiet and r.returncode != 0:
        raise SystemExit(f"graf kodu: {(r.stderr or r.stdout).strip()[-800:]}")
    return r


def project(repo: Path) -> str | None:
    """Nazwa projektu w mapie dla katalogu repo (albo None, gdy jeszcze nie zindeksowany)."""
    out = run(["cli", "list_projects"]).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and Path(parts[1]) == repo:
            return parts[0]
    return None


def ensure(repo: Path, refresh: bool = False) -> str:
    binary()
    name = None if refresh else project(repo)
    if name:
        return name
    print(f"graf kodu: indeksuję {repo}…", file=sys.stderr)
    r = run(["cli", "--quiet", "index_repository", "--repo-path", str(repo)])
    name = project(repo)
    if not name:
        raise SystemExit(f"graf kodu: indeks się nie udał: {r.stdout.strip()[-400:]}")
    return name


def trace(repo: Path, fn: str, direction: str, depth: int) -> str:
    name = ensure(repo)
    out = run(["cli", "trace_path", "--project", name, "--function-name", fn, "--direction", direction,
               "--depth", str(depth)]).stdout
    try:
        d = json.loads(out)
    except ValueError:
        return out
    if d.get("status") == "ambiguous":   # kilka funkcji o tej nazwie: pokaż pełne nazwy do wyboru
        opts = [s.get("qualified_name") for s in d.get("suggestions") or []]
        return "Kilka funkcji o tej nazwie, podaj pełną nazwę:\n" + "\n".join(f"  {o}" for o in opts)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("indeks").add_argument("repo")
    for name in ("kto-wola", "co-wola"):
        sp = sub.add_parser(name)
        sp.add_argument("repo")
        sp.add_argument("funkcja")
        sp.add_argument("--glebokosc", type=int, default=2, choices=range(1, 6))
    sp = sub.add_parser("szukaj")
    sp.add_argument("repo")
    sp.add_argument("wzorzec", help="wyrażenie regularne nazwy, np. '.*Handler.*'")
    sp.add_argument("--rodzaj", help="Function, Method, Class, Route…")
    sub.add_parser("architektura").add_argument("repo")
    sub.add_parser("wplyw").add_argument("repo")
    sp = sub.add_parser("surowo")
    sp.add_argument("narzedzie")
    sp.add_argument("reszta", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)

    if a.cmd == "surowo":
        binary()
        print(run(["cli", a.narzedzie, *a.reszta]).stdout)
        return 0
    repo = Path(a.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"graf kodu: nie ma katalogu {repo}")
    if a.cmd == "indeks":
        name = ensure(repo, refresh=True)
        print(f"Mapa gotowa: projekt {name} ({repo})")
    elif a.cmd in ("kto-wola", "co-wola"):
        print(trace(repo, a.funkcja, "inbound" if a.cmd == "kto-wola" else "outbound", a.glebokosc))
    elif a.cmd == "szukaj":
        args = ["cli", "search_graph", "--project", ensure(repo), "--name-pattern", a.wzorzec]
        if a.rodzaj:
            args += ["--label", a.rodzaj]
        print(run(args).stdout)
    elif a.cmd == "architektura":
        print(run(["cli", "get_architecture", "--project", ensure(repo)]).stdout)
    elif a.cmd == "wplyw":
        print(run(["cli", "detect_changes", "--project", ensure(repo)]).stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

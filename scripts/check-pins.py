#!/usr/bin/env python3
"""Sprawdza przypięte pakiety narzędzi obrazu (npm i Python) względem zasad obrazu Hermesa.

    python3 scripts/check-pins.py [--node 26.5.1] [--python 3.12]

Czy przypięte wersje istnieją i pasują do obrazu: npm `engines.node` względem Node obrazu (`engine-strict` wywraca
budowę), Python `requires_python` względem venv narzędzi (ManimGX: venv na 3.13). Wiek wersji to tylko informacja: o dodaniu decyduje
przegląd źródła (docs/SOURCES.md, „Przegląd przed dodaniem”), nie liczba dni od wydania.
Kod wyjścia 1 przy problemie. Wymaga dostępu do registry.npmjs.org i pypi.org.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "infra" / "node" / "package.json"
PY_REQS = sorted((Path(__file__).resolve().parent.parent / "infra" / "python").glob("requirements-*.txt"))
# pliki z własnym venv na innym Pythonie niż venv narzędzi (infra/Dockerfile)
PY_INNY = {"requirements-manimgx.txt": "3.13"}


def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def node_satisfies(spec: str | None, node: str) -> bool | None:
    """Uproszczone sprawdzenie zakresów typu '>=22.18', '^22.22.0 || >= 24.8.0'. None = nie umiem ocenić."""
    if not spec:
        return True
    have = tuple(int(x) for x in node.split("."))
    for alt in spec.split("||"):
        ok = True
        for m in re.finditer(r"(>=|!=|\^|~|>|<=|<)?\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", alt.strip()):
            op, parts = m.group(1) or "=", tuple(int(x or 0) for x in m.groups()[1:])
            if op == ">=":
                ok &= have >= parts
            elif op == ">":
                ok &= have > parts
            elif op == "<":
                ok &= have < parts
            elif op == "<=":
                ok &= have <= parts
            elif op == "!=":
                ok &= have[: len(parts)] != parts if m.group(4) or m.group(3) else have[0] != parts[0]
            elif op == "^":
                ok &= have >= parts and have[0] == parts[0]
            elif op == "~":
                ok &= have >= parts and have[:2] == parts[:2]
            else:
                ok &= have[: len(parts)] == parts
        if ok:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--node", default="26.5.1", help="wersja Node w obrazie Hermesa (node --version)")
    ap.add_argument("--python", default="3.12", help="Python venv narzędzi (infra/Dockerfile)")
    args = ap.parse_args(argv)
    deps = json.loads(PKG.read_text(encoding="utf-8"))["dependencies"]
    now = dt.datetime.now(dt.timezone.utc)
    bad = 0
    for name, ver in deps.items():
        with urllib.request.urlopen(f"https://registry.npmjs.org/{name.replace('/', '%2F')}", timeout=30) as r:  # noqa: S310
            data = json.load(r)
        published = data.get("time", {}).get(ver)
        if not published:
            print(f"✗ {name}@{ver}: brak takiej wersji")
            bad += 1
            continue
        age = (now - parse_ts(published)).days
        engines = (data["versions"].get(ver, {}).get("engines") or {}).get("node")
        eng_ok = node_satisfies(engines, args.node)
        problems = []
        if eng_ok is False:
            problems.append(f"engines.node {engines!r} nie obejmuje Node {args.node}")
        mark = "✗" if problems else "✓"
        bad += bool(problems)
        print(f"{mark} {name}@{ver}: {age} dni" + (f"  → {'; '.join(problems)}" if problems else ""))
    print(f"Piny npm: {len(deps) - bad}/{len(deps)} OK")
    return 1 if (bad + check_python(args, now)) else 0


def check_python(args, now: dt.datetime) -> int:
    bad = 0
    for req in PY_REQS:
        for line in req.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_.-]+)(\[[^\]]+\])?==(\S+)", line)
            if not m:
                continue
            name, ver = m.group(1), m.group(3)
            with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as r:  # noqa: S310
                data = json.load(r)
            files = data["releases"].get(ver) or []
            if not files:
                print(f"✗ {req.name}: {name}=={ver} nie istnieje (najnowsza {data['info']['version']})")
                bad += 1
                continue
            age = (now - min(parse_ts(f["upload_time_iso_8601"]) for f in files)).days
            req_py = next((f.get("requires_python") for f in files if f.get("requires_python")), None)
            py = PY_INNY.get(req.name, args.python)
            py_ok = node_satisfies(req_py.replace(",", " ") if req_py else None, py + ".0")
            note = []
            if py_ok is False:
                note.append(f"requires_python {req_py!r} nie obejmuje {py}")
                bad += 1
            mark = "✗" if py_ok is False else "✓"
            print(f"{mark} {req.name}: {name}=={ver}: {age} dni" + (f"  → {'; '.join(note)}" if note else ""))
    return bad


if __name__ == "__main__":
    sys.exit(main())

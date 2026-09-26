#!/usr/bin/env python3
"""Sprawdza przypięte pakiety narzędzi obrazu (npm i Python) względem zasad obrazu Hermesa.

    python3 scripts/check-pins.py [--min-age 14] [--node 26.5.1] [--python 3.12]

Obraz Hermesa ma globalny npmrc z `min-release-age = 14` (kwarantanna łańcucha dostaw) i `engine-strict`:
wersja opublikowana mniej niż 14 dni temu albo wymagająca innego Node wywraca budowę obrazu na VPS.
Skrypt pokazuje wiek każdej wersji, najnowszą dopuszczalną i zgodność `engines.node`.
Piny Pythona (infra/python/requirements-*.txt): czy wersja istnieje na PyPI i obsługuje Pythona venv narzędzi;
młode wersje są tylko ostrzeżeniem (uv nie ma kwarantanny, ale świeże wydania bywają wycofywane).
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


def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def node_satisfies(spec: str | None, node: str) -> bool | None:
    """Uproszczone sprawdzenie zakresów typu '>=22.18', '^22.22.0 || >= 24.8.0'. None = nie umiem ocenić."""
    if not spec:
        return True
    have = tuple(int(x) for x in node.split("."))
    for alt in spec.split("||"):
        ok = True
        for m in re.finditer(r"(>=|\^|~|>|<=|<)?\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", alt.strip()):
            op, parts = m.group(1) or "=", tuple(int(x or 0) for x in m.groups()[1:])
            if op == ">=":
                ok &= have >= parts
            elif op == ">":
                ok &= have > parts
            elif op == "<":
                ok &= have < parts
            elif op == "<=":
                ok &= have <= parts
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
    ap.add_argument("--min-age", type=int, default=14)
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
        allowed = [(v, t) for v, t in data["time"].items()
                   if v not in {"created", "modified"} and "-" not in v and (now - parse_ts(t)).days >= args.min_age]
        newest_ok = max(allowed, key=lambda x: x[1])[0] if allowed else "—"
        engines = (data["versions"].get(ver, {}).get("engines") or {}).get("node")
        eng_ok = node_satisfies(engines, args.node)
        problems = []
        if age < args.min_age:
            problems.append(f"za młoda ({age} dni < {args.min_age}); najnowsza dopuszczalna: {newest_ok}")
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
            py_ok = node_satisfies(req_py.replace(",", " ") if req_py else None, args.python + ".0")
            note = []
            if py_ok is False:
                note.append(f"requires_python {req_py!r} nie obejmuje {args.python}")
                bad += 1
            if age < args.min_age:
                note.append(f"młoda wersja ({age} dni), ostrzeżenie")
            mark = "✗" if py_ok is False else ("!" if note else "✓")
            print(f"{mark} {req.name}: {name}=={ver}: {age} dni" + (f"  → {'; '.join(note)}" if note else ""))
    return bad


if __name__ == "__main__":
    sys.exit(main())

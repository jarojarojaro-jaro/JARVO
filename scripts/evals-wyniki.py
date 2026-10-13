#!/usr/bin/env python3
"""Wyniki evals floty: trend, punkt odniesienia i porównanie dwóch przebiegów (docs/RSI.md §R0).

    python3 scripts/evals-wyniki.py trend [--agent jarvo-web] [--n 8] [--json]
    python3 scripts/evals-wyniki.py odniesienie --agent jarvo-web --przebieg 20261013-2210
    python3 scripts/evals-wyniki.py porownaj <przebieg A> <przebieg B> --agent jarvo-web [--json]
    python3 scripts/evals-wyniki.py porownaj odniesienie <przebieg B> --agent jarvo-web

Katalog wyników (--wyniki): domyślnie /opt/data/jarvo/evals (kopia ze stagingu, czyta ją HQ i przegląd tygodnia),
inaczej evals/results w repo. Przebieg to nazwa katalogu <data> albo ścieżka do niego.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalslib as ev  # noqa: E402
import fleetlib as fl  # noqa: E402


def domyslne_wyniki() -> Path:
    env = os.environ.get("JARVO_EVAL_RESULTS")
    if env:
        return Path(env)
    prod = Path(os.environ.get("JARVO_DATA_DIR", "/opt/data/jarvo")) / "evals"
    return prod if prod.is_dir() else fl.REPO_ROOT / "evals" / "results"


def przebieg(wyniki: Path, nazwa: str) -> Path:
    p = Path(nazwa)
    return p if p.is_dir() else wyniki / nazwa


def rekordy(wyniki: Path, nazwa: str, agent: str) -> list[dict]:
    if nazwa == "odniesienie":
        path = ev.odniesienie_path(wyniki, agent)
    else:
        path = przebieg(wyniki, nazwa) / f"{agent}.jsonl"
    if not path.is_file():
        raise SystemExit(f"Brak wyników: {path}")
    return ev.wczytaj_przebieg(path)


def fmt(x) -> str:
    return "—" if x is None else f"{x:.2f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wyniki", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trend")
    t.add_argument("--agent", action="append", default=[])
    t.add_argument("--n", type=int, default=8)
    t.add_argument("--json", action="store_true")
    o = sub.add_parser("odniesienie")
    o.add_argument("--agent", required=True)
    o.add_argument("--przebieg", required=True)
    c = sub.add_parser("porownaj")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--agent", required=True)
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    wyniki = args.wyniki or domyslne_wyniki()

    if args.cmd == "trend":
        agenci = args.agent or [a.name for a in fl.load_fleet().active()]
        dane = {a: ev.trend(wyniki, a, args.n) for a in agenci}
        if args.json:
            print(json.dumps(dane, ensure_ascii=False, indent=1))
            return 0
        if not any(dane.values()):
            print(f"Brak historii evals w {wyniki} (najpierw scripts/evals-staging.sh).")
            return 0
        for a, wpisy in dane.items():
            if not wpisy:
                print(f"{a}: brak przebiegów")
                continue
            ost = wpisy[-1]
            seria = " → ".join(fmt(w["score"]) for w in wpisy)
            print(f"{a}: {ost['zaliczone']}/{ost['n']} zaliczonych, wynik {fmt(ost['score'])} "
                  f"(odłożone {fmt(ost['odlozony'])}), commit {ost['commit'] or '—'}, {ost['data']}"
                  + ("  ALARM KANARKA" if ost["kanarek"] else ""))
            if len(wpisy) > 1:
                print(f"   trend: {seria}")
        return 0

    if args.cmd == "odniesienie":
        dst = ev.ustaw_odniesienie(wyniki, args.agent, przebieg(wyniki, args.przebieg))
        print(f"✓ {args.agent}: punkt odniesienia = {args.przebieg} ({dst})")
        return 0

    cmp = ev.porownaj(rekordy(wyniki, args.a, args.agent), rekordy(wyniki, args.b, args.agent))
    if args.json:
        print(json.dumps(cmp, ensure_ascii=False, indent=1))
        return 0
    print(f"{args.agent}: {args.a} → {args.b}, wspólnych scenariuszy {cmp['wspolne']}")
    print(f"  zmiana wyniku {cmp['delta']:+.3f}; lepsze {len(cmp['wygrane'])}, gorsze {len(cmp['przegrane'])}, "
          f"remisy {cmp['remisy']}; test znaków p={cmp['p']}")
    for nazwa, klucz in (("Regresje", "regresje"), ("Regresje bezpieczeństwa", "bezpieczenstwo"),
                         ("Naprawione", "poprawy")):
        if cmp[klucz]:
            print(f"  {nazwa}: {', '.join(cmp[klucz])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

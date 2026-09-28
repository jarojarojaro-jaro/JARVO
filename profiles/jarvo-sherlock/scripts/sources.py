#!/usr/bin/env python3
"""Dziennik źródeł śledztwa (out/zrodla.jsonl) z oceną wiarygodności i lokalną archiwizacją.

    python3 sources.py add <url> --tier A|B|C|D --type pierwotne|wtorne|dane|opinia \
        [--date RRRR-MM-DD] [--title "..."] [--note "..."] [--archive]
    python3 sources.py list [--min-tier B]
    python3 sources.py cite            # lista numerowana do sekcji "Źródła" raportu

Tier (skala w skillu weryfikacja-faktow): A oficjalne/pierwotne, B renomowane media/branża,
C blogi/fora z nazwiskiem, D anonimowe/afiliacyjne/niepewne.
--archive zapisuje lokalną kopię HTML + tekstu w out/archiwum/ (dowód, gdyby strona się zmieniła).
Dziennik leży w bieżącym katalogu roboczym karty (out/).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

LOG = Path("out/zrodla.jsonl")
ARCHIVE = Path("out/archiwum")
TIERS = ["A", "B", "C", "D"]


def load() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_all(entries: list[dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def archive(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jarvo-sherlock/1.0"})
        with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310
            raw = resp.read(8_000_000)
    except Exception as exc:
        print(f"archiwizacja nieudana: {exc}", file=sys.stderr)
        return None
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE / f"{digest}.html"
    path.write_bytes(raw)
    return str(path)


def cmd_add(args) -> int:
    entries = load()
    existing = next((e for e in entries if e["url"] == args.url), None)
    entry = existing or {"n": len(entries) + 1, "url": args.url}
    entry.update({
        "tier": args.tier, "type": args.type, "date": args.date, "title": args.title,
        "note": args.note, "checked_at": dt.date.today().isoformat(),
    })
    if args.archive:
        entry["archive"] = archive(args.url)
    if not existing:
        entries.append(entry)
    save_all(entries)
    print(json.dumps(entry, ensure_ascii=False))
    return 0


def cmd_list(args) -> int:
    limit = TIERS.index(args.min_tier) if args.min_tier else len(TIERS) - 1
    for e in load():
        if TIERS.index(e.get("tier", "D")) <= limit:
            print(f"[{e['n']}] {e.get('tier')} {e.get('type')} {e.get('date') or '?'} {e.get('title') or ''} {e['url']}")
    return 0


def cmd_cite(_args) -> int:
    for e in load():
        date = f", {e['date']}" if e.get("date") else ""
        print(f"[{e['n']}] {e.get('title') or e['url']}{date}. {e['url']} (wiarygodność {e.get('tier')}, {e.get('type')})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("url")
    a.add_argument("--tier", choices=TIERS, required=True)
    a.add_argument("--type", choices=["pierwotne", "wtorne", "dane", "opinia"], required=True)
    a.add_argument("--date")
    a.add_argument("--title")
    a.add_argument("--note")
    a.add_argument("--archive", action="store_true")
    a.set_defaults(fn=cmd_add)
    ls = sub.add_parser("list")
    ls.add_argument("--min-tier", choices=TIERS)
    ls.set_defaults(fn=cmd_list)
    c = sub.add_parser("cite")
    c.set_defaults(fn=cmd_cite)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

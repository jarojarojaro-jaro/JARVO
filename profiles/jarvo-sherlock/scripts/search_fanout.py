#!/usr/bin/env python3
"""Jedno zapytanie → wiele kategorii i języków SearXNG, deduplikacja URL-i, wynik JSON.

    python3 search_fanout.py "zapytanie" [--lang pl] [--lang en] [--category general --category news]
                            [--time day|week|month|year] [--limit 20]

Wymaga SEARXNG_URL (np. http://searxng:8080) z włączonym formatem JSON (infra/searxng/settings.yml).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def search(base: str, query: str, lang: str | None, category: str, time_range: str | None, page: int = 1) -> list[dict]:
    params = {"q": query, "format": "json", "categories": category, "pageno": str(page)}
    if lang:
        params["language"] = lang
    if time_range:
        params["time_range"] = time_range
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "jarvo-sherlock/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (adres z konfiguracji)
        data = json.load(resp)
    out = []
    for r in data.get("results", []):
        out.append({
            "url": r.get("url"),
            "title": r.get("title"),
            "snippet": (r.get("content") or "")[:400],
            "engines": r.get("engines") or [r.get("engine")],
            "published": r.get("publishedDate"),
            "category": category,
            "lang": lang,
        })
    return out


def normalize(url: str) -> str:
    p = urllib.parse.urlsplit(url or "")
    query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.startswith("utm_")])
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), query, ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--lang", action="append", default=[])
    ap.add_argument("--category", action="append", default=[])
    ap.add_argument("--time", dest="time_range", choices=["day", "week", "month", "year"])
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args(argv)

    base = os.environ.get("SEARXNG_URL")
    if not base:
        print(json.dumps({"error": "Brak SEARXNG_URL"}))
        return 2
    langs = args.lang or ["pl", "en"]
    cats = args.category or ["general"]
    merged: dict[str, dict] = {}
    errors = []
    for lang in langs:
        for cat in cats:
            try:
                for r in search(base, args.query, lang, cat, args.time_range):
                    key = normalize(r["url"])
                    if not key:
                        continue
                    if key in merged:
                        merged[key]["hits"] += 1
                        merged[key]["engines"] = sorted(set(merged[key]["engines"]) | set(r["engines"] or []))
                    else:
                        merged[key] = {**r, "hits": 1}
            except Exception as exc:  # jedna kategoria nie może zatrzymać reszty
                errors.append(f"{lang}/{cat}: {exc}")
    ranked = sorted(merged.values(), key=lambda r: (-r["hits"], -len(r["engines"] or [])))[: args.limit]
    print(json.dumps({"query": args.query, "results": ranked, "errors": errors}, ensure_ascii=False, indent=1))
    return 0 if ranked or not errors else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Czysta treść strony + metadane (tytuł, autor, data publikacji) przez trafilatura.

    python3 extract.py <url> [--max-chars 20000] [--json]

Trafilatura jest instalowana w obrazie Jarvo (infra/Dockerfile). Bez niej skrypt robi prosty
fallback (HTML → tekst), a w wyniku ustawia "degraded": true.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) jarvo-sherlock/1.0"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310 (URL od agenta, tylko odczyt)
        raw = resp.read(8_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


TOOLS_PY = "/opt/jarvo/venv/bin/python"


def _reexec_in_tools_venv() -> None:
    """trafilatura żyje w /opt/jarvo/venv; jeśli uruchomiono nas innym Pythonem, przełącz się."""
    import os

    if os.path.exists(TOOLS_PY) and os.path.realpath(sys.executable) != os.path.realpath(TOOLS_PY):
        os.execv(TOOLS_PY, [TOOLS_PY, *sys.argv])


def extract(url: str, max_chars: int) -> dict:
    try:
        import trafilatura  # type: ignore
    except ImportError:
        _reexec_in_tools_venv()
        trafilatura = None

    if trafilatura is not None:
        downloaded = trafilatura.fetch_url(url) or fetch(url)
        result = trafilatura.extract(
            downloaded, url=url, output_format="json", with_metadata=True,
            include_comments=False, include_tables=True, favor_precision=True,
        )
        if result:
            data = json.loads(result)
            text = data.get("text") or ""
            return {
                "url": url, "title": data.get("title"), "author": data.get("author"),
                "date": data.get("date"), "sitename": data.get("sitename"),
                "text": text[:max_chars], "truncated": len(text) > max_chars, "degraded": False,
            }
    page = fetch(url)
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return {"url": url, "title": html.unescape(title.group(1).strip()) if title else None, "author": None,
            "date": None, "sitename": None, "text": text[:max_chars], "truncated": len(text) > max_chars,
            "degraded": True}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--max-chars", type=int, default=20000)
    ap.add_argument("--json", action="store_true", help="wynik jako JSON (domyślnie czytelny tekst)")
    args = ap.parse_args(argv)
    try:
        data = extract(args.url, args.max_chars)
    except Exception as exc:
        print(json.dumps({"url": args.url, "error": str(exc)[:300]}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(f"# {data.get('title') or '(bez tytułu)'}")
        print(f"URL: {data['url']}\nData: {data.get('date') or 'nieznana'} | Autor: {data.get('author') or '—'} | Serwis: {data.get('sitename') or '—'}")
        if data.get("degraded"):
            print("UWAGA: ekstrakcja uproszczona (brak trafilatura)")
        print()
        print(data["text"])
        if data.get("truncated"):
            print("\n[… ucięte, użyj --max-chars]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

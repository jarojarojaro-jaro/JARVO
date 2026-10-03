#!/usr/bin/env python3
"""Czysta treść strony + metadane (tytuł, autor, data publikacji) przez trafilatura.

    python3 extract.py <url> [--max-chars 20000] [--json] [--tier A|B|C|D] [--type pierwotne|wtorne|dane|opinia]
        [--rejestr PLIK] [--bez-rejestru]

Przy pobraniu strona trafia do rejestru źródeł (`sources.py`, domyślnie out/zrodla.json): dostaje numer [n],
a cały jej tekst zostaje w `strony/<n>.txt` obok rejestru jako dowód do cytatów (`sources.py quote`).
--tier/--type od razu oceniają źródło. --bez-rejestru: tylko odczyt (np. strona, której nie zacytujesz).

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
from pathlib import Path

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


def extract(url: str) -> dict:
    """Pełny tekst strony z metadanymi (main przycina go do --max-chars dopiero przy wypisaniu)."""
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
            return {
                "url": url, "title": data.get("title"), "author": data.get("author"),
                "date": data.get("date"), "sitename": data.get("sitename"),
                "text": data.get("text") or "", "degraded": False,
            }
    page = fetch(url)
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return {"url": url, "title": html.unescape(title.group(1).strip()) if title else None, "author": None,
            "date": None, "sitename": None, "text": text, "degraded": True}


def zarejestruj(data: dict, rejestr: str | None, tier: str | None, typ: str | None) -> tuple[dict, Path]:
    """Wpis w rejestrze źródeł z zapisanym tekstem strony; zwraca (wpis, plik z tekstem)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sources  # noqa: E402 (skrypt obok, bez instalacji)

    path = sources.sciezka_rejestru(rejestr)
    meta = {"tier": tier, "type": typ, "date": (data.get("date") or "")[:10] or None}
    wpis = sources.add_sources(path, [data["url"]], title=data.get("title"), meta=meta, text=data["text"])[0]
    return wpis, path.parent / wpis["tekst"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--max-chars", type=int, default=20000)
    ap.add_argument("--json", action="store_true", help="wynik jako JSON (domyślnie czytelny tekst)")
    ap.add_argument("--tier", choices=["A", "B", "C", "D"], help="ocena wiarygodności (skala z weryfikacja-faktow)")
    ap.add_argument("--type", choices=["pierwotne", "wtorne", "dane", "opinia"])
    ap.add_argument("--rejestr", help="plik rejestru źródeł (domyślnie $JARVO_REJESTR_ZRODEL albo out/zrodla.json)")
    ap.add_argument("--bez-rejestru", action="store_true", help="tylko odczyt, bez wpisu w rejestrze")
    args = ap.parse_args(argv)
    try:
        data = extract(args.url)
    except Exception as exc:
        print(json.dumps({"url": args.url, "error": str(exc)[:300]}, ensure_ascii=False))
        return 1
    if not args.bez_rejestru and data["text"].strip():
        wpis, plik = zarejestruj(data, args.rejestr, args.tier, args.type)
        data["zrodlo"], data["tekst"] = wpis["id"], str(plik)
    full = data["text"]
    data["text"], data["truncated"] = full[:args.max_chars], len(full) > args.max_chars
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        if data.get("zrodlo"):
            print(f"[{data['zrodlo']}] w rejestrze źródeł; pełny tekst: {data['tekst']}")
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

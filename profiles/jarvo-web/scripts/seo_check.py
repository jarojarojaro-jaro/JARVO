#!/usr/bin/env python3
"""Szybka kontrola SEO on-page i „head” jednej strony (tylko biblioteka standardowa).

    python3 seo_check.py <url|plik.html> [--json] [--base-url https://domena.pl]

Sekcje: head (title, description, canonical, lang, viewport, robots), icons (favicon, apple-touch,
manifest), og (Open Graph/Twitter), jsonld (typy i poprawność składni), content (H1, nagłówki,
obrazy bez alt/wymiarów), crawl (robots.txt, sitemap.xml, hreflang). Każda sekcja: errors/warnings/info.
Kod wyjścia 1, gdy są błędy.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 jarvo-web-seo-check/1.0"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: list[dict] = []
        self.links: list[dict] = []
        self.scripts_ld: list[str] = []
        self.imgs: list[dict] = []
        self.headings: list[tuple[str, str]] = []
        self.html_attrs: dict = {}
        self.title = ""
        self._in_title = False
        self._in_ld = False
        self._ld_buf: list[str] = []
        self._heading: str | None = None
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.html_attrs = a
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld, self._ld_buf = True, []
        elif tag == "img":
            self.imgs.append(a)
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading, self._heading_buf = tag, []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self.scripts_ld.append("".join(self._ld_buf))
            self._in_ld = False
        elif self._heading and tag == self._heading:
            self.headings.append((tag, " ".join("".join(self._heading_buf).split())))
            self._heading = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._ld_buf.append(data)
        if self._heading:
            self._heading_buf.append(data)


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.status, resp.read(5_000_000).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def meta_content(p: PageParser, key: str, attr: str = "name") -> str | None:
    for m in p.meta:
        if m.get(attr, "").lower() == key.lower():
            return m.get("content")
    return None


def has_link(p: PageParser, rel: str) -> dict | None:
    for link in p.links:
        rels = link.get("rel", "").lower().split()
        if rel in rels:
            return link
    return None


def check(html: str, url: str | None) -> dict:
    p = PageParser()
    p.feed(html)
    r = {s: {"errors": [], "warnings": [], "info": []} for s in ["head", "icons", "og", "jsonld", "content", "crawl"]}

    title = " ".join(p.title.split())
    if not title:
        r["head"]["errors"].append("brak <title>")
    elif not 15 <= len(title) <= 60:
        r["head"]["warnings"].append(f"title ma {len(title)} znaków (zalecane 15–60): {title!r}")
    else:
        r["head"]["info"].append(f"title ({len(title)}): {title!r}")
    desc = meta_content(p, "description")
    if not desc:
        r["head"]["errors"].append("brak meta description")
    elif not 70 <= len(desc) <= 160:
        r["head"]["warnings"].append(f"description ma {len(desc)} znaków (zalecane 70–160)")
    if not has_link(p, "canonical"):
        r["head"]["warnings"].append("brak link rel=canonical")
    if not p.html_attrs.get("lang"):
        r["head"]["errors"].append("brak atrybutu lang w <html>")
    if not meta_content(p, "viewport"):
        r["head"]["errors"].append("brak meta viewport")
    robots = (meta_content(p, "robots") or "").lower()
    if "noindex" in robots:
        r["head"]["errors"].append(f"meta robots zawiera noindex: {robots!r}")

    if not (has_link(p, "icon") or has_link(p, "shortcut")):
        r["icons"]["errors"].append("brak favicon (link rel=icon)")
    if not has_link(p, "apple-touch-icon"):
        r["icons"]["warnings"].append("brak apple-touch-icon")
    if not has_link(p, "manifest"):
        r["icons"]["warnings"].append("brak manifestu (link rel=manifest)")
    if not meta_content(p, "theme-color"):
        r["icons"]["info"].append("brak meta theme-color")

    for key in ["og:title", "og:description", "og:image", "og:url", "og:type"]:
        if not meta_content(p, key, "property"):
            (r["og"]["errors"] if key in {"og:title", "og:image"} else r["og"]["warnings"]).append(f"brak {key}")
    if not meta_content(p, "twitter:card"):
        r["og"]["warnings"].append("brak twitter:card")

    types = []
    for raw in p.scripts_ld:
        try:
            data = json.loads(raw)
            items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
            for it in items:
                t = it.get("@type") if isinstance(it, dict) else None
                types.extend(t if isinstance(t, list) else [t] if t else [])
        except json.JSONDecodeError as exc:
            r["jsonld"]["errors"].append(f"niepoprawny JSON-LD: {exc}")
    if not p.scripts_ld:
        r["jsonld"]["warnings"].append("brak danych strukturalnych JSON-LD")
    else:
        r["jsonld"]["info"].append(f"typy: {sorted(set(types))}")

    h1 = [h for h in p.headings if h[0] == "h1"]
    if len(h1) != 1:
        r["content"]["errors" if not h1 else "warnings"].append(f"liczba H1: {len(h1)} (zalecane 1)")
    levels = [int(h[0][1]) for h in p.headings]
    for a, b in zip(levels, levels[1:]):
        if b > a + 1:
            r["content"]["warnings"].append(f"przeskok nagłówków h{a} → h{b}")
            break
    no_alt = [i.get("src", "?") for i in p.imgs if "alt" not in i]
    no_dims = [i.get("src", "?") for i in p.imgs if not (i.get("width") and i.get("height"))]
    if no_alt:
        r["content"]["errors"].append(f"{len(no_alt)} obrazów bez alt, np. {no_alt[:3]}")
    if no_dims:
        r["content"]["warnings"].append(f"{len(no_dims)} obrazów bez width/height (CLS), np. {no_dims[:3]}")

    if url and url.startswith("http"):
        origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(url))
        status, robots_txt = fetch(origin + "/robots.txt")
        if status != 200:
            r["crawl"]["warnings"].append(f"robots.txt: HTTP {status}")
        elif "sitemap:" not in robots_txt.lower():
            r["crawl"]["info"].append("robots.txt bez wpisu Sitemap:")
        status, _ = fetch(origin + "/sitemap.xml")
        if status != 200:
            status_idx, _ = fetch(origin + "/sitemap-index.xml")
            if status_idx != 200:
                r["crawl"]["warnings"].append(f"brak sitemap.xml (HTTP {status})")
    hreflang = [l for l in p.links if l.get("rel", "").lower() == "alternate" and l.get("hreflang")]
    if hreflang:
        r["crawl"]["info"].append(f"hreflang: {[l['hreflang'] for l in hreflang]}")

    r["summary"] = {
        "errors": sum(len(s["errors"]) for k, s in r.items() if k != "summary"),
        "warnings": sum(len(s["warnings"]) for k, s in r.items() if k != "summary"),
    }
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--base-url", help="URL do sprawdzenia robots/sitemap, gdy target to plik")
    args = ap.parse_args(argv)
    if args.target.startswith("http"):
        status, html = fetch(args.target)
        if status >= 400:
            print(json.dumps({"error": f"HTTP {status}"}))
            return 1
        url = args.target
    else:
        html = Path(args.target).read_text(encoding="utf-8", errors="replace")
        url = args.base_url
    result = check(html, url)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for section, data in result.items():
            if section == "summary":
                continue
            for level in ["errors", "warnings", "info"]:
                for msg in data[level]:
                    print(f"[{section}] {level[:-1].upper()}: {msg}")
        print(f"PODSUMOWANIE: {result['summary']['errors']} błędów, {result['summary']['warnings']} ostrzeżeń")
    return 1 if result["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

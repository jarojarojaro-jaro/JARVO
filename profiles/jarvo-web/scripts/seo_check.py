#!/usr/bin/env python3
"""Kontrola SEO on-page, „head” i widoczności: jedna strona albo cały build (tylko biblioteka standardowa).

    python3 seo_check.py <url|plik.html> [--json] [--base-url https://domena.pl] [--podglad]
    python3 seo_check.py --dir dist [--base-url https://domena.pl] [--json]

Jedna strona, sekcje:
  head     title, description, canonical (bezwzględny, ten sam host co strona), lang, viewport, noindex,
  icons    favicon, apple-touch-icon, manifest, theme-color,
  og       og:title/description/image/url/type, twitter:card; obraz OG: bezwzględny URL, HTTP 200, image/*,
           wymiary 1200×630 (z nagłówka PNG/JPEG/WebP/GIF),
  jsonld   typy i poprawność składni,
  content  jeden H1, nagłówki po kolei, landmarki (jeden <main>, <header>, <nav>, <footer>), alt (bez alt
           i alt="TODO" = błąd, alt="" dla ozdobników jest dobry), wymiary obrazów, linki wewnętrzne, czyste adresy,
  crawl    robots.txt, sitemap, /llms.txt, strona 404 (losowy adres musi dać HTTP 404, 200 = „soft 404”), hreflang.
Sieć (crawl i pobranie obrazu OG) tylko dla adresu http(s) albo z --base-url; plik bez --base-url: bez sieci.

--podglad   adres podglądu (localhost, tymczasowy link): noindex i canonical na domenie produkcyjnej to tylko
            info, obraz OG z domeny produkcyjnej sprawdzany pod tą samą ścieżką na adresie podglądu.
--dir       katalog buildu (np. dist): każda strona **/*.html jak wyżej (bez sieci), do tego duplikaty title,
            description i canonical między stronami (404.html pominięta), pliki 404.html, robots.txt, llms.txt
            i sitemap w katalogu, obraz OG z og:image w katalogu (istnieje, wymiary), strony poza sitemapą.
            --base-url = adres produkcyjny (`site` z astro.config): canonical musi wskazywać ten host.

Każda sekcja: errors/warnings/info; summary: liczba błędów i ostrzeżeń. Kod wyjścia 1, gdy są błędy.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import secrets
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import NamedTuple

UA = "Mozilla/5.0 jarvo-web-seo-check/1.1"
SEKCJE = ["head", "icons", "og", "jsonld", "content", "crawl"]
OG_ROZMIAR = (1200, 630)
# landmark: tag HTML i odpowiadająca mu rola ARIA
LANDMARKI = {"header": "banner", "nav": "navigation", "main": "main", "footer": "contentinfo"}
ALT_OGOLNE = {"obraz", "obrazek", "zdjęcie", "zdjecie", "grafika", "foto", "image", "img", "photo", "picture",
              "placeholder"}
POZIOM = {"errors": "ERROR", "warnings": "WARNING", "info": "INFO"}
BEZ_SIECI = ("robots.txt, sitemap, llms.txt, strona 404 i obraz OG nie sprawdzone (plik bez sieci): "
             "podaj adres http(s), --base-url albo --dir")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: list[dict] = []
        self.links: list[dict] = []
        self.scripts_ld: list[str] = []
        self.imgs: list[dict] = []
        self.anchors: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.landmarki: Counter = Counter()
        self.html_attrs: dict = {}
        self.title = ""
        self._in_title = False
        self._in_ld = False
        self._ld_buf: list[str] = []
        self._heading: str | None = None
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        role = a.get("role", "").lower()
        if tag in LANDMARKI:
            self.landmarki[tag] += 1
        elif role in LANDMARKI.values():
            self.landmarki[next(t for t, r in LANDMARKI.items() if r == role)] += 1
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
        elif tag == "a" and a.get("href"):
            self.anchors.append(a["href"])
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


# ------------------------------------------------------------------------------------------------ sieć

class Odpowiedz(NamedTuple):
    status: int        # 0 = brak odpowiedzi (DNS, odmowa połączenia, timeout)
    typ: str           # nagłówek Content-Type
    tresc: bytes
    url: str           # adres po przekierowaniach

    def tekst(self) -> str:
        m = re.search(r"charset=([\w-]+)", self.typ, re.I)
        try:
            return self.tresc.decode(m.group(1) if m else "utf-8", "replace")
        except LookupError:
            return self.tresc.decode("utf-8", "replace")


def pobierz(url: str, limit: int = 5_000_000) -> Odpowiedz:
    """GET z limitem bajtów. Błąd HTTP też zwraca treść (strona 404). Jedyne miejsce z siecią (testy je podmieniają)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return Odpowiedz(resp.status, resp.headers.get("Content-Type", ""), resp.read(limit), resp.geturl())
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(limit)
        except Exception:  # noqa: BLE001 — treść błędu jest dodatkiem
            body = b""
        return Odpowiedz(exc.code, (exc.headers or {}).get("Content-Type", ""), body, url)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Odpowiedz(0, "", str(exc).encode(), url)


def fetch(url: str) -> tuple[int, str]:
    """(status, tekst), jak w wersji 1.0."""
    o = pobierz(url)
    return o.status, o.tekst()


def opis(status: int) -> str:
    return f"HTTP {status}" if status else "brak odpowiedzi"


# ---------------------------------------------------------------------------------------------- pomocnicze

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


def canonical_of(p: PageParser) -> str:
    return (has_link(p, "canonical") or {}).get("href", "").strip()


def bezwzgledny(adres: str) -> bool:
    return bool(re.match(r"https?://[^/\s]", adres))


def wymiary_obrazu(b: bytes) -> tuple[int, int] | None:
    """Szerokość i wysokość z nagłówka PNG, GIF, WebP albo JPEG (bez dekodowania obrazu)."""
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    if b[:6] in (b"GIF87a", b"GIF89a") and len(b) >= 10:
        return struct.unpack("<HH", b[6:10])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP" and len(b) >= 30:
        chunk = b[12:16]
        if chunk == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if chunk == b"VP8L":
            bits = int.from_bytes(b[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        return None
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 <= len(b):
            if b[i] != 0xFF:
                return None
            m = b[i + 1]
            if m == 0xFF:                                   # bajt wypełnienia
                i += 1
            elif 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):   # SOFn
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            elif m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:    # znaczniki bez długości
                i += 2
            else:
                i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def ocen_obraz_og(dane: bytes, typ: str, gdzie: str, s: dict) -> None:
    """Format i wymiary pobranego albo lokalnego obrazu OG."""
    if "svg" in typ.lower():
        s["warnings"].append(f"obraz OG {gdzie} to SVG: Facebook, X i LinkedIn go nie pokażą (PNG albo JPEG 1200×630)")
        return
    wym = wymiary_obrazu(dane)
    if wym is None:
        s["info"].append(f"nie odczytano wymiarów obrazu OG {gdzie} (zalecane 1200×630)")
    elif tuple(wym) != OG_ROZMIAR:
        s["warnings"].append(f"obraz OG {gdzie} ma {wym[0]}×{wym[1]} (zalecane 1200×630)")
    else:
        s["info"].append(f"obraz OG {gdzie}: 1200×630")


def ocen_robots(tekst: str, s: dict) -> None:
    if re.search(r"<(!doctype|html)\b", tekst[:1000], re.I):
        s["errors"].append("robots.txt zwraca HTML (serwer odsyła stronę zamiast pliku)")
    elif re.search(r"(?im)^user-agent:\s*\*\s*(?:\n(?!user-agent).*)*?\n\s*disallow:\s*/\s*$", tekst):
        s["errors"].append("robots.txt blokuje całą stronę (User-agent: * / Disallow: /)")
    elif "sitemap:" not in tekst.lower():
        s["warnings"].append("robots.txt bez wpisu Sitemap:")


def ocen_llms(tekst: str, s: dict) -> None:
    if not tekst.lstrip().startswith("#"):
        s["errors"].append("llms.txt nie zaczyna się od nagłówka „# Nazwa” (szablon: audyt-strony/references/widocznosc.md)")


def jest_mapa(dane: bytes) -> bool:
    return bool(re.search(rb"<(urlset|sitemapindex)\b", dane))


def podsumuj(r: dict) -> dict:
    return {"errors": sum(len(r[s]["errors"]) for s in SEKCJE), "warnings": sum(len(r[s]["warnings"]) for s in SEKCJE)}


# ------------------------------------------------------------------------------------------- jedna strona

def analizuj(html: str, url: str | None, *, podglad: bool = False,
             strona_404: bool = False) -> tuple[dict, PageParser]:
    """Wynik kontroli i sparsowana strona. url http(s) włącza sieć (crawl, pobranie obrazu OG)."""
    p = PageParser()
    p.feed(html)
    r = {s: {"errors": [], "warnings": [], "info": []} for s in SEKCJE}
    siec = bool(url and url.startswith("http"))
    host = urllib.parse.urlsplit(url).netloc.lower() if siec else ""
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(url)) if siec else ""

    # ---------------------------------------------------------------- head
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
    canonical = canonical_of(p)
    if not canonical:
        if not strona_404:
            r["head"]["errors"].append("brak link rel=canonical")
    elif not bezwzgledny(canonical):
        r["head"]["errors"].append(f"canonical nie jest bezwzględnym adresem http(s): {canonical!r}")
    elif host and urllib.parse.urlsplit(canonical).netloc.lower() != host:
        inny = urllib.parse.urlsplit(canonical).netloc
        if podglad:
            r["head"]["info"].append(f"canonical na {inny} (podgląd na {host}: dobrze, jeśli to domena produkcyjna)")
        else:
            r["head"]["errors"].append(f"canonical wskazuje inny host ({inny}) niż strona ({host})")
    if not p.html_attrs.get("lang"):
        r["head"]["errors"].append("brak atrybutu lang w <html>")
    if not meta_content(p, "viewport"):
        r["head"]["errors"].append("brak meta viewport")
    robots = (meta_content(p, "robots") or "").lower()
    if "noindex" in robots:
        if strona_404:
            r["head"]["info"].append("strona 404 z noindex")
        elif podglad:
            r["head"]["info"].append(f"meta robots {robots!r}: dopuszczalne na podglądzie, nie na produkcji")
        else:
            r["head"]["errors"].append(f"meta robots zawiera noindex: {robots!r}")
    elif strona_404:
        r["head"]["warnings"].append("strona 404 bez <meta name=\"robots\" content=\"noindex\">")

    # --------------------------------------------------------------- icons
    if not (has_link(p, "icon") or has_link(p, "shortcut")):
        r["icons"]["errors"].append("brak favicon (link rel=icon)")
    if not has_link(p, "apple-touch-icon"):
        r["icons"]["warnings"].append("brak apple-touch-icon")
    if not has_link(p, "manifest"):
        r["icons"]["warnings"].append("brak manifestu (link rel=manifest)")
    if not meta_content(p, "theme-color"):
        r["icons"]["info"].append("brak meta theme-color")

    # ------------------------------------------------------------------ og
    for key in ["og:title", "og:description", "og:image", "og:url", "og:type"]:
        if not meta_content(p, key, "property"):
            (r["og"]["errors"] if key in {"og:title", "og:image"} else r["og"]["warnings"]).append(f"brak {key}")
    if not (meta_content(p, "twitter:card") or meta_content(p, "twitter:card", "property")):
        r["og"]["errors"].append("brak twitter:card (summary_large_image)")
    og_image = (meta_content(p, "og:image", "property") or "").strip()
    if og_image and not bezwzgledny(og_image):
        r["og"]["errors"].append(f"og:image nie jest bezwzględnym adresem http(s): {og_image!r}")
    elif og_image:
        w, h = meta_content(p, "og:image:width", "property"), meta_content(p, "og:image:height", "property")
        if w and h and (w.strip(), h.strip()) != tuple(str(x) for x in OG_ROZMIAR):
            r["og"]["warnings"].append(f"og:image:width/height = {w}×{h} (zalecane 1200×630)")
        if siec:
            adres = og_image
            sp = urllib.parse.urlsplit(og_image)
            if podglad and sp.netloc.lower() != host:
                adres = origin + sp.path + ("?" + sp.query if sp.query else "")
                r["og"]["info"].append(f"obraz OG z {sp.netloc} sprawdzony na podglądzie: {sp.path}")
            o = pobierz(adres, limit=2_000_000)
            if o.status != 200:
                r["og"]["errors"].append(f"obraz OG {adres}: {opis(o.status)}")
            elif not o.typ.lower().startswith("image/"):
                r["og"]["errors"].append(f"obraz OG {adres}: Content-Type {o.typ or 'brak'!r} (wymagane image/*)")
            else:
                ocen_obraz_og(o.tresc, o.typ, adres, r["og"])

    # -------------------------------------------------------------- jsonld
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

    # ------------------------------------------------------------- content
    h1 = [h for h in p.headings if h[0] == "h1"]
    if len(h1) != 1:
        r["content"]["errors" if not h1 else "warnings"].append(f"liczba H1: {len(h1)} (zalecane 1)")
    levels = [int(h[0][1]) for h in p.headings]
    for a, b in zip(levels, levels[1:]):
        if b > a + 1:
            r["content"]["warnings"].append(f"przeskok nagłówków h{a} → h{b}")
            break
    if not p.landmarki["main"]:
        r["content"]["errors"].append("brak <main> (główna treść strony w jednym <main>)")
    elif p.landmarki["main"] > 1:
        r["content"]["warnings"].append(f"{p.landmarki['main']} elementy <main> (powinien być jeden)")
    brak_lm = [f"<{t}>" for t in ("header", "nav", "footer") if not p.landmarki[t]]
    if brak_lm:
        r["content"]["warnings"].append(f"brak landmarków: {', '.join(brak_lm)}")
    no_alt = [i.get("src", "?") for i in p.imgs if "alt" not in i]
    todo = [i.get("src", "?") for i in p.imgs if i.get("alt", "").strip().lower() == "todo"]
    ogolne = []
    for i in p.imgs:
        alt = i.get("alt", "").strip().lower()
        plik = PurePosixPath(urllib.parse.urlsplit(i.get("src", "")).path).name.lower()
        if alt and alt != "todo" and (alt in ALT_OGOLNE or alt in {plik, plik.rsplit(".", 1)[0]}):
            ogolne.append(i.get("src", "?"))
    no_dims = [i.get("src", "?") for i in p.imgs if not (i.get("width") and i.get("height"))]
    if no_alt:
        r["content"]["errors"].append(f"{len(no_alt)} obrazów bez alt, np. {no_alt[:3]}")
    if todo:
        r["content"]["errors"].append(f"{len(todo)} obrazów z alt=\"TODO\" (opisz obraz albo alt=\"\" dla ozdobnika), "
                                      f"np. {todo[:3]}")
    if ogolne:
        r["content"]["warnings"].append(f"{len(ogolne)} obrazów z alt bez opisu (nazwa pliku albo „zdjęcie”), "
                                        f"np. {ogolne[:3]}")
    if no_dims:
        r["content"]["warnings"].append(f"{len(no_dims)} obrazów bez width/height (CLS), np. {no_dims[:3]}")

    # linki wewnętrzne i czyste adresy (slugi): małe litery, myślniki, bez spacji, _ i identyfikatorów w parametrach
    wewn = []
    for href in p.anchors:
        sp = urllib.parse.urlsplit(href)
        if sp.scheme in ("mailto", "tel", "javascript") or href.startswith("#"):
            continue
        if not sp.netloc or sp.netloc == host:
            wewn.append(sp)
    if len(p.headings) > 2 and len(wewn) < 3:
        r["content"]["warnings"].append(f"tylko {len(wewn)} linków wewnętrznych (zalecane ≥ 3 do powiązanych podstron)")
    brudne = sorted({sp.path + ("?" + sp.query if sp.query else "") for sp in wewn
                     if re.search(r"[A-Z_ ]|%20|\.(php|aspx?)$|/\d{4,}(/|$)", sp.path)
                     or re.search(r"(^|&)(id|p|page_id|cat)=\d", sp.query)})
    if brudne:
        r["content"]["warnings"].append(f"nieczyste adresy ({len(brudne)}), np. {brudne[:3]}: małe litery, myślniki, słowa zamiast ID")

    # --------------------------------------------------------------- crawl
    if siec:
        crawl_siec(origin, r["crawl"])
    hreflang = [link for link in p.links if link.get("rel", "").lower() == "alternate" and link.get("hreflang")]
    if hreflang:
        r["crawl"]["info"].append(f"hreflang: {[link['hreflang'] for link in hreflang]}")

    r["summary"] = podsumuj(r)
    return r, p


def crawl_siec(origin: str, c: dict) -> None:
    """robots.txt, sitemap, llms.txt i strona 404 na serwerze strony."""
    o = pobierz(origin + "/robots.txt")
    robots_txt = o.tekst() if o.status == 200 else ""
    if o.status != 200:
        c["errors"].append(f"brak robots.txt ({opis(o.status)})")
    else:
        ocen_robots(robots_txt, c)

    # sitemap: nazwy standardowe i ścieżki z wpisów Sitemap: (na badanym hoście, także na podglądzie)
    sciezki = ["/sitemap.xml", "/sitemap-index.xml"]
    sciezki += [urllib.parse.urlsplit(m).path for m in re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_txt)]
    for s in dict.fromkeys(x for x in sciezki if x):
        o = pobierz(origin + s)
        if o.status == 200 and jest_mapa(o.tresc):
            c["info"].append(f"sitemap: {s}")
            break
    else:
        c["errors"].append("brak sitemap (sitemap.xml, sitemap-index.xml ani adresu z robots.txt z <urlset>/<sitemapindex>)")

    o = pobierz(origin + "/llms.txt")
    if o.status != 200:
        c["errors"].append(f"brak /llms.txt ({opis(o.status)}; mapa strony dla wyszukiwarek AI: ChatGPT, Perplexity, Claude)")
    else:
        ocen_llms(o.tekst(), c)

    sciezka = f"/jarvo-nie-istnieje-{secrets.token_hex(4)}"
    o = pobierz(origin + sciezka)
    if o.status == 200:
        c["errors"].append(f"soft 404: nieistniejący adres {sciezka} zwraca HTTP 200 (potrzebna strona 404 ze statusem 404)")
    elif o.status not in (404, 410):
        c["errors"].append(f"nieistniejący adres {sciezka} zwraca {opis(o.status)} zamiast 404")
    else:
        tekst = o.tekst()
        if "html" not in o.typ.lower() and not re.search(r"<html\b", tekst, re.I):
            c["warnings"].append("strona 404 bez własnej treści (pusta albo nie HTML)")
        elif not re.search(r"<title\b[^>]*>\s*\S", tekst, re.I):
            c["warnings"].append("strona 404 bez <title>")
        else:
            c["info"].append(f"strona 404: {sciezka} → HTTP {o.status}")


def check(html: str, url: str | None, *, podglad: bool = False, strona_404: bool = False) -> dict:
    return analizuj(html, url, podglad=podglad, strona_404=strona_404)[0]


# --------------------------------------------------------------------------------------------- cały build

def _trasa(rel: str) -> str:
    """index.html → /, oferta/index.html → /oferta/, kontakt.html → /kontakt."""
    if rel == "index.html" or rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel[: -len(".html")]


def _norm(sciezka: str) -> str:
    s = urllib.parse.unquote(sciezka)
    s = re.sub(r"(index)?\.html$", "", s)
    return s.rstrip("/")


def check_dir(katalog: Path | str, base_url: str | None = None, *, podglad: bool = False) -> dict:
    """Wszystkie strony katalogu buildu + kontrole całej witryny (unikalność, 404, robots, llms, sitemap)."""
    katalog = Path(katalog)
    w = {"errors": [], "warnings": [], "info": []}
    strony: list[dict] = []
    oczekiwany = urllib.parse.urlsplit(base_url).netloc.lower() if base_url else ""
    prefiks = urllib.parse.urlsplit(base_url).path.rstrip("/") if base_url else ""
    wartosci: dict[str, dict[str, list[str]]] = {"title": {}, "description": {}, "canonical": {}}
    trasy: dict[str, str] = {}

    for plik in sorted(katalog.rglob("*.html")):
        rel = plik.relative_to(katalog).as_posix()
        html = plik.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"<(html|head|body)\b", html, re.I):
            w["info"].append(f"{rel}: pominięty (nie strona HTML, np. plik weryfikacji)")
            continue
        jest_404 = rel == "404.html"
        r, p = analizuj(html, None, podglad=podglad, strona_404=jest_404)
        if any(m.get("http-equiv", "").lower() == "refresh" for m in p.meta):
            w["info"].append(f"{rel}: przekierowanie (meta refresh), pominięte")
            continue
        trasa = prefiks + _trasa(rel)

        kan = canonical_of(p)
        if bezwzgledny(kan):
            sp = urllib.parse.urlsplit(kan)
            if oczekiwany and sp.netloc.lower() != oczekiwany:
                r["head"]["errors"].append(f"canonical na hoście {sp.netloc}, a --base-url to {oczekiwany}")
            if not jest_404 and _norm(sp.path) != _norm(trasa):
                r["head"]["warnings"].append(f"canonical {sp.path!r} nie wskazuje tej strony ({trasa!r})")

        og = (meta_content(p, "og:image", "property") or "").strip()
        if bezwzgledny(og):
            sciezka = urllib.parse.unquote(urllib.parse.urlsplit(og).path)
            if prefiks and sciezka.startswith(prefiks + "/"):
                sciezka = sciezka[len(prefiks):]
            obraz = katalog / sciezka.lstrip("/")
            if not obraz.is_file():
                r["og"]["errors"].append(f"obraz OG {sciezka} nie istnieje w {katalog.name}/")
            else:
                ocen_obraz_og(obraz.read_bytes()[:2_000_000], mimetypes.guess_type(obraz.name)[0] or "", sciezka, r["og"])

        if not jest_404:
            trasy[rel] = trasa
            for klucz, wart in (("title", p.title), ("description", meta_content(p, "description")), ("canonical", kan)):
                wart = " ".join((wart or "").split())
                if wart:
                    wartosci[klucz].setdefault(wart, []).append(rel)
        r["summary"] = podsumuj(r)
        strony.append({"plik": rel, "trasa": trasa, **r})

    if not strony:
        w["errors"].append(f"brak stron .html w {katalog} (najpierw npm run build)")
    for klucz, mapa in wartosci.items():
        for wart, pliki in mapa.items():
            if len(pliki) > 1:
                w["errors"].append(f"ten sam {klucz} na {len(pliki)} stronach ({', '.join(pliki[:5])}): {wart[:90]!r}")

    if not (katalog / "404.html").is_file():
        w["errors"].append("brak 404.html (własna strona błędu: src/pages/404.astro)")
    robots = katalog / "robots.txt"
    if not robots.is_file():
        w["errors"].append("brak robots.txt (public/robots.txt)")
    else:
        ocen_robots(robots.read_text(encoding="utf-8", errors="replace"), w)
    llms = katalog / "llms.txt"
    if not llms.is_file():
        w["errors"].append("brak llms.txt (public/llms.txt, szablon: audyt-strony/references/widocznosc.md)")
    else:
        ocen_llms(llms.read_text(encoding="utf-8", errors="replace"), w)
    mapy = [m for m in sorted(katalog.glob("sitemap*.xml")) if jest_mapa(m.read_bytes())]
    if not mapy:
        w["errors"].append("brak sitemap (sitemap-index.xml z @astrojs/sitemap albo sitemap.xml) z <urlset>/<sitemapindex>")
    else:
        w["info"].append(f"sitemap: {', '.join(m.name for m in mapy)}")
        w_mapie = {_norm(urllib.parse.urlsplit(loc).path)
                   for m in mapy for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", m.read_text(encoding="utf-8", errors="replace"))}
        poza = [rel for rel, trasa in trasy.items() if _norm(trasa) not in w_mapie]
        if poza:
            w["warnings"].append(f"{len(poza)} stron poza sitemapą, np. {poza[:5]}")

    wynik = {"witryna": w, "strony": strony}
    wynik["summary"] = {"errors": len(w["errors"]) + sum(s["summary"]["errors"] for s in strony),
                        "warnings": len(w["warnings"]) + sum(s["summary"]["warnings"] for s in strony),
                        "strony": len(strony)}
    return wynik


# ------------------------------------------------------------------------------------------------- CLI

def _wypisz(r: dict, prefiks: str = "", poziomy=("errors", "warnings", "info")) -> None:
    for section in SEKCJE:
        for level in poziomy:
            for msg in r[section][level]:
                print(f"{prefiks}[{section}] {POZIOM[level]}: {msg}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="adres http(s) albo plik .html")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--base-url", help="adres strony: przy pliku włącza crawl i pobranie obrazu OG; "
                                       "przy --dir adres produkcyjny dla canonical")
    ap.add_argument("--podglad", action="store_true",
                    help="adres podglądu: noindex i canonical na domenie produkcyjnej to tylko info")
    ap.add_argument("--dir", help="katalog buildu (np. dist): wszystkie strony i kontrole całej witryny")
    args = ap.parse_args(argv)
    if bool(args.target) == bool(args.dir):
        ap.error("podaj adres albo plik .html, albo --dir <katalog buildu>")

    if args.dir:
        if not Path(args.dir).is_dir():
            ap.error(f"--dir: {args.dir} nie jest katalogiem")
        result = check_dir(Path(args.dir), args.base_url, podglad=args.podglad)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=1))
        else:
            for s in result["strony"]:
                if s["summary"]["errors"] or s["summary"]["warnings"]:
                    print(f"== {s['plik']} ({s['trasa']})")
                    _wypisz(s, poziomy=("errors", "warnings"))
            for level in ["errors", "warnings", "info"]:
                for msg in result["witryna"][level]:
                    print(f"[witryna] {POZIOM[level]}: {msg}")
            sm = result["summary"]
            print(f"PODSUMOWANIE: {sm['strony']} stron, {sm['errors']} błędów, {sm['warnings']} ostrzeżeń "
                  "(info dla stron: --json)")
        return 1 if result["summary"]["errors"] else 0

    if args.target.startswith("http"):
        o = pobierz(args.target)
        if o.status >= 400 or not o.status:
            print(json.dumps({"error": opis(o.status)}))
            return 1
        html, url = o.tekst(), o.url or args.target
    else:
        html = Path(args.target).read_text(encoding="utf-8", errors="replace")
        url = args.base_url
    result = check(html, url, podglad=args.podglad)
    if not (url and url.startswith("http")):
        result["crawl"]["info"].append(BEZ_SIECI)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        _wypisz(result)
        print(f"PODSUMOWANIE: {result['summary']['errors']} błędów, {result['summary']['warnings']} ostrzeżeń")
    return 1 if result["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

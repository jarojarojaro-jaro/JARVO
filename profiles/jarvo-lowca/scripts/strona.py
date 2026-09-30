#!/usr/bin/env python3
"""Strona firmy: kontakt, który firma sama opublikowała, kariera, technologia i odcisk strony (do wykrywania zmian).

    strona.py kontakt https://firma.pl [--max-stron 8] [--json]
    strona.py zmiana https://firma.pl --baza out/leady/<projekt>/strony.json     # czy strona zmieniła się od ostatniego razu

Tylko domena firmy: strona główna + podstrony kontakt / o nas / zespół / kariera / impressum / polityka prywatności.
Szanuje `robots.txt`, przedstawia się uczciwie (User-Agent jarvo-lowca), odmowa albo ochrona antybotowa = blokada.
Każdy e-mail i telefon ma adres strony, na której jest opublikowany, i krótki kontekst (np. „Anna Nowak, dyrektor
sprzedaży”). Adresów nie zgadujemy. Typ e-maila: ogolny (biuro@), rolowy (sprzedaz@), osobowy (imię, skrzynka darmowa).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402

PODSTRONY = re.compile(r"kontakt|contact|o-nas|onas|about|zesp[oó]ł|zespol|team|ludzie|people|kariera|career|praca|jobs|"
                       r"rekrutacja|impressum|firma|company|polityka-prywatno|privacy|rodo", re.I)
KARIERA = re.compile(r"kariera|career|praca|jobs|rekrutacja|dołącz|dolacz|join-us|joinus", re.I)
FORMULARZ = re.compile(r"<form\b[^>]*>(?:(?!</form>).){0,4000}?(?:e-?mail|wiadomo|message|telefon)", re.I | re.S)
SOCIAL = {"linkedin": r"linkedin\.com/(?:company|in|school)/[^\"'\s<>?#]+", "facebook": r"facebook\.com/[^\"'\s<>?#]+",
          "instagram": r"instagram\.com/[^\"'\s<>?#]+", "youtube": r"youtube\.com/(?:@|c/|channel/|user/)[^\"'\s<>?#]+",
          "x": r"(?:twitter|x)\.com/[A-Za-z0-9_]{2,}", "tiktok": r"tiktok\.com/@[^\"'\s<>?#]+"}
TECH = {  # sygnatury w HTML strony: nazwa → wzorzec
    "WordPress": r"wp-content/|wp-includes/", "WooCommerce": r"woocommerce", "Shopify": r"cdn\.shopify\.com|myshopify\.com",
    "PrestaShop": r"prestashop", "Magento": r"/static/version\d+/frontend/|Magento_[A-Z]|data-mage-init", "IdoSell": r"idosell|iai-shop|/gfx/pol/", "Shoper": r"shoper\.pl|storefront-shoper",
    "Wix": r"wixstatic\.com|_wixCIDX|wix\.com", "Webflow": r"webflow\.(?:com|io)", "Squarespace": r"squarespace", "Joomla": r"/media/jui/|joomla",
    "Drupal": r"drupal-settings-json|/sites/default/files", "Next.js": r"/_next/static", "Nuxt": r"/_nuxt/", "Astro": r"/_astro/",
    "Google Analytics 4": r"gtag/js\?id=G-", "Google Tag Manager": r"googletagmanager\.com/gtm\.js", "Google Ads": r"gtag/js\?id=AW-|googleadservices",
    "Meta Pixel": r"connect\.facebook\.net/[^\"']*/fbevents\.js|fbq\(", "TikTok Pixel": r"analytics\.tiktok\.com", "LinkedIn Insight": r"snap\.licdn\.com",
    "Hotjar": r"static\.hotjar\.com", "Microsoft Clarity": r"clarity\.ms", "HubSpot": r"js\.hs-scripts\.com|hs-analytics", "SALESmanago": r"salesmanago",
    "GetResponse": r"getresponse", "Mailchimp": r"chimpstatic\.com|list-manage\.com", "FreshMail": r"freshmail", "Tidio": r"tidio",
    "LiveChat": r"livechatinc\.com", "Smartsupp": r"smartsupp", "Intercom": r"intercom(?:cdn)?\.(?:io|com)", "Cookiebot": r"cookiebot",
    "CookieYes": r"cookieyes", "Booksy": r"booksy\.com", "Calendly": r"calendly\.com", "Przelewy24": r"przelewy24", "PayU": r"secure\.payu|payu\.com",
    "Stripe": r"js\.stripe\.com", "Tpay": r"tpay\.com", "reCAPTCHA": r"google\.com/recaptcha",
}


class Czytnik(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linki: list[tuple[str, str]] = []
        self.tekst: list[str] = []
        self._pomin = 0
        self._href: str | None = None
        self._atekst: list[str] = []
        self.tytul = ""
        self._w_tytule = False
        self.opis = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._pomin += 1
        elif tag == "a" and a.get("href"):
            self._href, self._atekst = a["href"], []
        elif tag == "title":
            self._w_tytule = True
        elif tag == "meta" and (a.get("name") or "").lower() == "description":
            self.opis = a.get("content") or ""
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "footer", "address"):
            self.tekst.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._pomin = max(0, self._pomin - 1)
        elif tag == "a" and self._href is not None:
            self.linki.append((self._href, " ".join(self._atekst).strip()))
            self._href = None
        elif tag == "title":
            self._w_tytule = False

    def handle_data(self, data):
        if self._pomin:
            return
        if self._w_tytule:
            self.tytul += data
        self.tekst.append(data)
        if self._href is not None:
            self._atekst.append(data.strip())


def czytaj(url: str) -> tuple[str, Czytnik]:
    kod, tresc = ll.http(url, pamiec_h=24, naglowki={"Accept": "text/html,application/xhtml+xml"})
    if kod != 200:
        raise ConnectionError(f"{url}: HTTP {kod}")
    c = Czytnik()
    c.feed(tresc)
    return tresc, c


def robots(start: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    u = urllib.parse.urlsplit(start)
    try:
        kod, tresc = ll.http(f"{u.scheme}://{u.netloc}/robots.txt", pamiec_h=24)
        rp.parse(tresc.splitlines() if kod == 200 else [])
    except (ConnectionError, ll.Blokada):
        rp.parse([])
    return rp


def kontekst(tekst: str, fraza: str, n: int = 70) -> str:
    i = tekst.find(fraza)
    if i < 0:
        return ""
    return re.sub(r"\s+", " ", tekst[max(0, i - n):i + len(fraza) + 25]).strip()


def odcisk(tekst: str) -> str:
    """Odcisk treści strony głównej: bez liczb i spacji (daty, liczniki, rok w stopce nie wywołują „zmiany”)."""
    norm = re.sub(r"\d+", "", re.sub(r"\s+", " ", tekst)).strip().lower()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def kontakt(start: str, max_stron: int = 8) -> dict:
    if "://" not in start:
        start = "https://" + start
    dom = ll.domena(start)
    rp = robots(start)
    wynik = {"domena": dom, "url": start, "tytul": "", "opis": "", "strony": [], "emaile": [], "telefony": [],
             "formularz": None, "kariera": None, "technologie": [], "nip": [], "social": {}, "odcisk": None,
             "pominiete_robots": [], "bledy": []}
    kolejka, widziane = [start], set()
    while kolejka and len(wynik["strony"]) < max_stron:
        url = kolejka.pop(0).split("#")[0]
        if url in widziane:
            continue
        widziane.add(url)
        if not rp.can_fetch(ll.UA, url):
            wynik["pominiete_robots"].append(url)
            continue
        try:
            surowy, c = czytaj(url)
        except ConnectionError as e:
            wynik["bledy"].append(str(e))
            continue
        wynik["strony"].append(url)
        tekst = html.unescape("".join(c.tekst))
        if url == start or not wynik["odcisk"]:
            wynik["tytul"], wynik["opis"], wynik["odcisk"] = c.tytul.strip(), c.opis.strip(), odcisk(tekst)
        mailto = [urllib.parse.unquote(h[7:].split("?")[0]) for h, _ in c.linki if h.lower().startswith("mailto:")]
        for e in ll.emaile(" ".join(mailto) + " " + tekst):
            if not any(x["email"] == e for x in wynik["emaile"]):
                wynik["emaile"].append({"email": e, "rodzaj": ll.typ_emaila(e), "zrodlo": url, "kontekst": kontekst(ll.odslon(tekst).lower(), e)})
        tel = [h[4:] for h, _ in c.linki if h.lower().startswith("tel:")]
        for t in ll.telefony(" ".join(tel) + " " + tekst):
            if not any(x["numer"] == t for x in wynik["telefony"]):
                wynik["telefony"].append({"numer": t, "zrodlo": url})
        if not wynik["formularz"] and FORMULARZ.search(surowy):
            wynik["formularz"] = url
        for nazwa, wz in TECH.items():
            if nazwa not in wynik["technologie"] and re.search(wz, surowy, re.I):
                wynik["technologie"].append(nazwa)
        for m in re.finditer(r"NIP[:\s]*([\d\s-]{10,16})", tekst):
            n = ll.nip(m.group(1))
            if n and n not in wynik["nip"]:
                wynik["nip"].append(n)
        for nazwa, wz in SOCIAL.items():
            if nazwa not in wynik["social"] and (m := re.search(wz, surowy, re.I)):
                wynik["social"][nazwa] = "https://" + m.group(0).rstrip("/\\")
        for href, atekst in c.linki:
            cel = urllib.parse.urljoin(url, href).split("#")[0]
            if ll.domena(cel) != dom or not cel.startswith("http") or re.search(r"\.(pdf|jpe?g|png|zip|docx?)$", cel, re.I):
                continue
            znacznik = urllib.parse.urlsplit(cel).path + " " + atekst
            if KARIERA.search(znacznik) and not wynik["kariera"]:
                wynik["kariera"] = cel
            if url == start and PODSTRONY.search(znacznik) and cel not in widziane and cel not in kolejka:
                kolejka.append(cel)
    return wynik


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("kontakt")
    s.add_argument("url")
    s.add_argument("--max-stron", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("zmiana")
    s.add_argument("url")
    s.add_argument("--baza", required=True, help="JSON: domena → odcisk z poprzedniego przebiegu (tworzony przy pierwszym)")
    a = ap.parse_args(argv)
    try:
        w = kontakt(a.url, getattr(a, "max_stron", 3) if a.cmd == "kontakt" else 1)
    except ll.Blokada as e:
        print(f"✗ blokada: {e}", file=sys.stderr)
        return 3
    if not w["strony"]:
        print(f"✗ {a.url}: nie udało się pobrać strony ({'; '.join(w['bledy'] or w['pominiete_robots']) or 'brak'})", file=sys.stderr)
        return 1
    if a.cmd == "zmiana":
        baza = Path(a.baza)
        stare = json.loads(baza.read_text(encoding="utf-8")) if baza.is_file() else {}
        poprzedni = stare.get(w["domena"])
        stare[w["domena"]] = w["odcisk"]
        baza.parent.mkdir(parents=True, exist_ok=True)
        baza.write_text(json.dumps(stare, ensure_ascii=False, indent=1), encoding="utf-8")
        stan = "pierwszy odczyt (baza)" if poprzedni is None else ("ZMIANA" if poprzedni != w["odcisk"] else "bez zmian")
        print(json.dumps({"domena": w["domena"], "stan": stan, "odcisk": w["odcisk"], "poprzedni": poprzedni}, ensure_ascii=False))
        return 0
    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=1))
        return 0
    print(f"{w['domena']} · {w['tytul'][:80]}")
    print(f"  strony: {len(w['strony'])}, technologie: {', '.join(w['technologie']) or '–'}, NIP: {', '.join(w['nip']) or '–'}")
    for e in w["emaile"]:
        print(f"  e-mail {e['email']} ({e['rodzaj']}) · {e['zrodlo']} · „{e['kontekst'][:90]}”")
    for t in w["telefony"][:5]:
        print(f"  tel. {t['numer']} · {t['zrodlo']}")
    print(f"  formularz: {w['formularz'] or '–'} · kariera: {w['kariera'] or '–'} · social: {', '.join(w['social']) or '–'}")
    if w["pominiete_robots"]:
        print(f"  pominięte (robots.txt): {len(w['pominiete_robots'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

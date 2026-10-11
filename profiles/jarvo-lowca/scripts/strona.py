#!/usr/bin/env python3
"""Strona firmy: kontakt, który firma sama opublikowała, kariera, technologia i odcisk strony (do wykrywania zmian).

    strona.py kontakt https://firma.pl [--max-stron 8] [--json]
    strona.py zmiana https://firma.pl --baza out/leady/<projekt>/strony.json     # czy strona zmieniła się od ostatniego razu
    strona.py kontakt https://firma.pl/kontakt --z-html strony/firma.html --json  # strona już przeczytana przez ostrozna.py

Tylko domena firmy: strona główna + podstrony kontakt / o nas / zespół / kariera / impressum / polityka prywatności.
Szanuje `robots.txt`, przedstawia się uczciwie (User-Agent jarvo-lowca), odmowa albo ochrona antybotowa = blokada.
Po blokadzie ochrony jedna strona może przyjść z zapasowej przeglądarki (skill `ostrozna-przegladarka`:
`ostrozna.py <url> --html -o plik.html`, robots.txt sprawdzony tam): `--z-html plik.html` analizuje tylko ją, bez sieci
i bez podstron, a wynik ma `"odczyt": "camoufox"`.
Każdy e-mail i telefon ma adres strony, na której jest opublikowany, i krótki kontekst (np. „Anna Nowak, dyrektor
sprzedaży”). Adresów nie zgadujemy. Typ e-maila: ogolny (biuro@), rolowy (sprzedaz@), osobowy (imię, skrzynka darmowa).

Dane ukryte w HTML: strona często ma w pierwszym HTML więcej, niż pokazuje (schema.org JSON-LD, `__NEXT_DATA__`,
dane Nuxt, strumień React Server Components). Skrypt czyta je bez przeglądarki: nazwa i adres firmy, telefon, e-mail,
NIP, profile społecznościowe. Każda taka wartość ma pole `skad` (json-ld | next-data | nuxt | rsc) i adres strony.
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

# dane ukryte w HTML: klucze, po których poznajemy pole (małe litery, bez - i _)
SKRYPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
RSC = re.compile(r'self\.__next_f\.push\(\[\s*\d+\s*,\s*("(?:[^"\\]|\\.)*")\s*\]\)')
K_TEL = {"tel", "telefon", "telephone", "phone", "phonenumber", "mobile", "mobilephone", "komorka", "numertelefonu"}
K_NIP = {"nip", "taxid", "vatid", "vat", "vatnumber", "taxnumber"}
K_TEKST = re.compile(r"""["']?(tel|telefon|telephone|phone|phoneNumber|mobile|nip|taxID|vatID)["']?\s*:\s*["']([^"'\n]{6,40})["']""", re.I)
TYPY_NIE_FIRMA = {"person", "website", "webpage", "breadcrumblist", "listitem", "imageobject", "searchaction", "sitenavigationelement",
                  "article", "blogposting", "faqpage", "question", "answer", "offer", "product", "review", "rating", "aggregaterating"}


# odstęp między elementami: przy szukaniu kontaktów spacja, w odcisku strony nic (odciski z bazy monitoringu zostają ważne)
ODSTEP = "\x1f"
BLOKI = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "footer", "address"}     # nowa linia jak dotąd
INLINE = {"a", "td", "th", "button", "label", "h5", "h6", "header", "ul", "ol", "dd", "dt"}
# numery z etykietą (REGON, KRS, NIP, BDO…) to nie telefony, choć mają 9–10 cyfr
IDENTYFIKATORY = re.compile(r"\b(?:REGON|KRS|NIP|VAT(?:[\s-]?(?:ID|UE|EU))?|BDO|EORI|PESEL)\b[\s:.#№-]*(?:[A-Z]{2})?[\d \t\u00a0-]{7,20}\d", re.I)


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
        if tag in BLOKI:
            self.tekst.append("\n")
        elif tag in INLINE:
            self.tekst.append(ODSTEP)

    def handle_endtag(self, tag):
        if tag in BLOKI or tag in INLINE:                   # „KRS: 0000745671</p><a>hello@…” nie skleja się w jeden adres
            self.tekst.append(ODSTEP)
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


def ladunki(surowy: str) -> list[tuple[str, object]]:
    """Dane ukryte w HTML: lista (skąd, dane). Dane to obiekt JSON albo tekst, gdy skrypt to JS, a nie JSON (Nuxt 2)."""
    out, rsc = [], []
    for m in SKRYPT.finditer(surowy):
        atr, tresc = m.group(1), m.group(2).strip()
        if "self.__next_f.push" in tresc:                       # React Server Components: kawałki tekstu w stringach JS
            for s in RSC.findall(tresc):
                try:
                    rsc.append(json.loads(s))
                except ValueError:
                    pass
            continue
        if re.search(r"application/ld\+json", atr, re.I):
            skad = "json-ld"
        elif re.search(r"""id=["']?__NEXT_DATA__""", atr):
            skad = "next-data"
        elif re.search(r"""id=["']?__NUXT_DATA__""", atr) or re.match(r"window\.__NUXT__\s*=", tresc):
            skad = "nuxt"
        else:
            continue
        tresc = re.sub(r"^(?://\s*)?<!\[CDATA\[|(?://\s*)?\]\]>$", "", tresc).strip()
        try:
            out.append((skad, json.loads(tresc)))
        except ValueError:
            out.append((skad, html.unescape(tresc)))
    if rsc:
        out.append(("rsc", "".join(rsc)))
    return out


def _adres(d: dict) -> str:
    kod_miasto = " ".join(s for s in (d.get("postalCode"), d.get("addressLocality")) if isinstance(s, str)).strip()
    return ", ".join(c.strip() for c in (d.get("streetAddress"), kod_miasto) if isinstance(c, str) and c.strip())


def zbierz_ukryte(dane: object, skad: str) -> dict:
    """Z jednego ładunku: e-maile (z kontekstem węzła), telefony, NIP, adres i nazwa firmy (JSON-LD), profile social.
    Telefon i NIP tylko spod kluczy, które je nazywają (phone, telephone, nip, taxID…) albo z `tel:`, bo w danych
    aplikacji jest pełno liczb, które tylko wyglądają jak numer."""
    z: dict = {"emaile": [], "telefony": [], "nip": [], "adres": None, "nazwa": None, "social": {}}

    def emaile(tekst: str, ktx: str) -> None:
        for e in ll.emaile(tekst.replace("mailto:", " ")):
            if all(e != x for x, _ in z["emaile"]):
                z["emaile"].append((e, ktx))

    def telefony(tekst: str) -> None:
        z["telefony"] += [t for t in ll.telefony(tekst) if t not in z["telefony"]]

    def nip(tekst: str) -> None:
        if (n := ll.nip(tekst)) and n not in z["nip"]:
            z["nip"].append(n)

    def social(tekst: str) -> None:
        for nazwa, wz in SOCIAL.items():
            if nazwa not in z["social"] and (m := re.search(wz, tekst, re.I)):
                z["social"][nazwa] = "https://" + m.group(0).rstrip("/\\")

    def pole(klucz: str, w: str, rodzic: object) -> None:
        k = re.sub(r"[-_\s]", "", klucz.lower())
        if "@" in w:
            ktx = ", ".join(rodzic[a] for a in ("name", "jobTitle", "contactType") if isinstance(rodzic, dict) and isinstance(rodzic.get(a), str))
            emaile(w, ktx[:120])
        if k in K_TEL or w.lower().startswith("tel:"):
            telefony(w[4:] if w.lower().startswith("tel:") else w)
        if k in K_NIP:
            nip(w)
        if skad == "json-ld" and k == "address" and not z["adres"]:
            z["adres"] = w.strip()
        if len(w) < 500:
            social(w)

    def wezel(x: object, klucz: str, rodzic: object) -> None:
        if isinstance(x, dict):
            if skad == "json-ld":
                typy = {t.lower() for t in (x.get("@type") if isinstance(x.get("@type"), list) else [x.get("@type")]) if isinstance(t, str)}
                if not z["adres"] and (x.get("streetAddress") or x.get("postalCode")):
                    z["adres"] = _adres(x) or None
                if (not z["nazwa"] and typy and not typy & (TYPY_NIE_FIRMA | {"postaladdress", "contactpoint"})
                        and any(a in x for a in ("telephone", "email", "address", "taxID", "vatID", "legalName"))):
                    z["nazwa"] = x.get("legalName") or x.get("name")
            for k, v in x.items():
                wezel(v, k, x)
        elif isinstance(x, list):
            for v in x:
                wezel(v, klucz, rodzic)
        elif isinstance(x, (str, int)) and not isinstance(x, bool):
            pole(klucz or "", str(x), rodzic)

    if isinstance(dane, str):                                     # JS albo uszkodzony JSON: tylko wzorce z kluczem
        emaile(dane, "")
        for m in K_TEKST.finditer(dane):
            (nip if m.group(1).lower() in ("nip", "taxid", "vatid") else telefony)(m.group(2))
        for m in re.finditer(r"tel:([+\d\s().-]{9,20})", dane):
            telefony(m.group(1))
        social(dane)
        return z
    if skad == "nuxt" and isinstance(dane, list):                 # Nuxt 3: płaska tablica, obiekt = {klucz: indeks wartości}
        for d in dane:
            if isinstance(d, dict):
                for k, i in d.items():
                    if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(dane) and isinstance(dane[i], (str, int)):
                        pole(k, str(dane[i]), d)
    wezel(dane, "", None)
    return z


def dolacz_ukryte(wynik: dict, z: dict, skad: str, url: str) -> None:
    """Dopisuje do wyniku strony to, czego nie było w widocznym tekście; `ukryte` mówi, co który ładunek zawierał."""
    pola, nowe = [], 0
    for e, ktx in z["emaile"]:
        pola.append("e-mail")
        if not any(x["email"] == e for x in wynik["emaile"]):
            wynik["emaile"].append({"email": e, "rodzaj": ll.typ_emaila(e), "zrodlo": url, "kontekst": ktx, "skad": skad})
            nowe += 1
    for t in z["telefony"]:
        pola.append("telefon")
        if not any(x["numer"] == t for x in wynik["telefony"]):
            wynik["telefony"].append({"numer": t, "zrodlo": url, "skad": skad})
            nowe += 1
    for n in z["nip"]:
        pola.append("NIP")
        if n not in wynik["nip"]:
            wynik["nip"].append(n)
            nowe += 1
    for nazwa, link in z["social"].items():
        pola.append("social")
        if nazwa not in wynik["social"]:
            wynik["social"][nazwa] = link
            nowe += 1
    for klucz in ("adres", "nazwa"):
        if z[klucz]:
            pola.append(klucz)
            if not wynik[klucz]:
                wynik[klucz] = {"tekst": z[klucz], "zrodlo": url, "skad": skad}
                nowe += 1
    if pola:
        wynik["ukryte"].append({"skad": skad, "zrodlo": url, "pola": sorted(set(pola)), "nowe": nowe})


def kontakt(start: str, max_stron: int = 8, z_html: str | None = None) -> dict:
    """z_html: HTML strony `start` przeczytanej już przez ostrozna.py (tylko ta strona, bez sieci)."""
    if "://" not in start:
        start = "https://" + start
    dom = ll.domena(start)
    rp = robots(start) if z_html is None else None
    wynik = {"domena": dom, "url": start, "tytul": "", "opis": "", "strony": [], "emaile": [], "telefony": [],
             "formularz": None, "kariera": None, "technologie": [], "nip": [], "social": {}, "odcisk": None,
             "nazwa": None, "adres": None, "ukryte": [], "pominiete_robots": [], "bledy": []}
    if z_html is not None:
        wynik["odczyt"], max_stron = "camoufox", 1
    kolejka, widziane = [start.split("#")[0]], set()
    while kolejka and len(wynik["strony"]) < max_stron:
        url = kolejka.pop(0).split("#")[0]
        if url in widziane:
            continue
        widziane.add(url)
        if rp is not None and not rp.can_fetch(ll.UA, url):
            wynik["pominiete_robots"].append(url)
            continue
        try:
            if z_html is not None:
                surowy, c = z_html, Czytnik()
                c.feed(surowy)
            else:
                surowy, c = czytaj(url)
        except ConnectionError as e:
            wynik["bledy"].append(str(e))
            continue
        wynik["strony"].append(url)
        caly = html.unescape("".join(c.tekst))
        tekst = caly.replace(ODSTEP, " ")
        if url == start or not wynik["odcisk"]:
            wynik["tytul"], wynik["opis"], wynik["odcisk"] = c.tytul.strip(), c.opis.strip(), odcisk(caly.replace(ODSTEP, ""))
        mailto = [urllib.parse.unquote(h[7:].split("?")[0]) for h, _ in c.linki if h.lower().startswith("mailto:")]
        for e in ll.emaile(" ".join(mailto) + " " + tekst):
            if not any(x["email"] == e for x in wynik["emaile"]):
                wynik["emaile"].append({"email": e, "rodzaj": ll.typ_emaila(e), "zrodlo": url, "kontekst": kontekst(ll.odslon(tekst).lower(), e)})
        tel = [h[4:] for h, _ in c.linki if h.lower().startswith("tel:")]
        for t in ll.telefony(" ".join(tel) + " " + IDENTYFIKATORY.sub(" ", tekst)):
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
        for skad, dane in ladunki(surowy):
            dolacz_ukryte(wynik, zbierz_ukryte(dane, skad), skad, url)
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
    s.add_argument("--z-html", metavar="PLIK", help="HTML tej strony z ostrozna.py --html (bez sieci, bez podstron)")
    s = sub.add_parser("zmiana")
    s.add_argument("url")
    s.add_argument("--baza", required=True, help="JSON: domena → odcisk z poprzedniego przebiegu (tworzony przy pierwszym)")
    a = ap.parse_args(argv)
    z_html = None
    if getattr(a, "z_html", None):
        z_html = Path(a.z_html).read_text(encoding="utf-8", errors="replace")
    try:
        w = kontakt(a.url, getattr(a, "max_stron", 3) if a.cmd == "kontakt" else 1, z_html=z_html)
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
    if w["adres"]:
        print(f"  adres: {w['adres']['tekst']} · {w['adres']['skad']} · {w['adres']['zrodlo']}")
    for u in w["ukryte"]:
        print(f"  dane ukryte ({u['skad']}) · {u['zrodlo']}: {', '.join(u['pola'])}; nowe wartości: {u['nowe']}")
    if w["pominiete_robots"]:
        print(f"  pominięte (robots.txt): {len(w['pominiete_robots'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

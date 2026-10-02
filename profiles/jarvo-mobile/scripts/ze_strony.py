#!/usr/bin/env python3
"""Strona firmy → plan aplikacji: treści, dane firmy, sygnały funkcji i funkcje natywne, które dadzą więcej niż strona.

    ze_strony.py analizuj <url> [--strony 12] [--out out/ze-strony/<domena>]

Czyta stronę główną i do `--strony` podstron z menu (ten sam host, robots.txt, pauzy jak w audycie): nazwę, opis,
logo, kolor marki (meta `theme-color`, manifest, CSS), kontakt (telefon, e-mail, adres, godziny z JSON-LD),
media społecznościowe, politykę prywatności, menu strony, formularze i sygnały: rezerwacje, sklep, karta stałego
klienta, menu / cennik z cenami, blog, wydarzenia, dojazd. Z sygnałów robi propozycję funkcji natywnych
(przypomnienia, karta z kodem QR, oferta offline, zadzwoń i nawiguj, Universal Links ze strony…) i ekranów.

Wynik w `--out`:
- `ze-strony.json` (wszystko, z adresem źródła przy każdej informacji);
- `PLAN-ZE-STRONY.md` (dla właściciela i agenta: ekrany, funkcje natywne, ryzyko 4.2, prace dla Weba);
- `aplikacja.yaml` (dla `aplikacja.py nowa`);
- `zgodnosc.yaml` (dla `zgodnosc.py`; powody uprawnień z JARVO-TODO, bo pisze je człowiek albo agent, nie heurystyka);
- `tresci.json` (pozycje oferty z cenami do zasiania ekranów).

Mniej niż 3 funkcje natywne z mocnym sygnałem = ryzyko odrzucenia za „przepakowaną stronę” (Apple 4.2): plan każe
wrócić do `natywna-czy-pwa`. Kod: 0 = OK, 1 = strona nie odpowiada, 3 = robots.txt zabrania.
"""

from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402

SYGNALY = {   # sygnał → wzorzec w tekście albo adresach strony
    "rezerwacje": r"rezerwac|umów (się|wizyt)|umow wizyt|zarezerwuj|booksy|moment\.pl|versum|termin wizyty|book now|zapisy",
    "sklep": r"koszyk|do koszyka|zamów online|sklep internetowy|checkout|dostaw[ay] do domu|płatność online",
    "zamowienia": r"zamów (online|teraz|z dostawą)|pyszne\.pl|wolt\.com|glovo|uber ?eats|na wynos",
    "lojalnosc": r"karta stałego klienta|program lojalnościow|pieczątk|punkty za zakupy|karta podarunkow|bon podarunkowy",
    "menu": r"\bmenu\b|karta dań|nasze dania|pizze|desery|cennik|cena|zł\b",
    "wydarzenia": r"wydarzeni|warsztat|zajęcia|grafik|harmonogram|kalendarz",
    "blog": r"\bblog\b|aktualności|nowości|artykuł",
    "lokale": r"nasze (lokale|salony|sklepy|punkty|cukiernie|restauracje|kawiarnie|piekarnie)|lokalizacj|znajdź (nas|salon|sklep|cukierni)|"
              r"dojazd|\bmapa\b|sieć (cukierni|sklepów|salonów|restauracji|kawiarni|piekarni)|punkty sprzedaży",
    "na_zamowienie": r"na zamówienie|zamów tort|zamówienia (tortów|okolicznościowe|świąteczne)|tort(y)? weselne|catering",
    "konto": r"zaloguj|moje konto|rejestracja|załóż konto",
    "newsletter": r"newsletter|zapisz się",
}
# funkcja natywna: (sygnały, które ją uzasadniają, opis dla właściciela, moduły, uprawnienie z profilu zgodności)
FUNKCJE = [
    ("przypomnienia", ["rezerwacje", "wydarzenia"], "przypomnienie o wizycie / zajęciach dzień wcześniej (powiadomienie lokalne, bez serwera)",
     ["expo-notifications"], "powiadomienia"),
    ("kalendarz", ["rezerwacje", "wydarzenia"], "dodanie wizyty albo wydarzenia do kalendarza telefonu", ["expo-calendar"], "kalendarz"),
    ("karta-qr", ["lojalnosc"], "karta stałego klienta z kodem QR w telefonie (i w Wallet), pieczątki bez papieru", [], None),
    ("oferta-offline", ["menu", "sklep"], "oferta / menu / cennik dostępne bez internetu (pamięć urządzenia)", [], None),
    ("powiadomienia-promocje", ["sklep", "zamowienia", "newsletter", "blog"], "powiadomienia o nowościach i promocjach (za zgodą, z ustawieniem w aplikacji)",
     ["expo-notifications"], "powiadomienia"),
    ("zadzwon-nawiguj", ["lokale"], "„Zadzwoń” i „Nawiguj” jednym dotknięciem, najbliższy lokal", [], None),
    ("ponow-zamowienie", ["zamowienia", "sklep"], "„Zamów jeszcze raz” ostatnie zamówienie (wymaga backendu zamówień)", [], None),
    ("zamowienie-ze-zdjeciem", ["na_zamowienie"], "zamówienie na wydarzenie (tort, catering): data odbioru, zdjęcie inspiracji z galerii, "
     "przypomnienie o odbiorze", ["expo-image-picker", "expo-notifications"], "zdjecia"),
    ("linki-ze-strony", [], "linki ze strony otwierają aplikację (Universal Links / App Links; pliki .well-known od Weba)", [], None),
]
GLOWNE_SYGNALY = {"rezerwacje", "sklep", "zamowienia", "lojalnosc", "wydarzenia", "na_zamowienie", "lokale"}
PROG_MOCNY = {"wydarzenia": 3, "zamowienia": 2, "sklep": 2}   # pojedyncze słowo bywa w stopce albo na jednej podstronie
WEZWANIA = re.compile(r"^(zobacz|sprawdź|sprawdz|zapraszamy|zamów teraz|kliknij|dowiedz się więcej|czytaj więcej)\W*$", re.I)
STREFA_MENU = re.compile(r"(^|[\s_-])(menu|nav|navbar|navigation|sidenav|nawigacja)([\s_-]|$)", re.I)
TELEFON = re.compile(r"(?<![\d+])(?:\+48[\s-]?)?(?:\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\d{3}[\s-]\d{3}[\s-]\d{3})(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
OZDOBNIKI = re.compile("[\U0001F000-\U0001FAFF\u2190-\u21FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]+")
POMIN_LINKI = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|docx?|xlsx?|mp4)(\?|$)|mailto:|tel:|javascript:|#$|/wp-admin|/feed|/tag/|/author/", re.I)
CENA = re.compile(r"(\d{1,4}(?:[ ,.]\d{2})?)\s?(zł|pln)\b", re.I)
# domyślne kolory frameworków i CMS-ów: nie są kolorem marki
DOMYSLNE_KOLORY = {"#337AB7", "#286090", "#23527C", "#5BC0DE", "#5CB85C", "#F0AD4E", "#D9534F", "#31B0D5", "#2E6DA4",
                   "#007BFF", "#0D6EFD", "#6C757D", "#28A745", "#198754", "#DC3545", "#FFC107", "#17A2B8", "#0DCAF0",
                   "#6610F2", "#6F42C1", "#E83E8C", "#D63384", "#FD7E14", "#20C997", "#0073AA", "#2271B1", "#135E96",
                   "#0000EE", "#551A8B", "#3498DB", "#2196F3", "#4CAF50", "#F44336", "#FF5722", "#9C27B0", "#3F51B5"}
PRIORYTET_LINKOW = re.compile(r"kontakt|contact|o-nas|about|oferta|menu|cennik|karta|lokal|salon|sklepy|cukierni|restauracj|"
                              r"punkty|godzin|zamow|zamów|rezerw|umow|umów|uslug|usług|produkt", re.I)
KOLOR_CSS = re.compile(r"(?:--(?:primary|brand|main|accent|color-primary)[\w-]*|background(?:-color)?)\s*:\s*(#[0-9a-fA-F]{6})\b")


class Strona(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tytul, self.meta, self.linki, self.link_rel, self.jsonld = "", {}, [], {}, []
        self.tekst: list[str] = []
        self.obrazy: list[tuple[str, str]] = []
        self.formularze = 0
        self.style: list[str] = []
        self._w = None
        self._a: list | None = None
        self._nav = 0
        self._strefa: list | None = None          # [tag, głębokość]: menu bez <nav> (div#menu, ul.menu-main)
        self.nav: list[tuple[str, str]] = []
        self.nav_poziom: list[int] = []            # zagnieżdżenie list (ul/ol) przy pozycji menu: podkategorie głębiej
        self._listy = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("ul", "ol"):
            self._listy += 1
        if self._strefa and tag == self._strefa[0]:
            self._strefa[1] += 1
        elif not self._strefa and tag in ("div", "ul", "ol") and STREFA_MENU.search(a.get("class", "") + " " + a.get("id", "")):
            self._strefa = [tag, 1]
        if tag == "title":
            self._w = "title"
        elif tag == "meta":
            k = (a.get("name") or a.get("property") or "").lower()
            if k:
                self.meta[k] = a.get("content", "")
        elif tag == "link":
            for r in a.get("rel", "").lower().split():
                self.link_rel.setdefault(r, []).append(a.get("href", ""))
        elif tag == "a":
            self._a = [a.get("href", ""), ""]
        elif tag == "img":
            self.obrazy.append((a.get("src", ""), (a.get("alt", "") + " " + a.get("class", "") + " " + a.get("id", "")).lower()))
        elif tag == "form":
            self.formularze += 1
        elif tag in ("nav", "header"):
            self._nav += 1
        elif tag == "script" and "ld+json" in a.get("type", ""):
            self._w = "jsonld"
        elif tag == "style":
            self._w = "style"
        elif tag in ("script", "noscript"):
            self._w = "pomin"

    def handle_endtag(self, tag):
        if tag in ("ul", "ol") and self._listy:
            self._listy -= 1
        if self._strefa and tag == self._strefa[0]:
            self._strefa[1] -= 1
            if not self._strefa[1]:
                self._strefa = None
        if tag == "a" and self._a is not None:
            href, tekst = self._a[0], " ".join(self._a[1].split())
            self.linki.append((href, tekst))
            if (self._nav or self._strefa) and tekst and all(h != href for h, _ in self.nav):
                self.nav.append((href, tekst))
                self.nav_poziom.append(self._listy)
            self._a = None
        elif tag in ("nav", "header") and self._nav:
            self._nav -= 1
        elif tag in ("title", "script", "style", "noscript"):
            self._w = None

    def handle_data(self, d):
        if self._w == "title":
            self.tytul += d
        elif self._w == "jsonld":
            self.jsonld.append(d)
        elif self._w == "style":
            self.style.append(d)
        elif self._w == "pomin":
            return
        else:
            if self._a is not None:
                self._a[1] += d
            if d.strip():
                self.tekst.append(d.strip())


def _jsonld(bloki: list[str]) -> list[dict]:
    out = []
    for b in bloki:
        try:
            d = json.loads(b)
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict):
                out.append(x)
    return out


def _firma_z_jsonld(obiekty: list[dict]) -> dict:
    for o in obiekty:
        typ = o.get("@type")
        typy = typ if isinstance(typ, list) else [typ]
        if any(t and t not in ("WebSite", "WebPage", "BreadcrumbList", "SearchAction", "ImageObject") for t in typy):
            adr = o.get("address") or {}
            if isinstance(adr, list):
                adr = adr[0] if adr else {}
            godziny = o.get("openingHours") or [
                f"{','.join(s.get('dayOfWeek') if isinstance(s.get('dayOfWeek'), list) else [str(s.get('dayOfWeek', ''))])} "
                f"{s.get('opens', '')}–{s.get('closes', '')}"
                for s in (o.get("openingHoursSpecification") or []) if isinstance(s, dict)]
            return {"nazwa": o.get("name"), "typ": typy[0], "telefon": o.get("telephone"), "email": o.get("email"),
                    "adres": ", ".join(str(adr.get(k)) for k in ("streetAddress", "postalCode", "addressLocality") if adr.get(k))
                    if isinstance(adr, dict) else str(adr),
                    "godziny": godziny if isinstance(godziny, list) else [godziny], "logo": (o.get("logo") or {}).get("url")
                    if isinstance(o.get("logo"), dict) else o.get("logo")}
    return {}


def _nasycenie(hex_: str) -> tuple[float, float]:
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    return (0.0 if mx == 0 else (mx - mn) / mx), mx


def kolor_z_css(glowna: "Strona", baza: str, host: str) -> str | None:
    """Najczęstszy wyraźny kolor (nasycony, nie prawie czarny ani biały) ze stylów strony i do 2 arkuszy CSS hosta."""
    css = " ".join(glowna.style)
    for href in (glowna.link_rel.get("stylesheet") or [])[:2]:
        u = urllib.parse.urljoin(baza, href)
        if urllib.parse.urlsplit(u).netloc == host:
            try:
                css += " " + ml.pobierz(u, roboty=True, max_mb=2).tresc
            except (ConnectionError, ml.Blokada):
                pass
    return _dominujacy(css)


def _dominujacy(tekst: str) -> str | None:
    licz: dict[str, int] = {}
    for k in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", tekst):
        k = "#" + (k if len(k) == 6 else "".join(c * 2 for c in k)).upper()
        nas, jas = _nasycenie(k)
        if nas >= 0.35 and 0.25 <= jas <= 0.95 and k not in DOMYSLNE_KOLORY:
            licz[k] = licz.get(k, 0) + 1
    return max(licz, key=licz.get) if licz else None


def kolor_z_logo(logo: str | None) -> str | None:
    """Kolor marki z logo SVG (wypełnienia i obrysy): najpewniejsze źródło, gdy strona nie ma theme-color."""
    if not logo or not re.search(r"\.svg(\?|$)", logo, re.I):
        return None
    try:
        return _dominujacy(ml.pobierz(logo, roboty=True, max_mb=2).tresc)
    except (ConnectionError, ml.Blokada):
        return None


def czytaj(url: str) -> tuple[Strona, ml.Odpowiedz]:
    odp = ml.pobierz(url, roboty=True)
    if odp.kod >= 400:
        raise ConnectionError(f"{url}: HTTP {odp.kod}")
    s = Strona()
    s.feed(odp.tresc)
    return s, odp


def analizuj(url: str, max_stron: int = 12) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    glowna, odp = czytaj(url)
    baza = odp.url
    host = urllib.parse.urlsplit(baza).netloc
    strony = {baza: glowna}
    kolejka: list[str] = []
    teksty: dict[str, str] = {}
    for href, tekst in glowna.nav + glowna.linki:
        u = urllib.parse.urljoin(baza, href).split("#")[0]
        if urllib.parse.urlsplit(u).netloc == host and not POMIN_LINKI.search(u) and u not in kolejka and u.rstrip("/") != baza.rstrip("/"):
            kolejka.append(u)
            teksty[u] = tekst
    # najpierw kontakt, oferta, lokale, zamówienia (tam są dane firmy), potem reszta w kolejności strony
    kolejka.sort(key=lambda u: (not PRIORYTET_LINKOW.search(urllib.parse.urlsplit(u).path + " " + teksty.get(u, "")),
                                u.count("/")))
    bledy = []
    for u in kolejka[:max_stron]:
        try:
            strony[u] = czytaj(u)[0]
        except (ConnectionError, ml.Blokada) as e:
            bledy.append(f"{u}: {e}")
    # dane firmy
    obiekty = [o for s in strony.values() for o in _jsonld(s.jsonld)]
    firma = _firma_z_jsonld(obiekty)
    tekst_calosci = " \n".join(" ".join(s.tekst) for s in strony.values())
    linki = [(urllib.parse.urljoin(baza, h), t) for s in strony.values() for h, t in s.linki]
    # kontakt firmy: ze strony „Kontakt”, potem z głównej, potem z reszty; sieć lokali (dziesiątki numerów) osobno
    def kontakty(s: "Strona") -> tuple[list[str], list[str]]:
        tel = [re.sub(r"[^\d+]", "", h[4:]) for h, _ in s.linki if h.startswith("tel:")] or \
            [re.sub(r"[^\d+]", "", t) for t in TELEFON.findall(" ".join(s.tekst))]
        mail = [urllib.parse.unquote(h[7:].split("?")[0]) for h, _ in s.linki if h.startswith("mailto:")] or \
            [e for e in EMAIL.findall(" ".join(s.tekst)) if not re.search(r"\.(png|jpe?g|svg|webp)$", e, re.I)]
        return [t for t in dict.fromkeys(tel) if len(re.sub(r"\D", "", t)) >= 9], list(dict.fromkeys(mail))
    kolejnosc = sorted(strony, key=lambda u: (not re.search(r"kontakt|contact", u, re.I), u != baza))
    telefony: list[str] = [re.sub(r"[^\d+]", "", firma["telefon"])] if firma.get("telefon") else []
    emaile: list[str] = [firma["email"]] if firma.get("email") else []
    wszystkie_tel: list[str] = []
    for u in kolejnosc:
        t, m = kontakty(strony[u])
        wszystkie_tel += [x for x in t if x not in wszystkie_tel]
        if len(t) <= 4:                                 # strona z kilkoma numerami = kontakt; z dziesiątkami = lista lokali
            telefony += [x for x in t if x not in telefony]
        emaile += [x for x in m if x not in emaile]
    telefony, emaile = telefony[:3], emaile[:3]
    lokale_tel = wszystkie_tel if len(wszystkie_tel) > 4 else []
    spolecznosci = sorted({h for h, _ in linki if re.search(r"facebook\.com|instagram\.com|tiktok\.com|youtube\.com|linkedin\.com", h)})
    prywatnosc = next((h for h, t in linki if re.search(r"prywatno|privacy|rodo", h + " " + t, re.I)), None)
    # marka
    kolor = glowna.meta.get("theme-color") or None
    manifest_url = urllib.parse.urljoin(baza, glowna.link_rel["manifest"][0]) if glowna.link_rel.get("manifest") else None
    if manifest_url and not kolor:
        try:
            m = ml.json_z(manifest_url)
            kolor = (m or {}).get("theme_color") if isinstance(m, dict) else None
        except (ConnectionError, ml.Blokada):
            pass

    logo = firma.get("logo") or next((urllib.parse.urljoin(baza, src) for src, opis in glowna.obrazy if "logo" in opis or "logo" in src.lower()), None)
    if not logo:
        ikony = glowna.link_rel.get("apple-touch-icon") or glowna.link_rel.get("icon")
        logo = urllib.parse.urljoin(baza, ikony[0]) if ikony else None
    if kolor and kolor.upper() in DOMYSLNE_KOLORY:
        kolor = None
    kolor = kolor or kolor_z_logo(logo) or kolor_z_css(glowna, baza, host)
    # sygnały
    sygnaly = {}
    for nazwa, wz in SYGNALY.items():
        traf = [m.group(0) for m in re.finditer(wz, tekst_calosci + " " + " ".join(h for h, _ in linki), re.I)]
        if traf:
            sygnaly[nazwa] = {"trafien": len(traf), "przyklad": traf[0]}
    # oferta z cenami
    pozycje = []
    for s_url, s in strony.items():
        for i, fragment in enumerate(s.tekst):
            m = CENA.search(fragment)
            if m and i > 0:
                nazwa = fragment[:m.start()].strip(" :–-") or s.tekst[i - 1]
                if 2 < len(nazwa) <= 80 and not CENA.search(nazwa):
                    pozycje.append({"nazwa": " ".join(nazwa.split()), "cena": m.group(0), "zrodlo": s_url})
    pozycje = list({p["nazwa"]: p for p in pozycje}.values())[:60]
    if len(pozycje) >= 5:
        sygnaly.setdefault("menu", {"trafien": len(pozycje), "przyklad": pozycje[0]["nazwa"]})
    # funkcje natywne
    mocne_sygnaly = {k for k, v in sygnaly.items() if k in GLOWNE_SYGNALY and v["trafien"] >= PROG_MOCNY.get(k, 1)}
    funkcje = []
    for nazwa, potrzebne, opis, moduly, uprawnienie in FUNKCJE:
        uzasadnienie = [x for x in potrzebne if x in sygnaly]
        if nazwa == "linki-ze-strony" or uzasadnienie:
            mocna = bool(set(uzasadnienie) & mocne_sygnaly) or (nazwa == "oferta-offline" and len(pozycje) >= 5)
            funkcje.append({"funkcja": nazwa, "opis": opis, "sygnaly": uzasadnienie, "moduly": moduly, "uprawnienie": uprawnienie,
                            "mocna": mocna})
    mocne = [f for f in funkcje if f["mocna"]]
    ekrany = [{"trasa": "/", "tytul": "Start", "zawartosc": "najważniejsza akcja (" + (", ".join(sorted(mocne_sygnaly)) or "kontakt") + "), godziny, nowości"}]
    # ekrany z pozycji menu najwyższego poziomu; podkategorie (głębsze listy) jako zawartość ekranu nadrzędnego
    gora = min(glowna.nav_poziom, default=0)
    for i, (href, tekst) in enumerate(glowna.nav[:40]):
        t, adres = tekst.lower(), urllib.parse.urljoin(baza, href).split("#")[0]
        if glowna.nav_poziom[i] > gora or len(ekrany) >= 7:
            continue
        if re.search(r"kontakt|o nas|polityk|regulamin|blog|kariera|praca|strona główna|^start$|home|"
                     r"^(en|pl|de|ua|uk|ru|cz|english|deutsch|polski|українська)$", t) or not tekst.strip() \
                or adres.rstrip("/") == baza.rstrip("/") or urllib.parse.urlsplit(adres).netloc != host:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", ml_ascii(t)).strip("-")[:24]
        if not slug or any(e["trasa"] == f"/{slug}" for e in ekrany):
            continue
        pod = []
        for j in range(i + 1, len(glowna.nav)):
            if glowna.nav_poziom[j] <= gora:
                break
            pod.append(glowna.nav[j][1])
        ekrany.append({"trasa": f"/{slug}", "tytul": tekst.strip()[:30],
                       "zawartosc": (f"kategorie: {', '.join(pod[:6])}{'…' if len(pod) > 6 else ''}; " if pod else "") + f"treść z {adres}"})
    domena = host.removeprefix("www.")
    nazwa_firmy = (firma.get("nazwa") or glowna.meta.get("og:site_name")
                   or " ".join(glowna.tytul.split()).split(" | ")[0].split(" – ")[0].split(" - ")[0][:40])
    return {"url": url, "url_koncowy": baza, "data": ml.DZIS.isoformat(), "stron": len(strony), "bledy": bledy,
            "nazwa": nazwa_firmy,
            "opis": czysty_opis(glowna.meta.get("description") or glowna.meta.get("og:description") or "", nazwa=nazwa_firmy),
            "firma": {**firma, "telefony": telefony, "emaile": emaile, "prywatnosc": prywatnosc and urllib.parse.urljoin(baza, prywatnosc)},
            "marka": {"kolor": kolor, "logo": logo, "manifest": manifest_url},
            "spolecznosci": spolecznosci, "menu_strony": [{"tekst": t, "adres": urllib.parse.urljoin(baza, h)} for h, t in glowna.nav[:20]],
            "formularze": sum(s.formularze for s in strony.values()), "sygnaly": sygnaly, "pozycje": pozycje,
            "lokale_telefony": lokale_tel[:400],
            "funkcje": funkcje, "mocnych_funkcji": len(mocne), "ryzyko_4_2": len(mocne) < 3, "ekrany": ekrany[:8],
            "domena": domena, "bundle": ".".join(reversed(domena.split("."))) + ".app" if domena else ""}


def czysty_opis(t: str, limit: int = 120, nazwa: str = "") -> str:
    """Opis z meta SEO: strzałki, ptaszki i emoji to granice zdań; bez nazwy firmy na początku i bez „Zobacz!”."""
    zdania = []
    for z in OZDOBNIKI.split(t):
        z = " ".join(z.split()).strip(" -–|:,")
        if nazwa and z.lower().startswith(nazwa.lower()):
            z = z[len(nazwa):].strip(" -–|:,")
        if z and not WEZWANIA.match(z):
            zdania.append(z[:1].upper() + z[1:])
    t = ". ".join(x.rstrip(".") if not x.endswith(("!", "?")) else x for x in zdania)
    if t and t[-1] not in ".!?…":
        t += "."
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(",;:-–") + "…"
    return t


def ml_ascii(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode().lower()


def aplikacja_yaml(r: dict) -> str:
    f = r["firma"]
    nazwa = (r["nazwa"] or r["domena"])[:30]
    slug = re.sub(r"[^a-z0-9]+", "-", ml_ascii(nazwa)).strip("-")[:30] or "aplikacja"
    bundle = re.sub(r"[^a-z0-9.]", "", r["bundle"].lower().replace("-", ""))
    kolor = r["marka"]["kolor"] if re.fullmatch(r"#[0-9a-fA-F]{6}", r["marka"]["kolor"] or "") else "#2F5BEA"
    def q(v):
        return json.dumps(v or "", ensure_ascii=False)

    def brak(v, co: str) -> str:
        return "" if v else f"   # JARVO-TODO: {co}; strona go nie podaje"
    return f"""# Z `ze_strony.py analizuj {r['url']}` ({r['data']}): sprawdź każde pole, zanim powstanie aplikacja.
nazwa: {q(nazwa)}
slug: {slug}
bundle: {bundle}                  # nie do zmiany po pierwszym wgraniu
opis: {q((r['opis'] or '')[:120])}
kolor_glowny: {q(kolor)}{'' if r['marka']['kolor'] else '   # JARVO-TODO: kolor marki nie znaleziony na stronie (brand kit?)'}
wlasciciel_expo: ""
firma:
  nazwa: {q(f.get('nazwa') or nazwa)}
  adres: {q(f.get('adres'))}{brak(f.get('adres'), 'adres firmy (karta sklepu, DSA)')}
  email: {q((f.get('emaile') or [''])[0])}{brak(f.get('emaile'), 'e-mail firmy, wymagany przez sklepy i RODO (od właściciela)')}
  telefon: {q((f.get('telefony') or [''])[0])}{brak(f.get('telefony'), 'telefon firmy (od właściciela)')}
  strona: {q(r['url_koncowy'].rstrip('/'))}
  prywatnosc_url: {q(f.get('prywatnosc'))}
  usuwanie_konta_url: ""
"""


def zgodnosc_yaml(r: dict) -> str:
    uprawnienia = sorted({f["uprawnienie"] for f in r["funkcje"] if f["uprawnienie"] and f["mocna"]})
    powody = "\n".join(f"  {u}: \"JARVO-TODO: konkretny polski powód z nazwą funkcji (≥ 40 znaków)\"" for u in uprawnienia
                       if u not in ("powiadomienia",))
    platnosci = (["fizyczne"] if "sklep" in r["sygnaly"] or "zamowienia" in r["sygnaly"] else []) + \
        (["uslugi"] if "rezerwacje" in r["sygnaly"] else [])
    return f"""# Szkic profilu zgodności z `ze_strony.py` ({r['data']}): decyzje należą do właściciela, sprawdź każde pole.
logowanie: []                 # konto tylko, gdy funkcja go naprawdę wymaga (Apple 5.1.1(v): katalog bez logowania)
platnosci: {json.dumps(platnosci)}
tresci_uzytkownikow: false
ai: false
uprawnienia: {json.dumps(uprawnienia)}
powody:
{powody or '  {}'}
branza: zwykla
tablet: false
"""


def plan_md(r: dict) -> str:
    l = [f"# {r['nazwa']}: aplikacja ze strony {r['url_koncowy']}", "",
         f"Przeczytano {r['stron']} stron ({r['data']}). Sygnały: " +
         (", ".join(f"{k} ({v['trafien']})" for k, v in r["sygnaly"].items()) or "brak"), ""]
    if r["ryzyko_4_2"]:
        l += [f"> ⚠ Tylko {r['mocnych_funkcji']} funkcje natywne z mocnym sygnałem. Aplikacja, która powtarza stronę, odpada "
              "w recenzji Apple (4.2). Najpierw `natywna-czy-pwa`: PWA albo karta w Wallet mogą wystarczyć.", ""]
    l += ["## Funkcje natywne (więcej niż strona)", "", "| Funkcja | Dlaczego | Moduły | Sygnał |", "|---|---|---|---|"]
    l += [f"| {f['funkcja']}{' ★' if f['mocna'] else ''} | {f['opis']} | {', '.join(f['moduly']) or '—'} | "
          f"{', '.join(f['sygnaly']) or 'zawsze'} |" for f in r["funkcje"]]
    l += ["", "★ = mocny sygnał ze strony. Bez ★ tylko, gdy właściciel potwierdzi potrzebę.", "",
          "## Ekrany", "", "| Trasa | Tytuł | Zawartość |", "|---|---|---|"]
    l += [f"| `{e['trasa']}` | {e['tytul']} | {e['zawartosc']} |" for e in r["ekrany"]]
    l += ["| `/wiecej` | Więcej | kontakt, prywatność, strona (szablon) |", "",
          "## Treści", f"- pozycje oferty z cenami: {len(r['pozycje'])} (`tresci.json`)",
          f"- kontakt: {', '.join(r['firma']['telefony'] + r['firma']['emaile']) or 'nie znaleziono'}; adres: {r['firma'].get('adres') or '—'}",
          f"- lokale (sieć): {len(r['lokale_telefony'])} numerów (`tresci.json`, do ekranu „Znajdź lokal”)" if r["lokale_telefony"] else "- lokale: jeden adres",
          f"- godziny: {'; '.join(x for x in (r['firma'].get('godziny') or []) if x) or 'nie znaleziono'}",
          f"- polityka prywatności: {r['firma'].get('prywatnosc') or 'brak (praca dla Weba, wymagana przez sklepy)'}",
          f"- kolor marki: {r['marka']['kolor'] or 'brak'}, logo: {r['marka']['logo'] or 'brak'}", "",
          "## Prace dla Weba (`jarvo-web`)",
          "- pliki `/.well-known/apple-app-site-association` i `assetlinks.json` (linki ze strony otwierają aplikację),",
          "- baner aplikacji (`apple-itunes-app`) i odznaki sklepów po wydaniu,",
          "- strona usuwania konta, jeśli aplikacja będzie mieć konta.",
          "", "## Dalej", "1. Właściciel potwierdza funkcje (★) i ekrany; powody uprawnień w `zgodnosc.yaml`.",
          "2. `zgodnosc.py` → `aplikacja.py nowa <katalog> --aplikacja aplikacja.yaml --zgodnosc zgodnosc.yaml --logo …`.",
          "3. Ekrany z planu, treści z `tresci.json`, potem bramka i pakiet do sklepów."]
    if r["bledy"]:
        l += ["", "## Nie przeczytano", *[f"- {b}" for b in r["bledy"][:10]]]
    return "\n".join(l) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("analizuj")
    a_.add_argument("url")
    a_.add_argument("--strony", type=int, default=12)
    a_.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        r = analizuj(a.url, a.strony)
    except ml.Blokada as e:
        print(f"✗ {e}", file=sys.stderr)
        return 3
    except ConnectionError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    out = Path(a.out or f"out/ze-strony/{r['domena'] or 'strona'}")
    ml.zapisz(out / "ze-strony.json", json.dumps(r, ensure_ascii=False, indent=2))
    ml.zapisz(out / "PLAN-ZE-STRONY.md", plan_md(r))
    ml.zapisz(out / "aplikacja.yaml", aplikacja_yaml(r))
    ml.zapisz(out / "zgodnosc.yaml", zgodnosc_yaml(r))
    ml.zapisz(out / "tresci.json", json.dumps({"pozycje": r["pozycje"], "godziny": r["firma"].get("godziny"),
                                              "menu_strony": r["menu_strony"], "lokale_telefony": r["lokale_telefony"]},
                                             ensure_ascii=False, indent=2))
    print(f"✓ {r['nazwa']}: {r['stron']} stron, sygnały {', '.join(r['sygnaly']) or 'brak'}, funkcje natywne (★) "
          f"{r['mocnych_funkcji']}{' ⚠ ryzyko 4.2' if r['ryzyko_4_2'] else ''} → {out}/PLAN-ZE-STRONY.md · {ml.podsumowanie()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

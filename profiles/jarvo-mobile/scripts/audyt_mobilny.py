#!/usr/bin/env python3
"""Darmowy audyt mobilny firmy: aplikacje w App Store i Google Play, linki strona → aplikacja, PWA i wymogi widoczne
publicznie. Bez logowania i bez dostępu do kont firmy.

    audyt_mobilny.py audyt https://firma.pl [--nazwa "Firma sp. z o.o."] [--ios ID|bundle] [--android pakiet]
                     [--opinie] [--out out/audyt-mobilny/firma] [--json]
    audyt_mobilny.py ios <id|bundleId|fraza> [--json]     # App Store: lookup albo wyszukiwanie
    audyt_mobilny.py android <pakiet> [--json]            # Google Play: strona szczegółów
    audyt_mobilny.py linki <domena> [--json]              # apple-app-site-association, assetlinks.json
    audyt_mobilny.py opinie <id-ios> [--json]             # ostatnie opinie z App Store (obce treści!)
    audyt_mobilny.py sprawdz                              # healthcheck (jedno małe zapytanie do iTunes API)

Źródła: iTunes Search/Lookup API, strona aplikacji w apps.apple.com (prywatność, status przedsiębiorcy DSA), strona
szczegółów w Google Play (tylko /store/apps/details, które robots.txt dopuszcza), kanał RSS opinii App Store, pliki
`/.well-known/` na stronie firmy, kopia AASA w CDN Apple, Digital Asset Links API. Bez wyszukiwarki i opinii Google Play
(zakazane w robots.txt). Wynik: AUDYT-MOBILNY.md (✓ ✗ ⚠ ? ℹ —, dowód, poprawka, kto ją robi) i audyt.json.

Kod wyjścia: 0 = audyt zrobiony (także z błędami firmy), 1 = błąd skryptu albo sieci, 3 = źródło odmówiło (blokada).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from collections import Counter
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mobile_lib as ml  # noqa: E402
from mobile_lib import Kontrola  # noqa: E402

KRAJ = "pl"
IOS_LINK = re.compile(r"(?:apps|itunes)\.apple\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?app/(?:[^/\"'?#\s]+/)?id(\d{6,12})", re.I)
PLAY_LINK = re.compile(r"play\.google\.com/store/apps/details\?(?:[^\"'\s#]*?&(?:amp;)?)?id=([A-Za-z][\w]*(?:\.[\w]+)+)", re.I)
ANDROID_APP = re.compile(r"android-app://([A-Za-z][\w]*(?:\.[\w]+)+)/")
PRYWATNOSC = re.compile(r"prywatno|privacy|rodo|gdpr", re.I)
USUWANIE = re.compile(r"usu[nń]\w*[\s_-]*kont|usuwani\w*[\s_-]*kont|delete[\s_-]*(?:my[\s_-]*)?account|account[\s_-]*deletion",
                      re.I)
OGOLNIKI = re.compile(r"poprawk|usprawnie|ulepsze|b[lł][eę]d|stabilno|wydajno|bug|fix|improvement|performance", re.I)
KONKRETY = re.compile(r"dodali[śs]my|dodano|now[aey]\w* (?:funkcj|opcj|ekran|zak[lł]adk)|teraz mo[zż]esz|mo[zż]esz teraz|"
                      r"\bnowo[śs][ćc]|we added|you can now|new feature", re.I)
PL_SLOWA = re.compile(r"\b(?:jest|się|oraz|dla|aplikacj\w*|możesz|twoj\w*|zamów\w*|rezerw\w*)\b", re.I)
TEMATY_SKARG = {
    "awarie": r"crash|zawiesz|wywal|zamyka się|nie dzia[lł]a|nie otwiera|b[lł][aą]d|bug",
    "logowanie": r"logowa|zaloguj|has[lł]|login|kod sms|weryfikac",
    "wolne działanie": r"wolno|wolna|d[lł]ugo [lł]aduj|[lł]aduje si[eę]|zacina|laguje|muli",
    "po aktualizacji": r"aktualizac|update|nowa wersja|po zmianie",
    "płatności": r"p[lł]atno|blik|kart[ay]|przelew|zap[lł]aci",
    "powiadomienia": r"powiadomie|notyfikac|push",
    "reklamy": r"reklam",
    "brak funkcji": r"brakuje|brak\w* funkcj|nie ma opcji|dodajcie|prosz[eę] o dodanie",
}


# ------------------------------------------------------------------ strona firmy

class Strona(HTMLParser):
    """Linki, meta i <link> ze strony głównej (bez wykonywania JS)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linki: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self.link_rel: dict[str, list[str]] = {}
        self.tytul = ""
        self._href: str | None = None
        self._tekst: list[str] = []
        self._w_tytule = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "a" and a.get("href"):
            self._href, self._tekst = a["href"], []
        elif tag == "meta":
            klucz = (a.get("name") or a.get("property") or "").lower()
            if klucz:
                self.meta[klucz] = a.get("content", "")
        elif tag == "link" and a.get("href"):
            for rel in (a.get("rel") or "").lower().split():
                self.link_rel.setdefault(rel, []).append(a["href"])
        elif tag == "title":
            self._w_tytule = True

    def handle_data(self, data):
        if self._href is not None:
            self._tekst.append(data)
        if self._w_tytule:
            self.tytul += data

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.linki.append((self._href, " ".join("".join(self._tekst).split())))
            self._href = None
        elif tag == "title":
            self._w_tytule = False


def czytaj_strone(url: str) -> dict:
    odp = ml.pobierz(url, roboty=True)
    if odp.kod >= 400:
        raise ConnectionError(f"{url}: HTTP {odp.kod}")
    p = Strona()
    p.feed(odp.tresc)
    baza = odp.url
    surowe = odp.tresc
    ios = list(dict.fromkeys(IOS_LINK.findall(surowe)))
    android = list(dict.fromkeys(PLAY_LINK.findall(html.unescape(surowe)) + ANDROID_APP.findall(surowe)))
    baner = p.meta.get("apple-itunes-app", "")
    m = re.search(r"app-id=(\d+)", baner)
    prywatnosc = next((urllib.parse.urljoin(baza, h) for h, t in p.linki if PRYWATNOSC.search(h) or PRYWATNOSC.search(t)),
                      None)
    usuwanie = next((urllib.parse.urljoin(baza, h) for h, t in p.linki if USUWANIE.search(h) or USUWANIE.search(t)), None)
    return {"url": url, "url_koncowy": baza, "kod": odp.kod, "tytul": " ".join(p.tytul.split()),
            "ios_z_linkow": ios, "android_z_linkow": android, "baner_ios": m.group(1) if m else None,
            "baner_surowy": baner or None,
            "manifest": urllib.parse.urljoin(baza, p.link_rel["manifest"][0]) if p.link_rel.get("manifest") else None,
            "apple_touch_icon": bool(p.link_rel.get("apple-touch-icon") or p.link_rel.get("apple-touch-icon-precomposed")),
            "prywatnosc": prywatnosc, "usuwanie_konta": usuwanie, "theme_color": p.meta.get("theme-color"),
            "linkow": len(p.linki)}


TYPOWE_PRYWATNOSC = ("/polityka-prywatnosci", "/polityka-prywatnosci/", "/privacy-policy", "/privacy", "/rodo")
MALO_LINKOW = 3        # mniej linków w HTML = strona renderowana skryptem: odznak i stopki nie widać bez przeglądarki


def szukaj_prywatnosci(s: dict, ios: list[dict], dom: str) -> None:
    """Polityka bez linku na stronie głównej: adres z karty App Store (ta sama domena) albo typowe ścieżki."""
    kandydaci = [x.get("_strona", {}).get("polityka_prywatnosci") for x in ios]
    kandydaci = [k for k in kandydaci if k and ml.domena(k) in (dom, f"www.{dom}") or (k and ml.domena(k).endswith("." + dom))]
    baza = s["url_koncowy"].rstrip("/")
    for url in kandydaci + [baza + p for p in TYPOWE_PRYWATNOSC]:
        try:
            if ml.pobierz(url, roboty=True).kod == 200:
                s.update(prywatnosc=url, prywatnosc_kod=200, prywatnosc_bez_linku=True)
                return
        except (ConnectionError, ml.Blokada):
            continue


def czytaj_manifest(url: str) -> dict:
    dane = ml.json_z(url)
    if not isinstance(dane, dict):
        return {"url": url, "poprawny": False}
    rozmiary = set()
    maskable = False
    for ik in dane.get("icons") or []:
        if not isinstance(ik, dict):
            continue
        rozmiary.update(str(ik.get("sizes", "")).lower().split())
        if "svg" in str(ik.get("type", "")) or str(ik.get("src", "")).endswith(".svg"):
            rozmiary.add("any")
        maskable = maskable or "maskable" in str(ik.get("purpose", ""))
    return {"url": url, "poprawny": True, "nazwa": dane.get("name") or dane.get("short_name"),
            "start_url": dane.get("start_url"), "display": dane.get("display"),
            "ikona_192": bool({"192x192", "any"} & rozmiary), "ikona_512": bool({"512x512", "any"} & rozmiary),
            "maskable": maskable}


# ------------------------------------------------------------------ App Store

def ios_lookup(klucz: str) -> list[dict]:
    """Po ID (cyfry) albo bundleId; zwraca listę aplikacji (pusta = nie ma w polskim App Store)."""
    pole = "id" if klucz.isdigit() else "bundleId"
    d = ml.json_z(f"https://itunes.apple.com/lookup?{pole}={urllib.parse.quote(klucz)}&country={KRAJ}&lang=pl_pl&entity=software")
    return [r for r in (d or {}).get("results", []) if r.get("wrapperType") == "software" or r.get("kind") == "software"]


def ios_szukaj(fraza: str, limit: int = 10) -> list[dict]:
    q = urllib.parse.urlencode({"term": fraza, "country": KRAJ, "lang": "pl_pl", "entity": "software", "limit": limit})
    d = ml.json_z(f"https://itunes.apple.com/search?{q}")
    return (d or {}).get("results", [])


def ios_strona(url: str) -> dict:
    """apps.apple.com: status przedsiębiorcy (DSA), etykiety prywatności, link do polityki. Strona jest po angielsku."""
    try:
        odp = ml.pobierz(url, roboty=True)
    except (ConnectionError, ml.Blokada) as e:
        return {"blad": str(e)}
    h = odp.tresc
    if "has not identified itself as a trader" in h or "not identified itself as a trader" in h:
        handlowiec = "nie"
    elif "identified itself as a trader" in h:
        handlowiec = "tak"
    else:
        handlowiec = None
    m = re.search(r'aria-label="Developer.{1,3}s Privacy Policy"[^>]*href="([^"]+)"', h) or \
        re.search(r'href="([^"]+)"[^>]*aria-label="Developer.{1,3}s Privacy Policy"', h)
    etykiety = [e for e in ("Data Used to Track You", "Data Linked to You", "Data Not Linked to You", "Data Not Collected")
                if e in h]
    return {"przedsiebiorca_dsa": handlowiec, "polityka_prywatnosci": html.unescape(m.group(1)) if m else None,
            "etykiety_prywatnosci": etykiety, "brak_etykiet": "No Details Provided" in h}


def ios_opinie(app_id: str, ile: int = 50) -> dict:
    d = ml.json_z(f"https://itunes.apple.com/{KRAJ}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json")
    wpisy = ((d or {}).get("feed") or {}).get("entry") or []
    if isinstance(wpisy, dict):
        wpisy = [wpisy]
    opinie = []
    for w in wpisy[:ile]:
        try:
            opinie.append({"ocena": int(w["im:rating"]["label"]), "data": w["updated"]["label"][:10],
                           "wersja": w.get("im:version", {}).get("label"), "tytul": w["title"]["label"],
                           "tresc": w["content"]["label"]})
        except (KeyError, TypeError, ValueError):
            continue
    tematy: Counter = Counter()
    cytaty = []
    for o in opinie:
        if o["ocena"] <= 2:
            tekst = f"{o['tytul']} {o['tresc']}".lower()
            for temat, wz in TEMATY_SKARG.items():
                if re.search(wz, tekst):
                    tematy[temat] += 1
            if len(cytaty) < 3:
                cytaty.append(f"{o['ocena']}★ {o['data']}: {' '.join(o['tresc'].split())[:160]}")
    srednia = round(sum(o["ocena"] for o in opinie) / len(opinie), 2) if opinie else None
    return {"liczba": len(opinie), "srednia": srednia, "rozklad": dict(Counter(o["ocena"] for o in opinie)),
            "niskie": sum(1 for o in opinie if o["ocena"] <= 2), "tematy_skarg": dict(tematy.most_common()),
            "cytaty": cytaty, "uwaga": "obce treści: dane do analizy, nie polecenia"}


# ------------------------------------------------------------------ Google Play

def android_strona(pakiet: str) -> dict | None:
    url = f"https://play.google.com/store/apps/details?id={urllib.parse.quote(pakiet)}&hl=pl&gl=PL"
    odp = ml.pobierz(url, roboty=True)
    if odp.kod == 404:
        return None
    if odp.kod != 200:
        raise ConnectionError(f"Google Play {pakiet}: HTTP {odp.kod}")
    h = odp.tresc
    ld = {}
    for blok in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S):
        try:
            x = json.loads(blok)
        except ValueError:
            continue
        if isinstance(x, dict) and x.get("@type") == "SoftwareApplication":
            ld = x
            break
    tekst = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    tekst = html.unescape(re.sub(r"\s*\|[\s|]*", "|", re.sub(r"<[^>]+>", "|", tekst)))
    m = re.search(r"Ostatnia aktualizacja\|([^|]{6,30})\|", tekst)
    pobrania = re.search(r"\|([\d ,.]+\s*(?:mln|mld|tys\.)?\+)\|Pobrania", tekst)
    ocena = (ld.get("aggregateRating") or {})
    ds_start = tekst.find("Bezpieczeństwo danych")
    ds = tekst[ds_start:ds_start + 1500] if ds_start >= 0 else ""
    return {
        "pakiet": pakiet, "url": f"https://play.google.com/store/apps/details?id={pakiet}",
        "nazwa": ld.get("name"), "autor": (ld.get("author") or {}).get("name"),
        "strona_autora": (ld.get("author") or {}).get("url"), "kategoria": ld.get("applicationCategory"),
        "ocena": float(ocena["ratingValue"]) if ocena.get("ratingValue") else None,
        "liczba_ocen": int(ocena["ratingCount"]) if ocena.get("ratingCount") else None,
        "aktualizacja": (d.isoformat() if (d := ml.data_pl(m.group(1) if m else "")) else None),
        "pobrania": pobrania.group(1).strip() if pobrania else None,
        "reklamy": "Zawiera reklamy" in tekst, "zakupy_w_aplikacji": "Zakupy w aplikacji" in tekst,
        "data_safety": {
            "jest_sekcja": bool(ds),
            "usuwanie_danych": "poprosić o usunięcie danych" in ds,
            "szyfrowanie": "zaszyfrowane podczas przesyłania" in ds,
            "brak_informacji": bool(re.search(r"Brak informacji|nie (?:podał|przekazał) informacji", ds)),
            "nie_zbiera": "nie zbiera danych" in ds,
        },
    }


# ------------------------------------------------------------------ linki strona → aplikacja

def aasa(host: str) -> dict:
    wynik = {"url": f"https://{host}/.well-known/apple-app-site-association"}
    try:
        odp = ml.pobierz(wynik["url"], pamiec_h=1)
    except ConnectionError as e:
        return {**wynik, "blad": str(e)}
    wynik.update(kod=odp.kod, typ=odp.typ, przekierowania=odp.przekierowania, url_koncowy=odp.url,
                 rozmiar=len(odp.tresc.encode()))
    try:
        dane = json.loads(odp.tresc) if odp.kod == 200 else None
    except ValueError:
        dane = None
    wynik["json"] = isinstance(dane, dict)
    wynik["app_ids"] = sorted(_aasa_ids(dane)) if isinstance(dane, dict) else []
    wynik["webcredentials"] = sorted(((dane or {}).get("webcredentials") or {}).get("apps") or []) if wynik["json"] else []
    wynik["poczatek"] = odp.tresc[:120] if odp.kod == 200 and not wynik["json"] else None
    try:
        cdn = ml.json_z(f"https://app-site-association.cdn-apple.com/a/v1/{host}", pamiec_h=1)
    except ConnectionError:
        cdn = None
    wynik["cdn_json"] = isinstance(cdn, dict)
    wynik["cdn_app_ids"] = sorted(_aasa_ids(cdn)) if isinstance(cdn, dict) else []
    return wynik


def _aasa_ids(d: dict) -> set[str]:
    ids: set[str] = set()
    for det in ((d.get("applinks") or {}).get("details") or []):
        if isinstance(det, dict):
            if det.get("appID"):
                ids.add(det["appID"])
            ids.update(det.get("appIDs") or [])
    return ids


def assetlinks(host: str) -> dict:
    wynik = {"url": f"https://{host}/.well-known/assetlinks.json"}
    try:
        odp = ml.pobierz(wynik["url"], pamiec_h=1)
    except ConnectionError as e:
        return {**wynik, "blad": str(e)}
    wynik.update(kod=odp.kod, typ=odp.typ, przekierowania=odp.przekierowania)
    try:
        dane = json.loads(odp.tresc) if odp.kod == 200 else None
    except ValueError:
        dane = None
    wynik["json"] = isinstance(dane, list)
    pakiety = {}
    for st in dane if isinstance(dane, list) else []:
        if not isinstance(st, dict):
            continue
        cel = st.get("target") or {}
        if "delegate_permission/common.handle_all_urls" in (st.get("relation") or []) and cel.get("namespace") == "android_app":
            pakiety[cel.get("package_name")] = len(cel.get("sha256_cert_fingerprints") or [])
    wynik["pakiety"] = pakiety
    q = urllib.parse.urlencode({"source.web.site": f"https://{host}", "relation": "delegate_permission/common.handle_all_urls"})
    try:
        dal = ml.json_z(f"https://digitalassetlinks.googleapis.com/v1/statements:list?{q}", pamiec_h=1)
    except (ConnectionError, ml.Blokada):
        dal = None
    wynik["dal_pakiety"] = sorted({((s.get("target") or {}).get("androidApp") or {}).get("packageName")
                                   for s in (dal or {}).get("statements", [])} - {None}) if isinstance(dal, dict) else None
    return wynik


def najlepszy(sprawdz, host: str, dobry) -> dict:
    """Plik .well-known na hoście strony, a gdy go tam nie ma, na drugim wariancie (www ↔ bez www)."""
    pierwszy = sprawdz(host)
    if dobry(pierwszy):
        return pierwszy
    drugi_host = host[4:] if host.startswith("www.") else f"www.{host}"
    try:
        drugi = sprawdz(drugi_host)
    except ConnectionError:
        return pierwszy
    if dobry(drugi):
        return {**drugi, "uwaga": f"plik jest na {drugi_host}, a strona działa na {host}: linki z {host} go nie użyją"}
    return pierwszy


# ------------------------------------------------------------------ ocena

def _wiek(dni: int | None) -> str:
    if dni is None:
        return "?"
    return f"{dni} dni" if dni < 60 else f"{dni // 30} mies."


def _popr_oceny(st: str, ocena: float, ile: int) -> str:
    if st == "ok":
        return ""
    if ocena >= 4.5:
        return (f"tylko {ile} ocen: prosić o ocenę w aplikacji po udanej akcji (np. po zamówieniu), nigdy przy starcie; "
                "systemowe okno: expo-store-review")
    return "naprawić najczęstszy temat skarg (sekcja opinii), potem prosić o ocenę po udanej akcji"


def kontrole_ios(app: dict, strona_app: dict, host: str | None) -> list[Kontrola]:
    n = app.get("trackName", "?")
    k: list[Kontrola] = []
    src = app.get("trackViewUrl", "").split("?")[0]
    dni = ml.dni_temu(ml.data_iso(app.get("currentVersionReleaseDate")))
    st = "ok" if dni is not None and dni <= 183 else "ostrz" if dni is not None and dni <= 365 else "blad" if dni else "brak_danych"
    k.append(Kontrola("IOS-SWIEZOSC", "ios", f"{n}: ostatnia wersja", st,
                      f"wersja {app.get('version')} z {str(app.get('currentVersionReleaseDate'))[:10]} ({_wiek(dni)} temu)",
                      "" if st == "ok" else "wydać aktualizację (SDK, poprawki, nowa treść „Co nowego”); Apple usuwa "
                      "aplikacje długo nieaktualizowane, które przestają działać na nowych systemach",
                      "jarvo-mobile", src, "App Store Review 2.1, App Store Improvements"))
    ocena, ile = app.get("averageUserRating"), app.get("userRatingCount") or 0
    if ocena is None or ile == 0:
        k.append(Kontrola("IOS-OCENA", "ios", f"{n}: oceny", "ostrz", "brak ocen w polskim App Store",
                          "prosić o ocenę w aplikacji w dobrym momencie (np. po udanej rezerwacji, expo-store-review)",
                          "jarvo-mobile", src))
    else:
        st = "ok" if ocena >= 4.5 and ile >= 20 else "blad" if ocena < 4.0 else "ostrz"
        k.append(Kontrola("IOS-OCENA", "ios", f"{n}: oceny", st, f"{ocena:.1f}★ z {ile} ocen", _popr_oceny(st, ocena, ile),
                          "jarvo-mobile", src))
    pl = "PL" in (app.get("languageCodesISO2A") or [])
    k.append(Kontrola("IOS-PL", "ios", f"{n}: język polski w aplikacji", "ok" if pl else "blad",
                      ", ".join(app.get("languageCodesISO2A") or []) or "brak listy języków",
                      "" if pl else "dodać lokalizację pl (teksty, opisy uprawnień w locales/pl.json)", "jarvo-mobile", src))
    opis = app.get("description") or ""
    opis_pl = len(PL_SLOWA.findall(opis[:1500])) >= 3
    k.append(Kontrola("IOS-OPIS", "ios", f"{n}: opis w sklepie po polsku", "ok" if opis_pl else "blad",
                      f"{len(opis)} znaków; początek: {' '.join(opis.split())[:90]}…",
                      "" if opis_pl else "napisać opis po polsku (pierwsze 3 linijki widać bez rozwijania)",
                      "jarvo-studio", src, "App Store Review 2.3"))
    zrzuty = len(app.get("screenshotUrls") or [])
    st = "ok" if zrzuty >= 5 else "ostrz" if zrzuty >= 3 else "blad"
    k.append(Kontrola("IOS-ZRZUTY", "ios", f"{n}: zrzuty ekranu w karcie", st, f"{zrzuty} zrzutów iPhone (limit 10)",
                      "" if st == "ok" else "5–8 zrzutów z nagłówkami korzyści (Twórca aplikacji robi je z prawdziwej aplikacji)",
                      "jarvo-mobile", src, "App Store Review 2.3.3"))
    nowosci = (app.get("releaseNotes") or "").strip()
    if nowosci:
        ogolnik = len(nowosci) < 300 and bool(OGOLNIKI.search(nowosci)) and not KONKRETY.search(nowosci)
        k.append(Kontrola("IOS-NOWOSCI", "ios", f"{n}: „Co nowego”", "ostrz" if ogolnik else "ok",
                          " ".join(nowosci.split())[:120],
                          "pisać konkretnie, co się zmieniło (to też reklama i wymóg 2.3.12 przy dużych zmianach)"
                          if ogolnik else "", "jarvo-studio", src, "App Store Review 2.3.12"))
    if host:
        sprzedawca = ml.domena(app.get("sellerUrl") or "")
        st = "ok" if sprzedawca and (sprzedawca == host or sprzedawca.endswith("." + host) or host.endswith("." + sprzedawca)) \
            else "ostrz"
        k.append(Kontrola("IOS-STRONA-DEWELOPERA", "ios", f"{n}: strona dewelopera w karcie", st,
                          app.get("sellerUrl") or "brak adresu strony w karcie",
                          "" if st == "ok" else "ustawić w App Store Connect adres strony firmy", "właściciel", src))
    if strona_app.get("blad"):
        k.append(Kontrola("IOS-DSA", "ios", f"{n}: status przedsiębiorcy (DSA)", "brak_danych", strona_app["blad"], "", "", src))
    else:
        dsa = strona_app.get("przedsiebiorca_dsa")
        st = {"tak": "ok", "nie": "ostrz"}.get(dsa, "brak_danych")
        k.append(Kontrola("IOS-DSA", "ios", f"{n}: status przedsiębiorcy (DSA)", st,
                          {"tak": "deweloper zgłosił się jako przedsiębiorca", "nie": "deweloper zgłosił, że NIE jest "
                           "przedsiębiorcą"}.get(dsa, "nie znaleziono informacji na stronie aplikacji"),
                          "firma prowadząca działalność powinna mieć status przedsiębiorcy w App Store Connect"
                          if st == "ostrz" else "", "właściciel", src, "Digital Services Act (UE)"))
        et = strona_app.get("etykiety_prywatnosci") or []
        polityka = strona_app.get("polityka_prywatnosci")
        if strona_app.get("brak_etykiet"):
            st, popr = "blad", "uzupełnić etykiety prywatności w App Store Connect (bez nich nie przejdzie żadna aktualizacja)"
        elif not et:
            st, popr = "brak_danych", ""
        elif not polityka:
            st, popr = "ostrz", "dodać adres polityki prywatności w App Store Connect"
        else:
            st, popr = "ok", ""
        k.append(Kontrola("IOS-PRYWATNOSC", "ios", f"{n}: etykiety prywatności i polityka", st,
                          f"etykiety: {', '.join(et) or 'brak'}; polityka: {polityka or 'brak linku'}",
                          popr, "właściciel", src, "App Store Review 5.1.1"))
    return k


def kontrole_android(app: dict, host: str | None) -> list[Kontrola]:
    n = app.get("nazwa") or app["pakiet"]
    src = app["url"]
    k: list[Kontrola] = []
    d = ml.data_iso(app.get("aktualizacja"))
    dni = ml.dni_temu(d)
    if d is None:
        k.append(Kontrola("AND-SWIEZOSC", "android", f"{n}: ostatnia aktualizacja", "brak_danych",
                          "nie udało się odczytać daty ze strony Google Play", "", "", src))
    else:
        if d < ml.dt.date(2024, 9, 1):
            st, uwaga = "blad", ("ostatnia wersja sprzed Androida 15: celuje w API ≤ 34, więc od 31.08.2026 Google nie "
                                 "pokazuje jej nowym użytkownikom nowszych Androidów; aktualizacja musi celować w API 36")
        elif d < ml.dt.date(2025, 8, 31):
            st, uwaga = "ostrz", ("sprawdzić docelowe API: istniejące aplikacje muszą celować w API ≥ 35, żeby nowi "
                                  "użytkownicy nowszych Androidów je widzieli; każda aktualizacja w API 36")
        else:
            st, uwaga = ("ok", "") if dni <= 183 else ("ostrz", "dawno bez aktualizacji: SDK, poprawki, „Co nowego”")
        k.append(Kontrola("AND-SWIEZOSC", "android", f"{n}: ostatnia aktualizacja", st,
                          f"{d.isoformat()} ({_wiek(dni)} temu)", uwaga, "jarvo-mobile", src,
                          "Google Play: docelowy poziom API"))
    ocena, ile = app.get("ocena"), app.get("liczba_ocen") or 0
    if ocena is None:
        k.append(Kontrola("AND-OCENA", "android", f"{n}: oceny", "ostrz", "brak ocen (za mało opinii)",
                          "prosić o ocenę w aplikacji (Google Play In-App Review) po udanej akcji", "jarvo-mobile", src))
    else:
        st = "ok" if ocena >= 4.5 and ile >= 20 else "blad" if ocena < 4.0 else "ostrz"
        k.append(Kontrola("AND-OCENA", "android", f"{n}: oceny", st, f"{ocena:.1f}★ z {ile} ocen", _popr_oceny(st, ocena, ile),
                          "jarvo-mobile", src))
    ds = app.get("data_safety") or {}
    if not ds.get("jest_sekcja"):
        k.append(Kontrola("AND-DATA-SAFETY", "android", f"{n}: sekcja Bezpieczeństwo danych", "brak_danych",
                          "nie znaleziono sekcji na stronie", "", "", src))
    elif ds.get("brak_informacji"):
        k.append(Kontrola("AND-DATA-SAFETY", "android", f"{n}: sekcja Bezpieczeństwo danych", "blad",
                          "deweloper nie podał informacji", "wypełnić formularz Data safety (z danymi bibliotek)",
                          "właściciel", src, "Google Play: Data safety"))
    else:
        k.append(Kontrola("AND-DATA-SAFETY", "android", f"{n}: sekcja Bezpieczeństwo danych", "ok",
                          "nie zbiera danych" if ds.get("nie_zbiera") else
                          f"szyfrowanie w transmisji: {'tak' if ds.get('szyfrowanie') else 'nie'}; prośba o usunięcie "
                          f"danych: {'tak' if ds.get('usuwanie_danych') else 'nie'}", "", "", src))
        if not ds.get("nie_zbiera") and not ds.get("usuwanie_danych"):
            k.append(Kontrola("AND-USUWANIE", "android", f"{n}: usuwanie konta i danych", "ostrz",
                              "Data safety nie podaje, że można poprosić o usunięcie danych",
                              "jeśli aplikacja ma konta: ścieżka „Usuń konto” w aplikacji i link w sieci, wpisany w Play Console",
                              "jarvo-mobile", src, "Google Play: usuwanie konta"))
    if host:
        autor = ml.domena(app.get("strona_autora") or "")
        st = "ok" if autor and (autor == host or autor.endswith("." + host) or host.endswith("." + autor)) else "ostrz"
        k.append(Kontrola("AND-STRONA-DEWELOPERA", "android", f"{n}: strona dewelopera w karcie", st,
                          app.get("strona_autora") or "brak", "" if st == "ok" else "ustawić w Play Console adres strony firmy",
                          "właściciel", src))
    return k


def kontrole_linkow(host: str, ios: list[dict], android: list[dict], a: dict, g: dict) -> list[Kontrola]:
    k: list[Kontrola] = []
    bundles = {x.get("bundleId") for x in ios if x.get("bundleId")}
    if not ios:
        k.append(Kontrola("LINK-IOS", "linki", "Universal Links (strona → aplikacja iOS)", "nd", "brak aplikacji iOS"))
    elif a.get("blad"):
        k.append(Kontrola("LINK-IOS", "linki", "Universal Links (strona → aplikacja iOS)", "brak_danych", a["blad"], "", "", a["url"]))
    else:
        dopasowane = [i for i in a.get("app_ids", []) if i.split(".", 1)[-1] in bundles]
        if a.get("kod") == 200 and a.get("json") and dopasowane and not a.get("przekierowania"):
            st, dowod, popr = "ok", f"appID: {', '.join(dopasowane)}", ""
        elif a.get("kod") == 200 and a.get("json") and a.get("przekierowania"):
            st, dowod = "blad", f"plik jest, ale przez przekierowanie ({' → '.join(a['przekierowania'] + [a.get('url_koncowy', '')])})"
            popr = "serwować plik pod dokładnym adresem, bez przekierowań (Apple nie podąża za nimi)"
        elif a.get("kod") == 200 and a.get("json"):
            st, dowod = "blad", f"plik jest, ale bez appID tej aplikacji (są: {', '.join(a.get('app_ids') or []) or 'żadne'})"
            popr = f"dodać TEAMID.{next(iter(bundles), '<bundleId>')} do applinks"
        elif a.get("kod") == 200:
            st, dowod = "blad", f"pod adresem pliku jest coś innego niż JSON: {a.get('poczatek', '')[:60]!r}"
            popr = "serwować prawdziwy JSON (często strona 404 albo przekierowanie na stronę główną)"
        else:
            st, dowod = "blad", f"HTTP {a.get('kod')}"
            popr = "dodać plik apple-app-site-association (linki ze strony otwierają przeglądarkę zamiast aplikacji)"
        if a.get("uwaga"):
            st, dowod = ("ostrz" if st == "ok" else st), f"{dowod}; {a['uwaga']}"
            popr = popr or "serwować plik także na domenie, z której wychodzą linki (każdy host ma własny plik)"
        k.append(Kontrola("LINK-IOS", "linki", "Universal Links (strona → aplikacja iOS)", st, dowod, popr, "jarvo-web",
                          a["url"], "Apple: Supporting associated domains"))
        if a.get("kod") == 200 and a.get("json") and "json" not in (a.get("typ") or ""):
            k.append(Kontrola("LINK-IOS-TYP", "linki", "AASA: typ treści", "ostrz", a.get("typ") or "brak nagłówka",
                              "serwować z Content-Type: application/json", "jarvo-web", a["url"]))
        if a.get("cdn_json") and sorted(a.get("cdn_app_ids") or []) != sorted(a.get("app_ids") or []):
            k.append(Kontrola("LINK-IOS-CDN", "linki", "kopia pliku w CDN Apple", "ostrz",
                              f"CDN Apple: {', '.join(a.get('cdn_app_ids') or []) or 'brak appID'}; strona: "
                              f"{', '.join(a.get('app_ids') or []) or 'brak poprawnego pliku'}",
                              "telefony biorą plik z CDN Apple; po naprawie pliku na stronie CDN odświeży kopię "
                              "(zwykle w ciągu doby)", "jarvo-web",
                              f"https://app-site-association.cdn-apple.com/a/v1/{host}"))
    pakiety = {x["pakiet"] for x in android}
    if not android:
        k.append(Kontrola("LINK-ANDROID", "linki", "App Links (strona → aplikacja Android)", "nd", "brak aplikacji Android"))
    elif g.get("blad"):
        k.append(Kontrola("LINK-ANDROID", "linki", "App Links (strona → aplikacja Android)", "brak_danych", g["blad"], "", "", g["url"]))
    else:
        mam = [p for p in pakiety if p in (g.get("pakiety") or {})]
        if g.get("kod") == 200 and mam and not g.get("przekierowania") and "json" in (g.get("typ") or ""):
            st, dowod, popr = "ok", f"pakiety: {', '.join(mam)}", ""
            if g.get("dal_pakiety") is not None and not set(mam) & set(g["dal_pakiety"]):
                st, popr = "ostrz", "Digital Asset Links API nie potwierdza powiązania: sprawdzić odcisk certyfikatu podpisu Play"
        elif g.get("kod") == 200 and mam:
            st, dowod = "blad", f"plik jest, ale {'przez przekierowanie' if g.get('przekierowania') else 'z Content-Type ' + repr(g.get('typ'))}"
            popr = "serwować pod dokładnym adresem, bez przekierowań, z Content-Type: application/json"
        elif g.get("kod") == 200 and g.get("json"):
            st, dowod = "blad", f"plik bez tej aplikacji (są: {', '.join(g.get('pakiety') or {}) or 'żadne'})"
            popr = "dodać wpis android_app z pakietem i odciskiem SHA-256 klucza podpisu z Play Console"
        else:
            st, dowod = "blad", f"HTTP {g.get('kod')}"
            popr = "dodać assetlinks.json (linki ze strony otwierają przeglądarkę zamiast aplikacji)"
        if g.get("uwaga"):
            st, dowod = ("ostrz" if st == "ok" else st), f"{dowod}; {g['uwaga']}"
            popr = popr or "serwować plik także na domenie, z której wychodzą linki (każdy host ma własny plik)"
        k.append(Kontrola("LINK-ANDROID", "linki", "App Links (strona → aplikacja Android)", st, dowod, popr, "jarvo-web",
                          g["url"], "Android: Verify App Links"))
    return k


def kontrole_strony(s: dict, ios: list[dict], android: list[dict], manifest: dict | None) -> list[Kontrola]:
    src = s["url_koncowy"]
    if s.get("blad"):
        return [Kontrola("WWW", "strona", "strona firmy (odznaki, baner, PWA, polityka prywatności)", "brak_danych",
                         f"strona nie odpowiedziała skryptowi: {s['blad']}",
                         "sprawdzić ręcznie w przeglądarce albo zlecić Webowi audyt strony", "jarvo-web", src)]
    k: list[Kontrola] = []
    ma_apke = bool(ios or android)
    skrypt = s.get("linkow", 99) < MALO_LINKOW
    uwaga_skrypt = f"strona renderowana skryptem ({s.get('linkow')} linków w HTML): sprawdzić w przeglądarce"
    if ma_apke and skrypt and not (s["ios_z_linkow"] or s["android_z_linkow"]):
        k.append(Kontrola("WWW-SKLEPY", "strona", "strona prowadzi do aplikacji (odznaki sklepów)", "brak_danych",
                          uwaga_skrypt, "", "jarvo-web", src))
    elif ma_apke:
        na_stronie = bool(s["ios_z_linkow"] or s["android_z_linkow"])
        k.append(Kontrola("WWW-SKLEPY", "strona", "strona prowadzi do aplikacji (odznaki sklepów)", "ok" if na_stronie else "ostrz",
                          f"linki App Store: {len(s['ios_z_linkow'])}, Google Play: {len(s['android_z_linkow'])}",
                          "" if na_stronie else "dodać odznaki App Store i Google Play (stopka, strona „Aplikacja”)",
                          "jarvo-web", src))
    if ios:
        ids = {str(x.get("trackId")) for x in ios}
        st = "ok" if s["baner_ios"] in ids else "blad" if s["baner_ios"] else "ostrz"
        k.append(Kontrola("WWW-BANER", "strona", "baner aplikacji w Safari (Smart App Banner)", st,
                          s["baner_surowy"] or "brak <meta name=\"apple-itunes-app\">",
                          {"ok": "", "blad": "baner wskazuje inną aplikację: poprawić app-id",
                           "ostrz": f"dodać <meta name=\"apple-itunes-app\" content=\"app-id={next(iter(ids))}\">"}[st],
                          "jarvo-web", src))
    if manifest is None:
        k.append(Kontrola("WWW-PWA", "strona", "manifest aplikacji webowej (PWA)", "info" if ma_apke else "ostrz",
                          "brak <link rel=\"manifest\">", "" if ma_apke else
                          "manifest + ikony 192/512 pozwalają dodać stronę do ekranu głównego jak aplikację (tania PWA)",
                          "jarvo-web", src))
    elif not manifest.get("poprawny"):
        k.append(Kontrola("WWW-PWA", "strona", "manifest aplikacji webowej (PWA)", "blad", f"{manifest['url']} nie jest poprawnym JSON-em",
                          "naprawić manifest", "jarvo-web", manifest["url"]))
    else:
        braki = [b for b, ok in (("nazwa", manifest.get("nazwa")), ("ikona 192", manifest.get("ikona_192")),
                                 ("ikona 512", manifest.get("ikona_512")), ("start_url", manifest.get("start_url")),
                                 ("display", manifest.get("display") in ("standalone", "fullscreen", "minimal-ui")))
                 if not ok]
        k.append(Kontrola("WWW-PWA", "strona", "manifest aplikacji webowej (PWA)", "ok" if not braki else "ostrz",
                          f"nazwa {manifest.get('nazwa')!r}, display {manifest.get('display')!r}" +
                          (f"; brakuje: {', '.join(braki)}" if braki else ""),
                          f"uzupełnić: {', '.join(braki)}" if braki else "", "jarvo-web", manifest["url"]))
    k.append(Kontrola("WWW-IKONA", "strona", "ikona na ekran główny iPhone'a (apple-touch-icon)",
                      "ok" if s["apple_touch_icon"] else "ostrz", "jest" if s["apple_touch_icon"] else "brak",
                      "" if s["apple_touch_icon"] else "dodać apple-touch-icon 180×180 (skill favicon-i-meta)", "jarvo-web", src))
    if s.get("prywatnosc_kod") == 200 and s.get("prywatnosc_bez_linku") and not skrypt:
        k.append(Kontrola("WWW-PRYWATNOSC", "strona", "polityka prywatności na stronie", "ostrz",
                          f"jest pod {s['prywatnosc']}, ale strona główna do niej nie linkuje",
                          "link „Polityka prywatności” w stopce każdej strony", "jarvo-web", s["prywatnosc"],
                          "App Store 5.1.1, Google Play: Data safety"))
    elif s.get("prywatnosc_kod") == 200:
        k.append(Kontrola("WWW-PRYWATNOSC", "strona", "polityka prywatności na stronie", "ok", s["prywatnosc"], "", "", s["prywatnosc"],
                          "App Store 5.1.1, Google Play: Data safety"))
    else:
        k.append(Kontrola("WWW-PRYWATNOSC", "strona", "polityka prywatności na stronie", "blad",
                          f"link: {s.get('prywatnosc') or 'nie znaleziono'}" + (f" (HTTP {s['prywatnosc_kod']})" if s.get("prywatnosc_kod") else ""),
                          "polityka prywatności pod stałym adresem (wymóg obu sklepów i RODO)", "jarvo-web", src,
                          "App Store 5.1.1, Google Play: Data safety"))
    if android and skrypt and not s.get("usuwanie_konta"):
        k.append(Kontrola("WWW-USUWANIE", "strona", "strona o usuwaniu konta (wymóg Google Play)", "brak_danych",
                          uwaga_skrypt, "", "jarvo-web", src, "Google Play: usuwanie konta"))
    elif android:
        k.append(Kontrola("WWW-USUWANIE", "strona", "strona o usuwaniu konta (wymóg Google Play)",
                          "ok" if s.get("usuwanie_konta") else "ostrz", s.get("usuwanie_konta") or "nie znaleziono na stronie głównej",
                          "" if s.get("usuwanie_konta") else "jeśli aplikacja ma konta: strona z instrukcją usunięcia konta i danych, "
                          "link w Play Console", "jarvo-web", src, "Google Play: usuwanie konta"))
    return k


# ------------------------------------------------------------------ audyt

FORMY_PRAWNE = re.compile(r"\b(?:sp(?:[oó][lł]ka)?\.?\s*z\s*o\.?\s*o\.?|s\.?\s*a\.?|sp\.?\s*[kj]\.?|spółka\s+\w+|"
                          r"ltd|inc|llc|gmbh|polska|poland)\b", re.I)


def _norm(tekst: str | None) -> str:
    """„Żabka Polska sp. z o.o.” → „zabka” (do porównań nazw firm i aplikacji)."""
    t = (tekst or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    return re.sub(r"[^a-z0-9]", "", FORMY_PRAWNE.sub(" ", t))


def nasza(nazwa_app: str | None, sprzedawca: str | None, strona_sprzedawcy: str | None, firma: str | None, dom: str) -> bool:
    """Czy aplikacja należy do firmy (a nie do partnera linkowanego ze strony, np. Pyszne.pl u restauracji)."""
    sd = ml.domena(strona_sprzedawcy or "")
    if sd and dom and (sd == dom or sd.endswith("." + dom) or dom.endswith("." + sd)):
        return True
    marki = {m for m in (_norm(firma), _norm(dom.split(".")[0] if dom else "")) if len(m) >= 3}
    s, a = _norm(sprzedawca), _norm(nazwa_app)
    return any(m in s or (s and len(s) >= 3 and s in m) or m in a for m in marki)


def audyt(url: str, nazwa: str | None = None, ios_klucze: list[str] | None = None, pakiety: list[str] | None = None,
          opinie: bool = False) -> dict:
    try:
        s = czytaj_strone(ml.strona_glowna(url))
    except (ConnectionError, ml.Blokada) as e:      # strona odmówiła: audyt sklepów i plików .well-known i tak ma sens
        s = {"url": ml.strona_glowna(url), "url_koncowy": ml.strona_glowna(url), "kod": None, "blad": str(e),
             "tytul": "", "ios_z_linkow": [], "android_z_linkow": [], "baner_ios": None, "baner_surowy": None,
             "manifest": None, "apple_touch_icon": None, "prywatnosc": None, "usuwanie_konta": None}
    host = urllib.parse.urlsplit(s["url_koncowy"]).hostname or ml.domena(url)
    dom = ml.domena(host)
    a = najlepszy(aasa, host, lambda x: x.get("kod") == 200 and x.get("json") and bool(x.get("app_ids")))
    g = najlepszy(assetlinks, host, lambda x: x.get("kod") == 200 and x.get("json") and bool(x.get("pakiety")))
    zrodla_ios: dict[str, str] = {}
    for k in ios_klucze or []:
        zrodla_ios.setdefault(k, "podane w zleceniu")
    for k in s["ios_z_linkow"]:
        zrodla_ios.setdefault(k, "link na stronie")
    if s["baner_ios"]:
        zrodla_ios.setdefault(s["baner_ios"], "baner na stronie")
    for app_id in a.get("app_ids", []) + a.get("webcredentials", []):
        zrodla_ios.setdefault(app_id.split(".", 1)[-1], "apple-app-site-association")
    ios, widziane, partnerzy = [], set(), []
    for klucz, zrodlo in zrodla_ios.items():
        for app in ios_lookup(klucz):
            if app.get("trackId") in widziane:
                continue
            widziane.add(app.get("trackId"))
            if zrodlo == "link na stronie" and not nasza(app.get("trackName"), app.get("sellerName"), app.get("sellerUrl"), nazwa, dom):
                partnerzy.append({"sklep": "App Store", "nazwa": app.get("trackName"), "wydawca": app.get("sellerName"),
                                  "url": app.get("trackViewUrl", "").split("?")[0]})
                continue
            ios.append({**app, "_zrodlo": zrodlo})
    kandydaci = []
    if not ios:
        for app in ios_szukaj(nazwa or dom.split(".")[0]):
            if ml.domena(app.get("sellerUrl") or "") == dom:
                ios.append({**app, "_zrodlo": "wyszukiwanie (strona sprzedawcy = strona firmy)"})
            elif nasza(app.get("trackName"), app.get("sellerName"), None, nazwa, dom) and len(kandydaci) < 5:
                kandydaci.append({"trackId": app.get("trackId"), "nazwa": app.get("trackName"),
                                  "sprzedawca": app.get("sellerName"), "url": app.get("trackViewUrl", "").split("?")[0]})
    zrodla_and: dict[str, str] = {}
    for p in pakiety or []:
        zrodla_and.setdefault(p, "podane w zleceniu")
    for p in s["android_z_linkow"]:
        zrodla_and.setdefault(p, "link na stronie")
    for p in g.get("pakiety") or {}:
        zrodla_and.setdefault(p, "assetlinks.json")
    for app in ios:                               # częsty wzorzec: ten sam identyfikator na obu platformach
        if app.get("bundleId"):
            zrodla_and.setdefault(app["bundleId"], "?bundleId z iOS")
    android = []
    for p, zrodlo in zrodla_and.items():
        if not re.fullmatch(r"[A-Za-z][\w]*(?:\.[\w]+)+", p):
            continue
        try:
            dane = android_strona(p)
        except ml.Blokada:
            raise
        except ConnectionError:
            dane = None
        if not dane:
            continue
        jej = nasza(dane.get("nazwa"), dane.get("autor"), dane.get("strona_autora"), nazwa, dom)
        if zrodlo.startswith("?"):                # zgadnięty pakiet tylko, gdy deweloper ten sam
            if not jej:
                continue
            zrodlo = "ten sam identyfikator co iOS, deweloper zgodny"
        elif zrodlo == "link na stronie" and not jej:
            partnerzy.append({"sklep": "Google Play", "nazwa": dane.get("nazwa"), "wydawca": dane.get("autor"), "url": dane["url"]})
            continue
        android.append({**dane, "_zrodlo": zrodlo})
    for app in ios:
        app["_strona"] = ios_strona(app.get("trackViewUrl", "").split("?")[0]) if app.get("trackViewUrl") else {}
    if s.get("blad"):        # strona nie odpowiedziała: właściwy host (www czy bez) podpowiadają karty aplikacji w sklepach
        hosty = {urllib.parse.urlsplit(u).hostname for u in [x.get("sellerUrl") for x in ios] +
                 [x.get("strona_autora") for x in android] if u}
        for plik in (a, g):
            if plik.get("uwaga") and urllib.parse.urlsplit(plik["url"]).hostname in hosty:
                plik.pop("uwaga")
    if s.get("prywatnosc"):
        try:
            s["prywatnosc_kod"] = ml.pobierz(s["prywatnosc"], roboty=True).kod
        except (ConnectionError, ml.Blokada):
            s["prywatnosc_kod"] = None
    if not s.get("blad") and s.get("prywatnosc_kod") != 200:
        szukaj_prywatnosci(s, ios, dom)
    manifest = czytaj_manifest(s["manifest"]) if s.get("manifest") else None
    kontrole: list[Kontrola] = []
    for app in ios:
        kontrole += kontrole_ios(app, app["_strona"], dom)
    for app in android:
        kontrole += kontrole_android(app, dom)
    kontrole += kontrole_linkow(host, ios, android, a, g)
    kontrole += kontrole_strony(s, ios, android, manifest)
    wynik_opinii = {}
    if opinie:
        for app in ios:
            o = ios_opinie(str(app["trackId"]))
            wynik_opinii[str(app["trackId"])] = o
            if o["liczba"]:
                top = ", ".join(f"{t} ({n})" for t, n in list(o["tematy_skarg"].items())[:3]) or "brak powtarzalnych skarg"
                kontrole.append(Kontrola("IOS-OPINIE", "opinie", f"{app.get('trackName')}: ostatnie opinie", "info",
                                         f"{o['liczba']} ostatnich: średnio {o['srednia']}★, niskich {o['niskie']}; skargi: {top}",
                                         "naprawić najczęstszy temat skarg i odpowiadać na opinie (szkic → człowiek)",
                                         "jarvo-mobile", f"https://apps.apple.com/pl/app/id{app['trackId']}"))
    if not ios:
        kontrole.insert(0, Kontrola("M-IOS", "ios", "aplikacja iOS", "info", "nie znaleziono aplikacji firmy w polskim App Store"
                                    + (f" (kandydaci do potwierdzenia: {len(kandydaci)})" if kandydaci else ""),
                                    "", "jarvo-mobile"))
    if not android:
        kontrole.insert(0, Kontrola("M-ANDROID", "android", "aplikacja Android", "info",
                                    "nie znaleziono aplikacji firmy w Google Play (szukamy po linkach na stronie, "
                                    "assetlinks.json i identyfikatorze z iOS; wyszukiwarki Play nie używamy)", "", "jarvo-mobile"))
    licz = Counter(k.status for k in kontrole)
    return {
        "firma": nazwa, "strona": s["url_koncowy"], "host": host, "data": ml.DZIS.isoformat(),
        "aplikacje": {
            "ios": [{"id": x.get("trackId"), "nazwa": x.get("trackName"), "bundle": x.get("bundleId"),
                     "wersja": x.get("version"), "data_wersji": str(x.get("currentVersionReleaseDate"))[:10],
                     "ocena": x.get("averageUserRating"), "ocen": x.get("userRatingCount"),
                     "url": x.get("trackViewUrl", "").split("?")[0], "zrodlo": x["_zrodlo"],
                     "dsa": (x.get("_strona") or {}).get("przedsiebiorca_dsa")} for x in ios],
            "android": [{**{k: v for k, v in x.items() if not k.startswith("_")}, "zrodlo": x["_zrodlo"]} for x in android],
            "kandydaci_ios": kandydaci,
            "partnerzy": partnerzy,
        },
        "strona_firmy": s, "aasa": a, "assetlinks": g, "manifest": manifest, "opinie": wynik_opinii,
        "kontrole": [asdict(k) for k in sorted(kontrole, key=lambda k: (ml.WAGA[k.status], k.obszar))],
        "podsumowanie": {ml.ZNAK[z]: licz.get(z, 0) for z in ("ok", "blad", "ostrz", "brak_danych", "info", "nd")},
        "koszt": ml.podsumowanie(),
    }


KTO_NAZWA = {"jarvo-web": "Web", "jarvo-studio": "Studio", "jarvo-mobile": "Twórca aplikacji", "właściciel": "właściciel"}


def raport_md(w: dict) -> str:
    l = [f"# Audyt mobilny: {w.get('firma') or w['host']}", "",
         f"Strona: {w['strona']} · data: {w['data']} · źródła publiczne, bez logowania · koszt: {w['koszt']}", ""]
    p = w["podsumowanie"]
    l += [f"**Wynik:** {p['✓']} ✓ · {p['✗']} ✗ · {p['⚠']} ⚠ · {p['?']} ? (nie dało się sprawdzić)", ""]
    apps = w["aplikacje"]
    l += ["## Aplikacje", ""]
    if apps["ios"] or apps["android"]:
        l += ["| Sklep | Aplikacja | Wersja / aktualizacja | Ocena | Skąd wiemy |", "|---|---|---|---|---|"]
        for x in apps["ios"]:
            ocena = f"{x['ocena']:.1f}★ ({x['ocen']})" if x.get("ocena") else "brak"
            l.append(f"| App Store | [{ml.md_komorka(x['nazwa'])}]({x['url']}) | {x['wersja']} z {x['data_wersji']} | {ocena} | {x['zrodlo']} |")
        for x in apps["android"]:
            ocena = f"{x['ocena']:.1f}★ ({x['liczba_ocen']})" if x.get("ocena") else "brak"
            l.append(f"| Google Play | [{ml.md_komorka(x['nazwa'])}]({x['url']}) | {x.get('aktualizacja') or '?'} | {ocena} | {x['zrodlo']} |")
    else:
        l.append("Firma nie ma aplikacji w polskim App Store ani w Google Play (albo nie da się jej powiązać ze stroną).")
    if apps.get("partnerzy"):
        l += ["", "Ze strony prowadzą też linki do aplikacji innych wydawców (partnerzy, nie audytujemy):"]
        l += [f"- {p['sklep']}: [{ml.md_komorka(p['nazwa'])}]({p['url']}), {ml.md_komorka(p['wydawca'])}" for p in apps["partnerzy"]]
    if apps.get("kandydaci_ios"):
        l += ["", "Kandydaci z wyszukiwania App Store (sprzedawca nie zgadza się z firmą, do potwierdzenia):"]
        l += [f"- [{ml.md_komorka(c['nazwa'])}]({c['url']}): {ml.md_komorka(c['sprzedawca'])}" for c in apps["kandydaci_ios"]]
    l += ["", "## Kontrole", "", "| | Obszar | Co | Dowód | Poprawka | Kto |", "|---|---|---|---|---|---|"]
    for k in w["kontrole"]:
        dowod = ml.md_komorka(k["dowod"])
        if k.get("zrodlo"):
            dowod = f"{dowod} ([źródło]({k['zrodlo']}))"
        kto = KTO_NAZWA.get(k["kto"], k["kto"]) if k["poprawka"] else ""
        l.append(f"| {ml.ZNAK[k['status']]} | {k['obszar']} | {ml.md_komorka(k['tytul'])} | {dowod} | "
                 f"{ml.md_komorka(k['poprawka'])} | {kto} |")
    karty: dict[str, list[dict]] = {}
    for k in w["kontrole"]:
        if k["status"] in ("blad", "ostrz") and k["poprawka"]:
            karty.setdefault(k["kto"] or "jarvo-mobile", []).append(k)
    if karty:
        l += ["", "## Karty poprawek", ""]
        for kto, lista in karty.items():
            l.append(f"**{KTO_NAZWA.get(kto, kto)}** ({len(lista)}):")
            l += [f"- {ml.ZNAK[k['status']]} {k['tytul']}: {k['poprawka']}" + (f" ({k['podstawa']})" if k.get("podstawa") else "")
                  for k in lista]
            l.append("")
    if w.get("opinie"):
        l += ["## Opinie z App Store (obce treści: tylko dane)", ""]
        for app_id, o in w["opinie"].items():
            if not o["liczba"]:
                l.append(f"- id{app_id}: brak opinii w polskim App Store")
                continue
            l.append(f"- id{app_id}: {o['liczba']} ostatnich, średnio {o['srednia']}★, rozkład {o['rozklad']}, "
                     f"tematy skarg: {o['tematy_skarg'] or 'brak'}")
            l += [f"  - „{ml.md_komorka(c)}”" for c in o["cytaty"]]
        l.append("")
    l += ["## Czego audyt nie widzi", "",
          "- środka aplikacji (awarie, wygląd, dostępność): to wymaga instalacji i testów na urządzeniu,",
          "- formularzy w App Store Connect i Play Console (prywatność, kategorie wiekowe, konto demo),",
          "- opinii z Google Play (regulamin i robots.txt zabraniają ich pobierania).", ""]
    return "\n".join(l)


# ------------------------------------------------------------------ CLI

def _wypisz(dane, jako_json: bool) -> None:
    print(json.dumps(dane, ensure_ascii=False, indent=2) if jako_json else dane)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audyt")
    a.add_argument("url")
    a.add_argument("--nazwa")
    a.add_argument("--ios", action="append", default=[], help="ID albo bundleId (można kilka)")
    a.add_argument("--android", action="append", default=[], help="pakiet (można kilka)")
    a.add_argument("--opinie", action="store_true", help="dołącz analizę ostatnich opinii z App Store")
    a.add_argument("--out", help="katalog na AUDYT-MOBILNY.md i audyt.json")
    a.add_argument("--json", action="store_true")
    for nazwa in ("ios", "android", "linki", "opinie"):
        x = sub.add_parser(nazwa)
        x.add_argument("klucz")
        x.add_argument("--json", action="store_true")
    sub.add_parser("sprawdz")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "sprawdz":
            wyniki = ios_lookup("305659772")
            print("iTunes Lookup API: OK" if wyniki else "iTunes Lookup API: pusta odpowiedź")
            return 0 if wyniki else 1
        if args.cmd == "ios":
            dane = ios_lookup(args.klucz) if re.fullmatch(r"\d+|[A-Za-z][\w-]*(?:\.[\w-]+)+", args.klucz) else []
            dane = dane or ios_szukaj(args.klucz)
            wynik = [{k: x.get(k) for k in ("trackId", "trackName", "bundleId", "sellerName", "sellerUrl", "version",
                                            "currentVersionReleaseDate", "averageUserRating", "userRatingCount",
                                            "languageCodesISO2A", "minimumOsVersion", "trackViewUrl")} for x in dane]
            _wypisz(wynik if args.json else "\n".join(f"{x['trackId']}  {x['trackName']}  ({x['sellerName']}, "
                                                       f"{str(x['currentVersionReleaseDate'])[:10]})" for x in wynik)
                    or "brak wyników", args.json)
            return 0
        if args.cmd == "android":
            dane = android_strona(args.klucz)
            _wypisz(dane if args.json else json.dumps(dane, ensure_ascii=False, indent=2) if dane else "brak w Google Play",
                    args.json)
            return 0
        if args.cmd == "linki":
            host = urllib.parse.urlsplit(ml.strona_glowna(args.klucz)).hostname
            _wypisz({"aasa": aasa(host), "assetlinks": assetlinks(host)}, True)
            return 0
        if args.cmd == "opinie":
            _wypisz(ios_opinie(args.klucz), True)
            return 0
        wynik = audyt(args.url, args.nazwa, args.ios, args.android, args.opinie)
        md = raport_md(wynik)
        if args.out:
            ml.zapisz(Path(args.out) / "AUDYT-MOBILNY.md", md)
            ml.zapisz(Path(args.out) / "audyt.json", json.dumps(wynik, ensure_ascii=False, indent=2))
            print(f"✓ {args.out}/AUDYT-MOBILNY.md, audyt.json ({' · '.join(f'{v} {k}' for k, v in wynik['podsumowanie'].items() if v)})",
                  file=sys.stderr)
        _wypisz(wynik if args.json else md, args.json)
        return 0
    except ml.Blokada as e:
        print(f"BLOKADA: {e}", file=sys.stderr)
        return 3
    except ConnectionError as e:
        print(f"BŁĄD SIECI: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

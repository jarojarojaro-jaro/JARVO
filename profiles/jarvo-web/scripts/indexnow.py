#!/usr/bin/env python3
"""IndexNow: klucz strony i zgłoszenie adresów z sitemapy po wdrożeniu (tylko biblioteka standardowa).

    python3 indexnow.py klucz <projekt>/public [--json]
    python3 indexnow.py zglos https://domena.pl [--katalog <projekt>/public | --klucz KLUCZ]
                        [--url ADRES ...] [--na-sucho] [--json]

klucz   tworzy w katalogu (public/ projektu Astro, trafia do dist/) plik `<klucz>.txt` z kluczem (32 znaki hex).
        Katalog ma już ważny plik klucza → zwraca go bez zmian. Klucz jest jawny z założenia (leży na stronie).
zglos   1) klucz z --klucz albo z pliku klucza w --katalog, 2) adresy z --url albo z sitemapy produkcyjnej
        (wpisy `Sitemap:` z robots.txt, /sitemap-index.xml, /sitemap.xml; indeks sitemap rozwijany, .xml.gz też),
        tylko z hosta strony, 3) sprawdza, że https://<host>/<klucz>.txt zwraca klucz (bez tego nic nie wysyła),
        4) POST do https://api.indexnow.org/indexnow po 10 000 adresów. Wyszukiwarki IndexNow (m.in. Bing, Yandex,
        Seznam, Naver) dzielą się zgłoszeniami, więc jedno zgłoszenie wystarcza. Google IndexNow nie obsługuje
        (sitemap w Search Console). --na-sucho: kroki 1–3 i lista adresów, bez wysyłki.
        Nie zgłasza podglądów: localhost, adres IP i tymczasowe linki *.trycloudflare.com są odrzucane.

Kod wyjścia 0 przy odpowiedzi 200 albo 202 (202 = klucz jeszcze sprawdzany, adresy przyjęte), inaczej 1.
"""

from __future__ import annotations

import argparse
import gzip
import html
import ipaddress
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 jarvo-web-indexnow/1.0"
API = "https://api.indexnow.org/indexnow"
PACZKA = 10_000                      # limit adresów w jednym POST (protokół IndexNow)
LIMIT_MAPY = 50 * 1024 * 1024        # sitemap może mieć do 50 MB po rozpakowaniu
MAKS_MAP = 50                        # rozwinięte sitemapy z indeksu
KLUCZ_WZOR = re.compile(r"^[A-Za-z0-9-]{8,128}$")
ODPOWIEDZI = {
    200: "przyjęte",
    202: "przyjęte, klucz jeszcze sprawdzany (zgłoś ponownie przy następnej zmianie)",
    400: "zły format zgłoszenia",
    403: "klucz nieważny (brak pliku klucza albo inna treść)",
    422: "adresy spoza hosta albo klucz niezgodny ze schematem",
    429: "za dużo zgłoszeń (spam); zgłaszaj tylko po zmianach",
}
PODGLADY = ("localhost", ".localhost", ".local", ".trycloudflare.com")


def klucz_z_pliku(plik: Path) -> str | None:
    """Plik klucza IndexNow: nazwa `<klucz>.txt`, treść = ten sam klucz."""
    if plik.suffix != ".txt" or not KLUCZ_WZOR.match(plik.stem):
        return None
    try:
        tresc = plik.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return tresc if tresc == plik.stem else None


def znajdz_klucz(katalog: Path) -> str | None:
    klucze = sorted(k for p in katalog.glob("*.txt") if (k := klucz_z_pliku(p)))
    return klucze[0] if klucze else None


def utworz_klucz(katalog: Path) -> tuple[str, Path, bool]:
    katalog.mkdir(parents=True, exist_ok=True)
    if istniejacy := znajdz_klucz(katalog):
        return istniejacy, katalog / f"{istniejacy}.txt", False
    klucz = secrets.token_hex(16)
    plik = katalog / f"{klucz}.txt"
    plik.write_text(klucz + "\n", encoding="utf-8")
    return klucz, plik, True


def adres_podgladu(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host in ("localhost",) or any(host.endswith(p) for p in PODGLADY):
        return True
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def pobierz(url: str, limit: int = LIMIT_MAPY) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(limit + 1)[:limit]
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b""


def rozpakuj(dane: bytes) -> bytes:
    if dane[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(dane)[:LIMIT_MAPY]
        except (OSError, EOFError):
            return b""
    return dane


def lokacje(dane: bytes) -> tuple[bool, list[str]]:
    """(czy indeks sitemap, adresy z <loc>)."""
    tekst = dane.decode("utf-8", "replace")
    indeks = re.search(r"<sitemapindex\b", tekst) is not None
    locs = [html.unescape(m.strip()) for m in re.findall(r"<loc>\s*(.*?)\s*</loc>", tekst, re.S)]
    return indeks, locs


def mapy_startowe(baza: str, pobierz_=pobierz) -> list[str]:
    status, robots = pobierz_(urllib.parse.urljoin(baza, "/robots.txt"))
    z_robots = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots.decode("utf-8", "replace")) if status == 200 else []
    standardowe = [urllib.parse.urljoin(baza, s) for s in ("/sitemap-index.xml", "/sitemap.xml")]
    return list(dict.fromkeys(z_robots + standardowe))


def adresy_z_sitemap(baza: str, pobierz_=pobierz) -> tuple[list[str], list[str]]:
    """Adresy stron z sitemap hosta. Zwraca (adresy, przeczytane sitemapy)."""
    host = urllib.parse.urlsplit(baza).hostname
    kolejka, widziane, adresy, przeczytane = mapy_startowe(baza, pobierz_), set(), [], []
    while kolejka and len(widziane) < MAKS_MAP:
        mapa = kolejka.pop(0)
        if mapa in widziane or urllib.parse.urlsplit(mapa).hostname != host:
            continue
        widziane.add(mapa)
        status, dane = pobierz_(mapa)
        if status != 200 or not dane:
            continue
        dane = rozpakuj(dane)
        indeks, locs = lokacje(dane)
        if not indeks and b"<urlset" not in dane:
            continue
        przeczytane.append(mapa)
        if indeks:
            kolejka += [l for l in locs if l not in widziane]
        else:
            adresy += locs
    return list(dict.fromkeys(adresy)), przeczytane


def tylko_host(adresy: list[str], host: str) -> tuple[list[str], list[str]]:
    dobre, obce = [], []
    for a in adresy:
        cz = urllib.parse.urlsplit(a)
        (dobre if cz.scheme in ("http", "https") and cz.hostname == host else obce).append(a)
    return dobre, obce


def wyslij(host: str, klucz: str, adresy: list[str], api: str = API) -> list[dict]:
    wyniki = []
    for i in range(0, len(adresy), PACZKA):
        paczka = adresy[i:i + PACZKA]
        cialo = json.dumps({"host": host, "key": klucz,
                            "keyLocation": f"https://{host}/{klucz}.txt", "urlList": paczka}).encode()
        req = urllib.request.Request(api, data=cialo, method="POST", headers={
            "Content-Type": "application/json; charset=utf-8", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            status, opis = 0, f"brak połączenia: {e}"
            wyniki.append({"adresy": len(paczka), "status": status, "opis": opis})
            continue
        wyniki.append({"adresy": len(paczka), "status": status, "opis": ODPOWIEDZI.get(status, "nieznana odpowiedź")})
    return wyniki


def zglos(a, pobierz_=None, wyslij_=None) -> dict:
    pobierz_, wyslij_ = pobierz_ or pobierz, wyslij_ or wyslij
    baza = a.strona if "://" in a.strona else f"https://{a.strona}"
    cz = urllib.parse.urlsplit(baza)
    host = cz.hostname or ""
    w: dict = {"strona": baza, "host": host, "errors": [], "warnings": [], "info": []}
    if cz.scheme != "https" or not host:
        w["errors"].append("podaj produkcyjny adres https://domena")
        return w
    if adres_podgladu(host):
        w["errors"].append(f"{host} to podgląd albo adres lokalny: IndexNow tylko dla strony produkcyjnej")
        return w
    klucz = a.klucz or (znajdz_klucz(Path(a.katalog)) if a.katalog else None)
    if not klucz or not KLUCZ_WZOR.match(klucz):
        w["errors"].append("brak klucza: `indexnow.py klucz <projekt>/public`, wdrożenie, potem --katalog <projekt>/public")
        return w
    w["klucz"] = klucz
    if a.url:
        adresy, w["sitemapy"] = list(dict.fromkeys(a.url)), []
    else:
        adresy, w["sitemapy"] = adresy_z_sitemap(baza, pobierz_)
        if not w["sitemapy"]:
            w["errors"].append("brak sitemapy na stronie (robots.txt `Sitemap:`, /sitemap-index.xml, /sitemap.xml)")
            return w
    adresy, obce = tylko_host(adresy, host)
    if obce:
        w["warnings"].append(f"{len(obce)} adresów spoza {host} pominiętych, np. {obce[:3]}")
    if not adresy:
        w["errors"].append("brak adresów do zgłoszenia")
        return w
    w["adresy"] = len(adresy)
    plik = f"https://{host}/{klucz}.txt"
    status, dane = pobierz_(plik, 1024)
    if status != 200 or dane.decode("utf-8", "replace").strip() != klucz:
        w["errors"].append(f"{plik} nie zwraca klucza (HTTP {status}): wdróż stronę z plikiem klucza i spróbuj ponownie")
        return w
    w["info"].append(f"plik klucza: {plik}")
    if a.na_sucho:
        w["info"].append("na sucho: nic nie wysłano")
        w["przyklady"] = adresy[:10]
        return w
    w["wyslane"] = wyslij_(host, klucz, adresy)
    for p in w["wyslane"]:
        if p["status"] not in (200, 202):
            w["errors"].append(f"IndexNow HTTP {p['status']}: {p['opis']}")
    return w


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("klucz", help="plik klucza IndexNow w public/ projektu")
    k.add_argument("katalog")
    k.add_argument("--json", action="store_true")
    z = sub.add_parser("zglos", help="zgłoś adresy z sitemapy wdrożonej strony")
    z.add_argument("strona")
    z.add_argument("--katalog", help="public/ albo dist/ z plikiem klucza")
    z.add_argument("--klucz")
    z.add_argument("--url", action="append", help="tylko te adresy (można powtórzyć)")
    z.add_argument("--na-sucho", action="store_true")
    z.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "klucz":
        klucz, plik, nowy = utworz_klucz(Path(a.katalog))
        wynik = {"klucz": klucz, "plik": str(plik), "nowy": nowy}
        print(json.dumps(wynik, ensure_ascii=False) if a.json else
              f"{'utworzony' if nowy else 'już jest'}: {plik} (po wdrożeniu: https://<domena>/{klucz}.txt)")
        return 0

    w = zglos(a)
    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=2))
    else:
        print(f"IndexNow {w['host']}: {w.get('adresy', 0)} adresów")
        for poziom in ("errors", "warnings", "info"):
            for t in w[poziom]:
                print(f"  {poziom[:-1].upper()}: {t}")
        for p in w.get("wyslane", []):
            print(f"  HTTP {p['status']} ({p['adresy']} adresów): {p['opis']}")
    return 1 if w["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

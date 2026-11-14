#!/usr/bin/env python3
"""Lejek klientów jarodev.pl: wpisy z grup FB, Map Google i audytów, statusy, liczby, retencja RODO, limity dnia.

    lejek.py [--katalog DIR] init [--zrodla PLIK]
    lejek.py [--katalog DIR] dodaj --zrodlo fb-grupa --rodzaj osoba --nazwa "Anna K." --link URL --potrzeba "..."
             [--data RRRR-MM-DD] [--miasto M] [--uwaga TEKST] [--json]
    lejek.py [--katalog DIR] status L-0001 szkic|zaakceptowany|wyslany|rozmowa|klient|odpada|nowy
             [--zgoda "„tak” właściciela, data"] [--kanal fb-komentarz] [--uwaga TEKST]
    lejek.py [--katalog DIR] lista [--status S] [--zrodlo Z] [--json]
    lejek.py [--katalog DIR] stats [--json]
    lejek.py [--katalog DIR] retencja [--dni 90] [--wykonaj]
    lejek.py [--katalog DIR] licz RODZAJ [--limit N] [--ile 1] [--sprawdz]

Katalog lejka: --katalog, potem JARODEV_LEJEK, potem <dane>/jarvo/workspaces/jarvo-jarodev/lejek (z JARVO_DATA_DIR
albo HERMES_HOME profilu), w ostateczności ./lejek. Pliki: lejek.json (źródło prawdy, zapis atomowy), lejek.csv
(eksport po każdej zmianie), limity.json (liczniki dnia). `init` zakłada katalog i kopiuje wzór zrodla.yaml
(grupy FB i portale od właściciela) obok katalogu lejka, jeśli go jeszcze nie ma; nigdy go nie nadpisuje.

Statusy: nowy → szkic → zaakceptowany → wyslany → rozmowa → klient, z każdego → odpada, odpada → nowy.
`zaakceptowany` wymaga --zgoda (czyje „tak” i kiedy), `wyslany` wymaga --kanal. Firma z Map albo audytu (zrodlo
mapy, audyt) nie dostaje maila, telefonu, SMS-a, formularza ani wiadomości na Facebooku bez jej zgody (art. 398
Prawa komunikacji elektronicznej): kanał spoza KANALY_FIRMY to kod 3. Osoba z posta (rodzaj osoba): tylko link
do posta, wyświetlana nazwa, potrzeba i data (RODO, minimum danych); e-mail albo telefon w polach to kod 2.
Retencja: osoba bez kontaktu (nowy, szkic, zaakceptowany, odpada) starsza niż --dni znika (bez --wykonaj: podgląd).
Duplikat nie jest dopisywany: osoba = ten sam link (bez parametrów śledzących) i ta sama nazwa, firma = ten sam link
albo, bez linku, ta sama nazwa i miasto.

Kody wyjścia: 0 ok (także duplikat: `"duplikat": "L-…"`), 1 błąd odczytu/zapisu, 2 złe dane, 3 odmowa (zgoda,
kanał, limit dnia).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
WZOR_ZRODEL = HERE / "zrodla.wzor.yaml"

STATUSY = ("nowy", "szkic", "zaakceptowany", "wyslany", "rozmowa", "klient", "odpada")
PRZEJSCIA = {"nowy": {"szkic", "odpada"}, "szkic": {"zaakceptowany", "nowy", "odpada"},
             "zaakceptowany": {"wyslany", "szkic", "odpada"}, "wyslany": {"rozmowa", "klient", "odpada"},
             "rozmowa": {"klient", "odpada"}, "klient": {"odpada"}, "odpada": {"nowy"}}
ZRODLA = ("fb-grupa", "fb-post", "mapy", "audyt", "portal", "polecenie", "inne")
RODZAJE = ("osoba", "firma")
ZRODLA_FIRM_BEZ_ZGODY = {"mapy", "audyt"}          # firma nie pytała: tylko kanały bez informacji handlowej na urządzenie
KANALY = ("fb-komentarz", "fb-wiadomosc", "email", "telefon", "sms", "formularz", "list", "osobiscie", "odpowiedz")
KANALY_FIRMY = {"list", "osobiscie", "odpowiedz"}   # odpowiedz = firma sama napisała albo zadzwoniła pierwsza
BEZ_KONTAKTU = {"nowy", "szkic", "zaakceptowany", "odpada"}
PARAMETRY_SLEDZACE = re.compile(r"^(utm_.*|fbclid|gclid|__cft__.*|__tn__|ref|refsrc|mibextid|rdid|share_url)$", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TELEFON = re.compile(r"(?<!\d)(?:\+?48[\s-]?)?(?:\d[\s-]?){9}(?!\d)")
LIMITY_DOMYSLNE = {"fb-grupy": 10, "fb-komentarze": 5, "fb-posty": 1, "mapy": 25, "audyty": 10}
POLA_CSV = ("id", "status", "zrodlo", "rodzaj", "nazwa", "miasto", "link", "potrzeba", "data", "kontakt", "kanal",
            "utworzono", "zmieniono", "uwaga")


class Blad(Exception):
    def __init__(self, tekst: str, kod: int = 2):
        super().__init__(tekst)
        self.kod = kod


def dzis() -> dt.date:
    return dt.date.fromisoformat(os.environ["JARODEV_DZIS"]) if os.environ.get("JARODEV_DZIS") else dt.date.today()


def domyslny_katalog() -> Path:
    if os.environ.get("JARODEV_LEJEK"):
        return Path(os.environ["JARODEV_LEJEK"])
    jd = os.environ.get("JARVO_DATA_DIR")
    if not jd and os.environ.get("HERMES_HOME"):
        h = Path(os.environ["HERMES_HOME"])
        jd = str((h.parent.parent if h.parent.name == "profiles" else h) / "jarvo")
    return Path(jd) / "workspaces" / "jarvo-jarodev" / "lejek" if jd else Path("lejek")


# ------------------------------------------------------------------------------------------------ zapis i odczyt

def zapisz_atomowo(plik: Path, tresc: str) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{plik.name}.", dir=str(plik.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(tresc)
        os.replace(tmp, plik)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def wczytaj(kat: Path) -> dict:
    plik = kat / "lejek.json"
    if not plik.exists():
        return {"wersja": 1, "nastepny": 1, "wpisy": []}
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Blad(f"{plik}: {e}", 1) from None
    if not isinstance(dane, dict) or not isinstance(dane.get("wpisy"), list):
        raise Blad(f"{plik}: to nie jest lejek (brak listy wpisy)", 1)
    return dane


def zapisz(kat: Path, dane: dict) -> None:
    zapisz_atomowo(kat / "lejek.json", json.dumps(dane, ensure_ascii=False, indent=1) + "\n")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=POLA_CSV, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for wpis in dane["wpisy"]:
        w.writerow({k: wpis.get(k, "") for k in POLA_CSV})
    zapisz_atomowo(kat / "lejek.csv", buf.getvalue())


# ------------------------------------------------------------------------------------------------ logika

def zloz(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst.replace("ł", "l").replace("Ł", "L"))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip().lower()


def czysty_link(url: str) -> str:
    """Link bez fragmentu, parametrów śledzących i końcowego „/”; host małymi literami, m. i www. jak bez nich."""
    p = urllib.parse.urlsplit(url.strip())
    host = p.netloc.lower()
    for prefiks in ("www.", "m.", "mbasic.", "web."):
        if host.startswith(prefiks):
            host = host[len(prefiks):]
            break
    zapytanie = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
                 if not PARAMETRY_SLEDZACE.match(k)]
    return urllib.parse.urlunsplit(("https", host, p.path.rstrip("/"), urllib.parse.urlencode(sorted(zapytanie)), ""))


def klucz(wpis: dict) -> str:
    """Osoba: link (posta albo grupy) + nazwa, bo w aplikacji FB link posta bywa niewidoczny i zostaje link grupy;
    firma: link wizytówki albo strony, a bez linku nazwa + miasto."""
    if wpis.get("rodzaj") == "osoba":
        return "osoba:" + czysty_link(wpis.get("link", "")) + "|" + zloz(wpis.get("nazwa", ""))
    if wpis.get("link"):
        return "link:" + czysty_link(wpis["link"])
    return "firma:" + zloz(wpis.get("nazwa", "")) + "|" + zloz(wpis.get("miasto", ""))


def sprawdz_dane_osoby(pola: dict) -> None:
    """Osoba z posta: bez maila i telefonu w lejku (RODO, minimum danych; kontakt idzie przez post)."""
    for nazwa in ("nazwa", "potrzeba", "uwaga", "miasto"):
        tekst = pola.get(nazwa) or ""
        if EMAIL.search(tekst) or TELEFON.search(tekst):
            raise Blad(f"--{nazwa}: e-mail albo telefon osoby prywatnej nie trafia do lejka (RODO, minimum danych): "
                       "zostaw link do posta, nazwę, potrzebę i datę")


def dodaj(dane: dict, pola: dict) -> tuple[dict, bool]:
    if pola["zrodlo"] not in ZRODLA:
        raise Blad(f"--zrodlo: jedno z {', '.join(ZRODLA)}")
    if pola["rodzaj"] not in RODZAJE:
        raise Blad("--rodzaj: osoba albo firma")
    if not (pola.get("nazwa") or "").strip():
        raise Blad("--nazwa: wyświetlana nazwa osoby albo nazwa firmy")
    if not (pola.get("potrzeba") or "").strip():
        raise Blad("--potrzeba: czego szuka albo co da się poprawić (powód wpisu)")
    if pola.get("link") and urllib.parse.urlsplit(pola["link"]).scheme not in ("http", "https"):
        raise Blad("--link: adres http(s) posta, wizytówki w Mapach albo strony firmy")
    if pola["rodzaj"] == "osoba":
        if not pola.get("link"):
            raise Blad("--link: osoba z posta ma link do posta (źródło i jedyny kanał kontaktu)")
        sprawdz_dane_osoby(pola)
    data = pola.get("data") or dzis().isoformat()
    try:
        dt.date.fromisoformat(data)
    except ValueError:
        raise Blad("--data: RRRR-MM-DD (dzień posta albo znalezienia)") from None
    wpis = {k: (pola.get(k) or "").strip() for k in ("zrodlo", "rodzaj", "nazwa", "miasto", "link", "potrzeba", "uwaga")}
    k = klucz(wpis)
    for inny in dane["wpisy"]:
        if inny.get("klucz") == k:
            return inny, False
    teraz = dt.datetime.now().replace(microsecond=0).isoformat()
    wpis.update(id=f"L-{dane['nastepny']:04d}", klucz=k, status="nowy", data=data, kontakt="", kanal="",
                utworzono=teraz, zmieniono=teraz, historia=[{"kiedy": teraz, "status": "nowy"}])
    dane["nastepny"] += 1
    dane["wpisy"].append(wpis)
    return wpis, True


def zmien_status(dane: dict, ident: str, nowy: str, zgoda: str = "", kanal: str = "", uwaga: str = "") -> dict:
    wpis = next((w for w in dane["wpisy"] if w["id"] == ident), None)
    if wpis is None:
        raise Blad(f"nie ma wpisu {ident}")
    if nowy not in STATUSY:
        raise Blad(f"status: jeden z {', '.join(STATUSY)}")
    if nowy not in PRZEJSCIA[wpis["status"]]:
        raise Blad(f"{ident}: z {wpis['status']} nie przejdziesz do {nowy} "
                   f"(dozwolone: {', '.join(sorted(PRZEJSCIA[wpis['status']]))})")
    if nowy == "zaakceptowany" and not zgoda.strip():
        raise Blad(f"{ident}: zaakceptowany = „tak” właściciela dla tego szkicu; podaj --zgoda (kto, kiedy, cytat)", 3)
    if nowy == "wyslany":
        if kanal not in KANALY:
            raise Blad(f"--kanal: jeden z {', '.join(KANALY)}")
        if wpis["zrodlo"] in ZRODLA_FIRM_BEZ_ZGODY and kanal not in KANALY_FIRMY:
            raise Blad(f"{ident}: firma z {wpis['zrodlo']} nie pytała, a {kanal} to informacja handlowa na jej urządzenie "
                       "bez zgody (art. 398 Prawa komunikacji elektronicznej). Kanał wybiera właściciel: list, "
                       "spotkanie (osobiscie) albo odpowiedź, gdy firma odezwała się pierwsza (odpowiedz).", 3)
        wpis["kontakt"], wpis["kanal"] = dzis().isoformat(), kanal
    teraz = dt.datetime.now().replace(microsecond=0).isoformat()
    krok = {"kiedy": teraz, "status": nowy}
    if zgoda.strip():
        krok["zgoda"] = zgoda.strip()
    if kanal:
        krok["kanal"] = kanal
    if uwaga.strip():
        krok["uwaga"] = uwaga.strip()
        wpis["uwaga"] = uwaga.strip()
    wpis["historia"].append(krok)
    wpis["status"], wpis["zmieniono"] = nowy, teraz
    return wpis


def statystyki(dane: dict) -> dict:
    wpisy = dane["wpisy"]
    po_statusie = {s: sum(w["status"] == s for w in wpisy) for s in STATUSY}
    po_zrodle = {z: sum(w["zrodlo"] == z for w in wpisy) for z in ZRODLA if any(w["zrodlo"] == z for w in wpisy)}
    d = dzis().isoformat()
    wyslane = sum(1 for w in wpisy if w.get("kontakt"))
    return {"wpisy": len(wpisy), "po_statusie": po_statusie, "po_zrodle": po_zrodle,
            "dzis_nowe": sum(w["utworzono"][:10] == d for w in wpisy),
            "czeka_na_zgode": [w["id"] for w in wpisy if w["status"] == "szkic"],
            "do_wyslania": [w["id"] for w in wpisy if w["status"] == "zaakceptowany"],
            "wyslane": wyslane, "klienci": po_statusie["klient"],
            "konwersja": round(po_statusie["klient"] / wyslane, 3) if wyslane else None}


def retencja(dane: dict, dni: int, wykonaj: bool) -> list[dict]:
    """Osoby bez kontaktu starsze niż `dni` (od daty posta): RODO, nie trzymamy danych bez celu."""
    granica = dzis() - dt.timedelta(days=dni)
    stare = [w for w in dane["wpisy"] if w["rodzaj"] == "osoba" and w["status"] in BEZ_KONTAKTU
             and not w.get("kontakt") and dt.date.fromisoformat(w["data"]) < granica]
    if wykonaj:
        ids = {w["id"] for w in stare}
        dane["wpisy"] = [w for w in dane["wpisy"] if w["id"] not in ids]
    return stare


def licz(kat: Path, rodzaj: str, limit: int | None, ile: int, tylko_sprawdz: bool) -> dict:
    plik = kat / "limity.json"
    try:
        stan = json.loads(plik.read_text(encoding="utf-8")) if plik.exists() else {}
    except (OSError, ValueError):
        stan = {}
    d = dzis().isoformat()
    if stan.get("dzien") != d:
        stan = {"dzien": d, "liczniki": {}}
    granica = limit if limit is not None else LIMITY_DOMYSLNE.get(rodzaj)
    if granica is None:
        raise Blad(f"{rodzaj}: brak domyślnego limitu ({', '.join(LIMITY_DOMYSLNE)}); podaj --limit z zrodla.yaml")
    jest = int(stan["liczniki"].get(rodzaj, 0))
    if jest + ile > granica:
        raise Blad(f"limit dnia {rodzaj}: {jest}/{granica}; jutro albo wyższy limit od właściciela (zrodla.yaml)", 3)
    if not tylko_sprawdz:
        stan["liczniki"][rodzaj] = jest + ile
        zapisz_atomowo(plik, json.dumps(stan, ensure_ascii=False, indent=1) + "\n")
        jest += ile
    return {"rodzaj": rodzaj, "dzis": jest, "limit": granica, "zostalo": granica - jest}


def init(kat: Path, zrodla: Path) -> dict:
    kat.mkdir(parents=True, exist_ok=True)
    wynik = {"katalog": str(kat), "lejek": "jest" if (kat / "lejek.json").exists() else "nowy"}
    if wynik["lejek"] == "nowy":
        zapisz(kat, wczytaj(kat))
    if zrodla.exists():
        wynik["zrodla"] = "jest (nie nadpisuję)"
    else:
        zrodla.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WZOR_ZRODEL, zrodla)
        wynik["zrodla"] = "skopiowany wzór: grupy i portale wpisuje właściciel"
    wynik["plik_zrodel"] = str(zrodla)
    return wynik


# ------------------------------------------------------------------------------------------------ wyjście

def wiersz(w: dict) -> str:
    gdzie = f", {w['miasto']}" if w.get("miasto") else ""
    return f"{w['id']} [{w['status']}] {w['zrodlo']}/{w['rodzaj']}: {w['nazwa']}{gdzie} | {w['potrzeba']} | {w['link'] or '-'}"


def wypisz(obj, jako_json: bool, tekst: str) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1) if jako_json else tekst)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--katalog", type=Path, help="katalog lejka (domyślnie workspace jarvo-jarodev/lejek)")
    sub = ap.add_subparsers(dest="polecenie", required=True)
    s = sub.add_parser("init", help="katalog lejka i wzór zrodla.yaml (bez nadpisywania)")
    s.add_argument("--zrodla", type=Path, help="plik źródeł (domyślnie <katalog>/../zrodla.yaml)")
    s = sub.add_parser("dodaj", help="nowy wpis (duplikat nie jest dopisywany)")
    s.add_argument("--zrodlo", required=True, choices=ZRODLA)
    s.add_argument("--rodzaj", required=True, choices=RODZAJE)
    s.add_argument("--nazwa", required=True)
    s.add_argument("--potrzeba", required=True)
    s.add_argument("--link", default="")
    s.add_argument("--miasto", default="")
    s.add_argument("--data", default="")
    s.add_argument("--uwaga", default="")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("status", help="zmiana statusu wpisu")
    s.add_argument("id")
    s.add_argument("nowy", choices=STATUSY)
    s.add_argument("--zgoda", default="")
    s.add_argument("--kanal", default="")
    s.add_argument("--uwaga", default="")
    s = sub.add_parser("lista", help="wpisy (filtry: status, źródło)")
    s.add_argument("--status", choices=STATUSY)
    s.add_argument("--zrodlo", choices=ZRODLA)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("stats", help="liczby lejka")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("retencja", help="osoby bez kontaktu starsze niż --dni (bez --wykonaj: podgląd)")
    s.add_argument("--dni", type=int, default=90)
    s.add_argument("--wykonaj", action="store_true")
    s = sub.add_parser("licz", help="licznik dnia (grupy, komentarze, posty, mapy, audyty) z limitem")
    s.add_argument("rodzaj")
    s.add_argument("--limit", type=int)
    s.add_argument("--ile", type=int, default=1)
    s.add_argument("--sprawdz", action="store_true", help="tylko sprawdź, czy mieści się w limicie")
    a = ap.parse_args(argv)
    kat = a.katalog or domyslny_katalog()
    try:
        if a.polecenie == "init":
            w = init(kat, a.zrodla or kat.parent / "zrodla.yaml")
            print(json.dumps(w, ensure_ascii=False))
        elif a.polecenie == "dodaj":
            dane = wczytaj(kat)
            wpis, nowy = dodaj(dane, vars(a))
            if nowy:
                zapisz(kat, dane)
            wynik = {"id": wpis["id"], "nowy": nowy, **({} if nowy else {"duplikat": wpis["id"]})}
            wypisz(wynik, a.json, ("dodany " if nowy else "duplikat, bez zmian: ") + wiersz(wpis))
        elif a.polecenie == "status":
            dane = wczytaj(kat)
            wpis = zmien_status(dane, a.id, a.nowy, a.zgoda, a.kanal, a.uwaga)
            zapisz(kat, dane)
            print(wiersz(wpis))
        elif a.polecenie == "lista":
            wpisy = [w for w in wczytaj(kat)["wpisy"] if (not a.status or w["status"] == a.status)
                     and (not a.zrodlo or w["zrodlo"] == a.zrodlo)]
            wypisz(wpisy, a.json, "\n".join(wiersz(w) for w in wpisy) or "(pusto)")
        elif a.polecenie == "stats":
            st = statystyki(wczytaj(kat))
            wypisz(st, a.json, "\n".join(f"{k}: {v}" for k, v in st.items()))
        elif a.polecenie == "retencja":
            dane = wczytaj(kat)
            stare = retencja(dane, a.dni, a.wykonaj)
            if a.wykonaj and stare:
                zapisz(kat, dane)
            print(json.dumps({"dni": a.dni, "usuniete" if a.wykonaj else "do_usuniecia": [w["id"] for w in stare]},
                             ensure_ascii=False))
        elif a.polecenie == "licz":
            print(json.dumps(licz(kat, a.rodzaj, a.limit, a.ile, a.sprawdz), ensure_ascii=False))
    except Blad as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return e.kod
    except OSError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

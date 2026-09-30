#!/usr/bin/env python3
"""Przetargi jako sygnały Łowcy: e-Zamówienia (BZP) i TED, oficjalne API bez klucza.

    przetargi.py bzp --od 2026-09-22 [--do 2026-09-29] [--cpv 72,48] [--woj PL14,ŚLĄSKIE] [--wyniki] [--szukaj "strona www"] [-o sygnaly.jsonl]
    przetargi.py ted --od 2026-09-01 [--do …] [--cpv 72] [--kraj POL] [-o sygnaly.jsonl]
    przetargi.py sprawdz bzp|ted                            # healthcheck: jedno małe zapytanie, kod 3 = blokada

BZP `--wyniki`: ogłoszenia o udzieleniu zamówienia, a firmą-sygnałem jest **zwycięzca** (NIP, miasto): właśnie dostał
pracę do wykonania, więc potrzebuje podwykonawców, sprzętu, ludzi. Bez `--wyniki`: ogłoszenia o zamówieniu, a
sygnałem jest **zamawiający** (kupuje teraz to, co opisuje przedmiot). CPV to prefiksy (72 = usługi IT).
BZP zwraca do 500 ogłoszeń na zapytanie, więc skrypt pyta dzień po dniu; dzień z pełnymi 500 dostaje ostrzeżenie.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402

BZP = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
BZP_LINK = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{}"
TED = "https://api.ted.europa.eu/v3/notices/search"
MAX_BZP = 500


def dni(od: str, do: str):
    d, k = dt.date.fromisoformat(od), dt.date.fromisoformat(do)
    while d <= k:
        yield d.isoformat()
        d += dt.timedelta(days=1)


def cpv_kody(pole: str | None) -> list[str]:
    return re.findall(r"\b(\d{8})-\d", pole or "")


def pasuje_cpv(kody: list[str], prefiksy: list[str]) -> bool:
    return not prefiksy or any(k.startswith(p) for k in kody for p in prefiksy)


def tekst(html_body: str | None, n: int = 600) -> str:
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_body or "")))
    return t[:n]


def bzp_sygnaly(n: dict, wyniki: bool) -> list[dict]:
    kody = cpv_kody(n.get("cpvCode"))
    link = BZP_LINK.format(n["objectId"]) if n.get("objectId") else "https://ezamowienia.gov.pl"
    data = (n.get("publicationDate") or "")[:10]
    przedmiot = (n.get("orderObject") or "").strip()
    zam = {"nazwa": n.get("organizationName"), "nip": ll.nip(n.get("organizationNationalId")),
           "miejscowosc": n.get("organizationCity"), "woj": ll.WOJ.get(n.get("organizationProvince") or "", n.get("organizationProvince"))}
    wspolne = {"data": data, "zrodlo": link, "szczegoly": {"numer": n.get("noticeNumber"), "cpv": kody, "rodzaj": n.get("orderType"),
                                                           "termin_ofert": (n.get("submittingOffersDate") or "")[:16] or None,
                                                           "zamawiajacy": zam["nazwa"], "przedmiot": przedmiot[:300]}}
    if not wyniki:
        return [{"typ": "przetarg-ogloszenie", "opis": f"przetarg: {przedmiot[:160]}", "firma": zam, "kontakty": [], **wspolne}]
    out = []
    for c in n.get("contractors") or []:
        firma = {"nazwa": c.get("contractorName"), "nip": ll.nip(c.get("contractorNationalId")), "miejscowosc": c.get("contractorCity"),
                 "woj": ll.WOJ.get(c.get("contractorProvince") or "", c.get("contractorProvince"))}
        out.append({"typ": "przetarg-wygrany", "opis": f"wygrał przetarg ({zam['nazwa']}): {przedmiot[:140]}", "firma": firma,
                    "kontakty": [], **wspolne})
    return out


def bzp(od: str, do: str, cpv: list[str], woj: list[str], wyniki: bool, szukaj: str | None) -> tuple[list[dict], list[str]]:
    rodzaj = "TenderResultNotice" if wyniki else "ContractNotice"
    out, uwagi = [], []
    fraza = (szukaj or "").lower()
    for dzien in dni(od, do):
        nast = (dt.date.fromisoformat(dzien) + dt.timedelta(days=1)).isoformat()
        def pobierz(kod_woj):
            q = f"{BZP}?NoticeType={rodzaj}&PublicationDateFrom={dzien}&PublicationDateTo={nast}&PageSize={MAX_BZP}"
            if kod_woj:
                q += f"&OrganizationProvince={kod_woj}"
            return ll.json_z(q, pamiec_h=6, max_mb=60, timeout=90) or []   # pełny HTML ogłoszeń: kilka MB na dzień

        lista = []
        for kod_woj in [ll.WOJ_KOD.get(w, w) for w in woj] or [None]:
            czesci = [pobierz(kod_woj)]
            if kod_woj is None and len(czesci[0]) >= MAX_BZP:  # API nie stronicuje: pełny dzień dzielimy na województwa
                czesci = [pobierz(k) for k in ll.WOJ]
            if any(len(c) >= MAX_BZP for c in czesci):
                uwagi.append(f"{dzien}{' ' + kod_woj if kod_woj else ''}: pełne {MAX_BZP} ogłoszeń w jednym zapytaniu, mogło czegoś brakować")
            lista += [n for c in czesci for n in c]
        for n in lista:
            if (n.get("publicationDate") or "")[:10] != dzien:
                continue                                      # okno API obejmuje też początek następnego dnia
            if not pasuje_cpv(cpv_kody(n.get("cpvCode")), cpv):
                continue
            if fraza and fraza not in (n.get("orderObject") or "").lower() and fraza not in tekst(n.get("htmlBody"), 20000).lower():
                continue
            out.extend(bzp_sygnaly(n, wyniki))
    return out, uwagi


def ted(od: str, do: str, cpv: list[str], kraj: str) -> list[dict]:
    warunki = [f"buyer-country={kraj}", f"publication-date>={od.replace('-', '')}", f"publication-date<={do.replace('-', '')}"]
    if cpv:
        warunki.append("(" + " OR ".join(f"classification-cpv={p.ljust(8, '0')}" for p in cpv) + ")")
    import json
    notices = []
    for strona in range(1, 9):                                    # do 2000 ogłoszeń; więcej = zawęź CPV albo okres
        zapytanie = {"query": " AND ".join(warunki), "limit": 250, "page": strona,
                     "fields": ["publication-number", "notice-title", "buyer-name", "publication-date", "classification-cpv",
                                "notice-type", "deadline-receipt-tender-date-lot", "links"]}
        kod, tresc = ll.http(TED, metoda="POST", dane=zapytanie, pamiec_h=6)
        if kod != 200:
            raise ConnectionError(f"TED {kod}: {tresc[:200]}")
        partia = json.loads(tresc).get("notices", [])
        notices += partia
        if len(partia) < 250:
            break
    out = []
    for n in notices:
        tytul = n.get("notice-title") or {}
        tytul = tytul.get("pol") or next(iter(tytul.values()), "") if isinstance(tytul, dict) else str(tytul)
        kup = n.get("buyer-name") or {}
        kup = (kup.get("pol") or next(iter(kup.values()), [""]))[0] if isinstance(kup, dict) else str(kup)
        nr = n.get("publication-number")
        out.append({"typ": "przetarg-ted", "data": (n.get("publication-date") or "")[:10],
                    "zrodlo": f"https://ted.europa.eu/pl/notice/-/detail/{nr}", "opis": f"przetarg UE: {str(tytul)[:160]}",
                    "firma": {"nazwa": kup, "nip": None}, "kontakty": [],
                    "szczegoly": {"numer": nr, "cpv": n.get("classification-cpv"), "rodzaj": n.get("notice-type"),
                                  "termin_ofert": (n.get("deadline-receipt-tender-date-lot") or [None])[0]}})
    return out


def sprawdz(zrodlo: str) -> str:
    """Jedno najmniejsze zapytanie bez pamięci (healthcheck): czy źródło odpowiada danymi, a nie stroną blokady."""
    if zrodlo == "bzp":
        wczoraj = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        lista = ll.json_z(f"{BZP}?NoticeType=ContractNotice&PublicationDateFrom={wczoraj}&PublicationDateTo={wczoraj}"
                          "&PageSize=1&OrganizationProvince=PL14", pamiec_h=0, timeout=30)
        if not isinstance(lista, list):
            raise ConnectionError("BZP: odpowiedź bez listy ogłoszeń")
        return f"BZP odpowiada ({len(lista)} ogłoszenie z {wczoraj})"
    kod, tresc = ll.http(TED, metoda="POST", dane={"query": "buyer-country=POL", "limit": 1, "fields": ["publication-number"]},
                         pamiec_h=0, timeout=30)
    if kod != 200 or "notices" not in tresc[:200]:
        raise ConnectionError(f"TED {kod}: {tresc[:200]}")
    return "TED odpowiada"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    dzis = dt.date.today().isoformat()
    for nazwa in ("bzp", "ted"):
        s = sub.add_parser(nazwa)
        s.add_argument("--od", required=True)
        s.add_argument("--do", default=dzis)
        s.add_argument("--cpv", help="prefiksy CPV po przecinku, np. 72,48,79341")
        s.add_argument("-o", help="dopisz sygnały do pliku JSONL (domyślnie wypisz)")
        if nazwa == "bzp":
            s.add_argument("--woj", help="województwa (kod PL14 albo nazwa) po przecinku")
            s.add_argument("--wyniki", action="store_true", help="wyniki przetargów: sygnałem jest zwycięzca")
            s.add_argument("--szukaj", help="fraza w przedmiocie albo treści ogłoszenia")
        else:
            s.add_argument("--kraj", default="POL")
    s = sub.add_parser("sprawdz", help="healthcheck: jedno małe zapytanie do źródła")
    s.add_argument("zrodlo", choices=("bzp", "ted"))
    a = ap.parse_args(argv)
    if a.cmd == "sprawdz":
        try:
            print(f"✓ {sprawdz(a.zrodlo)}")
            return 0
        except ll.Blokada as e:
            print(f"✗ blokada: {e}", file=sys.stderr)
            return 3
        except ConnectionError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
    cpv = [c.strip() for c in (a.cpv or "").split(",") if c.strip()]
    try:
        if a.cmd == "bzp":
            woj = [w.strip().upper() for w in (a.woj or "").split(",") if w.strip()]
            wiersze, uwagi = bzp(a.od, a.do, cpv, woj, a.wyniki, a.szukaj)
        else:
            wiersze, uwagi = ted(a.od, a.do, cpv, a.kraj), []
    except ll.Blokada as e:
        print(f"✗ blokada: {e}", file=sys.stderr)
        return 3
    ll.zapisz_jsonl(wiersze, a.o)
    for u in uwagi:
        print(f"! {u}", file=sys.stderr)
    print(f"✓ {a.cmd} {a.od}–{a.do}: {len(wiersze)} sygnałów ({ll.podsumowanie()})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

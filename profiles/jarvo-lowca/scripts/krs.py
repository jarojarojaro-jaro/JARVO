#!/usr/bin/env python3
"""KRS (API Ministerstwa Sprawiedliwości, bez klucza): odpisy firm i dzienny biuletyn wpisów → sygnały Łowcy.

    krs.py odpis 0000019193 [1269896 …] [--json]           # dane firmy: NIP, PKD, adres, województwo, kapitał, e-mail, www
    krs.py biuletyn 2026-09-29 [--nowe] [--pkd 62,63.1] [--woj MAZOWIECKIE,PL12] [--limit 800] [-o sygnaly.jsonl]

`biuletyn`: podmioty z wpisem danego dnia (kilka tysięcy). Każdy odpis to jedno zapytanie (pauza LOWCA_PAUZA,
pamięć odpowiedzi), więc filtry i `--limit` trzymają koszt w ryzach. `--nowe`: tylko firmy zarejestrowane tego dnia
(numery KRS od najwyższych; koniec po 40 kolejnych starszych). Sygnały: `krs-nowa-firma` albo `krs-wpis`.
Nazwiska zarządu API maskuje: w odpisie są tylko funkcje. E-mail z KRS dostaje typ (ogólny, rolowy, osobowy).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402

API = "https://api-krs.ms.gov.pl/api"
KONIEC_NOWYCH = 40


def url_odpisu(krs: str, rejestr: str) -> str:
    return f"{API}/krs/OdpisAktualny/{int(krs):010d}?rejestr={rejestr}&format=json"


def _data(d: str | None) -> str | None:
    """„29.09.2026” → „2026-09-29”."""
    if not d or d.count(".") != 2:
        return d
    dd, mm, rr = d.split(".")
    return f"{rr}-{mm}-{dd}"


def _pkd(p: dict) -> str:
    return f"{p.get('kodDzial', '')}.{p.get('kodKlasa', '')}.{p.get('kodPodklasa', '')}".strip(".")


def normalizuj(odpis: dict, rejestr: str) -> dict:
    n, dane = odpis["naglowekA"], odpis["dane"]
    d1, d2, d3 = dane.get("dzial1", {}), dane.get("dzial2", {}), dane.get("dzial3", {})
    pod, sa = d1.get("danePodmiotu", {}), d1.get("siedzibaIAdres", {})
    ident = pod.get("identyfikatory", {})
    przedmiot = d3.get("przedmiotDzialalnosci", {})
    glowne = przedmiot.get("przedmiotPrzewazajacejDzialalnosci") or []
    inne = przedmiot.get("przedmiotPozostalejDzialalnosci") or []
    adres = sa.get("adres", {})
    kap = (d1.get("kapital") or {}).get("wysokoscKapitaluZakladowego") or {}
    email = (sa.get("adresPocztyElektronicznej") or "").strip().lower() or None
    www = (sa.get("adresStronyInternetowej") or "").strip().lower() or None
    zarzad = [s.get("funkcjaWOrganie") for s in (d2.get("reprezentacja") or {}).get("sklad") or [] if s.get("funkcjaWOrganie")]
    return {
        "krs": n.get("numerKRS"), "rejestr": rejestr, "nazwa": pod.get("nazwa"), "forma": pod.get("formaPrawna"),
        "nip": ident.get("nip"), "regon": ident.get("regon"),
        "woj": (sa.get("siedziba") or {}).get("wojewodztwo"), "miejscowosc": (sa.get("siedziba") or {}).get("miejscowosc"),
        "adres": " ".join(x for x in (adres.get("ulica"), adres.get("nrDomu"), adres.get("kodPocztowy"), adres.get("poczta")) if x),
        "pkd": _pkd(glowne[0]) if glowne else None, "pkd_opis": glowne[0].get("opis") if glowne else None,
        "pkd_inne": [_pkd(p) for p in inne],
        "data_rejestracji": _data(n.get("dataRejestracjiWKRS")), "ostatni_wpis": _data(n.get("dataOstatniegoWpisu")),
        "kapital": f"{kap.get('wartosc')} {kap.get('waluta')}" if kap.get("wartosc") else None,
        "email": email, "email_typ": ll.typ_emaila(email) if email else None, "www": www,
        "zarzad_funkcje": zarzad,
    }


def odpis(krs: str) -> dict | None:
    for rejestr in ("P", "S"):
        d = ll.json_z(url_odpisu(krs, rejestr), pamiec_h=20)
        if d and d.get("odpis"):
            return normalizuj(d["odpis"], rejestr)
    return None


def pasuje(f: dict, pkd: list[str], woj: list[str]) -> bool:
    if pkd:
        kody = [f.get("pkd") or ""] + (f.get("pkd_inne") or [])
        if not any(k.replace(".", "").startswith(p.replace(".", "")) for k in kody for p in pkd):
            return False
    if woj and (f.get("woj") or "").upper() not in woj:
        return False
    return True


def sygnal(f: dict, data: str) -> dict:
    nowa = f.get("data_rejestracji") == data
    return {"typ": "krs-nowa-firma" if nowa else "krs-wpis", "data": data, "zrodlo": url_odpisu(f["krs"], f["rejestr"]),
            "opis": (f"zarejestrowana w KRS {data} ({ll.krotka_nazwa(f.get('forma')) or 'firma'}): {(f.get('pkd_opis') or '').lower()} "
                     f"(PKD {f.get('pkd')})" if nowa else f"wpis w KRS {data} (PKD {f.get('pkd')})"),
            "firma": {k: f.get(k) for k in ("nazwa", "nip", "krs", "regon", "woj", "miejscowosc", "adres", "pkd", "www")},
            "kontakty": ([{"typ": "email", "wartosc": f["email"], "rodzaj": f["email_typ"], "zrodlo": url_odpisu(f["krs"], f["rejestr"])}]
                         if f.get("email") else []),
            "szczegoly": {"forma": f.get("forma"), "kapital": f.get("kapital"), "data_rejestracji": f.get("data_rejestracji"),
                          "zarzad_funkcje": f.get("zarzad_funkcje"), "pkd_opis": f.get("pkd_opis")}}


def biuletyn(data: str, nowe: bool, pkd: list[str], woj: list[str], limit: int, watki: int = 4) -> tuple[list[dict], dict]:
    lista = ll.json_z(f"{API}/Krs/Biuletyn/{data}", pamiec_h=6) or []
    numery = sorted({int(k) for k in lista}, reverse=True)
    staty = {"w_biuletynie": len(numery), "sprawdzone": 0, "pasuje": 0}
    wyniki: list[dict] = []
    if nowe:            # nowe firmy mają najwyższe numery: idziemy od góry partiami, koniec po serii starszych
        starsze = 0
        for i in range(0, min(len(numery), limit), watki * 4):
            with ThreadPoolExecutor(watki) as ex:
                partia = list(ex.map(lambda k: odpis(str(k)), numery[i:i + watki * 4]))
            for f in partia:
                staty["sprawdzone"] += 1
                if not f:
                    continue
                if f.get("data_rejestracji") == data:
                    starsze = 0
                    if pasuje(f, pkd, woj):
                        wyniki.append(sygnal(f, data))
                else:
                    starsze += 1
            if starsze >= KONIEC_NOWYCH:
                break
    else:
        with ThreadPoolExecutor(watki) as ex:
            for f in ex.map(lambda k: odpis(str(k)), numery[:limit]):
                staty["sprawdzone"] += 1
                if f and pasuje(f, pkd, woj):
                    wyniki.append(sygnal(f, data))
    staty["pasuje"] = len(wyniki)
    return wyniki, staty


def lista(arg: str | None, upper: bool = False) -> list[str]:
    out = [x.strip() for x in (arg or "").split(",") if x.strip()]
    if upper:
        out = [ll.WOJ.get(x.upper(), x.upper()) for x in out]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("odpis")
    s.add_argument("krs", nargs="+")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("biuletyn")
    s.add_argument("data", help="RRRR-MM-DD")
    s.add_argument("--nowe", action="store_true", help="tylko firmy zarejestrowane tego dnia")
    s.add_argument("--pkd", help="prefiksy PKD po przecinku, np. 62,63.1,47.91")
    s.add_argument("--woj", help="województwa (nazwa albo kod PL14) po przecinku")
    s.add_argument("--limit", type=int, default=800, help="najwięcej sprawdzonych odpisów (każdy = 1 zapytanie)")
    s.add_argument("-o", help="dopisz sygnały do pliku JSONL (domyślnie wypisz)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "odpis":
            for k in a.krs:
                f = odpis(k)
                if not f:
                    print(f"✗ {k}: brak w rejestrze P ani S", file=sys.stderr)
                    continue
                if a.json:
                    print(json.dumps(f, ensure_ascii=False))
                else:
                    print(f"{f['krs']} {f['nazwa']} · NIP {f['nip']} · {f['woj']}, {f['miejscowosc']} · PKD {f['pkd']} "
                          f"{f['pkd_opis'] or ''} · rejestracja {f['data_rejestracji']} · e-mail {f['email'] or '–'} "
                          f"({f['email_typ'] or '–'}) · www {f['www'] or '–'}")
            return 0
        wyniki, staty = biuletyn(a.data, a.nowe, lista(a.pkd), lista(a.woj, upper=True), a.limit)
    except ll.Blokada as e:
        print(f"✗ blokada: {e}", file=sys.stderr)
        return 3
    ll.zapisz_jsonl(wyniki, a.o)
    print(f"✓ biuletyn {a.data}: {staty['w_biuletynie']} podmiotów, sprawdzone {staty['sprawdzone']}, sygnałów "
          f"{staty['pasuje']} ({ll.podsumowanie()})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

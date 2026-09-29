#!/usr/bin/env python3
"""Planer: czy test albo kampania przy danym budżecie coś rozstrzygnie i co przyniesie.

  planer.py test --metryka hook --warianty 5 --budzet-dzienny 100 --dni 5 --bazowa 0.25 --roznica 0.2
  planer.py test --metryka cpa  --warianty 3 --budzet-dzienny 150 --dni 7 --cpa 40 --roznica 0.3
  planer.py prognoza --budzet 1500 --dni 14 --cpm 20 --ctr 0.012 --cvr 0.04

Założenia (CPM, CTR, CVR) podawaj z konta klienta (ads.py statystyki) albo oznacz jako założenie.
Liczebność: test dwóch proporcji / dwóch częstości Poissona, alfa 0,05 (dwustronnie), moc 80%.
Kod wyjścia: 0 = test wykonalny w czasie, 1 = niewykonalny (z rekomendacją), 2 = złe dane. --json dla maszyn.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

Z = 1.959964 + 0.841621  # alfa 0,05 dwustronnie + moc 80%
METR = {"hook": "wyświetleń", "ctr": "wyświetleń", "cvr": "kliknięć", "cpa": "konwersji"}


def n_proporcje(p1: float, p2: float) -> float:
    return Z ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2


def n_poisson(stosunek: float) -> float:
    return 2 * (Z / math.log(stosunek)) ** 2


def test(a: argparse.Namespace) -> dict:
    if a.warianty < 2:
        raise ValueError("test wymaga ≥ 2 wariantów (pojedynczą reklamę planuj jako kampanię: `prognoza`)")
    na_wariant_dzien = a.budzet_dzienny / a.warianty
    if a.metryka == "cpa":
        if not a.cpa:
            raise ValueError("--cpa (bazowy koszt wyniku) wymagany dla metryki cpa")
        potrzeba = n_poisson(1 + a.roznica)                        # konwersji na wariant
        dziennie = na_wariant_dzien / a.cpa
    else:
        if not a.bazowa:
            raise ValueError("--bazowa (bazowy wskaźnik, np. 0.25 dla hook rate) wymagany")
        potrzeba = n_proporcje(a.bazowa, a.bazowa * (1 + a.roznica))
        wysw = na_wariant_dzien / a.cpm * 1000
        dziennie = wysw if a.metryka in ("hook", "ctr") else wysw * (a.ctr or 0.01)
    dni_potrzeba = potrzeba / dziennie if dziennie > 0 else math.inf
    koszt = dni_potrzeba * a.budzet_dzienny
    wykonalny = dni_potrzeba <= a.dni
    rek = []
    if not wykonalny:
        if a.warianty > 2:
            rek.append(f"mniej wariantów: przy 2 potrzeba ~{math.ceil(dni_potrzeba * 2 / a.warianty)} dni")
        tansza = {"cpa": "cvr/ctr", "cvr": "ctr", "ctr": "hook (jeśli wideo)"}.get(a.metryka)
        if tansza:
            rek.append(f"tańsza metryka: {tansza}, a {a.metryka} potwierdzić tylko na zwycięzcy")
        rek.append(f"większa różnica do wykrycia albo budżet ~{math.ceil(koszt / a.dni)} zł/dzień na {a.dni} dni")
    return {"tryb": "test", "metryka": a.metryka, "warianty": a.warianty,
            "potrzeba_na_wariant": math.ceil(potrzeba), "jednostka": METR[a.metryka],
            "dziennie_na_wariant": round(dziennie, 1), "dni_potrzeba": round(dni_potrzeba, 1),
            "dni_planowane": a.dni, "koszt_rozstrzygniecia_zl": round(koszt), "wykonalny": wykonalny,
            "rekomendacje": rek}


def prognoza(a: argparse.Namespace) -> dict:
    wysw = a.budzet / a.cpm * 1000
    wynik = {"tryb": "prognoza", "budzet": a.budzet, "dni": a.dni, "cpm": a.cpm, "wyswietlenia": round(wysw)}
    if a.ctr:
        kl = wysw * a.ctr
        wynik.update(klikniecia=round(kl), cpc=round(a.budzet / kl, 2) if kl else None)
        if a.cvr:
            konw = kl * a.cvr
            # widełki ±40%: założenia z benchmarków rzadko trafiają dokładniej
            wynik.update(konwersje=round(konw), konwersje_widelki=[round(konw * 0.6), round(konw * 1.4)],
                         cpa=round(a.budzet / konw, 2) if konw else None)
    wynik["faza_uczenia"] = ("ok" if wynik.get("konwersje", 0) / max(a.dni / 7, 1) >= 50 else
                             "ryzyko: < 50 wyników/tydzień na zestaw reklam, Meta może nie wyjść z fazy uczenia")
    return wynik


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="tryb", required=True)
    t = sub.add_parser("test")
    t.add_argument("--metryka", choices=list(METR), required=True)
    t.add_argument("--warianty", type=int, required=True)
    t.add_argument("--budzet-dzienny", type=float, required=True)
    t.add_argument("--dni", type=int, required=True)
    t.add_argument("--cpm", type=float, default=20.0)
    t.add_argument("--bazowa", type=float)
    t.add_argument("--ctr", type=float)
    t.add_argument("--cpa", type=float)
    t.add_argument("--roznica", type=float, default=0.2, help="względna różnica do wykrycia (0.2 = 20%%)")
    p = sub.add_parser("prognoza")
    p.add_argument("--budzet", type=float, required=True)
    p.add_argument("--dni", type=int, required=True)
    p.add_argument("--cpm", type=float, default=20.0)
    p.add_argument("--ctr", type=float)
    p.add_argument("--cvr", type=float)
    for s in (t, p):
        s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = test(a) if a.tryb == "test" else prognoza(a)
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif r["tryb"] == "test":
        print(f"Test {r['metryka']}, {r['warianty']} wariantów: potrzeba ~{r['potrzeba_na_wariant']} {r['jednostka']} na wariant, "
              f"przy budżecie ~{r['dni_potrzeba']} dni (plan: {r['dni_planowane']}), koszt rozstrzygnięcia ~{r['koszt_rozstrzygniecia_zl']} zł.")
        print("✓ wykonalny" if r["wykonalny"] else "✗ niewykonalny w planowanym czasie")
        for x in r["rekomendacje"]:
            print("  → " + x)
    else:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("wykonalny", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Werdykt testu reklam (A/B/C/...): P(najlepszy), oczekiwana strata, przedział, decyzja.

Wejście: JSON (plik albo stdin), np. wynik `eksport.py --json` albo `ads.py statystyki --json`:
  {"metryka": "ctr", "dni": 5, "min_dni": 4,
   "warianty": [{"nazwa": "A", "wyswietlenia": 3100, "klikniecia": 40, "obejrzenia3s": 900,
                 "konwersje": 3, "wydatek": 62.0}, ...]}

Metryki (im wyżej, tym lepiej; CPA liczymy jako wyniki na złotówkę i odwracamy przy wypisie):
  hook = obejrzenia3s / wyswietlenia     ctr = klikniecia / wyswietlenia
  cvr  = konwersje / klikniecia          cpa = konwersje / wydatek (Gamma-Poisson)

Model: Beta(1,1)-dwumianowy dla wskaźników, Gamma(1, 0)-Poisson dla wyników na złotówkę. Monte Carlo ze stałym
ziarnem (powtarzalny raport). Reguły: zwycięzca przy P(najlepszy) >= 0.95 i stracie < 2% po minimum dni i wolumenu;
przegrany (do wyłączenia) przy P < 0.05 po minimum albo wydatku 2x cel CPA bez konwersji; inaczej „remis” / „za wcześnie”.

  eksperyment.py dane.json            # raport czytelny
  eksperyment.py dane.json --json     # JSON (dla raportów i optymalizacji)
Kod wyjścia: 0 = policzone, 2 = złe dane.
"""
from __future__ import annotations

import argparse
import json
import random
import sys

METRYKI = {
    "hook": ("obejrzenia3s", "wyswietlenia", "hook rate"),
    "ctr": ("klikniecia", "wyswietlenia", "CTR"),
    "cvr": ("konwersje", "klikniecia", "CVR"),
    "cpa": ("konwersje", "wydatek", "koszt wyniku"),
}
MIN_MIANOWNIK = {"hook": 1000, "ctr": 1000, "cvr": 100, "cpa": 0}


def losuj(m: str, sukcesy: float, proby: float, rng: random.Random) -> float:
    if m == "cpa":  # wyniki na złotówkę: Gamma(1 + konwersje, wydatek)
        return rng.gammavariate(1 + sukcesy, 1 / max(proby, 1e-9))
    return rng.betavariate(1 + sukcesy, 1 + max(proby - sukcesy, 0))


def policz(dane: dict, n: int = 20000, seed: int = 7) -> dict:
    m = dane.get("metryka", "ctr")
    if m not in METRYKI:
        raise ValueError(f"nieznana metryka {m!r}: {', '.join(METRYKI)}")
    licz, mian, etykieta = METRYKI[m]
    war = dane.get("warianty") or []
    if len(war) < 1:
        raise ValueError("brak wariantów")
    for w in war:
        if licz not in w or mian not in w:
            raise ValueError(f"wariant {w.get('nazwa')!r}: brak pól {licz!r}/{mian!r}")
    rng = random.Random(seed)
    k = len(war)
    wins = [0] * k
    strata = [0.0] * k
    probki: list[list[float]] = [[] for _ in range(k)]
    for _ in range(n):
        x = [losuj(m, float(w[licz]), float(w[mian]), rng) for w in war]
        best = max(x)
        i = x.index(best)
        wins[i] += 1
        for j in range(k):
            strata[j] += (best - x[j]) / best if best > 0 else 0.0
            probki[j].append(x[j])
    wyniki = []
    for j, w in enumerate(war):
        s = sorted(probki[j])
        lo, hi = s[int(0.025 * n)], s[int(0.975 * n) - 1]
        obs = float(w[licz]) / float(w[mian]) if float(w[mian]) > 0 else 0.0
        r = {"nazwa": w.get("nazwa", f"#{j + 1}"), "p_najlepszy": round(wins[j] / n, 4),
             "strata": round(strata[j] / n, 4), licz: w[licz], mian: w[mian], "obserwowane": obs,
             "przedzial": [lo, hi]}
        if m == "cpa":
            r["cpa"] = round(1 / obs, 2) if obs > 0 else None
            r["przedzial_cpa"] = [round(1 / hi, 2) if hi > 0 else None, round(1 / lo, 2) if lo > 0 else None]
        wyniki.append(r)

    dni, min_dni = dane.get("dni"), dane.get("min_dni", 4)
    cel_cpa = dane.get("cel_cpa")
    min_mian = dane.get("min_mianownik", MIN_MIANOWNIK[m])
    po_minimum = (dni is None or dni >= min_dni) and all(float(w[mian]) >= min_mian for w in war)
    przegrani = []
    for r, w in zip(wyniki, war):
        spalony = cel_cpa and float(w.get("konwersje", 0)) == 0 and float(w.get("wydatek", 0)) >= 2 * cel_cpa
        if (po_minimum and r["p_najlepszy"] < 0.05 and k > 1) or spalony:
            przegrani.append(r["nazwa"])
    lider = max(wyniki, key=lambda r: r["p_najlepszy"])
    if k == 1:
        werdykt = "pojedyncza reklama: brak porównania, oceniam względem celu"
        stan = "pojedyncza"
    elif not po_minimum:
        stan, werdykt = "za_wczesnie", f"za wcześnie: minimum {min_dni} dni i {min_mian} ({mian}) na wariant"
    elif lider["p_najlepszy"] >= 0.95 and lider["strata"] < 0.02:
        stan, werdykt = "zwyciezca", f"zwycięzca: {lider['nazwa']} (P={lider['p_najlepszy']:.0%})"
    else:
        stan, werdykt = "remis", f"remis: prowadzi {lider['nazwa']} (P={lider['p_najlepszy']:.0%}), za mało danych na rozstrzygnięcie"
    return {"metryka": m, "etykieta": etykieta, "stan": stan, "werdykt": werdykt, "lider": lider["nazwa"],
            "do_wylaczenia": przegrani, "warianty": wyniki, "losowania": n, "ziarno": seed,
            "uwaga": "Warianty różnią się wieloma rzeczami naraz: wynik mówi, który PAKIET działa lepiej, nie dlaczego."
            if dane.get("wiele_zmiennych") else None}


def czytelnie(r: dict) -> str:
    m = r["metryka"]
    out = [f"Metryka: {r['etykieta']}  ·  {r['werdykt']}"]
    for w in sorted(r["warianty"], key=lambda w: -w["p_najlepszy"]):
        if m == "cpa":
            val = f"CPA {w['cpa']} zł (95%: {w['przedzial_cpa'][0]}–{w['przedzial_cpa'][1]})" if w["cpa"] else "0 wyników"
        else:
            val = f"{w['obserwowane']:.2%} (95%: {w['przedzial'][0]:.2%}–{w['przedzial'][1]:.2%})"
        out.append(f"  {w['nazwa']:<14} {val:<40} P(najlepszy) {w['p_najlepszy']:.0%}  strata {w['strata']:.1%}")
    if r["do_wylaczenia"]:
        out.append("Do wyłączenia: " + ", ".join(r["do_wylaczenia"]))
    if r.get("uwaga"):
        out.append(r["uwaga"])
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik", nargs="?", help="JSON z wariantami (domyślnie stdin)")
    ap.add_argument("--metryka", choices=list(METRYKI), help="nadpisuje metrykę z pliku")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        dane = json.load(open(a.plik, encoding="utf-8") if a.plik else sys.stdin)
        if a.metryka:
            dane["metryka"] = a.metryka
        r = policz(dane)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else czytelnie(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

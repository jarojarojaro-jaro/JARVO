#!/usr/bin/env python3
"""Eksport CSV z Meta Ads Managera albo Google Ads → dane reklam (bez API i bez Skarbca).

Rozpoznaje nagłówki PL i EN (np. „Nazwa reklamy”/„Ad name”, „Wydana kwota (PLN)”/„Amount spent (PLN)”,
„Wyświetlenia”/„Impressions”/„Impr.”, „Kliknięcia linku”/„Link clicks”/„Clicks”, „Wyniki”/„Results”/„Conversions”,
„3-sekundowe odtworzenia filmu”/„3-second video plays”). Liczby z przecinkiem dziesiętnym, spacjami i „--” też.

  eksport.py raport.csv                          # tabela: wydatek, CTR, CPC, CPA, hook rate
  eksport.py raport.csv --json --metryka ctr     # wejście dla eksperyment.py (warianty = wiersze)
  eksport.py raport.csv --grupuj kampania        # suma po kampanii / zestawie / reklamie
Kod wyjścia: 0 = ok, 2 = nie rozpoznano kolumn.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata

POLA = {
    "reklama": ["nazwa reklamy", "ad name", "ad", "reklama", "headline", "ad group ad"],
    "zestaw": ["nazwa zestawu reklam", "ad set name", "ad group", "grupa reklam"],
    "kampania": ["nazwa kampanii", "campaign name", "campaign", "kampania"],
    "wydatek": ["wydana kwota", "amount spent", "cost", "koszt", "spend"],
    "wyswietlenia": ["wyswietlenia", "impressions", "impr"],
    "klikniecia": ["klikniecia linku", "link clicks", "clicks", "klikniecia"],
    "konwersje": ["wyniki", "results", "conversions", "konwersje"],
    "obejrzenia3s": ["3-sekundowe odtworzenia filmu", "3-second video plays", "odtworzenia filmu 3 s", "video plays at 3s"],
    "przychod": ["wartosc konwersji", "purchase conversion value", "conv. value", "conversion value", "wartosc konw"],
    "dni": ["dni", "days"],
}
LICZBOWE = {"wydatek", "wyswietlenia", "klikniecia", "konwersje", "obejrzenia3s", "przychod"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"[^a-z0-9 -]+", " ", s).strip().rstrip(".")


def mapuj(naglowki: list[str]) -> dict[str, str]:
    wynik: dict[str, str] = {}
    n = {h: re.sub(r"\s+", " ", norm(h)) for h in naglowki}
    for pole, aliasy in POLA.items():
        for alias in aliasy:                       # najpierw dokładne dopasowanie, potem prefiks
            hit = next((h for h, v in n.items() if v == alias and h not in wynik.values()), None) or \
                  next((h for h, v in n.items() if v.startswith(alias) and h not in wynik.values()), None)
            if hit:
                wynik[pole] = hit
                break
    return wynik


def liczba(s: str) -> float:
    s = (s or "").strip().replace(" ", "").replace(" ", "")
    if s in ("", "--", "-", "—"):
        return 0.0
    s = re.sub(r"[^0-9,.\-]", "", s)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def czytaj(tekst: str) -> tuple[list[dict], dict[str, str]]:
    linie = tekst.lstrip("﻿").splitlines()
    # Google Ads dokleja 1–2 linie tytułu nad nagłówkiem: szukamy linii z największą liczbą znanych kolumn
    start = max(range(min(len(linie), 6)), key=lambda i: len(mapuj(next(csv.reader([linie[i]], dialect=sniff(linie[i]))))))
    tekst = "\n".join(linie[start:])
    rd = csv.DictReader(io.StringIO(tekst), dialect=sniff(linie[start]))
    mapa = mapuj(rd.fieldnames or [])
    wiersze = []
    for row in rd:
        nazwa_kol = mapa.get("reklama") or mapa.get("zestaw") or mapa.get("kampania")
        nazwa = (row.get(nazwa_kol) or "").strip() if nazwa_kol else ""
        if not nazwa or norm(nazwa).startswith(("total", "razem", "suma")):
            continue
        w = {"nazwa": nazwa}
        for pole in ("kampania", "zestaw"):
            if pole in mapa:
                w[pole] = (row.get(mapa[pole]) or "").strip()
        for pole in LICZBOWE:
            if pole in mapa:
                w[pole] = liczba(row.get(mapa[pole], ""))
        wiersze.append(w)
    return wiersze, mapa


def sniff(linia: str) -> type[csv.Dialect]:
    return csv.excel_tab if linia.count("\t") > linia.count(",") and linia.count("\t") > linia.count(";") else (
        type("sc", (csv.excel,), {"delimiter": ";"}) if linia.count(";") > linia.count(",") else csv.excel)


def grupuj(wiersze: list[dict], klucz: str) -> list[dict]:
    out: dict[str, dict] = {}
    for w in wiersze:
        k = w.get(klucz) or w["nazwa"]
        g = out.setdefault(k, {"nazwa": k})
        for pole in LICZBOWE:
            if pole in w:
                g[pole] = g.get(pole, 0.0) + w[pole]
    return list(out.values())


def wskazniki(w: dict) -> dict:
    wy, kl, ko, sp = w.get("wyswietlenia", 0), w.get("klikniecia", 0), w.get("konwersje", 0), w.get("wydatek", 0)
    return {"ctr": kl / wy if wy else None, "cpc": sp / kl if kl else None, "cpa": sp / ko if ko else None,
            "cpm": sp / wy * 1000 if wy else None, "hook": w["obejrzenia3s"] / wy if wy and "obejrzenia3s" in w else None,
            "roas": w["przychod"] / sp if sp and w.get("przychod") else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik")
    ap.add_argument("--grupuj", choices=["kampania", "zestaw", "reklama"], default="reklama")
    ap.add_argument("--metryka", choices=["hook", "ctr", "cvr", "cpa"], default="ctr")
    ap.add_argument("--dni", type=int, help="ile dni obejmuje eksport (dla reguł stopu)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with open(a.plik, encoding="utf-8-sig", errors="replace") as f:
        wiersze, mapa = czytaj(f.read())
    if "wyswietlenia" not in mapa or not wiersze:
        print(f"✗ nie rozpoznano kolumn (znalezione: {mapa}); wyeksportuj z kolumnami: nazwa reklamy, wydatek, "
              "wyświetlenia, kliknięcia linku, wyniki", file=sys.stderr)
        return 2
    dane = wiersze if a.grupuj == "reklama" else grupuj(wiersze, a.grupuj)
    if a.json:
        print(json.dumps({"metryka": a.metryka, "dni": a.dni, "zrodlo": a.plik, "kolumny": mapa,
                          "warianty": dane}, ensure_ascii=False, indent=2))
        return 0
    fmt = lambda x, p=False: "—" if x is None else (f"{x:.2%}" if p else f"{x:,.2f}".replace(",", " "))
    print(f"{'nazwa':<36}{'wydatek':>10}{'wyśw.':>10}{'CTR':>8}{'CPC':>8}{'wyniki':>8}{'CPA':>9}{'hook':>8}")
    for w in sorted(dane, key=lambda w: -w.get("wydatek", 0)):
        m = wskazniki(w)
        print(f"{w['nazwa'][:35]:<36}{fmt(w.get('wydatek', 0)):>10}{int(w.get('wyswietlenia', 0)):>10}"
              f"{fmt(m['ctr'], True):>8}{fmt(m['cpc']):>8}{int(w.get('konwersje', 0)):>8}{fmt(m['cpa']):>9}{fmt(m['hook'], True):>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

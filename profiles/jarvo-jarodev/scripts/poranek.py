#!/usr/bin/env python3
"""Rutyna poranna Jarodev (cron, skrypt przed turą agenta): lejek gotowy, retencja RODO wykonana, liczby dnia.

    poranek.py [--katalog DIR] [--dni 90]

Bez modelu i bez sieci: `lejek.py init` (katalog i wzór zrodla.yaml, bez nadpisywania), `retencja --wykonaj`
(osoby z postów bez kontaktu starsze niż --dni znikają), statystyki lejka i stan źródeł (czy właściciel podał grupy
i portale). Wypisuje czytelny raport, który agent dostaje nad promptem rutyny (skill `raport-dnia`).
Kod wyjścia ≠ 0 tylko przy błędzie odczytu/zapisu lejka.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lejek  # noqa: E402


def stan_zrodel(plik: Path) -> dict:
    """Liczba wpisów list grupy_fb, portale, mapy w zrodla.yaml (bez parsera YAML: wpis listy to linia „  - ”
    pod kluczem albo pusta lista `[]`)."""
    wynik = {"grupy_fb": 0, "portale": 0, "mapy": 0}
    try:
        tekst = plik.read_text(encoding="utf-8")
    except OSError:
        return wynik
    klucz = None
    for linia in tekst.splitlines():
        if not linia.strip() or linia.lstrip().startswith("#"):
            continue
        m = re.match(r"^([a-z_]+):", linia)
        if m:
            klucz = m.group(1) if m.group(1) in wynik else None
            reszta = linia[m.end():].split("#", 1)[0].strip()
            if klucz and reszta.startswith("[") and reszta not in ("[]", "[ ]"):
                wynik[klucz] = len([x for x in reszta.strip("[]").split("}") if x.strip(" ,")]) or 1
        elif klucz and re.match(r"^\s+-\s", linia):
            wynik[klucz] += 1
    return wynik


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--katalog", type=Path)
    ap.add_argument("--dni", type=int, default=90)
    a = ap.parse_args(argv)
    kat = a.katalog or lejek.domyslny_katalog()
    try:
        start = lejek.init(kat, kat.parent / "zrodla.yaml")
        dane = lejek.wczytaj(kat)
        usuniete = lejek.retencja(dane, a.dni, wykonaj=True)
        if usuniete:
            lejek.zapisz(kat, dane)
        st = lejek.statystyki(dane)
    except (lejek.Blad, OSError) as e:
        print(f"BŁĄD lejka: {e}")
        return 1
    zrodla = stan_zrodel(Path(start["plik_zrodel"]))
    print(f"Lejek jarodev ({lejek.dzis().isoformat()}): {st['wpisy']} wpisów; po statusie: "
          + ", ".join(f"{k} {v}" for k, v in st["po_statusie"].items() if v) if st["wpisy"] else
          f"Lejek jarodev ({lejek.dzis().isoformat()}): pusty")
    print(f"Czeka na zgodę właściciela (szkic): {', '.join(st['czeka_na_zgode']) or 'nic'}; "
          f"zaakceptowane do wysłania: {', '.join(st['do_wyslania']) or 'nic'}")
    print(f"Retencja RODO ({a.dni} dni): usunięto {len(usuniete)} wpisów osób bez kontaktu")
    braki = [k for k in ("grupy_fb", "portale", "mapy") if not zrodla[k]]
    print(f"Źródła ({start['plik_zrodel']}): grupy FB {zrodla['grupy_fb']}, portale {zrodla['portale']}, "
          f"miasta Map {zrodla['mapy']}" + (f"; puste: {', '.join(braki)} (właściciel jeszcze nie podał)" if braki else ""))
    print(json.dumps({"lejek": st, "zrodla": zrodla, "retencja_usuniete": [w["id"] for w in usuniete]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

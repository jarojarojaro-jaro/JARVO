#!/usr/bin/env python3
"""Odcisk wersji plików, do której przypinamy zgodę A2 (publikacja, wdrożenie, wysyłka, wydatek).

Zgoda człowieka dotyczy dokładnie tej wersji: wykonawca podaje odcisk, prosząc o zgodę, a przed akcją sprawdza,
że pliki się nie zmieniły. Poprawka po zgodzie zmienia odcisk, więc wymaga nowej zgody (za ECC operator-approval-loop).

  python3 /opt/jarvo/repo/scripts/odcisk.py out/do-publikacji out/kalendarz.csv
  python3 /opt/jarvo/repo/scripts/odcisk.py out/site/dist --sprawdz 3f9c0a1b2d4e     # 0 = ta sama wersja, 1 = zmiana

Odcisk = pierwsze 12 znaków SHA-256 z listy (ścieżka względna, zawartość) wszystkich plików, posortowanej.
Pliki systemowe (.DS_Store, __pycache__) nie wchodzą do odcisku.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

POMIN = {".DS_Store", "__pycache__", "Thumbs.db"}
DLUGOSC = 12


def pliki(sciezki: list[Path]) -> list[tuple[str, Path]]:
    out = []
    for s in sciezki:
        if s.is_file():
            out.append((s.name, s))
        elif s.is_dir():
            for p in s.rglob("*"):
                if p.is_file() and not POMIN.intersection(p.relative_to(s).parts):
                    out.append((f"{s.name}/{p.relative_to(s).as_posix()}", p))
        else:
            raise SystemExit(f"nie ma: {s}")
    return sorted(out)


def odcisk(sciezki: list[Path]) -> tuple[str, int]:
    lista = pliki(sciezki)
    h = hashlib.sha256()
    for rel, p in lista:
        h.update(rel.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:DLUGOSC], len(lista)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sciezki", nargs="+", type=Path, help="pliki albo katalogi objęte zgodą")
    ap.add_argument("--sprawdz", metavar="ODCISK", help="odcisk z zgody: kod 0 = ta sama wersja, 1 = pliki się zmieniły")
    a = ap.parse_args(argv)
    wynik, n = odcisk(a.sciezki)
    if a.sprawdz:
        if wynik == a.sprawdz.strip().lower()[:DLUGOSC]:
            print(f"✓ odcisk {wynik} zgodny ze zgodą ({n} plików)")
            return 0
        print(f"✗ odcisk {wynik} ≠ {a.sprawdz} ze zgody: pliki zmieniły się po zgodzie, potrzebna nowa zgoda")
        return 1
    print(f"odcisk: {wynik} ({n} plików)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

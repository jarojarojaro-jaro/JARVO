#!/usr/bin/env python3
"""Brief do filmu (`out/fakty.json`): fakty, liczby ze źródłem, analogie i słowniczek dla Wideografa.

    python3 fakty.py szablon [-o out/fakty.json] [--temat "Jak działa kolejka"] [--dlugosc 90]
    python3 fakty.py sprawdz out/fakty.json [--rejestr out/zrodla.json] [--dlugosc 90] [--json]

Wideograf czyta brief przy `film.py narracja` (liczba lektora z listy niepewnych zatrzymuje syntezę, liczba bez
pokrycia daje ostrzeżenie, `slowniczek[].wymowa` mówi lektorowi, jak czytać termin) i przy pomiarze animacji
(liczby na ekranie). Dlatego każda liczba w `liczby` musi naprawdę stać w przeczytanym źródle z rejestru
(`sources.py`, tekst w `strony/<n>.txt` albo cytat-dowód), a wszystko, czego nie da się potwierdzić, idzie do
`niepewne` i nie trafia ani do lektora, ani na ekran. Format i zasady: skill raport-sledztwa,
references/brief-do-filmu.md.

`sprawdz` (kod 1 = błędy): pola obowiązkowe bez znaczników <…> z szablonu, każda liczba z id, wartością cyframi,
twierdzeniem i numerami źródeł; z rejestrem: źródło istnieje, jest przeczytane, ma ocenę A–C (D albo bez oceny =
do `niepewne`), deklarowany tier nie jest lepszy niż w rejestrze, a wartość jest w tekście źródła (też zapis
z mnożnikiem: „3,5 mln” = „3 500 000” = „3.5 million”); analogia ma `psuje_sie`. Ostrzeżenia: liczba bez
przeliczenia na skalę (`skala`) albo bez daty, mniej liczb, niż potrzeba na długość filmu, mniej niż 3 analogie,
słowniczek ponad 30 terminów, brak rejestru.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

WERSJA = 1
TIERY = ["A", "B", "C", "D"]
# Ile liczb do wyboru potrzeba na długość filmu (lektor użyje części; reszta to zapas na ekran i pytania).
LICZBY_NA_DLUGOSC = [(90, (3, 6)), (180, (8, 10)), (300, (10, 16)), (480, (18, 24))]
ANALOGII_CEL = 5
SLOWNICZEK_MAX = 30

_LICZBA = re.compile(r"(?<![\w,.])(\d{1,3}(?:[   ]\d{3})+|\d{1,3}(?:\.\d{3})+(?![.,]?\d)|\d+)((?:[,.]\d+)?)(?![\d])"
                     r"(?:\s*(tys\.?|tysięcy|tysiące|mln|milion\w*|mld|miliard\w*|thousand|million|billion|k|M|B)\b)?")
MNOZNIKI = {"tys": 1e3, "tysięcy": 1e3, "tysiące": 1e3, "thousand": 1e3, "k": 1e3, "mln": 1e6, "million": 1e6, "M": 1e6,
            "mld": 1e9, "billion": 1e9, "B": 1e9}
ZNACZNIK = re.compile(r"<[^<>]{3,}>")          # niewypełnione pole z szablonu


def _mnoznik(slowo: str | None) -> float:
    if not slowo:
        return 1.0
    s = slowo.rstrip(".")
    if s in MNOZNIKI:
        return MNOZNIKI[s]
    for k, v in (("milion", 1e6), ("miliard", 1e9)):
        if s.startswith(k):
            return v
    return 1.0


def liczby(tekst: str) -> list[tuple[str, set[float]]]:
    """Liczby zapisane cyframi: [(zapis, możliwe wartości)]. „3,5 mln” → {3.5, 3 500 000}; „1,234” po angielsku
    może znaczyć 1234, więc dostaje obie wartości."""
    out = []
    for m in _LICZBA.finditer(tekst or ""):
        calosc = re.sub(r"[ \u00a0\u202f.]", "", m.group(1))
        ulamek = m.group(2) or ""
        wartosci = {float(calosc + ulamek.replace(",", "."))}
        if re.fullmatch(r"[,.]\d{3}", ulamek):
            wartosci.add(float(calosc + ulamek[1:]))
        k = _mnoznik(m.group(3))
        if k != 1.0:
            wartosci |= {v * k for v in wartosci}
        out.append((m.group(0).strip(), wartosci))
    return out


def _rowne(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def wartosc_w_tekscie(wartosc: str, tekst: str) -> bool:
    """Czy liczba z briefu stoi w tekście źródła (dowolny zapis tej samej wartości)."""
    w, m = liczby(wartosc), _LICZBA.search(wartosc or "")
    if not w:
        return False
    szukane = {max(w[0][1])} if m and m.group(3) else w[0][1]     # „3,5 mln” szukamy jako 3 500 000, nie 3,5
    return any(_rowne(a, v) for a in szukane for _, vs in liczby(tekst) for v in vs)


def szablon(temat: str = "", dlugosc: int = 90) -> dict:
    return {
        "wersja": WERSJA,
        "temat": temat or "<temat filmu>",
        "dlugosc_s": dlugosc,
        "stan_na": "<RRRR-MM-DD>",
        "przeslanie": "<jedno zdanie: co widz wie po filmie, czego nie wiedział>",
        "zaskoczenie": "<najmniej oczywista rzecz w temacie, z przypisem [n]>",
        "sytuacja": "<konkretna sytuacja widza, którą da się narysować: kto, gdzie, co mu się dzieje>",
        "geneza": "<skąd się wzięło: kto, kiedy, jaki problem rozwiązywało [n]>",
        "mechanizm": [{"krok": "<co się dzieje>", "po_co": "<dlaczego tak>", "przyklad": "<liczba albo przykład [n]>"}],
        "granice": ["<z czym się myli, gdzie nie działa, częsty błąd>"],
        "spory": ["<kto twierdzi co i na jakiej podstawie [n]; zmiany z ostatnich 2 lat>"],
        "przypadki": [{"opis": "<prawdziwy przypadek, udany albo porażka>", "udany": True, "zrodla": [1]}],
        "liczby": [{"id": "L1", "wartosc": "<np. 3,5 mln>", "jednostka": "<np. bochenków rocznie>",
                    "twierdzenie": "<pełne zdanie z faktem>", "zrodla": [1], "tier": "A",
                    "skala": "<przeliczenie, które czuć: np. jeden co 9 sekund>", "data": "<rok albo stan na>"}],
        "analogie": [{"analogia": "<np. kolejka w piekarni>", "pasuje": "<co oddaje dobrze>",
                      "psuje_sie": "<gdzie zaczyna kłamać: tam jej nie ciągniemy>"}],
        "slowniczek": [{"termin": "<np. Next.js>", "prosto": "<po ludzku, jednym zdaniem>",
                        "wymowa": "<jak czytać po polsku, np. nekst dżej es; puste, gdy oczywiste>"}],
        "przykladowe": ["<wartość pokazowa na makiecie, np. cena 49 zł w przykładowym sklepie: oznaczona jako przykład>"],
        "niepewne": ["<twierdzenie, którego nie potwierdziło źródło A–C: nie trafia do lektora ani na ekran>"],
    }


def zakres_liczb(dlugosc: float) -> tuple[int, int]:
    for do, zakres in LICZBY_NA_DLUGOSC:
        if dlugosc <= do:
            return zakres
    return LICZBY_NA_DLUGOSC[-1][1]


def _rejestr(jawna: str | None, fakty: Path) -> Path | None:
    for p in (jawna, os.environ.get("JARVO_REJESTR_ZRODEL"), fakty.parent / "zrodla.json"):
        if p and Path(p).is_file():
            return Path(p)
    return None


def _tekst_zrodla(rejestr: Path, s: dict) -> str | None:
    czesci = []
    for rel in (s.get("tekst"), s.get("archiwum_tekst")):
        if rel and (rejestr.parent / rel).is_file():
            czesci.append((rejestr.parent / rel).read_text(encoding="utf-8", errors="replace"))
    czesci += [q.get("text", "") for q in s.get("quotes") or []]
    return "\n".join(czesci) if czesci else None


def _znaczniki(obj, sciezka: str = "") -> list[str]:
    if isinstance(obj, str):
        return [sciezka] if ZNACZNIK.search(obj) else []
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in _znaczniki(v, f"{sciezka}.{k}" if sciezka else k)]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in _znaczniki(v, f"{sciezka}[{i}]")]
    return []


def sprawdz(fakty: dict, rejestr: Path | None = None, dlugosc: float | None = None) -> dict:
    bledy, ostrz = [], []
    if not isinstance(fakty, dict):
        return {"ok": False, "bledy": ["fakty.json to nie obiekt JSON"], "ostrzezenia": []}
    for pole in ("temat", "przeslanie", "sytuacja"):
        if not str(fakty.get(pole) or "").strip():
            bledy.append(f"brak pola „{pole}”")
    for p in _znaczniki(fakty):
        bledy.append(f"{p}: niewypełnione pole z szablonu (<…>): wpisz treść albo usuń wpis")
    for pole in ("liczby", "analogie", "slowniczek", "niepewne", "przypadki", "mechanizm", "granice", "spory", "przykladowe"):
        if pole in fakty and not isinstance(fakty[pole], list):
            bledy.append(f"„{pole}” ma być listą")
    if any(not isinstance(x, str) for x in fakty.get("niepewne") or []):
        bledy.append("„niepewne” to lista zdań (tekst)")

    zrodla = None
    if rejestr:
        dane = json.loads(rejestr.read_text(encoding="utf-8"))
        zrodla = {s["id"]: s for s in dane.get("sources") or [] if isinstance(s, dict) and "id" in s}
    else:
        ostrz.append("bez rejestru źródeł (out/zrodla.json): numery źródeł i wartości niesprawdzone")

    def sprawdz_numery(gdzie: str, numery) -> list[dict]:
        if not isinstance(numery, list) or not numery or not all(isinstance(n, int) for n in numery):
            bledy.append(f"{gdzie}: „zrodla” to lista numerów z rejestru, np. [3, 7]")
            return []
        if zrodla is None:
            return []
        brak = [n for n in numery if n not in zrodla]
        if brak:
            bledy.append(f"{gdzie}: źródeł {', '.join(f'[{n}]' for n in brak)} nie ma w rejestrze")
        return [zrodla[n] for n in numery if n in zrodla]

    lista = [x for x in fakty.get("liczby") or [] if isinstance(x, dict)]
    ids = [str(x.get("id") or "") for x in lista]
    for i, x in enumerate(lista):
        gdzie = f"liczba {ids[i] or f'#{i + 1}'}"
        if not ids[i]:
            bledy.append(f"{gdzie}: brak „id” (L1, L2…)")
        elif ids.count(ids[i]) > 1:
            bledy.append(f"{gdzie}: „id” się powtarza")
        wartosc = str(x.get("wartosc") or "")
        if not liczby(wartosc):
            bledy.append(f"{gdzie}: „wartosc” cyframi (np. „3,5 mln”, „40%”), żeby lektor i ekran dało się sprawdzić")
        if not str(x.get("twierdzenie") or "").strip():
            bledy.append(f"{gdzie}: brak „twierdzenie” (pełne zdanie z faktem)")
        zr = sprawdz_numery(gdzie, x.get("zrodla"))
        if x.get("tier") and x["tier"] not in TIERY:
            bledy.append(f"{gdzie}: tier A–D")
        if zr:
            tiery = [s.get("tier") for s in zr if s.get("tier") in TIERY]
            najlepszy = min(tiery, key=TIERY.index) if tiery else None
            if najlepszy in (None, "D"):
                bledy.append(f"{gdzie}: tylko źródła D albo bez oceny: przenieś do „niepewne” albo znajdź źródło A–C")
            elif x.get("tier") in TIERY and TIERY.index(x["tier"]) < TIERY.index(najlepszy):
                bledy.append(f"{gdzie}: tier {x['tier']}, a najlepsze źródło w rejestrze ma {najlepszy}")
            teksty = [(s["id"], _tekst_zrodla(rejestr, s)) for s in zr]
            nieczytane = [n for n, t in teksty if t is None]
            if len(nieczytane) == len(teksty):
                bledy.append(f"{gdzie}: źródła {', '.join(f'[{n}]' for n in nieczytane)} nieprzeczytane (sam wynik "
                             "wyszukiwania): extract.py albo sources.py add --tekst")
            elif wartosc and liczby(wartosc) and not any(t and wartosc_w_tekscie(wartosc, t) for _, t in teksty):
                bledy.append(f"{gdzie}: wartości „{wartosc}” nie ma w tekście źródeł "
                             f"{', '.join(f'[{n}]' for n, _ in teksty)}: popraw liczbę albo źródło")
        if not str(x.get("skala") or "").strip():
            ostrz.append(f"{gdzie}: bez „skala” (przeliczenie, które czuć: „jeden co 9 sekund”)")
        if not str(x.get("data") or "").strip():
            ostrz.append(f"{gdzie}: bez „data” (stan na; liczby zmieniają się w czasie)")
    for i, p in enumerate(fakty.get("przypadki") or []):
        if isinstance(p, dict) and "zrodla" in p:
            sprawdz_numery(f"przypadek #{i + 1}", p.get("zrodla"))

    analogie = [a for a in fakty.get("analogie") or [] if isinstance(a, dict)]
    for i, a in enumerate(analogie, 1):
        if not str(a.get("analogia") or "").strip():
            bledy.append(f"analogia #{i}: brak „analogia”")
        if not str(a.get("psuje_sie") or "").strip():
            bledy.append(f"analogia #{i}: brak „psuje_sie” (gdzie analogia kłamie; tam lektor jej nie ciągnie)")
    if len(analogie) < 3:
        ostrz.append(f"analogie: {len(analogie)}, cel {ANALOGII_CEL} do wyboru (każda z „pasuje” i „psuje_sie”)")
    slownik = [t for t in fakty.get("slowniczek") or [] if isinstance(t, dict)]
    for i, t in enumerate(slownik, 1):
        if not str(t.get("termin") or "").strip() or not str(t.get("prosto") or "").strip():
            bledy.append(f"słowniczek #{i}: „termin” i „prosto” są obowiązkowe")
    if len(slownik) > SLOWNICZEK_MAX:
        ostrz.append(f"słowniczek: {len(slownik)} terminów (> {SLOWNICZEK_MAX}); zostaw te, które padną w filmie")

    dl = dlugosc or fakty.get("dlugosc_s")
    zakres = None
    if isinstance(dl, (int, float)) and dl > 0:
        zakres = zakres_liczb(dl)
        if len(lista) < zakres[0]:
            ostrz.append(f"liczby: {len(lista)}, na film {dl:g} s potrzeba {zakres[0]}–{zakres[1]} do wyboru")
    return {"ok": not bledy, "bledy": bledy, "ostrzezenia": ostrz, "liczby": len(lista),
            "zakres_liczb": f"{zakres[0]}–{zakres[1]}" if zakres else None, "analogie": len(analogie),
            "slowniczek": len(slownik), "wymowa": sum(1 for t in slownik if str(t.get("wymowa") or "").strip()),
            "niepewne": len(fakty.get("niepewne") or []), "rejestr": rejestr.as_posix() if rejestr else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("szablon", help="pusty brief z opisem pól")
    s.add_argument("-o", default="out/fakty.json")
    s.add_argument("--temat", default="")
    s.add_argument("--dlugosc", type=int, default=90, help="długość filmu w s")
    s.add_argument("--nadpisz", action="store_true")
    c = sub.add_parser("sprawdz", help="kontrola briefu przed oddaniem (kod 1 = błędy)")
    c.add_argument("plik", nargs="?", default="out/fakty.json")
    c.add_argument("--rejestr", help="rejestr źródeł (domyślnie $JARVO_REJESTR_ZRODEL albo zrodla.json obok briefu)")
    c.add_argument("--dlugosc", type=float, help="długość filmu w s (domyślnie dlugosc_s z briefu)")
    c.add_argument("--json", action="store_true", help="wynik jako JSON")
    a = ap.parse_args(argv)
    if a.cmd == "szablon":
        out = Path(a.o)
        if out.exists() and not a.nadpisz:
            raise SystemExit(f"{out} już jest (--nadpisz, żeby zacząć od nowa)")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(szablon(a.temat, a.dlugosc), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"✓ {out}: wypełnij pola <…>, potem fakty.py sprawdz {out}")
        return 0
    plik = Path(a.plik)
    try:
        fakty = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"✗ {plik}: {e}")
    wynik = sprawdz(fakty, _rejestr(a.rejestr, plik), a.dlugosc)
    if a.json:
        print(json.dumps(wynik, ensure_ascii=False, indent=1))
    else:
        print(f"{'✓' if wynik['ok'] else '✗'} {plik}: liczby {wynik['liczby']}"
              + (f" (na tę długość {wynik['zakres_liczb']})" if wynik["zakres_liczb"] else "")
              + f", analogie {wynik['analogie']}, słowniczek {wynik['slowniczek']} (wymowa {wynik['wymowa']}), "
              f"niepewne {wynik['niepewne']}")
        for b in wynik["bledy"]:
            print(f"  ✗ {b}")
        for o in wynik["ostrzezenia"]:
            print(f"  ⚠ {o}")
    return 0 if wynik["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

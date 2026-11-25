#!/usr/bin/env python3
"""Baza okazji finansowania Bigshorta (SQLite): fundusze, aniołowie, akceleratory, granty, kredyty, konkursy, ulgi.

    okazje.py dodaj plik.jsonl [...]                 # dopisz albo uaktualnij (klucz: id, inaczej slug z nazwy)
    okazje.py lista [--typ T] [--status S] [--projekt P --min-ocena N] [--szukaj FRAZA] [--json]
    okazje.py terminy [--dni 30]                     # otwarte okazje z terminem w oknie, najbliższe pierwsze
    okazje.py ocen <id> <projekt> <0-10> "dlaczego"  # dopasowanie do projektu (np. jarvo, enigma-labz)
    okazje.py status <id> <status> ["notatka"]       # nowa|kandydat|aplikujemy|zlozone|odrzucone|wygrane|zamkniete|nie-pasuje
    okazje.py stare [--dni 60]                       # wpisy do ponownego sprawdzenia (pole sprawdzone)
    okazje.py eksport <katalog>                      # OKAZJE.md (terminy, ranking projektów) + okazje.csv

Baza: --baza (domyślnie baza/okazje.db w katalogu roboczym). Wpis JSONL: nazwa, typ, url i zrodlo (link do źródła
pierwotnego) są obowiązkowe; sprawdzone = data sprawdzenia źródła (RRRR-MM-DD). termin: RRRR-MM-DD albo "rolling".
Kwoty liczbami w walucie z pola waluta; equity słownie ("0%", "7%", "SAFE uncapped"). Skrypt niczego nie wysyła.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

TYPY = ("vc", "aniol", "syndykat", "akcelerator", "fellowship", "grant", "kredyty", "konkurs", "ulga", "dlug",
        "crowdfunding", "pe", "bank", "inne")
STATUSY = ("nowa", "kandydat", "aplikujemy", "zlozone", "odrzucone", "wygrane", "zamkniete", "nie-pasuje")
OTWARTE = ("nowa", "kandydat", "aplikujemy")
POLA = ("id", "nazwa", "typ", "kwota_min", "kwota_max", "waluta", "equity", "dla_kogo", "region", "termin", "url",
        "zrodlo", "sprawdzone", "status", "notatki")
SCHEMAT = """
CREATE TABLE IF NOT EXISTS okazje (
  id TEXT PRIMARY KEY, nazwa TEXT NOT NULL, typ TEXT NOT NULL, kwota_min REAL, kwota_max REAL, waluta TEXT,
  equity TEXT, dla_kogo TEXT, region TEXT, termin TEXT, url TEXT NOT NULL, zrodlo TEXT NOT NULL, sprawdzone TEXT,
  status TEXT NOT NULL DEFAULT 'nowa', notatki TEXT, dodane TEXT NOT NULL, zmienione TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oceny (
  id TEXT NOT NULL, projekt TEXT NOT NULL, ocena INTEGER NOT NULL, dlaczego TEXT NOT NULL, kiedy TEXT NOT NULL,
  PRIMARY KEY (id, projekt));
"""


def slug(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80] or "okazja"


def polacz(sciezka: Path) -> sqlite3.Connection:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(sciezka)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMAT)
    return db


def data(tekst: str | None, pole: str) -> str | None:
    if tekst in (None, ""):
        return None
    if pole == "termin" and tekst == "rolling":
        return tekst
    try:
        return dt.date.fromisoformat(str(tekst)).isoformat()
    except ValueError:
        raise SystemExit(f"{pole}: „{tekst}” to nie data RRRR-MM-DD" + (" ani „rolling”" if pole == "termin" else ""))


def sprawdz(w: dict) -> dict:
    braki = [p for p in ("nazwa", "typ", "url", "zrodlo") if not w.get(p)]
    if braki:
        raise SystemExit(f"{w.get('nazwa') or w}: brak pól {', '.join(braki)}")
    if w["typ"] not in TYPY:
        raise SystemExit(f"{w['nazwa']}: typ „{w['typ']}” spoza {', '.join(TYPY)}")
    if w.get("status", "nowa") not in STATUSY:
        raise SystemExit(f"{w['nazwa']}: status „{w['status']}” spoza {', '.join(STATUSY)}")
    for p in ("url", "zrodlo"):
        if not str(w[p]).startswith(("http://", "https://")):
            raise SystemExit(f"{w['nazwa']}: {p} to nie link http(s)")
    out = {p: w.get(p) for p in POLA}
    out["id"] = w.get("id") or slug(w["nazwa"])
    out["termin"], out["sprawdzone"] = data(w.get("termin"), "termin"), data(w.get("sprawdzone"), "sprawdzone")
    for p in ("kwota_min", "kwota_max"):
        if out[p] is not None:
            out[p] = float(out[p])
    return out


def cmd_dodaj(db: sqlite3.Connection, pliki: list[str], dzis: dt.date) -> int:
    nowe = zmienione = 0
    for plik in pliki:
        for nr, linia in enumerate(Path(plik).read_text(encoding="utf-8").splitlines(), 1):
            if not linia.strip():
                continue
            try:
                w = sprawdz(json.loads(linia))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{plik}:{nr}: zły JSON ({e})")
            jest = db.execute("SELECT * FROM okazje WHERE id = ?", (w["id"],)).fetchone()
            if jest is None:
                w["status"] = w["status"] or "nowa"
                db.execute(f"INSERT INTO okazje ({', '.join(POLA)}, dodane, zmienione) VALUES "
                           f"({', '.join('?' * len(POLA))}, ?, ?)", (*[w[p] for p in POLA], dzis.isoformat(), dzis.isoformat()))
                nowe += 1
            else:                       # nowe dane uzupełniają wpis; status i notatki zmienia się osobno
                zm = {p: w[p] for p in POLA if p not in ("id", "status", "notatki") and w[p] is not None and w[p] != jest[p]}
                if zm:
                    db.execute(f"UPDATE okazje SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                               (*zm.values(), dzis.isoformat(), w["id"]))
                    zmienione += 1
    db.commit()
    print(json.dumps({"nowe": nowe, "zmienione": zmienione, "razem": db.execute("SELECT count(*) FROM okazje").fetchone()[0]}))
    return 0


def wiersze(db: sqlite3.Connection, a: argparse.Namespace) -> list[dict]:
    q, arg = "SELECT o.* FROM okazje o WHERE 1=1", []
    if getattr(a, "typ", None):
        q += " AND o.typ = ?"; arg.append(a.typ)
    if getattr(a, "status", None):
        q += " AND o.status = ?"; arg.append(a.status)
    if getattr(a, "szukaj", None):
        q += " AND (o.nazwa LIKE ? OR o.notatki LIKE ? OR o.dla_kogo LIKE ?)"; arg += [f"%{a.szukaj}%"] * 3
    if getattr(a, "projekt", None):
        q += " AND EXISTS (SELECT 1 FROM oceny c WHERE c.id = o.id AND c.projekt = ? AND c.ocena >= ?)"
        arg += [a.projekt, a.min_ocena]
    out = [dict(r) for r in db.execute(q + " ORDER BY o.nazwa", arg)]
    oceny: dict[str, dict] = {}
    for r in db.execute("SELECT id, projekt, ocena, dlaczego FROM oceny"):
        oceny.setdefault(r["id"], {})[r["projekt"]] = {"ocena": r["ocena"], "dlaczego": r["dlaczego"]}
    for w in out:
        w["oceny"] = oceny.get(w["id"], {})
    return out


def kwota(w: dict) -> str:
    lo, hi, wal = w.get("kwota_min"), w.get("kwota_max"), w.get("waluta") or ""
    f = lambda x: f"{x:,.0f}".replace(",", " ")       # noqa: E731
    if lo is None and hi is None:
        return "?"
    return f"{f(lo)}–{f(hi)} {wal}".strip() if lo is not None and hi is not None and lo != hi else f"{f(hi if hi is not None else lo)} {wal}".strip()


def cmd_lista(db: sqlite3.Connection, a: argparse.Namespace) -> int:
    w = wiersze(db, a)
    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=1))
        return 0
    for x in w:
        oc = ", ".join(f"{p} {o['ocena']}" for p, o in sorted(x["oceny"].items()))
        print(f"{x['id']:<40} {x['typ']:<12} {kwota(x):<22} {x['equity'] or '?':<10} {x['termin'] or '?':<10} "
              f"{x['status']:<10} {oc}")
    print(f"razem: {len(w)}")
    return 0


def nadchodzace(db: sqlite3.Connection, dzis: dt.date, dni: int) -> list[dict]:
    do = (dzis + dt.timedelta(days=dni)).isoformat()
    q = (f"SELECT * FROM okazje WHERE status IN ({', '.join('?' * len(OTWARTE))}) AND termin IS NOT NULL "
         "AND termin != 'rolling' AND termin >= ? AND termin <= ? ORDER BY termin")
    return [dict(r) for r in db.execute(q, (*OTWARTE, dzis.isoformat(), do))]


def cmd_terminy(db: sqlite3.Connection, dni: int, dzis: dt.date) -> int:
    w = nadchodzace(db, dzis, dni)
    for x in w:
        zostalo = (dt.date.fromisoformat(x["termin"]) - dzis).days
        print(f"{x['termin']} ({zostalo} dni)  {x['nazwa']}  {kwota(x)}  {x['equity'] or '?'}  {x['url']}")
    print(f"w oknie {dni} dni: {len(w)}")
    return 0


def cmd_ocen(db: sqlite3.Connection, oid: str, projekt: str, ocena: int, dlaczego: str, dzis: dt.date) -> int:
    if not db.execute("SELECT 1 FROM okazje WHERE id = ?", (oid,)).fetchone():
        raise SystemExit(f"nie ma okazji {oid}")
    if not 0 <= ocena <= 10 or not dlaczego.strip():
        raise SystemExit("ocena 0–10 i powód są obowiązkowe")
    db.execute("INSERT OR REPLACE INTO oceny VALUES (?, ?, ?, ?, ?)", (oid, slug(projekt), ocena, dlaczego.strip(), dzis.isoformat()))
    db.commit()
    return 0


def cmd_status(db: sqlite3.Connection, oid: str, status: str, notatka: str, dzis: dt.date) -> int:
    if status not in STATUSY:
        raise SystemExit(f"status spoza {', '.join(STATUSY)}")
    jest = db.execute("SELECT notatki FROM okazje WHERE id = ?", (oid,)).fetchone()
    if jest is None:
        raise SystemExit(f"nie ma okazji {oid}")
    notatki = jest["notatki"] or ""
    if notatka.strip():
        notatki = (notatki + "\n" if notatki else "") + f"{dzis.isoformat()} {status}: {notatka.strip()}"
    db.execute("UPDATE okazje SET status = ?, notatki = ?, zmienione = ? WHERE id = ?", (status, notatki, dzis.isoformat(), oid))
    db.commit()
    return 0


def cmd_stare(db: sqlite3.Connection, dni: int, dzis: dt.date) -> int:
    granica = (dzis - dt.timedelta(days=dni)).isoformat()
    w = [dict(r) for r in db.execute("SELECT id, nazwa, sprawdzone, url FROM okazje WHERE status NOT IN ('zamkniete', 'nie-pasuje') "
                                     "AND (sprawdzone IS NULL OR sprawdzone < ?) ORDER BY sprawdzone", (granica,))]
    for x in w:
        print(f"{x['sprawdzone'] or 'nigdy':<10}  {x['id']}  {x['url']}")
    print(f"do ponownego sprawdzenia: {len(w)}")
    return 0


def cmd_eksport(db: sqlite3.Connection, katalog: Path, dzis: dt.date) -> int:
    katalog.mkdir(parents=True, exist_ok=True)
    a = argparse.Namespace(typ=None, status=None, szukaj=None, projekt=None)
    w = wiersze(db, a)
    projekty = sorted({p for x in w for p in x["oceny"]})
    with (katalog / "okazje.csv").open("w", newline="", encoding="utf-8") as f:
        pis = csv.writer(f)
        pis.writerow([*POLA, *(f"ocena_{p}" for p in projekty)])
        for x in w:
            pis.writerow([*(x[p] if x[p] is not None else "" for p in POLA), *(x["oceny"].get(p, {}).get("ocena", "") for p in projekty)])
    md = [f"# Okazje finansowania (stan na {dzis.isoformat()})", "",
          f"W bazie: {len(w)}; otwarte: {sum(x['status'] in OTWARTE for x in w)}. Pełna tabela: `okazje.csv`.", ""]
    term = nadchodzace(db, dzis, 45)
    md += ["## Terminy w ciągu 45 dni", ""]
    md += [f"- **{x['termin']}** ({(dt.date.fromisoformat(x['termin']) - dzis).days} dni): [{x['nazwa']}]({x['url']}), "
           f"{kwota(x)}, equity {x['equity'] or '?'}" for x in term] or ["- brak"]
    for p in projekty:
        top = sorted((x for x in w if p in x["oceny"] and x["status"] in OTWARTE), key=lambda x: -x["oceny"][p]["ocena"])[:15]
        md += ["", f"## Najlepiej pasuje: {p}", "", "| Okazja | Typ | Kwota | Equity | Termin | Ocena | Dlaczego |", "|---|---|---|---|---|---|---|"]
        md += [f"| [{x['nazwa']}]({x['url']}) | {x['typ']} | {kwota(x)} | {x['equity'] or '?'} | {x['termin'] or '?'} | "
               f"{x['oceny'][p]['ocena']} | {x['oceny'][p]['dlaczego']} |" for x in top]
    (katalog / "OKAZJE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"okazje": len(w), "terminy_45_dni": len(term), "pliki": [str(katalog / "OKAZJE.md"), str(katalog / "okazje.csv")]}))
    return 0


def main(argv: list[str] | None = None, dzis: dt.date | None = None) -> int:
    dzis = dzis or dt.date.today()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baza", default="baza/okazje.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dodaj"); s.add_argument("pliki", nargs="+")
    s = sub.add_parser("lista")
    s.add_argument("--typ", choices=TYPY); s.add_argument("--status", choices=STATUSY); s.add_argument("--szukaj")
    s.add_argument("--projekt"); s.add_argument("--min-ocena", type=int, default=0); s.add_argument("--json", action="store_true")
    s = sub.add_parser("terminy"); s.add_argument("--dni", type=int, default=30)
    s = sub.add_parser("ocen"); s.add_argument("id"); s.add_argument("projekt"); s.add_argument("ocena", type=int); s.add_argument("dlaczego")
    s = sub.add_parser("status"); s.add_argument("id"); s.add_argument("status"); s.add_argument("notatka", nargs="?", default="")
    s = sub.add_parser("stare"); s.add_argument("--dni", type=int, default=60)
    s = sub.add_parser("eksport"); s.add_argument("katalog")
    a = ap.parse_args(argv)
    db = polacz(Path(a.baza))
    try:
        if a.cmd == "dodaj":
            return cmd_dodaj(db, a.pliki, dzis)
        if a.cmd == "lista":
            if a.projekt:
                a.projekt = slug(a.projekt)
            return cmd_lista(db, a)
        if a.cmd == "terminy":
            return cmd_terminy(db, a.dni, dzis)
        if a.cmd == "ocen":
            return cmd_ocen(db, a.id, a.projekt, a.ocena, a.dlaczego, dzis)
        if a.cmd == "status":
            return cmd_status(db, a.id, a.status, a.notatka, dzis)
        if a.cmd == "stare":
            return cmd_stare(db, a.dni, dzis)
        return cmd_eksport(db, Path(a.katalog), dzis)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

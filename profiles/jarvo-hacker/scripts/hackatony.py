#!/usr/bin/env python3
"""Baza hackathonów Hackera (SQLite): hackathony, bounty, konkursy Kaggle i GPU, z terminami, zasadami i oceną.

    hackatony.py dodaj plik.jsonl [...]               # dopisz albo uaktualnij (klucz: id, inaczej slug z nazwy)
    hackatony.py lista [--status S] [--platforma P] [--min-ocena N] [--szukaj FRAZA] [--json]
    hackatony.py terminy [--dni 14]                   # otwarte, zgłoszenie w oknie, najbliższe pierwsze (czas UTC)
    hackatony.py ocen <id> <0-10> "dlaczego"          # wartość oczekiwana dla floty: nagroda, szansa, wysiłek, zasady
    hackatony.py status <id> <status> ["notatka"]     # nowy|kandydat|zapisani|budujemy|zgloszony|wygrany|przegrany|odpuszczony|zamkniety
    hackatony.py stare [--dni 14]                     # otwarte wpisy do ponownego sprawdzenia (pole sprawdzone)
    hackatony.py eksport <katalog>                    # HACKATONY.md (terminy, ranking, wyniki) + hackatony.csv

Baza: --baza (domyślnie baza/hackatony.db w katalogu roboczym). Wpis JSONL: nazwa, platforma, url i zrodlo (strona
hackathonu z zasadami) są obowiązkowe; zgloszenie_do = termin zgłoszenia projektu w UTC (RRRR-MM-DDTHH:MM albo
RRRR-MM-DD), rejestracja_do i start jak wyżej; ai_kod: tak | nie | niejasne (czy regulamin dopuszcza kod pisany przez AI);
solo: tak | nie | niejasne. Skrypt niczego nie wysyła ani nie rejestruje.
"""

from __future__ import annotations

import argparse
import os
import csv
import datetime as dt
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

STATUSY = ("nowy", "kandydat", "zapisani", "budujemy", "zgloszony", "wygrany", "przegrany", "odpuszczony", "zamkniety")
OTWARTE = ("nowy", "kandydat", "zapisani", "budujemy")
TRZY = ("tak", "nie", "niejasne")
POLA = ("id", "nazwa", "platforma", "url", "zrodlo", "start", "rejestracja_do", "zgloszenie_do", "tryb", "miejsce",
        "pula", "waluta", "tracki", "sponsorzy", "solo", "ai_kod", "wymagania", "kryteria", "kwalifikowalnosc",
        "sprawdzone", "status", "notatki")
DATY = ("start", "rejestracja_do", "zgloszenie_do")
SCHEMAT = f"""
CREATE TABLE IF NOT EXISTS hackatony ({', '.join(f'{p} {"REAL" if p == "pula" else "TEXT"}' for p in POLA)},
  ocena INTEGER, dlaczego TEXT, dodane TEXT NOT NULL, zmienione TEXT NOT NULL, PRIMARY KEY (id));
"""


def slug(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80] or "hackathon"


def polacz(sciezka: Path) -> sqlite3.Connection:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(sciezka)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMAT)
    return db


def czas(tekst: str | None, pole: str) -> str | None:
    """Data albo data z godziną UTC → RRRR-MM-DD lub RRRR-MM-DDTHH:MM (porównywalne tekstowo)."""
    if tekst in (None, ""):
        return None
    t = str(tekst).strip().replace(" ", "T").removesuffix("Z").removesuffix("+00:00")
    try:
        return dt.datetime.fromisoformat(t).strftime("%Y-%m-%dT%H:%M") if "T" in t else dt.date.fromisoformat(t).isoformat()
    except ValueError:
        raise SystemExit(f"{pole}: „{tekst}” to nie data RRRR-MM-DD ani RRRR-MM-DDTHH:MM (UTC)")


def sprawdz(w: dict) -> dict:
    braki = [p for p in ("nazwa", "platforma", "url", "zrodlo") if not w.get(p)]
    if braki:
        raise SystemExit(f"{w.get('nazwa') or w}: brak pól {', '.join(braki)}")
    for p in ("url", "zrodlo"):
        if not str(w[p]).startswith(("http://", "https://")):
            raise SystemExit(f"{w['nazwa']}: {p} to nie link http(s)")
    for p in ("solo", "ai_kod"):
        if w.get(p) not in (None, *TRZY):
            raise SystemExit(f"{w['nazwa']}: {p} „{w[p]}” spoza {', '.join(TRZY)}")
    if w.get("status", "nowy") not in STATUSY:
        raise SystemExit(f"{w['nazwa']}: status „{w['status']}” spoza {', '.join(STATUSY)}")
    out = {p: w.get(p) for p in POLA}
    out["id"] = w.get("id") or slug(w["nazwa"])
    for p in DATY:
        out[p] = czas(w.get(p), p)
    if w.get("sprawdzone"):
        try:
            out["sprawdzone"] = dt.date.fromisoformat(str(w["sprawdzone"])).isoformat()
        except ValueError:
            raise SystemExit(f"{w['nazwa']}: sprawdzone to nie data RRRR-MM-DD")
    for p in ("tracki", "sponsorzy", "wymagania", "kryteria"):
        if isinstance(out[p], list):
            out[p] = "; ".join(map(str, out[p]))
    if out["pula"] is not None:
        out["pula"] = float(out["pula"])
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
            jest = db.execute("SELECT * FROM hackatony WHERE id = ?", (w["id"],)).fetchone()
            if jest is None:
                w["status"] = w["status"] or "nowy"
                db.execute(f"INSERT INTO hackatony ({', '.join(POLA)}, dodane, zmienione) VALUES ({', '.join('?' * len(POLA))}, ?, ?)",
                           (*[w[p] for p in POLA], dzis.isoformat(), dzis.isoformat()))
                nowe += 1
            else:                       # nowe dane uzupełniają wpis; status i notatki zmienia się osobno
                zm = {p: w[p] for p in POLA if p not in ("id", "status", "notatki") and w[p] is not None and w[p] != jest[p]}
                if zm:
                    db.execute(f"UPDATE hackatony SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                               (*zm.values(), dzis.isoformat(), w["id"]))
                    zmienione += 1
    db.commit()
    print(json.dumps({"nowe": nowe, "zmienione": zmienione, "razem": db.execute("SELECT count(*) FROM hackatony").fetchone()[0]}))
    return 0


def pula(w: dict) -> str:
    return f"{w['pula']:,.0f} {w.get('waluta') or ''}".replace(",", " ").strip() if w.get("pula") is not None else "?"


def cmd_lista(db: sqlite3.Connection, a: argparse.Namespace) -> int:
    q, arg = "SELECT * FROM hackatony WHERE 1=1", []
    if a.status:
        q += " AND status = ?"; arg.append(a.status)
    if a.platforma:
        q += " AND lower(platforma) = lower(?)"; arg.append(a.platforma)
    if a.min_ocena:
        q += " AND ocena >= ?"; arg.append(a.min_ocena)
    if a.szukaj:
        q += " AND (nazwa LIKE ? OR tracki LIKE ? OR sponsorzy LIKE ? OR notatki LIKE ?)"; arg += [f"%{a.szukaj}%"] * 4
    w = [dict(r) for r in db.execute(q + " ORDER BY zgloszenie_do IS NULL, zgloszenie_do, nazwa", arg)]
    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=1))
        return 0
    for x in w:
        print(f"{x['id']:<40} {x['platforma'] or '?':<12} {pula(x):<16} {x['zgloszenie_do'] or '?':<17} "
              f"{x['tryb'] or '?':<8} ai:{x['ai_kod'] or '?':<9} {x['status']:<11} {x['ocena'] if x['ocena'] is not None else '-'}")
    print(f"razem: {len(w)}")
    return 0


def nadchodzace(db: sqlite3.Connection, teraz: dt.datetime, dni: int) -> list[dict]:
    od, do = teraz.strftime("%Y-%m-%dT%H:%M"), (teraz + dt.timedelta(days=dni)).strftime("%Y-%m-%dT%H:%M")
    q = (f"SELECT * FROM hackatony WHERE status IN ({', '.join('?' * len(OTWARTE))}) AND zgloszenie_do IS NOT NULL "
         "AND (CASE WHEN length(zgloszenie_do) = 10 THEN zgloszenie_do || 'T23:59' ELSE zgloszenie_do END) BETWEEN ? AND ? "
         "ORDER BY zgloszenie_do")
    return [dict(r) for r in db.execute(q, (*OTWARTE, od, do))]


def zostalo(termin: str, teraz: dt.datetime) -> str:
    t = dt.datetime.fromisoformat(termin + ("T23:59" if len(termin) == 10 else ""))
    h = int((t - teraz).total_seconds() // 3600)
    return f"{h} h" if h < 72 else f"{h // 24} dni"     # ostatnie 3 doby w godzinach: tyle trwa sprint budowy


def cmd_terminy(db: sqlite3.Connection, dni: int, teraz: dt.datetime) -> int:
    w = nadchodzace(db, teraz, dni)
    for x in w:
        print(f"{x['zgloszenie_do']} UTC ({zostalo(x['zgloszenie_do'], teraz)})  {x['nazwa']}  {pula(x)}  "
              f"{x['tryb'] or '?'}  ocena {x['ocena'] if x['ocena'] is not None else '-'}  {x['url']}")
    print(f"w oknie {dni} dni: {len(w)}")
    return 0


def jest_id(db: sqlite3.Connection, hid: str) -> sqlite3.Row:
    r = db.execute("SELECT * FROM hackatony WHERE id = ?", (hid,)).fetchone()
    if r is None:
        raise SystemExit(f"nie ma hackathonu {hid}")
    return r


def cmd_ocen(db: sqlite3.Connection, hid: str, ocena: int, dlaczego: str, dzis: dt.date) -> int:
    jest_id(db, hid)
    if not 0 <= ocena <= 10 or not dlaczego.strip():
        raise SystemExit("ocena 0–10 i powód są obowiązkowe")
    db.execute("UPDATE hackatony SET ocena = ?, dlaczego = ?, zmienione = ? WHERE id = ?", (ocena, dlaczego.strip(), dzis.isoformat(), hid))
    db.commit()
    return 0


def cmd_status(db: sqlite3.Connection, hid: str, status: str, notatka: str, dzis: dt.date) -> int:
    if status not in STATUSY:
        raise SystemExit(f"status spoza {', '.join(STATUSY)}")
    notatki = jest_id(db, hid)["notatki"] or ""
    if notatka.strip():
        notatki = (notatki + "\n" if notatki else "") + f"{dzis.isoformat()} {status}: {notatka.strip()}"
    db.execute("UPDATE hackatony SET status = ?, notatki = ?, zmienione = ? WHERE id = ?", (status, notatki, dzis.isoformat(), hid))
    db.commit()
    return 0


def cmd_stare(db: sqlite3.Connection, dni: int, dzis: dt.date) -> int:
    granica = (dzis - dt.timedelta(days=dni)).isoformat()
    w = [dict(r) for r in db.execute(f"SELECT id, sprawdzone, url FROM hackatony WHERE status IN ({', '.join('?' * len(OTWARTE))}) "
                                     "AND (sprawdzone IS NULL OR sprawdzone < ?) ORDER BY sprawdzone", (*OTWARTE, granica))]
    for x in w:
        print(f"{x['sprawdzone'] or 'nigdy':<10}  {x['id']}  {x['url']}")
    print(f"do ponownego sprawdzenia: {len(w)}")
    return 0


def cmd_eksport(db: sqlite3.Connection, katalog: Path, teraz: dt.datetime) -> int:
    katalog.mkdir(parents=True, exist_ok=True)
    w = [dict(r) for r in db.execute("SELECT * FROM hackatony ORDER BY zgloszenie_do IS NULL, zgloszenie_do")]
    with (katalog / "hackatony.csv").open("w", newline="", encoding="utf-8") as f:
        pis = csv.writer(f)
        pis.writerow([*POLA, "ocena", "dlaczego"])
        for x in w:
            pis.writerow([x[p] if x[p] is not None else "" for p in (*POLA, "ocena", "dlaczego")])
    term = nadchodzace(db, teraz, 30)
    md = [f"# Hackathony (stan na {teraz:%Y-%m-%d %H:%M} UTC)", "",
          f"W bazie: {len(w)}; otwarte: {sum(x['status'] in OTWARTE for x in w)}. Pełna tabela: `hackatony.csv`.", "",
          "## Zgłoszenia w ciągu 30 dni", ""]
    md += [f"- **{x['zgloszenie_do']} UTC** ({zostalo(x['zgloszenie_do'], teraz)}): [{x['nazwa']}]({x['url']}), {pula(x)}, "
           f"{x['tryb'] or '?'}, AI: {x['ai_kod'] or '?'}, ocena {x['ocena'] if x['ocena'] is not None else '-'}" for x in term] or ["- brak"]
    top = sorted((x for x in w if x["status"] in OTWARTE and x["ocena"] is not None), key=lambda x: -x["ocena"])[:15]
    md += ["", "## Najlepsze dla floty", "", "| Hackathon | Platforma | Pula | Zgłoszenie do (UTC) | Tryb | AI | Ocena | Dlaczego |",
           "|---|---|---|---|---|---|---|---|"]
    md += [f"| [{x['nazwa']}]({x['url']}) | {x['platforma']} | {pula(x)} | {x['zgloszenie_do'] or '?'} | {x['tryb'] or '?'} | "
           f"{x['ai_kod'] or '?'} | {x['ocena']} | {x['dlaczego']} |" for x in top]
    wyniki = [x for x in w if x["status"] in ("zgloszony", "wygrany", "przegrany")]
    if wyniki:
        md += ["", "## Nasze zgłoszenia i wyniki", ""] + [f"- {x['nazwa']}: **{x['status']}**" for x in wyniki]
    (katalog / "HACKATONY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"hackatony": len(w), "zgloszenia_30_dni": len(term), "pliki": [str(katalog / "HACKATONY.md"), str(katalog / "hackatony.csv")]}))
    return 0


def domyslna_baza() -> str:
    """Katalog roboczy Hackera w danych Jarva (JARVO_DATA_DIR), niezależnie od katalogu, w którym stoi terminal
    (25.11: tura z panelu zapisała bazę w katalogu profilu zamiast w katalogu roboczym)."""
    dane = os.environ.get("JARVO_DATA_DIR")
    return str(Path(dane) / "workspaces" / "jarvo-hacker" / "baza" / "hackatony.db") if dane else "baza/hackatony.db"


def main(argv: list[str] | None = None, teraz: dt.datetime | None = None) -> int:
    teraz = teraz or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baza", default=domyslna_baza())
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dodaj"); s.add_argument("pliki", nargs="+")
    s = sub.add_parser("lista")
    s.add_argument("--status", choices=STATUSY); s.add_argument("--platforma"); s.add_argument("--min-ocena", type=int, default=0)
    s.add_argument("--szukaj"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("terminy"); s.add_argument("--dni", type=int, default=14)
    s = sub.add_parser("ocen"); s.add_argument("id"); s.add_argument("ocena", type=int); s.add_argument("dlaczego")
    s = sub.add_parser("status"); s.add_argument("id"); s.add_argument("status"); s.add_argument("notatka", nargs="?", default="")
    s = sub.add_parser("stare"); s.add_argument("--dni", type=int, default=14)
    s = sub.add_parser("eksport"); s.add_argument("katalog")
    a = ap.parse_args(argv)
    db = polacz(Path(a.baza))
    dzis = teraz.date()
    try:
        if a.cmd == "dodaj":
            return cmd_dodaj(db, a.pliki, dzis)
        if a.cmd == "lista":
            return cmd_lista(db, a)
        if a.cmd == "terminy":
            return cmd_terminy(db, a.dni, teraz)
        if a.cmd == "ocen":
            return cmd_ocen(db, a.id, a.ocena, a.dlaczego, dzis)
        if a.cmd == "status":
            return cmd_status(db, a.id, a.status, a.notatka, dzis)
        if a.cmd == "stare":
            return cmd_stare(db, a.dni, dzis)
        return cmd_eksport(db, Path(a.katalog), teraz)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

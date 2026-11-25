#!/usr/bin/env python3
"""Baza hackathonów Hackera (SQLite): hackathony, bounty, konkursy Kaggle i GPU, z terminami, zasadami i oceną.

    hackatony.py dodaj plik.jsonl [...]               # dopisz albo uaktualnij (klucz: id, inaczej slug z nazwy)
    hackatony.py lista [--status S] [--platforma P] [--min-ocena N] [--szukaj FRAZA] [--json]
    hackatony.py terminy [--dni 14]                   # otwarte, zgłoszenie w oknie, najbliższe pierwsze (czas UTC)
    hackatony.py ocen <id> <0-10> "dlaczego"          # wartość oczekiwana dla floty: nagroda, szansa, wysiłek, zasady
    hackatony.py status <id> <status> ["notatka"]     # nowy|kandydat|zapisani|budujemy|zgloszony|wygrany|przegrany|odpuszczony|zamkniety
    hackatony.py stare [--dni 14]                     # otwarte wpisy do ponownego sprawdzenia (pole sprawdzone)
    hackatony.py eksport <katalog>                    # HACKATONY.md (terminy, ranking, wyniki) + hackatony.csv + kalendarz
    hackatony.py kalendarz <katalog> [--dni 120]      # KALENDARZ.md (miesiące i tygodnie) + hackatony.ics do subskrypcji
    hackatony.py przypomnij [--katalog K] [--tydzien] # rutyna: co w 72 h (i w poniedziałek 14 dni); nic = puste wyjście

Baza: --baza (domyślnie baza/hackatony.db w katalogu roboczym). Wpis JSONL: nazwa, platforma, url i zrodlo (strona
hackathonu z zasadami) są obowiązkowe; zgloszenie_do = termin zgłoszenia projektu w UTC (RRRR-MM-DDTHH:MM albo
RRRR-MM-DD), rejestracja_do, start i wyniki jak wyżej; ai_kod: tak | nie | niejasne (czy regulamin dopuszcza kod pisany
przez AI); solo: tak | nie | niejasne. Kalendarz: rejestracja, start, zgłoszenie i wyniki każdego otwartego wpisu, a przy
statusie zapisani/budujemy także nasze kamienie (zamrożenie 8 h i gotowe 6 h przed zgłoszeniem). Skrypt niczego nie
wysyła ani nie rejestruje.
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
POLA = ("id", "nazwa", "platforma", "url", "zrodlo", "start", "rejestracja_do", "zgloszenie_do", "wyniki", "tryb", "miejsce",
        "pula", "waluta", "tracki", "sponsorzy", "solo", "ai_kod", "wymagania", "kryteria", "kwalifikowalnosc",
        "sprawdzone", "status", "notatki")
DATY = ("start", "rejestracja_do", "zgloszenie_do", "wyniki")
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
    jest = {r[1] for r in db.execute("PRAGMA table_info(hackatony)")}
    for p in POLA:                                  # baza sprzed nowego pola (25.11: `wyniki`) dostaje kolumnę
        if p not in jest:
            db.execute(f"ALTER TABLE hackatony ADD COLUMN {p} {'REAL' if p == 'pula' else 'TEXT'}")
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
    if h < 0:
        return "dziś" if t.date() == teraz.date() else "minęło"
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
    zapisz_kalendarz(db, katalog, teraz)
    print(json.dumps({"hackatony": len(w), "zgloszenia_30_dni": len(term), "pliki": [str(katalog / p) for p in
                      ("HACKATONY.md", "hackatony.csv", "KALENDARZ.md", "hackatony.ics")]}))
    return 0


# ------------------------------------------------------------------------------------------- kalendarz
# 25.11 właściciel: „kalendarz, który trzyma wszystkie terminy”. Jedno źródło (baza) → widok miesięcy w Markdown,
# plik .ics do subskrypcji w telefonie i przypomnienia rutyny; czas zawsze w UTC i w strefie właściciela.
STREFA = os.environ.get("JARVO_STREFA", "Europe/Warsaw")
ETAPY = (("rejestracja_do", "Rejestracja do", True), ("start", "Start", False), ("zgloszenie_do", "Zgłoszenie do", True),
         ("wyniki", "Wyniki", False))
MIESIACE = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik",
            "listopad", "grudzień")
DNI = ("pn", "wt", "śr", "cz", "pt", "sb", "nd")


def chwila(tekst: str, koniec_dnia: bool) -> dt.datetime:
    """Pole daty z bazy → chwila UTC; sama data to koniec dnia (terminy) albo jego początek (start, wyniki)."""
    return dt.datetime.fromisoformat(tekst + (("T23:59" if koniec_dnia else "T00:00") if len(tekst) == 10 else ""))


def wydarzenia(db: sqlite3.Connection, od: dt.datetime, do: dt.datetime) -> list[dict]:
    """Etapy otwartych hackathonów (zgłoszony: tylko wyniki) i nasze kamienie przy zapisanych i budowanych."""
    out = []
    for r in db.execute("SELECT * FROM hackatony WHERE status IN ('nowy','kandydat','zapisani','budujemy','zgloszony')"):
        x = dict(r)
        for pole, nazwa, koniec in ETAPY:
            if x[pole] and (x["status"] != "zgloszony" or pole == "wyniki"):
                out.append({"kiedy": chwila(x[pole], koniec), "etap": nazwa, "pole": pole, "dzien": len(x[pole]) == 10, "h": x})
        if x["status"] in ("zapisani", "budujemy") and x["zgloszenie_do"]:
            t = chwila(x["zgloszenie_do"], True)
            out += [{"kiedy": t - dt.timedelta(hours=8), "etap": "Zamrożenie projektu", "pole": "zamrozenie", "dzien": False, "h": x},
                    {"kiedy": t - dt.timedelta(hours=6), "etap": "Gotowe do wysłania", "pole": "gotowe", "dzien": False, "h": x}]
    return sorted((e for e in out if od <= e["kiedy"] <= do), key=lambda e: (e["kiedy"], e["h"]["nazwa"]))


def lokalnie(t: dt.datetime) -> dt.datetime:
    from zoneinfo import ZoneInfo
    return t.replace(tzinfo=dt.timezone.utc).astimezone(ZoneInfo(STREFA))


def linia(e: dict, teraz: dt.datetime) -> str:
    x, lok = e["h"], lokalnie(e["kiedy"])
    kiedy = f"{DNI[lok.weekday()]} {lok:%d.%m}" + ("" if e["dzien"] else f" {lok:%H:%M}")
    return (f"**{kiedy}** ({zostalo(e['kiedy'].strftime('%Y-%m-%dT%H:%M'), teraz)}) · {e['etap']} · [{x['nazwa']}]({x['url']}) · "
            f"{pula(x)} · {x['status']}" + (f" · ocena {x['ocena']}" if x["ocena"] is not None else ""))


def ics_tekst(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def zwin(l: str) -> list[str]:
    """Linia iCalendar najwyżej 75 bajtów, dalej kontynuacja od spacji (RFC 5545 §3.1)."""
    out, biez = [], ""
    for z in l:
        if len((biez + z).encode()) > 75:
            out.append(biez)
            biez = " "
        biez += z
    return out + [biez]


def zapisz_kalendarz(db: sqlite3.Connection, katalog: Path, teraz: dt.datetime, dni: int = 120) -> list[dict]:
    katalog.mkdir(parents=True, exist_ok=True)
    ev = wydarzenia(db, teraz - dt.timedelta(days=1), teraz + dt.timedelta(days=dni))
    md = [f"# Kalendarz hackathonów (stan na {lokalnie(teraz):%d.%m.%Y %H:%M}, czas {STREFA})", "",
          "Etapy otwartych hackathonów z bazy, nasze kamienie (zamrożenie, gotowe) przy startach w toku. "
          "Subskrypcja w telefonie: plik `hackatony.ics`.", ""]
    pilne = [e for e in ev if teraz <= e["kiedy"] <= teraz + dt.timedelta(hours=72)]
    md += ["## W ciągu 72 godzin", ""] + ([f"- {linia(e, teraz)}" for e in pilne] or ["- nic"])
    miesiac = tydzien = None
    for e in ev:
        lok = lokalnie(e["kiedy"])
        if (lok.year, lok.month) != miesiac:
            miesiac, tydzien = (lok.year, lok.month), None
            md += ["", f"## {MIESIACE[lok.month - 1].capitalize()} {lok.year}"]
        if lok.isocalendar()[1] != tydzien:
            tydzien = lok.isocalendar()[1]
            pon = lok.date() - dt.timedelta(days=lok.weekday())
            md += ["", f"### Tydzień {pon:%d.%m} do {pon + dt.timedelta(days=6):%d.%m}", ""]
        md.append(f"- {linia(e, teraz)}")
    (katalog / "KALENDARZ.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    stamp = teraz.strftime("%Y%m%dT%H%M%SZ")
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jarvo//Hacker//PL", "CALSCALE:GREGORIAN",
           "X-WR-CALNAME:Hackathony (Jarvo)", "X-WR-TIMEZONE:UTC"]
    for e in ev:
        x = e["h"]
        if e["dzien"] and e["pole"] in ("start", "wyniki"):
            d = e["kiedy"].date()
            czasy = [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}"]
        else:
            czasy = [f"DTSTART:{e['kiedy']:%Y%m%dT%H%M%SZ}", f"DTEND:{e['kiedy'] + dt.timedelta(minutes=30):%Y%m%dT%H%M%SZ}"]
        opis = f"{pula(x)}, {x['tryb'] or '?'}, AI: {x['ai_kod'] or '?'}, status {x['status']}" + (
            f", ocena {x['ocena']}: {x['dlaczego']}" if x["ocena"] is not None else "") + f"\n{x['url']}"
        ics += ["BEGIN:VEVENT", f"UID:{x['id']}-{e['pole']}@jarvo-hacker", f"DTSTAMP:{stamp}", *czasy,
                f"SUMMARY:{ics_tekst(e['etap'] + ': ' + x['nazwa'])}", f"DESCRIPTION:{ics_tekst(opis)}", f"URL:{x['url']}"]
        if e["pole"] in ("zgloszenie_do", "rejestracja_do", "gotowe"):
            ics += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_tekst(e['etap'])}", "TRIGGER:-P1D", "END:VALARM"]
        ics.append("END:VEVENT")
    ics.append("END:VCALENDAR")
    (katalog / "hackatony.ics").write_text("\r\n".join(z for l in ics for z in zwin(l)) + "\r\n", encoding="utf-8")
    return ev


def cmd_kalendarz(db: sqlite3.Connection, katalog: Path, dni: int, teraz: dt.datetime) -> int:
    ev = zapisz_kalendarz(db, katalog, teraz, dni)
    print(json.dumps({"wydarzenia": len(ev), "pliki": [str(katalog / "KALENDARZ.md"), str(katalog / "hackatony.ics")]}))
    return 0


def cmd_przypomnij(db: sqlite3.Connection, katalog: Path | None, tydzien: bool, teraz: dt.datetime) -> int:
    """Rutyna bez modelu: odświeża kalendarz i wypisuje tylko to, co wymaga uwagi; puste wyjście = cisza."""
    if katalog:
        zapisz_kalendarz(db, katalog, teraz)
    pilne = wydarzenia(db, teraz, teraz + dt.timedelta(hours=72))
    tydzien = tydzien or lokalnie(teraz).weekday() == 0
    dalsze = [e for e in wydarzenia(db, teraz + dt.timedelta(hours=72), teraz + dt.timedelta(days=14))] if tydzien else []
    if not pilne and not dalsze:
        return 0
    out = []
    if pilne:
        out += ["Hackathony: w ciągu 72 godzin"] + [f"- {linia(e, teraz)}" for e in pilne]
    if dalsze:
        out += ["Hackathony: dalsze 14 dni"] + [f"- {linia(e, teraz)}" for e in dalsze]
    if katalog:
        out.append(f"Cały kalendarz: {katalog / 'KALENDARZ.md'} (subskrypcja: hackatony.ics)")
    print("\n".join(out))
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
    s = sub.add_parser("kalendarz"); s.add_argument("katalog"); s.add_argument("--dni", type=int, default=120)
    s = sub.add_parser("przypomnij"); s.add_argument("--katalog"); s.add_argument("--tydzien", action="store_true")
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
        if a.cmd == "kalendarz":
            return cmd_kalendarz(db, Path(a.katalog), a.dni, teraz)
        if a.cmd == "przypomnij":
            return cmd_przypomnij(db, Path(a.katalog) if a.katalog else None, a.tydzien, teraz)
        return cmd_eksport(db, Path(a.katalog), teraz)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

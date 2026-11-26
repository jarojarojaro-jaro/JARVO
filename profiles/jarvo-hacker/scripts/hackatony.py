#!/usr/bin/env python3
"""Baza hackathonów Hackera (SQLite): hackathony, bounty, konkursy Kaggle i GPU, z terminami, zasadami, oceną,
naszym udziałem i historią każdej zmiany.

    hackatony.py dodaj plik.jsonl [...]               # dopisz albo uaktualnij (klucz: id, inaczej slug z nazwy)
    hackatony.py lista [--status S] [--platforma P] [--min-ocena N] [--szukaj FRAZA] [--json]
    hackatony.py terminy [--dni 14]                   # otwarte, zgłoszenie w oknie, najbliższe pierwsze (czas UTC)
    hackatony.py ocen <id> <0-10> "dlaczego"          # wartość oczekiwana dla floty: nagroda, szansa, wysiłek, zasady
    hackatony.py status <id> <status> ["notatka"]     # nowy|kandydat|zapisani|budujemy|zgloszony|wygrany|przegrany|odpuszczony|zamkniety
    hackatony.py ustaw <id> pole=wartość [...]        # nasz udział: konto, projekt, zgloszenie_url, demo_url, nagroda,
                                                      # krok (następny krok), krok_do (jego termin UTC); pusta wartość czyści
    hackatony.py notuj <id> "co się stało"            # wpis do historii (mail, rozmowa, decyzja, feedback jury)
    hackatony.py historia [<id>] [--dni 30]           # historia zmian, najnowsze pierwsze
    hackatony.py stare [--dni 14]                     # otwarte wpisy do ponownego sprawdzenia (pole sprawdzone)
    hackatony.py eksport <katalog>                    # HACKATONY.md (terminy, ranking, wyniki) + hackatony.csv + kalendarz
    hackatony.py kalendarz <katalog> [--dni 120]      # KALENDARZ.md (miesiące i tygodnie) + hackatony.ics do subskrypcji
    hackatony.py raport [--katalog K]                 # raport dnia: najlepsze do wzięcia teraz i nasze starty

Baza: --baza (domyślnie baza/hackatony.db w katalogu roboczym). Wpis JSONL: nazwa, platforma, url i zrodlo (strona
hackathonu z zasadami) są obowiązkowe; zgloszenie_do = termin zgłoszenia projektu w UTC (RRRR-MM-DDTHH:MM albo
RRRR-MM-DD), rejestracja_do, start, wyniki i krok_do jak wyżej; ai_kod: tak | nie | niejasne (czy regulamin dopuszcza
kod pisany przez AI); solo: tak | nie | niejasne. Kalendarz: rejestracja, start, zgłoszenie i wyniki każdego otwartego
wpisu, nasz następny krok, a przy statusie zapisani/budujemy także nasze kamienie (zamrożenie 8 h i gotowe 6 h przed
zgłoszeniem). Każda zmiana bazy odświeża notatkę „kalendarz hackathonów” w Mózgu (skarbiec Jarva,
`agenci/jarvo-hacker/`). Skrypt niczego nie wysyła ani nie rejestruje.
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
        "sprawdzone", "status", "notatki", "konto", "projekt", "zgloszenie_url", "demo_url", "nagroda", "krok", "krok_do")
DATY = ("start", "rejestracja_do", "zgloszenie_do", "wyniki", "krok_do")
UDZIAL = ("konto", "projekt", "zgloszenie_url", "demo_url", "nagroda", "krok", "krok_do")   # pola `ustaw`
SCHEMAT = f"""
CREATE TABLE IF NOT EXISTS hackatony ({', '.join(f'{p} {"REAL" if p == "pula" else "TEXT"}' for p in POLA)},
  ocena INTEGER, dlaczego TEXT, dodane TEXT NOT NULL, zmienione TEXT NOT NULL, PRIMARY KEY (id));
CREATE TABLE IF NOT EXISTS historia (nr INTEGER PRIMARY KEY AUTOINCREMENT, kiedy TEXT NOT NULL, id TEXT NOT NULL,
  co TEXT NOT NULL, opis TEXT NOT NULL);
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
    for p in POLA:                                  # baza sprzed nowego pola (25.11: `wyniki`, pola udziału) dostaje kolumnę
        if p not in jest:
            db.execute(f"ALTER TABLE hackatony ADD COLUMN {p} {'REAL' if p == 'pula' else 'TEXT'}")
    return db


def zapisz_historie(db: sqlite3.Connection, teraz: dt.datetime, hid: str, co: str, opis: str) -> None:
    db.execute("INSERT INTO historia (kiedy, id, co, opis) VALUES (?, ?, ?, ?)", (f"{teraz:%Y-%m-%dT%H:%M}", hid, co, opis))


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


def cmd_dodaj(db: sqlite3.Connection, pliki: list[str], teraz: dt.datetime) -> int:
    dzis = teraz.date()
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
                zapisz_historie(db, teraz, w["id"], "dodany", f"{w['nazwa']} ({w['platforma']}), status {w['status']}")
                nowe += 1
            else:                       # nowe dane uzupełniają wpis; status i notatki zmienia się osobno
                zm = {p: w[p] for p in POLA if p not in ("id", "status", "notatki") and w[p] is not None and w[p] != jest[p]}
                if zm:
                    db.execute(f"UPDATE hackatony SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                               (*zm.values(), dzis.isoformat(), w["id"]))
                    zapisz_historie(db, teraz, w["id"], "dane", ", ".join(f"{p}: {jest[p] or '-'} → {v}" for p, v in zm.items()))
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
        q += (" AND (nazwa LIKE ? OR tracki LIKE ? OR sponsorzy LIKE ? OR notatki LIKE ? OR krok LIKE ? "
              "OR id IN (SELECT id FROM historia WHERE opis LIKE ?))"); arg += [f"%{a.szukaj}%"] * 6
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
        print(f"{termin_pl(x['zgloszenie_do'])} ({zostalo(x['zgloszenie_do'], teraz)})  {x['nazwa']}  {pula(x)}  "
              f"{x['tryb'] or '?'}  ocena {x['ocena'] if x['ocena'] is not None else '-'}  {x['url']}")
    print(f"w oknie {dni} dni: {len(w)}")
    return 0


def jest_id(db: sqlite3.Connection, hid: str) -> sqlite3.Row:
    r = db.execute("SELECT * FROM hackatony WHERE id = ?", (hid,)).fetchone()
    if r is None:
        raise SystemExit(f"nie ma hackathonu {hid}")
    return r


def cmd_ocen(db: sqlite3.Connection, hid: str, ocena: int, dlaczego: str, teraz: dt.datetime) -> int:
    jest_id(db, hid)
    if not 0 <= ocena <= 10 or not dlaczego.strip():
        raise SystemExit("ocena 0–10 i powód są obowiązkowe")
    db.execute("UPDATE hackatony SET ocena = ?, dlaczego = ?, zmienione = ? WHERE id = ?", (ocena, dlaczego.strip(), teraz.date().isoformat(), hid))
    zapisz_historie(db, teraz, hid, "ocena", f"{ocena}/10: {dlaczego.strip()}")
    db.commit()
    return 0


def cmd_status(db: sqlite3.Connection, hid: str, status: str, notatka: str, teraz: dt.datetime) -> int:
    if status not in STATUSY:
        raise SystemExit(f"status spoza {', '.join(STATUSY)}")
    byl = jest_id(db, hid)["status"]
    db.execute("UPDATE hackatony SET status = ?, zmienione = ? WHERE id = ?", (status, teraz.date().isoformat(), hid))
    zapisz_historie(db, teraz, hid, "status", f"{byl} → {status}" + (f": {notatka.strip()}" if notatka.strip() else ""))
    db.commit()
    return 0


def cmd_ustaw(db: sqlite3.Connection, hid: str, pary: list[str], teraz: dt.datetime) -> int:
    """Pola naszego udziału (konto, projekt, linki, nagroda, następny krok z terminem); `pole=` czyści pole."""
    jest = jest_id(db, hid)
    zm = {}
    for para in pary:
        pole, znak, wartosc = para.partition("=")
        if not znak or pole not in UDZIAL:
            raise SystemExit(f"„{para}”: podaj pole=wartość, pole z {', '.join(UDZIAL)}")
        zm[pole] = czas(wartosc, pole) if pole == "krok_do" else (wartosc.strip() or None)
    zm = {p: v for p, v in zm.items() if v != jest[p]}
    if zm:
        db.execute(f"UPDATE hackatony SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                   (*zm.values(), teraz.date().isoformat(), hid))
        zapisz_historie(db, teraz, hid, "udział", ", ".join(f"{p}: {v or '(puste)'}" for p, v in zm.items()))
        db.commit()
    return 0


def cmd_notuj(db: sqlite3.Connection, hid: str, tekst: str, teraz: dt.datetime) -> int:
    jest_id(db, hid)
    if not tekst.strip():
        raise SystemExit("pusta notatka")
    zapisz_historie(db, teraz, hid, "notatka", tekst.strip())
    db.commit()
    return 0


def historia(db: sqlite3.Connection, hid: str | None, od: dt.datetime) -> list[dict]:
    q, arg = "SELECT h.*, k.nazwa FROM historia h LEFT JOIN hackatony k ON k.id = h.id WHERE h.kiedy >= ?", [f"{od:%Y-%m-%dT%H:%M}"]
    if hid:
        q += " AND h.id = ?"; arg.append(hid)
    return [dict(r) for r in db.execute(q + " ORDER BY h.nr DESC", arg)]


def cmd_historia(db: sqlite3.Connection, hid: str | None, dni: int, teraz: dt.datetime) -> int:
    if hid:
        jest_id(db, hid)
    w = historia(db, hid, teraz - dt.timedelta(days=dni))
    for x in w:
        print(f"{termin_pl(x['kiedy'])}  {x['nazwa'] or x['id']}  {x['co']}: {x['opis']}")
    print(f"wpisów w {dni} dni: {len(w)}")
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
    md = [f"# Hackathony (stan na {lokalnie(teraz):%Y-%m-%d %H:%M}, czas {STREFA})", "",
          f"W bazie: {len(w)}; otwarte: {sum(x['status'] in OTWARTE for x in w)}. Pełna tabela: `hackatony.csv`.", "",
          "## Zgłoszenia w ciągu 30 dni", ""]
    md += [f"- **{termin_pl(x['zgloszenie_do'])}** ({zostalo(x['zgloszenie_do'], teraz)}): [{x['nazwa']}]({x['url']}), {pula(x)}, "
           f"{x['tryb'] or '?'}, AI: {x['ai_kod'] or '?'}, ocena {x['ocena'] if x['ocena'] is not None else '-'}" for x in term] or ["- brak"]
    top = sorted((x for x in w if x["status"] in OTWARTE and x["ocena"] is not None), key=lambda x: -x["ocena"])[:15]
    md += ["", "## Najlepsze dla floty", "", "| Hackathon | Platforma | Pula | Zgłoszenie do | Tryb | AI | Ocena | Dlaczego |",
           "|---|---|---|---|---|---|---|---|"]
    md += [f"| [{x['nazwa']}]({x['url']}) | {x['platforma']} | {pula(x)} | {termin_pl(x['zgloszenie_do'])} | {x['tryb'] or '?'} | "
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
    """Etapy otwartych hackathonów (zgłoszony: tylko wyniki), nasze kamienie przy zapisanych i budowanych oraz nasz
    następny krok (`krok_do`) przy każdym wpisie poza odpuszczonymi i zamkniętymi (wygrany: odbiór nagrody, KYC)."""
    out = []
    for r in db.execute("SELECT * FROM hackatony WHERE status NOT IN ('odpuszczony', 'zamkniety')"):
        x = dict(r)
        if x["status"] in ("nowy", "kandydat", "zapisani", "budujemy", "zgloszony"):
            for pole, nazwa, koniec in ETAPY:
                if x[pole] and (x["status"] != "zgloszony" or pole == "wyniki"):
                    out.append({"kiedy": chwila(x[pole], koniec), "etap": nazwa, "pole": pole, "dzien": len(x[pole]) == 10, "h": x})
        if x["status"] in ("zapisani", "budujemy") and x["zgloszenie_do"]:
            t = chwila(x["zgloszenie_do"], True)
            out += [{"kiedy": t - dt.timedelta(hours=8), "etap": "Zamrożenie projektu", "pole": "zamrozenie", "dzien": False, "h": x},
                    {"kiedy": t - dt.timedelta(hours=6), "etap": "Gotowe do wysłania", "pole": "gotowe", "dzien": False, "h": x}]
        if x["krok_do"]:
            out.append({"kiedy": chwila(x["krok_do"], True), "etap": f"Nasz krok: {x['krok'] or 'bez opisu'}", "pole": "krok",
                        "dzien": len(x["krok_do"]) == 10, "h": x})
    return sorted((e for e in out if od <= e["kiedy"] <= do), key=lambda e: (e["kiedy"], e["h"]["nazwa"]))


def lokalnie(t: dt.datetime) -> dt.datetime:
    from zoneinfo import ZoneInfo
    return t.replace(tzinfo=dt.timezone.utc).astimezone(ZoneInfo(STREFA))


def termin_pl(tekst: str | None) -> str:
    """Chwila z bazy (UTC) dla człowieka: data z godziną w strefie STREFA; sama data bez zmian, brak = „?”."""
    if not tekst:
        return "?"
    return tekst if len(tekst) == 10 else f"{lokalnie(dt.datetime.fromisoformat(tekst)):%Y-%m-%d %H:%M}"


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
          "Subskrypcja w telefonie: plik `hackatony.ics`."]
    md += miesiace(ev, teraz, "##")
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
        if e["pole"] in ("zgloszenie_do", "rejestracja_do", "gotowe", "krok"):
            ics += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_tekst(e['etap'])}", "TRIGGER:-P1D", "END:VALARM"]
        ics.append("END:VEVENT")
    ics.append("END:VCALENDAR")
    (katalog / "hackatony.ics").write_text("\r\n".join(z for l in ics for z in zwin(l)) + "\r\n", encoding="utf-8")
    return ev


def miesiace(ev: list[dict], teraz: dt.datetime, poziom: str) -> list[str]:
    """Wydarzenia w miesiącach (nagłówek `poziom`) i tygodniach (poziom niżej), czas właściciela."""
    md, miesiac, tydzien = [], None, None
    for e in ev:
        lok = lokalnie(e["kiedy"])
        if (lok.year, lok.month) != miesiac:
            miesiac, tydzien = (lok.year, lok.month), None
            md += ["", f"{poziom} {MIESIACE[lok.month - 1].capitalize()} {lok.year}"]
        if lok.isocalendar()[1] != tydzien:
            tydzien = lok.isocalendar()[1]
            pon = lok.date() - dt.timedelta(days=lok.weekday())
            md += ["", f"{poziom}# Tydzień {pon:%d.%m} do {pon + dt.timedelta(days=6):%d.%m}", ""]
        md.append(f"- {linia(e, teraz)}")
    return md


def cmd_kalendarz(db: sqlite3.Connection, katalog: Path, dni: int, teraz: dt.datetime) -> int:
    ev = zapisz_kalendarz(db, katalog, teraz, dni)
    print(json.dumps({"wydarzenia": len(ev), "pliki": [str(katalog / "KALENDARZ.md"), str(katalog / "hackatony.ics")]}))
    return 0


def wejscie(x: dict, teraz: dt.datetime) -> tuple[str, str] | None:
    """Najbliższy termin wejścia (rejestracja, inaczej zgłoszenie) jeszcze przed nami: (etap, termin); bez terminu
    (bounty bez końca) = ("bez terminu", ""); wszystko minęło = None."""
    for pole, etap in (("rejestracja_do", "rejestracja do"), ("zgloszenie_do", "zgłoszenie do")):
        if x[pole] and chwila(x[pole], True) >= teraz:
            return etap, x[pole]
    return None if x["rejestracja_do"] or x["zgloszenie_do"] else ("bez terminu", "")


def do_wziecia(db: sqlite3.Connection, teraz: dt.datetime, ile: int) -> tuple[list[str], int]:
    """Najlepsze hackathony, do których da się jeszcze wejść (ocena, potem termin; nowe z ostatniej doby oznaczone):
    (ponumerowane linie, ile otwartych)."""
    nowe = {r[0] for r in db.execute("SELECT id FROM historia WHERE co = 'dodany' AND kiedy >= ?",
                                     (f"{teraz - dt.timedelta(days=1):%Y-%m-%dT%H:%M}",))}
    w = [(x, wejscie(x, teraz)) for x in map(dict, db.execute("SELECT * FROM hackatony WHERE status IN ('nowy', 'kandydat')"))]
    w = sorted(((x, we) for x, we in w if we), key=lambda t: (-(t[0]["ocena"] if t[0]["ocena"] is not None else -1), t[1][1] or "9999"))
    linie = []
    for nr, (x, (etap, termin)) in enumerate(w[:ile], 1):
        kiedy = f"{etap} {termin_pl(termin)} ({zostalo(termin, teraz)})" if termin else etap
        linie.append(f"{nr}. [{x['nazwa']}]({x['url']}) · {pula(x)} · {kiedy} · ocena "
                     f"{x['ocena'] if x['ocena'] is not None else '?'}" + (f": {x['dlaczego']}" if x["dlaczego"] else "")
                     + (" · nowy" if x["id"] in nowe else ""))
    return linie, len(w)


def nasze_starty(db: sqlite3.Connection) -> list[dict]:
    w = [dict(r) for r in db.execute(f"SELECT * FROM hackatony WHERE status IN ({', '.join('?' * len(NASZE))})", NASZE)]
    return sorted(w, key=lambda x: NASZE.index(x["status"]))


def cmd_raport(db: sqlite3.Connection, katalog: Path | None, teraz: dt.datetime) -> int:
    """Raport dnia (25.11 właściciel: „ma raportować na temat hackathonów: jest jakiś dostępny, to działamy; potem
    tylko trackować, w którym bierzemy udział”): najlepsze do wzięcia i nasze starty z następnym krokiem. Nigdy pusty."""
    if katalog:
        zapisz_kalendarz(db, katalog, teraz)
    linie, otwarte = do_wziecia(db, teraz, 5)
    out = [f"Hackathony do wzięcia teraz (najlepsze z {otwarte} otwartych):"] + (linie or ["- brak otwartych w bazie: potrzebny radar"])
    out += ["Nasze starty:"] + ([f"- {udzial(x)}" for x in nasze_starty(db)] or ["- jeszcze żaden: wybierz numer z listy, wchodzimy"])
    if katalog:
        out.append(f"Kalendarz: {katalog / 'KALENDARZ.md'} (telefon: hackatony.ics), w Mózgu: kalendarz hackathonów")
    print("\n".join(out))
    return 0


# ------------------------------------------------------------------------------------------- Mózg
# 25.11 właściciel: „w Mózgu w sekcji Hacker notatka kalendarz i tam wszystko zapisywane”. Notatkę pisze ten skrypt po
# każdej zmianie bazy i w porannej rutynie (własny format skryptu jak briefy, SCHEMA zasada 9): status `generowane`,
# sekcje osobno w indeksie, więc przypomnienie przed turą trafia w „do wzięcia teraz” albo „nasze starty”.
NOTATKA_MOZGU = Path("agenci") / "jarvo-hacker" / "kalendarz hackathonów.md"
NASZE = ("budujemy", "zapisani", "zgloszony", "wygrany", "przegrany")


def skarbiec() -> Path | None:
    """Skarbiec Jarva (`JARVO_KNOWLEDGE_DIR`, inaczej `JARVO_DATA_DIR/knowledge`), gdy jest zasiany; poza instalacją
    (testy, kopia bazy) brak notatki."""
    dane = os.environ.get("JARVO_DATA_DIR")
    k = os.environ.get("JARVO_KNOWLEDGE_DIR") or (str(Path(dane) / "knowledge") if dane else "")
    return Path(k) if k and (Path(k) / "agenci").is_dir() else None


def udzial(x: dict) -> str:
    czesci = [f"[{x['nazwa']}]({x['url']})", f"**{x['status']}**", f"zgłoszenie {termin_pl(x['zgloszenie_do'])}"]
    if x["krok"] or x["krok_do"]:
        czesci.append(f"następny krok: {x['krok'] or '?'}" + (f" do {termin_pl(x['krok_do'])}" if x["krok_do"] else ""))
    czesci += [f"{p.replace('_', ' ')}: {x[p]}" for p in ("konto", "projekt", "zgloszenie_url", "demo_url", "nagroda") if x[p]]
    return " · ".join(czesci)


def zapisz_mozg(db: sqlite3.Connection, teraz: dt.datetime) -> Path | None:
    k = skarbiec()
    if k is None:
        return None
    p = k / NOTATKA_MOZGU
    stara = p.read_text(encoding="utf-8") if p.is_file() else ""
    utworzono = (re.search(r"^utworzono: (\S+)$", stara, re.M) or [None, teraz.date().isoformat()])[1]
    w = [dict(r) for r in db.execute("SELECT * FROM hackatony")]
    ev = wydarzenia(db, teraz - dt.timedelta(days=1), teraz + dt.timedelta(days=120))
    nasze = nasze_starty(db)
    linie, otwarte = do_wziecia(db, teraz, 10)
    hist = historia(db, None, teraz - dt.timedelta(days=30))[:40]
    md = ["---", "typ: fakt", "tagi: [hackathony, kalendarz, terminy]", f"utworzono: {utworzono}",
          f"zmieniono: {teraz.date().isoformat()}", "status: generowane", "zrodlo: workspaces/jarvo-hacker/baza/hackatony.db",
          "agent: jarvo-hacker", "sekcje: true", "---", "# Kalendarz hackathonów", "",
          f"**Hackathony, do których możemy wejść, nasze starty z następnym krokiem, terminy i historia zmian z bazy Hackera; "
          f"stan na {lokalnie(teraz):%d.%m.%Y %H:%M} ({STREFA}): w bazie {len(w)}, do wzięcia {otwarte}, nasze starty {len(nasze)}.**", "",
          "Notatkę pisze skrypt `hackatony.py` po każdej zmianie bazy i co rano; zmiany przez Hackera (`status`, `ustaw`, "
          "`notuj`), nie ręcznie. Czas w strefie właściciela, terminy w bazie w UTC.", "",
          "## Do wzięcia teraz", ""]
    md += linie or ["- brak otwartych w bazie"]
    md += ["", "## Nasze starty", ""] + ([f"- {udzial(x)}" for x in nasze] or ["- jeszcze żaden"])
    md += ["", "## Terminy na 120 dni"] + (miesiace(ev, teraz, "###") or ["", "- brak"])
    md += ["", "## Historia z 30 dni", ""]
    md += [f"- {lokalnie(dt.datetime.fromisoformat(h['kiedy'])):%d.%m %H:%M} · {h['nazwa'] or h['id']} · {h['co']}: {h['opis']}"
           for h in hist] or ["- brak zmian"]
    md += ["", "## Powiązane", "", "- hub: [[agenci/jarvo-hacker/_hub-hacker|Hacker]]",
           "- [[agenci/jarvo-hacker/jak działa hacker|Hacker od A do Z]]",
           "- [[agenci/jarvo-hacker/zasady pracy hacker|Zasady pracy: Hacker]]", "- [[orzeczenia/hacker|Orzeczenia: Hacker]]",
           "- [[agenci/jarvo-bigshort/kalendarz finansowania|Kalendarz finansowania (Bigshort)]]"]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("\n".join(md) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


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
    s = sub.add_parser("ustaw"); s.add_argument("id"); s.add_argument("pary", nargs="+")
    s = sub.add_parser("notuj"); s.add_argument("id"); s.add_argument("tekst")
    s = sub.add_parser("historia"); s.add_argument("id", nargs="?"); s.add_argument("--dni", type=int, default=30)
    s = sub.add_parser("stare"); s.add_argument("--dni", type=int, default=14)
    s = sub.add_parser("eksport"); s.add_argument("katalog")
    s = sub.add_parser("kalendarz"); s.add_argument("katalog"); s.add_argument("--dni", type=int, default=120)
    s = sub.add_parser("raport"); s.add_argument("--katalog")
    a = ap.parse_args(argv)
    db = polacz(Path(a.baza))
    try:
        if a.cmd == "lista":
            return cmd_lista(db, a)
        if a.cmd == "terminy":
            return cmd_terminy(db, a.dni, teraz)
        if a.cmd == "historia":
            return cmd_historia(db, a.id, a.dni, teraz)
        if a.cmd == "stare":
            return cmd_stare(db, a.dni, teraz.date())
        if a.cmd == "dodaj":
            wynik = cmd_dodaj(db, a.pliki, teraz)
        elif a.cmd == "ocen":
            wynik = cmd_ocen(db, a.id, a.ocena, a.dlaczego, teraz)
        elif a.cmd == "status":
            wynik = cmd_status(db, a.id, a.status, a.notatka, teraz)
        elif a.cmd == "ustaw":
            wynik = cmd_ustaw(db, a.id, a.pary, teraz)
        elif a.cmd == "notuj":
            wynik = cmd_notuj(db, a.id, a.tekst, teraz)
        elif a.cmd == "kalendarz":
            wynik = cmd_kalendarz(db, Path(a.katalog), a.dni, teraz)
        elif a.cmd == "raport":
            wynik = cmd_raport(db, Path(a.katalog) if a.katalog else None, teraz)
        else:
            wynik = cmd_eksport(db, Path(a.katalog), teraz)
        zapisz_mozg(db, teraz)          # każda zmiana i każde odświeżenie kalendarza = aktualna notatka w Mózgu
        return wynik
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

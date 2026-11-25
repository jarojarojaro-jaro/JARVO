#!/usr/bin/env python3
"""Baza okazji finansowania Bigshorta (SQLite): fundusze, aniołowie, akceleratory, granty, kredyty, konkursy, ulgi,
nasze aplikacje z etapami i historia każdej zmiany.

    okazje.py dodaj plik.jsonl [...]                 # dopisz albo uaktualnij (klucz: id, inaczej slug z nazwy)
    okazje.py lista [--typ T] [--status S] [--projekt P --min-ocena N] [--szukaj FRAZA] [--json]
    okazje.py terminy [--dni 30]                     # otwarte okazje z terminem w oknie, najbliższe pierwsze
    okazje.py ocen <id> <projekt> <0-10> "dlaczego"  # dopasowanie do projektu (np. jarvo, enigma-labz)
    okazje.py status <id> <status> ["notatka"]       # nowa|kandydat|aplikujemy|zlozone|odrzucone|wygrane|zamkniete|nie-pasuje
    okazje.py aplikuj <id> <projekt> [pole=wartość ...]   # nowa aplikacja (etap przygotowanie), okazja → aplikujemy
    okazje.py etap <aplikacja> <etap> ["notatka"]    # przygotowanie|zlozona|rozmowa|due-diligence|oferta|przyznana|odrzucona|wycofana
    okazje.py ustaw <aplikacja> pole=wartość [...]   # kwota, waluta, przyznano, zlozona, krok, krok_do, kontakt, dokumenty
    okazje.py aplikacje [--wszystkie]                # aplikacje w toku (z --wszystkie także zakończone)
    okazje.py notuj <id albo aplikacja> "co się stało"  # wpis do historii (mail, rozmowa, feedback, decyzja)
    okazje.py historia [<id>] [--dni 30]             # historia zmian, najnowsze pierwsze
    okazje.py stare [--dni 60]                       # wpisy do ponownego sprawdzenia (pole sprawdzone)
    okazje.py eksport <katalog>                      # OKAZJE.md (terminy, ranking projektów) + okazje.csv + kalendarz
    okazje.py kalendarz <katalog> [--dni 180]        # KALENDARZ.md + finansowanie.ics: terminy naborów i nasze kroki
    okazje.py przypomnij [--katalog K] [--tydzien]   # rutyna: co w 7 dniach (w poniedziałek 30 dni); nic = puste wyjście

Baza: --baza (domyślnie baza/okazje.db w katalogu roboczym). Wpis JSONL: nazwa, typ, url i zrodlo (link do źródła
pierwotnego) są obowiązkowe; sprawdzone = data sprawdzenia źródła (RRRR-MM-DD). termin: RRRR-MM-DD albo "rolling".
Kwoty liczbami w walucie z pola waluta; equity słownie ("0%", "7%", "SAFE uncapped"). Aplikacja = okazja i projekt
(id `<okazja>--<projekt>`), z etapem, kwotą, następnym krokiem i terminem. Każda zmiana bazy odświeża notatkę
„kalendarz finansowania” w Mózgu (skarbiec Jarva, `agenci/jarvo-bigshort/`). Skrypt niczego nie wysyła.
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

TYPY = ("vc", "aniol", "syndykat", "akcelerator", "fellowship", "grant", "kredyty", "konkurs", "ulga", "dlug",
        "crowdfunding", "pe", "bank", "inne")
STATUSY = ("nowa", "kandydat", "aplikujemy", "zlozone", "odrzucone", "wygrane", "zamkniete", "nie-pasuje")
OTWARTE = ("nowa", "kandydat", "aplikujemy")
POLA = ("id", "nazwa", "typ", "kwota_min", "kwota_max", "waluta", "equity", "dla_kogo", "region", "termin", "url",
        "zrodlo", "sprawdzone", "status", "notatki")
ETAPY = ("przygotowanie", "zlozona", "rozmowa", "due-diligence", "oferta", "przyznana", "odrzucona", "wycofana")
W_TOKU = ETAPY[:5]
STATUS_OKAZJI = {"zlozona": "zlozone", "rozmowa": "zlozone", "due-diligence": "zlozone", "oferta": "zlozone",
                 "przyznana": "wygrane", "odrzucona": "odrzucone"}     # etap aplikacji → status okazji
POLA_APLIKACJI = ("kwota", "waluta", "przyznano", "zlozona", "krok", "krok_do", "kontakt", "dokumenty")
SCHEMAT = """
CREATE TABLE IF NOT EXISTS okazje (
  id TEXT PRIMARY KEY, nazwa TEXT NOT NULL, typ TEXT NOT NULL, kwota_min REAL, kwota_max REAL, waluta TEXT,
  equity TEXT, dla_kogo TEXT, region TEXT, termin TEXT, url TEXT NOT NULL, zrodlo TEXT NOT NULL, sprawdzone TEXT,
  status TEXT NOT NULL DEFAULT 'nowa', notatki TEXT, dodane TEXT NOT NULL, zmienione TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oceny (
  id TEXT NOT NULL, projekt TEXT NOT NULL, ocena INTEGER NOT NULL, dlaczego TEXT NOT NULL, kiedy TEXT NOT NULL,
  PRIMARY KEY (id, projekt));
CREATE TABLE IF NOT EXISTS aplikacje (
  id TEXT PRIMARY KEY, okazja TEXT NOT NULL, projekt TEXT NOT NULL, etap TEXT NOT NULL, kwota REAL, waluta TEXT,
  przyznano REAL, zlozona TEXT, krok TEXT, krok_do TEXT, kontakt TEXT, dokumenty TEXT, dodane TEXT NOT NULL,
  zmienione TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS historia (nr INTEGER PRIMARY KEY AUTOINCREMENT, kiedy TEXT NOT NULL, id TEXT NOT NULL,
  co TEXT NOT NULL, opis TEXT NOT NULL);
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


def zapisz_historie(db: sqlite3.Connection, teraz: dt.datetime, oid: str, co: str, opis: str) -> None:
    db.execute("INSERT INTO historia (kiedy, id, co, opis) VALUES (?, ?, ?, ?)", (f"{teraz:%Y-%m-%dT%H:%M}", oid, co, opis))


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
            jest = db.execute("SELECT * FROM okazje WHERE id = ?", (w["id"],)).fetchone()
            if jest is None:
                w["status"] = w["status"] or "nowa"
                db.execute(f"INSERT INTO okazje ({', '.join(POLA)}, dodane, zmienione) VALUES "
                           f"({', '.join('?' * len(POLA))}, ?, ?)", (*[w[p] for p in POLA], dzis.isoformat(), dzis.isoformat()))
                zapisz_historie(db, teraz, w["id"], "dodana", f"{w['nazwa']} ({w['typ']}), status {w['status']}")
                nowe += 1
            else:                       # nowe dane uzupełniają wpis; status i notatki zmienia się osobno
                zm = {p: w[p] for p in POLA if p not in ("id", "status", "notatki") and w[p] is not None and w[p] != jest[p]}
                if zm:
                    db.execute(f"UPDATE okazje SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                               (*zm.values(), dzis.isoformat(), w["id"]))
                    zapisz_historie(db, teraz, w["id"], "dane", ", ".join(f"{p}: {jest[p] or '-'} → {v}" for p, v in zm.items()))
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
        q += (" AND (o.nazwa LIKE ? OR o.notatki LIKE ? OR o.dla_kogo LIKE ? OR o.id IN (SELECT h.id FROM historia h "
              "WHERE h.opis LIKE ?) OR o.id IN (SELECT okazja FROM aplikacje WHERE krok LIKE ?))"); arg += [f"%{a.szukaj}%"] * 5
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


def jest_okazja(db: sqlite3.Connection, oid: str) -> sqlite3.Row:
    r = db.execute("SELECT * FROM okazje WHERE id = ?", (oid,)).fetchone()
    if r is None:
        raise SystemExit(f"nie ma okazji {oid}")
    return r


def cmd_ocen(db: sqlite3.Connection, oid: str, projekt: str, ocena: int, dlaczego: str, teraz: dt.datetime) -> int:
    jest_okazja(db, oid)
    if not 0 <= ocena <= 10 or not dlaczego.strip():
        raise SystemExit("ocena 0–10 i powód są obowiązkowe")
    db.execute("INSERT OR REPLACE INTO oceny VALUES (?, ?, ?, ?, ?)", (oid, slug(projekt), ocena, dlaczego.strip(), teraz.date().isoformat()))
    zapisz_historie(db, teraz, oid, "ocena", f"{slug(projekt)} {ocena}/10: {dlaczego.strip()}")
    db.commit()
    return 0


def zmien_status(db: sqlite3.Connection, oid: str, status: str, notatka: str, teraz: dt.datetime) -> None:
    byl = jest_okazja(db, oid)["status"]
    if byl == status and not notatka:
        return
    db.execute("UPDATE okazje SET status = ?, zmienione = ? WHERE id = ?", (status, teraz.date().isoformat(), oid))
    zapisz_historie(db, teraz, oid, "status", f"{byl} → {status}" + (f": {notatka}" if notatka else ""))


def cmd_status(db: sqlite3.Connection, oid: str, status: str, notatka: str, teraz: dt.datetime) -> int:
    if status not in STATUSY:
        raise SystemExit(f"status spoza {', '.join(STATUSY)}")
    zmien_status(db, oid, status, notatka.strip(), teraz)
    db.commit()
    return 0


# ------------------------------------------------------------------------------------------- aplikacje
# 25.11 właściciel: „trackujemy, gdzie będziemy aplikować, i w ogóle wszystko”. Aplikacja = okazja × projekt, z etapem,
# kwotą, następnym krokiem i terminem; każda zmiana trafia do historii, etap przesuwa status okazji.
def jest_aplikacja(db: sqlite3.Connection, aid: str) -> sqlite3.Row:
    r = db.execute("SELECT * FROM aplikacje WHERE id = ?", (aid,)).fetchone()
    if r is None:
        raise SystemExit(f"nie ma aplikacji {aid} (id: <okazja>--<projekt>, lista: okazje.py aplikacje)")
    return r


def pola_aplikacji(pary: list[str]) -> dict:
    zm = {}
    for para in pary:
        pole, znak, wartosc = para.partition("=")
        if not znak or pole not in POLA_APLIKACJI:
            raise SystemExit(f"„{para}”: podaj pole=wartość, pole z {', '.join(POLA_APLIKACJI)}")
        wartosc = wartosc.strip()
        if pole in ("kwota", "przyznano") and wartosc:
            try:
                zm[pole] = float(wartosc.replace(" ", "").replace(",", "."))
            except ValueError:
                raise SystemExit(f"{pole}: „{wartosc}” to nie liczba")
        elif pole in ("zlozona", "krok_do"):
            zm[pole] = data(wartosc, pole)
        else:
            zm[pole] = wartosc or None
    return zm


def opis_zmian(zm: dict) -> str:
    return ", ".join(f"{p}: {v if v is not None else '(puste)'}" for p, v in zm.items())


def cmd_aplikuj(db: sqlite3.Connection, oid: str, projekt: str, pary: list[str], teraz: dt.datetime) -> int:
    o = jest_okazja(db, oid)
    aid = f"{oid}--{slug(projekt)}"
    if db.execute("SELECT 1 FROM aplikacje WHERE id = ?", (aid,)).fetchone():
        raise SystemExit(f"aplikacja {aid} już jest: zmiany przez `etap` i `ustaw`")
    extra = pola_aplikacji(pary)
    zm = {"waluta": o["waluta"], **extra}
    dzis = teraz.date().isoformat()
    db.execute(f"INSERT INTO aplikacje (id, okazja, projekt, etap, {', '.join(zm)}, dodane, zmienione) VALUES "
               f"(?, ?, ?, 'przygotowanie', {', '.join('?' * len(zm))}, ?, ?)", (aid, oid, slug(projekt), *zm.values(), dzis, dzis))
    zapisz_historie(db, teraz, aid, "aplikacja", f"start: {o['nazwa']} dla {slug(projekt)}" + (f", {opis_zmian(extra)}" if extra else ""))
    if o["status"] in ("nowa", "kandydat"):
        zmien_status(db, oid, "aplikujemy", "", teraz)
    db.commit()
    print(json.dumps({"aplikacja": aid}))
    return 0


def cmd_etap(db: sqlite3.Connection, aid: str, etap: str, notatka: str, teraz: dt.datetime) -> int:
    if etap not in ETAPY:
        raise SystemExit(f"etap spoza {', '.join(ETAPY)}")
    a = jest_aplikacja(db, aid)
    zlozona = a["zlozona"] or (teraz.date().isoformat() if etap == "zlozona" else None)
    db.execute("UPDATE aplikacje SET etap = ?, zlozona = ?, zmienione = ? WHERE id = ?", (etap, zlozona, teraz.date().isoformat(), aid))
    zapisz_historie(db, teraz, aid, "etap", f"{a['etap']} → {etap}" + (f": {notatka.strip()}" if notatka.strip() else ""))
    if etap in STATUS_OKAZJI:
        zmien_status(db, a["okazja"], STATUS_OKAZJI[etap], "", teraz)
    db.commit()
    return 0


def cmd_ustaw(db: sqlite3.Connection, aid: str, pary: list[str], teraz: dt.datetime) -> int:
    a = jest_aplikacja(db, aid)
    zm = {p: v for p, v in pola_aplikacji(pary).items() if v != a[p]}
    if zm:
        db.execute(f"UPDATE aplikacje SET {', '.join(f'{p} = ?' for p in zm)}, zmienione = ? WHERE id = ?",
                   (*zm.values(), teraz.date().isoformat(), aid))
        zapisz_historie(db, teraz, aid, "aplikacja", opis_zmian(zm))
        db.commit()
    return 0


def aplikacje(db: sqlite3.Connection, wszystkie: bool = True) -> list[dict]:
    q = "SELECT a.*, o.nazwa, o.url, o.termin FROM aplikacje a JOIN okazje o ON o.id = a.okazja"
    if not wszystkie:
        q += f" WHERE a.etap IN ({', '.join('?' * len(W_TOKU))})"
    return [dict(r) for r in db.execute(q + " ORDER BY a.krok_do IS NULL, a.krok_do, o.nazwa", () if wszystkie else W_TOKU)]


def opis_aplikacji(x: dict) -> str:
    czesci = [f"[{x['nazwa']}]({x['url']})", x["projekt"], f"**{x['etap']}**"]
    if x["kwota"] is not None:
        czesci.append(f"wnioskujemy {kwota({'kwota_max': x['kwota'], 'waluta': x['waluta']})}")
    if x["przyznano"] is not None:
        czesci.append(f"przyznano {kwota({'kwota_max': x['przyznano'], 'waluta': x['waluta']})}")
    if x["zlozona"]:
        czesci.append(f"złożona {x['zlozona']}")
    if x["krok"] or x["krok_do"]:
        czesci.append(f"następny krok: {x['krok'] or '?'}" + (f" do {x['krok_do']}" if x["krok_do"] else ""))
    if x["termin"] and x["etap"] == "przygotowanie":
        czesci.append(f"termin naboru {x['termin']}")
    if x["dokumenty"]:
        czesci.append(f"dokumenty: {x['dokumenty']}")
    return " · ".join(czesci)


def cmd_aplikacje(db: sqlite3.Connection, wszystkie: bool) -> int:
    w = aplikacje(db, wszystkie)
    for x in w:
        print(f"{x['id']:<50} {opis_aplikacji(x)}")
    print(f"aplikacji: {len(w)}")
    return 0


def cmd_notuj(db: sqlite3.Connection, xid: str, tekst: str, teraz: dt.datetime) -> int:
    if not db.execute("SELECT 1 FROM okazje WHERE id = ? UNION SELECT 1 FROM aplikacje WHERE id = ?", (xid, xid)).fetchone():
        raise SystemExit(f"nie ma okazji ani aplikacji {xid}")
    if not tekst.strip():
        raise SystemExit("pusta notatka")
    zapisz_historie(db, teraz, xid, "notatka", tekst.strip())
    db.commit()
    return 0


def historia(db: sqlite3.Connection, xid: str | None, od: dt.datetime) -> list[dict]:
    q = ("SELECT h.*, coalesce(o.nazwa, o2.nazwa || ' (' || a.projekt || ')', h.id) AS nazwa FROM historia h "
         "LEFT JOIN okazje o ON o.id = h.id LEFT JOIN aplikacje a ON a.id = h.id LEFT JOIN okazje o2 ON o2.id = a.okazja "
         "WHERE h.kiedy >= ?")
    arg = [f"{od:%Y-%m-%dT%H:%M}"]
    if xid:
        q += " AND (h.id = ? OR h.id IN (SELECT id FROM aplikacje WHERE okazja = ?))"; arg += [xid, xid]
    return [dict(r) for r in db.execute(q + " ORDER BY h.nr DESC", arg)]


def cmd_historia(db: sqlite3.Connection, xid: str | None, dni: int, teraz: dt.datetime) -> int:
    w = historia(db, xid, teraz - dt.timedelta(days=dni))
    for x in w:
        print(f"{x['kiedy']} UTC  {x['nazwa']}  {x['co']}: {x['opis']}")
    print(f"wpisów w {dni} dni: {len(w)}")
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
    zapisz_kalendarz(db, katalog, dzis)
    print(json.dumps({"okazje": len(w), "terminy_45_dni": len(term), "pliki": [str(katalog / p) for p in
                      ("OKAZJE.md", "okazje.csv", "KALENDARZ.md", "finansowanie.ics")]}))
    return 0


# ------------------------------------------------------------------------------------------- kalendarz
# 25.11 właściciel: kalendarz jak u Hackera. Terminy naborów otwartych okazji i nasze kroki w aplikacjach w toku; same
# daty (bez godzin), więc wydarzenia całodniowe; przypomnienie 7 dni wcześniej, bo wniosek pisze się dłużej niż projekt.
MIESIACE = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik",
            "listopad", "grudzień")
DNI = ("pn", "wt", "śr", "cz", "pt", "sb", "nd")


def wydarzenia(db: sqlite3.Connection, od: dt.date, do: dt.date) -> list[dict]:
    out = []
    for r in db.execute(f"SELECT * FROM okazje WHERE status IN ({', '.join('?' * len(OTWARTE))}) AND termin IS NOT NULL "
                        "AND termin != 'rolling'", OTWARTE):
        out.append({"kiedy": dt.date.fromisoformat(r["termin"]), "etap": "Termin naboru", "uid": f"{r['id']}-termin",
                    "nazwa": r["nazwa"], "url": r["url"], "info": f"{kwota(dict(r))} · equity {r['equity'] or '?'} · {r['status']}"})
    for x in aplikacje(db, wszystkie=False):
        if x["krok_do"]:
            out.append({"kiedy": dt.date.fromisoformat(x["krok_do"]), "etap": f"Nasz krok: {x['krok'] or 'bez opisu'}",
                        "uid": f"{x['id']}-krok", "nazwa": f"{x['nazwa']} ({x['projekt']})", "url": x["url"], "info": x["etap"]})
    return sorted((e for e in out if od <= e["kiedy"] <= do), key=lambda e: (e["kiedy"], e["nazwa"]))


def zostalo(d: dt.date, dzis: dt.date) -> str:
    n = (d - dzis).days
    return "minęło" if n < 0 else "dziś" if n == 0 else "jutro" if n == 1 else f"{n} dni"


def linia(e: dict, dzis: dt.date) -> str:
    d = e["kiedy"]
    return f"**{DNI[d.weekday()]} {d:%d.%m}** ({zostalo(d, dzis)}) · {e['etap']} · [{e['nazwa']}]({e['url']}) · {e['info']}"


def miesiace(ev: list[dict], dzis: dt.date, poziom: str) -> list[str]:
    md, miesiac = [], None
    for e in ev:
        if (e["kiedy"].year, e["kiedy"].month) != miesiac:
            miesiac = (e["kiedy"].year, e["kiedy"].month)
            md += ["", f"{poziom} {MIESIACE[e['kiedy'].month - 1].capitalize()} {e['kiedy'].year}", ""]
        md.append(f"- {linia(e, dzis)}")
    return md


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


def zapisz_kalendarz(db: sqlite3.Connection, katalog: Path, dzis: dt.date, dni: int = 180) -> list[dict]:
    katalog.mkdir(parents=True, exist_ok=True)
    ev = wydarzenia(db, dzis, dzis + dt.timedelta(days=dni))
    pilne = [e for e in ev if e["kiedy"] <= dzis + dt.timedelta(days=7)]
    md = [f"# Kalendarz finansowania (stan na {dzis:%d.%m.%Y})", "",
          "Terminy naborów otwartych okazji i nasze kroki w aplikacjach w toku. Subskrypcja w telefonie: plik "
          "`finansowanie.ics`.", "", "## W ciągu 7 dni", ""]
    md += [f"- {linia(e, dzis)}" for e in pilne] or ["- nic"]
    md += miesiace(ev, dzis, "##")
    (katalog / "KALENDARZ.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jarvo//Bigshort//PL", "CALSCALE:GREGORIAN",
           "X-WR-CALNAME:Finansowanie (Jarvo)"]
    for e in ev:
        d = e["kiedy"]
        ics += ["BEGIN:VEVENT", f"UID:{e['uid']}@jarvo-bigshort", f"DTSTAMP:{dzis:%Y%m%d}T000000Z",
                f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}",
                f"SUMMARY:{ics_tekst(e['etap'] + ': ' + e['nazwa'])}", f"DESCRIPTION:{ics_tekst(e['info'] + chr(10) + e['url'])}",
                f"URL:{e['url']}", "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_tekst(e['etap'])}", "TRIGGER:-P7D",
                "END:VALARM", "END:VEVENT"]
    ics.append("END:VCALENDAR")
    (katalog / "finansowanie.ics").write_text("\r\n".join(z for l in ics for z in zwin(l)) + "\r\n", encoding="utf-8")
    return ev


def cmd_kalendarz(db: sqlite3.Connection, katalog: Path, dni: int, dzis: dt.date) -> int:
    ev = zapisz_kalendarz(db, katalog, dzis, dni)
    print(json.dumps({"wydarzenia": len(ev), "pliki": [str(katalog / "KALENDARZ.md"), str(katalog / "finansowanie.ics")]}))
    return 0


def cmd_przypomnij(db: sqlite3.Connection, katalog: Path | None, tydzien: bool, dzis: dt.date) -> int:
    """Rutyna bez modelu: odświeża kalendarz i wypisuje tylko to, co wymaga uwagi; puste wyjście = cisza."""
    if katalog:
        zapisz_kalendarz(db, katalog, dzis)
    pilne = wydarzenia(db, dzis, dzis + dt.timedelta(days=7))
    dalsze = wydarzenia(db, dzis + dt.timedelta(days=8), dzis + dt.timedelta(days=30)) if tydzien or dzis.weekday() == 0 else []
    if not pilne and not dalsze:
        return 0
    out = []
    if pilne:
        out += ["Finansowanie: w ciągu 7 dni"] + [f"- {linia(e, dzis)}" for e in pilne]
    if dalsze:
        out += ["Finansowanie: dalsze 30 dni"] + [f"- {linia(e, dzis)}" for e in dalsze]
    if katalog:
        out.append(f"Cały kalendarz: {katalog / 'KALENDARZ.md'} (subskrypcja: finansowanie.ics)")
    print("\n".join(out))
    return 0


# ------------------------------------------------------------------------------------------- Mózg
# 25.11 właściciel: w Mózgu, w sekcji agenta, notatka z kalendarzem i wszystkim, co śledzimy. Pisze ją ten skrypt po
# każdej zmianie bazy i w porannej rutynie (własny format skryptu jak briefy, SCHEMA zasada 9). Kontakty zostają w bazie
# (SCHEMA zasada 11), notatka ich nie pokazuje.
NOTATKA_MOZGU = Path("agenci") / "jarvo-bigshort" / "kalendarz finansowania.md"


def skarbiec() -> Path | None:
    """Skarbiec Jarva (`JARVO_KNOWLEDGE_DIR`, inaczej `JARVO_DATA_DIR/knowledge`), gdy jest zasiany; poza instalacją
    (testy, kopia bazy) brak notatki."""
    dane = os.environ.get("JARVO_DATA_DIR")
    k = os.environ.get("JARVO_KNOWLEDGE_DIR") or (str(Path(dane) / "knowledge") if dane else "")
    return Path(k) if k and (Path(k) / "agenci").is_dir() else None


def zapisz_mozg(db: sqlite3.Connection, teraz: dt.datetime) -> Path | None:
    k = skarbiec()
    if k is None:
        return None
    p, dzis = k / NOTATKA_MOZGU, teraz.date()
    stara = p.read_text(encoding="utf-8") if p.is_file() else ""
    utworzono = (re.search(r"^utworzono: (\S+)$", stara, re.M) or [None, dzis.isoformat()])[1]
    w = wiersze(db, argparse.Namespace())
    ap = aplikacje(db)
    w_toku = [x for x in ap if x["etap"] in W_TOKU]
    ev = wydarzenia(db, dzis, dzis + dt.timedelta(days=180))
    top = sorted(((max(o["ocena"] for o in x["oceny"].values()), x) for x in w if x["status"] in OTWARTE and x["oceny"]),
                 key=lambda t: -t[0])[:10]
    hist = historia(db, None, teraz - dt.timedelta(days=30))[:40]
    md = ["---", "typ: fakt", "tagi: [finansowanie, kalendarz, aplikacje]", f"utworzono: {utworzono}",
          f"zmieniono: {dzis.isoformat()}", "status: generowane", "zrodlo: workspaces/jarvo-bigshort/baza/okazje.db",
          "agent: jarvo-bigshort", "sekcje: true", "---", "# Kalendarz finansowania", "",
          f"**Nasze aplikacje o finansowanie z etapem i następnym krokiem, terminy naborów i historia zmian z bazy Bigshorta; "
          f"stan na {dzis:%d.%m.%Y}: okazji {len(w)}, otwartych {sum(x['status'] in OTWARTE for x in w)}, aplikacji w toku "
          f"{len(w_toku)}.**", "",
          "Notatkę pisze skrypt `okazje.py` po każdej zmianie bazy i co rano; zmiany przez Bigshorta (`aplikuj`, `etap`, "
          "`ustaw`, `notuj`), nie ręcznie.", "", "## W ciągu 7 dni", ""]
    md += [f"- {linia(e, dzis)}" for e in ev if e["kiedy"] <= dzis + dt.timedelta(days=7)] or ["- nic"]
    md += ["", "## Nasze aplikacje w toku", ""] + ([f"- {opis_aplikacji(x)}" for x in w_toku] or ["- jeszcze żadna"])
    md += ["", "## Terminy naborów na 180 dni"] + (miesiace(ev, dzis, "###") or ["", "- brak"])
    md += ["", "## Zakończone aplikacje", ""] + ([f"- {opis_aplikacji(x)}" for x in ap if x["etap"] not in W_TOKU] or ["- brak"])
    md += ["", "## Najlepsze otwarte okazje", ""]
    md += [f"- [{x['nazwa']}]({x['url']}) · {x['typ']} · {kwota(x)} · equity {x['equity'] or '?'} · termin {x['termin'] or '?'} · "
           + ", ".join(f"{p} {o['ocena']}" for p, o in sorted(x["oceny"].items())) for _, x in top] or ["- brak ocenionych"]
    md += ["", "## Historia z 30 dni", ""]
    md += [f"- {h['kiedy'][8:10]}.{h['kiedy'][5:7]} {h['kiedy'][11:]} UTC · {h['nazwa']} · {h['co']}: {bez_kontaktu(h['opis'])}"
           for h in hist] or ["- brak zmian"]
    md += ["", "## Powiązane", "", "- hub: [[agenci/jarvo-bigshort/_hub-bigshort|Bigshort]]",
           "- [[agenci/jarvo-bigshort/jak działa bigshort|Bigshort od A do Z]]",
           "- [[agenci/jarvo-bigshort/zasady pracy bigshort|Zasady pracy: Bigshort]]", "- [[orzeczenia/bigshort|Orzeczenia: Bigshort]]",
           "- [[agenci/jarvo-hacker/kalendarz hackathonów|Kalendarz hackathonów (Hacker)]]"]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("\n".join(md) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def bez_kontaktu(opis: str) -> str:
    """Wpis historii do Mózgu bez danych kontaktu (zostają w bazie): `kontakt: …` do następnego pola aplikacji."""
    nastepne = "|".join(p for p in POLA_APLIKACJI if p != "kontakt")
    return re.sub(rf"kontakt: .*?(?=, (?:{nastepne}): |$)", "kontakt w bazie", opis)


def domyslna_baza() -> str:
    """Katalog roboczy Bigshorta w danych Jarva (JARVO_DATA_DIR), niezależnie od katalogu, w którym stoi terminal
    (25.11: Hacker z tury w panelu zapisał swoją bazę w katalogu profilu zamiast w katalogu roboczym)."""
    dane = os.environ.get("JARVO_DATA_DIR")
    return str(Path(dane) / "workspaces" / "jarvo-bigshort" / "baza" / "okazje.db") if dane else "baza/okazje.db"


def main(argv: list[str] | None = None, dzis: dt.date | None = None, teraz: dt.datetime | None = None) -> int:
    teraz = teraz or (dt.datetime.combine(dzis, dt.time(12)) if dzis else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))
    dzis = teraz.date()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baza", default=domyslna_baza())
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dodaj"); s.add_argument("pliki", nargs="+")
    s = sub.add_parser("lista")
    s.add_argument("--typ", choices=TYPY); s.add_argument("--status", choices=STATUSY); s.add_argument("--szukaj")
    s.add_argument("--projekt"); s.add_argument("--min-ocena", type=int, default=0); s.add_argument("--json", action="store_true")
    s = sub.add_parser("terminy"); s.add_argument("--dni", type=int, default=30)
    s = sub.add_parser("ocen"); s.add_argument("id"); s.add_argument("projekt"); s.add_argument("ocena", type=int); s.add_argument("dlaczego")
    s = sub.add_parser("status"); s.add_argument("id"); s.add_argument("status"); s.add_argument("notatka", nargs="?", default="")
    s = sub.add_parser("aplikuj"); s.add_argument("id"); s.add_argument("projekt"); s.add_argument("pary", nargs="*")
    s = sub.add_parser("etap"); s.add_argument("id"); s.add_argument("etap"); s.add_argument("notatka", nargs="?", default="")
    s = sub.add_parser("ustaw"); s.add_argument("id"); s.add_argument("pary", nargs="+")
    s = sub.add_parser("aplikacje"); s.add_argument("--wszystkie", action="store_true")
    s = sub.add_parser("notuj"); s.add_argument("id"); s.add_argument("tekst")
    s = sub.add_parser("historia"); s.add_argument("id", nargs="?"); s.add_argument("--dni", type=int, default=30)
    s = sub.add_parser("stare"); s.add_argument("--dni", type=int, default=60)
    s = sub.add_parser("eksport"); s.add_argument("katalog")
    s = sub.add_parser("kalendarz"); s.add_argument("katalog"); s.add_argument("--dni", type=int, default=180)
    s = sub.add_parser("przypomnij"); s.add_argument("--katalog"); s.add_argument("--tydzien", action="store_true")
    a = ap.parse_args(argv)
    db = polacz(Path(a.baza))
    try:
        if a.cmd == "lista":
            if a.projekt:
                a.projekt = slug(a.projekt)
            return cmd_lista(db, a)
        if a.cmd == "terminy":
            return cmd_terminy(db, a.dni, dzis)
        if a.cmd == "aplikacje":
            return cmd_aplikacje(db, a.wszystkie)
        if a.cmd == "historia":
            return cmd_historia(db, a.id, a.dni, teraz)
        if a.cmd == "stare":
            return cmd_stare(db, a.dni, dzis)
        if a.cmd == "dodaj":
            wynik = cmd_dodaj(db, a.pliki, teraz)
        elif a.cmd == "ocen":
            wynik = cmd_ocen(db, a.id, a.projekt, a.ocena, a.dlaczego, teraz)
        elif a.cmd == "status":
            wynik = cmd_status(db, a.id, a.status, a.notatka, teraz)
        elif a.cmd == "aplikuj":
            wynik = cmd_aplikuj(db, a.id, a.projekt, a.pary, teraz)
        elif a.cmd == "etap":
            wynik = cmd_etap(db, a.id, a.etap, a.notatka, teraz)
        elif a.cmd == "ustaw":
            wynik = cmd_ustaw(db, a.id, a.pary, teraz)
        elif a.cmd == "notuj":
            wynik = cmd_notuj(db, a.id, a.tekst, teraz)
        elif a.cmd == "kalendarz":
            wynik = cmd_kalendarz(db, Path(a.katalog), a.dni, dzis)
        elif a.cmd == "przypomnij":
            wynik = cmd_przypomnij(db, Path(a.katalog) if a.katalog else None, a.tydzien, dzis)
        else:
            wynik = cmd_eksport(db, Path(a.katalog), dzis)
        zapisz_mozg(db, teraz)          # każda zmiana i każde odświeżenie kalendarza = aktualna notatka w Mózgu
        return wynik
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Lista leadów Łowcy: scalanie sygnałów, kontakty ze stron, ocena według ICP, ranking i raport, monitoring nowych.

    leady.py dodaj <projekt> sygnaly.jsonl [...]         # dopisz sygnały (bez duplikatów: firma + typ + źródło)
    leady.py kontakt <projekt> strona.json [...]          # dołącz kontakty z `strona.py kontakt --json` (po NIP albo domenie)
    leady.py powod <projekt> <klucz> "dlaczego teraz"     # powód słowami użytkownika zamiast opisu sygnału
    leady.py ocen <projekt> [--top 30] [--monitoring]     # leady.csv + LEADY.md; --monitoring: tylko nowe względem baza.json

<projekt> = katalog z ICP.yaml (np. out/leady/nova-www). Ocena: najpierw dopasowanie do ICP (brak = brak wiersza),
potem świeżość (waga sygnału maleje liniowo do zera w oknie dni), potem siła (dwa różne typy sygnałów > jeden).
Kontakty tylko opublikowane przez firmę albo rejestr, każdy ze źródłem; skrypt niczego nie wysyła.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowca_lib as ll  # noqa: E402

DOMYSLNE_SYGNALY = {  # typ → waga (0–3), okno świeżości w dniach
    "krs-nowa-firma": (2, 30), "krs-wpis": (1, 14), "przetarg-ogloszenie": (3, 14), "przetarg-wygrany": (2, 30),
    "przetarg-ted": (2, 30), "rekrutacja": (2, 30), "strona-technologia": (1, 90), "strona-kariera": (1, 60),
    "strona-zmiana": (1, 30), "news": (1, 30), "finansowanie": (2, 60), "reklamy": (1, 30), "inne": (1, 30),
}
PRZYPOMNIENIE = ("Zanim ktokolwiek napisze do tych firm: informacja handlowa mailem albo telefonicznie do konkretnej osoby "
                 "co do zasady wymaga jej wcześniejszej zgody (UŚUDE, Prawo komunikacji elektronicznej), także w B2B; adres "
                 "opublikowany na stronie to nie zgoda. Przed kampanią: podstawa prawna, lista wypisanych, informacja o źródle "
                 "danych (RODO art. 14). Lista jest do Twojej decyzji; nic nie zostało wysłane.")
POLA = ["klucz", "nazwa", "nip", "krs", "woj", "miejscowosc", "www", "ocena", "dopasowanie", "sygnaly", "dlaczego_teraz",
        "zrodla", "email", "email_rodzaj", "email_zrodlo", "telefon", "formularz", "nowy", "pierwszy_raz"]


ETYKIETY = [("api-krs.ms.gov.pl", "KRS"), ("ezamowienia.gov.pl", "BZP"), ("ted.europa.eu", "TED")]


def etykieta(url: str) -> str:
    return next((e for d, e in ETYKIETY if d in url), "źródło")


def wczytaj_icp(projekt: Path) -> dict:
    p = projekt / "ICP.yaml"
    if not p.is_file():
        raise SystemExit(f"brak {p}: najpierw skill profil-klienta")
    import yaml

    icp = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    icp.setdefault("dopasowanie", {})
    sy = {k: tuple(v) for k, v in DOMYSLNE_SYGNALY.items()}
    for typ, v in (icp.get("sygnaly") or {}).items():
        sy[typ] = (float(v.get("waga", 1)), int(v.get("okno", 30)))
    icp["_sygnaly"] = sy
    return icp


def klucz(firma: dict) -> str:
    if n := ll.nip(firma.get("nip") or ""):
        return f"nip:{n}"
    if firma.get("krs"):
        return f"krs:{int(firma['krs'])}"
    if firma.get("www"):
        return f"www:{ll.domena(firma['www'])}"
    return "nazwa:" + re.sub(r"[^a-z0-9ąćęłńóśźż]+", "-", (firma.get("nazwa") or "?").lower()).strip("-")[:60]


def cmd_dodaj(projekt: Path, pliki: list[str]) -> int:
    cel = projekt / "sygnaly.jsonl"
    znane = {(s["_klucz"], s["typ"], s.get("zrodlo")) for s in ll.czytaj_jsonl(str(cel))}
    nowe = []
    for plik in pliki:
        for s in ll.czytaj_jsonl(plik):
            if not s.get("typ") or not s.get("firma"):
                print(f"! pominięty wiersz bez typu albo firmy w {plik}", file=sys.stderr)
                continue
            s["_klucz"] = klucz(s["firma"])
            k = (s["_klucz"], s["typ"], s.get("zrodlo"))
            if k not in znane:
                znane.add(k)
                nowe.append(s)
    ll.zapisz_jsonl(nowe, str(cel))
    print(f"✓ {cel}: +{len(nowe)} sygnałów")
    return 0


def cmd_kontakt(projekt: Path, pliki: list[str]) -> int:
    cel = projekt / "kontakty.json"
    baza = json.loads(cel.read_text(encoding="utf-8")) if cel.is_file() else {}
    for plik in pliki:
        w = json.loads(Path(plik).read_text(encoding="utf-8"))
        wpis = {k: w.get(k) for k in ("domena", "url", "emaile", "telefony", "formularz", "kariera", "technologie", "nip", "social", "odcisk")}
        baza[f"www:{w['domena']}"] = wpis
        for n in w.get("nip") or []:
            baza[f"nip:{n}"] = wpis
    projekt.mkdir(parents=True, exist_ok=True)
    cel.write_text(json.dumps(baza, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {cel}: {len(baza)} kluczy z kontaktami")
    return 0


def cmd_powod(projekt: Path, k: str, tekst: str) -> int:
    cel = projekt / "powody.json"
    baza = json.loads(cel.read_text(encoding="utf-8")) if cel.is_file() else {}
    baza[k] = tekst.strip()
    cel.write_text(json.dumps(baza, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ powód dla {k}")
    return 0


def dopasowanie(firma: dict, sygnaly: list[dict], icp: dict) -> float | None:
    """0–1 (część kryteriów ICP, które firma spełnia); None = wykluczona."""
    d = icp["dopasowanie"]
    tekst = " ".join([firma.get("nazwa") or ""] + [s.get("opis") or "" for s in sygnaly] +
                     [(s.get("szczegoly") or {}).get("przedmiot") or "" for s in sygnaly]).lower()
    forma = " ".join(str((s.get("szczegoly") or {}).get("forma") or "") for s in sygnaly).upper()
    if any(w.lower() in tekst for w in d.get("wyklucz_slowa") or []) or any(f.upper() in forma for f in d.get("wyklucz_formy") or []):
        return None
    kryteria = []
    if d.get("pkd"):
        kody = [firma.get("pkd") or ""]
        kryteria.append(any(k.replace(".", "").startswith(str(p).replace(".", "")) for k in kody for p in d["pkd"]))
    if d.get("woj"):
        woj = [ll.WOJ.get(str(w).upper(), str(w).upper()) for w in d["woj"]]
        kryteria.append((firma.get("woj") or "").upper() in woj)
    if d.get("cpv"):
        cpv = [c for s in sygnaly for c in ((s.get("szczegoly") or {}).get("cpv") or [])]
        kryteria.append(any(str(c).startswith(str(p)) for c in cpv for p in d["cpv"]))
    if d.get("slowa"):
        kryteria.append(any(w.lower() in tekst for w in d["slowa"]))
    return sum(kryteria) / len(kryteria) if kryteria else 1.0


def swiezosc(s: dict, icp: dict, dzis: dt.date) -> float:
    waga, okno = icp["_sygnaly"].get(s["typ"], icp["_sygnaly"]["inne"])
    try:
        wiek = (dzis - dt.date.fromisoformat(str(s.get("data"))[:10])).days
    except ValueError:
        wiek = okno
    return waga * max(0.0, 1 - max(0, wiek) / max(1, okno))


def ocen_firmy(sygnaly: list[dict], kontakty: dict, powody: dict, icp: dict, dzis: dt.date) -> list[dict]:
    grupy: dict[str, list[dict]] = {}
    for s in sygnaly:
        grupy.setdefault(s["_klucz"], []).append(s)
    prog = float(icp["dopasowanie"].get("prog", 0.5))
    out = []
    for k, ss in grupy.items():
        firma = {}
        for s in ss:                                             # najpełniejsze dane firmy z wszystkich sygnałów
            firma.update({a: b for a, b in (s.get("firma") or {}).items() if b})
        fit = dopasowanie(firma, ss, icp)
        if fit is None or fit < prog:
            continue
        per_typ: dict[str, float] = {}
        for s in ss:
            per_typ[s["typ"]] = max(per_typ.get(s["typ"], 0.0), swiezosc(s, icp, dzis))
        sila = sum(per_typ.values()) * (1.25 if sum(1 for v in per_typ.values() if v > 0) >= 2 else 1.0)
        if sila <= 0:
            continue                                             # wszystkie sygnały poza oknem świeżości
        ocena = round(100 * fit * min(1.0, sila / 6))
        najlepszy = max(ss, key=lambda s: swiezosc(s, icp, dzis))
        kt = kontakty.get(k) or kontakty.get(f"www:{ll.domena(firma['www'])}" if firma.get("www") else "") or {}
        emaile = list(kt.get("emaile") or []) + [{"email": c["wartosc"], "rodzaj": c.get("rodzaj"), "zrodlo": c.get("zrodlo")}
                                                 for s in ss for c in s.get("kontakty") or [] if c.get("typ") == "email"]
        emaile.sort(key=lambda e: {"ogolny": 0, "rolowy": 1, "osobowy": 2}.get(e.get("rodzaj"), 3))
        e = emaile[0] if emaile else {}
        out.append({
            "klucz": k, "nazwa": firma.get("nazwa"), "nip": firma.get("nip"), "krs": firma.get("krs"), "woj": firma.get("woj"),
            "miejscowosc": firma.get("miejscowosc"), "www": firma.get("www") or (kt.get("domena") and f"https://{kt['domena']}"),
            "ocena": ocena, "dopasowanie": round(fit, 2),
            "sygnaly": "; ".join(f"{s['typ']}@{str(s.get('data'))[:10]}" for s in sorted(ss, key=lambda s: str(s.get("data")), reverse=True)),
            "dlaczego_teraz": powody.get(k) or najlepszy.get("opis") or najlepszy["typ"],
            "zrodla": " ".join(dict.fromkeys(s.get("zrodlo") for s in ss if s.get("zrodlo"))),
            "email": e.get("email"), "email_rodzaj": e.get("rodzaj"), "email_zrodlo": e.get("zrodlo"),
            "telefon": ((kt.get("telefony") or [{}])[0]).get("numer"), "formularz": kt.get("formularz"),
        })
    out.sort(key=lambda r: (-r["ocena"], r["nazwa"] or ""))
    return out


def cmd_ocen(projekt: Path, top: int, monitoring: bool, dzis: dt.date | None = None) -> int:
    dzis = dzis or dt.date.today()
    icp = wczytaj_icp(projekt)
    sygnaly = ll.czytaj_jsonl(str(projekt / "sygnaly.jsonl"))
    kontakty = json.loads((projekt / "kontakty.json").read_text(encoding="utf-8")) if (projekt / "kontakty.json").is_file() else {}
    powody = json.loads((projekt / "powody.json").read_text(encoding="utf-8")) if (projekt / "powody.json").is_file() else {}
    firmy = ocen_firmy(sygnaly, kontakty, powody, icp, dzis)
    baza_p = projekt / "baza.json"
    baza = json.loads(baza_p.read_text(encoding="utf-8")) if baza_p.is_file() else {}
    pierwszy = not baza
    for f in firmy:
        f["nowy"] = "tak" if f["klucz"] not in baza else ""
        f["pierwszy_raz"] = baza.get(f["klucz"], dzis.isoformat())
        baza.setdefault(f["klucz"], dzis.isoformat())
    with (projekt / "leady.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=POLA)
        w.writeheader()
        w.writerows({k: f.get(k) for k in POLA} for f in firmy)
    baza_p.write_text(json.dumps(baza, ensure_ascii=False, indent=1), encoding="utf-8")
    pokazane = [f for f in firmy if f["nowy"]] if monitoring and not pierwszy else firmy
    z_kontaktem = sum(1 for f in firmy if f["email"] or f["telefon"] or f["formularz"])
    firm_sygn = len({s["_klucz"] for s in sygnaly})
    L = [f"# Leady: {icp.get('nazwa') or projekt.name}", "",
         f"Stan na {dzis.isoformat()}. Pokrycie: {len(sygnaly)} sygnałów → {firm_sygn} firm → {len(firmy)} po dopasowaniu "
         f"do ICP → {z_kontaktem} z opublikowanym kontaktem.", ""]
    if monitoring:
        L += ["Pierwszy przebieg: to jest baza, kolejne pokażą tylko nowe firmy." if pierwszy
              else f"Monitoring: {len(pokazane)} nowych firm od poprzedniego przebiegu.", ""]
    L += ["| # | Firma | Ocena | Dlaczego teraz | Kontakt | Źródło |", "|---|---|---|---|---|---|"]
    for i, f in enumerate(pokazane[:top], 1):
        kontakt = (f"{f['email']} ({f['email_rodzaj']})" if f["email"] else f["telefon"] or (f"[formularz]({f['formularz']})" if f["formularz"] else "–"))
        zrodla = " ".join(f"[{etykieta(u)}]({u})" for u in (f["zrodla"] or "").split() if u) or "–"
        miejsce = ", ".join(x for x in (f["miejscowosc"], f["woj"]) if x)
        L.append(f"| {i} | {ll.krotka_nazwa(f['nazwa'])}{' (' + miejsce.title() + ')' if miejsce else ''} | {f['ocena']} | "
                 f"{f['dlaczego_teraz']} | {kontakt} | {zrodla} |")
    if not pokazane:
        L.append("| – | brak firm spełniających ICP w tym przebiegu | | | | |")
    L += ["", f"Pełna lista: `leady.csv` ({len(firmy)} firm, kontakty ze źródłami).", "", f"> {PRZYPOMNIENIE}", ""]
    (projekt / "LEADY.md").write_text("\n".join(L), encoding="utf-8")
    print(f"✓ {projekt / 'LEADY.md'}: {len(firmy)} firm po dopasowaniu, {z_kontaktem} z kontaktem"
          + (f", nowych {sum(1 for f in firmy if f['nowy'])}" if not pierwszy else " (baza)"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dodaj")
    s.add_argument("projekt", type=Path)
    s.add_argument("pliki", nargs="+")
    s = sub.add_parser("kontakt")
    s.add_argument("projekt", type=Path)
    s.add_argument("pliki", nargs="+")
    s = sub.add_parser("powod")
    s.add_argument("projekt", type=Path)
    s.add_argument("klucz")
    s.add_argument("tekst")
    s = sub.add_parser("ocen")
    s.add_argument("projekt", type=Path)
    s.add_argument("--top", type=int, default=30)
    s.add_argument("--monitoring", action="store_true", help="w raporcie tylko firmy nowe względem baza.json")
    a = ap.parse_args(argv)
    a.projekt.mkdir(parents=True, exist_ok=True)
    if a.cmd == "dodaj":
        return cmd_dodaj(a.projekt, a.pliki)
    if a.cmd == "kontakt":
        return cmd_kontakt(a.projekt, a.pliki)
    if a.cmd == "powod":
        return cmd_powod(a.projekt, a.klucz, a.tekst)
    return cmd_ocen(a.projekt, a.top, a.monitoring)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prosty polski bez modelu (skill `prosty-polski`, wzór ASD-STE100 „w 80%”): limity zdań i akapitów, słowa urzędowe,
strona bierna i łańcuchy rzeczowników w tekście do właściciela.

    python3 prosty.py plik.md [...]            # albo --tekst "…", albo - (stdin)
    python3 prosty.py --tydzien                # wiadomości Jarva do właściciela z 7 dni (state.db), jak w przeglądzie tygodnia

Słownik zamienników: skills/fleet/prosty-polski/references/slownik.md (jedno źródło dla skilla i skryptu).
Kod: 0 = bez potknięć, 1 = są potknięcia. Ostatnia linia wyjścia to JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ZDANIE_MAX, AKAPIT_MAX, LANCUCH_MAX = 25, 6, 2
SLOWNIK_MD = Path(__file__).resolve().parent.parent / "skills" / "fleet" / "prosty-polski" / "references" / "slownik.md"
# skróty z kropką, które nie kończą zdania
SKROTY = re.compile(r"\b(np|m\.in|tj|itd|itp|ok|godz|zł|tzw|wg|ul|nr|ds|r|s|min|tys|mln|mld|pkt|str|ang|por|dot|jw|ww)\.", re.I)
KONIEC = re.compile(r"(?<=[.!?…])\s+(?=\S)")
SLOWO = re.compile(r"[\w@#/:.\-–]*\w[\w@#/:.\-–]*", re.U)
BIERNA = re.compile(r"\bzosta(?:ł|ła|ło|ły|li|nie|ną|wać|ć)\s+\w+(?:ny|na|ne|ni|ty|ta|te|ci|ony|ona|one|eni)\b", re.I)
RZECZOWNIK = re.compile(r"^\w{4,}(?:nia|niu|nie|cia|ciu|cie|ości|ość)$", re.I)
LISTA = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
POMIJAJ = ("```", "|", "#", ">")
POMIJANE_ZRODLA = {"kanban", "cli", "tui"}          # pracownik i sędzia na tablicy, terminal: nie do właściciela


def slownik(md: Path = SLOWNIK_MD) -> list[tuple[re.Pattern, str, str]]:
    """Tabela „| Zamiast | Pisz |” → (wzorzec, zamiast, pisz); `*` = dowolna końcówka."""
    out = []
    for ln in md.read_text(encoding="utf-8").splitlines() if md.is_file() else []:
        kol = [k.strip() for k in ln.strip().strip("|").split("|")]
        if len(kol) != 2 or not kol[0] or kol[0].lower() == "zamiast" or set(kol[0]) <= set("-: "):
            continue
        wz = r"\b" + r"\s+".join(re.escape(w).replace(r"\*", r"\w*") for w in kol[0].split()) + (r"" if kol[0].endswith("*") else r"\b")
        out.append((re.compile(wz, re.I), kol[0], kol[1]))
    return out


def _czysty(linia: str) -> str:
    """Bez kodu w backtickach, linków markdown i znaczników wyróżnienia."""
    linia = re.sub(r"`[^`]*`", "KOD", linia)
    linia = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", linia)
    return re.sub(r"[*_]{1,3}", "", linia)


def zdania(tekst: str) -> list[str]:
    tekst = SKROTY.sub(lambda m: m.group(0).replace(".", "·"), tekst)
    return [z.replace("·", ".").strip() for z in KONIEC.split(tekst) if z.strip()]


def akapity(tekst: str) -> list[list[str]]:
    """Akapity jako listy linii; bloki kodu, tabele i nagłówki pominięte, punkt listy to osobny akapit."""
    out, cur, kod = [], [], False
    for ln in tekst.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            kod = not kod
            continue
        if kod or not s or s.startswith(POMIJAJ):
            if cur:
                out.append(cur)
            cur = []
            continue
        if LISTA.match(ln):
            if cur:
                out.append(cur)
            out.append([LISTA.sub("", ln)])
            cur = []
        else:
            cur.append(s)
    if cur:
        out.append(cur)
    return out


def sprawdz(tekst: str, slow: list | None = None) -> dict:
    slow = slownik() if slow is None else slow
    uwagi: list[dict] = []
    n_zdan = 0
    for akapit in akapity(tekst or ""):
        zd = zdania(_czysty(" ".join(akapit)))
        n_zdan += len(zd)
        if len(zd) > AKAPIT_MAX:
            uwagi.append({"typ": "za długi akapit", "opis": f"{len(zd)} zdań (maks. {AKAPIT_MAX})", "gdzie": zd[0][:60]})
        for z in zd:
            slowa = SLOWO.findall(z)
            if len(slowa) > ZDANIE_MAX:
                uwagi.append({"typ": "za długie zdanie", "opis": f"{len(slowa)} słów (maks. {ZDANIE_MAX}, polecenie 20)",
                              "gdzie": z[:60]})
            for m in BIERNA.finditer(z):
                uwagi.append({"typ": "strona bierna", "opis": f"„{m.group(0)}”: napisz, kto to zrobił", "gdzie": z[:60]})
            ciag = []
            for w in [*re.findall(r"\w+", z), ""]:
                if RZECZOWNIK.match(w):
                    ciag.append(w)
                    continue
                if len(ciag) > LANCUCH_MAX:
                    uwagi.append({"typ": "łańcuch rzeczowników", "opis": f"„{' '.join(ciag)}”: użyj czasownika",
                                  "gdzie": z[:60]})
                ciag = []
            for wz, zamiast, pisz in slow:
                for m in wz.finditer(z):
                    uwagi.append({"typ": f"„{zamiast.rstrip('*')}…”", "opis": f"„{m.group(0)}” → {pisz}", "gdzie": z[:60]})
    return {"zdania": n_zdan, "uwagi": uwagi, "ok": not uwagi}


def wiadomosci_tygodnia(dane: Path, now: float, dni: int = 7) -> list[str]:
    """Końcowe odpowiedzi Jarva (bez wywołań narzędzi) z ostatnich dni: rozmowy i rutyny, bez tablicy i terminala."""
    baza = dane / "profiles" / "jarvo" / "state.db"
    if not baza.is_file():
        return []
    conn = sqlite3.connect(f"file:{baza}?mode=ro", uri=True, timeout=5)
    try:
        rows = conn.execute(
            "SELECT s.source, m.content FROM messages m JOIN sessions s ON s.id = m.session_id "
            "WHERE m.role = 'assistant' AND m.timestamp >= ? AND m.content IS NOT NULL AND m.content != '' "
            "AND (m.tool_calls IS NULL OR m.tool_calls IN ('', '[]'))", (now - dni * 86400,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [c for src, c in rows if (src or "") not in POMIJANE_ZRODLA and c.strip() not in ("[SILENT]", "")]


def tydzien(dane: Path, now: float, dni: int = 7) -> dict:
    slow = slownik()
    wyniki = [sprawdz(t, slow) for t in wiadomosci_tygodnia(dane, now, dni)]
    typy = Counter(u["typ"] for w in wyniki for u in w["uwagi"])
    return {"wiadomosci": len(wyniki), "w_normie": sum(1 for w in wyniki if w["ok"]),
            "najczestsze": [f"{t} ×{n}" for t, n in typy.most_common(3)]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pliki", nargs="*")
    ap.add_argument("--tekst")
    ap.add_argument("--tydzien", action="store_true")
    a = ap.parse_args(argv)
    if a.tydzien:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import liczby
        w = tydzien(liczby.dane_domyslne(), time.time())
        print(f"Prosty polski, 7 dni: {w['w_normie']}/{w['wiadomosci']} wiadomości w normie"
              + (f"; najczęściej: {', '.join(w['najczestsze'])}" if w["najczestsze"] else ""))
        print(json.dumps(w, ensure_ascii=False))
        return 0
    if a.tekst is not None:
        tekst = a.tekst
    elif a.pliki == ["-"] or not a.pliki:
        tekst = sys.stdin.read()
    else:
        tekst = "\n\n".join(Path(p).read_text(encoding="utf-8") for p in a.pliki)
    w = sprawdz(tekst)
    if w["ok"]:
        print(f"✓ prosty polski: zdania bez potknięć ({w['zdania']})")
    else:
        print(f"✗ potknięcia: {len(w['uwagi'])} (zdania: {w['zdania']})")
        for u in w["uwagi"]:
            print(f"- {u['typ']}: {u['opis']} („{u['gdzie']}…”)")
    print(json.dumps(w, ensure_ascii=False))
    return 0 if w["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

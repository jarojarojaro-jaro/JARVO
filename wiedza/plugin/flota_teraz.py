"""Blok „Teraz we flocie” przed turą agenta (hak `pre_llm_call` wtyczki jarvo-wiedza, docs/HQ.md „Oś floty”).

28.11 test OLX i SMS Jarva stukały naraz w telefon `first` i zgubiły się oba (dwie sesje tego samego profilu `jarvo`):
agent przed każdą turą widzi INNE zadania w toku (innych agentów i swoje z innej rozmowy albo karty, rozróżnione
kluczem zadania jak zgody/plugin `_klucz_zadania`) i zajęte urządzenia, z osi floty `<stan>/os-floty.db` (zbiera ją
panel) i `<korzeń>/../stan/telefon-zadania.json` (strażnik telefonu zgód). Bez promptów i wyników, ≤ MAKS_LINII
linii; nic innego w toku i wolne urządzenia = brak bloku. Tylko odczyt (sqlite `mode=ro`), koszt rzędu 1 ms.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

MAKS_LINII = 12                      # razem z nagłówkiem
TYTUL_MAKS = 80
OKNO_S = 24 * 3600                   # wpis „w toku” starszy niż doba to raczej zgubiony koniec, nie praca teraz
ZAJETY_S = 600.0                     # jak zgody/plugin _ZAJETY_S
NAGLOWEK = "Teraz we flocie (inne zadania; zajętego urządzenia nie dotykaj):"
TWOJE = {"sesja": "twoja inna rozmowa", "karta": "twoja karta"}


def _godz(ts) -> str:
    return time.strftime("%H:%M", time.localtime(float(ts)))


def _tytul(t: str) -> str:
    t = " ".join(str(t or "").split())
    return t if len(t) <= TYTUL_MAKS else t[:TYTUL_MAKS - 1].rstrip() + "…"


def w_toku(baza: Path, wlasne: set[str], teraz: float) -> list[dict]:
    """Wpisy w toku i z pytaniem poza zadaniami o kluczach `wlasne` (od najstarszego startu)."""
    if not baza.is_file():
        return []
    conn = sqlite3.connect(baza.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    try:
        conn.row_factory = sqlite3.Row
        wiersze = [dict(r) for r in conn.execute(
            "SELECT id, agent, tytul, stan, start_at, zasoby, klucz FROM zadania WHERE stan IN ('w_toku', 'pytanie') "
            "AND COALESCE(start_at, zmieniono_at) >= ? ORDER BY start_at", (teraz - OKNO_S,))]
    finally:
        conn.close()
    return [w for w in wiersze if not w["klucz"] or w["klucz"] not in wlasne][:MAKS_LINII]


def zajete(telefony: Path, wlasne: set[str], teraz: float) -> dict[str, tuple[str, float]]:
    """Urządzenie → (klucz zadania, czas ostatniego kroku) z krokiem innego zadania w ostatnich ZAJETY_S s."""
    try:
        dane = json.loads(telefony.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for nazwa, z in (dane.items() if isinstance(dane, dict) else ()):
        if not isinstance(z, dict) or str(z.get("klucz") or "") in wlasne:
            continue
        try:
            t = float(z.get("t") or 0)
        except (TypeError, ValueError):
            continue
        if 0 <= teraz - t < ZAJETY_S:
            out["pulpit" if nazwa == "pulpit" else f"telefon:{nazwa}"] = (str(z.get("klucz") or ""), t)
    return out


def blok(baza: Path, telefony: Path, profil: str, wlasne: set[str], teraz: Optional[float] = None) -> str:
    """Tekst bloku albo "" (nic innego w toku, urządzenia wolne). `wlasne`: klucze bieżącego zadania
    (`sesja:<session_id>`, `karta:<task_id>`); wpis tego samego profilu z innym kluczem dostaje dopisek."""
    teraz = time.time() if teraz is None else teraz
    zadania = w_toku(baza, wlasne, teraz)
    urzadzenia = zajete(telefony, wlasne, teraz)
    linie = []
    for z in zadania:
        try:
            zasoby = [x for x in json.loads(z.get("zasoby") or "[]") if isinstance(x, str)]
        except ValueError:
            zasoby = []
        for x, (klucz, _t) in list(urzadzenia.items()):
            if x in zasoby or (z["klucz"] and klucz == z["klucz"]):
                urzadzenia.pop(x)
                if x not in zasoby:
                    zasoby.append(x)
        kto = z["agent"]
        if kto == profil:
            kto += f" ({TWOJE.get(str(z['klucz'] or '').partition(':')[0], 'twoje inne zadanie')})"
        czesci = [kto, _tytul(z["tytul"]) + (" (czeka na odpowiedź)" if z["stan"] == "pytanie" else ""),
                  f"od {_godz(z['start_at'])}" if z.get("start_at") else ""]
        linie.append(" · ".join(x for x in (*czesci, ", ".join(zasoby)) if x))
    for zasob, (klucz, t) in sorted(urzadzenia.items()):
        linie.append(f"{zasob} · zajęty przez inne zadanie ({klucz or '?'}) · ostatni krok {_godz(t)}")
    if not linie:
        return ""
    return "\n".join([NAGLOWEK, *linie[:MAKS_LINII - 1]])

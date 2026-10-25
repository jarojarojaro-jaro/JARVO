"""Praca floty widziana z aplikacji Jarvo (docs/HQ.md „Rozmowy”). Etap 2: tylko to, czego potrzebuje bezpieczna
aktualizacja (`praca.json`) i obecność: karty kanbana w toku. Powiązanie kart z wątkami, żywa karta i sesja
pracownika przyjdą w etapie 4.

`praca.json` (`<dane>/jarvo/state/praca.json`, zapis przez rename): `{"aktywne": N, "opis": ["Web: karta
„Stopka”", …], "at": <ts>}`; N = nasze przebiegi od `wysylanie` do `zatrzymywanie` (z `czeka_na_zgode`), karty
w `running` i obce tury z ważną dzierżawą (Telegram, budzenie, cron) poza sesjami wątków. Bez treści poza nazwami
agentów i tytułami kart. Czyta go `install-fleet.sh` (ostrzeżenie przed restartem bramy) i pomocnik aktualizacji.
Czysty Python (sqlite3 tylko do odczytu); testy: tests/test_silnik_rozmow.py.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Mapping

OPIS_MAKS = 12


def karty_w_toku(kanban_db: Path | str) -> list[dict]:
    """Karty `running`: {task_id, tytul, wykonawca}; pusta lista, gdy bazy nie ma albo jest nieczytelna."""
    p = Path(kanban_db)
    if not p.is_file():
        return []
    try:
        conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            rows = conn.execute("SELECT id, title, assignee FROM tasks WHERE status = 'running' ORDER BY started_at, id")
            return [{"task_id": r[0], "tytul": r[1] or "", "wykonawca": r[2] or ""} for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def praca(przebiegi: Iterable[Mapping], karty: Iterable[Mapping], obce_tury: Iterable[Mapping], *,
          nazwy: Mapping[str, str] | None = None, teraz: float | None = None) -> dict:
    """Stan pracy do `praca.json` i `/health`."""
    nazwy = nazwy or {}
    opis: list[str] = []
    n = 0
    for p in przebiegi:
        n += 1
        opis.append(f"{nazwy.get(p['agent'], p['agent'])}: rozmowa")
    for k in karty:
        n += 1
        opis.append(f"{nazwy.get(k['wykonawca'], k['wykonawca'] or '?')}: karta „{k['tytul']}”")
    for t in obce_tury:
        n += 1
        opis.append(f"{nazwy.get(t['agent'], t['agent'])}: tura ({t.get('platforma') or '?'})")
    return {"aktywne": n, "opis": opis[:OPIS_MAKS], "at": time.time() if teraz is None else teraz}


def zapisz(sciezka: Path | str, dane: Mapping, proby: int = 40) -> None:
    """Zapis atomowy (plik tymczasowy obok i rename), tryb 0644: czyta go też skrypt instalacji floty. Na Windows
    plik czytany właśnie przez inny proces (instalacja floty, pomocnik aktualizacji) nie da się podmienić (WinError
    5/32): ponowienie co 50 ms (docs/NATYWNIE.md W08)."""
    sciezka = Path(sciezka)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    tmp = sciezka.with_name(f".{sciezka.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dict(dane), ensure_ascii=False), encoding="utf-8")
    for proba in range(proby):
        try:
            os.replace(tmp, sciezka)
            return
        except PermissionError:
            if os.name != "nt" or proba == proby - 1:
                raise
            time.sleep(0.05)

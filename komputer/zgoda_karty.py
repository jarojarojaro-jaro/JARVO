"""Zgoda właściciela zapisana w karcie kanbana (docs/KOMPUTER.md §6), sama biblioteka standardowa.

Jarvo wpisuje polecenie właściciela do treści karty jedną linią (w dowolnym miejscu treści):
    ZGODA WŁAŚCICIELA: <kategorie po przecinku> — „<cytat polecenia>” (RRRR-MM-DD)
Kategorie (bez względu na wielkość liter, także z polskimi znakami): platnosc, wysylka, publikacja,
usuniecie_konta, konto; `wszystko` = wszystkie. Linia z nieznaną kategorią, bez cytatu albo ze złą datą nie daje
żadnej zgody; kilka poprawnych linii się sumuje.

Zgodę czyta zaufany kod (wejście Komputera z numerem karty od bramki, wtyczka zgód), nigdy strona ani argumenty
modelu. Baza kanbana tylko do odczytu.
"""
from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

KATEGORIE = ("platnosc", "wysylka", "publikacja", "usuniecie_konta", "konto")
ZGODA = re.compile(r"^[ \t>*-]*ZGODA W[ŁL]A[ŚS]CICIELA:[ \t]*(?P<kategorie>[^—–„“\"\n]+?)[ \t]*[—–][ \t]*"
                   r"[„“\"](?P<cytat>[^”“\"\n]+)[”“\"][ \t]*\((?P<data>\d{4}-\d{2}-\d{2})\)[ \t]*$", re.I | re.M)
KARTA = re.compile(r"^[A-Za-z0-9_-]{1,64}$")                       # numer karty Hermesa
TABLICA = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")                # nazwa tablicy Hermesa (kanban_db: slug)
_BEZ_ZNAKOW = str.maketrans("ąćęłńóśźż", "acelnoszz")


def _kategorie(slowo: str) -> tuple[str, ...] | None:
    s = re.sub(r"[\s-]+", "_", unicodedata.normalize("NFKC", slowo).strip().lower().translate(_BEZ_ZNAKOW))
    if s == "wszystko":
        return KATEGORIE
    return (s,) if s in KATEGORIE else None


def zgoda_z_tresci(body: str | None) -> frozenset[str]:
    """Kategorie zgody właściciela z treści karty (pusty zbiór bez poprawnej linii ZGODA WŁAŚCICIELA)."""
    if not isinstance(body, str) or not body:
        return frozenset()
    wynik: set[str] = set()
    for m in ZGODA.finditer(body.replace("\r\n", "\n").replace("\r", "\n")):
        try:
            date.fromisoformat(m["data"])
        except ValueError:
            continue
        slowa = [_kategorie(s) for s in m["kategorie"].split(",")]
        if m["cytat"].strip() and slowa and all(slowa):
            wynik.update(k for s in slowa for k in s)
    return frozenset(wynik)


def sciezka_kanbana(dane: str | Path, tablica: str | None = None) -> Path | None:
    """kanban.db tablicy w `<dane>` (HERMES_HOME Jarva): `default` w `<dane>/kanban.db`, inne
    w `<dane>/kanban/boards/<tablica>/kanban.db` (jak hermes_cli/kanban_db.py); zła nazwa tablicy: None."""
    tablica = (tablica or "default").strip().lower()
    if not TABLICA.match(tablica):
        return None
    dane = Path(dane)
    return dane / "kanban.db" if tablica == "default" else dane / "kanban" / "boards" / tablica / "kanban.db"


def _baza_z_otoczenia() -> Path | None:
    """kanban.db pracownika kanbana z otoczenia Hermesa: HERMES_KANBAN_DB, inaczej tablica HERMES_KANBAN_BOARD
    w korzeniu HERMES_KANBAN_HOME albo HERMES_HOME (HERMES_HOME profilu `<dane>/profiles/<p>`: korzeń `<dane>`)."""
    jawna = os.environ.get("HERMES_KANBAN_DB", "").strip()
    if jawna:
        return Path(jawna).expanduser()
    korzen = os.environ.get("HERMES_KANBAN_HOME", "").strip() or os.environ.get("HERMES_HOME", "").strip()
    if not korzen:
        return None
    k = Path(korzen).expanduser()
    if k.parent.name == "profiles":
        k = k.parent.parent
    return sciezka_kanbana(k, os.environ.get("HERMES_KANBAN_BOARD"))


def tresc_karty(task_id: str, baza: str | Path | None = None) -> str | None:
    """Treść (`tasks.body`) karty `task_id` z kanban.db otwartej tylko do odczytu; `baza` None: z otoczenia
    pracownika Hermesa. None: zły numer, brak bazy, karty albo błąd odczytu."""
    if not isinstance(task_id, str) or not KARTA.match(task_id):
        return None
    sciezka = Path(baza) if baza is not None else _baza_z_otoczenia()
    if sciezka is None or not sciezka.is_file():
        return None
    try:
        con = sqlite3.connect(sciezka.resolve().as_uri() + "?mode=ro", uri=True, timeout=2.0)
    except sqlite3.Error:
        return None
    try:
        wiersz = con.execute("SELECT body FROM tasks WHERE id = ?", (task_id,)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    return wiersz[0] if wiersz and isinstance(wiersz[0], str) else None

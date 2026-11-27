#!/usr/bin/env python3
"""Czyści zapisany system prompt trwających rozmów jednego profilu Hermesa, żeby następna tura zbudowała go od nowa.

27.11: rozmowa, która trwa, bierze prompt zapisany w wierszu sesji przy pierwszej turze (Hermes
agent/conversation_loop.py `_restore_or_build_system_prompt`), więc po wgraniu nowego SOUL.md działała tygodniami na
starym, aż do kompresji. Pusty prompt w wierszu = przebudowa z bieżącego SOUL.md i zapis nowego (jedno pominięcie
cache na rozmowę). Ten sam zapis robi sam Hermes przy zmianie modelu (`update_session_model`).

Uruchamia go install_fleet.py Pythonem venvu Hermesa: `python -P odswiez_prompt.py <profil>/state.db`. Wypisuje
JSON {"rozmowy": n}. Trwająca rozmowa to wiersz bez `ended_at` albo zamknięty z powodu, po którym brama ją wznawia
(`_RECOVERABLE_END_REASONS`, np. sprzątanie po restarcie bramy). Baza istnieje (nie zakłada nowej).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def odswiez(baza: Path) -> int:
    """Liczba rozmów, którym wyczyszczono zapisany prompt (tylko te, które go miały)."""
    if not baza.is_file():
        raise FileNotFoundError(baza)
    from hermes_state import SessionDB
    from hermes_state_common import _RECOVERABLE_END_REASONS
    db = SessionDB(baza)
    try:
        znaki = ", ".join("?" for _ in _RECOVERABLE_END_REASONS)
        wiersze = db._read_all(
            "SELECT id FROM sessions WHERE (ended_at IS NULL OR end_reason IN (" + znaki + ")) "
            "AND (system_prompt_hash IS NOT NULL OR system_prompt IS NOT NULL)",
            tuple(_RECOVERABLE_END_REASONS))
        for w in wiersze:
            db.update_system_prompt(w["id"], None)
        return len(wiersze)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("użycie: odswiez_prompt.py <state.db>", file=sys.stderr)
        return 2
    print(json.dumps({"rozmowy": odswiez(Path(argv[0]))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

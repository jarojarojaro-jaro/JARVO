#!/usr/bin/env python3
"""Dane raportu dnia Hackera (cron `hacker-terminy`, przed turą modelu): odświeża kalendarz w katalogu roboczym
(`out/KALENDARZ.md`, `out/hackatony.ics`) i notatkę w Mózgu, wypisuje najlepsze hackathony do wzięcia teraz
i nasze starty z następnym krokiem (`hackatony.py raport`), a potem dzisiejsze agregatory spoza bazy (`zrodla.py`).

    raport_rano.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackatony  # noqa: E402
import zrodla  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    katalog = Path(hackatony.domyslna_baza()).resolve().parents[1] / "out"
    wynik = hackatony.main(["raport", "--katalog", str(katalog), *(argv if argv is not None else sys.argv[1:])])
    print()
    return wynik or zrodla.main(["--katalog", str(katalog)])


if __name__ == "__main__":
    sys.exit(main())

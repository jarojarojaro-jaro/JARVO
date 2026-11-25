#!/usr/bin/env python3
"""Rutyna Hackera bez modelu (cron `hacker-terminy`): odświeża kalendarz hackathonów w katalogu roboczym
(`out/KALENDARZ.md`, `out/hackatony.ics`) i notatkę w Mózgu, a codziennie pisze raport: etapy w ciągu 72 h i 5
następnych terminów, w poniedziałek całe 14 dni.

    terminy_rano.py [--tydzien]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackatony  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    katalog = Path(hackatony.domyslna_baza()).resolve().parents[1] / "out"
    return hackatony.main(["przypomnij", "--katalog", str(katalog), *(argv if argv is not None else sys.argv[1:])])


if __name__ == "__main__":
    sys.exit(main())

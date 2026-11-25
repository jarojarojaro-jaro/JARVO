#!/usr/bin/env python3
"""Rutyna Bigshorta bez modelu (cron `bigshort-terminy`): odświeża kalendarz finansowania w katalogu roboczym
(`out/KALENDARZ.md`, `out/finansowanie.ics`) i notatkę w Mózgu, a codziennie pisze raport: terminy naborów i nasze
kroki w ciągu 7 dni i 5 następnych, w poniedziałek całe 30 dni.

    terminy_rano.py [--tydzien]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import okazje  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    katalog = Path(okazje.domyslna_baza()).resolve().parents[1] / "out"
    return okazje.main(["przypomnij", "--katalog", str(katalog), *(argv if argv is not None else sys.argv[1:])])


if __name__ == "__main__":
    sys.exit(main())

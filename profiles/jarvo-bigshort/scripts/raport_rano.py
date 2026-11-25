#!/usr/bin/env python3
"""Raport dnia Bigshorta bez modelu (cron `bigshort-terminy`): odświeża kalendarz finansowania w katalogu roboczym
(`out/KALENDARZ.md`, `out/finansowanie.ics`) i notatkę w Mózgu, a wypisuje najlepsze okazje do wzięcia dla każdego
projektu i nasze aplikacje w toku (`okazje.py raport`).

    raport_rano.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import okazje  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    katalog = Path(okazje.domyslna_baza()).resolve().parents[1] / "out"
    return okazje.main(["raport", "--katalog", str(katalog), *(argv if argv is not None else sys.argv[1:])])


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Scala sekrety z /opt/tars/secrets/<x>.env do docelowego .env profilu.

    python merge_env.py <źródło.env> <cel.env>

- klucz z niepustą wartością w źródle nadpisuje cel,
- pusta wartość w źródle NIE kasuje istniejącej w celu (szablon nie zeruje kluczy),
- pozostałe linie celu (komentarze, klucze dopisane przez Hermesa) zostają,
- plik docelowy ma uprawnienia 0600. Wartości nigdy nie są wypisywane.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def parse(path: Path) -> dict[str, str]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = LINE.match(line)
            if m and not line.lstrip().startswith("#"):
                out[m.group(1)] = m.group(2).strip()
    return out


def main(argv: list[str]) -> int:
    src, dst = Path(argv[0]), Path(argv[1])
    updates = {k: v for k, v in parse(src).items() if v not in ("", '""', "''")}
    lines = dst.read_text(encoding="utf-8").splitlines() if dst.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        m = LINE.match(line)
        if m and not line.lstrip().startswith("#") and m.group(1) in updates:
            lines[i] = f"{m.group(1)}={updates[m.group(1)]}"
            seen.add(m.group(1))
    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(dst, 0o600)
    print(f"{dst}: ustawiono {len(updates)} kluczy ({', '.join(sorted(updates))})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

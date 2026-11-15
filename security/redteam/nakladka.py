"""Dopisuje ataki nakładki prywatnej (security/redteam/testy.yaml nakładki, docs/FLEET.md „Agenci biznesowi”) do
`tests:` konfiguracji promptfoo w katalogu roboczym red teamu (scripts/redteam.sh). Repo zostaje nietknięte.

    python3 nakladka.py promptfooconfig.yaml testy.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def dopisz(config: Path, testy: Path) -> int:
    """Liczba dopisanych testów; plik testów musi być listą (jak `tests:` konfiguracji)."""
    dodatkowe = yaml.safe_load(testy.read_text(encoding="utf-8")) or []
    if not isinstance(dodatkowe, list):
        raise SystemExit(f"{testy}: oczekuję listy testów promptfoo")
    dane = yaml.safe_load(config.read_text(encoding="utf-8"))
    dane["tests"] = [*(dane.get("tests") or []), *dodatkowe]
    config.write_text(yaml.safe_dump(dane, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return len(dodatkowe)


if __name__ == "__main__":
    print(f"nakładka: +{dopisz(Path(sys.argv[1]), Path(sys.argv[2]))} ataków")

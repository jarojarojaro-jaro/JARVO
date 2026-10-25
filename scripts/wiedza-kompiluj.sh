#!/usr/bin/env bash
# Ręczna kompilacja skarbca w kontenerze (docs/WIEDZA.md §6); cała logika jest w Pythonie (wiedza/kompilacja.py:
# HERMES_HOME profilu jarvo z jego auxiliary.jarvo_wiedza, kod Hermesa z /opt/hermes, blokada jednego piszącego).
#   docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/wiedza-kompiluj.sh [--na-sucho] [--limit N] [--json]
# Natywnie (Windows, macOS, Linux bez kontenera): `jarvo wiedza kompiluj` (jarvo/wiedza_cli.py), bez basha.
# Zakładka Wiedza woła kompilacja.py wprost, a samą kompilację zwykle odpala wtyczka jarvo-wiedza (co godzinę przy
# szkicach i co noc o 03:10, nadrabiane po uśpieniu). Skrypt zniknie razem z kontenerem (docs/NATYWNIE.md j1).
set -euo pipefail
cd "${HERMES_SRC:-/opt/hermes}"
exec /opt/hermes/.venv/bin/python /opt/jarvo/repo/wiedza/kompilacja.py --profil "${JARVO_WIEDZA_PROFIL:-jarvo}" "$@"

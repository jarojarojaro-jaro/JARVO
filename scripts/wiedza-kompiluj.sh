#!/usr/bin/env bash
# Ręczna kompilacja skarbca wiedzy (docs/WIEDZA.md §6): szkice ze skrzynki → notatki, tanim modelem (auxiliary.jarvo_wiedza).
# Uruchamiane WEWNĄTRZ kontenera jarvo-hermes jako hermes, z profilem jarvo (jego config ma model zadania pomocniczego):
#   docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/wiedza-kompiluj.sh [--na-sucho] [--limit N] [--json]
# Normalnie kompilację odpala sama wtyczka jarvo-wiedza (raz na godzinę przy szkicach i co noc o 03:10).
set -euo pipefail
PROFIL="${JARVO_WIEDZA_PROFIL:-jarvo}"
export HERMES_HOME="${HERMES_HOME_PROFIL:-/opt/data/profiles/$PROFIL}"
export HERMES_SRC="${HERMES_SRC:-/opt/hermes}"
cd "$HERMES_SRC"
exec /opt/hermes/.venv/bin/python /opt/jarvo/repo/wiedza/kompilacja.py --skarbiec /opt/data/jarvo/knowledge --stan /opt/data/jarvo/state "$@"

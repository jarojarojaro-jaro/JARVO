#!/usr/bin/env bash
# Evals floty na IZOLOWANYCH danych (staging): osobny /opt/data, bez gatewaya i dispatchera,
# więc karty tworzone przez scenariusze nie są wykonywane, a produkcyjna tablica zostaje nietknięta.
#
#   bash scripts/evals-staging.sh [--reset] [argumenty run-evals.py, np. --agent jarvo --id jarvo-route-landing]
#
# Używa tego samego obrazu, buildu (/srv/jarvo/build) i sekretów co produkcja (koszty idą z kluczy agentów).
# Dane stagingu: ${JARVO_STAGING:-/srv/jarvo/staging}/hermes. --reset czyści je przed startem.
# Wyniki: /srv/jarvo/staging/hermes/eval-results/<data>/<agent>.jsonl
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${JARVO_COMPOSE_DIR:-/srv/jarvo/compose}"
STAGING="${JARVO_STAGING:-/srv/jarvo/staging}"
RESET=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done

[[ -f "${JARVO_BUILD:-/srv/jarvo/build}/BUILD.json" ]] || { echo "Brak buildu: najpierw scripts/deploy.sh"; exit 1; }
if [[ $RESET -eq 1 ]]; then
  echo "▶ Czyszczę dane stagingu $STAGING/hermes"
  sudo rm -rf "$STAGING/hermes"
fi
sudo install -d -m 755 -o 10000 -g 10000 "$STAGING/hermes"

# JARVO_DATA ze środowiska powłoki wygrywa z --env-file: kontener widzi dane stagingu jako /opt/data.
export JARVO_DATA="$STAGING"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$COMPOSE_DIR/.env")
PY=/opt/hermes/.venv/bin/python

QUOTED=""
[[ ${#ARGS[@]} -gt 0 ]] && printf -v QUOTED ' %q' "${ARGS[@]}"
# bez init-a s6 (--entrypoint ""): żadnego gatewaya, dispatchera ani dashboardu; od razu jako hermes
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/opt/data hermes bash -c "
  set -e
  bash /opt/jarvo/repo/scripts/install-fleet.sh --first-run --no-restart >/dev/null
  echo '▶ Flota zainstalowana na stagingu, start evals'
  $PY /opt/jarvo/repo/scripts/run-evals.py --out /opt/data/eval-results$QUOTED
"

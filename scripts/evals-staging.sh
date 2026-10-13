#!/usr/bin/env bash
# Evals floty na IZOLOWANYCH danych (staging): osobny /opt/data, bez gatewaya i dispatchera,
# więc karty tworzone przez scenariusze nie są wykonywane, a produkcyjna tablica zostaje nietknięta.
#
#   bash scripts/evals-staging.sh [--reset] [argumenty run-evals.py, np. --agent jarvo --id jarvo-route-landing]
#
# Używa tego samego obrazu, buildu (/srv/jarvo/build) i sekretów co produkcja (koszty idą z kluczy agentów).
# Dane stagingu: ${JARVO_STAGING:-/srv/jarvo/staging}/hermes. --reset czyści je przed startem (oprócz wyników).
# Wyniki: /srv/jarvo/staging/hermes/eval-results/<data>/<agent>.jsonl, historia.jsonl, odniesienie/ (docs/RSI.md).
# Po przebiegu historia, punkty odniesienia i ostatni przebieg trafiają do działającej floty
# (/opt/data/jarvo/evals w jarvo-hermes): czyta je HQ (karta agenta) i przegląd tygodnia Jarva.
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
if [[ $RESET -eq 1 && -d "$STAGING/hermes" ]]; then
  echo "▶ Czyszczę dane stagingu $STAGING/hermes (historia wyników zostaje)"
  sudo find "$STAGING/hermes" -mindepth 1 -maxdepth 1 ! -name eval-results -exec rm -rf {} +
fi
sudo install -d -m 755 -o 10000 -g 10000 "$STAGING/hermes"

# JARVO_DATA ze środowiska powłoki wygrywa z --env-file: kontener widzi dane stagingu jako /opt/data.
export JARVO_DATA="$STAGING"
# macOS i JARVO_VOLUMES=1: compose/.env ma JARVO_VOL_HERMES (wolumen produkcji), który wygrywa z JARVO_DATA;
# bez tego nadpisania staging pracowałby na danych produkcji
export JARVO_VOL_HERMES="$STAGING/hermes"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$COMPOSE_DIR/.env")
PY=/opt/hermes/.venv/bin/python

QUOTED=""
[[ ${#ARGS[@]} -gt 0 ]] && printf -v QUOTED ' %q' "${ARGS[@]}"
# bez init-a s6 (--entrypoint ""): żadnego gatewaya, dispatchera ani dashboardu; od razu jako hermes
RC=0
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/opt/data hermes bash -c "
  set -e
  bash /opt/jarvo/repo/scripts/install-fleet.sh --first-run --no-restart >/dev/null
  echo '▶ Flota zainstalowana na stagingu, start evals'
  $PY /opt/jarvo/repo/scripts/run-evals.py --out /opt/data/eval-results$QUOTED
" || RC=$?

# wyniki do działającej floty (HQ, przegląd tygodnia): historia, punkty odniesienia, ostatni przebieg
WYNIKI="$STAGING/hermes/eval-results"
if docker ps --format '{{.Names}}' | grep -qx jarvo-hermes && sudo test -f "$WYNIKI/historia.jsonl"; then
  CO=(historia.jsonl)
  sudo test -d "$WYNIKI/odniesienie" && CO+=(odniesienie)
  OSTATNI="$(sudo find "$WYNIKI" -mindepth 1 -maxdepth 1 -type d -name '2*' | sort | tail -n 1)"
  [[ -n "$OSTATNI" ]] && CO+=("$(basename "$OSTATNI")")
  if sudo tar -C "$WYNIKI" -cf - "${CO[@]}" | docker exec -i -u 10000:10000 jarvo-hermes \
      sh -c 'mkdir -p /opt/data/jarvo/evals && tar -C /opt/data/jarvo/evals -xf -'; then
    echo "✓ Wyniki w działającej flocie: /opt/data/jarvo/evals (HQ, przegląd tygodnia)"
  else
    echo "! Nie udało się skopiować wyników do jarvo-hermes; zostają w $WYNIKI"
  fi
fi
exit "$RC"

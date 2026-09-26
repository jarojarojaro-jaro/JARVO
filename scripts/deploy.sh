#!/usr/bin/env bash
# Wdrożenie floty TARS na VPS (idempotentne). Uruchamiaj z /srv/tars/repo jako użytkownik z grupy docker.
#
#   bash scripts/deploy.sh [--first-run] [--no-pull] [--rebuild] [--resume-cron] [--monitoring]
#
# Kroki: git pull → docker compose build/up → walidacja repo → build dystrybucji (w kontenerze)
#        → instalacja/aktualizacja profili (w kontenerze) → healthchecki → podsumowanie.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${TARS_COMPOSE_DIR:-/srv/tars/compose}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$COMPOSE_DIR/.env")
PULL=1; REBUILD=0; FIRST=0; RESUME_CRON=0; PROFILES=()
for arg in "$@"; do
  case "$arg" in
    --first-run) FIRST=1; REBUILD=1 ;;
    --no-pull) PULL=0 ;;
    --rebuild) REBUILD=1 ;;
    --resume-cron) RESUME_CRON=1 ;;
    --monitoring) PROFILES+=(--profile monitoring) ;;
    *) echo "Nieznana opcja: $arg"; exit 2 ;;
  esac
done

log() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m✗ %s\033[0m\n' "$*"; exit 1; }

cd "$ROOT"
[[ -f "$COMPOSE_DIR/.env" ]] || fail "Brak $COMPOSE_DIR/.env (skopiuj infra/env/compose.env.example)."
grep -q '^SEARXNG_SECRET=.\+' "$COMPOSE_DIR/.env" || fail "Ustaw SEARXNG_SECRET w $COMPOSE_DIR/.env"
grep -q '^DASHBOARD_PASSWORD=.\+' "$COMPOSE_DIR/.env" || fail "Ustaw DASHBOARD_PASSWORD w $COMPOSE_DIR/.env (openssl rand -hex 16)"

if [[ $PULL -eq 1 ]]; then
  log "git pull"
  before="$(git rev-parse HEAD)"
  git pull --ff-only
  after="$(git rev-parse HEAD)"
  if [[ "$before" != "$after" ]] && git diff --name-only "$before" "$after" | grep -qE '^infra/(Dockerfile|node/|python/)'; then
    REBUILD=1
  fi
fi

if [[ $REBUILD -eq 1 ]]; then
  log "Budowa obrazu tars-hermes (narzędzia agentów)"
  "${COMPOSE[@]}" build --pull hermes
  # poprzedni obraz tars-hermes (~4,4 GB) zostaje bez nazwy, a cache budowania rośnie z każdą wersją:
  # sprzątamy, żeby dysk VPS nie puchł (cache z ostatnich 7 dni zostaje dla szybkich przebudów)
  docker image prune -f >/dev/null || true
  docker builder prune -f --filter until=168h >/dev/null || true
fi

log "Start usług"
"${COMPOSE[@]}" "${PROFILES[@]}" up -d

PY=/opt/hermes/.venv/bin/python
# Jednorazowe kroki bez init-a s6 (--entrypoint ""): na wspólnym wolumenie danych init wznowiłby
# drugi gateway i dashboard. Od razu jako użytkownik hermes (uid 10000), repo tylko do odczytu.
ONEOFF=(run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/tmp
        -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/opt/tars/repo)
log "Walidacja repo"
"${COMPOSE[@]}" "${ONEOFF[@]}" hermes "$PY" /opt/tars/repo/scripts/validate.py

log "Build dystrybucji profili"
"${COMPOSE[@]}" "${ONEOFF[@]}" \
  -v "${TARS_BUILD:-/srv/tars/build}:/out" -v "$COMPOSE_DIR:/opt/tars/compose:ro" \
  -e TARS_HERMES_PYTHON="$PY" \
  hermes "$PY" /opt/tars/repo/scripts/build.py --hermes-src /opt/hermes --out /out \
  --env-file /opt/tars/compose/tars.env --runtime-build-dir /opt/tars/build

log "Instalacja/aktualizacja floty w kontenerze"
EXTRA=()
[[ $RESUME_CRON -eq 1 ]] && EXTRA+=(--resume-cron)
[[ $FIRST -eq 1 ]] && EXTRA+=(--first-run)
docker exec -u hermes tars-hermes bash /opt/tars/repo/scripts/install-fleet.sh "${EXTRA[@]}"

log "Healthchecki narzędzi"
docker exec -u hermes tars-hermes bash /opt/tars/repo/scripts/healthcheck.sh || echo "(są ostrzeżenia, patrz wyżej)"

log "Stan"
docker exec -u hermes tars-hermes hermes profile list || true
docker exec -u hermes tars-hermes hermes -p tars cron list || true
echo
echo "✅ Wdrożenie zakończone. Commit: $(git rev-parse --short HEAD)"
[[ $RESUME_CRON -eq 0 ]] && echo "ℹ Rutyny TARS-a są wstrzymane. Po teście Telegrama: bash scripts/deploy.sh --no-pull --resume-cron"

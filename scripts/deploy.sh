#!/usr/bin/env bash
# Wdrożenie floty Jarvo na VPS (idempotentne). Uruchamiaj z /srv/jarvo/repo jako użytkownik z grupy docker.
#
#   bash scripts/deploy.sh [--first-run] [--no-pull] [--rebuild] [--pull-base] [--no-build] [--resume-cron] [--monitoring]
#
# --rebuild przebudowuje obraz na tej samej wersji Hermesa; --pull-base (i --first-run) pobiera też najnowszy
# obraz bazowy Hermesa. Zmiana infra/ w git pull robi jedno i drugie, zmiana branding/ tylko przebudowę.
# Zanim zbuduje, próbuje pobrać gotowy obraz tej wersji z rejestru (scripts/obraz.sh; JARVO_BUILD_IMAGE=1: zawsze buduj).
# --no-build nigdy nie buduje obrazu (także przy --first-run): jarvo-hermes:local zbudowano wcześniej
# (piaskownica Claude Code, scripts/sandbox-up.sh, gdzie budowanie przez compose nie widzi proxy).
#
# Kroki: git pull → docker compose build/up → walidacja repo → build dystrybucji (w kontenerze)
#        → instalacja/aktualizacja profili (w kontenerze) → healthchecki → podsumowanie.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# stary pomocnik aktualizacji (sprzed zmiany nazwy) podaje TARS_*: przyjmujemy i migrujemy
COMPOSE_DIR="${JARVO_COMPOSE_DIR:-${TARS_COMPOSE_DIR:-/srv/jarvo/compose}}"
JARVO_BUILD="${JARVO_BUILD:-${TARS_BUILD:-}}"
# migracja instalacji TARS → Jarvo (katalogi, env, stare kontenery); idempotentna
eval "$(python3 "$(dirname "${BASH_SOURCE[0]}")/migrate_jarvo.py" host --compose "$COMPOSE_DIR" ${JARVO_BUILD:+--build "$JARVO_BUILD"})"
COMPOSE_DIR="$JARVO_COMPOSE_DIR"; [[ -n "$JARVO_BUILD" ]] || unset JARVO_BUILD
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$COMPOSE_DIR/.env")
PULL=1; REBUILD=0; PULLBASE=0; NOBUILD=0; FIRST=0; RESUME_CRON=0; PROFILES=()
for arg in "$@"; do
  case "$arg" in
    --first-run) FIRST=1; REBUILD=1; PULLBASE=1 ;;
    --no-pull) PULL=0 ;;
    --rebuild) REBUILD=1 ;;
    --pull-base) PULLBASE=1 ;;
    --no-build) NOBUILD=1 ;;
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
# dawny domyślny HERMES_IMAGE (ruchomy latest) → wersja przypięta w repo (infra/Dockerfile) i gotowy obraz z rejestru
if grep -qx 'HERMES_IMAGE=nousresearch/hermes-agent:latest' "$COMPOSE_DIR/.env"; then
  sed -i.bak 's#^HERMES_IMAGE=nousresearch/hermes-agent:latest$#HERMES_IMAGE=#' "$COMPOSE_DIR/.env" && rm -f "$COMPOSE_DIR/.env.bak"
  REBUILD=1
fi
# sufit CPU kontenerów najwyżej tyle, ile procesorów widzi Docker (laptop z 2 rdzeniami, mały VPS, Colima
# z 2 CPU); inaczej Docker odmawia startu: "range of CPUs is from 0.01 to 2.00"
ncpu="$(docker info --format '{{.NCPU}}' 2>/dev/null || true)"
if [[ "$ncpu" =~ ^[1-9][0-9]*$ ]]; then
  for v in HERMES_CPUS=4 ANDROID_CPUS=2 KOMPUTER_CPUS=2; do
    cur="$(sed -n "s/^${v%=*}=//p" "$COMPOSE_DIR/.env" | tail -1)"; cur="${cur:-${v#*=}}"
    if awk -v c="$cur" -v n="$ncpu" 'BEGIN { exit !(c + 0 > n + 0) }'; then
      log "${v%=*}=$cur, a Docker ma $ncpu procesory: ustawiam ${v%=*}=$ncpu"
      if grep -q "^${v%=*}=" "$COMPOSE_DIR/.env"; then
        sed -i.bak "s/^${v%=*}=.*/${v%=*}=$ncpu/" "$COMPOSE_DIR/.env" && rm -f "$COMPOSE_DIR/.env.bak"
      else
        echo "${v%=*}=$ncpu" >> "$COMPOSE_DIR/.env"
      fi
    fi
  done
fi

if [[ $PULL -eq 1 ]]; then
  log "git pull"
  before="$(git rev-parse HEAD)"
  git pull --ff-only
  after="$(git rev-parse HEAD)"
  if [[ "$before" != "$after" ]]; then
    changed="$(git diff --name-only "$before" "$after")"
    if grep -qE '^infra/(Dockerfile|node/|python/|bin/)' <<<"$changed"; then REBUILD=1; PULLBASE=1
    elif grep -qE '^branding/' <<<"$changed"; then REBUILD=1; fi   # ostatnia warstwa obrazu: sekundy
  fi
fi

if [[ $NOBUILD -eq 1 ]]; then
  REBUILD=0
  docker image inspect jarvo-hermes:local >/dev/null 2>&1 || fail "Brak obrazu jarvo-hermes:local (--no-build wymaga gotowego obrazu)."
fi
# gotowy obraz z rejestru (GitHub Actions buduje go dla każdej wersji infra/ i branding/): pobranie zamiast budowy
if [[ $REBUILD -eq 1 ]] && bash "$ROOT/scripts/obraz.sh" pobierz "$COMPOSE_DIR"; then
  REBUILD=0
  git -C "$ROOT" rev-parse HEAD:infra > "$COMPOSE_DIR/.infra-tree" 2>/dev/null || true
  git -C "$ROOT" rev-parse HEAD > "$COMPOSE_DIR/.image-src" 2>/dev/null || true
  docker image prune -f >/dev/null || true
fi
if [[ $REBUILD -eq 1 ]]; then
  log "Budowa obrazu jarvo-hermes (narzędzia agentów)"
  BUILD_ARGS=(); [[ $PULLBASE -eq 1 ]] && BUILD_ARGS+=(--pull)
  "${COMPOSE[@]}" build "${BUILD_ARGS[@]}" hermes
  # z której wersji infra/ zbudowano obraz (local-up przebudowuje tylko, gdy się zmieniła)
  git -C "$ROOT" rev-parse HEAD:infra > "$COMPOSE_DIR/.infra-tree" 2>/dev/null || true
  git -C "$ROOT" rev-parse HEAD > "$COMPOSE_DIR/.image-src" 2>/dev/null || true
  # poprzedni obraz jarvo-hermes (~4,4 GB) zostaje bez nazwy, a cache budowania rośnie z każdą wersją:
  # sprzątamy, żeby dysk VPS nie puchł (cache z ostatnich 7 dni zostaje dla szybkich przebudów)
  docker image prune -f >/dev/null || true
  docker builder prune -f --filter until=168h >/dev/null || true
fi

# telefon testowy włączony (COMPOSE_PROFILES w compose/.env): obraz ekranu (ws-scrcpy) budujemy na nowo, gdy zmieniło
# się infra/android/ od ostatniej budowy (lokalnie i na VPS, niezależnie od git pull w tym przebiegu)
if [[ $NOBUILD -eq 0 ]] && "${COMPOSE[@]}" config --services 2>/dev/null | grep -qx android-ekran; then
  screen_tree="$(git -C "$ROOT" rev-parse HEAD:infra/android 2>/dev/null || echo brak)"
  if [[ "$(cat "$COMPOSE_DIR/.screen-tree" 2>/dev/null)" != "$screen_tree" ]] \
     || ! docker image inspect jarvo-ws-scrcpy:local >/dev/null 2>&1; then
    log "Budowa obrazu ekranu telefonu testowego (ws-scrcpy)"
    "${COMPOSE[@]}" build android-ekran && echo "$screen_tree" > "$COMPOSE_DIR/.screen-tree"
  fi
fi

# Komputer Jarva włączony (profil komputer, docs/KOMPUTER.md): obraz budujemy na miejscu przy pierwszym razie i po zmianie
# infra/komputer/ (ten sam plik .komputer-tree co `jarvo komputer on`); publiczne adresy tego serwera dopisujemy do
# KOMPUTER_BLOKADA, żeby przeglądarka w Komputerze nie sięgała do portów floty i SSH hosta (prywatne blokuje start.sh)
KOMPUTER=0
"${COMPOSE[@]}" config --services 2>/dev/null | grep -qx komputer && KOMPUTER=1
if [[ $KOMPUTER -eq 1 && $NOBUILD -eq 0 ]]; then
  komputer_tree="$(git -C "$ROOT" rev-parse HEAD:infra/komputer 2>/dev/null || echo brak)"
  if [[ "$(cat "$COMPOSE_DIR/.komputer-tree" 2>/dev/null)" != "$komputer_tree" ]] \
     || ! docker image inspect jarvo-komputer:local >/dev/null 2>&1; then
    log "Budowa obrazu Komputera Jarva (pulpit, Chromium, sterownik ekranu)"
    "${COMPOSE[@]}" build komputer && echo "$komputer_tree" > "$COMPOSE_DIR/.komputer-tree"
  fi
fi
if [[ $KOMPUTER -eq 1 && "$(uname -s)" == Linux ]] && ! grep -qi microsoft /proc/version 2>/dev/null; then
  publiczne="$({ hostname -I 2>/dev/null || true; } | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' \
    | grep -vE '^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)' \
    | sort -u | paste -sd, - || true)"
  if [[ "$(sed -n 's/^KOMPUTER_BLOKADA=//p' "$COMPOSE_DIR/.env" | tail -1)" != "$publiczne" ]]; then
    tmp="$(mktemp)"; grep -v '^KOMPUTER_BLOKADA=' "$COMPOSE_DIR/.env" > "$tmp" || true
    echo "KOMPUTER_BLOKADA=$publiczne" >> "$tmp"; cat "$tmp" > "$COMPOSE_DIR/.env"; rm -f "$tmp"
  fi
fi

# dane i build w wolumenach Dockera (macOS): nowy wolumen należy do roota, a kontener pracuje jako hermes (10000)
if grep -q '^JARVO_VOL_HERMES=.' "$COMPOSE_DIR/.env"; then
  "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint "" -u 0 -v "${JARVO_BUILD:-jarvo-build}:/out" hermes \
    chown 10000:10000 /opt/data /out
fi

# instalacja na własnym komputerze: ta wersja Jarvo potrzebuje nowszych programów na hoście (Docker, Colima…)?
# install.sh zapisuje HOST_VERSION przy każdej instalacji i aktualizacji przez `jarvo update`
if [[ -f "$COMPOSE_DIR/.host-version" ]]; then
  hv="$(sed -n 's/^HOST_VERSION=//p' "$ROOT/install.sh")"
  [[ "$(cat "$COMPOSE_DIR/.host-version")" == "$hv" ]] \
    || echo "ℹ Ta wersja Jarvo potrzebuje nowszych programów na komputerze. Uruchom w terminalu: jarvo update"
fi

log "Start usług"
"${COMPOSE[@]}" "${PROFILES[@]}" up -d

PY=/opt/hermes/.venv/bin/python
# Jednorazowe kroki bez init-a s6 (--entrypoint ""): na wspólnym wolumenie danych init wznowiłby
# drugi gateway i dashboard. Od razu jako użytkownik hermes (uid 10000), repo tylko do odczytu.
ONEOFF=(run --rm --no-deps -T --entrypoint "" -u 10000:10000 -e HOME=/tmp
        -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/opt/jarvo/repo)
log "Walidacja repo"
"${COMPOSE[@]}" "${ONEOFF[@]}" hermes "$PY" /opt/jarvo/repo/scripts/validate.py

log "Build dystrybucji profili"
"${COMPOSE[@]}" "${ONEOFF[@]}" \
  -v "${JARVO_BUILD:-/srv/jarvo/build}:/out" -v "$COMPOSE_DIR:/opt/jarvo/compose:ro" \
  -e JARVO_HERMES_PYTHON="$PY" \
  hermes "$PY" /opt/jarvo/repo/scripts/build.py --hermes-src /opt/hermes --out /out \
  --env-file /opt/jarvo/compose/jarvo.env --runtime-build-dir /opt/jarvo/build

log "Instalacja/aktualizacja floty w kontenerze"
EXTRA=()
[[ $RESUME_CRON -eq 1 ]] && EXTRA+=(--resume-cron)
[[ $FIRST -eq 1 ]] && EXTRA+=(--first-run)
docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/install-fleet.sh "${EXTRA[@]}"

log "Healthchecki narzędzi"
docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/healthcheck.sh || echo "(są ostrzeżenia, patrz wyżej)"
if [[ $KOMPUTER -eq 1 ]]; then
  for _ in $(seq 1 45); do docker exec jarvo-komputer /opt/jarvo-komputer/zdrowie.sh >/dev/null 2>&1 && break; sleep 2; done
  if docker exec jarvo-komputer /opt/jarvo-komputer/zdrowie.sh >/dev/null 2>&1 \
     && docker exec jarvo-hermes test -S /opt/jarvo/komputer/rfb.sock \
     && docker exec jarvo-hermes test -S /opt/jarvo/komputer/cua.sock; then
    echo "✓ Komputer Jarva: pulpit i wejście sterownika działają, flota widzi gniazda ekranu i wejścia"
  else
    echo "⚠ Komputer Jarva nie odpowiada (docker logs jarvo-komputer)"
  fi
fi

log "Stan"
docker exec -u hermes jarvo-hermes hermes profile list || true
docker exec -u hermes jarvo-hermes hermes -p jarvo cron list || true
echo
echo "✅ Wdrożenie zakończone. Commit: $(git rev-parse --short HEAD)"
if [[ $RESUME_CRON -eq 0 ]]; then
  # lokalnie (local-up.sh ustawia JARVO_LOCAL_INSTALL=1) wznawia się przez polecenie jarvo, na VPS przez deploy.sh
  if [[ "${JARVO_LOCAL_INSTALL:-0}" == 1 ]]; then
    echo "ℹ Rutyny Jarva (patrol, brief, przegląd tygodnia) są wstrzymane. Włączenie: JARVO_RESUME_CRON=1 jarvo up"
  else
    echo "ℹ Rutyny Jarva są wstrzymane. Po teście Telegrama: bash scripts/deploy.sh --no-pull --resume-cron"
  fi
fi

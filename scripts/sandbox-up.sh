#!/usr/bin/env bash
# Flota Jarvo w piaskownicy Claude Code (chmurowy kontener za proxy TLS): od zera do działającej floty
# jednym poleceniem, żeby każdą zmianę dało się sprawdzić w prawdziwym kontenerze (zasady w CLAUDE.md).
#
#   JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh   # dockerd, obrazy, instalacja, deploy
#   bash scripts/sandbox-up.sh --rebuild                              # wymuś przebudowę obrazów
#   bash scripts/sandbox-up.sh down                                   # zatrzymaj flotę
#
# Kroki:
#   1. dockerd (piaskownica nie ma systemd; demon sam bierze HTTPS_PROXY ze środowiska do pobierania obrazów),
#   2. hermes-ca:test = oficjalny obraz Hermesa + certyfikat proxy w magazynie systemowym,
#   3. jarvo-hermes:local: docker build --network host z HTTPS_PROXY (budowanie przez compose nie widzi proxy);
#      przebudowa tylko przy braku obrazu, --rebuild albo zmianie infra/ od ostatniej budowy,
#   4. instalacja w $JARVO_LOCAL (compose/.env, jarvo.env, sekrety bez kluczy: GUI i narzędzia działają,
#      agenci odpowiedzą po dodaniu klucza w dashboardzie Keys),
#   5. certyfikat proxy w magazynie NSS hermesa ($JARVO_LOCAL/data/hermes/.pki/nssdb): Chromium (Lighthouse, axe,
#      zrzuty, Playwright) nie czyta magazynu systemowego i bez tego każda strona z internetu kończy się
#      ERR_CERT_AUTHORITY_INVALID; odtwarzany tylko po zmianie certyfikatu,
#   6. scripts/deploy.sh --no-pull --no-build (pierwszy raz z --first-run): walidacja, build dystrybucji,
#      instalacja profili, healthchecki.
#
# Tylko do piaskownicy. Na VPS: scripts/deploy.sh, na własnym komputerze: scripts/local-up.sh.
# Weryfikacji TLS nigdzie nie wyłączamy: curl, apt, uv, npm i Python w kontenerze ufają certyfikatowi proxy
# z magazynu systemowego (krok 2), Chromium z magazynu NSS (krok 5).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="${JARVO_LOCAL:-$HOME/jarvo-local}"
CA="${JARVO_PROXY_CA:-/root/.ccr/ca-bundle.crt}"
BASE="${HERMES_IMAGE:-nousresearch/hermes-agent:latest}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$L/compose/.env")
REBUILD=0
log() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m✗ %s\033[0m\n' "$*"; exit 1; }

case "${1:-}" in
  down) "${COMPOSE[@]}" down; exit 0 ;;
  --rebuild) REBUILD=1 ;;
  "") ;;
  *) echo "Nieznana opcja: $1"; exit 2 ;;
esac
[[ -n "${HTTPS_PROXY:-}" && -f "$CA" ]] || fail "Brak HTTPS_PROXY albo $CA: to nie piaskownica Claude Code (użyj scripts/local-up.sh)."
mkdir -p "$L"/{compose,secrets,build,data}

log "dockerd"
if ! docker info >/dev/null 2>&1; then
  nohup dockerd >"$L/dockerd.log" 2>&1 &
  for _ in $(seq 60); do docker info >/dev/null 2>&1 && break; sleep 1; done
  docker info >/dev/null 2>&1 || fail "dockerd nie wstał (log: $L/dockerd.log)"
fi
echo "Docker $(docker version -f '{{.Server.Version}}')"

if [[ $REBUILD -eq 1 ]] || ! docker image inspect hermes-ca:test >/dev/null 2>&1; then
  log "hermes-ca:test ($BASE + certyfikat proxy)"
  ctx="$(mktemp -d)"; trap 'rm -rf "$ctx"' EXIT
  cp "$CA" "$ctx/proxy-ca.crt"
  cat >"$ctx/Dockerfile" <<'EOF'
ARG HERMES_IMAGE
FROM ${HERMES_IMAGE}
USER root
COPY proxy-ca.crt /usr/local/share/ca-certificates/sandbox-proxy-ca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt
EOF
  [[ $REBUILD -eq 1 ]] && docker pull "$BASE"
  docker build --network host --build-arg HERMES_IMAGE="$BASE" -t hermes-ca:test "$ctx"
  REBUILD=1                           # nowa baza → jarvo-hermes:local też od nowa
fi

# commit, z którego zbudowano obraz: przebudowa tylko, gdy od tamtej pory zmieniło się infra/ albo branding/
BUILT="$(cat "$L/compose/.image-src" 2>/dev/null || true)"
if [[ -z "$BUILT" ]] || ! git -C "$ROOT" diff --quiet "$BUILT" HEAD -- infra/Dockerfile infra/node infra/python infra/bin branding 2>/dev/null \
   || ! docker image inspect jarvo-hermes:local >/dev/null 2>&1; then
  REBUILD=1
fi
if [[ $REBUILD -eq 1 ]]; then
  log "jarvo-hermes:local (budowa z proxy, kilkanaście minut za pierwszym razem)"
  docker build --network host --build-arg HERMES_IMAGE=hermes-ca:test \
    --build-arg HTTPS_PROXY="$HTTPS_PROXY" --build-arg https_proxy="$HTTPS_PROXY" \
    --build-arg NO_PROXY="${NO_PROXY:-}" --build-arg no_proxy="${NO_PROXY:-}" \
    -t jarvo-hermes:local -f "$ROOT/infra/Dockerfile" "$ROOT"
  git -C "$ROOT" rev-parse HEAD > "$L/compose/.image-src"
  docker image prune -f >/dev/null || true
fi

if [[ ! -f "$L/compose/.env" ]]; then
  log "Instalacja w $L"
  PASS="$(openssl rand -hex 12)"
  sed -e "s#^JARVO_DATA=.*#JARVO_DATA=$L/data#" -e "s#^JARVO_REPO=.*#JARVO_REPO=$ROOT#" \
      -e "s#^JARVO_BUILD=.*#JARVO_BUILD=$L/build#" -e "s#^JARVO_SECRETS=.*#JARVO_SECRETS=$L/secrets#" \
      -e "s#^HERMES_IMAGE=.*#HERMES_IMAGE=hermes-ca:test#" \
      -e "s#^SEARXNG_SECRET=.*#SEARXNG_SECRET=$(openssl rand -hex 32)#" \
      -e "s#^DASHBOARD_PASSWORD=.*#DASHBOARD_PASSWORD=$PASS#" \
      -e "s#^DASHBOARD_SESSION_SECRET=.*#DASHBOARD_SESSION_SECRET=$(openssl rand -hex 32)#" \
      "$ROOT/infra/env/compose.env.example" > "$L/compose/.env"
  cp "$ROOT/infra/env/jarvo.env.example" "$L/compose/jarvo.env"
  for f in "$ROOT"/infra/env/secrets/*.env.example; do cp "$f" "$L/secrets/$(basename "${f%.example}")"; done
  chgrp -R 10000 "$L/secrets" && chmod 2750 "$L/secrets" && chmod 640 "$L"/secrets/*.env
  chmod 600 "$L/compose/.env"
fi

NSS="$L/data/hermes/.pki/nssdb"                 # $HOME hermesa w kontenerze to /opt/data
CA_SHA="$(sha256sum "$CA" | cut -c1-64)"
if [[ "$(cat "$NSS/.ca-sha" 2>/dev/null)" != "$CA_SHA" ]]; then
  log "certyfikat proxy dla Chromium (NSS)"
  command -v certutil >/dev/null || apt-get install -y -q libnss3-tools >/dev/null \
    || { apt-get update -q >/dev/null && apt-get install -y -q libnss3-tools >/dev/null; }
  rm -rf "$NSS" && mkdir -p "$NSS"
  certutil -N -d "sql:$NSS" --empty-password
  tmp="$(mktemp -d)"
  csplit -s -z -f "$tmp/ca-" "$CA" '/-----BEGIN CERTIFICATE-----/' '{*}'
  i=0
  for c in "$tmp"/ca-*; do i=$((i + 1)); certutil -A -d "sql:$NSS" -t "C,," -n "piaskownica-$i" -i "$c"; done
  rm -rf "$tmp"
  echo "$CA_SHA" > "$NSS/.ca-sha"
fi
# kontener pracuje jako hermes (uid 10000); przy działającej flocie pliki -wal/-shm SQLite potrafią zniknąć w trakcie
# przechodzenia katalogu, więc jedna powtórka (druga porażka to już prawdziwy błąd)
chown -R 10000:10000 "$L/build" "$L/data" 2>/dev/null || chown -R 10000:10000 "$L/build" "$L/data"

FLAGS=(--no-pull --no-build)
[[ -f "$L/.installed" ]] || FLAGS+=(--first-run)
JARVO_COMPOSE_DIR="$L/compose" JARVO_BUILD="$L/build" bash "$ROOT/scripts/deploy.sh" "${FLAGS[@]}"
touch "$L/.installed"

PASS="$(grep '^DASHBOARD_PASSWORD=' "$L/compose/.env" | cut -d= -f2)"
cat <<EOF

✅ Flota działa w piaskownicy.
   Jarvo HQ:   http://localhost:9119/base   login: jarvo   hasło: $PASS
   komenda:    docker exec -u hermes jarvo-hermes <polecenie>   (PATH obrazu ma już Hermesa i narzędzia; bez bash -l)
   ponownie:   JARVO_LOCAL=$L bash scripts/sandbox-up.sh   (przebudowa obrazu tylko po zmianie infra/)
   stop:       JARVO_LOCAL=$L bash scripts/sandbox-up.sh down
EOF

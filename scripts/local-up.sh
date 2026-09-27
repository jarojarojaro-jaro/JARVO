#!/usr/bin/env bash
# Lokalny test floty TARS (Linux / WSL2 z Dockerem). Jedno polecenie:
#
#   bash scripts/local-up.sh            # przygotuj ~/tars-local (raz) i uruchom flotę
#   bash scripts/local-up.sh down       # zatrzymaj
#
# Pyta tylko o klucz OpenRouter (Enter = bez klucza: GUI i narzędzia działają, agenci nie odpowiadają).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="${TARS_LOCAL:-$HOME/tars-local}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$L/compose/.env")

if [[ "${1:-}" == "down" ]]; then "${COMPOSE[@]}" down; exit 0; fi
docker info >/dev/null 2>&1 || { echo "Docker nie działa (uruchom Docker Desktop, włącz integrację WSL)."; exit 1; }

if [[ ! -f "$L/compose/.env" ]]; then
  echo "▶ Przygotowuję $L"
  mkdir -p "$L"/{compose,secrets,build,data}
  read -rsp "Klucz OpenRouter (Enter = pomiń): " KEY; echo
  PASS="$(openssl rand -hex 12)"
  sed -e "s#^TARS_DATA=.*#TARS_DATA=$L/data#" -e "s#^TARS_REPO=.*#TARS_REPO=$ROOT#" \
      -e "s#^TARS_BUILD=.*#TARS_BUILD=$L/build#" -e "s#^TARS_SECRETS=.*#TARS_SECRETS=$L/secrets#" \
      -e "s#^SEARXNG_SECRET=.*#SEARXNG_SECRET=$(openssl rand -hex 32)#" \
      -e "s#^DASHBOARD_PASSWORD=.*#DASHBOARD_PASSWORD=$PASS#" \
      -e "s#^DASHBOARD_SESSION_SECRET=.*#DASHBOARD_SESSION_SECRET=$(openssl rand -hex 32)#" \
      "$ROOT/infra/env/compose.env.example" > "$L/compose/.env"
  cp "$ROOT/infra/env/tars.env.example" "$L/compose/tars.env"
  for f in "$ROOT"/infra/env/secrets/*.env.example; do
    sed "s#^OPENROUTER_API_KEY=.*#OPENROUTER_API_KEY=$KEY#" "$f" > "$L/secrets/$(basename "${f%.example}")"
  done
  sudo chgrp -R 10000 "$L/secrets" && sudo chmod 2750 "$L/secrets" && sudo chmod 640 "$L"/secrets/*.env
  chmod 600 "$L/compose/.env"
fi
# kontener pracuje jako uid 10000 (użytkownik hermes): build i dane muszą być jego
if [[ "$(stat -c %u "$L/build")" != "10000" || "$(stat -c %u "$L/data")" != "10000" ]]; then
  sudo chown -R 10000:10000 "$L/build" "$L/data"
fi

TARS_COMPOSE_DIR="$L/compose" TARS_BUILD="$L/build" bash "$ROOT/scripts/deploy.sh" --first-run --no-pull

PASS="$(grep '^DASHBOARD_PASSWORD=' "$L/compose/.env" | cut -d= -f2)"
cat <<EOF

✅ Flota działa.
   TARS HQ:  http://localhost:9119   login: tars   hasło: $PASS
   czat:     docker exec -it -u hermes tars-hermes hermes -p tars chat
   RAM:      docker stats
   stop:     bash scripts/local-up.sh down
EOF

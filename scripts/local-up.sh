#!/usr/bin/env bash
# Lokalny test floty TARS (Linux / WSL2 z Dockerem). Jedno polecenie:
#
#   bash scripts/local-up.sh            # przygotuj ~/tars-local (raz) i uruchom flotę
#   bash scripts/local-up.sh down       # zatrzymaj
#
# Przy pierwszym uruchomieniu pyta o dostawcę modeli (OpenRouter albo CommandCode) i jego klucz
# (Enter = bez klucza: GUI i narzędzia działają, agenci nie odpowiadają; klucz dodasz potem w Keys).
# Zmiana dostawcy później:  TARS_MODEL_PROVIDER=commandcode bash scripts/local-up.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="${TARS_LOCAL:-$HOME/tars-local}"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$L/compose/.env")

if [[ "${1:-}" == "down" ]]; then "${COMPOSE[@]}" down; exit 0; fi
docker info >/dev/null 2>&1 || { echo "Docker nie działa (uruchom Docker Desktop, włącz integrację WSL)."; exit 1; }

if [[ ! -f "$L/compose/.env" ]]; then
  echo "▶ Przygotowuję $L"
  mkdir -p "$L"/{compose,secrets,build,data}
  echo "Dostawca modeli dla agentów:"
  echo "  1) OpenRouter"
  echo "  2) CommandCode: modele Claude"
  echo "  3) CommandCode: modele otwarte (DeepSeek, Kimi)"
  read -rp "Wybór [1]: " CHOICE
  case "${CHOICE:-1}" in
    2) PROVIDER=commandcode-anthropic; KEYVAR=COMMANDCODE_API_KEY ;;
    3) PROVIDER=commandcode; KEYVAR=COMMANDCODE_API_KEY ;;
    *) PROVIDER=; KEYVAR=OPENROUTER_API_KEY ;;
  esac
  read -rsp "Klucz $KEYVAR (Enter = pomiń): " KEY; echo
  PASS="$(openssl rand -hex 12)"
  sed -e "s#^TARS_DATA=.*#TARS_DATA=$L/data#" -e "s#^TARS_REPO=.*#TARS_REPO=$ROOT#" \
      -e "s#^TARS_BUILD=.*#TARS_BUILD=$L/build#" -e "s#^TARS_SECRETS=.*#TARS_SECRETS=$L/secrets#" \
      -e "s#^SEARXNG_SECRET=.*#SEARXNG_SECRET=$(openssl rand -hex 32)#" \
      -e "s#^DASHBOARD_PASSWORD=.*#DASHBOARD_PASSWORD=$PASS#" \
      -e "s#^DASHBOARD_SESSION_SECRET=.*#DASHBOARD_SESSION_SECRET=$(openssl rand -hex 32)#" \
      "$ROOT/infra/env/compose.env.example" > "$L/compose/.env"
  sed "s#^TARS_MODEL_PROVIDER=.*#TARS_MODEL_PROVIDER=$PROVIDER#" "$ROOT/infra/env/tars.env.example" > "$L/compose/tars.env"
  for f in "$ROOT"/infra/env/secrets/*.env.example; do
    if [[ $KEYVAR == OPENROUTER_API_KEY ]]; then
      sed "s#^OPENROUTER_API_KEY=.*#OPENROUTER_API_KEY=$KEY#" "$f" > "$L/secrets/$(basename "${f%.example}")"
    else
      cp "$f" "$L/secrets/$(basename "${f%.example}")"
    fi
  done
  # klucz innego dostawcy: do głównego .env (host), skąd trafia do wszystkich agentów (scripts/share_keys.py)
  [[ $KEYVAR != OPENROUTER_API_KEY && -n $KEY ]] && echo "$KEYVAR=$KEY" >> "$L/secrets/host.env"
  sudo chgrp -R 10000 "$L/secrets" && sudo chmod 2750 "$L/secrets" && sudo chmod 640 "$L"/secrets/*.env
  chmod 600 "$L/compose/.env"
fi
# zmiana dostawcy w istniejącej instalacji: TARS_MODEL_PROVIDER=... bash scripts/local-up.sh
if [[ -n "${TARS_MODEL_PROVIDER+x}" ]]; then
  grep -q '^TARS_MODEL_PROVIDER=' "$L/compose/tars.env" || echo "TARS_MODEL_PROVIDER=" >> "$L/compose/tars.env"
  sed -i "s#^TARS_MODEL_PROVIDER=.*#TARS_MODEL_PROVIDER=$TARS_MODEL_PROVIDER#" "$L/compose/tars.env"
  echo "▶ Dostawca modeli: ${TARS_MODEL_PROVIDER:-openrouter}"
fi
# kontener pracuje jako uid 10000 (użytkownik hermes): build i dane muszą być jego
if [[ "$(stat -c %u "$L/build")" != "10000" || "$(stat -c %u "$L/data")" != "10000" ]]; then
  sudo chown -R 10000:10000 "$L/build" "$L/data"
fi

TARS_COMPOSE_DIR="$L/compose" TARS_BUILD="$L/build" bash "$ROOT/scripts/deploy.sh" --first-run --no-pull

PASS="$(grep '^DASHBOARD_PASSWORD=' "$L/compose/.env" | cut -d= -f2)"
cat <<EOF

✅ Flota działa.
   TARS HQ:  http://localhost:9119/base   login: tars   hasło: $PASS
   czat:     docker exec -it -u hermes tars-hermes hermes -p tars chat
   RAM:      docker stats
   stop:     bash scripts/local-up.sh down
EOF

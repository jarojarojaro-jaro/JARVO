#!/usr/bin/env bash
# Red team floty: ataki promptfoo na agentów w działającym kontenerze (środowisko testowe!).
#
#   bash scripts/redteam.sh                    # wszystkie ataki
#   bash scripts/redteam.sh --filtr ads        # tylko testy, których opis zawiera „ads”
#
# Każdy atak to prawdziwa rozmowa z agentem (kosztuje tokeny modelu). Ocena bez modelu-sędziego: po komendach
# z przebiegu sesji (czy agent coś wykonał) i po wycieku sekretów. Wynik: tabela w konsoli + JSON w kontenerze.
set -euo pipefail
FILTR=""
[[ "${1:-}" == "--filtr" ]] && FILTR="${2:-}"
C=${JARVO_CONTAINER:-jarvo-hermes}
docker exec -u hermes -e FILTR="$FILTR" "$C" bash -c '
  set -e
  export PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH HOME=/opt/data/jarvo/redteam PROMPTFOO_DISABLE_TELEMETRY=1 \
         PROMPTFOO_DISABLE_UPDATE=1 PROMPTFOO_PYTHON=python3 npm_config_update_notifier=false
  mkdir -p "$HOME" && cd "$HOME"
  cp -r /opt/jarvo/repo/security/redteam/. .
  ARGS=(eval -c promptfooconfig.yaml --output wynik.json --no-cache --no-progress-bar)
  [[ -n "$FILTR" ]] && ARGS+=(--filter-pattern "$FILTR")
  PF=/opt/data/jarvo/tools/promptfoo
  if [[ ! -x "$PF/node_modules/.bin/promptfoo" ]]; then       # przypięta wersja, raz; potem z dysku
    mkdir -p "$PF" && (cd "$PF" && echo "{\"private\":true}" > package.json && npm install --no-audit --no-fund --silent promptfoo@0.123.1)
  fi
  "$PF/node_modules/.bin/promptfoo" "${ARGS[@]}" >eval.log 2>&1 || true
  python3 podsumowanie.py wynik.json
'

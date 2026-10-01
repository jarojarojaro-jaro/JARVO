#!/usr/bin/env bash
# Przypina obrazy usług i Hermesa do digestów (powtarzalne wdrożenia). Uruchom po udanym pierwszym wdrożeniu,
# a potem przy świadomej aktualizacji. Nadpisuje zmienne IMAGE_* i HERMES_IMAGE w /srv/jarvo/compose/.env.
set -euo pipefail
ENV_FILE="${1:-/srv/jarvo/compose/.env}"
[[ -f "$ENV_FILE" ]] || { echo "Brak $ENV_FILE"; exit 1; }

pin() {  # pin <ZMIENNA> <obraz:tag>
  local var="$1" ref="$2" digest
  docker pull -q "$ref" >/dev/null
  digest="$(docker image inspect --format '{{index .RepoDigests 0}}' "$ref")"
  if grep -q "^$var=" "$ENV_FILE"; then sed -i "s#^$var=.*#$var=$digest#" "$ENV_FILE"; else echo "$var=$digest" >> "$ENV_FILE"; fi
  echo "  $var=$digest"
}

current() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2- | sed 's/@sha256:.*//'; }

pin HERMES_IMAGE "$(current HERMES_IMAGE || echo nousresearch/hermes-agent:latest)"
pin IMAGE_SEARXNG "$(current IMAGE_SEARXNG || echo searxng/searxng:latest)"
pin IMAGE_VALKEY "$(current IMAGE_VALKEY || echo valkey/valkey:8-alpine)"
# telefon testowy tylko, gdy włączony (obrazy 1,5–2,7 GB)
if grep -qE '^COMPOSE_PROFILES=(.*,)?android(,|$)' "$ENV_FILE"; then
  pin IMAGE_REDROID "$(current IMAGE_REDROID || echo redroid/redroid:14.0.0_64only-latest)"
fi
if grep -qE '^COMPOSE_PROFILES=.*android-kvm' "$ENV_FILE"; then
  pin IMAGE_ANDROID_EMULATOR "$(current IMAGE_ANDROID_EMULATOR || echo halimqarroum/docker-android:api-33)"
fi
echo "✅ Przypięte. Następny deploy użyje dokładnie tych obrazów (przebuduj: deploy.sh --rebuild)."

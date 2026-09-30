#!/usr/bin/env bash
# Flota Jarvo na własnym komputerze (Linux / WSL2 / macOS z Dockerem). Zwykle przez polecenie `jarvo`
# (bin/jarvo) albo install.sh; prosto z klonu:
#
#   bash scripts/local-up.sh              # przygotuj ~/jarvo-local (raz) i uruchom flotę
#   bash scripts/local-up.sh down         # zatrzymaj
#   bash scripts/local-up.sh --prepare    # tylko przygotuj katalog (env, sekrety), floty nie uruchamiaj
#
# Przy pierwszym uruchomieniu pyta o dostawcę modeli (OpenRouter, CommandCode albo OpenAI przez logowanie ChatGPT)
# i jego klucz (Enter = bez klucza: GUI i narzędzia działają, agenci nie odpowiadają; klucz dodasz potem w Keys).
# Bez pytań: JARVO_PROVIDER=openrouter|commandcode-anthropic|commandcode|openai-codex, JARVO_KEY=…, JARVO_YES=1
# (same domyślne: OpenRouter bez klucza). Klucz nigdy nie jest wypisywany.
# Zmiana dostawcy później:  JARVO_MODEL_PROVIDER=commandcode bash scripts/local-up.sh
# JARVO_NO_BUILD=1: obraz jarvo-hermes:local jest już gotowy (docker load, rejestr): nigdy nie buduj.
# JARVO_LOCAL: katalog instalacji (domyślnie ~/jarvo-local).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L="${JARVO_LOCAL:-$HOME/jarvo-local}"
SUDO=; [[ $(id -u) -eq 0 ]] || SUDO=sudo
# instalacja sprzed zmiany nazwy (~/tars-local): przeniesienie, env, stare kontenery w dół
OLD_L="${TARS_LOCAL:-$HOME/tars-local}"
if [[ -d "$OLD_L/compose" && ! -e "$L" && "$(basename "$OLD_L")" == "tars-local" && "$(basename "$L")" == "jarvo-local" ]]; then
  python3 "$ROOT/scripts/migrate_jarvo.py" host --compose "$OLD_L/compose" >/dev/null
fi
# macOS (BSD) i Linux (GNU) różnią się stat, sed -i i setsid
owner() { stat -c %u "$1" 2>/dev/null || stat -f %u "$1"; }
sedi() { if sed --version >/dev/null 2>&1; then sed -i "$@"; else sed -i '' "$@"; fi; }
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml" --env-file "$L/compose/.env")

PREPARE=0
case "${1:-}" in
  down)
    [[ -f "$L/updater.pid" ]] && kill "$(cat "$L/updater.pid")" 2>/dev/null || true
    "${COMPOSE[@]}" down; exit 0 ;;
  --prepare) PREPARE=1 ;;
  "") ;;
  *) echo "Nieznana opcja: $1 (down | --prepare)"; exit 2 ;;
esac
docker info >/dev/null 2>&1 || { echo "Docker nie działa (Linux: sudo systemctl start docker; macOS: Docker Desktop; WSL: sudo service docker start)."; exit 1; }

if [[ ! -f "$L/compose/.env" ]]; then
  echo "▶ Przygotowuję $L"
  mkdir -p "$L"/{compose,secrets,build,data}
  CHOICE="${JARVO_PROVIDER:-}"
  case "$CHOICE" in
    openrouter|1) CHOICE=1 ;;
    commandcode-anthropic|2) CHOICE=2 ;;
    commandcode|3) CHOICE=3 ;;
    openai-codex|openai|4) CHOICE=4 ;;
    "")
      if [[ "${JARVO_YES:-0}" == 1 ]]; then CHOICE=1
      else
        echo "Dostawca modeli dla agentów:"
        echo "  1) OpenRouter"
        echo "  2) CommandCode: modele Claude"
        echo "  3) CommandCode: modele otwarte (DeepSeek, Kimi)"
        echo "  4) OpenAI: logowanie ChatGPT (bez klucza; zaloguj się w dashboardzie: Models → Login)"
        read -rp "Wybór [1]: " CHOICE
      fi ;;
    *) echo "Nieznany JARVO_PROVIDER: $CHOICE (openrouter, commandcode-anthropic, commandcode, openai-codex)"; exit 2 ;;
  esac
  case "${CHOICE:-1}" in
    2) PROVIDER=commandcode-anthropic; KEYVAR=COMMANDCODE_API_KEY ;;
    3) PROVIDER=commandcode; KEYVAR=COMMANDCODE_API_KEY ;;
    4) PROVIDER=; KEYVAR= ;;                      # puste = domyślny dostawca z fleet.yaml (openai-codex)
    *) PROVIDER=openrouter; KEYVAR=OPENROUTER_API_KEY ;;
  esac
  KEY="${JARVO_KEY:-}"
  if [[ -n $KEYVAR && -z $KEY && "${JARVO_YES:-0}" != 1 ]]; then read -rsp "Klucz $KEYVAR (Enter = pomiń): " KEY; echo; fi
  [[ -n $KEYVAR && -z $KEY ]] && echo "ℹ Bez klucza: GUI i narzędzia działają, agenci odpowiedzą po dodaniu klucza w dashboardzie (Keys)."
  PASS="$(openssl rand -hex 12)"
  sed -e "s#^JARVO_DATA=.*#JARVO_DATA=$L/data#" -e "s#^JARVO_REPO=.*#JARVO_REPO=$ROOT#" \
      -e "s#^JARVO_BUILD=.*#JARVO_BUILD=$L/build#" -e "s#^JARVO_SECRETS=.*#JARVO_SECRETS=$L/secrets#" \
      -e "s#^SEARXNG_SECRET=.*#SEARXNG_SECRET=$(openssl rand -hex 32)#" \
      -e "s#^DASHBOARD_PASSWORD=.*#DASHBOARD_PASSWORD=$PASS#" \
      -e "s#^DASHBOARD_SESSION_SECRET=.*#DASHBOARD_SESSION_SECRET=$(openssl rand -hex 32)#" \
      "$ROOT/infra/env/compose.env.example" > "$L/compose/.env"
  sed "s#^JARVO_MODEL_PROVIDER=.*#JARVO_MODEL_PROVIDER=$PROVIDER#" "$ROOT/infra/env/jarvo.env.example" > "$L/compose/jarvo.env"
  for f in "$ROOT"/infra/env/secrets/*.env.example; do
    if [[ $KEYVAR == OPENROUTER_API_KEY ]]; then
      sed "s#^OPENROUTER_API_KEY=.*#OPENROUTER_API_KEY=$KEY#" "$f" > "$L/secrets/$(basename "${f%.example}")"
    else
      cp "$f" "$L/secrets/$(basename "${f%.example}")"
    fi
  done
  # klucz innego dostawcy: do głównego .env (host), skąd trafia do wszystkich agentów (scripts/share_keys.py)
  [[ $KEYVAR != OPENROUTER_API_KEY && -n $KEY ]] && echo "$KEYVAR=$KEY" >> "$L/secrets/host.env"
  # sekrety czyta tylko użytkownik hermes w kontenerze (uid/gid 10000)
  $SUDO chgrp -R 10000 "$L/secrets" && $SUDO chmod 2750 "$L/secrets" && $SUDO chmod 640 "$L"/secrets/*.env
  chmod 600 "$L/compose/.env"
fi
# zmiana dostawcy w istniejącej instalacji: JARVO_MODEL_PROVIDER=... bash scripts/local-up.sh
if [[ -n "${JARVO_MODEL_PROVIDER+x}" ]]; then
  grep -q '^JARVO_MODEL_PROVIDER=' "$L/compose/jarvo.env" || echo "JARVO_MODEL_PROVIDER=" >> "$L/compose/jarvo.env"
  sedi "s#^JARVO_MODEL_PROVIDER=.*#JARVO_MODEL_PROVIDER=$JARVO_MODEL_PROVIDER#" "$L/compose/jarvo.env"
  echo "▶ Dostawca modeli: ${JARVO_MODEL_PROVIDER:-openai-codex (domyślny z fleet.yaml)}"
fi
# kontener pracuje jako uid 10000 (użytkownik hermes): build i dane muszą być jego
if [[ "$(owner "$L/build")" != "10000" || "$(owner "$L/data")" != "10000" ]]; then
  $SUDO chown -R 10000:10000 "$L/build" "$L/data"
fi
if [[ $PREPARE -eq 1 ]]; then echo "✅ Katalog $L gotowy (env, sekrety). Uruchomienie: jarvo up"; exit 0; fi

# pierwsza instalacja raz; później przebudowa obrazu tylko, gdy zmieniło się to, z czego się go buduje
# (Dockerfile, pakiety, skrypty w obrazie, branding i tłumaczenie dashboardu; ta ostatnia warstwa buduje się
# w kilka sekund). Sama zmiana docker-compose.yml (np. nowy port) odtwarza kontener bez budowy.
FLAGS=(--no-pull)
BUILT="$(cat "$L/compose/.image-src" 2>/dev/null || true)"   # commit, z którego zbudowano obraz (deploy.sh)
TREE="$(cat "$L/compose/.infra-tree" 2>/dev/null || true)"   # starsze instalacje: drzewo infra/ z budowy
infra_changed() {
  if [[ -n "$BUILT" ]]; then ! git -C "$ROOT" diff --quiet "$BUILT" HEAD -- infra/Dockerfile infra/node infra/python infra/bin 2>/dev/null
  elif [[ -n "$TREE" ]]; then ! git -C "$ROOT" diff --quiet "$TREE" HEAD:infra -- Dockerfile node python bin 2>/dev/null
  else true; fi
}
brand_changed() { [[ -z "$BUILT" ]] || ! git -C "$ROOT" diff --quiet "$BUILT" HEAD -- branding 2>/dev/null; }
if [[ "${JARVO_NO_BUILD:-0}" == 1 ]]; then
  FLAGS+=(--no-build)               # gotowy obraz (docker load, rejestr): deploy.sh sprawdza, że istnieje
  [[ -f "$L/.installed" ]] || FLAGS+=(--first-run)
elif [[ ! -f "$L/.installed" ]]; then
  FLAGS+=(--first-run)
elif infra_changed; then
  FLAGS+=(--rebuild --pull-base)
elif brand_changed; then
  FLAGS+=(--rebuild)                # tylko branding/tłumaczenie: ta sama wersja Hermesa, kilka sekund
fi
JARVO_COMPOSE_DIR="$L/compose" JARVO_BUILD="$L/build" bash "$ROOT/scripts/deploy.sh" "${FLAGS[@]}"
touch "$L/.installed"

# pomocnik aktualizacji: przycisk „Aktualizuj” w dashboardzie (git pull + deploy na prośbę z panelu).
# Usługa systemd użytkownika (jarvo autostart on) albo proces w tle do wylogowania.
if [[ -f "$L/updater.pid" ]] && kill -0 "$(cat "$L/updater.pid")" 2>/dev/null; then kill "$(cat "$L/updater.pid")" || true; fi
rm -f "$L/updater.pid"
if systemctl --user is-enabled jarvo-updater.service >/dev/null 2>&1; then
  systemctl --user restart jarvo-updater.service
  echo "▶ Pomocnik aktualizacji: usługa jarvo-updater (systemd)"
else
  DETACH=(); command -v setsid >/dev/null && DETACH=(setsid)
  JARVO_AUTO_UPDATE="${JARVO_AUTO_UPDATE:-0}" nohup ${DETACH[@]+"${DETACH[@]}"} python3 "$ROOT/scripts/updater.py" --mode local --compose "$L/compose" --build "$L/build" \
    >> "$L/updater.log" 2>&1 < /dev/null &
  echo $! > "$L/updater.pid"
fi

PASS="$(grep '^DASHBOARD_PASSWORD=' "$L/compose/.env" | cut -d= -f2)"
JARVO=jarvo; command -v jarvo >/dev/null 2>&1 || JARVO="bash $ROOT/bin/jarvo"
cat <<EOF

✅ Flota działa.
   Jarvo HQ:   http://localhost:9119/base   login: jarvo   hasło: $PASS
   polecenia:  $JARVO status | logs | chat | update | down   ($JARVO help: wszystkie)
   RAM:        docker stats
EOF

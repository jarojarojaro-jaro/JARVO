#!/usr/bin/env bash
# Instalacja/aktualizacja floty WEWNĄTRZ kontenera tars-hermes (jako użytkownik hermes).
# Wołane przez scripts/deploy.sh:  docker exec -u hermes tars-hermes bash /opt/tars/repo/scripts/install-fleet.sh
#
#   --first-run     dodatkowo: inicjalizacja tablicy kanban i szablonów wiedzy
#   --resume-cron   wznawia rutyny TARS-a (po sprawdzeniu, że Telegram działa)
#   --no-restart    bez restartu gatewaya (staging evals: dane izolowane, gateway nie działa)
set -euo pipefail

BUILD=/opt/tars/build
SECRETS=/opt/tars/secrets
REPO=/opt/tars/repo
DATA=/opt/data
PY=/opt/hermes/.venv/bin/python
FIRST=0; RESUME=0; RESTART=1
for a in "$@"; do
  case "$a" in --first-run) FIRST=1 ;; --resume-cron) RESUME=1 ;; --no-restart) RESTART=0 ;; esac
done

log() { printf '▶ %s\n' "$*"; }
[[ -f "$BUILD/BUILD.json" ]] || { echo "Brak $BUILD/BUILD.json: najpierw scripts/build.py"; exit 1; }
if [[ -d "$SECRETS" ]] && ! ls "$SECRETS" >/dev/null 2>&1; then
  echo "✗ $SECRETS jest nieczytelny dla użytkownika $(id -un) (uid $(id -u)). Na hoście:"
  echo "  sudo chgrp -R 10000 /srv/tars/secrets && sudo chmod 2750 /srv/tars/secrets && sudo chmod 640 /srv/tars/secrets/*.env"
  exit 1
fi
for f in "$SECRETS"/*.env; do
  [[ -e "$f" && ! -r "$f" ]] && { echo "✗ $f nieczytelny (uprawnienia): sudo chgrp 10000 $f && sudo chmod 640 $f"; exit 1; }
done
AGENTS=$($PY -c "import json;print(' '.join(a['agent'] for a in json.load(open('$BUILD/BUILD.json'))['agents']))")

# 1. katalogi floty i szablony wiedzy
log "Katalogi floty"
mkdir -p "$DATA/tars/missions" "$DATA/tars/state" "$DATA/tars/knowledge/brands" "$DATA/tars/knowledge/user"
for a in $AGENTS; do mkdir -p "$DATA/tars/workspaces/$a"; done
[[ -f "$DATA/tars/missions/INDEX.md" ]] || cp "$BUILD/profiles/tars/skills/fleet/mission-ledger/references/INDEX.template.md" "$DATA/tars/missions/INDEX.md"
rm -rf "$DATA/tars/knowledge/brands/_szablon" && cp -r "$REPO/knowledge/brands/_szablon" "$DATA/tars/knowledge/brands/_szablon"
[[ -f "$DATA/tars/knowledge/user/USER.md" ]] || cp "$BUILD/profiles/tars/skills/fleet/onboarding-interview/references/USER.template.md" "$DATA/tars/knowledge/user/USER.md"

# 2. profil hosta: config (scalanie kluczy floty), SOUL, sekrety
log "Profil hosta"
# pierwsza instalacja: obraz zasiał config.yaml przykładowym modelem → wymuszamy model floty
MERGE_FLAGS=()
[[ $FIRST -eq 1 ]] && MERGE_FLAGS+=(--force-model)
$PY "$REPO/scripts/merge_host_config.py" "$BUILD/host/config.yaml" "$DATA/config.yaml" "${MERGE_FLAGS[@]+"${MERGE_FLAGS[@]}"}"
cp "$BUILD/host/SOUL.md" "$DATA/SOUL.md"
if [[ -f "$SECRETS/host.env" ]]; then
  $PY "$REPO/scripts/merge_env.py" "$SECRETS/host.env" "$DATA/.env"
fi

# 3. profile agentów
for a in $AGENTS; do
  src="$BUILD/profiles/$a"
  if [[ -d "$DATA/profiles/$a" && -f "$DATA/profiles/$a/distribution.yaml" ]]; then
    log "Aktualizacja profilu $a"
    hermes profile update "$a" --force-config --yes
  else
    log "Instalacja profilu $a"
    hermes profile install "$src" --yes --alias
  fi
  # usuń skille floty/vendorowane, których nie ma już w buildzie (skille utworzone przez agenta zostają)
  $PY "$REPO/scripts/prune_skills.py" "$src/skills" "$DATA/profiles/$a/skills"
  if [[ -f "$SECRETS/$a.env" ]]; then
    $PY "$REPO/scripts/merge_env.py" "$SECRETS/$a.env" "$DATA/profiles/$a/.env"
  else
    echo "  ! brak $SECRETS/$a.env (agent nie ma klucza OpenRouter)"
  fi
done

# 4. tablica kanban
if [[ $FIRST -eq 1 || ! -f "$DATA/kanban.db" ]]; then
  log "Tablica kanban"
  hermes kanban init
fi

# 5. rutyny
if [[ $RESUME -eq 1 ]]; then
  log "Wznawiam rutyny TARS-a"
  for job in tars-patrol tars-daily-brief tars-weekly-review tars-knowledge-freshness; do
    hermes -p tars cron resume "$job" || echo "  ! nie udało się wznowić $job"
  done
fi

# 6. restart gatewaya (nowe trasy, profile, skille od nowej sesji); w kontenerze przez s6
if [[ $RESTART -eq 1 ]]; then
  log "Restart gatewaya"
  hermes gateway restart || echo "  ! restart gatewaya nieudany: sprawdź 'hermes gateway status'"
fi
echo "✅ Flota zainstalowana: $AGENTS"

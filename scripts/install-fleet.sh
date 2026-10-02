#!/usr/bin/env bash
# Instalacja/aktualizacja floty WEWNĄTRZ kontenera jarvo-hermes (jako użytkownik hermes).
# Wołane przez scripts/deploy.sh:  docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/install-fleet.sh
#
#   --first-run     dodatkowo: inicjalizacja tablicy kanban i szablonów wiedzy
#   --resume-cron   wznawia rutyny Jarva (po sprawdzeniu, że Telegram działa)
#   --no-restart    bez restartu gatewaya (staging evals: dane izolowane, gateway nie działa)
set -euo pipefail

BUILD=/opt/jarvo/build
SECRETS=/opt/jarvo/secrets
REPO=/opt/jarvo/repo
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
  echo "  sudo chgrp -R 10000 /srv/jarvo/secrets && sudo chmod 2750 /srv/jarvo/secrets && sudo chmod 640 /srv/jarvo/secrets/*.env"
  exit 1
fi
for f in "$SECRETS"/*.env; do
  [[ -e "$f" && ! -r "$f" ]] && { echo "✗ $f nieczytelny (uprawnienia): sudo chgrp 10000 $f && sudo chmod 640 $f"; exit 1; }
done
# migracja danych i profili sprzed zmiany nazwy (TARS → Jarvo): sesje i pamięć przechodzą z profilem
$PY "$REPO/scripts/migrate_jarvo.py" container --data "$DATA" || echo "  ! migracja Jarvo z ostrzeżeniami (patrz wyżej)"
AGENTS=$($PY -c "import json;print(' '.join(a['agent'] for a in json.load(open('$BUILD/BUILD.json'))['agents']))")

# 1. katalogi floty i szablony wiedzy
log "Katalogi floty"
mkdir -p "$DATA/jarvo/missions" "$DATA/jarvo/state" "$DATA/jarvo/knowledge/brands" "$DATA/jarvo/knowledge/user"
for a in $AGENTS; do mkdir -p "$DATA/jarvo/workspaces/$a"; done
[[ -f "$DATA/jarvo/missions/INDEX.md" ]] || cp "$BUILD/profiles/jarvo/skills/fleet/mission-ledger/references/INDEX.template.md" "$DATA/jarvo/missions/INDEX.md"
rm -rf "$DATA/jarvo/knowledge/brands/_szablon" && cp -r "$REPO/knowledge/brands/_szablon" "$DATA/jarvo/knowledge/brands/_szablon"
[[ -f "$DATA/jarvo/knowledge/user/USER.md" ]] || cp "$BUILD/profiles/jarvo/skills/fleet/onboarding-interview/references/USER.template.md" "$DATA/jarvo/knowledge/user/USER.md"

# 1b. skarbiec wiedzy (docs/WIEDZA.md): huby agentów z buildu, SCHEMA, INDEX, docs repo jako źródła; 0 tokenów, git na punkty zapisu
log "Skarbiec wiedzy"
$PY "$REPO/wiedza/wiedza.py" --skarbiec "$DATA/jarvo/knowledge" --stan "$DATA/jarvo/state" zasiej --fleet "$BUILD/wiedza/fleet.json" --docs "$REPO/docs"

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
    $PY "$REPO/scripts/profile_model.py" snapshot "$DATA/profiles/$a"
    # źródło aktualizacji zawsze = bieżący build (po migracji TARS → Jarvo zostawała stara ścieżka /opt/tars/…)
    sed -i "s#^source:.*#source: $src#" "$DATA/profiles/$a/distribution.yaml"
    hermes profile update "$a" --force-config --yes
    $PY "$REPO/scripts/profile_model.py" restore "$DATA/profiles/$a"
  else
    log "Instalacja profilu $a"
    hermes profile install "$src" --yes --alias
    $PY "$REPO/scripts/profile_model.py" restore "$DATA/profiles/$a"
  fi
  # usuń skille floty/vendorowane, których nie ma już w buildzie (skille utworzone przez agenta zostają)
  $PY "$REPO/scripts/prune_skills.py" "$src/skills" "$DATA/profiles/$a/skills"
  if [[ -f "$SECRETS/$a.env" ]]; then
    $PY "$REPO/scripts/merge_env.py" "$SECRETS/$a.env" "$DATA/profiles/$a/.env"
  else
    echo "  ! brak $SECRETS/$a.env (agent nie ma klucza OpenRouter)"
  fi
done

# 3b. klucze API profili: multipleksowany gateway obsługuje /p/<profil>/ tylko z własnym API_SERVER_KEY
#     profilu (z niego korzysta Jarvo HQ do rozmów z agentami). Generujemy brakujące, istniejących nie ruszamy.
for a in $AGENTS; do
  envf="$DATA/profiles/$a/.env"
  if ! grep -qE '^API_SERVER_KEY=.{16,}' "$envf" 2>/dev/null; then
    [[ -s "$envf" && -n "$(tail -c1 "$envf")" ]] && echo >> "$envf"   # plik bez końcowego \n
    echo "API_SERVER_KEY=$($PY -c 'import secrets; print(secrets.token_hex(32))')" >> "$envf"
    chmod 600 "$envf"
    echo "  + API_SERVER_KEY dla $a"
  fi
done

# 3b2. impeccable (detektor „znaków AI” w projektach): program w wersji z VERSION skilla, raz, do trwałego katalogu
IMP_HOME="$DATA/jarvo/narzedzia/impeccable"
for a in $AGENTS; do
  imp="$DATA/profiles/$a/skills/design/impeccable/scripts/impeccable"
  [[ -f "$imp" ]] || continue
  envf="$DATA/profiles/$a/.env"
  grep -q '^IMPECCABLE_HOME=' "$envf" 2>/dev/null || echo "IMPECCABLE_HOME=$IMP_HOME" >> "$envf"
  mkdir -p "$IMP_HOME"
  IMPECCABLE_HOME="$IMP_HOME" sh "$imp" --version >/dev/null 2>&1 && echo "  ✓ impeccable ($a)" \
    || echo "  ! impeccable: nie pobrano programu (sieć?); pobierze się przy pierwszym użyciu"
done

# Podmiana wtyczki z buildu (ta sama treść = stara kopia zostaje). O restarcie dashboardu decyduje odcisk na końcu.
put_plugin() {
  local src="$BUILD/plugins/$1" dst="$DATA/plugins/$1"
  mkdir -p "$DATA/plugins"
  if [[ -d "$dst" ]] && diff -rq -x __pycache__ "$src" "$dst" >/dev/null 2>&1; then
    echo "  = $1 bez zmian"
    return
  fi
  rm -rf "$dst.new" && cp -r "$src" "$dst.new"
  rm -rf "$dst" && mv "$dst.new" "$dst"
}
# Odcisk treści wtyczek panelu (bez __pycache__): porównywany z odciskiem z ostatniego restartu dashboardu.
odcisk_wtyczek() {
  local d; local -a dirs=()
  for d in jarvo-hq jarvo-wiedza; do [[ -d "$DATA/plugins/$d" ]] && dirs+=("$d"); done
  (( ${#dirs[@]} )) || return 0
  (cd "$DATA/plugins" && find "${dirs[@]}" -type f ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
}

# 3c. Jarvo HQ: plugin dashboardu (zakładka BASE, :9119/base)
if [[ -d "$BUILD/plugins/jarvo-hq" ]]; then
  log "Jarvo HQ (plugin dashboardu)"
  put_plugin jarvo-hq
  # pluginy użytkownika muszą być jawnie włączone (zabezpieczenie Hermesa)
  hermes plugins enable jarvo-hq >/dev/null 2>&1 || $PY "$REPO/scripts/enable_plugin.py" "$DATA/config.yaml" jarvo-hq
fi

# 3c'. skarbiec wiedzy: wtyczka jarvo-wiedza (docs/WIEDZA.md). Dostawca pamięci każdego profilu (memory.provider w config.yaml
# profilu z buildu); Hermes szuka dostawców w <HERMES_HOME profilu>/plugins/, więc jedna kopia + dowiązanie w każdym profilu.
if [[ -d "$BUILD/plugins/jarvo-wiedza" ]]; then
  log "Wtyczka jarvo-wiedza (skarbiec wiedzy)"
  put_plugin jarvo-wiedza             # zmiana = restart dashboardu na końcu (zakładka „Wiedza”)
  for a in $AGENTS; do
    mkdir -p "$DATA/profiles/$a/plugins"
    ln -sfn "$DATA/plugins/jarvo-wiedza" "$DATA/profiles/$a/plugins/jarvo-wiedza"
  done
  # zakładka „Wiedza” w dashboardzie (dashboard/manifest.json): wtyczka włączona w config hosta jak Jarvo HQ
  hermes plugins enable jarvo-wiedza >/dev/null 2>&1 || $PY "$REPO/scripts/enable_plugin.py" "$DATA/config.yaml" jarvo-wiedza
fi

# 3d. branding terminala: skórka "jarvo" dla hosta i każdego profilu (display.skin w config.yaml)
if [[ -f "$REPO/branding/skin-jarvo.yaml" ]]; then
  for home in "$DATA" "$DATA"/profiles/*/; do
    [[ -d "$home" ]] || continue
    mkdir -p "$home/skins" && cp -f "$REPO/branding/skin-jarvo.yaml" "$home/skins/jarvo.yaml"
  done
fi

# 3e. motywy dashboardu „Fosfor” (jeden kolor → cały wygląd; lista w branding/fosfor/palettes.yaml)
if [[ -f "$REPO/branding/fosfor/palettes.yaml" ]]; then
  $PY "$REPO/scripts/install_themes.py" "$REPO" "$DATA"
fi

# 3f. wspólne klucze: klucze dostawców/narzędzi z głównego .env do każdego agenta (na żywo pilnuje ich Jarvo HQ)
$PY "$REPO/scripts/share_keys.py" "$DATA"

# 4. tablica kanban
if [[ $FIRST -eq 1 || ! -f "$DATA/kanban.db" ]]; then
  log "Tablica kanban"
  hermes kanban init
fi

# 5. rutyny
if [[ $RESUME -eq 1 ]]; then
  log "Wznawiam rutyny Jarva"
  for job in jarvo-patrol jarvo-daily-brief jarvo-weekly-review jarvo-knowledge-freshness; do
    hermes -p jarvo cron resume "$job" || echo "  ! nie udało się wznowić $job"
  done
fi

# 6. restart gatewaya (nowe trasy, profile, skille, klucze API od nowej sesji); w kontenerze przez s6
if [[ $RESTART -eq 1 ]]; then
  log "Restart gatewaya"
  hermes gateway restart || echo "  ! restart gatewaya nieudany: sprawdź 'hermes gateway status'"
  # Dashboard czyta listę wtyczek (zakładki Baza, Wiedza) i montuje ich backendy raz, przy starcie procesu. Restart, gdy
  # wtyczki na dysku różnią się od tych, z którymi był ostatnio restartowany, także gdy poprzednia instalacja skopiowała
  # wtyczkę i nie dotarła do restartu. Te same wtyczki: bez restartu, otwarty panel się nie rozłącza.
  ODCISK="$(odcisk_wtyczek)"
  if [[ -n "$ODCISK" && -d /run/service/dashboard && "$ODCISK" != "$(cat "$DATA/plugins/.odcisk-panelu" 2>/dev/null || true)" ]]; then
    if /command/s6-svc -r /run/service/dashboard 2>/dev/null; then
      echo "$ODCISK" > "$DATA/plugins/.odcisk-panelu"; echo "  ↻ dashboard (wtyczki Jarvo HQ i Wiedza)"
    else
      echo "  ! restart dashboardu nieudany"
    fi
  fi
fi
echo "✅ Flota zainstalowana: $AGENTS"

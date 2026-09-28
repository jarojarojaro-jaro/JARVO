#!/usr/bin/env bash
# Miesięczny test odtworzenia backupu (cron hosta: 40 4 1 * *). Odtwarza ostatni snapshot do katalogu
# tymczasowego i sprawdza, czy kluczowe pliki są czytelne. Wynik → /srv/jarvo/backups/restore-test.log.
set -euo pipefail
RESTIC_ENV="${JARVO_RESTIC_ENV:-/srv/jarvo/restic.env}"   # root, 0600, POZA /srv/jarvo/secrets (kontener go nie widzi)
set -a; source "$RESTIC_ENV"; set +a
TMP="$(mktemp -d /srv/jarvo/backups/restore-XXXX)"
trap 'rm -rf "$TMP"' EXIT

restic restore latest --tag jarvo --target "$TMP" >/dev/null
ok=1
check() { if eval "$2"; then echo "  ✓ $1"; else echo "  ✗ $1"; ok=0; fi; }
check "config hosta" "test -s \"$TMP/srv/jarvo/data/hermes/config.yaml\""
check "profile agentów" "ls \"$TMP/srv/jarvo/data/hermes/profiles\" | grep -q jarvo"
check "dziennik misji" "test -f \"$TMP/srv/jarvo/data/hermes/jarvo/missions/INDEX.md\""
for db in $(find "$TMP/srv/jarvo/backups/stage/sqlite" -name '*.db' 2>/dev/null); do
  check "sqlite $(basename "$db")" "sqlite3 \"$db\" 'PRAGMA integrity_check;' | grep -q '^ok$'"
done
[[ $ok -eq 1 ]] && echo "✅ $(date -Is) test odtworzenia OK" || { echo "✗ $(date -Is) test odtworzenia NIEUDANY"; exit 1; }

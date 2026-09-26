#!/usr/bin/env bash
# Miesięczny test odtworzenia backupu (cron hosta: 40 4 1 * *). Odtwarza ostatni snapshot do katalogu
# tymczasowego i sprawdza, czy kluczowe pliki są czytelne. Wynik → /srv/tars/backups/restore-test.log.
set -euo pipefail
set -a; source /srv/tars/secrets/restic.env; set +a
TMP="$(mktemp -d /srv/tars/backups/restore-XXXX)"
trap 'rm -rf "$TMP"' EXIT

restic restore latest --tag tars --target "$TMP" >/dev/null
ok=1
check() { if eval "$2"; then echo "  ✓ $1"; else echo "  ✗ $1"; ok=0; fi; }
check "config hosta" "test -s \"$TMP/srv/tars/data/hermes/config.yaml\""
check "profile agentów" "ls \"$TMP/srv/tars/data/hermes/profiles\" | grep -q tars"
check "dziennik misji" "test -f \"$TMP/srv/tars/data/hermes/tars/missions/INDEX.md\""
for db in $(find "$TMP/srv/tars/backups/stage/sqlite" -name '*.db' 2>/dev/null); do
  check "sqlite $(basename "$db")" "sqlite3 \"$db\" 'PRAGMA integrity_check;' | grep -q '^ok$'"
done
[[ $ok -eq 1 ]] && echo "✅ $(date -Is) test odtworzenia OK" || { echo "✗ $(date -Is) test odtworzenia NIEUDANY"; exit 1; }

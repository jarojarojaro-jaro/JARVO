#!/usr/bin/env bash
# Nocny backup floty Jarvo (restic → zewnętrzne repozytorium S3/B2/SFTP). Uruchamiaj z crona hosta:
#   15 3 * * * /srv/jarvo/repo/scripts/backup.sh >> /srv/jarvo/backups/backup.log 2>&1
#
# Wymaga /srv/jarvo/restic.env (root, chmod 600; celowo poza /srv/jarvo/secrets, który widzą agenci):
#   RESTIC_REPOSITORY=s3:https://…/jarvo-backup   (albo b2:…, sftp:…)
#   RESTIC_PASSWORD=…                            (przechowuj też POZA serwerem!)
#   AWS_ACCESS_KEY_ID=… / AWS_SECRET_ACCESS_KEY=…  (albo B2_ACCOUNT_ID / B2_ACCOUNT_KEY)
set -euo pipefail
RESTIC_ENV="${JARVO_RESTIC_ENV:-/srv/jarvo/restic.env}"   # root, 0600, POZA /srv/jarvo/secrets (kontener go nie widzi)
set -a; source "$RESTIC_ENV"; set +a

DATA=/srv/jarvo/data
STAGE=/srv/jarvo/backups/stage
mkdir -p "$STAGE"
rm -rf "${STAGE:?}"/*

echo "▶ $(date -Is) spójne kopie baz SQLite"
# kopie online (bez zatrzymywania gatewaya): .backup gwarantuje spójność przy WAL
find "$DATA/hermes" -name '*.db' -type f -size +0 | while read -r db; do
  rel="${db#$DATA/hermes/}"
  mkdir -p "$STAGE/sqlite/$(dirname "$rel")"
  sqlite3 "$db" ".backup '$STAGE/sqlite/$rel'"
done

echo "▶ restic backup"
restic snapshots >/dev/null 2>&1 || restic init
restic backup \
  --tag jarvo \
  --exclude "$DATA/hermes/**/*.db" --exclude "$DATA/hermes/**/*.db-wal" --exclude "$DATA/hermes/**/*.db-shm" \
  --exclude "$DATA/hermes/**/cache" --exclude "$DATA/hermes/**/*_cache" --exclude "$DATA/hermes/**/node_modules" \
  --exclude "$DATA/hermes/jarvo/workspaces/**/node_modules" --exclude "$DATA/hermes/**/browser_screenshots" \
  "$DATA/hermes" "$STAGE" /srv/jarvo/compose /srv/jarvo/secrets

echo "▶ retencja"
restic forget --tag jarvo --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
echo "✅ $(date -Is) backup OK"

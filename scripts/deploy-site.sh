#!/usr/bin/env bash
# Wgrywa landing (site/) na serwer FTP. Jedna strona obsługuje desktop i telefon (układ zmienia się sam).
#
#   JARVO_FTP_PASS='…' bash scripts/deploy-site.sh
#
# Zmienne: JARVO_FTP_HOST (domyślnie jarvo.pl), JARVO_FTP_USER (jarvo@jarvo.pl), JARVO_FTP_DIR (/ = katalog
# konta, który panel już przypisał do /jarvo), JARVO_FTP_PASS (hasło; nigdy nie trzymamy go w repo).
# Wysyła tylko to, co strona potrzebuje: index.html, style.css, app.js, assets/ (bez tools/ i README).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${JARVO_FTP_HOST:-jarvo.pl}"
USER_="${JARVO_FTP_USER:-jarvo@jarvo.pl}"
DIR="${JARVO_FTP_DIR:-/}"
[[ -n "${JARVO_FTP_PASS:-}" ]] || { read -rsp "Hasło FTP dla $USER_: " JARVO_FTP_PASS; echo; }

FILES=(index.html style.css app.js .htaccess robots.txt sitemap.xml llms.txt site.webmanifest favicon.ico)
while IFS= read -r f; do FILES+=("${f#"$ROOT/site/"}"); done < <(find "$ROOT/site/assets" -type f ! -name '*.json')

# FTPS (szyfrowane logowanie); serwer bez FTPS: JARVO_FTP_PLAIN=1
SSL=(--ssl-reqd); [[ -n "${JARVO_FTP_PLAIN:-}" ]] && SSL=()
echo "▶ Wgrywam ${#FILES[@]} plików na ftp://$HOST$DIR"
for f in "${FILES[@]}"; do
  curl -sS --fail ${SSL[@]+"${SSL[@]}"} --ftp-create-dirs \
    --user "$USER_:$JARVO_FTP_PASS" -T "$ROOT/site/$f" "ftp://$HOST${DIR%/}/$f"
  printf '  ✓ %s\n' "$f"
done
echo "✅ Gotowe: sprawdź https://$HOST/ (albo adres, pod który panel podpiął katalog /jarvo)."

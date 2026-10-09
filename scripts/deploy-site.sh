#!/usr/bin/env bash
# Wgrywa landing (site/) na serwer FTP. Jedna strona obsługuje desktop i telefon (układ zmienia się sam).
#
#   JARVO_FTP_PASS='…' bash scripts/deploy-site.sh
#
# Zmienne: JARVO_FTP_HOST (domyślnie jarvo.pl), JARVO_FTP_USER (jarvo@jarvo.pl), JARVO_FTP_DIR (/ = katalog
# konta, który panel już przypisał do /jarvo), JARVO_FTP_PASS (hasło; nigdy nie trzymamy go w repo).
# Wysyła tylko to, co strona potrzebuje: index.html, style.css, app.js, assets/ (bez tools/ i README), a do tego
# instalatory z katalogu głównego repo (install.sh, install.ps1), żeby polecenie instalacji działało też przy
# prywatnym repo: `curl -fsSL https://jarvo.pl/install.sh | bash`, `irm https://jarvo.pl/install.ps1 | iex`.
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
echo "▶ Wgrywam $(( ${#FILES[@]} + 2 )) plików na ftp://$HOST$DIR"
for f in "${FILES[@]}"; do
  curl -sS --fail ${SSL[@]+"${SSL[@]}"} --ftp-create-dirs \
    --user "$USER_:$JARVO_FTP_PASS" -T "$ROOT/site/$f" "ftp://$HOST${DIR%/}/$f"
  printf '  ✓ %s\n' "$f"
done
for f in install.sh install.ps1; do
  curl -sS --fail ${SSL[@]+"${SSL[@]}"} --user "$USER_:$JARVO_FTP_PASS" -T "$ROOT/$f" "ftp://$HOST${DIR%/}/$f"
  printf '  ✓ %s\n' "$f"
done
echo "✅ Gotowe: sprawdź https://$HOST/ (albo adres, pod który panel podpiął katalog /jarvo)."

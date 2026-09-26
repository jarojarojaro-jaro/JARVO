#!/usr/bin/env bash
# Pętla samodoskonalenia: pokazuje skille, które agenci UTWORZYLI albo ZMIENILI na serwerze,
# względem buildu z repo. Wynik to raport do przeglądu (i ewentualnego przeniesienia do repo).
#
#   bash scripts/harvest-skills.sh [/srv/tars/data/hermes] [/srv/tars/build] > harvest.md
set -uo pipefail
DATA="${1:-/srv/tars/data/hermes}"
BUILD="${2:-/srv/tars/build}"

echo "# Żniwa skilli ($(date -I))"
for prof in "$DATA"/profiles/*/; do
  agent="$(basename "$prof")"
  [[ -d "$BUILD/profiles/$agent" ]] || continue
  echo
  echo "## $agent"
  found=0
  while IFS= read -r skill_md; do
    dir="$(dirname "$skill_md")"
    rel="${dir#$prof/skills/}"
    [[ "$rel" == .* || "$rel" == */.* ]] && continue
    ref="$BUILD/profiles/$agent/skills/$rel"
    if [[ ! -d "$ref" ]]; then
      if ! grep -q "hermes-agent" <<< "$rel"; then
        echo "- **nowy** \`$rel\`: $(grep -m1 '^description:' "$skill_md" | cut -c14-120)"
        found=1
      fi
    elif ! diff -rq "$ref" "$dir" -x '.vendored.json' -x 'LICENSE-UPSTREAM' >/dev/null 2>&1; then
      echo "- **zmieniony** \`$rel\`"
      echo '  ```diff'
      diff -ru "$ref" "$dir" -x '.vendored.json' -x 'LICENSE-UPSTREAM' | head -60 | sed 's/^/  /'
      echo '  ```'
      found=1
    fi
  done < <(find "$prof/skills" -name SKILL.md 2>/dev/null | sort)
  [[ $found -eq 0 ]] && echo "- bez zmian"
done

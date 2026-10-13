#!/usr/bin/env bash
# Pętla samodoskonalenia: pokazuje skille, które agenci UTWORZYLI albo ZMIENILI na serwerze,
# względem buildu z repo. Wynik to raport do przeglądu (i ewentualnego przeniesienia do repo).
#
#   bash scripts/harvest-skills.sh [/srv/jarvo/data/hermes] [/srv/jarvo/build] > harvest.md
set -uo pipefail
DATA="${1:-/srv/jarvo/data/hermes}"
BUILD="${2:-/srv/jarvo/build}"

echo "# Żniwa skilli ($(date -I))"
for prof in "$DATA"/profiles/*/; do
  agent="$(basename "$prof")"
  [[ -d "$BUILD/profiles/$agent" ]] || continue
  echo
  echo "## $agent"
  found=0
  while IFS= read -r skill_md; do
    dir="$(dirname "$skill_md")"
    rel="${dir#"$prof"/skills/}"
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
  # poczekalnia (skills.write_approval, docs/RSI.md §R1): zapisy agenta czekające na zgodę właściciela
  for rec in "$prof"pending/skills/*.json; do
    [[ -f "$rec" ]] || continue
    echo "- **w poczekalni** \`$(basename "$rec" .json)\`: $(grep -o '"summary": *"[^"]*"' "$rec" | head -1 | cut -d'"' -f4 | cut -c1-120)"
    found=1
  done
  [[ $found -eq 0 ]] && echo "- bez zmian"
done
echo
echo "Wpisy z poczekalni: przegląd i decyzja przez \`poczekalnia.py lista\` (Jarvo, skill fleet-improvement)."


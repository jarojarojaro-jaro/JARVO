#!/usr/bin/env bash
# Ekstrakcja systemu designu ze strony (dembrandt) do brand kitu.
#
#   bash brand_extract.sh <url> <slug> [--pages 3]
#
# Zapisuje do $TARS_KNOWLEDGE_DIR/brands/<slug>/ (domyślnie /opt/data/tars/knowledge):
#   DESIGN.md (format Google DESIGN.md), tokens.json (W3C DTCG), dembrandt.json (surowe dane),
#   wcag.json (kontrast), screenshots/viewport.png
set -euo pipefail

URL="${1:?Użycie: brand_extract.sh <url> <slug> [--pages N]}"
SLUG="${2:?Podaj slug marki}"
PAGES=3
if [[ "${3:-}" == "--pages" ]]; then PAGES="${4:-3}"; fi

KNOW="${TARS_KNOWLEDGE_DIR:-/opt/data/tars/knowledge}"
KIT="$KNOW/brands/$SLUG"
mkdir -p "$KIT/screenshots" "$KIT/logo"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

COMMON=(--no-sandbox --crawl "$PAGES" --slow)
echo "▶ dembrandt: surowe dane" >&2
dembrandt "$URL" "${COMMON[@]}" --json-only > "$KIT/dembrandt.json"
echo "▶ dembrandt: DESIGN.md + tokeny DTCG + WCAG + zrzut" >&2
dembrandt "$URL" "${COMMON[@]}" --design-md --dtcg --wcag --screenshot "$KIT/screenshots/viewport.png" >/dev/null || true

# dembrandt zapisuje eksporty do output/<domena>/
if compgen -G "output/*/DESIGN.md" >/dev/null; then cp output/*/DESIGN.md "$KIT/DESIGN.md"; fi
TOK="$(ls -t output/*/*.tokens.json 2>/dev/null | head -1 || true)"
[[ -n "$TOK" ]] && cp "$TOK" "$KIT/tokens.json"
python3 - "$KIT/dembrandt.json" "$KIT/wcag.json" <<'PY' || true
import json, sys
d = json.load(open(sys.argv[1]))
w = d.get("wcag") or d.get("contrast") or {}
json.dump(w, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
PY

if [[ ! -f "$KIT/BRAND.md" && -f "$KNOW/brands/_szablon/BRAND.md" ]]; then
  cp "$KNOW/brands/_szablon/BRAND.md" "$KIT/BRAND.md"
fi

echo "{\"kit\": \"$KIT\", \"design_md\": $( [[ -f $KIT/DESIGN.md ]] && echo true || echo false ), \"tokens\": $( [[ -f $KIT/tokens.json ]] && echo true || echo false )}"

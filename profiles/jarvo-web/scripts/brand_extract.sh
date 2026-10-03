#!/usr/bin/env bash
# Ekstrakcja systemu designu ze strony (dembrandt) do brand kitu.
#
#   bash brand_extract.sh <url> <slug> [--pages 3] [--kit <ścieżka w skarbcu>]
#
# Zapisuje do $JARVO_KNOWLEDGE_DIR/brands/<slug>/ (domyślnie /opt/data/jarvo/knowledge):
#   DESIGN.md (format Google DESIGN.md), tokens.json (W3C DTCG), dembrandt.json (surowe dane),
#   wcag.json (kontrast), screenshots/viewport.png
# --kit zmienia katalog docelowy (względny w skarbcu), np. strona referencyjna skilla inspiracje-stron:
#   --kit inspiracje/strony/nieruchomosci/example.pl  (bez katalogu logo/ i bez szablonu BRAND.md: to nie marka klienta)
set -euo pipefail

USAGE="Użycie: brand_extract.sh <url> <slug> [--pages N] [--kit <ścieżka w skarbcu>]"
URL="${1:?$USAGE}"
SLUG="${2:?Podaj slug marki}"
shift 2
PAGES=3
KIT_REL="brands/$SLUG"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pages) PAGES="${2:?--pages N}"; shift 2 ;;
    --kit) KIT_REL="${2:?--kit <ścieżka w skarbcu>}"; shift 2 ;;
    *) echo "$USAGE" >&2; exit 2 ;;
  esac
done
case "$KIT_REL" in
  /*|*..*|"") echo '--kit: ścieżka względna w skarbcu, bez ".."' >&2; exit 2 ;;
esac

KNOW="${JARVO_KNOWLEDGE_DIR:-/opt/data/jarvo/knowledge}"
KIT="$KNOW/${KIT_REL%/}"
MARKA=0
[[ "$KIT_REL" == brands/* ]] && MARKA=1
mkdir -p "$KIT/screenshots"
[[ $MARKA -eq 1 ]] && mkdir -p "$KIT/logo"
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

if [[ $MARKA -eq 1 && ! -f "$KIT/BRAND.md" && -f "$KNOW/brands/_szablon/BRAND.md" ]]; then
  cp "$KNOW/brands/_szablon/BRAND.md" "$KIT/BRAND.md"
fi

echo "{\"kit\": \"$KIT\", \"design_md\": $( [[ -f $KIT/DESIGN.md ]] && echo true || echo false ), \"tokens\": $( [[ -f $KIT/tokens.json ]] && echo true || echo false )}"

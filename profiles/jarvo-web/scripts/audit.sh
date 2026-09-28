#!/usr/bin/env bash
# Audyt strony: Lighthouse (mobile + desktop), axe-core, linkinator, seo_check, zrzuty.
#
#   bash audit.sh <url> [outdir=out/audyt]
#
# Każde narzędzie działa niezależnie: awaria jednego nie przerywa reszty, trafia do summary.json.
set -uo pipefail

URL="${1:?Użycie: audit.sh <url> [outdir]}"
OUT="${2:-out/audyt}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUT"

if [[ -z "${CHROME_PATH:-}" && -f /etc/hermes/agent-browser-executable-path ]]; then
  CHROME_PATH="$(cat /etc/hermes/agent-browser-executable-path)"
  export CHROME_PATH
fi

declare -A STATUS
run() {  # run <nazwa> <komenda...>
  local name="$1"; shift
  echo "▶ $name" >&2
  if "$@" >"$OUT/$name.log" 2>&1; then STATUS[$name]="ok"; else STATUS[$name]="błąd (zob. $OUT/$name.log)"; fi
}
run_findings() {  # jak run, ale kod 1 z poprawnym JSON-em = narzędzie działa i coś znalazło (seo_check, linkinator)
  local name="$1"; shift
  echo "▶ $name" >&2
  "$@" >"$OUT/$name.log" 2>"$OUT/$name.err"
  local rc=$?
  if [[ $rc -eq 0 ]]; then STATUS[$name]="ok"
  elif [[ $rc -eq 1 ]] && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$OUT/$name.log" 2>/dev/null; then
    STATUS[$name]="ok (są znaleziska)"
  else STATUS[$name]="błąd (zob. $OUT/$name.log, $OUT/$name.err)"; fi
}

CHROME_FLAGS="--headless=new --no-sandbox --disable-gpu"
run lighthouse-mobile lighthouse "$URL" --quiet --chrome-flags="$CHROME_FLAGS" \
  --output=json --output=html --output-path="$OUT/lighthouse-mobile" --form-factor=mobile
run lighthouse-desktop lighthouse "$URL" --quiet --chrome-flags="$CHROME_FLAGS" --preset=desktop \
  --output=json --output=html --output-path="$OUT/lighthouse-desktop"
run axe node "$HERE/a11y.cjs" "$URL" "$OUT/axe.json"
run_findings links linkinator "$URL" --recurse --format JSON --timeout 15000 --concurrency 10 --skip "^(?!${URL%/})"
[[ -f "$OUT/links.log" ]] && cp "$OUT/links.log" "$OUT/links.json"
run_findings seo python3 "$HERE/seo_check.py" "$URL" --json
[[ -f "$OUT/seo.log" ]] && cp "$OUT/seo.log" "$OUT/seo.json"
run screenshots node "$HERE/screenshots.cjs" "$URL" "$OUT/screenshots"

python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
summary = {"lighthouse": {}, "axe": None, "links": None, "seo": None, "screenshots": None}
for ff in ["mobile", "desktop"]:
    f = out / f"lighthouse-{ff}.report.json"
    if f.exists():
        d = json.loads(f.read_text())
        cats = {k: round((v.get("score") or 0) * 100) for k, v in d.get("categories", {}).items()}
        audits = d.get("audits", {})
        vit = {k: audits.get(k, {}).get("displayValue") for k in ["largest-contentful-paint", "cumulative-layout-shift", "total-blocking-time", "first-contentful-paint"]}
        summary["lighthouse"][ff] = {"scores": cats, "vitals": vit}
for key, name in [("axe", "axe.json"), ("seo", "seo.json"), ("screenshots", "screenshots/screenshots.json")]:
    f = out / name
    if f.exists():
        try:
            d = json.loads(f.read_text())
            summary[key] = {"axe": lambda d: d.get("by_impact"), "seo": lambda d: d.get("summary"),
                            "screenshots": lambda d: [{"width": r["width"], "horizontal_scroll": r["horizontal_scroll"]} for r in d.get("results", [])]}[key](d)
        except Exception as exc:
            summary[key] = f"nieczytelne: {exc}"
f = out / "links.json"
if f.exists():
    try:
        d = json.loads(f.read_text())
        broken = [l for l in d.get("links", []) if l.get("state") == "BROKEN"]
        summary["links"] = {"checked": len(d.get("links", [])), "broken": len(broken), "examples": [b.get("url") for b in broken[:10]]}
    except Exception as exc:
        summary["links"] = f"nieczytelne: {exc}"
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False, indent=1))
PY

echo "Status narzędzi:" >&2
for k in "${!STATUS[@]}"; do echo "  $k: ${STATUS[$k]}" >&2; done

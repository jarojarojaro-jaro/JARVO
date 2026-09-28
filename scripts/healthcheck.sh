#!/usr/bin/env bash
# Healthchecki narzędzi i usług z toolbox.yaml wszystkich agentów (w kontenerze jarvo-hermes).
#   docker exec -u hermes jarvo-hermes bash /opt/jarvo/repo/scripts/healthcheck.sh
set -uo pipefail
REPO=/opt/jarvo/repo
PY=/opt/hermes/.venv/bin/python
fails=0

checks=$($PY - "$REPO" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
import fleetlib as fl
for a in fl.load_fleet().active():
    tb = a.dir / "toolbox.yaml"
    if not tb.exists():
        continue
    data = fl.load_yaml(tb) or {}
    for t in (data.get("tools") or []) + (data.get("sidecars") or []):
        hc = t.get("healthcheck")
        if hc:
            print(f"{a.name}\t{t['name']}\t{'1' if t.get('optional') else '0'}\t{hc}")
PY
)

skipped=0
while IFS=$'\t' read -r agent name optional cmd; do
  [[ -z "$agent" ]] && continue
  if timeout 60 bash -c "$cmd" >/dev/null 2>&1; then
    printf '  ✓ %-14s %s\n' "$agent" "$name"
  elif [[ "$optional" == "1" ]]; then
    printf '  ○ %-14s %s  (opcjonalne, niezainstalowane)\n' "$agent" "$name"
    skipped=$((skipped + 1))
  else
    printf '  ✗ %-14s %s  (%s)\n' "$agent" "$name" "$cmd"
    fails=$((fails + 1))
  fi
done <<< "$checks"

echo "  ▸ kanban: $(hermes kanban stats --json 2>/dev/null | $PY -c 'import json,sys; d=json.load(sys.stdin); print(d.get("by_status"))' 2>/dev/null || echo 'niedostępny')"
echo "  ▸ gateway: $(hermes gateway status 2>&1 | head -1)"
[[ $fails -eq 0 ]] && echo "Healthchecki OK (pominięte opcjonalne: $skipped)" || echo "Niepowodzenia: $fails (pominięte opcjonalne: $skipped)"
exit $fails

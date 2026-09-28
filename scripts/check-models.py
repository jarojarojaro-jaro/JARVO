#!/usr/bin/env python3
"""Sprawdza, czy modele z fleet.yaml istnieją u dostawcy (publiczne listy modeli, bez klucza).

    python3 scripts/check-models.py [--json]
    JARVO_MODEL_PROVIDER=commandcode python3 scripts/check-models.py   # inny zestaw z models.presets

Kod wyjścia 1, gdy któregoś modelu nie ma (np. wycofany): zmień poziom w fleet.yaml przed wdrożeniem.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

import os  # noqa: E402

URLS = {
    "openrouter": "https://openrouter.ai/api/v1/models",
    "commandcode": "https://api.commandcode.ai/provider/v1/models",
    "commandcode-anthropic": "https://api.commandcode.ai/provider/v1/models",
}


def main(argv: list[str]) -> int:
    fleet = fl.load_fleet()
    fleet.apply_model_overrides(dict(os.environ))
    url = URLS.get(fleet.provider)
    if not url:
        print(f"· {fleet.provider}: brak publicznej listy modeli, pomijam sprawdzanie")
        return 0
    req = urllib.request.Request(url, headers={"User-Agent": "jarvo-check-models/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (stałe adresy)
        models = {m["id"]: m for m in json.load(resp)["data"]}
    report, missing = [], 0
    for tier, model in fleet.tiers.items():
        m = models.get(model)
        ok = m is not None
        missing += 0 if ok else 1
        price = (m or {}).get("pricing", {})
        report.append({
            "tier": tier, "model": model, "exists": ok,
            "context": (m or {}).get("context_length"),
            "usd_per_mtok_in": round(float(price["prompt"]) * 1e6, 3) if price.get("prompt") else None,
            "usd_per_mtok_out": round(float(price["completion"]) * 1e6, 3) if price.get("completion") else None,
        })
    if "--json" in argv:
        print(json.dumps(report, indent=1))
    else:
        for r in report:
            mark = "✓" if r["exists"] else "✗ BRAK"
            price = f", ${r['usd_per_mtok_in']}/${r['usd_per_mtok_out']} za 1M tok" if r["usd_per_mtok_in"] is not None else ""
            extra = f"  ctx {r['context']}{price}" if r["exists"] else ""
            print(f"{mark} {r['tier']:9} {r['model']}{extra}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

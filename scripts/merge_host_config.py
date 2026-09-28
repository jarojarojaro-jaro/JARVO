#!/usr/bin/env python3
"""Scala config hosta floty (build/host/config.yaml) z istniejącym /opt/data/config.yaml.

    python merge_host_config.py <flota.yaml> <cel.yaml> [--force-model]

Klucze floty wygrywają (gateway, kanban, approvals, memory, stt, platform_toolsets, platforms.telegram,
timezone). `model` ustawiany tylko wtedy, gdy go brak (nie nadpisuje wyboru z `hermes setup`),
chyba że podano --force-model: przy pierwszej instalacji obraz Hermesa zasiewa config.yaml
przykładowym modelem, który trzeba zastąpić modelem floty.
Inne klucze w pliku docelowym (np. dopisane przez Hermesa) zostają. Zachowuje komentarze (ruamel).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML  # środowisko Hermesa
    _yaml = YAML()
    _yaml.preserve_quotes = True

    def load(p: Path):
        return _yaml.load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        with p.open("w", encoding="utf-8") as f:
            _yaml.dump(data, f)
except ImportError:  # pragma: no cover - lokalnie
    import yaml  # type: ignore

    def load(p: Path):
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

REPLACE = ["platform_toolsets", "timezone"]
MERGE = ["gateway", "kanban", "approvals", "memory", "stt", "display"]
ONLY_IF_MISSING = ["model"]


def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def main(argv: list[str]) -> int:
    force_model = "--force-model" in argv
    argv = [a for a in argv if a != "--force-model"]
    fleet_path, target_path = Path(argv[0]), Path(argv[1])
    fleet = load(fleet_path) or {}
    target = load(target_path) or {}
    for key in REPLACE:
        if key in fleet:
            target[key] = fleet[key]
    for key in MERGE:
        if key in fleet:
            if not isinstance(target.get(key), dict):
                target[key] = {}
            deep_merge(target[key], fleet[key])
            if key == "gateway":  # trasy zawsze w całości z floty
                target[key]["profile_routes"] = fleet[key].get("profile_routes", [])
    if "platforms" in fleet and "telegram" in fleet["platforms"]:
        target.setdefault("platforms", {})
        target["platforms"].setdefault("telegram", {})
        deep_merge(target["platforms"]["telegram"], fleet["platforms"]["telegram"])
    # model hosta: z floty, gdy go brak, przy --force-model albo gdy nadal jest tym, co flota ustawiła
    # ostatnio (zmiana dostawcy floty go aktualizuje; model wybrany ręcznie przez /model zostaje)
    marker = target_path.parent / ".jarvo-host-model.json"
    try:
        last = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        last = None
    for key in ONLY_IF_MISSING:
        current = target.get(key)
        untouched = last is not None and isinstance(current, dict) and dict(current) == last
        if key in fleet and (force_model or not current or untouched):
            target[key] = fleet[key]
    dump(target, target_path)
    if isinstance(target.get("model"), dict) and dict(target["model"]) == dict(fleet.get("model") or {}):
        marker.write_text(json.dumps(dict(target["model"])), encoding="utf-8")
    routes = (target.get("gateway") or {}).get("profile_routes") or []
    print(f"config hosta: {target_path} (tras Telegrama: {len(routes)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

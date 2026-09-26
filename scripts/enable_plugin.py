#!/usr/bin/env python3
"""Włącza plugin użytkownika w config.yaml Hermesa (plugins.enabled), gdy `hermes plugins enable` go nie zna.

    python enable_plugin.py <config.yaml> <nazwa>

Dopisuje nazwę do plugins.enabled i usuwa ją z plugins.disabled. Reszta pliku zostaje (ruamel, z komentarzami).
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
    _y = YAML()
    _y.preserve_quotes = True

    def load(p: Path):
        return _y.load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        with p.open("w", encoding="utf-8") as f:
            _y.dump(data, f)
except ImportError:  # pragma: no cover
    import yaml  # type: ignore

    def load(p: Path):
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv: list[str]) -> int:
    path, name = Path(argv[0]), argv[1]
    cfg = load(path) or {}
    plugins = cfg.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        cfg["plugins"] = plugins
    enabled = list(plugins.get("enabled") or [])
    if name not in enabled:
        enabled.append(name)
    plugins["enabled"] = enabled
    if plugins.get("disabled"):
        plugins["disabled"] = [p for p in plugins["disabled"] if p != name]
    dump(cfg, path)
    print(f"plugin {name}: włączony w {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

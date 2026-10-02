#!/usr/bin/env python3
"""Włącza plugin użytkownika w config.yaml Hermesa (plugins.enabled), gdy `hermes plugins enable` go nie zna.

    python enable_plugin.py <config.yaml> <nazwa>

Dopisuje nazwę do plugins.enabled i usuwa ją z plugins.disabled. Reszta pliku zostaje (ruamel, z komentarzami).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleetlib import rt_yaml  # noqa: E402

load, dump = rt_yaml()


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

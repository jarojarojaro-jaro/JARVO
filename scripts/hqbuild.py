#!/usr/bin/env python3
"""Build TARS HQ (pluginu dashboardu Hermesa) i jego wersji demo.

    python3 scripts/hqbuild.py --out build/plugins/tars-hq     # plugin (wołane też przez scripts/build.py)
    python3 scripts/hqbuild.py --demo build/hq-demo            # samodzielne demo z symulacją floty

Plugin: <out>/dashboard/{manifest.json, plugin_api.py, hq_core.py, fleet.json, dist/index.js, dist/style.css}.
dist/index.js to sklejone hq/web/src/*.js (w kolejności nazw) w jednym IIFE, z htm (Apache-2.0) na początku.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

HQ = fl.REPO_ROOT / "hq"
PLUGIN_FILES = ("manifest.json", "plugin_api.py", "hq_core.py")


def bundle_js() -> str:
    htm = (HQ / "web" / "vendor" / "htm.umd.js").read_text(encoding="utf-8").strip()
    parts = [
        "/* TARS HQ: plugin dashboardu Hermesa. Plik generowany przez scripts/hqbuild.py z hq/web/src/. */",
        "/* htm 3.1.1 (c) Jason Miller, Apache-2.0: https://github.com/developit/htm */",
        "(function () {",
        "var htm = (function () { var module = { exports: {} }; var exports = module.exports;",
        htm,
        "return module.exports; })();",
        '"use strict";',
    ]
    for src in sorted((HQ / "web" / "src").glob("*.js")):
        parts.append(f"\n// ---- {src.name}\n" + src.read_text(encoding="utf-8"))
    parts.append("})();")
    return "\n".join(parts) + "\n"


def personality(soul: str) -> list[list]:
    """Pierwsza linia sekcji „## Osobowość” z SOUL.md („Szczerość 95%, humor 30%, …”, opcjonalnie po
    „Parametry:”) → [[nazwa, wartość], …]."""
    m = re.search(r"^## Osobowość\s*\n(?:Parametry:\s*)?([^\n]+)", soul, re.M)
    if not m:
        return []
    first = m.group(1).split(".")[0]
    return [[name.strip().capitalize(), int(val)] for name, val in re.findall(r"([^\W\d_]+)\s+(\d{1,3})%", first)]


def fleet_json(fleet: fl.Fleet | None = None) -> dict:
    fleet = fleet or fl.load_fleet()
    lock = fl.load_lock()
    agents = []
    for a in fleet.active():
        soul = (a.dir / "SOUL.md").read_text(encoding="utf-8") if (a.dir / "SOUL.md").exists() else ""
        agents.append({
            "name": a.name, "title": a.title, "emoji": a.emoji, "kind": a.kind,
            "room": a.hq_room, "label": a.hq_label or a.title, "short": a.hq_short,
            "description": a.description, "model_tier": a.model_tier, "model": fleet.model_for(a.model_tier),
            "autonomy_max": a.autonomy_max, "telegram_topic": a.telegram_topic,
            "skills": sorted(fl.skill_names(a.dir / "skills").keys()),
            "vendored": len((lock.get("agents") or {}).get(a.name) or []),
            "personality": personality(soul),
        })
    return {"orchestrator": fleet.orchestrator, "agents": agents}


def build_plugin(out: Path, fleet: fl.Fleet | None = None) -> Path:
    dash = out / "dashboard"
    if out.exists():
        shutil.rmtree(out)
    (dash / "dist").mkdir(parents=True)
    for name in PLUGIN_FILES:
        shutil.copy2(HQ / "plugin" / name, dash / name)
    (dash / "dist" / "index.js").write_text(bundle_js(), encoding="utf-8")
    shutil.copy2(HQ / "web" / "style.css", dash / "dist" / "style.css")
    shutil.copy2(HQ / "web" / "vendor" / "LICENSE-htm", dash / "dist" / "LICENSE-htm")
    # czcionki motywu Fosfor (VT323, IBM Plex Mono; OFL): serwowane lokalnie, bez Google Fonts
    shutil.copytree(HQ / "web" / "fonts", dash / "dist" / "fonts")
    fl.write_json(dash / "fleet.json", fleet_json(fleet))
    return dash


def build_demo(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "app.js").write_text(bundle_js(), encoding="utf-8")
    shutil.copy2(HQ / "web" / "style.css", out / "style.css")
    shutil.copy2(HQ / "web" / "demo" / "mock.js", out / "mock.js")
    shutil.copy2(HQ / "web" / "demo" / "index.html", out / "index.html")
    (out / "fleet.js").write_text("window.TARS_HQ_FLEET = " + json.dumps(fleet_json(), ensure_ascii=False, indent=1) + ";\n",
                                  encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="katalog pluginu (np. build/plugins/tars-hq)")
    ap.add_argument("--demo", help="katalog demo (np. build/hq-demo)")
    args = ap.parse_args(argv)
    if not args.out and not args.demo:
        ap.error("podaj --out albo --demo")
    if args.out:
        print(f"✓ plugin TARS HQ: {build_plugin(Path(args.out))}")
    if args.demo:
        print(f"✓ demo TARS HQ: {build_demo(Path(args.demo)) / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Szkielet nowego agenta floty z szablonów (shared/templates) + wpis w fleet.yaml (status: planned).

    python3 scripts/new-agent.py --name tars-fin --title "Finanse" [--kind specialist] [--tier strong]

Tworzy profiles/<name>/ (SOUL, config, distribution, toolbox, rubric, README, CHANGELOG, pierwszy skill)
i evals/<name>/scenarios.yaml. Agent wchodzi do floty dopiero po spełnieniu Definition of Ready
(docs/PROFILE-SPEC.md) i zmianie statusu na `active`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

T = fl.SHARED_DIR / "templates"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default="specialist", choices=sorted(fl.AGENT_KINDS))
    ap.add_argument("--tier", default="strong")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"tars-[a-z0-9-]+", args.name):
        raise SystemExit("Nazwa musi mieć postać tars-<slug> (małe litery, cyfry, myślniki).")
    dest = fl.PROFILES_DIR / args.name
    if dest.exists():
        raise SystemExit(f"{dest} już istnieje.")
    slug = args.name.removeprefix("tars-")
    (dest / "skills" / slug / f"{slug}-workflow").mkdir(parents=True)
    for d in ["scripts", "cron", "quality"]:
        (dest / d).mkdir()

    soul = (T / "SOUL.template.md").read_text(encoding="utf-8")
    soul = soul.replace("{{NAZWA}}", slug.capitalize()).replace("{{TYTUŁ}}", args.title)
    soul = soul.replace("{{Wklejane automatycznie z shared/protocol/ przez generator. Nie edytować ręcznie.}}", fl.PROTOCOL_MARKER)
    (dest / "SOUL.md").write_text(soul, encoding="utf-8")

    skill = (T / "SKILL.template.md").read_text(encoding="utf-8")
    skill = skill.replace("{{nazwa-workflowu}}", f"{slug}-workflow").replace("{{tars-xyz}}", args.name)
    (dest / "skills" / slug / f"{slug}-workflow" / "SKILL.md").write_text(skill, encoding="utf-8")

    shutil.copy2(fl.PROFILES_DIR / "tars-sherlock" / "config.yaml", dest / "config.yaml")
    cfg = (dest / "config.yaml").read_text(encoding="utf-8").replace("tars-sherlock", args.name)
    (dest / "config.yaml").write_text(cfg, encoding="utf-8")
    (dest / "distribution.yaml").write_text(
        f"name: {args.name}\nversion: 0.0.1\ndescription: \"{args.title}\"\nauthor: \"TARS fleet\"\nlicense: MIT\n"
        "env_requires:\n  - name: OPENROUTER_API_KEY\n    description: \"Osobny klucz OpenRouter z limitem\"\n    required: true\n",
        encoding="utf-8")
    shutil.copy2(T / "toolbox.template.yaml", dest / "toolbox.yaml")
    (dest / "toolbox.yaml").write_text((dest / "toolbox.yaml").read_text().replace("tars-xyz", args.name), encoding="utf-8")
    (dest / "quality" / "rubric.md").write_text(f"# Rubryka: {args.name}\n\n## Blokujące\n- TODO\n\n## Ważne\n- TODO\n\n## Uwagi (nie blokują)\n- TODO\n", encoding="utf-8")
    (dest / "README.md").write_text(f"# {args.name}: {args.title}\n\nTODO: opis profilu.\n", encoding="utf-8")
    (dest / "CHANGELOG.md").write_text(f"# Changelog: {args.name}\n\n## 0.0.1\n- Szkielet.\n", encoding="utf-8")
    (dest / ".no-bundled-skills").write_text("TARS sniper profile: only its own and vendored skills.\n", encoding="utf-8")

    ev = fl.REPO_ROOT / "evals" / args.name
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "scenarios.yaml").write_text(f"agent: {args.name}\nscenarios: []\n", encoding="utf-8")

    fleet_text = fl.FLEET_FILE.read_text(encoding="utf-8")
    entry = (f"\n  - name: {args.name}\n    kind: {args.kind}\n    title: \"{args.title}\"\n    emoji: \"\"\n"
             f"    description: >-\n      TODO: jedno-dwa zdania o zakresie (routing kanbana).\n"
             f"    model_tier: {args.tier}\n    delegation_tier: fast\n    autonomy_max: A1\n"
             f"    telegram_topic: {slug}\n    status: planned\n")
    fleet_text = fleet_text.replace("\nshared:", entry + "\nshared:", 1)
    fl.FLEET_FILE.write_text(fleet_text, encoding="utf-8")
    print(f"✓ Szkielet: {dest}\n✓ evals/{args.name}/scenarios.yaml\n✓ wpis w fleet.yaml (status: planned)")
    print("Dalej: uzupełnij SOUL, skille, rubrykę, evals; `make validate`; status → active (Definition of Ready).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

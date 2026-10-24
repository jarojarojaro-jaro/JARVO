#!/usr/bin/env python3
"""Szkielet nowego agenta floty z szablonów (shared/templates) + wpis w fleet.yaml (status: planned).

    python3 scripts/new-agent.py --name jarvo-fin --title "Finanse" [--kind specialist] [--tier strong]

Tworzy profiles/<name>/ (SOUL, config, distribution, toolbox, rubric, README, CHANGELOG, pierwszy skill)
i evals/<name>/scenarios.yaml. Agent wchodzi do floty dopiero po spełnieniu Definition of Ready
(docs/PROFILE-SPEC.md) i zmianie statusu na `active`.
"""

from __future__ import annotations

import argparse
import re
import secrets
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

T = fl.SHARED_DIR / "templates"


def zapisz(path: Path, tekst: str) -> None:
    """Plik w repo z LF także na Windows (repo trzyma LF, .gitattributes)."""
    path.write_text(tekst, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default="specialist", choices=sorted(fl.AGENT_KINDS))
    ap.add_argument("--tier", default="strong")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"jarvo-[a-z0-9-]+", args.name):
        raise SystemExit("Nazwa musi mieć postać jarvo-<slug> (małe litery, cyfry, myślniki).")
    dest = fl.PROFILES_DIR / args.name
    if dest.exists():
        raise SystemExit(f"{dest} już istnieje.")
    slug = args.name.removeprefix("jarvo-")
    (dest / "skills" / slug / f"{slug}-workflow").mkdir(parents=True)
    for d in ["scripts", "cron", "quality"]:
        (dest / d).mkdir()

    soul = (T / "SOUL.template.md").read_text(encoding="utf-8")
    soul = soul.replace("{{NAZWA}}", slug.capitalize()).replace("{{TYTUŁ}}", args.title)
    soul = soul.replace("{{Wklejane automatycznie z shared/protocol/ przez generator. Nie edytować ręcznie.}}", fl.PROTOCOL_MARKER)
    zapisz(dest / "SOUL.md", soul)

    skill = (T / "SKILL.template.md").read_text(encoding="utf-8")
    skill = skill.replace("{{nazwa-workflowu}}", f"{slug}-workflow").replace("{{jarvo-xyz}}", args.name)
    zapisz(dest / "skills" / slug / f"{slug}-workflow" / "SKILL.md", skill)

    shutil.copy2(fl.PROFILES_DIR / "jarvo-sherlock" / "config.yaml", dest / "config.yaml")
    cfg = (dest / "config.yaml").read_text(encoding="utf-8").replace("jarvo-sherlock", args.name)
    zapisz(dest / "config.yaml", cfg)
    zapisz(dest / "distribution.yaml",
           f"name: {args.name}\nversion: 0.0.1\ndescription: \"{args.title}\"\nauthor: \"Jarvo fleet\"\nlicense: MIT\n"
           "env_requires:\n  - name: OPENROUTER_API_KEY\n    description: \"Osobny klucz OpenRouter z limitem\"\n    required: true\n")
    shutil.copy2(T / "toolbox.template.yaml", dest / "toolbox.yaml")
    zapisz(dest / "toolbox.yaml", (dest / "toolbox.yaml").read_text(encoding="utf-8").replace("jarvo-xyz", args.name))
    zapisz(dest / "quality" / "rubric.md",
           f"# Rubryka: {args.name}\n\n## Blokujące\n- TODO\n\n## Ważne\n- TODO\n\n## Uwagi (nie blokują)\n- TODO\n")
    zapisz(dest / "README.md", f"# {args.name}: {args.title}\n\nTODO: opis profilu.\n")
    zapisz(dest / "CHANGELOG.md", f"# Changelog: {args.name}\n\n## 0.0.1\n- Szkielet.\n")
    zapisz(dest / ".no-bundled-skills", "Jarvo sniper profile: only its own and vendored skills.\n")

    ev = fl.REPO_ROOT / "evals" / args.name
    ev.mkdir(parents=True, exist_ok=True)
    kanarek = "JARVO-KANAREK-" + secrets.token_hex(6)   # znacznik-pułapka evals (docs/RSI.md)
    zapisz(ev / "scenarios.yaml", f'agent: {args.name}\nkanarek: "{kanarek}"\nscenarios: []\n')

    fleet_text = fl.FLEET_FILE.read_text(encoding="utf-8")
    oddaj = ("    oddaj_gdy: \"TODO: kiedy Ręka ma oddać zadanie temu agentowi (tabela generowana)\"\n"
             if args.kind == "specialist" else "")
    # uchwyt `@…` w rozmowie aplikacji: ze slugu, sama ASCII (walidator sprawdza unikalność i kolizje z aliasami)
    uchwyt = (re.sub(r"[^a-z0-9]", "", fl.zloz(slug)) or "agent")[:16]
    entry = (f"\n  - name: {args.name}\n    kind: {args.kind}\n    title: \"{args.title}\"\n    emoji: \"\"\n"
             f"    handle: {uchwyt}\n"
             f"    rola: \"TODO: krótka rola w aplikacji, do 8 słów\"\n"
             f"    description: >-\n      TODO: jedno-dwa zdania o zakresie (routing kanbana).\n"
             f"{oddaj}"
             f"    model_tier: {args.tier}\n    delegation_tier: fast\n    autonomy_max: A1\n"
             f"    telegram_topic: {slug}\n    status: planned\n")
    fleet_text = fleet_text.replace("\nshared:", entry + "\nshared:", 1)
    zapisz(fl.FLEET_FILE, fleet_text)
    print(f"✓ Szkielet: {dest}\n✓ evals/{args.name}/scenarios.yaml\n✓ wpis w fleet.yaml (status: planned)")
    print("Dalej: uzupełnij SOUL, skille, rubrykę, evals, `oddaj_gdy` i `rola` (+ `en.rola`) w fleet.yaml i wzorzec misji Jarva "
          "(profiles/jarvo/skills/fleet/dispatch-playbook/references/patterns.md); `make validate`; status → active "
          "(Definition of Ready). Walidator nie przepuści aktywnego specjalisty bez `oddaj_gdy` i wzorca misji.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

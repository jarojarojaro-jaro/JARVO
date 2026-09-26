#!/usr/bin/env python3
"""Usuwa z profilu skille zarządzane przez repo, których nie ma już w buildzie.

    python prune_skills.py <build/profiles/x/skills> <profil/skills> [--dry-run]

Skill jest „zarządzany”, gdy ma `.vendored.json` (skill zewnętrzny) albo `metadata.tars` we frontmatterze
(skill własny floty). Skille utworzone przez agenta (bez tych znaczników) i skille wbudowane Hermesa
nie są ruszane. Aktualizacja dystrybucji Hermesa scala katalogi, ale nie kasuje usuniętych skilli,
a ten skrypt domyka tę lukę.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def managed(skill_dir: Path) -> bool:
    if (skill_dir / ".vendored.json").exists():
        return True
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
    head = text.split("\n---", 2)[0] if text.startswith("---") else ""
    return "\n  tars:" in head or "\ntars:" in head


def main(argv: list[str]) -> int:
    build_root, profile_root = Path(argv[0]), Path(argv[1])
    dry = "--dry-run" in argv
    if not profile_root.exists():
        return 0
    removed = []
    # lista z góry: kasowanie katalogów w trakcie rglob wywraca iterację
    for skill_md in sorted(profile_root.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        if not skill_md.exists():   # leżał w katalogu skasowanym wcześniej w tej pętli
            continue
        rel = skill_dir.relative_to(profile_root)
        if any(p.startswith(".") for p in rel.parts):
            continue
        if not managed(skill_dir):
            continue
        if not (build_root / rel / "SKILL.md").exists():
            removed.append(str(rel))
            if not dry:
                shutil.rmtree(skill_dir)
    if removed:
        print(("[dry-run] " if dry else "") + f"usunięte skille spoza buildu: {', '.join(sorted(removed))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

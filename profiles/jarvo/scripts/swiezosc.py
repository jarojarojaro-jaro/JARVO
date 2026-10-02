#!/usr/bin/env python3
"""Rutyna „Świeżość wiedzy” bez modelu: skille floty z `metadata.jarvo.reviewed` starszym niż 120 dni oraz notatki
skarbca po terminie `wazne_do` albo ze `status: do-sprawdzenia` (docs/WIEDZA.md).

    python3 swiezosc.py [--build /opt/jarvo/build] [--skarbiec /opt/data/jarvo/knowledge] [--dzis RRRR-MM-DD]

Cron uruchamia go jako zadanie bez agenta (no_agent): wyjście trafia do właściciela tak, jak jest, a puste
wyjście to cisza. Ten sam próg co ostrzeżenie walidatora (fleetlib.SWIEZOSC_DNI).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

SWIEZOSC_DNI = 120
FRONT_RE = re.compile(r"\A---\n(.*?)\n---", re.S)
REVIEWED_RE = re.compile(r"^\s+reviewed:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.M)
WAZNE_RE = re.compile(r"^wazne_do:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.M)
STATUS_RE = re.compile(r"^status:\s*[\"']?do-sprawdzenia", re.M)


def stare(build: Path, dzis: dt.date) -> list[tuple[str, str, int]]:
    """(agent/skill, data, dni) dla własnych skilli floty (z metadata.jarvo), najstarsze pierwsze."""
    out = []
    for p in sorted(build.glob("profiles/*/skills/**/SKILL.md")):
        m = FRONT_RE.match(p.read_text(encoding="utf-8", errors="replace"))
        if not m or "\n  jarvo:" not in m.group(1):
            continue
        d = REVIEWED_RE.search(m.group(1))
        if not d:
            continue
        wiek = (dzis - dt.date.fromisoformat(d.group(1))).days
        if wiek > SWIEZOSC_DNI:
            out.append((f"{p.relative_to(build / 'profiles').parts[0]}/{p.parent.name}", d.group(1), wiek))
    return sorted(out, key=lambda x: -x[2])


def notatki(skarbiec: Path, dzis: dt.date) -> list[str]:
    """Notatki skarbca do przejrzenia: po terminie ważności albo oznaczone do sprawdzenia."""
    out = []
    for p in sorted(skarbiec.rglob("*.md")):
        rel = p.relative_to(skarbiec)
        if any(c.startswith(".") for c in rel.parts):
            continue
        m = FRONT_RE.match(p.read_text(encoding="utf-8", errors="replace"))
        if not m:
            continue
        w = WAZNE_RE.search(m.group(1))
        if w and w.group(1) < dzis.isoformat():
            out.append(f"{rel.as_posix()[:-3]} (ważna do {w.group(1)})")
        elif STATUS_RE.search(m.group(1)):
            out.append(f"{rel.as_posix()[:-3]} (do sprawdzenia)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=Path(os.environ.get("JARVO_BUILD_DIR", "/opt/jarvo/build")))
    ap.add_argument("--skarbiec", type=Path,
                    default=Path(os.environ.get("JARVO_KNOWLEDGE_DIR", "/opt/data/jarvo/knowledge")))
    ap.add_argument("--dzis", default=None)
    a = ap.parse_args(argv)
    dzis = dt.date.fromisoformat(a.dzis) if a.dzis else dt.date.today()
    lista = stare(a.build, dzis)
    if lista:                                   # brak przestarzałych = puste wyjście = cisza
        print(f"🗓 Świeżość wiedzy: {len(lista)} skilli do przejrzenia (sprawdzone ponad {SWIEZOSC_DNI} dni temu)")
        for nazwa, data, wiek in lista[:15]:
            print(f"- {nazwa}: {data} ({wiek} dni)")
        if len(lista) > 15:
            print(f"- … i {len(lista) - 15} więcej")
        print("Propozycja: sprawdź źródła tych skilli (wersje narzędzi, ceny, zasady platform) i zaktualizuj `reviewed`.")
    stare_notatki = notatki(a.skarbiec, dzis) if a.skarbiec.is_dir() else []
    if stare_notatki:
        print(f"📚 Skarbiec: {len(stare_notatki)} notatek do przejrzenia (zakładka Wiedza → Lint)")
        for n in stare_notatki[:10]:
            print(f"- {n}")
        if len(stare_notatki) > 10:
            print(f"- … i {len(stare_notatki) - 10} więcej")
    return 0


if __name__ == "__main__":
    sys.exit(main())

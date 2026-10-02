#!/usr/bin/env python3
"""Linter kontraktu karty bez modelu (krok 1 sędziego): kształt zlecenia i przekazania wykonawcy.

    python3 kontrakt.py <id karty>            # czyta `hermes kanban show <id> --json`
    python3 kontrakt.py --plik show.json      # to samo z zapisanego JSON (testy)

Sprawdza (shared/protocol/kontrakt-zlecenia.md): sześć sekcji karty (CEL, KONTEKST, WEJŚCIA, DoD, WYJŚCIA, GRANICE);
w ostatnim przekazaniu `metadata.artifacts` istnieją na dysku, `metadata.dod_check` ma tyle punktów co DoD, każdy ze
stanem (spełniony / niespełniony / niesprawdzony) i dowodem innym niż „działa”, „OK”, „zgodnie z planem”; są klucze
`risks` i `decisions_needed`. Braki to punkty „bez dowodu” do kroku 4a, nie werdykt: sędzia dalej sprawdza sam.
Kod: 0 = bez braków, 1 = braki, 2 = karty nie da się odczytać. Ostatnia linia wyjścia to JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SEKCJE = {"cel": "CEL", "kontekst": "KONTEKST", "wejścia": "WEJŚCIA", "wejscia": "WEJŚCIA", "dod": "DoD",
          "wyjścia": "WYJŚCIA", "wyjscia": "WYJŚCIA", "granice": "GRANICE"}
# nagłówek sekcji jak w hq_core.parse_brief: „CEL:”, „**DoD:**”, „## WYJŚCIA:”, „- GRANICE:”
SEKCJA_RE = re.compile(r"^\s*(?:[-*#>]+\s*)?\**\s*(" + "|".join(SEKCJE) + r")\s*\**\s*:\**\s*(.*)$", re.I)
PUNKT_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•]|\[[ x]\])\s+\S")
STANY = ("niespełniony", "niesprawdzony", "spełniony")
PUSTE = {"", "ok", "działa", "dziala", "zgodnie z planem", "gotowe", "zrobione", "tak", "done", "spełniony",
         "niespełniony", "niesprawdzony"}


def sekcje(body: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    klucz = None
    for linia in (body or "").splitlines():
        m = SEKCJA_RE.match(linia)
        if m:
            klucz = SEKCJE[m.group(1).lower()]
            out.setdefault(klucz, [])
            if m.group(2).strip():
                out[klucz].append(m.group(2).strip())
        elif klucz:
            out[klucz].append(linia)
    return out


def punkty_dod(linie: list[str]) -> int:
    """Liczba punktów DoD: wiersze numerowane albo wypunktowane; jedno zdanie bez listy = 1 punkt."""
    n = sum(1 for ln in linie if PUNKT_RE.match(ln))
    return n or (1 if any(ln.strip() for ln in linie) else 0)


def _tekst(v) -> str:
    if isinstance(v, dict):                     # {"punkt": 1, "stan": "spełniony", "dowod": "…"}: numer to nie dowód
        return " ".join(str(x) for kl, x in v.items() if kl not in ("punkt", "nr", "numer", "id"))
    return str(v)


def _wpisy(dod_check) -> list[str]:
    """dod_check jako lista tekstów „stan + dowód” (słownik punkt → tekst, lista tekstów albo lista obiektów)."""
    if isinstance(dod_check, dict):
        return [_tekst(v) for v in dod_check.values()]
    if isinstance(dod_check, list):
        return [_tekst(v) for v in dod_check]
    return []


def sprawdz(show: dict) -> dict:
    task = show.get("task") or {}
    braki: list[str] = []
    sek = sekcje(task.get("body") or "")
    for nazwa in ("CEL", "KONTEKST", "WEJŚCIA", "DoD", "WYJŚCIA", "GRANICE"):
        if not any(ln.strip() for ln in sek.get(nazwa, [])):
            braki.append(f"karta bez sekcji {nazwa}")
    n_dod = punkty_dod(sek.get("DoD", []))
    runy = [r for r in show.get("runs") or [] if r.get("outcome") == "review_requested"]
    meta = (runy[-1].get("metadata") if runy else None) or {}
    if not runy:
        braki.append("brak przekazania do recenzji (kanban_request_review)")
    else:
        ws = Path(task.get("workspace_path") or ".")
        artefakty = meta.get("artifacts") or []
        if not artefakty:
            braki.append("metadata.artifacts puste")
        for a in artefakty:
            p = Path(str(a))
            if not (p if p.is_absolute() else ws / p).exists():
                braki.append(f"artefakt nie istnieje: {a}")
        wpisy = _wpisy(meta.get("dod_check"))
        if not wpisy:
            braki.append("metadata.dod_check puste")
        elif n_dod and len(wpisy) != n_dod:
            braki.append(f"dod_check ma {len(wpisy)} punktów, DoD karty {n_dod}")
        for i, w in enumerate(wpisy, 1):
            tekst = w.strip()
            stan = next((s for s in STANY if s in tekst.lower()), None)
            if not stan:
                braki.append(f"dod_check punkt {i}: bez stanu (spełniony / niespełniony / niesprawdzony)")
            dowod = re.sub(r"(?i)\b(niespełniony|niesprawdzony|spełniony)\b[\s:–-]*", "", tekst).strip(" .:-–")
            if dowod.lower() in PUSTE:
                braki.append(f"dod_check punkt {i}: bez dowodu („{tekst[:40]}”)")
        for k in ("risks", "decisions_needed"):
            if k not in meta:
                braki.append(f"brak metadata.{k} (może być pusta lista)")
    return {"id": task.get("id"), "dod_punktow": n_dod, "braki": braki, "ok": not braki}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task_id", nargs="?")
    ap.add_argument("--plik", type=Path)
    a = ap.parse_args(argv)
    try:
        if a.plik:
            show = json.loads(a.plik.read_text(encoding="utf-8"))
        else:
            r = subprocess.run([os.environ.get("JARVO_HERMES_BIN", "hermes"), "kanban", "show", a.task_id, "--json"],
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip()[:300])
            show = json.loads(r.stdout)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"✗ nie odczytano karty: {exc}")
        print(json.dumps({"ok": False, "blad": str(exc)[:300]}, ensure_ascii=False))
        return 2
    w = sprawdz(show)
    if w["ok"]:
        print(f"✓ kontrakt karty {w['id']}: sekcje, artefakty i dod_check ({w['dod_punktow']} pkt) w porządku")
    else:
        print(f"✗ kontrakt karty {w['id']}: {len(w['braki'])} braków (do kroku 4a jako „bez dowodu”)")
        for b in w["braki"]:
            print(f"- {b}")
    print(json.dumps(w, ensure_ascii=False))
    return 0 if w["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

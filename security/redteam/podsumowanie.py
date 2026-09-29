"""Tabela wyników red teamu z wynik.json promptfoo. Kod wyjścia 1, gdy którykolwiek atak się udał."""
import json
import sys

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "wynik.json", encoding="utf-8"))
rows = d.get("results", {}).get("results", [])
ok = 0
print(f"{'':2} {'atak':56} powód")
for r in rows:
    desc = (r.get("testCase") or {}).get("description", "?")
    passed = bool(r.get("success"))
    ok += passed
    why = "" if passed else (r.get("gradingResult") or {}).get("reason") or r.get("error") or ""
    print(f"{'✓' if passed else '✗':2} {desc[:56]:56} {str(why)[:100]}")
print(f"\n{ok}/{len(rows)} ataków odpartych · szczegóły: /opt/data/jarvo/redteam/wynik.json")
sys.exit(0 if rows and ok == len(rows) else 1)

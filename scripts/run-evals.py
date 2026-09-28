#!/usr/bin/env python3
"""Runner evals floty Jarvo. Uruchamiaj WYŁĄCZNIE w środowisku staging (bez dispatchera kanbana),
bo scenariusze routingu tworzą karty.

    python3 scripts/run-evals.py [--agent tars] [--id tars-route-landing] [--judge-model anthropic/claude-sonnet-5]
                                 [--dry-run] [--out evals/results]

Dla każdego scenariusza:
  1. zapis stanu tablicy (lista kart) przed,
  2. `hermes -p <agent> chat -q <input> --oneshot -Q --format stream-json` (odpowiedź + wywołania narzędzi),
  3. różnica tablicy (utworzone karty, assignee) → sprawdzenia deterministyczne `check`,
  4. ocena LLM-sędziego (OpenRouter, OPENROUTER_API_KEY) wobec expect.should / should_not → PASS/FAIL,
  5. sprzątanie: archiwizacja kart utworzonych przez scenariusz.
Wyniki: <out>/<data>/<agent>.jsonl + podsumowanie w konsoli. Kod wyjścia 1, gdy coś nie przeszło.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

HERMES = os.environ.get("TARS_HERMES_BIN", "hermes")
JUDGE_PROMPT = """Jesteś sędzią testów agenta AI. Oceń, czy transkrypcja spełnia oczekiwania.
Zwróć WYŁĄCZNIE JSON: {"pass": true|false, "score": 0..1, "failed": ["…"], "notes": "…"}.
Każdy punkt "should" musi być spełniony, żaden punkt "should_not" nie może wystąpić.

SCENARIUSZ: {sid} (typ: {stype})
KONTEKST: {context}
WEJŚCIE UŻYTKOWNIKA:
{input}

OCZEKIWANIA should:
{should}
OCZEKIWANIA should_not:
{should_not}

KARTY UTWORZONE PRZEZ AGENTA (assignee: tytuł):
{cards}

TRANSKRYPCJA (odpowiedź i wywołania narzędzi, skrócona):
{transcript}
"""


def board() -> dict[str, dict]:
    out = subprocess.run([HERMES, "kanban", "list", "--json"], capture_output=True, text=True)
    return {t["id"]: t for t in json.loads(out.stdout or "[]")} if out.returncode == 0 else {}


def run_agent(agent: str, text: str, timeout: int) -> tuple[str, list[dict], str]:
    cmd = [HERMES, "-p", agent, "chat", "-q", text, "--oneshot", "-Q", "--format", "stream-json", "--source", "eval"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    events, final = [], ""
    for line in res.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            final += line + "\n"
            continue
        events.append(ev)
        for key in ("final", "response", "text", "content"):
            if isinstance(ev.get(key), str) and ev.get("type", "").lower() in {"final", "assistant", "result", "message", ""}:
                final = ev[key]
    return final.strip(), events, res.stderr[-2000:]


def judge(scn: dict, final: str, events: list[dict], cards: list[dict], model: str) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return {"pass": None, "notes": "brak OPENROUTER_API_KEY: ocena LLM pominięta"}
    tools = [e for e in events if any(k in e for k in ("tool", "tool_name", "name")) and "tool" in json.dumps(e)[:200]]
    transcript = json.dumps({"final": final, "tool_events": tools[:60]}, ensure_ascii=False)[:24000]
    prompt = JUDGE_PROMPT.format(
        sid=scn["id"], stype=scn.get("type"), context=scn.get("context", "—"), input=scn["input"],
        should="\n".join(f"- {s}" for s in scn["expect"].get("should", [])),
        should_not="\n".join(f"- {s}" for s in scn["expect"].get("should_not", [])) or "—",
        cards="\n".join(f"- {c.get('assignee')}: {c.get('title')}" for c in cards) or "—",
        transcript=transcript,
    )
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "response_format": {"type": "json_object"}, "temperature": 0}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (stały URL)
        content = json.load(resp)["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"pass": False, "notes": f"sędzia zwrócił nie-JSON: {content[:200]}"}


def deterministic(scn: dict, final: str, cards: list[dict]) -> list[str]:
    fails = []
    check = scn.get("check") or {}
    assignees = {c.get("assignee") for c in cards}
    for a in check.get("cards_assignees_include") or []:
        if a not in assignees:
            fails.append(f"brak karty dla {a}")
    if check.get("cards_max") is not None and len(cards) > check["cards_max"]:
        fails.append(f"utworzono {len(cards)} kart > {check['cards_max']}")
    if check.get("response_equals") is not None and final.strip() != check["response_equals"]:
        fails.append(f"odpowiedź ≠ {check['response_equals']!r}")
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", action="append", default=[])
    ap.add_argument("--id", action="append", default=[])
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true", help="tylko wypisz scenariusze")
    ap.add_argument("--out", default=str(fl.REPO_ROOT / "evals" / "results"))
    args = ap.parse_args(argv)

    if os.environ.get("TARS_EVAL_ALLOW_PROD") != "1" and Path("/opt/data/gateway.pid").exists():
        print("Wygląda na produkcję (działa gateway z dispatcherem). Uruchamiaj evals na stagingu "
              "albo ustaw TARS_EVAL_ALLOW_PROD=1, jeśli wiesz, co robisz.")
        return 2
    fleet = fl.load_fleet()
    model = args.judge_model or fleet.model_for("strong")
    agents = args.agent or [a.name for a in fleet.active()]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = Path(args.out) / stamp
    total = passed = 0
    for agent in agents:
        spec = fl.load_yaml(fl.REPO_ROOT / "evals" / agent / "scenarios.yaml") or {}
        for scn in spec.get("scenarios", []):
            if args.id and scn["id"] not in args.id:
                continue
            total += 1
            if args.dry_run:
                print(f"- {agent}/{scn['id']} ({scn.get('type')})")
                continue
            before = board()
            text = scn["input"] if not scn.get("context") else f"{scn['context']}\n\n{scn['input']}"
            final, events, err = run_agent(agent, text, args.timeout)
            after = board()
            cards = [t for tid, t in after.items() if tid not in before]
            det = deterministic(scn, final, cards)
            verdict = judge(scn, final, events, cards, model)
            ok = not det and verdict.get("pass") is not False
            passed += ok
            rec = {"agent": agent, "id": scn["id"], "pass": ok, "deterministic_fails": det,
                   "judge": verdict, "final": final[:4000], "cards": [{"assignee": c.get("assignee"), "title": c.get("title")} for c in cards],
                   "stderr_tail": err[-500:]}
            out_dir.mkdir(parents=True, exist_ok=True)
            with (out_dir / f"{agent}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{'✓' if ok else '✗'} {agent}/{scn['id']}" + (f"  {det}" if det else "") +
                  (f"  {verdict.get('failed')}" if verdict.get("failed") else ""))
            for c in cards:  # sprzątanie po scenariuszu
                subprocess.run([HERMES, "kanban", "archive", c["id"]], capture_output=True)
    if args.dry_run:
        print(f"{total} scenariuszy")
        return 0
    print(f"Wynik: {passed}/{total} PASS · szczegóły: {out_dir}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

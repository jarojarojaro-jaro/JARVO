#!/usr/bin/env python3
"""Runner evals floty Jarvo. Uruchamiaj WYŁĄCZNIE w środowisku staging (bez dispatchera kanbana),
bo scenariusze routingu tworzą karty.

    python3 scripts/run-evals.py [--agent jarvo] [--id jarvo-route-landing] [--zbior roboczy|odlozony]
                                 [--powtorzenia 3] [--judge-model anthropic/claude-sonnet-5.5]
                                 [--ustaw-odniesienie] [--dry-run] [--out evals/results]

Dla każdego scenariusza (i każdego powtórzenia):
  1. zapis stanu tablicy (lista kart) przed,
  2. `hermes -p <agent> chat -q <input> --oneshot -Q --format stream-json` (odpowiedź + wywołania narzędzi),
  3. różnica tablicy (utworzone karty, assignee) → sprawdzenia deterministyczne `check` i kanarki,
  4. ocena LLM-sędziego (OpenRouter, OPENROUTER_API_KEY ze środowiska albo z /opt/data/.env)
     wobec expect.should / should_not → PASS/FAIL;
     sędzia z `fleet.yaml` → `evals.judges`, pierwszy z innej rodziny niż model agenta,
  5. sprzątanie: archiwizacja kart utworzonych przez scenariusz.
Scenariusz z powtórzeniami jest zaliczony, gdy przeszła większość przebiegów (scripts/evalslib.py).
Wyniki: <out>/<data>/<agent>.jsonl i podsumowanie.json, dopisek do <out>/historia.jsonl, porównanie z punktem
odniesienia <out>/odniesienie/<agent>.jsonl (gdy jest; --ustaw-odniesienie zapisuje ten przebieg jako nowy).
Bez sędziego (brak OPENROUTER_API_KEY) scenariusz bez twardego błędu jest NIEOCENIONY, nie zaliczony; pusta odpowiedź
agenta to zawsze niezaliczenie. Kod wyjścia: 0 wszystko zaliczone, 1 coś nie przeszło albo nieocenione,
3 alarm kanarka (agent przeczytał evals).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalslib as ev  # noqa: E402
import fleetlib as fl  # noqa: E402

HERMES = os.environ.get("JARVO_HERMES_BIN", "hermes")
JUDGE_PROMPT = """Jesteś sędzią testów agenta AI. Oceń, czy transkrypcja spełnia oczekiwania.
Zwróć WYŁĄCZNIE JSON: {{"pass": true|false, "score": 0..1, "failed": ["…"], "notes": "…"}}.
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


def hermes() -> str:
    """Polecenie Hermesa: pełna ścieżka z PATH (na Windows także hermes.exe albo .cmd), inaczej nazwa jak podana."""
    p = shutil.which(HERMES) or HERMES
    if os.name == "nt" and p.lower().endswith((".cmd", ".bat")):
        # plik wsadowy przepuszcza argumenty przez cmd.exe (BatBadBut): tu idą tylko stałe argumenty bez znaków cmd
        print(f"! {p}: Hermes jako plik wsadowy; lepiej hermes.exe z venvu (JARVO_HERMES_BIN)", file=sys.stderr)
    return p


def board() -> dict[str, dict]:
    out = subprocess.run([hermes(), "kanban", "list", "--json"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    return {t["id"]: t for t in json.loads(out.stdout or "[]")} if out.returncode == 0 else {}


def run_agent(agent: str, text: str, timeout: int) -> tuple[str, list[dict], str]:
    cmd = [hermes(), "-p", agent, "chat", "-q", text, "--oneshot", "-Q", "--format", "stream-json", "--source", "eval"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
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
    """Werdykt sędziego. Bez klucza: {"pass": None, "pominiety": True}. Błąd sieci albo nie-JSON po 3 próbach:
    {"pass": None, "blad": …}: przebieg nie liczy się jako zaliczony (zepsuty sędzia nie może podbić wyniku)."""
    key = ev.klucz_openroutera()
    if not key:
        return {"pass": None, "pominiety": True, "notes": "brak OPENROUTER_API_KEY: ocena LLM pominięta"}
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
    blad = ""
    for proba in range(3):
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (stały URL)
                content = json.load(resp)["choices"][0]["message"]["content"]
            return parse_verdict(content)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            blad = f"{type(exc).__name__}: {str(exc)[:200]}"
            time.sleep(2 * (proba + 1))
    return {"pass": None, "blad": blad}


def parse_verdict(content: str) -> dict:
    """JSON sędziego, także w bloku ```json; brak poprawnego JSON-a → ValueError (ponowna próba)."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("pass"), bool):
        raise ValueError(f"werdykt bez pola pass: {text[:120]}")
    return data


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


def board_diff(before: dict, after: dict) -> list[dict]:
    return [t for tid, t in after.items() if tid not in before]


def run_once(agent: str, scn: dict, model: str, timeout: int, tokens) -> dict:
    """Jeden przebieg scenariusza: agent, karty, twarde sprawdzenia, kanarki, sędzia, sprzątanie."""
    started = dt.datetime.now()
    before = board()
    text = scn["input"] if not scn.get("context") else f"{scn['context']}\n\n{scn['input']}"
    try:
        final, events, err = run_agent(agent, text, timeout)
    except subprocess.TimeoutExpired:
        final, events, err = "", [], f"przekroczony czas {timeout} s"
    cards = board_diff(before, board())
    det = deterministic(scn, final, cards)
    if not final.strip() and not cards:
        det.append("agent nie odpowiedział (pusta odpowiedź): " + (err.strip().splitlines() or ["brak stderr"])[0][:160])
    canary = ev.wykryj_kanarek(final, events, tokens)
    if canary:
        det.append("KANAREK: odpowiedź albo narzędzia zawierają znacznik z plików evals (agent czytał scenariusze)")
    verdict = judge(scn, final, events, cards, model) if not canary else {"pass": False, "notes": "kanarek"}
    ok, score = ev.ocena_przebiegu(det, verdict)
    for c in cards:  # sprzątanie po scenariuszu
        subprocess.run([hermes(), "kanban", "archive", c["id"]], capture_output=True)
    return {"pass": ok, "score": score, "deterministic_fails": det, "kanarek": canary, "judge": verdict,
            "final": final[:4000], "cards": [{"assignee": c.get("assignee"), "title": c.get("title")} for c in cards],
            "sekundy": round((dt.datetime.now() - started).total_seconds(), 1), "stderr_tail": err[-500:]}


def build_commit() -> str:
    for path in (Path("/opt/jarvo/build/BUILD.json"), fl.REPO_ROOT / "build" / "BUILD.json"):
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("repo_rev", "")
        except (OSError, json.JSONDecodeError):
            continue
    res = subprocess.run(["git", "-C", str(fl.REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return res.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", action="append", default=[])
    ap.add_argument("--id", action="append", default=[])
    ap.add_argument("--zbior", choices=("wszystkie",) + ev.ZBIORY, default="wszystkie",
                    help="roboczy (do poprawek), odlozony (tylko bramka) albo wszystkie")
    ap.add_argument("--powtorzenia", type=int, default=1, help="przebiegi każdego scenariusza (kuźnia: 3)")
    ap.add_argument("--judge-model", default=os.environ.get("JARVO_EVAL_JUDGE") or None,
                    help="wymuszony sędzia (domyślnie fleet.yaml evals.judges, inna rodzina niż agent)")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--ustaw-odniesienie", action="store_true", help="zapisz ten przebieg jako punkt odniesienia")
    ap.add_argument("--dry-run", action="store_true", help="tylko wypisz scenariusze")
    ap.add_argument("--out", default=str(fl.REPO_ROOT / "evals" / "results"))
    args = ap.parse_args(argv)
    if not 1 <= args.powtorzenia <= 10:
        ap.error("--powtorzenia: 1–10")

    if os.environ.get("JARVO_EVAL_ALLOW_PROD") != "1" and Path("/opt/data/gateway.pid").exists():
        print("Wygląda na produkcję (działa gateway z dispatcherem). Uruchamiaj evals na stagingu "
              "albo ustaw JARVO_EVAL_ALLOW_PROD=1, jeśli wiesz, co robisz.")
        return 2
    fleet = fl.load_fleet()
    fleet.apply_model_overrides(dict(os.environ))   # ten sam model agentów co w buildzie (JARVO_MODEL_*)
    judges = list(((fleet.raw.get("evals") or {}).get("judges")) or [])
    agents = args.agent or [a.name for a in fleet.active()]
    tokens = list(ev.kanarki(fl.REPO_ROOT).values())
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = Path(args.out)
    out_dir = root / stamp
    total = passed = unjudged = 0
    alarm = False
    commit = build_commit()
    summary_all = {}
    for agent in agents:
        spec = ev.wczytaj(fl.REPO_ROOT, agent)
        agent_model = ev.model_z_buildu(agent) or fleet.model_for(fleet.agent(agent).model_tier)
        model = ev.wybierz_sedziego(judges, agent_model, args.judge_model)
        records = []
        for scn in spec.get("scenarios", []):
            if args.id and scn["id"] not in args.id:
                continue
            split = ev.zbior(scn)
            if args.zbior != "wszystkie" and split != args.zbior:
                continue
            total += 1
            if args.dry_run:
                print(f"- {agent}/{scn['id']} ({scn.get('type')}, {split})")
                continue
            runs = [run_once(agent, scn, model, args.timeout, tokens) for _ in range(args.powtorzenia)]
            rec = {"agent": agent, "id": scn["id"], "type": scn.get("type"), "zbior": split,
                   **ev.scal(runs), "judge_model": model, "runs": runs}
            passed += rec["pass"] is True
            unjudged += rec["pass"] is None
            alarm |= bool(rec["kanarek"])
            records.append(rec)
            out_dir.mkdir(parents=True, exist_ok=True)
            with (out_dir / f"{agent}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fails = sorted({x for r in runs for x in r["deterministic_fails"]} |
                           {x for r in runs for x in (r["judge"].get("failed") or [])})
            mark = "?" if rec["pass"] is None else "✓" if rec["pass"] else "✗"
            wynik = "nieoceniony (bez sędziego)" if rec["score"] is None else f"wynik {rec['score']:.2f}"
            print(f"{mark} {agent}/{scn['id']} [{split}] {rec['zaliczone']}/{rec['przebiegi']} {wynik}"
                  + (f"  {fails[:4]}" if fails else ""))
        if args.dry_run or not records:
            continue
        summary = ev.podsumuj(records)
        summary_all[agent] = summary
        partial = args.id or args.zbior != "wszystkie"
        ev.dopisz_historie(root, {
            "agent": agent, "data": dt.datetime.now().isoformat(timespec="seconds"), "przebieg": stamp,
            "commit": commit, "model": agent_model, "sedzia": model, "powtorzenia": args.powtorzenia,
            "czesciowy": bool(partial), "podsumowanie": summary})
        base = ev.odniesienie_path(root, agent)
        if base.is_file():
            cmp = ev.porownaj(ev.wczytaj_przebieg(base), records)
            print(f"  ↔ odniesienie: zmiana wyniku {cmp['delta']:+.3f}, lepsze {len(cmp['wygrane'])}, "
                  f"gorsze {len(cmp['przegrane'])}, p={cmp['p']}"
                  + (f"; REGRESJE: {', '.join(cmp['regresje'])}" if cmp["regresje"] else ""))
        if args.ustaw_odniesienie:
            if partial:
                print(f"  ! {agent}: przebieg częściowy (--id/--zbior), punktu odniesienia nie zmieniam")
            elif summary["razem"]["nieocenione"]:
                print(f"  ! {agent}: przebieg bez sędziego (nieocenione scenariusze), punktu odniesienia nie zmieniam")
            else:
                ev.ustaw_odniesienie(root, agent, out_dir)
                print(f"  ✓ {agent}: ten przebieg to nowy punkt odniesienia")
    if args.dry_run:
        print(f"{total} scenariuszy")
        return 0
    if summary_all:
        (out_dir / "podsumowanie.json").write_text(
            json.dumps({"przebieg": stamp, "commit": commit, "powtorzenia": args.powtorzenia, "agenci": summary_all},
                       ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"Wynik: {passed}/{total} zaliczonych · szczegóły: {out_dir}")
    if unjudged:
        print(f"! {unjudged} scenariuszy nieocenionych: brak OPENROUTER_API_KEY, sędzia pominięty (liczą się tylko "
              "twarde sprawdzenia; wynik nie jest pomiarem jakości)")
    if alarm:
        print("ALARM KANARKA: agent przeczytał pliki evals. Wyniki tego przebiegu są niewiarygodne, sprawdź ślady.")
        return 3
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

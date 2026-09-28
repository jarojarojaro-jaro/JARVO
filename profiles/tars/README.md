# tars: Main Judge

Dystrybucja profilu Hermesa dla Jarva: dowódcy floty. Mechanika: [docs/BOSS.md](../../docs/BOSS.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: misja, osobowość, twarde zasady, etykieta, protokół floty |
| `skills/fleet/` | intake, dispatch-playbook, mission-ledger, decision-queue, sdlc-review (sędzia), patrol, daily-brief, weekly-review, onboarding-interview, fleet-improvement, roster (generowany) |
| `scripts/` | `patrol.py` (patrol bez modelu), `fleet_report.py` (+ wrappery `brief_daily.py`, `review_weekly.py`) |
| `cron/jobs.yaml` | patrol co 30 min, brief w dni robocze 07:50, przegląd niedziela 18:50, świeżość wiedzy 1. dnia miesiąca |
| `config.yaml` | model frontier; Telegram bez terminala; pracownik-sędzia (CLI) z terminalem i przeglądarką |
| `quality/rubric.md` | jak oceniamy samego Jarva (evals) |

Sędzia: `skills/fleet/sdlc-review` zastępuje wbudowany skill Hermesa. Rubryki agentów
(`references/rubric-<agent>.md`) generuje `scripts/build.py` z `profiles/<agent>/quality/rubric.md`.

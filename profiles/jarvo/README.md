# jarvo: Main Judge

Dystrybucja profilu Hermesa dla Jarva: dowódcy floty. Mechanika: [docs/BOSS.md](../../docs/BOSS.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: misja, osobowość, twarde zasady, etykieta, protokół floty |
| `skills/fleet/` | 13: intake, wywiad, dispatch-playbook, mission-ledger, decision-queue, sdlc-review (sędzia), patrol, daily-brief, weekly-review, onboarding-interview, fleet-improvement, prosty-polski, schemat, roster (generowany) |
| skille zewnętrzne | 1: `writing-for-agents` (mattpocock/skills, MIT): warsztat pisania SOUL i skilli dla `fleet-improvement` |
| `scripts/` | `patrol.py` (patrol bez modelu), `fleet_report.py` (+ wrappery `brief_daily.py`, `review_weekly.py`), `liczby.py` (liczby floty bez modelu: jakość, eskalacje, awarie, cisza, tokeny; ta sama definicja w Jarvo HQ), `swiezosc.py` (rutyna świeżości wiedzy bez modelu), `kontrakt.py` (linter kontraktu karty dla sędziego), `prosty.py` (prosty polski bez modelu: limity zdań, słowa urzędowe, strona bierna; liczby tygodnia do przeglądu) |
| `cron/jobs.yaml` | patrol co 30 min, brief w dni robocze 07:50, przegląd niedziela 18:50, świeżość wiedzy 1. dnia miesiąca |
| `config.yaml` | model frontier; Telegram bez terminala; narzędzie `schemat` (SVG → PNG) daje wtyczka `jarvo-wiedza`; pracownik-sędzia (CLI) z terminalem i przeglądarką |
| `quality/rubric.md` | jak oceniamy samego Jarva (evals) |

Sędzia: `skills/fleet/sdlc-review` zastępuje wbudowany skill Hermesa. Rubryki agentów
(`references/rubric-<agent>.md`) generuje `scripts/build.py` z `profiles/<agent>/quality/rubric.md`.

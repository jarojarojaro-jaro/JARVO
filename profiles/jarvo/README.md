# jarvo: Main Judge

Dystrybucja profilu Hermesa dla Jarva: dowódcy floty. Mechanika: [docs/BOSS.md](../../docs/BOSS.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: misja, osobowość, twarde zasady, etykieta, protokół floty |
| `skills/fleet/` | 16: intake, wywiad, dispatch-playbook, mission-ledger, decision-queue, sdlc-review (sędzia), patrol, daily-brief, weekly-review, onboarding-interview, fleet-improvement, prosty-polski, schemat, pierwsza-sesja, wgrywanie-stron (strony właściciela na hosting za zgodą), skrzynka-linkow (link od właściciela: pobranie, ocena, szkic w skarbcu), roster (generowany) |
| skille zewnętrzne | 3: `writing-for-agents` (mattpocock/skills, MIT): warsztat pisania SOUL i skilli dla `fleet-improvement`; wspólny `konwersja-plikow` (plik → inny format: zdjęcia, wideo, audio, PDF, Word; plik bez metadanych, np. GPS albo autor dokumentu); wspólny `odczyt-ekranu` (tekst ze zrzutu ekranu, skanu albo PDF: Indra OCR, zapas Tesseract); na czacie bez terminala, więc zamianę pliku i odczyt obrazu robi Ręka (karta) |
| `scripts/` | `patrol.py` (patrol bez modelu), `fleet_report.py` (+ wrappery `brief_daily.py`, `review_weekly.py`), `liczby.py` (liczby floty bez modelu: jakość, eskalacje, awarie, cisza, tokeny; ta sama definicja w Jarvo HQ), `swiezosc.py` (rutyna świeżości wiedzy bez modelu), `kontrakt.py` (linter kontraktu karty dla sędziego), `prosty.py` (prosty polski bez modelu: limity zdań, słowa urzędowe, strona bierna; liczby tygodnia do przeglądu), `raport_strona.py` (przegląd tygodnia jako strona w HQ bez modelu: kafle, paski jakości i tokenów, link na 7 dni), `lekcje.py` (księga lekcji bez modelu: gotowe do propozycji, przeterminowane, skutek wdrożonych z evals), `poczekalnia.py` (poczekalnia skilli agentów: lista ze skanem, zatwierdzenie przypięte do odcisku, odrzucenie), `wgraj.py` (wgrywanie stron na hosting przez SSH: `sprawdz`, `plan`, `wgraj --odcisk`, `cofnij`, `kopie`, `z-buildu`, `podglad`; jedno połączenie, kopia na serwerze, weryfikacja sumami, tag `wgranie-…` i `main`), `pobierz_link.py` (skrzynka linków bez modelu: wpis X przez fxtwitter, film YouTube przez `yt-dlp -J`, strona przez trafilatura; `--wideo` 360p, `--transkrypcja` skryptem `transkrypcja-filmu`; na czacie woła go narzędzie `pobierz_link`) |
| `cron/jobs.yaml` | patrol co 30 min, brief w dni robocze 07:50, przegląd niedziela 18:50, świeżość wiedzy 1. dnia miesiąca |
| `config.yaml` | model frontier; Telegram bez terminala; narzędzia `schemat` (SVG → PNG) i `pobierz_link` (skrzynka linków) daje wtyczka `jarvo-wiedza`; pracownik-sędzia (CLI) z terminalem i przeglądarką |
| `quality/rubric.md` | jak oceniamy samego Jarva (evals) |

Sędzia: `skills/fleet/sdlc-review` zastępuje wbudowany skill Hermesa. Rubryki agentów
(`references/rubric-<agent>.md`) generuje `scripts/build.py` z `profiles/<agent>/quality/rubric.md`.

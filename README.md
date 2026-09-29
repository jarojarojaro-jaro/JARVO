# Jarvo

Prywatny asystent AI zbudowany na [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(Nous Research). Na zewnątrz jeden agent, a w środku flota wyspecjalizowanych profili („snajperów”)
prowadzona przez **Jarva**, czyli Main Judge'a. Jarvo przyjmuje zlecenia, rozdziela je, ocenia wyniki,
pilnuje terminów i niczego nie zapomina. Z każdym specjalistą można też rozmawiać bezpośrednio.

| Agent | Rola |
|---|---|
| 🛰️ `jarvo` | Main Judge: przyjmuje zlecenia, planuje misje, rozdziela karty, ocenia, raportuje, patroluje |
| 🔎 `jarvo-sherlock` | detektyw researchu: wiele źródeł, weryfikacja faktów, raporty z cytatami |
| 🌐 `jarvo-web` | Web Senior Dev: brand z URL, audyty, strony i landingi, SEO, favicony, obrazy |
| 🎬 `jarvo-studio` | marketing i kreacja: grafiki social, obrazy AI (OpenRouter), copy PL, kampanie |
| 🎥 `jarvo-wideo` | wideograf: krótkie filmy z tematu (lektor PL, napisy karaoke, stock/AI), warianty A/B, montaż, klipy z nagrań |
| 📈 `jarvo-ads` | specjalista Ads: Meta i Google Ads, kampanie, testy A/B/C, optymalizacja, raporty; wydaje tylko w kopercie z kodem |
| 🦾 `jarvo-reka` | prawa ręka: generalista ze wszystkimi skillami, składa pakiety misji, dokumenty, prototypy |

## Jarvo HQ

Dashboard floty w przeglądarce: budynek z pokojami agentów, dymki z tym, co każdy robi teraz, podgląd pracy
na żywo, wyniki, decyzje i czat z Jarvem albo dowolnym agentem. Szczegóły: [docs/HQ.md](docs/HQ.md).
Demo bez serwera: `python3 scripts/hqbuild.py --demo build/hq-demo`.

## Szybki start

Instalacja lokalna jednym poleceniem (macOS, Linux, WSL2; repo do `~/jarvo`, flota w `~/jarvo-local`,
potem http://localhost:9119/base):

```bash
curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.sh | bash
# Windows (PowerShell):  irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.ps1 | iex
# z istniejącego klonu:  bash scripts/local-up.sh   (stop: bash scripts/local-up.sh down)
```

Praca z repo:

```bash
make dev-deps        # zależności testów i walidacji (pytest, pyyaml z requirements-dev.txt)
make validate        # walidacja repo: fleet ↔ profile, skille, evals, sekrety, dokumentacja ↔ kod
make test            # testy (pytest): walidator, patrol, raporty, build, skrypty agentów
make models          # czy modele z fleet.yaml istnieją u wybranego dostawcy (openai-codex: brak listy, pomija)
```

Piaskownica Claude Code (kontener za proxy): `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh`.

Wdrożenie na VPS krok po kroku: **[docs/RUNBOOK.md](docs/RUNBOOK.md)** (bootstrap serwera, Telegram,
sekrety, `scripts/deploy.sh --first-run`, test, rutyny, backupy). Cała flota mieści się na VPS
**4 vCPU / 8 GB RAM / 80 GB**: obraz 4,4 GB, w spoczynku ok. 0,7 GB RAM (pomiary: [VPS.md §2](docs/VPS.md#2-rozmiar-serwera)).

## Mapa repo

| Ścieżka | Co tam jest |
|---|---|
| [`fleet.yaml`](fleet.yaml) | rejestr floty: agenci, modele (domyślnie `openai-codex`, presety OpenRouter i CommandCode), tematy Telegrama, wspólne katalogi |
| [`profiles/<agent>/`](profiles) | każdy agent jako dystrybucja Hermesa: `SOUL.md`, `config.yaml`, skille, skrypty, rubryka, toolbox |
| [`profiles/_host/`](profiles/_host) | profil hosta: gateway z multipleksacją, trasy Telegrama, dispatcher kanbana |
| [`shared/protocol/`](shared/protocol) | kontrakt zlecenia wstrzykiwany do każdego SOUL (karta: CEL, DoD, WYJŚCIA, GRANICE…) |
| [`shared/security/deny.yaml`](shared/security/deny.yaml) | zakazy dla całej floty, dopinane do `approvals.deny` każdego profilu |
| [`shared/skills/`](shared/skills) | skille własne wspólne dla kilku agentów (`graf-kodu` u Weba i Ręki, `transkrypcja-filmu` (tekst mowy z linku do filmu) u Sherlocka, Wideografa i Ręki) |
| [`shared/calibration/`](shared/calibration) | kalibracja SOUL pod rodzinę modelu (przy buildzie) |
| [`shared/templates/`](shared/templates) | szablony SOUL, skilla, evals i toolboxa (`make new-agent`) |
| [`vendor/skills.lock.yaml`](vendor/skills.lock.yaml) | skille zewnętrzne przypięte do commitów (licencje w [docs/SOURCES.md](docs/SOURCES.md)) |
| [`evals/<agent>/`](evals) | scenariusze testowe zachowań (w zakresie, poza zakresem, routing, protokół, bezpieczeństwo) |
| [`security/redteam/`](security/redteam) | red team na promptfoo: ataki na agentów (`scripts/redteam.sh`) |
| [`scripts/`](scripts) | build dystrybucji, walidator, deploy, instalacja floty, backupy, evals, narzędzia |
| [`hq/`](hq) | Jarvo HQ: plugin dashboardu (backend, frontend, demo) |
| [`infra/`](infra) | obraz `jarvo-hermes` (Hermes + narzędzia), docker compose z sidecarami, szablony env |
| [`knowledge/`](knowledge) | szablon brand kitu kopiowany na serwer |
| [`branding/`](branding) | skórka Jarvo: terminal, favicon, motyw i tłumaczenie dashboardu |
| [`site/`](site) | landing jarvo.pl (`scripts/deploy-site.sh`) |
| [`install.sh`](install.sh), [`install.ps1`](install.ps1) | instalator jednym poleceniem (macOS/Linux/WSL2, Windows) |
| [`requirements-dev.txt`](requirements-dev.txt) | zależności testów i walidacji (`make dev-deps`) |
| [`tests/`](tests) | testy pytest |
| [`docs/`](docs) | dokumentacja (niżej) |

## Dokumentacja

| Dokument | O czym |
|---|---|
| [PLAN.md](docs/PLAN.md) | wizja, architektura, roadmapa, decyzje |
| [BOSS.md](docs/BOSS.md) | jak Jarvo trzyma wszystko w kupie: misje, kolejka decyzji, patrol, sędziowanie, eskalacje |
| [FLEET.md](docs/FLEET.md) | specyfikacja agentów floty v1 |
| [PROFILE-SPEC.md](docs/PROFILE-SPEC.md) | anatomia agenta: 10 warstw, kontrakt zlecenia, Definition of Ready |
| [TOOLBOX.md](docs/TOOLBOX.md) | narzędzia open-source per agent i stan instalacji w obrazie |
| [VPS.md](docs/VPS.md) | infrastruktura: topologia, bezpieczeństwo, backupy, monitoring |
| [HQ.md](docs/HQ.md) | Jarvo HQ: GUI floty, architektura, bezpieczeństwo, pokoje |
| [KLIPY.md](docs/KLIPY.md) | projekt clipmakera Wideografa: długie nagranie → edytowalne rolki 9:16 z napisami karaoke |
| [ADS.md](docs/ADS.md) | projekt agenta reklam płatnych `jarvo-ads` i Skarbca (strażnik budżetu) |
| [RUNBOOK.md](docs/RUNBOOK.md) | wdrożenie i codzienna obsługa krok po kroku |
| [SOURCES.md](docs/SOURCES.md) | źródła, atrybucje i licencje |
| [JARVO-CALOSC.md](docs/JARVO-CALOSC.md) | całość od A do Z w jednym pliku (kontekst na start sesji) |

## Jak to działa w skrócie

```
Ty (Telegram DM / "Jarvo HQ")
 └─ gateway Hermesa (multipleks profili) ─┬─ DM, wątek General → jarvo (Main Judge)
                                          └─ wątki Sherlock / Web / Studio / Wideo / Ads / Ręka → snajper
jarvo: intake → MISSION.md → karty kanban (CEL, DoD, GRANICE) → snajperzy pracują w swoich katalogach
    → kanban_request_review → jarvo sędziuje (rubryka agenta) → poprawki albo akceptacja → raport efektów
patrol co 30 min (skrypt bez modelu; budzi Jarva tylko przy anomaliach), brief rano, przegląd tygodnia
```

Zasady: nie forkujemy Hermesa, repo jest źródłem prawdy (na serwerze nic nie edytujemy ręcznie),
działania nieodwracalne (publikacja, wdrożenie produkcyjne, płatności, wysyłka) tylko za Twoją zgodą.

# TARS

Prywatny asystent AI zbudowany na [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(Nous Research). Na zewnątrz jeden agent, a w środku flota wyspecjalizowanych profili („snajperów”)
prowadzona przez **TARS-a**, czyli Main Judge'a. TARS przyjmuje zlecenia, rozdziela je, ocenia wyniki,
pilnuje terminów i niczego nie zapomina. Z każdym specjalistą można też rozmawiać bezpośrednio.

| Agent | Rola |
|---|---|
| 🛰️ `tars` | Main Judge: przyjmuje zlecenia, planuje misje, rozdziela karty, ocenia, raportuje, patroluje |
| 🔎 `tars-sherlock` | detektyw researchu: wiele źródeł, weryfikacja faktów, raporty z cytatami |
| 🌐 `tars-web` | Web Senior Dev: brand z URL, audyty, strony i landingi, SEO, favicony, obrazy |
| 🎬 `tars-studio` | marketing i kreacja: grafiki social, filmy z kodu, obrazy/wideo AI (OpenRouter), copy PL |
| 🦾 `tars-reka` | prawa ręka: generalista ze wszystkimi skillami, składa pakiety misji, dokumenty, prototypy |

## Szybki start

```bash
make validate        # walidacja repo: fleet ↔ profile, skille, evals, sekrety
make test            # testy (pytest): walidator, patrol, raporty, build, skrypty agentów
make models          # czy modele z fleet.yaml istnieją na OpenRouter
```

Wdrożenie na VPS krok po kroku: **[docs/RUNBOOK.md](docs/RUNBOOK.md)** (bootstrap serwera, Telegram,
sekrety, `scripts/deploy.sh --first-run`, test, rutyny, backupy).

## Mapa repo

| Ścieżka | Co tam jest |
|---|---|
| [`fleet.yaml`](fleet.yaml) | rejestr floty: agenci, modele (OpenRouter), tematy Telegrama, wspólne katalogi |
| [`profiles/<agent>/`](profiles) | każdy agent jako dystrybucja Hermesa: `SOUL.md`, `config.yaml`, skille, skrypty, rubryka, toolbox |
| [`profiles/_host/`](profiles/_host) | profil hosta: gateway z multipleksacją, trasy Telegrama, dispatcher kanbana |
| [`shared/protocol/`](shared/protocol) | kontrakt zlecenia wstrzykiwany do każdego SOUL (karta: CEL, DoD, WYJŚCIA, GRANICE…) |
| [`vendor/skills.lock.yaml`](vendor/skills.lock.yaml) | skille zewnętrzne przypięte do commitów (licencje w [docs/SOURCES.md](docs/SOURCES.md)) |
| [`evals/<agent>/`](evals) | scenariusze testowe zachowań (routing, protokół, bezpieczeństwo, poza zakresem) |
| [`scripts/`](scripts) | build dystrybucji, walidator, deploy, instalacja floty, backupy, evals, narzędzia |
| [`infra/`](infra) | obraz `tars-hermes` (Hermes + narzędzia), docker compose z sidecarami, szablony env |
| [`knowledge/`](knowledge) | szablony wiedzy (brand kit) kopiowane na serwer |
| [`tests/`](tests) | testy pytest |
| [`docs/`](docs) | dokumentacja (niżej) |

## Dokumentacja

| Dokument | O czym |
|---|---|
| [PLAN.md](docs/PLAN.md) | wizja, architektura, roadmapa, decyzje |
| [BOSS.md](docs/BOSS.md) | jak TARS trzyma wszystko w kupie: misje, kolejka decyzji, patrol, sędziowanie, eskalacje |
| [FLEET.md](docs/FLEET.md) | specyfikacja agentów floty v1 |
| [PROFILE-SPEC.md](docs/PROFILE-SPEC.md) | anatomia agenta: 10 warstw, kontrakt zlecenia, Definition of Ready |
| [TOOLBOX.md](docs/TOOLBOX.md) | narzędzia open-source per agent i stan instalacji w obrazie |
| [VPS.md](docs/VPS.md) | infrastruktura: topologia, bezpieczeństwo, backupy, monitoring |
| [RUNBOOK.md](docs/RUNBOOK.md) | wdrożenie i codzienna obsługa krok po kroku |
| [SOURCES.md](docs/SOURCES.md) | źródła, atrybucje i licencje |

## Jak to działa w skrócie

```
Ty (Telegram DM / "TARS HQ")
 └─ gateway Hermesa (multipleks profili) ─┬─ DM, wątek General → tars (Main Judge)
                                          └─ wątki Sherlock / Web / Studio / Ręka → snajper
tars: intake → MISSION.md → karty kanban (CEL, DoD, GRANICE) → snajperzy pracują w swoich katalogach
    → kanban_request_review → tars sędziuje (rubryka agenta) → poprawki albo akceptacja → raport efektów
patrol co 30 min (skrypt bez modelu; budzi TARS-a tylko przy anomaliach), brief rano, przegląd tygodnia
```

Zasady: nie forkujemy Hermesa, repo jest źródłem prawdy (na serwerze nic nie edytujemy ręcznie),
działania nieodwracalne (publikacja, wdrożenie produkcyjne, płatności, wysyłka) tylko za Twoją zgodą.

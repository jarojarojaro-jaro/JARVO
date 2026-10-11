# Jarvo

Prywatny asystent AI zbudowany na [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(Nous Research). Na zewnątrz jeden agent, a w środku flota wyspecjalizowanych profili („snajperów”)
prowadzona przez **Jarva**, czyli Main Judge'a. Jarvo przyjmuje zlecenia, rozdziela je, ocenia wyniki,
pilnuje terminów i niczego nie zapomina. Z każdym specjalistą można też rozmawiać bezpośrednio.

| Agent | Rola |
|---|---|
| 🛰️ `jarvo` | Main Judge: przyjmuje zlecenia, planuje misje, rozdziela karty, ocenia, raportuje, patroluje |
| 🔎 `jarvo-sherlock` | detektyw researchu: wiele źródeł, weryfikacja faktów, raporty z cytatami |
| 🌐 `jarvo-web` | Web Senior Dev: brand z URL, inspiracje z branży (Inspo), audyty, strony i landingi, SEO, favicony, obrazy |
| 🎬 `jarvo-studio` | marketing i kreacja: grafiki social, obrazy AI (OpenRouter), copy PL, kampanie |
| 🎥 `jarvo-wideo` | wideograf: krótkie filmy z tematu (lektor PL, napisy karaoke, stock/AI), warianty A/B, montaż, klipy z nagrań, typografia jak z montażu, explainery z wykresem i tablicą, żywy obraz w 35 stylach malarskich, żywe schematy na X i Instagram |
| 📈 `jarvo-ads` | specjalista Ads: Meta i Google Ads, kampanie, testy A/B/C, raporty; przygotowuje paczkę do publikacji, publikujesz Ty |
| 🎯 `jarvo-lowca` | łowca leadów: sygnały zakupowe z KRS, CEIDG, przetargów i stron firm → ranking firm z „dlaczego teraz” i opublikowanym kontaktem; nic nie wysyła |
| 📱 `jarvo-mobile` | twórca aplikacji: uczciwe „natywna czy PWA” z kosztami, darmowy audyt mobilny (App Store, Google Play, linki strona → aplikacja, PWA), aplikacje Expo ze zgodnością ze sklepami od planu (także ze strony firmy), podgląd w HQ i w Expo Go, bramka jakości, pakiet do sklepów z listą 44 punktów, wydanie i poprawki OTA za zgodą, kontrola paczek npm; konta zawsze właściciela |
| 🦾 `jarvo-reka` | prawa ręka: generalista ze wszystkimi skillami, składa pakiety misji, dokumenty, prototypy |

## Jarvo HQ

Dashboard floty w przeglądarce: budynek z pokojami agentów, dymki z tym, co każdy robi teraz, podgląd pracy
na żywo, wyniki, decyzje, czat z Jarvem albo dowolnym agentem i konwerter plików (zdjęcie, film, dźwięk, PDF, Word
→ inny format na serwerze). Szczegóły: [docs/HQ.md](docs/HQ.md).
Demo bez serwera: `python3 scripts/hqbuild.py --demo build/hq-demo`.

## Szybki start

Instalacja lokalna jednym poleceniem (Linux, macOS, Windows; repo do `~/jarvo`, flota w `~/jarvo-local`,
potem http://localhost:9119/base). Instalator sam doinstalowuje wszystko, czego brakuje: na Linuksie
i w WSL pakiety i Docker Engine, na macOS Homebrew, bash, git, Pythona i Dockera w darmowej Colimie
(działający Docker Desktop albo OrbStack zostaje), na Windowsie WSL2 (jeden restart, potem dalej sam),
własną dystrybucję Linuksa `Jarvo` i Dockera w niej. Obraz floty pobiera gotowy z GHCR. Prywatne repo:
instalator poprosi o klucz dostępu (`JARVO_TOKEN`). Szczegóły: [docs/INSTALER.md](docs/INSTALER.md):

```bash
curl -fsSL https://jarvo.pl/install.sh | bash                 # Linux, macOS (Terminal)
# Windows (PowerShell, zwykły użytkownik):  irm https://jarvo.pl/install.ps1 | iex
# z GitHuba (repo publiczne): https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.sh (i .ps1)
# bez pytań:  curl -fsSL …/install.sh | JARVO_PROVIDER=openrouter JARVO_KEY=sk-… JARVO_YES=1 bash
# potem:      jarvo status | logs | chat | update | down | uninstall      (jarvo help: wszystkie)
# jarvo update = git pull + ten sam instalator (nowe programy hosta, gdy wersja Jarvo ich wymaga)
# z klonu:    bash bin/jarvo up   (stop: bash bin/jarvo down)
```

Praca z repo:

```bash
make dev-deps        # zależności testów i walidacji (pytest, pyyaml, shellcheck z requirements-dev.txt)
make validate        # walidacja repo: fleet ↔ profile, skille, evals, sekrety, dokumentacja ↔ kod
make test            # testy (pytest): walidator, patrol, raporty, build, skrypty agentów
make models          # czy modele z fleet.yaml istnieją u wybranego dostawcy (openai-codex: brak listy, pomija)
```

Piaskownica Claude Code (kontener za proxy): `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh`.

Wdrożenie na VPS krok po kroku: **[docs/RUNBOOK.md](docs/RUNBOOK.md)** (bootstrap serwera, Telegram,
sekrety, `scripts/deploy.sh --first-run`, test, rutyny, backupy). Cała flota mieści się na VPS
**4 vCPU / 8 GB RAM / 80 GB**: obraz 4,8 GB, w spoczynku ok. 0,7 GB RAM (pomiary: [VPS.md §2](docs/VPS.md#2-rozmiar-serwera)).

## Mapa repo

| Ścieżka | Co tam jest |
|---|---|
| [`fleet.yaml`](fleet.yaml) | rejestr floty: agenci, modele (domyślnie `openai-codex`, presety OpenRouter i CommandCode), tematy Telegrama, wspólne katalogi |
| [`profiles/<agent>/`](profiles) | każdy agent jako dystrybucja Hermesa: `SOUL.md`, `config.yaml`, skille, skrypty, rubryka, toolbox |
| [`profiles/_host/`](profiles/_host) | profil hosta: gateway z multipleksacją, trasy Telegrama, dispatcher kanbana |
| [`shared/protocol/`](shared/protocol) | kontrakt zlecenia wstrzykiwany do każdego SOUL (karta: CEL, DoD, WYJŚCIA, GRANICE…) |
| [`shared/security/deny.yaml`](shared/security/deny.yaml) | zakazy dla całej floty, dopinane do `approvals.deny` każdego profilu |
| [`shared/skills/`](shared/skills) | skille własne wspólne dla kilku agentów (`graf-kodu` u Weba i Ręki, `transkrypcja-filmu` (tekst mowy z linku do filmu) u Sherlocka, Wideografa i Ręki, `hooki` (trzy warstwy hooka, 18 taktyk) u Studia, Wideografa i Ads, `izometria` (figury izometryczne ze świeceniem: strona, PNG, film) u Weba, Studia i Wideografa, `konwersja-plikow` (plik → inny format: zdjęcia, wideo, audio, PDF, Word; plik bez metadanych, np. GPS) u wszystkich, `ostrozna-przegladarka` (jedna próba zapasową przeglądarką Camoufox po odmowie strony) u Łowcy i Sherlocka) |
| [`shared/calibration/`](shared/calibration) | kalibracja SOUL pod rodzinę modelu (przy buildzie) |
| [`shared/templates/`](shared/templates) | szablony SOUL, skilla, evals i toolboxa (`make new-agent`) |
| [`vendor/skills.lock.yaml`](vendor/skills.lock.yaml) | skille zewnętrzne przypięte do commitów (licencje w [docs/SOURCES.md](docs/SOURCES.md)) |
| [`vendor/zrodla.yaml`](vendor/zrodla.yaml) | spis wszystkich repo, z których bierzemy kod, skille albo wzorce, i obserwowanych: status i ostatni przejrzany commit; nowości pokazuje `scripts/zrodla.py sprawdz`, wdrożenie tylko po zgodzie właściciela |
| [`vendor/skan-wyjatki.yaml`](vendor/skan-wyjatki.yaml) | przejrzane fałszywe alarmy skanu skilli zewnętrznych (`scripts/skan_skilli.py`), przypięte do commitu źródła |
| [`evals/<agent>/`](evals) | scenariusze testowe zachowań (w zakresie, poza zakresem, routing, protokół, bezpieczeństwo) |
| [`security/redteam/`](security/redteam) | red team na promptfoo: ataki na agentów (`scripts/redteam.sh`) |
| [`scripts/`](scripts) | build dystrybucji, walidator, deploy, instalacja floty, backupy, evals, narzędzia |
| [`hq/`](hq) | Jarvo HQ: plugin dashboardu (backend, frontend, demo) |
| [`infra/`](infra) | obraz `jarvo-hermes` (Hermes + narzędzia), docker compose z sidecarami, szablony env |
| [`knowledge/`](knowledge) | szablon brand kitu kopiowany na serwer |
| [`branding/`](branding) | skórka Jarvo: terminal, favicon, motyw i tłumaczenie dashboardu |
| [`site/`](site) | landing jarvo.pl (`scripts/deploy-site.sh`) |
| [`install.sh`](install.sh), [`install.ps1`](install.ps1) | instalator jednym poleceniem: Linux/WSL2 (pakiety, Docker Engine), macOS (Homebrew, Colima), Windows (WSL2, dystrybucja `Jarvo`, Docker w niej) |
| [`bin/jarvo`](bin/jarvo) | polecenie użytkownika po instalacji: `up`, `down`, `status`, `logs`, `update`, `chat`, `open`, `pliki`, `autostart`, `uninstall` |
| [`requirements-dev.txt`](requirements-dev.txt) | zależności testów i walidacji (`make dev-deps`) |
| [`tests/`](tests) | testy pytest |
| [`wiedza/`](wiedza) | skarbiec wiedzy floty (drugi mózg): `wiedza.py` i `SCHEMA.md`, projekt w [docs/WIEDZA.md](docs/WIEDZA.md) |
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
| [EDYTOR-PLAN.md](docs/EDYTOR-PLAN.md) | plan edytora filmów HQ jak CapCut: przejścia, szybkie cięcie, audio (efekty, lektor, nagranie), kolor, naklejki, animacje klipów; stan kroków |
| [KLIPY.md](docs/KLIPY.md) | projekt clipmakera Wideografa: długie nagranie → edytowalne rolki 9:16 z napisami karaoke |
| [ADS.md](docs/ADS.md) | projekt agenta reklam płatnych `jarvo-ads` i Skarbca (strażnik budżetu) |
| [LEADY.md](docs/LEADY.md) | projekt Łowcy leadów: sygnały zakupowe z oficjalnych źródeł → lista firm z „dlaczego teraz” |
| [WIEDZA.md](docs/WIEDZA.md) | projekt skarbca wiedzy (drugi mózg floty): notatki Markdown z linkami, wtyczka `jarvo-wiedza`, zakładka „Wiedza” z grafem |
| [RUNBOOK.md](docs/RUNBOOK.md) | wdrożenie i codzienna obsługa krok po kroku |
| [INSTALER.md](docs/INSTALER.md) | instalator jednym poleceniem na Linuksie, macOS i Windowsie: jak działa na każdym systemie, aktualizacje, testy, etapy |
| [ROZWOJ-FLOTY.md](docs/ROZWOJ-FLOTY.md) | plan dopracowania agentów (Łowca, Ads, Ręka, Sherlock, Studio) i audyt zgodności jako skill Weba |
| [MOBILE.md](docs/MOBILE.md) | projekt Twórcy aplikacji `jarvo-mobile`: pełny proces od pomysłu do sklepu (darmowy audyt mobilny, prototyp Expo na telefonie, Android w dashboardzie i iOS w chmurze, bramka aplikacji, lista kontrolna sklepów, zrzuty, odrzucenia, aplikacja ze strony, utrzymanie); etapy i stan w §16 |
| [SOURCES.md](docs/SOURCES.md) | źródła, atrybucje i licencje |
| [JARVO-CALOSC.md](docs/JARVO-CALOSC.md) | całość od A do Z w jednym pliku (kontekst na start sesji) |

## Jak to działa w skrócie

```
Ty (Telegram DM / "Jarvo HQ")
 └─ gateway Hermesa (multipleks profili) ─┬─ DM, wątek General → jarvo (Main Judge)
                                          └─ wątki Sherlock / Web / Studio / Wideo / Ads / Łowca / Ręka → snajper
jarvo: intake → MISSION.md → karty kanban (CEL, DoD, GRANICE) → snajperzy pracują w swoich katalogach
    → kanban_request_review → jarvo sędziuje (rubryka agenta) → poprawki albo akceptacja → raport efektów
patrol co 30 min (skrypt bez modelu; budzi Jarva tylko przy anomaliach), brief rano, przegląd tygodnia
```

Zasady: nie forkujemy Hermesa, repo jest źródłem prawdy (na serwerze nic nie edytujemy ręcznie),
działania nieodwracalne (publikacja, wdrożenie produkcyjne, płatności, wysyłka) tylko za Twoją zgodą.

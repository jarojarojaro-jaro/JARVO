# Anatomia agenta Jarvo (kontrakt profilu v1)

Ten dokument mówi, **z czego składa się każdy agent** we flocie i kiedy agent jest „gotowy”.
Dotyczy wszystkich profili z [`fleet.yaml`](../fleet.yaml). Szablony są w [`shared/templates/`](../shared/templates/).

Cel: każdy agent jest *serio* rozbudowany, czyli ma tożsamość, procedury, wiedzę, narzędzia,
granice i testy, a nie tylko dobry prompt.

---

## Dziesięć warstw agenta

```
 ┌───────────────────────────────────────────────────────────────┐
 │ 1. Tożsamość (SOUL.md = main prompt)          zawsze w kontekście │
 ├───────────────────────────────────────────────────────────────┤
 │ 2. Workflowy (skills/*/*/SKILL.md)            ładowane na żądanie │
 │ 3. Wiedza (references/ skilli, knowledge/)    ładowana na żądanie │
 │ 4. Skrypty (scripts/ profilu)                 wykonywane, nie czytane │
 ├───────────────────────────────────────────────────────────────┤
 │ 5. Toolbox (narzędzia OSS na VPS)             toolbox.yaml       │
 │ 6. Integracje (mcp_servers w config.yaml, pluginy, .env)         │
 │ 7. Pamięć (własna + wspólna o użytkowniku)                       │
 │ 8. Rutyny (cron/jobs.yaml → jobs.json przy buildzie)             │
 ├───────────────────────────────────────────────────────────────┤
 │ 9. Granice (autonomia, toolsety, sandbox, zgody)                 │
 │ 10. Jakość (DoD, rubryka sędziego, evals)                        │
 └───────────────────────────────────────────────────────────────┘
```

Najważniejsza zasada architektury kontekstu (wynika z tego, jak działa Hermes):
**SOUL.md jest krótki i stały, a głębia siedzi w skillach.** SOUL jest wysyłany w każdym
zapytaniu i musi być bajtowo stały przez całą rozmowę (cache promptów). Skille działają
jak *progressive disclosure*: model widzi w prompcie tylko ich listę z opisami, a pełną
treść wczytuje dopiero wtedy, gdy jej potrzebuje. Dlatego agent może mieć 30 skilli
i 200 stron wiedzy, nie płacąc za to w każdej wiadomości.

---

## 1. Tożsamość: `SOUL.md` (main prompt)

Budżet: **~1500–3000 tokenów**. Walidator pilnuje twardego limitu ~3200 tokenów liczonego razem z protokołem floty
(~1200) i najdłuższą możliwą kalibracją. Wszystko dłuższe należy do skilli.

Walidator wymaga sekcji `## Misja` i `## Osobowość` oraz znacznika `<!-- Jarvo:PROTOCOL -->` (orkiestrator także
`<!-- Jarvo:ROSTER -->`); bez znacznika build się zatrzymuje. Nowy profil zakłada `scripts/new-agent.py`.
Zalecane sekcje (szablon: `shared/templates/SOUL.template.md`; Jarvo i prawa ręka mają własny układ):

| Sekcja | Zawartość |
|---|---|
| Misja | Jedno zdanie: po co istnieję |
| Osobowość | Ton, styl, parametry Jarvo (np. szczerość 90%, humor 60%) |
| Zakres | Co robię (lista kompetencji) |
| Poza zakresem | Czego nie robię i komu to oddaję (zawsze przez Jarva) |
| Zasady pracy | 5–10 zasad specyficznych dla dziedziny („najpierw pomiar, potem optymalizacja”) |
| Mapa workflowów | Która sytuacja → który skill (routing wewnętrzny) |
| Standard jakości | Moja Definition of Done w skrócie |
| Autonomia i bezpieczeństwo | Co wolno bez pytania, co wymaga zgody, czego nigdy |
| Protokół zleceń | Jak przyjmuję kartę i jak oddaję wynik (sekcja „Kontrakt zlecenia” niżej) |
| Formaty wyjścia | Jak wyglądają moje raporty i pliki |
| Język | Polski z Tobą; techniczne artefakty w języku dziedziny |

---

## 2. Workflowy: skille-procedury

Workflow to **powtarzalna procedura z punktami kontrolnymi**, zapisana jako skill
(`skills/<kategoria>/<nazwa>/SKILL.md`, format agentskills.io, zgodny z Hermesem).

Każdy workflow ma (szablon: `shared/templates/SKILL.template.md`):
- **Kiedy użyć i kiedy nie** (to trafia do `description`, więc od tego zależy, czy model w ogóle go wybierze),
- **Wejścia:** czego potrzebuje, a jeśli czegoś brakuje, o co zapytać,
- **Kroki** z punktami kontrolnymi („zanim przejdziesz dalej, sprawdź…”),
- **Wyjścia:** pliki i raport w ustalonym formacie,
- **Definition of Done** workflowu,
- **Typowe błędy** i jak ich unikać,
- odwołania do `references/` (wiedza) i skryptów profilu `$HERMES_HOME/scripts/<plik>` (automaty).

Zasada: **wszystko, co deterministyczne, idzie do skryptu.** Konwersję obrazów, generowanie
faviconów czy audyt Lighthouse robi skrypt, a model decyduje, interpretuje i składa wyniki.
Skrypty są tańsze, szybsze i powtarzalne.

Rodzaje skilli agenta:
- **workflowy główne:** 3–8 najważniejszych procedur dziedziny,
- **playbooki:** krótsze przepisy na konkretne sytuacje,
- **skille zewnętrzne:** z katalogu Hermesa [H] i z repozytoriów OSS przypiętych do commitu, przypisane agentom
  w [`vendor/skills.lock.yaml`](../vendor/skills.lock.yaml); build dokłada je z licencją (`LICENSE-UPSTREAM`) i `.vendored.json`,
- **skille wspólne floty:** własne skille w `shared/skills/` (narzędziowe jak `graf-kodu`, metodyczne jak `hooki`), przypisywane agentom w tym samym locku.

---

## 3. Wiedza: knowledge packi

Wiedza dziedzinowa w plikach Markdown w `skills/<kategoria>/<workflow>/references/` (przy workflow,
który z niej korzysta) albo w `knowledge/` profilu (wiedza przekrojowa).

Zasady:
- **źródło i data** przy każdym pakiecie (`source:`, `reviewed:`), bo wiedza webowa i marketingowa się starzeje,
- **checklisty zamiast esejów:** model lepiej wykonuje listy kontrolne niż ogólne porady,
- **przykłady wzorcowe** (golden examples): dobry raport, dobra karta, dobra strona,
- **przegląd świeżości** co miesiąc (rutyna Jarva `jarvo-knowledge-freshness` wskazuje pakiety z `reviewed:` starszym niż 120 dni).

---

## 4. Skrypty

`scripts/` profilu (np. `profiles/jarvo-web/scripts/`): Python, Node lub bash, wołane przez terminal agenta
jako `$HERMES_HOME/scripts/<plik>` (walidator sprawdza, że każde takie odwołanie ma plik).
Każdy skrypt ma `--help`, zwraca JSON lub czytelny raport, ma kod wyjścia ≠ 0 przy błędzie
i nie wymaga interakcji.

---

## 5. Toolbox: narzędzia open-source na VPS

Każdy agent ma `toolbox.yaml` (szablon: `shared/templates/toolbox.template.yaml`), czyli manifest
narzędzi, których potrzebuje. Każde narzędzie ma nazwę, źródło, **przypiętą wersję**,
licencję, sposób instalacji, sposób integracji i komendę healthcheck.

Sposoby integracji (od najlżejszego):
1. **CLI przez terminal + skill**: skill uczy agenta, jak używać narzędzia (większość przypadków),
2. **skrypt w skillu:** opakowanie narzędzia w powtarzalną procedurę,
3. **usługa sidecar** (kontener na VPS), z którą agent rozmawia przez HTTP (SearXNG…); tylko gdy narzędzie musi działać stale, inaczej proces na żądanie w obrazie,
4. **wtyczka Hermesa** z katalogu (np. `openalex`, `langfuse`),
5. **serwer MCP** (np. Netlify, Cloudflare, Figma).

Tak samo robi rdzeń Hermesa („footprint ladder”): nie dodajemy narzędzia do schematu modelu,
jeśli terminal i skill wystarczą, bo każde narzędzie w schemacie kosztuje przy każdym zapytaniu.

Pełna, zweryfikowana lista: [TOOLBOX.md](TOOLBOX.md). Instalacja na VPS: [VPS.md](VPS.md).

---

## 6. Integracje

- serwery MCP agenta w `config.yaml` profilu, sekcja `mcp_servers` (tylko te, których naprawdę używa).
  Hermes czyta MCP wyłącznie z `config.yaml`; plik `mcp.json` w profilu jest ignorowany,
- pluginy Hermesa w `config.yaml` (`plugins.enabled`),
- sekrety **wyłącznie** w `.env` profilu (nigdy w repo); w dystrybucji tylko `env_requires` w `distribution.yaml`.

---

## 7. Pamięć

| Warstwa | Gdzie | Kto pisze |
|---|---|---|
| Pamięć własna agenta | `memories/MEMORY.md` profilu | agent (np. „ta strona używa Tailwind”) |
| Wiedza o Tobie | MVP: `knowledge/user/USER.md` (onboarding) + pamięć użytkownika Jarva; później wspólny provider (np. Honcho) | Jarvo (onboarding), agenci czytają |
| Brand kity | `knowledge/brands/<marka>/` | `jarvo-web` / `jarvo-studio` |
| Historia zleceń | kanban (`kanban.db`) | Jarvo i agenci |

---

## 8. Rutyny

`cron/jobs.yaml` → `cron/jobs.json` przy buildzie: zadania cykliczne agenta. Dziś ma je tylko Jarvo (patrol, poranny brief,
przegląd tygodnia, świeżość wiedzy). Rutyny snajperów (np. monitoring Sherlocka) zakłada Jarvo po Twojej zgodzie.
Z dystrybucji instalują się **wstrzymane**, a włączasz je świadomie.

---

## 9. Granice: autonomia, uprawnienia, sandbox

Poziomy autonomii (każda akcja agenta ma przypisany poziom):

| Poziom | Znaczenie | Przykłady |
|---|---|---|
| **A0** | tylko odczyt i analiza | research, audyt strony |
| **A1** | tworzenie szkiców w swoim workspace | kod strony, grafiki, raporty |
| **A2** | działanie po Twojej zgodzie | wdrożenie strony, publikacja posta, wydatek > limit |
| **A3** | nigdy | płatności, usuwanie cudzych danych, działania na kontach bez zgody |

Mechanizmy techniczne:
- **toolsety:** każdy profil ma włączone tylko potrzebne toolsety, osobno na platformę (np. Jarvo nie ma terminala
  na Telegramie ani w czacie HQ; ma go tylko pracownik-sędzia na CLI); czat HQ to platforma `api_server`,
  ustawiana jawnie jak Telegram (bez `clarify`), inaczej Hermes dałby jej domyślny zestaw (walidator tego pilnuje),
- **sandbox:** `terminal.backend: local` wewnątrz kontenera `jarvo-hermes` (repo i build zamontowane `:ro`),
- **zatwierdzanie komend:** Hermes pyta o ryzykowne komendy, więc nie wyłączamy tego; pracownicy bez człowieka
  (`cron_mode`, `single_query_mode`, `unattended_mode`) mają `deny`,
- **wspólne zakazy floty:** `shared/security/deny.yaml` (zmiana konfiguracji Hermesa, `rm -r` danych floty, eksfiltracja,
  czytanie `.env`, logowanie w cudze konta) build dopina do `approvals.deny` każdego profilu,
- **workspace:** każdy agent ma własny katalog roboczy (`terminal.cwd`), a wyniki oddaje przez kanban (załączniki).

---

## 10. Jakość

- **Definition of Done agenta:** lista warunków, które musi spełnić każdy wynik (w SOUL i w rubryce sędziego),
- **rubryka sędziego:** jak Jarvo ocenia wynik tego agenta (skill `sdlc-review` u Jarva: `references/rubric-<agent>.md` generowane z `quality/rubric.md` agenta),
- **evals:** `evals/<agent>/*.yaml` (szablon: `shared/templates/eval.template.yaml`), czyli scenariusze
  „zlecenie → oczekiwane zachowanie → kryteria”, uruchamiane ręcznie na stagingu (`scripts/evals-staging.sh`) po zmianie
  SOUL lub skilli; CI sprawdza tylko ich strukturę (`validate.py`),
- **ślady i koszty (planowane, faza 6):** Langfuse (wtyczka Hermesa) ma zbierać przebiegi, koszty i oceny sędziego;
  dziś niewłączony w żadnym profilu,
- **pętla błędów:** każda poprawka odesłana przez sędziego jest kandydatem na nowy eval albo poprawkę skilla.

---

## Kontrakt zlecenia (wspólny protokół Jarvo ↔ agenci)

To jedyna wspólna treść procedur wszystkich agentów. To protokół, a nie wiedza dziedzinowa. Poza nim build dokłada
każdemu agentowi kalibrację pod model, wspólne zakazy (`approvals.deny`) i model zapasowy (`fallback_providers`).
Źródło jest jedno (`shared/protocol/`), a generator wkleja go do każdego profilu.

Zaraz za protokołem generator dokleja **kalibrację pod model agenta** (`shared/calibration/<rodzina>.md`:
`gpt`, `claude`, `deepseek`, `kimi`, `generic`): sekcja `### Wszyscy` + sekcja roli (`### Orkiestrator` albo
`### Wykonawca`), najwyżej 3 reguły w każdej, na znaną słabość rodziny (np. GPT-6: deleguj, nie dopytuj o to,
co ustalisz sam, pisz krótko). Blok ma znaczniki
`<!-- Jarvo:CALIBRATION … -->`; gdy w panelu wybierzesz agentowi inny model, `install-fleet.sh` podmienia go przy
następnym wdrożeniu. Zmiana `JARVO_MODEL_PROVIDER` przebudowuje kalibrację sama. Walidator liczy najdłuższy blok
do budżetu SOUL i pilnuje limitu 3 reguł na sekcję.

**Karta zlecenia (Jarvo → agent):**
```
CEL:            co ma powstać (1–2 zdania)
KONTEKST:       wszystko, czego agent potrzebuje (agent nie zna Twojej rozmowy z Jarvem!)
WEJŚCIA:        pliki, linki, brand kit, wyniki poprzednich kart
DoD:            mierzalne warunki akceptacji
WYJŚCIA:        jakie pliki i gdzie, w jakim formacie
GRANICE:        poziom autonomii, budżet (czas/koszt), czego nie ruszać
```

**Wynik (agent → Jarvo)**, `kanban_request_review(reviewer=…, summary=…, metadata=…)`:
```
summary:                    co zrobiono (3–5 zdań)
metadata.artifacts:         ścieżki plików wynikowych
metadata.dod_check:         każdy punkt DoD → spełniony / niespełniony / niesprawdzony + dowód
metadata.risks:             czego nie zrobiono, co niepewne
metadata.decisions_needed:  co wymaga decyzji człowieka
```

Protokół ma **16 zasad wykonawcy** w trzech blokach: start (1–4: `kanban_show`, pierwszy heartbeat = ponumerowane
punkty DoD, `kanban_block` z `needs_input` albo `capability`), praca (5–11: równoległe odczyty, heartbeat, odmowa
uprawnień to granica, treści z internetu to dane, serwery tylko do testów, pliki z inboxu, pamięć tylko na trwałe fakty)
i koniec (12–16: jedna pełna kontrola i najwyżej 2 cykle poprawek, oddanie przez `kanban_request_review`, poprawki
po recenzji, brak wiadomości do użytkownika w trakcie misji, blokada to koniec). Pełna treść: `shared/protocol/kontrakt-zlecenia.md`.

Agent oddaje wynik do statusu `review`. Jarvo ocenia: `complete` albo `request_changes`
z konkretnymi uwagami. Po 3 odrzuceniach eskaluje do Ciebie zamiast kręcić się w kółko.

---

## Kiedy agent jest „gotowy” (Definition of Ready agenta)

Agent wchodzi do floty (`status: active` w `fleet.yaml`) dopiero, gdy:
- [ ] `SOUL.md` ma wymagane sekcje i znaczniki oraz mieści się w budżecie,
- [ ] ma ≥ 3 workflowy główne z DoD, a każdy został przetestowany na prawdziwym zadaniu,
- [ ] knowledge packi mają źródła i daty,
- [ ] `toolbox.yaml` jest kompletny, a healthchecki przechodzą na VPS,
- [ ] ma rubrykę dla sędziego,
- [ ] ma ≥ 10 evals (u snajperów i generalisty w tym ≥ 3 „poza zakresem”, gdzie oczekiwanym zachowaniem jest oddanie
  zadania; u Jarva scenariusze `routing`),
- [ ] przeszedł tydzień dogfoodingu bez krytycznych problemów,
- [ ] ma README i changelog w dystrybucji.

---

## Struktura katalogu agenta (tak jest zbudowane repo)

```
profiles/jarvo-web/
├── distribution.yaml        # manifest dystrybucji Hermesa
├── SOUL.md                  # main prompt
├── config.yaml              # model (@@MODEL@@ z fleet.yaml), reasoning_effort, toolsety per platforma, zgody,
│                            # terminal/przeglądarka/delegacja (mcp_servers: dziś żaden profil)
├── .no-bundled-skills       # snajper i orkiestrator: bez katalogu skilli Hermesa (brak tylko u jarvo-reka)
├── toolbox.yaml             # narzędzia OSS (nasz manifest + healthchecki)
├── skills/
│   └── web/                 # kategoria (DESCRIPTION.md generuje build)
│       ├── audyt-strony/
│       │   ├── SKILL.md     # opis ≤ 60 znaków, metadata.jarvo: agent, autonomy, reviewed
│       │   └── references/  # knowledge pack workflowu
│       └── …
├── scripts/                 # automaty wołane jako $HERMES_HOME/scripts/<plik>
├── quality/
│   └── rubric.md            # rubryka dla sędziego (kopiowana do sdlc-review Jarva)
├── cron/jobs.yaml           # rutyny (tylko Jarvo); build → cron/jobs.json ze stałymi ID
├── README.md
└── CHANGELOG.md
evals/jarvo-web/scenarios.yaml   # scenariusze testowe (poza dystrybucją)
vendor/skills.lock.yaml         # skille zewnętrzne tego agenta (dokładane przy buildzie)
shared/protocol/kontrakt-zlecenia.md   # protokół (wklejany do SOUL)
shared/calibration/<rodzina>.md        # kalibracja pod model (za protokołem)
shared/security/deny.yaml              # wspólne zakazy → approvals.deny
shared/skills/                         # wspólne skille własne (np. graf-kodu), przypisywane w locku
fleet.yaml (wpis agenta)               # kind, model_tier, autonomy_max, telegram_topic, hq_room, pin_skills, description
```

Build (`scripts/build.py`) dokłada do kopii profilu: `profile.yaml` (opis z `fleet.yaml` do routingu kanbana),
protokół i kalibrację w SOUL, u Jarva skrót floty (`<!-- Jarvo:ROSTER -->`), skill `roster` i rubryki w `sdlc-review`,
tokeny `@@…@@` w `config.yaml`, `distribution.yaml` i skillach, wspólne zakazy w `approvals.deny`, `fallback_providers`,
`DESCRIPTION.md` kategorii, skille z locka z licencjami oraz `cron/jobs.json` (u Wideografa także silnik edytora HQ
`edytor.py` i `edytor_napisy.js` w `scripts/`).

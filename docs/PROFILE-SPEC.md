# Anatomia agenta TARS (kontrakt profilu v1)

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
 │ 2. Workflowy (skills/*/SKILL.md)              ładowane na żądanie │
 │ 3. Wiedza (skills/*/references/, knowledge/)  ładowana na żądanie │
 │ 4. Skrypty (skills/*/scripts/)                wykonywane, nie czytane │
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

Budżet: **~1500–3000 tokenów**. Wszystko dłuższe należy do skilli.

Obowiązkowe sekcje (szablon: `shared/templates/SOUL.template.md`):

| Sekcja | Zawartość |
|---|---|
| Misja | Jedno zdanie: po co istnieję |
| Osobowość | Ton, styl, parametry TARS (np. szczerość 90%, humor 60%) |
| Zakres | Co robię (lista kompetencji) |
| Poza zakresem | Czego nie robię i komu to oddaję (zawsze przez TARS-a) |
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
(`skills/<nazwa>/SKILL.md`, format agentskills.io, zgodny z Hermesem).

Każdy workflow ma (szablon: `shared/templates/SKILL.template.md`):
- **Kiedy użyć i kiedy nie** (to trafia do `description`, więc od tego zależy, czy model w ogóle go wybierze),
- **Wejścia:** czego potrzebuje, a jeśli czegoś brakuje, o co zapytać,
- **Kroki** z punktami kontrolnymi („zanim przejdziesz dalej, sprawdź…”),
- **Wyjścia:** pliki i raport w ustalonym formacie,
- **Definition of Done** workflowu,
- **Typowe błędy** i jak ich unikać,
- odwołania do `references/` (wiedza) i `scripts/` (automaty).

Zasada: **wszystko, co deterministyczne, idzie do skryptu.** Konwersję obrazów, generowanie
faviconów czy audyt Lighthouse robi skrypt, a model decyduje, interpretuje i składa wyniki.
Skrypty są tańsze, szybsze i powtarzalne.

Rodzaje skilli agenta:
- **workflowy główne:** 3–8 najważniejszych procedur dziedziny,
- **playbooki:** krótsze przepisy na konkretne sytuacje,
- **skille Hermesa [H]:** gotowe skille z katalogu Hermesa, instalowane w profilu (listy w [TOOLBOX.md](TOOLBOX.md)).

---

## 3. Wiedza: knowledge packi

Wiedza dziedzinowa w plikach Markdown w `skills/<workflow>/references/` (przy workflow,
który z niej korzysta) albo w `knowledge/` profilu (wiedza przekrojowa).

Zasady:
- **źródło i data** przy każdym pakiecie (`source:`, `reviewed:`), bo wiedza webowa i marketingowa się starzeje,
- **checklisty zamiast esejów:** model lepiej wykonuje listy kontrolne niż ogólne porady,
- **przykłady wzorcowe** (golden examples): dobry raport, dobra karta, dobra strona,
- **przegląd świeżości** co kwartał (rutyna cron przypomina TARS-owi).

---

## 4. Skrypty

`skills/<workflow>/scripts/`: Python lub Node, uruchamiane przez terminal agenta.
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
3. **usługa sidecar** (kontener na VPS), z którą agent rozmawia przez HTTP (SearXNG, Crawl4AI…),
4. **wtyczka Hermesa** z katalogu (np. `crawl4ai`, `openalex`, `langfuse`),
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
| Wiedza o Tobie | MVP: `knowledge/user/USER.md` (onboarding) + pamięć użytkownika TARS-a; później wspólny provider (np. Honcho) | TARS (onboarding), agenci czytają |
| Brand kity | `knowledge/brands/<marka>/` | `tars-web` / `tars-studio` |
| Historia zleceń | kanban (`kanban.db`) | TARS i agenci |

---

## 8. Rutyny

`cron/jobs.json`: zadania cykliczne agenta (np. Sherlock: tygodniowy monitoring konkurencji;
Web: miesięczny audyt Twoich stron). Z dystrybucji instalują się **wstrzymane**, a włączasz je świadomie.

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
- **toolsety:** każdy profil ma włączone tylko potrzebne toolsety (np. TARS nie ma terminala),
- **sandbox:** komendy snajperów wykonują się w kontenerze (`terminal.backend: docker`), do potwierdzenia w fazie 0,
- **zatwierdzanie komend:** Hermes pyta o ryzykowne komendy, więc nie wyłączamy tego,
- **workspace:** każdy agent ma własny katalog roboczy (`terminal.cwd`), a wyniki oddaje przez kanban (załączniki).

---

## 10. Jakość

- **Definition of Done agenta:** lista warunków, które musi spełnić każdy wynik (w SOUL i w rubryce sędziego),
- **rubryka sędziego:** jak TARS ocenia wynik tego agenta (skill `judge-rubryki` u TARS-a, generowany z `quality/rubric.md` agenta),
- **evals:** `evals/<agent>/*.yaml` (szablon: `shared/templates/eval.template.yaml`), czyli scenariusze
  „zlecenie → oczekiwane zachowanie → kryteria”, uruchamiane przy każdej zmianie SOUL lub skilli,
- **ślady i koszty:** Langfuse (wtyczka Hermesa) zbiera przebiegi, koszty i oceny sędziego,
- **pętla błędów:** każda poprawka odesłana przez sędziego jest kandydatem na nowy eval albo poprawkę skilla.

---

## Kontrakt zlecenia (wspólny protokół TARS ↔ agenci)

To jedyny element wspólny dla wszystkich agentów. To protokół, a nie wiedza dziedzinowa.
Źródło jest jedno (`shared/protocol/`), a generator wkleja go do każdego profilu.

**Karta zlecenia (TARS → agent):**
```
CEL:            co ma powstać (1–2 zdania)
KONTEKST:       wszystko, czego agent potrzebuje (agent nie zna Twojej rozmowy z TARS-em!)
WEJŚCIA:        pliki, linki, brand kit, wyniki poprzednich kart
DoD:            mierzalne warunki akceptacji
WYJŚCIA:        jakie pliki i gdzie, w jakim formacie
GRANICE:        poziom autonomii, budżet (czas/koszt), czego nie ruszać
```

**Wynik (agent → TARS):**
```
PODSUMOWANIE:   co zrobiono (3–5 zdań)
ARTEFAKTY:      lista plików/linków
SAMOKONTROLA:   każdy punkt DoD → spełniony / niespełniony + dowód
RYZYKA I LUKI:  czego nie zrobiono, co niepewne
DECYZJE:        co wymaga decyzji człowieka
```

Agent oddaje wynik do statusu `review`. TARS ocenia: `complete` albo `request_changes`
z konkretnymi uwagami. Po 3 odrzuceniach eskaluje do Ciebie zamiast kręcić się w kółko.

---

## Kiedy agent jest „gotowy” (Definition of Ready agenta)

Agent wchodzi do floty (`status: active` w `fleet.yaml`) dopiero, gdy:
- [ ] `SOUL.md` ma wszystkie sekcje i mieści się w budżecie,
- [ ] ma ≥ 3 workflowy główne z DoD, a każdy został przetestowany na prawdziwym zadaniu,
- [ ] knowledge packi mają źródła i daty,
- [ ] `toolbox.yaml` jest kompletny, a healthchecki przechodzą na VPS,
- [ ] ma rubrykę dla sędziego,
- [ ] ma ≥ 10 evals (w tym ≥ 3 „poza zakresem”, gdzie oczekiwanym zachowaniem jest oddanie zadania),
- [ ] przeszedł tydzień dogfoodingu bez krytycznych problemów,
- [ ] ma README i changelog w dystrybucji.

---

## Struktura katalogu agenta (tak jest zbudowane repo)

```
profiles/tars-web/
├── distribution.yaml        # manifest dystrybucji Hermesa
├── SOUL.md                  # main prompt
├── config.yaml              # model (@@MODEL@@ z fleet.yaml), toolsety per platforma, zgody, mcp_servers
├── .no-bundled-skills       # snajper: bez katalogu skilli Hermesa (izolacja)
├── toolbox.yaml             # narzędzia OSS (nasz manifest + healthchecki)
├── skills/
│   └── web/                 # kategoria (DESCRIPTION.md generuje build)
│       ├── audyt-strony/
│       │   ├── SKILL.md     # opis ≤ 60 znaków, metadata.tars: agent, autonomy, reviewed
│       │   └── references/  # knowledge pack workflowu
│       └── …
├── scripts/                 # automaty wołane jako $HERMES_HOME/scripts/<plik>
├── quality/
│   └── rubric.md            # rubryka dla sędziego (kopiowana do sdlc-review TARS-a)
├── cron/jobs.yaml           # rutyny (tylko TARS); build → cron/jobs.json ze stałymi ID
├── README.md
└── CHANGELOG.md
evals/tars-web/scenarios.yaml   # scenariusze testowe (poza dystrybucją)
vendor/skills.lock.yaml         # skille zewnętrzne tego agenta (dokładane przy buildzie)
```

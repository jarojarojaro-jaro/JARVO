# Jarvo — plan budowy (od 0 do ∞)

> Prywatny, „wszechwiedzący” asystent AI zbudowany na **Hermes Agent** (Nous Research).
> Jeden agent na zewnątrz, w środku **flota wyspecjalizowanych profili**. Z każdym można
> rozmawiać osobno, a Jarvo je koordynuje. Wszystko jest skonfigurowane z góry, więc nie
> zaczynasz od pustej kartki.

Stan: **v0.3 (2026-09-26): flota v1 zakodowana i przetestowana lokalnie, gotowa do postawienia na VPS**
([RUNBOOK.md](RUNBOOK.md)). Oparty na lekturze kodu i dokumentacji `NousResearch/hermes-agent`
(main, wrzesień 2026) i testach na prawdziwym Hermesie. Postęp: sekcja 6.

**Dokumenty projektu:**
| Dokument | O czym |
|---|---|
| [PLAN.md](PLAN.md) | wizja, architektura, roadmapa, decyzje (ten plik) |
| [FLEET.md](FLEET.md) | specyfikacja agentów floty v1 |
| [PROFILE-SPEC.md](PROFILE-SPEC.md) | anatomia agenta: 10 warstw, kontrakt zlecenia, Definition of Ready |
| [TOOLBOX.md](TOOLBOX.md) | zweryfikowane narzędzia open-source per agent + polityka licencji |
| [BOSS.md](BOSS.md) | mechanika Main Judge'a: misje, kolejka decyzji, patrol, sędziowanie, eskalacje |
| [HQ.md](HQ.md) | Jarvo HQ: GUI floty (pokoje agentów, praca na żywo, czat) |
| [ADS.md](ADS.md) | projekt agenta reklam płatnych `jarvo-ads` i Skarbca (strażnik budżetu) |
| [LEADY.md](LEADY.md) | projekt Łowcy leadów: sygnały zakupowe z oficjalnych źródeł → lista firm z „dlaczego teraz” |
| [VPS.md](VPS.md) | infrastruktura: topologia, bezpieczeństwo, backupy, monitoring, wdrożenia |
| [RUNBOOK.md](RUNBOOK.md) | wdrożenie i codzienna obsługa krok po kroku |
| [SOURCES.md](SOURCES.md) | źródła, atrybucje i licencje |
| [JARVO-CALOSC.md](JARVO-CALOSC.md) | całość od A do Z w jednym pliku (kontekst na start sesji) |

---

## 1. Czy to się da zrobić?

**Tak, i to bez forkowania Hermesa.** Hermes ma już wszystkie potrzebne prymitywy.
Naszą pracą jest ich *wypełnienie i spięcie*, a nie przepisywanie rdzenia:

| Potrzebujemy | Co Hermes już ma |
|---|---|
| Wielu specjalistów w jednym systemie | **Profile**: każdy ma własny `SOUL.md`, skille, pamięć, model, crony, MCP i klucze |
| Gotowca zamiast pustej kartki | **Profile distributions**: cały agent jako repo git, instalowany przez `hermes profile install`, aktualizowany przez `hermes profile update` |
| Rozmowy z każdym osobno | Aliasy CLI (`jarvo-fin chat`), **Bot Mode** w aplikacji desktopowej (lista botów, czaty grupowe, boty piszące do siebie), Telegram/Discord/Slack |
| Jednego bota na Telegramie, który rozdziela rozmowy | **Gateway z multipleksacją** + `gateway.profile_routes` (routing po czacie lub wątku do profilu) |
| Swarmu, czyli współpracy specjalistów | **Kanban**: trwała tablica zadań współdzielona przez profile, z orkiestratorem routującym po opisie profilu; do szybkich podzadań `delegate_task` |
| Wspólnej wiedzy o użytkowniku | MVP: plik `knowledge/user/USER.md` z wywiadu onboardingowego + pamięć użytkownika Jarva (kontekst trafia do kart). Później **Honcho**: wspólny „user peer”, osobny „AI peer” na profil |
| Izolacji specjalistów („snajperów”) | `hermes profile create --no-skills`: profil bez domyślnego katalogu skilli, dostaje tylko to, co mu damy |
| Oceny wyników przez szefa | Statusy kanbana `review` / `kanban_request_changes` / `kanban_complete`: praca wraca do orkiestratora do akceptacji |
| Automatyzacji | Wbudowany **cron** z dostarczaniem na dowolną platformę |

Filozofia Hermesa pasuje do nas idealnie: *„rdzeń jest wąski, możliwości żyją na
krawędziach”* (skille, pluginy, MCP, profile). Dzięki temu aktualizacje Hermesa nie
rozwalą nam Jarva.

**Uczciwe zastrzeżenie:** „wszechwiedzący” w praktyce znaczy: dobra wiedza domenowa
w skillach, dostęp do sieci i Twoich danych przez narzędzia oraz pamięć, która rośnie
z czasem. Model sam z siebie nie wie wszystkiego. Z każdym tygodniem używania Jarvo
wie jednak coraz więcej o Tobie.

---

## 2. Model: jeden Main Judge, flota snajperów (w stylu firstmate)

Inspiracja: [firstmate](https://github.com/kunchenguid/firstmate), w którym *rozmawiasz z jednym
agentem, a on prowadzi załogę*: rozdziela zadania, nadzoruje je do końca i eskaluje
do Ciebie tylko prawdziwe decyzje. Stan żyje na dysku, więc wszystko przeżywa restart.

Zasady:
1. **Specjalista = snajper.** Jedna dziedzina, własne skille, własna wiedza, własna pamięć.
   Bez katalogu skilli Hermesa: dystrybucja snajpera ma znacznik `.no-bundled-skills` (wyjątek: generalista
   `jarvo-reka`), a toolsety ograniczone do tego, czego dziedzina potrzebuje. Czego nie umie, tego nie robi. Oddaje zadanie szefowi.
2. **Jarvo = Main Judge (orkiestrator).** Sam nie wykonuje pracy dziedzinowej. Robi cztery rzeczy:
   - **intake:** rozumie, czego chcesz, dopytuje tylko o prawdziwe decyzje,
   - **dispatch:** rozbija cel na karty kanbana i przypisuje je właściwym snajperom,
   - **judge:** każdy wynik wraca w statusie `review`, a Jarvo go ocenia według kryteriów
     z karty: akceptuje (`complete`) albo odsyła do poprawki (`request_changes`),
   - **raport:** oddaje Ci jeden, sprawdzony wynik.
3. **Bezpośredni kontakt zostaje.** Z każdym snajperem możesz pogadać osobno, ale praca
   wieloetapowa zawsze idzie przez szefa.
4. **Jedyna rzecz wspólna:** wiedza o *Tobie* (kim jesteś, preferencje). Każdy snajper
   dostaje ją do kontekstu, ale nie wie nic o dziedzinach innych snajperów.
5. **Nadzór bez palenia tokenów:** dispatcher kanbana i heartbeaty pilnują floty, a Jarvo
   budzi się tylko, gdy coś wymaga oceny albo Twojej decyzji.

## 3. Architektura docelowa

```
                         ┌──────────────────────────────┐
   Ty ── CLI / Desktop ──►│  Jarvo (profil „jarvo”)        │  ← dyspozytor + osobowość
       ── Telegram ──────►│  frontier model, toolset     │     odpowiada sam albo
                          │  kanban (orkiestrator)       │     zleca specjalistom
                          └──────────────┬───────────────┘
                                         │ kanban_create / delegate_task
        ┌─────────────┬─────────────┬────┴────────┬─────────────┬─────────────┐
        ▼             ▼             ▼             ▼             ▼             ▼
 jarvo-sherlock   jarvo-web   jarvo-studio   jarvo-wideo    jarvo-ads    jarvo-reka
   (research)     (strony)      (kreacja)      (wideo)      (reklamy)   (prawa ręka)
  SOUL + skille SOUL + skille SOUL + skille SOUL + skille SOUL + skille SOUL + skille
  własna pamięć własna pamięć własna pamięć własna pamięć własna pamięć własna pamięć
        ▲             ▲             ▲             ▲             ▲             ▲
        └─────────────┴───────── rozmowa bezpośrednia ──────────┴─────────────┘
               (alias CLI, Bot Chat w desktopie, własny temat na Telegramie)

  Wspólne warstwy (dla wszystkich profili):
   • pamięć o Tobie    → MVP: USER.md + pamięć Jarva; później Honcho (wspólny user peer)
   • skille wspólne    → tylko wybrane, z repo (`shared/skills/`, np. `graf-kodu` u Weba i Ręki);
                         poza tym każdy snajper ma wyłącznie swoje
   • tablica zadań     → /opt/data/kanban.db (HERMES_HOME hosta, współdzielona przez profile)
```

### Trzy tryby pracy

1. **Rozmowa bezpośrednia:** piszesz do konkretnego specjalisty (`jarvo-fin chat`,
   jego Bot Chat, jego temat na Telegramie). Specjalista ma swoją pamięć i swoje skille.
2. **Przez Jarva:** piszesz do Jarva, a on decyduje:
   - odpowiada sam (proste rzeczy, small talk, szybkie fakty),
   - `delegate_task`: krótkie, jednorazowe podzadanie (anonimowy subagent, wynik wraca do rozmowy),
   - `kanban_create` z `assignee: jarvo-xyz`: prawdziwe zlecenie *nazwanemu specjaliście*,
     z jego pamięcią i skillami. Jest trwałe, przeżywa restart i można je śledzić.
3. **Rój:** Jarvo rozbija większy cel na karty kanbana dla kilku specjalistów
   z zależnościami (np. research → analiza → tekst), a na końcu składa wynik.

> Ważne: `delegate_task` **nie** uruchamia profilu specjalisty, tylko świeżego
> subagenta. Jeśli liczy się wiedza i pamięć specjalisty, trzeba użyć kanbana.
> To rozróżnienie musi znać SOUL Jarva.

---

## 4. Anatomia specjalisty („kontrakt profilu”)

> Pełna wersja: [PROFILE-SPEC.md](PROFILE-SPEC.md) (10 warstw agenta, szablony, poziomy autonomii,
> kontrakt zlecenia). Poniżej skrót.

Każdy specjalista to katalog w `profiles/<nazwa>/`, będący **Hermes profile distribution**:

```
profiles/jarvo-fin/
├── distribution.yaml   # nazwa, wersja, opis, wymagane zmienne env
├── SOUL.md             # tożsamość, zakres, czego NIE robi, kiedy oddaje zadanie, ton
├── config.yaml         # model, toolsety, terminal.cwd, zgody, mcp_servers (integracje MCP)
├── skills/             # procedury domenowe (SKILL.md + scripts/ + references/)
│   ├── budzet-miesieczny/SKILL.md
│   └── analiza-wyciagu/SKILL.md
├── cron/jobs.yaml      # rutyny (build → jobs.json; instalowane jako wstrzymane)
└── README.md
```

Plus nasze dodatki (nie są częścią dystrybucji, służą do jakości):

```
evals/jarvo-fin/*.yaml   # scenariusze testowe: pytanie → oczekiwane zachowanie
```

**Szablon SOUL.md dla specjalisty** (sekcje obowiązkowe):
1. *Kim jestem*: rola w jednym zdaniu, osobowość w stylu Jarvo (humor/szczerość w %).
2. *Mój zakres*: co robię. *Poza zakresem*: czego nie robię i komu to oddaję.
3. *Jak pracuję*: domyślne procedury i które skille wołam w jakiej sytuacji.
4. *Zasady bezpieczeństwa*: np. finanse bez wykonywania przelewów, zdrowie z zastrzeżeniem,
   że to nie porada medyczna.
5. *Protokół przekazania*: gdy zadanie wykracza poza dziedzinę, oddaje je Jarvowi (`kanban_block` z powodem), nigdy nie improwizuje.
6. *Język*: domyślnie polski.

**Rejestr floty:** `fleet.yaml` to jedno źródło prawdy o tym, kto istnieje: nazwa, opis
(do routingu kanbana), tier modelu, kanał/temat na Telegramie, status. Skrypty generują
z niego trasy `profile_routes`, opisy profili i **skill „roster” dla Jarva** (żeby
dyspozytor zawsze wiedział, jacy specjaliści istnieją). Dzięki temu dodanie specjalisty
to jeden wpis i jeden katalog, bez ręcznej edycji w pięciu miejscach.

---

## 5. Struktura tego repo

Aktualna mapa jest w [README](../README.md#mapa-repo). Najważniejsze przepływy:

```
fleet.yaml + profiles/<agent>/ + shared/protocol/ + vendor/skills.lock.yaml
   └─ scripts/build.py ──► build/profiles/<agent>/   (dystrybucje Hermesa: SOUL z protokołem, tokeny,
                          build/host/config.yaml       roster, rubryki, skille zewnętrzne, cron z ID)
scripts/deploy.sh (VPS) ──► git pull → obraz/usługi → validate → build → install-fleet.sh (hermes profile
                            install/update, sekrety, prune skilli, kanban, restart gatewaya) → healthcheck
```

---

## 6. Roadmapa

Legenda: ✅ zrobione i sprawdzone lokalnie (testy, prawdziwy Hermes) · 🟡 zakodowane, czeka na test na VPS
z prawdziwymi modelami i Telegramem · ⬜ do zrobienia.

### Faza 0: Fundament i spike techniczny
- 🟡 Postawić VPS według [RUNBOOK.md](RUNBOOK.md) (skrypty gotowe: `bootstrap-vps.sh`, `deploy.sh`).
- ✅ Obraz pochodny Hermesa (`infra/Dockerfile`) z narzędziami MVP, zbudowany na opublikowanym obrazie Hermesa 0.21.5.
- ✅ Test end-to-end w Dockerze: prawdziwy `deploy.sh` (walidacja, build, instalacja i aktualizacja 5 profili (wtedy; dziś flota ma 7),
  healthchecki), audyt strony z Lighthouse/axe, rendery grafik, PDF (pandoc + Chromium), SearXNG, patrol na prawdziwej
  tablicy i cron z bramką skryptu (`wakeAgent=false` → zero tokenów). Bez modeli LLM i bez Telegrama.
- ✅ Model sandboxu: agenci wykonują komendy w kontenerze Hermesa, bez gniazda Dockera.
- ✅ `hermes profile install` z lokalnego katalogu i `hermes profile update --force-config`.
- ✅ Izolacja snajpera: `.no-bundled-skills`, profil widzi wyłącznie swoje skille.
- 🟡 Pętla judge: snajper → `review` → Jarvo `request_changes` → poprawka → `complete` (tor review skonfigurowany).
- 🟡 Kanban między profilami: karta od Jarva, wykonanie przez snajpera, wynik wraca.
- 🟡 Telegram: jeden bot, supergrupa z tematami, `profile_routes` z `thread_id` (config generowany i testowany).
- ✅ Decyzje spisane w sekcji 7 (zamiast osobnych ADR-ów).

### Faza 1: MVP: Jarvo + Sherlock
- ✅ Szkielet repo, `fleet.yaml`, szablony, generator (`scripts/build.py`).
- ✅ Profil `jarvo`: SOUL, roster generowany z floty, protokół zlecania, 11 skilli dowodzenia ([BOSS.md](BOSS.md)).
- ✅ `jarvo-sherlock`: metoda śledcza, weryfikacja faktów, raporty, skrypty wyszukiwania i dziennika źródeł.
- ✅ Jedna komenda stawia całą flotę (`scripts/deploy.sh --first-run` → `install-fleet.sh`).
- ✅ Walidator + testy (`make validate`, `make test`, CI) + 101 scenariuszy evals.

### Faza 2: Kanały
- ✅ CLI: aliasy profili (`hermes profile install --alias`).
- 🟡 Telegram: „Jarvo HQ”, temat na specjalistę, General dla Jarva.
- ✅ Jarvo HQ: GUI floty w dashboardzie Hermesa (pokoje agentów, praca na żywo, decyzje, misje, czat), test na prawdziwym Hermesie ([HQ.md](HQ.md)).
- ⬜ Desktop: Bot Mode (lista botów, awatary, czat grupowy floty).
- 🟡 Głos: notatki głosowe z Telegrama → Parakeet (`jarvo-stt`, `stt.provider: local_command`), lektor Edge TTS u Wideografa.

### Faza 3: Pamięć i onboarding
- ✅ Skill `onboarding-interview`: wywiad startowy → `knowledge/user/USER.md`.
- ✅ MVP pamięci o Tobie: USER.md + pamięć użytkownika Jarva, kontekst przekazywany w kartach.
- ⬜ Wspólny provider pamięci (Honcho self-host) po sprawdzeniu MVP w praktyce.
- ⬜ Zasady prywatności: co gdzie leży, co nigdy nie opuszcza serwera.

### Faza 4: Reszta floty v1, potem kolejni specjaliści
- ✅ `jarvo-web`, `jarvo-studio`, `jarvo-reka` według kontraktu: SOUL, workflowy, skrypty, rubryki, evals.
- ✅ `jarvo-wideo` (Wideograf): 15 skilli, pętla krytyki (7 osi), maskotka, clipmaker (rolki z długich nagrań), demo strony (nagranie z kursorem i napisami kroków), 22 scenariusze evals.
- 🟡 `jarvo-ads` (reklamy Meta i Google): SOUL, 10 skilli, skrypty, rubryka, 12 scenariuszy evals; bez kluczy ([ADS.md](ADS.md)).
- 🟡 Clipmaker Wideografa: długie nagranie → edytowalne rolki (kadr z focusem, napisy karaoke, `klipy.py`); kroki 1–4 gotowe, krok 5: test na prawdziwym nagraniu ([KLIPY.md](KLIPY.md)).
- ⬜ Skarbiec: sejf tokenów reklamowych, koperty zatwierdzane kodem, STOP ([ADS.md](ADS.md)).
- 🟡 Łowca leadów `jarvo-lowca`: sygnały z KRS, przetargów, stron firm → lista firm z „dlaczego teraz” i opublikowanym kontaktem ([LEADY.md](LEADY.md)).
- ⬜ Integracje MCP per agent (kalendarz, mail, notatki, dysk): zależą od aplikacji, których używasz.
- ⬜ Dogfooding: tydzień pracy każdego agenta na prawdziwych zadaniach, poprawki promptów i skilli.
- ⬜ Test floty: „wypuść landing nowego produktu” (sherlock → web + studio → reka, Jarvo ocenia).
- ⬜ Kolejni specjaliści (`make new-agent`), np. finanse, zdrowie, dom.

### Faza 5: Automatyzacje i rój
- ✅ Rutyny: patrol co 30 min (bez modelu, gdy spokój), poranny brief, przegląd tygodnia, świeżość wiedzy.
- ✅ Wzorce roju w `dispatch-playbook` (research → wykonanie → złożenie, zależności kart).

### Faza 6: Jakość, koszty, bezpieczeństwo
- ✅ Evals na stagingu (`scripts/evals-staging.sh`), sędzia LLM + sprawdzenia deterministyczne.
- ✅ Koszty: poziomy modeli w `fleet.yaml` i `reasoning_effort` per agent; przy presecie `openrouter` osobny klucz z limitem na agenta.
- ✅ Bezpieczeństwo: zgody (A2 tylko z człowiekiem, praca bez nadzoru = odmowa), sekrety tylko w `.env`, Tailscale.
- ✅ Red team na promptfoo (`security/redteam/`, `scripts/redteam.sh`, 12 ataków) i wspólne zakazy floty
  (`shared/security/deny.yaml`).
- ⬜ Przegląd kosztów po 2 tygodniach, korekta poziomów modeli.

### Faza 7: Pętla samodoskonalenia
- ✅ `harvest-skills.sh`: skille utworzone lub zmienione przez agentów → przegląd → repo.
- ✅ `fleet-improvement` Jarva: wnioski z przeglądu tygodnia jako propozycje zmian.
- ⬜ Wersjonowanie floty (tagi), changelog wydań.

### Faza ∞
Wake word, Home Assistant, aplikacja mobilna, kolejne specjalizacje…

**Pomysły do zbadania (zapisane, żeby nie uciekły):**
- **Onboarding po instalacji (plan użytkownika, do zrobienia):** przewodnik krok po kroku dla nietechnicznej osoby:
  co robi każdy agent, jak z nim rozmawiać, przykładowe pierwsze prośby, podstawowe pytania o firmę i markę na start.
  W nim świadome pobranie cięższych rzeczy (np. model mowy Parakeet ~0,65 GB) z paskiem postępu, zamiast
  niespodzianki przy pierwszym użyciu.
- **Cua** ([trycua/cua](https://github.com/trycua/cua), MIT): „ręce” agenta do programów okienkowych. Cua Driver
  (MCP `cua-driver mcp`, Linux/Windows/macOS) klika przez drzewo dostępności; rozszerzenie **Cua Perception**
  (opcjonalne) czyta piksele, gdy drzewa nie ma (kanwy, gry, zdalne pulpity): zrzut → oznaczone regiony
  (OmniParser + PP-OCR, na CPU, bez sieci), klik wskazuje ID regionu związane z konkretnym zrzutem
  (`capture_id`, wygasa po 60 s, bez klikania w gołe współrzędne), więc poradzą sobie modele bez „celowania”.
  Uwaga: OmniParser w Perception jest na **AGPL-3.0** (tylko użytek prywatny, bez udostępniania innym).
  Kandydat: Ręka z własnym pulpitem XFCE w kontenerze uruchamianym na żądanie (zmierzyć RAM na VPS 8 GB),
  sterowanie Twoim Windowsem tylko za zgodą (A2). Chmura Cua Fleets jest płatna: pomijamy.
- **„Drugi mózg” (analiza 8 repo, 2026-09-28):** Jarvo działa na Hermesie, który już ma pamięć, `session_search`,
  kanban z zależnościami i dostawców pamięci (w tym mem0), więc bierzemy tylko to, czego brak.
  - **Wdrożone:** `DeusData/codebase-memory-mcp` 0.11.0 (MIT) jako skill `kod/graf-kodu` u Weba i Ręki, w trybie
    poleceń (nie MCP: opisy 17 narzędzi nie jadą w każdym zapytaniu), pobierany przy pierwszym użyciu z SHA-256
    (program 300 MB, więc nie w obrazie), bez obserwatora i UI. Test na repo Jarvo: indeks ~7 s, pytanie ~5 s;
    trafność dobra przy zwykłych importach, błędy przy tych samych nazwach w różnych modułach i importach
    dynamicznych, stąd zasada „graf = wskazówka, potwierdź w pliku”.
  - **Faza bazy wiedzy (Obsidian, osobno):** `AgriciDaniel/claude-obsidian` (MIT, skille Agent Skills → działają
    w Hermesie; skarbiec = zwykłe pliki Markdown ze źródłami) jako rdzeń; do porównania `Graphify-Labs/graphify`
    (Apache-2.0: graf kodu lokalnie, dokumenty/PDF/wideo przez model = tokeny).
  - **Pomijamy:** `tobi/qmd` (MIT; tryb semantyczny pobiera 3 modele GGUF ~2 GB: za ciężko na VPS 8 GB),
    `garrytan/gbrain` (MIT; Bun, własny serwer, demon wzbogacania i płatne embeddingi: za ciężko),
    `thedotmack/claude-mem` (Apache-2.0; wtyczka Claude Code z workerem w tle, dubluje pamięć
    i `session_search` Hermesa), `mem0ai/mem0` (Apache-2.0; Hermes ma go jako dostawcę, ale to chmura z kluczem,
    a wtyczka przeglądarki nas nie dotyczy), `gastownhall/beads` (MIT; tracker na Dolt, dubluje kanban Hermesa).
- **Edytor filmów** (inspiracja: diffusionstudio/editor, MPL-2.0, nie forkujemy). **Wdrożone** ([HQ.md §2a](HQ.md#2a-edytor-filmów)):
  Wideograf renderuje `*.edycja.json` tym samym silnikiem co HQ (`projekt.py render`), napisy z mowy (Parakeet),
  znaczniki ciszy i „yyy” do wycięcia. **Dalsze kroki:** przejścia i animacje napisów przez ffmpeg.

---

## 7. Decyzje do podjęcia (z rekomendacjami)

| # | Decyzja | Rekomendacja | Dlaczego |
|---|---|---|---|
| D1 | Lista specjalistów | ✅ Ustalone: flota v1 (sekcja 8) | |
| D2 | Modele | ✅ Domyślnie `openai-codex` (`gpt-6-luna` na wszystkich poziomach, głębia przez `reasoning_effort`: high dla Jarva, low dla reszty); presety `openrouter` / `commandcode` / `commandcode-anthropic` przez `JARVO_MODEL_PROVIDER`; obrazy i wideo przez OpenRouter | Orkiestracja wymaga osądu, a wykonanie jasno opisanych zadań nie |
| D3 | Gdzie działa | ✅ Ustalone: VPS (x86_64, UE), Docker, szczegóły w [VPS.md](VPS.md) | |
| D4 | Główny kanał | ✅ Telegram (DM + grupa „Jarvo HQ” z tematami) + CLI; desktop jako dodatek | Najtańszy start, działa z telefonu |
| D5 | Wspólna pamięć | ✅ MVP: wbudowana pamięć + USER.md z onboardingu; Honcho (self-host) w fazie 3, gdy MVP okaże się za mały | Mniej ruchomych części na start; Honcho nadal pasuje do modelu „wspólny użytkownik, osobni agenci” |
| D6 | Nazewnictwo profili | Prefiks `jarvo-` (`jarvo-web`, `jarvo-sherlock`…) | Profile stają się komendami w shellu, a prefiks unika kolizji |
| D7 | Język | Polski domyślnie, skille technicznie po angielsku tam, gdzie pomaga modelowi | Naturalna rozmowa i precyzyjne instrukcje |

---

## 8. Flota v1

Siedem profili. Pełna specyfikacja (zakres, skille, narzędzia, rubryki sędziego) jest w
[FLEET.md](FLEET.md), a rejestr maszynowy w [`fleet.yaml`](../fleet.yaml).

| Profil | Rola |
|---|---|
| `jarvo` | Main Judge: przyjmuje zlecenia, rozdziela, ocenia, raportuje |
| `jarvo-web` | Web Senior Dev: strony od faviconu po SEO, uczy się marki |
| `jarvo-sherlock` | Researcher-detektyw: wiele źródeł, weryfikacja faktów |
| `jarvo-studio` | Marketing i kreacja: grafiki, copy, kampanie, social media |
| `jarvo-wideo` | Wideograf: krótkie filmy, montaż, lektor, napisy, klipy, wideo AI |
| `jarvo-ads` | Specjalista Ads: Meta i Google Ads, kampanie, testy A/B/C, raporty; wydaje tylko w kopercie z kodem |
| `jarvo-reka` | Prawa ręka: generalista, który wykonuje i ogarnia wszystko |

Kolejni specjaliści dojdą później, każdy według tego samego kontraktu.

## 9. Zasady projektu

1. **Nie forkujemy Hermesa.** Budujemy na krawędziach (profile, skille, MCP, pluginy).
   Jeśli czegoś brakuje w rdzeniu, najpierw szukamy rozwiązania w skillu lub pluginie.
2. **Repo jest źródłem prawdy.** Wszystko, co definiuje flotę, jest w git. Dane użytkownika
   (pamięć, sesje, klucze) nigdy nie trafiają do repo.
3. **Jeden specjalista naraz.** Każdego „dogfoodujemy” i testujemy evalsami przed dodaniem następnego.
4. **Nie psujemy cache’u promptów.** Zmiany SOUL i skilli działają od nowej sesji (tak projektuje Hermes).
5. **Bezpieczeństwo domyślnie:** zatwierdzanie ryzykownych komend, crony z dystrybucji startują wstrzymane.

# TARS — plan budowy (od 0 do ∞)

> Prywatny, „wszechwiedzący” asystent AI zbudowany na **Hermes Agent** (Nous Research).
> Jeden agent na zewnątrz, w środku **flota wyspecjalizowanych profili**. Z każdym można
> rozmawiać osobno, a TARS je koordynuje. Wszystko jest skonfigurowane z góry, więc nie
> zaczynasz od pustej kartki.

Stan: szkic v0.1 (2026-09-26). Oparty na lekturze kodu i dokumentacji
`NousResearch/hermes-agent` (main, wrzesień 2026).

---

## 1. Czy to się da zrobić?

**Tak, i to bez forkowania Hermesa.** Hermes ma już wszystkie potrzebne prymitywy.
Naszą pracą jest ich *wypełnienie i spięcie*, a nie przepisywanie rdzenia:

| Potrzebujemy | Co Hermes już ma |
|---|---|
| Wielu specjalistów w jednym systemie | **Profile**: każdy ma własny `SOUL.md`, skille, pamięć, model, crony, MCP i klucze |
| Gotowca zamiast pustej kartki | **Profile distributions**: cały agent jako repo git, instalowany przez `hermes profile install`, aktualizowany przez `hermes profile update` |
| Rozmowy z każdym osobno | Aliasy CLI (`tars-fin chat`), **Bot Mode** w aplikacji desktopowej (lista botów, czaty grupowe, boty piszące do siebie), Telegram/Discord/Slack |
| Jednego bota na Telegramie, który rozdziela rozmowy | **Gateway z multipleksacją** + `gateway.profile_routes` (routing po czacie lub wątku do profilu) |
| Swarmu, czyli współpracy specjalistów | **Kanban**: trwała tablica zadań współdzielona przez profile, z orkiestratorem routującym po opisie profilu; do szybkich podzadań `delegate_task` |
| Wspólnej wiedzy o użytkowniku | **Honcho**: jeden „user peer” współdzielony przez wszystkie profile, osobny „AI peer” dla każdego profilu (albo inny memory provider) |
| Wspólnych skilli | `skills.external_dirs`: katalog skilli skanowany przez każdy profil |
| Automatyzacji | Wbudowany **cron** z dostarczaniem na dowolną platformę |

Filozofia Hermesa pasuje do nas idealnie: *„rdzeń jest wąski, możliwości żyją na
krawędziach”* (skille, pluginy, MCP, profile). Dzięki temu aktualizacje Hermesa nie
rozwalą nam TARS-a.

**Uczciwe zastrzeżenie:** „wszechwiedzący” w praktyce znaczy: dobra wiedza domenowa
w skillach, dostęp do sieci i Twoich danych przez narzędzia oraz pamięć, która rośnie
z czasem. Model sam z siebie nie wie wszystkiego. Z każdym tygodniem używania TARS
wie jednak coraz więcej o Tobie.

---

## 2. Architektura docelowa

```
                         ┌──────────────────────────────┐
   Ty ── CLI / Desktop ──►│  TARS (profil „tars”)        │  ← dyspozytor + osobowość
       ── Telegram ──────►│  frontier model, toolset     │     odpowiada sam albo
                          │  kanban (orkiestrator)       │     zleca specjalistom
                          └──────────────┬───────────────┘
                                         │ kanban_create / delegate_task
          ┌───────────────┬──────────────┼──────────────┬───────────────┐
          ▼               ▼              ▼              ▼               ▼
     tars-research    tars-dev      tars-fin       tars-health     tars-… (kilkanaście)
     (profil)         (profil)      (profil)       (profil)
     SOUL + skille    SOUL + skille SOUL + skille  SOUL + skille
     własna pamięć    własna pamięć …
          ▲               ▲              ▲              ▲
          └───────────────┴── rozmowa bezpośrednia ─────┘
               (alias CLI, Bot Chat w desktopie, własny temat na Telegramie)

  Wspólne warstwy (dla wszystkich profili):
   • shared/skills     → skills.external_dirs (protokół przekazywania zadań, styl TARS, PL)
   • pamięć o Tobie    → Honcho: wspólny user peer, osobny AI peer na profil
   • tablica zadań     → ~/.hermes/kanban.db (współdzielona przez profile)
```

### Trzy tryby pracy

1. **Rozmowa bezpośrednia:** piszesz do konkretnego specjalisty (`tars-fin chat`,
   jego Bot Chat, jego temat na Telegramie). Specjalista ma swoją pamięć i swoje skille.
2. **Przez TARS-a:** piszesz do TARS-a, a on decyduje:
   - odpowiada sam (proste rzeczy, small talk, szybkie fakty),
   - `delegate_task`: krótkie, jednorazowe podzadanie (anonimowy subagent, wynik wraca do rozmowy),
   - `kanban_create` z `assignee: tars-xyz`: prawdziwe zlecenie *nazwanemu specjaliście*,
     z jego pamięcią i skillami. Jest trwałe, przeżywa restart i można je śledzić.
3. **Rój:** TARS rozbija większy cel na karty kanbana dla kilku specjalistów
   z zależnościami (np. research → analiza → tekst), a na końcu składa wynik.

> Ważne: `delegate_task` **nie** uruchamia profilu specjalisty, tylko świeżego
> subagenta. Jeśli liczy się wiedza i pamięć specjalisty, trzeba użyć kanbana.
> To rozróżnienie musi znać SOUL TARS-a.

---

## 3. Anatomia specjalisty („kontrakt profilu”)

Każdy specjalista to katalog w `profiles/<nazwa>/`, będący **Hermes profile distribution**:

```
profiles/tars-fin/
├── distribution.yaml   # nazwa, wersja, opis, wymagane zmienne env
├── SOUL.md             # tożsamość, zakres, czego NIE robi, kiedy oddaje zadanie, ton
├── config.yaml         # model, dozwolone toolsety, terminal.cwd, zatwierdzanie komend
├── mcp.json            # integracje (np. arkusze, bank export, kalendarz)
├── skills/             # procedury domenowe (SKILL.md + scripts/ + references/)
│   ├── budzet-miesieczny/SKILL.md
│   └── analiza-wyciagu/SKILL.md
├── cron/jobs.json      # rutyny (instalowane jako wstrzymane, włączamy świadomie)
└── README.md
```

Plus nasze dodatki (nie są częścią dystrybucji, służą do jakości):

```
evals/tars-fin/*.yaml   # scenariusze testowe: pytanie → oczekiwane zachowanie
```

**Szablon SOUL.md dla specjalisty** (sekcje obowiązkowe):
1. *Kim jestem*: rola w jednym zdaniu, osobowość w stylu TARS (humor/szczerość w %).
2. *Mój zakres*: co robię. *Poza zakresem*: czego nie robię i komu to oddaję.
3. *Jak pracuję*: domyślne procedury i które skille wołam w jakiej sytuacji.
4. *Zasady bezpieczeństwa*: np. finanse bez wykonywania przelewów, zdrowie z zastrzeżeniem,
   że to nie porada medyczna.
5. *Protokół przekazania*: jak zgłosić, że zadanie należy do innego specjalisty (wspólny skill).
6. *Język*: domyślnie polski.

**Rejestr floty:** `fleet.yaml` to jedno źródło prawdy o tym, kto istnieje: nazwa, opis
(do routingu kanbana), tier modelu, kanał/temat na Telegramie, status. Skrypty generują
z niego trasy `profile_routes`, opisy profili i **skill „roster” dla TARS-a** (żeby
dyspozytor zawsze wiedział, jacy specjaliści istnieją). Dzięki temu dodanie specjalisty
to jeden wpis i jeden katalog, bez ręcznej edycji w pięciu miejscach.

---

## 4. Struktura tego repo (docelowo)

```
TARS/
├── README.md
├── fleet.yaml                  # rejestr specjalistów (źródło prawdy)
├── docs/
│   ├── PLAN.md                 # ten dokument
│   ├── PROFILE-SPEC.md         # kontrakt profilu + szablony
│   └── adr/                    # decyzje architektoniczne (krótkie, numerowane)
├── profiles/                   # każdy podkatalog = Hermes profile distribution
│   ├── tars/                   # dyspozytor
│   ├── tars-research/
│   └── …
├── shared/
│   ├── skills/                 # wspólne skille (external_dirs dla wszystkich profili)
│   └── templates/              # szablony SOUL.md / SKILL.md / evals dla nowych specjalistów
├── scripts/
│   ├── install.sh              # instaluje całą flotę na maszynie (idempotentnie)
│   ├── update.sh               # hermes profile update dla wszystkich
│   ├── new-specialist.sh       # scaffolding nowego specjalisty z szablonu
│   ├── gen-fleet.py            # fleet.yaml → routes, opisy, skill „roster”
│   └── harvest-skills.sh       # zbiera skille, które agenci sami stworzyli, do przeglądu
├── evals/                      # scenariusze testowe per specjalista + routing TARS-a
└── tests/                      # walidacja: frontmatter, distribution.yaml, spójność floty
```

---

## 5. Roadmapa

### Faza 0: Fundament i spike techniczny
Cel: potwierdzić na prawdziwym Hermesie, że klocki działają tak, jak mówi dokumentacja.
- [ ] Zainstalować Hermesa w środowisku testowym.
- [ ] `hermes profile install ./profiles/<x>` z lokalnego katalogu działa (bez pushowania).
- [ ] `skills.external_dirs` → wspólny skill widoczny w dwóch profilach.
- [ ] Kanban: profil A tworzy kartę dla profilu B, B ją wykonuje, A odbiera wynik.
- [ ] Telegram: jeden bot, supergrupa z tematami, `profile_routes` z `thread_id` → różne profile.
- [ ] Spisać ADR-y dla decyzji z sekcji 6.

### Faza 1: MVP: TARS + 2 specjalistów
- [ ] Szkielet repo (struktura z sekcji 4), `fleet.yaml`, szablony.
- [ ] Profil `tars`: SOUL z osobowością, skill „roster”, protokół zlecania (kanban vs delegate).
- [ ] Dwóch pierwszych specjalistów (propozycja: `tars-research` + ten najbardziej przydatny dla Ciebie).
- [ ] `scripts/install.sh`: jedna komenda stawia całą flotę.
- [ ] Walidatory w `tests/` + pierwsze evals (routing: czy TARS oddaje właściwemu specjaliście).

### Faza 2: Kanały
- [ ] CLI: aliasy dla każdego profilu.
- [ ] Telegram: jedna grupa „TARS HQ”, jeden temat na specjalistę plus temat ogólny do TARS-a.
- [ ] Desktop: Bot Mode (lista botów, awatary, sekcje, czat grupowy floty).
- [ ] (opcjonalnie) głos: transkrypcja notatek głosowych, TTS.

### Faza 3: Pamięć i onboarding („żeby znał Ciebie od pierwszego dnia”)
- [ ] Wspólna pamięć o użytkowniku (Honcho: wspólny user peer, AI peer na profil).
- [ ] Skill **onboarding-wywiad**: TARS przeprowadza z Tobą rozmowę startową (cele, praca,
      nawyki, preferencje) i zapisuje profil użytkownika, z którego korzystają wszyscy.
- [ ] Zasady prywatności: co gdzie jest przechowywane, co nigdy nie opuszcza maszyny.

### Faza 4: Pełna flota (kilkunastu specjalistów)
- [ ] Każdy specjalista według kontraktu z sekcji 3: SOUL, 3–8 skilli, knowledge w `references/`, evals.
- [ ] Integracje MCP per specjalista (kalendarz, mail, notatki, dysk, bank export…).
- [ ] Budowa iteracyjna: 1–2 specjalistów na raz, każdy „dogfoodowany” przed kolejnym.

### Faza 5: Automatyzacje i rój
- [ ] Rutyny cron: poranny brief (TARS zbiera od specjalistów), przegląd tygodnia, przypomnienia.
- [ ] Gotowe „przepływy roju” jako skille TARS-a (np. *decyzja zakupowa*: research → finanse → rekomendacja).

### Faza 6: Jakość, koszty, bezpieczeństwo
- [ ] Evals odpalane przy każdej zmianie SOUL/skilli (regresje zachowań i routingu).
- [ ] Budżet kosztów: frontier tylko dla TARS-a i trudnych ról, tańsze modele dla reszty; `/usage`, `/insights`.
- [ ] Bezpieczeństwo: zatwierdzanie komend, backend Docker dla ryzykownych profili, sekrety tylko w `.env`.

### Faza 7: Pętla samodoskonalenia
- [ ] Hermes sam tworzy i poprawia skille podczas pracy. `harvest-skills.sh` zbiera te
      zmiany z `~/.hermes/profiles/*/skills`, a my je przeglądamy i commitujemy do repo.
      Dzięki temu flota uczy się, a repo zostaje źródłem prawdy.
- [ ] Wersjonowanie floty (tagi), changelog.

### Faza ∞
Wake word, Home Assistant, aplikacja mobilna, serwer 24/7 z backupami, kolejne specjalizacje…

---

## 6. Decyzje do podjęcia (z rekomendacjami)

| # | Decyzja | Rekomendacja | Dlaczego |
|---|---|---|---|
| D1 | Lista specjalistów | Wybierasz Ty (propozycja w sekcji 7) | To Twoje życie i Twoje potrzeby |
| D2 | Modele | Frontier dla TARS-a (np. Claude), tańsze dla specjalistów; zmiana per profil w `config.yaml` | Orkiestracja wymaga osądu, a wykonanie jasno opisanych zadań nie |
| D3 | Gdzie działa | Mały VPS lub domowy serwer z Dockerem (s6 pilnuje gatewaya); laptop do developmentu | TARS dostępny 24/7 z Telegrama |
| D4 | Główny kanał | Telegram (grupa z tematami) + CLI; desktop jako dodatek | Najtańszy start, działa z telefonu |
| D5 | Wspólna pamięć | Honcho (self-host, jeśli prywatność jest priorytetem) | Natywny model „wspólny użytkownik, osobni agenci” |
| D6 | Nazewnictwo profili | Prefiks `tars-` (`tars-fin`, `tars-dev`…) | Profile stają się komendami w shellu, a prefiks unika kolizji |
| D7 | Język | Polski domyślnie, skille technicznie po angielsku tam, gdzie pomaga modelowi | Naturalna rozmowa i precyzyjne instrukcje |

---

## 7. Propozycja floty (do wyboru i przycięcia)

| Profil | Rola |
|---|---|
| `tars` | Dyspozytor, osobowość, pierwsza linia, poranny brief |
| `tars-research` | Research w sieci, weryfikacja faktów, raporty ze źródłami |
| `tars-dev` | Programowanie, repozytoria, code review, automatyzacje skryptami |
| `tars-ops` | Serwer, backupy, Docker, bezpieczeństwo sprzętu i kont |
| `tars-fin` | Budżet, wydatki, oszczędzanie, inwestycje (bez wykonywania transakcji) |
| `tars-biz` | Strategia, pomysły biznesowe, analiza rynku, oferty |
| `tars-write` | Teksty, maile, social media, korekta, tłumaczenia |
| `tars-learn` | Nauka: plany, fiszki, tłumaczenie trudnych tematów |
| `tars-health` | Trening, dieta, sen, nawyki (z zastrzeżeniami medycznymi) |
| `tars-plan` | Kalendarz, zadania, cele, przeglądy tygodnia |
| `tars-home` | Dom, zakupy, porównywanie produktów, naprawy |
| `tars-travel` | Podróże: planowanie, loty, noclegi, plany dnia |
| `tars-legal` | Urzędy, umowy, pisma, prawo PL w ogólnym zarysie (nie porada prawna) |

---

## 8. Zasady projektu

1. **Nie forkujemy Hermesa.** Budujemy na krawędziach (profile, skille, MCP, pluginy).
   Jeśli czegoś brakuje w rdzeniu, najpierw szukamy rozwiązania w skillu lub pluginie.
2. **Repo jest źródłem prawdy.** Wszystko, co definiuje flotę, jest w git. Dane użytkownika
   (pamięć, sesje, klucze) nigdy nie trafiają do repo.
3. **Jeden specjalista naraz.** Każdego „dogfoodujemy” i testujemy evalsami przed dodaniem następnego.
4. **Nie psujemy cache’u promptów.** Zmiany SOUL i skilli działają od nowej sesji (tak projektuje Hermes).
5. **Bezpieczeństwo domyślnie:** zatwierdzanie ryzykownych komend, crony z dystrybucji startują wstrzymane.

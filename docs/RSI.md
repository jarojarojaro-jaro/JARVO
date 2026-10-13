# Pętla samodoskonalenia floty (RSI)

Flota sama poprawia swoje skille i prompty, a Jarvo zostaje tym samym Jarvem, tylko lepszym. Nie uczymy wag modelu
(nie mamy GPU ani własnego modelu; flota działa na modelach z API). Doskonalimy to, co jest nasze: skille, SOUL,
wzorce delegowania i skrypty. Każda zmiana przechodzi pomiar, bramki i Twoją zgodę, a potem zwykłą drogę:
commit w repo, `validate.py`, testy, `deploy.sh`. Cofnięcie zmiany to `git revert`.

Decyzja właściciela 2026-10-13: robimy R0, R1 i R2. R3 dopiero, gdy R2 sprawdzi się na specjalistach.

## Spis treści
- [1. Zasady](#1-zasady)
- [2. Research: co wzięliśmy, a czego nie](#2-research-co-wzięliśmy-a-czego-nie)
- [3. Etapy i stan](#3-etapy-i-stan)
- [4. R0: pomiar](#4-r0-pomiar)
- [5. R1: doświadczenie → lekcje](#5-r1-doświadczenie--lekcje)
- [6. Koszty](#6-koszty)
- [7. Czego nie robimy](#7-czego-nie-robimy)

## 1. Zasady

Te same zasady powtarzają wszystkie źródła z §2. Pilnuje ich kod, nie dobra wola agenta.

1. **Jarvo nadrzędny.** Pętla to kod i skille Jarva w repo. Nie stawiamy nad flotą obcego systemu (CLAUDE.md).
2. **Pomiar przed zmianą.** Bez historii wyników, punktu odniesienia i kilku przebiegów nie da się odróżnić poprawy
   od szczęścia (R0).
3. **Kto proponuje, ten nie ocenia.** Model, który proponuje zmianę, nie widzi zbioru odłożonego i nie może zmienić
   evals, rubryk, runnera ani red teamu. Sędzia evals jest z innej rodziny modeli niż oceniany agent.
4. **Zbiór odłożony i kanarki.** Ok. 1/4 scenariuszy to bramka, nigdy materiał do poprawek. Kanarek to znacznik-pułapka
   w pliku evals: jeśli pojawi się w odpowiedzi agenta, agent czytał scenariusze i wynik jest nieważny.
5. **Twarde sprawdzenia przed sędzią.** Sprawdzenia deterministyczne (`check`, kanarek) wygrywają z oceną LLM.
   Błąd sędziego nigdy nie liczy się jako zaliczenie.
6. **Bezpieczeństwo bez regresji.** Zmiana, po której choć jeden scenariusz `safety` albo atak red teamu przestaje
   przechodzić, odpada niezależnie od zysku gdzie indziej. Skille pisane przez agentów skanujemy przy zapisie.
7. **Człowiek zatwierdza.** Nic nie trafia na produkcję samo. Agenci zostają na A1; wdrożenie zmiany to A2.
8. **Małe zmiany z limitem.** Mała poprawka na raz (limit przyrostu tekstu), budżet na przebieg, koszt w raporcie.
9. **Wersja i cofnięcie.** Każda przyjęta zmiana to commit z wpisem w CHANGELOG profilu; poprzednia wersja zostaje w git.

## 2. Research: co wzięliśmy, a czego nie

Przegląd 2026-10-13: artykuły podane przez właściciela, repozytoria i praktyka produkcyjna. Wpisy repozytoriów
są w `vendor/zrodla.yaml`, licencje w [SOURCES.md](SOURCES.md).

| Źródło | Co robi | Dla Jarva |
|---|---|---|
| MASS, Sakana (arXiv 2610.12176, repo SakanaAI/mass bez licencji) | model układa zespół swoich kopii (rola, polecenie, kontrakt, kolejność), testuje układ przeciw najlepszemu, potem LoRA na najlepszych przebiegach | bierzemy: sędzia inny niż optymalizator (R0), pojedynek kandydat vs mistrz (R2), format workflowu (R3). Nie bierzemy: uczenia wag (6×H100) ani kodu |
| Harness Learning (arXiv 2609.35738) | model przepisuje harness; zmiana przyjęta tylko przy poprawie na zbiorze rozłącznym z tym do poprawek | bierzemy zasadę akceptacji (R0, R2); trening proponującego (RL) nie |
| Harness design (arXiv 2609.20804) | badanie budowy harnessu: przycinanie kontekstu, plan, wykrywanie zapętlenia | wskazówki, bez wdrożenia |
| RSI-Anything, Gen-Verse (arXiv 2610.13912) | propozycja, przewidywanie wyniku modelem świata, budżet sprawdzeń, bramki z cofaniem | tylko idee (budżet, osobne bramki); kod trenuje modele na GPU, odłożone |
| Recuris, Gen-Verse (arXiv 2608.24876, Apache-2.0) | stały meta-agent łata pamięć skilli, łatka przechodzi parowane porównanie na zbiorze odłożonym | wzór bramki R2, kod własny |
| hermes-agent-self-evolution, Nous (MIT) | projekt: SKILL.md przez DSPy + GEPA, benchmark jako bramka, zmiana tylko przez PR | bierzemy projekt bramek; prototyp nie działa (skill wychodzi bez zmian, metryka z pokrycia słów), kodu nie używamy |
| GEPA (MIT) | refleksja nad śladami i mutacja tekstu, zbiór Pareto | wzorzec mutacji w R2, bez paczki w obrazie |
| ACE (Apache-2.0) | playbook z licznikami pomógł/zaszkodził, zmiany przyrostowe | wzór księgi lekcji w R1 |
| Darwin Gödel Machine, SICA, Gödel Agent | agent przepisuje własny kod | odrzucone: koszt (DGM ok. 22 tys. $ za przebieg), DGM „naprawił” wynik, wycinając znaczniki wykrywania halucynacji |
| PROCTOR (arXiv 2609.02246) | lekcje z produkcyjnych pętli optymalizacji promptów: sędzia to nie wyrocznia | kanarki, role rozdzielone, twarde sprawdzenia przed sędzią, zamrożony zbiór odłożony (R0) |
| Skill misevolution (arXiv 2608.12851) | agenci uczący się bez bramki dopisują sobie szkodliwe skille (wszystkie 21 badanych kombinacji) | skan skilli przy zapisie i poczekalnia (R1) |
| Harness tampering (arXiv 2609.00069), RRSI (arXiv 2609.24972) | samodoskonalące się harnessy oszukują pomiar i przeuczają się na zbiorze treningowym | przegląd diffów, nie tylko wyników; limit zmian na kandydata |

## 3. Etapy i stan

| Etap | Co | Stan |
|---|---|---|
| R0 | pomiar: sędzia, historia, punkt odniesienia, zbiór odłożony, kanarki, powtórzenia, trend w HQ i w przeglądzie tygodnia | ✅ 2026-10-13 |
| R1 | doświadczenie → lekcje: liczniki w księdze lekcji, poczekalnia skilli agentów, skan przy zapisie | ✅ 2026-10-13 |
| R2 | kuźnia skilli: propozycja z nieudanych śladów, pojedynek, bramki, raport do decyzji | ⬜ |
| R3 | workflowy zespołowe Jarva (`dispatch-playbook`) | ⬜ po R2 |
| R4 | ewolucja skryptów z twardym sprawdzianem, z limitem kosztu | ⬜ opcjonalnie |

## 4. R0: pomiar

**Gdzie:** `scripts/run-evals.py` (runner), `scripts/evalslib.py` (zbiory, kanarki, scalanie, historia, porównanie,
wybór sędziego), `scripts/evals-wyniki.py` (trend, punkt odniesienia, porównanie), `scripts/evals-staging.sh`
(przebieg na stagingu), `fleet.yaml` → `evals.judges`.

**Zbiory.** Scenariusz jest w zbiorze roboczym albo odłożonym: pole `zbior` w `evals/<agent>/scenarios.yaml`,
a bez niego stały skrót id (co czwarty do odłożonego). `validate.py` wymaga co najmniej 2 odłożonych na agenta.
Scenariusza odłożonego nie przenosimy do roboczych: model proponujący zobaczyłby wtedy bramkę.

**Kanarki.** Każdy plik evals ma pole `kanarek: "JARVO-KANAREK-<12 hex>"` (unikalne, pilnuje `validate.py`; nowy agent
dostaje je z `new-agent.py`). Znacznik pojawia się tylko w `evals/`: skarbiec, dokumenty i profile go nie mają
(test). Znacznik w odpowiedzi albo w wywołaniach narzędzi = przebieg niezaliczony, alarm i kod wyjścia 3.

**Powtórzenia.** `--powtorzenia N` (1–10). Scenariusz jest zaliczony, gdy przeszła większość przebiegów; wynik
to średnia ocen sędziego (0..1). Sędzia z `evals.judges`, pierwszy z innej rodziny niż model agenta (agenci na
`gpt-6-luna` → `anthropic/claude-sonnet-5.5`; agenci na Claude → `openai/gpt-6-luna`). `--judge-model` albo
`JARVO_EVAL_JUDGE` wymusza innego. Błąd sędziego (sieć, nie-JSON po 3 próbach) = przebieg niezaliczony bez wyniku.
Bez `OPENROUTER_API_KEY` scenariusz bez twardego błędu jest **nieoceniony** (nie zaliczony), a taki przebieg nie zmienia
punktu odniesienia. Pusta odpowiedź agenta to zawsze niezaliczenie. Obie zasady wyszły z próby w piaskownicy bez
modelu: wcześniej runner pokazał 14/14 z wynikiem 1,00, choć agent nic nie odpowiedział.

**Historia i odniesienie.** Każdy przebieg dopisuje wiersz na agenta do `<wyniki>/historia.jsonl` (data, commit
z `BUILD.json`, model agenta, sędzia, powtórzenia, podsumowanie razem, per zbiór i per typ). `--ustaw-odniesienie`
zapisuje pełny przebieg jako punkt odniesienia; kolejne przebiegi porównują się z nim po scenariuszach (zmiana wyniku,
lepsze, gorsze, regresje, regresje bezpieczeństwa, jednostronny test znaków `p`). Przebieg częściowy (`--id`, `--zbior`)
trafia do historii z flagą `czesciowy`, ale nie zmienia odniesienia i nie liczy się do trendu.

**Gdzie widać wyniki.** `evals-staging.sh` po przebiegu kopiuje historię, punkty odniesienia i ostatni przebieg do
działającej floty (`/opt/data/jarvo/evals`). Karta agenta w HQ (zakładka o agencie) pokazuje wynik, zbiór
odłożony, trend i alarm kanarka; przegląd tygodnia Jarva (`weekly-review` 1.4.0, dane `evals` z `liczby.evals`)
wymienia spadki i alarmy, a spadek to sygnał do `fleet-improvement`, nie wyrok.

**Komendy (na serwerze):**
```bash
bash scripts/evals-staging.sh --agent jarvo-web --powtorzenia 3 --ustaw-odniesienie   # pierwszy pomiar
bash scripts/evals-staging.sh --agent jarvo-web --powtorzenia 3                       # po zmianie: porównanie
python3 scripts/evals-wyniki.py --wyniki /srv/jarvo/staging/hermes/eval-results trend
python3 scripts/evals-wyniki.py --wyniki … porownaj odniesienie <przebieg> --agent jarvo-web
```

**Naprawione przy okazji (2026-10-13):**
- szablon promptu sędziego miał klamry JSON-a, przez co `.format()` rzucał wyjątkiem i sędzia nie oceniał nic;
- runner nie brał `JARVO_MODEL_*` (`apply_model_overrides`), więc domyślnie wysyłał do OpenRoutera model
  `gpt-6-luna` bez prefiksu dostawcy;
- staging na macOS (wolumeny Dockera) podpinał dane produkcji, bo `JARVO_VOL_HERMES` z `compose/.env` wygrywał
  z `JARVO_DATA`;
- `--reset` stagingu kasował też historię wyników.

## 5. R1: doświadczenie → lekcje

**Gdzie:** `profiles/jarvo/scripts/lekcje.py` (księga lekcji), `profiles/jarvo/scripts/poczekalnia.py` (poczekalnia
skilli), `skills.write_approval: true` w `config.yaml` każdego specjalisty, skille Jarva `fleet-improvement` 1.2.0
i `weekly-review` 1.5.0, `scripts/harvest-skills.sh`.

**Księga lekcji z pomiarem skutku** (za ACE: licznik „pomogło / zaszkodziło” przy każdej regule). Wpis w
`<skarbiec>/fleet/lekcje.md` to jedna linia z polami po „ · ”: `potwierdzenia`, `karty`, `od`, `ostatnio`, opcjonalnie
`waga` (bezpieczeństwo, pieniądze, A2), `wdrożone: <data> <commit>` i `powroty` (karty, na których błąd wrócił).
`lekcje.py` (0 tokenów) dzieli wpisy na:
- **gotowe** do propozycji: ≥ 3 potwierdzenia z różnych kart albo ≥ 1 przy wadze,
- **przeterminowane**: bez potwierdzenia od 60 dni (wdrożonych nie przycinamy),
- **wdrożone** ze skutkiem: wynik evals agenta z ostatniego pełnego przebiegu przed wdrożeniem i z pierwszego po nim;
  zmiana ≥ +0,03 = pomogło, ≤ −0,03 = zaszkodziło, brak przebiegu po = brak pomiaru. Powroty błędu znaczą,
  że reguła nie działa, niezależnie od evals.

Przegląd tygodnia dostaje to jako `lekcje`; „zaszkodziło” albo powroty dają propozycję poprawki albo cofnięcia.

**Poczekalnia skilli** (za badaniem misevolution: agenci uczący się bez bramki dopisują sobie szkodliwe skille).
Specjaliści dalej tworzą skille po zadaniach (`creation_nudge_interval`), ale z `skills.write_approval: true` Hermes
nie zapisuje ich od razu: każdy zapis `skill_manage` (nowy skill, poprawka, plik pomocniczy) trafia do
`<profil>/pending/skills/<id>.json`. `validate.py` pilnuje, żeby każdy profil, który sam tworzy skille, miał bramę.
`poczekalnia.py lista` zbiera wpisy wszystkich profili i skanuje ich treść tymi samymi wzorcami co skille zewnętrzne
(`scripts/skan_skilli.py`: wstrzyknięcia, sekrety, pobierz-i-uruchom, ukryte znaki, groźny kod). Jarvo pokazuje je
w przeglądzie tygodnia z odciskiem; właściciel decyduje:
```bash
python3 $HERMES_HOME/scripts/poczekalnia.py lista
python3 $HERMES_HOME/scripts/poczekalnia.py zatwierdz jarvo-web 3f9c0a1b --odcisk 1a2b3c4d5e6f   # po „ok”
python3 $HERMES_HOME/scripts/poczekalnia.py odrzuc jarvo-web 3f9c0a1b --powod "dubluje nowa-strona"
```
- odcisk = SHA-256 agenta, id i treści zmiany: zgoda dotyczy tej wersji, inna treść wymaga nowej zgody,
- ustalenie skanu `high`/`critical` blokuje zatwierdzenie,
- zatwierdzenie stosuje zmianę kodem Hermesa (to samo co `/skills approve <id>` w czacie agenta), każda decyzja
  trafia do `<dane>/jarvo/poczekalnia.jsonl`,
- `brama_wylaczona`: profil tworzy skille bez bramy (np. ktoś zmienił config na serwerze); wdrożenie przywraca config
  z repo,
- zatwierdzony skill działa na serwerze, ale repo jest źródłem prawdy: `harvest-skills.sh` pokazuje go (i wpisy
  czekające) do przeniesienia do repo.

## 6. Koszty

Sędzia `claude-sonnet-5.5`: ok. 2 $ za 1 mln tokenów wejścia i 10 $ za 1 mln wyjścia (OpenRouter, 2026-10-13).
Jedna ocena to ok. 8 tys. tokenów wejścia, czyli ok. 0,02 $. Pełny przebieg floty (195 scenariuszy) z 3 powtórzeniami
to ok. 580 ocen, ok. 12 $ za sędziego. Do tego przebiegi agentów z ich limitu (subskrypcja albo klucze agentów).
Przebieg jednego agenta (14–39 scenariuszy × 3) to ok. 1–2,5 $ za sędziego.

## 7. Czego nie robimy

- uczenia wag (druga połowa MASS, RSI-Anything): nie mamy GPU ani własnego modelu;
- agenta przepisującego własny kod (Darwin Gödel Machine): drogie i oszukuje pomiar;
- automatycznego wdrożenia: każda zmiana czeka na Twoje „ok”;
- kodu MASS (brak licencji) i hermes-agent-self-evolution (nie działa) jako zależności;
- archiwum śladów do przyszłego uczenia modelu: to dane klientów, tylko za osobną zgodą właściciela.

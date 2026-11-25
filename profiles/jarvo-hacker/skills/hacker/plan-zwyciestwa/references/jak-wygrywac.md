---
source: "research floty Jarva 2026-11-25 (regulaminy platform, analizy zwycięzców, porady jury; tabela źródeł na końcu)"
reviewed: "2026-11-25"
---

# Jak wygrywać hackathony (także agentami AI)

Badanie dla agenta „Hacker” (właściciel: solo founder z Polski, UE).
Data weryfikacji wszystkich źródeł: **2026-11-25**.

Legenda statusu źródeł:

- **[P]** strona przeczytana bezpośrednio (źródło pierwotne lub tekst w całości).
- **[W]** fakt z wyników wyszukiwania lub fragmentu strony, nie czytany w całości.
- **[NZ]** niezweryfikowane: źródło wtórne, wpis na X, liczby nie do potwierdzenia u organizatora.
- **[INFERENCJA]** wniosek autora badania, nie fakt ze źródła.

Numery w nawiasach kwadratowych, np. [S3], odsyłają do listy źródeł na końcu.

---

## TL;DR

1. Sędziowie najpierw sprawdzają **wymagania formalne** (pass/fail), potem oceniają według rubryki. Wiele zgłoszeń odpada na etapie formalnym [S2][S8].
2. Wygrywa **działające demo jednej rzeczy dla jednego użytkownika**, opowiedziane krótko i pod rubrykę, a nie najbardziej ambitny kod [S2][S13][S14][S18].
3. Hackathon to **marketing sponsora**. Projekt wygrywa, gdy sponsor „dobrze wygląda”, nagradzając go [S17][S18].
4. Sponsor tracki dają najlepsze szanse, ale platformy **limitują liczbę nagród na projekt** (ETHGlobal: 3 nagrody partnerów; Devpost: często 1 główna + 1 bonusowa albo tylko 1) [S10][S8][S9].
5. Reguły dotyczące AI rozjechały się: od „wolno, ujawnij” (MLH) przez „nie cały projekt z AI” (ETHGlobal) po „przeważnie AI = dyskwalifikacja” (część wydarzeń 2026) [S1][S10][S36][S37][S38].
6. Agenci AI **już wygrywają** konkursy z obiektywną metryką (AtCoder AHC058, Kaggle Playground) i tory hackathonów (Agent Academy), a także mają własne areny (Colosseum Agent Hackathon) [S23][S24][S27][S29].
7. Wartość oczekiwana zależy głównie od **liczby rzeczywistych zgłoszeń** (często 5% do 30% zarejestrowanych), kwalifikowalności i reguł AI, a nie od wielkości puli [S31][S29][S41].

---

## 1. Kryteria ocen

### 1.1 Devpost (mechanika platformy)

- Sędzia ocenia każde kryterium w skali **1 do 5**; wynik projektu to średnia (lub średnia ważona, jeśli organizator włączy wagi, które muszą sumować się do 100%). Organizator dodaje **do 6 kryteriów**. Możliwe ocenianie punktowe albo rankingowe oraz wiele rund (np. runda 1 punktowa, runda 2 rankingowa) [S6][W].
- Typowy regulamin korporacyjny ma **dwa etapy** [S8][P]:
  - **Stage One (pass/fail):** czy zgłoszenie zawiera wszystkie wymagane elementy, odpowiada na wyzwanie i stosuje wymagane technologie.
  - **Stage Two:** kryteria ważone. Przykład Gemini 3 Hackathon: *Technical Execution 40%*, *Innovation/Wow Factor 30%*, *Potential Impact 20%*, *Presentation/Demo 10%* (w tym: czy wyjaśniono użycie Gemini 3, czy jest dokumentacja lub diagram architektury).
- Sędziowie Devpost (Square, Databricks, Google, NEAR, Atlassian) mówią [S2][P]:
  - pierwszy krok to **sprawdzenie wymagań**; „zaskakująco wiele” zgłoszeń ich nie spełnia;
  - wideo daje najwięcej kontekstu i często jest pierwszym (czasem jedynym) materiałem;
  - wyróżnia się projekt, który **wyraźnie celuje w kryteria** i równoważy je wszystkie; minus za przesadne skupienie na jednym kryterium lub sam backend bez UI;
  - czerwona flaga: ładne wideo i strona, a w repo mało kodu; ten sam projekt przemalowany pod kolejne hackathony (widać to w historii profilu Devpost);
  - nagradzane jest użycie zasobów od sponsora (kredyty, paczki, partnerzy).

### 1.2 ETHGlobal

Pięć kategorii (np. ETHGlobal Tokyo 2026) [S10][P]:

| Kategoria | Pytanie sędziego |
|---|---|
| Technicality | Jak złożony problem i jak wyrafinowane rozwiązanie? |
| Originality | Nowy pomysł albo kreatywne rozwiązanie znanego problemu? |
| Practicality | Na ile kompletne i działające? Czy grupa docelowa może tego użyć dziś? |
| Usability (UI/UX/DX) | Czy łatwo z tego korzystać? |
| WOW Factor | Czy zostaje w pamięci? |

- Finaliści: **7 minut**, w tym 4 min demo i 3 min pytań. Typowe pytania: inspiracja, dobór narzędzi, rozwiązane wyzwania [S10][P].
- Nagrody partnerów oceniane są **na podstawie materiałów zgłoszenia** (wizyta na stoisku opcjonalna) [S10][P].
- Przy wydarzeniach asynchronicznych pierwsza runda jest asynchroniczna i odsiewa projekty, do rundy na żywo przechodzi ok. 20% [S11][W].

### 1.3 lablab.ai / Starfield Labs

lablab.ai zmienił nazwę na **Starfield Labs** (strona lablab przekierowuje) [S15][P].

- Domyślnie cztery kryteria o równej wadze, które organizator może zmienić: **Innovation, Technical execution, Impact, Presentation**. „Istniejący produkt z dodanym czatem rzadko punktuje” [S13][P].
- Historyczne rubryki lablab: stopień ukończenia, prezentacja, zastosowalność, wartość biznesowa, innowacyjność, technologia, realny wpływ, wrażenie ogólne [S14][P].
- Wartość biznesowa wg lablab: konkretny użytkownik (nie „wszyscy”), przybliżony TAM, model przychodu, dlaczego bez AI się nie da [S16][W].

### 1.4 MLH

Cztery kryteria o równej wadze: **Technology, Design, Completion, Learning** [S1][P].

- MLH wprost: **nie ocenia** jakości kodu, jakości pitchu, jakości pomysłu ani tego, czy projekt rozwiązuje problem. Ocenia to, co zbudowano. Zalecane jest demo, a nie prezentacja.
- Kryterium „Learning” (czy zespół wyszedł poza strefę komfortu) słabo pasuje do autonomicznej floty [INFERENCJA].

### 1.5 Konkursy z obiektywną metryką (Kaggle, AtCoder Heuristic)

- Wynik = pozycja na leaderboardzie; brak subiektywnej oceny. To gra **liczby eksperymentów**, w której agenci mają przewagę [S24][S26].
- Kaggle: narzędzia AutoML (AMLT) dozwolone, jeśli masz licencję zgodną z regulaminem; dane i modele zewnętrzne dozwolone, o ile „rozsądnie dostępne dla wszystkich” i tanie, chyba że gospodarz zabroni; notebooki często bez internetu, więc wywołania zewnętrznych API w czasie predykcji nie działają [S45][W].

### 1.6 Wspólny mianownik

| Oś | Devpost (korporacyjne) | ETHGlobal | Starfield/lablab | MLH |
|---|---|---|---|---|
| Technika | 25% do 40% | Technicality | Technical execution | Technology |
| Nowość | Innovation/Wow | Originality + WOW | Innovation | brak (wprost nieoceniane) |
| Wpływ/biznes | Potential Impact | Practicality | Impact / Business value | brak |
| UX | często w Presentation | Usability | w Presentation | Design |
| Prezentacja | 10% do 25% | demo na żywo + Q&A | Presentation | demo, nie pitch |
| Kompletność | Stage One + Execution | Practicality | Degree of completion | Completion |

**Wniosek dla agenta Hacker:** przed budową zawsze tworzyć **macierz rubryki** (kryterium, waga, dowód, który pokażemy w wideo i README) i kilka godzin przed terminem oceniać projekt tą macierzą, poprawiając najpierw najniżej ocenione kryterium o najwyższej wadze [S13].

---

## 2. Wzorce zwycięzców

### 2.1 Wzorce powtarzające się w wielu źródłach

| Wzorzec | Dowód |
|---|---|
| Jeden konkretny użytkownik i jeden problem | Zwycięzcy lablab: kiwi video (uczący się), MarkU (marketerzy), Found in Translation (moderatorzy) [S14][P] |
| Działa tam, gdzie użytkownik już jest (Slack, mail, przeglądarka) | Found in Translation jako bot Slack [S14][P]; zwycięzcy Agent Academy wpięci w Teams/SharePoint/Jira [S27][P] |
| Wygląda na skończony produkt | AI Brand Intel („ready to market”, zbudowany solo) [S14][P] |
| Prawdziwe dane, nie placeholdery | Devpost: aplikacja straciła punkty, bo karty demo nie wyglądały realnie [S3][P] |
| Demo ważniejsze niż kod | „Zespół z najlepszym kodem prawie nigdy nie wygrywa. Wygrywa ten z najlepszym demo” [S18][P] |
| Narracja sponsora | „Czy nagradzając ten projekt, moja firma dobrze wypadnie?” [S17][P]; „hackathon to marketing” [S18][P] |
| Temat zgodny z trendem sponsora | Ray Deck przegrał kategorię z projektem AI, bo wybrał web3 [S17][P] |
| Cięcie zakresu, by zdążyć | „Cut bone to ship”: wielu zapowiadało dużo i nie dowiozło [S17][P] |
| Wideo jest najważniejszym nośnikiem | Sędziowie spędzają czas głównie w wideo, a sponsor potem nim się chwali [S17][P][S2] |
| Wczesne zgłoszenie | Czas na sprawdzenie kwalifikowalności, poprawki i odpowiedzi na pytania [S5][P] |
| Prawdziwa trakcja | MyFixam (3. miejsce, $100 000, Build with Gemini XPRIZE): realni użytkownicy, przychód, wersja co 2 do 3 dni [S4][P] |
| Wiedza domenowa człowieka | MyFixam: AI założyłoby płatność kartą, a w Nigerii kartami się nie płaci; model nie ustala cen [S4][P] |

### 2.2 Analizy konkretnych zwycięzców

- **MyFixam** (Devpost, Build with Gemini XPRIZE, 26 000 uczestników, top 100, top 5, 3. miejsce): Gemini 2.5 Flash w 5 systemach produkcyjnych, wideo w stylu reklamy z prawdziwym rzemieślnikiem, scenariusz pisany samodzielnie „z perspektywy rzemieślnika” [S4][S3][P].
- **Polyfork** (1. miejsce $500 000, Build with Gemini XPRIZE) oraz **Tailored Labs** (grand prize $100 000, World's Largest Hackathon by Bolt) wskazywane przez Devpost jako wzorcowe wideo [S3][P].
- **Alfred Robot Butler** (John Kim, grand prize na hackathonie AI robotics, 2026): jeden projekt trafiający w **4 tracki** sponsorów (telefoniczny agent głosowy, framework agentów, sterowanie robotem, hosting MCP). Wcześniej wygrana nagroda Esri po rozmowie: „jeśli zbudujemy to dziś, wygrywamy?” [S18][P].
- **Microsoft Agent Academy Hackathon** (12 maja do 2 czerwca 2026): zwycięzcy mają repo + wideo, wielu używa MCP i human-in-the-loop. Zwycięzca toru Cowork Collective, **Copilot Cowork Autonomous ITSM**, był „w całości zbudowany i utrzymywany przez agentów AI pod nadzorem jednej osoby”. Sędziowie chwalili bramki akceptacji, least-privilege i jasną prezentację wartości [S27][P].
- **lablab 2022/2023**: zwycięzcy to wąskie, codzienne zadania biznesowe; wąskie zadanie (MarkU) pokonało ambitniejsze (GPT-Swarm) [S14][P].

### 2.3 Era AI: co zmieniło się w 2026

- Aplikacje zbudowane przez AI wyglądają tak samo (fioletowe gradienty, zaokrąglone karty, emoji w nagłówkach); sędziowie rozpoznają „generyczne” w 2 sekundy. Pomysły z AI też się powtarzają, bo ten sam model podsuwa je wszystkim [S39][W].
- Sędziowie piszą o „tej samej formule” w dziesiątkach projektów [S40][W].
- Devfolio wdrożyło **agenta-audytora** zgłoszeń: czyta opis, przechodzi repo narzędziami i wypisuje niezgodności między deklaracjami a kodem z cytatami `plik:linia`; ostateczną decyzję podejmuje człowiek. Nadmuchany README to dłuższa lista twierdzeń do obalenia [S25][P].
- Devpost radzi pisać historię projektu **własnymi słowami**; AI tylko do szlifu, bo teksty AI „zaczynają brzmieć tak samo” [S3][P].

**Wniosek [INFERENCJA]:** flota powinna świadomie odróżniać się wizualnie (własny design system zamiast domyślnego szablonu), zaczynać od problemu z doświadczenia właściciela lub danych z badań, a każde twierdzenie w README mieć udokumentowane w kodzie.

### 2.4 Agenci AI, którzy już wygrywają

| Przypadek | Wynik | Uwagi |
|---|---|---|
| Sakana ALE-Agent, AtCoder Heuristic Contest 058 (14.12.2025) | **1. miejsce** z 804 uczestników | Koszt ok. $1 300 (2 654 wywołań GPT-5.2, 2 119 Gemini 3 Pro); udział „za specjalną zgodą” AtCoder; wirtualny rating 2592 (66. wśród aktywnych) [S23][P] |
| Agent OpenAI, AtCoder World Tour Finals Heuristic 2025 | 2. miejsce | wg Sakana [S23][P] |
| Zespół NVIDIA, Kaggle Playground (churn), marzec 2026 | **1. miejsce** | 3 agenci LLM, ponad 600 000 linii kodu, 850 eksperymentów, stack 150 modeli; „tabular ML to gra liczby eksperymentów” [S24][W] |
| MLE-bench (OpenAI, 75 konkursów Kaggle) | o1-preview + AIDE: medal w 16,9% konkursów | późniejsze prace: 47,7% na MLE-bench lite [S26][S47][W] |
| Colosseum Agent Hackathon (Solana, 2 do 12.02.2026) | 1 634 agentów, 454 ukończone projekty; 1. DegenDome ($50 000) | agenci rejestrują się i budują sami, ludzie głosują, sędziowie wybierają [S29][P] [S30][NZ] |
| Copilot Cowork ITSM (Agent Academy) | 1. miejsce w torze | zbudowany przez agentów pod nadzorem jednej osoby [S27][P] |
| 0xClaw | deklaruje „Hackathon Champion Project” i publikację EMNLP 2026 Findings | dostał tylko URL hackathonu i sam przeszedł 7 faz do dokumentów zgłoszenia [S32][P, deklaracje twórców NZ] |

---

## 3. Strategia sponsor tracków

### 3.1 Twarde limity

| Platforma / wydarzenie | Limit nagród na projekt |
|---|---|
| ETHGlobal | Do **3 nagród partnerów**; partner z wieloma trackami liczy się jako 1 [S10][P] |
| ETHGlobal | Projekt budowany przed wydarzeniem: **brak nagród partnerów i statusu finalisty** (chyba że track Continuity) [S10][P] |
| Devpost, np. Codegeist 2026, Hack Reddit 2025 | 1 nagroda główna + 1 bonusowa [S9][W] |
| Devpost, np. Gemini 3, OpenAI Build Week | **Tylko 1 nagroda** [S8][P][S9][W] |
| Devpost, DIF Hackathon | 1 główna + 1 bonusowa + 1 sponsorska [S9][W] |
| Devpost, World's Largest Hackathon (Bolt) | 1 globalna LUB regionalna + 1 challenge + 1 bonusowa [S9][W] |

### 3.2 Taktyka

1. **Jeden główny track + 2 lub 3 poboczne**, wszystkie głęboko zintegrowane, a nie doklejone [S20][NZ][S18][P]. Nagrody sponsorów są łatwiejsze do zdobycia niż główna nagroda czy People's Choice, zwłaszcza gdy projekt mówi językiem celów sponsora [S22][W]; zespoły z kilkoma nagrodami zapamiętuje się lepiej niż z jedną [S21][W].
2. **Mniej oblegane bounty:** przewidzieć, które tracki wybiorą wszyscy, i iść w mniej popularne; na jednym wydarzeniu kilka bounty zostało w ogóle nieodebranych [S19][W][S17][P].
3. **Nagrody pulowe** dają niemal pewne małe pieniądze: np. ENS na ETHGlobal New York 2026 dzielił pulę między maks. 43 zespoły po maks. $140, za dowolną integrację z kodem napisanym pod ENS [S12][P].
4. **Rozmowa ze sponsorem** (na żywo przy stoisku, online na Discordzie sponsora): sprawdzić reakcję na pomysł, dopytać, co chcą zobaczyć [S18][P][S20][NZ].
5. **Analiza poprzednich zwycięzców tego samego sponsora** (ETHGlobal Showcase, galerie Devpost): do tego służą scrapery z sekcji 6.
6. **Nazwa sponsora w demo i w opisie**: dla każdej nagrody partnera ETHGlobal trzeba opisać sposób integracji i dać feedback [S10][P]; sponsor chce usłyszeć nazwę produktu [S18][P].
7. **Spełnić wymagania kwalifikacyjne tracku dosłownie** (np. HackMoney 2026: TxID transakcji, repo GitHub, README; brak UI dozwolony, ale musi być dowód działającego kodu) [S12][P].

### 3.3 Zastrzeżenia

- Według analizy WebZero (wpis na X) zespoły z jednym trackiem miały ok. 13% skuteczności, a „stackowanie” nie poprawiało wyraźnie szans; lepiej wypadały zintegrowane produkty, a nie zbieranie nagród [S20][NZ].
- Na Devpost stackowanie wielu nagród jest często niemożliwe (limit 1 lub 1+1), więc tam liczy się wybór **jednej** kategorii, gdzie jesteśmy najmocniejsi [S8][S9].

---

## 4. Zgłoszenie (wideo, README, opis)

### 4.1 Wideo: twarde wymagania platform

| Platforma | Wymagania |
|---|---|
| Devpost (zwykle) | ok. 3 min, część wydarzeń 5 min; TTS zwykle dopuszczalny (sprawdzić wymóg języka); publiczne lub niepubliczne, nie prywatne [S3][P][S7][W] |
| MLH digital | **max 2 min**, nagrane w weekend hackathonu, na początku nazwa hackathonu („Hey, I'm Sam and this is my demo for CorgiHacks”) [S1][P] |
| ETHGlobal | **2 do 4 min** (poza zakresem upload odrzuca), min. 720p, **bez przyspieszania**, **bez muzyki z napisami zamiast mowy**, **bez nagrywania telefonem**, **bez TTS / AI voiceover** [S10][P] |
| Gemini 3 (Devpost) | projekt musi działać tak, jak pokazano na wideo i w opisie [S8][P] |

**Konsekwencja dla floty [INFERENCJA]:** agent wideo może przygotować scenariusz, nagranie ekranu, montaż i napisy, ale przy ETHGlobal narrację musi nagrać właściciel własnym głosem. Do nagrań aplikacji mobilnych używać zrzutu ekranu z telefonu floty, a nie kamery skierowanej na telefon.

### 4.2 Wideo: dobre praktyki

- Aplikacja na ekranie **w pierwszych 10 sekundach** („scrub test”) [S3][P].
- W pierwszych 30 s: jaki problem i dla kogo [S3][P][S13][P].
- Struktura 3 min (Devpost): 15 s problem, 2 min aplikacja, 30 s jak zbudowane i co dalej. Struktura 4 min (Starfield): 0:00 do 0:30 problem, 0:30 do 2:30 działanie na prawdziwych danych, 2:30 do 3:30 wpływ i biznes, 3:30 do 4:00 zespół, czego jeszcze brak, plan [S3][S13][P].
- Pitch i demo ćwiczyć jak osobny produkt: zwycięzcy MadHacks 2023 przypisują wygraną całemu przedpołudniu prób prezentacji [S28][W].
- Realistyczne dane demo, powiększona czcionka, wyłączone powiadomienia, wskaźniki i zoomy prowadzące wzrok [S3][P].
- Nie przyspieszać audio, by zmieścić się w limicie; ciąć wstęp, nie demo [S3][S10][P].
- Nagrać szybką wersję **jak najwcześniej**, wrzucić od razu (YouTube daje link przed końcem uploadu), sprawdzić link w oknie prywatnym bez logowania [S3][P].
- Mieć gotowe wideo zapasowe, nawet przy demo na żywo; organizatorzy potrafią w ostatniej chwili wymusić nagrania [S18][P].
- Wideo w stylu reklamy z prawdziwym użytkownikiem może wyróżnić projekt (MyFixam) [S4][P].

### 4.3 README (repo)

Szablon wynikający ze źródeł [S42][S43][W][S8][S10][P]:

1. Nazwa + jednozdaniowy tagline: „[Produkt] pomaga [komu] robić [co] dzięki [jak]”.
2. Problem i użytkownik (jedna scena, nie rynek).
3. Co robi: podróż użytkownika w 3 krokach (przynosi X, aplikacja robi Y, wychodzi z Z).
4. Link do demo + **dane testowe lub tryb demo**, jeśli jest logowanie [S3].
5. Uruchomienie w 5 minut (jedna komenda, Docker lub skrypt).
6. Diagram architektury (wymagany wprost np. w kryterium Presentation Gemini 3 [S8]).
7. Sekcja **„Integracje sponsorów”**: każda technologia sponsora z odnośnikami do plików, w których jest użyta.
8. Sekcja **„Użycie AI”**: jakie narzędzia, które pliki lub zasoby są generowane lub wspomagane; przy spec-driven development dołączyć specyfikacje, prompty i artefakty planowania (wymóg ETHGlobal) [S10][P].
9. Sekcja **„Co istniało wcześniej”**: biblioteki, starter kity, kod sprzed wydarzenia; jasne oddzielenie nowego od użytego ponownie [S10][P].
10. Ograniczenia i to, co jeszcze nie działa (uczciwość, sędziowie wyczuwają zainscenizowane demo) [S13][P].
11. Licencja i zespół z rolami (w tym jasny opis roli człowieka i agentów).

Historia commitów: **regularne commity przez cały czas trwania**; ETHGlobal może zdyskwalifikować zgłoszenie z dużym pojedynczym commitem lub bez historii [S10][P]; Starfield: „jeden wielki commit na końcu” to błąd [S13][P].

### 4.4 Opis projektu (Devpost „story”)

Sekcje: *Inspiration, What it does, How we built it, Challenges we ran into, Accomplishments, What we learned, What's next* [S42][W].

- Wyzwania: formuła „trafiliśmy na X, próbowaliśmy Y, skończyło się na Z”, z liczbami [S42][W].
- Osiągnięcia: liczby i „pierwsze razy” [S42][W].
- Odpowiedzieć **wprost na każde kryterium oceny** i każde pytanie formularza [S2][S5][P].
- Pisać własnym głosem; AI tylko poprawia [S3][P]. Dla floty: szkic pisze agent, właściciel czyta, poprawia i dopisuje własne zdania [INFERENCJA].
- Nie przesadzać z deklaracjami: audytor (człowiek lub agent jak w Devfolio) porównuje opis z kodem [S25][P].

---

## 5. Zasady i ryzyka dyskwalifikacji

### 5.1 Kod istniejący przed wydarzeniem

| Źródło | Reguła |
|---|---|
| MLH | Cała praca w czasie hackathonu; wolno pomysł sprzed wydarzenia, nie wolno kodu ani materiałów; wolno biblioteki i open source, ale **nie wolno** opublikować własnego kodu przed wydarzeniem tylko po to, by go użyć [S1][P] |
| Devpost, wariant „New Projects Only” | Projekt tworzony od zera w okresie konkursu, nie modyfikacja istniejącej pracy (Gemini 3, Kiroween 2026) [S8][P][S7][W] |
| Devpost, wariant „New & Existing” | Istniejący projekt dopuszczony, jeśli **znacząco zaktualizowany** w okresie zgłoszeń; trzeba opisać co zmieniono [S7][W] |
| ETHGlobal | Track Classic „From Scratch” albo tracki Continuity (rozwój istniejącego kodu, z dokumentacją) [S10][P] |
| HackUTD 2025 | Pomysły wcześniejsze tak, projekty nie [S37][P] |

**Dla floty [INFERENCJA]:** biblioteka komponentów floty (szablony, narzędzia) musi być publiczna, ogólna i używana jawnie jako „starter kit”, z opisem w README. Ryzykowne jest wnoszenie gotowego produktu Jarvo jako „nowego” projektu.

### 5.2 Kod generowany przez AI i autonomiczni agenci

| Źródło | Reguła |
|---|---|
| MLH | AI dozwolone (uzupełnianie, generowanie kodu i obrazów), ale trzeba być **uczciwym i transparentnym**, wymienić narzędzia w zgłoszeniu i odpowiadać na pytania; „najlepsze projekty użyją AI, ale ostatecznie stworzą je ludzie” [S1][P] |
| ETHGlobal | AI dozwolone z **atrybucją** (które pliki, które zasoby); AI ma **wspierać, nie stworzyć całości**; projekty oparte całkowicie na AI bez znaczącego wkładu ludzi mogą stracić prawo do nagród partnerów i finału; przy spec-driven trzeba dołączyć specyfikacje i prompty [S10][P] |
| HackUTD 2025 | „Każde użycie AI do pisania kodu będzie badane i grozi dyskwalifikacją”; nie wolno zgłosić projektu w pełni wygenerowanego [S37][P] |
| HackAIthon (Craft Ventures) | Co najmniej **40% kodu oryginalnego** (nie z AI, nie open source, nie sprzed wydarzenia) [S36][P] |
| Hackathon University of Sydney 2026 | Zgłoszenie „przeważnie wygenerowane przez AI” zostanie zdyskwalifikowane [S38][W] |
| Przegląd regulaminów 2026 (brabble.ai) | Trzy grupy: dozwolone z ujawnieniem; tylko debugowanie i zrozumienie; odradzane do masowego generowania [S35][P] |
| Starfield / lablab | Wprost „ludzie i ich agenci budują obok siebie”, MCP do zapisu, zespołu i zgłoszenia [S15][P]; „AI team members excluded” z limitu wielkości zespołu (wydarzenie na Luma) [S16][W] |
| Colosseum Agent Hackathon | Agenci są uczestnikami; nagrody uznaniowe, z weryfikacją i sprawdzeniem kwalifikowalności; człowiek „przejmuje” agenta, by odebrać nagrodę [S29][P] |
| AtCoder AHC | ALE-Agent startował „za specjalną zgodą” AtCoder [S23][P]; [INFERENCJA] autonomiczny udział wymaga zgody organizatora |
| Kaggle | AutoML dozwolony przy odpowiedniej licencji; reguły danych zewnętrznych zależą od konkursu [S45][W] |

### 5.3 Inne typowe pułapki

- **Kwalifikowalność geograficzna:** np. Gemini 3 wyklucza mieszkańców Włoch, Quebecu, Krymu, Kuby, Iranu, Syrii, Korei Płn., Sudanu, Białorusi, Rosji i krajów objętych sankcjami OFAC; Polski nie ma na liście [S8][P]. Zawsze sprawdzać, bo część wydarzeń jest tylko dla studentów, jednego kraju lub partnerów [S31][P].
- **Studenci:** MLH to wydarzenia głównie studenckie (student = także absolwent do 12 miesięcy) [S1][P].
- **Zgłaszanie tego samego projektu w wielu miejscach:** zakazane przez MLH digital i np. HackUTD [S1][S37][P]; sędziowie widzą historię profilu Devpost [S2][P].
- **Repo i wideo muszą pozostać publiczne** po wydarzeniu, inaczej można wybrać nowych zwycięzców [S1][P].
- **Prace po terminie:** dozwolone tylko drobne poprawki błędów [S1][P]. Na Devpost zmiany po terminie nie trafiają do zgłoszenia [S5][P].
- **Termin:** spóźnione zgłoszenia nie są przyjmowane (ETHGlobal) [S10][P]; część hackathonów nie daje przedłużeń [S5][P].
- **Odbiór nagrody:** Devpost wymaga formularza W-8BEN dla osoby spoza USA [S44][W]; standardowo 30% potrącenia, chyba że umowa o unikaniu podwójnego opodatkowania obniża stawkę [S46][W]. [INFERENCJA, do weryfikacji z doradcą podatkowym]: czy umowa USA-Polska obniża podatek od nagród konkursowych i jak rozliczyć nagrodę (także w USDC) w polskim PIT.
- **Kryptowaluty:** nagrody w USDC/tokenach (Colosseum, ETHGlobal) wymagają portfela i rozliczenia podatkowego [S29][P][INFERENCJA].

### 5.4 Etyka: czego Hacker nie robi nigdy

1. **Brak plagiatu.** Plagiat oznacza dyskwalifikację (np. Hack the North 2025) [S48][W]. Głośny przypadek Hackout 2025: drużyna przyłapana na oszustwie i najpierw zdyskwalifikowana, później wygrała, co wywołało falę krytyki organizatorów [S49][W]. Nauka: nawet jeśli oszustwo „przejdzie”, niszczy reputację.
2. **Brak fałszywych demo.** Projekt musi działać tak, jak na wideo [S8][P]; sędziowie widzą inscenizację [S13][P]; audytorzy AI porównują deklaracje z kodem [S25][P]. Wolno pokazać „szczęśliwą ścieżkę” i mockować peryferia, ale „najtrudniejsza rzecz, którą deklarujesz, musi działać naprawdę” [S18][P].
3. **Pełne ujawnienie użycia AI i agentów** zgodnie z regulaminem [S1][S10][P].
4. **Brak masowego spamu zgłoszeniami.** curl zamknął program bug bounty (koniec stycznia 2026) z powodu zalewu raportów AI slop: odsetek ważnych zgłoszeń spadł z ponad 15% do poniżej 5% [S33][S34][W]. Popularne bounty na Algora dostają od 8 do 158 prób w ciągu godzin, większość to niedziałający kod AI [S50][W]. Flota musi zgłaszać mało, ale dobrze.
5. **Brak manipulacji głosowaniem** (People's Choice, głosy ludzi w Colosseum) [INFERENCJA].
6. **Jeden projekt, jedno wydarzenie**, chyba że regulamin wprost pozwala inaczej [S1][S2].
7. **Szacunek dla sędziów i mentorów:** pytania do organizatorów przed terminem w kanale dyskusji, nie po [S5][P].

---

## 6. Narzędzia i agenci open source

### 6.1 Odkrywanie hackathonów

| Narzędzie | URL | Co robi | Status |
|---|---|---|---|
| hackathons-ics | https://github.com/TerexitariusStomp/hackathons-ics | Kalendarz iCal z Devpost, DoraHacks, Encode, lablab, ETHGlobal, MLH, Devfolio, Unstop, HackerEarth; deduplikacja, przypomnienia o terminach, przebudowa 4 razy dziennie, MIT | [P] |
| 0xarchit/hackathon-api | https://github.com/0xarchit/hackathon-api | API w Go agregujące Devfolio, Unstop, Devpost, MLH, HackerEarth i inne (rdzeń hackathons-ics), MIT | [P przez README hackathons-ics] |
| online-hackathons-by-prize-per-entrant | https://github.com/arxhww/online-hackathons-by-prize-per-entrant | Ranking hackathonów Devpost wg nagrody na zarejestrowanego, utrzymywany przez agenta (Claude); ostatnia aktualizacja 2026-11-03 | [P] |
| hackathon-aggregator | https://github.com/handyautomatization-commits/hackathon-aggregator | Cotygodniowy digest konkursów i bounty z 6+ źródeł, ranking przez DeepSeek, Telegram, GitHub Actions | [W] |
| HackFinder | https://github.com/nivash-devs/HackFinder | Hack Club, Devpost, MLH, itch.io wg miasta | [W] |
| Hackathon Radar (Apify) | https://apify.com/kineticforge/hackathon-radar | Devpost, Devfolio, MLH: pula w USD, daty, online, liczba uczestników | [W] |
| ETHGlobal Showcase scraper | https://github.com/Pabl0cks/hackathon-scraper | Dane projektów z ETHGlobal Showcase (analiza zwycięzców sponsorów) | [W] |
| devpost-scraper | https://github.com/lasamson/devpost-scraper | Zgłoszenia z dowolnego hackathonu Devpost do CSV (analiza konkurencji i zwycięzców) | [W] |
| Zbiór danych 10 000+ hackathonów Devpost | https://www.kaggle.com/datasets/aceeedev/hackathons | Hackathony 2009 do 2024, do modelowania wartości oczekiwanej | [W] |
| Starfield Labs MCP | https://starfieldlabs.ai/ | Oficjalny MCP: wyszukiwanie wydarzeń, zapis, zespół, kredyty, zgłoszenie przed terminem | [P] |
| lablab-mcp | https://github.com/WilliamAxelC/lablab-mcp | Serwer MCP: szczegóły wydarzeń, nagrody, technologie sponsorów, scaffold repo (określa się jako oficjalny, nie potwierdzono u lablab) | [W][NZ] |

### 6.2 Agenci budujący i zgłaszający projekty

| Narzędzie | URL | Co robi | Status |
|---|---|---|---|
| 0xClaw | https://0xclaw-ai.github.io/ , https://github.com/0xclaw-ai/0xClaw | Autonomiczny agent hackathonowy: z URL wydarzenia przez 7 faz (research, pomysły, wybór, plan, kod, testy, dokumenty zgłoszenia); MIT; deklaruje publikację EMNLP 2026 Findings | [P][NZ dla deklaracji wygranych] |
| hackathon-agent-factory | https://github.com/Ash-Blanc/hackathon-agent-factory | Pętla: skanowanie hackathonów z dozwolonym AI (TinyFish), wywiad o poprzednich zwycięzcach (Parallel.ai, Nia), budowa w sandboxach przez OpenCode **lub Hermes**, pipeline nagrywania demo (Kdenlive) | [P] |
| autonomous-hackathon-agent | https://github.com/karun99/autonomous-hackathon-agent | Skanowanie hackathonów, pomysły, prototypy bez płatnych API | [W] |
| hackathon-playbook (skill) | https://github.com/SidTheKid-dotcom/hackathon-playbook | Skill dla Claude Code, Codex, Cursor: dekodowanie wydarzenia, kill-test pomysłów, budowa, weryfikacja, demo | [W] |
| hackathon-submission-kit | https://github.com/swapnilchaudhari007/hackathon-submission-kit | Szablony opisu Devpost, README, scenariusza demo, checklisty | [W] |
| convex-hackathon-skill | https://github.com/get-convex/convex-hackathon-skill | Dziennik postępu z historii git (dowód pracy w czasie wydarzenia) | [W] |

### 6.3 Agenci do konkursów z metryką

| Narzędzie / praca | URL | Znaczenie | Status |
|---|---|---|---|
| ALE-Agent / ALE-Bench (Sakana AI) | https://sakana.ai/ahc058/ | 1. miejsce AHC058; logi agenta publiczne | [P] |
| AIDE (Weco AI) | https://arxiv.org/abs/2502.13138 | Scaffold do Kaggle, najlepszy w MLE-bench | [W] |
| MLE-bench (OpenAI) | https://arxiv.org/abs/2410.07095 | 75 konkursów Kaggle jako benchmark agentów | [W] |
| AI Research Agents for ML (MLE-bench lite 47,7%) | https://arxiv.org/abs/2507.02554 | Strategie przeszukiwania i operatory | [W] |
| AutoKaggle | https://arxiv.org/html/2410.20424v3 | Wieloagentowy framework do Kaggle | [W] |
| Playbook NVIDIA (EDA, baseline, feature engineering, hill climbing, stacking) | https://developer.nvidia.com/blog/winning-a-kaggle-competition-with-generative-ai-assisted-coding/ | Przepis dla agentów + GPU (cuDF, cuML, XGBoost) | [W] |

### 6.4 Areny wyłącznie dla agentów

| Arena | URL | Uwagi | Status |
|---|---|---|---|
| Colosseum Agent Hackathon (Solana) | https://colosseum.com/agent-hackathon | 1. edycja 2 do 12.02.2026, $100 000 USDC (50/30/15 tys. + $5 000 „Most Agentic”); skill.md dla agentów, API, forum, leaderboard | [P] |
| Moltathon | https://www.moltathon.xyz/ | Agenci zakładają hackathony, proponują pomysły, budują i oceniają; ludzie tylko obserwują | [W] |
| Agentathon | https://agentathon.dev/ | Agenci zapisują się, budują i zgłaszają; „zero ludzi” | [W] |

### 6.5 Strona sędziów

- Devfolio Agentic Evaluator: wiedzieć, że zgłoszenia mogą być audytowane przez agenta, który szuka niezgodności opisu z kodem [S25][P].
- Część regulaminów Devpost dopuszcza „zautomatyzowaną analizę AI” w ocenie [S41][W].

---

## 7. Wartość oczekiwana

### 7.1 Wzór

Dla hackathonu h:

$$EV_h = \sum_{k} p_k \cdot N_k \cdot (1 - t) \cdot f \; + \; V_{\text{niemat}} \; - \; C_{\text{API}} - C_{\text{GPU}} - w \cdot T_{\text{właściciel}}$$

- $p_k$: prawdopodobieństwo zdobycia nagrody k (główna, track, pula);
- $N_k$: kwota nominalna; $t$: potrącenia podatkowe (domyślnie 30% przy organizatorze z USA, dopóki nie potwierdzono niższej stawki) [S46][W]; $f$: kurs i zmienność (krypto);
- $V_{\text{niemat}}$: kredyty, kontakt ze sponsorem, widoczność produktów Jarvo, portfolio;
- $C$: koszt API i GPU (punkt odniesienia: $1 300 za 4 godziny ALE-Agent [S23]); $T_{\text{właściciel}}$: godziny właściciela (narracja, przegląd, decyzje), $w$: jego stawka.

Szacunek $p_k$ [INFERENCJA]:

$$p_k \approx \min\left(0{,}9;\; \frac{\text{liczba nagród w kategorii } k}{\text{oczekiwana liczba zgłoszeń w } k} \cdot q\right)$$

gdzie $q$ to mnożnik jakości (1 = przeciętne zgłoszenie, 2 do 4 = zgłoszenie z checklisty „Plan zwycięstwa”, 0 = ryzyko dyskwalifikacji za AI).

### 7.2 Dane do kalibracji

| Wydarzenie | Zarejestrowani | Zgłoszenia | Wskaźnik |
|---|---|---|---|
| Google ADK Hackathon (2025) | 10 400+ | 477 | ok. 4,6% [S41][P] |
| Colosseum Agent Hackathon (2026) | 1 634 agentów | 454 | ok. 28% [S30][NZ] |
| Build with Gemini XPRIZE | 26 000 | top 100, top 5 do finału | [S4][P] |
| Meta AI Hackathon 2026 | b.d. | 5 367 | [S40][W] |
| Wydarzenia MLH 2024 (stacjonarne) | b.d. | 60% do 70% zarejestrowanych | [S51][NZ] |

- Mediana puli hackathonów webdev wg HackathonRadar: $5 000, ok. $29 na uczestnika [S52][W].
- Ranking „nagroda na zarejestrowanego” (2026-11-03): AWS MSP AI Hackathon $1 882, QNX $316, Meta VR $202, Codegeist 2026 $85, Kiroween 2026 $14, PayPal AI $2. Uwaga autora rankingu: zarejestrowani to nie zgłoszenia, wskaźnik spada z czasem, a ograniczenia kwalifikowalności bywają ważniejsze niż wskaźnik [S31][P].
- Ktoś na HN szacuje, że 2 do 4 hackathonów miesięcznie z bounty $1 000 do $10 000 może utrzymać jedną osobę [S53][W].

### 7.3 Przykład liczbowy [INFERENCJA]

Hackathon online Devpost, pula $50 000, 10 nagród (średnio $5 000), 2 000 zarejestrowanych, zakładamy 7,5% zgłoszeń, czyli 150:

- bazowo $p = 10/150 \approx 6{,}7\%$; z $q = 3$: $p \approx 20\%$;
- przychód brutto: $0{,}2 \cdot 5\,000 = 1\,000$ USD; po 30% potrącenia: 700 USD;
- koszt: 150 USD API + 6 h właściciela; jeśli godzina właściciela = 50 USD, to $EV \approx 700 - 150 - 300 = 250$ USD plus wartości niematerialne.

Track sponsora za $2 000, ok. 8 konkurentów (ze scrapera galerii), $q = 2$: $p \approx 25\%$, $EV$ brutto 500 USD przy marginalnym koszcie dodatkowej integracji.

### 7.4 Heurystyki wyboru (do karty oceny agenta)

1. **Najpierw filtry zero-jedynkowe:** kraj, wiek, status studenta, zakaz AI, wymóg obecności na miejscu, wymóg głosu człowieka, wymóg firmy lub partnera.
2. **Nagroda na realne zgłoszenie**, nie na rejestrację.
3. **Liczba nagród** (szeroki rozkład lepszy niż jedna duża) i limity łączenia nagród.
4. **Typ oceny:** obiektywna metryka (przewaga agentów i GPU) kontra subiektywna (przewaga historii i demo).
6. **Czas trwania:** długie online (tygodnie) pozwalają flocie dopracować wideo i trakcję; krótkie 24 do 48 h premiują szybki scaffold [INFERENCJA].
7. **Ryzyko regulaminowe AI** jako mnożnik: „ujawnij” = 1,0; „nie cały projekt” = 0,6 i wymaga realnego wkładu właściciela; „przeważnie AI = DQ” lub „40% oryginalnego kodu” = pominąć [INFERENCJA].
8. **Wartość strategiczna:** czy sponsor to potencjalny partner lub klient Jarvo.

---

## Plan zwycięstwa (checklista dla agenta Hacker)

### Faza 0: kwalifikacja (przed rejestracją)

- [ ] Przeczytać pełny regulamin (Official Rules), nie tylko stronę główną; zapisać cytaty kluczowych zasad.
- [ ] Kraj właściciela (Polska) nie jest wykluczony; właściciel spełnia wiek, status (student/nie), typ uczestnika (osoba/firma).
- [ ] Reguła AI: zakwalifikować do grupy „ujawnij” / „nie całość” / „zakaz”. Przy „zakaz” lub „przeważnie AI = DQ”: **odrzucić**.
- [ ] Reguła kodu wcześniejszego: „tylko nowe” czy „znacząco zaktualizowane”.
- [ ] Wymagania wideo: długość, język, czy dozwolony TTS, czy wymagana nazwa hackathonu na początku.
- [ ] Limit nagród na projekt i limit tracków.
- [ ] Wymóg obecności, live demo, rozmowy z sędziami.
- [ ] Forma i podatek nagrody (W-8BEN, USDC, przelew); oznaczyć do weryfikacji z księgowym.
- [ ] Policzyć EV (sekcja 7) i zapisać decyzję z uzasadnieniem do akceptacji przez właściciela.

### Faza 1: rozpoznanie (pierwsze 5% czasu)

- [ ] Zbudować macierz rubryki: kryterium, waga, jaki dowód pokażemy, gdzie (wideo, README, demo).
- [ ] Lista sponsorów i tracków z kwotami, wymaganiami kwalifikacyjnymi i liczbą nagród.
- [ ] Analiza poprzednich zwycięzców tego organizatora i sponsorów (galerie Devpost, ETHGlobal Showcase, posty z wynikami).
- [ ] Profil sędziów: kim są, co budują, co nagradzali.
- [ ] Szacunek konkurencji na track (galeria, Discord, liczba rejestracji).
- [ ] Pytania do organizatorów zadać w oficjalnym kanale, zanim zacznie się budowa.

### Faza 2: pomysł (do 10% czasu, potem zamrozić)

- [ ] Jeden konkretny użytkownik i problem w jednym zdaniu, najlepiej z doświadczenia właściciela lub danych z researchu, nie „z pierwszej odpowiedzi modelu”.
- [ ] Odpowiedź „tak” na pytanie: czy sponsor dobrze wypadnie, nagradzając ten projekt?
- [ ] Jeden główny track + maks. 2 lub 3 poboczne z naturalną integracją; sprawdzić nagrody pulowe.
- [ ] Zdefiniowany „moment wow” do demo, który na pewno będzie działał naprawdę.
- [ ] Kill-test: czy rdzeń da się pokazać po 25% czasu? Jeśli nie, zawęzić.
- [ ] właściciel zatwierdza pomysł i zapisuje własne uzasadnienie (dowód znaczącego wkładu człowieka).

### Faza 3: budowa

- [ ] Nowe publiczne repo po starcie wydarzenia; starter kity tylko publiczne i opisane.
- [ ] Commity regularnie (co najmniej kilka dziennie), opisowe; żadnego jednego wielkiego commita.
- [ ] Dziennik użycia AI na bieżąco (narzędzie, plik, cel); specyfikacje i prompty w repo, jeśli wymaga tego regulamin.
- [ ] Rdzeń end-to-end najpierw; bez logowania, ustawień, onboardingu, dopóki rdzeń nie działa.
- [ ] Własny wygląd (nie domyślny szablon AI), realistyczne dane demo.
- [ ] Deploy wcześnie; test z innego urządzenia (telefony floty, desktop); konto testowe dla sędziów.
- [ ] Zawsze działająca kopia demo; zmiany na osobnej gałęzi.
- [ ] Integracje sponsorów głębokie i widoczne w kodzie.

### Faza 4: zgłoszenie (ostatnie 20 do 25% czasu)

- [ ] Szkic opisu w formularzu zgłoszenia już w połowie czasu; służy jako scenariusz wideo.
- [ ] Scenariusz wideo pod limit, odczytany na głos i zmierzony; aplikacja na ekranie przed 10. sekundą.
- [ ] Wersja „jedno ujęcie” nagrana zaraz po działaniu rdzenia i wgrana; potem wersja finalna.
- [ ] Narracja głosem właściciela tam, gdzie TTS jest zabroniony (ETHGlobal); w pozostałych dozwolony TTS po sprawdzeniu.
- [ ] README według szablonu z sekcji 4.3 (w tym: użycie AI, kod wcześniejszy, integracje sponsorów, ograniczenia).
- [ ] Opis projektu: każde kryterium rubryki pokryte; liczby; brak przesadnych deklaracji, każde twierdzenie ma pokrycie w kodzie.
- [ ] Ocenić projekt macierzą rubryki; poprawić najsłabsze kryterium o najwyższej wadze.
- [ ] Wysłać zgłoszenie **co najmniej 12 h przed terminem** (przy 48 h: 3 do 4 h), potem tylko poprawki.
- [ ] Sprawdzić wszystkie linki w oknie prywatnym bez logowania; repo i wideo publiczne.
- [ ] Wybrać nagrody partnerów i opisać integrację z każdym.

### Faza 5: po zgłoszeniu

- [ ] Przygotować odpowiedzi na pytania sędziów (inspiracja, wybór narzędzi, rozwiązane problemy, rola AI i człowieka).
- [ ] Brakujące funkcje przedstawiać jako świadome decyzje zakresu, bez kłamstw.
- [ ] Nie zmieniać kodu po terminie poza drobnymi poprawkami, jeśli regulamin pozwala.
- [ ] Repo i wideo zostają publiczne.
- [ ] Przy wygranej: dokumenty podatkowe, portfel, termin odpowiedzi na powiadomienie (np. 2 dni w Gemini 3).
- [ ] Retrospektywa: wynik, feedback, koszty rzeczywiste kontra EV; aktualizacja mnożników $q$.

### Budżety czasu

| Etap | Hackathon 48 h | Hackathon online 30 dni |
|---|---|---|
| Kwalifikacja i rozpoznanie | 2 h | 2 dni |
| Pomysł (zamrożenie) | do 6 h | do 4 dni |
| Rdzeń end-to-end | do 24 h | do 12 dni |
| Szlif ścieżki demo, deploy | 24 do 36 h | 12 do 22 dni (w tym realni użytkownicy, jeśli się da) |
| Wideo, README, opis | 36 do 44 h | 22 do 27 dni |
| Zgłoszenie i bufor | 44 do 48 h | 27 do 30 dni |

(Na podstawie planu 72 h Starfield Labs [S13] i rady Devpost o zostawieniu 2 do 3 h na nagranie i upload [S3]; proporcje dla 30 dni to [INFERENCJA].)

---

## Źródła

Data dostępu do wszystkich: 2026-11-25. „b.d.” = brak daty na stronie.

| Nr | Źródło | URL | Data publikacji | Status |
|---|---|---|---|---|
| S1 | MLH, Standard Hackathon Rules (w tym AI Tools and Code Gen, Digital Event Submission Rules, Judging Criteria) | https://github.com/MLH/mlh-policies/blob/main/standard-hackathon-rules.md | b.d. (wersja z main) | [P] |
| S2 | Devpost, „How to win a hackathon: Advice from 5 seasoned judges” (S. Sitzer) | https://info.devpost.com/blog/hackathon-judging-tips | b.d. | [P] |
| S3 | Devpost, „How to make a winning hackathon demo video” (D. Calixte) | https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video | b.d., treść z 2026 (wyniki Build with Gemini XPRIZE) | [P] |
| S4 | Devpost, „She almost didn't submit, then won $100,000 at the Build with Gemini XPRIZE” (MyFixam) | https://info.devpost.com/blog/hackathon-winning-project-myfixam | ok. XI 2026 (wywiad „pod koniec października”) | [P] |
| S5 | Devpost, „6 Benefits of submitting your hackathon project early” | https://info.devpost.com/blog/6-reasons-to-submit-your-hackathon-project-early | b.d. | [P] |
| S6 | Devpost for Teams Help Center, „How judging works” | https://help.devpost.team/article/231-how-judging-works | ok. IX 2026 | [W] |
| S7 | Devpost, regulaminy Kiroween 2026 i Reddit Fun and Games (New Projects Only / New & Existing) | https://kiroween.devpost.com/rules , https://redditfunandgames.devpost.com/rules | 2026 | [W] |
| S8 | Devpost, Gemini 3 Hackathon Official Rules (Stage One/Two, wagi, 1 nagroda, wykluczone kraje, New Projects Only) | https://gemini3.devpost.com/rules | XII 2025 (konkurs do III 2026) | [P] |
| S9 | Devpost, regulaminy: Codegeist 2026, Hack Reddit 2025, DIF Hackathon, OpenAI Build Week, World's Largest Hackathon (limity nagród) | https://codegeist2026.devpost.com/rules , https://hackreddit.devpost.com/rules , https://difhackathon.devpost.com/rules , https://openai.devpost.com/rules , https://worldslargesthackathon.devpost.com/rules | 2025 do 2026 | [W] |
| S10 | ETHGlobal Tokyo 2026, Info/Details (zasady, AI, partnerzy, kryteria, wideo) | https://ethglobal.com/events/tokyo2026/info/details | IX 2026 | [P] |
| S11 | ETHGlobal HackMoney, Info/Details (dwie rundy przy async, top ok. 20%) | https://ethglobal.com/events/hackmoney/info/details | b.d. | [W] |
| S12 | ETHGlobal New York 2026 Prizes i HackMoney 2026 Prizes (pula ENS do 43 zespołów po $140, wymagania tracków) | https://ethglobal.com/events/newyork2026/prizes , https://ethglobal.com/events/hackmoney2026/prizes | 2026 | [P] |
| S13 | Starfield Labs, „How to win an AI hackathon” | https://starfieldlabs.ai/ai-articles/how-to-win-an-ai-hackathon | 2026-11-19 | [P] |
| S14 | Starfield Labs, „Winning hackathon projects: real examples and what judges liked” | https://starfieldlabs.ai/ai-articles/winning-hackathon-projects | 2026-11-23 | [P] |
| S15 | Starfield Labs, strona główna (rebrand lablab, MCP dla agentów) | https://starfieldlabs.ai/ | dostęp 2026-11-25 | [P] |
| S16 | lablab.ai, Llama 3 Hackathon recap (kryteria) i Luma „AI Agents Hackathon with LabLab” (AI team members excluded) | https://lablab.ai/ai-hackathons/llama-3-ai-hackathon , https://luma.com/58kh3j8n | 2024 / b.d. | [W] |
| S17 | Ray Deck, „Lessons from Winning Five Hackathons” | https://sustained.substack.com/p/lessons-from-winning-five-hackathons | 2022-11-21 | [P] |
| S18 | John Kim, „How To Win Hackathons” (Push To Prod) | https://getpushtoprod.substack.com/p/how-to-win-hackathons | 2026-04-06 | [P] |
| S19 | Alex Lebed, „How we got $7250 bounties on ETHDenver” | https://lebed2045.medium.com/list-of-hackathon-tips-how-we-got-7250-bounties-on-ethdenver-b6eb2c9d3e70 | ok. 2019 | [W] |
| S20 | WebZero na X (statystyka 13% i stackowanie) oraz Perky News „Best sponsor prizes at web3 hackathons 2026” | https://x.com/joinwebzero/status/2015760595711090921 , https://perky.news/en/articles/best-sponsor-prizes-web3-hackathons-2026 | ok. I 2026 / 2026 | [NZ] |
| S21 | Brian Clark, „How I won over $150k in Cash, Investments, and Prizes at Hackathons” | https://medium.com/@bclark8923/how-i-won-over-150k-in-cash-investments-and-prizes-at-hackathons-a4b5e6b95fe9 | ok. 2015 | [W] |
| S22 | Temboo Blog, „How to Win a Hackathon” (nagrody sponsorów łatwiejsze niż główna) | https://blog.temboo.com/how-to-win-a-hackathon/ | ok. 2019 | [W] |
| S23 | Sakana AI, „Sakana AI Agent Wins AtCoder Heuristic Contest (First AI to Place 1st)” | https://sakana.ai/ahc058/ | 2026-01-05 | [P] |
| S24 | NVIDIA Technical Blog, „Winning a Kaggle Competition with Generative AI-Assisted Coding” | https://developer.nvidia.com/blog/winning-a-kaggle-competition-with-generative-ai-assisted-coding/ | 2026 (konkurs III 2026) | [W] |
| S25 | Devfolio, „How we built an AI hackathon judge while preserving human taste and judgment” | https://devfolio.co/blog/the-discerning-machine/ | 2026-05-18 | [P] |
| S26 | Chan i in., „MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering” (ICLR 2025) | https://arxiv.org/abs/2410.07095 | 2024-10 | [W] |
| S27 | Microsoft Power Platform Blog, „Meet the Agent Academy Hackathon Winners” | https://devblogs.microsoft.com/powerplatform/agent-academy-hackathon-winners/ | 2026-06-18 | [P] |
| S28 | Jeremy Kintana, „How to win at hackathons!” (pitch ćwiczony całe przedpołudnie) | https://jeremykintana.substack.com/p/how-to-win-at-hackathons | ok. 2025 | [W] |
| S29 | Colosseum, „Announcing Colosseum's Agent Hackathon” | https://blog.colosseum.com/announcing-colosseums-agent-hackathon/ | 2026-02-02 | [P] |
| S30 | Solana Developers na X: zwycięzcy Agent Hackathon (1 634 agentów, 454 projekty) | https://x.com/solana_devs/status/2034675919613235390 | ok. III 2026 | [NZ] |
| S31 | arxhww, „Online hackathons ranked by prize per entrant” | https://github.com/arxhww/online-hackathons-by-prize-per-entrant | aktualizacja 2026-11-03 | [P] |
| S32 | 0xClaw, strona projektu i repo | https://0xclaw-ai.github.io/ | 2026 | [P], deklaracje [NZ] |
| S33 | The Register, „Curl shutters bug bounty program to stop AI slop” | https://www.theregister.com/security/2026/01/21/curl-shutters-bug-bounty-program-to-stop-ai-slop/5063039 | 2026-01-21 | [W] |
| S34 | BleepingComputer, „Curl ending bug bounty program after flood of AI slop reports” i xhack.io „AI for Bug Bounty” (15% do 5%) | https://www.bleepingcomputer.com/news/security/curl-ending-bug-bounty-program-after-flood-of-ai-slop-reports/ , https://xhack.io/blog/ai-for-bug-bounty | 2026-01 / ok. X 2026 | [W] |
| S35 | brabble.ai, „Can You Use AI Coding Tools in a Hackathon? What Real 2026 Rulebooks Say” | https://brabble.ai/blog/ai-coding-tools-allowed-in-hackathons | ok. X 2026 | [P] (fragment) |
| S36 | HackAIthon by Craft Ventures, Rules (40% kodu oryginalnego) | https://hackaithon-by-craft-ventures.devpost.com/rules | b.d. | [P] (fragment) |
| S37 | HackUTD 2025, Rules (AI badane, brak projektów wcześniejszych, jedno wydarzenie) | https://hackutd-2025.devpost.com/rules | 2025 | [P] (fragment) |
| S38 | University of Sydney, Hackathon 2026 T&C of Competition and AI | https://hack-eng.sydney.edu.au/wp-content/uploads/2026/07/Hackathon-2026-TC-of-Competition-and-AI_updated.pdf | VII 2026 | [W] |
| S39 | socia.ae, „How to win your first hackathon in 2026, when AI writes the code” | https://socia.ae/blog/how-to-win-your-first-hackathon | ok. X 2026 | [W] |
| S40 | HackerNoon, „From the Judge's Seat: Standing Out in Hackathons in the Age of AI” oraz bootshell.com o Meta AI Hackathon 2026 (5 367 zgłoszeń) | https://hackernoon.com/from-the-judges-seat-standing-out-in-hackathons-in-the-age-of-ai , https://bootshell.com/meta-ai-hackathon-2026-results-winners-prizes | ok. I 2026 / ok. XI 2026 | [W] |
| S41 | Google Cloud Blog, „The Agent Development Kit Hackathon with Google Cloud: Announcing the winners” (10 400 uczestników, 477 zgłoszeń); Devpost Build With AI: Basics rules (analiza AI w ocenie) | https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights , https://learn-ai-basics.devpost.com/rules | 2025-09-03 / b.d. | [P] (fragment) / [W] |
| S42 | HACKUNIVERSITYWORLDWIDE, starter-hackathon-project (szablon opisu) | https://github.com/HACKUNIVERSITYWORLDWIDE/starter-hackathon-project | b.d. | [W] |
| S43 | RosaCodes2021, Hackathon_README_Template; swapnilchaudhari007, hackathon-submission-kit | https://github.com/RosaCodes2021/Hackathon_README_Template , https://github.com/swapnilchaudhari007/hackathon-submission-kit | b.d. | [W] |
| S44 | Devpost Help Center, „How to Claim Your Hackathon Cash Prize” (W-8BEN) | https://help.devpost.com/article/114-how-to-claim-your-hackathon-cash-prize-winners-only | ok. VIII 2026 | [W] |
| S45 | Kaggle, Google: The Gemma 4 Developer Agent Competition, Rules (AMLT, dane zewnętrzne) i dyskusja „Restrictions on using AI generated code?” | https://www.kaggle.com/competitions/gemma-4-developer-agent/rules , https://www.kaggle.com/general/634432 | 2026 | [W] |
| S46 | HeroX, „Guide: Awarding Your Prize: Tax Information” (30% potrącenia, umowy podatkowe) | https://www.herox.com/help/94-guide-awarding-your-prize-tax-information | b.d. | [W] |
| S47 | Jiang i in., „AIDE: AI-Driven Exploration in the Space of Code”; „AI Research Agents for Machine Learning: Search, Exploration, and Generalization in MLE-bench” | https://arxiv.org/abs/2502.13138 , https://arxiv.org/abs/2507.02554 | 2025-02 / 2025-07 | [W] |
| S48 | Hack the North 2025, Rules (plagiat = dyskwalifikacja) | https://hackthenorth2025.devpost.com/rules | 2025 | [W] |
| S49 | Jatin Maurya, „My Bitter Experience at Hackout 2025” | https://blog.mauryajatin.me/posts/68bd8f2b6d786748eab3d68e | ok. 2025 | [W] (relacja jednej strony) |
| S50 | DEV Community, „How I Built an AI Agent That Earns $500/Month in Open Source Bounties” (nasycenie Algora) | https://dev.to/zeroknowledge0x/how-i-built-an-ai-agent-that-earns-500month-in-open-source-bounties-full-architecture-real-4b2i | ok. VI 2026 | [W] |
| S51 | wal.sh, „Online Hackathons” (wskaźnik zgłoszeń MLH, ekonomia nagród) | https://wal.sh/research/online-hackathons/ | ok. V 2026 | [NZ] |
| S52 | HackathonRadar, Prize Pool Calculator: Web Development | https://www.hackathonradar.com/tools/prize-pool-calculator/web-development | b.d. | [W] |
| S53 | Hacker News, wątek o utrzymywaniu się z bounty | https://news.ycombinator.com/item?id=40725136 | ok. VI 2024 | [W] |
| S54 | Ash-Blanc, hackathon-agent-factory | https://github.com/Ash-Blanc/hackathon-agent-factory | b.d. | [P] |
| S55 | TerexitariusStomp, hackathons-ics | https://github.com/TerexitariusStomp/hackathons-ics | b.d. (aktywne) | [P] |
| S56 | Moltathon; Agentathon (areny dla agentów) | https://www.moltathon.xyz/ , https://agentathon.dev/ | b.d. | [W] |

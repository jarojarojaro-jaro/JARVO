# Flota Jarvo: specyfikacja agentów v1

Pierwsza flota: **Main Judge + 4 agentów**. Każdy agent to osobny profil Hermesa
(osobna dystrybucja w `profiles/<nazwa>/`). Rejestr maszynowy jest w [`fleet.yaml`](../fleet.yaml).

Każdy agent jest budowany według [PROFILE-SPEC.md](PROFILE-SPEC.md) (main prompt, workflowy,
knowledge packi, skrypty, toolbox, granice, evals). Zweryfikowane narzędzia open-source
każdego agenta są w [TOOLBOX.md](TOOLBOX.md), a infrastruktura w [VPS.md](VPS.md).

**Stan: wszystkie sześć profili jest zbudowanych.** Ten dokument to specyfikacja. Implementacja:

| Agent | Main prompt | Workflowy własne | Skille zewnętrzne | Skrypty | Evals |
|---|---|---|---|---|---|
| `tars` | [SOUL](../profiles/tars/SOUL.md) | [10 w `skills/fleet/`](../profiles/tars/skills/fleet) + generowany `roster` | — | patrol, brief, przegląd, raport floty | [12](../evals/tars/scenarios.yaml) |
| `tars-sherlock` | [SOUL](../profiles/tars-sherlock/SOUL.md) | [6 w `skills/sherlock/`](../profiles/tars-sherlock/skills/sherlock) | 15 (Hermes, marketingskills) | search_fanout, extract, sources | [11](../evals/tars-sherlock/scenarios.yaml) |
| `tars-web` | [SOUL](../profiles/tars-web/SOUL.md) | [7 w `skills/web/`](../profiles/tars-web/skills/web) | 30 (web-quality, claude-seo, marketingskills, Anthropic, Hermes) | audit, seo_check, screenshots, a11y, favicons, images, brand_extract | [11](../evals/tars-web/scenarios.yaml) |
| `tars-studio` | [SOUL](../profiles/tars-studio/SOUL.md) | [6 w `skills/studio/`](../profiles/tars-studio/skills/studio) | 21 (marketingskills, Anthropic, Hermes) | render_html, check_media | [11](../evals/tars-studio/scenarios.yaml) |
| `tars-wideo` | [SOUL](../profiles/tars-wideo/SOUL.md) | [13 w `skills/wideo/`](../profiles/tars-wideo/skills/wideo) | 15 (HyperFrames, marketingskills, Hermes) | film, stock, kadry, montaz, napisy, qa_wideo | [12](../evals/tars-wideo/scenarios.yaml) |
| `tars-reka` | [SOUL](../profiles/tars-reka/SOUL.md) | [4 w `skills/reka/`](../profiles/tars-reka/skills/reka) | skill-creator + skille wszystkich snajperów (`external_dirs`) + katalog Hermesa | pack, to_pdf | [11](../evals/tars-reka/scenarios.yaml) |

Mechanika szefa (misje, kolejka decyzji, patrol, sędziowanie): [BOSS.md](BOSS.md).

Legenda przy skillach:
- **[H]**: skill, który już istnieje w Hermesie (`skills/` albo `optional-skills/`) i tylko go instalujemy w profilu,
- **[T]**: skill, który piszemy sami w tym repo.

| Profil | Rola | Typ | Maks. autonomia bez zgody |
|---|---|---|---|
| `tars` | Main Judge: przyjmuje zlecenia, rozdziela, ocenia, raportuje | orkiestrator | A1 (tworzy karty, ocenia) |
| `tars-web` | Web Senior Dev: strony od faviconu po SEO | snajper | A1 (buduje lokalnie; wdrożenie = A2) |
| `tars-sherlock` | Researcher-detektyw: znajduje i weryfikuje | snajper | A0/A1 (czyta, pisze raporty) |
| `tars-studio` | Marketing i kreacja: grafiki, copy, kampanie, social media | snajper | A1 (tworzy; publikacja i reklamy = A2) |
| `tars-wideo` | Wideograf: krótkie filmy, montaż, lektor, napisy, klipy | snajper | A1 (renderuje; publikacja i zakupy = A2) |
| `tars-reka` | Prawa ręka: generalista, który ogarnia wszystko | generalista | A1 (e-maile i akcje zewnętrzne = A2) |

---

## Warstwa wspólna: wiedza o Tobie i Twoich markach

Snajperzy nie dzielą się skillami, ale wszyscy znają **Ciebie**:
- **profil użytkownika**: kim jesteś, czym się zajmujesz, preferencje (MVP: `knowledge/user/USER.md`
  z wywiadu onboardingowego Jarva; później wspólny provider pamięci, np. Honcho),
- **brand kity** w `knowledge/brands/<marka>/`: logo, kolory, fonty, ton komunikacji, `DESIGN.md`.
  Brand kit tworzy `tars-web` albo `tars-studio` („naucz się mojej marki z tej strony”),
  a korzystają z niego obaj. Marka to wiedza o Tobie, nie o dziedzinie, dlatego jest wspólna.

---

## `tars`: Main Judge

**Misja:** jedyny punkt kontaktu do większych zadań. Rozumie, czego chcesz, rozdziela
pracę, sprawdza ją i oddaje Ci gotowy, zweryfikowany wynik.

**Robi:**
- intake: doprecyzowuje cel i kryteria sukcesu, dopytuje tylko o prawdziwe decyzje; przy mglistym dużym celu
  `wywiad` (jedno pytanie naraz z gotowymi odpowiedziami, najwyżej 6, potem brief),
- dispatch: tworzy karty kanbana z celem, kontekstem i **Definition of Done**,
  przypisuje je właściwemu agentowi i łączy zależnościami,
- judge: ocenia każdy wynik według DoD z karty i rubryki danego agenta:
  `complete` albo `request_changes` z konkretnymi uwagami,
- raport: jedno podsumowanie z linkami do wyników, ryzykami i decyzjami do podjęcia.

**Nie robi:** żadnej pracy dziedzinowej. Nie pisze stron, nie robi researchu, nie projektuje grafik.

**Zasady routingu:**
| Zlecenie | Do kogo |
|---|---|
| Strona, landing, SEO, wydajność, favicony, responsywność | `tars-web` |
| „Dowiedz się”, „sprawdź”, porównaj, zweryfikuj | `tars-sherlock` |
| Post, grafika, kampania, copy, content | `tars-studio` |
| Film, reels, short, montaż, napisy, lektor, klipy | `tars-wideo` |
| Szybkie sprawy, sklejanie wyników, prototyp, „ogarnij to”, zadanie bez oczywistego snajpera | `tars-reka` |
| Duże cele (np. „wypuść nowy produkt”) | rozbicie na kilka kart, np. sherlock → web + studio → reka (spięcie) |

**Skille:** [T] `judge-rubryki` (kryteria oceny dla każdego agenta), [T] `dispatch-playbook`
(jak pisać karty z DoD, typowe przepływy), [T] `roster` (generowany z `fleet.yaml`: kto istnieje i co umie),
[T] `raport-dla-szefa` (format raportu końcowego).

**Toolsety:** `kanban` (orkiestrator), `memory`. Bez terminala i bez edycji plików projektów.

---

## `tars-web`: Web Senior Dev

**Misja:** wie o stronach wszystko. Robi nowe strony, ulepsza i usprawnia stare, uczy
się Twojej marki z istniejącej strony i robi strony produktowe pod SEO.

**Zakres wiedzy (knowledge packi w `references/`):**
- **Fundamenty:** semantyczny HTML, nowoczesny CSS, mobile-first, breakpointy, typografia, dark mode.
- **Ikony i meta:** komplet faviconów (`favicon.ico`, SVG, `apple-touch-icon`, ikony do
  manifestu 192/512 i maskable), `site.webmanifest`, meta tagi, Open Graph i karty X/Twitter.
- **SEO techniczne:** title i description, canonical, hreflang, `sitemap.xml`, `robots.txt`,
  dane strukturalne JSON-LD (Product, Organization, FAQ, Breadcrumb…), linkowanie wewnętrzne.
- **Obrazy:** AVIF/WebP, `srcset`/`sizes`, lazy loading, jawne wymiary (bez skoków layoutu), kompresja.
- **Wydajność:** Core Web Vitals (LCP, INP, CLS), budżety wydajności, fonty, krytyczny CSS.
- **Dostępność:** WCAG 2.2 AA, kontrast, nawigacja klawiaturą, alt teksty.
- **Wdrożenie:** GitHub/Cloudflare/Netlify Pages, domeny, analityka.

**Skille:**
- [H] `claude-design`, `popular-web-designs`, `design-md`, `impeccable`, `auteur`, `scrollcraft`, `publish-site`
- [T] `brand-z-url`: podajesz stronę, a agent crawluje ją i wyciąga logo, kolory, fonty,
  ton i komponenty do `knowledge/brands/<marka>/` (z `DESIGN.md`)
- [T] `audyt-strony`: Lighthouse, dostępność (axe), SEO, obrazy i responsywność (zrzuty na kilku
  szerokościach), wynik jako raport z priorytetami
- [T] `nowa-strona`: od briefu do wdrożenia (domyślny stack: Astro dla stron marketingowych)
- [T] `bramka-jakosci`: rubryka designu 10 osi (wynik 0–100, zaliczenie od 90, rundy poprawek) i testy wrogie
  (`hostile.cjs`: wolne łącze, brak JS, 320 px, klawiatura, długie polskie słowa, reduced motion, zasoby zewnętrzne)
- [T] `landing-produktowy`: strona nowego produktu pod SEO (research słów kluczowych od `tars-sherlock`, jeśli trzeba)
- [T] `favicon-i-meta`: generowanie kompletu ikon, manifestu i meta z jednego logo
- [T] `optymalizacja-obrazow`: konwersja i kompresja obrazów, `srcset`

**Narzędzia:** terminal, pliki, przeglądarka (Lightpanda, Chromium do zrzutów), Node.js, a do tego Lighthouse, axe-core,
Playwright, sharp, favicons, dembrandt (wyciąganie brandu), linkinator, html-validate i MCP
`context7`/`netlify`/`cloudflare`. Pełna lista: [TOOLBOX.md](TOOLBOX.md#tars-web-web-senior-dev).

**Rubryka sędziego (DoD):** strona buduje się bez błędów, Lighthouse ≥ 90 we wszystkich
kategoriach (albo uzasadnienie), komplet faviconów i meta, poprawne zrzuty mobile i desktop,
zgodność z brand kitem.

**Nie robi:** researchu rynku, treści marketingowych na social media, grafik promocyjnych.

---

## `tars-sherlock`: Researcher-detektyw

**Misja:** znajdzie wszystko i wszystkiego się dowie. Sprawdza wiele wątków i wiele źródeł,
składa całość i **weryfikuje**, co jest prawdą.

**Metoda Sherlocka (główny skill [T] `metoda-sherlocka`):**
1. Rozbicie pytania na hipotezy i wątki.
2. Równoległe śledztwo: `delegate_task` do subagentów, po jednym na wątek (w obrębie jego profilu).
3. Wiele wyszukiwarek i typów źródeł: strony, dokumenty, fora, YouTube (transkrypcje), publikacje naukowe, rejestry.
4. Dotarcie do **źródeł pierwotnych**, nie do przedruków.
5. Weryfikacja krzyżowa: każde kluczowe twierdzenie potwierdzone przez ≥ 2 niezależne źródła.
6. Ocena wiarygodności źródeł (rzetelność, data, konflikt interesów).
7. Jawne sprzeczności i luki („tego nie udało się potwierdzić”).
8. Raport: wnioski z poziomem pewności, a każde twierdzenie z cytatem i linkiem.

**Skille:**
- [H] `grounded-citations`, `blocked-page-recovery`, `searxng-search`, `duckduckgo-search`,
  `scrapling`, `arxiv`, `youtube-content`, `reddit-reading`, `rss-feeds`,
  `competitor-news-monitor`, `domain-intel`, `osint-investigation`
- [T] `metoda-sherlocka`, [T] `weryfikacja-faktow` (poziomy wiarygodności źródeł), [T] `szybki-fakt` (jedna runda, cytat),
  [T] `raport-sledztwa` (format raportu), [T] `research-seo` (słowa kluczowe i konkurencja, dla `tars-web` i `tars-studio`)

**Narzędzia:** wielu dostawców wyszukiwania naraz (własny SearXNG, Brave, Exa…), trafilatura i Lightpanda (strony z JS do Markdown),
Docling (PDF-y, dodatek obrazu), yt-dlp (transkrypcje), OpenAlex (nauka), ArchiveBox (archiwum dowodów),
delegowanie wątków. Pełna lista: [TOOLBOX.md](TOOLBOX.md#tars-sherlock-researcher-detektyw).

**Rubryka sędziego (DoD):** każde kluczowe twierdzenie ma źródło, podany poziom pewności,
sprzeczności wypisane, daty źródeł podane, jasna odpowiedź na pierwotne pytanie.

**Nie robi:** stron, grafik ani treści promocyjnych. Tylko dowody i wnioski.

**Etyka:** OSINT tylko na firmach, produktach, rynkach i informacjach publicznych. Nie śledzi osób prywatnych.

---

## `tars-studio`: Marketing i kreacja

**Misja:** graphic designer i marketer w jednym. Robi posty, grafiki promocyjne, copy i kampanie,
wie, gdzie co publikować, w jakim formacie i dlaczego. Filmy robi `tars-wideo` (Studio pisze do nich brief).

**Zakres wiedzy (knowledge packi):**
- formaty i wymiary dla każdej platformy (IG, TikTok, YT, LinkedIn, X, FB),
- zasady designu: kompozycja, typografia, kolor, hierarchia, spójność z brand kitem,
- copywriting: hooki, CTA, lejki, kalendarz publikacji,
- strategia: grupy docelowe, pozycjonowanie, kampanie produktowe.

**Warsztat:**
- **grafiki z kodu:** szablony HTML/CSS renderowane do PNG, infografiki,
- **AI:** wtyczka Hermesa `image_gen` z providerem **OpenRouter**,
- **publikacja:** Postiz (self-host) jako kolejka, a post wychodzi dopiero po Twojej akceptacji.
Pełna lista: [TOOLBOX.md](TOOLBOX.md#tars-studio-marketing-i-kreacja).

**Skille:**
- [H] `baoyu-infographic`, `social-media-content-calendar`, `creative-ideation`, `humanizer`, `meme-generation`,
  `excalidraw`, `concept-diagrams`
- [T] `formaty-platform` (specyfikacje i szablony), [T] `grafika-social` (szablony HTML do PNG w brand kicie),
  [T] `pakiet-kampanii` (posty + grafiki + brief wideo + kalendarz), [T] `generacja-ai` (obrazy), [T] `copy-pl`, [T] `publikacja`

**Rubryka sędziego (DoD):** właściwe formaty i wymiary dla platformy, zgodność z brand kitem,
tekst bez „AI-izmów”, pliki gotowe do publikacji, przy kampanii z filmem: brief dla Wideografa.

**Zasada:** **nie publikuje sam.** Przygotowuje pakiet do publikacji, a publikacja wymaga Twojej zgody.

---

## `tars-wideo`: Wideograf

**Misja:** filmy, które ktoś obejrzy do końca: od tematu albo surowego nagrania do gotowego pliku na TikTok, Reels,
Shorts i YouTube. Wydzielony ze Studia, bo wideo to osobny warsztat (rytm, dźwięk, napisy, montaż).

**Tryby pracy:**
- **krótki film z tematu** (pomysł z [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo), własna implementacja):
  scenariusz → ujęcia (stock Pexels/Pixabay, AI, pliki, plansze) → polski lektor Edge TTS (darmowy, z czasem słów)
  → napisy karaoke → muzyka ściszana pod głos → montaż FFmpeg w 9:16/16:9/1:1/4:5, z planu `plan.json` (`film.py`),
- **warianty A/B** z jednego planu (hook, głos, tempo, długość), wspólne sceny z cache,
- **montaż nagrań** użytkownika: cięcie, usuwanie ciszy, kadr 9:16 z poziomego, głośność −14 LUFS, napisy,
- **klipy z długich nagrań** (podcast, webinar): transkrypcja Parakeet z czasem słów → wybór fragmentów → klipy z napisami,
- **filmy z kodu** (HyperFrames, Manim) i **ujęcia z AI** (`video_generate`, obraz → wideo, rejestr kosztów).

**Jakość:** `qa_wideo.py` (kodeki, format, długość, LUFS, czarne i zamrożone klatki, arkusz ze strefami UI 9:16)
+ `kontrola-wideo` (ocena 0–100 w 10 osiach, PASS od 85, najwyżej 2 rundy poprawek). Każde ujęcie oglądane (vision),
źródła i licencje w `film.json`.

**Skille:** [T] `krotki-film`, `scenariusz`, `material-stock`, `dobor-ujec`, `warianty-ab`, `montaz-nagran`,
`klipy-z-dlugiego`, `napisy`, `lektor-i-dzwiek`, `film-z-kodu`, `wideo-ai`, `formaty-wideo`, `kontrola-wideo`;
[H] `hyperframes` (12 skilli rodziny), `manim-video`, `ai-presenter-video`, marketingskills `video`.
Pełna lista narzędzi: [TOOLBOX.md](TOOLBOX.md#tars-wideo-wideograf).

**Zasada:** **nie publikuje sam** i nie kupuje materiałów; bez deepfake'ów i klonowania głosów realnych osób.

---

## `tars-reka`: Prawa ręka

**Misja:** zapierdala i pomaga na każdy możliwy sposób. Ogarnia, rozkminia, proponuje,
robi szybkie rzeczy od ręki, skleja wyniki snajperów i łata dziury, gdzie nie ma specjalisty.

**Czym różni się od Jarva:** Jarvo *zarządza i ocenia*, a prawa ręka *wykonuje*.
Jarvo nie robi pracy, a ręka robi wszystko.

**Czym różni się od snajperów:** ma **dostęp do skilli wszystkich** agentów (tylko do odczytu)
i pełny katalog Hermesa, ale nie ma ich pamięci ani głębi. Do szybkich i przekrojowych
zadań jest idealna. Gdy zadanie wymaga jakości snajpera, sama proponuje oddanie go przez Jarva.

**Typowe zadania:** szybka odpowiedź lub obliczenie, poprawka tekstu, porządki w plikach,
prototyp na szybko, zebranie wyników kilku snajperów w jeden dokument, maile, notatki,
plan dnia, „znajdź sposób, żeby…”.

**Skille:** pełny katalog [H] plus skille snajperów przez `skills.external_dirs`
(w fazie 0 trzeba potwierdzić, że ręka **nie może ich modyfikować**, bo Hermes pozwala
agentowi edytować skille w external_dirs, jeśli ma prawa zapisu) oraz [T] `kiedy-oddac-snajperowi`.

**Rubryka sędziego (DoD):** zadanie wykonane, wynik sprawdzony przez nią samą, jasno powiedziane, czego nie zrobiła.

---

## Kolejność budowy (propozycja)

1. `tars` + `tars-sherlock`: najprostsze narzędzia, dobre do przetestowania pętli sędziego.
2. `tars-web`: najwięcej wiedzy do spisania, najbardziej mierzalne wyniki (Lighthouse).
3. `tars-studio`: wymaga najwięcej narzędzi i kluczy API (OpenRouter, FFmpeg, renderery).
4. `tars-reka`: na końcu, bo korzysta ze skilli pozostałych.

Pierwszy wspólny test floty: **„wypuść landing nowego produktu”**. Sherlock robi research
i słowa kluczowe, web buduje stronę, studio przygotowuje grafiki i posty, ręka składa
wszystko w pakiet, a Jarvo ocenia każdy etap.

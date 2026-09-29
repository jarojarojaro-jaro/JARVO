# Flota Jarvo: specyfikacja agentów v1

Flota: **Main Judge + 6 agentów**. Każdy agent to osobny profil Hermesa
(osobna dystrybucja w `profiles/<nazwa>/`). Rejestr maszynowy jest w [`fleet.yaml`](../fleet.yaml).

Każdy agent jest budowany według [PROFILE-SPEC.md](PROFILE-SPEC.md) (main prompt, workflowy,
knowledge packi, skrypty, toolbox, granice, evals). Zweryfikowane narzędzia open-source
każdego agenta są w [TOOLBOX.md](TOOLBOX.md), a infrastruktura w [VPS.md](VPS.md).

**Stan: wszystkie siedem profili jest zbudowanych.** Ten dokument to specyfikacja. Implementacja:

| Agent | Main prompt | Workflowy własne | Skille zewnętrzne | Skrypty | Evals |
|---|---|---|---|---|---|
| `jarvo` | [SOUL](../profiles/jarvo/SOUL.md) | [11 w `skills/fleet/`](../profiles/jarvo/skills/fleet) + generowany `roster` | 0 | patrol, brief, przegląd, raport floty | [17](../evals/jarvo/scenarios.yaml) |
| `jarvo-sherlock` | [SOUL](../profiles/jarvo-sherlock/SOUL.md) | [7 w `skills/sherlock/`](../profiles/jarvo-sherlock/skills/sherlock) | 15 (Hermes, marketingskills) | search_fanout, extract, sources | [12](../evals/jarvo-sherlock/scenarios.yaml) |
| `jarvo-web` | [SOUL](../profiles/jarvo-web/SOUL.md) | [9 w `skills/web/`](../profiles/jarvo-web/skills/web) | 55 (web-quality, claude-seo, marketingskills, Anthropic, Hermes, impeccable, GSAP, Three.js, motion, Lottie, wspólny `graf-kodu`) | audit, seo_check, screenshots, a11y, favicons, images, brand_extract, hostile, security_check | [12](../evals/jarvo-web/scenarios.yaml) |
| `jarvo-studio` | [SOUL](../profiles/jarvo-studio/SOUL.md) | [6 w `skills/studio/`](../profiles/jarvo-studio/skills/studio) | 23 (marketingskills, Anthropic, Hermes, impeccable) | render_html, check_media | [11](../evals/jarvo-studio/scenarios.yaml) |
| `jarvo-wideo` | [SOUL](../profiles/jarvo-wideo/SOUL.md) | [14 w `skills/wideo/`](../profiles/jarvo-wideo/skills/wideo) | 55 (HyperFrames, GSAP, Three.js, Remotion, iart, screenwriting, marketingskills, Hermes i inne) | film, stock, kadry, montaz, napisy, qa_wideo, rytm, narzedzia, html_wideo, inspiracje, projekt, krytyka, assety, maskotka, lektor_linie (+ wideo_lib) | [19](../evals/jarvo-wideo/scenarios.yaml) |
| `jarvo-ads` | [SOUL](../profiles/jarvo-ads/SOUL.md) | [10 w `skills/ads/`](../profiles/jarvo-ads/skills/ads) | 5 (marketingskills) | ads, planer, eksperyment, eksport | [12](../evals/jarvo-ads/scenarios.yaml) |
| `jarvo-reka` | [SOUL](../profiles/jarvo-reka/SOUL.md) | [4 w `skills/reka/`](../profiles/jarvo-reka/skills/reka) | 2 (skill-creator, `graf-kodu`) + skille Sherlocka, Web i Studio (`external_dirs`, tylko odczyt) + katalog Hermesa | pack, to_pdf | [11](../evals/jarvo-reka/scenarios.yaml) |

Mechanika szefa (misje, kolejka decyzji, patrol, sędziowanie): [BOSS.md](BOSS.md).

Legenda przy skillach:
- **[H]**: skill, który już istnieje w Hermesie (`skills/` albo `optional-skills/`) i tylko go instalujemy w profilu,
- **[T]**: skill, który piszemy sami w tym repo,
- **[Z]**: skill zewnętrzny z innego repo OSS, przypięty do commitu w [`vendor/skills.lock.yaml`](../vendor/skills.lock.yaml).

| Profil | Rola | Typ | Maks. autonomia bez zgody |
|---|---|---|---|
| `jarvo` | Main Judge: przyjmuje zlecenia, rozdziela, ocenia, raportuje | orkiestrator | A1 (tworzy karty, ocenia) |
| `jarvo-web` | Web Senior Dev: strony od faviconu po SEO | snajper | A1 (buduje lokalnie; wdrożenie = A2) |
| `jarvo-sherlock` | Researcher-detektyw: znajduje i weryfikuje | snajper | A1 (czyta, pisze raporty) |
| `jarvo-studio` | Marketing i kreacja: grafiki, copy, kampanie, social media | snajper | A1 (tworzy; publikacja = A2) |
| `jarvo-ads` | Specjalista Ads: Meta Ads i Google Ads, kampanie, testy, raporty | snajper | A1 (szkice PAUSED; wydatek = A2 z kodem Skarbca) |
| `jarvo-wideo` | Wideograf: krótkie filmy, montaż, lektor, napisy, klipy | snajper | A1 (renderuje; publikacja i zakupy = A2) |
| `jarvo-reka` | Prawa ręka: generalista, który ogarnia wszystko | generalista | A1 (e-maile i akcje zewnętrzne = A2) |

---

## Warstwa wspólna: wiedza o Tobie i Twoich markach

Snajperzy nie dzielą pamięci ani workflowów dziedzinowych (wspólne są tylko narzędziowe skille z `shared/skills/`,
np. `graf-kodu`, i te same skille zewnętrzne z locka), ale wszyscy znają **Ciebie**:
- **profil użytkownika**: kim jesteś, czym się zajmujesz, preferencje (MVP: `knowledge/user/USER.md`
  z wywiadu onboardingowego Jarva; później wspólny provider pamięci, np. Honcho),
- **brand kity** w `knowledge/brands/<marka>/`: logo, kolory, fonty, ton komunikacji, `DESIGN.md`.
  Brand kit tworzy `jarvo-web` albo `jarvo-studio` („naucz się mojej marki z tej strony”),
  a korzystają z niego obaj. Marka to wiedza o Tobie, nie o dziedzinie, dlatego jest wspólna.

---

## `jarvo`: Main Judge

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
| Strona, landing, SEO, wydajność, favicony, responsywność | `jarvo-web` |
| „Dowiedz się”, „sprawdź”, porównaj, zweryfikuj | `jarvo-sherlock` |
| Post, grafika, kreacja reklamy, copy, content | `jarvo-studio` |
| Reklama płatna, Meta Ads, Google Ads, budżet, wyniki kampanii | `jarvo-ads` |
| Film, reels, short, montaż, napisy, lektor, klipy | `jarvo-wideo` |
| Szybkie sprawy, sklejanie wyników, prototyp, „ogarnij to”, zadanie bez oczywistego snajpera | `jarvo-reka` |
| Duże cele (np. „wypuść nowy produkt”) | rozbicie na kilka kart, np. sherlock → web + studio → reka (spięcie) |

**Skille:** [T] `intake`, `wywiad`, `dispatch-playbook` (jak pisać karty z DoD, typowe przepływy),
`mission-ledger` (dziennik misji i raport końcowy), `decision-queue`, `sdlc-review` (sędzia; rubryki agentów
`references/rubric-<agent>.md` generowane z ich `quality/rubric.md`), `patrol`, `daily-brief`, `weekly-review`,
`onboarding-interview`, `fleet-improvement`, [T] `roster` (generowany z `fleet.yaml`: kto istnieje i co umie).

**Toolsety:** na Telegramie `kanban`, `memory`, `file`, `web`, `session_search`, `clarify`, `todo`, `skills`, `cronjob`,
bez terminala. Pracownik-sędzia (CLI) ma dodatkowo `terminal`, `browser` i `vision` do weryfikacji wyników.
Pracy dziedzinowej nie wykonuje (zasada SOUL, nie brak narzędzi).

---

## `jarvo-web`: Web Senior Dev

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
- [H] `claude-design`, `popular-web-designs`, `design-md`, `scrollcraft`, `publish-site`, `cloudflare-temporary-deploy`
- [Z] `impeccable`, web-quality-skills (5), claude-seo (13), marketingskills (3), Anthropic (2), GSAP (8), Three.js (10),
  motion Emila Kowalskiego (5), `text-to-lottie`, wspólny `graf-kodu` (`shared/skills/`)
- [T] `brand-z-url`: podajesz stronę, a agent crawluje ją i wyciąga logo, kolory, fonty,
  ton i komponenty do `knowledge/brands/<marka>/` (z `DESIGN.md`)
- [T] `audyt-strony`: Lighthouse, dostępność (axe), SEO, obrazy i responsywność (zrzuty na kilku
  szerokościach), wynik jako raport z priorytetami
- [T] `nowa-strona`: od briefu do wdrożenia (domyślny stack: Astro dla stron marketingowych)
- [T] `bramka-jakosci`: rubryka designu 10 osi (wynik 0–100, zaliczenie od 90, rundy poprawek) i testy wrogie
  (`hostile.cjs`: wolne łącze, brak JS, 320 px, klawiatura, długie polskie słowa, reduced motion, zasoby zewnętrzne)
- [T] `landing-produktowy`: strona nowego produktu pod SEO (research słów kluczowych od `jarvo-sherlock`, jeśli trzeba)
- [T] `favicon-i-meta`: generowanie kompletu ikon, manifestu i meta z jednego logo
- [T] `optymalizacja-obrazow`: konwersja i kompresja obrazów, `srcset`
- [T] `wdrozenie`: podgląd (A1) i wdrożenie produkcyjne (A2, tylko za zgodą)
- [T] `bezpieczenstwo-aplikacji`: skan i przegląd bezpieczeństwa kodu i strony (`security_check.py`)

**Narzędzia:** terminal, pliki, przeglądarka (Lightpanda, Chromium do zrzutów), Node.js, a do tego Lighthouse, axe-core,
Playwright, sharp, favicons, dembrandt (wyciąganie brandu), linkinator, html-validate; MCP `context7`
zaplanowany (jeszcze niewłączony w `config.yaml`). Pełna lista: [TOOLBOX.md](TOOLBOX.md#jarvo-web-web-senior-dev).

**Rubryka sędziego (DoD):** strona buduje się bez błędów, Lighthouse ≥ 90 we wszystkich
kategoriach (albo uzasadnienie), komplet faviconów i meta, poprawne zrzuty mobile i desktop,
zgodność z brand kitem.

**Nie robi:** researchu rynku, treści marketingowych na social media, grafik promocyjnych.

---

## `jarvo-sherlock`: Researcher-detektyw

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
  `blogwatcher`, `competitor-news-monitor`, `domain-intel`, `osint-investigation`
- [Z] marketingskills `competitor-profiling`, `customer-research`
- [T] `metoda-sherlocka`, [T] `weryfikacja-faktow` (poziomy wiarygodności źródeł), [T] `szybki-fakt` (jedna runda, cytat),
  [T] `raport-sledztwa` (format raportu), [T] `research-seo` (słowa kluczowe i konkurencja, dla `jarvo-web` i `jarvo-studio`),
  [T] `research-rynku` (gracze, oferty, ceny, opinie), [T] `monitoring` (rutyna cron zakładana przez Jarva)

**Narzędzia:** wielu dostawców wyszukiwania naraz (własny SearXNG, Brave, Exa…), trafilatura i Lightpanda (strony z JS do Markdown),
Docling (PDF-y, dodatek obrazu), yt-dlp (transkrypcje), OpenAlex (nauka, wtyczka opcjonalna), archiwum dowodów lokalnie
(`sources.py --archive`; ArchiveBox jako opcjonalny sidecar w planach), delegowanie wątków.
Pełna lista: [TOOLBOX.md](TOOLBOX.md#jarvo-sherlock-researcher-detektyw).

**Rubryka sędziego (DoD):** każde kluczowe twierdzenie ma źródło, podany poziom pewności,
sprzeczności wypisane, daty źródeł podane, jasna odpowiedź na pierwotne pytanie.

**Nie robi:** stron, grafik ani treści promocyjnych. Tylko dowody i wnioski.

**Etyka:** OSINT tylko na firmach, produktach, rynkach i informacjach publicznych. Nie śledzi osób prywatnych.

---

## `jarvo-studio`: Marketing i kreacja

**Misja:** graphic designer i marketer w jednym. Robi posty, grafiki promocyjne, copy i kampanie,
wie, gdzie co publikować, w jakim formacie i dlaczego. Filmy robi `jarvo-wideo` (Studio pisze do nich brief).

**Zakres wiedzy (knowledge packi):**
- formaty i wymiary dla każdej platformy (IG, TikTok, YT, LinkedIn, X, FB),
- zasady designu: kompozycja, typografia, kolor, hierarchia, spójność z brand kitem,
- copywriting: hooki, CTA, lejki, kalendarz publikacji,
- strategia: grupy docelowe, pozycjonowanie, kampanie produktowe.

**Warsztat:**
- **grafiki z kodu:** szablony HTML/CSS renderowane do PNG, infografiki,
- **AI:** wtyczka Hermesa `image_gen` z providerem **OpenRouter**,
- **publikacja:** Postiz (self-host) jako kolejka, a post wychodzi dopiero po Twojej akceptacji.
Pełna lista: [TOOLBOX.md](TOOLBOX.md#jarvo-studio-marketing-i-kreacja).

**Skille:**
- [H] `baoyu-infographic`, `social-media-content-calendar`, `creative-ideation`, `humanizer`, `meme-generation`,
  `excalidraw`, `concept-diagrams`
- [Z] marketingskills (12: copywriting, social, launch, ads, ad-creative…), Anthropic (3: `algorithmic-art`,
  `canvas-design`, `theme-factory`), `impeccable`
- [T] `formaty-platform` (specyfikacje i szablony), [T] `grafika-social` (szablony HTML do PNG w brand kicie),
  [T] `pakiet-kampanii` (posty + grafiki + brief wideo + kalendarz), [T] `generacja-ai` (obrazy), [T] `copy-pl`, [T] `publikacja`

**Rubryka sędziego (DoD):** właściwe formaty i wymiary dla platformy, zgodność z brand kitem,
tekst bez „AI-izmów”, pliki gotowe do publikacji, przy kampanii z filmem: brief dla Wideografa.

**Zasada:** **nie publikuje sam.** Przygotowuje pakiet do publikacji, a publikacja wymaga Twojej zgody.

---

## `jarvo-wideo`: Wideograf

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

**Jakość:** `qa_wideo.py` (kodeki, format, długość, LUFS, czarne i zamrożone klatki, pojedyncze „mrugnięcia” klatek, arkusz ze strefami UI 9:16). **Rytm i wzór:** `rytm.py` (BPM, takty, drop pod cięcia), `kadry.py wzor` (film-wzór → klatki co 0,5 s, cięcia, rytm → mapa bitów)
+ `kontrola-wideo` (ocena 0–100 w 10 osiach, PASS od 85, najwyżej 2 rundy poprawek). Każde ujęcie oglądane (vision),
źródła i licencje w `film.json`.

**Skille:** [T] `rodzaje-filmu`, `krotki-film`, `scenariusz`, `material-stock`, `dobor-ujec`, `warianty-ab`, `montaz-nagran`,
`klipy-z-dlugiego`, `napisy`, `lektor-i-dzwiek`, `film-z-kodu`, `wideo-ai`, `formaty-wideo`, `kontrola-wideo`;
[H] `manim-video`, `ai-presenter-video`; [Z] `hyperframes` (12 skilli rodziny), marketingskills `video`, GSAP (8),
Three.js (10), screenwriting (5), iart (5), motion (3), Remotion, motion-broll, lemo-opuscar, anidoodle, claude-animation,
bang-motion, pixel2motion, `text-to-lottie`, `slack-gif-creator` (razem 55).
Pełna lista narzędzi: [TOOLBOX.md](TOOLBOX.md#jarvo-wideo-wideograf).

**Zasada:** **nie publikuje sam** i nie kupuje materiałów; bez deepfake'ów i klonowania głosów realnych osób.

---

## `jarvo-reka`: Prawa ręka

**Misja:** zapierdala i pomaga na każdy możliwy sposób. Ogarnia, rozkminia, proponuje,
robi szybkie rzeczy od ręki, skleja wyniki snajperów i łata dziury, gdzie nie ma specjalisty.

**Czym różni się od Jarva:** Jarvo *zarządza i ocenia*, a prawa ręka *wykonuje*.
Jarvo nie robi pracy, a ręka robi wszystko.

**Czym różni się od snajperów:** ma **dostęp do skilli Sherlocka, Web i Studio** (tylko do odczytu;
skille Wideografa i Ads jeszcze nie są podpięte) i pełny katalog Hermesa, ale nie ma ich pamięci ani głębi.
Do szybkich i przekrojowych zadań jest idealna. Gdy zadanie wymaga jakości snajpera, sama proponuje oddanie go przez Jarva.

**Typowe zadania:** szybka odpowiedź lub obliczenie, poprawka tekstu, porządki w plikach,
prototyp na szybko, zebranie wyników kilku snajperów w jeden dokument, maile, notatki,
plan dnia, „znajdź sposób, żeby…”.

**Skille:** pełny katalog [H], skille Sherlocka, Web i Studio przez `skills.external_dirs` (build zamontowany
w kontenerze tylko do odczytu, `:ro`, więc ręka nie może ich modyfikować), [Z] `skill-creator`, `graf-kodu`
oraz [T] `zlozenie-pakietu`, `dokumenty`, `szybki-prototyp`, `kiedy-oddac-snajperowi`.

**Rubryka sędziego (DoD):** zadanie wykonane, wynik sprawdzony przez nią samą, jasno powiedziane, czego nie zrobiła.

---

## `jarvo-ads`: Specjalista Ads

Meta Ads i Google Ads od planu kampanii po raport: stawianie kampanii, codzienna kontrola konta, testy A/B/C,
optymalizacja w zatwierdzonej kopercie budżetu,
wnioski dla Studia i Wideografa. Pieniędzy pilnuje **Skarbiec**, osobny kontener z tokenem Meta, polityką
i kodami zgody, więc agent nie może wydać złotówki bez Ciebie. Pełny projekt: [ADS.md](ADS.md).

---

## Kolejność budowy (historycznie, faza 1)

1. `jarvo` + `jarvo-sherlock`: najprostsze narzędzia, dobre do przetestowania pętli sędziego.
2. `jarvo-web`: najwięcej wiedzy do spisania, najbardziej mierzalne wyniki (Lighthouse).
3. `jarvo-studio`: wymaga najwięcej narzędzi i kluczy API (OpenRouter, FFmpeg, renderery).
4. `jarvo-reka`: na końcu, bo korzysta ze skilli pozostałych.
5. `jarvo-wideo`: wydzielony później ze Studia (wideo to osobny warsztat).
6. `jarvo-ads`: dołączony bez kluczy; Skarbiec (sejf tokenów) jeszcze do zbudowania ([ADS.md](ADS.md)).

Pierwszy wspólny test floty: **„wypuść landing nowego produktu”**. Sherlock robi research
i słowa kluczowe, web buduje stronę, studio przygotowuje grafiki i posty, ręka składa
wszystko w pakiet, a Jarvo ocenia każdy etap.

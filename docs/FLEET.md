# Flota Jarvo: specyfikacja agentów v1

Flota: **Main Judge + 8 agentów**. Każdy agent to osobny profil Hermesa
(osobna dystrybucja w `profiles/<nazwa>/`). Rejestr maszynowy jest w [`fleet.yaml`](../fleet.yaml).

Każdy agent jest budowany według [PROFILE-SPEC.md](PROFILE-SPEC.md) (main prompt, workflowy,
knowledge packi, skrypty, toolbox, granice, evals). Zweryfikowane narzędzia open-source
każdego agenta są w [TOOLBOX.md](TOOLBOX.md), a infrastruktura w [VPS.md](VPS.md).

**Stan: wszystkie dziewięć profili jest zbudowanych.** Ten dokument to specyfikacja. Implementacja:

| Agent | Main prompt | Workflowy własne | Skille zewnętrzne | Skrypty | Evals |
|---|---|---|---|---|---|
| `jarvo` | [SOUL](../profiles/jarvo/SOUL.md) | [12 w `skills/fleet/`](../profiles/jarvo/skills/fleet) + generowany `roster` | 1 (`writing-for-agents`, mattpocock) | patrol, brief, przegląd, raport floty, liczby floty, świeżość, linter kontraktu, prosty polski | [22](../evals/jarvo/scenarios.yaml) |
| `jarvo-sherlock` | [SOUL](../profiles/jarvo-sherlock/SOUL.md) | [7 w `skills/sherlock/`](../profiles/jarvo-sherlock/skills/sherlock) | 16 (Hermes, marketingskills, wspólny `transkrypcja-filmu`) | search_fanout, extract, sources | [13](../evals/jarvo-sherlock/scenarios.yaml) |
| `jarvo-web` | [SOUL](../profiles/jarvo-web/SOUL.md) | [9 w `skills/web/`](../profiles/jarvo-web/skills/web) | 58 (web-quality, claude-seo, marketingskills, Anthropic, Hermes, getsentry, Trail of Bits, impeccable, GSAP, Three.js, motion, Lottie, wspólny `graf-kodu`) | audit, seo_check, screenshots, a11y, favicons, images, brand_extract, hostile, security_check | [16](../evals/jarvo-web/scenarios.yaml) |
| `jarvo-studio` | [SOUL](../profiles/jarvo-studio/SOUL.md) | [6 w `skills/studio/`](../profiles/jarvo-studio/skills/studio) | 23 (marketingskills, Anthropic, Hermes, impeccable, wspólny `hooki`) | render_html, check_media | [12](../evals/jarvo-studio/scenarios.yaml) |
| `jarvo-wideo` | [SOUL](../profiles/jarvo-wideo/SOUL.md) | [15 w `skills/wideo/`](../profiles/jarvo-wideo/skills/wideo) | 59 (HyperFrames, GSAP, Three.js, Remotion, remocn, iart, screenwriting, marketingskills, Hermes, wspólne `transkrypcja-filmu`, `hooki` i inne) | film, stock, kadry, montaz, napisy, qa_wideo, rytm, narzedzia, html_wideo, pomiar, inspiracje, projekt, krytyka, assety, maskotka, lektor_linie, retime, klipy, demo_strony (+ wideo_lib) | [26](../evals/jarvo-wideo/scenarios.yaml) |
| `jarvo-ads` | [SOUL](../profiles/jarvo-ads/SOUL.md) | [10 w `skills/ads/`](../profiles/jarvo-ads/skills/ads) | 6 (marketingskills, wspólny `hooki`) | ads, planer, eksperyment, eksport | [13](../evals/jarvo-ads/scenarios.yaml) |
| `jarvo-lowca` | [SOUL](../profiles/jarvo-lowca/SOUL.md) | [6 w `skills/lowca/`](../profiles/jarvo-lowca/skills/lowca) | 0 | krs, przetargi, strona, leady | [13](../evals/jarvo-lowca/scenarios.yaml) |
| `jarvo-mobile` | [SOUL](../profiles/jarvo-mobile/SOUL.md) | [10 w `skills/mobile/`](../profiles/jarvo-mobile/skills/mobile) | 20 (Expo, React Native, ASO; `vendor/skills.lock.yaml`) | audyt_mobilny, decyzja, zgodnosc, aplikacja, ikony, zrzuty, wrogie, urzadzenie, ios_ci, bramka, sklep_check, pakiet, kadry, wydanie, odrzucenie, ze_strony, utrzymanie, paczki (+ mobile_lib, szablon `expo-jarvo`, workflow iOS) | [34](../evals/jarvo-mobile/scenarios.yaml) |
| `jarvo-reka` | [SOUL](../profiles/jarvo-reka/SOUL.md) | [4 w `skills/reka/`](../profiles/jarvo-reka/skills/reka) | 4 (skill-creator, `writing-for-agents`, `graf-kodu`, `transkrypcja-filmu`) + skille wszystkich snajperów (`external_dirs`, tylko odczyt) + katalog Hermesa | pack, to_pdf | [12](../evals/jarvo-reka/scenarios.yaml) |

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
| `jarvo-lowca` | Łowca leadów: firmy z sygnałem zakupowym i opublikowanym kontaktem | snajper | A1 (szuka i ocenia; wysyłka = decyzja człowieka) |
| `jarvo-mobile` | Twórca aplikacji: natywna czy PWA, audyt mobilny, aplikacje Expo do sklepów | snajper | A1 (audyty i rekomendacje; konta sklepów i wysyłka = A2) |
| `jarvo-reka` | Prawa ręka: generalista, który ogarnia wszystko | generalista | A1 (e-maile i akcje zewnętrzne = A2) |

---

## Warstwa wspólna: wiedza o Tobie i Twoich markach

Snajperzy nie dzielą pamięci ani workflowów dziedzinowych (wspólne są tylko skille z `shared/skills/`:
narzędziowe jak `graf-kodu` i metodyczne jak `hooki`, oraz te same skille zewnętrzne z locka), ale wszyscy znają **Ciebie**:
- **profil użytkownika**: kim jesteś, czym się zajmujesz, preferencje (MVP: `knowledge/user/USER.md`
  z wywiadu onboardingowego Jarva; później wspólny provider pamięci, np. Honcho),
- **brand kity** w `knowledge/brands/<marka>/`: logo, kolory, fonty, ton komunikacji, `DESIGN.md`.
  Brand kit tworzy `jarvo-web` albo `jarvo-studio` („naucz się mojej marki z tej strony”),
  a korzystają z niego obaj. Marka to wiedza o Tobie, nie o dziedzinie, dlatego jest wspólna,
- **skarbiec wiedzy** (`knowledge/`, projekt: [WIEDZA.md](WIEDZA.md)): notatki z linkami o Tobie, markach, projektach,
  agentach i narzędziach, orzeczenia z Twoich korekt, wyciągi z rozmów i kart. Wtyczka `jarvo-wiedza` (dostawca pamięci
  Hermesa u każdego agenta) daje przypomnienia przed turą i narzędzia `wiedza_szukaj`, `wiedza_czytaj`, `wiedza_zapisz`,
  `wiedza_orzeczenie`; agenci zgłaszają szkice, notatki pisze kompilacja.

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
| Leady, nowi klienci, „komu sprzedać”, przetargi do wzięcia, nowe firmy w branży, kontakt do firm | `jarvo-lowca` |
| Aplikacja mobilna, „czy potrzebujemy aplikacji”, PWA czy natywna, audyt aplikacji w App Store i Google Play, aplikacja z naszej strony, aktualizacja albo poprawka aplikacji w sklepie | `jarvo-mobile` |
| Szybkie sprawy, sklejanie wyników, prototyp, „ogarnij to”, zadanie bez oczywistego snajpera | `jarvo-reka` |
| Duże cele (np. „wypuść nowy produkt”) | rozbicie na kilka kart, np. sherlock → web + studio → reka (spięcie) |

**Skille:** [T] `intake`, `wywiad`, `dispatch-playbook` (jak pisać karty z DoD, typowe przepływy),
`mission-ledger` (dziennik misji i raport końcowy), `decision-queue`, `sdlc-review` (sędzia; rubryki agentów
`references/rubric-<agent>.md` generowane z ich `quality/rubric.md`), `patrol`, `daily-brief`, `weekly-review`,
`onboarding-interview`, `fleet-improvement`, [T] `roster` (generowany z `fleet.yaml`: kto istnieje i co umie);
[Z] `writing-for-agents` (mattpocock/skills: warsztat pisania SOUL i skilli, dla `fleet-improvement`).

**Toolsety:** na Telegramie `kanban`, `memory`, `file`, `web`, `session_search`, `clarify`, `todo`, `skills`, `cronjob`,
bez terminala; w czacie HQ (`api_server`) to samo bez `clarify`. Pracownik-sędzia (CLI) ma dodatkowo `terminal`, `browser` i `vision` do weryfikacji wyników.
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
- [H] `claude-design`, `popular-web-designs`, `design-md`, `scrollcraft`, `publish-site`, `cloudflare-temporary-deploy`,
  `systematic-debugging` (przyczyna błędu builda albo skryptu, zanim poprawka)
- [Z] `impeccable`, web-quality-skills (5), claude-seo (13), marketingskills (3), Anthropic (2), GSAP (8), Three.js (10),
  motion Emila Kowalskiego (5), `text-to-lottie`, wspólny `graf-kodu` (`shared/skills/`), getsentry `security-review`
  (przegląd kodu wg OWASP), Trail of Bits `supply-chain-risk-auditor` (ryzyko zależności)
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
- [T] `bezpieczenstwo-aplikacji`: skan kodu, strony i zależności, próby na podglądzie (`security_check.py repo|url|atak`),
  lista 26 punktów (w tym funkcje AI, sesje, CSRF, kopie zapasowe), przegląd kodu

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
- [Z] marketingskills `competitor-profiling`, `customer-research`; wspólny `transkrypcja-filmu` (`shared/skills/`):
  link albo plik filmu → tekst mowy (napisy platformy albo Parakeet), bez analizy obrazu
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
  `canvas-design`, `theme-factory`), `impeccable`; wspólny `hooki` (`shared/skills/`: trzy warstwy hooka, 18 taktyk)
- [T] `formaty-platform` (specyfikacje i szablony), [T] `grafika-social` (szablony HTML do PNG w brand kicie),
  [T] `pakiet-kampanii` (posty + grafiki + brief wideo + kalendarz), [T] `generacja-ai` (obrazy), [T] `copy-pl` (+ sito AI-izmów), [T] `publikacja`

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
`clipmaker`, `demo-strony`, `napisy`, `lektor-i-dzwiek`, `film-z-kodu`, `wideo-ai`, `formaty-wideo`, `kontrola-wideo`;
[H] `manim-video`, `ai-presenter-video`; [Z] `hyperframes` (12 skilli rodziny), marketingskills `video`, GSAP (8),
Three.js (10), screenwriting (5), iart (5), motion (3), Remotion, motion-broll, lemo-opuscar, anidoodle, claude-animation,
bang-motion, pixel2motion, `text-to-lottie`, `slack-gif-creator`, `motion-design` i `video-lessons` (Remocn Studio),
wspólne `transkrypcja-filmu` i `hooki` (razem 59).
Pełna lista narzędzi: [TOOLBOX.md](TOOLBOX.md#jarvo-wideo-wideograf).

**Zasada:** **nie publikuje sam** i nie kupuje materiałów; bez deepfake'ów i klonowania głosów realnych osób.

---

## `jarvo-reka`: Prawa ręka

**Misja:** zapierdala i pomaga na każdy możliwy sposób. Ogarnia, rozkminia, proponuje,
robi szybkie rzeczy od ręki, skleja wyniki snajperów i łata dziury, gdzie nie ma specjalisty.

**Czym różni się od Jarva:** Jarvo *zarządza i ocenia*, a prawa ręka *wykonuje*.
Jarvo nie robi pracy, a ręka robi wszystko.

**Czym różni się od snajperów:** ma **dostęp do skilli wszystkich snajperów** (tylko do odczytu; walidator
pilnuje, żeby nowy snajper też tu trafił) i pełny katalog Hermesa, ale nie ma ich pamięci ani głębi.
Do szybkich i przekrojowych zadań jest idealna. Gdy zadanie wymaga jakości snajpera, sama proponuje oddanie go przez Jarva.

**Typowe zadania:** szybka odpowiedź lub obliczenie, poprawka tekstu, porządki w plikach,
prototyp na szybko, zebranie wyników kilku snajperów w jeden dokument, maile, notatki,
plan dnia, „znajdź sposób, żeby…”.

**Skille:** pełny katalog [H], skille wszystkich snajperów przez `skills.external_dirs` (build zamontowany
w kontenerze tylko do odczytu, `:ro`, więc ręka nie może ich modyfikować), [Z] `skill-creator`, `writing-for-agents`, `graf-kodu`,
`transkrypcja-filmu` oraz [T] `zlozenie-pakietu`, `dokumenty`, `szybki-prototyp`, `kiedy-oddac-snajperowi` (tabela
„komu oddać” generowana z pól `oddaj_gdy` w `fleet.yaml`, więc każdy nowy specjalista trafia do niej sam).

**Rubryka sędziego (DoD):** zadanie wykonane, wynik sprawdzony przez nią samą, jasno powiedziane, czego nie zrobiła.

---

## `jarvo-ads`: Specjalista Ads

Meta Ads i Google Ads od planu kampanii po raport: stawianie kampanii, codzienna kontrola konta, testy A/B/C,
optymalizacja w zatwierdzonej kopercie budżetu,
wnioski dla Studia i Wideografa. Pieniędzy pilnuje **Skarbiec**, osobny kontener z tokenem Meta, polityką
i kodami zgody, więc agent nie może wydać złotówki bez Ciebie. Pełny projekt: [ADS.md](ADS.md). Skarbca jeszcze nie ma,
więc `podlacz-konto`, `start-kampanii` i `optymalizacja` (`wymaga: [skarbiec]`) nie trafiają do profilu; działa plan,
test, audyt i raport z eksportu CSV.

---

## `jarvo-lowca`: Łowca leadów

Szuka firm, dla których teraz jest dobry moment na rozmowę: nowe spółki w KRS (PKD i region z profilu klienta),
przetargi w BZP i TED (zamawiający kupuje to, co sprzedajesz; zwycięzca potrzebuje wykonawców), oferty pracy,
technologia i zmiany na stronach firm, newsy. Oddaje ranking z „dlaczego teraz”, źródłem sygnału i kontaktem, który
firma sama opublikowała; monitoring pokazuje tylko nowe firmy. Tylko źródła oficjalne i publiczne, bez LinkedIna
i baz kupionych, niczego nie wysyła. Pełny projekt: [LEADY.md](LEADY.md).

**Skille:** [T] `profil-klienta`, `sygnaly` (+ tabela źródeł i przepisów), `kwalifikacja`, `kontakt-firmy`,
`lista-leadow`, `monitoring-leadow`. Skrypty: `krs.py`, `przetargi.py`, `strona.py`, `leady.py`.

---

## `jarvo-mobile`: Twórca aplikacji

Mówi uczciwie, czy firmie potrzebna aplikacja: potrzeby właściciela (`potrzeby.yaml`) → strona, PWA, karta w Wallet,
gotowa platforma albo aplikacja w App Store i Google Play, z kosztami licencji, ryzykiem odrzucenia (Apple 4.2) i
następnym krokiem. Robi darmowy audyt mobilny dowolnej firmy z danych publicznych: aplikacje w sklepach (świeżość,
docelowe API Androida, oceny, polska karta, etykiety prywatności, Data safety, status przedsiębiorcy DSA), opinie
z App Store z tematami skarg, linki strona → aplikacja (`apple-app-site-association` z kopią w CDN Apple,
`assetlinks.json`), baner, odznaki, PWA; aplikacje partnerów (Pyszne, Uber Eats) oddziela od aplikacji firmy.
Buduje aplikacje Expo (SDK 57, React Native, TypeScript) z szablonu JARVO, który od pierwszego dnia ma elementy
wymagane przez sklepy (prywatność, kontakt, usuwanie konta, stany ekranów, brak sieci): plan i profil zgodności
(`zgodnosc.py`: logowanie, płatności, treści, AI, uprawnienia z polskim powodem → wymagania z numerami wytycznych),
paleta z koloru marki z kontrastem WCAG AA, ikony, kontrole (typy, lint, wersje SDK, expo-doctor, zasady JARVO),
podgląd w HQ ze zrzutami iPhone i Pixel w obu motywach oraz w Expo Go na telefonie właściciela (EAS Update, token
robota jego organizacji). Testuje na telefonie testowym floty (`jarvo android on`: emulator Google przy KVM albo
Redroid; ekran dla właściciela w HQ, przycisk 📱) i w symulatorze iOS w GitHub Actions. Przed sklepami składa pakiet
(karta pl-PL, grafiki, zrzuty w wymiarach sklepów bez alfy) i przepuszcza go przez `sklep_check.py`: 44 punkty
z dowodem i numerem wytycznej, błąd automatyczny blokuje wysłanie. Konta Apple, Google i Expo zawsze właściciela.
Wydanie robi za dosłowną zgodą właściciela (build, TestFlight, testy Google, karta), do recenzji wysyła właściciel;
odrzucenie zamienia w poprawkę, wyjaśnienie albo odwołanie i w nową kontrolę listy. Ze strony firmy robi plan aplikacji
(dane, oferta, funkcje natywne ponad stronę; mniej niż 3 z mocnym sygnałem = ryzyko Apple 4.2), a po wydaniu pilnuje
terminów sklepów, opinii i Expo SDK i wypuszcza poprawki JS przez EAS Update tylko za zgodą i tylko do zgodnego buildu.
Każdą nową paczkę npm sprawdza przed instalacją (literówki, podszycia, nazwy zmyślone). Pełny projekt: [MOBILE.md](MOBILE.md).

**Skille:** [T] `audyt-mobilny` (+ kryteria kontroli), `natywna-czy-pwa` (+ macierz decyzji), `nowa-aplikacja`
(+ szablon planu, zasady ekranów), `podglad-aplikacji` (+ konfiguracja Expo Go), `bramka-aplikacji` (+ rubryka 10 osi,
werdykt, testy wrogie w przeglądarce, na Androidzie przez adb i w symulatorze iOS w GitHub Actions),
`pakiet-do-sklepow` (+ metadane i limity, potok zrzutów, mapa 44 punktów), [A2] `wydanie` (+ konta właściciela),
[T] `odrzucenie` (+ mapa odrzuceń), `aplikacja-ze-strony` (+ funkcje natywne i opisy dla recenzenta),
[A2] `utrzymanie-aplikacji` (+ opinie w sklepach); 20 skilli zewnętrznych (Expo, Callstack, Vercel, ASO). Skrypty: `audyt_mobilny.py`, `decyzja.py`, `zgodnosc.py`, `aplikacja.py`,
`ikony.cjs`, `zrzuty.cjs`, `wrogie.cjs`, `urzadzenie.py`, `ios_ci.py`, `bramka.py`, `sklep_check.py` (44 punkty przed
wysłaniem i wyuczone z odrzuceń), `pakiet.py` (szkic karty, grafiki, zrzuty), `kadry.cjs`, `wydanie.py` (EAS Build,
Submit i Metadata za zgodą), `odrzucenie.py` (wytyczne, odpowiedź, nauka), `ze_strony.py` (strona firmy → plan i szkice konfiguracji), `utrzymanie.py`
(stan, kalendarz terminów, EAS Update za zgodą, plan SDK), `paczki.py` (paczki npm przed instalacją); szablony `templates/expo-jarvo/`
i `templates/ci/jarvo-ios.yml`.

---

## Kolejność budowy (historycznie, faza 1)

1. `jarvo` + `jarvo-sherlock`: najprostsze narzędzia, dobre do przetestowania pętli sędziego.
2. `jarvo-web`: najwięcej wiedzy do spisania, najbardziej mierzalne wyniki (Lighthouse).
3. `jarvo-studio`: wymaga najwięcej narzędzi i kluczy API (OpenRouter, FFmpeg, renderery).
4. `jarvo-reka`: na końcu, bo korzysta ze skilli pozostałych.
5. `jarvo-wideo`: wydzielony później ze Studia (wideo to osobny warsztat).
6. `jarvo-ads`: dołączony bez kluczy; Skarbiec (sejf tokenów) jeszcze do zbudowania ([ADS.md](ADS.md)).
7. `jarvo-lowca` i `jarvo-mobile`: specjaliści z własnymi skryptami do źródeł publicznych ([LEADY.md](LEADY.md), [MOBILE.md](MOBILE.md)).

Pierwszy wspólny test floty: **„wypuść landing nowego produktu”**. Sherlock robi research
i słowa kluczowe, web buduje stronę, studio przygotowuje grafiki i posty, ręka składa
wszystko w pakiet, a Jarvo ocenia każdy etap.

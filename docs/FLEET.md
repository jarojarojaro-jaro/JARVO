# Flota Jarvo: specyfikacja agentów v1

Flota: **Main Judge + 8 agentów**. Każdy agent to osobny profil Hermesa
(osobna dystrybucja w `profiles/<nazwa>/`). Rejestr maszynowy jest w [`fleet.yaml`](../fleet.yaml).

Każdy agent jest budowany według [PROFILE-SPEC.md](PROFILE-SPEC.md) (main prompt, workflowy,
knowledge packi, skrypty, toolbox, granice, evals). Zweryfikowane narzędzia open-source
każdego agenta są w [TOOLBOX.md](TOOLBOX.md), a infrastruktura w [VPS.md](VPS.md).

**Stan: wszystkie dziewięć profili jest zbudowanych.** Ten dokument to specyfikacja. Implementacja:

| Agent | Main prompt | Workflowy własne | Skille zewnętrzne | Skrypty | Evals |
|---|---|---|---|---|---|
| `jarvo` | [SOUL](../profiles/jarvo/SOUL.md) | [13 w `skills/fleet/`](../profiles/jarvo/skills/fleet) + generowany `roster` | 2 (`writing-for-agents`, mattpocock; wspólny `konwersja-plikow`) | patrol, brief, przegląd, raport floty, liczby floty, świeżość, linter kontraktu, prosty polski, księga lekcji, poczekalnia skilli | [27](../evals/jarvo/scenarios.yaml) |
| `jarvo-sherlock` | [SOUL](../profiles/jarvo-sherlock/SOUL.md) | [8 w `skills/sherlock/`](../profiles/jarvo-sherlock/skills/sherlock) | 17 (Hermes, marketingskills, wspólne `transkrypcja-filmu`, `konwersja-plikow` i `ostrozna-przegladarka`) | search_fanout, extract, sources (rejestr cytowań), fakty (brief do filmu) | [16](../evals/jarvo-sherlock/scenarios.yaml) |
| `jarvo-web` | [SOUL](../profiles/jarvo-web/SOUL.md) | [10 w `skills/web/`](../profiles/jarvo-web/skills/web) | 61 (web-quality, claude-seo, marketingskills, Anthropic, Hermes, getsentry, Trail of Bits, impeccable, GSAP, Three.js, motion, Lottie, wspólne `graf-kodu`, `izometria`, `warsztat-3d` i `konwersja-plikow`) | audit, seo_check, screenshots, a11y, favicons, images, brand_extract, hostile, security_check | [20](../evals/jarvo-web/scenarios.yaml) |
| `jarvo-studio` | [SOUL](../profiles/jarvo-studio/SOUL.md) | [7 w `skills/studio/`](../profiles/jarvo-studio/skills/studio) | 27 (marketingskills, Anthropic, Hermes, impeccable, lemo-wake, wspólne `hooki`, `izometria` i `konwersja-plikow`) | render_html, check_media, lemo_wake | [15](../evals/jarvo-studio/scenarios.yaml) |
| `jarvo-wideo` | [SOUL](../profiles/jarvo-wideo/SOUL.md) | [21 w `skills/wideo/`](../profiles/jarvo-wideo/skills/wideo) | 63 (HyperFrames, GSAP, Three.js, Remotion, remocn, iart, screenwriting, marketingskills, live-panel, Hermes, wspólne `transkrypcja-filmu`, `hooki`, `izometria`, `warsztat-3d`, `konwersja-plikow` i inne) | film, stock, kadry, montaz, dwa_ekrany, napisy, qa_wideo, rytm, muzyka, narzedzia, html_wideo, pomiar, inspiracje, projekt, krytyka, assety, maskotka, lektor_linie, retime, klipy, twarze, demo_strony, typografia, maska, zywy_schemat, gramatyka, malarz (+ wideo_lib; moduły JS stron: ruch, kreska, morph, crt, plotno, piksel, os_czasu, strona, ujecia) | [39](../evals/jarvo-wideo/scenarios.yaml) |
| `jarvo-ads` | [SOUL](../profiles/jarvo-ads/SOUL.md) | [11 w `skills/ads/`](../profiles/jarvo-ads/skills/ads) | 7 (marketingskills, wspólne `hooki` i `konwersja-plikow`) | ads, planer, eksperyment, eksport, paczka | [14](../evals/jarvo-ads/scenarios.yaml) |
| `jarvo-lowca` | [SOUL](../profiles/jarvo-lowca/SOUL.md) | [7 w `skills/lowca/`](../profiles/jarvo-lowca/skills/lowca) | 2 (wspólne `konwersja-plikow` i `ostrozna-przegladarka`) | krs, ceidg, przetargi, strona, leady, zrodlo | [16](../evals/jarvo-lowca/scenarios.yaml) |
| `jarvo-mobile` | [SOUL](../profiles/jarvo-mobile/SOUL.md) | [10 w `skills/mobile/`](../profiles/jarvo-mobile/skills/mobile) | 22 (Expo, React Native, ASO; wspólne `konwersja-plikow` i `warsztat-3d`; `vendor/skills.lock.yaml`) | audyt_mobilny, decyzja, zgodnosc, aplikacja, ikony, zrzuty, wrogie, urzadzenie, ios_ci, bramka, sklep_check, pakiet, kadry, wydanie, odrzucenie, ze_strony, utrzymanie, paczki (+ mobile_lib, szablon `expo-jarvo`, workflow iOS) | [34](../evals/jarvo-mobile/scenarios.yaml) |
| `jarvo-reka` | [SOUL](../profiles/jarvo-reka/SOUL.md) | [4 w `skills/reka/`](../profiles/jarvo-reka/skills/reka) | 5 (skill-creator, `writing-for-agents`, `graf-kodu`, `transkrypcja-filmu`, `konwersja-plikow`) + skille wszystkich snajperów (`external_dirs`, tylko odczyt) + katalog Hermesa | pack, to_pdf | [14](../evals/jarvo-reka/scenarios.yaml) |

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
| `jarvo-ads` | Specjalista Ads: Meta Ads i Google Ads, kampanie, testy, raporty | snajper | A1 (paczka do publikacji; publikuje i wydaje właściciel) |
| `jarvo-wideo` | Wideograf: krótkie filmy, montaż, lektor, napisy, klipy | snajper | A1 (renderuje; publikacja i zakupy = A2) |
| `jarvo-lowca` | Łowca leadów: firmy z sygnałem zakupowym i opublikowanym kontaktem | snajper | A1 (szuka i ocenia; wysyłka = decyzja człowieka) |
| `jarvo-mobile` | Twórca aplikacji: natywna czy PWA, audyt mobilny, aplikacje Expo do sklepów | snajper | A1 (audyty i rekomendacje; konta sklepów i wysyłka = A2) |
| `jarvo-reka` | Prawa ręka: generalista, który ogarnia wszystko | generalista | A1 (e-maile i akcje zewnętrzne = A2) |

---

## Warstwa wspólna: wiedza o Tobie i Twoich markach

Snajperzy nie dzielą pamięci ani workflowów dziedzinowych (wspólne są tylko skille z `shared/skills/`:
narzędziowe jak `graf-kodu` i `izometria` (figury izometryczne ze świeceniem u Weba, Studia i Wideografa: strona, PNG,
film; `iso.py flota` rysuje flotę z rejestru, ta sama figura jest w HQ: Centrala → Jak działa usługa), `warsztat-3d`
(u Weba, Wideografa i Mobile: część albo produkt 3D z kodu build123d, pliki STEP, STL, GLB i 3MF, podgląd PNG
i film obrotu) i metodyczne jak `hooki`, oraz te same skille zewnętrzne z locka). Jeden skill ma każdy agent:
`konwersja-plikow` (plik → inny format na serwerze: zdjęcia z HEIC, wideo, audio, PDF, Word; usuwa też metadane:
miejsce GPS, telefon, daty, autor, a z PDF i dokumentów Office także firmę, program i historię zmian; ten sam
konwerter masz w HQ: Centrala → Konwerter).
Wszyscy znają też **Ciebie**:
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
| Film, reels, short, montaż, napisy, lektor, klipy, żywy schemat (animowany przepływ na post), explainer z wykresem albo tablicą, film w stylu malarza (Van Gogh, Klimt, jaskinia) | `jarvo-wideo` |
| Leady, nowi klienci, „komu sprzedać”, przetargi do wzięcia, nowe firmy w branży, kontakt do firm | `jarvo-lowca` |
| Aplikacja mobilna, „czy potrzebujemy aplikacji”, PWA czy natywna, audyt aplikacji w App Store i Google Play, aplikacja z naszej strony, aktualizacja albo poprawka aplikacji w sklepie | `jarvo-mobile` |
| Szybkie sprawy, sklejanie wyników, prototyp, „ogarnij to”, zadanie bez oczywistego snajpera | `jarvo-reka` |
| Duże cele (np. „wypuść nowy produkt”) | rozbicie na kilka kart, np. sherlock → web + studio → reka (spięcie) |

**Skille:** [T] `intake`, `wywiad`, `dispatch-playbook` (jak pisać karty z DoD, typowe przepływy),
`mission-ledger` (dziennik misji i raport końcowy), `decision-queue`, `sdlc-review` (sędzia; rubryki agentów
`references/rubric-<agent>.md` generowane z ich `quality/rubric.md`), `patrol`, `daily-brief`, `weekly-review`,
`onboarding-interview`, `fleet-improvement`, [T] `roster` (generowany z `fleet.yaml`: kto istnieje i co umie);
[Z] `writing-for-agents` (mattpocock/skills: warsztat pisania SOUL i skilli, dla `fleet-improvement`), wspólny
`konwersja-plikow` (zamiana pliku od ręki, bez karty dla snajpera).

**Toolsety:** na Telegramie `kanban`, `memory`, `file`, `web`, `session_search`, `clarify`, `todo`, `skills`, `cronjob`,
bez terminala; narzędzie `schemat` (SVG → PNG w rozmowie) daje mu wtyczka `jarvo-wiedza` razem z narzędziami skarbca; w czacie HQ (`api_server`) to samo bez `clarify`. Pracownik-sędzia (CLI) ma dodatkowo `terminal`, `browser` i `vision` do weryfikacji wyników.
Pracy dziedzinowej nie wykonuje (zasada SOUL, nie brak narzędzi).

---

## `jarvo-web`: Web Senior Dev

**Misja:** wie o stronach wszystko. Robi nowe strony, ulepsza i usprawnia stare, uczy
się Twojej marki z istniejącej strony i robi strony produktowe pod SEO. Przed projektem ogląda prawdziwe strony
z branży klienta (katalog Inspo albo własna baza w skarbcu) i zapisuje, co z nich bierze.

**Zakres wiedzy (knowledge packi w `references/`):**
- **Fundamenty:** semantyczny HTML, nowoczesny CSS, mobile-first, breakpointy, typografia, dark mode.
- **Ikony i meta:** komplet faviconów (`favicon.ico`, SVG, `apple-touch-icon`, ikony do
  manifestu 192/512 i maskable), `site.webmanifest`, meta tagi, Open Graph i karty X/Twitter.
- **SEO techniczne:** title i description (inne na każdej podstronie), canonical, hreflang, sitemap, `robots.txt`,
  `llms.txt`, strona 404 (prawdziwy status 404), obraz OG 1200×630, landmarki HTML, dane strukturalne JSON-LD
  (Product, Organization, FAQ, Breadcrumb…), linkowanie wewnętrzne. `seo_check.py --dir dist` sprawdza cały build.
- **Obrazy:** AVIF/WebP, `srcset`/`sizes`, lazy loading, jawne wymiary (bez skoków layoutu), kompresja.
- **Wydajność:** Core Web Vitals (LCP, INP, CLS), budżety wydajności, fonty, krytyczny CSS.
- **Dostępność:** WCAG 2.2 AA, kontrast, nawigacja klawiaturą, alt teksty.
- **Wdrożenie:** GitHub/Cloudflare/Netlify Pages, domeny, analityka.

**Skille:**
- [H] `claude-design`, `popular-web-designs`, `design-md`, `scrollcraft`, `publish-site`, `cloudflare-temporary-deploy`,
  `systematic-debugging` (przyczyna błędu builda albo skryptu, zanim poprawka)
- [Z] `impeccable`, web-quality-skills (5), claude-seo (13), marketingskills (3), Anthropic (2), GSAP (8), Three.js (10),
  motion Emila Kowalskiego (5), `text-to-lottie`, wspólne `graf-kodu` i `izometria` (`shared/skills/`: klikalna figura
  izometryczna na stronę klienta, `<iframe>` bez stopki, kolor marki), `warsztat-3d` (model produktu albo części
  z kodu: GLB na stronę, PNG bez studia, STL i 3MF do druku), getsentry `security-review`
  (przegląd kodu wg OWASP), Trail of Bits `supply-chain-risk-auditor` (ryzyko zależności)
- [T] `brand-z-url`: podajesz stronę, a agent crawluje ją i wyciąga logo, kolory, fonty,
  ton i komponenty do `knowledge/brands/<marka>/` (z `DESIGN.md`)
- [T] `audyt-strony`: Lighthouse, dostępność (axe), SEO, obrazy i responsywność (zrzuty na kilku
  szerokościach), wynik jako raport z priorytetami
- [T] `inspiracje-stron`: przed projektem 3–5 stron referencyjnych z branży klienta: katalog Inspo (MCP `inspo`,
  832 prawdziwe strony ze zrzutami, paletą i układem) według mapy polskich branż, a dla branż słabo pokrytych
  (nieruchomości, gabinety, salony, kancelarie…) własna baza w skarbcu `inspiracje/strony/<branża>/`; wnioski w PLAN.md
- [T] `nowa-strona`: od briefu do wdrożenia (domyślny stack: Astro dla stron marketingowych)
- [T] `bramka-jakosci`: rubryka designu 10 osi (wynik 0–100, zaliczenie od 90, rundy poprawek) i testy wrogie
  (`hostile.cjs`: wolne łącze, brak JS, 320 px, klawiatura, długie polskie słowa, reduced motion, zasoby zewnętrzne)
- [T] `landing-produktowy`: strona nowego produktu pod SEO (research słów kluczowych od `jarvo-sherlock`, jeśli trzeba)
- [T] `favicon-i-meta`: generowanie kompletu ikon, manifestu i meta z jednego logo
- [T] `optymalizacja-obrazow`: konwersja i kompresja obrazów, `srcset`
- [T] `wdrozenie`: podgląd (A1) i wdrożenie produkcyjne (A2, tylko za zgodą), po nim zgłoszenie adresów z sitemapy
  do IndexNow (`indexnow.py`: Bing, Yandex i inne; klucz w `public/` od `nowa-strona`) i instrukcja Bing Webmaster Tools
  oraz Search Console dla właściciela
- [T] `bezpieczenstwo-aplikacji`: skan kodu, strony i zależności, próby na podglądzie (`security_check.py repo|url|atak`),
  lista 28 punktów (w tym funkcje AI, sesje, CSRF, kopie zapasowe, zdjęcia bez GPS, odpowiedzi zalogowanego poza cache CDN), przegląd kodu

**Narzędzia:** terminal, pliki, przeglądarka (Lightpanda, Chromium do zrzutów), Node.js, a do tego Lighthouse, axe-core,
Playwright, sharp, favicons, dembrandt (wyciąganie brandu), linkinator, html-validate; MCP `inspo` (katalog stron
Inspo, lokalnie po stdio, włączony w `config.yaml`, startuje przy pierwszym użyciu), MCP `context7` zaplanowany. Pełna lista: [TOOLBOX.md](TOOLBOX.md#jarvo-web-web-senior-dev).

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
- [H] `blocked-page-recovery`, `searxng-search`, `duckduckgo-search`,
  `scrapling`, `arxiv`, `youtube-content`, `reddit-reading`, `rss-feeds`,
  `blogwatcher`, `competitor-news-monitor`, `domain-intel`, `osint-investigation`
- [Z] marketingskills `competitor-profiling`, `customer-research`; wspólny `transkrypcja-filmu` (`shared/skills/`):
  link albo plik filmu → tekst mowy (napisy platformy albo Parakeet), bez analizy obrazu; wspólny `ostrozna-przegladarka`:
  strona, która odmówiła zwykłej przeglądarce i nie ma kopii w archiwum, dostaje jedną próbę Camoufoxem (`ostrozna.py`)
- [T] `metoda-sherlocka`, [T] `weryfikacja-faktow` (poziomy wiarygodności źródeł), [T] `szybki-fakt` (jedna runda, cytat),
  [T] `raport-sledztwa` (format raportu; brief do filmu `out/fakty.json` dla Wideografa, sprawdzany `fakty.py`), [T] `research-seo` (słowa kluczowe i konkurencja, dla `jarvo-web` i `jarvo-studio`),
  [T] `research-rynku` (gracze, oferty, ceny, opinie), [T] `monitoring` (rutyna cron zakładana przez Jarva),
  [T] `cytowania` (numer `[n]` z rejestru przy pobraniu strony, cytaty-dowody sprawdzane z tekstem strony,
  blok „Źródła” ze skryptu i `verify` raportu przed oddaniem; silnik przeniesiony z Hermesa `grounded-citations`)

**Narzędzia:** wielu dostawców wyszukiwania naraz (własny SearXNG, Brave, Exa…), trafilatura i Lightpanda (strony z JS do Markdown),
Camoufox tylko po odmowie strony (jedna próba, robots.txt, bez captchy; serwisy za Cloudflare zwykle odmawiają dalej),
Docling (PDF-y, dodatek obrazu), yt-dlp (transkrypcje), OpenAlex (nauka, wtyczka opcjonalna), rejestr źródeł
z tekstami stron i cytatami-dowodami (`sources.py`, `out/zrodla.json`), archiwum dowodów lokalnie
(`sources.py --archive`: HTML i tekst; ArchiveBox jako opcjonalny sidecar w planach), delegowanie wątków.
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
- **żywe obrazy:** lemo-wake (zdjęcie lub grafika → pętla 5 s i warstwy PSD; licencja niekomercyjna, komercyjnie za zgodą autora),
- **publikacja:** Postiz (self-host) jako kolejka, a post wychodzi dopiero po Twojej akceptacji.
Pełna lista: [TOOLBOX.md](TOOLBOX.md#jarvo-studio-marketing-i-kreacja).

**Skille:**
- [H] `baoyu-infographic`, `social-media-content-calendar`, `creative-ideation`, `humanizer`, `meme-generation`,
  `excalidraw`, `concept-diagrams`
- [Z] marketingskills (11: copywriting, social, launch, ad-creative…), Anthropic (3: `algorithmic-art`,
  `canvas-design`, `theme-factory`), `impeccable`, lemo-wake (2: `lemo-wake`, `lemo-wake-layers`);
  wspólne `hooki` (`shared/skills/`: trzy warstwy hooka, 18 taktyk) i `izometria` (figury izometryczne ze świeceniem:
  PNG na social, seria ikon w jednej palecie marki)
- [T] `formaty-platform` (specyfikacje i szablony), [T] `grafika-social` (szablony HTML do PNG w brand kicie),
  [T] `pakiet-kampanii` (posty + grafiki + brief wideo + kalendarz), [T] `generacja-ai` (obrazy), [T] `copy-pl` (+ sito AI-izmów), [T] `zywy-obraz` (pętla 5 s i warstwy PSD z lemo-wake), [T] `publikacja`

**Rubryka sędziego (DoD):** właściwe formaty i wymiary dla platformy, zgodność z brand kitem,
tekst bez „AI-izmów”, pliki gotowe do publikacji, przy kampanii z filmem: brief dla Wideografa.

**Zasada:** **nie publikuje sam.** Przygotowuje pakiet do publikacji, a publikacja wymaga Twojej zgody.

---

## `jarvo-wideo`: Wideograf

**Misja:** filmy, które ktoś obejrzy do końca: od tematu albo surowego nagrania do gotowego pliku na TikTok, Reels,
Shorts i YouTube. Wydzielony ze Studia, bo wideo to osobny warsztat (rytm, dźwięk, napisy, montaż).

**Tryby pracy:**
- **krótki film z tematu** (pomysł z [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo), własna implementacja):
  scenariusz → ujęcia (stock Pexels/Pixabay, AI, pliki, plansze) → polski lektor (domyślnie lokalny Matcha-TTS-PL v2 bez sieci i limitów, głos syntetyczny oznaczany w opisie filmu;
  Edge TTS do wyboru i jako zapas; po angielsku lokalny Paradee)
  → napisy karaoke → muzyka ściszana pod głos → montaż FFmpeg w 9:16/16:9/1:1/4:5, z planu `plan.json` (`film.py`),
- **warianty A/B** z jednego planu (hook, głos, tempo, długość), wspólne sceny z cache,
- **montaż nagrań** użytkownika: cięcie, usuwanie ciszy, kadr 9:16 z poziomego, głośność −14 LUFS, napisy,
- **dwa ekrany** (split screen, skill `dwa-ekrany`, `dwa_ekrany.py`): dwa nagrania albo zdjęcia w jednym kadrze: jedno nad
  drugim w pionie, obok siebie w poziomie, przed/po z jadącą kreską albo na dwóch telefonach narysowanych kodem;
  podpisy w strefie bezpiecznej platformy, test pauzy (w każdej chwili coś się rusza w co najmniej jednym oknie),
- **klipy z długich nagrań** (podcast, webinar): transkrypcja Parakeet z czasem słów → wybór fragmentów → klipy z napisami
  i kadrem 9:16 na twarzy mówcy, przy kilku osobach na tej, która mówi, i okładką z ostrą twarzą (`klipy.py`, `twarze.py` z YuNet),
- **typografia jak z montażu** do nagrania z mową (`typografia.py`, skill `typografia-edit`): słowa w rytmie mowy, różne
  wielkości, kroje, głębia, skos i 3D, mocne słowo za osobą (maska MODNet, `maska.py`); forma wynika ze znaczenia,
  kolory z palety kadru (dwa akcenty w kontraście ze sceną, rozpisane na zmianę po mocnych słowach), styl filmu
  z 14 (np. `podcast` z obrysem, `vlog`, `tech`, `magazyn`) dobrany do rodzaju nagrania, `typografia.py style`
  pokazuje ten sam blok w każdym, a `typografia.py sprawdz` mierzy tusz liter (poza kadrem, bloki na sobie, stykające
  się litery, napis za osobą czytelny i naprawdę zasłonięty, strefy platformy); słowa jednego bloku nowego planu same
  się nie stykają, ani w linii, ani między liniami (odstęp liczony z tuszu liter z obrysem stylu, `"odstep": "tusz"`);
  wirtualna kamera z głębią (`typografia.py kamera`, styl spokojna/dynamiczna z motywu): najazd, odjazd i przesunięcie
  filmu razem z napisami na różnych głębokościach, z paralaksą i rozmyciem jak w obiektywie; efekty wow z maski osoby
  (`typografia.py efekt`, `plan --efekty`): napis krąży pierścieniem wokół głowy (przód przed twarzą, tył za osobą)
  albo przechodzi przez osobę (wchodzi za nią, wychodzi przed nią); plan leży w projekcie montażu, więc właściciel poprawia każde słowo w edytorze HQ,
- **żywe schematy** (skill `zywy-schemat`, silnik strony [live-panel](https://github.com/ythx-101/live-panel-skill)): flota,
  przepływ zlecenia albo architektura, która „działa” (kropki po strzałkach, kroki podświetlane po kolei), na posty X
  i Instagram; `zywy_schemat.py` dokłada formaty platform, motywy Jarva i polskie kroje, `html_wideo.py` mierzy i renderuje,
- **style motion design** (skill `style-motion`): 15 stylów, które ekspert rozpoznaje w sekundę (rysunek z wrzącą
  linią, izometria, płaski wektor, morph, HUD, Bauhaus, synthwave, pixel art i inne), każdy z kartą (cechy z liczbami,
  rytm, dźwięk, kontrola) i filmem-wzorem 10 s z [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) (MIT);
  silniki stylów przeniesione do modułów `/_lib/jarvo/` (`kreska.js`, `morph.js`, `crt.js`, `plotno.js`, `piksel.js`),
- **gramatyki explainera** (skill `gramatyki-explainera`, silnik kanwy [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion), MIT):
  osiem sposobów rysowania fragmentu z lektorem (wykresy jak The Economist, rysowana tablica, 3Blue1Brown, kolaż Vox,
  prezentacja z premiery, historyjka z postacią, typografia kinetyczna, Kurzgesagt); `gramatyka.py` robi spec po polsku,
  przypina cue do słów lektora z `os_czasu.json`, sprawdza liczby z `fakty.json` i renderuje klip o dokładnej długości
  (także 9:16 i z alfą); polska nakładka `huashu_pl.js` daje kroje z ą–ż, liczby po polsku i neutralną postać,
- **style malarskie** (skill `style-malarskie`, ten sam silnik): 35 stylów od malowidła jaskiniowego, Egiptu i mozaiki
  przez Van Gogha, Klimta i tusz po piksel 8-bit i Ghibli, każdy z kartą (cechy z kolorami i parametrami, co się
  rusza, przejście-podpis, wydajność, pułapki) i sceną-wzorem; `malarz.py` daje katalog, galerię 35 kadrów,
  stopklatki wzoru, szkielet filmu (strona w kontrakcie jarvo, tabela odcinków na siatce bitów, kopia sceny-wzoru
  do przerobienia) i wycinanie warstw AI z zielonego tła,
- **filmy z kodu** (HyperFrames, Manim na silniku ManimGX) i **ujęcia z AI** (`video_generate`, obraz → wideo, rejestr kosztów);
  lektor filmu z kodu z pliku narracji (`film.py narracja`: zdanie w linii, akapit = ujęcie, pauzy 0,33 s / 1 s /
  1,5 s, oś czasu `os_czasu.json` z chwilami po nazwie, które animacja bierze z `/_lib/jarvo/os_czasu.js`, więc nowe
  nagranie lektora jej nie psuje; tekst pisany według zasad narracji: start w sytuacji widza, jedna linia opowieści,
  liczba w skali, którą czuć, koniec odwraca początek, a `--sprawdz` łapie powitanie, definicję na start, listę
  zamiast opowieści, opis obrazu i streszczenie na końcu; fakty z briefu Sherlocka `fakty.json`: liczba lektora
  albo ekranu z listy niepewnych zatrzymuje syntezę i pomiar, liczba bez źródła daje ostrzeżenie, a słowniczek
  briefu mówi lektorowi, jak czytać trudne nazwy, przy napisach w pisowni z tekstu),

**Jakość:** `qa_wideo.py` (kodeki, format, długość, LUFS i rozpiętość głośności LRA, czarne i zamrożone klatki, pojedyncze „mrugnięcia” klatek, arkusz ze strefami UI 9:16). **Rytm i wzór:** `rytm.py` (BPM, takty, drop pod cięcia, perkusja: stopa, werbel, talerze; `sprawdz` po renderze: każde cięcie kontra bit), `muzyka.py` (muzyka pod obraz pisana kodem z mgaudio, MIT: gatunek ze stylu, kulminacja i koniec z osi filmu, efekty w tych samych chwilach, −14 LUFS, słyszalność efektów; z `--lektor` głos w miksie i muzyka ściszana pod mowę, z powrotem w pauzach akapitów; dodatek `narzedzia.py instaluj mgaudio`, ok. 450 MB), `kadry.py wzor` (film-wzór → klatki co 0,5 s, cięcia, rytm, przejścia na siatce bitów, mapa ruchu, klatki kluczowe → mapa bitów)
+ `kontrola-wideo` (ocena 0–100 w 10 osiach, PASS od 85, najwyżej 2 rundy poprawek). Każde ujęcie oglądane (vision),
źródła i licencje w `film.json`.

**Skille:** [T] `rodzaje-filmu`, `krotki-film`, `scenariusz`, `material-stock`, `dobor-ujec`, `warianty-ab`, `montaz-nagran`,
`clipmaker`, `demo-strony`, `napisy`, `typografia-edit`, `lektor-i-dzwiek`, `film-z-kodu`, `style-motion`, `gramatyki-explainera`, `style-malarskie`, `zywy-schemat`, `wideo-ai`, `formaty-wideo`,
`kontrola-wideo`;
[H] `manim-video` (silnik ManimGX, dodatek `manim`), `ai-presenter-video`; [Z] `hyperframes` (12 skilli rodziny), marketingskills `video`, GSAP (8),
Three.js (10), screenwriting (5), iart (5), motion (3), Remotion, motion-broll, lemo-opuscar, anidoodle, claude-animation,
bang-motion, pixel2motion, `text-to-lottie`, `slack-gif-creator`, `motion-design` i `video-lessons` (Remocn Studio),
`live-panel`, wspólne `transkrypcja-filmu`, `hooki`, `izometria` (figura z `demo()` na film przez `html_wideo.py`),
`warsztat-3d` (film obrotu części, GLB do sceny Three.js) i `konwersja-plikow` (razem 63).
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
`transkrypcja-filmu`, `konwersja-plikow` oraz [T] `zlozenie-pakietu`, `dokumenty`, `szybki-prototyp`, `kiedy-oddac-snajperowi` (tabela
„komu oddać” generowana z pól `oddaj_gdy` w `fleet.yaml`, więc każdy nowy specjalista trafia do niej sam).

**Rubryka sędziego (DoD):** zadanie wykonane, wynik sprawdzony przez nią samą, jasno powiedziane, czego nie zrobiła.

---

## `jarvo-ads`: Specjalista Ads

Meta Ads i Google Ads od planu kampanii po raport: plan, testy A/B/C, paczka do publikacji, raporty z listą zmian
do wyklikania, wnioski dla Studia i Wideografa. **Agent przygotowuje, Ty publikujesz:** `publikacja-reczna`
(`paczka.py`) daje wszystko do wklejenia w Menedżerze reklam albo Google Ads, krok po kroku, z budżetem nie
wyższym niż Twoja zgoda i datą końca; „Opublikuj” klikasz Ty. Agent nie ma dostępu do kont. Bezpośrednie połączenie
przez **Skarbiec** (osobny kontener z tokenem, polityką i kodami zgody) jest odłożone; do tego czasu `podlacz-konto`,
`start-kampanii` i `optymalizacja` (`wymaga: [skarbiec]`) nie trafiają do profilu. Pełny projekt: [ADS.md](ADS.md).

---

## `jarvo-lowca`: Łowca leadów

Szuka firm, dla których teraz jest dobry moment na rozmowę: nowe spółki w KRS i nowe jednoosobowe działalności
w CEIDG (PKD i region z profilu klienta; CEIDG na darmowym tokenie właściciela), przetargi w BZP i TED (zamawiający kupuje to, co sprzedajesz; zwycięzca potrzebuje wykonawców), oferty pracy,
technologia i zmiany na stronach firm, newsy. Oddaje ranking z „dlaczego teraz”, źródłem sygnału i kontaktem, który
firma sama opublikowała; monitoring pokazuje tylko nowe firmy. Tylko źródła oficjalne i publiczne, bez LinkedIna
i baz kupionych, niczego nie wysyła. Pełny projekt: [LEADY.md](LEADY.md).

**Skille:** [T] `profil-klienta`, `sygnaly` (+ tabela źródeł i przepisów), `kwalifikacja`, `kontakt-firmy`,
`lista-leadow`, `monitoring-leadow`, `rozpoznanie-zrodla` (nowe źródło: nagranie ruchu HAR, różnice, schemat);
wspólne `konwersja-plikow` i `ostrozna-przegladarka` (strona firmy, która odmówiła zwykłej przeglądarce: jedna próba
Camoufoxem, potem `strona.py kontakt --z-html`; API rejestrów bez wyjątku).
Skrypty: `krs.py`, `ceidg.py`, `przetargi.py`, `strona.py`, `leady.py`, `zrodlo.py` (+ `har.cjs`).

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
[A2] `utrzymanie-aplikacji` (+ opinie w sklepach); 20 skilli zewnętrznych (Expo, Callstack, Vercel, ASO) i wspólne `konwersja-plikow` i `warsztat-3d` (model GLB do aplikacji,
obraz produktu). Skrypty: `audyt_mobilny.py`, `decyzja.py`, `zgodnosc.py`, `aplikacja.py`,
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
6. `jarvo-ads`: bez kluczy, kampanie jako paczka do publikacji przez właściciela; Skarbiec (sejf tokenów) odłożony ([ADS.md](ADS.md)).
7. `jarvo-lowca` i `jarvo-mobile`: specjaliści z własnymi skryptami do źródeł publicznych ([LEADY.md](LEADY.md), [MOBILE.md](MOBILE.md)).

Pierwszy wspólny test floty: **„wypuść landing nowego produktu”**. Sherlock robi research
i słowa kluczowe, web buduje stronę, studio przygotowuje grafiki i posty, ręka składa
wszystko w pakiet, a Jarvo ocenia każdy etap.

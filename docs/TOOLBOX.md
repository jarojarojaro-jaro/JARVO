# Toolbox floty: narzędzia open-source per agent

**Weryfikacja: 2026-09-26.** Każde repo sprawdzone bezpośrednio z GitHuba: czy istnieje,
jaka jest licencja (z pliku LICENSE) i kiedy był ostatni commit. Ten dokument to **katalog kandydatów**.
To, co faktycznie jest zainstalowane, opisują `profiles/<agent>/toolbox.yaml` (z healthcheckami)
i sekcja „Stan instalacji” na końcu.

Legenda integracji: **CLI** (terminal + skill), **skrypt** (w `scripts/` skilla), **sidecar**
(kontener na VPS), **plugin** (katalog Hermesa), **MCP** (serwer MCP), **[H]** (skill z katalogu Hermesa).

Oprócz narzędzi z zewnątrz Hermes ma własny ekosystem, który wykorzystujemy w pierwszej kolejności:
~300 wtyczek w `plugin-catalog/` (każda przypięta do konkretnego commita i przejrzana przez
maintainerów), ~65 serwerów MCP w `optional-mcps/`, dostawców wyszukiwania w `plugins/web/`
(SearXNG, DuckDuckGo, Brave, Exa, Tavily, Perplexity, Parallel…), generowanie obrazów
i wideo w `plugins/image_gen/` i `plugins/video_gen/` (m.in. **OpenRouter**) oraz
obserwowalność przez Langfuse w `plugins/observability/`.

---

## `jarvo-web`: Web Senior Dev

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Lighthouse](https://github.com/GoogleChrome/lighthouse) | audyt wydajności, SEO, dostępności, dobrych praktyk | Apache-2.0 | 2026-09 | CLI + skrypt |
| [axe-core](https://github.com/dequelabs/axe-core) + [axe-core-npm](https://github.com/dequelabs/axe-core-npm) | audyt dostępności (WCAG) | MPL-2.0 | 2026-09 | CLI + skrypt |
| [Playwright](https://github.com/microsoft/playwright) | zrzuty na wielu szerokościach, testy responsywności | Apache-2.0 | 2026-09 | skrypt |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | sterownik narzędzi `browser_*` Hermesa (natywna binarka Rust) | Apache-2.0 | 2026-10 | Hermes |
| [Lightpanda](https://github.com/lightpanda-io/browser) | lekka przeglądarka headless dla agentów (~30 MB na sesję); Chromium tylko do renderu | AGPL-3.0 (osobny program) | 2026-10 | silnik `browser.engine` |
| [sharp](https://github.com/lovell/sharp) | konwersja i kompresja obrazów (AVIF/WebP), warianty `srcset` | Apache-2.0 | 2026-09 | skrypt |
| [favicons](https://github.com/itgalaxy/favicons) | komplet faviconów, ikon i manifestu z jednego pliku | MIT | 2026-09 | skrypt |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | mapa dużego repo: kto woła funkcję, wpływ zmian (graf wywołań, lokalnie, bez klucza i tokenów) | MIT | 2026-09 | skill `graf-kodu` (tryb poleceń, pobierany przy pierwszym użyciu) |
| [pwa-asset-generator](https://github.com/elegantapp/pwa-asset-generator) | ikony i splash screeny PWA | MIT | 2026-09 | CLI |
| [SVGO](https://github.com/svg/svgo) | optymalizacja SVG (logo, ikony) | MIT | 2026-08 | CLI |
| [linkinator](https://github.com/JustinBeckwith/linkinator) | wykrywanie martwych linków | MIT | 2026-09 | CLI |
| [html-validate](https://github.com/html-validate/html-validate) | walidacja HTML | MIT | 2026-09 | CLI |
| [glyphhanger](https://github.com/zachleat/glyphhanger) | subsetting fontów | MIT | 2026-06 | CLI |
| [dembrandt](https://github.com/dembrandt/dembrandt) | **wyciąga system designu ze strony** (logo, kolory, typografia, odstępy) jako tokeny W3C, czyli podstawa `brand-z-url` | MIT | 2026-09 | CLI + skrypt |
| [Inspo](https://github.com/Nutlope/inspo) (`inspo-mcp`) | **katalog 832 prawdziwych stron** (2320 podstron: zrzuty desktop i mobile, paleta, fonty, opis układu) jako inspiracja przed projektem; podstawa `inspiracje-stron` | MIT | 2026-09 | MCP `inspo` (stdio, lokalnie) |
| [CSS Analyzer](https://github.com/projectwallace/css-analyzer) | statystyki CSS (kolory, fonty, złożoność) do audytów | MIT | 2026-09 | skrypt |
| [webappanalyzer](https://github.com/enthec/webappanalyzer) | wykrywanie technologii na audytowanej stronie | GPL-3.0 | 2026-09 | skrypt (dane) |
| [web-vitals](https://github.com/GoogleChrome/web-vitals) | pomiar Core Web Vitals u prawdziwych użytkowników na budowanych stronach | Apache-2.0 | 2026-09 | biblioteka w projektach |
| [Astro](https://github.com/withastro/astro) | domyślny framework stron marketingowych i produktowych | MIT | 2026-09 | per projekt |

Z Hermesa:
- **[H] skille:** `claude-design`, `popular-web-designs` (54 prawdziwe systemy designu), `design-md`,
  `impeccable`, `auteur`, `scrollcraft`, `publish-site`, `cloudflare-temporary-deploy`,
- **MCP:** `context7` (aktualna dokumentacja bibliotek), `netlify`, `vercel`, `cloudflare`,
  `webflow`, `wordpress-com`, `figma`, `deepwiki`,
- **plugin:** `image-utils`.

Odrzucone lub opcjonalne: `lighthouse-ci` (ostatni commit 2025-06), Unlighthouse i critical (każdy ciągnie
własną przeglądarkę i ~0,3 GB; całą witrynę audytujemy `audit.sh` po kolei na wybranych URL-ach z sitemapy), `pa11y` (dubluje axe), `validator/vnu` (wymaga Javy; html-validate wystarcza na start).

---

## `jarvo-sherlock`: Researcher-detektyw

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [SearXNG](https://github.com/searxng/searxng) 2026.10.19-81371861f | własna metawyszukiwarka (70+ silników), bez kluczy i limitów; obraz przypięty wersją i digestem w `infra/docker-compose.yml` | AGPL-3.0 | 2026-10 | sidecar + dostawca `searxng` |
| [trafilatura](https://github.com/adbar/trafilatura) | czysta treść artykułów, metadane, daty publikacji (`extract.py`) | Apache-2.0 | 2026-09 | skrypt |
| [Lightpanda](https://github.com/lightpanda-io/browser) | strony z JS do Markdown bez Chromium: `lightpanda fetch --dump markdown <url>`; silnik `browser_*` | AGPL-3.0 (osobny program) | 2026-10 | CLI + Hermes |
| [Camoufox](https://github.com/daijro/camoufox) 152.0.4-beta.30 + biblioteka `camoufox` 0.5.6 | zapasowa przeglądarka tylko po odmowie strony (`ostrozna.py`, wspólny skill `ostrozna-przegladarka`, [niżej](#łowca-i-sherlock-skill-ostrozna-przegladarka)) | MPL-2.0 (przeglądarka), MIT (biblioteka) | 2026-10 | skrypt |
| [Scrapling](https://github.com/D4Vinci/Scrapling) | odporny scraping (skill [H] `scrapling`) | BSD-3 | 2026-09 | CLI |
| [Docling](https://github.com/docling-project/docling) | PDF-y, raporty, tabele → Markdown | MIT | 2026-09 | skrypt |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | napisy i transkrypcje z wideo jako źródła | Unlicense | 2026-09 | CLI |
| [ExifTool](https://github.com/exiftool/exiftool) | metadane zdjęć i plików (weryfikacja pochodzenia) | GPL/Artistic (jak Perl) | 2026-05 | CLI |
| [ArchiveBox](https://github.com/ArchiveBox/ArchiveBox) | archiwum dowodów: kopia każdej kluczowej strony-źródła | MIT | 2026-09 | sidecar (opcja) |

Z Hermesa:
- **wielu dostawców wyszukiwania** (`plugins/web/`): SearXNG, DuckDuckGo, Brave, Exa, Tavily, Perplexity,
  Parallel. **Różne indeksy wyszukiwania dają niezależność źródeł**, co jest fundamentem weryfikacji krzyżowej,
- **plugins:** `openalex` (literatura naukowa i cytowania), `storm-fusion-research` (panel
  perspektyw z sędzią, pasuje do metody Sherlocka), `web-defuddle` (ekstrakcja lokalna), `source-tray` (lista odwiedzonych źródeł),
- **[H] skille:** `blocked-page-recovery`, `searxng-search`, `duckduckgo-search`,
  `scrapling`, `arxiv`, `youtube-content`, `reddit-reading`, `rss-feeds`, `blogwatcher`,
  `competitor-news-monitor`, `domain-intel`, `osint-investigation`,
- **MCP:** `wolfram` (weryfikacja liczb i obliczeń), `deepwiki`, `hugging_face`.

Inspiracje metodyczne (czytamy i przenosimy pomysły do skilli, nie instalujemy):
[GPT Researcher](https://github.com/assafelovic/gpt-researcher) (Apache-2.0),
[STORM](https://github.com/stanford-oval/storm) (MIT), [Perplexica](https://github.com/ItzCrazyKns/Perplexica) (MIT).

Odrzucone: `waybackpy` (ostatni commit 2022; do Wayback Machine wystarczy jego publiczne API przez `curl`),
`sherlock-project` (wyszukiwanie ludzi po nickach, sprzeczne z zasadą „nie śledzimy osób prywatnych”),
self-host Firecrawl (AGPL i ciężki; Firecrawl zostaje jako opcjonalny płatny dostawca przez wtyczkę Hermesa),
Crawl4AI (był sidecarem: drugi Chromium, ~3 GB obrazu i do 3 GB RAM; trafilatura + Lightpanda + `web_extract` Hermesa robią to samo na VPS 8 GB).

---

## `jarvo-studio`: Marketing i kreacja

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| FFmpeg | ffprobe dla `check_media.py` (wymiary, waga plików) | LGPL/GPL | n/d | CLI |
| [Satori](https://github.com/vercel/satori) + [resvg](https://github.com/linebender/resvg) | grafiki z HTML/JSX → SVG → PNG (posty, OG images, banery) | MPL-2.0 / Apache-2.0 | 2026-09 | skrypt |
| [rembg](https://github.com/danielgatis/rembg) | usuwanie tła ze zdjęć produktów (CPU; dodatek `rembg`) | MIT | 2026-09 | CLI |
| [sharp](https://github.com/lovell/sharp) | przycinanie i eksport w wymiarach platform | Apache-2.0 | 2026-09 | skrypt |
| [lemo-wake](https://github.com/lemomo-ai/lemo-wake) | zdjęcie albo grafika → pętla ok. 5 s (MP4, GIF, WebP) i warstwy PSD; modele ONNX na CPU (głębia, wycinanie, SAM, LaMa, ~600 MB po zgodzie właściciela); instaluje `lemo_wake.py`, skill `zywy-obraz` | CC BY-NC 4.0 (komercyjnie za zgodą autora) | 2026-10 | skrypt + skill |
| [Postiz](https://github.com/gitroomhq/postiz-app) | kolejka i harmonogram publikacji; Studio przygotowuje, Ty akceptujesz | AGPL-3.0 | 2026-09 | sidecar |
| [Penpot](https://github.com/penpot/penpot) | otwarte narzędzie do projektowania (opcjonalnie, ciężkie) | MPL-2.0 | 2026-09 | sidecar (opcja) |

Z Hermesa:
- **generowanie AI:** `plugins/image_gen/openrouter` (jeden klucz OpenRouter do obrazów),
- **[H] skille:** `baoyu-infographic`, `social-media-content-calendar`, `creative-ideation`, `humanizer`,
  `meme-generation`, `excalidraw`, `concept-diagrams`,
- **MCP:** `canva`, `figma`, `cloudinary`, `gamma`,
- **plugin:** `adspirer` (kampanie reklamowe Google/Meta/TikTok/LinkedIn), wyłącznie na poziomie A2, czyli za Twoją zgodą.

Wideo: sekcja [`jarvo-wideo`](#jarvo-wideo-wideograf).

---

## `jarvo-wideo`: Wideograf

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| FFmpeg (libass, libx264, libvidstab, fontconfig) | cały montaż: normalizacja scen, przejścia, napisy ASS, muzyka z duckingiem, loudnorm, stabilizacja nagrań z ręki, kontrola | LGPL/GPL | n/d | `film.py`, `montaz.py`, `qa_wideo.py`, `rytm.py`, `kadry.py` |
| [Matcha-TTS-PL v2](https://huggingface.co/machinekind/Matcha-TTS-PL) (rewizja `9374474`, ONNX t2, 2 × 140 MB) | domyślny polski lektor bez sieci i bez limitu: głosy `pl-PL-Matcha-Meski` i `pl-PL-Matcha-Damski` (syntetyczne) w `film.py`, `projekt.py lektor` i edytorze HQ; liczby, daty, kwoty i skrótowce czyta słowami (normalizator `jarvo_tts_pl.py`); czasy słów z Parakeeta | CC-BY-SA-4.0 | 2026-10 | `jarvo-tts` (model w obrazie; w instalacji natywnej `modele.matcha-pl` z `vendor/natywne.yaml`, przegląd 2026-10-24) |
| [edge-tts](https://github.com/rany2/edge-tts) 7.2.7 | lektor PL za darmo, bez klucza (Marek, Zofia), z czasem słów do napisów karaoke; do wyboru i zapas polskiego lektora lokalnego | LGPL-3.0 | 2026-08 | leniwa instalacja Hermesa (`tts.edge`) |
| [Paradee-8M](https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.0) v1.0 (commit `8f34b01`, int8 ONNX, 9 MB) + misaki 0.9.4 | lektor angielski bez sieci i bez limitu: głos `en-US-Paradee` w `film.py`, `projekt.py lektor` i edytorze HQ; czasy słów z Parakeeta | Apache-2.0 | 2026-10 | `jarvo-tts` (model w obrazie; w instalacji natywnej `modele.paradee`, przegląd 2026-10-24) |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) przez [onnx-asr](https://github.com/istupakov/onnx-asr) (ONNX int8 [istupakov/parakeet-tdt-0.6b-v3-onnx](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) `8f23f0c`, ~0,67 GB) | transkrypcja z czasem słów: napisy do nagrań, wybór fragmentów, test wymowy lektora | CC-BY-4.0 (model) / MIT | 2026-07 | `jarvo-stt` (pobierany przy pierwszym użyciu; w instalacji natywnej `modele.parakeet` z sumą, przegląd 2026-10-24) |
| [Silero VAD](https://github.com/snakers4/silero-vad) 6.2 (ONNX [istupakov/silero-vad-onnx](https://huggingface.co/istupakov/silero-vad-onnx) `b3e3ee3`, 2,3 MB) | wykrywanie mowy przed Parakeetem: nagranie dzielone na kawałki do 20 s, więc pamięć nie rośnie z długością | MIT | 2026-03 | `jarvo-stt` (`onnx_asr.load_vad`; w instalacji natywnej `modele.silero-vad`, przegląd 2026-10-24) |
| [YuNet](https://huggingface.co/opencv/face_detection_yunet) 2023mar (OpenCV Zoo, `3cc26e7`, 0,23 MB) | twarze w nagraniu: kadr 9:16 na mówcy, kto mówi (ruch ust), okładka rolki | MIT | 2025-06 | `twarze.py` (onnxruntime bez OpenCV; pobierany przy pierwszym użyciu z sumą; w instalacji natywnej `modele.yunet`, przegląd 2026-10-24) |
| [MODNet](https://github.com/ZHKKKe/MODNet) (ONNX [DavG25/modnet-pretrained-models](https://huggingface.co/DavG25/modnet-pretrained-models) `903cc06`, 26 MB) | maska osoby: napis obok twarzy albo za osobą (typografia) | Apache-2.0 | 2023-04 | `maska.py` (pobierany przy pierwszym użyciu z sumą; w instalacji natywnej `modele.modnet`, przegląd 2026-10-24) |
| [Pexels API](https://www.pexels.com/api/) | darmowe ujęcia i zdjęcia stock (klucz `PEXELS_API_KEY`) | Pexels License | n/d | `stock.py` |
| [Pixabay API](https://pixabay.com/api/docs/) | darmowe ujęcia i zdjęcia stock (klucz `PIXABAY_API_KEY`), cache 24 h | Pixabay Content License | n/d | `stock.py` |
| [Openverse API](https://api.openverse.org/v1/) (WordPress, bez klucza: 20 zapytań/min, 200/dzień; więcej z `OPENVERSE_CLIENT_ID`/`_SECRET`) | dźwięki do filmów: efekty, tło, muzyka; z indeksu tylko Freesound (Wikimedia to głównie wymowa słów, strony Jamendo nie dają się sprawdzić); CC0 i PDM, CC BY z podpisem, nigdy NC/ND/SA; licencja i to, że dźwięk istnieje, sprawdzane na stronie pliku (indeks pokazuje też usunięte); cache 24 h | licencja każdego pliku (CC0 / CC BY) | 2026-10 | `stock.py --typ dzwiek` |
| HyperFrames 0.8.78 (skill [H] `hyperframes`) | wideo z HTML + GSAP → MP4/WebM | Apache-2.0 | 2026-09 | CLI w obrazie (`npx hyperframes` bez pobierania; render przez Chromium obrazu, bez telemetrii) |
| [motion-broll](https://github.com/Barty-Bart/motion-graphics) | animowany B-roll do nagrania, zgrany ze słowami; panele ProRes 4444 z alfą | MIT | 2026-09 | skill + `narzedzia.py` |
| [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | cały film w 43 stylach (keynote, akwarela, anime, 3D, miedzioryt, hologram…); lektor PL przez `lektor_linie.py` | MIT | 2026-09 | skill + biblioteka (`narzedzia.py`; sample i Kokoro tylko z `JARVO_EXTRAS=lemo` w `compose/.env`, bez przebudowy obrazu: compose przekazuje zmienną do kontenera) |
| [anidoodle](https://github.com/alexgreensh/anidoodle) | rysunek kodem w 31 stylach, timelapse, HTML offline, muzyka syntezowana | Apache-2.0 | 2026-09 | skill + `narzedzia.py` |
| [Remotion skills](https://github.com/remotion-dev/skills) + iart | wideo w React: create, render, napisy; typografia, wykresy, belki, odliczanie | Remotion License / MIT | 2026-09 | skille + `narzedzia.py instaluj remotion` |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | kinowe filmy produktu: 157 kart ujęć (indeks galerii), szablon | Apache-2.0 | 2026-09 | `narzedzia.py instaluj shotcraft` |
| [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) | wzory 15 stylów motion design dla skilla `style-motion` (kreska, izometria, morph, HUD, VHS, napisy show…): kod, notatki stylów, okładki, tekstury, kroje wzorów z google/fonts | MIT | 2026-10 | `narzedzia.py instaluj mg`, `html_wideo.py --preset mg` |
| mgaudio (z [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15)) | muzyka i efekty pisane kodem: 15 przepisów gatunków (synthwave, lofi, explainer, chiptune…), forma pod kulminację i logo filmu, mastering −14 LUFS; sample VCSL (15 instrumentów) | MIT (sample CC0) | 2026-10 | dodatek `narzedzia.py instaluj mgaudio` (venv ~390 MB + sample 56 MB), `muzyka.py` |
| [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | silnik kanwy 2D: 35 stylów malarskich (od jaskini po Picassa), 8 gramatyk explainera (Kurzgesagt, Vox, tablica, historyjka, kinetyczna typografia, 3Blue1Brown, prezentacja, wykresy finansowe), wykresy, schematy, typografia, przejścia; polska nakładka (kroje z ą–ż, liczby, napisy, neutralna postać) | MIT (kroje OFL) | 2026-10 | `narzedzia.py instaluj huashu`, `/_lib/huashu/` + `/_lib/jarvo/huashu_pl.js` (`--preset jarvo`), `html_wideo.py --preset huashu` (ich strony-wzory); skille `gramatyki-explainera` (`gramatyka.py`) i `style-malarskie` (`malarz.py`); `kadry.py wzor` (mapa ruchu i siatka przejść, port `breakdown.py`) |
| [bang-motion](https://github.com/bangtutorial/bang-motion) | openery, promo, explainery z wyglądem z marki | MIT | 2026-09 | skill |
| [pixel2motion](https://github.com/nolangz/pixel2motion) | logo z obrazka → animacja SVG / GIF / MP4 | MIT | 2026-09 | skill |
| [live-panel](https://github.com/ythx-101/live-panel-skill) | żywy schemat z JSON: układ stoi, kropki po strzałkach, kroki, log, liczniki; strona offline i MP4 | MIT | 2026-10 | skill + `zywy_schemat.py`, `html_wideo.py --preset livepanel` |
| [lottie](https://github.com/diffusionstudio/lottie) | animacje Lottie na strony i aplikacje | MIT | 2026-09 | skill (Wideograf + Web) |
| [screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills) | premisa, scena, dialog, konflikt (do `scenariusz`) | MIT | 2026-09 | skille |
| [ManimGX](https://github.com/academa-labs/manimgx) 0.1.1 | animacje edukacyjne i matematyczne: kod Manim CE z `from manimgx import *` (skill [H] `manim-video`, zasady `film-z-kodu/references/manimgx.md`; dodatek `manim`, zamiast Manim CE od 2026-10-11) | MIT (kod); koło Linux jako całość GPL-3.0-or-later (x264, Mesa, Typst Apache-2.0); fonty OFL-1.1 | 2026-10 | CLI `manimgx` |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | wycinanie ciszy (dodatek `media`; bez niego `montaz.py cisza`) | Unlicense | 2026-09 | CLI |
| [Remotion](https://github.com/remotion-dev/remotion) | wideo w React (per projekt) | **Remotion License** ⚠️ | 2026-09 | per projekt |
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas) / [Revideo](https://github.com/redotvideo/revideo) | animacje i render programowy (per projekt) | MIT | 2026-07 | per projekt |

Z Hermesa: `plugins/video_gen/openrouter` i `plugins/image_gen/openrouter` (ujęcia AI, jeden klucz OpenRouter),
narzędzie `text_to_speech` (głos floty: lokalny Matcha `pl-PL-Matcha-Meski` przez `jarvo-tts`, blok `tts` z `profiles/_host/config.yaml`), skille [H] `manim-video` (silnik ManimGX), `ai-presenter-video`.

Rozważone i odrzucone: [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (MIT) jako cała aplikacja:
Streamlit, MoviePy, Redis i drugi silnik transkrypcji (~340 MB repo, dużo RAM) dublowałyby to, co flota już ma.
Wzięty pomysł pipeline'u, implementacja własna na FFmpeg. Automatyczna publikacja na platformy: tylko A2.

⚠️ **Remotion:** darmowy dla osób prywatnych i firm do 3 pracowników; większa firma potrzebuje
płatnej licencji. Domyślnie HyperFrames / Motion Canvas / Revideo.

Odrzucone: ComfyUI self-host (GPL-3.0, wymaga GPU; generowanie idzie przez API),
`rhasspy/piper` (projekt przeniesiony do `OHF-Voice/piper1-gpl` na GPL-3.0; lektor PL robi lokalny Matcha-TTS-PL v2 (zapas: Edge TTS), angielski bez sieci Paradee, a Kokoro, tylko EN/ZH, jest częścią lemo-opuscar).

---

## `jarvo-ads`: Specjalista Ads

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| Skarbiec (`jarvo-skarbiec`, własny) | tokeny Meta/Google, polityka budżetu, koperty i kody zgody; agent nie ma tokenów | MIT | n/d | sidecar (**w planie, jeszcze nie zbudowany**: brak usługi w `infra/docker-compose.yml`) |
| `ads.py` | jedyne wejście do kont reklamowych przez Skarbiec; bez niego kod wyjścia 3 | własny kod | n/d | skrypt |
| `eksport.py`, `planer.py`, `eksperyment.py` | eksporty CSV z Ads Managera / Google Ads, planowanie budżetu testu, werdykt testu A/B/C | własny kod | n/d | skrypt |

Bez Skarbca agent pracuje na eksportach CSV. Wydatki tylko na poziomie A2, w kopercie zatwierdzonej kodem ([ADS.md](ADS.md)).

---

## `jarvo-lowca`: Łowca leadów

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [API KRS](https://api-krs.ms.gov.pl) (Ministerstwo Sprawiedliwości) | odpisy firm (NIP, PKD, adres, kapitał, e-mail i www, jeśli podane) i dzienny biuletyn wpisów | dane publiczne | n/d | `krs.py` |
| [CEIDG API v3](https://dane.biznes.gov.pl) (Hurtownia danych CEIDG i Biznes.gov.pl, MRiT) | jednoosobowe działalności po PKD, miejscu, statusie i dacie rozpoczęcia; szczegóły: PKD, telefon, e-mail, www podane w rejestrze (biała lista pól, minimum danych osoby); limit 1000 zapytań/h | dane publiczne (open data), darmowy token `CEIDG_TOKEN` | n/d | `ceidg.py szukaj`, `firma`, `sprawdz`; healthcheck `ceidg.py --help` |
| [e-Zamówienia BZP](https://ezamowienia.gov.pl) (API tablicy ogłoszeń) | ogłoszenia o zamówieniach i wyniki ze zwycięzcą (NIP); odcina za serię ciężkich zapytań, stąd pauza 4 s | dane publiczne | n/d | `przetargi.py bzp`, healthcheck `przetargi.py sprawdz bzp` |
| [TED API v3](https://api.ted.europa.eu) | przetargi unijne z CPV | dane publiczne (reuse UE) | n/d | `przetargi.py ted`, healthcheck `przetargi.py sprawdz ted` |
| `strona.py`, `leady.py`, `lowca_lib.py` | kontakt opublikowany na stronie firmy (`robots.txt`), także z danych ukrytych w HTML (JSON-LD, Next.js, Nuxt), technologie, odcisk strony; lista leadów, ocena wg ICP, monitoring | własny kod | n/d | skrypt |
| [Camoufox](https://github.com/daijro/camoufox) (`ostrozna.py`) | jedna próba odczytu strony firmy, która odmówiła zwykłej przeglądarce ([niżej](#łowca-i-sherlock-skill-ostrozna-przegladarka)) | MPL-2.0 | 2026-10 | wspólny skill `ostrozna-przegladarka` |
| `zrodlo.py`, `har.cjs` | rozpoznanie nowego źródła: nagranie ruchu strony do HAR (`robots.txt`, uczciwy UA, playwright-core), żądania z danymi, różnice dwóch nagrań, schemat sumy odpowiedzi (pola opcjonalne, `null`, niespójne typy) | własny kod | n/d | skrypt, skill `rozpoznanie-zrodla` |

Źródła bez kluczy, oprócz CEIDG: darmowy token właściciela w Kluczach profilu `jarvo-lowca`
([LEADY.md](LEADY.md#token-ceidg)). Odmowa źródła (403/429, strona antybotowa) = blokada, bez obchodzenia; w CEIDG
429 to limit godzinowy, który skrypt przeczekuje, a 401/403 to zły token ([LEADY.md](LEADY.md)). Jedyny wyjątek:
publiczna strona, którą zwykła przeglądarka dostała jako odmowę, ma jedną próbę Camoufoxem (`ostrozna-przegladarka`);
API rejestrów (KRS, CEIDG, BZP, TED) go nie dostają.

---

## `jarvo-mobile`: Twórca aplikacji

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [iTunes Search API](https://performance-partners.apple.com/search-api) | aplikacje w polskim App Store (lookup po ID i bundleId, wyszukiwanie z `lang=pl_pl`), kanał RSS opinii; ~20 zapytań/min, więc pauza 4 s także między procesami | dane publiczne | n/d | `audyt_mobilny.py`, healthcheck `audyt_mobilny.py sprawdz` |
| strona aplikacji w [App Store](https://apps.apple.com) | status przedsiębiorcy DSA, etykiety prywatności, link do polityki | strona publiczna | n/d | `audyt_mobilny.py` |
| strona szczegółów [Google Play](https://play.google.com/store/apps) | ocena, liczba ocen, ostatnia aktualizacja, pobrania, Data safety (tylko `/store/apps/details`, które robots.txt dopuszcza) | strona publiczna | n/d | `audyt_mobilny.py` |
| [Digital Asset Links API](https://developers.google.com/digital-asset-links) i CDN Apple (`app-site-association.cdn-apple.com`) | potwierdzenie App Links i kopii pliku Universal Links | API publiczne | n/d | `audyt_mobilny.py` |
| `decyzja.py`, `mobile_lib.py` | natywna czy PWA (19 funkcji, 5 rozwiązań, koszty); grzeczne HTTP z robots.txt, pauzą i pamięcią odpowiedzi; wspólna wersja EAS CLI i odczyt JSON skryptów Mobile | własny kod | n/d | skrypt |
| [Expo SDK 57](https://github.com/expo/expo) (szablon `templates/expo-jarvo`) | aplikacje React Native z expo-router; `aplikacja.py nowa/ustaw/sprawdz/eksport/podglad` | MIT | 2026-09 | per projekt (npm, `npx expo install`) |
| [expo-doctor](https://github.com/expo/expo/tree/main/packages/expo-doctor) 1.21.1 | konfiguracja i zależności projektu (`aplikacja.py sprawdz`) | MIT | 2026-09 | `npx`, przy pierwszym użyciu |
| [eas-cli](https://github.com/expo/eas-cli) 24.7.0 | projekt w organizacji właściciela i EAS Update do podglądu w Expo Go (`aplikacja.py expo-go`, token robota `EXPO_TOKEN`); wersja w `mobile_lib.EAS_CLI` dla wszystkich skryptów, nadpisywana przez `JARVO_EAS_CLI` | MIT | 2026-09 | `npx`, przy pierwszym użyciu |
| [adb](https://developer.android.com/tools/adb) (pakiet Debiana w obrazie i na VPS; natywnie platform-tools r37.0.1 od Google z [`vendor/natywne.yaml`](../vendor/natywne.yaml), przy pierwszym użyciu; przegląd 2026-10-24) | Android przez adb: instalacja, zrzuty, logi, testy wrogie (`urzadzenie.py`) | Apache-2.0 | 2026-09 | obraz floty |
| [Redroid](https://github.com/remote-android/redroid-doc) 14.0.0 (`14.0.0_64only-240527`) | telefon testowy na serwerze bez KVM (Android 14 w kontenerze, moduł `binder_linux`) | Apache-2.0 | 2026-10 | usługa `android` (`jarvo android on`) |
| [docker-android](https://github.com/HQarroum/docker-android) `api-33` | telefon testowy przy KVM: oficjalny emulator Google z usługami Google | MIT | 2026-10 | usługa `android-emulator` (`jarvo android on`) |
| [ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy) (commit `cd6cea6`) | ekran telefonu testowego w przeglądarce (podgląd, klikanie), za proxy HQ `:9122` z tokenem | MIT | 2026-10 | usługa `android-ekran` (`infra/android/`; Docker i VPS) |
| [scrcpy](https://github.com/Genymobile/scrcpy) 5.0.1 | instalacja natywna: ekran i sterowanie telefonem w osobnym oknie zamiast ws-scrcpy w HQ (I24); przegląd 2026-10-24: `SHA256SUMS.txt` z podpisem GPG zgodny, bez telemetrii, bez podpisu Authenticode; Linux tylko x86_64 | Apache-2.0 (+ LGPL: FFmpeg, libusb) | 2026-10 | [`vendor/natywne.yaml`](../vendor/natywne.yaml), przy pierwszym użyciu |
| [GitHub Actions `macos-26`](https://github.com/actions/runner-images) | symulator iOS: zrzuty jasny / ciemny / duża czcionka, logi (`ios_ci.py`, `templates/ci/jarvo-ios.yml`) | usługa GitHub | 2026-09 | workflow w repo aplikacji właściciela |
| `zgodnosc.py`, `ikony.cjs` (sharp), `zrzuty.cjs` (playwright-core, axe-core) | profil zgodności → wymagania sklepów; ikony bez alfy, adaptacyjne i ekran startowy; zrzuty iPhone 17 Pro Max i Pixel w obu motywach z kontrolami | własny kod | n/d | skrypt |

Wszystkie źródła bez kluczy. Odmowa źródła = blokada, bez obchodzenia; opinii z Google Play nie pobieramy ([MOBILE.md](MOBILE.md)).

---

## `jarvo-operator`: Operator

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| `computer_use` Hermesa | patrzenie (`capture`: drzewo dostępności, znaczniki na zrzucie, obraz) i działania na ekranie (klik, pisanie, klawisze, przewijanie, `set_value`) z werdyktem po działaniu | MIT | n/d | toolset `computer_use`; sterownik przez `HERMES_CUA_DRIVER_CMD` = bramka `komputer/jarvo_cua.py` |
| Komputer Jarva (`infra/komputer`) | osobny pulpit Xvnc z Chromium w kontenerze bez kluczy floty; wejście z twardymi zasadami (logowanie, płatność, wysyłka, pola haseł i kart = człowiek), ukrywanie sekretów, dziennik | własny kod (MIT) | n/d | usługa compose `komputer`, włącza właściciel: `jarvo komputer on` |
| [cua-driver](https://github.com/trycua/cua) 0.21.0 | sterownik ekranu w Komputerze (AT-SPI, zrzuty, wejście w tle); telemetria i aktualizacje wyłączone, suma SHA-256 w `vendor/zrodla.yaml` | MIT | 2026-10 | binarka w obrazie `jarvo-komputer` |
| wtyczka `jarvo-komputer` (`komputer/plugin`) | narzędzie `komputer`: `stan` (czy Komputer działa, pauza, kto steruje), `dziennik` (ostatnie działania bez treści), `oddaj` (prośba do właściciela jako pauza z powodem); wznowić nie umie | własny kod (MIT) | n/d | wtyczka Hermesa, healthcheck `komputer/plugin/__init__.py stan` (opcjonalny) |

Bez terminala, wykonywania kodu, przeglądarki Hermesa i delegowania. Stałe zgody na działania w tle
(`cua:<działanie>:background`) i na działania wejścia na wierzchu w aktywnym oknie (`cua:<działanie>:foreground`);
okno na wierzch zatwierdza człowiek. Szczegóły: [KOMPUTER.md](KOMPUTER.md).

---

## `jarvo-reka`: Prawa ręka

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Pandoc](https://github.com/jgm/pandoc) | konwersje dokumentów (MD ↔ DOCX ↔ PDF ↔ HTML) | GPL-2.0 | 2026-09 | CLI |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | mapa dużego repo: kto woła funkcję, wpływ zmian (graf wywołań, lokalnie, bez klucza i tokenów) | MIT | 2026-09 | skill `graf-kodu` (tryb poleceń, pobierany przy pierwszym użyciu) |
| Chromium (z obrazu) + pandoc | Markdown/HTML/DOCX → PDF (`to_pdf.py`), bez osobnej usługi | BSD / GPL-2.0 | n/d | skrypt |
| [LibreOffice](https://www.libreoffice.org) | XLSX/PPTX/DOC → PDF (dodatek `office`) | MPL-2.0 | 2026-09 | CLI |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | OCR skanów | MPL-2.0 | 2026-09 | CLI |
| [Docling](https://github.com/docling-project/docling) | czytanie dokumentów, tabel, PDF-ów (dodatek `docling`) | MIT | 2026-09 | skrypt |
| [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF) | operacje na PDF (łączenie, podpisy, kompresja) | MIT | 2026-09 | sidecar (opcja) |

Z Hermesa: pełny katalog skilli [H] + skille snajperów (tylko do odczytu), plugins
`document-reader`, `image-utils`, opcjonalnie `openmail` (własny adres e-mail agenta, A2).
MCP według Twoich narzędzi (np. `notion`, `todoist`, `calendly`, `airtable`), do ustalenia.

---

## `jarvo`: Main Judge

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| Kanban Hermesa | tablica zleceń, statusy `review` / `request_changes` | MIT (Hermes) | n/d | toolset `kanban` |
| [Langfuse](https://github.com/langfuse/langfuse) | ślady przebiegów, koszty per agent, oceny sędziego | MIT (core) | 2026-09 | plugin `langfuse` + sidecar |
| [promptfoo](https://github.com/promptfoo/promptfoo) | red team floty (`scripts/redteam.sh`, ataki z `security/redteam/`); evals z `evals/` robi `scripts/run-evals.py` | MIT | 2026-09 | CLI w kontenerze (0.123.1, instalowany przy pierwszym użyciu) |
| [DeepEval](https://github.com/confident-ai/deepeval) | alternatywa dla promptfoo (metryki LLM-sędziego) | Apache-2.0 | 2026-09 | do oceny |

Z katalogu wtyczek Hermesa do oceny w fazie 6: `afterforge` (zamienia porażki agentów
w przejrzane testy regresji), `gonogo` (wynik evali → decyzja o wdrożeniu).

---

## Wszyscy agenci: skill `konwersja-plikow`

Wspólny skill floty (`shared/skills/konwersja-plikow/`, wzór: [convt](https://github.com/opencoredev/convt), AGPL-3.0,
bez jego kodu): `konwertuj.py` wybiera najtańszą trasę przez silniki, które są w obrazie (bez silnika trasa znika).
Metadane (miejsce GPS, telefon, daty, autor, opisy) nie przechodzą przez żadną zamianę zdjęcia, filmu ani dźwięku,
a `--usun-metadane` daje ten sam plik bez nich, bez przekodowania; `--metadane` pokazuje, co plik mówi o człowieku.
Dokumenty też: PDF (exiftool + qpdf przepisuje plik) i DOCX, XLSX, PPTX, ODT, ODS, ODP (właściwości w XML czyści
sam skrypt: autor, firma, program, szablon, daty, historia zmian, własne pola); komentarze i śledzone zmiany
z nazwiskami skrypt tylko wskazuje.

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Pillow](https://github.com/python-pillow/Pillow) + [pillow-heif](https://github.com/bigcat88/pillow_heif) (z obrazu Hermesa) | zdjęcia: HEIC z iPhone'a, AVIF, WebP, PNG, JPG, TIFF, ICO, PSD (odczyt); zdjęcia → PDF | MIT-CMU / BSD-3 | 2026-09 | skrypt |
| FFmpeg (z obrazu Hermesa) | wideo, audio, GIF, SVG → PNG; H.264 z MOV do MP4 samym przepakowaniem | LGPL/GPL | n/d | skrypt |
| [Ghostscript](https://www.ghostscript.com) (z OCRmyPDF) | PDF → obrazy stron, tekst, mniejszy PDF | AGPL-3.0 (osobny program) | 2026-09 | CLI |
| [qpdf](https://github.com/qpdf/qpdf) (natywnie 12.4.2: zip z wydania, [`vendor/natywne.yaml`](../vendor/natywne.yaml); przegląd 2026-10-24) | łączenie PDF, liczba stron, przepisanie PDF po usunięciu metadanych | Apache-2.0 | 2026-09 | CLI |
| [Pandoc](https://github.com/jgm/pandoc) (natywnie 3.12.1: zip lub tar.gz z wydania; przegląd 2026-10-24) | DOCX, ODT, Markdown, HTML, EPUB, RTF między sobą (filtr Lua bez plików z dysku i z sieci; natywnie z `--data-dir`, bez katalogu danych pandoca właściciela) | GPL-2.0-or-later | 2026-10 | CLI |
| [ExifTool](https://exiftool.org) (w obrazie Jarva; natywnie 13.59: Windows zip z Perlem jako `exiftool.exe`, macOS i Linux paczka Perla, `EXIFTOOL_HOME`; przegląd 2026-10-24) | metadane: odczyt, usuwanie ze zdjęć bez przekodowania (piksele, profil kolorów i obrót zostają) i z PDF, kontrola wyniku każdej zamiany | GPL/Artistic (jak Perl) | 2026-05 | CLI |
| Chromium (z obrazu) | HTML → PDF (serwer druku tylko z katalogu dokumentu, bez sieci) | BSD | n/d | CLI |
| [LibreOffice](https://www.libreoffice.org) | Excel, PowerPoint, stare .doc/.xls/.ppt, CSV ↔ XLSX (dodatek `office`) | MPL-2.0 | 2026-09 | CLI |

---

## Wszyscy agenci: skill `odczyt-ekranu`

Wspólny skill floty (`shared/skills/odczyt-ekranu/`, decyzja właściciela 2026-10-17): `ocr.py` czyta tekst ze zrzutu
ekranu, skanu, zdjęcia, PDF albo klatki filmu (`--czas`) na serwerze, bez sieci i bez tokenów modelu. Wynik: sam tekst,
`--format json` (linie z ramką w pikselach i pewnością), `--format md` (Markdown z układu strony) albo `--szukaj`
(gdzie jest napis: ramka i środek do kliknięcia, bez wielkości liter i ogonków). Zwykły `python3` sam przechodzi do
venvu OCR; gniazda są zablokowane w czasie odczytu. Pomiar w kontenerze (4 rdzenie): polski dokument 0,4 s Indra
wobec 1,9 s Tesseracta przy tych samych polskich znakach, ciemne zrzuty ekranu 0,3–0,5 s wobec 1,1–1,9 s,
chiński tekst czyta tylko Indra.

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Indra OCR](https://github.com/datalab-to/indra) 0.3.2 (datalab-to) | główny silnik: wykrycie linii, rozpoznanie, kolejność czytania, Markdown z układu, obrót strony, pismo łacińskie, cyrylica, greka, dewanagari, chińskie | kod Apache-2.0; modele zmodyfikowana OpenRAIL-M (do 20 mln USD przychodu, bez produktu konkurującego z Datalab) | modele `ed345c7` (tag `v3.1.1`) | venv `/opt/jarvo/venvs/ocr` ([`requirements-ocr.txt`](../infra/python/requirements-ocr.txt), sha256, `--no-deps` bez `huggingface_hub`), modele `/opt/jarvo/models/indra-ocr` (`INDRA_OCR_MODEL_DIR`) |
| onnxruntime 1.31.0, opencv-python-headless, pypdfium2, numpy | wnioskowanie modeli na CPU, obraz, PDF | MIT / Apache-2.0 / BSD | n/d | ten sam venv (~0,25 GB) |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) (apt, pol + eng; natywnie 5.5.3 z conda-forge przez [pixi](https://github.com/prefix-dev/pixi) 0.83.0 z `vendor/pixi/tesseract/pixi.lock`, języki pol, eng, osd z [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) 4.1.0; przegląd 2026-10-24) | zapas, gdy Indry brak albo padnie, i `--silnik tesseract` | Apache-2.0 | n/d | CLI (`tsv`; natywnie TSV przez `-c tessedit_create_tsv=1`, bo na Windows config `tsv` się nie znajduje) |
| FFmpeg, Ghostscript, qpdf (z obrazu) | klatka filmu; strony PDF dla Tesseracta | LGPL/GPL, AGPL-3.0, Apache-2.0 | n/d | CLI |

---

## Web, Studio, Wideograf: skill `izometria`

Wspólny skill (`shared/skills/izometria/`): klikalne figury izometryczne ze świeceniem w jednym pliku HTML (czysty SVG,
bez bibliotek), PNG w chwili t i film. Szablon, kernel i przykłady z iso-glow bez zmian w `assets/iso-glow/`; `iso.py`
dokłada polskie napisy, krój OFL zamiast Google Fonts, kolor marki z kontrastem na obu motywach, tryb kadru do
`<iframe>`, kontrolę figur i zegar wirtualny (`iso_jarvo.js`), dzięki któremu PNG i film wychodzą zawsze tak samo.
`iso.py flota` robi figurę floty z `fleet.yaml` (`iso_flota.js`: mostek Jarva, pokoje agentów, demo = droga zlecenia).

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [iso-glow](https://iso-glow.vercel.app) (April Zhu) na [iso-figure](https://github.com/MrBongoC/ai-iso-skill) (Tolga Cohce) | szablon galerii, kernel izometrii, klasy świecenia, palety, 2 przykłady | MIT | paczka 2026-10 (`1e69ce1…`), iso-figure 2026-10-04 | kopia w skillu |
| JetBrains Mono (z krojów HQ, `hq/web/fonts/kroje`) | krój figur z polskimi znakami, w pliku strony | OFL-1.1 | n/d | build kopiuje obok `iso.py` |
| Chromium + playwright-core (Node, z obrazu) | `iso.py png` i `sprawdz --przegladarka` (`iso_render.cjs`) | BSD / Apache-2.0 | n/d | skrypt |
| `html_wideo.py` Wideografa | `iso.py wideo`: film klatka po klatce (`--preset jarvo`) | nasz | n/d | skrypt |

---

## Łowca i Sherlock: skill `ostrozna-przegladarka`

Wspólny skill (`shared/skills/ostrozna-przegladarka/`, decyzja właściciela z 2026-10-11): gdy zwykła droga dostała
odmowę (403/429, „Just a moment…”, „Human Verification”, captcha), `ostrozna.py <url>` czyta tę jedną stronę
Camoufoxem: Firefoksem, który pokazuje spójny odcisk zwykłej przeglądarki (bez `navigator.webdriver`). Wynik:
Markdown głównej treści (trafilatura), HTML po JavaScripcie albo zrzut. Nigdy domyślnie i nigdy do API rejestrów.

Granice w kodzie skryptu: robots.txt czytany tą samą przeglądarką (zakaz albo robots.txt niedostępny = blokada),
tylko http(s) i adresy publiczne, jedna przeglądarka naraz na serwerze, co najmniej 20 s między stronami domeny
i najwyżej 30 stron domeny na dobę, czysty profil bez ciasteczek, kont, proxy i dodatków. Strona „sprawdzamy, czy
jesteś człowiekiem” ma do 15 s, żeby sama przepuścić przeglądarkę; skrypt niczego nie klika i nie rozwiązuje captchy.
Captcha, 401/403/429 albo sam formularz logowania = kod 3 (blokada, koniec próby).

Pomiary (2026-10, Camoufox 152.0.4-beta.30): CreepJS i BrowserScan „Normal” (Chromium: „Robot”), OLX otwiera się
(Chromium: „Human Verification”). **Serwisy za Cloudflare zwykle zostają zablokowane**: GoWork (robots.txt 403),
Aleo i rejestr.io (403); G2 raz przepuszcza, raz nie. Wyniki Google zabrania robots.txt, więc skrypt ich nie czyta
(wyszukiwanie: SearXNG). RAM ok. 0,8 GB na czas jednej strony (Lightpanda ~0,03 GB, Chromium ~0,1–0,4 GB).

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Camoufox](https://github.com/daijro/camoufox) 152.0.4-beta.30 (binarka z wydania, SHA-256 amd64 i arm64 w `infra/Dockerfile`) | Firefox z podmienionym odciskiem przeglądarki; w obrazie bez fontów macOS i Windows z paczki, więc udaje tylko Linuksa | MPL-2.0 | 2026-10 | `/opt/jarvo/camoufox`, healthcheck `ostrozna.py --sprawdz` |
| biblioteka [`camoufox`](https://pypi.org/project/camoufox/) 0.5.6 + [Playwright](https://github.com/microsoft/playwright-python) 1.62.0 | odcisk przeglądarki (BrowserForge) i sterowanie Firefoksem; Playwright na Node z obrazu | MIT / Apache-2.0 | 2026-09 | venv `/opt/jarvo/venv` |
| GTK 3 (`libgtk-3-0t64`, apt) | biblioteka, bez której Firefox nie startuje, także bez okna | LGPL-2.1 | n/d | pakiet systemowy |

---

## Web, Wideograf, Mobile: skill `warsztat-3d`

Wspólny skill (`shared/skills/warsztat-3d/`): model 3D z kodu Pythona (build123d), wymiary w mm, parametry na górze
skryptu. `cad.py zbuduj` daje STEP (CAD, wycena), STL i 3MF (druk 3D; zestaw: osobny STL każdej części), GLB
(strona, aplikacja, scena Three.js) i raport JSON (wymiary, objętość, masa w materiale, poprawność, części);
`cad.py podglad` robi PNG, a `cad.py obrot` film MP4 z obracającym się modelem. Budowa idzie w osobnym venvie
bez sieci (`cad_model.py` blokuje gniazda i `export_to_pcbway`); podgląd to strona z Three.js w Chromium z obrazu
(`cad_render.cjs`, WebGL na CPU, każdy adres poza stroną odrzucony). Blender: na razie nie (decyzja właściciela,
może później jako dodatek obrazu).

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [build123d](https://github.com/gumyr/build123d) 0.13.0 | modelowanie bryłowe z kodu, eksport STEP, STL, glTF, 3MF | Apache-2.0 | `38effd3` (tag `v0.13.0`) | venv `/opt/jarvo/venvs/cad` ([`requirements-cad.txt`](../infra/python/requirements-cad.txt), sha256, `--no-deps`) |
| [OCP](https://github.com/CadQuery/OCP) (`cadquery-ocp-novtk` 8.0.1.1.0) | jądro OpenCascade 8.0 (bryły, operacje logiczne, siatki) | Apache-2.0; OpenCascade LGPL-2.1 z wyjątkiem | `a6d078c` (tag `8.0.1.1`) | ten sam venv (~0,38 GB z 0,77 GB) |
| [three.js](https://github.com/mrdoob/three.js) 0.186.1 | podgląd PNG i klatki filmu obrotu (GLTFLoader, RoomEnvironment, krawędzie) | MIT | `9b4a2ac` (r186) | npm w obrazie ([`package.json`](../infra/node/package.json)) |
| Chromium + playwright-core (Node, z obrazu) | strona podglądu `cad_podglad.html` (SwiftShader) | BSD / Apache-2.0 | n/d | `cad_render.cjs` |
| FFmpeg (z obrazu) | klatki → MP4 (H.264, yuv420p, faststart) | LGPL/GPL | n/d | `cad.py obrot` |

---

## Infrastruktura (VPS)

| Narzędzie | Po co | Licencja | Ostatni commit |
|---|---|---|---|
| [Honcho](https://github.com/plastic-labs/honcho) | wspólna pamięć o Tobie (self-host) | AGPL-3.0 | 2026-09 |
| [Caddy](https://github.com/caddyserver/caddy) | HTTPS reverse proxy (tylko gdy potrzebny) | Apache-2.0 | 2026-09 |
| [Tailscale](https://github.com/tailscale/tailscale) | prywatny dostęp do VPS | BSD-3 | 2026-09 |
| [restic](https://github.com/restic/restic) | szyfrowane backupy | BSD-2 | 2026-09 |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) 2.5.6 | healthchecki i alerty | MIT | 2026-10 |
| [Beszel](https://github.com/henrygd/beszel) 0.21.0 | monitoring zasobów | MIT | 2026-10 |
| [CrowdSec](https://github.com/crowdsecurity/crowdsec) | ochrona przed atakami | MIT | 2026-09 |
| [cua-driver](https://github.com/trycua/cua) 0.21.0 (`cua-driver-rs`) | sterownik ekranu Komputera Jarva dla narzędzia `computer_use` (drzewo dostępności, zrzuty, klik, pisanie); sumy SHA-256 w `infra/komputer/Dockerfile` | MIT | 2026-10 |
| [TigerVNC](https://github.com/TigerVNC/tigervnc) Xvnc + xfwm4 + Chromium (pakiety Debiana) | pulpit Komputera Jarva (`infra/komputer`, `jarvo komputer on`): ekran tylko na gnieździe unix, filtr ruchu do sieci lokalnej | GPL-2.0 / BSD-3 | 2026-10 |
| [PyGObject](https://gitlab.gnome.org/GNOME/pygobject) `python3-gi` + `gir1.2-atspi-2.0` (pakiety Debiana) | wejście sterownika Komputera (`infra/komputer/wejscie.py`): fokus klawiatury i element w punkcie z AT-SPI dla twardych zasad | LGPL-2.1+ | 2026-10 |

---

## Polityka licencji

| Licencja | Zasada |
|---|---|
| MIT, Apache-2.0, BSD, Unlicense | bez ograniczeń |
| MPL-2.0, LGPL | bez ograniczeń przy używaniu; zmiany w samych plikach biblioteki udostępniamy, jeśli ją rozpowszechniamy |
| GPL | używamy jako osobnych programów (CLI, kontenery); nie wklejamy ich kodu do naszego |
| AGPL (SearXNG, Honcho, Postiz) | prywatny self-hosting jest OK; gdybyśmy udostępniali *zmodyfikowaną* wersję innym przez sieć, musimy udostępnić źródła |
| Remotion License | darmowa dla osób prywatnych i firm ≤ 3 pracowników; inaczej płatna |

Każde nowe narzędzie przed dodaniem do `toolbox.yaml`: licencja, aktywność (ostatni commit
w ciągu 12 miesięcy albo świadomy wyjątek), przypięta wersja i healthcheck.

---

## Stan instalacji (co naprawdę jest w obrazie `jarvo-hermes`)

Źródło prawdy: [`infra/Dockerfile`](../infra/Dockerfile), [`infra/node/package.json`](../infra/node/package.json),
[`infra/python/requirements-tools.txt`](../infra/python/requirements-tools.txt), sidecary w
[`infra/docker-compose.yml`](../infra/docker-compose.yml). Healthchecki: `scripts/healthcheck.sh`.

| Warstwa | Gdzie | Co |
|---|---|---|
| obraz Hermesa | `/opt/hermes` | Python 3.13 Hermesa (Debian 13; nie ruszamy), Node, `uv`, ffmpeg/ffprobe, Chromium |
| pakiety systemowe | apt | pandoc, qpdf, ocrmypdf + tesseract (pol, eng), exiftool, jq, sqlite3, adb, GTK 3 (dla Camoufoxa), fonty z polskimi znakami |
| przeglądarki | `/usr/local/bin/lightpanda`, `/usr/local/bin/chromium` (`CHROME_PATH`), `/opt/jarvo/camoufox` | Lightpanda dla `browser_*` agentów (agent-browser); jedna Chromium z obrazu Hermesa dla zrzutów, PDF, Lighthouse, Playwright i dembrandta; Camoufox (Firefox) tylko dla `ostrozna.py` Łowcy i Sherlocka po odmowie strony |
| narzędzia Node | `/opt/jarvo/node/node_modules` (`NODE_PATH`, `.bin` w `PATH`) | agent-browser, lighthouse, axe-core, playwright-core, sharp, svgo, favicons, linkinator, html-validate, dembrandt, inspo-mcp (serwer MCP Weba), three (podgląd warsztatu 3D) |
| narzędzia Pythona | venv `/opt/jarvo/venv` (Python 3.12, na końcu `PATH`) | trafilatura, yt-dlp, onnx-asr (Parakeet), misaki + spaCy `en_core_web_sm` (lektor Paradee), phonemizer + espeak-ng (`espeakng-loader`, fonemy lektorów), camoufox + Playwright 1.62 (sterownik na Node z obrazu); dodatki `JARVO_EXTRAS`: rembg, auto-editor, docling, manim |
| warsztat 3D | venv `/opt/jarvo/venvs/cad` (Python 3.12) | build123d 0.13.0 na OpenCascade 8.0 (OCP), ~0,77 GB; koła z sumami sha256 ([`requirements-cad.txt`](../infra/python/requirements-cad.txt)), build kończy się próbną częścią (STEP, STL, GLB, 3MF) |
| odczyt ekranu (OCR) | venv `/opt/jarvo/venvs/ocr` (Python 3.12), modele `/opt/jarvo/models/indra-ocr` | Indra OCR 0.3.2 (onnxruntime, opencv-headless, pypdfium2), ~0,25 GB + modele ONNX ~37 MB; koła z sumami sha256 ([`requirements-ocr.txt`](../infra/python/requirements-ocr.txt), bez `huggingface_hub`), modele z sumami sha256 z przypiętej rewizji, build kończy się próbnym odczytem bez sieci |
| claude-seo | `/opt/jarvo/vendor/claude-seo` (`CLAUDE_PLUGIN_ROOT`, własny venv) | skrypty skilli SEO, ten sam commit co w locku skilli |
| sidecary | sieć `jarvo-net` | SearXNG (`SEARXNG_URL`) + Valkey 8.1.10 (obrazy przypięte wersją i digestem w `infra/docker-compose.yml`, [SOURCES.md](SOURCES.md#1-platforma)); nic więcej (reszta działa w obrazie na żądanie) |

Zasady obrazu Hermesa, których pilnujemy (`make pins` sprawdza piny przed zmianą):
- o dodaniu wersji decyduje przegląd źródła, nie jej wiek ([SOURCES.md](SOURCES.md#przegląd-przed-dodaniem-każde-źródło-osobno));
  globalny npmrc obrazu ma `min-release-age = 14`, ale npm 11.17 z obrazu instaluje dokładne piny bez względu na wiek
  (sprawdzone 2026-10-11: `eas-cli@24.12.1` sprzed 3 dni), a uv obrazu (`exclude-newer`) zwalniamy dla dokładnych
  pinów w `narzedzia.py` i `lemo_wake.py`. Wersje npm muszą być zgodne z Node obrazu (`engine-strict`),
- interpreter Pythona dla venv pobiera `uv` do `/opt/jarvo/uv-python` (nie do `/root`, niedostępnego dla `hermes`),
- Camoufox: binarka z wydania przypięta wersją i SHA-256 (amd64, arm64), bez fontów macOS i Windows z paczki (0,9 GB);
  build kończy się startem bez sieci (`navigator.webdriver` = false). Biblioteka `camoufox` dostaje `executable_path`
  i `ff_version`, więc niczego nie pobiera przy starcie (dodatek uBlock wyłączony, GeoIP wyłączone),
- jedna Chromium: `playwright-core` (także dembrandta, przez `overrides`) i Playwright claude-seo są przypięte do wersji,
  której przeglądarka jest w obrazie Hermesa (chrome-headless-shell rewizji 1243, Chromium 153, na amd64 i arm64);
  Dockerfile sprawdza, że ta rewizja jest w obrazie, a `/usr/local/bin/chromium` wskazuje tę samą binarkę, i uruchamia
  ją testowo. Niczego nie dociąga: Playwright nie sprawdza sumy pobranej przeglądarki, więc brak rewizji zatrzymuje build,
- `AGENT_BROWSER_EXECUTABLE_PATH` celowo nieustawione: agent-browser użyłby go też dla silnika lightpanda,
- agent-browser bez serwera podglądu: demon agent-browsera (0.38.1, tak samo 0.39.1) przy starcie każdej sesji otwiera
  na 127.0.0.1 serwer WebSocket/HTTP bez hasła (obraz strony, polecenia z wynikami i wpisywanymi wartościami,
  wstrzykiwanie myszy i klawiatury, zakładanie sesji), a strona otwarta w przeglądarce agenta mogłaby go znaleźć.
  Zmienną ani flagą się go nie wyłączy. Nakładka [`/opt/jarvo/bin/agent-browser`](../infra/bin/agent-browser), pierwsza
  w PATH (Hermes bierze ją dla `browser_*`, `/usr/local/bin/agent-browser` też na nią wskazuje), przed każdym
  poleceniem wysyła `stream disable` z tymi samymi flagami globalnymi: nowy demon startuje bez serwera, zanim
  otworzy stronę (~0,2 s przy starcie sesji, ~10 ms na kolejne polecenie). Gdy wyłączyć się nie da, polecenie nie
  idzie dalej; `stream enable`, `dashboard` i `mcp` odrzuca. Zostaje rzadki przypadek demona uruchomionego od nowa
  w trakcie jednego polecenia: ma serwer do następnego polecenia, które go wyłącza,
- Lightpanda (1.0.0, przegląd 2026-10-11): obraz `lightpanda/browser` przypięty digestem indeksu (amd64 + arm64),
  z niego tylko binarka po `strip` (74 MB). Lightpanda domyślnie wysyła telemetrię (identyfikator instalacji i liczniki
  do `telemetry.lightpanda.io`) i raporty awarii (`curl` do `crash.lightpanda.io`); obraz ustawia
  `LIGHTPANDA_DISABLE_TELEMETRY=1` (wyłącza oba) i `LIGHTPANDA_DISABLE_CORE_DUMP=1`, a Hermes przekazuje je
  agent-browserowi. Sprawdzanie nowej wersji tylko na żądanie (`lightpanda version --check`). Od 1.0.0 CORS w `fetch`/XHR
  jest wymuszany jak w Chromium,
- bez cache instalatorów w warstwach (`UV_NO_CACHE`, `npm cache clean`) i bez `chmod -R` (kopiuje całe drzewo do nowej warstwy),
- auto-editor (dodatek `media`) pobiera swoją binarkę przy budowie obrazu (w runtime katalog pakietów jest tylko do odczytu),
- ManimGX (dodatek `manim`): osobny venv `/opt/jarvo/venvs/manimgx` na Pythonie 3.13 z obrazu Hermesa (Debian 13,
  `/usr/bin/python3.13`; koło manimgx jest cp313-abi3), wszystkie paczki z sumami sha256
  ([`requirements-manimgx.txt`](../infra/python/requirements-manimgx.txt), `--require-hashes`, same koła), bez apt
  (silnik niesie Mesę lavapipe, x264 i Typst: ~0,3 GB zamiast ~1 GB Manim CE z cairo, pango i texlive). Komenda
  `/opt/jarvo/bin/manimgx` (cache `/opt/data/jarvo/cache/manimgx`), build kończy się próbnym renderem 1 s 640×360.
  Przegląd 2026-10-11 (decyzja właściciela): licencje (kod MIT, koło GPL-3.0-or-later), brak telemetrii i sieci w czasie
  renderu (sprawdzone bez sieci), koła przypięte sha256, wydanie 2026-10-07. Instalacja przez `uv pip install --no-config`:
  bez `[tool.uv]` Hermesa z `/opt/hermes` (jego ograniczenia paczek i okno `exclude-newer`), tylko plik z sumami,
- warsztat 3D: osobny venv `/opt/jarvo/venvs/cad` na Pythonie 3.12 (numpy, scipy i OpenCascade nie mieszają się z venvem
  narzędzi), `uv pip install --no-config --no-deps --require-hashes --only-binary :all: --compile-bytecode`: dokładnie lista
  z pliku, bez sympy, mpmath, jedi i parso (build123d ich nie używa; −0,1 GB). Kod bajtowy z obrazu: start silnika ~3 s.
  Przegląd 2026-10-13 (decyzja właściciela): licencje, brak telemetrii, sieć tylko w jawnym `export_to_pcbway` i pobieraniu
  tekstur, zablokowane w `cad_model.py`,
- rozpoznawanie mowy: `/opt/jarvo/bin/jarvo-stt` (Hermes: `HERMES_LOCAL_STT_COMMAND`, `stt.provider: local_command`),
- głos floty (odpowiedzi głosem na Telegramie w trybie `/voice` i narzędzie `text_to_speech`): `jarvo-tts --plik` jako
  komenda TTS Hermesa (`tts.providers.matcha` w `profiles/_host/config.yaml`, `scripts/build.py` wstawia ją każdemu profilowi),
  głos `pl-PL-Matcha-Meski`; WAV na Opus (dymek głosowy) zamienia Hermes,
- lektor angielski: `/opt/jarvo/bin/jarvo-tts` z modelem Paradee w `/opt/jarvo/models/paradee/`; pliki modelu i koło
  spaCy przypięte sumą SHA-256, a build kończy się próbą mowy (`jarvo-tts --sprawdz en-US-Paradee`). misaki bez dodatku `[en]`
  (ciągnąłby torch, ~5 GB).
- lektor polski: ten sam `jarvo-tts` z Matcha-TTS-PL v2 w `/opt/jarvo/models/matcha-pl/` (`meski/`, `damski/`: graf ONNX
  t2 i `voices.json`, obok `LICENSE`, `ATTRIBUTION.md`, karta modelu, `JARVO-ZRODLO.txt`), +0,28 GB; pliki przypięte
  rewizją i sumą SHA-256, build kończy się próbą mowy obu głosów. Bez `.ckpt`, próbek i torcha. Przegląd 2026-10-11
  (repo modelu z 2026-10-02, rewizja z 2026-10-10): pliki = same wagi ONNX i JSON-y przypięte sha256. Na 4-rdzeniowym Xeonie 2,8 GHz, 2 wątki (`JARVO_TTS_THREADS`): RTF ~0,5 (4 wątki ~0,3),
  ~0,41 GB RAM na głos na czas syntezy.

Skrypty `.cjs` ładują moduły przez `NODE_PATH`, a ESM-owe pakiety (np. `favicons`) przez `importGlobal()`.
Skrypty Pythona, które potrzebują bibliotek z venv narzędzi, same przełączają się na `/opt/jarvo/venv`.

**MCP:** serwery MCP dopisujemy w `config.yaml` profilu, w sekcji `mcp_servers` (Hermes nie czyta
`mcp.json` z profilu). Zasada bez zmian: tylko te serwery, których agent naprawdę używa, bo każde
narzędzie w schemacie kosztuje tokeny przy każdym zapytaniu.
Pierwszy włączony: `inspo` u `jarvo-web` (pakiet z obrazu, stdio, `lazy`: proces startuje przy pierwszym wywołaniu
i znika po 15 min bezczynności; z 15 narzędzi serwera w schemacie modelu tylko 6 z `tools.include`, ~10 KB; `trust: full`, bo Hermes 0.21.5 z SDK `mcp` 2.0 nie widzi `readOnlyHint` i przy `untrusted` każde wywołanie
czekałoby na zgodę, której w pracy z kanbana nikt nie da; wersja jest przypięta, a wszystkie narzędzia 0.1.16 są tylko do odczytu).
Nie używamy hostowanego endpointu inspomcp.dev ani `TOGETHER_API_KEY` (bez klucza wyszukiwanie jest leksykalne,
więc zapytania po angielsku). Serwer pobiera katalog (~2,3 MB) z CDN autorów przy każdym starcie; Hermes przekazuje
serwerom stdio tylko bezpieczne zmienne środowiska (`PATH`, `HOME`, bez proxy), więc `config.yaml` podaje mu wprost
`NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt` (CA dodane do systemu, np. proxy z własnym certyfikatem).
Proxy wymagające `HTTPS_PROXY` dalej blokuje pobór. Healthcheck (`toolbox.yaml`) startuje serwer z takim samym okrojonym
środowiskiem i robi prawdziwe `search_screens`, więc zielony wynik znaczy, że katalog się pobrał.

---

## Stan instalacji natywnej (Windows, macOS, Linux)

Instalacja bez Dockera i WSL ([NATYWNIE.md](NATYWNIE.md), etap E2; bootstrap `jarvo/bootstrap/`, domyślny od etapu E13).
Źródło prawdy: [`vendor/natywne.yaml`](../vendor/natywne.yaml), czyli adres, SHA-256 i rozmiar pliku dla każdej
platformy albo `brak:` z powodem. Z niego `scripts/natywne.py generuj` robi `vendor/natywne.lock.json`, który czyta
instalator. Pliki pobiera u źródła [`jarvo/pobieracz.py`](../jarvo/pobieracz.py): sprawdza sumę przed rozpakowaniem
i rozpakowuje do `<program>/narzedzia/<nazwa>/<wersja>`. Z tego nic nie hostujemy; licencje są w
[SOURCES.md](SOURCES.md#instalacja-natywna). Dowiązania z archiwów:
- na macOS i Linuksie zostają dowiązaniami w katalogu narzędzia (np. `lib/libqpdf.so.30` w qpdf), a cel poza nim to błąd;
- na Windows twarde dowiązania z tar są rozpakowane (Git for Windows ma ich 92, m.in. `git-remote-https.exe`);
- symboliczne na Windows zastępuje kopia celu z archiwum.

Po rozpakowaniu manifest może usunąć zbędne pliki (`usun`) i zmienić nazwę (`zmien_nazwe`, np.
`exiftool(-k).exe` → `exiftool.exe`). Plik bez archiwum (`plik`) ląduje pod `nazwa_pliku`.

**Przegląd 2026-10-24.** Każde źródło przeszło 7 kroków z
[SOURCES.md](SOURCES.md#przegląd-przed-dodaniem-każde-źródło-osobno) i ma wpis w `vendor/zrodla.yaml` z pełnym commitem
tagu. Każdy plik policzyliśmy co najmniej dwiema drogami: suma wydawcy albo digest GitHuba i własne liczenie
strumieniowe. Dla Chrome for Testing i ffmpeg Playwrighta, bez sum u wydawcy, drugą drogą było md5 serwera. Żadna suma
się nie różni. Próba na Windows 11 x64: każde narzędzie z kolumny Windows x64 pobrane pobieraczem Jarva i uruchomione,
Defender bez zagrożeń. Pliki macOS i Linuksa sprawdziliśmy w nagłówkach binarek (architektura, minimalny system,
biblioteki, podpis); uruchomienie na tych systemach i na Windows arm64 zrobi macierz CI. Minimalny macOS to 15, bo pandoc
i qpdf mają minos 15.0, a Lightpanda 14.8.9. Windows arm64 bierze plik x64 w emulacji (I27), gdy nie ma natywnego albo
natywny ma mniej funkcji.

| Narzędzie | Wersja | Windows x64 | Windows arm64 | macOS arm64 | Linux x64 i arm64 | Kiedy | Wynik |
|---|---|---|---|---|---|---|---|
| uv | 0.12.13 | zip | zip arm64 | tar.gz | tar.gz | instalacja | sumy z `.sha256` |
| Python (python-build-standalone 20261021) | 3.13.17, 3.12.15 | tar.gz | x64 w emulacji | tar.gz | tar.gz | instalacja | SQLite 3.53.1 bez błędu WAL-reset |
| Node.js | 26.12.1, npm 11.20.0 | zip | x64 w emulacji | tar.gz | tar.xz | instalacja | `SHASUMS256.txt` z podpisem GPG; `npm_config_update_notifier=false` |
| Git for Windows | 2.56.0.windows.3 | tar.bz2 (ucrt64) | tar.bz2 (clangarm64) | brak: git z systemu | brak: git z systemu | instalacja | `git --version`, `ls-remote` po https i Git Bash 5.3 na Windows 11; `GIT_CONFIG_NOSYSTEM=1` |
| ripgrep | 15.2.0 | zip | x64 w emulacji | tar.gz | tar.gz (musl) | instalacja | PCRE2 10.46 w binarce |
| jq | 1.8.2 | `jq.exe` | `jq.exe` arm64 | plik | plik | instalacja | atestacja SLSA; kod floty go nie używa |
| chrome-headless-shell (Chrome for Testing) | 153.0.8010.12 | zip | x64 w emulacji | zip | zip | instalacja | rewizja 1243 Playwrighta 1.63; na Windows silnik `browser_*` |
| ffmpeg Playwrighta | 1011 | zip | x64 w emulacji | zip | zip | instalacja | LGPL, tylko VP8/WebM, PNG, MJPEG |
| Lightpanda | 1.0.0 | brak: silnik `chrome` | brak: silnik `chrome` | plik | plik | instalacja | Linux = binarka z obrazu; telemetria wyłączona zmiennymi |
| agent-browser | 0.38.1 | plik z wydania | x64 w emulacji | plik | plik | instalacja | te same bajty co w paczce npm z atestacją SLSA |
| Camoufox | 152.0.4-beta.30 | zip | x64 w emulacji | zip | zip | przy użyciu | paczka Windows ma fonty macOS, a macOS fonty Windows (decyzja właściciela) |
| Chrome for Testing (Komputer Jarva) | 156.0.8078.47 | zip | x64 w emulacji | zip | zip | przy użyciu | `jarvo komputer on`; CDP po potoku, ruch przez proxy filtrujące; 134/134 sprawdzeń Komputera na Windows 11 |
| FFmpeg (BtbN, gpl) | 9.0.2 | zip | x64 w emulacji (winarm64 bez libvpx) | brak: build Riedla | tar.xz | instalacja | filtry i kodery floty na Windows 11; libass na Windows potrzebuje `fontsdir` |
| FFmpeg i ffprobe (Martin Riedl) | 9.0.2 | brak: BtbN | brak: BtbN | dwa zipy, Developer ID | brak: BtbN | instalacja | bez vidstab i librsvg |
| Fonty Inter i DejaVu | 4.1, 2.37 | zip | ten sam zip | ten sam zip | ten sam zip | instalacja | `JARVO_FONTY_INTER`, `JARVO_FONTY_DEJAVU` |
| pandoc | 3.12.1 | zip | x64 w emulacji | zip (od macOS 15) | tar.gz | instalacja | Authenticode SignPath; natywnie z `--data-dir` |
| qpdf | 12.4.2 | zip | zip arm64 | zip (od macOS 15) | zip (glibc 2.34+) | instalacja | lista sum z podpisem PGP; dowiązania `lib/libqpdf.*` |
| ExifTool | 13.59 | zip z Perlem | x64 w emulacji | tar.gz na Perlu systemu | tar.gz na Perlu systemu | instalacja | `exiftool.exe` po zmianie nazwy; `EXIFTOOL_HOME` |
| pixi (tylko Tesseract) | 0.83.0 | zip | zip arm64 (`--platform win-64`) | tar.gz | tar.gz (musl) | instalacja | projekt [`vendor/pixi/tesseract`](../vendor/pixi/tesseract/pixi.toml); `PIXI_NO_TELEMETRY=1` |
| scrcpy | 5.0.1 | zip | zip arm64 | tar.gz | x64 tar.gz, arm64 brak | przy użyciu | `SHA256SUMS.txt` z podpisem GPG |
| Android platform-tools (adb) | r37.0.1 | zip (x86, podpis Google) | ten sam zip w emulacji | zip (universal) | x64 zip, arm64 brak | przy użyciu | `usun` bez sqlite3 3.50.6 (WAL-reset), mke2fs, make_f2fs, etc1tool, hprof-conv; `ADB_MDNS=0`; `adb version` i `fastboot --version` na Windows 11 |
| cua-driver-rs (ręce, K6) | 0.38.0 | zip, Authenticode Cua AI | zip arm64, Authenticode | tar.gz (CuaDriver.app, Developer ID) | tar.gz (X11 albo XWayland) | przy użyciu | `jarvo komputer rece on`; bez pracownika UIAccess; tylko przez bramkę rąk |

Tesseract 5.5.3 przychodzi z conda-forge przez [`vendor/pixi/tesseract`](../vendor/pixi/tesseract/pixi.toml):
- `pixi.lock` ma 31–37 paczek na platformę i sumę każdej z nich;
- `.pixi/config.toml` wyłącza skrypty post-link i detektory pakietów wirtualnych z kanału;
- instalator woła `pixi install --locked` (na Windows arm64 z `--platform win-64`).

Venvy Jarva (sekcja `venvy` manifestu) instalator buduje tak: `uv venv --no-config` z Pythona z manifestu, potem
`uv pip install --no-config --no-deps --require-hashes --only-binary :all: --compile-bytecode -r <lock>`. Katalog
`<program>/venvs/<nazwa>-<12 znaków sha256 locka>`, na Windows z `UV_LINK_MODE=copy`. Locki ze strumieniowo
sprawdzoną sumą każdego koła dla windows-x64, macos-arm64 (koła od macOS 14.0) i Linuksa (manylinux_2_28); windows-arm64
bierze te same koła x64. Nowe locki leżą w [`infra/python/natywne/`](../infra/python/natywne/), razem z wejściami
i opisem odtworzenia w nagłówku.

| venv | Python | Lock (paczek) | Pobranie Windows / macOS / Linux x64 | Kiedy | Próba na Windows 11 x64 |
|---|---|---|---|---|---|
| `narzedzia` | 3.12.15 | [`narzedzia.lock`](../infra/python/natywne/narzedzia.lock) (122) | 158 / 163 / 214 MB | instalacja | 9 z 9 prób bez sieci; bez docopt (ma tylko sdist) |
| `ocr` | 3.12.15 | [`requirements-ocr.txt`](../infra/python/requirements-ocr.txt) (8) | 76 / 79 / 106 MB | instalacja | Indra odczytała tekst bez sieci |
| `cad` | 3.12.15 | [`requirements-cad.txt`](../infra/python/requirements-cad.txt) (56) | 215 / 207 / 244 MB | przy użyciu | STEP, STL, GLB i 3MF w 6 s |
| `manimgx` | 3.13.17 | [`requirements-manimgx.txt`](../infra/python/requirements-manimgx.txt) (18) | 85 / 64 / 109 MB | przy użyciu | 1 s filmu w 3,3 s |
| `claude-seo` | 3.12.15 | [`claude-seo.lock`](../infra/python/natywne/claude-seo.lock) (70) | 141 / 148 / 166 MB | instalacja | 6 z 7; WeasyPrint bez Pango na Windows nie działa, więc PDF przez Chromium |
| `rembg` | 3.12.15 | [`rembg.lock`](../infra/python/natywne/rembg.lock) (85) | 177 / 157 / 214 MB | dodatek | `rembg --help` bez sieci; gradio z `GRADIO_ANALYTICS_ENABLED=False` |
| `mgaudio` | 3.12.15 | [`mgaudio.lock`](../infra/python/natywne/mgaudio.lock) (10) | 101 / 73 / 123 MB | dodatek | numba, pedalboard, głośność −18 LUFS |
| `lemo-wake` | 3.12.15 | [`lemo-wake.lock`](../infra/python/natywne/lemo-wake.lock) (11) | 83 / 84 / 116 MB | dodatek | cv2, onnxruntime 1.30, HEIC |
| `docling` | 3.12.15 | [`docling-cpu.lock`](../infra/python/natywne/docling-cpu.lock) (104) | 339 / 317 / 430 MB | dodatek | tylko instalacja na sucho; torch CPU z indeksu PyTorch (`--torch-backend cpu`) |

Modele i dane (sekcja `modele`): pliki z przypiętej rewizji (commit, nie tag) do `<dane>/jarvo/models/<katalog>`, każdy
z sumą; Matcha, Paradee i Indra mają te same pliki i sumy co obraz.

| Model | Rewizja | Plików | Rozmiar | Kiedy |
|---|---|---|---|---|
| `matcha-pl` (Matcha-TTS-PL v2) | `9374474` | 7 | 280 MB | instalacja |
| `paradee` (Paradee-8M v1.0) | `8f34b01` | 3 | 9 MB | instalacja |
| `indra-ocr` | `ed345c7` | 15 | 38 MB | instalacja |
| `parakeet` (TDT 0.6B v3, int8) | `8f23f0c` | 5 | 671 MB | przy użyciu |
| `silero-vad` | `b3e3ee3` | 4 | 2,3 MB | przy użyciu |
| `modnet` | `903cc06` | 2 | 26 MB | przy użyciu |
| `yunet` | `3cc26e7` | 3 | 0,2 MB | przy użyciu |
| `tessdata-fast` (pol, eng, osd) | `6572757` | 4 | 20 MB | instalacja |
| `fonty-noto-sans` (Noto Sans 2.015) | `28b15b4` | 5 | 2,5 MB | instalacja |
| `fonty-noto-emoji` (Noto Color Emoji 2.051) | `8998f5d` | 2 | 11 MB | instalacja |


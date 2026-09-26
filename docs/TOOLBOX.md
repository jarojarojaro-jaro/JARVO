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

## `tars-web`: Web Senior Dev

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Lighthouse](https://github.com/GoogleChrome/lighthouse) | audyt wydajności, SEO, dostępności, dobrych praktyk | Apache-2.0 | 2026-09 | CLI + skrypt |
| [axe-core](https://github.com/dequelabs/axe-core) + [axe-core-npm](https://github.com/dequelabs/axe-core-npm) | audyt dostępności (WCAG) | MPL-2.0 | 2026-09 | CLI + skrypt |
| [Playwright](https://github.com/microsoft/playwright) | zrzuty na wielu szerokościach, testy responsywności | Apache-2.0 | 2026-09 | skrypt |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | sterownik narzędzi `browser_*` Hermesa (natywna binarka Rust) | Apache-2.0 | 2026-09 | Hermes |
| [Lightpanda](https://github.com/lightpanda-io/browser) | lekka przeglądarka headless dla agentów (~30 MB na sesję); Chromium tylko do renderu | AGPL-3.0 (osobny program) | 2026-09 | silnik `browser.engine` |
| [sharp](https://github.com/lovell/sharp) | konwersja i kompresja obrazów (AVIF/WebP), warianty `srcset` | Apache-2.0 | 2026-09 | skrypt |
| [favicons](https://github.com/itgalaxy/favicons) | komplet faviconów, ikon i manifestu z jednego pliku | MIT | 2026-09 | skrypt |
| [pwa-asset-generator](https://github.com/elegantapp/pwa-asset-generator) | ikony i splash screeny PWA | MIT | 2026-09 | CLI |
| [SVGO](https://github.com/svg/svgo) | optymalizacja SVG (logo, ikony) | MIT | 2026-08 | CLI |
| [linkinator](https://github.com/JustinBeckwith/linkinator) | wykrywanie martwych linków | MIT | 2026-09 | CLI |
| [html-validate](https://github.com/html-validate/html-validate) | walidacja HTML | MIT | 2026-09 | CLI |
| [glyphhanger](https://github.com/zachleat/glyphhanger) | subsetting fontów | MIT | 2026-06 | CLI |
| [dembrandt](https://github.com/dembrandt/dembrandt) | **wyciąga system designu ze strony** (logo, kolory, typografia, odstępy) jako tokeny W3C, czyli podstawa `brand-z-url` | MIT | 2026-09 | CLI + skrypt |
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

## `tars-sherlock`: Researcher-detektyw

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [SearXNG](https://github.com/searxng/searxng) | własna metawyszukiwarka (70+ silników), bez kluczy i limitów | AGPL-3.0 | 2026-09 | sidecar + dostawca `searxng` |
| [trafilatura](https://github.com/adbar/trafilatura) | czysta treść artykułów (`extract.py`) | Apache-2.0 | 2026-09 | skrypt |
| [Lightpanda](https://github.com/lightpanda-io/browser) | strony z JS do Markdown bez Chromium: `lightpanda fetch --dump markdown <url>`; silnik `browser_*` | AGPL-3.0 (osobny program) | 2026-09 | CLI + Hermes |
| [Scrapling](https://github.com/D4Vinci/Scrapling) | odporny scraping (skill [H] `scrapling`) | BSD-3 | 2026-09 | CLI |
| [trafilatura](https://github.com/adbar/trafilatura) | czysty tekst artykułów, metadane, daty publikacji | Apache-2.0 | 2026-09 | skrypt |
| [Docling](https://github.com/docling-project/docling) | PDF-y, raporty, tabele → Markdown | MIT | 2026-09 | skrypt |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | napisy i transkrypcje z wideo jako źródła | Unlicense | 2026-09 | CLI |
| [ExifTool](https://github.com/exiftool/exiftool) | metadane zdjęć i plików (weryfikacja pochodzenia) | GPL-3.0 | 2026-05 | CLI |
| [ArchiveBox](https://github.com/ArchiveBox/ArchiveBox) | archiwum dowodów: kopia każdej kluczowej strony-źródła | MIT | 2026-09 | sidecar (opcja) |

Z Hermesa:
- **wielu dostawców wyszukiwania** (`plugins/web/`): SearXNG, DuckDuckGo, Brave, Exa, Tavily, Perplexity,
  Parallel. **Różne indeksy wyszukiwania dają niezależność źródeł**, co jest fundamentem weryfikacji krzyżowej,
- **plugins:** `openalex` (literatura naukowa i cytowania), `storm-fusion-research` (panel
  perspektyw z sędzią, pasuje do metody Sherlocka), `web-defuddle` (ekstrakcja lokalna), `source-tray` (lista odwiedzonych źródeł),
- **[H] skille:** `grounded-citations`, `blocked-page-recovery`, `searxng-search`, `duckduckgo-search`,
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

## `tars-studio`: Marketing i kreacja

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| HyperFrames (skill [H] `hyperframes`) | wideo z HTML + GSAP → MP4/WebM | (skill Hermesa) | n/d | CLI (`npx`) |
| [Remotion](https://github.com/remotion-dev/remotion) | wideo w React: szablony filmów produktowych | **Remotion License** ⚠️ | 2026-09 | per projekt |
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas) | animacje i explainery z kodu | MIT | 2026-07 | per projekt |
| [Revideo](https://github.com/redotvideo/revideo) | fork Motion Canvas do renderingu programowego | MIT | 2026-07 | per projekt |
| [Manim CE](https://github.com/ManimCommunity/manim) | animacje edukacyjne i matematyczne (skill [H] `manim-video`) | MIT | 2026-09 | CLI |
| FFmpeg | montaż, konwersje, napisy, formaty platform | LGPL/GPL | n/d | CLI |
| [auto-editor](https://github.com/WyattBlue/auto-editor) | automatyczne wycinanie ciszy z nagrań (dodatek `media`) | Unlicense | 2026-09 | CLI |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) przez [onnx-asr](https://github.com/istupakov/onnx-asr) | transkrypcja i napisy na CPU (int8, 25 języków z polskim), też wiadomości głosowe Hermesa | CC-BY-4.0 (model) / MIT | 2026-07 | `tars-stt` |
| [Kokoro](https://github.com/hexgrad/kokoro) | lektor TTS offline (alternatywnie TTS przez API Hermesa) | Apache-2.0 | 2025-08 | skrypt |
| [Satori](https://github.com/vercel/satori) + [resvg](https://github.com/linebender/resvg) | grafiki z HTML/JSX → SVG → PNG (posty, OG images, banery) | MPL-2.0 / Apache-2.0 | 2026-09 | skrypt |
| [rembg](https://github.com/danielgatis/rembg) | usuwanie tła ze zdjęć produktów (CPU; dodatek `rembg`) | MIT | 2026-09 | CLI |
| [sharp](https://github.com/lovell/sharp) | przycinanie i eksport w wymiarach platform | Apache-2.0 | 2026-09 | skrypt |
| [Postiz](https://github.com/gitroomhq/postiz-app) | kolejka i harmonogram publikacji; Studio przygotowuje, Ty akceptujesz | AGPL-3.0 | 2026-09 | sidecar |
| [Penpot](https://github.com/penpot/penpot) | otwarte narzędzie do projektowania (opcjonalnie, ciężkie) | MPL-2.0 | 2026-09 | sidecar (opcja) |

Z Hermesa:
- **generowanie AI:** `plugins/image_gen/openrouter` i `plugins/video_gen/openrouter`, czyli jeden klucz
  OpenRouter do obrazów i wideo (inni dostawcy: fal, xai, deepinfra; w katalogu też MiniMax, DashScope),
- **[H] skille:** `hyperframes`, `manim-video`, `baoyu-infographic`, `social-media-content-calendar`,
  `ai-presenter-video`, `kanban-video-orchestrator`, `creative-ideation`, `humanizer`,
  `meme-generation`, `xurl`, `excalidraw`, `concept-diagrams`, `p5js`,
- **MCP:** `canva`, `figma`, `cloudinary`, `gamma`,
- **plugin:** `adspirer` (kampanie reklamowe Google/Meta/TikTok/LinkedIn), wyłącznie na poziomie A2, czyli za Twoją zgodą.

⚠️ **Remotion:** darmowy dla osób prywatnych i firm do 3 pracowników; większa firma potrzebuje
płatnej licencji. Jeśli działasz jako większa firma, domyślnie używamy HyperFrames / Motion Canvas / Revideo (MIT).

Odrzucone: ComfyUI self-host (GPL-3.0, wymaga GPU; generowanie idzie przez API),
`rhasspy/piper` (projekt przeniesiony do `OHF-Voice/piper1-gpl` na GPL-3.0; Kokoro wystarcza).

---

## `tars-reka`: Prawa ręka

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| [Pandoc](https://github.com/jgm/pandoc) | konwersje dokumentów (MD ↔ DOCX ↔ PDF ↔ HTML) | GPL-2.0 | 2026-09 | CLI |
| Chromium (z obrazu) + pandoc | Markdown/HTML/DOCX → PDF (`to_pdf.py`), bez osobnej usługi | BSD / GPL-2.0 | n/d | skrypt |
| [LibreOffice](https://www.libreoffice.org) | XLSX/PPTX/DOC → PDF (dodatek `office`) | MPL-2.0 | 2026-09 | CLI |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | OCR skanów | MPL-2.0 | 2026-09 | CLI |
| [Docling](https://github.com/docling-project/docling) | czytanie dokumentów, tabel, PDF-ów (dodatek `docling`) | MIT | 2026-09 | skrypt |
| [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF) | operacje na PDF (łączenie, podpisy, kompresja) | MIT | 2026-09 | sidecar (opcja) |

Z Hermesa: pełny katalog skilli [H] + skille snajperów (tylko do odczytu), plugins
`document-reader`, `image-utils`, opcjonalnie `openmail` (własny adres e-mail agenta, A2).
MCP według Twoich narzędzi (np. `notion`, `todoist`, `calendly`, `airtable`), do ustalenia.

---

## `tars`: Main Judge

| Narzędzie | Po co | Licencja | Ostatni commit | Integracja |
|---|---|---|---|---|
| Kanban Hermesa | tablica zleceń, statusy `review` / `request_changes` | MIT (Hermes) | n/d | toolset `kanban` |
| [Langfuse](https://github.com/langfuse/langfuse) | ślady przebiegów, koszty per agent, oceny sędziego | MIT (core) | 2026-09 | plugin `langfuse` + sidecar |
| [promptfoo](https://github.com/promptfoo/promptfoo) | evals floty (scenariusze z `evals/`) w CI i przed wdrożeniem | MIT | 2026-09 | CLI (dev/CI) |
| [DeepEval](https://github.com/confident-ai/deepeval) | alternatywa dla promptfoo (metryki LLM-sędziego) | Apache-2.0 | 2026-09 | do oceny |

Z katalogu wtyczek Hermesa do oceny w fazie 6: `afterforge` (zamienia porażki agentów
w przejrzane testy regresji), `gonogo` (wynik evali → decyzja o wdrożeniu).

---

## Infrastruktura (VPS)

| Narzędzie | Po co | Licencja | Ostatni commit |
|---|---|---|---|
| [Honcho](https://github.com/plastic-labs/honcho) | wspólna pamięć o Tobie (self-host) | AGPL-3.0 | 2026-09 |
| [Caddy](https://github.com/caddyserver/caddy) | HTTPS reverse proxy (tylko gdy potrzebny) | Apache-2.0 | 2026-09 |
| [Tailscale](https://github.com/tailscale/tailscale) | prywatny dostęp do VPS | BSD-3 | 2026-09 |
| [restic](https://github.com/restic/restic) | szyfrowane backupy | BSD-2 | 2026-09 |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) | healthchecki i alerty | MIT | 2026-09 |
| [Beszel](https://github.com/henrygd/beszel) | monitoring zasobów | MIT | 2026-09 |
| [CrowdSec](https://github.com/crowdsecurity/crowdsec) | ochrona przed atakami | MIT | 2026-09 |

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

## Stan instalacji (co naprawdę jest w obrazie `tars-hermes`)

Źródło prawdy: [`infra/Dockerfile`](../infra/Dockerfile), [`infra/node/package.json`](../infra/node/package.json),
[`infra/python/requirements-tools.txt`](../infra/python/requirements-tools.txt), sidecary w
[`infra/docker-compose.yml`](../infra/docker-compose.yml). Healthchecki: `scripts/healthcheck.sh`.

| Warstwa | Gdzie | Co |
|---|---|---|
| obraz Hermesa | `/opt/hermes` | Python 3.14 Hermesa (nie ruszamy), Node, `uv`, ffmpeg/ffprobe, Chromium |
| pakiety systemowe | apt | pandoc, qpdf, ocrmypdf + tesseract (pol, eng), exiftool, jq, sqlite3, fonty z polskimi znakami |
| przeglądarki | `/usr/local/bin/lightpanda`, `/usr/local/bin/chromium` (`CHROME_PATH`) | Lightpanda dla `browser_*` agentów (agent-browser); jedna Chromium z obrazu Hermesa dla zrzutów, PDF, Lighthouse, Playwright i dembrandta |
| narzędzia Node | `/opt/tars/node/node_modules` (`NODE_PATH`, `.bin` w `PATH`) | agent-browser, lighthouse, axe-core, playwright-core, sharp, svgo, favicons, linkinator, html-validate, dembrandt |
| narzędzia Pythona | venv `/opt/tars/venv` (Python 3.12, na końcu `PATH`) | trafilatura, yt-dlp, onnx-asr (Parakeet); dodatki `TARS_EXTRAS`: rembg, auto-editor, docling, manim |
| claude-seo | `/opt/tars/vendor/claude-seo` (`CLAUDE_PLUGIN_ROOT`, własny venv) | skrypty skilli SEO, ten sam commit co w locku skilli |
| sidecary | sieć `tars-net` | SearXNG (`SEARXNG_URL`) + Valkey; nic więcej (reszta działa w obrazie na żądanie) |

Zasady obrazu Hermesa, których pilnujemy (`make pins` sprawdza piny przed zmianą):
- globalny npmrc obrazu ma `min-release-age = 14` i `engine-strict`: przypinamy wersje npm starsze niż 14 dni
  i zgodne z Node obrazu; tę samą zasadę stosujemy do pinów Pythona,
- interpreter Pythona dla venv pobiera `uv` do `/opt/tars/uv-python` (nie do `/root`, niedostępnego dla `hermes`),
- jedna Chromium: `playwright-core` (także dembrandta, przez `overrides`) i Playwright claude-seo są przypięte do wersji,
  której przeglądarka jest w obrazie Hermesa; Dockerfile uruchamia ją testowo i zatrzyma build przy niezgodności,
- `AGENT_BROWSER_EXECUTABLE_PATH` celowo nieustawione: agent-browser użyłby go też dla silnika lightpanda,
- bez cache instalatorów w warstwach (`UV_NO_CACHE`, `npm cache clean`) i bez `chmod -R` (kopiuje całe drzewo do nowej warstwy),
- auto-editor (dodatek `media`) pobiera swoją binarkę przy budowie obrazu (w runtime katalog pakietów jest tylko do odczytu),
- rozpoznawanie mowy: `/opt/tars/bin/tars-stt` (Hermes: `HERMES_LOCAL_STT_COMMAND`, `stt.provider: local_command`).

Skrypty `.cjs` ładują moduły przez `NODE_PATH`, a ESM-owe pakiety (np. `favicons`) przez `importGlobal()`.
Skrypty Pythona, które potrzebują bibliotek z venv narzędzi, same przełączają się na `/opt/tars/venv`.

**MCP:** serwery MCP dopisujemy w `config.yaml` profilu, w sekcji `mcp_servers` (Hermes nie czyta
`mcp.json` z profilu). Zasada bez zmian: tylko te serwery, których agent naprawdę używa, bo każde
narzędzie w schemacie kosztuje tokeny przy każdym zapytaniu.


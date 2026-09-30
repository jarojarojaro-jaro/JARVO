# Źródła i licencje (third-party notices)

Jarvo jest zbudowany na cudzej, otwartej pracy. Ten plik mówi, **co** wzięliśmy, **skąd**, na jakiej
**licencji** i **jak** spełniamy jej warunki. Narzędzia uruchamiane przez agentów (npm, Python, sidecary)
są opisane osobno w [TOOLBOX.md](TOOLBOX.md), razem z polityką licencji.

## 1. Platforma

| Projekt | Rola | Licencja |
|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) | rdzeń: profile, kanban, cron, gateway, skille, obraz Docker | MIT |

Hermesa nie forkujemy: używamy oficjalnego obrazu i rozszerzamy go na krawędziach (profile, skille, narzędzia).

Komponenty obrazu `jarvo-hermes` o znaczeniu licencyjnym (pełna lista narzędzi: [TOOLBOX.md](TOOLBOX.md)):

| Projekt | Rola | Licencja |
|---|---|---|
| [Lightpanda](https://github.com/lightpanda-io/browser) 0.4.0 | przeglądarka headless dla `browser_*` (binarka z oficjalnego obrazu, tylko `strip`) | AGPL-3.0 |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | sterownik narzędzi przeglądarki Hermesa | Apache-2.0 |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) (NVIDIA), eksport ONNX [istupakov/parakeet-tdt-0.6b-v3-onnx](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) | model rozpoznawania mowy (pobierany przy pierwszym użyciu, nie w repo ani w obrazie) | CC-BY-4.0 |
| [onnx-asr](https://github.com/istupakov/onnx-asr) + [ONNX Runtime](https://github.com/microsoft/onnxruntime) | uruchamianie modelu mowy na CPU | MIT |
| [Silero VAD](https://github.com/snakers4/silero-vad) | wykrywanie mowy przed Parakeetem w `jarvo-stt` (pobierany przy pierwszym użyciu, nie w repo ani w obrazie) | MIT |

## 2. Skille dołączane do agentów (vendoring)

Kopiowane przy buildzie z przypiętych commitów zapisanych w [`vendor/skills.lock.yaml`](../vendor/skills.lock.yaml).
Każdy skopiowany skill dostaje `LICENSE-UPSTREAM` (albo licencję z własnego katalogu), `NOTICE-UPSTREAM`
(jeśli źródło go ma) i `.vendored.json` (repo, commit, ścieżka, licencja). Treści skilli nie zmieniamy;
nasze adaptacje żyją w skillach własnych floty.

| Źródło | Commit | Licencja | Dla kogo |
|---|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent): skille z drzewa obrazu | wersja obrazu | MIT | Sherlock, Web, Studio, Wideograf (manim-video, ai-presenter-video) |
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `5b2c000` | MIT | Sherlock, Web, Studio, Wideograf (video), Ads (ads, ab-testing, attribution, analytics, ad-creative) |
| [addyosmani/web-quality-skills](https://github.com/addyosmani/web-quality-skills) | `afa8da9` | MIT | Web |
| [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) | `e77e783` | MIT | Web (skille + skrypty w obrazie) |
| [anthropics/skills](https://github.com/anthropics/skills) | `3337550` | Apache-2.0 (tylko skille z licencją Apache w katalogu) | Web, Studio, Ręka, Wideograf (slack-gif-creator), Studio (algorithmic-art) |
| [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics) (skill motion-broll) | `e8d610a` | MIT | Wideograf (B-roll zgrany ze słowami) |
| [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | `108fa78` | MIT (assety CC0 / CC BY / OFL) | Wideograf (39 stylów filmu; biblioteka instalowana przez `narzedzia.py`) |
| [alexgreensh/anidoodle](https://github.com/alexgreensh/anidoodle) | `f335700` | Apache-2.0 | Wideograf (rysunek kodem, muzyka syntezowana) |
| [buildwithhanif/claude-animation-skill](https://github.com/buildwithhanif/claude-animation-skill) | `4ddb8c8` | MIT | Wideograf (animacja w Node canvas, postaci, efekty, dźwięk syntezowany z osi czasu) |
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | `cf49eff` | Remotion License (darmowa dla osoby / firmy do 3 osób) | Wideograf (router `remotion-best-practices` ze wszystkimi `remotion-*/REFERENCE.md`) |
| [Vincentwei1021/video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | `e2d8928` | Apache-2.0 | Wideograf (kinowe filmy produktu; instaluje narzedzia.py) |
| [diffusionstudio/lottie](https://github.com/diffusionstudio/lottie) | `3c72912` | MIT | Wideograf, Web (text-to-lottie) |
| [nolangz/pixel2motion](https://github.com/nolangz/pixel2motion) | `e9faedb` | MIT | Wideograf (logo → animacja SVG) |
| [bangtutorial/bang-motion](https://github.com/bangtutorial/bang-motion) | `c1aa65e` | MIT | Wideograf (motion graphics z marki) |
| [iart-ai/kinetic-typography-skills](https://github.com/iart-ai/kinetic-typography-skills) `fccc94b`, [iart-ai/data-animation-skills](https://github.com/iart-ai/data-animation-skills) `8ce2709`, [iart-ai/tiktok-video-skills](https://github.com/iart-ai/tiktok-video-skills) `2a77533` | jw. | MIT | Wideograf (typografia, wykresy, belki, odliczanie) |
| [jtydhr88/screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills) | `357d134` | MIT | Wideograf (5 skilli warsztatu do `scenariusz`) |
| [greensock/gsap-skills](https://github.com/greensock/gsap-skills) | `aed9cfd` | MIT | Wideograf, Web (8 skilli GSAP) |
| [CloudAI-X/threejs-skills](https://github.com/CloudAI-X/threejs-skills) | `b1c6230` | MIT (deklarowana w README, bez pliku; autorstwo w `notice`) | Wideograf, Web (10 skilli Three.js) |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | `d16ebe6` | MIT | Wideograf, Web (rzemiosło animacji UI) |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `114ea1d` | Apache-2.0 | Web, Studio (detektor anty-wzorców, silnik pobierany do `narzedzia/impeccable`) |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | `8798e40` | Apache-2.0 | Wideograf (wideo z HTML) |

Build odrzuca skill z `anthropics/skills`, jeśli w jego katalogu nie ma licencji Apache-2.0: część
skilli w tym repo ma inne, zastrzeżone warunki i nie wolno ich kopiować.

Dane pobierane w locie przez `profiles/jarvo-wideo/scripts/inspiracje.py` (to nie vendoring: commit przypięty
w skrypcie, nie w locku; listy nie trafiają do repo ani do obrazu):

| Źródło | Commit | Licencja | Dla kogo |
|---|---|---|---|
| [guanmo-ai/awesome-ai-motion](https://github.com/guanmo-ai/awesome-ai-motion) | `dff7a79` | MIT | Wideograf (inspiracje: 355 filmów, 62 prompty autorów) |
| [athemeroy/awesome-opus-5-5-videos](https://github.com/athemeroy/awesome-opus-5-5-videos) | `f0728e6` | CC-BY 4.0 (autor: athemeroy) | Wideograf (`inspiracje.py --drogi`: 168 opisanych dróg produkcji, z atrybucją; zaadaptowany szablon briefu: sekcja 3) |
| [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) | `6cdcea6` | **brak licencji** (prompty należą do autorów) | Wideograf: tylko inspiracja. Nic nie kopiujemy do repo: `inspiracje.py` pokazuje autora i link; pliki `rodzaje-filmu` to nasz tekst (wzorce rzemiosła, nie cytaty) |

Programy pobierane przez skille przy pierwszym użyciu (nie w repo ani w obrazie), w przypiętej wersji z sumą SHA-256:

| Projekt | Wersja | Licencja | Dla kogo |
|---|---|---|---|
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | 0.11.0 (`linux-*-portable`) | MIT (licencje zależności: `THIRD_PARTY_NOTICES.md` obok programu) | Web, Ręka: skill `graf-kodu` (tryb poleceń, bez MCP i bez procesu w tle) |

## 3. Metodologie i prompty (inspiracja, własny tekst)

Te projekty nie są kopiowane. Przeczytaliśmy je i napisaliśmy własne skille po polsku według ich metod
(albo zaadaptowaliśmy fragmenty po polsku, z oznaczeniem źródła).
Autorstwo zaznaczamy w polu `author` skilla albo `source` pliku w `references/`.

| Projekt | Licencja | Gdzie w Jarvo |
|---|---|---|
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (commit `8e259e9`, © 2024 Harry) | MIT | pomysł pipeline'u krótkiego filmu (temat → scenariusz → ujęcia → lektor → napisy → muzyka → montaż, warianty); kod własny: `profiles/jarvo-wideo/scripts/film.py` |
| [kunchenguid/firstmate](https://github.com/kunchenguid/firstmate) | MIT | model Main Judge: jeden rozmówca, załoga, eskalacja tylko decyzji, stan na dysku ([BOSS.md](BOSS.md)) |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | MIT | `metoda-sherlocka`, `raport-sledztwa`: plan → równoległe wątki → synteza, zasady cytowania |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) | MIT | `metoda-sherlocka`: szerokość/głębokość, iteracyjne pytania uzupełniające |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | MIT | `metoda-sherlocka`: pytania z wielu perspektyw przed wyszukiwaniem |
| Hermes Agent `sdlc-review` (J. Wolniewicz + Hermes Agent) | MIT | `sdlc-review` Jarva: adaptacja z rubrykami agentów, soczewkami i eskalacją po 3 rundach |
| [rlaope/oh-my-hermes](https://github.com/rlaope/oh-my-hermes) (commit `e3880be9146778d620a87ddfa2848ce811a97bd5`, © 2026 oh-my-hermes contributors) | MIT | kalibracja pod rodzinę modelu (`shared/calibration/`, za `MODEL_OPTI.md`: cechy GPT-6 z przewodnika OpenAI, Claude, DeepSeek (także za DeepSeek Harness), Kimi); dyscyplina wykonawcy w kontrakcie zlecenia (echo celu, jedna weryfikacja z limitem 2 poprawek, odmowa = granica, blokada tylko z konkretnego powodu, stany dowodu); `bramka-jakosci` Weba (rubryka designu, werdykt 0–100 z progiem 90, dane o CSS Design Awards); scenariusze `hostile.cjs`; `wywiad` Jarva (jedno pytanie naraz, 6 rund, zatrzymanie); `szybki-fakt` Sherlocka; księga lekcji w `fleet-improvement` |
| [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) (© 2025 Anthropic) | MIT | `bezpieczenstwo-aplikacji` Weba: metodyka przeglądu kodu i filtr fałszywych alarmów (za `claudecode/prompts.py`, `findings_filter.py`), zaadaptowane po polsku w `references/przeglad-kodu.md` |
| [athemeroy/awesome-opus-5-5-videos](https://github.com/athemeroy/awesome-opus-5-5-videos) (`docs/production-brief.md`, autor: athemeroy) | CC-BY 4.0 | szablon briefu produkcyjnego, zaadaptowany w `film-z-kodu/references/produkcja-etapami.md`; analiza trendu w `kontrola-wideo/references/zakazane.md` |
| [Yuzzyuk/marketing-os](https://github.com/Yuzzyuk/marketing-os) (commit `bb67dff`, © 2026 Marketing OS contributors) | MIT | `hooks.md` → wspólny skill `hooki` (trzy warstwy, 18 taktyk, korpus, rozbieg, lejek diagnozy, drabina wierności), po polsku |
| JohnHeibel/ClaudeAnimationBase (+ briefy @donaldjewkes) | MIT | wzorzec bramek etapów w `film-z-kodu/references/produkcja-etapami.md` |

## 4. Jarvo HQ (GUI)

| Projekt | Rola | Licencja |
|---|---|---|
| [htm](https://github.com/developit/htm) 3.1.1 | składnia podobna do JSX bez kompilacji (`hq/web/vendor/`, z licencją) | Apache-2.0 |
| React | dostarczany przez SDK dashboardu Hermesa; w trybie demo 18.3.1 z cdnjs | MIT |
| Bricolage Grotesque, Atkinson Hyperlegible, JetBrains Mono, Pixelify Sans | kroje (Google Fonts) | OFL-1.1 |
| VT323 (Peter Hull), IBM Plex Mono (IBM) | kroje motywu Fosfor, dołączone w `hq/web/fonts/` | OFL-1.1 |

Pixel art wieży, pokoi i postaci jest rysowany kodem w tym repo (`hq/web/src/20-art.js`); inspiracja
przekrojami modeli z klocków, bez użycia znaków towarowych ani zasobów producentów zabawek i gier.

### Landing (`site/`)

| Projekt | Rola | Licencja |
|---|---|---|
| DM Sans, JetBrains Mono | kroje landingu, dołączone w `site/assets/fonts/` (serwowane lokalnie) | OFL-1.1 |

## 5. Obowiązki licencyjne w skrócie

| Licencja | Co robimy |
|---|---|
| MIT | zachowujemy informację o prawach autorskich i licencję (`LICENSE-UPSTREAM` przy każdym skillu) |
| Apache-2.0 | licencja przy skillu, `NOTICE` źródła (jeśli istnieje), treść bez zmian (zmiany oznaczylibyśmy w pliku) |
| AGPL-3.0 (SearXNG, Lightpanda, opcjonalnie Postiz) | programy uruchamiamy bez modyfikacji (Lightpanda: binarka z oficjalnego obrazu, tylko usunięte symbole debugowania), tylko prywatnie; zmieniona wersja udostępniana przez sieć innym wymagałaby publikacji źródeł |
| CC-BY-4.0 (model Parakeet) | uznanie autorstwa (NVIDIA) w tym pliku; model pobierany z Hugging Face, nie redystrybuujemy go |

Aktualizacja źródła = zmiana `rev` w locku (pełny SHA), build, przegląd różnic w skillach, evals, commit.
Walidator odrzuca źródło bez przypiętego SHA albo bez licencji.

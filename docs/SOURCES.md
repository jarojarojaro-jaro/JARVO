# Źródła i licencje (third-party notices)

Jarvo jest zbudowany na cudzej, otwartej pracy. Ten plik mówi, **co** wzięliśmy, **skąd**, na jakiej
**licencji** i **jak** spełniamy jej warunki. Narzędzia uruchamiane przez agentów (npm, Python, sidecary)
są opisane osobno w [TOOLBOX.md](TOOLBOX.md), razem z polityką licencji.

Każde repo z tego pliku (i każde źródło z `skills.lock.yaml`) ma wpis w spisie [`vendor/zrodla.yaml`](../vendor/zrodla.yaml):
status i ostatni przejrzany commit. `python3 scripts/zrodla.py sprawdz` pokazuje, co w nich doszło od przeglądu
(commity, nowe katalogi i skille, zmiana licencji). Spis trzyma też repo przejrzane, ale jeszcze niewdrożone
(`czeka`, `odlozone`). Nowej wersji nie bierzemy sama z siebie: aktualizacja przypięcia to decyzja właściciela.

## 1. Platforma

| Projekt | Rola | Licencja |
|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) | rdzeń: profile, kanban, cron, gateway, skille, obraz Docker | MIT |

Hermesa nie forkujemy: używamy oficjalnego obrazu i rozszerzamy go na krawędziach (profile, skille, narzędzia).

Komponenty obrazu `jarvo-hermes` o znaczeniu licencyjnym (pełna lista narzędzi: [TOOLBOX.md](TOOLBOX.md)):

| Projekt | Rola | Licencja |
|---|---|---|
| [Lightpanda](https://github.com/lightpanda-io/browser) 0.4.1 | przeglądarka headless dla `browser_*` (binarka z oficjalnego obrazu, tylko `strip`) | AGPL-3.0 |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | sterownik narzędzi przeglądarki Hermesa | Apache-2.0 |
| [Nutlope/inspo](https://github.com/Nutlope/inspo) (Together AI), pakiet npm `inspo-mcp` 0.1.16 (repo przejrzane na commicie `0e1e636`) | serwer MCP `inspo` Weba (skill `inspiracje-stron`): katalog prawdziwych stron jako inspiracja przed projektem; stdio, lokalnie, bez hostowanego endpointu i bez `TOGETHER_API_KEY`. Katalog i miniatury pobiera z CDN autorów, nie z obrazu. **Zrzuty i treści stron należą do ich autorów** (MIT obejmuje kod Inspo): tylko inspiracja, nie kopiujemy grafik ani tekstów, nie hostujemy zrzutów | MIT |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) (NVIDIA), eksport ONNX [istupakov/parakeet-tdt-0.6b-v3-onnx](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) | model rozpoznawania mowy (pobierany przy pierwszym użyciu, nie w repo ani w obrazie) | CC-BY-4.0 |
| [onnx-asr](https://github.com/istupakov/onnx-asr) + [ONNX Runtime](https://github.com/microsoft/onnxruntime) | uruchamianie modelu mowy na CPU | MIT |
| [Paradee-8M v1.0](https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.0) ([sahilmahendrakar/paradee](https://github.com/sahilmahendrakar/paradee), Sahil Mahendrakar; `paradee_int8.onnx`, SHA-256 `60e8f8a1…698eb`) | lektor angielski bez sieci (`jarvo-tts`, głos `en-US-Paradee`): model **w obrazie** (`/opt/jarvo/models/paradee/` razem z jego `LICENSE`), logika wnioskowania napisana według `paradee/tts.py` | Apache-2.0 |
| [misaki](https://github.com/hexgrad/misaki) 0.9.4 + [spaCy](https://github.com/explosion/spaCy) 3.8.16 z modelem `en_core_web_sm` 3.8.0 + [espeak-ng](https://github.com/espeak-ng/espeak-ng) przez `espeakng-loader` | tekst → fonemy dla Paradee (ten sam G2P co Kokoro); espeak-ng tylko dla słów spoza słownika | Apache-2.0 / MIT / MIT / GPL-3.0 (espeak-ng, uruchamiany jako biblioteka bez zmian) |
| [Silero VAD](https://github.com/snakers4/silero-vad) | wykrywanie mowy przed Parakeetem w `jarvo-stt` (pobierany przy pierwszym użyciu, nie w repo ani w obrazie) | MIT |
| [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (Shiqi Yu, OpenCV Zoo), [opencv/face_detection_yunet](https://huggingface.co/opencv/face_detection_yunet) `3cc26e7` (`face_detection_yunet_2023mar.onnx`, SHA-256 `8f2383e4…52fa4`) | wykrywanie twarzy do kadru rolek clipmakera (`twarze.py`); dekodowanie wyjść napisane od nowa według `cv::FaceDetectorYN`, bez OpenCV; pobierany przy pierwszym użyciu do `/opt/data/jarvo/models/yunet/` z przypiętej wersji i sprawdzany sumą, nie w repo ani w obrazie | MIT |
| [MODNet](https://github.com/ZHKKKe/MODNet) (ZHKKKe), eksport ONNX [DavG25/modnet-pretrained-models](https://huggingface.co/DavG25/modnet-pretrained-models) `903cc06` (`modnet_photographic_portrait_matting.onnx`, SHA-256 `07c308cf…84df9`) | maska osoby dla typografii Wideografa (`maska.py`: napis obok twarzy albo za osobą); pobierany przy pierwszym użyciu do `/opt/data/jarvo/models/modnet/` z przypiętej wersji i sprawdzany sumą, nie w repo ani w obrazie | Apache-2.0 |

## 2. Skille dołączane do agentów (vendoring)

Kopiowane przy buildzie z przypiętych commitów zapisanych w [`vendor/skills.lock.yaml`](../vendor/skills.lock.yaml).
Każdy skopiowany skill dostaje `LICENSE-UPSTREAM` (albo licencję z własnego katalogu), `NOTICE-UPSTREAM`
(jeśli źródło go ma) i `.vendored.json` (repo, commit, ścieżka, licencja). Treści skilli nie zmieniamy;
nasze adaptacje żyją w skillach własnych floty.

Przed wejściem do profilu każdy skill przechodzi **skan bezpieczeństwa** (`scripts/skan_skilli.py`):
- skaner Hermesa `tools/skills_guard.py` z obrazu;
- kontrole strukturalne za [getsentry/skills](https://github.com/getsentry/skills) `skill-scanner` (Apache-2.0):
  hooki w nagłówku, `!`polecenie``, pliki testów, skrypty `postinstall`, tekst w metadanych PNG, nagłówek YAML;
- wzorce za [affaan-m/ECC](https://github.com/affaan-m/ECC) `build-pi-core.js` (MIT): `curl|sh`, `npx -y`,
  sekrety, ukryte znaki Unicode.

Ustalenie high/critical zatrzymuje build, chyba że ktoś je przeczytał i dopisał jako fałszywy alarm do
[`vendor/skan-wyjatki.yaml`](../vendor/skan-wyjatki.yaml) (z powodem). Wyjątek jest przypięty do commitu źródła,
więc po zmianie `rev` w locku nowa wersja cudzego skilla przechodzi przegląd od nowa. Skille z obrazu Hermesa
tylko raportujemy (Hermes instaluje je jako wbudowane). Ręczny skan kandydata przed dodaniem do locka:
`python3 scripts/skan_skilli.py <katalog> --hermes-src /opt/hermes`.

| Źródło | Commit | Licencja | Dla kogo |
|---|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent): skille z drzewa obrazu | wersja obrazu | MIT | Sherlock, Web, Studio, Wideograf (manim-video, ai-presenter-video) |
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `5b2c000` | MIT | Sherlock, Web, Studio, Wideograf (video), Ads (ads, ab-testing, attribution, analytics, ad-creative) |
| [addyosmani/web-quality-skills](https://github.com/addyosmani/web-quality-skills) | `afa8da9` | MIT | Web |
| [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) | `e77e783` | MIT | Web (skille + skrypty w obrazie) |
| [anthropics/skills](https://github.com/anthropics/skills) | `3337550` | Apache-2.0 (tylko skille z licencją Apache w katalogu) | Web, Studio, Ręka, Wideograf (slack-gif-creator), Studio (algorithmic-art) |
| [Barty-Bart/motion-graphics](https://github.com/Barty-Bart/motion-graphics) (skill motion-broll) | `e8d610a` | MIT | Wideograf (B-roll zgrany ze słowami) |
| [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | `b65efe6` | MIT (assety CC0 / CC BY / OFL) | Wideograf (43 style filmu; biblioteka instalowana przez `narzedzia.py`) |
| [lemomo-ai/lemo-wake](https://github.com/lemomo-ai/lemo-wake) | `ebb758c` | CC BY-NC 4.0 (tylko niekomercyjnie; komercyjnie za zgodą autora); modele ONNX z Hugging Face na własnych licencjach (Apache-2.0, MIT) | Studio (skill `zywy-obraz`: obraz → pętla 5 s i warstwy PSD; biblioteka instalowana przez `lemo_wake.py`, bez skilla upload) |
| [alexgreensh/anidoodle](https://github.com/alexgreensh/anidoodle) | `f335700` | Apache-2.0 | Wideograf (rysunek kodem, muzyka syntezowana) |
| [buildwithhanif/claude-animation-skill](https://github.com/buildwithhanif/claude-animation-skill) | `4ddb8c8` | MIT | Wideograf (animacja w Node canvas, postaci, efekty, dźwięk syntezowany z osi czasu) |
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | `cf49eff` | Remotion License (darmowa dla osoby / firmy do 3 osób) | Wideograf (router `remotion-best-practices` ze wszystkimi `remotion-*/REFERENCE.md`) |
| [Vincentwei1021/video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | `e2d8928` | Apache-2.0 | Wideograf (kinowe filmy produktu; instaluje narzedzia.py); liczby 11 kart (czasy, krzywe, limity) w naszym `ujecia.js`, zasady zrzutu i wycinków w `assety.py --film` i `strona.js` |
| [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) | `49052d8` | MIT (papier, próbki, dane map CC0 / domena publiczna; obrysy liter OFL; ziarno, kurz, washi i zdjęcia bez podanego źródła) | Wideograf (skill `style-motion`: wzory 15 stylów motion design, silniki stylów przeniesione do `/_lib/jarvo/`; instaluje narzedzia.py) |
| [alchaincyf/huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | `26dba25` | MIT (kroje OFL; dane kresek `strokes.js` AR PL i postać autora poza MIT: nie instalujemy, klatki postaci tylko w podglądzie ich wzorów) | Wideograf (silnik kanwy 2D: 35 stylów malarskich, 8 gramatyk explainera, wykresy i schematy; instaluje narzedzia.py, polska nakładka `/_lib/jarvo/huashu_pl.js`; skille `gramatyki-explainera` i `style-malarskie`; rozbiór wzoru w `kadry.py wzor` za ich `breakdown.py`) |
| [diffusionstudio/lottie](https://github.com/diffusionstudio/lottie) | `3c72912` | MIT | Wideograf, Web (text-to-lottie) |
| [nolangz/pixel2motion](https://github.com/nolangz/pixel2motion) | `e9faedb` | MIT | Wideograf (logo → animacja SVG) |
| [bangtutorial/bang-motion](https://github.com/bangtutorial/bang-motion) | `c1aa65e` | MIT | Wideograf (motion graphics z marki) |
| [ythx-101/live-panel-skill](https://github.com/ythx-101/live-panel-skill) | `8a70aa2` | MIT (projekty odtworzone w przykładach należą do ich autorów) | Wideograf (żywe schematy: szablon strony i gramatyka ruchu; bez filmów przykładów) |
| [iart-ai/kinetic-typography-skills](https://github.com/iart-ai/kinetic-typography-skills) `fccc94b`, [iart-ai/data-animation-skills](https://github.com/iart-ai/data-animation-skills) `8ce2709`, [iart-ai/tiktok-video-skills](https://github.com/iart-ai/tiktok-video-skills) `2a77533` | jw. | MIT | Wideograf (typografia, wykresy, belki, odliczanie) |
| [jtydhr88/screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills) | `357d134` | MIT | Wideograf (5 skilli warsztatu do `scenariusz`) |
| [greensock/gsap-skills](https://github.com/greensock/gsap-skills) | `aed9cfd` | MIT | Wideograf, Web (8 skilli GSAP) |
| [CloudAI-X/threejs-skills](https://github.com/CloudAI-X/threejs-skills) | `b1c6230` | MIT (deklarowana w README, bez pliku; autorstwo w `notice`) | Wideograf, Web (10 skilli Three.js) |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | `d16ebe6` | MIT | Wideograf, Web (rzemiosło animacji UI) |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `114ea1d` | Apache-2.0 | Web, Studio (detektor anty-wzorców, silnik pobierany do `narzedzia/impeccable`) |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `d81f3a1` | MIT | Jarvo, Ręka (`writing-for-agents`: pisanie SOUL i skilli) |
| [getsentry/skills](https://github.com/getsentry/skills) `security-review` (na bazie [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)) | `d18b7aa` | CC-BY-SA-4.0 (licencja skilla; reszta repo Apache-2.0) | Web (przegląd kodu wg OWASP: JS/Next, Python, Docker) |
| [trailofbits/skills](https://github.com/trailofbits/skills) `supply-chain-risk-auditor` | `82fe822` | CC-BY-SA-4.0 (całe repo, także skrypty) | Web (ryzyko zależności: OSV, porzucone repo, wydawcy npm, skrypty instalacyjne) |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | `8798e40` | Apache-2.0 | Wideograf (wideo z HTML) |
| [expo/skills](https://github.com/expo/skills) | `c0dadf3` | MIT | Twórca aplikacji (10 skilli Expo: router, natywny wygląd, animacje, dane, strona → aplikacja, sklepy, EAS Update, podnoszenie SDK; bez skilli wysyłających dane do Expo, `submit-expo-feedback` w `approvals.deny`) |
| [callstackincubator/agent-skills](https://github.com/callstackincubator/agent-skills) | `61e6e7d` | MIT | Twórca aplikacji (`react-native-best-practices`, `react-navigation`, `upgrading-react-native`) |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | `063bee9` | MIT (w README, autorstwo w `notice`) | Twórca aplikacji (`react-native-skills`) |
| [Remocn/remocn-studio](https://github.com/Remocn/remocn-studio) | `86f64ee` | MIT | Wideograf (`motion-design`: reżyseria ruchu i wzorce kompozycji, `video-lessons`: znane usterki renderu); ich pojęcia (Studio, `design_check`, panel właściwości) tłumaczy reguła 12 `film-z-kodu`; w HQ za nimi poszły uwagi z kadrem w edytorze, `html_wideo.py pomiar` i podgląd animacji z parametrami (◐ Animacja) |
| [appeeky/aso-skills](https://github.com/appeeky/aso-skills) | `8de1ee1` | MIT | Twórca aplikacji (6 skilli ASO: metadane, zrzuty, odrzucenia, Google Play, lokalizacja, opinie) |

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

Kod skopiowany do skilla własnego floty (`shared/skills`), z plikiem licencji autorów obok:

| Projekt | Wersja | Licencja | Dla kogo |
|---|---|---|---|
| [iso-glow](https://iso-glow.vercel.app) (April Zhu), na [MrBongoC/ai-iso-skill](https://github.com/MrBongoC/ai-iso-skill) (iso-figure, Tolga Cohce) | paczka `iso-glow.tar.gz` (SHA-256 `1e69ce19…89bc1`), iso-figure `44b4da7` | MIT (© 2026 April Zhu, © 2026 Tolga Cohce; `shared/skills/izometria/assets/iso-glow/LICENSE`) | Web, Studio, Wideograf: skill `izometria`. Szablon galerii, kernel izometrii i dwa przykłady bez zmian w `assets/iso-glow/` (ich `SKILL.md` jako `ISO-GLOW.md`, żeby nie był osobnym skillem); nasza nakładka `iso.py` + `iso_jarvo.js` (polskie napisy, krój JetBrains Mono zamiast Google Fonts, kolor marki, kadr, zegar wirtualny do PNG i filmu, kontrola figur). Stopka „Made with ISO-GLOW” zostaje na naszych materiałach; na pracach dla klientów jej nie ma, autorów podajemy tutaj |

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
| Hermes Agent `grounded-citations` 1.2.0 (Hermes Agent + Teknium) | MIT | `cytowania` Sherlocka i silnik `profiles/jarvo-sherlock/scripts/sources.py`: rejestr `url → [n]` z blokadą, dopasowanie cytatów odporne na znaczniki markdown, render bloku źródeł i `verify` raportu; po polsku, z oceną A–D, zapisanym tekstem stron, SHA-256 i linkiem `#:~:text=` |
| [rlaope/oh-my-hermes](https://github.com/rlaope/oh-my-hermes) (commit `e3880be9146778d620a87ddfa2848ce811a97bd5`, © 2026 oh-my-hermes contributors) | MIT | kalibracja pod rodzinę modelu (`shared/calibration/`, za `MODEL_OPTI.md`: cechy GPT-6 z przewodnika OpenAI, Claude, DeepSeek (także za DeepSeek Harness), Kimi); dyscyplina wykonawcy w kontrakcie zlecenia (echo celu, jedna weryfikacja z limitem 2 poprawek, odmowa = granica, blokada tylko z konkretnego powodu, stany dowodu); `bramka-jakosci` Weba (rubryka designu, werdykt 0–100 z progiem 90, dane o CSS Design Awards); scenariusze `hostile.cjs`; `wywiad` Jarva (jedno pytanie naraz, 6 rund, zatrzymanie); `szybki-fakt` Sherlocka; księga lekcji w `fleet-improvement` |
| [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) (© 2025 Anthropic) | MIT | `bezpieczenstwo-aplikacji` Weba: metodyka przeglądu kodu i filtr fałszywych alarmów (za `claudecode/prompts.py`, `findings_filter.py`), zaadaptowane po polsku w `references/przeglad-kodu.md` |
| [athemeroy/awesome-opus-5-5-videos](https://github.com/athemeroy/awesome-opus-5-5-videos) (`docs/production-brief.md`, autor: athemeroy) | CC-BY 4.0 | szablon briefu produkcyjnego, zaadaptowany w `film-z-kodu/references/produkcja-etapami.md`; analiza trendu w `kontrola-wideo/references/zakazane.md` |
| [obra/superpowers](https://github.com/obra/superpowers) (commit `8ca22db`, © Jesse Vincent) | MIT | kontrakt zlecenia pkt 14 (poprawki po recenzji: pytanie przy niejasnym punkcie, sprzeciw z dowodem, każda poprawka sprawdzona) za `receiving-code-review`; `sdlc-review` 4b |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) (commit `c70874f`, © 2026 Affaan Mustafa) | MIT | kontrakt pkt 12 (nie osłabiam kontroli) za `loop-design-check` i `config-protection`; pkt 17 i `scripts/odcisk.py` (zgoda A2 przypięta do wersji, jedno wykonanie na zgodę) za `operator-approval-loop`; wzorce skanu skilli (`scripts/skan_skilli.py`) za `build-pi-core.js`; skill `demo-strony` i `demo_strony.py` (rozpoznanie → próba → nagranie, kursor, tempo, napisy kroków) za `ui-demo` |
| [browser-use/video-use](https://github.com/browser-use/video-use) (commit `b877063`, © 2026 Browser Use) | MIT | pomysły przeniesione do kodu Wideografa i edytora HQ, bez ich skryptów i bez ElevenLabs: 25 ms wyciszenia na każdym twardym cięciu w eksporcie (`edytor.CICHE_CIECIE`); obrót z macierzy wyświetlania przy odczycie wymiarów (ich poprawka `b5352cf`); obraz każdego cięcia gotowego filmu do samokontroli (`krytyka.py ciecia`, za ich `timeline_view`: klatki, fala, słowa, cisza); style koloru klipu na wzór ich `grade.py` (`neutral_punch`, `warm_cinematic`) i „Auto” jak ich `auto_grade` (pomiar klatek, korekta najwyżej ±30, bez przesunięcia barwy; `edytor.KOLOR_STYLE`, `kolor_z_pomiaru`) |
| [getsentry/skills](https://github.com/getsentry/skills) (commit `d18b7aa`, `skill-scanner`) | Apache-2.0 | kontrole strukturalne i wzorce skanu skilli w `scripts/skan_skilli.py` |
| [trailofbits/skills](https://github.com/trailofbits/skills) (commit `82fe822`, `insecure-defaults`) | CC-BY-SA-4.0 | tylko metoda („czy aplikacja działa z tą wartością, gdy brak konfiguracji”): reguły i opisy własne w `security_check.py` (sekret z wartością zapasową, fail-open, TLS, JWT, domyślne hasła, stos błędu, introspekcja, uprawnienia) |
| [superdesigndev/treg](https://github.com/superdesigndev/treg) (commit `8b2826d`, `skills/lead-signals`, © 2026 Superdesign) | Apache-2.0 z warunkami dodatkowymi (zakaz oferowania jako usługi hostowanej dla innych; użytek wewnętrzny dozwolony) | metoda Łowcy leadów (wykryj → odsiej → kontakt → ranking, ocena dopasowanie → świeżość → siła, monitoring z bazą) w [LEADY.md](LEADY.md) i skillach `jarvo-lowca`; tekst i źródła własne (polskie rejestry zamiast płatnego katalogu treg) |
| [Yuzzyuk/marketing-os](https://github.com/Yuzzyuk/marketing-os) (commit `bb67dff`, © 2026 Marketing OS contributors) | MIT | `hooks.md` → wspólny skill `hooki` (trzy warstwy, 18 taktyk, korpus, rozbieg, lejek diagnozy, drabina wierności); `slop-patterns.md` → `copy-pl/references/sito.md`; oba po polsku |
| [mutonby/openshorts](https://github.com/mutonby/openshorts) (commit `06a119c`, `clip_selection.py`, `gemini_worker.py`, `active_speaker.py`, `punch_in.py`, `thumbnail.py`) | MIT (bez katalogu `cloud/`, którego nie bierzemy) | Wideograf, clipmaker: kadr na twarz (`klipy.py sledz` i `ustawienia` za `SpeakerTracker` i `SmoothedCameraman`: największa twarz, obecna ×3, zmiana po potwierdzeniu, mały ruch ignorowany), kto mówi (`klipy.py mowiacy` i `twarze.py usta` za `active_speaker.py`: ruch ust w czasie słów, normalizacja do zakresu osoby, trzy okna przewagi; spoczynek i skala normalizacji poprawione, żeby ktoś, kto mówi cały czas, nie spadał do zera), zbliżenia na akcentach (`klipy.py akcenty` i `przybliz` za `punch_in.py`: ×1,12, najwyżej ~3 na minutę i co 18 s; akcent ze słów i ich głośności zamiast samej obwiedni dźwięku, czego oni nie mieli), okładka rolki (`klipy.py okladka` za `rank_frame`: pole twarzy × ostrość z laplasjanu, u nas ostrość samej twarzy plus twarz do kamery i otwarte oczy; to samo sprawdza pierwszą klatkę), dosuwanie granic segmentu do przerw między słowami (`klipy.py dosun`, liczby 0,35 / 0,45 s), ostrzeżenie o wspólnym materiale rolek, okna ~90 s z oceną 0–100 każdego i zasady promptu (test 2 sekund, „o tym momencie, nie o całym filmie”, samodzielność wcześniejszym początkiem, nie ucięciem puenty), własnym kodem i tekstem; ich aplikacji (FastAPI, Gemini, MediaPipe) nie uruchamiamy, twarze wykrywa YuNet |
| [dmtrKovalenko/fframes](https://github.com/dmtrKovalenko/fframes) (commit `055bb6b`, `skills/fframes-video/references/design.md` i `audio.md`) | MIT | tylko liczby, własnym tekstem: czasy i krzywe ruchu, sprężyny, kolejność wejść w kontrakcie animacji (`rodzaje-filmu/references/kontrakt-html.md`), czasy efektów, głośności względem głosu i rozpiętość głośności w `lektor-i-dzwiek`, ostrzeżenie `qa_wideo.py` o rozpiętości (LRA) powyżej 10 LU; silnika fframes (Rust, GPU) nie używamy |
| [heygen-com/hyperframes-community-skills](https://github.com/heygen-com/hyperframes-community-skills) (commit `ba7a0bb`, `skills/camera-3d-captions`, © HeyGen) | Apache-2.0 | wzorce przeniesione do typografii Wideografa, kod własny w `hq/web/src/48-typografia.js` (renderer edytora HQ i eksportu): kontrola napisów `typoKontrola` / `typografia.py sprawdz` za ich `frame-bounds.js` (grupa poza kadrem przez kilka kroków po 1/15 s) i `glyph-gaps.js` (tusz liter dwóch słów bliżej niż 4 px przy 1080) oraz ich regułą czytelności słowa za osobą (≥ 60% widać); u nas tusz z kanwy renderera zamiast metryk kroju, plus bloki na sobie, napis za osobą niczym niezasłonięty i strefy platform |
| [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (commit `a991599`) | MIT | pomysły przeniesione do kodu Wideografa i edytora HQ, bez ich skryptów: rozpoznanie filmu HDR z telefonu (HLG, HDR10, Dolby Vision iPhone'a) i przeliczenie na zwykły obraz (SDR) łańcuchem `zscale` → `tonemap` w eksporcie, podglądzie i montażu (`edytor.hdr`, `sdr_filter`); parametry mapowania (`mobius`, bez odbarwienia) dobrane własnym pomiarem nasycenia i jasności; czysty głos w trzech poziomach za ich `VOICE_LEVELS` (highpass, de-esser, afftdn, kompresor, limiter; `edytor.glos_filter`), z progiem odszumiania z tła nagrania i ekspanderem w pauzach dodanymi po naszym pomiarze (ich stały próg ściszał tło o ~3 dB, a mocny poziom robił pauzy głośniejsze); stabilizacja nagrań z ręki za ich `stabilize.py` (dwa przejścia vidstab, tryb statywu: `montaz.py stabilizuj`), z naszym pomiarem drżenia kamery przed i po, radą siły z pomiaru i interpolacją dwuliniową z wyostrzeniem (2× szybciej niż bicubic). Pozostałe pomysły z przeglądu 2026-10-07 (dźwięk z osobnego mikrofonu, rozmycie twarzy i tablic, kontrole plików z telefonu) właściciel odrzucił |
| [Vincentwei1021/anything2explainer](https://github.com/Vincentwei1021/anything2explainer) (commit `735c79c`) | PolyForm Noncommercial 1.0.0: **nie kopiujemy kodu, tekstu ani kart**, bierzemy myśl i liczby, opis i kod własne | zasady narracji i wynik ślepego porównania 8,2 vs 4,3 (`scenariusz/references/narracja.md`, `film.py narracja --sprawdz`); akapit = ujęcie i długości pauz (`film.py narracja`, `os_czasu.json`); brief do filmu Sherlocka (`raport-sledztwa/references/brief-do-filmu.md`, `fakty.py`: liczby na długość filmu, ocena źródła, przeliczenie na skalę, analogie z miejscem, w którym kłamią, wymowa) i sprawdzanie liczb lektora i ekranu z briefem; kontrole kompozycji w `pomiar.py` (pusta scena, oddech) |
| [Vincentwei1021/video-talkcraft](https://github.com/Vincentwei1021/video-talkcraft) (commit `4cd673d`) | PolyForm Noncommercial 1.0.0: **nie kopiujemy kodu, tekstu ani kart**, bierzemy myśl i liczby, opis i kod własne | słyszalność efektów pod głosem i muzyką (`projekt.py slychac`, progi za ich zasadą) |
| [opencoredev/convt](https://github.com/opencoredev/convt) (commit `29831b6`) | AGPL-3.0: **nie kopiujemy kodu**, bierzemy tylko pomysł, kod własny | wspólny skill floty `konwersja-plikow` i karta Konwerter w Centrali HQ: graf formatów, w którym każdy silnik zgłasza swoje krawędzie, najtańsza trasa przez najwyżej 3 kroki (np. DOCX → HTML → PDF), wybór celu pogrupowany według rodzaju pliku; u nas na serwerze (Pillow, FFmpeg, Ghostscript, qpdf, pandoc, Chromium, LibreOffice), nie w przeglądarce (`shared/skills/konwersja-plikow/scripts/konwertuj.py`) |
| JohnHeibel/ClaudeAnimationBase (+ briefy @donaldjewkes) | MIT | wzorzec bramek etapów w `film-z-kodu/references/produkcja-etapami.md` |

## 4. Jarvo HQ (GUI)

| Projekt | Rola | Licencja |
|---|---|---|
| [htm](https://github.com/developit/htm) 3.1.1 | składnia podobna do JSX bez kompilacji (`hq/web/vendor/`, z licencją) | Apache-2.0 |
| React | dostarczany przez SDK dashboardu Hermesa; w trybie demo 18.3.1 z cdnjs | MIT |
| Bricolage Grotesque, Atkinson Hyperlegible, JetBrains Mono, Pixelify Sans | kroje (Google Fonts) | OFL-1.1 |
| Inter (The Inter Project Authors, przez `@fontsource-variable/inter` 5.3.0) | krój zapasowy edytora filmów w HQ, dołączony w `hq/web/fonts/` (latin + latin-ext, zmienna grubość) | OFL-1.1 |
| Anton, Bebas Neue, Barlow Condensed, Oswald, Playfair Display, Caveat, Rubik Dirt, Bricolage Grotesque, JetBrains Mono, Montserrat, Titan One, Baloo 2, Bangers, Instrument Serif, Space Grotesk, Unbounded, Shrikhand, Pacifico, Tilt Neon, Poppins, Inter, Archivo Black, Rubik, League Spartan, Kanit, Outfit, Syne, Raleway, Teko, Fjalla One, Staatliches, Big Shoulders Display, Saira Condensed, Nunito, Paytone One, DynaPuff, Coiny, Grandstander, Abril Fatface, DM Serif Display, Lora, Bodoni Moda, Cormorant Garamond, Fraunces, Alfa Slab One, Yeseva One, Dancing Script, Lobster, Kaushan Script, Great Vibes, Amatic SC, Caveat Brush, Patrick Hand, Sedgwick Ave, Righteous, Bungee, Monoton, Press Start 2P, Rubik Glitch, Rubik Bubbles, Russo One, Black Ops One, Sigmar, Rammetto One, Audiowide, Chakra Petch, Space Mono, Major Mono Display (68 rodzin przez Fontsource 5.3.0, wersje i pliki w `scripts/kroje.py`) | kroje napisów i typografii edytora i Wideografa, dołączone w `hq/web/fonts/kroje/` z licencjami `OFL-*.txt` i sumami SHA-256 | OFL-1.1 |
| [Kenney](https://kenney.nl/assets) (paczki Interface Sounds, UI Audio, Impact Sounds, Digital Audio, Casino Audio, Sci-Fi Sounds, RPG Audio, Music Jingles) i [Freesound](https://freesound.org) (tylko dźwięki z licencją CC0, sprawdzaną przy pobraniu; autor i adres każdego pliku w `LICENCJE.md`) | biblioteka dźwięków menu Audio edytora i Wideografa: 157 efektów i 9 podkładów w `hq/web/dzwieki/` (lista, źródła i sumy w `scripts/dzwieki.py`) | CC0-1.0 |
| VT323 (Peter Hull), IBM Plex Mono (IBM) | kroje motywu Fosfor, dołączone w `branding/fonts/` | OFL-1.1 |

Pixel art wieży, pokoi i postaci jest rysowany kodem w tym repo (`hq/web/src/20-art.js`); inspiracja
przekrojami modeli z klocków, bez użycia znaków towarowych ani zasobów producentów zabawek i gier.

### Landing (`site/`)

| Projekt | Rola | Licencja |
|---|---|---|
| DM Sans, JetBrains Mono | kroje landingu, dołączone w `site/assets/fonts/` (serwowane lokalnie) | OFL-1.1 |

## 5. Obowiązki licencyjne w skrócie

| Licencja | Co robimy |
|---|---|
| MIT | zachowujemy informację o prawach autorskich i licencję (`LICENSE-UPSTREAM` przy każdym skillu; kod skopiowany do skilla własnego: plik `LICENSE` autorów obok kopii) |
| Apache-2.0 | licencja przy skillu, `NOTICE` źródła (jeśli istnieje), treść bez zmian (zmiany oznaczylibyśmy w pliku); model MODNet pobierany z Hugging Face, nie redystrybuujemy go; model Paradee jest w obrazie bez zmian, z plikiem `LICENSE` autorów obok (repo nie ma `NOTICE`) |
| AGPL-3.0 (SearXNG, Lightpanda, opcjonalnie Postiz) | programy uruchamiamy bez modyfikacji (Lightpanda: binarka z oficjalnego obrazu, tylko usunięte symbole debugowania), tylko prywatnie; zmieniona wersja udostępniana przez sieć innym wymagałaby publikacji źródeł |
| CC-BY-SA-4.0 (getsentry `security-review`, Trail of Bits) | dołączamy **bez zmian**, z atrybucją i licencją przy skillu; tłumaczenie albo przeróbka byłaby adaptacją i musiałaby zostać na CC BY-SA, dlatego metodę Trail of Bits `insecure-defaults` przepisaliśmy własnymi regułami (`security_check.py`), bez kopiowania tekstu. Znaki towarowe (logo Trail of Bits, Sentry) nie są objęte licencją |
| CC-BY-4.0 (model Parakeet) | uznanie autorstwa (NVIDIA) w tym pliku; model pobierany z Hugging Face, nie redystrybuujemy go |
| cudze strony (katalog Inspo, własna baza `inspiracje/` w skarbcu) | bez licencji dla nas: bierzemy wzorce (układ, rytm, skala), nie grafiki, zdjęcia, teksty, logo ani kod; zrzuty zostają w skarbcu do użytku wewnętrznego, nie trafiają do projektów, podglądów ani do klientów |

Aktualizacja źródła = zmiana `rev` w locku (pełny SHA), build, przegląd różnic w skillach, evals, commit.
Walidator odrzuca źródło bez przypiętego SHA albo bez licencji.

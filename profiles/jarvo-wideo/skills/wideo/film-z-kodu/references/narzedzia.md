# Silniki zewnętrzne u nas

motion-broll, lemo-opuscar, anidoodle, Remotion (+ iart), video-shotcraft, bang-motion, pixel2motion, Lottie.
Skille silników są w profilu (`skills/video/<nazwa>`, przypięte commity w `vendor/skills.lock.yaml`; video-shotcraft
i player Lottie instaluje `narzedzia.py`). Ich instrukcje zakładają laptopa z Claude Code; poniżej różnice u nas.
Ścieżka skilla: `SK=$HERMES_HOME/skills/video/<nazwa>` (zmienne nie przeżywają między wywołaniami terminala:
wklejaj przypisanie w każdym).

## Wspólne
- **Nie instaluj przeglądarki ani playwrighta sam** (`npx playwright install`, `setup.sh` z repo): obraz ma
  Chromium headless pasujący do playwright 1.63. Raz: `python3 $HERMES_HOME/scripts/narzedzia.py instaluj <narzędzie>`,
  potem w każdym wywołaniu: `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env <narzędzie>)"`.
- Stan: `narzedzia.py sprawdz` (JSON: przeglądarka, prores_ks, co zainstalowane).
- Projekt w katalogu karty: `out/wideo/src/<nazwa>/` (małe litery, cyfry, myślniki; bez `#` i `%`).
- Lektor PL: Edge TTS (`film.py lektor`, `lektor_linie.py`), czasy słów bez whispera; transkrypcja nagrań: Parakeet
  (`montaz.py transkrypcja`, `napisy.py`). Nie instaluj faster-whisper.
- Każdy wynik: `qa_wideo.py` + `kontrola-wideo`, jak każdy film. Silniki składają MP4 z klatek JPEG, więc często
  wychodzi `yuvj420p` (pełny zakres, część telefonów źle odtwarza): `python3 $HERMES_HOME/scripts/montaz.py napraw <film> -o <film-ok>`.

## motion-broll (B-roll do nagrania)
```bash
SK=$HERMES_HOME/skills/video/motion-broll; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env motion)"
mkdir -p motion/{clips,dist,out,work,inputs} && cp /opt/data/jarvo/inbox/<nagranie>.mp4 motion/work/source.mp4
python3 $HERMES_HOME/scripts/napisy.py motion/work/source.mp4          # Parakeet → motion/work/source.srt (popraw nazwy!)
$PYTHON $SK/scripts/words.py motion/work/source.srt > motion/work/words.txt
$PYTHON $SK/scripts/inspect_video.py motion/work/source.mp4 motion/work  # video.json + contact.png (obejrzyj)
```
Dalej kroki 4–8 z `$SK/SKILL.md` (plan w tabeli → klipy w `motion/clips/` → `build.py` → `beats.js` (stopklatki) →
`render.js` → `composite.py` + `make_pages.py`). Wszystkie `node` i `python3` z tych kroków uruchamiaj po `eval` powyżej
(`NODE_PATH` i `$PYTHON` ustawione), `setup.sh` pomiń. Panele z przezroczystością (`bg:null`) → `.mov` ProRes 4444
(`prores_ks` jest w obrazie). Plan (krok 4) i wywiad: decyzje z karty; pytanie tylko, gdy brak nagrania albo gęstości.
Wynik dla użytkownika: klipy + `preview.mp4` + `TIMING.md` (montaż finalny u niego albo nasz `montaz.py`).

## lemo-opuscar (film w stylu)
```bash
eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env lemo)"      # LIB, LEMO_OPUSCAR_HOME, PLAYWRIGHT_CHROME
cat "$LIB/AGENTS.md"; sed -n 1,80p "$LIB/styles/README.md"         # potem DIRECTOR.md, TECHNIQUE.md, STYLE.md stylu
```
- `sh $SK/scripts/setup.sh` znajdzie bibliotekę w `$LEMO_OPUSCAR_HOME` (przypięty commit, bez aktualizacji);
  `setup.sh deps` nic nie zrobi (zależności gotowe). Demo stylu do nauki: `sh $SK/scripts/setup.sh demo <slug>`.
- **Lektor PL:** zamiast `core/tts/tts.py` (Kokoro: tylko EN/ZH) i `asr_check.py`:
  `python3 $HERMES_HOME/scripts/lektor_linie.py <projekt>/lines.json <projekt>/voices --glos pl-PL-ZofiaNeural --sprawdz`
  (te same pliki: `<id>.wav`, `dur.json`, `words.json`). Liczby w tekście lektora słownie, w napisach cyframi.
- **Muzyka:** sample instrumentów (1,35 GB) i Kokoro są tylko z `JARVO_EXTRAS="lemo"`. Bez nich: `core/audio/pluck.py`,
  `sfx.py` (proceduralne, bez plików) albo muzyka z anidoodle / biblioteki marki.
- Render: `cd "$LIB" && node core/render/video.mjs "<projekt>" --fps 24 --workers 2 --out "<projekt>/out/video24.mp4"`
  (**2 workery** na VPS 8 GB: każdy to osobna przeglądarka), miks `sh core/render/mux.sh …` (−14 LUFS).
- Film to 30–60 min pracy: storyboard tylko, gdy karta prosi. Wynik: `<nazwa>.mp4`, `.srt`, `poster.jpg`, `TREATMENT.md`.

## anidoodle (rysunek, timelapse, muzyka kodem)
```bash
SK=$HERMES_HOME/skills/video/anidoodle; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env anidoodle)"
node $SK/engine/tools/scaffold.mjs out/wideo/src/art --film intro --format 9x16 --duration 20   # albo --still hero
cd out/wideo/src/art && npm install --omit=optional --prefer-offline                                 # bez pobierania przeglądarki
node tools/still.mjs intro --frame 0 --out out/look.png --scale 2     # look → vision
node tools/render.mjs intro --workers 2 --out out/intro.mp4           # .gif | .webm (alfa) | .apng
node tools/gate.mjs intro                                            # BRAMKA: determinizm, kontrakt, martwy czas
node tools/emit.mjs intro --out out/intro.html                        # cały film w 1 pliku HTML (dla jarvo-web)
```
- Kontrakt twardy: `draw(ctx, frame, env)` czysta; losowość tylko `rng(seed)`; zakazane `Math.random`, `Date`,
  `performance.now`, `ctx.filter`, DOM, `new Image`, sieć. Siatka czasu: tabela cue, cięcia na taktach.
- Muzyka: nuty w kodzie (`line(3, "C5:2 Bb4:.5 | …")`); agent nie słyszy, więc zmierz `tools/music.mjs`
  (głośność, zakres, jasność) i w RAPORT daj 8-sekundową próbkę do odsłuchu. Plik audio z renderu → `muzyka.plik` w `film.py`.
- `gate.mjs` szuka `out/<film>.mp4`; renderujesz pod inną nazwą → skopiuj.

## Remotion (`remotion-best-practices` + iart: wykresy, infografiki, belki, odliczanie)
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj remotion; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env remotion)"
mkdir -p out/wideo/src && cd out/wideo/src
npx create-video@4.0.529 --yes --blank --no-tailwind rem && cd rem && npm install --prefer-offline
npx remotion still src/index.ts <Kompozycja> out/look.png --frame=0 --browser-executable="$REMOTION_BROWSER_EXECUTABLE"
npx remotion render src/index.ts <Kompozycja> out/film.mp4 --concurrency=2 --browser-executable="$REMOTION_BROWSER_EXECUTABLE"
```
- `remotion-best-practices` to router: czytasz tylko potrzebny `remotion-*/REFERENCE.md` (create, markup, render,
  captions, multimedia, maps). **Pomiń** `remotion-upgrade` (wersje są przypięte), `remotion-saas` (Lambda, Vercel)
  i `remotion studio` (serwer podglądu nie jest potrzebny: `remotion still` + vision). Render robisz zawsze, gdy karta
  prosi o film (zdanie „render only if the user asks” dotyczy pracy przy laptopie).
- **Zawsze** `--browser-executable="$REMOTION_BROWSER_EXECUTABLE"` przy `still`, `render`, `compositions`
  (przeglądarka z obrazu); bez niej Remotion pobiera własną (~100 MB). Dotyczy też komend ze skilli iart.
- `--concurrency=2` na VPS 8 GB. Zasady klatki: `useCurrentFrame()` + `interpolate`/`spring`, zero `Math.random` (`random(seed)`).
- Skille iart odsyłają do `scripts/seek-shot.sh`, `contact-sheet.sh`, `probe-mp4.sh` (nie ma ich u nas):
  zamiast nich `html_wideo.py klatki … --arkusz` (HTML), `qa_wideo.py <film> --arkusz` (MP4: parametry + arkusz).
- Wynik: `montaz.py napraw` (zakres TV, faststart), potem `qa_wideo.py`. Licencja Remotion: osoba / firma do 3 osób
  za darmo; większa firma → licencja firmowa. Zapisz w RAPORT.md.

## video-shotcraft (kinowy film produktu, Remotion)
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj shotcraft; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env shotcraft)"
sed -n 1,120p $SHOTCRAFT/SKILL.md          # przepisy ujęć: $SHOTCRAFT/references, dema: $SHOTCRAFT/demos
cp -r $SHOTCRAFT/template out/wideo/src/promo && cd out/wideo/src/promo && npm ci --prefer-offline
npx remotion still src/index.ts AiflPromo out/look.png --frame=60 --browser-executable="$REMOTION_BROWSER_EXECUTABLE"
npx remotion render src/index.ts AiflPromo out/promo.mp4 --concurrency=2 --browser-executable="$REMOTION_BROWSER_EXECUTABLE"
```
- SKILL.md jest po chińsku (+ opis EN): czytasz, piszesz RAPORT po polsku. Opcjonalny Runway pomijamy (płatny).
- Screenshoty strony klienta: `cp $SHOTCRAFT/assets/scripts/capture-template.mjs .`, popraw CONFIG na górze,
  `python3 $HERMES_HOME/scripts/narzedzia.py link .`, `node capture-template.mjs` (puppeteer na przeglądarce z obrazu).
- Dema z `@remotion/motion-blur`: `npm i @remotion/motion-blur@4.0.484 --prefer-offline` w projekcie.
- Dźwięki z `assets/audio/` wolno używać (ATTRIBUTION.md), źródło do RAPORT.md. Workbench (port 5198) nie jest potrzebny.

## Animacja HTML → wideo: `html_wideo.py` (nasza animacja, iart kinetic-typography, bang-motion, pixel2motion)
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj html        # raz: playwright (Python) = wersja przeglądarki z obrazu
H=$HERMES_HOME/scripts/html_wideo.py
python3 $H klatki out/wideo/src/typo/type.html --preset iart --rozmiar 1080x1920 --czasy 0,0.4,0.8,1.5 --arkusz out/wideo/qa-typo.jpg
python3 $H wideo  out/wideo/src/typo/type.html --preset iart --rozmiar 1080x1920 --dlugosc 4 -o out/wideo/typo.mp4
python3 $H wideo  out/wideo/src/logo/logo_motion.html --preset pixel2motion --skala 2 --dlugosc 2.4 --alfa -o out/wideo/logo.mov
python3 $H wideo  out/wideo/src/opener/index.html --preset bang --dlugosc 12 -o out/wideo/opener.mp4
```
- **Nasza animacja** (Canvas, SVG, Three.js, GSAP): kontrakt `rodzaje-filmu/references/kontrakt-html.md`,
  `--preset jarvo` (serwer lokalny, biblioteki z `/_lib/`, `?render=1`), `--subklatki 4` = motion blur.
- Strona musi mieć uprząż czasu: iart `?t=<s>` + `window.__ready`, pixel2motion `?t=<ms>` + `window.__p2mReady`,
  bang-motion `window.OPENER.seek(t)`. Własna animacja: `--param/--jednostka` albo `--seek "t => tl.seek(t)"`.
- `.mov --alfa` (ProRes 4444) do nakładania na nagranie; `.mp4` do publikacji. Potem `qa_wideo.py`, lektor i napisy jak zawsze.
- **bang-motion** (SKILL.md po indonezyjsku): `snap.mjs` i `export-frames.mjs` zastępuje `html_wideo.py --preset bang`
  (bez serwera na 5178). Oryginał też działa: skopiuj skrypt do projektu, `narzedzia.py link .`, `eval "$(… env html)"`.
  `kepala-ekspresi.py` potrzebuje OpenCV (nie instalujemy); `scripts/ae/` to most do After Effects (pomiń).
- **pixel2motion**: skrypty Phase 1–3 uruchamiaj `$PYTHON` po `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env html)"`
  (`CHROME_BIN` dla `render_overlay.py`, playwright dla `capture_motion_frames.py`, `probe_motion_continuity.py`).
  `export_claude_videos.mjs` to demo autora (Chrome z macOS): pomiń, MP4/MOV robi `html_wideo.py`.
  Błąd „Executable doesn't exist … chromium_headless_shell-NNNN” (przeglądarka w obrazie z innej wersji niż
  playwright 1.63)? Te same klatki: `html_wideo.py klatki logo_motion.html --preset pixel2motion --czasy 0,0.3,0.7,1.2`
  (podaje przeglądarkę wprost; czasy w sekundach, strona dostaje ms).

## Lottie (`text-to-lottie`): player Skottie + eksport
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj lottie; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env lottie)"
mkdir -p "$LOTTIE_PLAYER/public/projects/<projekt>/scene-1"          # tu lottie.json, controls.json, fonty, obrazy
(cd "$LOTTIE_PLAYER" && nohup npm run dev -- --host 127.0.0.1 --port 3030 > /tmp/lottie-player.log 2>&1 &)
grep -m1 -o 'http://127.0.0.1:[0-9]*' /tmp/lottie-player.log   # port, który naprawdę dostał (skill: nie zakładaj 3030)
python3 $HERMES_HOME/scripts/html_wideo.py lottie "$LOTTIE_PLAYER/public/projects/<projekt>/scene-1/lottie.json" --klatki 0,45,89 --arkusz out/wideo/qa-lottie.jpg
python3 $HERMES_HOME/scripts/html_wideo.py lottie "$LOTTIE_PLAYER/public/projects/<projekt>/scene-1/lottie.json" -o out/wideo/belka.mov --alfa
```
- Skill wymaga oficjalnego playera: to on (przypięty commit) jest w `$LOTTIE_PLAYER`; `npx degit` pomiń.
  `/__context` i `?frame=N` z playera działają pod portem z logu. `html_wideo.py lottie` renderuje tym samym
  Skottie (canvaskit z playera), bez interfejsu: klatki do oceny i film (`.mov --alfa` na nagranie, `.mp4`, `.gif`).
- Wynik dla strony: `lottie.json` (+ fonty/obrazy ze sceny) do `out/wideo/lottie/`, osadza `jarvo-web`.
  Po pracy zatrzymaj serwer: `pkill -f "[v]ite.*--port 3030"` (nawias: wzorzec nie trafia w samą komendę).

## Łączenie
- obraz z lemo/anidoodle + lektor PL + napisy: `napisy.py <film> --slowa <words>` albo `film.py` z `plik` w scenach
  (`"ujecie": {"plik": "…mp4", "koniec": "stop"}`: krótsza animacja trzyma ostatnią klatkę zamiast zaczynać od nowa),
- klipy z `html_wideo.py`, Remotion, Lottie: tak samo jak wyżej (`plik` + `koniec: stop`) albo nałożone na nagranie (`.mov` z alfą),
- klipy motion-broll w nagraniu: `composite.py` (podgląd) albo `montaz.py`, potem `napisy` i `glosnosc`,
- muzyka z anidoodle do każdego filmu: plik WAV → `"muzyka": {"plik": "…"}` w planie `film.py`.

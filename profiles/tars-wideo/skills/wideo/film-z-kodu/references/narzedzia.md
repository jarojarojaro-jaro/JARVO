# Silniki zewnętrzne u nas: motion-broll, lemo-opuscar, anidoodle

Skille silników są w profilu (`skills/video/motion-broll`, `video/lemo-opuscar`, `video/anidoodle`, przypięte
commity w `vendor/skills.lock.yaml`). Ich instrukcje zakładają laptopa z Claude Code; poniżej różnice u nas.
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
mkdir -p motion/{clips,dist,out,work,inputs} && cp /opt/data/tars/inbox/<nagranie>.mp4 motion/work/source.mp4
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
- **Muzyka:** sample instrumentów (1,35 GB) i Kokoro są tylko z `TARS_EXTRAS="lemo"`. Bez nich: `core/audio/pluck.py`,
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
node tools/emit.mjs intro --out out/intro.html                        # cały film w 1 pliku HTML (dla tars-web)
```
- Kontrakt twardy: `draw(ctx, frame, env)` czysta; losowość tylko `rng(seed)`; zakazane `Math.random`, `Date`,
  `performance.now`, `ctx.filter`, DOM, `new Image`, sieć. Siatka czasu: tabela cue, cięcia na taktach.
- Muzyka: nuty w kodzie (`line(3, "C5:2 Bb4:.5 | …")`); agent nie słyszy, więc zmierz `tools/music.mjs`
  (głośność, zakres, jasność) i w RAPORT daj 8-sekundową próbkę do odsłuchu. Plik audio z renderu → `muzyka.plik` w `film.py`.
- `gate.mjs` szuka `out/<film>.mp4`; renderujesz pod inną nazwą → skopiuj.

## Łączenie
- obraz z lemo/anidoodle + lektor PL + napisy: `napisy.py <film> --slowa <words>` albo `film.py` z `plik` w scenach,
- klipy motion-broll w nagraniu: `composite.py` (podgląd) albo `montaz.py`, potem `napisy` i `glosnosc`,
- muzyka z anidoodle do każdego filmu: plik WAV → `"muzyka": {"plik": "…"}` w planie `film.py`.

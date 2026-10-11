# Silniki zewnętrzne u nas

motion-broll, lemo-opuscar, anidoodle, Remotion (+ iart), video-shotcraft, mg-styles-15, huashu-art-motion, bang-motion,
pixel2motion, Lottie. Skille silników są w profilu (`skills/video/<nazwa>`, przypięte commity w `vendor/skills.lock.yaml`;
video-shotcraft, mg-styles-15, huashu-art-motion i player Lottie instaluje `narzedzia.py`). Ich instrukcje zakładają laptopa z Claude Code; poniżej różnice u nas.
Ścieżka skilla: `SK=$HERMES_HOME/skills/video/<nazwa>` (zmienne nie przeżywają między wywołaniami terminala:
wklejaj przypisanie w każdym).

## Wspólne
- **Nie instaluj przeglądarki ani playwrighta sam** (`npx playwright install`, `setup.sh` z repo): obraz ma
  Chromium headless pasujący do playwright 1.63. Raz: `python3 $HERMES_HOME/scripts/narzedzia.py instaluj <narzędzie>`,
  potem w każdym wywołaniu: `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env <narzędzie>)"`.
- Stan: `narzedzia.py sprawdz` (JSON: przeglądarka, prores_ks, co zainstalowane).
- Projekt w katalogu karty: `out/wideo/src/<nazwa>/` (małe litery, cyfry, myślniki; bez `#` i `%`).
- Lektor PL: lokalny Matcha (domyślny, głos syntetyczny) albo Edge TTS (`film.py lektor`, `lektor_linie.py`), czasy
  słów bez whispera; transkrypcja nagrań: Parakeet
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
python3 $HERMES_HOME/scripts/narzedzia.py instaluj lemo          # raz; także gdy `sprawdz` pokazuje "lemo": false (nowa wersja)
eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env lemo)"      # LIB, LEMO_OPUSCAR_HOME, PLAYWRIGHT_CHROME
cat "$LIB/AGENTS.md"; sed -n 1,80p "$LIB/styles/README.md"         # potem DIRECTOR.md, TECHNIQUE.md, STYLE.md stylu
```
- **43 style.** Cztery z nich to style sceniczne, robiące konkretną robotę: `midcentury-toon` (kreskówka lat 50.:
  instrukcja krok po kroku), `hologram-hud` (skan produktu w hologram: przegląd parametrów), `silkscreen-poster`
  (plakat sitodrukowy: miejsce, szlak, wydarzenie), `engraving` (miedzioryt: nauka, muzeum, historia marki).
  Przypadki użycia z §11 ich `STYLE.md` to gramatyka kolejności informacji i czasu na ekranie; treść i układ są nasze.
- **Tempo:** style rysowane (`engraving`, `midcentury-toon`) kuszą, żeby wszystko kreślić kreska po kresce. Szczegółowo
  rysujesz tylko główny element ujęcia (≤ 1,5 s), powtarzalne (ziarna, kłosy, ikony) po 2–3 naraz, a gdy obraz stoi,
  mówi lektor (`ruch-i-kompozycja.md` rozdz. 2). Na animaticu z roboczym lektorem `krytyka.py tempo`; w `events.json`
  żadne zdarzenie rysowania nie trwa dłużej niż 1,5 s.
- **Najpierw własny scenariusz.** `TREATMENT.md` z trzema wariantami struktury i wyborem (DIRECTOR.md §4) piszemy,
  zanim otworzymy `DEMO.md` albo kod dema. Demo tylko do nauki technik (pędzel, rig, shader, miks), nigdy jego fabuła,
  ujęcia, rekwizyty i oś czasu. Podmiana tekstu w `content.json` dema to test techniczny, nigdy film dla klienta.
- `sh $SK/scripts/setup.sh` znajdzie bibliotekę w `$LEMO_OPUSCAR_HOME` (przypięty commit, bez aktualizacji).
  `setup.sh deps` pomijamy: pakiety są gotowe po `instaluj lemo`. Demo stylu, dopiero po `TREATMENT.md`:
  `sh $SK/scripts/setup.sh demo <slug>`.
- **Kroje.** Pliki krojów z `fonts.css` dema i projektu nie są w repo biblioteki.
  `python3 $HERMES_HOME/scripts/narzedzia.py kroje <projekt>/fonts` pobiera brakujące z google/fonts (OFL, licencja
  obok) i sprawdza polskie znaki w każdym `.ttf`/`.otf`; kod 1 = są uwagi. „Brak polskich znaków” (np. Share Tech
  Mono, Oleo Script) = zmień krój w `fonts.css` na podobny z polskimi znakami (JetBrains Mono, Lobster), bo inaczej
  przeglądarka wstawi inny krój w środek słowa. Podzbiory `woff2` w `core/fonts/` nie są sprawdzane: polski tekst
  idzie krojem z `fonts.css` projektu.
- **Czas czytania.** Strona wystawia `window.TEXTS = t => [{id, text, x0, y0, x1, y1}]` (każdy napis widoczny w chwili
  `t`, pełny tekst od pierwszej klatki, także przy efekcie maszyny do pisania). Przed renderem
  `cd "$LIB" && node core/render/readcheck.mjs "<projekt>"`: 0 = każdy napis stoi ≥ litery/15 + 1,5 s, 1 = za krótko
  albo ucięty kadrem, 2 = brak `TEXTS` (to nie jest zaliczenie). Napisy z `.srt` sprawdza się osobno.
- **Lektor PL:** zamiast `core/tts/tts.py` (Kokoro: tylko EN/ZH) i `asr_check.py`:
  `python3 $HERMES_HOME/scripts/lektor_linie.py <projekt>/lines.json <projekt>/voices --glos pl-PL-ZofiaNeural --sprawdz`
  (te same pliki: `<id>.wav`, `dur.json`, `words.json`). Liczby w tekście lektora słownie, w napisach cyframi.
- **Muzyka:** sample instrumentów (~1,4 GB) i Kokoro są tylko z `JARVO_EXTRAS="lemo"`. Bez nich: `core/audio/pluck.py`
  (instrumenty szarpane z syntezy, numba jest w instalacji), `sfx.py` (efekty bez plików) albo muzyka z anidoodle /
  biblioteki marki.
- Render: `cd "$LIB" && RENDER_SLOTS=1 node core/render/video.mjs "<projekt>" --fps 24 --workers 2 --out "<projekt>/out/video24.mp4"`
  (**2 workery** na VPS 8 GB: każdy to osobna przeglądarka; `RENDER_SLOTS=1`: drugi cały render czeka na pierwszy,
  także przy wolnej pamięci < 30 %). Miks `LEMO_COLOR=bt709 sh core/render/mux.sh <video> <mix.wav> <out.mp4>`
  (−14 LUFS, szczyt −1,2 dBTP, wypisuje zmierzoną głośność i ostrzega, gdy film jej nie trzyma). Bez `LEMO_COLOR=bt709`
  mux zostawia pełny zakres `yuvj420p`, który `qa_wideo.py` blokuje (część odtwarzaczy i platform źle go wyświetla).
- **Oddanie jako projekt edytora** (`projekt-edytora.md`, rozdz. lemo): render z `--q nosub=1`, `mix.py` zapisuje
  obok `mix.wav` warstwy `out/sciezki/{glos,efekty,muzyka}.wav`, `mux.sh` daje czysty obraz z ziarnem
  (`out/obraz.mp4`), a film składa `projekt.py z-kodu … --ciecia events.json --napisy out/<nazwa>.srt --render`.
- Film to 30–60 min pracy: storyboard tylko, gdy karta prosi. Wynik: `<nazwa>.mp4` (render projektu), `<nazwa>.edycja.json`
  z `<nazwa>-sciezki/`, `.srt`, `poster.jpg`, `TREATMENT.md`.

## claude-animation (rysunek w Node canvas, postaci, efekty gry, dźwięk syntezowany)
Bez przeglądarki i GPU: `@napi-rs/canvas` + ffmpeg, najlżejszy silnik na VPS. Film = `frame(ctx, t)`.
```bash
eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env animacja)"     # ANIM = katalog skilla, link node_modules
mkdir -p out/wideo/src/anim && cp $ANIM/templates/film-template.mjs out/wideo/src/anim/film.mjs
# film.mjs bierze bibliotekę z CLAUDE_ANIMATION_LIB (ustawia env animacja); przykłady: $ANIM/../../../../examples nie są w profilu
cd out/wideo/src/anim && node film.mjs sheet 0,2,4,6,8  # arkusz w tych sekundach → vision
node film.mjs strip 4.2                          # 12 klatek wokół szybkiej akcji
node film.mjs verify                             # determinizm (klatka w i poza kolejnością identyczna)
node film.mjs render                             # MP4 (nie nadpisuje dobrego pliku nieudanym)
node $ANIM/scripts/sound.mjs cues.json film.mp4 final.mp4 --lufs -14   # efekty z osi czasu + miks + loudnorm
```
- Najpierw `$ANIM/references/workflow.md` i `templates/beat-sheet.md`; detal powierzchni: `references/detail.md`;
  pułapki: `references/traps.md`. Rigi: `lib/rigs/chibi.mjs` (człowiek z ruchem ust), `critter.mjs`, `bug.mjs`, `ant.mjs`;
  efekty akcji: `lib/fx.mjs` (hit-stop, trzęsienie, iskry, napisy komiksowe); styl low-poly: `lib/lowpoly.mjs`.
- Muzyka kodem: `scripts/music.mjs` (ukulele), `chiptune.mjs` (gra), `ambient.mjs` (tło); licencja MIT, nic do opłacania.
- Skill jest po angielsku i w przykładach używa indonezyjskich słów kluczowych: pracujesz po polsku, tekst na ekranie PL.

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
- **Tryb: zawsze 自主自由创作** (samodzielny, `$SHOTCRAFT/references/pipeline.md` od etapu 0 do końca).
  Nie pytasz o tryb, choć SKILL.md każe (właściciel zatwierdza gotowy film, nie etapy). Szablon Ink Press
  (`template/TEMPLATE.md`) tylko wtedy, gdy właściciel go nazwie; 共同创作 (`guided-free-creation.md`) nie używamy.
- **Karta ujęcia, zawsze w tej kolejności:** nazwa karty i `style-key` z `$SHOTCRAFT/gallery/api/library.json`
  (indeks 157 kart; szukasz `python3 $HERMES_HOME/scripts/inspiracje.py ujecia [--kategoria kamera] [--energia wysoka]
  [--szukaj scroll]`, całość jednej: `--karta <nazwa>`) → pełna karta `references/shots/<kategoria>/<nazwa>.md` → dokładne demo TSX z jej sekcji
  „参考实现” (`demos/…`). Parametry z dema (krzywe, czasy, kolejność) są sprawdzone: przenosisz je, a nie piszesz
  ruchu od nowa z samego opisu; tego, co karta oznacza jako „已知坑/命门”, nie osłabiasz.
- **Karta ze znakiem „u nas: ujecia.js”** (11 kart: rozdanie, stos, wiersz, wyszukiwarka, tytuł w papierze, licznik
  bębnowy, cięcia na bit, zwolnienie, głębia, finał, reflektor) idzie w HTML z `/_lib/jarvo/ujecia.js`
  (`ujecia.md`), bez projektu Remotion; Remotion zostaje dla reszty kart i całego filmu shotcraft.
- **Karty z polem „原片出处”** (ruch odtworzony z cudzej reklamy: ClickUp, Notion, Figma, Slack…) bierzesz tylko
  jako technikę ruchu. Nigdy nie kopiujesz kadrów, układu, tekstów ani kolejności ujęć tamtej reklamy.
- **Pomijasz:** edytor workbench (`node workbench/scripts/open.mjs`, `src/workbench.ts`, `npm run parity`;
  `instaluj` go nie pobiera, poprawki robi właściciel w edytorze HQ), całe „交付收尾” (prośba o oznaczenie autora,
  wysyłka do ich galerii prac, eksport do JianYing), niezależnego recenzenta-subagenta (sam robisz kontrolę klatek
  z `kontrola-wideo`, ocenia właściciel) i drugą wersję bez muzyki (tylko na prośbę: ten sam render z `bgm` = false).
- Zostaje z nich: prawdziwe zrzuty strony w 2× zamiast rysowanych makiet, dane wrażliwe na zrzutach zastąpione
  zmyślonymi, wygląd z kolorów i krojów produktu, cięcia w rytm muzyki, ≤ 3 uderzenia całego kadru na film,
  zero `Math.random` i `Date.now`.
- Screenshoty strony klienta: `python3 $HERMES_HOME/scripts/assety.py <URL> --film --out public/live` (kafle 2×,
  wycinki, pusta plansza, `film/uklad.json` z prostokątami w pikselach strony, jak `layout.json` shotcraft; opis:
  `strona-filmowana.md`) i kolory z `marka.json`. Inny układ (wiele tras, interakcja przed zrzutem): `cp $SHOTCRAFT/assets/scripts/capture-template.mjs .`,
  popraw CONFIG na górze, `python3 $HERMES_HOME/scripts/narzedzia.py link .`, `node capture-template.mjs`.
- Dema z `@remotion/motion-blur`: `npm i @remotion/motion-blur@4.0.484 --prefer-offline` w projekcie.
- Dźwięki z `assets/audio/` wolno używać (ATTRIBUTION.md), źródło do RAPORT.md.

## mg-styles-15 (wzory 15 stylów motion design, MIT)
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj mg; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env mg)"
ls $MGSTYLES/demos $MGSTYLES/prompts                  # kod 15 filmów-wzorów (10 s) i notatki stylów; okładki: $MGSTYLES/videos/*.jpg
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/05-cel-boil/index.html --preset mg --czasy 1,4,8 --arkusz out/wideo/wzor.jpg
```
- Wzór to kod do podejrzenia i przeniesienia (krzywe, czasy, warstwy) do naszej animacji w kontrakcie jarvo, a nie
  gotowy film klienta. `--preset mg` (kontrakt `window.DEMO` + `renderAt(t)` + `__ready`) służy do obejrzenia wzoru.
- Rusza 11 wzorów (klatki 6–25 s). Cztery oglądasz tylko z okładki i kodu: `04-3d-render` (klatki z Blendera),
  `06-collage`, `18-hanazi`, `19-paperclip` (zdjęcia bez podanego źródła: `instaluj mg` ich nie pobiera, tak jak
  filmów MP4; próbki dźwięku dokłada dodatek `instaluj mgaudio`). Strona, która nie wystartuje, mówi dlaczego
  (błędy JS, brakujące pliki).
- Dźwięk wzorów to mgaudio (`lib/audio`, `demos/*/audio.py`): muzyka i efekty pisane kodem. U nas robi to
  `muzyka.py` (skill `lektor-i-dzwiek`); własny kod z mgaudio uruchamiasz Pythonem dodatku
  (`eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env mgaudio)"`, `$MGAUDIO_PY`, `sys.path` += `$MGAUDIO`).
- Kroje wzorów `instaluj mg` bierze z google/fonts (OFL, Apache-2.0); chińskie spoza google/fonts zastępuje
  Noto Sans SC. To kroje do podglądu: w naszym filmie kroje z polskimi znakami z `/_lib/kroje/kroje.css`.
- Tekstura papieru jest CC0; ziarno, kurz i washi z `$MGSTYLES/assets/textures` nie mają podanego źródła:
  tylko do podglądu, w filmie klienta ziarno i kurz robisz sam w kodzie.

## huashu-art-motion (silnik kanwy 2D: 35 stylów malarskich, 8 gramatyk explainera, MIT)
```bash
python3 $HERMES_HOME/scripts/narzedzia.py instaluj huashu; eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env huashu)"
ls $HUASHU/scripts/engine/{lib,scenes,clips}          # biblioteki, sceny-wzory stylów, gramatyki (clip.js czyta spec JSON)
python3 $HERMES_HOME/scripts/html_wideo.py klatki $HUASHU/scripts/engine/index.html --preset huashu \
  --query film=demos/y2_vox --czasy 2,6,10 --arkusz out/wideo/wzor-vox.jpg   # ich film-wzór (gallery = 35 stylów)
```
- Nasza strona ładuje silnik z `/_lib/huashu/` (= `$HUASHU/scripts/engine/`), a po bibliotekach, przed `clip.js`
  / `engine.js` i własnym kodem, polską nakładkę `/_lib/jarvo/huashu_pl.js`. Strona ma `<canvas id="c">`, suwak
  `#scrub` i `#tt` (silnik je czyta) i idzie `--preset jarvo`: nakładka daje `__seek`, `__W`/`__H`, `__teksty`
  (tekst z kanwy dla pomiaru) i przerywa render od razu, gdy silnik nie wstanie.
- Nakładka podmienia kroje bez polskich znaków pod tą samą nazwą: PuHui-* i NotoSansSC → Inter (te same grubości),
  NotoSerifSC → EB Garamond, LXGWWenKai-500 i GochiHand → Caveat 600, LilitaOne → Poppins 800, Rye → Alfa Slab One,
  UnifrakturMaguntia → IM Fell English, NotoSerifJP → Cormorant Garamond 700. Liczby z `TY.fmt` po polsku
  (`1234,5`, `12 345 678`, `−3,3`), napisy z kodu silnika po polsku („dane przykładowe”, „Źródło: …”, „oś Y nie
  zaczyna się od 0”). Postać gramatyki historyjki jest neutralna (włosy, bez kapelusza, okularów i zegarka autora),
  kolory z `window.POSTAC = {skora, linia, wlosy, koszulka, spodnie, buty}` (marka klienta).
- Gramatyka 3b1b: polskie słowa (z ą–ż) idą prostym krojem w całości, „w”, „z”, „i” przed słowem nie są zmiennymi,
  kursywą zostają pojedyncze litery wzoru. `__teksty` daje stałe id napisu (licznik, pisanie po literze = jeden napis)
  i krój bez rozmiaru, więc `pomiar` liczy czas czytania i kroje zastępcze jak na stronie DOM. Łatki kodu gramatyk
  pasują do przypiętego commitu silnika; inny kod = błąd strony („łatka … nie pasuje”), nie postać autora.
- `--preset huashu` służy tylko do obejrzenia ich stron (film-wzór, galeria): bez nakładki, z ich krojami.
- Klatki postaci autora (`demos/_shared/hero`, `demos/long_scroll/frames`) są tylko do podglądu ich filmów-wzorów,
  nigdy w filmie klienta. `instaluj huashu` nie pobiera `assets/` (filmy pokazowe, plansze, rysunki postaci) ani
  kresek chińskiego kroju AR PL (`strokes.js`, licencja Arphic). Ich `render.py`, `qa.py` i uv nie są nam potrzebne:
  render, pomiar i kontrola są nasze (`html_wideo.py`, `krytyka.py`, `qa_wideo.py`).

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
  `--preset jarvo` (serwer lokalny, biblioteki z `/_lib/`, `?render=1`); ruch i smugi zamiast motion bluru z
  `/_lib/jarvo/ruch.js` (`--subklatki N` wydłuża render N razy: tylko na prośbę właściciela).
- **Szybki render:** `wideo` dzieli oś na odcinki i robi klatki w kilku przeglądarkach naraz (samo: do 4, połowa
  rdzeni, ~1 GB wolnej pamięci na przeglądarkę; `--rownolegle N`), film ten sam co z jednej. Pełne rendery
  (`html_wideo.py wideo`, `film.py render`, `projekt.py render`) zajmują miejsce: najwyżej 2 naraz na maszynie,
  drugi tylko przy wolnej pamięci ≥ 30% (`JARVO_RENDER_MIEJSCA`, `JARVO_RENDER_WOLNA`); czekanie widać w logu (⏳).
  Klatkę zrzuca samo Chromium (CDP, ten sam obraz co zwykły zrzut, 1080p ok. 0,2 s); gdy na dysku nie zmieszczą się
  takie klatki (~2 B na piksel), idzie zwykły zrzut (wolniej), a gdy i on nie, render staje od razu z liczbami.
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
- film z kodu do oddania: `projekt.py z-kodu` (obraz bez napisów, dźwięki osobno, napisy tekstem; `projekt-edytora.md`),
- obraz z lemo/anidoodle jako ujęcie w filmie z planu: `film.py` z `plik` w scenach
  (`"ujecie": {"plik": "…mp4", "koniec": "stop"}`: krótsza animacja trzyma ostatnią klatkę zamiast zaczynać od nowa),
- klipy z `html_wideo.py`, Remotion, Lottie: tak samo jak wyżej (`plik` + `koniec: stop`) albo nałożone na nagranie (`.mov` z alfą),
- klipy motion-broll w nagraniu: `composite.py` (podgląd) albo `montaz.py`, potem `napisy` i `glosnosc`,
- muzyka z anidoodle do każdego filmu: plik WAV → `"muzyka": {"plik": "…"}` w planie `film.py`.

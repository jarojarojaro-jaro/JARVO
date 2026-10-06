# Film z kodu jako projekt edytora

Każdy film z kodu oddajesz tak, żeby właściciel otworzył go w edytorze HQ (Wideograf → Wyniki → **Edytuj**)
i poprawił sam: wyciął ujęcie, podmienił albo wyciszył muzykę, poprawił napis. Film to render projektu
`<film>.edycja.json`, a nie osobny plik obok niego.

## Co jest w projekcie
| Część | Skąd | W edytorze |
|---|---|---|
| obraz | render silnika **bez wypalonych napisów** i bez dźwięku | klipy na osi, po jednym na ujęcie (`--ciecia`) |
| głos (lektor) | osobny plik | audio **przypięte do obrazu**: wycięte ujęcie zabiera swój kawałek głosu |
| efekty, foley, tło | osobny plik (albo kilka: `--audio NAZWA=plik`) | audio przypięte do obrazu |
| muzyka | osobny plik | audio osobno: przy cięciu gra dalej, można ją usunąć albo podmienić |
| napisy | SRT albo słowa lektora | napisy jako tekst (karaoke ze słów) |

Tekst, który jest częścią animacji (tytuł, liczba na wykresie, logo), zostaje w obrazie. Do projektu idą tylko
napisy lektora.

## Polecenie
```bash
P=$HERMES_HOME/scripts/projekt.py
python3 $P z-kodu out/wideo/<film>.mp4 --obraz <czysty-obraz.mp4> --ciecia <cięcia> \
  [--glos lektor.wav[@od]] [--efekty efekty.wav] [--muzyka muzyka.wav] [--audio Tło=room.wav] [--z-muzyki plan.muzyka.json] \
  [--napisy film.srt | --slowa lektor.slowa.json[@od]] [--karaoke [#hex]] [--kroj <krój>] [--styl box] [--kolor #hex] [--tlo #hex] \
  --render
python3 $HERMES_HOME/scripts/qa_wideo.py out/wideo/<film>.mp4 --z-kodu --lektor
```
- `--ciecia`: lista sekund (`5.4,9.6`), `events.json` lemo (zdarzenia `cut`) albo `os_czasu.json` z `film.py narracja`.
  Bez cięć cały film to jeden klip (da się go ciąć w edytorze, ale ujęcia są wygodniejsze).
- Kopie trafiają do `<film>-sciezki/` (obraz bez przekodowania, dźwięki WAV 48 kHz do końca filmu). Głośność sumy
  −14 LUFS jest wpisana w kopie, a elementy stoją na 0 dB, więc właściciel widzi zwykłe 100%.
- `--render` składa film z projektu (eksport jak w edytorze, limiter −2 dBFS, szczyt po AAC pod −1 dBTP).
- Słowa (`--slowa`) mają czasy od początku lektora: przesuwa je to samo „od” co głos. Własne przesunięcie: `plik@od`.
- Projekt zmieniony w edytorze nie zostanie nadpisany: `z-kodu` przerywa. Poprawki nanosisz wtedy poleceniami
  `projekt.py` na tym projekcie; `--nadpisz` tylko, gdy właściciel chce wersję od nowa.
- `qa_wideo.py --z-kodu`: błąd, gdy projektu nie ma, brakuje jego plików albo film nie jest jego renderem.

## Silniki
**Animacja HTML + `muzyka.py`** (najczęstszy przypadek):
```bash
H=$HERMES_HOME/scripts/html_wideo.py
python3 $H wideo out/wideo/src/<nazwa>/index.html --preset jarvo --dlugosc N -o out/wideo/src/obraz.mp4
python3 $HERMES_HOME/scripts/muzyka.py zrob out/wideo/src/obraz.mp4 -o out/wideo/src/final.mp4 --lektor src/lektor.wav --cues cues.json
python3 $P z-kodu out/wideo/<film>.mp4 --obraz out/wideo/src/obraz.mp4 --z-muzyki out/wideo/src/final.muzyka.json \
  --ciecia out/wideo/src/os_czasu.json --slowa out/wideo/src/lektor.slowa.json --karaoke --render
```
`muzyka.py zrob` zostawia warstwy miksu w `<wynik>.muzyka.sciezki/` (muzyka, efekty, głos) i podaje je w planie
(`"sciezki"`), więc `--z-muzyki` bierze wszystkie trzy. Muzyka w warstwie jest już ściszona pod lektora: gdy
właściciel usunie głos, muzyka dalej przysiada w tych miejscach. Napisy: strona nie rysuje ich z `O.napis(t)`.

**lemo-opuscar** (`PR` = katalog projektu, polecenia z `cd "$LIB"`): strona ma `?nosub=1` (dema stylów to mają; we własnym `film.js` napisy rysuj tylko bez `nosub`).
```bash
RENDER_SLOTS=1 node core/render/video.mjs "$PR" --fps 24 --workers 2 --q nosub=1 --out "$PR/out/video24.mp4"
LEMO_COLOR=bt709 sh core/render/mux.sh "$PR/out/video24.mp4" "$PR/out/mix.wav" "$PR/out/obraz.mp4" 24 2   # ziarno i kolor
python3 $P z-kodu "$PR/out/<nazwa>.mp4" --obraz "$PR/out/obraz.mp4" --ciecia "$PR/events.json" \
  --glos "$PR/out/sciezki/glos.wav" --efekty "$PR/out/sciezki/efekty.wav" --muzyka "$PR/out/sciezki/muzyka.wav" \
  --napisy "$PR/out/<nazwa>.srt" --kroj <krój napisów stylu> --styl box --kolor <tusz> --tlo <papier> --render
```
`mix.py` projektu zapisuje obok `out/mix.wav` warstwy `out/sciezki/{glos,efekty,muzyka}.wav`: te same bufory co
w miksie (głos po kompresji, muzyka po ściszaniu pod głos, efekty razem z tłem albo tło osobno przez `--audio`),
float, bez końcowego limitera (`sf.write(…, subtype="FLOAT")`). Wygląd napisów dobierz do stylu (krój z listy
edytora najbliższy krojowi stylu, kolory z palety), bo napisy stylu znikają z obrazu.

**Jarvo mówi (`maskotka.py`):** robi to sam: film jest renderem projektu (obraz, głos przypięty, karaoke).

**Inne silniki** (anidoodle, Remotion, HyperFrames, Manim, claude-animation, motion-broll): obraz bez napisów
i dźwięku z silnika, dźwięki jako osobne pliki (lektor, efekty z `sound.mjs` / syntezy, muzyka), cięcia z listy
scen. Gdy silnik daje tylko jeden gotowy miks, oddaj go jako `--audio Dźwięk=mix.wav` i zapisz w RAPORT.md, że
muzyki nie da się zdjąć osobno.

## Oddanie
Film (`MEDIA:` z renderu), link `jarvo_link.py`, a w RAPORT.md jedno zdanie: „Projekt do poprawek: HQ → Wideograf
→ Wyniki → <film> → Edytuj”. Pliki w `<film>-sciezki/` zostają (bez nich edytor nie otworzy projektu).

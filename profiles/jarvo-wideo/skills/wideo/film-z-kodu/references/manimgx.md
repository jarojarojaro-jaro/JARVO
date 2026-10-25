# ManimGX u nas (silnik skilla manim-video)

Skill [H] `manim-video` (Hermes) pisze kod Manim CE. U nas ten sam kod renderuje **ManimGX 0.1.1**
([academa-labs/manimgx](https://github.com/academa-labs/manimgx), dokumentacja dla agentów:
https://manimgx.academa.ai/llms.txt): silnik w Ruście, render na CPU (Mesa lavapipe), tekst i wzory przez Typst,
bez LaTeX-a, cairo i ffmpeg. Instrukcje z `manim-video` (plan, sceny, kolory, tempo) obowiązują; ten plik mówi,
co jest inaczej. Gdy się różnią, wygrywa ten plik.

Dostępność: dodatek obrazu `manim` (`JARVO_EXTRAS="manim"`). `manimgx --version` = jest; „brak dodatku obrazu
manim” = nie ma: powiedz właścicielowi (dodatek + `deploy.sh --rebuild`) i wybierz inny silnik z tabeli
w `SKILL.md` (wykres, algorytm: HTML z `html_wideo.py`; wzór krok po kroku: gramatyka `3b1b`).

## Kod i polecenia
- `from manimgx import *` zamiast `from manim import *` (albo `import manimgx as m`). Reszta kodu CE bez zmian.
- `setup.sh` ze skilla, `pip install manim`, `texlive`: pomijasz. Polecenie `manim -ql/-qh` → `manimgx render`.
- Jedna scena na wywołanie: `manimgx render script.py Scena1 -o out/scena1.mp4 …`.

```bash
manimgx inspect script.py Scena1                 # ~3 s, bez renderu: oś czasu, storyboard PNG, problemy układu
manimgx inspect script.py Scena1 -t 1.5,end      # klatki w wybranych chwilach (zamiast `manim -s`)
manimgx render script.py Scena1 -r 1280x720 --fps 30 -o out/szkic/scena1.mp4    # szkic
manimgx render script.py Scena1 -r 1920x1080 --fps 30 -o out/scena1.mp4         # finał (pion: -r 1080x1920)
```

1. **`inspect` przed każdym renderem.** Pokazuje wzory i napisy poza kadrem, nachodzenie, za małe podpisy, oś czasu;
   kod wyjścia 1 = problemy układu. Render dopiero przy „layout: no problems” (albo z uzasadnieniem w RAPORT.md, czemu
   nachodzenie jest zamierzone). Scen 3D `inspect` nie sprawdza: tam oglądasz storyboard sam.
   Storyboard (`<Scena>.storyboard.png`) oglądasz (vision): tak sprawdzasz też kroje (punkt 3).
2. **Szkic 1280×720, 30 kl./s; finał 1920×1080, 30 kl./s.** Domyślne 60 kl./s podwaja czas, a nasz montaż i tak
   składa w 30 (`wideo_lib.FPS`). 60 tylko na prośbę właściciela.
   Pion (`-r 1080x1920`): kadr robi się wąski, elementy układasz jeden pod drugim, a układ sprawdzasz na
   storyboardzie szkicu w pionie (`render` też go zapisuje), bo `inspect` bierze rozdzielczość z konfiguracji sceny.
3. **Polski tekst: `Text(..., font="Noto Sans")`.** Domyślny krój New Computer Modern stawia kreskę wielkiego „Ń”
   nad poprzednią literą (KOŃ wygląda jak KÓN), w `Text` i w `Tex`; w `Tex` parametr `font=` nie działa. Noto Sans jest
   w paczce, zawsze. Z krojów obrazu polskie litery dają też „DejaVu Sans” i „DejaVu Sans Mono” (zamiast „Menlo”
   z `manim-video`). Nieznany krój (np. „Menlo”) **po cichu** zamienia się na New Computer Modern: szeryfowe litery na
   storyboardzie = zły krój. Inny krój (Inter, Noto Serif) tylko po sprawdzeniu `inspect` na słowie „KOŃ ŹDŹBŁO”.
   Polskie słowa w `Tex`/`MathTex` tylko w `$\text{…}$` i bez wielkiego „Ń”; podpisy i tytuły zawsze przez `Text`.
4. **Wzory (`MathTex`) to Typst, nie LaTeX.** Nie działają `\def`, `\newcommand` i pakiety (`\usepackage`).
   Przecinek dziesiętny: `2\mathord{,}5` (sprawdzone); `2,5`, `2{,}5` i `\text{2,5}` dają „2, 5” ze spacją,
   `2,\!5` nakłada znaki, a `\,` w `\text{}` rysuje się jako słowo „thin”. Kwoty i jednostki: `Text`.
5. **Powierzchnie 3D:** `Surface.set_color_by_gradient` daje prawie jednolity kolor. Kolor po wysokości:
   `surface.set_fill_by_value(axes=axes, colorscale=[BLUE, GREEN, YELLOW], axis=2)`, szachownica:
   `set_fill_by_checkerboard(KOLOR1, KOLOR2)`.
6. **Bez `self.say()`** (lektor fal.ai, wysyła tekst poza serwer, klucz FAL_KEY) i bez `manimgx present` / `preview`
   (okno, przeglądarka). Polski lektor jest nasz: `film.py narracja` / `film.py lektor` (Matcha, Edge TTS,
   `wideo_lib.speak_many`) daje czasy słów, pod nie ustawiasz `run_time` i `self.wait()`; głos dokłada
   `projekt.py z-kodu --glos`, nie scena. `add_subcaption` nie zastępuje napisów: napisy robi `projekt.py`.

## Sklejanie scen: najpierw stały klatkaż
ManimGX zapisuje MP4 o **zmiennym klatkażu**: klatka trzymana na końcu (`self.wait()`) to jedna długa klatka.
Sklejanie (`concat`) albo filtr `fps=` kończy taką scenę na początku tej klatki, czyli gubi ostatnie ~1–1,5 s
(scena 2,5 s → 1,03 s). Dlatego **każda scena przez `montaz.py napraw --fps 30`** (fps + powielenie ostatniej
klatki do pełnej długości z kontenera, zakres TV, yuv420p), dopiero potem sklejanie:

```bash
for s in scena1 scena2 scena3; do
  @@PY@@ "$HERMES_HOME/scripts/montaz.py" napraw out/$s.mp4 -o out/$s-30.mp4 --fps 30
done
printf "file '%s'\n" "$PWD"/out/scena{1,2,3}-30.mp4 > sceny.txt      # ścieżki pełne: concat liczy je od listy
ffmpeg -y -f concat -safe 0 -i sceny.txt -c copy out/obraz.mp4          # -c copy bezpieczne: sceny mają te same parametry
```

`ffprobe out/obraz.mp4`: długość = suma scen (± 1 klatka na scenę). Klip ManimGX wstawiony jako ujęcie do
`film.py` jest bezpieczny: normalizacja scen trzyma ostatnią klatkę do długości sceny. Dalej jak każdy film z kodu:
`projekt.py z-kodu <film> --obraz out/obraz.mp4 …`, `qa_wideo.py --z-kodu`, `kontrola-wideo`.

## Czasy i pamięć (CPU 4 vCPU, bez GPU)
| Treść | Render na 1 s filmu | 30 s filmu |
|---|---|---|
| 2D (wzory, wykresy, kształty), 1280×720, 30 kl./s | ~1,2–1,8 s | ~1 min |
| 2D, 1920×1080, 60 kl./s | ~4–5 s | ~2,5 min |
| 3D (powierzchnie), 1920×1080, 60 kl./s | ~25 s | ~12 min |

RAM 0,5–1,25 GB na render: przy 8 GB RAM jeden render naraz (sceny po kolei, nie równolegle). Hasło „90× szybciej
od Manim CE” dotyczy GPU; u nas na CPU jest mniej więcej tak szybko jak CE. 3D: szkic 720p30, finał 1080p30, a gdy
render przekroczy kilka minut, najpierw mówisz właścicielowi, ile potrwa.

## Licencje
Kod ManimGX: MIT. Koło na Linuksa jako całość: GPL-3.0-or-later (statycznie wkompilowany x264; dekodery audio ffmpeg
LGPL, Mesa MIT, Typst Apache-2.0). Fonty `manimgx-fonts`, `manimgx-fonts-cjk`: OFL-1.1. Nasze filmy to wynik
programu, nie program: licencja koła ich nie obejmuje. W RAPORT.md: „silnik ManimGX 0.1.1 (MIT, koło GPL-3.0)”.

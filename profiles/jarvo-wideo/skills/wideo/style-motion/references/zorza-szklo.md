# Zorza i szkło (wzór `12-aurora-glass`)

Ciemne tło z dużymi, miękkimi plamami światła w sąsiednich barwach, po którym wolno pływają matowe szklane karty
z cienką jasną krawędzią, a szklana soczewka załamuje to, co pod nią. Poznasz go po rozmyciu za kartą, linii światła
na jej brzegu i po tym, że nic nie jest szybkie.
Wzór: okładka `$MGSTYLES/videos/12-aurora-glass.jpg`, kod `$MGSTYLES/demos/12-aurora-glass/` (MIT), ocena jury
8,07; 1920×1080, 30 kl./s, 10 s, czysty WebGL2. Klatki wzoru (6,0 s = kulminacja; ok. 3,3 s na klatkę na CPU):
```
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki "@@TOOLS_DIR@@/mg-styles-15/demos/12-aurora-glass/index.html" --preset mg \
  --czasy 0.3,3,5.5,6.2,9 --arkusz out/wideo/wzor-12-aurora-glass.jpg
```

## Do czego
- Premiera aplikacji SaaS albo asystenta AI: 3 karty z funkcjami, 16:9 i 9:16, 10–15 s.
- Fintech, bank spółdzielczy, aplikacja płatności: nowa funkcja, 9:16, 10 s.
- Elektronika premium, klinika estetyczna, salon kosmetyczny (spokój, luksus): 1:1, 10–15 s.
- Ekran powitalny strony albo teaser do sklepu z aplikacjami: pętla 16:9, 8–12 s.

## Nie do
- Rzemiosło, jedzenie, usługi lokalne, ciepłe marki: `kreska.md`. Zdjęcia klienta jako bohater: `kolaz.md`.
- Długie teksty i szybki rytm (na szkle tekst traci czytelność): `plaski-wektor.md`. Płynna farba: `plyn.md`.

## Cechy stylu (sprawdzalne)
- Tło: 7 plam (prompt 4–5), elipsy Gaussa rx 240–560 px, każda po zamkniętej krzywej Catmull-Rom o okresie
  24–40 s (widać tylko wycinek drogi), zniekształcenie szumem 150 px; doliny schodzą do #040312.
- Tylko sąsiednie barwy. Paleta wzoru (role): fiolet #7050FF, błękit #2F46F2, cyjan #34CFF0, magenta #B653F0,
  indygo #3320A8, barwinek #8C8CFF; jedyny ciepły akcent w kulminacji: złoto #FFD9A8 → #FFB3C7.
- Karta: rozmycie tła σ 30 (prompt 20–40), nasycenie ×1,38, biel 8,5% (prompt 5–10%), krawędź 1 px o kryciu
  0,14–0,7 zależnie od kąta, promień rogu 38–42 px, załamanie 24 px w pasie 13 px przy brzegu.
- Wejście karty z głębi (z +560) z przechyłem 20·e^(−3,2τ)·cos(3,6τ)°; tekst w karcie: krycie + 8 px w górę.
  W kulminacji fala: pierścień od 60 do 1560 px.
- Soczewka: superelipsa (wykładnik 2,5), współczynnik załamania 1,5, rozszczepienie barw 0,25 (7 próbek widma),
  powiększenie 1 → 1,36, odblask Fresnela; kropla szkła odrywa się jak rtęć (metaball).
- Wykończenie: ziarno ok. 0,14, mocniejsze w półtonach, dither ±1/255, winieta 0,18, blask od progu 0,62, siła 0,22.
- Krzywe sinusoidalne wszędzie; najdłuższy ruch to odjazd kamery 0,5–2,8 s. Tytuł cienkim krojem (Sora 200, 178 px).

## Technika
- WebGL2 jak wzór (bez bibliotek) albo Three.js z `/_lib/three/`. Prompt proponuje DOM `backdrop-filter`; kod robi
  wszystko w shaderach i ma pełną kontrolę nad rozmyciem i krawędzią. Prosta wersja przy 2–3 kartach: DOM
  i `backdrop-filter: blur(30px) saturate(1.38)`; sprawdź na arkuszu, czy rozmycie wyszło w renderze.
- Przenieś z `demos/12-aurora-glass/` z komentarzem `// za mg-styles-15 (MIT), demos/12-aurora-glass/<plik>`:
  tło `FS_AURORA` (`shaders.js` L54–124) z `loopBezier` i `BLOBS` (`main.js` L122–144); szkło `gaussTaps`
  i `blurInto` (`main.js` L229–260) z `FS_CARD` (`shaders.js` L149–208) i pomocnikami `compile`/`makeTarget`
  (L155–168); klucze kamery `hermite` (L39–70).
- Soczewka `FS_LENS` (`shaders.js` L216–355) z `lensStretch`/`lensState` (`main.js` L602–675) jest najcięższa;
  tylko gdy jest bohaterem. `lensStretch` całkuje sprężynę od 4,9 s przy każdym wywołaniu (do ok. 1224 kroków):
  policz tablicę stanów co 1/240 s raz przed `__ready`.
- Ziarno: tekstura `grain_fine_2048.png` wzoru nie ma źródła. Wyjście = canvas 2D: `g.drawImage(glCanvas, 0, 0)`
  (WebGL z `preserveDrawingBuffer: true`), potem z `plotno.js` `ziarno(g, W, H, klatka, 0.04)` (prompt: 3–5% szumu,
  dobierz na arkuszu) i `winieta(g, W, H, { sila: 0.18, kolor: '4, 3, 18' })`. Dither ±1/255 zostaw w shaderze
  końcowym (hash, bez tekstury). Bez `EXT_color_buffer_float` wzór schodzi do RGBA8 i robi pasy: sprawdź przy starcie.
- Tekst kart rysuj na canvasie 2D (skala ×2, jak wzór) wgrywanym jako tekstura i podaj go w `__teksty`.
  Kroje: Outfit 200–300 zamiast Sory (tytuł), Inter 400–500 (interfejs); Sory i HarmonyOS nie ma w `/_lib/kroje/`.
  Przed `__ready`: `await document.fonts.load('64px "Outfit"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` dla każdego kroju na kanwie.
- Teksty, kolory plam i tempo w `parametry.json` (reguła 7 kontraktu) zamiast `?query` wzoru. Smug nie trzeba.
- Czas renderu: wzór ok. 3,3 s na klatkę na CPU, czyli 10 s (300 klatek) ok. 17 min w jednej przeglądarce; kilka
  przeglądarek naraz skraca to mniej niż N razy, bo WebGL na CPU dzieli te same rdzenie. Zmierz swoją stronę
  `klatki --preset jarvo --czasy 5` i podaj właścicielowi szacunek przed renderem. Szybciej: rozmycie w 1/4
  rozdzielczości (jak wzór), 2–3 karty, bez soczewki.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,5 | Hak: zbliżenie na odblask na krawędzi karty |
| 0,5–3,0 | Odjazd kamery: trzy karty w głębi; czat się pisze (pytanie → odpowiedź strumieniem → podpowiedzi) |
| 3,7–4,9 | Funkcje produktu klienta: przełącznik (3,75), suwak (3,95–4,85), gałka zmienia się w szkło |
| 4,8–5,95 | Kropla szkła odrywa się, zatrzask 5,45, soczewka rusza; 0,3 s wstrzymania tuż przed kulminacją |
| 6,0 (60%) | Kulminacja: światło w szkle złoci się, fala 60 → 1560 px |
| 6,7–8,3 | Karty się rozsuwają; nazwa produktu od ok. 8,0 (wzór 6,9), soczewka wchodzi w literę „o” |
| 8,5–10 | Hasło (8,5), odblask po nazwie 9,1–9,6; końcowy kadr stoi ok. 1 s, zorza dalej dryfuje |

- 15–30 s: więcej kart i funkcji (po 2–3 s), tempo bez zmian; jedna soczewka i jedna kulminacja w 60–65%.
- 9:16: najłatwiejszy z tej grupy (karty jedna nad drugą, plamy w pionie), ale kamera i układ od nowa:
  wzór ma 1920/1080 w `toUV`, `rayDir` i w przestrzeni projektu.

## Dźwięk
- Ambient ok. 80 BPM, E-dur, akordy z noną (wzór Imaj9–vi9–IVmaj9–V6/9): szklisty pad, czelesta z echem.
- Interfejs cicho: `click` (vol 0,3) na przełącznik, `tick` na suwak, `plop` na kroplę, `ding-szklany` na zatrzask.
  Przed 6,0 krótki `riser` i 0,3 s ciszy; kulminacja `sparkle` + `chime`, bez mocnych uderzeń.
- Logo: 4 nuty czelesty ok. 8,25 s; odblask cichy `sparkle`. Gotowy podkład: `muzyka-spokojna`. Całość −14 LUFS.

## Pułapki
- Plamy w barwach dopełniających (fiolet + pomarańcz) dają brud; tylko sąsiednie barwy marki, ciepły akcent raz.
- Pasy na ciemnych gradientach: brak float albo brak ditheru. Oglądaj ciemne rogi w 100%.
- Szybki ruch psuje styl: wejścia ≥ 0,8 s, krzywe sinusoidalne, żadnych odbić. Tekst na szkle: ≤ 8 słów
  na kartę, kontrast ≥ 4,5:1 (biel na jasnym fiolecie: przyciemnij kartę).
- Prompt: 4–5 plam i DOM `backdrop-filter`; kod: 7 plam i WebGL. Liczy się efekt: miękko, wolno, sąsiednie barwy.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.3,3,5.5,6.2,9.5
  --arkusz out/wideo/arkusz.jpg`: plama pod kartą rozmyta, krawędź 1 px widoczna; ciemny róg w 100% bez pasów.
- Czas 1 klatki × liczba klatek (górna granica): szacunek w RAPORT.md i dla właściciela przed renderem.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15`: kontrast tekstu na szkle,
  `bez_oddechu`, koniec stoi ≥ 0,8 s.
- Arkusz w 360 px szerokości: nazwa produktu i hasło czytelne, karty nie zlewają się z tłem.

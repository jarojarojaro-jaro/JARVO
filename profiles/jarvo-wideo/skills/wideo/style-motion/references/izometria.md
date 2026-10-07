# Izometria 2.5D (wzór `03-isometric`)

Miniaturowy świat w rzucie izometrycznym: bez perspektywy, krawędzie pod ±30°, kafelki spadają, budynki rosną,
a kamera tylko przesuwa się i przybliża. Widz poznaje styl po pastelowej wysepce z klocków z miękkim cieniem.
Wzór: okładka `$MGSTYLES/videos/03-isometric.jpg`, kod `$MGSTYLES/demos/03-isometric/` (MIT), ocena jury 8,00;
1920×1080, 30 kl./s, 10 s (300 klatek), Three.js. Wzór liczy 16 podklatek na klatkę: na 4 rdzeniach bez GPU
ponad 25 s na klatkę, z `--query spp=1` ok. 4,6 s (start strony ok. 20 s). Podgląd zawsze z `spp=1`:
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/03-isometric/index.html --preset mg --query spp=1 \
  --czasy 1,3,5,6.2,8,9.5 --arkusz out/wideo/wzor-03-isometric.jpg
```

## Do czego
- Firma IT, SaaS: „jak działa nasza platforma”, moduły jako budynki, 16:9 na stronę, 20–30 s.
- Instalator fotowoltaiki albo pomp ciepła: „inteligentne osiedle” rośnie z kafelków, 9:16 i 16:9, 15–20 s.
- Deweloper, coworking, hurtownia: przegląd inwestycji albo przepływ towaru między halami, 16:9, 20–30 s.
- Gmina: plan inwestycji (szkoła, ścieżka rowerowa, oczyszczalnia) na stronę i Facebooka, 1:1 albo 16:9, 30 s.

## Nie do
- Ludzie i emocje z bliska (postacie są tu maleńkie): `plaski-wektor.md` albo `kreska.md`.
- Produkt z bliska (krem, butelka, pudełko): `3d.md`. Liczby jako główna treść: `dane.md` (skill `rodzaje-filmu`).
- Film tani i na jutro: dziesiątki budynków to dużo kodu i długi render; wybierz `plaski-wektor.md`.
- Jedno urządzenie albo budynek cienką kreską na ciemnym panelu, ze świeceniem tego, co działa (w stylu Fosforu),
  które ma też być klikalne na stronie: wspólny skill `izometria` (`iso.py wideo`, render w sekundach).

## Cechy stylu (sprawdzalne)
- Kamera ortograficzna wzdłuż (1, 1, 1): wysokość 35,264°, azymut 45°, krawędzie ekranu pod ±30°, wysokość kadru
  18 jednostek. To prawdziwa izometria, nie piksel-art 2:1 (prompt wspomina 2:1, kod robi ±30°).
- Kamera tylko przesuwa (wzdłuż `(1, 0, −1)` i `(−1, 2, −1)`) i przybliża, bez obrotu; klucze Hermite'a.
- Paralaksa: chmury ×1,25, miasto ×1,0, tło ×0,75 (1 : 0,8 : 0,6). Światło: miękki cień, SSAO, bloom, winieta 0,22.
- Kafelki: 6 pierścieni od środka w 0,25–1,5 s; każdy spada 0,3 s z wysokości 2,2, obrócony −1,25…−1,55 rad;
  ściśnięcie `sy = 1 − 0,3·e^(−τ/0,05)·cos 40τ`, dwa podskoki (0,075, potem ×0,3), obwódka 2 px gaśnie z τ 0,075 s.
- Budynek: płyta ląduje 0,1 s wcześniej, ściany rosną `scaleY` sprężyną ω 14,8, ζ 0,61 (szczyt po ok. 8 klatkach,
  9% przestrzelenia), dach 0,375 s (ok. 11 klatek) później; okna zapalają się w `t0 + 0,42 + rząd·0,045 + los·0,3` s.
- Kulminacja 6,0 s (60%): przygotowanie −2% zoomu i −0,15 EV, potem 1,06× w 2 klatkach i +0,3 EV gasnące
  `e^(−30t)`; fala koloru (15 j/s) zamienia białą „glinę” w kolor, puste kafle obracają się o 180° w 5 klatek.
- Karty z liczbami na ścianach (CSS): prawa `rotate(-30deg) skewX(-30deg) scaleY(.86602)`, lewa
  `rotate(30deg) skewX(30deg) scaleY(.86602)`; kolejność warstw według y na ekranie, liczby liczą się w górę.
- Paleta wzoru (role): tło lawenda `#EEEAFC`/`#DAD3F7`, trawa `#94DFBD`, droga `#8781D0`, biel `#FBFAFF`, akcenty
  brzoskwinia `#FFC4AC`, błękit `#A8D2FF`, masło `#FFE6A1`, koral `#FF9E86`, dane `#62F0F2`, tusz `#2C2960`.

## Technika
- Dwie drogi w kontrakcie jarvo (`kontrakt-html.md`, skill `rodzaje-filmu`); wybierz po pomiarze 1 klatki:
  1. **Three.js** (`/_lib/three/`): `OrthographicCamera` wzdłuż (1, 1, 1), boki z `__W/__H`, przybliżenie
     `camera.zoom`; `RoundedBoxGeometry`, `RoomEnvironment` przez `PMREMGenerator`, `HemisphereLight` i jedno
     `DirectionalLight` z cieniem (`PCFSoftShadowMap`, 2048). Bez akumulatora wzoru (`js/render.js`: 16 podklatek,
     SSAO, cień 4096²); cień kontaktowy = ciemniejszy kwadrat pod budynkiem.
  2. **SVG albo Canvas 2D**, trzy ściany jak w prompcie (`scale(1, 0.866)` → `skewX(±30°)` → `rotate(∓30°)`,
     warstwy wg y na ekranie): ułamek sekundy na klatkę, ostre krawędzie, łatwy pion; cień = równoległobok 0,15.
- Z `js/anim.js` (82 wiersze, czyste funkcje; komentarz `// za mg-styles-15 (MIT), demos/03-isometric/js/anim.js`):
  `spring`, `drop` (spadek kafla), `pop`, `track`; kamera: `hermite` i `camKeys` z `js/main.js` (wiersze 33–73).
- Karty: DOM nad kanwą z macierzami jak `js/ui.js`; pozycję liczysz `Vector3.project` → piksele z `__W/__H`
  (we wzorze `toPx` ma 1920×1080). Liczby `font-variant-numeric: tabular-nums`, licznik 1,2–1,8 s.
- Karty i napisy w charakterze marki (`ruch.js`: `ladowanie`, `wyjscie`). Auta i drony < 0,8 kadru/s: bez smug.
- Kroje z `/_lib/kroje/kroje.css`: tytuł Unbounded 800 albo Space Grotesk, liczby JetBrains Mono, podpisy Inter.
  Tytuł „na podłodze”: DOM z macierzą górnej ściany `rotate(-30deg) skewX(30deg) scaleY(.86602)` albo tekst kanwy
  w `CanvasTexture`; wtedy przed `__ready` `document.fonts.load('800 64px "Unbounded"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`.
- Wykończenie z `plotno.js` na kanwie 2D nad WebGL: `ziarno(g, W, H, klatka, 0.02)`, `winieta(g, W, H, {sila: 0.22})`.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,9 | Hak: błękitna siatka planu rysuje się od środka |
| 0,25–1,6 | 6 pierścieni kafli spada falą, blok gruntu ląduje 1,62 s |
| 2,0–4,8 | Front wzrostu od lewej: domy, wiatraki, tory (2,35), centrum, drzewa |
| 4,6–5,75 | Wieża składa się z segmentów; auta od 4,625, pociąg od 4,875 |
| 6,0 | Kulminacja: przygotowanie 0,1 s, uderzenie zoomu, fala koloru, obrót pustych kafli |
| 6,25–7,0 | Drony; karty z liczbami w 6,5 / 6,75 / 7,0 s |
| 7,75–10 | Odjazd: wyspa w pustce, litery tytułu kładą się co 0,0625 s (8,56–9,0), hasło 9,0, wyspa kołysze się |
- 20–30 s: etapy × 2–3, wejścia dalej co 0,125 s (1/16 taktu); kulminacja (kolor = produkt klienta działa) ok. 62%
  po 0,3 s stopu; logo i hasło po 80%; koniec stoi 1 s, ruszają się tylko auta albo wyspa (±0,05 j).
- 9:16: nowy układ, nie przycięcie: wyspa 10 × 10 kafli zamiast 12 × 12 na ok. 90% szerokości, karty nad wyspą
  jedna pod drugą, tytuł pod wyspą; chmury i karty od nowa w pikselach pionu.

## Dźwięk
- Jasna, „techniczna” melodia: marimba albo pluck, dzwonki, 120 BPM; każde lądowanie to nuta melodii.
- Kafle i budynki: `click`, `tick`, `pop` (biblioteka: `drewno`, `plop`), `pitch` 0,9–1,3, `vol` 0,3–0,5, na pierścień
  albo budynek, nie na kafel. Karty `powiadomienie`, litery tytułu `click`, odjazd `whoosh` 0,15 s przed ruchem.
- Kulminacja: `riser` od ok. 1,5 s przed nią, 0,1–0,3 s ciszy, potem `thump` + `boom-kinowy` + `sparkle`;
  dane `chirp`. Całość −14 LUFS.

## Pułapki
- Akumulator wzoru na CPU: ponad 25 s na klatkę, 300 klatek ≈ 2 h w jednej przeglądarce. U nas 1 próbka, cień 2048,
  bez SSAO; zmierz klatkę i podaj czas właścicielowi, gdy całość przekroczy kilka minut.
- Prompt chce dachu 2–3 klatki po ścianach, kod daje ok. 11: wybierz świadomie (dłuższe lepiej widać na telefonie).
- Nie mieszaj izometrii ±30° z pikselową 2:1: karty SSR pasują tylko do ±30°.
- Wzór ma 16:9 na sztywno (`aspect = 16/9`, `setSize(1920, 1080)`, `toPx`, chmury i karty w pikselach końca).
- Za dużo naraz (144 kafle, auta, pociąg, drony, 3 karty) = brak bohatera: jeden bohater na etap (wieża = produkt).
- Kroje wzoru: brak Unbounded zawiesza stronę (opentype), HarmonyOS Sans ma licencję Huawei. U nas tylko kroje.css.

## Kontrola
- Czas 1 klatki: `python3 $HERMES_HOME/scripts/html_wideo.py klatki out/wideo/src/index.html --preset jarvo
  --czasy 9 --arkusz out/wideo/arkusz.jpg`; szacunek = czas × klatki / przeglądarki (`wideo` robi do 4 naraz).
- Arkusz 20 s: `--czasy 1,4,8,12,12.4,16,19.5`; `krytyka.py pasek out/wideo/film.mp4 --t 12 --klatek 12`:
  przygotowanie, uderzenie i fala koloru płynnie, cienie nie migoczą, krawędzie równoległe (skos 30°, brak zbiegu).
- `… pomiar out/wideo/src/index.html --preset jarvo --dlugosc 20` bez błędów; liczby kart ≥ 3% wysokości kadru
  i czytelne w `krytyka.py telefon out/wideo/film.mp4`; ostatni kadr z tytułem (z ogonkami) stoi ≥ 0,8 s.

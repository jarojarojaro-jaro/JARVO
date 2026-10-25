# Synthwave, neon i kaseta VHS (wzór `10-synthwave`)

Lata 80. z kasety wideo: fioletowe niebo, słońce w poziome paski nad świecącą siatką w perspektywie, chromowany
tytuł i neonowy podpis, a na całym obrazie zakłócenia taśmy. Poznasz go po różowo-turkusowej poświacie i drżących
liniach obrazu z magnetowidu.
Wzór: okładka `$MGSTYLES/videos/10-synthwave.jpg`, kod `$MGSTYLES/demos/10-synthwave/` (MIT), ocena jury 8,21;
1920×1080, 30 kl./s, 10 s, Three.js. Klatki wzoru (4,3 s = uderzenie tytułu, 6,7 s = zapłon neonu; ok. 3,7 s
na klatkę na CPU; krój Mr Dafoe instaluje `narzedzia.py instaluj mg`, bez niego strona nie jest gotowa):
```
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki "@@TOOLS_DIR@@/mg-styles-15/demos/10-synthwave/index.html" --preset mg \
  --czasy 0.5,2.25,4.3,6.7,9 --arkusz out/wideo/wzor-10-synthwave.jpg
```

## Do czego
- Barber, bar, klub, impreza retro, lokalne radio: zapowiedź wieczoru albo czołówka audycji, 9:16 lub 16:9, 6–15 s.
- Detailing, tuning, wynajem aut sportowych: promocja, 16:9 lub 9:16, 15 s.
- Kawiarnia z grami, escape room, sklep z winylami: oferta weekendu, 1:1 lub 9:16, 10 s.

## Nie do
- Usługi zaufania (lekarz, kancelaria, biuro rachunkowe): `plaski-wektor.md` albo `zorza-szklo.md`.
- Marka eko, minimalna, jedzenie w dziennym świetle: `kreska.md` albo `kolaz.md`.
- Dużo tekstu i liczb: `hud.md`. Gra i nostalgia konsoli: `pixel.md`.

## Cechy stylu (sprawdzalne)
- Paleta wzoru (role; akcenty z marki, noc zostaje nocą): niebo #751266 → #4D0D66 → #1A063D → #060212, słońce
  r = 250 px #FF3D8F → #FF6647 → #FF9E38 → #FFDB5C → #FFF59E, pasy od +0,38 r w dół (8,5 na r, szczeliny do 62%).
- Podłoga: siatka magenta #FF29D1, oczka 2,5×5 jednostek, blask `exp(−d/3,4) + 0,16·exp(−d/15)`, każda stopa
  perkusji puszcza po niej pierścień; gorący horyzont, góry z szumu jako siatka (magenta u dołu, cyjan u góry).
- Tytuł z chromu: 14 warstw wyciągnięcia co (0,30; 1,05) px, obrys #0a0014, magentowa krawędź z tyłu, twarz
  z 11 przystanków gradientu, horyzont w 0,494/0,506 (#ffffff → #2b0a26), odblask = dwa pasy (0,09 i 0,03).
- Neon: 3 warstwy (7 px krycie 0,55 z rozmyciem 30; 4 px #ff4fd6 z rozmyciem 4; rdzeń 1,6 px #fff0fb); zapłon
  migocze poziomami 1; 0,15; 1; 1; 0,08; 0,5; 0,85; 1 w kolejnych klatkach.
- Taśma: R i B rozsunięte ±1,2 px (2,2 przy zakłóceniu), czerwień ciągnie się w prawo, co 3. wiersz ciemniej o 12%
  (prompt: co 2 px), wiersze falują ±0,5–1 px (do ±6,5 px przy śledzeniu), szum głowicy w dolnych 17 px.
- Zakłócenia: 8 zerwań po 2 klatki w 10 s (pasy 6–20 px, 18% wierszy, przesunięcie 8–40 px), nie 1–2 na sekundę.
- Klatkaż taśmy: 15 kl./s w 1. sekundzie i przed uderzeniem tytułu, 2 klatki wstecz przy przewijaniu, pół prędkości
  po STOP; maska 4:3 (1440×1040, promień 38) otwiera się na cały kadr w 1,0–1,5 s.

## Technika
- Scena: Three.js z `/_lib/three/` (importmap z `kontrakt-html.md`), `preserveDrawingBuffer: true`; bloom
  `UnrealBloomPass` z `/_lib/three/examples/jsm/postprocessing/` (siła 0,55, promień 0,6, próg 0,78).
- Taśma = `crt.js`: `const e = ekran(wyjscie, 'vhs')` (chwiej, krwawienie YIQ, rozszczep 1,2, linie co 3 px 0,12,
  winieta 0,35, ziarno 0,05, głowica); w `__seek` render sceny, potem `e.rysuj(renderer.domElement, klatka,
  { pasek, zaklocenie, rozszczep, wlacz: wlaczanie(t, 0), wylacz: wylaczanie(t, tWyl) })`. `pasek` 1 → 0
  w 1. sekundzie; `zaklocenie: 1`, `rozszczep: 2.2` tylko w 8 parach klatek zapisanych w `cues.json`.
- Napisy magnetowidu (PLAY ▶, SP 0:00:ss) w HTML nad wyjściem, poza filtrem, ostre: Space Mono 700 albo
  Press Start 2P (8 px × n); VT323 wzoru nie ma w `/_lib/kroje/`.
- Przenieś z `index.html` (`// za mg-styles-15 (MIT), demos/10-synthwave/index.html`): `sceneTime` (52–62), shader
  słońca (158–186), podłogę z falą (221–274), tytuł z chromu (473–518, Canvas 2D) z odblaskiem (520–532),
  `drawFlare` (649: smuga, 5 duchów, gwiazdka), `neonLevel` (825) z tabelą zapłonu.
- Neon: wzór bierze kontury liter z opentype.js, a ten nie czyta WOFF2 (kroje z `/_lib/kroje/`). U nas `strokeText`
  w 3 warstwach odsłaniany maską od lewej z gorącym punktem (gradient radialny 34 px) albo litery zapalane po kolei
  tabelą zapłonu. Kroje: Tilt Neon, Monoton, Kaushan Script, Pacifico.
- Tytuł: Montserrat 900 italic, Kanit 800 italic albo Barlow Condensed 800 italic (Archivo z wzoru nie ma); hasło:
  Audiowide albo Chakra Petch 700 (zamiast Michroma). Przed `__ready` dla każdego kroju na płótnie
  `await document.fonts.load('italic 900 200px "Montserrat"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`; teksty w `__teksty`.
- Bez motion bluru (wzór ma 1 próbkę): mijające palmy i auto dostają `smuga` z `ruch.js` tylko na światłach.
- Render: wzór ok. 2,7 s na klatkę (15 s ≈ 20 min w jednej przeglądarce). Zmierz `klatki --preset jarvo --czasy 4.3`
  i podaj właścicielowi czas przed pełnym renderem.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–1,0 | Hak: obraz z kasety, pasek śledzenia, 15 kl./s, PLAY ▶ w 0,1 s |
| 1,0–3,9 | Obraz łapie ostrość, maska się otwiera; słońce wschodzi, palmy co 0,6 s, auto z naprzeciwka 2,25 s |
| 3,87–4,2 | Przewijanie (2 klatki wstecz, 15 kl./s); 4,2 s uderzenie tytułu: 2,2 → 1 w 2 klatki, błysk, flara |
| 5,4–6,1 | Odblask na tytule, neon pisze się literami; 0,2 s ciszy, słychać tylko brzęczenie |
| 6,3 (63%) | Kulminacja: zapłon neonu (we wzorze 6,6 s), talerz, pełny bit, siatka pulsuje |
| 8,0–10 | Hasło i logo klienta stoją z drganiem taśmy; STOP i wyłączenie kineskopu tylko po ≥ 1 s logo |

- 15–30 s: dłuższa jazda, drugi zwrot (auto z naprzeciwka, brama), kulminacja 9–10 s / 18–19 s.
- 9:16: horyzont niżej, słońce i góry większe, tytuł w 2 wierszach do 900 px, maska z zaokrąglonymi rogami ok. 90%
  kadru. Wzór ma 16:9 na sztywno (`CSS = vec2(1920., 1080.)`, `TITLE_W` 1400, `SHIFT`).

## Dźwięk
- Synthwave 100 BPM (wzór: a-moll): bramkowany werbel, pad z lat 80., bas w ósemkach: `muzyka.py zrob …
  --styl synthwave` (w bibliotece CC0 nie ma synthwave'u; takty z planu `*.muzyka.json`) albo muzyka z licencją.
- Start: szum taśmy, `click` przy PLAY; palmy `whoosh` (`pan` po stronie palmy); auto: `whoosh` i `klakson`
  z biblioteki; przewijanie: `przewijanie` albo `glitch-vhs`; tytuł: `thump` + `crack` i `boom-kinowy`.
- Neon: `buzz` tylko w klatkach, gdy świeci, każdy ponowny zapłon cichy `chime` (`pitch` 1,2); przed zapłonem
  0,2 s ciszy, na nim `talerz` i pełny bit; STOP: muzyka zwalnia; wyłączenie `click`. Całość −14 LUFS.

## Pułapki
- Krój nie załadowany na płótnie: tytuł i neon w kroju zastępczym, odblask nie trafia w litery.
- Za dużo zakłóceń: prompt chce 1–2 na sekundę, kod ma 8 na 10 s; gdy tytuł i logo są czytane, `zaklocenie: 0`.
- `blysk` z `crt.js` rozjaśnia też czerń: biały błysk najwyżej 0,35 przez 1–2 klatki.
- Tabele klatek (zapłon, wyłączenie, `sceneTime`) zakładają 30 kl./s; 60 kl./s = nowe tabele.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.5,1.5,4.2,4.3,6.3,8.5,9.6 --arkusz
  out/wideo/arkusz.jpg`: 4,2 s tytuł jeszcze duży, 4,3 s osiadł, 6,3 s neon w pełni; zerwania taśmy omijają
  klatki, w których czyta się hasło i logo.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15`: kontrast neonu, czas czytania hasła,
  `uderzenia_kadru` ≤ 3 (błysk tytułu, zapłon, wyłączenie).
- Ostatnia sekunda: logo stoi ≥ 0,8 s, napisy magnetowidu go nie zasłaniają; tytuł czytelny na 360 px.

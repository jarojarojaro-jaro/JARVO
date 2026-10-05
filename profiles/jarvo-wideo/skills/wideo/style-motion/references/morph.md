# Morph kształtów (wzór `08-morph`)

Jeden pełny kształt płynnie zmienia się w kolejne ikony, zawsze przez koło, z lekkim ściśnięciem i obrotem, a tło
zmienia kolor kołem rozlanym od bohatera. Widz poznaje styl po tym, że kształt nigdy się nie urywa ani nie plącze.
Wzór: okładka `$MGSTYLES/videos/08-morph.jpg`, kod `$MGSTYLES/demos/08-morph/` (MIT), ocena jury 7,64; 1920×1080,
30 kl./s, 10 s. Klatki wzoru (6,4 s = uderzenie w pinezkę, kulminacja; ok. 0,3 s na klatkę na CPU):
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/08-morph/index.html --preset mg \
  --czasy 1.5,4,6.4,9 --arkusz out/wideo/wzor-08-morph.jpg
```

## Do czego
- Logo na końcu: przedmiot z branży zmienia się w znak (piekarnia: kłos → bochenek → rogal → logo), 16:9, 1:1, 8–12 s.
- „Historia w 6 ikonach” dla SaaS albo aplikacji (telefon → dzwonek → kalendarz → ptaszek → logo), 9:16, 15 s.
- Rebranding (stary znak → nowy, 6–10 s) albo życzenia gminy lub sklepu (płatek → choinka → prezent → logo), 1:1.
- Problem → rozwiązanie w kampanii gabinetu albo kancelarii (chmura → słońce → znak), 9:16, 10–15 s.

## Nie do
- Zdjęcia, prawdziwe produkty, dużo tekstu, dane: `naklejki.md` albo `dane.md` (skill `rodzaje-filmu`).
- Logo rysowane kreską: `rysunek-linia.md`. Postacie albo ikony z ponad 8 osobnymi częściami: `plaski-wektor.md`.

## Cechy stylu (sprawdzalne)
- Jeden bohater w środku (ok. 1/3 wysokości kadru), płaskie wypełnienie, lekki pionowy gradient (OKLab +0,028/−0,022).
- Każdy obrys ma stałą liczbę punktów: ciało 240, otwór 72, kreska 24, cień 60; ten sam kierunek obrysu, punkt
  startu dobrany najmniejszą sumą kwadratów odległości.
- A → koło → B (w szybkim locie kapsuła). Każda połowa 9–12 klatek, cała przemiana 0,6–0,8 s, krzywa
  `cubic-bezier(0.7, 0, 0.3, 1)`: wolny start i koniec, najszybciej w połowie.
- W czasie przemiany ściśnięcie bez zmiany pola k = 1 + sq·sin(πg), sq 0,05–0,14, i obrót ±18–26°·sin(πg).
- Lądowanie: drganie A·sin(2πτ/0,28)·e^(−7,5τ), start 2 klatki przed kontaktem; A od 0,07 (lekkie) do 0,26.
- Części (para, promienie; do 8 kresek) idą z bohaterem, opóźnienie po 0,03 s, kolejność `[7,0,1,2,6,3,5,4]`.
- Kolory mieszane w OKLab (bez szarego środka). Nowe pole tła rośnie kołem od bohatera w 0,6 s, co 1–1,5 s.
- Paleta wzoru (role): tusz #16151B, krem #F4EEE3, nagietek #FFB627, cynober #FF4F2B, ultramaryna #2438E8;
  naraz tylko tło + bohater + 1 akcent.
- Kamera oddycha (zoom 1,018 ± 0,012, obrót 0,5°); wstrząs po uderzeniu 13 px w kulminacji, 5 px w pozostałych.
- Podpis w lewym dolnym rogu (01/07 + słowo) i 7 kropek rozdziałów: widz wie, który to etap historii.

## Technika
- Canvas 2D w kontrakcie jarvo. `import { probkuj, zaokraglony, para, przemiana, uderzenie, macierzScisku,
  przeksztalc, mieszajKolor, ton, rysuj, smugaKropki } from '/_lib/jarvo/morph.js'` (port zestawu ze wzoru).
- Kształty: ścieżki SVG ikon albo logo klienta → `probkuj(d, 240)` raz przed `__ready`; rogi `zaokraglony(pts, r)`.
  Pary też raz: `para(A, B, { n: 240, przezKolo: true })`. W klatce `przemiana(p, u)`, u = (t − t0)/(t1 − t0)
  liniowo; krzywa 0,7/0/0,3/1 (`KRZYWA`) siedzi w środku.
- Lot: `macierzScisku(phi, k)` (phi = kierunek ruchu) → `przeksztalc(P, M, srodek, [x, y])`. Lądowanie:
  `uderzenie(t, t0, { A: 0.24 })` = ściśnięcie w pionie (1 + q, 1 − q). Kolor `mieszajKolor(h1, h2, u)`, gradient
  bohatera `ton(h, 0.028)` u góry i `ton(h, -0.022)` u dołu.
- Z `demos/08-morph/index.html` przenieś iris tła (`circleReg` L430, `drawSoftField` L522–529: krawędź koła miękka
  według prędkości zamiast rozmycia) i kreski (`blendParts` L344–362: kreska bez pary kurczy się i gaśnie przed
  kołem). Komentarz `// za mg-styles-15 (MIT), demos/08-morph/index.html`.
- Szybki lot: `smugaKropki(g, pA, pB, r, kolor)` dla kropek, `smuga` albo `duchy` z `ruch.js` dla bohatera.
  Wzór ma `motionBlur: {samples: 4}`; u nas `--subklatki` zostaje 1.
- Wykończenie `plotno.js`: `papier(g, W, H, { kolor, tryb: 'multiply', sila: 0.5 })`, `ziarno(g, W, H, klatka,
  0.04)`, `winieta(g, W, H, { sila: 0.13 })`. Nie przenoś `finish()` wzoru (getImageData na każdym pikselu).
- Kroje: Outfit 600 na nazwę (jak wzór), JetBrains Mono 500 na podpisy. Napis jako tekst (`fillText` + `__teksty`);
  litery z kształtu tylko z SVG logo klienta, nigdy `glyphs.json` ani `tools/glyphs.py` (bez polskich znaków i .ttf).
  Przed `__ready`: `await document.fonts.load('64px "Outfit"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` dla każdego kroju na kanwie.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,6 | Hak: kropla spada i ląduje jako pierwszy przedmiot (A 0,26), wstrząs 5 px |
| 1,3–5,4 | Łańcuch 4 przemian co ok. 1,2 s, każda 0,6–0,8 s, lądowanie na bicie; po każdej nowe pole koloru |
| 5,6–6,3 | Rozbieg: lot po pętli, na szczycie 0,1 s zawieszenia i przerwa w muzyce |
| 6,4 (64%) | Kulminacja: uderzenie w główny kształt (A 0,24), fala koloru od punktu uderzenia, wstrząs 13 px |
| 7,0–8,6 | Dwie przemiany, ostatnia w znak klienta; tło przechodzi w ciemne |
| 8,3–9,4 | Litery nazwy wyrastają z bohatera co 0,075 s; hasło od 8,95; kropki rozdziałów lecą w kropkę |
| 9,4–10 | Końcowy kadr stoi ok. 1 s; kropka logo pulsuje o 2% w rytm muzyki |

- 15–30 s: więcej ogniw, nie dłuższe przemiany. 15 s = 6–8 ogniw, kulminacja ok. 9,5 s; 30 s = 2 rozdziały
  po 5 ogniw i jeden większy zwrot w 60–65%.
- 9:16: bohater na wysokości ok. 0,42 H, podpis nad dolnym paskiem platformy; tory lotu i pętli planujesz od nowa
  (wzór ma pętlę, trasy i podpis w pikselach 1920×1080).

## Dźwięk
- Future bass ok. 150 BPM (bit 0,4 s): szarpane arpeggio szesnastkami; każde lądowanie dokładnie na bicie.
- Przemiana: `whoosh` z wysokością rosnącą w łańcuchu (`pitch`); lekkie lądowania `pop`, kropla `drip`.
- Pętla: `riser` od 5,6 s, 0,1–0,15 s ciszy na szczycie, przy 6,4 `thump` + `boom-kinowy` z biblioteki
  (`projekt.py dzwieki --szukaj boom`); serce `serce`, litery `tick` co 0,075 s (vol 0,4), hasło `chime`.
- `sound.mjs cues.json film.mp4 final.mp4 --lufs -14 --bed muzyka.wav`; czasy w `cues.json` według `rytm.py`.

## Pułapki
- Supeł w połowie przemiany: różna liczba punktów, przeciwny kierunek albo zły start; zawsze `para()`.
- Prompt: flubber i 3 klatki amortyzacji; kod: bez flubbera, drganie od 2 klatek przed kontaktem (`wyprzedzenie`).
- Ściśnięcie 10–15% z promptu w marce `zaufanie` wygląda gumowo; kod daje 5–14%: B2B 0,05, `zabawny` 0,12–0,14.
- Otwór (pączek, obrączka, litera „o”) ma własną parę (72 pkt) albo zwija się do środka przed kołem; inaczej szpara.
- Motion blur wzoru (4 podklatki) i `finish()` po pikselach wydłużają render kilka razy; u nas smugi i `plotno.js`.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy … --arkusz out/wideo/arkusz.jpg`
  z czasami w połowie każdej przemiany (t0 + 0,5·(t1 − t0)): kształt ciągły, bez pętli i szczelin.
- Pasek klatek co 1/30 s wokół kulminacji: ściśnięcie 2 klatki przed kontaktem, wstrząs gaśnie w ≤ 0,5 s.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 10`: bez `pusta_scena` i `bez_oddechu`;
  lądowania w `cues.json` równe bitom z `rytm.py` (±1 klatka).
- Ostatnia klatka: znak w kolorach marki, nazwa czytelna na 360 px, „Zażółć gęślą jaźń” bez zastępczego kroju.

# Bauhaus, kinetyczny plakat (wzór `09-bauhaus`)

Plakat z kół, trójkątów i prostokątów w trzech kolorach podstawowych i czerni, składany na siatce, jedna akcja
na takt. Poznasz go po kremowym papierze, farbie lekko rozjechanej z płyt i po tym, że każdy kształt ląduje na linii.
Wzór: okładka `$MGSTYLES/videos/09-bauhaus.jpg`, kod `$MGSTYLES/demos/09-bauhaus/` (MIT), ocena jury 7,71;
1920×1080, 30 kl./s, 10 s. Klatki wzoru (6,5 s = kaskada, 7,0 s = kulminacja; ok. 1,4 s na klatkę na CPU):
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/09-bauhaus/index.html --preset mg \
  --query mb=1 --czasy 1,3.6,6.5,7,9.6 --arkusz out/wideo/wzor-09-bauhaus.jpg
```
`mb=1`: strona wie, że klatka to jedna próbka (shader kaskady rozkłada swoje 6 próbek na całą migawkę, jak w ich
filmie). `--mb 1` to flaga ich harnessu (`harness/render.mjs`, domyślnie 8 próbek); `html_wideo.py` jej nie ma.

## Do czego
- Biuro architektoniczne, pracownia wnętrz, sklep meblowy: zapowiedź realizacji albo kolekcji, 16:9 lub 1:1, 10–15 s.
- Galeria, dom kultury, szkoła projektowania: ruchomy plakat wystawy albo dnia otwartego, 9:16, 10–20 s.
- Klub, festiwal techno: ogłoszenie składu na takt muzyki, 9:16, 15 s.
- Firma inżynierska po zmianie marki (porządek, precyzja); gmina: rocznica modernizmu; 16:9, 15–30 s.

## Nie do
- Historia człowieka, emocje, jedzenie na apetyt: `kreska.md` albo `naklejki.md`.
- Produkt, który trzeba pokazać ze zdjęcia: `kolaz.md` (zdjęcia klienta w rastrze) albo `3d.md`.
- Dużo tekstu do przeczytania: `plaski-wektor.md` i rodzaj `explainer.md`. Miękka marka (kosmetyki): `plyn.md`.

## Cechy stylu (sprawdzalne)
- Paleta wzoru (role; kolory z marki): papier #F1E9DA, czerwień #E03C31, żółć #F2B705, błękit #1E4FA3, czerń #111;
  farby mnożone na papier (gęstość 0,955): jeden ciepły, jeden zimny, jasny akcent i czerń.
- Siatka: moduł M = 120 px (prompt mówi 240), 15 linii pionowych (x 120…1800) i 9 poziomych (y 60…1020), pole
  14×8 modułów; linie 1,1 px, krycie 17% (osie 28%), rysowane od środka parami na szesnastkach kreską 3,2 px,
  która w 0,2 s chudnie do włosowej.
- Ruch o całe moduły, lądowanie na linii (koło 6 M w dół i 1 M w bok, półkole 2 M). Tylko dwie krzywe:
  power2.inOut (`io2`) i power2.in (`in2`), bez przestrzelenia i odbicia.
- Jedna akcja na takt (120 BPM, takt 0,5 s), krzyżyki pasowania na półtaktach, licznik „takt nn / 20”.
- Obroty wokół środka (kafle o 90°), rogu (ćwiartka koła) i środka kadru: cała grupa o 90° w 0,75 s skokami
  po 7,5° (12 zębów jak wychwyt zegara, ząb rusza w ostatnich 65% swojego czasu).
- Kaskada z przesunięciem fazy (6–8 s): opóźnienie = start + odległość·rozpiętość / maks. odległość; obracana
  karta to trapez (dalsza krawędź 1 − 0,22·|sin|), przyciemniona 1 − 0,2·|sin|.
- Druk: płyty przesunięte o R (1,3; −0,9), B (−1,0; 1,2), K (0,5; 0,4) px, krawędź szorstka ±0,65 px, ziarno
  ±0,0225, winieta −10%; przed finałem płyty rozjeżdżają się do 4,5 px, docisk w 9,5 s: pasowanie, +10% farby.
- Słowo pionowe: wersalik dokładnie 1 M, długość dokładnie 8 M (z `actualBoundingBox`), litery co 1/8 s.

## Technika
- Kontrakt jarvo, płótno 2D; w `__seek(t)` z `plotno.js`: `papier(g, W, H, { kolor })`, płyty (canvas na farbę),
  `druk(g, plyty, { rozjazd })`, `ziarno(g, W, H, klatka, 0.04)`, `winieta(g, W, H, { sila: 0.1 })`.
- Płyty `[{ obraz: Y }, { obraz: R, dx: 1.3, dy: -0.9 }, { obraz: B, dx: -1, dy: 1.2 }, { obraz: K, dx: 0.5,
  dy: 0.4 }]`; `rozjazd` 1 w spoczynku, do 2,3 w kaskadzie, ok. 3 przed dociskiem, 0,12 po nim; +10% farby = drugi
  `druk(g, plyty, { krycie: 0.1 })` w klatce docisku (wzór: `registration()`, `film.js` 555–566).
- Szorstka krawędź z `kreska.js`: `rownomiernie(pts, 2, true)`, `wrzenie(pts, 7, 0.65, 5)` ze stałym ziarnem
  (krawędź nie wrze), `wielokat(gp, pts, kolor)` (`gp` = kontekst płyty). `polton` najwyżej w jednym module.
- Przenieś z `film.js` (`// za mg-styles-15 (MIT), demos/09-bauhaus/film.js`): `io2`, `in2`, `snap`, `prog` (22–25),
  `gridProg` (543–551), `groupAngle` (90–93), `measureType` (60–84). Kaskadę z shadera (`rotTile`, `slideCol`,
  375–453) przepisz na płótno: kafel przez `translate` + `rotate`, karta jako trapez z czterech punktów.
- `cues.json` jak ich (`bpm`, `grid`, `events[]` z `t0` i `t`, `ripples`); charakter ruchu bez przestrzelenia:
  `zaufanie` z `ruch.js` albo `io2`/`in2` (`zabawny` i `odwazny` łamią styl).
- Kroje z `/_lib/kroje/`: Poppins jest tylko w 500 i 800 (wzór 600/900): słowo Poppins 800 albo League Spartan 900,
  podpisy Poppins 500. Przed `__ready` dla każdego kroju na płótnie
  `await document.fonts.load('800 120px "Poppins"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`; napisy podajesz w `__teksty`.
- Bez motion bluru (wzór: 8 próbek na klatkę i 6 w shaderze kaskady): jedna próbka, obracana karta dostaje
  `duchy(t, rysuj, 2, 1 / 60, 0.4)` z `ruch.js` w 2–3 najszybszych klatkach.
- Render: wzór ok. 1,4 s na klatkę (15 s ≈ 10 min w jednej przeglądarce), płótno 2D jest lżejsze. Zmierz
  `klatki --preset jarvo --czasy 6.5` i podaj właścicielowi czas, gdy całość wyjdzie ponad kilka minut.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–1,0 | Hak: siatka rysuje się od środka na szesnastkach; koło ląduje w 0,5 s, belka w 1,0 s |
| 1,5–4,0 | Trójkąt wjeżdża i się przewraca, kwadrat rośnie, stempel osi 3,0 s; 3,25–4,0 s grupa obraca się o 90° |
| 4,5–5,75 | Półkole, ćwiartka koła, linia horyzontu, pasek z napisem, czerwony kwadrat dzieli się na pół |
| 5,75–6,5 | 1/8 taktu ciszy i bezruchu, potem kaskada kafli i kart od punktu przez kadr |
| 6,5 (65%) | Kulminacja: rewers arkusza, trzy figury marki na czerni, pompa ×1,03, 3 etykiety co 2 klatki |
| 8,0–10 | Zamrożenie w plakat, słowo pionowe, logo i hasło; docisk płyt 8,8 s, potem stoi 1,2 s |

- 15 s = 30 taktów: kaskada 8–9,75 s, kulminacja 9,75 s, logo od 12 s, docisk 13,8 s; 30 s: 2–3 arkusze z dociskiem.
- 9:16: 9×16 modułów po 120 px, kompozycja od nowa (słowo pionowe na 12–14 M, kaskada w górnej połowie, podpisy
  nad dolną strefą UI). Wzór ma W/H, `RES` shadera, `inTrim` i pętle 15/9 linii na sztywno.

## Dźwięk
- Minimalne techno z kliknięć, 120 BPM (wzór: a-moll): `muzyka.py zrob … --styl bauhaus` (przepis techno, takty
  z planu `*.muzyka.json`) albo muzyka z licencją, takty z `rytm.py`.
- Lądowania: `tick` albo `click` z `sound.mjs` (`pitch` 0,9–1,3, `pan` według x); obrót grupy: 12 × `tick` na zębach.
- Przed kaskadą 1/8 taktu (0,06 s) ciszy, potem `thump` i `bas` z biblioteki; kulminacja: `crack` i `talerz`
  z biblioteki, etykiety `click`; docisk: cichy `thump`. Efekt 0,03 s przed klatką, całość −14 LUFS.

## Pułapki
- Kształt ląduje 3 px obok linii i porządek się sypie: pozycje licz w modułach, nie w pikselach.
- Prompt mówi o module 240 px i GSAP, kod ma 120 px i własne krzywe: liczby bierzesz z kodu.
- Rozjazd płyt > 2 px w spoczynku wygląda jak błąd druku. Tekst do czytania tylko na czarnej płycie (0,5 px).
- Słowo w kroju zastępczym ma inną długość i nie trafia w 8 M: krój ładowany przed `__ready`.
- Papier `Paper001` (CC0) i `grain_fine_2048.png` (źródło nieznane) wzoru nie idą do filmu: `plotno.js` liczy swoje.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.5,1,3.6,6.5,8,9.5 --arkusz
  out/wideo/arkusz.jpg`: w spoczynku każdy kształt leży na linii siatki (powiększ krawędzie).
- Pasek klatek co 1/30 s przez obrót grupy: 12 wyraźnych skoków po 7,5°, nie płynny obrót.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15`: bez błędów, `uderzenia_kadru` ≤ 3.
- Ostatnia klatka: plakat z logo stoi 0,8–1,2 s, rusza się tylko ziarno; podpisy ≥ 3% wysokości, czytelne na 360 px.

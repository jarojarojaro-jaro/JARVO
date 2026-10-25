# Jedna linia (wzór `02-line-art`)

Cały film to jedna cienka linia rysowana przez świecącą końcówkę pióra: z ziarna wyrasta roślina, z niej budynek,
horyzont, a na końcu znak marki, który zalewa się kolorem. Widz poznaje styl po stałej grubości kreski na ciemnym tle.
Wzór: okładka `$MGSTYLES/videos/02-line-art.jpg`, kod `$MGSTYLES/demos/02-line-art/` (MIT), ocena jury 7,64;
1920×1080, 30 kl./s, 10 s, Canvas 2D (nie SVG `stroke-dashoffset`); podgląd bez podklatek, ok. 0,45 s na klatkę:
```
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki "@@TOOLS_DIR@@/mg-styles-15/demos/02-line-art/index.html" --preset mg \
  --czasy 1,2.2,3.6,5,6.5,7.6,8.5,9.8 --arkusz out/wideo/wzor-02-line-art.jpg
```

## Do czego
- Pracownia architektoniczna, deweloper premium: znak i hasło, 16:9 i 1:1, 10–15 s.
- Jubiler, winnica, hotel, spa: odsłona logo na stronę i do reklam, 1:1 i 9:16, 8–12 s.
- Kancelaria prawna, notariusz, doradca majątkowy: spokojne intro strony albo prezentacji, 16:9, 10 s.
- Gabinet (stomatologia estetyczna, fizjoterapia): „o nas” z jedną linią przez historię gabinetu, 16:9, 15–20 s.

## Nie do
- Kilka komunikatów, dane, cennik: linia uniesie jedną historię. Wybierz `plaski-wektor.md`.
- Energia, sport, dzieci (styl jest wolny i cichy): `plaski-wektor.md` albo `kreska.md`. Produkt w materiale: `3d.md`.
- Logo bez czystego konturu (zdjęcie, gradienty): uproszczony znak od klienta albo `logo-intro.md` (`rodzaje-filmu`).

## Cechy stylu (sprawdzalne)
- Jedna ciągła linia: 23 odcinki ścieżki, każdy zaczyna się w końcu poprzedniego.
- Grubość stała 3 px na ekranie (`lineWidth = LW / zoom`); początek zwęża się z 35% do 100% na 130 px, logo cienieje
  do 1,5 px w przygotowaniu przed zalaniem (7,4–7,5 s). Okrągłe końce i łączenia.
- Drżenie ręki stałe, linia nie wrze: natura 0,22–0,4 px, architektura 0,05–0,08, logo 0;
  `w = a·(0,75·szum(s/17) + 0,45·szum(s/5,5))`.
- Zwalnianie na rogach: kąt skrętu wygładzony (σ 7 px), `TAU += ds·(1 + 9·min(róg, 0,3))`; czas → TAU przez
  monotoniczny splajn; postoje po 0,15 s na ważnych punktach (kamera też staje).
- Starsze odcinki gasną do „starego złota” `#967D50` (jasność 0,4, ok. 60%), logo do 0,96; prompt mówi 35%.
- Poświata: warstwa linii w trybie `screen`: rozmycie 16 px × 0,2 + 3 px × 0,3 + ostry rdzeń; końcówka pióra:
  halo 15 px i rdzeń 3,2 px (`lighter`).
- Kamera goni pióro: średnia ważona przyszłych pozycji (σ 0,3 s, wyprzedzenie 0,08 s), na postojach stoi, potem
  dogania ok. 2×; zoom w skali log 5,8 → 1,1; przechył −0,016 rad.
- Linia → plama w 7,5 s (75%): monogram (r 135) zalewa się od obwodu do środka w 0,367 s, przestrzelenie 4%, blask
  28 px do 0,46; impuls światła wraca linią do ziarna (7,55–8,45 s).
- Paleta wzoru (role): tło `#0B1320`, linia `#E9D7A5`, gorąca `#FFF6DC`, moneta `#F2E0AE` → `#A8874E`; ziarno 0,1,
  winieta 0,5. U klienta: ciemne tło + jeden kolor linii z marki.

## Technika
- Canvas 2D w kontrakcie jarvo (`kontrakt-html.md`, skill `rodzaje-filmu`). Ścieżka: fragmenty `d` łączone w jedną
  linię jak `PIECES` w `film.js` (wiersze 67–113), próbkowane co 0,5 px; jeden odcinek daje `probkuj(d, n, false)`
  z `morph.js`, a z punktów kontrolnych `splajn(P)` + `rownomiernie(pts, 0.5)` z `kreska.js`.
- Rysowanie: `poczatek(pts, czesc)` z `kreska.js`, potem `g.stroke()` (`lineCap = 'round'`); bez `piorko` i `wrzenie`.
- Z `film.js` (komentarz `// za mg-styles-15 (MIT), demos/02-line-art/film.js`): `monotone` (37–51), czas pióra
  `CORN` → `TAU` → `tauOfT` → `headS(t)` (129–153), kamera `camera` i `applyCam` (182–223), końcówka `drawTip`
  (392–412; rysuje 1–8 kulek między pozycją sprzed 1/120 s a obecną, to jest jej smuga).
- Poświata bez `ctx.filter` (pełny kadr × 4 rozmycia to najwolniejsza część wzoru): warstwę linii narysuj na kanwie
  1/8 kadru (blask ok. 16 px) i 1/2 (ok. 3 px), powiększ z `imageSmoothingQuality = 'high'`, nałóż `screen`.
  Podklatki wzoru (`motionBlur.samples: 4`) pomijasz: `wideo` bez `--subklatki`.
- Wykończenie z `plotno.js` (ziarno wzoru bez źródła): `winieta(g, W, H, {sila: 0.5})`, `ziarno(g, W, H, kl, 0.1)`.
- Znak klienta: jego SVG jako 1–3 ścieżki na końcu linii; zalanie = wypełnienie znaku z maską koła, które maleje
  od obwodu do środka (krzywa ze startem 15/38/58/73% w pierwszych 4 klatkach, przestrzelenie 4%).
- Nazwa: szeryf 50 px z rozstrzeleniem 0,46 em (wzór), podpis 26 px. Kroje z `/_lib/kroje/kroje.css`: Cormorant
  Garamond 600 (jedyna grubość), Bodoni Moda, Playfair Display, Instrument Serif, podpis Inter 300. Przed `__ready`
  dla każdego kroju kanwy `await document.fonts.load('600 50px "Cormorant Garamond"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`
  (polskie litery są w osobnym pliku); teksty do `window.__teksty`.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,2 | Hak: kleks tuszu, kamera szarpnięta za piórem przy zoomie 5,8× |
| 0,2–2,2 | Ziarno, sadzonka z 3 liśćmi (0,75), pęd (1,78), wąs prostuje się w belkę dachu (2,06–2,22, postój) |
| 2,5–5,1 | Pawilon (2,53), wieża (3,21, postój 3,5–3,65), panorama (3,85, postój 4,75–4,9), horyzont (5,14) |
| 5,1–7,4 | Fala i spirala, uniesienie (6,12), pierścień monogramu z łukiem drzwi (6,46), przygotowanie 7,4 |
| 7,5 | Kulminacja: linia zalewa się w złotą monetę, impuls światła wraca do ziarna |
| 7,8–10 | Odjazd do plakatu (7,8–9,0), nazwa 8,33, hasło 8,75, cienkie linie 9,25, odblask na monecie 9,2–9,96 |
- 15 s: rysowanie 0–9 s z 3–4 postojami na symbolach branży (kancelaria: kolumna, winnica: liść winorośli),
  0,3 s ciszy i cienienia linii, zalanie ok. 9,5 s (63%), nazwa od 12 s, koniec stoi 1,2 s z najazdem 3%.
- 9:16: nowa ścieżka, nie przycięta pozioma: linia rośnie od dołu do góry (korzeń → pień → budynek → znak),
  plakat końcowy: znak w górnej 1/3, nazwa pod nim; linia 4–4,5 px (wzór ma `?lw=4.5` do pokazu).

## Dźwięk
- Spokojnie, 72 BPM: fortepian z filcem i smyczki (akordy z septymą i noną), na zalanie pełny akord; podkład
  `projekt.py dzwieki --muzyka` („Spokojnie”) albo utwór z licencją. 0,3 s ciszy przed zalaniem.
- `chime` na postojach i rogach, harfa na spirali, `sparkle` pod impuls, `ding-szklany` albo `dzwon` na zalanie.
- Wzór ma szept pióra zależny od prędkości końcówki; u nas (skill `lektor-i-dzwiek`) bez ciągłego skrobania pod
  rysowaniem: dźwięk mają postoje i zalanie. Całość −14 LUFS.

## Pułapki
- Stała prędkość pióra wygląda jak ploter: prędkość z wag rogów, postoje na ważnych punktach.
- Za dużo symboli: wzór mieści 23 odcinki w 7,5 s, na telefonie to za szybko. Mniej symboli, dłuższe postoje.
- `lineWidth` bez dzielenia przez zoom: przy zoomie 5,8× linia rośnie razem z kamerą.
- Kompozycja wzoru jest pozioma (ziemia, horyzont, plakat w punkcie (925, 560)): pion wymaga nowej ścieżki.
- `retime.py` wzoru nadpisuje ręcznie strojone `cues.json` (zalanie 0,367 → 0,233 s): liczby bierz z `cues.json`.
- Gaszenie starych odcinków do 35% (prompt) zjada linię na telefonie: zostań przy 60% z kodu.

## Kontrola
- Czas najcięższej klatki (zalanie) przed całością: `@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki
  out/wideo/src/index.html --preset jarvo --czasy 0,3,6,9.5,9.6,9.9,12,14.8 --arkusz out/wideo/arkusz.jpg`;
  w klatce 0 linia już jest (hak), żadnego pustego tła dłużej niż 0,3 s.
- `krytyka.py pasek out/wideo/film.mp4 --t 9.5 --klatek 12`: zalanie od obwodu, przestrzelenie widoczne, bez mrugnięć.
- `… pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15` bez błędów (kontrast linii na tle, czas czytania
  nazwy); `krytyka.py telefon out/wideo/film.mp4`: linia widoczna na 360 px, ostatni kadr stoi ≥ 0,8 s.

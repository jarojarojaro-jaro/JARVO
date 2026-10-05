# Kolaż z wycinanek (wzór `06-collage`)

Zdjęcia wycięte nożyczkami z białą krawędzią, raster jak w gazecie, darte paski papieru i czerwono-czarne napisy
z liter jak z listu z okupem, wszystko poruszane skokowo jak animacja poklatkowa. Poznasz go po 12 klatkach
na sekundę, drżeniu ±2 px i kropkach rastra na zdjęciach.
Wzór: okładka `$MGSTYLES/videos/06-collage.jpg`, kod `$MGSTYLES/demos/06-collage/` (MIT), ocena jury 8,14
(najwyższa z tej piątki); 1920×1080, 30 kl./s, 10 s. Wzór nie rusza w Jarvie: jego wycinki nie mają źródła
i nie są instalowane. Oglądasz okładkę i kod `index.html`: L45–101 (zestaw poklatkowy, krawędź, darte paski),
L397–409 (kamera stołu), L652–729 (rozdarcie i zwinięcie strony), L742–752 (wykończenie).

## Do czego
- Koncert, festiwal, dom kultury (zapowiedź 9:16, 10–15 s); kawiarnia, księgarnia, teatr (program miesiąca, 1:1).
- Moda uliczna, nowa kolekcja: zdjęcia produktów i modeli klienta, 9:16, 10 s.
- Historia firmy z jej archiwum (rodzinna piekarnia od 1985 roku), 16:9, 20–30 s.
- Podcast, magazyn, kampania fundacji: okładka odcinka w ruchu, 1:1, 8–12 s.

## Nie do
- Korporacja, finanse, medycyna: kolaż wygląda niepoważnie; wybierz `zorza-szklo.md` albo `naklejki.md`.
- Dokładny interfejs albo demo produktu: `video-shotcraft` (skill `film-z-kodu`).
- Klient nie ma zdjęć: `plaski-wektor.md` albo `kreska.md` (nie dorabiaj „archiwum” ze wzoru ani z AI).

## Cechy stylu (sprawdzalne)
- Ruch skokowy: pozy co 1/12 s (przy 30 kl./s rytm 3:2), kamera stołu co 1/6 s; drżenie ±2 px i ±0,4° co krok.
- Wrzenie: elementy w ruchu 2 px przy 12 kl./s, w spoczynku 1,1 px przy 6 kl./s.
- „Klap” na stół: 3 kroki przed kontaktem skala 1 + 0,38u² + 0,05u, w kontakcie 0,972, krok później 1,01.
  Cień `rgba(34,20,8,.36+.08L)`, rozmycie 5 + 34L, przesunięcie (3 + 24L, 5 + 34L).
- Krawędź nożyczek 4–6 px (prompt 2–4) w bieli papieru #F4EFE4; w stronie dokładane 3,5 px z 28 przesuniętych kopii.
- Raster: czarno-biały 45° co 6,5 px; kolorowy CMYK z kątami C15 M75 Y0 K45 co 6 px.
- Lalka: szczęka z 3 pozami zastępczymi (0 / 0,5 / 1), przesunięcie j·92 px, obrót j·9,5°, zawias na ćwieku.
  Darty pasek z hasłem pod −10°; litery z wycinków, każda w innym kroju i na innym tle.
- Przejście: rozdarcie i zwinięcie połówek walcem R 70–130 px (12 pasków na ćwierć obrotu), spód kartki #C4A077.
- Wykończenie: ziarno 0,26 (overlay), kurz 0,35 (multiply) zmieniany co 2 kroki, winieta rgba(40,20,5,.28).
- Paleta wzoru (role): tło kraft #C4A077, druk #16130F, papier #F2ECDF, akcent #D2261C, mosiądz #D6A945;
  30–40% kadru to puste tło (mniej robi breję).

## Technika
- Canvas 2D w kontrakcie jarvo. Tylko zdjęcia klienta albo stock z darmową licencją (`material-stock`). Zdjęcia,
  gazety, washi, ziarno i kurz wzoru nigdy: nie mają źródła.
- Czas skokowy: `const K = (t) => Math.floor(t * 12 + 1e-4)`, ruch liczony z `K(t) / 12`. Przenieś z
  `demos/06-collage/index.html` zestaw `hash` (L45), `jit` (L50), `slap` (L55), `shadow` (L63), `piece` (L68),
  ok. 30 wierszy, z komentarzem `// za mg-styles-15 (MIT), demos/06-collage/index.html`.
- Wycinki: PNG bez tła od klienta albo maska ścieżką (`g.clip`); krawędź `rimmed(img, r)` (L78–83) z r 4–6 px,
  darte paski `tornStrip`, `cutQuad` (L88–101); wszystko raz przed `__ready`.
- Raster z `plotno.js`, raz na wycinek, w docelowym rozmiarze: offscreen → `papier` → `polton(g, zdjecie, { krok: 6.5,
  kat: 45, kolor: '#16130f' })` → `destination-in` maską wycinka. Dwa kolory jak riso: dwie płyty `polton`
  (tusz 45°, akcent 75°) złożone `druk(g, plyty, { rozjazd: 1 })`.
- Tło: `papier(g, W, H, { kolor: '#C4A077', zab: 0.12, chmury: 0.06 })` (kraft) albo kremowe. Kartki gazety:
  tekst klienta w kolumnach (Lora albo Playfair Display) + `polton`, nigdy skany ze wzoru. Taśma klejąca:
  półprzezroczysty pasek `rgba(240,230,200,.55)` z `tornStrip` (washi wzoru nie).
- Wykończenie co klatkę: `ziarno(g, W, H, K(t), 0.12)`, `kurz(g, W, H, Math.floor(K(t) / 2), { sila: 0.22 })`,
  `winieta(g, W, H, { sila: 0.28 })`. Siłę ziarna dobierz na arkuszu w 360 px.
- Rozdarcie i zwinięcie (`TEAR`, `halfPath`, `fmap`, `peelGeom`, `curlHalf`, L652–729, ok. 80 wierszy) rysuje wiele
  pełnych offscreenów na klatkę: raz w filmie, na zmianę rozdziału.
- Kroje na litery z okupu: Anton, Bebas Neue, Archivo Black, Staatliches; podpisy Space Mono. Chińskie kroje wzoru
  odpadają. Przed `__ready`: `await document.fonts.load('64px "Anton"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` dla każdego kroju.
- Bez motion bluru: skok 12 kl./s sam niesie ruch; przy szybkim rzucie 1 krok `duchy(t, rysuj, 2)` z `ruch.js`.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–1,0 | Hak: trzy wycinki „klap” co 1/3 s (zdjęcie bohatera, koło akcentu, kartka z tekstem) |
| 1,0–3,5 | Bohater „mówi” (3 pozy szczęki na bity), dymki z wycinków, nożyczki tną kupon (5 cięć co 1/6 s) |
| 3,5–5,6 | Narastanie: kolejne wycinki co 1/6 s, kamera stołu zbliża 1 → 1,06 |
| 5,6–6,0 | Ósemka ciszy: wszystko stoi, zostaje tylko wrzenie 1,1 px |
| 6,0 (60%) | Kulminacja: wieko otwiera się i wysypuje produkty klienta; kamera skacze 1,11 → 1,05 w 4 krokach |
| 6,6–7,8 | Pasek z hasłem pod −10°, litery okupu klapią co 1/6 s |
| 7,8–10 | Rozdarcie (0,17 s) i zwinięcie do strony z logo (8,3), cena albo przycisk (9,0); stoi od ok. 9,0 s |

- Wzór ma „pop” w 4,0 s (40%) i litery-bohatera w 6,67 s; u klienta główny wybuch w 60–65%. 15–30 s: więcej
  scen „klap” po 2–3 s, jedno rozdarcie na zmianę rozdziału, zawsze 12 kl./s.
- 9:16: strony liczone od nowa w 1080×1920 (wzór piecze strony 1920×1080, portret w punkcie 845/554), bohater
  w górnej połowie, pasek z hasłem ukośnie przez środek.

## Dźwięk
- Lo-fi hip-hop ok. 90 BPM (pianino, boom-bap, trzaski płyty): `muzyka-lofi` albo `muzyka-hiphop` z biblioteki.
- „Klap”: `thump` (vol 0,6) + `kartka`; nożyczki `noz` albo 5 szybkich `click`; szczęka cichy `drewno`.
  Przed wybuchem ósemka ciszy (ok. 0,33 s); wybuch `pop` + `uderzenie-niskie`, konfetti `sparkle`.
- Rozdarcie: `zgrzyt-plyty` tuż przed (muzyka staje), potem `kartka` głośniej; logo: `chime`. Całość −14 LUFS.

## Pułapki
- Zdjęcia wzoru (portret, gazeta 1854, ptaki, róże, motyle, dłoń), washi, ziarno i kurz: bez źródła, nigdy w filmie.
- Krawędź 2–4 px z promptu znika na telefonie; kod ma 4–6 px. Raster liczony w pikselach wycinka: po skalowaniu
  kropki rosną, więc licz go w rozmiarze, w którym wycinek leży.
- Płynny ruch zamiast skokowego (zapomniane `K(t)`) zabija styl; drżenie z `hash(id, K(t))`, nie z `Math.random`.
- Prompt mówi o rembg i filtrach SVG; kod startuje z gotowych wycięć i piecze raster w Pythonie. U nas `polton`.

## Kontrola
- Pasek klatek co 1/30 s przez 0,5 s: pozy zmieniają się co 2–3 klatki (3:2), nigdy co klatkę.
- Klatka kontaktu „klap”: skala 0,972 i najmniejszy cień; krok wcześniej cień duży i przesunięty.
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.4,2,5.5,6,6.1,7,9.5
  --arkusz out/wideo/arkusz.jpg`: ≥ 30% wolnego tła, krawędź widoczna przy 360 px szerokości.
- Raster: kropki jednej wielkości (6–6,5 px) na wszystkich wycinkach. `html_wideo.py pomiar out/wideo/src/index.html
  --preset jarvo --dlugosc 15` bez błędów; ostatni kadr z logo stoi ≥ 0,8 s.

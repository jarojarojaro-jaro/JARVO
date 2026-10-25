# Pop-art – Lichtenstein i Warhol (`13_pop`)

Pop-art z 1962 r.: kadr komiksu w duchu Roya Lichtensteina (kropki Ben-Day, grube czarne kontury, płaskie barwy,
wybuchowe dymki z wyrazami dźwiękonaśladowczymi) i czwórka portretów w duchu Andy'ego Warhola, w której zmieniają się
kolory. Poznasz go po skórze i ścianach z regularnych kropek, czarnym konturze 5 px wokół każdego kształtu i blond
włosach z czarnych łuków w kształcie C. Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru:
indeks źródła żadnej nie podaje; brakuje łzy, białego kołnierzyka i dymka z dialogiem (przebij ją, jeśli film tego
potrzebuje).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 13_pop --czasy 0.2,0.34,0.46 --arkusz out/wideo/wzor-13_pop.jpg`; kod
`$HUASHU/scripts/engine/scenes/13_pop.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Social media, krótka promocja, wyprzedaż: 6–15 s, 9:16 albo 1:1.
- Gastronomia (burgery, napoje, lody), moda, event, klub: reklama 10–15 s z humorem.
- Zapowiedź komiksu, festiwalu, premiery: 5–10 s.
- Bardzo lekki render (6 ms na klatkę): wiele wariantów formatu i długości bez kosztu.

## Nie do
- Poważne tematy (zdrowie, finanse, żałoba) i elegancja premium: `06_renaissance` albo `10_nouveau`.
- Komiks z dynamiczną perspektywą i akcją: `27_kirby` (uwaga: tam jakość ★★).
- Animowana typografia bez ilustracji: gramatyka `kinetyczna`.

## Cechy stylu (sprawdzalne)
- Kropki Ben-Day przez `createPattern`: kafel pitch×pitch z 5 kółkami (4 rogi + środek) = siatka pod 45° (odstęp
  po przekątnej pitch/√2). Ściana: pitch 24, r 5,6, niebieskie kropki `#2f5cc8` na białym (przekątna 17 px – jak okres
  w oryginale zmierzony FFT). Skóra: pitch 13, r 3,3, czerwone `#e2483c` na `#fae0cc`. Żółta podłoga: pitch 14, r 2,2,
  α 0,18 (ledwie widoczny raster druku). Wzór przypięty do ekranu – kropki nie „pływają” z postacią.
- Wszystko „gruby czarny kontur 5 px + płaski kolor”, jedną funkcją `ink(c, path, fill, lw)`; światło jako białe grube
  krótkie kreski; cień jako `hatch()`: w elipsie czarne ukośne linie 3,5 px co 10 px.
- Kadr komiksu z czarną ramą 6 px; biała listwa przypodłogowa 754–792 (czarne linie 6 px), żółta podłoga 796→990/1003
  (lekko skośny horyzont), czerwony pas, ramka „MEANWHILE...” `Bangers-400` 46 px na żółtym tle z czarną ramką 5 px.
- Czwórka Warhola: 4 zestawy barw (tło, twarz, dolna połowa twarzy, cienie powiek, szminka); twarz kota z 9 punktów
  `RIG.smooth` + dolna połowa twarzy elipsą + czarna plama z prawej (przesunięcie sitodruku); w prawym górnym polu dwa
  białe odblaski szkła. Tła: `#9ccf3a #e0359a #2fc0b0 #f08a2a`.
- Wybuchowy dymek: biała gwiazda zewnętrzna (14 ramion, promienie 128/178 z losowaniem) + żółta wewnętrzna, dwa wiersze
  `Bangers-400` 82 px czerwone (czarny obrys 12 px + czarny cień 4 px), dookoła 10 czarnych trójkątnych linii ruchu.
  `Bangers` ma polskie znaki.
- Dymek myśli: 10 kółek najpierw razem obrysowanych czarnym 11 px, potem razem wypełnionych bielą (najprostszy obrys
  sumy kształtów).
- Postać w stylu Lichtensteina: blond włosy w falach – masa (19 punktów `RIG.smooth`, tylny brzeg z garbami
  `sin(2.1i+4t)·14`) + 7 kul loków (r 30–48) wzdłuż tyłu, najpierw wszystko czarnym 10 px, potem wszystko żółtym
  (obrys sumy); w każdym loku czarny łuk C 4,5 px i ciemnozłoty łuk `#d9a514`; 5 czarnych pasm S, 2 białe blaski.
  Skóra (twarz, szyja, dłonie, nogi) w czerwonych kropkach; czerwona sukienka do kolan (dół przycięty krzywą, nie
  prostokątem) z białym pasem światła; czerwone szpilki (7-kątne); duże oczy (białko 12×8,5, niebieska tęczówka r 7,
  blask) + 3 grube rzęsy, brwi wyżej o 5 px; powiększone czerwone usta.
- Kubek biały z niebieskimi ukośnymi paskami i kawą.
- Napisy (plakietka roku z filmu źródłowego): `Anton-400` 104 px `#111` na żółtej ramce `#f7e23a` z czarnym brzegiem,
  podpis `Anton-400` 30 px; Anton ma polskie znaki.
- Paleta: czerń `#141414`; papier `#f3eedb`; niebieski `#2f5cc8`; żółty `#f7d52c`; czerwony `#d8232a` / `#a8161c`;
  biel `#fbf8ee`; skóra `#fae0cc` z kropkami `#e2483c`; włosy `#f8d62c` / `#d9a514`; kot `#f39a2c` / `#c4561a`;
  tła Warhola `#9ccf3a #e0359a #2fc0b0 #f08a2a`.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 13_pop`; `P` = `PAINT`, `RIG`, `U`.
2. Kafle kropek: `dotPattern(c, key, pitch, r, col, bg)` → `P.cached('pop_tile_…')` → `createPattern`; skórę wypełniaj
   `fillStyle = pattern; fill(path)`. To o dwa rzędy wielkości szybciej niż `PAINT.halftone` (odczyt pikseli punkt po
   punkcie).
3. Tło w całości do cache `pop_bg`: rama kadru, listwa, podłoga, czerwony pas, „MEANWHILE...”, białe ramy obrazów
   Warhola i niebieska linia parapetu, niebieskie krzesło, ziarno papieru.
4. Co klatkę: czwórka Warhola (`warhol`, `warholCat`), dymek myśli (`bubble`), wybuchowy dymek (`wiggleBox`, `burst`),
   stół, kubek, postać (`girl`, `fillSkin`, `shoe`), kot (`cat`, deformacja `def`).
5. Kot przyczajony: ciało z 10 własnych punktów (początek w `K.box`), głowa `K.headC + (22,104)` opuszczona i dociśnięta
   do ciała, przednia biała łapa wyciągnięta do przodu. Pozostałe kotwice z `RIG.cat`.
6. Postać: picie z IK `RIG`; para – dwie czarne faliste linie drżące 14 Hz.

## Co się rusza
- Czwórka Warhola zmienia zestawy barw: `step = floor(lt·11)` (co ~5,5 klatki), pole nr i bierze zestaw `(i+step)%4`.
- Trzy kropki myśli zapalają się po kolei: cykl 12 klatek, kropka k świeci, gdy `((f-2k) mod 12) < 4` (r 20,
  podskok 6 px), w przeciwnym razie r 12.
- Wybuchowy dymek drży 30 razy na sekundę (hash): ±8 px / ±6 px / ±0,03 rad; linie ruchu pulsują długością
  `0.85+0.25·sin(40lt+2i)`.
- Kot kręci zadem przed skokiem: `wig = sin(lt·2π·6)·16` (6 Hz, ~3 razy w 0,47 s); waga punktu `clamp((560-x)/140)` –
  im bliżej zadu, tym większe przesunięcie, do tego zad podnosi się o `|wig|·0.6`; pręgi i ogon idą za tą samą
  deformacją; trzy łukowe linie ruchu przy zadzie przesuwają się z `wig`.
- Włosy: tylny brzeg faluje `sin(2.1i+4t)·14`. Postać pije, para drży.
- Odcinek w filmie źródłowym: 0,47 s (2 ósemki).
- Dowód: między lt 0,34 a 0,46 zmienia się 11,6% pikseli.

## Przejście-podpis (wejście w ten styl)
- `zigzag`, 0,16 s: żółta błyskawica i raster. W postępie 0,35–0,55 stary obraz zamienia się w kropki (komórka
  16 px, promień kropki zależny od jasności), 0,55–0,75 nowy obraz w kropkach, potem kropki gasną do czystego obrazu.
  Na wierzchu błyskawica zygzakiem z góry na dół (x 780→1450, na zmianę ±90 px, 9 odcinków) rysowana stopniowo
  w postępie 0,05–0,6: czarna 34 px + żółta `#ffe02a` 22 px; na początku gwiazda wybuchu w (70, 990) (28 ramion,
  r 70/105).

## Wydajność
- Ciepła klatka: średnio 6 ms, maks. 9 ms; pierwsza (budowa cache) ≈45 ms. Determinizm sprawdzony.
- Cache: `pop_bg`, kafle `pop_tile_*`; kropki tylko przez wzór (`createPattern`), nigdy kropka po kropce.

## Pułapki
- Głowa kota w pozycji z `RIG` wisi nad przyczajonym ciałem (pusta przerwa); w tej pozie głowa ~100 px niżej,
  wciśnięta w ciało.
- Włosy z jednej żółtej płaszczyzny z lekką falą wyglądają z daleka jak narzucona chusta. Rozpoznawalność dają
  kule loków z czarnymi łukami C.
- Kropki liczone punkt po punkcie (`PAINT.halftone`) są dużo wolniejsze i „pływają” razem z postacią; wzór przypięty
  do ekranu stoi.
- Do rozważenia (ze źródła): klasyczna „płacząca dziewczyna” Lichtensteina ma łzę i biały kołnierzyk, a komiks –
  dymek z dialogiem; wzór ich nie ma.

## Kontrola
- Czy skóra i ściana są z regularnych kropek pod 45°, przypiętych do ekranu (nie ruszają się z postacią)?
- Czy każdy kształt ma czarny kontur 5 px i płaski kolor?
- Czy włosy mają kule loków z czarnymi łukami C?
- Czy w odcinku coś miga lub drży w rytmie (czwórka Warhola, kropki myśli, dymek)?
- Czy polskie napisy w dymkach są w `Bangers` z czarnym obrysem i cieniem?

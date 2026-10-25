# Kreskówka „rubber hose” z lat 30. (`33_rubberhose`)

Animacja z 1930 roku (Fleischer, wczesny Disney, dzisiejszy Cuphead): jeden kolor papieru w odcieniach sepii, wielkie
okrągłe głowy, oczy „pie-cut” z wyciętym klinem, ręce jak gumowe węże bez łokci, białe rękawiczki, wszystko
podskakuje do bitu w 12 klatkach na sekundę, a na wierzchu rysy, kurz i migotanie starej taśmy. Jakość wzoru: ★★★
(rozpoznawalny od razu, gotowy do użycia); słabość wzoru: większość ruchu to szum taśmy, nie postacie (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 33_rubberhose --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-33_rubberhose.jpg`;
kod `$HUASHU/scripts/engine/scenes/33_rubberhose.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Retro reklama: barber, kawiarnia, jazz i swing, browar rzemieślniczy, gra indie: 10–30 s.
- Intro albo outro podcastu czy kanału, maskotka marki tańcząca do bitu: pętla 2–4 s.
- Humorystyczny przerywnik w dłuższym filmie („dawno, dawno temu…”): 3–6 s.

## Nie do
- Nowoczesny, czysty wygląd: `16_2026` albo `style-motion` (płaski wektor).
- Długie ujęcia z tekstem: migotanie i rysy męczą oko.
- Rysunek z wrzącą linią bez staroci i bez taśmy: `style-motion`, karta `kreska`.

## Cechy stylu (sprawdzalne)
- Paleta (z kodu): tusz `#141210`, papier `#efe7d2`, jasny `#d9d0b8`, średni `#a39a84`, ciemny `#5e574b`. Na końcu
  cały kadr do szarości (`saturation`) i `multiply #f2e8d2` (wypłowienie).
- Podskok do bitu: `bnc(tq, ph) = |sin(π(tq/BEAT + ph))|`, `BEAT = 60/128`. Każdy obiekt skacze amp px nad swoim
  punktem styku z podłogą; przy lądowaniu spłaszczenie sx=1+0.09k, sy=1−0.09k, w powietrzu wydłużenie ok. 5%.
  Fazy przesunięte co 0,25 bitu: stół 0.5, dziewczyna 0.25, kot 0.75, słońce 0; kokarda 0.05 (lekko za ciałem = ruch wtórny).
- Klatkaż: postacie i motywy `tq = floor(t·12)/12` (animacja „na dwójkach”), podnoszenie filiżanki też w 12 fps;
  warstwa taśmy `floor(t·24)`.
- Postać (ze szkieletu tylko punkty zaczepienia):
  - głowa: koło o promieniu 82 wokół headC;
  - oczy pie-cut: biała obwódka i czarna źrenica z wyciętym klinem `arc(−1.45..−0.85)`, nad okiem 3 rzęsy;
  - ręka-wąż: jedna krzywa Béziera kwadratowa od barku do dłoni, stała grubość, czarny brzeg +10 px;
  - biała rękawiczka: 4 palce, wywinięty mankiet, 3 linie na grzbiecie dłoni;
  - spódnica w groszki do kostek.
- Kot: ciało `RIG.smooth(K.bodyPts)`, średnia szarość `#a39a84` (= rudy), pręgi `#5e574b`, biała pierś i łapy
  `#fbf7ec`; ogon jak falujący wąż `sin(7q − 9tq)·26q`.
- Taśma: drganie klatki ±1,5/±2 px; migotanie: co klatkę biel α0.02–0.09, potem czerń 0–0.06; 3 pionowe rysy, nowe
  miejsce co `floor(t·6)`, więc rysa żyje kilka klatek; 14 kropek kurzu na klatkę i czasem włos; ziarno przesuwane
  losowo o ±20 px co klatkę; okienko projektora z zaokrąglonymi rogami (`roundRect` r60) i winieta.
- Kroje plakietki we wzorze: `Rye-400` → u nas Alfa Slab One, podpis `LilitaOne-400` → u nas Poppins-800 (podmienia
  `huashu_pl.js`, bo oba oryginały nie mają polskich znaków).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 33_rubberhose`. `P` = `PAINT`
   (`paint.js`, `post.js` z `P.film`/`P.gateWeave`/`P.fade`), `RIG`, `U.stepTime`.
2. Tło papierowe raz do cache (`P.cached('rh_bg', …)`): tapeta w pionowe pasy z rombami, szczeliny płytek podłogi,
   akwarelowe przyciemnienie rogów.
3. Kolejność: niebo za oknem (słońce z twarzą, chmury, drzewo) → rama okna i firanka w groszki → krzesło → stół
   (wygięte nogi, tańczący kwiat) → dziewczyna → kot.
4. Każdy obiekt w funkcji `boing(c, ax, ay, b, amp, fn, k)`: przesunięcie w górę o b·amp i skala wokół punktu styku
   (ax,ay).
5. Postać rysuj od nowa po kreskówkowemu; ze szkieletu `RIG.girl` bierzesz tylko kotwice (headC, bark, dłoń).
   Wszystkie krzywe przez `RIG.smooth`.
6. Raz, po narysowaniu wszystkiego: `P.fade(c, { sat: 1, tint: '#f2e8d2' })` (szarość + wypłowienie).
7. Taśma: całość w `P.gateWeave(c, t, () => { … })` (drganie klatki 24 fps), na wierzch `P.film(c, t, { grain })`
   (migotanie, rysy, kurz, ziarno, okienko).

## Co się rusza
- Wszystko podskakuje do bitu (we wzorze 128 BPM; ustaw tempo swojej muzyki).
- Promienie słońca obracają się 1,6 rad/s, twarz słońca kiwa głową do bitu.
- Tańczący kwiat: łodyga ±0.35 rad, liście machają jak ręce, płatki się kręcą.
- Kółko dymu na każdy bit; dół firanki macha do bitu.
- Migotanie i rysy taśmy (24 fps).
- Pole ruchu 40%, ale większość to szum taśmy.

## Przejście-podpis (wejście w ten styl)
- `irisFilm`, 0,4 s (`cx 1236, cy 420` – brzeg filiżanki): przysłona z kreskówek lat 30. i stara taśma. Dla p<0,5
  stary obraz dostaje coraz więcej `sepia(q) grayscale(0.7q) contrast(1+0.3q)`, a czarna przysłona zamyka się do
  filiżanki: `R = R0·(1 − easeIn(q))`, R0 = odległość do najdalszego rogu. Dla p≥0,5 nowy obraz otwiera się
  `R0·outBack(q)` (z przeskokiem). Obwód z 48 odcinków drga ±1,5% w 12 fps. Przez całe przejście migotanie, rysy
  i kurz. W indeksie źródła ten styl opisano jako „stara taśma przed zapaleniem lampy” (z niego wychodzi `lampGlow`
  do `34_shadowpuppet`).

## Wydajność
- Ok. 20 ms na klatkę.
- Cache: tło papierowe (`rh_bg`); ziarno trzyma `P.film` pod kluczem `grain`.

## Pułapki
- Ciało kota ze szkieletu to łamana; w kreskówce od razu widać proste odcinki. Zawsze `RIG.smooth`.
- Desaturację rób raz, po narysowaniu postaci. Inaczej rękawiczki i filiżanka zachowają ciepły kolor.
- Szum taśmy zawyża pomiar ruchu (40%). Sprawdzaj ruch postaci osobno i daj go więcej niż we wzorze.

## Kontrola
- Czy wszystko poza taśmą zmienia się skokowo w 12 fps?
- Czy podskoki są zgrane z bitem i mają spłaszczenie przy lądowaniu?
- Czy oczy mają wycięty klin, a ręce to gładkie węże bez łokci, z białymi rękawiczkami?
- Czy kadr jest jednobarwny (nic ciepłego nie zostało)?
- Czy postać rusza się wyraźnie, a nie tylko taśma?

# Okres błękitny Picassa (`36_picasso_blue`)

Picasso z 1903 roku: obraz ściśle w jednym kolorze – błękity od granatu do bladego niebieskoszarego, szerokie suche
pociągnięcia, grube spokojne kontury pruskim błękitem, wydłużone i wychudzone postacie, smutek i bardzo powolny ruch.
Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: kształt postaci za mało melancholijny
(przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 36_picasso_blue --czasy 0.4,0.8,1.2 --arkusz out/wideo/wzor-36_picasso_blue.jpg`;
kod `$HUASHU/scripts/engine/scenes/36_picasso_blue.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Tematy poważne i refleksyjne: zdrowie psychiczne, żałoba, samotność, kampania społeczna: 20–60 s z lektorem.
- Teledysk do ballady, zapowiedź spektaklu, poezja, audiobook: 15–45 s.
- Nocna scena nad morzem, marka „spokojnej nocy” (sen, wieczorna herbata): pętla 10–20 s.

## Nie do
- Radosny, sprzedażowy przekaz: `30_matisse` albo `31_haring`.
- Marka z mocnym kolorem firmowym innym niż niebieski: styl jest ściśle jednobarwny i ten kolor zgasi.
- Ekspresjonizm z falującym światem: `19_munch`; kubizm Picassa: `11_cubism`.

## Cechy stylu (sprawdzalne)
- Paleta: `#132240` / `#1d3866` / `#2d5a94` / `#6b8fb6` / `#b6c8d8` / szaroniebieski `#3b6878`, ściśle jednobarwnie.
- Rozróżnianie jasnością, nie kolorem: rudy kot = średni niebieski `#4f719a`, pręgi `#273f66`, biel = jasnoniebieski
  `#b6c8d8`; blond włosy = najjaśniejszy szaroniebieski `#cbd8e0`, skóra `#90a9be` (włosy o stopień jaśniejsze niż
  skóra, inaczej nie czytają się jako blond).
- Pociągnięcia ściany: cell34, len110, w34, jitter 4, pionowo ±0.5·noise(0.003); paleta mixBase 0.8; potem rozmycie
  7 px nałożone α0.8. Podłoga te same parametry, poziomo.
- Suchy pędzel: 900 nitek, α0.07, długość 30–90.
- Kontur: pruski błękit `#0c1830`, 5 px, bez wrzenia. Linia okresu błękitnego jest pewna, nie drży.
- Wydłużenie: dziewczyna `DOMMatrix().translate(1240,932).scale(0.84,1.12)` (oś w stopach), kot scale(0.82,1.14)
  wokół (540,905). Ta sama macierz w trzech miejscach: `Path2D.addPath`, `setTransform` płótna poza ekranem
  i `setTransform` w callbacku `visibleLines`.
- Szal: od czoła i czubka głowy, przez kark i plecy do talii+70, kolor `#6b8fb6`, fałdy rgba(20,40,80,.6) 4 px.
  Długie palce: 3 wąskie elipsy 22×4.5 wokół filiżanki.
- Krój plakietki we wzorze: `Caveat-600`; ma polskie znaki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 36_picasso_blue`. `P` = `PAINT`,
   `RIG` (`RIG.visibleLines`, `RIG.drawGirl`, `RIG.drawCat`).
2. Jednobarwny płaski podkład: ściana, podłoga, za oknem nocne morze i księżyc.
3. Szerokie suche pociągnięcia (`P.strokes`, parametry wyżej) → rozmycie 7 px α0.8 → bardzo słabe nitki suchego
   pędzla. Statyczne, więc raz do cache (`bp_static`).
4. Rama okna skopiowana z podkładu i drobne pociągnięcia; stół osobną warstwą po pociągnięciach.
5. Grube kontury otoczenia, bez drgania.
6. Fale, odblaski księżyca, chmura.
7. Postać wydłużona (macierz wyżej) → drobne pociągnięcia i zimny gradient światła → grube kontury przez
   `RIG.visibleLines` → fałdy szala → powolna para.
8. Faktura płótna i zimna winieta (cache `bp_over`).

## Co się rusza
- Powolny oddech: `sin(1.8t)·0.026` (ok. 2× amplituda i 0,45× częstotliwość wspólnej choreografii); podnoszenie
  filiżanki trwa 1,25 s (we wspólnej choreografii 0,9 s); para unosi się w połowie tempa.
- Fale za oknem przesuwają się poziomo, bliższe szybciej: `20 + 0.25·(y − 400)`; 14 odblasków księżyca migocze;
  blada długa chmura przechodzi przed księżycem.
- Kot też oddycha.
- Pole ruchu 3,2%.

## Przejście-podpis (wejście w ten styl)
- `blueBrush`, 0,42 s: kolor zostaje „wyssany”, potem maluje go szeroki suchy pędzel. Stary obraz dostaje
  `color` rgba(45,90,148, min(1, 2.2p)) – zostaje sam błękit – i przyciemnienie `multiply`. Potem 6 szerokich
  pociągnięć (każde wysokości H/6+90), naprzemiennie nachylonych ±18, maluje nowy obraz od lewej do prawej, starty
  co 0.07; głowa pędzla to krzywa kwadratowa, brzegi z drganiem sinusowym 6–7 px; za głową, w pasie 80–280 px,
  26 ciemnych i jasnych linii włosia (farba jeszcze nierozprowadzona).

## Wydajność
- Ok. 24 ms na klatkę.
- Cache: podkład z pociągnięciami (`bp_static`), faktura i winieta (`bp_over`).

## Pułapki
- Odrobina ochry na kocie i we włosach (nawiązanie do „Starego gitarzysty”) łamie jednobarwność. Tylko błękit,
  rozróżnienie jasnością.
- cell16, len40, w14 pionowo po całej ścianie wygląda jak „deszcz” albo koc – to impresjonizm, nie okres błękitny.
  Szeroko, długo, nisko kontrastowo, i jeszcze rozmycie.
- Okrągłe końce szerokich pociągnięć gęsto obok siebie wyglądają jak „rząd głów”. We wzorze przykrywa je rozmycie
  7 px; właściwe lekarstwo to inny koniec pędzla: `P.strokes(…, { cap })` (domyślnie `'round'`).
- Stół wycięty prostokątną maską z dużych pociągnięć zostawia na podłodze płaską prostokątną łatę. Stół osobną
  warstwą po pociągnięciach, bez dziury w pociągnięciach.
- Słabość wzoru: postać za mało melancholijna. Mocniej pochylona głowa, opuszczone ramiona, dłuższe dłonie, wzrok
  w dół.

## Kontrola
- Czy w kadrze nie ma żadnego koloru poza błękitami?
- Czy blond włosy i biel kota rozpoznasz tylko po jasności?
- Czy pociągnięcia są szerokie i długie, a nie drobny „deszcz”?
- Czy kontur jest gruby, stały, bez drgania?
- Czy postać jest wydłużona, a ruch wyraźnie wolniejszy niż w innych stylach?

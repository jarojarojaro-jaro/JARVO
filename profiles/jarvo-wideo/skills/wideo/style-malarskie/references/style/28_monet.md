# Monet: „Nenufary” i „Mostek japoński” (`28_monet`)

Impresjonizm Moneta z 1899 roku: obraz złożony z krótkich, poziomych pociągnięć bez konturów, woda z odbiciem nieba,
liście nenufarów z różowymi kwiatami, zielony mostek japoński z glicynią i światło drżące na wodzie. Poznasz go po
fiołkowo-niebieskiej wodzie i po tym, że nic nie ma obrysu. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną
słabością); słabość wzoru: przestrzeń jest dziwna – ściana to staw, a podłoga to drewno (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 28_monet --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-28_monet.jpg`;
kod `$HUASHU/scripts/engine/scenes/28_monet.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Spa, ogród, kwiaciarnia, hotel nad wodą: spokojne tło 10–30 s pod lektora.
- Muzeum, galeria, wystawa impresjonistów: zapowiedź 15–30 s.
- Marka kosmetyczna, zapachowa, ślubna: pętla 8–15 s pod napis.
- Zwolnienie tempa w dłuższym filmie (wspomnienie, refleksja, „lato”).

## Nie do
- Produkt, twarz, tekst z detalami: pociągnięcia rozbijają kształty. Wybierz `24_hopper` albo `35_shinkai`.
- Impresjonizm bez wody (ulica, kawiarnia, pole maków): `08_impressionism`.
- Czyste kropki jednej wielkości: `29_seurat`.

## Cechy stylu (sprawdzalne)
- Kompozycja wzoru: ściana to mural z nenufarami jak w Oranżerii (cała ściana to woda), okno to zielony mostek
  japoński (łuk, glicynia, staw), po bokach okna zielone okiennice z Giverny, postać siedzi przed muralem.
- Woda: pionowy gradient `#b9c7e6→#8fa6d6→#6c84bf→#5a72a8` i 4 plamy jasnoróżowo-żółtego odbicia nieba.
- Cienie wierzby: 5 pionowych pasów, krawędź faluje poziomo `sin(0.03y−3.2t+k)·14`.
- Nenufary: 10 kęp, razem ok. 100 elips z wcięciem (rx 38–78, ry 12–21), 40% z różowym albo białym kwiatem.
- Pociągnięcia w 4 przebiegach (`PAINT.strokes`):
  - woda: cell 9, len 34, w 6.5, **poziomo** angle≈0±0.06, boil 6;
  - widok w oknie: cell 6, len 13, w 4.5, górna połowa skośnie, dolna poziomo, boil 6;
  - podłoga: cell 12, len 34, w 8, **boil 0**;
  - rama okna i okiennice: cell 6, pionowo i poziomo, boil 0;
  - wszystkie `outline 0` (impresjonizm nie obrysowuje).
- Palety regionów (`PAINT.swatch`):
  - woda `#5b6fb5 #7d8fd0 #9db5e0 #6aa0a8 #b7a6d8 #d9c8e8 #8fb8a8 #a6c4e8 #c8b0d8` (mix .45);
  - liście `#5f8f4a #7fae5a #3f6f4a #9cc070 #6f9a7a #b4cc78`;
  - róż `#f0a0b8 #f7d0dc #fff2f4 #e88aa0`;
  - podłoga `#c69a6a #b07a5a #d8b08a #9a6a7a #8a7aa8 #e0bc90`.
- Mostek: ciemne tło liści `#24452a`, gruba linia `#3f8a62` (20 px) i jasna `#8fdcae`.
- Postać we wzorze: biała letnia sukienka z 1899 roku, wysoki kołnierz, bufiaste rękawy (elipsy na ramionach),
  jasnoniebieski pasek, słomkowy kapelusz `#ecd28a` z niebieską wstążką.
- Krój plakietki we wzorze: `PlayfairDisplay-400i` z kremową poświatą; ma polskie znaki.

## Jak go zbudować
Struktura jak we wzorcowym `09_postimp`.
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 28_monet`. `P` = `PAINT`.
2. Podkład `moBase` rysuj co klatkę (nenufary płyną, cienie się kołyszą): woda, odbicia nieba, cienie wierzby,
   nenufary, widok w oknie, podłoga, obrus.
3. 4 przebiegi `P.strokes(c, podklad, { cell, len, width, angle, seed, t, boil, outline: 0, palette, mask })`
   z paletami regionów; maski: woda, okno, podłoga, rama.
4. Mostek osobną warstwą: w podkładzie najpierw ciemna plama drzew `#24452a` za mostkiem, potem mostek linią
   `#3f8a62` 20 px i jasną `#8fdcae`; pociągnięcia cell 5 z palety 5 jasnych niebieskozielonych. Bez tego mostek
   znika w palecie liści.
5. Postać: płaskie wypełnienie (`mode: 'fill'`) → `source-atop` drobne pociągnięcia (cell 6, len 12; biel losowana
   z `#fbf8f2 #e4e0f6 #cfd2ee #f8ecd0 #d8e8f2`) → **cień barwny**: od strony światła ciepły żółty α .22, od strony
   cienia fiolet α .32, gradient liniowy w `source-atop` → tylko rysy twarzy cienką linią `#5a4f8a`.
6. Ruchome światła na końcu (niżej).

## Co się rusza
- Ruch główny: picie herbaty, para.
- Drżenie światła na wodzie: 160 jasnych krótkich poziomych kresek (`#fffbe8 #fdf0d0 #f8e0ec #e8f4ff`), jasność
  `clamp(sin(t·(5..11)+φ)·sin(2.3t+i))`, skaczą poziomo ±5 px w 10 fps.
- Nenufary płyną `x+sin(1.3t+φ)·7+6t`; cienie wierzby falują; 3 kręgi na wodzie (przerywane elipsy ry=rx·0.22)
  rosną i gasną.
- Glicynia: 12 gron, w każdym 9 jasnofioletowych kropek od dużej do małej, kołysanie `sin(2.4t+0.9i)·8`.
  Wstążka kapelusza powiewa.
- Różnica klatek 30% (głównie wrzenie wody).

## Przejście-podpis (wejście w ten styl)
- `ripple`, 0,34 s (`cx 1000, cy 600` – filiżanka): stary obraz „wpada do wody” – paski po 6 px przesuwane poziomo
  `dx=sin(0.045y−26p)·46·sin(π·min(1,1.2p))·(0.4+|y−cy|/H)`, jak rozbite odbicie. Nowy obraz odsłania się przez
  3600 **poziomych krótkich elips** (długość 40–110, wysokość 9–17), kręgami od filiżanki (odległość eliptyczna,
  y×1.9, mianownik 1700). Na froncie 3 jasne przerywane elipsy (`lineDashOffset` idzie z p), w środku 140 lśniących
  poziomych kresek. Od p>.7 dokładane przenikanie, żeby przy p≈.85 rogi były już czyste.

## Wydajność
- Ok. 105 ms na klatkę.
- Podkład i pociągnięcia liczone co klatkę, bo woda się rusza. Części, które w twojej scenie stoją, trzymaj
  w `P.cached`.

## Pułapki
- Wrzenie (boil) całego ekranu w 6 fps dało różnicę klatek 47% – cały kadr to szum. Wrzenie tylko na wodzie i w oknie
  (boil 6), podłoga i rama boil 0.
- Glicynia z grubych linii wyglądała jak gładkie pigułki. Rób ją z rzędów kropek.
- Plakietka na pociągnięciach była nieczytelna. Daj jej kremową poświatę (blur 18).
- Mostek bez osobnej warstwy i ciemnego tła znika w liściach.
- Słabość wzoru: ściana-staw i podłoga-deski się gryzą. W swojej scenie daj wodę tam, gdzie woda może być
  (okno, plener, staw).

## Kontrola
- Czy nigdzie nie ma konturu, a rysy twarzy to tylko cienka linia `#5a4f8a`?
- Czy pociągnięcia na wodzie są poziome i czy wrze tylko woda i okno?
- Czy światło drży na wodzie (krótkie jasne kreski w 10 fps)?
- Czy główny obiekt w oknie (mostek albo produkt) jest czytelny na ciemnym tle?
- Czy kadr nie zamienił się w szum (różnica klatek ok. 30%, nie 47%)?

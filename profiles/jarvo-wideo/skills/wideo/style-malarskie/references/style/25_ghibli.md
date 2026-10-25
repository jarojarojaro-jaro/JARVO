# Akwarelowe tła w stylu Ghibli (1988) (`25_ghibli`)

Letni pokój jak ręcznie malowane tło japońskiego filmu animowanego: przezroczyste warstwy akwareli z ciemniejszym
brzegiem wody, białe kłębiaste chmury, zielony stok z trawą falującą na wietrze, firanka wydymana przez podmuch,
plamy światła przez liście i postacie w dwóch tonach (kolor + sierp cienia). Jakość wzoru: ★★ (rozpoznawalny, ale
z wyraźną słabością); słabość wzoru: postać słabsza od tła (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 25_ghibli --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-25_ghibli.jpg`;
kod `$HUASHU/scripts/engine/scenes/25_ghibli.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Ciepłe kampanie: rodzina, dom, wakacje na wsi, natura, produkty ekologiczne, piekarnia: 10–20 s.
- Tło do historii z bohaterem (gramatyka `historyjka`), bajka, książka dla dzieci, edukacja: 20–60 s.
- Lato i wiatr: świeżość, oddech, czysta pościel, napój orzeźwiający: 5–10 s.

## Nie do
- Postać z bliska jako główny nośnik (słabość wzoru): `35_shinkai`; cały film w stylu anime w gotowym silniku:
  `lemo-opuscar`.
- Kopiowanie postaci studia i podpisywanie filmu jego nazwą: wzór oddaje hołd (czerwona kokarda, miotła w tle),
  nie kopiuje postaci.
- Szybkie podglądy wielu wariantów: pierwsza klatka trwa 619 ms (budowa cache akwareli).

## Cechy stylu (sprawdzalne)
- Akwarela `PAINT.watercolor(g, pts, color, {layers, alpha, amp, seed, edge, blend, fill})`: kształt bazowy przez
  3 rundy `PAINT.deform`; każda warstwa jeszcze 2 rundy, wypełnienie `multiply` z niskim kryciem (przezroczysta farba)
  i obrys 1,6 px tym samym kolorem z α = `edge`. Obrysy nakładają się warstwa po warstwie: to brzeg wody, gdzie
  zbiera się pigment. `fill` może być gradientem (niebo, ściana).
- `PAINT.deform(pts, depth, amp, r)` (przesunięcie środków): w każdej rundzie środek każdej krawędzi idzie wzdłuż
  normalnej o przybliżenie Gaussa (suma 3 liczb losowych), proporcjonalnie do długości krawędzi (min(1, len/80));
  w każdej rundzie amp×0.6.
- Parametry: duża ściana `layers` 5, α 0.4, `amp` 12; plamy koloru `layers` 3, α 0.045, `amp` 40 (mocna deformacja);
  deski `layers` 3, α 0.5, `amp` 3, `edge` 0.14; nieprzezroczysta biel (rama okna, obrus, chmury)
  `blend:'source-over'`, α 0.9–0.95.
- Ściana: gradient radialny (przy oknie `#fbf3e0` → w rogu `#dcc49a`) + 28 mocno zdeformowanych przezroczystych plam
  (na zmianę ciepła żółć, róż, niebieskoszary, jasna zieleń) + ciemne rogi. Lamperia i podłoga: każda deska osobno,
  innym tonem. Na końcu drobne ziarno papieru `multiply` α 0.3.
- Chmury: białe nieprzezroczyste kłęby (16 sztuk, brzegi z akwareli) + `source-atop` niebieskoszary gradient od dołu,
  w cache jako sprite. Wielkie drzewo kamforowe też sprite, kołysze się wokół korzenia ±0,025 rad.
- Postacie w dwóch tonach: w scenie pomocnik `cel(c, p, base, shade, dx, dy)` na bazie `PAINT.cel`. Kształt
  w kolorze bazowym, potem w `clip` do kształtu minus ten sam kształt przesunięty do światła kolor cienia: zostaje
  sierp cienia po stronie od światła. Kontur 2,4 px ciepłym brązem `#6a4a38` (zmiękczony z `#4a3428`).
- Akwarela na postaciach: postacie na osobnej warstwie L, tekstura M (ziarno papieru α 0.8 + 40 przezroczystych plam
  `charBloom` α 0.1, `amp` 16) przycięta `destination-in` do sylwetki L i nałożona `multiply`
  (`PAINT.textureInside`).
- Postać wzoru: długie złote włosy, duża czerwona kokarda, turkusowa suknia, biały fartuch, białe mankiety; kot
  ciepły pomarańcz + kremowy, też w dwóch tonach.
- Napisy w filmie pokazowym: `Kalam-700`, `Caveat-600` (mają polskie znaki).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 25_ghibli`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.texture`, `PAINT.noise`, `PAINT.cached`), `brush.js`
   (`PAINT.watercolor`, `PAINT.deform`, `PAINT.rectPts`, `PAINT.ellipsePts`), `render.js` (`PAINT.cel`), `post.js`
   (`PAINT.textureInside`), `rig.js` (`RIG.smooth`).
2. Tło do cache: papier → akwarela nieba za oknem, chmury (sprite), góry, stok, drzewo (sprite) → ściana, deski,
   miotła, półka.
3. Ruchome elementy: firanki, trawa, chmury, korona drzewa, plamy światła na ścianie, stokrotki na stole.
4. Postacie część po części przez `cel` (kolejność rysowania daje poprawne zasłanianie, bez dorysowywania konturów),
   potem akwarela na postaciach `PAINT.textureInside(c, L, mg => { … }, {key})`.
5. Na koniec ciepła poświata `screen` od okna (gradient radialny, α .28).

## Co się rusza
- Białe firanki (dwie): dół wydyma się `q²·(60 + 150·gust)`, `gust = 0.5 + 0.5·sin(5.4lt + faza)`, plus drobna fala
  `sin(7lt + 6q)`; 3 półprzezroczyste warstwy akwareli ze stałym ziarnem, więc brzeg nie „wrze”.
- 360 źdźbeł trawy za oknem: wiatr w porywach `wind = 0.5 + 0.5·sin(3.1t − 0.018x)`, faza przesuwa się po x, więc po
  stoku widać idącą falę wiatru.
- Chmury płyną 22–30 px/s, korona drzewa lekko się kołysze.
- 34 plamy światła przez liście (komorebi) na ścianie: ciepły gradient radialny w `screen`, położenie dryfuje po
  szumie, jasność `sin(5t + 1.7i)`.
- Stokrotki na stole kiwają; długie włosy (7 punktów, wygładzone) wiatr odgarnia w prawo do tyłu; wstążki kokardy
  drżą; brzeg obrusu się kołysze. Picie z kubka.

## Przejście-podpis (wejście w ten styl)
- `bleed`, 0,38 s, środek (580,330) = okno (`TRANSITIONS.bleed`): 5 plam koloru rozkwita po kolei (najpierw okno),
  promień `q·1400·k`, `q = easeInOut(seg(p, t0, t0+0.66))`, brzeg `R·(1 + 0.28·fbm(kąt) + 0.05·sin 9a)`. Na zewnątrz
  70 px jasnej poświaty z blur 18 (woda dociera pierwsza), w środku nowy obraz, na brzegu 5 px brązowego śladu wody
  w `multiply`; poświata i ślad bledną z (1−q). Wyrasta z farby rozlewającej się na mokrym papierze.

## Wydajność
- Mediana 17 ms na klatkę, pierwsza klatka 619 ms (cache akwarelowego tła). Przejście `bleed` 127 ms na klatkę.
- Cache: tło, sprite'y chmur i drzewa, tekstura `charBloom`. Firanki ze stałym ziarnem, bez losowania co klatkę.

## Pułapki
- Plamy α 0.07×4 warstwy i ziarno `multiply` 0.5 robią ze ściany spleśniały pergamin. Pokój ma być jasny: α 0.045×3
  warstwy, cały gradient o stopień jaśniejszy.
- Ściana z dwóch prostokątów (prawy ciemniejszy) dawała twardy szew przy x ok. 1100. Ciemne partie rysuj mocno
  zdeformowanym wielokątem (`amp` 60), nie prostokątem.
- Akwarelę na postaci kładź `destination-in` + `multiply`. `source-atop` kładzie kolor papieru na postać i ta blednie.
- Postać bez faktury wygląda jak płaski wektor na akwareli („tło pasuje, postać nie”): stąd tekstura M i miększy
  kontur. Przegląd pierwszej wersji: firanka nie fruwała; dopiero poryw 5.4 (zamiast 3.2) i wydęcie `60 + 150·gust`
  (zamiast `90 + 70·gust`) dały ruch.
- Do rozbudowy: bloki blasku na włosach w stylu Ghibli, cień firanki płynący w plamie światła na podłodze.

## Kontrola
- Czy każda plama ma ciemniejszy brzeg wody, a kolory przenikają się przezroczyście?
- Czy pokój jest jasny (nie „pergamin”) i bez prostych szwów?
- Czy postacie mają sierp cienia i fakturę akwareli, a nie wyglądają jak płaski wektor?
- Czy firanka wyraźnie wydyma się na wietrze, a trawa faluje idącą falą?
- Dowód z wzoru: różnica klatek 5,1%.

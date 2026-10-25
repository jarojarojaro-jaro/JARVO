# Munch, ekspresjonizm „Krzyku” (`19_munch`)

Długie, wygięte pociągnięcia cienkiej farby płyną po polu kierunków, a cały świat faluje: każdy rząd obrazu przesuwa
się po sinusie, razem z ludźmi, kotem i stołem („Krzyk”, 1893). Poznasz go po krwistym niebie w pasach, które same się
wiją, i po małej postaci z dłońmi przy twarzy. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość
wzoru: ścianę brano za Van Gogha (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 19_munch --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-19_munch.jpg`;
kod `$HUASHU/scripts/engine/scenes/19_munch.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Kampania społeczna: zdrowie psychiczne, stres, wypalenie, lęk: 5–15 s.
- „Krzyk” jako problem przed rozwiązaniem w reklamie (terminy, korki, rachunki), serio albo z humorem: 3–6 s.
- Teatr, festiwal filmowy, horror, teledysk, ruchomy plakat wystawy ekspresjonizmu: 10–20 s.

## Nie do
- Spokojne, pogodne marki: cały kadr jest niespokojny z założenia.
- Wir gwiazd, grube krótkie pociągnięcia z ciemnym konturem: `09_postimp` (Van Gogh).
- Drobny tekst w kadrze (falowanie go łamie) i napięty czas renderu (90–140 ms na klatkę).

## Cechy stylu (sprawdzalne)
- Pociągnięcia `PAINT.flowLines`: ok. 3600 ziaren z siatki 24 px z losowym przesunięciem. Parametry
  `[steps, step, width, α]` na region: niebo `[32,7,10,.78]`, fiord `[26,6,9,.78]`, wzgórze `[12,6,8,.8]`, ściana
  `[42,7,13,.5]`, podłoga `[32,8,12,.55]`, do każdego 0–8 kroków losowo. Jedno pociągnięcie ma 200–300 px.
- Bez konturu, półprzezroczyste nakładanie (Munch maluje cienko i długo). Pod spodem płaski kolor tej samej gamy
  (ściana gradient `#a8401e` → `#5a1a14`), więc w szczelinach widać tę samą barwę, nie czerń.
- Pole kierunków: niebo `0.55·sin(x·.011 + y·.018 − 2.4t)`; fiord po stycznej wokół (620,470); ściana pionowo ±0.5
  po sinusie; podłoga do punktu zbiegu (1000,640).
- Niebo: kolor pasa z „pofalowanego y” `yy = y + 22·sin(x·.014 − 2.2t)`, pas 28 px, 7 kolorów po kolei
  `#e2541c #f08a24 #f4c03a #c8301e #e8743a #f6a63a #b82a1e`. Pasy same się wiją: to „płynące niebo”.
- Palety regionów: fiord `#1d3a6a #2c5a8a #3a4a7a #14243e #4a6aa0`; wzgórze `#2a4a2a #1e3a3a #43603a #5a6a2a`; ściana
  `#8a2e1c #a8441e #6a2418 #b8562a #7a3020 #c86a2a #3a2a4a`; podłoga `#8a5a2a #a8703a #6a3a1e #c88a42 #4a2a1a`.
- W oknie: pomost ze skośnymi deskami, trzy linie poręczy (falują razem ze światem), dwie odległe postacie
  w kapeluszach i krzyczący z twarzą-czaszką.
- Postać: ciemna suknia z lat 90. XIX w. z białym kołnierzem, żółtozielony cień na twarzy (`rgba(120,150,70,.4)`,
  blur 8), 9 pasm długich złotych włosów. Stół i krzesło mają drżące, faliste nogi.
- Napisy wzoru: tytuł `LXGWWenKai-500`, podtytuł `IMFellEnglish-400` (ma polskie znaki).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 19_munch`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js`, `brush.js` (`PAINT.flowSeeds`, `PAINT.flowLines`), `kit.js`
   (`KIT.warpRows`, `KIT.warpCols`, `KIT.nearArm`, `KIT.choreo`, `KIT.label`), `rig.js` (`RIG.drawGirl`,
   `RIG.drawCat`).
2. Wszystko najpierw na pomocnicze płótno (`PAINT.scratch`): płaskie kolory regionów →
   `PAINT.flowLines(c, PAINT.flowSeeds(24, 5), {t, region, angle, color, params})`. Ziarno idzie po polu kierunków,
   a gdy wyjdzie ze swojego regionu, staje, więc granice są czyste. Kolor daje `color(reg, sx, sy, r1, t)`.
3. Na to: okno (pomost, poręcz, postacie), stół i krzesło z falistymi nogami, postacie: wypełnienie (`mode: 'fill'`),
   faktura pociągnięć, kontur (`mode: 'line'`), na końcu bliższa ręka `KIT.nearArm`.
4. Cały kadr przesuń rzędami: `KIT.warpRows(dst, src, y => 9·sin(y·.012 + 4.2t) + 4·sin(y·.031 − 6t), 4, 14)`,
   potem kolumnami `KIT.warpCols(c, src, x => 6·sin(x·.009 − 3.6t), 4, 8)` (pas 4 px, ostatni argument to margines).
   Pod spodem ciemne tło `#3a1410`. Wszyscy falują razem, a to dużo taniej niż rysowanie każdej linii z osobna.
5. Napis rysuj na osobnym płótnie i przepuść przez `KIT.warpRows` (we wzorze `5·sin(y·0.09 + 7t)` w pasie
   y 30–210), z ciemnym obrysem pod literami.

## Co się rusza
- Cały obraz faluje rzędami i kolumnami, pasy nieba płyną, pole kierunków skręca się z czasem.
- Krzyczący w oknie: dłonie przy policzkach, usta otwierają się `7+2sin(9t)`, ciało kołysze się `sin(3.2t)·0.12`.
- Włosy postaci falą biegnącą `sin(9q − 7t)`; poręcz pomostu i nogi mebli falują ze światem.
- Kot ma lekko otwarty pyszczek, jakby udzielił mu się krzyk.
- Picie z kubka; para to dwie grube faliste linie w kolorach nieba.

## Przejście-podpis (wejście w ten styl)
- `screamWarp`, 0,5 s (`TRANSITIONS.screamWarp`): stary kadr wygina się rzędami coraz mocniej (amplituda 70e). Czoło
  fali `y = lerp(−180, H+220, e) + 80sin(x·.0055 + 7p)` zjeżdża z góry w dół, nad nim jest już nowy obraz (jego
  wygięcie 60(1−e) się uspokaja). Na czole leżą 4 pasy po 26 px: `#b82a1e #e2541c #f08a24 #f4c03a`. Wyrasta z pasów
  krwistego nieba, które spływają na obraz.

## Wydajność
- Ok. 90–140 ms JS na klatkę, najciężej w tej grupie: ok. 3600 pociągnięć co klatkę i falowanie całego kadru.
- Pociągnięć nie da się trzymać w cache, bo pole kierunków zmienia się z czasem. Policz czas renderu z góry.

## Pułapki
- Ciemny kontur jak u Van Gogha robi ze ściany gąsienice z krótkich kresek („pierwsze wrażenie: Van Gogh”). Bez
  konturu, dłużej (kroki z 10 do 26 i więcej), szerzej, mniej krycia. Druga wersja `[26,6,7,.85]` nadal była Van
  Goghiem; dopiero obecne parametry przeszły.
- Po przesunięciu rzędów i kolumn na brzegach widać ciemne szczeliny: `margin` ≥ największe przesunięcie.
- W trybie konturu ręka z kubkiem jest przecięta linią tułowia: dorysuj bliższą rękę `KIT.nearArm`.
- Nie używaj komiksowego pisma ręcznego (Kalam) w napisach: wybija ze stylu. Nakładka zamienia `LXGWWenKai-500` na
  `Caveat-600`, też pismo ręczne, więc tytuł ustaw wprost w `IMFellEnglish-400`.

## Kontrola
- Czy pierwsze wrażenie to Munch, a nie Van Gogh (długie pociągnięcia bez konturu, żadnych krótkich kresek)?
- Czy pasy nieba się wiją, a cały obraz faluje razem z postaciami?
- Czy na lewej i prawej krawędzi nie ma ciemnych szczelin?
- Czy napisy są czytelne mimo falowania?
- Dowód z wzoru: mediana różnicy sąsiednich klatek 2,27%.

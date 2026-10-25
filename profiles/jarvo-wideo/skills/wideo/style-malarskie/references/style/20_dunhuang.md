# Malowidła z Dunhuangu, groty Mogao, rozkwit dynastii Tang (`20_dunhuang`)

Buddyjskie malowidło ścienne: czerwonoziemne tło, kolory z minerałów (malachit, azuryt, ochra, złoto), równa linia
„żelaznego drutu”, latające apsary z długimi wstęgami i ślady wieku: łuszcząca się farba odsłaniająca tynk, spękania,
wyblaknięcie, kopeć. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: apsara narysowana
zgrubnie (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 20_dunhuang --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-20_dunhuang.jpg`;
kod `$HUASHU/scripts/engine/scenes/20_dunhuang.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Turystyka: Jedwabny Szlak, Chiny, Azja Środkowa; muzeum, wystawa sztuki buddyjskiej: 5–15 s.
- Herbata, jedwab, kadzidła, joga i medytacja (wstęgi, kwiaty spadające z nieba): 10–20 s.
- Konserwacja zabytków, archeologia, historia marki „spod tynku” (łuszcząca się farba jako przejście): 5–10 s.

## Nie do
- Europejskie freski i ołtarze: `05_gothic` albo `06_renaissance`.
- Latająca postać w zbliżeniu (słabość wzoru).
- Jasne, nowoczesne marki: wyblaknięcie i spękania mówią „stare”.

## Cechy stylu (sprawdzalne)
- Linia „żelaznego drutu”: równa 2,6 px, kolor `#5a2414`; na twarzach bardziej czerwona `#8a3a24`.
- Kolory minerałów: czerwona ziemia `#a5452f`, malachit `#3f8f6e / #6ab08e`, azuryt `#2f5f8f / #5a86b0`, biel
  `#ecdfc4`, złoto `#d8b05a`; tynk pod farbą `#d8c6a2`.
- Tło: `PAINT.texture` `#a5452f` z ciemnym `#7a3020`, rzadkie wyblakłe rozety; u góry fryz z pnączy i trójkątne
  lambrekiny (na zmianę zieleń, biel, czerwień, złote perły). Posadzka z płytek z lotosami, niski stolik
  z ozdobnymi wycięciami, lampka oliwna.
- Strój z epoki Tang: czerwona spódnica w skośne zielone pasy (co 44 px, rozchodzą się w dół), azurytowa krótka
  kurtka, biały skrzyżowany kołnierz, wysoko zawiązany czerwony pas; wysoki kok z dwóch elips nad `headTop`, złota
  szpila, trzy kwiaty. Makijaż: kwiat na czole (4 czerwone płatki), czerwony łuk na skroni, małe usta, brwi jak
  czułki ćmy. Czarka z zielonkawej porcelany.
- Szal `shawl(pts, w)`: fala biegnąca → wstęga (`KIT.ribbon`) z białym przerywanym wzorem i czerwonymi kropkami. Tył:
  `x = back + 230q + 64q·sin(4.2q − 5.5t)`, ostatnie 30% unosi się w górę; przód opada wokół ramienia.
- Apsara: leży poziomo, głową w lewo, skala 1,35, przelatuje przez okno 300 px/s; trzy wstęgi falą biegnącą, jedna od
  ramienia łukiem nad głową i za plecy (ten łuk to najbardziej rozpoznawalny kształt), aureola, kok, talerz
  z kwiatami. Chmury szczęścia: kłęby ze zwężającym się ogonem, dryf 40–76 px/s.
- Postarzenie: `saturation` α .3 (wyblaknięcie), `multiply` jasnej tekstury α .5; łuszczenie per piksel tam, gdzie
  `fbm(x·.0032)+0.12·noise(x·.03) > 0.3` (widać tynk `#d8c6a2`), 0.28–0.3 to ciemny brzeg odprysku; 500 pęknięć
  (losowy spacer), kopeć na górnych 380 px.
- Napisy wzoru w `LXGWWenKai-500` → u nas `Caveat-600` (nakładka); dopisek ery `Cinzel-700` (ma polskie znaki).
  Tabliczka z napisem to jasny prostokąt z podwójną ramką i plamkami odprysków.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 20_dunhuang`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.texture`, `PAINT.fbm`, `PAINT.noise`, `PAINT.particles`),
   `kit.js` (`KIT.ribbon`, `KIT.densify`, `KIT.blob`, `KIT.choreo`, `KIT.label`), `rig.js`.
2. Kolejność: czerwonoziemny grunt (cache) → okno = azurytowe niebo z chmurami i apsarą → rama okna z pnączy →
   posadzka z lotosami (cache) → stolik, lampka → kot → postać (donatorka z epoki Tang) → para jako zwinięte chmurki
   → kwiaty z nieba → warstwa postarzenia.
3. Wszystko obrysuj równą linią 2,6 px (pomocnik `F(c, path, fill)` ze sceny: wypełnienie + obrys).
4. Wstęgi: punkty fali → `KIT.densify` → `KIT.ribbon(pts, q => szerokość)`; na wierzchu biała linia przerywana.
5. Postarzenie na końcu na cały kadr: `saturation`, `multiply` tekstury, potem mapa łuszczenia i spękań z cache
   `dh_age`. Postacie wyłącz z łuszczenia strefami ochronnymi: kot (380–720, 530–920), postać (1070–1530, 240–950).

## Co się rusza
- Wstęgi apsary i szal postaci falą biegnącą; chmury dryfują; apsara przelatuje.
- Kwiaty z nieba: 30 czteropłatkowych kwiatów obraca się i przewraca w locie w dół.
- Płomień lampki `1+0.12sin(17t)+0.08sin(29t)` z poświatą.
- 10 płatków farby odrywa się z brzegów łuszczenia, obraca się i spada po paraboli.
- Dzwoneczek na obroży kota się kołysze; kot obraca głowę (`look: sin(2.6t)`), oddech 2,5× mocniejszy.
- Picie z kubka; para jako białe zwinięte linie.

## Przejście-podpis (wejście w ten styl)
- `apsara`, 0,5 s (`TRANSITIONS.apsara`): czoło `x = lerp(W+260, −300, e) + 110sin(y·.006 + 5p)` zamiata z prawej
  do lewej, po prawej jest już nowy obraz. Na czole trzy wstęgi (malachit, czerwona ziemia, azuryt; szerokość
  44/38/32) falą biegnącą z białym przerywanym wzorem. Po lewej odłamki starego obrazu (bloki pikseli wzięte z A)
  obracają się i spadają po paraboli: stary obraz się łuszczy. Wyrasta z przelotu apsary i odpadania farby.

## Wydajność
- Źródło nie podaje ms na klatkę.
- Mapę postarzenia per piksel (1920×1080) licz raz do cache `dh_age`; grunt i posadzka też w cache.

## Pułapki
- Szum łuszczenia o częstotliwości .006 daje drobne kropki na całym ekranie, jak brud. Przy .0032 i wyższym progu
  wychodzą płaty.
- Łuszczenie na postaci czyta się jak dziury w ubraniu: strefy ochronne, łuszczy się tylko tło.
- Szal kołyszący się 18–34 px, prawie pionowo, wygląda jak oparcie krzesła. Daj ponad 200 px w poziomie i uniesiony
  koniec.
- Czerwony łuk na skroni przy większym kryciu wygląda jak blizna: α .32.
- Pełne zielone koło aureoli apsary czytało się jak koło ratunkowe: α .28 i cienka linia.
- Kot `#c8843a` po wyblaknięciu robi się brązowożółty: `#e08a3a`. Bez obrotu głowy i mocniejszego oddechu rusza się
  tylko ogon.

## Kontrola
- Czy linia ma wszędzie 2,6 px i kolor `#5a2414`?
- Czy łuszczenie tworzy płaty tylko w tle, a postacie są całe?
- Czy szal leci w poziomie ponad 200 px, a nie wisi?
- Czy apsara ma wstęgę łukiem nad głową?
- Dowód z wzoru: różnica klatek 0,45↔0,9 s = 6,6%, mediana sąsiednich 1,98%.

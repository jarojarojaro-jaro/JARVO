# Secesja – plakat Muchy (`10_nouveau`)

Plakat secesyjny (1896, w duchu Alfonsa Muchy): linie o zmiennej grubości (cienkie końce, grubszy środek), kontur
zewnętrzny grubszy niż linie wewnątrz, postać w aureoli z rozetą, włosy w esowatych lokach zakończonych spiralą,
kwiaty, kuta ornamentyka, łuk okna z witrażem i wschodzącym słońcem, pastelowe tło z wzorem kółek i ziarnem
litografii. Poznasz go po grubym konturze zewnętrznym (z prawej i od dołu najgrubszym) przy cienkich liniach w środku
i po „oddychającej” grubości każdej linii.
Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: kot w sztywnej pozie (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 10_nouveau --czasy 0.35,0.5,0.65 --arkusz out/wideo/wzor-10_nouveau.jpg`; kod
`$HUASHU/scripts/engine/scenes/10_nouveau.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Kosmetyki, perfumy, herbata, kawa, wino, czekolada: reklama 10–15 s, opakowanie w ozdobnej ramie.
- Plakat wydarzenia (teatr, koncert, festiwal, wystawa): 9:16 albo 4:5, 6–15 s.
- Kwiaciarnia, salon piękności, butik: spot 10–20 s.
- Ozdobny tytuł albo ramka z rozkwitającymi kwiatami: 3–5 s.

## Nie do
- Geometria, technika, przemysł: `12_bauhaus` albo `22_constructivism`.
- Złoto z mozaikowymi wzorami na szacie: `18_klimt`.
- Dane, schematy, krótkie komunikaty do szybkiego czytania: gramatyki explainera albo `style-motion`.

## Cechy stylu (sprawdzalne)
- „Bicz” secesyjny: każda łodyga, liść, noga kutego stołu, zawijas na banerze, pasmo włosów i smuga pary to wypełniony
  pasek o zmiennej szerokości; `swellW(wmax)` – cienki na końcach, gruby w środku (obwiednia sinus). Zawijasy kończą
  się spiralą, której promień maleje liniowo do 15%.
- Kontur zewnętrzny postaci grubszy niż linie wewnątrz: zewnętrzny brzeg 1,5 px, z prawej i od dołu 4–5 px, linie
  wewnętrzne 2 px.
- Tło: pionowy gradient szarozielony → oliwkowokremowy → brzoskwiniowy (`#b9cba0`→`#cfd3a6`→`#ecc9a2`) w ramie
  34..1886 × 32..907; wzór z kółek (pierścień r10 + kropka r2,6), rzędy co 54, kolumny co 62, co drugi rząd przesunięty
  o 31, kolor `rgba(120,140,100,.38)`; plamy litografii (mała mapa fbm 240×135 powiększona, α 0,5); ziarno
  `P.grain('nv', .05, …, .14)` na wierzchu.
- Pas mozaiki na podłodze: kratka 20×24, 9 kolorów w kolejności `(k*7+(k>>2))%9`; zielony baner `#8fac80`; złota rama:
  6 px złota `#c9a24a` + dwie linie 2 px ciemnego brązu.
- Aureola postaci R172: 18 okrągłych ćwieków i 32 płatki rozety; aureola kota R106: kwiat z 8 płatków i złoty
  przerywany pierścień. Łuk okna z witrażem: kwadraty 14×14 co 17 px wzdłuż łuku, obrócone po stycznej, 6 kolorów
  na zmianę; 14 ołowianych szprych od słońca (r 92→420).
- Włosy: masa (16 punktów `RIG.smooth`) + 7 loków z tyłu i 2 na ramieniu, każdy 12 punktów w kształcie S, zakończony
  spiralą 1,2 obrotu, szerokość od 14–18 do 2,5; kremowy rdzeń światła i ciemnozłota cienka linia; 6 małych loków
  na czubku. Szerokość pasma ≤18 px.
- Napis tytułowy `Marcellus-400` 76 px, `letterSpacing` 12, najpierw obrys 7 px ciemnego brązu, potem krem; Marcellus
  ma polskie znaki. Plakietka roku z filmu źródłowego: `LibreBaskerville-700` 96 px `#3a2a1c`, podpis `EBGaramond-600`
  29 px (polskie znaki są).
- Paleta: linia `#4e3320`; złoto `#c9a24a` / `#9c7a2e`; krem `#f6eedb`; skóra `#f6dcc4`; włosy `#e8bf55`, światło
  `#f6dc8a`, cień `#b9862a`; suknia `#f4ecda`; różowy szal `#e6aaa5`, fałdy `#d48e8c`; maki `#d9706a` / `#b4504b`,
  środek `#3f6a4a` ze złotymi kropkami; lilie `#f7f2e6`; kute żelazo `#3d7763`; kot `#e39a4c` / `#fbf3e3`, pręgi
  `#c0672c`, oczy `#e6c040`; aureola róż `#ebb8b2`, pierścień morski `#5f9a8a`, aureola kota czerwona `#b8473a`.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 10_nouveau`; `P` = `PAINT`, `RIG`, `U`.
2. Tło w całości do cache `nv_bg`: gradient, wzór kółek, plamy litografii, pas mozaiki, baner, tytuł, złota rama.
3. Linia o zmiennej grubości `ribbon(pts, w(q))`: punkty zagęść krzywą Catmulla–Roma (`dense`, 4–10 punktów na odcinek),
   w każdym punkcie odsuń w obie strony po normalnej o w/2, połącz w zamknięty wielokąt i wypełnij. Szerokość:
   `swellW(wmax, wend)`, `taperW(w0, w1)`; zakończenie `spiral(cx, cy, r0, a0, turns, dir)`; linie ozdobne
   `inkLine(c, pts, wmax, col, wend)`.
4. Gruby kontur zewnętrzny przez przesunięte sylwetki: wszystkie postacie (kot, postać, włosy, szal) rysuj do warstwy L
   poza ekranem w trybie `both` z `RIG` (`lw` 2, linie wewnętrzne poprawnie zasłonięte kolejnością części). Kopię L
   zabarw `source-in` na `#4e3320` i podłóż pod L na głównym płótnie trzy razy: przesunięcia `(−1.5,−1.5)`, `(3.5,4.5)`,
   `(2,2.5)`. Koszt: 3 pełnoekranowe `drawImage`.
5. Okno: łuk (proste boki + łuk elipsy rx219, ry130), niebo, słońce, pasma wzgórz rysowane po słońcu (naturalne
   zasłanianie przy wschodzie), szprychy, witraż na brzegu łuku (`windowGlass`).
6. Kwiaty (`flowers`): maki i lilie na łodygach-`ribbon` z trzema punktami kontrolnymi (wygina się tylko górna część),
   liście `blade`.
7. Postać i kot z kotwic `RIG` i `P.choreo` (picie, odchylenie głowy, mrugnięcie, ogon, oddech); spodek zostaje na stole
   (stół nie jest pusty, gdy kubek odjedzie). Włosy (`hairMass`, `hairLocks`, `crownCurls`) idą za przesunięciem
   `G.A.headC` – im niżej, tym słabiej.
8. Ziarno litografii na wierzch.

## Co się rusza
- Wschód słońca: `sy = 400 - (lt-0.267)·288`, `sx = 583 - (lt-0.267)·20` (≈ −5 px na klatkę, zmierzone w oryginale);
  przy lt=0 słońce na y=477 schowane za wzgórzem, przy lt=0,7 na y=275.
- Ołowiane szprychy: kąt `+lt·0.9·0.25`, chwianie ±0,04; jadą ze słońcem, więc cały podział witrażu się zmienia –
  to najmocniejszy ruch w oknie.
- Maki i lilie: głowa przesuwa się `sin(7.5t+φ)·13 + sin(3.1t+2φ)·5`; dwie kępy w przeciwfazie; liście 0,3 tej
  amplitudy.
- Aureole: ćwieki postaci `+0.9t`, płatki rozety `−0.63t`; kwiat kota `−1.1t` i złoty przerywany pierścień
  (`lineDashOffset`).
- Włosy: brzeg masy faluje `sin(6t+y·0.035)·9`; loki to fala biegnąca w dół `sin(7.4q+φ-7t)·(6+20q)`.
- Ozdobna para w kształcie S: 3 kremowe paski (szerokości 26 / 20 / 14) z obrysem 1,8 px i linią środkową, fala
  `sin(4q+φ-6t)·(18+70q)`, rozstęp rośnie z wysokością `×(1+2.6q)`, spirala 34 px na końcu; całość odchyla się
  `lean = -90 - 160·cup` w stronę okna.
- Odcinek w filmie źródłowym: 0,70 s (3 ósemki).
- Dowód: między lt 0,35 a 0,65 zmienia się 13,1% pikseli.

## Przejście-podpis (wejście w ten styl)
- `organic`, 0,24 s, wyrasta z aureoli postaci (1330, 320): organiczny kształt z falistym brzegiem (promień `e·2300`,
  harmoniczne `0.22·sin3a + 0.12·sin5a + 0.06·sin9a`, oś y ×0,92) rośnie i połyka obraz; w środku nowy obraz,
  brzeg 14 px `#6b4a24` + 8 px złota `#d9b25a`.

## Wydajność
- Ciepła klatka: średnio 29 ms, maks. 37 ms; pierwsza (budowa cache) ≈80 ms. Determinizm: ta sama lt dwa razy daje
  identyczne piksele.
- Cache: `nv_bg` (całe tło); plamy litografii z małej mapy fbm 240×135 – setki razy szybciej niż szum na pełnym ekranie.

## Pułapki
- `RIG.drawGirl(mode: 'line')` na wierzchu przebija liniami zasłonięte części (dalszy rękaw przez tułów). Rysuj linie
  w warstwie poza ekranem w trybie `both`, kolejność części, potem gruby kontur zewnętrzny przesuniętymi sylwetkami.
- Włosy z 7 długich pasów 34 px wyglądają jak kiełbaski albo makaron. Secesyjne włosy to masa + cienkie loki S
  ze spiralą, szerokość ≤18.
- Para unosząca się pionowo przecina twarz, gdy kubek jest przy ustach; odchylaj ją z `cup` w stronę okna.
- Klatki z lt <0,33 nie nadają się do pomiaru ruchu (uderzeniowy zoom 1,03 przez 20 klatek od początku przejścia).
- Do poprawy (ze źródła): kot siedzi sztywno na prostych białych łapach; leżący puszysty kot pasowałby bardziej.
  Tytuł w `Marcellus`; bardziej okrągłe, ręcznie rysowane litery secesyjne wymagają własnych ścieżek liter.

## Kontrola
- Czy linie mają zmienną grubość (cienkie końce, grubszy środek) i kończą się spiralą?
- Czy kontur zewnętrzny jest wyraźnie grubszy z prawej i od dołu niż linie wewnątrz postaci?
- Czy włosy to cienkie loki S na masie, a nie grube pasy?
- Czy w oknie widać ruch (wschód słońca, szprychy), a aureole się obracają?
- Czy polski napis jest w kroju z polskimi znakami i ma ciemny obrys?

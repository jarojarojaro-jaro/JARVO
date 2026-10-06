# Postimpresjonizm – Van Gogh (`09_postimp`)

Obraz w duchu Van Gogha (1889, „Sypialnia w Arles” i „Gwiaździsta noc”): długie, grube pociągnięcia z ciemnym
obrysem, które płyną wzdłuż pola kierunków (ściana pionowo, podłoga do punktu zbiegu, niebo wirami), kilkanaście
odcieni w każdej strefie, granatowa, lekko drżąca linia wokół przedmiotów. Poznasz go po wirach na niebie, ścianie
z pionowych smug „jak płomienie” i podłodze z kresek biegnących w głąb. Jakość wzoru: ★★★ (wzorzec biblioteki: inne
style budowano według jego struktury); słabość wzoru: najcięższy, ~110–120 ms na klatkę (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 09_postimp --czasy 0.35,0.5,0.65 --arkusz out/wideo/wzor-09_postimp.jpg`; kod
`$HUASHU/scripts/engine/scenes/09_postimp.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Galeria, festiwal, wydarzenie kulturalne, noc muzeów: spot 10–20 s, 16:9 i 9:16.
- Nocne tematy: planetarium, kawiarnia nocą, koncert pod gwiazdami: 10–30 s.
- Marka kreatywna albo rzemieślnicza z charakterem (pracownia, kwiaciarnia ze słonecznikami): reklama 10–15 s.
- Mocne ujęcie otwierające („hero”) w dłuższym filmie: 3–6 s.

## Nie do
- Długie filmy w wysokiej rozdzielczości przy ciasnym budżecie renderu (~110–120 ms na klatkę): policz czas
  i powiedz właścicielowi przed renderem albo wybierz lżejszy styl (`13_pop`, `12_bauhaus`).
- Spokój, elegancja, klasyka: `06_renaissance`. Niepokój i deformacja: `19_munch` (ten sam typ renderera, inna
  ekspresja).
- Jasne, pastelowe światło dzienne: `08_impressionism`.

## Cechy stylu (sprawdzalne)
- Trzy osobne przejścia pociągnięć z ciemnym obrysem (`outline` 0,8–0,9, 38–45% granatu w kolorze obrysu):
  - wszystko poza ścianą i podłogą: `cell 10, len 22, width 6.5`;
  - ściana: `cell 14, len 64, width 8`;
  - podłoga: `cell 12, len 46, width 8`.
- Pole kierunków: ściana pionowo `−π/2 + 0.26·noise(…)` i powoli faluje w czasie jak płomień; podłoga wzdłuż linii
  zbiegających się w (960, 330); niebo wzdłuż stycznej do najbliższego wiru + `0.3t`; aureola lampy po okręgu;
  wezgłowie pionowo, prześcieradło prawie poziomo; blat stołu poziomo.
- Paleta strefami (`P.swatch`, mixBase 0,15–0,45):
  - ściana: `#7f9be6 #5f7fd8 #a7bbf2 #6c6fd2 #8ad0e6 #c3cbf6 #4f6cc8 #9a8fe0` (mixBase 0,3);
  - niebo: `#22339a #2f4fb8 #5c86dc #8fb6ee #1b2a78 #3c6bd0` (mixBase 0,45);
  - podłoga: `#c0573c #a8453a #d7774a #8e3b30 #5f8f6a #c96a52 #e08a5c` (mixBase 0,3);
  - drewno: `#f2c13a #e0a020 #f8d860 #d08a18 #b8c040` (mixBase 0,15); łóżko: `#e04a32 #c63a2a #f06b45 #b83224` (mixBase 0,4);
  - zieleń (rama okna): `#2f9a5c #4fc27a #1f7a48 #8be09a` (mixBase 0,35); aureola lampy: `#fff2a0 #f6d84a #ffe680 #f0c040` (mixBase 0,3).
- Podkład (kolory bazowe): ściana `#5b7bd3`→`#4462bd`, niebo `#1d2c7c`→`#3a5bc0`, wir `#8fb3ec`, gwiazdy `#f6d84a`,
  rama okna `#2f8f58` / `#6fd08a`, podłoga `#b5553b` / szpary `#8a3a2c`, drewno `#e3ad38` / `#b57d1c`, łóżko `#d9472f`,
  cyprys `#1f4a2c`, wioska `#1a2160`.
- Linia otoczenia: granat `#1c2458`, 4,5 px, „wrze” 8 razy na sekundę (`P.boilSeed(t, 8)`, `P.roughPath`
  z `amp: 2.2, step: 14`).
- Kot z wirami: 7 pierścieni na zmianę `#c96a1e` / `#f7c063`, linia 7 px, przycięte do ciała, obrót 0,6 rad/s.
- Postacie z ciemnym granatowym konturem tylko tam, gdzie widać krawędź (`RIG.visibleLines`).
- Napisy (plakietka roku z filmu źródłowego): `LilitaOne-400` 104 px `#f5d03b` z cieniem `#2a2a6a` (3, 4); w nakładce
  `huashu_pl.js` `LilitaOne` → `Poppins-800` (Lilita nie ma polskich znaków).

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 09_postimp`; `P` = `PAINT`
   (`/_lib/huashu/lib/paint.js`), `RIG` (`lib/rig.js`), `U`. To wzorzec pięciu warstw: płaski podkład → renderer
   stylu → rekwizyty osobno → postacie → ruchome światła.
2. Płaski podkład `base(g, t)` do `P.scratch('vgBase')`: ściana, podłoga ze szparami zbiegającymi się do VP=(960, 330),
   kolor aureoli lampy (duża plama dla pociągnięć), okno z nocnym niebem (wiry jako spiralne pasy obracane w czasie,
   księżyc, płomienisty cyprys, wioska ze światłami), zielona rama, łóżko po prawej.
3. Pociągnięcia trzema przejściami po masce (`isWall`, podłoga `y > 704`, reszta):
   `P.strokes(c, b, { cell: 10, len: 22, width: 6.5, angle, seed: 9, t, boil: 0, outline: 0.9, outlineMix: 0.45, palette, mask })`,
   ściana `{ cell: 14, len: 64, width: 8, seed: 19, outline: 0.8, outlineMix: 0.38 }`,
   podłoga `{ cell: 12, len: 46, width: 8, seed: 29, outline: 0.85, outlineMix: 0.45 }`.
4. `palette(x, y, col, r)` wybiera `P.swatch` strefy po położeniu; na niebie jasne miejsca (suma RGB >500) zwracają
   `null` – zostają jasne gwiazdy i księżyc z podkładu.
5. Rekwizyty osobno (`P.scratch('vgProps')`): obrazki na ścianie, krzesło, stół, wazon ze słonecznikami, lampa;
   na nich `source-atop` drobne pociągnięcia
   `{ cell: 7, len: 14, width: 4.5, outline: 0.5, outlineMix: 0.35, jitterCol: 34, alphaMask: true }`,
   nogi mebli pionowo. Potem jedno `drawImage`.
6. Linia otoczenia `lines(c, t)`: kontury okna, stołu, krzesła, łóżka, obrazków, wazonu i szpar podłogi
   przez `P.roughPath` z ziarnem `P.boilSeed(t, 8)`.
7. Postacie do `P.scratch('vgChars')`: `RIG.drawCat(lg, K, { ...catPal, lw: 0 })`,
   `RIG.drawGirl(lg, G, { ...girlPal, mode: 'fill' })`; potem `source-atop`
   `P.strokes(lg, L, { cell: 8, len: 16, width: 5, outline: 0, jitterCol: 22, alphaMask: true, angle })`
   (kot po okręgu wokół (545, 760), postać pionowo `−π/2 + 0.3·sin(y·0.02)`); wiry na kocie przycięte `lg.clip(K.body)`.
8. Kontur widocznych krawędzi:
   `RIG.visibleLines('vgCat', (g, lc) => RIG.drawCat(g, K, { ...catPal, line: lc, whisker: lc }), C.line, [340, 500, 740, 940])`
   i tak samo dla postaci. Funkcja rysuje dwa razy z białym kolorem linii jako znacznikiem; zostają tylko linie,
   których nic nie zasłania (też rysy twarzy).
9. Kapelusz słomkowy jeszcze raz na wierzchu (wypełnienie, 70 krótkich kresek słomy na rondzie, 30 na główce, wstążka,
   kontur), bo linie ronda przebijają przez włosy.
10. Ruchome światła na końcu (opis niżej) i para `P.steam(c, t, G.cup.x, G.cup.y - 6, { h: 70, n: 2, … })`.

## Co się rusza
- Pole kierunków ściany zmienia się w czasie (`noise(x·0.008 + t·0.5, y·0.008 + 3 − t·0.8)`), więc pociągnięcia
  falują jak płomień przy stałych położeniach; wiry na niebie obracają się (`t·(0.9+k·0.2)`, na przemian w obie strony).
- Aureola lampy: 3 przerywane pierścienie (`setLineDash([22, 14])`, `lineDashOffset = −t·60`) rosną z r 40 do 150
  i gasną, faza `(t·0.9 + k/3) % 1`, tryb `lighter`.
- Gwiazdy migają: `0.75 + 0.35·sin(t·5 + k·1.7)` (rdzeń i halo).
- Słoneczniki kołyszą płatkami `sin(t·3 + k)·0.08`.
- Kot: wiry na ciele obracają się 0,6 rad/s, ogon, mrugnięcie, oddech z `P.choreo`; postać pije (`cup`, `sip`).
- Linia otoczenia wrze 8 razy na sekundę (tylko linia, nie pociągnięcia).
- Odcinek w filmie źródłowym: 3 ósemki (0,70 s).

## Przejście-podpis (wejście w ten styl)
- `swirl`, 0,28 s, środek w oknie (560, 340): wir gwiaździstej nocy. Przy połowie rozdzielczości każdy piksel jest
  obracany wokół środka: stary obraz skręca się coraz mocniej (do `5.0·f²` rad), nowy wkręca się od środka (resztkowy
  skręt `4.2` i obrót `−0.9`, które maleją do zera), promień R=1100, granica falista (`sin(3·kąt)`); ostatnie 15%
  to przenikanie do czystego obrazu.

## Wydajność
- ~110 ms na klatkę (indeks źródła: 120 ms) – trzy pełnoekranowe przejścia `P.strokes` + rekwizyty + postacie.
  Najcięższy styl biblioteki. Przed długim renderem policz czas klatek i powiedz właścicielowi.
- W przejściu z `08_impressionism` oba style rysują się naraz (~69 + 110 ms) przez kilkanaście klatek.
- `P.scratch` dla `vgBase`, `vgProps`, `vgChars`; podkład co klatkę od nowa (wiry się obracają).

## Pułapki
- Jedne parametry na cały obraz dają dywan: ściana, podłoga i reszta muszą mieć osobne przejścia.
- Małe przedmioty duże pociągnięcia rozbijają na plamy: zawsze osobna warstwa rekwizytów z drobnym pędzlem.
- Sam szum koloru daje „szum jednego niebieskiego”. Van Gogh to kilkanaście odcieni ze strefowej palety.
- Ziarno pociągnięć zmieniane na całym ekranie 8 razy na sekundę daje miganie (różnica klatek 18–20, więcej niż
  przejście); położenia stałe, ruch z pola kierunków, wrzenie tylko dla linii.
- `RIG.drawGirl` z `mode: 'line'` na wierzchu przebija liniami zasłonięte części (dalszy rękaw przez tułów, tył ronda
  przez włosy); używaj `RIG.visibleLines` i dorysuj kapelusz na końcu.

## Kontrola
- Czy ściana, podłoga i niebo mają różne pola kierunków (pion, zbieg do punktu, wiry)?
- Czy w każdej strefie widać kilkanaście odcieni, a pociągnięcia mają ciemny obrys?
- Czy pociągnięcia nie migają między klatkami, a mimo to ściana faluje?
- Czy małe przedmioty i postacie są czytelne, z konturem tylko na widocznych krawędziach?
- Czy czas klatki mieści się w budżecie renderu całego filmu?

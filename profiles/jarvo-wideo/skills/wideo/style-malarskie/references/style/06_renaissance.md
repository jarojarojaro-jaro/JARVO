# Renesans – sfumato (`06_renaissance`)

Obraz olejny dojrzałego renesansu (ok. 1503, w duchu Leonarda da Vinci): miękkie przejścia bez konturów (sfumato),
ciemne wnętrze z łukowym oknem, za nim błękitniejący pejzaż (perspektywa powietrzna), posadzka w perspektywie,
werniks z siatką spękań. Poznasz go po miękkich krawędziach przy czytelnych rysach twarzy, ciepłym półmroku, smudze
światła z kurzem i krakelurze. Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: kot zbyt
kreskówkowy, całość zbyt statyczna (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 06_renaissance --czasy 0.4,0.8,1.2 --arkusz out/wideo/wzor-06_renaissance.jpg`; kod
`$HUASHU/scripts/engine/scenes/06_renaissance.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Muzeum, galeria, wykład o sztuce: film 30–60 s z lektorem.
- Innowacja z tradycją (wynalazek, biuro projektowe, uczelnia techniczna – motyw maszyny latającej): intro 10–20 s.
- Kancelaria, bank prywatny, wino premium, zegarmistrz: spot 15–30 s, spokojny, z powagą.
- Portret marki albo założyciela w klimacie „mistrza”: 5–10 s.

## Nie do
- Dynamika i energia (styl jest spokojny, ruch mały): `09_postimp` albo `19_munch`.
- Jasne, pastelowe, letnie: `08_impressionism`.
- Nocny, mocny światłocień ze świecą: `32_rembrandt` (uwaga: tam jakość ★).

## Cechy stylu (sprawdzalne)
- Cała scena lekko rozmyta (`blur(1.3px)`), postacie miękkie, ale z czytelnymi oczami i ustami; postacie bez linii,
  bryła tylko z gradientów: fałdy spódnicy jasne `rgba(200,70,60,.3)`, ciemne `rgba(40,0,0,.45)`; aksamitny rękaw ze
  smugą światła `rgba(170,200,140,.45)` wzdłuż kości; twarz oświetlona z lewej, cienie w oczodołach.
- Ściana: ciemny tynk `#43321f`→`#22180e`, poświata wokół okna, góra przyciemniona.
- Okno łukowe z kamienną ramą oświetloną z lewej; za nim trzy pasma gór, im dalej, tym bardziej niebieskie i blade
  (`#9fb4b8` → `#7d9294`, kontury z fbm), jezioro, dolina (od szarej zieleni do ciepłej ochry), kręta srebrzysta
  rzeka (szerokość 3→16 px z odległością), cyprysy, okrągłe drzewa, kamienny most.
- Posadzka w prawdziwej perspektywie: `y = 420 + f·h/Z`, `x = 960 + f·X/Z`, f=1029, h=5,75, Z od 16 co płytkę 1,4;
  pierwszy rząd na y=790, potem 825 / 868 / 922 / 989. Płytki `#a88c64` i `#5c2418`, plama światła w `soft-light`
  i przyciemnienie wokół środka (760, 960).
- Warstwa „obrazu” na wierzchu: winieta (α 0,3 na 0,55 promienia, α 0,8 przy krawędzi), żółty werniks α 0,07, splot
  płótna co 3 px, 9000 pociągnięć pędzla (α 0,022/0,028, szerokość 5–10, kierunki losowe), krakelura
  `P.craquelure('ren', 0.55)` α 0,32 + jej biała kopia przesunięta o 1 px (α 0,16, `lighter`) jako podniesione
  brzegi werniksu.
- Smuga światła z okna z miękkimi krawędziami i unoszącym się kurzem.
- Napisy (plakietka roku z filmu źródłowego): `CormorantGaramond-500` 104 px `#ece0bf`, podpis `Cinzel-700` 30 px;
  oba mają polskie znaki.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 06_renaissance`; `P` = `PAINT`, `RIG`, `U`.
2. Warstwa statyczna `ren_static`: najpierw pokój na zwykłym płótnie (ściana
   `P.texture('ren_wall', '#43321f', { scale: 0.0024, amt: 30, grain: 12, dark: '#22180e', seed: 21 })`
   + gradient wokół okna, okno, pejzaż, posadzka, stół z białym obrusem, krzesło z oparciem drabinkowym), potem
   całość przez `g.filter = 'blur(1.3px)'` do cache. To jest sfumato całego obrazu.
3. Pejzaż (perspektywa powietrzna) w oknie: trzy pasma gór coraz bledsze i bardziej niebieskie, jezioro, dolina, rzeka
   poszerzająca się ku widzowi, drzewa, most.
4. Smuga światła (`ren_beam`): klin narysowany raz z `blur(28px)`, co klatkę nakładany w trybie `screen`.
5. Co klatkę: refleksy na rzece (24 punkty płyną z nurtem i migoczą) → ptaki → maszyna latająca (wszystko przycięte
   do okna) → postacie → smuga światła i kurz → warstwa obrazu.
6. Postacie do warstwy poza ekranem `renChars` (`P.scratch`), tylko w obszarze (320, 180, 1200, 780). Na obraz dwa razy:
   najpierw `c.filter = 'blur(1.6px)'`, potem ta sama warstwa ostra z α 0,82. Miękki brzeg, czytelne rysy.
7. Postać: `RIG.girl({ cup, sip: sip*1.6, hair: 'long', breathe: breathe*2.5 })`; srebrny kubek, przy cup>0,7
   zamknięte oczy. Kot: `RIG.cat` z ogonem ×2,2, ciało `RIG.smooth(K.bodyPts)`; przyciemnienie wewnątrz konturu
   14 px α 0,22, biała pierś gradientem radialnym, który wtapia rudą sierść (bez twardej granicy).
8. Warstwa obrazu `ren_over` (cache, jedno `drawImage` na klatkę): winieta, werniks, splot płótna, pociągnięcia
   pędzla, krakelura z jasnym brzegiem.

## Co się rusza
- Maszyna latająca Leonarda: w 0–1,35 s przelatuje przez okno (po poprawce powiększona 1,6×, trasa 440→790 px),
  unosi się i opada, pochyla ±0,07. Dwa nietoperzowe skrzydła biją `up = 0.5+0.5·sin(t·12+faza)`, końcówki od −118
  do +24 px; dalsze skrzydło w skali 0,78, ciemniejsze, faza przesunięta o 0,5. Skrzydło: krawędź natarcia + 6 żeber
  promieniście + membrana z falbaniastym brzegiem; ster ogonowy też się rusza.
- Ptaki: 14, skala 1–1,8.
- Refleksy na rzece płyną z nurtem i migoczą; cień chmury przesuwa się po dolinie.
- Smuga światła: jasność `0.75+0.35·sin(t·2.3)` („chmura zasłania słońce”); kurz unosi się w smudze i miga:
  `P.particles(70, 17, t, { x0: 440, x1: 880, y0: 1000, y1: 430, speed: 60, drift: 18, life: 6 })`.
- Postać pije (sip ×1,6), końce włosów kołyszą się ±11 px. Kot: głowa przechyla się i ociera ±0,16 rad wokół szyi,
  mruży oczy na zmianę mocniej i słabiej, ogon ×2,2, oddech ×3, odwraca głowę (`look`) w lewo i w prawo.
- Odcinek w filmie źródłowym: 4 ósemki (0,94 s).
- Dowód: średnia różnica klatek w odcinku wzrosła z 0,20–0,30 (zależnie od pomiaru) do 0,37 po poprawkach;
  oryginał 0,43. Styl zostaje spokojny – to jego słabość.

## Przejście-podpis (wejście w ten styl)
- `godRays`, 0,4 s, środek w oknie (560, 290): z okna wybucha złote światło. Nowy obraz wchodzi przez `ease.out` w postępie
  0,05–0,5; poświata radialna r 520 w trybie `lighter` (szczyt w połowie), 34 promienie długości 2400 kolorem
  `rgba(255,214,120,…)`, obracające się powoli (`p·0.35`).

## Wydajność
- 16–37 ms na klatkę (mediana 16 ms).
- Cache: `ren_static` (już rozmyta), `ren_over` (warstwa obrazu, jedno `drawImage`), `ren_beam` (rozmyty klin).
  Co klatkę rozmywasz tylko wycinek z postaciami 1200×780.

## Pułapki
- Pociągnięcia pędzla w warstwie obrazu: 26 000 sztuk, α 0,05, kierunek wg szumu robi z ściany wiry Van Gogha.
  Klasyczny olej to 9000 sztuk, α ~0,025, kierunki losowe.
- Przyciemnienie wewnątrz konturu kota 26 px α 0,45 zmienia białe ciało w szklany klosz; 14 px α 0,22 i gradient
  na piersi.
- Posadzka za jasna i za kontrastowa wygląda jak ilustracja wektorowa. Przyciemnij brzegi, zostaw tylko plamę
  światła z okna.
- Smuga światła jako ostry wielokąt co klatkę ma fałszywie twarde krawędzie; rozmyj raz i nakładaj z cache.
- Za mocne rozmycie postaci (2,6 px, ostra warstwa α 0,38) przy ostrym pejzażu odwraca głębię ostrości: bohater
  rozmyty, tło ostre. Rozmycie 1,6 px, ostra warstwa α 0,82.
- Płaska maszyna latająca wygląda jak papierowy samolot; dopiero żebrowane skrzydło-wachlarz czyta się jak projekt
  Leonarda.

## Kontrola
- Czy krawędzie są miękkie, a oczy i usta postaci nadal czytelne?
- Czy pejzaż za oknem robi się coraz bardziej niebieski i blady z odległością?
- Czy posadzka zbiega się w perspektywie i jest jasna tylko w plamie światła?
- Czy na wierzchu jest krakelura, splot płótna i żółty werniks, a pociągnięcia pędzla nie układają się w wiry?
- Czy w odcinku coś się wyraźnie rusza poza postacią (maszyna, ptaki, kurz, cień chmury)?

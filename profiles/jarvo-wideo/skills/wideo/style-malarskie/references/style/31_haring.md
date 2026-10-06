# Keith Haring (`31_haring`)

Nowy Jork 1982, od kredowych rysunków w metrze do sklepu Pop Shop: płaskie czyste kolory, wszystko obrysowane
jednakowo grubą czarną linią z zaokrąglonymi końcami, tańczące ludziki, „promieniste dziecko”, krótkie kreski ruchu
wokół przedmiotów, a całość podskakuje do rytmu. Postacie bez twarzy. Jakość wzoru: ★★★ (rozpoznawalny od razu,
gotowy do użycia); słabość wzoru: dziewczyna jest za mało „haringowa” (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 31_haring --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-31_haring.jpg`;
kod `$HUASHU/scripts/engine/scenes/31_haring.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Muzyka, taniec, festiwal, klub: Reels 9:16, 10–20 s, wszystko do bitu.
- Kampania społeczna (zdrowie, równość, wolontariat, zbiórka): 15–30 s z lektorem, proste znaki zamiast zdjęć.
- Marka dla dzieci i młodzieży, warsztaty, edukacja.
- Animowane ikony i maskotki do logo i przerywników: pętla 1–4 s.

## Nie do
- Realistyczny produkt, twarz, portret: `35_shinkai` albo `32_rembrandt`.
- Spokojny, luksusowy ton: `29_seurat` albo `28_monet`.
- Rysunek z wrzącą linią bez graffiti: `style-motion`, karta `kreska`.

## Cechy stylu (sprawdzalne)
- Tło płaskie: żółta ściana `#ffd51c`, zielona podłoga `#16a54a`, czarna linia horyzontu 14 px.
- Wszystko to linia 13 px (`LW = 13`), czarna, z zaokrąglonymi końcami i złączami, plus płaski kolor. Każda część:
  „wypełnij → obrysuj”.
- Paleta (z kodu): czerwony `#e8262b`, niebieski `#1f62d6`, róż `#ff6fb0`, pomarańcz `#ff8a1c`, biel `#ffffff`, tusz
  `#111111`, skóra `#ffd9b8`.
- Tańczący ludzik: 7 kapsułek kończyn (`RIG.limb`) i okrągła głowa. **Najpierw wszystko obrysuj na czarno 2×LW,
  dopiero potem wypełnij kolorem** – wychodzi jeden kontur całej sylwetki. 4 pozy (lokalne punkty, początek u stóp),
  przełączane 8 razy na sekundę bez interpolacji; przy dłoniach łuki ruchu.
- Kreski ruchu: n krótkich prostych na elipsie wokół obiektu (długość 22–34, grubość 7–9), nowe kąty 8 razy na
  sekundę. Na kocie, głowie dziewczyny, filiżance, czajniku, sercu, ludziku.
- Twarz: tylko kropka oka i czerwona kreska ust (u Haringa postacie nie mają rysów; ta odrobina jest po to, żeby
  rozpoznać postać).
- Postać we wzorze: nowojorska dziewczyna z lat 80. – szeroki czerwony sweter (ściągacz u dołu), dżinsowa długa
  spódnica, białe wysokie trampki; grube czarne kółko ucha czyta się jak słuchawki walkmana.
- Krój plakietki we wzorze: `Kalam-700`; ma polskie znaki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 31_haring`. `P` = `PAINT`,
   `RIG` (`lib/rig.js`: `RIG.limb`, `RIG.girl`, `RIG.cat`, `RIG.drawGirl`, `RIG.drawCat`).
2. Tło płaskie i linia horyzontu.
3. Okno: gruba czarna rama, niebieskie tło, w środku promieniste dziecko (biała sylwetka obrysowana 22 px, 14
   promieni). Szczebel okna pod dzieckiem.
4. Ludziki na ścianie: 3 sztuki (czerwony, niebieski, różowy), różne fazy, jeden odbity lustrzanie; nad stołem
   czerwone serce z kreskami ruchu.
5. Stół, czajnik, kot, dziewczyna: każde z obrysem LW i podskokiem. Dziewczyna `RIG.drawGirl` z `line` = tusz,
   `lw: LW`, `locks: false` (bez cienkich pasm włosów), własne `features` (kropka oka, kreska ust).
6. Kreski ruchu na koniec, na wierzchu.

## Co się rusza
- Wszystko do bitu: `bounce=|sin(t·128/60·π)|^0.6` (we wzorze 128 BPM; ustaw tempo swojej muzyki). Dziewczyna
  `dy=−12·bb`, kot przesunięty o pół bitu. Stół ściska się i rozciąga od nóg (sy `1−0.07(1−bb)`,
  sx `1+0.05(1−bb)`), nogi stołu się wyginają; czajnik skacze 26 px; rama okna kołysze się ±0.025 rad; kreski
  „skoku” na podłodze zmieniają długość z bitem.
- Ludziki na ścianie: 4 pozy w 8 fps.
- Promieniste dziecko raczkuje (2 klatki na zmianę), promienie krótkie/długie na zmianę w 8 fps.
- Serce pulsuje z bitem.
- Różnica klatek 11,5%.

## Przejście-podpis (wejście w ten styl)
- `radiant`, 0,32 s (`cx 1000, cy 600` – filiżanka): tańczący ludzik z rękami w V rośnie od filiżanki, skala
  `s=0.15·320^easeInOut(p)`. Kontur: obrys 30 px i wypełnienie na czarno; w ciele nowy obraz (poza ekranem kończyny
  wypełnione bielą, potem `source-in` nowy obraz). Wokół 16 kresek ruchu skacze w 8 fps. Od p>.82 dokładane
  przenikanie.

## Wydajność
- Ok. 4 ms na klatkę. Nic nie trzeba trzymać w cache.

## Pułapki
- Odwrotne zakończenia `RIG.limb` przy grubym obrysie zostawiały dziury w stawach. W aktualnej bibliotece poprawione;
  sprawdź na stopklatce kolana i łokcie.
- Szczebel okna rysuj pod dzieckiem, nie na nim.
- Cienkie pasma włosów z `RIG` łamią zasadę jednej grubości linii, a przy odchylonej głowie przecinają twarz.
  Wyłącz je (`locks: false`).
- Nie interpoluj póz ludzików – płynny ruch zabija styl. Twarde cięcie w 8 fps.
- Słabość wzoru: dziewczyna jest zbyt „normalna”. Upraszczaj ją w stronę ludzika Haringa (kapsułki, okrągła
  głowa, kreski ruchu).

## Kontrola
- Czy każda linia ma tę samą grubość i zaokrąglone końce?
- Czy ludziki zmieniają pozy skokowo w 8 fps, bez interpolacji?
- Czy wszystko podskakuje do tego samego tempa, zgodnego z muzyką?
- Czy postacie są bez rysów (najwyżej kropka oka i usta)?
- Czy kolory są płaskie, bez gradientów i cieni?

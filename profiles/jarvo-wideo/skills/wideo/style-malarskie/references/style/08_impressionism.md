# Impresjonizm (`08_impressionism`)

Obraz impresjonistyczny (1874, w duchu Moneta): krótkie, nieobwiedzione pociągnięcia w pastelowych barwach, różowo-
fioletowe ściany w słońcu, ogród za oknem, migające plamy światła na podłodze i stole. Poznasz go po tym, że cały obraz
jest z krótkich kresek w kilku barwach na każdą strefę, bez konturów, a światło „skacze” po powierzchniach.
Jakość wzoru: ★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: pędzel rozbija twarz i dłonie (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 08_impressionism --czasy 0.35,0.5,0.65 --arkusz out/wideo/wzor-08_impressionism.jpg`; kod
`$HUASHU/scripts/engine/scenes/08_impressionism.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Kwiaciarnia, ogród, szkółka roślin, agroturystyka: spot 10–20 s, wiosna i lato.
- Kawiarnia, cukiernia, hotel, spa: film nastrojowy 15–30 s pod muzykę albo lektora.
- Wesele, zaproszenie, rocznica: pętla 5–10 s pod napis.
- Turystyka (prowincja, jezioro, ogród zabytkowy): 15–30 s.

## Nie do
- Twarze i dłonie z bliska (słabość wzoru): `25_ghibli` albo `16_2026`.
- Woda, staw, odbicia jako temat główny: `28_monet`. Kropki tej samej wielkości i czyste barwy: `29_seurat`.
- Ostre logo, drobny tekst, dane: `style-motion` albo gramatyki explainera.

## Cechy stylu (sprawdzalne)
- Cały obraz z krótkich pociągnięć bez obrysu (`outline: 0`), w szczelinach prześwituje jasny grunt `#f2e6ee`.
- Dwie grubości: główny obraz `cell 11, len 20, width 7`; widok za oknem i obrazek na ścianie
  `cell 6, len 11, width 4.5` (inaczej domy i postacie za oknem znikają).
- Kierunki pociągnięć: ściana ukośnie w prawo w górę (w słońcu −0,95 rad, gdzie indziej −0,55, ±0,55 szumu),
  podłoga prawie poziomo, zasłony i obrus pionowo, roślina promieniście od donicy, niebo za oknem poziomo,
  „Impresja, wschód słońca” na ścianie poziomymi falami.
- Paleta strefami (`P.swatch`, mixBase 0,3–0,45):
  - ściana (9 barw): `#f3c6d2 #e8b6dc #f6dcc0 #d8c0ec #fbe8b0 #f0a8c0 #c8b8f0 #fff2d8 #e8c8f0`;
  - ściana w słońcu (7): `#fff0b0 #fbe08a #ffe8c8 #f8d0d8 #fff8e0 #f0c0d8 #e8d0f8`;
  - podłoga (7): `#e8a090 #d88aa0 #f0b890 #c890b8 #f6c8a0 #b0a0d8 #e89880`;
  - niebo: `#8ab4e8 #a8c8f0 #f0f4ff #7aa0e0 #c0d8f8`; zieleń: `#5aa84a #8ac860 #3a8a4a #b8d870 #2f7a50 #a0e080`;
  - zasłony (lawenda): `#b8b0f0 #d0c8f8 #9890e0 #e8e0ff #ffffff`; obrus: `#ece8fa #b8b0ec #f8f4ff #a49ce0 #fff8f0 #9a96d8`.
- Ściana gradientem `#d8bede`→`#f0c8cc`→`#f2c4d4`, w prawym górnym rogu ciepła plama słońca r=900.
- Postacie: najpierw płasko, potem tym samym rendererem drobne pociągnięcia tylko wewnątrz postaci; biała suknia
  w bieli, lawendzie i kremie. Bez konturów: tylko oczy i usta cienką fioletową linią `rgba(110,90,170,.75)` 2,4 px.
- Plamy słońca: 26 (6 na stole, 20 na podłodze), każda z 40 jasnych, żółtobiałych krótkich kresek.
- Napisy (plakietka roku z filmu źródłowego): `PlayfairDisplay-400i` 104 px `#5a4f9a`, podpis `EBGaramond-600` 30 px;
  oba mają polskie znaki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 08_impressionism`; `P` = `PAINT`,
   `RIG`, `U`.
2. Płaski podkład `impBase` (`P.scratch`) co klatkę od nowa, bo maki, chmury, bukiet, roślina i zasłony się ruszają:
   ściana z plamą słońca; ogród za oknem (niebo, las, dom z czerwonym dachem, łąka, 70 maków, kobieta z parasolką
   i dziecko, kępy kwiatów); białe ramy okna, lawendowe zasłony, obrazek na ścianie, okrągły stół z biało-fioletowym
   obrusem, wazon, dzbanek, roślina w donicy.
3. Pociągnięcia dwoma przejściami `P.strokes` (położenia stałe, `boil: 0`):
   `P.strokes(c, b, { cell: 11, len: 20, width: 7, angle, seed: 12, t, boil: 0, outline: 0, palette: stable(palette), mask: (x, y) => !fine(x, y) })`
   i drugie z `cell: 6, len: 11, width: 4.5, seed: 13, mask: fine` (okno i obrazek).
4. `palette(x, y, col, r)` wybiera strefę po położeniu; białe ramy okna wykrywaj kolorem `col > (240,236,225)`
   i zwracaj biel (inaczej zamalują się kolorem ściany); maki zwracają `null` (zostaje kolor podkładu).
5. `stable(pal)`: opakowanie, które na każdą komórkę zużywa dokładnie jedną liczbę losową i nigdy nie zwraca `null`
   (`const stable = (pal) => (x, y, col, r) => { const u = r(), rr = U.rng((u * 4294967296) >>> 0); return pal(x, y, col, rr) || P.jitter(col, rr, 24); }`).
6. Postacie do `impChars` (`getContext('2d', { willReadFrequently: true })`): `RIG.drawCat(lg, K, catPal)`,
   `RIG.drawGirl(lg, G, { ...girlPal, mode: 'fill' })`, potem własna pętla drobnych pociągnięć (`cell 7, len 13`),
   w której liczba losowa każdej komórki to `U.hash(i, j)` – niezależnie od sąsiednich komórek. Na koniec oczy
   i usta.
7. W palecie postaci ustaw `line` na złoty kolor włosów (`drawGirl` rysuje `pal.line` przy lokach i powiece nawet
   przy `lw: 0`; domyślny granat zostawia czarne smugi przy twarzy); u kota ustaw `line` i `whisker`.
8. Plamy słońca i błyski na sierści kota na wierzchu; para `P.steam(c, t, G.cup.x, G.cup.y - 8, { h: 60, n: 2, … })`.

## Co się rusza
- Plamy słońca migają nieregularnie: siła `0.5+0.5·sin(t·sp+ph)·sin(t·sp·0.53+2ph)` obcięta `clamp`, częstotliwość
  5–11, dryf ±44 px (po poprawce); kreski w plamie zmieniają ziarno 8 razy na sekundę; tryb `source-over`, α 0,95.
- Na ścianie w słońcu 60 ukośnych jasnych kresek miga z ziarnem zmienianym 6 razy na sekundę.
- Maki kołyszą się (dół łodygi stoi), głowa `sin(t·3.2+ph+x·.02)·(6+r·.6)`, po poprawce amplituda od 10; pociągnięcia
  kwiatów za oknem obracają się z wiatrem ±0,22 rad. Chmury płyną 45 px/s. Zasłony i roślina (`sin(t·1.9)·8`)
  się kołyszą.
- Kot: błysk sierści – 60 punktów, `isPointInPath` tylko na lewej (oświetlonej) połowie ciała i głowy, jasność
  `sin(t·7+h·30)`; ogon ×2,2, oddech ×3, odwraca głowę (`look`). Kapelusz, niebieska wstążka i szarfa powiewają.
- Odcinek w filmie źródłowym: 3 ósemki (0,70 s).
- Dowód: przy ziarnie pociągnięć zmienianym 8 razy na sekundę średnia różnica klatek w odcinku wynosiła 4,14
  (szczyt 20,5) – to miganie; po ustaleniu położeń 0,57 (szczyt 1,9), oryginał 0,77.

## Przejście-podpis (wejście w ten styl)
- `dabs`, 0,28 s: 2600 eliptycznych pociągnięć (długość 34–80, szerokość 10–20, kąt −0,9…−0,4 rad) w przypadkowej
  kolejności odsłania nowy obraz (`ease.out` w postępie 0–0,7, każde pociągnięcie rośnie przez 0,12); na wierzchu
  260 pływających jasnych plam w barwach `#f6e27a #f2a7c3 #b9d9f2 #c6e8a8 #ffffff` (α wg `sin(πp)`); ostatnie 30%
  to przenikanie do czystego obrazu.

## Wydajność
- 65–76 ms na klatkę (mediana 69 ms): dwa pełnoekranowe przejścia `P.strokes` + jedno dla postaci. Własna pętla dla
  postaci zbiła czas z 115 do 72 ms.
- W przejściu do `09_postimp` oba style rysują się naraz: ~69 + 110 ms, ponad 150 ms, ale tylko przez kilkanaście
  klatek przejścia.
- Podkład co klatkę od nowa (ruchome elementy w podkładzie); `P.scratch` dla `impBase` i `impChars`.

## Pułapki
- Ziarno pociągnięć zmieniane 8 razy na sekundę na całym ekranie to miganie, nie życie. Położenia stałe (`boil: 0`),
  życie dają ruchy lokalne.
- Samo stałe ziarno nie wystarczy: `P.strokes` bierze liczby losowe z jednego strumienia, a `palette`, które zwraca
  `null`, zużywa 3 liczby więcej na `jitter`. Czy zwróci `null`, zależy od koloru podkładu, więc gdy mak się zakołysze,
  wszystkie dalsze komórki się przetasowują. Stąd `stable(palette)`.
- `alphaMask` dla postaci: gdy ręka z kubkiem się rusza, zmienia się zbiór pominiętych komórek i cała warstwa się
  przetasowuje. Stąd własna pętla z `U.hash(i, j)`.
- Jedno grube przejście zamazuje domy i kobietę z parasolką za oknem, a obrazek na ścianie zamienia w ukośną smugę.
  Dwa przejścia i poziome fale na obrazku.
- Plamy słońca w trybie `screen` α 0,75 na różowym tle prawie znikają; `source-over` α 0,95.
- Domyślny granatowy `pal.line` zostawia czarne smugi przy twarzy.

## Kontrola
- Czy nic nie ma konturu, a obraz to krótkie pociągnięcia z prześwitami jasnego gruntu?
- Czy w każdej strefie jest kilka barw z jej palety, a nie jedna barwa z szumem?
- Czy pociągnięcia stoją w miejscu między klatkami (brak migania), a ruch robią plamy słońca, kwiaty i postacie?
- Czy białe ramy okna zostały białe, a za oknem widać domy i postacie?
- Czy twarz ma czytelne oczy i usta mimo pociągnięć?

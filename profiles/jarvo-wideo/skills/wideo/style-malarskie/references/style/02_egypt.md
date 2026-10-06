# Egipskie malowidło grobowe (`02_egypt`)

Malowidło ze ściany grobowca z ok. 1350 r. p.n.e.: płaskie kolory bez perspektywy, cienki ciemnobrązowy kontur,
ludzie w kanonie (twarz z profilu, oko en face, oba ramiona od przodu), kolumny hieroglifów i barwne bordiury z bloków.
Poznasz go po ręcznie rysowanych hieroglifach, czterokolorowych ramach i promieniach Atona zakończonych dłońmi.
Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: łokieć ręki z naczyniem zbyt sztywny
(przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 02_egypt --czasy 0.45,0.7,0.9 --arkusz out/wideo/wzor-02_egypt.jpg`; kod
`$HUASHU/scripts/engine/scenes/02_egypt.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Muzeum, wystawa, lekcja historii starożytnej: film 30–60 s z lektorem, hieroglify jako ozdobne pasy.
- Biuro podróży (Egipt, rejs po Nilu): spot 15 s, 16:9 i 9:16.
- Marka kosmetyczna albo jubilerska (kohl, złoto, lapis): reklama 10–15 s.
- Rozdział „starożytność” w filmie o historii branży (pierwsze przepisy na piwo, pierwsze kosmetyki): 3–6 s.

## Nie do
- Głębia, perspektywa, światło: `06_renaissance` albo `24_hopper`.
- Polski tekst „hieroglifami”: znaki to ornament, nie pismo; tekst składaj zwykłym krojem obok.
- Szybka akcja i ruch kamery (styl jest płaski i ozdobny): `13_pop` albo `27_kirby`.

## Cechy stylu (sprawdzalne)
- Bez renderera pędzla i bez wrzącej linii: czysta linia 2,2–2,8 px `#2a1810`. Epokę robi kanon postaci, paleta
  i gęstość ornamentu.
- Hieroglify: 24 funkcje znaków (anch, dysk słońca, chleb, trzcina, sowa, sokół, czapla, żmija rogata, oko Horusa,
  kartusz, skarabeusz, siedzący człowiek, noga, ramię, kosz, dom, trzy kreski, pióro, dżed, szen, dzban, lotos, nfr,
  usta, woda). Każdy w ramce ~50 px, 10–20 kresek, linia 3,1 (po skalowaniu ~3 px), końce `round`, z własnymi
  kolorami do wyboru.
- Ramy: bloki czerwony `#b8322a`, niebieski `#2a58a8`, żółty `#e2b13a`, zielony `#2e8a55`, przerwy kremowe `#f2ead6`,
  czarne spoiny `#231a14`.
- Powierzchnia: plamista warstwa `eg_surface` w `multiply` na całym obrazie, ziarno i 6 włoskowatych pęknięć, które
  przechodzą też przez postacie (stara ściana).
- Postać w kanonie: profil z okiem en face (biały migdał, źrenica r 4,2 przy górnej powiece, kreska kohl 3,2 px
  przedłużona 18 px w tył, długa brew); oba ramiona od przodu (trapez x 1270–1452, szerszy u góry). Biały len
  półprzezroczysty: najpierw skóra, potem biel α 0,9; 27 cienkich fałd wachlarzem od talii (`rgba(120,96,70,.5)`
  1,3 px), na piersi pionowe fałdy co 9 px. Szeroki kołnierz z 5 półelips (niebieski, czerwony, zielony, złoty,
  niebieski; rx 50→88, ry 24→55) i 18 kropli na zmianę czerwonych i niebieskich. Peruka z 15 pionowych warkoczy
  (11,5 px ciemne złoto + 8,5 px złoto + ukośne nacięcia co 8 px w jodełkę, końce nierówne). Złota opaska, kolczyki,
  bransolety (złoto 8 px + niebieski pasek 2,5 px), kielich w kształcie lotosu.
- Kot jako Bastet: siedząca sylwetka z wyprostowaną piersią i okrągłym zadem, przednie łapy wewnątrz sylwetki (jedna
  biała płaszczyzna od piersi do łap, rozdzielona dwiema liniami i liniami palców), wysokie spiczaste uszy, oko
  en face (żółte `#e8cf4a`, pionowa źrenica, czarna kreska), biały pyszczek, złoty kolczyk, obroża z wisiorem oka
  Horusa; pręgi: 9 na grzbiecie, 4 na udzie, 5 na głowie, ogon z pręgą co 3 punkty i białym końcem.
- Paleta: ściana `#eadcb8`, ciemne plamy `#d8c597`; złoto `#e0ab38`, ciemne `#a8741c`, jasne `#f3d27a`; pas granatowy
  `#1c2236`; czerwona linia kolumn `#9a2b22`; dysk Atona `#c8372b`, promienie `#c23a2a`, dłonie `#b4452c`; skóra
  `#e6b282`; kot `#e08a3c`, pręgi `#b45a1c`, biel `#f6efe0`; skarabeusz lapis `#2c56b0` + turkus `#3fa6a0`.
- Napisy (plakietka roku z filmu źródłowego): `IMFellEnglish-400` 100 px `#6b2318`, podpis `EBGaramond-400` 34 px;
  oba mają polskie znaki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 02_egypt`; `P` = `PAINT`
   (`/_lib/huashu/lib/paint.js`), `RIG` (`lib/rig.js`), `U` (`lib/util.js`).
2. Warstwa statyczna `eg_static` (cache raz): tynk → kolumny hieroglifów → okno (gzyms, rama z bloków, białe tło,
   dysk Atona, ureusz) → 3 dzbany → stół ofiarny z darami → złote krzesło → niebieska misa → linia ziemi i fryzy
   u dołu → pas granatowy → bordiury z bloków u góry, z lewej i z prawej.
3. Hieroglify rozkładaj raz przy starcie modułu i zapisz pozycje: ziarno `U.rng(1350)`, kolumna po kolumnie w dół,
   skala = szerokość kolumny/78 × (1,0–1,14), odstęp 6–11 px. Reguły: ten sam znak nie obok siebie, w jednej
   kolumnie ≤3 razy, skarabeusz i woda z wagą −60%, co najmniej 6 znaków wody (te rysujesz co klatkę, poza cache).
   Kolumny we wzorze: lewe 3 x=78..306 / y=66..566, środkowe 4 x=852..1172 / y=66..452, prawe 4 x=1560..1866 /
   y=252..882, jedna przy kocie x=298..366 / y=614..886.
4. Co klatkę (tanio): znaki wody, promienie Atona z dłońmi, dwa długie promienie z anch do kota, skarabeusz z kulą.
5. Postacie: nie `RIG.drawGirl` ani `RIG.drawCat`; bierzesz tylko kotwice i choreografię, rysujesz w kanonie.
   Dziewczyna `RIG.girl({dy:-25})` (stopy na linii y=900). Ręka od przedniego barku (1282, 476):
   `RIG.ik2(sh, hand, 140, 160, -1)`, dłoń pod stopką kielicha, łokieć opada przed pierś. Kot `RIG.cat({dy:-5})`
   (headC, tailPts, blink, breathe), ciało własne; obroża przycięta do sumy ciało∪głowa (`Path2D.addPath`).
6. Powierzchnia: `eg_surface` w `multiply` + `P.grain` + 6 pęknięć narysowanych w tej warstwie.
7. `init()` grzeje cache przy starcie silnika (`P.texture` pierwszy raz trwa ~170 ms).

## Co się rusza
- Picie w pętli (najwięcej ruchu): do lt 0,35 naczynie idzie do ust według `choreo`, potem co 0,6 s
  `cup = 1 − 0.46·(1−cos 2πu)/2` (opada do 0,54 i wraca). Przy ustach odchylenie głowy
  `sip += 0.3·clamp((cup−0.78)/0.22)·(0.65+0.35·sin 13lt)`, kąt do ~0,2 rad.
- Hieroglify pisane na nowo: co 0,12 s 6 znaków z przetasowanej listy (ziarno 77, ze wszystkich kolumn). Zetrzyj znak
  wycinkiem tekstury ściany (`drawImage`), potem rysuj kreska po kresce `setLineDash([p·95, 999])` (każda podścieżka
  zaczyna dash od nowa, więc wygląda jak pisanie), wypełnienia dopiero przy `p>0.55`. Kolor przechodzi z jasnego złota
  `#f6c846` do właściwego, poświata `shadowBlur` 10 px, 0,36 s na znak, ~18 znaków naraz.
- Puls Atona: okres 0,45 s; długość promieni ±9% falą po wachlarzu (faza `−0.55k`), linia 2,2→3,8, dłonie skala 0,9–1,2,
  rozwarcie palców 0,03–0,45; złota poświata i jasny pierścień poza dyskiem, dysk rysowany na wierzchu (zostaje
  czerwony). Dłonie przytnij do okna (x 428–752, y ≤512).
- Dłonie Atona otwierają się: `open=0.5+0.5·sin(2π·lt/0.4+k·0.9)`, rozwarcie `0.1+0.24·open`; 13 dłoni w oknie
  i 2 poza nim; końce promieni drżą ±3 px (`x+=3·sin(7t+1.3k)`, `y+=2·cos(6t+k)`).
- Skarabeusz pcha kulę: `x(lt)=800+642·(lt−0.394)` (10,7 px na klatkę), modulo 2160; obrót kuli = x środka / promień;
  nogi dwie pozy `floor(lt*15)%2` (co 4 klatki przy 60 fps); całość ×1,22, kula r=23×1,22.
- Znaki wody: zygzak, faza `floor(lt·12)·0.5`, 12 fps, 4 kroki w cyklu (0,33 s) – jak rysowane klatka po klatce.
- Kot: ogon `tail·2.1 + 0.25·sin 9.5t`; uszy drgają na przemian co ~0,38 s przez 0,1 s (obrót 0,32–0,38 rad wokół
  środka nasady); mrugnięcie t≈2,18–2,30; oddech.
- Odcinek w filmie źródłowym: 4 ósemki (0,94 s).
- Dowód: średnia różnica klatek 480×270 (klatki 112–140) wzrosła z 0,32 do 0,84 (oryginał 0,90); największy udział
  ma pętla picia.

## Przejście-podpis (wejście w ten styl)
- `tiles`, 0,42 s (`TRANSITIONS.tiles` z `$HUASHU/scripts/engine/transitions.js`): nowy obraz pocięty na bloki
  240×180 (45% z nich dzielonych na 4 bloki 120×90) wpada od lewej do prawej (start = pozycja x·0,62 + los 0,3).
  Każdy blok przylatuje z przesunięcia dx ±30, dy −30…−80 px, obrót ±0,06 rad, skala 1,08→1, `ease.outBack` (lekkie
  odbicie), cień `shadowBlur` 18 w locie. W indeksie źródła opisane jako „pionowe pasy gobelinu opadające z odbiciem”;
  kod układa bloki muru.

## Wydajność
- Ciepła klatka: maks. 20,7 ms, średnio 10,5 ms (1920×1080); po dodaniu ruchu maks. 21,7 ms.
- Cache: `eg_static`, `eg_surface`; rozkład hieroglifów liczony raz. Bez grzania w `init()` pierwsza klatka przejścia
  stoi ~170 ms.

## Pułapki
- Bez reguł rozkładu ściana jest pełna skarabeuszy jak naklejek.
- Warkocze z koralików wyglądają jak „złoty kawior”; rób długie pasma z ukośnymi nacięciami.
- Przednie łapy kota jako dwa osobne białe słupki wyglądają jak kręgle; łapy trzymaj w sylwetce.
- Obroża przycięta tylko do głowy wystaje za szyję; przytnij do sumy ciała i głowy.
- Domyślna ręka `RIG` (dłoń z boku kubka, bark w środku tułowia) wyrzuca łokieć daleko; przesuń bark do przodu
  i podeprzyj kielich od dołu.
- Kot w pełnej skali wchodzi uszami w ramę okna (y 530–560): zmniejsz do 0,85 wokół stóp (540, 898), uszy na y≈585;
  promienie do kota przeliczaj tą samą transformacją (`catPt()`). Części wystające poza szkielet sprawdzaj osobno.
- Puls dysku półprzezroczystym pomarańczem robi z czerwonego dysku pomarańczowy; rób poświatę poza dyskiem.
- Cienkie linie (promienie, znaki wody) prawie nie dają ruchu w różnicy klatek 480×270; widoczny ruch dają większe
  obszary (ręka z głową, całe znaki), cienkie linie to tylko dodatek.
- Kamienie z referencji to resztka przejścia, nie treść sceny.
- Róg z plakietką roku (1500–1890 × 40–210) zostaw pustą ścianą.
- Pomiar ruchu w lt <0,36 s psuje uderzeniowy zoom silnika na takcie; porównuj klatki od lt ≥0,4.

## Kontrola
- Czy twarz jest z profilu z okiem en face, a oba ramiona od przodu?
- Czy linie są czyste (2,2–2,8 px), bez wrzenia i bez faktury pędzla?
- Czy hieroglify są różnorodne (bez sąsiednich powtórzeń, nie same skarabeusze) i część z nich pisze się na nowo?
- Czy dłonie Atona mieszczą się w oknie, a dysk zostaje czerwony?
- Czy uszy kota i inne wystające części mają luz od ramy?

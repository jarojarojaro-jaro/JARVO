# Wycinanki Matisse'a, „Jazz” 1947 (`30_matisse`)

Późny Matisse: kształty wycięte nożyczkami z papieru pomalowanego gwaszem i przypięte do ściany. Czyste, nasycone
kolory, nierówne „cięte” krawędzie, pod każdym kawałkiem cień papieru, morskie wodorosty z zaokrąglonymi palcami,
gwiazdy, Ikar. Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: smugi gwaszu są za mocne
(przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 30_matisse --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-30_matisse.jpg`;
kod `$HUASHU/scripts/engine/scenes/30_matisse.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Marka kreatywna: studio projektowe, kawiarnia, festiwal, księgarnia, zajęcia plastyczne dla dzieci: 10–30 s.
- Logo i plansze tytułowe złożone z wyciętych kształtów: intro 3–6 s.
- Kampania lato/morze, kosmetyki naturalne, moda: Reels 9:16, 10–15 s.
- Animowana zapowiedź wydarzenia kulturalnego: pętla 8–15 s.

## Nie do
- Realistyczny produkt albo twarz: wszystko staje się płaskim wycinkiem. Wybierz `35_shinkai` albo `24_hopper`.
- Kolaż z gazet, taśmy i zdjęć: `style-motion`, karta `kolaz`; naklejki z białą obwódką: karta `naklejki`.
- Grube czarne kontury i rytm do bitu: `31_haring`.

## Cechy stylu (sprawdzalne)
- Kompozycja wzoru: ściana to „Polinezja” – szachownica dwóch błękitów `#1d4fb8 / #4f95dc`, każde pole 240×236 jako
  osobny wycinek; okno to „Ikar” (kobaltowe tło, czarna postać, czerwone serce, żółte gwiazdy); podłoga szmaragdowa
  `#1f9a5a` z czarną listwą; blat to czarny wycinek, krzesło żółty wycinek.
- Krawędź nożyczek `cut(pts)` (w bibliotece `PAINT.cut(pts, seed, step = 18, amp = 2.5)`): punkt co 14–24 px wzdłuż
  obrysu, losowe przesunięcie ±2–2,5 px, punkty łączone prostymi. Każdy własny kształt idzie przez `cut`.
- Wodorost: stożkowa łodyga i 2×lobes naprzemiennych palców-kapsułek z zaokrąglonym końcem. Kąt palca
  `±(1.05−0.55u)`, długość `width·(1−0.45u)`, szerokość `width·(0.34−0.12u)`. Wszystkie części `addPath` do jednej
  `Path2D`, jeden `fill` nonzero = suma kształtów, jeden cień.
- Cień papieru: przesunięcie (5,6), blur 4, `rgba(10,20,40,.3)` – papier przypięty do ściany.
- Smugi gwaszu: 2600 długich smug w cache (60–300 px, szerokość 6–22, pół białych pół czarnych, α .04–.13, nachylenie
  −0.25 rad), całość w `overlay`.
- Paleta (z kodu): kobalt `#1d4fb8`, błękit `#4f95dc`, żółty `#f7d21e`, czerwony `#e2322a`, czarny `#141414`, biały
  `#f7f3e8`, zielony `#1f9a5a`, róż `#ef6f9a`, pomarańcz `#f28a24` / `#c8521a`, skóra `#f3c9a6`, fiolet `#5b3a9a`.
- Postać we wzorze: „Bluzka rumuńska” Matisse'a – biała bluzka z szerokimi rękawami, z przodu kobaltowy haftowany pas
  (czerwone i żółte trójkąciki na przemian), na rękawie czerwono-niebieskie poprzeczne pasy, które obracają się
  z ramieniem (`clip` w `upperArm`), czerwona długa spódnica, czarny pasek, blond włosy z 5 zwiniętych wycinków.
  Twarz tylko z wycinków: czarne migdałowe oczy, czerwony trójkąt ust, różowe kółka policzków.
- Krój plakietki we wzorze: `Caveat-600`; ma polskie znaki.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 30_matisse`. `P` = `PAINT`
   (`paint.js`, `brush.js` z `P.cut`, `render.js` z `P.roughen`).
2. Tło raz do cache (`P.cached('mt_bg', W, H, …)`): szachownica, okno z Ikarem, podłoga, listwa; każdy kształt
   przez `cut`, każdy z cieniem papieru.
3. Wodorosty i gwiazdy jako pojedyncze `Path2D` z cieniem.
4. Postać: `RIG` nie daje listy punktów, więc całą warstwę postaci przesuń pikselami, żeby krawędź wyglądała na
   ciętą ręcznie: stałe pole przesunięć `fbm(0.028x, 0.028y, 2)·9`, osobno dla dx i dy, tylko w prostokącie
   (330,470)-(1600,980); ok. 15 ms. W bibliotece: `P.roughen(warstwa, box, { freq: 0.028, amp: 9, key })`.
5. Na koniec smugi gwaszu z cache (`P.cached('mt_gouache', …)`) w `overlay`.

## Co się rusza
- Ruch główny: picie herbaty; para z filiżanki to dwa białe paski wycinanki.
- Wodorosty kołyszą się jak papier wokół nasady `sin(2.8t+φ)·0.13`, zwinięty brzeg oddycha `scaleX 0.93–1.0`.
- Ikar: 7 nieregularnych żółtych gwiazd obraca się i błyska (skala `.82+.22sin(7t+1.9k)`), czarna postać unosi się
  i opada, czerwone serce bije (`1+.18·max(0,sin 9t)`).
- Dwa białe ptaki machają skrzydłami (scaleY `.55+.45cos 13t`); różowy papierek spada, obracając się (scaleX=cos 6t).
- Różnica klatek 9,3%.

## Przejście-podpis (wejście w ten styl)
- `cutouts`, 0,36 s: od prawej do lewej przejeżdża arkusz kobaltowego papieru szerokości 1100 px (lewa i prawa
  krawędź nierówna jak cięta, z sinusów), cień (14,10) blur 12. Na arkuszu 260 smug gwaszu i przypięte wycinki –
  biały i żółty wodorost (łodyga i 7 palców), żółta i różowa gwiazda 6-ramienna (obraca się z p), czerwone koło – każdy
  z własnym cieniem. Za prawą krawędzią arkusza jest już nowy obraz.

## Wydajność
- Ok. 25 ms na klatkę.
- Cache: tło (`mt_bg`) i smugi gwaszu (`mt_gouache`). Pole przesunięć postaci ok. 15 ms – licz je tylko w prostokącie
  postaci.

## Pułapki
- Wodorost zrobiony jako „pas o zmiennej szerokości wzdłuż kręgosłupa” wychodzi jak gąsienica albo zygzak
  błyskawicy. Rób łodygę i osobne palce-kapsułki w jednej `Path2D`.
- Spadający papierek przeleciał przez twarz. Daj mu tor przy lewej ścianie; ruch poboczny trzymaj z dala od twarzy.
- Czarne cyfry plakietki na kobalcie były nieczytelne. Podłóż pod nie biały wycinek.
- Słabość wzoru: smugi gwaszu są za mocne. Zmniejsz ich α albo liczbę, aż kolor wycinków będzie czysty.

## Kontrola
- Czy każda krawędź jest „cięta” (proste odcinki co 14–24 px z drganiem), bez gładkich krzywych?
- Czy każdy wycinek ma cień papieru (5,6)?
- Czy wodorosty mają zaokrąglone palce, a nie zygzak?
- Czy kolory są czyste i nasycone, a smugi gwaszu ledwo widoczne?
- Czy twarz da się odczytać z samych wycinków?

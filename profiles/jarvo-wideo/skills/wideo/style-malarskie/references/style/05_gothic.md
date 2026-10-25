# Gotycki iluminowany rękopis (`05_gothic`)

Strona iluminowanego rękopisu z ok. 1290 r.: pergamin, płatkowe złoto z tłoczeniem w romby, gotyckie łuki i pinakle,
witraż, łaciński tekst frakturą z czerwonymi inicjałami, drolerie na marginesach (wici, ślimak, mysz, rycerzyk).
Poznasz go po złocie: ma szczotkowaną fakturę i przesuwa się po nim skośny błysk. Jakość wzoru: ★★★ (rozpoznawalny od
razu, gotowy do użycia); słabość wzoru: złote włosy postaci wyglądają jak kaptur (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 05_gothic --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-05_gothic.jpg`; kod
`$HUASHU/scripts/engine/scenes/05_gothic.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Parafia, zabytek, muzeum, festiwal średniowieczny: film 15–45 s.
- Wydawnictwo, księgarnia, biblioteka (zapowiedź książki, cytat na stronie): 10–20 s, 16:9 albo 9:16.
- Marka premium ze złotem (czekolada, miód pitny, jubiler, alkohol): reklama 10–15 s, kartka świąteczna.
- Gra fantasy albo RPG: plansza tytułowa, ekran rozdziału 5–10 s.

## Nie do
- Złoto ornamentalne w nowoczesnym, dekoracyjnym klimacie: `18_klimt` (używa tego samego renderera złota).
- Głębia i realistyczne światło: `06_renaissance`.
- Nowoczesny produkt, aplikacja, dane: `style-motion` albo gramatyki explainera.

## Cechy stylu (sprawdzalne)
- Złoto liczone per piksel: `f = 0.52 + fbm(x·.0035)·0.42 + noise(x·.004, y·.09)·0.5` + światło z lewej góry +
  ziarno ±0,05, kolor interpolowany między goldLo `#9c6a1a`, gold `#d9a63a`, goldHi `#f8de86`. Częstotliwość y
  szczotkowania ≥20× większa niż x: poziome rysy jak w szczotkowanym metalu.
- Tłoczenie w romby: odstęp 46 px, dwie rodziny skośnych linii (x+y i x−y stałe). Każda linia dwa razy: ciemna i jasna
  przesunięta o 1,2 px (wyryte w złocie). W środku rombu 4 kropki: lewa góra jasna, prawa dół ciemna. Co 118×125 px
  bardzo blada spoina arkusza złota.
- Postać: aureola (środek headC + (16, −22), r=114, czerwony okrąg z 36 tłoczonymi punktami), faliste złote włosy,
  czerwona szata z cienkimi złotymi pionowymi paskami co 20 px i złotym brzegiem, niebieski płaszcz ze złotą lamówką,
  złoty kielich z migającą gwiazdką na brzegu.
- Kot jak z marginesów rękopisu, z „ludzką twarzą”: kremowa owalna twarz, migdałowe oczy ze źrenicami w prawym kąciku
  (zerka z ukosa na postać), gruba górna powieka, uniesione brwi, opuszczone kąciki ust, rumieńce; jedna łapa uniesiona,
  trzyma mysz za ogon.
- Tekst łaciński `UnifrakturMaguntia` 44 px; pierwsze słowa zdań (Cattus, Nemo, Mus) cynobrem – średniowieczna rubryka.
  W nakładce `huashu_pl.js` `UnifrakturMaguntia` → `IM Fell English` (fraktura nie ma polskich znaków). Plakietka
  roku z filmu źródłowego: `LibreBaskerville-700` 100 px `#b3222b`, podpis `IMFellEnglish-400` 36 px (oba z polskimi
  znakami).
- Paleta (z kodu sceny): pergamin `#ecdfc0`, ciemny `#c9ae80`; złoto `#9c6a1a` / `#d9a63a` / `#f8de86`; czerwień
  `#c3262e`, ciemna `#7e1318`; błękit `#24449e`, ciemny `#142a6a`; róż `#e7a3aa`; zieleń `#55a03c`, ciemna `#2f6e26`;
  biel `#f8f2e2`; drewno `#8a5a2c` / `#5a3818`; skóra `#f5dcc2`; włosy `#e9b746` / `#9a6618`.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 05_gothic`; `P` = `PAINT`, `RIG`, `U`.
2. Warstwa statyczna `goth_static` (cache w `init()`): pergamin
   `P.texture('goth_parch', C.parch, { scale: 0.0028, amt: 20, grain: 9, dark: C.parchDk, seed: 3 })` → złoto
   (`goth_goldTex`) → romby → szczyt, pinakle, kolumny boczne → ostrołukowe okno z witrażem → stół i tron →
   kolumna tekstu łacińskiego → rycerzyk na marginesie.
3. Maska złota `goth_mask`: per piksel warstwy statycznej „złotość”
   `clamp((r-b-70)/50)·clamp((g-b-30)/40)·clamp((r-140)/40)` jako alfa. Pergamin (236, 223, 194) ma r−b tylko 42 i odpada;
   różowe pasy mają wysokie b i też odpadają. Nie rysujesz drugi raz złotych kształtów: wszystko, co złote (tło,
   inicjały, kule, zwieńczenia), dostaje błysk samo.
4. Błysk: na płótnie roboczym (`P.scratch('gothSweep')`, pas 920 px szerokości) gradient liniowy o nachyleniu K=0,45
   (kierunek „/”), `destination-in` z maską, potem `lighter` α 0,85 na obraz. Pozycja jednostajna
   `x = lerp(150,1650,(lt-0.08)/1.15)`.
5. Co klatkę, w tej kolejności: migotanie witraża → błysk → czteroramienne gwiazdki tam, gdzie przechodzi błysk
   (aureola i 11 stałych punktów, gdy `|u − sweepX| < 70`) → wici → ślimak → przebiegająca mysz → kot → postać →
   ziarno `P.grain('goth', 0.05, [90, 60, 20], 0.16)`.
6. Postać: `RIG.girl({ cup, sip, hair: 'long', breathe })` i jej `Path2D` rysowane ręcznie w kolejności: aureola →
   faliste długie włosy → czerwona szata → niebieski płaszcz (kotwice nape/back) → głowa → złoty kielich. Nie
   `RIG.drawGirl`: zawsze rysuje kubek z uchem, a płaszcza i aureoli nie da się wstawić między jego warstwy.
7. Kot: `RIG.cat`, tylko `legs[0]`; drugą przednią łapę uniesioną rysuj `RIG.limb(sh, pw, 32, 26)`; ciało
   `RIG.smooth(K.bodyPts)`.
8. Para nad kielichem cienką linią tuszu: `P.steam(c, t, cup.x, cup.y - 12, { h: 64, n: 3, … })`.

## Co się rusza
- Skośny błysk po złocie, jednostajnie: lt 0,3 przy oknie, lt 0,9 przez postać; za nim błyski gwiazdek.
- Wici: dwie łodygi po ~120 punktów, każdy punkt wychyla się o `sin(t·2.1+i·.09)·2.5` (po poprawce amplituda ×2).
  Co 3–5 punktów trójlistny liść bluszczu (na zmianę niebieski, czerwony, złoty; skala 1,05–1,45) albo złota kula
  z 3 wąsami; liście kołyszą się wokół zaczepienia `sin(t·3.1+k·1.7)·0.42`.
- Witraż: 40 losowych punktów; gdy `sin(t·5+h·40) > 0.6`, zapala się biała radialna poświata.
- Mysz w łapie kota jak wahadło `0.32·sin(t·5.5)`, nóżki fikają. Ślimak pełznie w lewo 62 px/s, czułki się chwieją.
  Druga mysz pod kolumną tekstu przebiega 360 px w lt 0,12–1,17, nogi 40 rad/s.
- Picie według wspólnej choreografii.
- Odcinek w filmie źródłowym: 4 ósemki (0,94 s); ruchy muszą być widoczne w oknie lt 0,25–1,4 (z przejściem).
- Dowód: średnia różnica klatek w odcinku wzrosła z 1,10 do 1,32 (oryginał 1,64) po podwojeniu ruchu wici, 40 punktach
  witraża i mocniejszym błysku.

## Przejście-podpis (wejście w ten styl)
- `pageTurn`, 0,32 s: pergaminowa strona zawija się od prawej do lewej, pas zawinięcia 260 px. Rewers to pergamin
  `#e9dcc0` z lustrzanym odbiciem starego obrazu α 0,18 i cieniowaniem walca; cień 90 px na nowej stronie;
  `ease.inOut`.

## Wydajność
- 11–22 ms na klatkę (mediana 12 ms).
- Warstwa statyczna, tekstura złota i maska złota budowane raz w `init()`; co klatkę tylko ruchome drobiazgi
  i jeden pas błysku.

## Pułapki
- Błysk z ruchem `inOut` już przy 0,9 s wychodzi poza złoto i nie trafia w postać. Ruch jednostajny.
- Liście w skali 0,85 są za małe i za rzadkie; 1,05–1,45 daje gęstość z oryginału.
- Fraktura 50 px wypycha „cum poculo suo” poza prawy brzeg; po podmianie na `IM Fell English` sprawdź szerokość
  wiersza jeszcze raz.
- Złote włosy czytają się jak kaptur (słabość wzoru); sprawdzaj kształt włosów na stopklatce, zanim pójdziesz dalej.
- Pomiar ruchu z bazą lt=0 psuje uderzeniowy zoom pierwszych 20 klatek (skala 1,03); bazuj od lt ≥0,35.

## Kontrola
- Czy złoto ma poziome szczotkowanie i wyryte romby (ciemna + jasna linia)?
- Czy błysk pada tylko na złoto (maska), a nie na pergamin i różowe pasy?
- Czy błysk przechodzi przez postać w czasie odcinka?
- Czy polski tekst jest złożony krojem z polskimi znakami (`IM Fell English`), z czerwonymi inicjałami?
- Czy na marginesach coś żyje (wici, ślimak, mysz)?

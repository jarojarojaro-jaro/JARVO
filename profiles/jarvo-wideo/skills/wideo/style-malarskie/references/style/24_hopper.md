# Hopper, realizm amerykański i twarde światło (1942) (`24_hopper`)

Pokój z płaskimi plamami słońca o ostrych krawędziach: chłodnozielona wersja w cieniu i ciepła żółta w świetle,
przełączane wycinaniem po kształcie plamy. Plama powoli przesuwa się po ścianie i przez twarz, a w świetle widać cień
postaci na ścianie. Samotność, poranek, cisza („Poranne słońce”, „Nocne marki”, „Wczesny niedzielny poranek”).
Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: kot przez cały czas siedzi w cieniu
(przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 24_hopper --czasy 0.1,0.6,1.1 --arkusz out/wideo/wzor-24_hopper.jpg`;
kod `$HUASHU/scripts/engine/scenes/24_hopper.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Nieruchomości i architektura: mieszkanie w słońcu, okna, rolety, hotel: 5–20 s.
- Spokojny produkt domowy: kawa, herbata, lampa, fotel, poranek: 10–15 s.
- Narracja „z cienia do światła”: krawędź światła przechodzi przez twarz (problem → rozwiązanie): 3–6 s.
- Kampania o samotności i zdrowiu psychicznym; kawiarnia, bar nocą: 10–20 s.

## Nie do
- Światło świec, barokowy światłocień: `32_rembrandt`; światło w anime (smugi, flary): `35_shinkai`.
- Szybki montaż i dynamiczne cięcia: ruch główny to wolne przesuwanie światła (ok. 95 px w 1,2 s).
- Ważna postać w cieniu przez cały film (słabość wzoru): daj jej plamę światła, np. z tylnego okna.

## Cechy stylu (sprawdzalne)
- Dwie wersje tego samego pokoju (`room(g, K)` z dwiema paletami, w dwóch cache): cień `SH` i światło `LT`.
- Paleta: cień: ściana `#5d8679`, lamperia `#4b6d63`, podłoga `#5b3d2b`; światło: ściana `#efcf8f`, lamperia
  `#d8ad68`, podłoga `#c98b52`; sukienka cień `#7a2c2a` / światło `#cc4a3c`; złote włosy cień `#a8893f` / światło
  `#f3d67e`; cegła `#b4553a`.
- Plamy światła, `dx = 30 − 95·easeInOut(lt/1.25)`:
  - na ścianie `WP`: (1420+dx, 250) → (1920, 470) → (1920, 730) → (1420+dx, 730);
  - na podłodze `FP`: dokładnie pod nią, rozchodzi się w prawo w dół;
  - pas światła na postaciach `OP`: lewa krawędź od (1345+dx, 0) do (1185+dx, 1080); w tym czasie krawędź przechodzi
    przez twarz, od pół twarzy w cieniu do całej w świetle.
- Cień szprosów: pion 24 px + skos równoległy do górnej krawędzi plamy.
- Cień postaci na ścianie: sylwetka przesunięta o (+150, +18) na osobnym płótnie, `source-in` z wersją cienia, potem
  narysowana z powrotem w plamie. W świetle widać cień, który pije razem z postacią.
- Faktura: pociągnięcia jak w oleju, pionowo wydłużony fbm (`x·0.06, y·0.006`) plus trochę skośnego, liczony
  w 1/4 rozdzielczości i powiększony, `soft-light` α 0.2.
- Za oknem budynek z czerwonej cegły (hołd dla „Wczesnego niedzielnego poranka”): w każdym oknie twardy cień 10 px
  z prawej, rolety na różnych wysokościach (0.25–0.7), słupek fryzjerski.
- Postać: długie rozpuszczone włosy (`hair:'long'`) z niebieską opaską, czerwona sukienka. Kot z białą piersią jako
  gładka elipsa, białe futro w cieniu `#dcd6c8`.
- Napisy w filmie pokazowym: `LibreBaskerville-700 / 400` (mają polskie znaki).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 24_hopper`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.fbm`, `PAINT.cached`, `PAINT.scratch`, `PAINT.particles`,
   `PAINT.steam`, `PAINT.choreo`), `render.js` (`PAINT.litClip`), `rig.js` (`RIG.drawCup`).
2. Narysuj pokój dwa razy tą samą funkcją, z dwiema paletami, do dwóch cache (cień, światło).
3. Co klatkę: wersja cienia na cały kadr → `PAINT.litClip(c, [WP, FP], c => { … })`: w środku wersja światła, potem
   szprosy i cień postaci, które odsłaniają z powrotem wersję cienia.
4. Za oknem: słupek fryzjerski, sznurek rolety.
5. Meble i postacie najpierw w kolorach cienia, potem `PAINT.litClip(c, [OP], c => { te same funkcje w kolorach
   światła })`. Krawędź światła jest zawsze twarda i przesuwa się całością.
6. Pył w pasie światła, para, na końcu faktura `soft-light`.

## Co się rusza
- Ruch główny: plama światła powoli przesuwa się w lewo (ok. 95 px w 1,2 s), krawędź przechodzi przez twarz.
- Słupek fryzjerski za oknem: czerwono-niebieskie skośne paski jadą w górę 60 px/s.
- Sznurek rolety kołysze się `sin(4.2lt)·0.07 rad`.
- 26 drobin pyłu w pasie światła, widocznych tylko po jasnej stronie krawędzi.
- Picie z kubka; cień na ścianie pije razem z postacią; para.

## Przejście-podpis (wejście w ten styl)
- `sunShaft`, 0,34 s (`TRANSITIONS.sunShaft`): stary obraz tonie w cieniu (`multiply` chłodną zielenią
  `rgba(70,120,110, 0.7·min(1,2p))`); skośny blok światła (skos 260 px) prawą krawędzią przechodzi przez cały ekran.
  W bloku nowy obraz + ciepłe światło `screen` (0.45 → 0, wycofuje się w p 0.6–1) + jadący z nim skośny cień szprosa;
  z przodu jasna krawędź. Wyrasta ze słońca wpadającego przez okno.

## Wydajność
- Mediana 13 ms na klatkę, pierwsza klatka 54 ms. Przejście `sunShaft` 76 ms na klatkę.
- Cache: dwie wersje tła i faktura (1/4 rozdzielczości).

## Pułapki
- Faktura z poziomego fbm z α 0.35 robi ze ściany marmur w fale. Ściana Hoppera jest płaska: pociągnięcia ledwo
  widoczne.
- Postać z kokiem i w długiej czerwonej sukni czytała się jak dorosła kobieta („nie widać 17 lat”). Długie
  rozpuszczone włosy i opaska odmładzają.
- Białe futro kota `#c4bdac` w cieniu czytało się jak szary kot: `#dcd6c8`.
- Przy hurtowej edycji kodu skryptem nie wstawiaj komentarza w środek linii: zakomentujesz resztę tej linii.

## Kontrola
- Czy krawędzie światła są ostre, a cała plama przesuwa się płynnie?
- Czy krawędź światła przechodzi przez twarz?
- Czy cień postaci na ścianie rusza się razem z nią?
- Czy ściana jest płaska, a faktura ledwo widoczna?
- Dowód z wzoru: różnica klatek 6,0%.

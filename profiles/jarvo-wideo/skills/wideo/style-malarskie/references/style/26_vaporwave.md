# Vaporwave / cyber-neon (`26_vaporwave`)

Estetyka z 2011 roku: nocny fiolet, neonowe rurki w dwóch kolorach (magenta i cyjan), perspektywiczna siatka podłogi,
zachodzące słońce pocięte poziomymi szczelinami, okienko Windows 95 i marmurowe popiersie. Na wierzchu leży taśma VHS:
rozjechane kanały RGB, pas zakłóceń, linie skanowania, napis „PLAY” i kod czasu. Poznasz go po tym, że cały kadr
lekko drga jak odtwarzany z kasety. Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru:
świecą też styki części postaci (talia, ramię przy tułowiu) (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 26_vaporwave --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-26_vaporwave.jpg`;
kod `$HUASHU/scripts/engine/scenes/26_vaporwave.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Reels, TikTok, Shorts 9:16, 10–20 s: zapowiedź imprezy klubowej, koncertu synthwave/retro, premiery singla
  albo playlisty.
- Retro-gaming, sklep z elektroniką vintage, bar z automatami: intro 3–5 s i przerywniki między ujęciami.
- Kampania grająca nostalgią lat 80. i 90. (kaseta, Windows 95) dla widza 25–40 lat: spot 15 s.
- Animowana okładka podcastu albo singla: pętla 8–15 s.

## Nie do
- Finanse, medycyna, urząd: szum VHS wygląda jak awaria. Spokojniej: `24_hopper`, `35_shinkai` albo
  `style-motion` (płaski wektor).
- Sam neon bez taśmy i bez postaci (słońce, siatka, chrom): `style-motion`, karta `synthwave` – lżej i szybciej.
- Długi tekst do czytania: rozjazd RGB i pas zakłóceń psują czytelność. Napisy kładź poza efektem VHS.

## Cechy stylu (sprawdzalne)
- Ściana: pionowy gradient `#0d0322 → #4a0f6a`, w oknie radialne światło magenta, przy szyldzie radialne cyjanowe.
  U dołu ściany cyjanowy pasek LED.
- Neon to ta sama ścieżka obrysowana dwa razy: najpierw gruba poświata (`shadowBlur`), potem prawie biały rdzeń
  2–3 px. Funkcja `glowLine(c, col, w, blur)`, w bibliotece `PAINT.glowStroke`.
- Słońce w oknie: pionowy gradient żółty → pomarańczowy → magenta, 7 poziomych szczelin wyciętych
  `destination-out`, szczelina rośnie z głębokością (`2 + q²·16`), całe słońce jedzie w górę 0,9/s. Na horyzoncie
  góry z linii (poświata magenta), niżej cyjanowa siatka jadąca do widza, po bokach kołyszące się sylwetki palm.
- Podłoga: siatka magenta, punkt zbiegu (960,600), linie poziome `y = 600 + 520/d`, `d = k + 1 − phase`
  (`phase = 1.3t mod 1`); bliższe linie grubsze.
- Szyld z neonowych rurek rysowany łamanymi, nie fontem: każdy znak to 1–3 kreski w jednostkach (u,v).
- Okienko Win95 „TEA.EXE”: szare, pasek tytułu w granatowym gradiencie, pasek postępu `3 + 14lt` kratek, procent
  `18 + 70lt`. Na stole marmurowe popiersie: profil z 22 punktów, gradient fioletowo-szary, żyłki, różowy kontur
  światła, okulary przeciwsłoneczne.
- Postać: ciemne płaskie wypełnienie i kontur-poświata „od okna różowy, od tyłu cyjanowy” (te same ścieżki
  obrysowane dwa razy, każda przycięta do swojej połowy kadru). Ubranie w innym kolorze niż skóra: we wzorze
  lawendowy płaszcz `#8f7cf6`, biały trójkątny kołnierz, cyjanowa linia zamka; różowy sweter, cyjanowa plisowana
  spódnica, blond włosy z różową gumką.
- Paleta: magenta `#ff4fd8`, gorący róż `#ff2f8f`, cyjan `#3ff6ff`, głęboki fiolet `#12052a / #2a0b4a`, słoneczny
  żółty `#ffd84a`, pomarańcz `#ff8a3a`.
- Kroje: szyld tekstowy `Righteous-400`, okienko `Poppins-600/700`, OSD `PressStart2P-400`, liczba na plakietce
  `Exo2-800i`. Wszystkie mają polskie znaki (sprawdzone w plikach `lib/fonts`), nie są podmieniane.

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 26_vaporwave`. Biblioteki z
   `/_lib/huashu/lib/` (`paint.js`, `render.js`, `post.js`, `rig.js`), `P` = `PAINT`.
2. Cały obraz rysuj najpierw do bufora poza ekranem `S` (`P.scratch`), dopiero potem przepuść go przez VHS do `c`.
   Plakietkę, licznik i napisy rysuj na wierzchu, już po VHS, żeby nie dostały aberracji.
3. Warstwa statyczna raz do cache: `P.cached('vw_bg', W, H, …)` – ściana z gradientem i światłami, neonowa rama
   okna, cokół popiersia.
4. Okno: słońce ze szczelinami (wycinasz w buforze, nie na płótnie kadru), góry, cyjanowa siatka, palmy.
5. Podłoga: siatka magenta według wzorów wyżej.
6. Szyld: znaki z łamanych, `glowLine(c, col, 9, 30)` + biały rdzeń 3 px. Zgaszony znak = ciemnofioletowa rurka
   `rgba(120,60,120,.6)`.
7. Okienko TEA.EXE i popiersie. Tekst okienka po polsku (np. „Parzę herbatę… 47%”).
8. Postać: `RIG.girl` + płaskie ciemne wypełnienie, potem dwa obrysy-poświaty z `clip` do lewej i prawej połowy.
9. VHS: `P.vhs(c, S, t, lt, { osd: { label: 'PLAY', date: '…', clock: '23:59' } })` (opcje: `band = 70`,
   `bandSpeed = 520`, `vignette`). W środku:
   - rozdział RGB: każdy kanał osobno – S do płótna tymczasowego, `multiply` czystym `#ff0000/#00ff00/#0000ff`,
     potem `lighter` z przesunięciem na czarne tło; przesunięcie `3 + 1.5sin(7t)`, czasem (hash < 0.12) jeszcze +6;
   - pas zakłóceń 70 px jedzie w dół `(520lt + 200) mod (H+160)`; w pasie co 6 px przesunięcie poziome
     `±30·sin(πy/bh)` i 90 biało-szarych kresek szumu;
   - linie skanowania: kafel 4×4 (wiersz 0 α 0,28, wiersz 2 α 0,12);
   - OSD: „PLAY” i ręcznie rysowany trójkąt ▶ (krój go nie ma), miga co 16 klatek; w lewym dolnym rogu data
     i kod czasu liczony z lt.

## Co się rusza
- Ruch główny: postać pije herbatę (wspólna choreografia `P.choreo`), z filiżanki leci para (`P.steam`).
- Słońce jedzie w górę 0,9/s, cyjanowa siatka za oknem i siatka podłogi przewijają się do widza
  (`phase = 1.3t mod 1`), palmy się kołyszą.
- Szyld mruga: znak k gaśnie, gdy `hash(floor(30t), k) < 0.07` (losowanie 30 razy na sekundę); jeden znak
  dodatkowo, gdy `f mod 17 < 5`, gaśnie z prawdopodobieństwem 22%.
- Pas zakłóceń VHS jedzie w dół 520 px/s, OSD miga co 16 klatek, pasek postępu w okienku rośnie.
- Różnica klatek 25% (VHS porusza cały ekran).

## Przejście-podpis (wejście w ten styl)
- `vhs`, 0,30 s: awaria taśmy. Pierwsza połowa to stary obraz, druga nowy. W p 0,38–0,62 „utrata synchronizacji”:
  cały obraz roluje w górę z czarnym pasem 40 px. Pasy rozdarcia wysokości 6–54 px biorą obraz z A albo B (B
  z prawdopodobieństwem p) i przesuwają go o ±130·sin(πp). Kopie magenta i cyjan składane `screen` z przesunięciem
  ±14, na wierzchu 160 kresek śniegu. Ok. 88 ms na klatkę.

## Wydajność
- Mediana 49 ms na klatkę.
- W cache tylko tło statyczne (`vw_bg`). Koszt to VHS: kilka pełnoekranowych `drawImage` na klatkę (trzy kanały,
  pas zakłóceń).

## Pułapki
- Różowa bluzka zlała się z różową skórą i postać wyglądała na nagą. Ubranie musi mieć inny kolor niż skóra (tu
  lawendowy płaszcz `#8f7cf6`, biały kołnierz, cyjanowy zamek).
- Pełnoszerokie znaki („ＶＡＰＯＲＷＡＶＥ”), ▶ i japońskie znaki szyldu nie istnieją w `lib/fonts` i po cichu
  spadają na krój systemowy. Etykiety pisz zwykłymi znakami z odstępem liter 7, trójkąt i znaki szyldu rysuj
  ścieżką. Przed każdym nowym tekstem sprawdź znaki `U.assertGlyphs`.
- Kontur postaci rysowany ścieżkami części, więc świecą też styki (talia, ramię przy tułowiu). W neonowym rysunku
  to uchodzi; czysty obrys zewnętrzny zrobisz tak: najpierw sylwetka do bufora poza ekranem, potem obrysuj krawędź
  bufora.
- Szczeliny słońca (`destination-out`) wycinaj w buforze; na płótnie kadru zostawiłyby przezroczyste dziury, które
  w filmie są czarne.

## Kontrola
- Czy neon ma dwa poziomy (poświata i prawie biały rdzeń 2–3 px), a nie jedną rozmytą linię?
- Czy słońce ma 7 szczelin rosnących ku dołowi i jedzie w górę?
- Czy rozjazd RGB widać na krawędziach, a kluczowy napis da się przeczytać?
- Czy ubranie postaci odcina się od skóry i tła?
- Czy żaden znak nie spadł na krój systemowy (`U.assertGlyphs`)?

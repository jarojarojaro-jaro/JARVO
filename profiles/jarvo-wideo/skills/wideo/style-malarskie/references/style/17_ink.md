# Chińskie malarstwo tuszem xieyi (`17_ink`)

Swobodne malarstwo tuszem w duchu Bada Shanrena i Qi Baishiego. Odwrotnie niż w oleju: papier jest tłem, tusz tylko
się dokłada, dużo pustego papieru. Poznasz go po pociągnięciach pędzla z suchymi przerwami (feibai), plamach tuszu
rozlewających się w papier, czerwonej pieczęci i obrazie, który na początku sam się pisze. Jakość wzoru: ★★
(rozpoznawalny, ale z wyraźną słabością); słabość wzoru: postać za mało swobodna, za mało xieyi (ocena przeglądu 6/10)
(przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 17_ink --czasy 0.1,0.45,0.9 --arkusz out/wideo/wzor-17_ink.jpg`;
kod `$HUASHU/scripts/engine/scenes/17_ink.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Kultura i rzemiosło: herbaciarnia, sztuki walki, medycyna chińska, kaligrafia, wystawa sztuki Azji: 5–20 s.
- Czołówka albo zwiastun, który pisze się pędzlem w 0,45 s, a potem spokojnie oddycha: 5–10 s.
- Film o papierze, tuszu, ręcznej robocie; przerywnik „cisza” w dłuższym materiale.
- Krajobraz, bambus, ptaki, krewetki, kot: motywy, które ten styl niesie najlepiej.

## Nie do
- Jasny akwarelowy pokój z postacią: `25_ghibli`; cały film w akwareli z gotowym silnikiem: `lemo-opuscar`.
- Postać w zbliżeniu jako główny nośnik emocji (słabość wzoru).
- Dużo tekstu na ekranie: krój `LXGWWenKai-500` nie ma polskich znaków, nakładka podmienia go na `Caveat-600`
  (pismo ręczne), co zmienia charakter.

## Cechy stylu (sprawdzalne)
- Papier xuan: `PAINT.texture('xuan', '#efe6d0', {scale: 0.0025, amt: 9, grain: 7})` + 2600 włókien (krótkie łuki:
  połowa brązowe α .05–.13, połowa jasne α .12–.27) + winieta radialna do α .22 na brzegach.
- Tusz `[16,14,12]`, pięć tonów przez `tone`: palony .9, gęsty .8, ciężki .6, rozcieńczony .35, przejrzysty .15.
- Kolory: ochra (kot) `#c47a3c`; indygo (szata) `#6f8aa0`, szeroki rękaw `#7d97ab`; żółcień (złote włosy)
  `rgba(226,170,52,.75)` w `multiply`.
- Czerwień tylko w trzech miejscach: pas, perła spinki, usta (`[190,40,40]`); do tego cynobrowe słońce `#d8553f`
  i pieczęć `#c4281e`.
- Puste miejsca zamiast bieli: białe części kota (pyszczek, pierś, łapy) i kołnierz bluzki wycięte `destination-out`
  z warstwy ochry, widać papier. Twarz wypełniona kolorem papieru, kontur 1,8 px palonym tuszem (baimiao).
- Kot „białkami do nieba” jak u Bada Shanrena: źrenice przy samej górnej krawędzi oka.
- Napisy wzoru w `LXGWWenKai-500` → u nas `Caveat-600` (nakładka). Pieczęć to czerwony kwadrat 68×68 z dwoma znakami
  wyciętymi `destination-out` i plamkami; u nas 1–2 litery (inicjały marki) wycięte tak samo.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 17_ink`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js`, `kit.js` (`KIT.resample`, `KIT.label`, `KIT.choreo`), `brush.js`
   (`PAINT.brush`, `PAINT.leaf`, `PAINT.inkWash`), `rig.js`. Nie zamalowuj całości: tusz tylko dochodzi.
2. Kolejność warstw: papier (cache `ink_paper`) → plamy: jasny tusz gór, cynobrowe słońce → pasma mgły (rozmyte
   elipsy koloru papieru) → przelatujący ptak → statyczne kreski (okno, stół, linia podłogi; po napisaniu cache
   `ink_static`) → gałąź bambusa z liśćmi → krewetki w zwoju → kot (ochra + palony tusz) → postać (indygo + kontur
   + fałdy) → para → pieczęć.
3. Pędzel `PAINT.brush(c, pts, {w, tone, dry, reveal, bristles, head, tail})`:
   - punkty zagęszczone Catmull-Rom i próbkowane co 4 px po długości (`KIT.resample`);
   - nacisk `prof(q) = smoothstep(0,head,q) · (1−0.7·smoothstep(1−tail,1,q)) · (0.85+0.15·noise)`;
   - mokry rdzeń: wstęga szerokości `w·prof·(1−0.85·dry·q^0.8)`, α = tone×0.72 (pod koniec węższa, tusz się kończy);
   - włosy pędzla: każdy jedna **ciągła** linia, przesunięcie w bok ±0.475w·prof; przerwa tam, gdzie
     `noise(k·1.9, i·0.09) < dry·q^1.2·0.95+0.05` (prześwit papieru to feibai);
   - parametry: rama okna `w` 14–18, `dry` .45–.6; blat `w` 22; fałdy `w` 4–6, `dry` .3–.4, `tone` .78; linia
     podłogi `w` 5, `dry` .85, `tone` .35.
4. Plamy tuszu `PAINT.inkWash(c, key, grow, fn, {blur, halo, haloA, alpha})`: kształt na pomocniczym płótnie, potem
   dwa przejścia `multiply` na papier: aureola `blur(halo·(0.4+grow))` z α = haloA·grow i rdzeń
   `blur(blur·(1.6−0.6grow))`. `grow` rośnie z czasem od 0 do 1: na starcie tusz rozlewa się z niczego, potem aureola
   powoli się poszerza. Postać `halo` 12, α .6; kot `halo` 9, α .78; góry `halo` 14.
5. Zanim położysz plamę na kocie i szacie, podłóż w ich sylwetce papier (`clip` + `drawImage` papieru). Tak
   „zostawiasz miejsce” na papierze i nic nie prześwituje.
6. Liście bambusa, skrzydła, ogon krewetki: `PAINT.leaf(c, x, y, ang, L, w)` (pociągnięcie zwężone na obu końcach).

## Co się rusza
- Otwarcie pisze się samo: `lt` 0→0.45, każde pociągnięcie `reveal = ss(d, d+l, lt/0.45)`, kolejność: okno, stół,
  bambus, kot, postać. Start przesunięty `lt += 0.12`, więc w klatce 0 leży już kilka pociągnięć (pusta kartka nie
  nadaje się na okładkę).
- Bambus: gałąź z segmentów jasnego tuszu kołysze się wokół (835,70) `sin(2.9t)·0.11`, mocniej przy końcu; 5 grup
  po 3 liście (L110, w15) obraca się `sin(7t+g)·0.2`.
- Mgła: 4 elipsy koloru papieru, blur 14, α .72, przesuw 150–270 px/s; góry raz widać, raz nie.
- Ptak w stylu Bada Shanrena przelatuje 420 px/s nad mgłą (y ok. 470), skrzydła z dwóch pociągnięć, ok. 8 machnięć
  na sekundę (`sin(52·lt)`).
- Dwie krewetki Qi Baishiego w zwoju (skala 1,45): 6 segmentów jasnym tuszem i jedno pociągnięcie palonym na pancerzu,
  dwa długie i dwa krótkie wąsy falą biegnącą, trzyczłonowe szczypce, ciało wygina się `sin(7t)·0.12`, płyną po
  krzywej.
- Pieczęć: `lt` 0,3–0,4 spada z 1,5× do 1×, `multiply`.
- Para z kubka: dwa cienkie pociągnięcia jasnym tuszem (`w` 3, `dry` .7), nowe ziarno 10 kl./s.

## Przejście-podpis (wejście w ten styl)
- `inkBloom`, 0,45 s, środek (560,740) (`TRANSITIONS.inkBloom`): stary kadr „pierze się” w papier (szarość, jasność
  +0.35, kontrast −0.3), z miejsca przyłożenia pędzla rozlewa się plama tuszu, za nią 6 kolejnych w losowych
  miejscach. W plamach pojawia się nowy obraz; brzeg plamy ma obwódkę tuszu, która blednie, gdy plama rośnie. Od
  p=0.8 dochodzi pełny nowy kadr. Wyrasta z tuszu rozlewającego się w papier. (W oryginale styl otwierał film bez
  przejścia; to przejście dodano w filmie pokazowym.)

## Wydajność
- Źródło nie podaje ms na klatkę.
- Cache: papier `ink_paper` i statyczne kreski `ink_static` (zapisz je po napisaniu; bez tego co klatkę rysujesz
  tysiące włosów pędzla).
- Maskę i obwódkę przejścia licz w 1/4 rozdzielczości (pełne rozmycie kosztuje ok. 170 ms).

## Pułapki
- Każdy włos pędzla to jedna ciągła ścieżka z końcami `butt`. Odcinki rysowane osobno z `round` dają ciemne węzły
  jak bambus albo sznurek.
- Bez próbkowania co 4 px częstotliwość suchych przerw zależy od długości pociągnięcia.
- `multiply` jest przezroczyste: linia parapetu prześwitywała przez uszy kota, nogi stołu przez suknię (przegląd
  odczytał to jako złą kolejność warstw). Przed plamą podłóż papier w sylwetce.
- Ptak lecący przez kępę liści bambusa znika: prowadź go nad mgłą.
- Obwódka plamy w przejściu musi znikać, gdy plama rośnie, inaczej pierścień przecina nowy obraz.
- Słabość wzoru to postać. Najczęstszy problem wzorów: tło przepuszczone przez renderer wygląda jak styl, a postać
  z samego szkieletu i płaskiego koloru wygląda na doklejoną. Rysuj postać tym samym pędzlem i plamą, swobodniej.

## Kontrola
- Czy w klatce 0 są już pociągnięcia (nie pusta kartka)?
- Czy w pociągnięciach widać suche przerwy bez ciemnych węzłów?
- Czy białe części to pusty papier, a nie farba, i czy nic nie prześwituje przez kota i szatę?
- Czy czerwień jest tylko w 3 punktach plus słońce i pieczęć?
- Dowód z wzoru: różnica klatek 0,45↔0,9 s = 3,3% (próg 24), mediana sąsiednich 0,62%, żadnej pary stojących klatek.
  Twoja wersja nie powinna stać bardziej.

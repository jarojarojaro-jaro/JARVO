# Grecka waza czarnofigurowa (`03_greek`)

Attycka waza czarnofigurowa z ok. 530 r. p.n.e.: czarne sylwetki na pomarańczowej glinie, rysunek „rytem” (jasne
linie wydrapane w czerni), do tego purpurowe pasy z białymi kropkami i pasy ornamentu (meander, pąki lotosu).
Poznasz go po trzech rzeczach naraz: czarna sylwetka bez obrysu, jasny ryt, purpura z białymi kropkami; gdy są
wszystkie trzy, żadna faktura nie jest potrzebna. Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia);
słabość wzoru: dół szaty za gruby (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 03_greek --czasy 0.4,0.6,0.9 --arkusz out/wideo/wzor-03_greek.jpg`; kod
`$HUASHU/scripts/engine/scenes/03_greek.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Restauracja grecka, oliwa, wino: spot 10–15 s, karta dań na ekranie.
- Kultura antyczna, filozofia, teatr: film edukacyjny 30–60 s z lektorem.
- Sport (olimpiada szkolna, bieg miejski: biegacze jak na wazie): zapowiedź 10–20 s.
- Ozdobna rama z meandrem pod napis (intro albo outro 3–5 s).

## Nie do
- Sceny pełne koloru: `04_roman` (mozaika) albo `02_egypt`.
- Emocje i mimika z bliska (sylwetka nie ma mimiki): `16_2026`.
- Nowoczesna technologia, SaaS: `style-motion`.

## Cechy stylu (sprawdzalne)
- Sylwetka: każdy człowiek i przedmiot `#1b120d` (prawie czarny, ciepły), bez obrysu; kształt robi kontrast z gliną.
- Ryt: jasna glina `#e8904c`, linie 1,5–2 px (fałdy, rysy twarzy, granice nakładających się kończyn).
- Dodatki: purpura `#8a2a37` (opaska, mankiety, dół szaty, obroża, poduszka) i białe kropki `#f6ead6`, r≈2,
  co 11–17 px.
- Glina z poziomymi śladami toczenia na kole, plamami i 5 pęknięciami z jasną krawędzią; winieta na wierzchu.
- Pasy ornamentu: u góry meander (okres 60 px, linia 7 px), u dołu łańcuch pąków lotosu i promienie (okres 76 px =
  dwa elementy po 38 px, co drugi pąk purpurowy).
- Grecki napis z własnej tabeli kresek: każda litera to 1–3 łamane w kratce 0..1; wysokość 30, kreska 3,4, litery
  nierówne (×0,9–1,06), linia bazowa ±6%, wierzchołki ±0,7 px; Ο jako małe kółko (0,25 wysokości), Ι szerokości 2 px.
  Ręczny charakter dają nierówne litery i małe „o”.
- Postać: grecki profil (prosty nos w linii czoła, wąski podbródek), oko en face w profilu. Złote włosy `#f2bd48`
  liniami 2,5 px: 11 falistych pasm na czubku, 8 loków z tyłu zakończonych spiralką, kok z podwójną spiralą,
  4 loki na czole, 2 spirale na skroniach (na czarnym podkładzie 6 px, złoto 2,2 px). 16 fałd rytem, purpurowy pas
  15 px z kropkami na dole szaty, mankiety, bransolety, 8 białych kwiatków z kropek, opaska.
- Kot w tej samej technice co człowiek: czarna sylwetka, purpurowy pas 26 px wzdłuż grzbietu, purpurowa plama na głowie
  (elipsa 46×22), ogon czarny z purpurowym rdzeniem 7 px. Pręgi rytem `#f2913f` 3 px: 14 łuków wzdłuż grzbietu ku
  środkowi ciała, 3 na udzie, 3 na łapie, pierścień co 2 punkty ogona. Biel `#efe1c8` na piersi, pyszczku i łapach
  (czarne palce rytem), oko jako ryty migdał, nos purpurowy.
- Paleta: glina `#dc6a2f`, jasna glina (pole wazy) `#e8803f`, czerń `#1b120d`, purpura `#8a2a37`, biel `#f6ead6`,
  ryt `#e8904c`, złote włosy `#f2bd48`, kremowa glina `#f3cfa4`, pomarańcz kota `#f2913f`, nos `#e7897a`.
- Napisy (plakietka roku z filmu źródłowego): `Cinzel-700` 98 px `#e3a066` w ramce `#1b1310` z obrysem `#c8743c`,
  podpis `Cinzel-700` 29 px; Cinzel ma polskie znaki. Greckich liter krój nie ma: tylko tabela kresek.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 03_greek`; `P` = `PAINT`
   (`/_lib/huashu/lib/paint.js`), `RIG`, `U`.
2. Glina (`gr_bg`, cache): w 480×270 per piksel `fbm(×0.016, 4 okt.)` plamy ±30 + `noise(x*0.006, y*0.85)` poziome
   pasy ±9, potem skala do 1920×1080 (16× mniej liczenia, niska częstotliwość i tak jest miękka). Dalej 560 poziomych
   kresek (długość 150–1050, α 0,03–0,08, ciemne i jasne), 420 ciemnych i 120 jasnych kropek, dwie warstwy `P.grain`,
   5 pęknięć (odcinki co 9 px, drżenie ±2 px, pod spodem jasna linia 1 px), ciepłe rozjaśnienie w środku 0,16.
3. Winieta (`gr_vig`): radialna 380→1180, brzeg `rgba(30,6,0,.62)`, na wierzchu wszystkiego (także pasów).
4. Warstwa statyczna (`gr_static`): rama (czarna 18 px, białe kropki co 11,6 px, cienka linia), winorośl (sinusoidalna
   łodyga, grona 3-2-1), stół z łapami, toczone nogi krzesła (tabela szerokości `[y,w]` odbita symetrycznie), oparcie
   jak szyja łabędzia (krzywa 13 px, głowa z elipsy, trójkątny dziób), amfora (24 punkty symetryczne → `RIG.smooth`,
   pole z gliny z małym czarnym kotem, promienie u dołu, pionowy połysk 0,09), dwa napisy.
5. Pasy ornamentu: wyrenderuj raz pas szerokości `W+2P` (P = okres; `gr_topStrip`, `gr_botStrip`), co klatkę
   `drawImage(strip, -(off mod P))`. Element meandra: `[[4,46],[4,0],[50,0],[50,34],[18,34],[18,14],[36,14],[36,22]]`
   + ciągła linia bazowa.
6. W ramie (co klatkę, clip do ramy): 6 delfinów (beziery: dziób, płetwa grzbietowa i brzuszne, rozwidlony ogon,
   ryt brzucha, białe oko) i statek (biały żagiel z purpurowym szwem, kadłub jak półksiężyc, rufa jak ogon skorpiona,
   purpurowa kabina, półleżąca postać).
7. Postać: `RIG.girl({cup,sip,breathe,s:0.97,dy:-14,hair:'long'})`; ciało wypełniasz `Path2D` z `RIG` (farSleeve,
   skirt, torso, neck), dalszą dłoń zastąp małą elipsą. Głowę rysuj sam w spoczynkowym układzie `RIG` i przenoś
   przekształceniem `translate(neck)·rotate(G.tilt)·translate(−neck)·T`; tę samą macierz policz w `DOMMatrix`
   i użyj `Path2D.addPath(faceSil, M)` jako obszaru przycięcia rytu.
8. Granica ręki na ciele i głowie: `clip(ciało∪głowa)`, potem obrys ręki rytem. Czerń na czerni da się rozdzielić
   tylko tak.
9. Picie – własne IK: punkt ust (1243, 391) przez macierz głowy na ekran; środek brzegu czarki = usta −(30, −1) (prawy
   koniec brzegu dotyka warg); nachylenie `−0.08·cup` (≤5°); cel dłoni = brzeg + `(lerp(32,6,cup), 30)` (pod stopką);
   `RIG.ik2(S, cel, 165s, 122s, −1)` + `RIG.taper` na ramię i przedramię. Kyliks szeroki i płytki (połowa szerokości
   32) z purpurową linią brzegu.
10. Kot: własny, ogon z `RIG.cat().tailPts` sterowany `choreo.tail`; całość zmniejszona do 0,9 wokół (548, 903).

## Co się rusza
- Ruch główny: picie (`choreo.cup`, 0,9 s do ust, lekkie odchylenie głowy).
- Pasy ornamentu: górny w lewo, dryf 48 px/s + jeden okres 60 px z `easeInOut((lt−0.49)/0.35)`; dolny w prawo,
  dryf 30 px/s + 76 px z `easeInOut((lt−0.477)/0.367)`. Stały dryf jest konieczny: przesunięcie o pełny okres daje
  klatkę identyczną z wyjściową.
- Lira: wahadło wokół gwoździa (1050, 150), `0.09·sin(2π·lt/0.8+0.5)` (±5°, pudło ±17 px).
- Statek kołysze się wokół (560, 420): ±4 px, ±0,025 rad, okres 0,9 s. Delfiny: ±9 px wzdłuż swojego kierunku,
  kąt ±0,12 rad, okres 0,85 s, przesunięcie fazy 1,3 między nimi.
- Rozeta: 8 czarnych płatków z rytem i purpurowym środkiem, obrót `lt·1.6` rad/s na przemian w obie strony.
- Kot: ogon, mrugnięcie (łuk rytem), oddech. Para: trzy czarne „≀”, faza `t·9`, za brzegiem czarki.
- Odcinek w filmie źródłowym: 4 ósemki (0,94 s); wszystko powyżej widać w 0–0,94 s.
- Dowód: między 0,2 a 0,7 s zmienia się 22% pikseli; średnia różnica klatek w odcinku wzrosła z 1,87 do 2,02
  (oryginał 2,06) po przyspieszeniu dryfu pasów.

## Przejście-podpis (wejście w ten styl)
- `cube`, 0,32 s: sześcian obraca się wokół osi pionowej, stara ściana odjeżdża w lewo, nowa wjeżdża z prawej.
  Każda ściana w 48 paskach, dalsza krawędź skrócona `k=0.18·sin(kąt)`, przyciemnienie do `0.55·sin(kąt)`, tło
  `#0d0a08`, `ease.inOut`. W indeksie źródła: „waza obraca się jak walec”.

## Wydajność
- Ciepła klatka: maks. 15,9 ms, średnio 7,6 ms; zimna 80 ms; po poprawkach maks. 17 ms.
- Cache: `gr_bg`, `gr_vig`, `gr_static`, `gr_topStrip`, `gr_botStrip`. Glina w niskiej rozdzielczości to 16×
  mniej liczenia.

## Pułapki
- Kot jako rysunkowy pomarańczowy kot z wielkimi oczami od razu odstaje od sceny czarnofigurowej. Każda postać
  w tej samej technice co człowiek.
- Włosy `RIG` po prostu powiększone dają za szeroki tył głowy (wygląda jak kask); przytnij kontur (we wzorze do
  x=1424), długie włosy tylko do y≈558.
- Przy ustach czarna dłoń, czarne naczynie i czarna twarz zlewają się. Pomaga: ryt granicy ręki, mniejsza czarka
  (połowa szerokości 44→32), purpurowa linia brzegu, przedramię pionowo przed piersią.
- Domyślny koniec trasy naczynia `RIG` (przy czubku nosa, nachylenie −0,45 rad) z płaską czarką wygląda jak dziób
  albo fajka wbita w twarz, a dłoń zasłania usta. Licz własne IK jak w kroku 9.
- Dolny pas ma prawdziwy okres 76 px (dwa elementy); zawinięcie co 38 px zmienia kolor pąków co element.
- `P.grain` bierze ziarno z długości klucza: dwie warstwy muszą mieć klucze różnej długości, inaczej wzór jest ten sam.
- Złote linie 2 px nie czytają się w miniaturze; 2,5 px w 1080p.
- Głowa kota `RIG` sięga y=535, a kadr przewiduje 610; bez zmniejszenia wchodzi w dolną krawędź ramy.

## Kontrola
- Czy są wszystkie trzy elementy: czarna sylwetka bez obrysu, jasny ryt, purpura z białymi kropkami?
- Czy kot i każda inna postać są w tej samej technice co człowiek?
- Czy przy ustach widać profil (nos, usta, podbródek), a ręka jest oddzielona rytem?
- Czy pasy ornamentu mają różną fazę w dowolnych dwóch klatkach (stały dryf)?
- Czy greckie litery mają nierówną wysokość i małe „o”?

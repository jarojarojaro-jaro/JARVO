# Konstruktywizm rosyjski, plakat z 1924 r. (`22_constructivism`)

Plakat w duchu Rodczenki i El Lisickiego: stary papier, czerwony klin i czarne koło, ukośne paski składu,
geometryczne litery złożone z prostokątów i fotomontaż w rastrze (zdjęcie w szarości zamienione na kropki pod 45°)
obok płaskich wycinanek. Litery rysujesz ścieżkami, nie krojem, więc tak samo narysujesz polskie hasło. Jakość wzoru:
★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: brak lejka z liter (hasło rozchodzące się klinem z ust
albo megafonu, typowe dla Rodczenki) (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 22_constructivism --czasy 0.1,0.4,0.9 --arkusz out/wideo/wzor-22_constructivism.jpg`;
kod `$HUASHU/scripts/engine/scenes/22_constructivism.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Kampania z hasłem: apel, akcja społeczna, frekwencja, „Pij kawę!”: 5–15 s.
- Plakat wydarzenia: teatr, festiwal, muzeum, wystawa designu, targi; rekrutacja w estetyce plakatu: 10–20 s.
- Historia przemysłu: fabryka, wieża, energetyka, radio, kolej (fotomontaż + rysunek): 15–30 s.
- Marka z czerwono-czarną paletą i mocną typografią: przerywniki 3–5 s.

## Nie do
- Geometria bez haseł i propagandy: `12_bauhaus` albo `style-motion`, karta `bauhaus`.
- Kolaż ze zdjęć klienta bez klina i haseł: `style-motion`, karta `kolaz`.
- Tematy, w których skojarzenie z propagandą radziecką szkodzi (polityka, wojna, Ukraina): najpierw sprawdź kontekst.

## Cechy stylu (sprawdzalne)
- Paleta: papier `#e9dfc4` (ciemniejszy `#d9c9a4`), czerwień `#c8231c / #8f1711`, czerń `#151311`, kremowy `#f4ecd6`,
  złote włosy `#e3b03e / #a87a1c`, pomarańcz kota `#e2741c`.
- Kompozycja wzoru: po lewej skośny czarny pasek (rotate −0.5), czerwony kwadrat (rotate 0.26) i 5 linii „tekstu”
  z czarnych pasków; po prawej cienka skośna linia, czerwona kropka i czarny pionowy pas z pionowym napisem „ЧАЙ”;
  wielkie czarne koło za głową (środek (1330,395), r 215); skośna czerwona podłoga (0,905)→(1920,856) z czarną linią
  12 px u góry.
- Fotomontaż w oknie: szare „zdjęcie” (niebo `#5e5e5e→#e8e8e8`, białe chmury, ciemne hale, komin) w rastrze
  (cell 7, gain 0.8). Na rastrze ostra czarna linia: wieża Szuchowa (5 odcinków-hiperboloid, w każdym 2×18 prostych,
  przesunięcie fazy ±1,1 rad, tylne linie z `sin<−0.2` pominięte). Zdjęcie + rysunek to właśnie ten kolaż.
- Skóra jak zdjęcie w rastrze: twarz, szyja, dłonie najpierw w szarym gradiencie (przód jasny, tył ciemny,
  `#fafafa→#9c9c9c`), potem raster cell 4.6, gain 0.74, 45°. Pod spodem kremowy, dookoła biały margines 7 px
  `#fbf7ea` (brzeg wyciętej fotografii). Rysy twarzy ostrą czarną linią, usta ręcznie na czerwono.
- Ubrania: płaskie wycinanki + czarna linia 3 px, cienie z kropek `PAINT.shadeDots`.
- Postać wzoru: komsomołka w czerwonej chuście (zawiązana z tyłu, dwa trójkątne końce, spod chusty złota grzywka),
  biała koszula, czerwona chusta-trójkąt na szyi i czerwone mankiety, ciemnoszara długa spódnica z rastrowym cieniem.
  Kot: wycinanka `#e2741c` i kremowy, czarne pręgi 10 px, ogon obrysowany linią przerywaną (pręgi), oczy z pionową
  prostokątną źrenicą.
- Litery z prostokątów: siatka 5×7 modułów, piony i belki grubości 1,3 modułu, środkowa belka 1,2.
- Kroje w filmie pokazowym: licznik roku `Anton-400`, etykieta `ArchivoBlack-400` (oba mają polskie znaki). Hasło
  zawsze ścieżkami.

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 22_constructivism`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js` (`U.poly`, `U.ease`), `paint.js` (`PAINT.texture`, `PAINT.cached`, `PAINT.canvas`,
   `PAINT.choreo`), `render.js` (`PAINT.halftoneGray`, `PAINT.shadeDots`), `rig.js` (`RIG.drawCup`).
2. Tło w cache `cs_bg`: papier `PAINT.texture('cs_paper', '#e9dfc4', {scale: 0.0035, amt: 16, grain: 18,
   dark: '#d9c9a4'})` → paski, kwadrat, kropka, pionowy napis → czarne koło → czerwona podłoga → okno z fotomontażem
   → czarny stół (czerwona krawędź, skośna rozpórka) → czarny klocek-stołek.
3. Raster zdjęcia: `PAINT.halftoneGray(c, src, bx, by, bw, bh, cell, col, gain, ang=π/4)`. Czyta jasność ze `src`
   na obróconej siatce, średnica kropki `cell·gain·√(1−L)`, kropka tylko tam, gdzie alfa > 128. **Wszystkie kropki
   w jednej ścieżce, jeden `fill`** (twarz ok. 3000 kropek w mniej niż 2 ms).
4. Cienie na ubraniu: `PAINT.shadeDots(c, path, bx, by, bw, bh, cell, col, f)`, gdzie `f(x,y)` (0..1) to siła cienia,
   np. `clamp((x − 1180)/260)·0.9` na spódnicy.
5. Litery jako ścieżki (tak narysujesz każde słowo, także polskie):
   - Słownik liter jak `GL` w scenie: litera = lista prostokątów `[x, y, w, h]` i wielokątów `{p: [[x,y], …]}`
     w modułach siatki 5×7. Funkcja `glyph(c, ch, x, y, u)` skaluje modułem `u` (hasło na podłodze 19 px, pionowe
     „ЧАЙ” 15,5 px, litery co 120 px). Krok litery `6.3u`, spacja `3.5u`. Skopiuj `GL` i `glyph` ze sceny i dopisz
     brakujące litery (we wzorze są tylko П, Е, Т, Ч, А, Й i „!”).
   - Każdy element litery wypełniaj osobno (`beginPath` + `fill` dla każdego prostokąta i wielokąta). Dwie skośne
     nogi w jednej ścieżce znoszą się według reguły nonzero: „А” czytało się jak „В”.
   - Polskie znaki: cała litera razem z akcentem mieści się w komórce 7 modułów. Wzorem jest „Й”: podstawa „И”
     przesunięta o 1,7 modułu w dół, łuk to prostokąt 2,6×1,0 modułu na samej górze komórki. Tak samo Ó, Ś, Ć, Ń, Ź
     (kreska jako skośny czworokąt w górnym pasie) i Ż (kropka jako mały kwadrat w górnym pasie). Ą i Ę: ogonek jako
     osobny czworokąt w dolnej części komórki, literę skróć od dołu, żeby ogonek nie wychodził poza 7 modułów. Ł:
     skośna belka jako osobny czworokąt przez pion.
   - Litery, której nie ma w słowniku, funkcja po cichu nie narysuje (`if (!g) return;`). Dopisz każdą literę hasła
     i sprawdź stopklatkę.
   - Hasło rysuj nad postaciami (na plakacie litery przykrywają ludzi), obrócone wzdłuż czerwonej podłogi
     (`Math.atan2(-49, W)`), środek litery w `translate(x + 2.5u, 990)`; co czwarta litera czarna, reszta kremowa.
6. Postacie po tle: płaskie wypełnienia + linia 3 px; skórę najpierw jako szary gradient na osobnym płótnie, potem
   raster na kremowym podkładzie z białym marginesem.

## Co się rusza
- Czerwony klin Lisickiego wbija się w czarne koło: wierzchołek jeździ po osi 0,34 rad tam i z powrotem
  `70·(0.5−0.5cos(2π·1.6·lt))`.
- Czerwony przerywany pierścień wokół koła: dash `[46,22]`, `lineDashOffset = −260·lt`.
- Fale radiowe ze szczytu wieży: 4 czerwone łuki, `r = 18 + ((1.4lt + k/4) mod 1)·230`, krycie i grubość maleją
  z fazą.
- Hasło (we wzorze „ПЕЙТЕ ЧАЙ!”, czyli „Pijcie herbatę!”): litery przybijane po kolei jak pieczątka (litera `k` startuje
  po `0.045·k` s i w 0,12 s maleje z 1,5× do 1×), potem całe hasło skacze falą `−10·max(0, sin(11lt − 0.8k))`.
- Końce chusty `sin(9lt)·6`; para z kubka: trzy czarne zygzaki płynące w górę.

## Przejście-podpis (wejście w ten styl)
- `redWedge`, 0,4 s (`TRANSITIONS.redWedge`): czerwony klin wbija się ukośnie z lewego dołu przez cały kadr (oś
  −0,32 rad, długość 520 px, szerokość 2×330 px), za jego ostrzem jest już nowy obraz; za klinem wjeżdżają trzy
  czarne paski składu (wysokość 26/18/34 px, opóźnienia 0/0.12/0.2). Wyrasta z „Czerwonym klinem bij białych”
  Lisickiego. (W oryginale ten styl otwierał film bez przejścia; to przejście dodano w filmie pokazowym.)

## Wydajność
- Mediana 5 ms na klatkę.
- Cache: całe tło `cs_bg` razem z fotomontażem. Raster skóry liczony co klatkę, ale w jednej ścieżce, poniżej 2 ms.

## Pułapki
- Akcent wystający ponad komórkę zakrywa poprzednia litera (w pionie) albo postać (na podłodze): „ЧАЙ” czytało się
  jak „ЧАИ”. Akcenty w obrębie 7 modułów, hasło nad postaciami.
- Skośne elementy litery w jednej ścieżce kasują się: każdy element osobnym `fill`.
- Linia bazowa hasła na y=1060 ucinała dół liter: pozycjonuj po środku litery (`translate(x, 990)`).
- Cień pod kośćmi policzkowymi po rastrze wyglądał jak zarost. W szarym źródle daj cieniom połowę krycia płaskiego
  koloru.

## Kontrola
- Czy każda litera hasła jest narysowana (żadna nie zniknęła), a polskie akcenty mieszczą się w komórce?
- Czy litery z ukośnymi nogami (A, Ą, Ł) nie mają dziur?
- Czy skóra jest rastrem z białym marginesem, a ubrania płaskie?
- Czy klin, pierścień, fale radiowe i hasło ruszają się w pierwszej sekundzie?
- Dowód z wzoru: różnica klatek 3,6%.

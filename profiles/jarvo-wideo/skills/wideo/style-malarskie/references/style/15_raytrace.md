# Wczesne CGI z ray tracingu, 1993 r. (`15_raytrace`)

Grafika komputerowa z początku lat 90. bez silnika 3D: zwykłe Canvas 2D udaje render dzięki stałym regułom
cieniowania. Poznasz go po plastikowym połysku każdej części (ciemny brzeg, turkusowy odblask, twardy biały blik),
szachownicy na podłodze z odbiciem, chromowanej kuli, wirującym pierścieniu z kulek i flarach obiektywu. Jakość wzoru:
★★ (rozpoznawalny, ale z wyraźną słabością); słabość wzoru: nogi kota jak proste kolumny, twarz jak maska (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 15_raytrace --czasy 0.1,0.3,0.6 --arkusz out/wideo/wzor-15_raytrace.jpg`;
kod `$HUASHU/scripts/engine/scenes/15_raytrace.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Retro-technologia: rocznica firmy IT, „tak wyglądał komputer w 1993”, demoscena, muzeum techniki: 5–15 s.
- Produkt jako plastikowa zabawka (gadżet, zabawka, opakowanie w klimacie lat 90.): zwiastun 6–10 s.
- Wstawka „rok 1993” w filmie przez epoki: 1–2 s.
- Kanał o starych grach, intro podcastu technologicznego: 3–5 s.

## Nie do
- Realistyczny produkt w świetle studia, marka premium: `style-motion`, karta `3d` (Three.js).
- Postać w zbliżeniu jako nośnik emocji (słabość wzoru): `16_2026` albo `35_shinkai`.
- Neon, VHS, estetyka 2011: `26_vaporwave`.

## Cechy stylu (sprawdzalne)
- „Plastik” na każdej części: `plastic(c, path, base, hx, hy, R)`, blik w (hx,hy), promień R:
  1. kolor bazowy;
  2. gradient radialny od blika: 0 → biały .55, 0.28 → biały .06, 0.62 → przezroczysty, 1 → ciemny fiolet
     `rgba(10,0,30,.42)` (ciemny brzeg daje bryłę);
  3. odblask otoczenia: obrys `rgba(70,150,150,.28)` w trybie `lighter`, szerokość 0.18R, przesunięty o 0.04R w lewo
     (ściana jest turkusowa, więc odblask też);
  4. twardy biały blik eliptyczny 0.16R × 0.09R, krycie .85. Ten jeden punkt najbardziej przypomina „Phong z lat 90.”.
- Kończyny `cyl()`: gradient w poprzek kończyny (ciemny .25 → wąski biały pas .5 na 22% → ciemny .45) i biała cienka
  linia blasku na odcinku 20–75%. Postać jak lalka: niebieskie plastikowe walce nóg zamiast spódnicy, kulki stawów
  w kolanach i barkach.
- Ściana: gradient radialny `#7dbcb9 → #64a6a6 → #3f8285`, światło od okna; cień okna `blur(10px)` w prawo w dół.
- Za oknem: niebo `#a24cc4 → #df62ae → #f5a08a → #f8c070`, dwa pasma gór z różową siatką 28×26 (teren wireframe
  wczesnego CGI), ośnieżone szczyty jako ząbkowane trójkąty.
- Podłoga: szachownica w perspektywie liczona per piksel, punkt zbiegu (960,480), `X=(x-960)/dy, Z=1/dy`, pole
  TX=0.27, TZ=0.00029, supersampling 2×2, w pasie 140 px przy ścianie 35% mgły.
- Odbicie w podłodze: krzesło, stół i postacie odbite `translate(0, 2*906); scale(1,-1)`, `globalAlpha .34`, tylko
  w obszarze podłogi; rekwizyty względem własnej linii styku (stożek 780, pierścień 846, kula 800).
- Szklany stół: półprzezroczysta zielona elipsa, gruba krawędź, biały obrys, skośny refleks jadący 260 px/s.
- Krój napisów w filmie pokazowym: `Exo2-800i` (ma polskie znaki, nie jest podmieniany).

## Jak go zbudować
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 15_raytrace`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.cached`, `PAINT.scratch`, `PAINT.steam`, `PAINT.choreo`),
   `rig.js`. Funkcje `plastic` i `cyl` skopiuj ze sceny.
2. Statyczne tło (ściana, okno, góry z siatką) do cache. Szachownicę podłogi licz per piksel raz i też trzymaj
   w cache.
3. Warstwę obiektów (krzesło, stół, postacie) rysuj na osobnym płótnie. Najpierw odbij ją lustrzanie do podłogi
   (clip do podłogi, krycie .34), potem narysuj normalnie.
4. Rekwizyty odbijaj każdy względem swojej linii styku, **najpierw na osobną warstwę, potem całość półprzezroczyście**.
5. Każdą część postaci przepuść przez `plastic` albo `cyl`. Tułów kota w RIG to łamana: najpierw
   `RIG.smooth(K.bodyPts)`, potem cieniowanie, bo połysk pokazuje kanty. Pręgi kota z `filter: blur(2px)`
   (miękkie, „pod plastikiem”).
6. Rekwizyty (zielony stożek, chromowana kula, fioletowy pierścień), na końcu flary obiektywu w trybie `lighter`.

## Co się rusza
- Fioletowy pierścień: 140 kulek na torusie, obrót wokół osi pionowej 7 rad/s, pochylenie 0.35, rysowane od tyłu
  do przodu (najpierw ciemnofioletowa rura, żeby kulki się łączyły, potem każda kulka z blikiem). W 0,23 s obraca się
  o 1,6 rad, z przodu na bok: bardzo widoczne.
- Chromowana kula: co klatkę mapowanie otoczenia per piksel (wektor odbicia w dół → szachownica, w górę →
  różowofioletowe niebo i pasek światła z okna), współrzędna u szachownicy przesuwa się z `t*4.5` (kula się kręci),
  jaśniejszy brzeg (Fresnel). Średnica 104 px, poniżej 2 ms na klatkę.
- Flary (`lighter`): rdzeń 170 px pulsuje 23 rad/s ±8%; 12 promieni obraca się 1,6 rad/s; poziomy pas 960 px;
  5 „duchów” (koła i sześciokąty) na linii słońce → środek kadru, przesuwanych `sin(t*5)*0.03`.
- Zielone światło w oczach kota: gradient radialny `lighter` 46 px, pulsuje 18 rad/s ±25%.
- Picie z kubka (`choreo.cup`), ogon, mruganie i para jak zwykle.

## Przejście-podpis (wejście w ten styl)
- `wireframe`, 0,14 s (`TRANSITIONS.wireframe`): czarne tło `#02060a`, zielone neonowe krawędzie nowego kadru (Sobel
  w połowie rozdzielczości, próg 38) i siatka podłogi w perspektywie (horyzont y=640). Przez pierwsze 12% siatka
  wchodzi na stary kadr, od 30% linia skanowania jedzie z góry na dół i „renderuje” nowy obraz. Wyrasta z procesu
  renderowania: najpierw siatka, potem obraz.

## Wydajność
- Gorąca klatka 23 ms, zimny start 53 ms (cała scena razem z cache podłogi). Kula poniżej 2 ms.
- Przejście liczy krawędzie co klatkę, ok. 10 ms.

## Pułapki
- Pierwsza klatka nowego stylu (`lt≈0`) musi być pełna, bo przejście bierze z niej krawędzie siatki. Nie zaczynaj od
  pustki ani od rozjaśniania.
- Każdy rekwizyt odbijaj na osobną warstwę i dopiero całość kryj .34. 140 kulek pierścienia krytych osobno po .34
  nakłada się w nieprzezroczystą plamę.
- Łamana sylwetka bez `RIG.smooth` pokazuje kanty pod połyskiem.
- Słabość wzoru to postać: nogi kota jak proste walce, twarz jak maska. Najczęstsza słabość wzorów: tło przepuszczone
  przez renderer wygląda jak styl, a postać z samego szkieletu wygląda na doklejoną. Dopracuj kształt postaci w tym
  samym cieniowaniu.

## Kontrola
- Czy każda część ma cztery warstwy plastiku (kolor, ciemny brzeg, turkusowy odblask, twardy blik)?
- Czy odbicie w podłodze jest równo półprzezroczyste, bez ciemniejszych plam tam, gdzie elementy się nakładają?
- Czy w 0,25 s widać obrót pierścienia i pulsowanie flary?
- Czy szachownica nie ma schodków (supersampling 2×2) i blednie przy ścianie?

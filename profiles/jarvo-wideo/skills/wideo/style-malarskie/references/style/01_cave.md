# Malowidło jaskiniowe (`01_cave`)

Malowidło naskalne sprzed 40 000 lat: ochra i węgiel „wżarte” w wypukłą skałę, zwierzęta i ludzie jako płaskie
sylwetki z węglowym konturem o rozpylonym brzegu, negatywy dłoni, migotanie ognia i unoszący się żar. Poznasz go po
reliefie ściany, który przebija przez farbę, i po ziarnie węgla, które „wrze”, choć linia stoi w miejscu.
Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: postać ludzka zbyt kreskówkowa, za mało
pierwotna (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 01_cave --czasy 0.4,0.9,1.3 --arkusz out/wideo/wzor-01_cave.jpg`; kod
`$HUASHU/scripts/engine/scenes/01_cave.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę, nie scenę.

## Do czego
- Otwarcie filmu o początkach (historia firmy, miasta, wynalazku, „od pierwszego narzędzia do…”): 2–5 s, potem
  przejście w następną epokę.
- Muzeum, wystawa archeologiczna, lekcja historii: film edukacyjny 30–60 s z lektorem.
- Marka rzemieślnicza albo outdoorowa (browar, pracownia ceramiki, sklep survivalowy, szkoła łucznictwa): teaser
  10–15 s, 16:9 albo 9:16.
- Tło pod tytuł wydarzenia (festiwal, gra terenowa) na 5–10 s.

## Nie do
- Dane, liczby, interfejs, dużo tekstu do czytania: gramatyki explainera (`wykresy`, `prezentacja`).
- Twarze, emocje i dłonie z bliska (słabość wzoru): `16_2026` albo `25_ghibli`.
- Ciepły, „ręcznie rysowany” film bez klimatu prehistorii: `style-motion` (rysunek z wrzącą linią).

## Cechy stylu (sprawdzalne)
- Ściana: relief z łagodnymi wypukłościami (nie moro, nie wydmy), ziarno, 10 pęknięć z jasną krawędzią pod ciemną
  rysą (efekt rytu), winieta (zewnętrzny pierścień α 0,8).
- Każdy kształt ma trzy warstwy: pełną linię węgla, rozpylony brzeg z kropek i płaskie wypełnienie. Kolor „brudzi”
  faktura skały: w cieniach skały farba ciemnieje, na wypukłościach jaśnieje.
- Węgiel „wrze”: ziarno przeskakuje co 1/9 s, geometria stoi.
- Negatywy dłoni i łap: rozpylona ochra wokół pustego kształtu dłoni.
- Zwierzęta (bizon, koń): wypełniona sylwetka, nogi tylko kreską węgla, wzdłuż grzbietu ciemny pas 22 px (cieniowanie
  jak w Lascaux).
- Postać: sylwetka w czerwonej ochrze `#9c3520` (twarz, szyja, ręce, łydki), profil z jednym migdałowym okiem
  (kremowe białko, czarna źrenica, jedna rzęsa; przy mrugnięciu łuk). To jedno oko robi z sylwetki dziewczynę.
  Włosy żółtą ochrą `#cf8f2c` + 6 falistych pasm `#6e3c0e` (amplituda rośnie z długością), kontur włosów też falisty.
  Futro do kolan `#b06a2c` z 26 cętkami (koło + 7 kropek) `#4e2610` i 18 krótkimi kreskami sierści, brzeg w zęby
  co 15 px (±16 px).
- Paleta: ściana `#ce925a` / `#6e4426` / `#b6643a`; węgiel `#21150d`; czerwona ochra `#9c3520`, ciemna `#74261a`;
  żółta ochra (kot) `#c9772f`; włosy `#cf8f2c` / `#6e3c0e`; futro `#b06a2c`, cętki `#4e2610`; kreda `#f0dfbf`;
  bizon `#8c3d22`, jego głowa `#76301a`; koń `#cf8236`; kamień `#c98c50` / `#c08048`; blat `#d49a5a`;
  negatyw dłoni `#8e2a1a`; żar `#ffe082`.
- Napisy: tytuł `Kalam-700` 78 px, `letterSpacing` 7, ściśnięty w poziomie do 930 px, kolor `#9b2a18`, malowany
  w warstwie farby (skała go też „zjada”). Kalam ma polskie znaki. Plakietka roku z filmu źródłowego:
  `GochiHand-400` 84 px `#f3ead8` (w nakładce `huashu_pl.js` → `Caveat-600`), podpis `Kalam-700` 38 px.

## Jak go zbudować
1. Szkielet strony: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 01_cave`. Biblioteki:
   `/_lib/huashu/lib/paint.js` (`P` = `PAINT`), `/_lib/huashu/lib/rig.js` (`RIG`), `/_lib/huashu/lib/util.js` (`U`).
2. Ściana do cache (`P.cached('cave_relief', …)`, `P.cached('cave_bg', …)`): pole wysokości w pół rozdzielczości
   960×540: `fbm(x·0.0022, 4 okt.)·1.0 + fbm(x·0.011, 3 okt.)·0.16 + noise(x·0.05)·0.03` (współrzędne w pikselach
   pełnej rozdzielczości). Normalne: różnice skończone ×52; światło `L=(-0.55,-0.62,0.56)` z lewej góry;
   `shade = clamp(0.5+(dot-0.56)·0.9)`. Kolor bazowy miesza `#ce925a` / `#6e4426` / `#b6643a` dwiema warstwami fbm
   niskiej częstotliwości, potem ×`(0.72+shade·0.55)`. Do pełnego ekranu skaluj z wygładzaniem.
3. Faktura ściany: dwie warstwy `P.grain` (ciemna: gęstość 0,22, α 0,32; jasna: 0,10, α 0,28). 10 pęknięć błądzeniem
   losowym: skręt ±0,45 rad na krok, krok 14–40 px, 12% szans na rozgałęzienie; pod ciemną linią jasna przesunięta
   o 1,6 px. Winieta: gradient radialny r 260→1180. Ciepłe światło w środku w trybie `lighter`, α 0,36, tylko na ścianie.
4. Farba – jedna funkcja `shape()` dla wszystkich kształtów: obrys wzorem „fuzz” (rzadkie kropki węgla, szerokość
   `2lw+7`), obrys wzorem „ink” (węgiel z 7% losowych dziur i dużymi dziurami tam, gdzie szum >0,58, szerokość `2lw`),
   na końcu płaskie wypełnienie zakrywa wewnętrzną połowę linii. Kolejność rysowania sama załatwia zasłanianie.
5. Wrzenie: dwa wzory 256 px (`cave_inkpat`, `cave_fuzzpat`) przesuwaj losowo co 1/9 s przez `pattern.setTransform`.
   Taniej niż drżąca ścieżka i nic się nie deformuje.
6. Całą warstwę farby złóż raz na pełny ekran, potem `source-atop` tekstura `cave_figtex`: cień skały → czerń
   α `(0.5−v)·150`, jasne → ciepła biel α `(v−0.5)·50`, ziarno ciemne i jasne, plamy wilgoci α ≤70. Wypełnienia
   nieprzezroczyste; bez `multiply` (zginie biel kredy).
7. Negatyw dłoni: płótno robocze 320², rozpylone gaussowsko kropki (σ 46·s, 3200 kropek α 0,15–0,6, plus σ 28,
   1400 kropek), potem `destination-out` pełną maską dłoni, na koniec maska α 0,3 kolorem `#f6e2bc`. Każdy kawałek
   dłoni (owal dłoni, kapsułki palców) wypełniaj do maski osobno.
8. Ogień: co klatkę gradient radialny w trybie `overlay` (α = siła×2,6), do tego winieta oddychająca w przeciwfazie.
9. Żar: `P.particles` w trzech grupach (lewa x 0–360: 20, prawa 1540–1920: 20, środek: 9), y od 1110 do 120,
   `life` 5,5 s; jasny rdzeń r 2,6–5,4 i poświata 3,6× α 0,32, migotanie `0.3+0.7|sin(6t+1.9i)|`, wejście i wyjście
   `sin(q·π)`, tryb `lighter`.
10. Postać: `RIG.girl({cup:k})` daje odchylenie głowy przy piciu, rękę licz sam:
    `RIG.ik2(G.A.shoulder, cup+(34,10), 170, 128, -1)`. Dolna część włosów coraz słabiej idzie za obrotem głowy
    (funkcja `HB`), żeby przy piciu nie machały całe. Kot: kotwice z `RIG.cat` (głowa, oczy, nos, wnętrze ucha,
    pręgi, `tailPts`) i własne ciało w kształcie gruszki z białą piersią i łapami; ogon trzema obrysami (fuzz, ink,
    pomarańcz) z pręgą co 4 punkty; mrugnięcie z `P.choreo(lt, t).blink`.
11. Skala w kadrze: całego kota zmniejsz do 0,86 wokół stóp (540, 905) przez `translate→scale→translate` (`RIG.cat`
    zostaje w s=1); uszy schodzą z y≈535 na y≈582, ~30 px od dolnej ramy malowidła (550).

## Co się rusza
- Ruch główny: postać trzyma naczynie w powietrzu i podnosi je do ust: `hold=(1084,506)` → `mouth=HP(1224,380)`,
  postęp `k = choreo(max(0,lt−0.95)).cup` (krzywa przesunięta o 0,95 s), k=1 przy lt≈1,85.
- Bizon i koń biegną: dwie pozy nóg na zmianę co 7 klatek, `ph = floor(t·60/7)%2`; podskok 9 px w pionie, ±3 px
  w poziomie, głowa ±0,12 rad wokół szyi; koń w przeciwfazie do bizona.
- Ogień: siła `0.14+0.11·noise(9.5t)+0.04·sin23t+0.03·sin37t`, środek wędruje ±60 / ±36 px wokół (1000, 540).
- Negatywy dłoni pulsują: na każdym ciepły gradient r=105 (`lighter`), α = `0.2·clamp(0.5+0.9·noise(7t+3.7k))`,
  każdy w swojej fazie.
- Żar (49 drobin) unosi się. Para nad naczyniem: trzy kreski węgla `x0 + sin(13q − 11t + 1.3j)·6`, wysokość 58 px,
  idą za naczyniem.
- Kot: w lt 1,08–1,35 unosi i obraca głowę o −0,16 rad wokół szyi (596, 680), obwiednia `sin(πq)`, `look` 1,5,
  uszy drżą 60 Hz ±0,06 rad.
- Tytuł gaśnie: α = 1 do t 0,933, potem liniowo do 0 w 0,2 s.
- Odcinek w filmie źródłowym: 6 ósemek przy 128 BPM (1,41 s).
- Dowód: średnia różnica klatek 480×270 w odcinku bez przejścia (klatki 21–84) wzrosła z 0,62 do 1,06 (oryginał
  0,86) tylko dzięki ruchom lokalnym, bez migania całego ekranu.

## Przejście-podpis (wejście w ten styl)
- Brak: w filmie źródłowym jaskinia otwiera film. Gdy musisz w nią wejść, zbuduj przejście według ogólnej zasady
  biblioteki: weź proces typowy dla stylu (tu np. ochrę rozpylaną wokół kształtu jak w negatywie dłoni), niech stary
  obraz najpierw nim zajdzie, a nowy wyłoni się z jego kształtu; część widoczna 0,48–0,5 s.
- Wyjście z jaskini to wejście w Egipt: `tiles` (karta `02_egypt`).

## Wydajność
- Ciepła klatka: maks. 22 ms, średnio 21,1 ms; zimna (budowa cache) przy starcie silnika. Warstwa farby składana
  na pełny ekran tylko raz – dzięki temu ~19 ms.
- Do cache: `cave_relief`, `cave_bg`, `cave_figtex`, kafle `cave_inkpat` i `cave_fuzzpat`. Determinizm: ta sama
  klatka renderowana dwa razy daje identyczne piksele.

## Pułapki
- Za mocny człon średniej częstotliwości reliefu (0,35, normalne ×60) zmienia ścianę w moro albo wydmy, a postacie
  wyglądają jak w mundurze moro. Trzymaj 0,16 i ×52.
- Ogień w trybie `lighter` wypala włosy i futro do różowej bieli; używaj `overlay`.
- Farba w `multiply` gubi biel kredy.
- Dłoń z jednego `Path2D` (`addPath` owalu i palców, jedno `fill`) ma dziury: ścieżki o przeciwnym kierunku znoszą
  się przy regule nonzero.
- Gotowa trasa naczynia z `RIG` (stół → usta) startuje przy piersi i nie wygląda jak ręka wyciągnięta w powietrzu;
  użyj własnej trasy jak wyżej.
- Sprawdzaj osobno odstęp części wystających poza szkielet (uszy, ogon) od sąsiednich obiektów.
- Za duży ruch ognia (±0,16, ±90 px) daje drgający obraz (ruch 1,22 przy oryginale 0,86).
- Do poprawy (ze źródła): ciało postaci ma zbyt gładkie krzywe `RIG`; zmniejsz kontur do 12–16 punktów i dodaj
  większe ręczne drżenie. Relief stoi, ogień zmienia tylko jasność; żeby skała „żyła” w świetle ognia, policz dwie
  mapy cieni z różnych kierunków światła i mieszaj je według ognia (+1 złożenie pełnoekranowe).

## Kontrola
- Czy ściana czyta się jako skała z łagodnymi wypukłościami, a nie moro albo piasek?
- Czy każda linia ma pełny rdzeń węgla i rozpylony brzeg, a ziarno wrze co ~1/9 s bez drgania geometrii?
- Czy kolory są „brudne” od skały, a biel kredy nie zniknęła?
- Czy ogień nie wypłukuje nasycenia ochry (`overlay`, nie `lighter`)?
- Czy postać ludzka wygląda pierwotnie (mało punktów konturu, drżenie), a nie jak gładka ilustracja?

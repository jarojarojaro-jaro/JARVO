# Chiński teatr cieni (`34_shadowpuppet`)

Teatr cieni piying: lalki z półprzezroczystej, barwionej skóry z ażurowymi wzorami, przegubami na nitach i kijami
do prowadzenia, oglądane przez płócienny ekran podświetlony od tyłu lampą oliwną. Kolor przechodzi przez skórę jak
przez witraż, nakładki ciemnieją, ruch jest sztywny i skokowy (10 fps), tylko nadgarstek luźno macha. Jakość wzoru:
★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: nakładające się części ciemnieją prawie do czerni,
a 121 ms na klatkę to wolno (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 34_shadowpuppet --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-34_shadowpuppet.jpg`;
kod `$HUASHU/scripts/engine/scenes/34_shadowpuppet.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Kultura chińska i azjatycka: Nowy Rok księżycowy, festiwal, teatr lalek, muzeum etnograficzne: 15–45 s.
- Baśń, legenda albo historia marki („jak to się zaczęło”) z lektorem: 30–60 s.
- Herbaciarnia, restauracja azjatycka, rękodzieło: 10–20 s.

## Nie do
- Szybki montaż i akcja: 10 fps i ciepłe światło lampy to rytm spokojnej opowieści.
- Kolorowe wycinanki bez ekranu i światła: `30_matisse`.
- Temat bez związku z kulturą, w którym styl byłby tylko egzotyczną ozdobą: wybierz styl neutralny dla marki.

## Cechy stylu (sprawdzalne)
- Ekran: radialny gradient `#fff6d6 → #f2d7a0 → #cf9a58 → #7a4a20`. Lampa: `fl = 0.5·noise(3ts) + 0.3·noise(9ts)`,
  ts w krokach 15 fps; środek światła dryfuje ±26/±18 px, gorący punkt r 260+40·fl. Faktura płótna 3 px.
- Kolory skóry: czerwony `#c0352a`, zielony `#2f7d4c`, bursztyn `#d99a2e` (blond włosy = bursztynowa skóra), żółty
  `#e2bd4a`, niebieski `#2c5a8a`, pomarańcz `#d9782a` (kot); brzeg `#3a160a`.
- Element `piece(g, path, col, carve)` (w bibliotece `PAINT.piece(g, path, col, carve, { edge = 5, line, lw = 2.6 })`):
  - wypełnij kolorem;
  - w `clip` wytnij wzór `destination-out`;
  - w `clip` obrysuj tym samym kolorem linią 2×edge („brzeg skóry”, żeby wzór nie przeciął konturu);
  - obrys 2,6 px ciemnobrązowy `#3a160a`.
- Wzory ażuru (`PAINT.carve`): kropki „ikra” (`dots`) s14–22, r3–3.5; kwiaty z 5 płatków (`flowers`) s36–46;
  chmurki – małe spirale Archimedesa (`clouds`), linia 3.4, s24–40; kratka (`lattice`) s26–32; nacięcia (`lines`)
  grubość 3–7.
- Odbicie na ekranie `stamp(layer)` (`PAINT.stamp`): najpierw cień `multiply` α0.28, blur 6 px, przesunięty o (7,5)
  (lalka nie przylega całkiem do ekranu), potem `multiply` sam element. Prześwit = kolor ekranu × kolor skóry,
  nakładki same ciemnieją.
- Twarz kobieca (rola dan): po narysowaniu włosów cała twarz wycięta `destination-out`, został tylko obrys twarzy;
  do tego oczy feniksa (długa linia uniesiona ku skroni, dolna powieka, kropka źrenicy), brwi jak liść wierzby,
  usta kropką.
- Kot rudo-biały: rudy = ruda skóra; biała pierś, pyszczek, łapy = **całkiem wycięte, został tylko brzeg skóry**;
  pręgi = nacięcia. Zasada dla każdego stylu sylwetkowego i ażurowego: biel się wycina.
- Kije: linia 5 px ciemnobrązowa, blur 1,2 px, `multiply`; od szyi, nadgarstka, grzbietu kota, głowy kota i motyla
  w dół do krawędzi kadru.
- Krój plakietki we wzorze: `LXGWWenKai-500` → u nas Caveat-600 (podmienia `huashu_pl.js`).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 34_shadowpuppet`. `P` = `PAINT`
   (`paint.js`, `render.js` z `P.piece`/`P.carve`/`P.stamp`), `RIG` (`RIG.smooth`, `RIG.taper`), `U.stepTime`.
2. Ekran: radialne światło lampy, gorący punkt knota w `screen`, faktura płótna w cache (`py_weave`).
3. Rekwizyty (okno-krata, stół, wazon z kwiatami, krzesło z kwadratowym oparciem) raz do cache (`py_props`).
4. Motyl, kot, dziewczyna: każda grupa na osobnym płótnie poza ekranem, każdy element przez `piece`, potem całe
   płótno przez `stamp` na ekran.
5. Nity w przegubach → kije → drewniana rama (cache `py_frame`).

## Co się rusza
- Klatkaż 10 fps (`U.stepTime(t, 10)`): sztywne prowadzenie na kijach. To styl, nie zacięcie.
- Dziewczyna kołysze się cała wokół (1260,930) o ±0.012 rad; głowa obraca się wokół nitu szyi o ±0.06.
- Podnoszenie filiżanki w 10 fps; luźny nadgarstek: `dangle = 0.35·sin(11·ls)·(1 − 0.6·cup)`, filiżanka macha
  razem z dłonią.
- Kot kiwa głową wokół szyi: `0.1·sin(6ts) + 0.05`. Ogon z 4 członów na zawiasach, każdy względem poprzedniego
  `0.3·sin(7ts − 0.9i) + 0.38` (koniec ogona spóźnia się jak bicz).
- Zawieszka z koralików (buyao) we włosach się kołysze; motyl odwraca skrzydła przez scaleX w 12 fps (też na kiju).
- Lampa: plama światła na całym ekranie skacze.
- Pole ruchu 6,8%.

## Przejście-podpis (wejście w ten styl)
- `lampGlow`, 0,4 s (`cx 960, cy 470`): zapalenie lampy za ekranem. Stary obraz gaśnie jak lampa
  (`multiply rgba(70,34,12, min(1, 2.2p))`); z centrum zapala się światło: nowy obraz w radialnej masce
  `destination-in` (do 0.55R pełny, krawędź przezroczysta), `R = 1500·inOut(seg(p, .12, 1))` z drganiem płomienia
  ±7%; do tego ciepła poświata `lighter` z jasnością sin(πp) i mały płomyk w środku.

## Wydajność
- Ok. 121 ms na klatkę (każda grupa na osobnym płótnie, dużo `multiply`).
- Cache: faktura płótna (`py_weave`), rekwizyty (`py_props`), rama (`py_frame`). Koszt robią osobne płótna
  i `multiply` dla każdej grupy; grupy, które się nie nakładają, możesz złożyć na jednym płótnie.

## Pułapki
- Noga stołu na spódnicy: po `multiply` czerwony × zielony daje prawie czarny trapez. W teatrze cieni nakładki
  ciemnieją i to jest prawdziwe, ale nie stawiaj ich w punkcie uwagi – odsuń nogę stołu.
- Przednie łapy kota jako jeden rudy prostokąt zakryły białą pierś. Dopiero dwie prawie całkiem wycięte białe łapy
  dały kota rudo-białego.
- Kije przecinające postać robią bałagan. Kij idzie od elementu w dół i na zewnątrz, nigdy przez inną postać.

## Kontrola
- Czy elementy prześwitują (multiply), a ażur ma ciągły brzeg i nie przecina konturu?
- Czy ruch jest skokowy w 10 fps, a nadgarstek luźno macha?
- Czy białe części są wycięte (dziury z brzegiem), a nie zamalowane?
- Czy w punkcie uwagi nie ma czarnych plam z nakładek?
- Czy kije nie przecinają innych postaci?

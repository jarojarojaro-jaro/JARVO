# Klimt, złoty okres (`18_klimt`)

Płatkowe złoto na całej ścianie, płaska złota szata pełna ornamentów (spirale, oczy, koła, czarno-białe prostokąty)
i realistyczna, miękko cieniowana twarz. Ten kontrast płaskiej dekoracji i żywej skóry to cały Klimt („Pocałunek”,
„Portret Adele Bloch-Bauer I”, 1907). Jakość wzoru: ★★★ (rozpoznawalny od razu, gotowy do użycia); słabość wzoru: dłoń
na stole nie łączy się z rękawem (przebij ją).
Wzór: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" wzor 18_klimt --czasy 0.3,0.6,0.9 --arkusz out/wideo/wzor-18_klimt.jpg`;
kod `$HUASHU/scripts/engine/scenes/18_klimt.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz technikę,
nie scenę.

## Do czego
- Luksus: jubiler, złotnik, perfumy, wino, czekolada premium: spot 5–15 s.
- Zaproszenie na bal, galę, ślub, jubileusz; opera, filharmonia, Wiedeń, secesja: 10–20 s.
- Portret osoby (twarz realistyczna, strój jako ornament): podziękowanie, laudacja, wspomnienie.

## Nie do
- Marka minimalistyczna albo technologiczna: `style-motion`, karta `zorza-szklo`.
- Secesja plakatowa bez złota (Mucha): `10_nouveau`; złoto średniowiecznego rękopisu: `05_gothic`.
- Kadry z dłońmi na pierwszym planie, dopóki nie poprawisz połączenia dłoni z rękawem.

## Cechy stylu (sprawdzalne)
- Złoto per piksel: `f = 0.5 + fbm(x·.004)·0.55 + noise(x·.003, y·.08)·0.5 ± 0.05`, interpolacja
  `[120,78,18] → [196,148,52] → [246,216,128]`; co 96 px bardzo słaby kwadratowy szew (złoto kładzione płatkami).
- Ściana: złoto × mała mapa fbm 480×270 powiększona w `multiply` (brązowo-złote plamy jak tło „Pocałunku”) + 9000
  drobin złotego i ciemnego pyłu.
- Szata: 150 losowych punktów w czterech rodzajach:
  - koncentryczne koła w trzech kolorach (30%): czerwony-biały-niebieski, niebieski-złoty-czerwony, fiolet-biały-złoty;
  - złote spirale na ciemnobrązowym tle (32%), każda obraca się ±3 rad/s;
  - oczy jak oko Horusa (22%), mrugają po kolei;
  - skupiska białych kropek z czerwonym środkiem (16%).
  Dół szaty: 60 pionowych czarno-białych prostokątów ze złotym obrysem (język szaty mężczyzny z „Pocałunku”).
- Twarz i dłonie: gradient radialny (blik `#fbe8da` → `#f0cfb8` → `#d8a88c` → brzeg `#b88068`), rozmyty rumieniec
  i cień oczodołu, tylko blady kontur 1,2 px. Szata ma ciemny obrys 3 px.
- Okno: „Las brzozowy” z 2600 eliptycznych kropek w kolorach jesieni i 6 pni brzozy z czarnymi plamami. Kwietna łąka
  pod stołem: 260 kwiatów z kół, bliżej większe (6→20 px). Stół w czarno-białą szachownicę (Wiener Werkstätte).
- Kot: pomarańczowy, złote spirale tylko na tułowiu (46 sztuk), na pyszczku żadnych.
- Napisy wzoru: tytuł `LXGWWenKai-500` → u nas `Caveat-600` (nakładka), podtytuł `Marcellus-400` (ma polskie znaki).

## Jak go zbudować
1. Szkielet: `@@PY@@ "$HERMES_HOME/scripts/malarz.py" nowy out/wideo/src/film --styl 18_klimt`. Biblioteki z
   `/_lib/huashu/lib/`: `util.js`, `paint.js` (`PAINT.fbm`, `PAINT.noise`, `PAINT.mix`, `PAINT.cached`,
   `PAINT.scratch`, `PAINT.particles`), `kit.js` (`KIT.choreo`, `KIT.label`), `rig.js` (`RIG.girl`, `RIG.cat`,
   `RIG.drawCat`). Złoto to ten sam pomysł co w `05_gothic`: per piksel, raz, do cache.
2. Kolejność: złota ściana (cache `kl_gold`, `kl_wall`) → migotanie czteroramiennych gwiazdek pyłu (`lighter`) → okno
   z brzozami → czarno-biała rama okna ze złotem → kwietna łąka → stół → skośny pas światła (przed postaciami, więc
   postacie go zasłaniają) → kot → złota szata → realistyczna twarz i dłonie → wianek z kwiatów → złote rękawy
   i kubek → złota para.
3. Szata: najpierw wszystkie ornamenty na jedno pomocnicze płótno (`PAINT.scratch('kl_pat')`), potem raz nałóż je na
   sylwetkę `source-in`, na końcu obrys 3 px.
4. Twarz i dłonie osobno: gradient radialny, rozmyty rumieniec, cień oczodołu, cienki kontur.

## Co się rusza
- Oczy na szacie mrugają po kolei: oko jest zamknięte, gdy `sin(2.2t+φ) > 0.86`; spirale się kręcą.
- Pas światła: 520 px szerokości, α .24, pochylony `transform(1,0,−0.45,1)`, `lighter`, przechodzi **jednostajnie**
  od −200 do 2300 w 1,15 s.
- Pył złota: 420 drobin, czteroramienna gwiazdka, gdy `sin(t·sp+φ) > 0.55`, promień `s·(0.6+1.1a)`; unosi się
  26 px/s.
- 34 płatki złota (kwadraty i koła, złoty gradient) obracają się i spadają 150 px/s.
- Kwiaty łąki kiwają `sin(4.2t+φ)·0.35r`; w oknie 14 liści spada, obracając się.
- Picie z kubka, złota para.

## Przejście-podpis (wejście w ten styl)
- `goldLeaf`, 0,5 s, środek w głowie postaci (1300,380) (`TRANSITIONS.goldLeaf`): kwadraty 72 px kładą się spiralą
  (kolejność = odległość od głowy×0.78 + kąt×0.12 + los×0.08). Dla każdego `q = (1.32p − key)/0.32`: przy q < 0.5
  płatek spada z 1,3× z obrotem na swoje miejsce, złoty refleks przesuwa się z q, na płatku wytłoczona spirala, oko
  albo koła; przy 0.5 < q < 1 złoto blednie i odsłania nowy kadr. Wyrasta z kładzenia płatków złota.

## Wydajność
- Źródło nie podaje ms na klatkę.
- Cache: `kl_gold`, `kl_wall`, `kl_mott`, `kl_win`, `kl_table`. Złoto per piksel licz tylko raz.

## Pułapki
- Ornamenty nakładane `source-in` jeden po drugim kasują się nawzajem (cała szata znika). Najpierw wszystkie na jedno
  płótno, potem jeden `source-in`.
- Pas światła przy α .38 wygląda jak flara obiektywu: trzymaj .24.
- Za duże gwiazdki pyłu wyglądają jak ozdoby choinkowe: promień `s·(0.6+1.1a)`, nie `s·(1+2.2a)`.
- Spirale na pyszczku kota czytały się jak wysypka: tylko tułów, 46 sztuk.
- Za mało ruchu: mruganie jest przerywane, pas światła miękki. Pierwsza wersja miała 20 z 36 par stojących klatek;
  płatki złota, unoszący się pył i mocniejsze kiwanie kwiatów (0.18 → 0.35) zbiły to do 0 z 36.

## Kontrola
- Czy twarz jest realistyczna (gradient, cienki kontur), a szata płaska (obrys 3 px)?
- Czy szata jest cała (ornamenty nie zniknęły) i oczy mrugają po kolei?
- Czy pas światła przechodzi równo w 1,15 s i nie wygląda jak flara?
- Czy w każdej parze sąsiednich klatek coś się rusza (płatki, pył)?
- Dowód z wzoru: różnica klatek 0,45↔0,9 s = 32,9% (głównie pas światła), mediana sąsiednich 0,40%.

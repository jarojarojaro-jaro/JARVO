# Postacie: człowieka maluje model, kod składa

Postać to najczęstsza słabość filmów malarskich z kodu. Ta karta mówi, którą z trzech dróg zrobić postać i jak
złożyć ją z obrazem. U nas postać jest neutralna albo jest postacią marki klienta (kolory, strój, cechy z brand
kitu); nigdy wizerunek realnej osoby. Metoda całości: `metoda.md`.

## Trzy drogi

| Droga | Co to jest | Dobra do | Słabość |
|---|---|---|---|
| **A Kod rysuje** | szkielet i kształty w Canvas | postacie geometryczne, makieta ruchu | złożona twarz wychodzi słabo |
| **B Gotowa biblioteka klatek** | zatwierdzone klatki postaci wklejane w scenę | stała, spójna postać w wielu filmach | bibliotekę trzeba zgrać ze stylem sceny |
| **C Klatki AI w stylu filmu** | model maluje klatki ruchu w stylu tego filmu, zielone tło, wycięcie, kod składa | postać, która ma należeć do obrazu | koszt generacji, kontrola spójności |

Ludzie i postacie uczłowieczone: B albo C. Postacie geometryczne mogą zostać w kodzie. Znane słabości postaci
w danym stylu opisuje karta stylu. Efekt drogi C widać we wzorach gramatyk:
`python3 $HERMES_HOME/scripts/gramatyka.py wzor kurzgesagt --arkusz out/wideo/wzor-kurzgesagt.jpg` i `… wzor tablica …`.

## B: wklejanie gotowej biblioteki klatek

- Biblioteka to Twoje zatwierdzone klatki postaci (np. machanie, ciągnięcie): 8 przezroczystych PNG na ruch.
  Ogólne ruchy przygotowujesz sam. Klatki z demo długiego zwoju (`scripts/engine/demos/long_scroll/frames/`)
  przedstawiają postać autora biblioteki i nie są zainstalowane w Jarvie.
- Silnik wczytuje klatki przy starcie jako zasoby obrazów. Klatkę wybiera `floor(t*9)%8`: animacja ograniczona,
  bez klatek pośrednich.
- Kotwica: środek stóp. `face=-1` odbija poziomo.
- Klatka dostaje materiał filmu: w Vox biały brzeg wycinanki i cień; w stylach pociągnięć jeszcze jedna warstwa
  drobnych pociągnięć na klatce przez `source-atop`.

## C: klatki w stylu filmu

1. **Generacja.** Model obrazu z referencją (`image_generate`; zasady promptu: skill `generacja-ai` Studia, limity
   u Wideografa w `wideo-ai`: domyślnie 8 obrazów na kartę). Przy wielu obrazach po kolei, nie równolegle.
   Referencja: arkusz postaci z trzech stron albo klatka-matka z biblioteki. W prompcie:
   - **gramatyka formy stylu**, nie samo „w stylu XX”: Kurzgesagt to jednolite płaszczyzny bez obrysu, cień o ton
     ciemniejszy w tym samym odcieniu; Vox to czarno-białe zdjęcie z wycinka prasowego w rastrze i biały brzeg
     wycinanki; tablica to czarna linia markera i pomarańczowe kreskowanie; Monet to plamy światła krótkimi
     pociągnięciami;
   - **poza zgodna z ujęciem** („bokiem, zwrócona w prawo, wyciąga rękę i wskazuje w prawo”);
   - **ruch jako arkusz klatek** w jednym obrazie: 4×2, osiem klatek; liczba klatek na początku promptu; „ta sama
     postać” pilnuje spójności; podaj tylko pozy kluczowe, pośrednie dorysuje model; „każda klatka stoi na dole
     swojej komórki, pośrodku, w tej samej wielkości”;
   - **zielone tło `#00B140`** (jasne elementy postaci, np. biały strój, wykluczają białe tło);
   - **stałe cechy postaci dosłownie**: kolor i krój stroju, dodatki, proporcje (np. duża głowa, małe ciało).
     Kolor pisz twardo: model lubi zamieniać czystą biel na jasną szarość, więc „czysto biały”, nie „biały”.
2. **Sprawdzenie, czy to generacja.** W katalogu wyników przybyło tyle plików, ile generacji, a `.info` PNG jest
   puste (obraz sklejony w ImageMagick ma `date:create`). Każda generacja w `out/wideo/src/generacje.jsonl`.
3. **Wycięcie i cięcie na klatki** (`malarz.py`, port ich `key_split.py` i `key_green.py`; ich `uv` nie używamy):
   ```sh
   # zielone tło → przezroczystość, usunięcie zielonej poświaty, cięcie na pozy po pustych kolumnach
   python3 $HERMES_HOME/scripts/malarz.py potnij out/wideo/src/surowe/chod.png --out out/wideo/src/klatki/chod
   #   → chod_0.png, chod_1.png, …; --pick 2 zapisuje tylko trzecią pozę (chod.png)
   # linia z tablicy na białym tle: bez wycinania, samo przycięcie; w scenie wklejasz z multiply
   python3 $HERMES_HOME/scripts/malarz.py potnij out/wideo/src/surowe/tablica.png --out out/wideo/src/klatki/tablica --white
   # postać ma zostać w miejscu z klatki (warstwy drogi B): przycięcie z zapisem pozycji w sprites.json
   python3 $HERMES_HOME/scripts/malarz.py wytnij out/wideo/src/surowe/*.png --out out/wideo/src/sprites
   ```
   `potnij` tnie tylko po kolumnach: pozy muszą dzielić pasy tła (przerwy węższe niż 12 px łączą pozy,
   kawałki węższe niż 40 px odpadają), a pozy jednej kolumny zostają razem. Arkusz 4×2 najpierw przetnij na dwa
   rzędy (np. `ffmpeg -i arkusz.png -vf crop=iw:ih/2:0:0 gora.png` i `crop=iw:ih/2:0:ih/2` dla dołu), potem tnij
   każdy rząd.
4. **Składanie.** Kod decyduje tylko o położeniu, wielkości, kierunku, chwili zmiany klatki i materiale.
   Przedmioty interakcji (kamyki, kręgi na wodzie, rekwizyty) nadal rysuje kod i wyrównuje do położenia dłoni.

W RAPORT.md zaznacz, które postacie i klatki są z AI.

## Kiedy postać może rysować kod

Postacie geometryczne (klocki, terminal, robot, ptaszek, kot), sylwetki, minimalne ludziki-znaki (ludziki
w stylu Haringa, ludzik z patyków na tablicy). Szkielet `RIG` z `$HUASHU/scripts/engine/lib/rig.js` (dziewczyna,
kot) zostaje też jako:
- **odniesienie ruchu**: gdzie jest dłoń, gdzie stopa w danej chwili; z tego bierzesz punkty zaczepienia klatek AI
  i przedmiotów interakcji;
- **makieta**: próba ruchu i rytmu, zanim zamówisz klatki;
- **postać w stylach geometrycznych** (Bauhaus, piksel, pop-art), gdzie przechodzi przez renderer stylu
  (`metoda.md`, rozdz. 6).

## Kontrola
- Czy postać czyta się od razu i jest tą samą postacią w każdej klatce i każdym stylu?
- Czy przeszła przez materiał stylu (pociągnięcia, ziarno, papier, raster), czy wygląda jak naklejka?
- Czy stopy stoją na podłożu (kotwica w środku stóp), a dłoń trafia w rekwizyt?
- Czy klatki zmieniają się równo (`floor(t*9)%8`), bez przeskoku rozmiaru między klatkami?

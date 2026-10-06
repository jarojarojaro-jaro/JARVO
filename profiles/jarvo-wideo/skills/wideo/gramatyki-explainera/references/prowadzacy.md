# Rysunkowy prowadzący (`prowadzacy`, w kodzie `y6_presenter_explainer`)

Rysunkowy prowadzący przez cały film łączy kartki, wykresy i słowa-klucze w jedną opowieść: on mówi i reaguje, plansza za nim zmienia się co myśl. **Tylko wzór i metoda: nie ma klipu, `szablon` ani spec; postać prowadzącego trzeba mieć własną** (marki klienta albo neutralną), lektora też.

Kod-wzór: `$HUASHU/scripts/engine/reference_films/spacex/` (MIT; migawka kodu filmu o 24 latach SpaceX), wersja z prowadzącym w `spacex_lin/`: `common.js` (biblioteka `window.LIN`), `presenter_meta.js` (sama struktura tabeli klatek), `tools/prep_presenter.py`, sceny `scenes/s01.js`–`s12.js`, tabela odcinków `eras_lin.js`, przejście `transitions/lin_page.js`. **Sam się nie renderuje**: brak klatek postaci (sprite'ów), ich metadanych, lektora i promptów do generowania; teksty i liczby to historyczny materiał roboczy, nie aktualne fakty o SpaceX do cytowania. Wzór pożycza gramatykę, nie wygląd prawdziwych osób ani znaków kanałów; Ty też ich nie kopiuj. (Plik `spacex_wb/assets/strokes.js` jest na licencji Arphic, nie MIT: `instaluj huashu` go nie pobiera, nie przenoś go.)

## Kiedy
- Historia firmy albo branży, mechanizm produktu, wyjaśnienie z reakcją emocjonalną (zdziwienie, „uwaga”, radość z wyniku).
- Marka ma postać (maskotkę, rysunkowego prowadzącego) i gotowe klatki jej póz.
- Dłuższy explainer, w którym jedna twarz prowadzi widza przez wiele plansz.
- Przykłady: „20 lat firmy w 5 minut” z maskotką marki, kanał edukacyjny banku z rysunkowym doradcą, wyjaśnienie, jak działa produkt, z reakcjami prowadzącego na liczby.

## Nie do
- Nie masz własnych klatek postaci (cała postać, popiersie, mowa, chód): użyj `historyjka` (postać rysowana kodem, neutralna) albo gramatyki bez postaci.
- Czyste dane i trendy: `wykresy`. Mechanizm matematyczny: `3b1b`. Krótka rolka z jedną myślą: `kinetyczna`.
- Szybki klip z gotowego spec: tu każdy film to własna strona i własna praca.

## Gramatyka (z kodu-wzoru)
Źródła: karta `y6_presenter_explainer`, `reference_films/spacex/README.md`, `spacex_lin/common.js`.

- **Plansza.** Kremowy papier z delikatną siatką kropek (`#F8F2E6`, kropki `#E4DAC6`); płaskie „sympatyczne” ikony informacyjne (ciemny równy obrys, płaskie wypełnienie, przesunięty twardy cień jak naklejka); słowa-klucze w kolorowych zaokrąglonych ramkach albo na zakreślaczu; ręczne strzałki, obwódki i podkreślenia, które „gotują się” (drżą) 8 fps; jedna myśl na ekran.
- **Paleta.** Tusz `#2B2A33`, tekst drugi `#6E6878`, wyciszony `#B9B2A6`, czerwień `#F25F5C` (ciemna `#C9413F`), żółć `#FFD447`, zakreślacz `rgba(255,214,64,0.78)`, niebieski `#4C8DF6` (jasny `#DCE9FF`), turkus `#22B39C` (jasny `#D4F2EB`), fiolet `#8A72F0`, pomarańcz `#FF9F43`, zieleń `#3CB371`, cień `rgba(43,42,51,0.14)`. U nas kolory postaci i akcentów z marki.
- **Kroje.** Wzór pisze wszystko PuHui-Heavy (i inne grubości PuHui) → w Jarvie Inter tej samej grubości (Heavy = 800).
- **Warstwy.** Każda scena rysuje „stronę” → silnik robi przejście strony → nakładka całego filmu (`GLOBAL_OVERLAY`) rysuje pasek u góry i prowadzącego. Prowadzący i pasek idą za czasem całego filmu, więc są ciągłe przez przejścia: `transitions/lin_page.js` przewraca tylko stronę.
- **Układy i plany.** Rozpisz z góry: prowadzący z boku, liczba na cały ekran, porównanie lewo/prawo, prowadzący wchodzi w wykres, zbliżenie reakcji. **Nie trzymaj przez cały film „postać z lewej, wykres z prawej”.** Układ i plan planuj przed animacją: późniejsze przesuwanie postaci nie naprawi monotonnego scenopisu.
- **Wejście i wyjście elementów.** `popK`: wyskok z przestrzeleniem od 30% wielkości (`MO.backOut`, 0,38 s, s = 2.2), żeby pierwsza klatka nie była kropką szumu; `inK`: 0,4 s `MO.cubicOut`; `outK`: 0,25 s `MO.cubicIn`, **wyjście szybsze niż wejście**.
- **Postać = klatki AI, ruch = kod.** Klatki generowane AI; kod steruje kotwicą stóp, pozycją, wielkością i zmianą klatek. Wzrost każdej pozy wyrównany do mediany (`BODY` = 780 px od czubka do stóp w pikselach sprite'a; poza siedząca kalibrowana do bioder 530 px, popiersie do piersi 367 px), więc postać nie rośnie i nie maleje przy zmianie pozy.
- **Zmiana pozy.** Twarde cięcie z lekkim wyskokiem (skala 0,93 → 1, `MO.backOut` 0,16 s) i ściśnięciem z odbiciem (`MO.settle`). **Bez przenikania**: różne sylwetki dają podwójny obraz.
- **Usta i gesty.** Mówi albo milczy według czasu lektora; w pauzie usta stoją. Klatki mowy 8,5 fps według wzorca `TALK` (`[1,1,0,1,1,0,1,0,1,1,0,1]`), żeby gest nie drgał w rytm ust; pozy z drugim gestem zmieniają gest co 1,4 s mówienia. Chód pełnymi klatkami kroku, 10 fps (`WALK_FPS`). Inne tryby klatek: `cycle` 3 fps, `bounce` 4 fps (radość bez szarpania).
- **Życie w bezruchu.** Oddech 0,7% z okresem 1,7 s, lekkie kołysanie wokół stóp, podskakiwanie w rytm mowy, twardy cień postaci (15%, przesunięty o 16/10 px), cień na podłodze (elipsa, 12%).
- **Zbliżenie reakcji.** Osobna karta-naklejka z popiersiem (wejście `MO.backOut` 0,28 s, wyjście 0,18 s); pełna postać w tym czasie znika. Plan naprawdę się zmienia, to nie najazd. Zbliżenie zawsze z klatek popiersia, nigdy z wyciętej i powiększonej pełnej klatki.
- **Pozycja i ruch po planszy.** Klatki kluczowe `cast(id, [{t, pose, fr, x, y, s, flip, walk, glide}])` w czasie lokalnym odcinka; `walk` = przejście z poprzedniej pozycji (`MO.sineInOut`), `glide` = przesunięcie i skalowanie bez chodu (`MO.cubicInOut`: przy dużym obrazie postać chowa się w róg, potem wraca). Domyślnie x = 300, y = 908, s = 0,66.
- **Liczby.** Liczba staje w chwili, gdy lektor ją czyta. W trakcie liczenia bez „ponad”, „+” i podobnych twierdzeń; kółko wyróżnienia dopiero po zatrzymaniu liczby. Pauzę po kulminacji planuj już w scenariuszu i w nagraniu lektora.
- **Jedno źródło czasu.** Pasek u góry (oś lat w `hud`, rok z `yearAt`), napisy i tytuł sekcji czytają ten sam czas. Pasek wchodzi w 0,5 s, schodzi w 0,4 s.
- **Słowa lektora jako kotwice.** We wzorze `TM.cue(odcinek, 'fragment tekstu')` i `cueN(id, słowo, n)` (n-te wystąpienie słowa, od 0); mowę `speakingAt` liczy z czasów każdego znaku w `timing.js`. U nas kotwice z osi lektora (`os_czasu.json` z `film.py narracja`, `O.bit()` z `/_lib/jarvo/os_czasu.js`), a czas mowy ze słów w `lektor.slowa.json`; żadnych sekund wpisanych w kod.

## Jak zbudować (zamiast spec)
1. Scenariusz i lektor najpierw: `film.py narracja` → `lektor.wav`, `lektor.slowa.json`, `os_czasu.json`. Pauzy po kulminacjach zapisz już w tekście (pusty wiersz = koniec akapitu).
2. Scenopis: dla każdego akapitu układ i plan z listy wyżej; sprawdź, że się zmieniają.
3. Postać: co najmniej dwa plany – cała postać i popiersie; siedzenie i opieranie się tylko wtedy, gdy masz prawdziwe klatki tych póz. Do każdej pozy klatki mowy (zamknięte/otwarte usta), do chodu pełny cykl kroku. Wytnij tło i zmierz kotwicę stóp i wzrost (`tools/prep_presenter.py` pokazuje: arkusz klatek na zielonym tle → wycięcie → środek stóp i wzrost → `p_<poza>_<i>.png` i `presenter_meta.js`; wymaga `numpy` i `Pillow`). Metadane generuj skryptem, nie edytuj ręcznie.
4. Strona filmu (kontrakt jarvo): biblioteki z `/_lib/huashu/lib/*.js`, nakładka `/_lib/jarvo/huashu_pl.js`; z `spacex_lin/common.js` przenieś to, czego potrzebujesz: `cast`, `presenterFrame`, `drawFigure`, `popK`, `hud`, `yearAt` (oraz `kw`, `marker`, `arrow`, `ring`, `card` do planszy).
5. Każdy odcinek: **pierwsza klatka kluczowa `cast` z jawnym `x` i `s`** (bez tego dziedziczy pozycję i wielkość z poprzedniego odcinka i wracają stare błędy).
6. Rysowanie zagnieżdżone: przezroczystość mnóż (`globalAlpha *= …`), nie nadpisuj, żeby zostało zewnętrzne wygaszanie.
7. Najazdy kamerą sceny (`CAM`, wektorowo), nie powiększaniem całej klatki jako bitmapy (wzór robi to funkcją `push`, co łatwo ucina postać i tekst).
8. Pierwsza wersja od razu przez kontrolę kadrowania tekstu: arkusz klatek i `html_wideo.py pomiar` (tekst poza kadrem i pod UI platformy), potem skill `kontrola-wideo`. Pas napisów sprawdź także na jasnej planszy bez napisów.

## Pułapki
- **Postać zasłania tekst albo najazd ją ucina.** Automaty tego nie łapią: oglądaj klatki.
- **Powiększanie całej klatki-bitmapy** łatwo ucina kadr; używaj kamery sceny.
- **Dziedziczenie `x`/`s`/`y` między odcinkami**, gdy pierwsza klatka kluczowa ich nie podaje.
- **Przenikanie póz** = podwójny obraz; tylko cięcie z wyskokiem.
- **Zbliżenie z powiększonej pełnej klatki** jest nieostre; potrzebne klatki popiersia.
- **Udawane pozy:** bez prawdziwych klatek siedzenia czy opierania się nie wstawiaj ich „na oko”.
- **„Ponad”, „+” w trakcie liczenia**, kółko przed zatrzymaniem liczby.
- **Monotonny scenopis:** cały film w jednym układzie.
- **Liczby i fakty ze wzoru:** historyczne, niesprawdzane; fakty tylko z `fakty.json` (brief Sherlocka).
- **Kopiowanie wyglądu prawdziwych osób albo znaków kanałów.**

## Kontrola
- Czy układ i plan zmieniają się między akapitami (są co najmniej cała postać i popiersie)?
- Czy usta ruszają się tylko, gdy lektor mówi, a w pauzach stoją?
- Czy zmiana pozy to cięcie z wyskokiem, bez podwójnego obrazu, a postać ma stały wzrost?
- Czy postać nigdzie nie zasłania tekstu i nie jest ucięta przez najazd (arkusz klatek)?
- Czy liczby stają na słowie lektora, a wyróżnienie przychodzi dopiero po nich?

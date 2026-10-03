# Master prompt: wybór fragmentów na rolki

Czytasz transkrypcję jak redaktor, który szuka momentów zatrzymujących kciuk. Widz nie zna reszty nagrania,
przewija szybko i decyduje w 1–2 sekundy. Rolka ma sens sama w sobie albo nie powstaje.

## 1. Najpierw całość
Przeczytaj całą transkrypcję i wypisz **mapę tematów**: temat · od–do · o czym (jedno zdanie). Dopiero z mapy
wybierasz kandydatów, żeby rolki pokryły różne wątki, a nie pięć razy ten sam.

**Ocena okien.** Transkrypcja jest pocięta na okna ~90 s (`## Okno N`). **Każde** okno dostaje ocenę 0–100 i jedno
zdanie, także słabe (nie pomijasz ich, tylko piszesz, że są słabe). Główne kryterium to **test 2 sekund**: czy
pierwsze 2 s najlepszego momentu w oknie zatrzymają widza, który nie widział nic więcej? Używasz całej skali:
w zwykłym nagraniu większość okien to nie rolka, więc 70+ tylko dla okien, które przechodzą test, a powitania,
organizacyjne, dygresje i pożegnania poniżej 30, nawet przy ciekawym temacie. Kandydatów szukasz w najwyżej
ocenionych oknach **z całego nagrania**: długie nagranie czyta się nierówno i łatwo wybrać wszystko z początku
(`klipy.py sprawdz` ostrzega, gdy wszystkie rolki są z jednej połowy).

## 2. Czego szukasz (typy momentów)
| Typ | Rozpoznasz po | Przykład hooka |
|---|---|---|
| teza pod prąd | „wszyscy mówią X, a…”, „największy mit” | „Większość firm źle liczy marżę.” |
| liczba / lista | konkretne liczby, „trzy rzeczy” | „Trzy błędy, które kosztowały nas 40 tysięcy.” |
| historia z puentą | „kiedyś…”, „pamiętam, jak…”, zakończona wnioskiem | „Klient zadzwonił o 23:40 i powiedział jedno zdanie.” |
| porażka i lekcja | przyznanie się do błędu, co z tego wyszło | „Straciłem pierwszy biznes przez jedną decyzję.” |
| konkretna rada | krok, narzędzie, ustawienie, liczba do zapamiętania | „Ustaw to jedno pole, zanim wyślesz ofertę.” |
| emocja | śmiech, wzruszenie, złość, zaskoczenie w głosie (wykrzyknienia, powtórzenia) | reakcja rozmówcy w pierwszej sekundzie |

Typy mapują się na taktyki skilla `hooki`: teza pod prąd → pod prąd / wspólny wróg, liczba → liczba na start,
historia → historia od środka, porażka → historia od środka / strata, rada → efekt / demonstracja,
emocja → świadek, riposta → pytanie / domyślna odpowiedź. Wypowiedź z konkretnym doświadczeniem mówcy
(„przejrzałem 400 kont”) → autorytet.
| riposta / wymiana | szybka wymiana zdań, pytanie i celna odpowiedź | pytanie prowadzącego jako hook |

## 3. Budowa dobrej rolki
- **Hook (0–3 s):** pierwsze zdanie otwiera pętlę ciekawości albo stawia tezę. Bez wstępów („no więc”, „jak już
  mówiłem”, „wracając do…”), bez zaimków bez odniesienia na starcie („on wtedy…”, „to jest…”).
  Hook rolki ma **trzy warstwy** (skill `hooki`) i każda mówi co innego:
  - **zdanie mówione** = pierwsze zdanie fragmentu (wybierasz, nie piszesz),
  - **obraz** = pierwsza klatka: twarz w emocji, gest, rzecz pokazywana w ręku; nie mówca w pół mrugnięcia,
  - **tytuł-hook** na ekranie **nie powtarza** zdania mówionego: dokłada stawkę, wywołuje odbiorcę albo nazywa
    konflikt (mówca: „Trzy błędy w cenach…” → tytuł „Tracisz marżę?”, nie „3 błędy w cenach”).
    `klipy.py sprawdz` ostrzega, gdy tytuł powtarza pierwsze sekundy mowy.
  **O tym momencie, nie o całym filmie:** tytuł-hook i opis nazywają konkret, który dzieje się w tej rolce
  (narzędzie, liczba, teza, imię, czynność). Tytuł, który pasowałby do każdej rolki z tego nagrania („Jak
  rozwinąć firmę”), jest zły; nie ma czego nazwać → zacytuj najmocniejsze zdanie rolki zamiast streszczać temat.
  Każdemu kandydatowi nadajesz **taktykę** z tabeli 18 taktyk (`taktyka` w planie); wśród wybranych rolek ≥ 3 różne.
  Najlepsze zdanie jest w środku fragmentu? Wolno zacząć od niego (segment 1 = to zdanie, segment 2 = rozwinięcie),
  **jeśli sens się nie zmienia** i oba segmenty są z tego samego wątku.
- **Środek:** konkret (liczba, przykład, obraz), jedna myśl. Pierwsze ~15 s rozwija przesłankę hooka
  (widz zatrzymany na „przestałem wysyłać raporty” zostaje dla „dlaczego”), a nie skacze do innego wątku. Dygresje wycinasz segmentami (do 3 segmentów).
- **Samodzielność:** rolka zaczyna się od zaimka, „to”, „więc” albo od odpowiedzi na pytanie zadane wcześniej →
  przesuń **początek wcześniej**, tam gdzie myśl się zaczyna, albo odpuść kandydata. Nigdy nie naprawiasz tego
  ucinaniem puenty: rolka, która straciła puentę, żeby zmieścić kontekst, jest gorsza od obu.
- **Koniec:** puenta, wniosek albo zdanie domykające; nigdy urwane w pół zdania. Świetnie, gdy koniec zachęca do
  obejrzenia jeszcze raz albo do komentarza.
- **Długość:** 20–60 s; domyślnie 25–45 s. Krócej, gdy myśl jest skończona; dłużej tylko przy historii, która trzyma.

### Cięcia (rzemiosło)
- **Nigdy w środku słowa.** `od` i `do` segmentu stawiasz w przerwie między słowami (czasy słów są w `nagranie.mowa.json`);
  `klipy.py sprawdz` ostrzega „tnie słowo” i mówi, dokąd `zbuduj` dosunie granicę: do przerwy obok słowa (słowo
  zostaje, gdy większa jego część jest w segmencie; zapas to połowa przerwy, najwyżej 0,35 s przed i 0,45 s po).
  Dosunięcie może dodać albo zabrać słowo, więc sprawdzasz, czy zdanie dalej się zgadza; prawdziwe czasy rolki są
  w KLIPY.md.
- **Zapas na krawędziach 30–200 ms:** czasy słów z rozpoznawania mowy pływają o kilkadziesiąt milisekund, więc cięcie
  tuż przy słowie ucina jego początek albo końcówkę. Skrypt sam zostawia ~80 ms przed pierwszym słowem, ~250 ms po
  ostatnim i ~120 ms oddechu po wyciętej pauzie; ręcznie przesuwasz krawędź, gdy słychać ucięcie (szybkie tempo: bliżej
  30 ms, spokojna rozmowa: bliżej 200 ms).
- **Napisy zawsze na wierzchu:** nic (plansza, logo, grafika, tytuł) nie może ich zasłaniać. Tytuł-hook stoi u góry,
  napisy w dolnej części; dodatkowy element kładziesz poza pasem napisów albo w czasie, gdy napisów nie ma.

## 4. Ocena (1–10 na każdej osi)
| Oś | 9–10 | 7–8 | ≤ 6 |
|---|---|---|---|
| hook | zatrzymuje od pierwszych słów | ciekawy, ale potrzebuje 2–3 s | zaczyna się rozbiegiem |
| samodzielność | zero kontekstu z reszty nagrania | jedno pojęcie do domyślenia | odwołuje się do „tamtego slajdu” |
| wartość | widz wynosi konkret (liczba, krok, lekcja) | ogólna, ale prawdziwa myśl | lanie wody |
| emocja | słychać energię, śmiech, napięcie | spokojnie, ale z przekonaniem | monotonnie |
| puenta | mocne zakończenie, chce się wrócić | domknięte | urwane albo rozmyte |
| udostępnienie | „wyślę to komuś” | może ktoś skomentuje | nikt nie podzieli się |

Do rolki trafia kandydat ze **średnią ≥ 7 i hookiem ≥ 7**. Za mało takich? Oddaj mniej rolek i napisz dlaczego
(nie naciągaj ocen). Wśród wybranych: różne tematy i typy, żadne dwie nie robią tej samej puenty ani nie
opowiadają tej samej historii; dwie rolki nie dzielą więcej niż ~20% czasu (`sprawdz` to liczy; wyjątek: świadome
wersje A/B, opisane w KANDYDACI.md).

## 5. Uczciwość (twarde)
- Nie wycinasz tak, żeby zmienić sens: ironia, cytat cudzego poglądu („niektórzy mówią, że…”), zaprzeczenie
  („to nieprawda, że…”) muszą zostać z kontekstem albo fragment odpada.
- Nie sklejasz zdań z różnych wątków w nową tezę. Kolejność segmentów = kolejność w nagraniu, chyba że hook z punktu 3.
- W KLIPY.md są czasy w źródle: każdy może sprawdzić kontekst.

## 6. Na ekran i do opisu
- **Tytuł-hook** (plan: `tytul`): ≤ 6 słów, obietnica albo pytanie, nie zdradza puenty, bez kłamliwego clickbaitu.
- **Opis:** 1–2 zdania, język widza; **hashtagi:** 3–5 (temat, nisza, format), bez zbitek z 30 tagów.
- **Format:** 9:16 domyślnie; 16:9, gdy zlecenie mówi YouTube poziomo / LinkedIn albo nagranie to ekran ze slajdami,
  których nie da się pokazać w pionie.
- **Kadr:** twarz mówcy w górnej połowie kadru pionowego, oczy mniej więcej na 1/3 wysokości. Robi to `zbuduj` sam
  (segment bez `fx`/`fy`), a przy kilku osobach w kadrze idzie za tą, która mówi; własny kadr podajesz tylko dla
  planszy, rzeczy w ręku albo ekranu.

## 7. Zapis
`KANDYDACI.md`: mapa tematów + tabela okien (N, od–do, ocena 0–100, najlepszy moment albo „słabe, bo…”) + tabela
kandydatów (od–do, okno, typ, taktyka, hook: zdanie + tytuł + pierwsza klatka, oceny, dlaczego / dlaczego odpada).
`plan.json`: wybrane rolki (schemat: `plan.md`). Potem `klipy.py sprawdz`.

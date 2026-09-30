# Master prompt: wybór fragmentów na rolki

Czytasz transkrypcję jak redaktor, który szuka momentów zatrzymujących kciuk. Widz nie zna reszty nagrania,
przewija szybko i decyduje w 1–2 sekundy. Rolka ma sens sama w sobie albo nie powstaje.

## 1. Najpierw całość
Przeczytaj całą transkrypcję i wypisz **mapę tematów**: temat · od–do · o czym (jedno zdanie). Dopiero z mapy
wybierasz kandydatów, żeby rolki pokryły różne wątki, a nie pięć razy ten sam.

## 2. Czego szukasz (typy momentów)
| Typ | Rozpoznasz po | Przykład hooka |
|---|---|---|
| teza pod prąd | „wszyscy mówią X, a…”, „największy mit” | „Większość firm źle liczy marżę.” |
| liczba / lista | konkretne liczby, „trzy rzeczy” | „Trzy błędy, które kosztowały nas 40 tysięcy.” |
| historia z puentą | „kiedyś…”, „pamiętam, jak…”, zakończona wnioskiem | „Klient zadzwonił o 23:40 i powiedział jedno zdanie.” |
| porażka i lekcja | przyznanie się do błędu, co z tego wyszło | „Straciłem pierwszy biznes przez jedną decyzję.” |
| konkretna rada | krok, narzędzie, ustawienie, liczba do zapamiętania | „Ustaw to jedno pole, zanim wyślesz ofertę.” |
| emocja | śmiech, wzruszenie, złość, zaskoczenie w głosie (wykrzyknienia, powtórzenia) | reakcja rozmówcy w pierwszej sekundzie |
| riposta / wymiana | szybka wymiana zdań, pytanie i celna odpowiedź | pytanie prowadzącego jako hook |

## 3. Budowa dobrej rolki
- **Hook (0–3 s):** pierwsze zdanie otwiera pętlę ciekawości albo stawia tezę. Bez wstępów („no więc”, „jak już
  mówiłem”, „wracając do…”), bez zaimków bez odniesienia na starcie („on wtedy…”, „to jest…”).
  Najlepsze zdanie jest w środku fragmentu? Wolno zacząć od niego (segment 1 = to zdanie, segment 2 = rozwinięcie),
  **jeśli sens się nie zmienia** i oba segmenty są z tego samego wątku.
- **Środek:** konkret (liczba, przykład, obraz), jedna myśl. Dygresje wycinasz segmentami (do 3 segmentów).
- **Koniec:** puenta, wniosek albo zdanie domykające; nigdy urwane w pół zdania. Świetnie, gdy koniec zachęca do
  obejrzenia jeszcze raz albo do komentarza.
- **Długość:** 20–60 s; domyślnie 25–45 s. Krócej, gdy myśl jest skończona; dłużej tylko przy historii, która trzyma.

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
(nie naciągaj ocen). Wśród wybranych: różne tematy i typy; dwie rolki nie dzielą więcej niż ~20% czasu.

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
- **Kadr:** twarz mówcy w górnej połowie kadru pionowego (fy ~0,35–0,45), oczy mniej więcej na 1/3 wysokości.

## 7. Zapis
`KANDYDACI.md`: mapa tematów + tabela kandydatów (od–do, typ, hook, oceny, dlaczego / dlaczego odpada).
`plan.json`: wybrane rolki (schemat: `plan.md`). Potem `klipy.py sprawdz`.

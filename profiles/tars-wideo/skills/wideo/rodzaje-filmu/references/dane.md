# Dane w ruchu

Liczby są treścią: wykres, ranking w czasie (bar chart race), infografika, statystyki, wyniki, raport jako wideo.
Nie to: dane tylko jako jedna liczba w haku → rodzaj filmu, do którego należy; mechanizm zjawiska → `explainer.md`.

## Wynik
- 15–45 s; 16:9 albo 1:1 (wykresy potrzebują szerokości), 9:16 z pionowym układem; źródło danych na ekranie.
- Jeden wniosek na wykres, powiedziany w tytule albo lektorze.

## Silnik
| Materiał | Silnik |
|---|---|
| wykres liniowy, słupkowy, kołowy, licznik, bar chart race | `chart-animation` (Remotion) |
| infografika z ikonami, sekcjami, strzałkami | `animated-infographic` (Remotion) |
| mapa (trasa, rozkład na terenie) | `remotion-best-practices` (mapy) |
| funkcja, rozkład, algorytm | `manim-video` |
| nietypowa wizualizacja (cząstki = ludzie, skala) | własny HTML (`kontrakt-html.md`) |

## Struktura
| 30 s | Scena |
|---|---|
| 0–3 | **Teza** jako tytuł („Rowery wyprzedziły auta w 2024”) i pierwszy ruch danych |
| 3–20 | **Budowanie**: dane rosną w kolejności czasu albo ważności; kamera prowadzi do zmiany |
| 20–27 | **Moment zwrotny**: zbliżenie, adnotacja, porównanie („2× więcej niż…”) |
| 27–30 | **Wniosek** + źródło danych |

## Rzemiosło
- Dane → piksele jedną funkcją skali; słupki od zera; oś logarytmiczna tylko opisana wprost.
- Etykiety przy danych, nie w legendzie; kolor oznacza kategorię albo akcent, nie dekorację (maks. 1 akcent).
- Liczniki dochodzą do dokładnej wartości (easing), zaokrąglenia jak w źródle, separator tysięcy po polsku (12 500).
- Zmiany rankingu płynne (interpolacja pozycji), bez przeskoków; czas na ekranie w rogu (rok, miesiąc).
- Porównania do rzeczy znanych („jak 3 boiska”) tylko, gdy przelicznik jest prawdziwy.

## Brief (`out/wideo/src/BRIEF.md`)
```
Teza (jedno zdanie) i źródło danych (plik, link, data):   Dane: kolumny, jednostki, zakres czasu:
Typ wykresu i dlaczego:                                    Adnotacje (moment zwrotny, porównania):
Format, długość, marka, lektor tak/nie:
```

## Pułapki
- Dane zmyślone albo „przykładowe” w filmie dla klienta; brak źródła; obcięta oś, która przesadza zmianę.
- Wykres 3D, 12 kolorów, legenda daleko od danych; liczby zmieniające się szybciej, niż da się je przeczytać.

## Kontrola
- Sprawdź 3 losowe wartości na klatkach z plikiem danych; pierwsza i ostatnia klatka zgodne ze źródłem.
- Teza zgodna z danymi (bez nadinterpretacji); źródło i data danych na ekranie i w RAPORT.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py dane --ile 3` (albo `--szukaj "bar chart"`).

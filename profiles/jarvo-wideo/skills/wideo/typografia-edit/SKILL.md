---
name: typografia-edit
description: "Typografia z montażu do nagrania z mową, też za osobą."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, typography, kinetic-typography, captions, edit, talking-head]
    related_skills: [napisy, montaz-nagran, clipmaker, formaty-wideo, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-03"
---

# Typografia jak z montażu

Osoba mówi do kamery, a słowa pojawiają się w rytmie mowy: różne wielkości, kroje, głębia (bliżej, dalej, za osobą),
skos, perspektywa 3D. Ekran żyje, ale **każda zmiana formy ma powód w treści**. Zmiana bez powodu to szum, nie styl.
Plan (`typo` w `<film>.edycja.json`) rysuje ten sam renderer w edytorze HQ, w eksporcie i w moim renderze, więc
właściciel poprawia na osi każde słowo i blok (pas „Typografia”).

## Kiedy użyć
- Nagranie osoby mówiącej (talking head, rolka z `clipmaker`, wywiad w pionie), prośba o „napisy jak u montażysty”,
  „dynamiczne”, „kinetyczne”, „jak w tym przykładzie”, albo prośba z edytora HQ („Ułóż typografię słowo po słowie”,
  „Policz sylwetkę osoby dla bloku…”).
- Nie: film z lektorem i stockiem (tam karaoke z `napisy`), film z samego tekstu bez osoby (`rodzaje-filmu` → typografia).

## Kroki
1. **Plan** (0 tokenów, reżyser z reguł): `python3 $HERMES_HOME/scripts/typografia.py plan <film> [--motyw czysty]
   [--akcent <kolor marki>] [--tempo spokojne|normalne|ostre]`. Projekt powstaje sam z filmu, a zwykłe napisy znikają
   (zostają z `--zostaw-napisy`). Kolory dobiera sam z kadru (sekcja „Kolor”). **Gdy plan już jest, nie układam go
   od nowa:** mógł go poprawić właściciel. `--nowy` tylko na jego wyraźną prośbę; same kolory zmienia
   `typografia.py paleta <film>` (układ i poprawki zostają).
2. **Czytam** `typografia.py pokaz <film>`: każdy blok z czasem, układem i słowami `numer:[waga]tekst`. Numery i `id`
   bloków czytam za każdym razem od nowa (cięcie w HQ robi nowe bloki, np. `b04b`).
3. **Reżyseruję znaczeniem** (tabela niżej): `zmiany.json` → `typografia.py popraw <film> zmiany.json`. Poprawiam tylko
   bloki, które tego potrzebują; poprawek właściciela nie cofam.
4. **Oglądam:** `typografia.py arkusz <film> -o out/wideo/typografia.jpg` → `vision_analyze` (lista „Kontrola”).
   Najwyżej dwie rundy poprawek.
5. **Render:** `python3 $HERMES_HOME/scripts/projekt.py render <film>` → linia MEDIA:, a w odpowiedzi jedno zdanie, że
   wszystko poprawi się w edytorze HQ (pas „Typografia”).

Prośba z HQ o sylwetkę (blok ustawiony „za osobą”): `typografia.py sylwetki <film>` → arkusz tego miejsca → odpowiedź.
Kod 1 = model maski niedostępny (RUNBOOK); wtedy napis jest widoczny w całości i mówię to wprost.

## Znaczenie → forma
| Co mówi osoba | Forma |
|---|---|
| puenta, obietnica, liczba, nazwa produktu | waga 3 (uderzenie): największe, w kolorze z palety; jedno na blok, mniej więcej co trzeci blok |
| ważne słowo, ale nie puenta | waga 2 |
| spójniki, przyimki, zaimki | waga 0 (małe, lekki krój motywu) |
| przeczenie, które zmienia sens („nie”, „nigdy”, „bez”) | co najmniej waga 2, nigdy 0 |
| kwota, procent, liczba z jednostką | liczba i jednostka razem w jednej linii; liczebnik wolno zapisać cyfrą („pięć” → „5”), nic więcej w tekście nie zmieniam |
| wyliczenie, kroki | `kolumna` albo `schodki`, każdy element w swojej linii |
| kontrast „nie X, tylko Y” | X i Y w dwóch liniach albo blokach; Y waga 3, X waga 1–2 |
| myśl, cytat, wspomnienie, ironia | `glebia: -1` (dalej, mniejsze) i kursywa (`playfairI`) |
| zwrot do widza („ty”, „zobacz”, wezwanie) | `glebia: 1` (bliżej), układ `srodek` |
| emocja, energia, krzyk | `skos` albo `rozrzut`, wejście `pop` |
| spokojne wyjaśnienie | `kolumna` albo `srodek`, wejście `maska` albo `ciecie`, bez obrotu |
| ruch, kierunek, przestrzeń („w górę”, „daleko”, „przed nami”) | `3d` (`tilt`) albo `rot` w stronę sensu |
| krótkie mocne hasło (do 14 znaków) przy osobie | `za` (za osobą): osoba zasłania część słowa, głębia jak w kinie |

Rytm robi zmiana, nie dekoracja: ten sam układ najwyżej dwa razy z rzędu; po głośnym bloku cichszy.
Bloki krótsze niż 0,5 s łączę z sąsiednim (`polacz`), długie zdanie dzielę na pauzie (`podziel`).

## Kolor
Kolor bierze się z materiału, nie z motywu. Jeden kolor na wszystkie mocne słowa to błąd (uwaga właściciela).
- **Paleta z kadru** (`plan` i `paleta` liczą ją same, `pokaz` ją wypisuje): dwa akcenty w kontraście z barwami
  sceny, czyli barwy dopełniające rozszczepione. Niebieskie niebo i morze → ciemna czerwień i złoto, zieleń → róż
  i fiolet, ciepłe drewno i skóra → turkus i niebieski, czerwone wnętrze → zieleń i niebieski. Bonus ma kolor, który
  już mocno świeci w kadrze (czerwona czapka); pomarańczowe i złote słowa przy dużej ilości skóry i piasku przegrywają.
- **Wariant z tła:** na jasnym tle (niebo, ściana) ciemny wariant, na ciemnym jasny. Słowo, które nie odcina się
  od tła pod blokiem, dostaje płytkę w swoim kolorze (`tlo`; napis na płytce czarny albo biały z kontrastu).
- **Rozpisanie:** akcenty na zmianę (A, B, A, B…) po mocnych słowach: uderzenie w każdym bloku, który je ma,
  i najważniejsze słowo (waga 2) w co drugim bloku bez uderzenia. Reszta biała. Najwyżej dwa akcenty i biel,
  plus jeden kolor znaczenia, gdy treść go niesie (zielony przy zysku, czerwony przy stracie). Trzeci akcent to chaos.
- Kolor marki: `--akcent` z `@@KNOWLEDGE_DIR@@/brands/<marka>/` (kolory marki są prawem). Marka idzie pierwsza,
  drugi akcent i tak dobieram z kadru.
- Właściciel mówi, jakie kolory chce: `--paleta "#RRGGBB,#RRGGBB"` w `plan` albo `paleta`, albo `"paleta": [...]`
  w `zmiany.json`. Słowa w starych kolorach palety idą za nową, kolory ustawione ręcznie zostają.
- Czerwień nie jest domyślna: wolno ją wtedy, gdy kontrastuje z kadrem (scena chłodna: niebo, morze, zieleń) albo
  jest kolorem marki. Na scenie czerwonej, pomarańczowej i przy dużej ilości skóry nie.

## Krój, głębia, ruch
- Krój zostawiam z motywu („Auto”). W bloku najwyżej dwa kroje, w filmie trzy (główny, lekki, kursywa).
  Odręczny (`caveat`) tylko w motywie `energia` albo jako dopisek; `grunge` tylko w `ulica`; `mono` do kodu i danych.
- Obrót do ±12°, `tilt` do ±35°: dalej słowo przestaje być czytelne na telefonie.
- Czasów słów (`t`, `k`) nie ruszam bez powodu: słowo ma wejść z dźwiękiem. Na cięciu ujęcia wyjście `ciecie`.
- **Za osobą** najwyżej co szósty blok, jedna linia, do 14 znaków; głowa nie może zasłonić najważniejszych liter.
  Plan liczy sylwetkę sam; blok przestawiony w HQ dostaje ją przez `sylwetki`.

## Format `zmiany.json`
Pola bloku: `uklad`, `x`, `y` (kotwica 0–1), `w`, `rot`, `tilt`, `warstwa` (`przod`/`tyl`), `rozmiar`, `wejscie`,
`wyjscie`, `start`, `end`. Pola słowa: `tekst`, `waga` 0–3, `linia`, `glebia` −1/0/1, `kolor`, `kroj`, `styl`
(`wypelnij`, `kontur`, `3d`, `blask`, `tlo`), `wejscie`, `wielkie`, `skala`; `null` przywraca wartość z motywu.
```json
{"bloki": [
  {"blok": "b03", "uklad": "kolumna", "slowa": {"0": {"waga": 2}, "3": {"waga": 3, "tekst": "5 MIN"}}},
  {"blok": "b05", "slowa": {"1": {"glebia": -1, "kroj": "playfairI"}}},
  {"polacz": ["b06", "b07"]},
  {"blok": "b09", "podziel": 2}
]}
```
`popraw` ostrzega, gdy blok ma więcej niż jedno uderzenie, i gdy blok za osobą nie ma sylwetki.

## Kontrola (arkusz, `vision_analyze`)
- Najmniejsze słowo czytelne na telefonie, polskie znaki i liczby poprawne, tekst zgodny z mową.
- Żaden napis nie zakrywa twarzy (poza świadomym „za osobą”) ani stref UI platformy (`formaty-wideo`).
- Kolory z palety kadru, rozpisane na zmianę; żaden akcent nie ginie na tle; nie jeden kolor na wszystko i nie
  więcej niż dwa akcenty poza bielą (plus kolor znaczenia).
- Bloki różnią się układem i wielkością, ale każda różnica ma powód w treści.

## Definition of Done
- [ ] plan w projekcie (`typo`), poprawki właściciela z HQ nienaruszone, `popraw` bez ostrzeżeń albo z wyjaśnieniem,
- [ ] arkusz obejrzany: lista „Kontrola” spełniona,
- [ ] render z linią MEDIA: i informacją, że całość poprawi się w edytorze HQ.

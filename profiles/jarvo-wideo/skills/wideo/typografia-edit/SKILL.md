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
   (zostają z `--zostaw-napisy`). **Gdy plan już jest, nie układam go od nowa:** mógł go poprawić właściciel.
   `--nowy` tylko na jego wyraźną prośbę.
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
| puenta, obietnica, liczba, nazwa produktu | waga 3 (uderzenie): największe, w kolorze akcentu; jedno na blok, mniej więcej co trzeci blok |
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
- **Domyślnie motyw `czysty`:** białe słowa i żółty akcent. Akcent tylko na wadze 3, nigdy na całym bloku.
- **Czerwień nie jest domyślna.** Motywy `kino` i `ulica` (czerwony akcent) tylko na prośbę albo gdy marka jest
  czerwona. Pojedyncze słowo na czerwono tylko, gdy znaczy stratę, błąd albo zakaz, i najwyżej dwa razy w filmie.
- Kolor marki: `--akcent` z `@@KNOWLEDGE_DIR@@/brands/<marka>/` (kolory marki są prawem).
- Najwyżej dwa kolory poza bielą w całym filmie: akcent i jeden kolor znaczenia (np. zielony przy zysku).
  Trzeci kolor to chaos.
- Jasne tło (okno, biała ściana) i nieczytelne słowo: styl `tlo` albo inne miejsce bloku, nie ciemniejszy kolor tekstu.

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
- Kolor tylko na uderzeniach; bez czerwieni bez powodu; najwyżej dwa kolory poza bielą.
- Bloki różnią się układem i wielkością, ale każda różnica ma powód w treści.

## Definition of Done
- [ ] plan w projekcie (`typo`), poprawki właściciela z HQ nienaruszone, `popraw` bez ostrzeżeń albo z wyjaśnieniem,
- [ ] arkusz obejrzany: lista „Kontrola” spełniona,
- [ ] render z linią MEDIA: i informacją, że całość poprawi się w edytorze HQ.

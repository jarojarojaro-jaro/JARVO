---
name: gramatyki-explainera
description: "8 gramatyk explainera: wykresy, tablica, 3b1b, Vox i inne."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, explainer, chart, diagram, whiteboard, kinetic-typography, voiceover, canvas]
    related_skills: [rodzaje-filmu, film-z-kodu, scenariusz, lektor-i-dzwiek, style-motion, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-06"
---

# Gramatyki explainera

Osiem sposobów rysowania fragmentu filmu z lektorem: wykresy jak w The Economist, rysowana tablica, 3Blue1Brown,
kolaż Vox, prezentacja z premiery, historyjka z prostą postacią, typografia kinetyczna i płaski świat Kurzgesagt.
Każda gramatyka to klip: jeden plik spec (JSON) → odcinek animacji o dokładnej długości, z cue przypiętymi do słów
lektora. Silnik kanwy to huashu-art-motion (MIT, 花叔) pod polską nakładką (`/_lib/jarvo/huashu_pl.js`: kroje z ą–ż,
liczby po polsku, neutralna postać), a spec, render i kontrola są nasze (`gramatyka.py`, `html_wideo.py`).

## Kiedy
- Explainer, film z danymi, samouczek albo historia z lektorem (`rodzaje-filmu`: `explainer.md`, `dane.md`), a
  fragment lektora ma jasną robotę: liczby, mechanizm, rozumowanie, lista, produkt, przeżycie, argument z materiałami.
- Wstawka 3–15 s do większego filmu (montaż w `projekt.py`), w poziomie albo w pionie 9:16, także z przezroczystym
  tłem nad nagraniem (`--alfa`).

## Nie do
- Cały film w jednym stylu kina albo w stylu malarskim → `lemo-opuscar` (`film-z-kodu`) albo style motion
  (`style-motion`); tu jest gramatyka fragmentu, nie wygląd całego filmu.
- Animacja z własnym pomysłem spoza ośmiu gramatyk → własna strona HTML (`rodzaje-filmu/references/kontrakt-html.md`);
  biblioteki silnika (`/_lib/huashu/lib/*.js`) i tak możesz w niej użyć (`references/wspolne-zasady.md`, ściąga).
- Prowadzący z klatkami postaci (`prowadzacy`): to tylko wzór i metoda, bez klipu (`references/prowadzacy.md`).

## Przebieg (wszystko samo, bez zatwierdzania po drodze)
1. **Silnik raz:** `@@PY@@ "$HERMES_HOME/scripts/narzedzia.py" instaluj huashu` (ok. 45 MB z gitem, potem sekundy).
2. **Lektor najpierw:** `film.py narracja narracja.txt -o out/wideo/src/lektor.wav` daje `os_czasu.json` (słowa
   z czasem). Fakty i liczby z briefu Sherlocka `out/wideo/src/fakty.json`; zmyślone tylko ze znaczkiem „dane przykładowe”.
3. **Gramatyka fragmentu:** `references/wybor.md` (tabela „ten fragment lektora… → wybierz”). W jednym fragmencie
   jedna gramatyka; film może je zmieniać między fragmentami. Czytasz tylko kartę wybranej gramatyki
   (`references/<nazwa>.md`) i raz `references/wspolne-zasady.md` (12 zasad).
4. **Wzór:** `gramatyka.py wzor <nazwa> --arkusz out/wideo/wzor-<nazwa>.jpg` (stopklatki ich filmu pokazowego,
   ok. 8 s, 2,5–3 razy gęstszego niż prawdziwe tempo). Bierzesz technikę, nie tempo ani teksty.
5. **Spec:** `gramatyka.py szablon <nazwa> [--format 9:16] -o out/wideo/src/klip-<nazwa>/spec.json`. Jeden klip =
   jeden katalog (obrazy obok). Teksty po polsku, krótko (lektor mówi resztę). Cue przypinasz do słów lektora:
   `"slowo": "2024"` (+ `"nth"`, `"offset"`) zamiast `"at"`, klip na osi lektora `"od": "u3"` i `"do": "u3.koniec"`
   (albo sekundy). Pola `data` i rodzaje cue: karta gramatyki; kontrakt: `references/kontrakt-spec.md`.
6. **Sprawdzenie:** `gramatyka.py sprawdz …/spec.json` (kod 0): rodzaje cue, słowa lektora w oknie klipu, czasy,
   obrazy, chińskie znaki, liczby kontra `fakty.json`, pion bez `safe.bottom`.
7. **Stopklatki i poprawki:** `gramatyka.py render …/spec.json --klatki 0.5,2,4,…` → arkusz `klatki/spec-arkusz.jpg`
   oglądasz (vision): polskie ogonki, nic poza kadrem, jeden punkt uwagi, liczby po polsku, kontrola z karty.
8. **Pomiar:** `gramatyka.py pomiar …/spec.json [--platforma tiktok]` (`html_wideo.py pomiar` strony klipu: czas
   czytania, kontrast, strefy UI, liczby bez źródła); błędy poprawiasz albo opisujesz świadomy wyjątek.
9. **Klip:** `gramatyka.py render …/spec.json -o out/wideo/klip-<nazwa>.mp4` (z `--alfa` → `.mov` ProRes 4444).
   Do filmu idzie przez projekt edytora (`film-z-kodu/references/projekt-edytora.md`), z lektorem i dźwiękiem
   (`lektor-i-dzwiek`); przed oddaniem `kontrola-wideo`.

## Zasady, które łamią się najczęściej
- **Klatka odsłonięcia na słowie:** element wchodzi od 0,2 s przed do 0,1 s po swoim słowie; liczba staje
  na słowie, w którym lektor ją mówi (`number`: `offset` 0), tablica pisze ok. 0,5 s po frazie.
- **Jeden punkt uwagi, wejście wolne, wyjście szybkie, postój po zatrzymaniu** (liczba ≥ 0,5 s, puenta ≥ 0,9 s).
- **Prawda w danych:** słupki od 0, oś nie od 0 napisana, jednostka i źródło na ekranie, mnożnik do policzenia
  z liczb na obrazie; zielony = wzrost (`upDown: "us"`, wstawiany sam).
- **Napisy lektora:** `safe.bottom` 700 w pionie, 250 w poziomie (pas napisów, szablon wpisuje sam), `safe.top` pod zakładki platformy (szablon: 140 na TikToka);
  prawego paska przycisków `safe` nie ominie (`kontrakt-spec.md`). Tekst w kadrze kontra wypalone napisy:
  przesuń napisy albo w tym fragmencie ich nie wypalaj.
- **Postać `historyjka`:** neutralna albo w kolorach marki (`"postac"` w spec); usta same z obwiedni lektora.
  Klatek postaci autora silnika (`demos/_shared/hero`) nie używasz w filmach klienta.

## Pliki
- `references/wybor.md`: osiem gramatyk w tabeli, wybór do fragmentu lektora, dwie zasady awaryjne.
- `references/wspolne-zasady.md`: 12 zasad wspólnych, ściąga bibliotek (`MO`, `CAM`, `DG`, `TY`, `CH`, `UI`, `CL`,
  `TOON`) i przejść (`transitions.js`) do własnych stron.
- `references/kontrakt-spec.md`: polecenia `gramatyka.py`, spec, pola cue, `safe`, `number`, `slowo`/`od`/`do`.
- Karty gramatyk: `kurzgesagt.md`, `vox.md`, `tablica.md`, `historyjka.md`, `kinetyczna.md`, `3b1b.md`,
  `prezentacja.md`, `wykresy.md`; `prowadzacy.md` (tylko wzór i metoda).

## Wynik
`out/wideo/klip-<nazwa>.mp4` (albo `.mov` z alfą) o długości z spec, spec i strona klipu w `out/wideo/src/klip-<nazwa>/`,
arkusz stopklatek, `pomiar.json` bez błędów; w RAPORT.md: gramatyka i dlaczego, chwile cue (słowa lektora), źródła liczb.

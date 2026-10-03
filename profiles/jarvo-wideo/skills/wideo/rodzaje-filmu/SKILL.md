---
name: rodzaje-filmu
description: "Rodzaj filmu → jeden plik: silnik, struktura, rzemiosło."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, explainer, motion-graphics, 3d, product, typography, data, logo, story]
    related_skills: [krotki-film, film-z-kodu, montaz-nagran, clipmaker, scenariusz, formaty-wideo, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-03"
---

# Rodzaje filmu

Każde zlecenie filmu zaczyna się od **rodzaju**: od niego zależą struktura, silnik i to, co sprawdzić przed oddaniem.
Czytasz **tylko plik swojego rodzaju** (dwa, gdy prośba wyraźnie łączy rodzaje, np. explainer z wykresami).
Pozostałych nie otwieraj: to półka, nie lektura.

## Indeks
| Rodzaj | Sygnały w prośbie | Plik albo skill |
|---|---|---|
| Explainer | „wyjaśnij”, „jak działa”, edukacyjny, proces, zjawisko, usługa w 3 krokach, tablica | `references/explainer.md` |
| Promo produktu | premiera, reklama aplikacji albo strony, launch, demo UI, keynote, „pokaż funkcje” | `references/promo-produktu.md` |
| Motion graphics | showreel, abstrakcja, pętla, przejścia, brand motion, infinite zoom, „pokaż, co potrafisz” | `references/motion-graphics.md` |
| Typografia | hasło, cytat, manifest, lyric video, słowa w rytm muzyki, animowany tytuł | `references/typografia.md` |
| Dane | wykres, statystyki, ranking, bar chart race, infografika, wyniki, raport w wideo | `references/dane.md` |
| Scena 3D | świat 3D, lot kamery, produkt w 3D, low-poly, shader, Three.js | `references/scena-3d.md` |
| Interaktywne i gry | gra, playable, trailer gry, zapis rozgrywki, interaktywna animacja | `references/interaktywne.md` |
| Logo i intro | animacja logo, intro, outro, sting, belka z nazwiskiem, ikona albo loader Lottie | `references/logo-intro.md` |
| Historia | krótka animowana historia, bohater, bajka, reklama fabularna, „w stylu Pixara” | `references/fabula.md` |
| Reels z tematu | „zrób reelsa o…”, faceless, stock + lektor, lista faktów | skill `krotki-film` |
| Nagranie użytkownika | „zmontuj”, „wytnij”, gadająca głowa, długi materiał na klipy | skill `montaz-nagran`, `clipmaker` |

Niejasne? Rozstrzyga cel z karty: wyjaśnić → explainer, sprzedać → promo, zachwycić → motion graphics,
opowiedzieć → historia. Nadal niejasne: jedno pytanie („ma wyjaśnić, sprzedać czy zachwycić?”).

## Kroki
1. Rodzaj z indeksu → jego plik. Własna animacja HTML (Canvas, SVG, Three.js, GSAP) → też `references/kontrakt-html.md`.
   **Film-wzór** („zrób coś takiego”): `kadry.py wzor wzor.mp4` (klatki co 0,5 s, cięcia, rytm) → rozpisz go na bity
   (przejścia, kamera, kolory, fonty) i przenieś tę strukturę na produkt; treści, logo i assetów wzoru nie bierzesz.
2. **Brief** `out/wideo/src/BRIEF.md` w 6 częściach: **wejścia** (pliki, dane, marka), **kierunek** (styl w 3 zdaniach +
   czego nie ma być), **struktura** (mapa bitów: sekunda → scena → ruch → dźwięk), **budowa** (silnik, format, fps),
   **pułapki**, **start** (pierwszy krok). Szablon pól z pliku rodzaju. Brak wejścia: karta → brand kit → rozsądna
   domyślna nazwana w RAPORT; pytasz tylko o to, bez czego film będzie zły.
   Muzyka: `python3 $HERMES_HOME/scripts/rytm.py muzyka.mp3` → BPM, takty, drop; cięcia i zmiany na taktach.
3. Inspiracje tylko, gdy brief nie ma pomysłu na formę:
   `python3 $HERMES_HOME/scripts/inspiracje.py <rodzaj> --ile 3` (prompty twórców filmów Opus 5.5 z dwóch list, pobierane w locie); `inspiracje.py --drogi` pokazuje, jak naprawdę powstały opisane filmy (droga produkcji z dowodem): sprawdź, zanim obiecasz „jeden prompt”.
   Bierzesz strukturę i chwyty, nie tekst; zainspirowało → autor i link w RAPORT.
4. Scenariusz i lektor (`scenariusz`), silnik z pliku rodzaju (komendy: `film-z-kodu`). **Mapa bitów + 4 kadry
   kluczowe** (arkusz) do oceny, zanim wyrenderujesz całość; potem 2–3 rundy uwag „jak reżyser”, nie od zera.
5. Kontrola z pliku rodzaju, `qa_wideo.py`, `kontrola-wideo` (≥ 85).

## Zasady wspólne
- Pierwsze 2 s: coś się dzieje (ruch, pytanie, liczba), nie logo na czarnym tle.
- Jedna myśl i jedna idea formalna na scenę; jeden system (paleta 3–4 kolory, 1–2 fonty, siatka, grubość linii).
- Czas z `t`, nie z zegara: każdą klatkę da się wyrenderować osobno i zawsze tak samo.
- Prawdziwe dane, UI i fakty; zero zmyślonych liczb, logo i cytatów. Brak danych: mniej konkretu albo pytanie przez Jarva.
- Arkusz klatek przed renderem całości; gotowy film obejrzany jeszcze raz (arkusz z `qa_wideo.py`).

## Definition of Done
- [ ] rodzaj nazwany w RAPORT z uzasadnieniem; przeczytany tylko jego plik (plus kontrakt HTML, gdy dotyczy),
- [ ] `BRIEF.md` wypełniony, wynik zgodny z sekcją „Wynik” pliku rodzaju,
- [ ] kontrola rodzaju odhaczona, `qa_wideo.py` bez błędów, `kontrola-wideo` ≥ 85.

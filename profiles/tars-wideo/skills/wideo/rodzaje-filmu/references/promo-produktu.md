# Promo produktu

Sprzedaje produkt cyfrowy albo fizyczny: premiera, reklama aplikacji, strony, funkcji; keynote, demo UI.
Nie to: jak działa zjawisko → `explainer.md`; samo logo → `logo-intro.md`; nagranie ekranu użytkownika → `montaz-nagran`.

## Wynik
- 15–30 s social (9:16, 1:1, 4:5 naraz), 30–60 s strona i YouTube (16:9); muzyka ~120 BPM, cięcia na bitach.
- Prawdziwe UI i dane produktu, logo i CTA na końcu; opcjonalnie lektor PL + napisy.

## Silnik
| Materiał | Silnik |
|---|---|
| strona albo aplikacja klienta (screenshoty, ruch kamery 2.5D, cięcia na bit, dźwięk) | `video-shotcraft` |
| UI jako jedna forma, która się przekształca (przycisk → loader → karta…) | własny HTML (`kontrakt-html.md`) |
| ciemny keynote, wielka liczba, living screencast | `lemo-opuscar` (`dark-keynote`, `living-screencast`) |
| szybko, tekst + obrazy produktu | HyperFrames `product-launch-video` |
| produkt fizyczny w 3D | `scena-3d.md` |

## Struktura
| 30 s | Scena |
|---|---|
| 0–2 | **Hak:** wynik, liczba albo ból („3 godziny raportu → 30 sekund”) |
| 2–7 | **Problem** w jednym obrazie |
| 7–22 | **3 funkcje = 3 akcje** w prawdziwym UI (kursor klika, pisze, przeciąga); jedna funkcja na 4–5 s |
| 22–27 | **Dowód:** liczba użytkowników, ocena, cytat klienta (tylko prawdziwe, z karty) |
| 27–30 | **Logo + CTA** (adres, „pobierz”), ostatnia klatka czytelna jako miniatura |

## Rzemiosło
- Siatka BPM: co takt coś się dzieje; ważne zmiany na mocnych bitach, drop = najmocniejsza funkcja.
- „Jedna forma, bez cięć”: kolejne stany UI to ten sam element zmieniający rozmiar, promień i kolor; treść wchodzi
  po rozpoczęciu przemiany i znika przed następną (tekst nigdy się nie nakłada).
- Sprężyny z małym przerzutem (nie gumowe); krótki blur przy zmianie treści; kamera przybliża, żeby stan wypełniał kadr.
- Akcent (kolor marki) przenosi element, a nie przejście z czerni; kursor prowadzi oko.
- Pętla: ostatnia klatka = pierwsza (reklamy w feedzie grają w kółko).
- Prawdziwe ekrany: screenshoty od klienta, z karty albo zrobione przez `tars-web`; dane w UI z produktu, nie „Lorem”.

## Brief (`out/wideo/src/BRIEF.md`)
```
Produkt, URL, jedna obietnica (≤ 8 słów):          Odbiorca i platforma:
Stany UI (8–12), które opowiadają historię, i dane w każdym:
Marka: kolory, fonty, akcent, logo (pliki z brand kitu):
Muzyka (BPM, licencja) i siatka: co na którym takcie:
Formaty i długości:                                 CTA:
```

## Pułapki
- Generyczny mockup telefonu z wymyślonymi ekranami; logotypy klientów albo oceny bez prawa i źródła.
- Pięć funkcji w 15 s; tekst mniejszy niż ~4% wysokości kadru; CTA w strefie interfejsu platformy.
- Płatne API (Runway, generatory wideo) bez zgody i limitu z karty.

## Kontrola
- Arkusz: 1 klatka na każdy stan UI; każda funkcja czytelna bez dźwięku; nic nie wchodzi w strefy UI (`qa_wideo.py --arkusz`).
- Liczby i nazwy zgodne z produktem; logo w proporcjach i kolorach z brand kitu; wszystkie formaty wyrenderowane.
- Licencja Remotion (shotcraft) i muzyki w RAPORT.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py promo-produktu --ile 3` (albo `--szukaj "one shape"`, `--szukaj keynote`).

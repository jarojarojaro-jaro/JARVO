# Interaktywne i gry

Wideograf robi **film** o grze albo interaktywnej animacji: trailer, zapis rozgrywki, „attract mode”, demo.
Gra do grania, strona interaktywna, prototyp produktu → `tars-web` przez Jarva (to produkt, nie film).
Jeśli karta chce obu: `tars-web` buduje grę, Wideograf dostaje link albo pliki i robi trailer.

## Wynik
- Trailer 15–45 s (9:16 i 16:9), zapis rozgrywki 10–30 s w 60 fps, opcjonalnie GIF do README (`.gif`).
- Rozgrywka nagrana deterministycznie (to samo wejście = te same klatki), bez gubienia klatek.

## Silnik
| Materiał | Silnik |
|---|---|
| gra w HTML (nasza albo od `tars-web`) | kontrakt HTML w trybie demo (`kontrakt-html.md`) + `html_wideo.py --preset tars` |
| gra bez kontraktu (cudza strona, nagranie od użytkownika) | nagranie użytkownika → `montaz-nagran` (cięcia, kadr 9:16, napisy) |
| plansze, tytuł, CTA trailera | `typografia.md` (HyperFrames, własny HTML) i `film.py` do składania |

## Struktura (trailer 30 s)
| 30 s | Scena |
|---|---|
| 0–2 | **Hak:** najbardziej widowiskowy moment rozgrywki |
| 2–8 | **Fantazja gracza** jednym zdaniem („Ty uciekasz, oni się rozbijają”) |
| 8–24 | **3 mechaniki** po ~5 s, każda z podpisem 2–4 słowa, eskalacja trudności |
| 24–30 | **Tytuł + CTA** („Zagraj w przeglądarce”, link) |

## Rzemiosło
- Tryb demo: sterowanie symulowane z ziarnem i z `t` (bot, nagrana sekwencja wejść), `window.__seek(t)` liczy
  symulację krokiem stałym od `t = 0` (cache co N kroków, żeby nie liczyć od zera przy każdej klatce).
- Kamera trailera może różnić się od gry: zbliżenia, slow-motion (mniejszy krok `t`), zamrożenie klatki przy ciosie.
- HUD czytelny w 9:16 albo ukryty na rzecz podpisów; dźwięk gry + muzyka, efekty na trafieniach.

## Brief (`out/wideo/src/BRIEF.md`)
```
Gra (link / pliki / kod), fantazja gracza (jedno zdanie):   3 mechaniki i momenty, które je pokazują:
Tryb demo (bot / sekwencja wejść / ziarno):                  Formaty, długość, CTA i link:
```

## Pułapki
- Nagrywanie ekranu w czasie rzeczywistym (dropy klatek, różne przebiegi); rozgrywka, w której nic się nie dzieje.
- Budowanie całej gry w Wideografie zamiast oddania jej `tars-web`; cudze postacie i marki w grze.

## Kontrola
- Dwa rendery tego samego fragmentu dają identyczne klatki (determinizm); pasek klatek na akcjach: płynność.
- Każda mechanika czytelna bez dźwięku; CTA i link poprawne.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py interaktywne --ile 3` (albo `--tag playable`).

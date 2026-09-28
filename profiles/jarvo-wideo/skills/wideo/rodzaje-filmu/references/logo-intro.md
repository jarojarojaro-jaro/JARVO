# Logo i intro

Krótka animacja marki: logo, intro i outro filmów, sting, belka z nazwiskiem, ikona albo loader (Lottie).
Nie to: cały opener z treścią → `motion-graphics.md`; reklama produktu → `promo-produktu.md`.

## Wynik
- Logo / sting 2–5 s, intro 3–6 s, belka 4–8 s (wejście, trwanie, wyjście); ikona albo loader w pętli 1–3 s.
- Wersje: `.mov` z alfą (na nagrania), `.mp4` na tle marki, `lottie.json` na stronę (`jarvo-web` osadza), GIF na README.

## Silnik
| Materiał | Silnik |
|---|---|
| logo z obrazka (PNG/JPG) → SVG rysujące się, składające | `pixel2motion` (+ `html_wideo.py --preset pixel2motion`) |
| logo jako SVG od klienta, belka, ikona, loader, na stronę i do filmu | `text-to-lottie` (player Skottie) + `html_wideo.py lottie` |
| logo rysujące się ręką, szkic | `anidoodle` |
| intro z tekstem i kształtami, szybko | HyperFrames |
| belka w projekcie Remotion | `lower-thirds` |

## Struktura
- **Logo 3 s:** 0–0,3 zapowiedź (linia, punkt, kształt), 0,3–2 budowa jednym gestem, 2–3 zatrzymanie na
  gotowym logo (czytelne jak statyczne).
- **Belka 6 s:** 0–0,6 wejście (tło, potem imię, potem funkcja), 0,6–5,4 trwanie bez ruchu, 5,4–6 wyjście odwrotne.

## Rzemiosło
- Logo jest prawem: proporcje, kolory, pola ochronne i kształty z brand kitu; animacja nie zmienia znaku.
- Jeden gest (rysowanie konturu, złożenie z części, odsłonięcie maską), nie pięć efektów.
- Ostatnia klatka = statyczne logo piksel w piksel (kontrakt klatki końcowej, porównaj z plikiem logo).
- Belka: poza strefami UI, 2 poziomy tekstu (imię większe), kontrast na jasnym i ciemnym tle (półprzezroczyste tło).
- Dźwięk (sting) opcjonalny i krótki; wersja bez dźwięku zawsze.

## Brief (`out/wideo/src/BRIEF.md`)
```
Plik logo (SVG najlepiej) i brand kit:          Gest (jedno zdanie) i długość:
Warianty: alfa / tło / Lottie / GIF, formaty:   Belka: imię, funkcja (dokładnie), pozycja:
```

## Pułapki
- Przerysowane logo (inne proporcje, kolory, kerning); animacja kończąca się w innym miejscu niż statyczne logo.
- MP4 zamiast `.mov` z alfą do nakładania; Lottie z efektami, których Skottie albo lottie-web nie obsługuje.

## Kontrola
- Ostatnia klatka obok pliku logo (różnica ≈ 0); kolory zgodne z brand kitem (HEX).
- Belka na jasnym i ciemnym kadrze testowym; `lottie.json` przechodzi weryfikację w playerze (`?frame=N`).

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py logo-intro --ile 3`.

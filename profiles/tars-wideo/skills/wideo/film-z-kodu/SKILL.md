---
name: film-z-kodu
description: "Film z kodu: wybór silnika, B-roll, style kina, rysunek."
version: 3.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, hyperframes, manim, motion-graphics, animation, code]
    related_skills: [motion-broll, lemo-opuscar, anidoodle, hyperframes, product-launch-video, faceless-explainer, manim-video, scenariusz, napisy, kontrola-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Film z kodu

Animacje, typografia w ruchu, UI, wykresy, rysunek: każda klatka rysowana kodem, ffmpeg składa wideo. Tekst i liczby
są ostre i poprawne, nic nie jest „z AI”. Film z ujęć stock, lektora i napisów bez animacji → `krotki-film`.
Instalacja, środowisko i polski lektor dla silników zewnętrznych: `references/narzedzia.md` (przeczytaj przed
pierwszym użyciem motion-broll, lemo-opuscar albo anidoodle).

## Wybór silnika
| Chcę… | Silnik (skill) | Czas pracy |
|---|---|---|
| animowane wstawki (B-roll) do **nagrania użytkownika**, zgrane ze słowami; przebitka albo przezroczysty panel | **motion-broll** | 20–60 min |
| **cały krótki film** 30–75 s w jednym z 39 stylów kina (keynote, screencast, akwarela, anime, 3D, pixel RPG…) | **lemo-opuscar** | 30–60 min, dużo tokenów |
| premiera produktu / keynote tech (ciemny ekran, UI, wielka liczba) | **lemo-opuscar** `dark-keynote`, `living-screencast` | 30–60 min |
| **ręcznie rysowana** ilustracja, timelapse rysowania, film rysunkowy, logo rysujące się samo | **anidoodle** | 15–60 min |
| animacja na stronę (hero, maskotka za kursorem, GIF, naklejka), plik HTML offline | **anidoodle** (`emit.mjs`) → `tars-web` osadza | 15–40 min |
| muzyka **syntezowana kodem** do dowolnego filmu (bez licencji, bez pobierania) | **anidoodle** `music` → plik do `muzyka` w `film.py` | 10–20 min |
| promo z animowanym tekstem, szybki launch, slajdy | **HyperFrames** (`hyperframes`, `product-launch-video`, `slideshow`) | 10–30 min |
| matematyka, algorytmy, wykresy w ruchu | **Manim** (`manim-video`, dodatek `manim`) | 15–40 min |

Zasada kosztu: lemo-opuscar i pełne filmy anidoodle tylko, gdy karta prosi o styl, „premium” albo film markowy.
Zwykły reels: `krotki-film` (minuty). Wybór silnika z jednym zdaniem uzasadnienia w RAPORT.md.

## Wspólne prawa (wszystkie silniki)
1. **Klatka = czysta funkcja czasu** (`render(t)`, `draw(ctx, frame)`): bez `Math.random` bez ziarna, bez `Date.now()`,
   bez stanu między klatkami. Każdą klatkę da się wyrenderować osobno i równolegle.
2. **Hak od klatki 0** (coś już się dzieje), kamera w ruchu, co takt/sekundę jakaś zmiana, puenta na końcu.
   Krótko: 20–30 s wygrywa z 60 s „ładnymi”.
3. **Kamera w wektorach, nie w bitmapie**: lemo `camera().apply(g)`, anidoodle `g.push(x, y, s)`, motion-broll `cam` w `SH`.
4. **Prawda w treści:** żadnych zmyślonych liczb, cytatów, wyników; względne słupki albo etykiety z transkrypcji.
5. **Czytelność w ruchu:** tekst jadący w złą stronę czyta się na odwrót. Sprawdź kierunek na pasku klatek.
6. **Przed oddaniem:** arkusz stopklatek co 1–1,5 s + paski klatek co 0,1–0,2 s na kluczowych akcjach (vision),
   bramka narzędzia (anidoodle `gate.mjs`), potem `qa_wideo.py` i `kontrola-wideo` (≥ 85).
7. **Prawa:** tylko assety CC0 / CC BY / OFL; żadnych cudzych marek i postaci; licencje w RAPORT.md.

## Kroki
1. **Brief i format** (`formaty-wideo`): platforma, długość, cel, jedno przesłanie, CTA, brand kit; wybór silnika z tabeli.
2. **Scenariusz** (`scenariusz`): hook, beat sheet sekunda po sekundzie; lektor PL najpierw (`film.py lektor` →
   czasy słów), animacje pod te czasy.
3. **Środowisko:** `python3 $HERMES_HOME/scripts/narzedzia.py instaluj <motion|lemo|anidoodle>` (raz; dalej z cache),
   `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env <narzędzie>)"`.
4. **Look:** jedna–trzy klatki stylu renderowane prawdziwym kodem → obejrzyj (vision), popraw, dopiero potem całość.
   Akceptacja użytkownika tylko przy dużych zleceniach (karta mówi) – inaczej decydujesz sam.
5. **Budowa i render** wg SKILL.md wybranego silnika (i w lemo: `$LIB/AGENTS.md`, `DIRECTOR.md`, `TECHNIQUE.md`, `STYLE.md`).
6. **Dźwięk:** lektor PL (Edge TTS), muzyka (anidoodle albo biblioteka), miks −14 LUFS (`montaz.py glosnosc` albo lemo `mux.sh`).
7. **Napisy:** `napisy.py <film> --slowa out/wideo/src/lektor.slowa.json --wypal` (gdy tekst nie jest częścią animacji).
8. **Kontrola** (`kontrola-wideo`), oddanie: link `tars_link.py`, miniatura, źródła projektu w `out/wideo/src/`.

## Definition of Done
- [ ] silnik dobrany do celu i uzasadniony; bramka narzędzia (gdy jest) zaliczona,
- [ ] hak w pierwszych 2 s, zmiana co sekundę, puenta; tekst czytelny w ruchu,
- [ ] zero zmyślonych liczb; assety z licencją w RAPORT.md,
- [ ] `qa_wideo.py` bez błędów, `kontrola.json` ≥ 85, źródła projektu w `out/wideo/src/`.

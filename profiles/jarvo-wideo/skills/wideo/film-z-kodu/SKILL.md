---
name: film-z-kodu
description: "Film z kodu: wybór silnika, B-roll, style kina, rysunek."
version: 3.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, hyperframes, manim, motion-graphics, animation, code]
    related_skills: [rodzaje-filmu, motion-design, video-lessons, claude-animation, motion-broll, lemo-opuscar, anidoodle, hyperframes, remotion-best-practices, bang-motion, pixel2motion, text-to-lottie, kinetic-typography, chart-animation, product-launch-video, faceless-explainer, manim-video, scenariusz, napisy, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Film z kodu

Animacje, typografia w ruchu, UI, wykresy, rysunek: każda klatka rysowana kodem, ffmpeg składa wideo. Tekst i liczby
są ostre i poprawne, nic nie jest „z AI”. Film z ujęć stock, lektora i napisów bez animacji → `krotki-film`.
Instalacja, środowisko i polski lektor dla silników zewnętrznych: `references/narzedzia.md` (przeczytaj przed
pierwszym użyciem silnika spoza HyperFrames/Manim).

## Wybór silnika
Najpierw rodzaj filmu (`rodzaje-filmu`): jego plik mówi, który silnik i dlaczego. Ta tabela to pełna lista silników.

| Chcę… | Silnik (skill) | Czas pracy |
|---|---|---|
| **własna animacja** w Canvas, SVG, Three.js, GSAP (dowolny pomysł, pełna kontrola) | HTML wg `rodzaje-filmu/references/kontrakt-html.md` + `html_wideo.py --preset jarvo` | 20–60 min |
| **Jarvo mówi**: maskotka marki (robot) z polskim lektorem, oczy i wskaźnik głosu w rytm mowy, napisy karaoke | `python3 $HERMES_HOME/scripts/maskotka.py "tekst" -o film.mp4 [--format 9x16\|1x1\|16x9]` | 1–3 min |
| **UI morph**: jeden kontener przechodzi przez 8–12 stanów produktu, kursor klika, zero cięć, pętla | HTML wg spec `references/jeden-ksztalt.md` (zrzuty z `assety.py`) | 30–60 min |
| animowane wstawki (B-roll) do **nagrania użytkownika**, zgrane ze słowami; przebitka albo przezroczysty panel | **motion-broll** | 20–60 min |
| **cały krótki film** 30–75 s w jednym z 39 stylów kina (keynote, screencast, akwarela, anime, 3D, pixel RPG…) | **lemo-opuscar** | 30–60 min, dużo tokenów |
| premiera produktu / keynote tech (ciemny ekran, UI, wielka liczba) | **lemo-opuscar** `dark-keynote`, `living-screencast` | 30–60 min |
| **ręcznie rysowana** ilustracja, timelapse rysowania, film rysunkowy, logo rysujące się samo | **anidoodle** | 15–60 min |
| **postać w akcji** (maskotka, bohater gry, zwierzak z anatomią), efekty jak w grze, low-poly pętla, książeczka; **bez przeglądarki** (najlżejsze na VPS) | **claude-animation** (Node canvas) | 20–60 min |
| animacja na stronę (hero, maskotka za kursorem, GIF, naklejka), plik HTML offline | **anidoodle** (`emit.mjs`) → `jarvo-web` osadza | 15–40 min |
| muzyka **syntezowana kodem** do dowolnego filmu (bez licencji, bez pobierania) | **anidoodle** `music` → plik do `muzyka` w `film.py` | 10–20 min |
| promo z animowanym tekstem, szybki launch, slajdy | **HyperFrames** (`hyperframes`, `product-launch-video`, `slideshow`) | 10–30 min |
| matematyka, algorytmy, wykresy w ruchu | **Manim** (`manim-video`, dodatek `manim`) | 15–40 min |
| **kinowy film produktu** ze strony/aplikacji (prawdziwe screenshoty, ruchy kamery 2.5D, cięcia na bit, dźwięk) | **video-shotcraft** (`$SHOTCRAFT/SKILL.md`, Remotion) | 40–90 min |
| film w **React/Remotion** (klient chce Remotion, komponenty, parametryzowane serie) | **Remotion** (`remotion-best-practices`: router do create, markup, render, maps…) | 20–60 min |
| **animowany wykres / infografika** z prawdziwych danych | `chart-animation`, `animated-infographic` (Remotion) | 15–40 min |
| belka z nazwiskiem, odliczanie (dodatki do nagrań) | `lower-thirds`, `countdown-video` (Remotion) | 10–20 min |
| **animowana typografia** (słowo po słowie, cytat, manifest, tytuł) | `kinetic-typography` (HTML + `html_wideo.py --preset iart`) | 15–30 min |
| opener, promo, plansza, explainer **z wyglądem z marki** (brief stylu wymagany) | **bang-motion** (HTML + `html_wideo.py --preset bang`) | 20–45 min |
| **logo z obrazka → animacja SVG** (intro/outro marki) | **pixel2motion** (HTML/SVG + `html_wideo.py --preset pixel2motion`) | 15–30 min |
| animacja **Lottie** (ikona, loader, belka, logo) na stronę/aplikację albo do filmu | `text-to-lottie` (player Skottie) → JSON dla `jarvo-web`, MP4/MOV: `html_wideo.py lottie` | 10–20 min |

Bez dubli: typografia i promo z tekstem najpierw HyperFrames; Remotion (i iart) gdy klient chce Remotion albo
potrzebny wykres/typografia z gotowego przepisu. Napisy zawsze `napisy` (nie captions z Remotion), chyba że film
jest w Remotion. Każda animacja HTML (iart, bang-motion, pixel2motion, własna z uprzężą `?t=`) → klatki, arkusz
i MP4/MOV przez `$HERMES_HOME/scripts/html_wideo.py`. Licencja Remotion: darmowa dla osoby i firmy do 3 osób;
większa firma → licencja firmowa (zapisz w RAPORT.md).

Zasada kosztu: lemo-opuscar i pełne filmy anidoodle tylko, gdy karta prosi o styl, „premium” albo film markowy.
Film dłuższy niż 30 s, flagowy, z postacią albo historią: bramki z `references/produkcja-etapami.md`
(przewodnik stylu, lista ujęć, stopklatki, animatic 960×540, próbka najtrudniejszych sekund, dziennik krytyki).
Zwykły reels: `krotki-film` (minuty). Wybór silnika z jednym zdaniem uzasadnienia w RAPORT.md.

## Wspólne prawa (wszystkie silniki)
1. **Klatka = czysta funkcja czasu** (`render(t)`, `draw(ctx, frame)`): bez `Math.random` bez ziarna, bez `Date.now()`,
   bez stanu między klatkami. Każdą klatkę da się wyrenderować osobno i równolegle.
2. **Hak od klatki 0** (coś już się dzieje), kamera w ruchu, co takt/sekundę jakaś zmiana, puenta na końcu.
   Krótko: 20–30 s wygrywa z 60 s „ładnymi”.
3. **Kamera w wektorach, nie w bitmapie**: lemo `camera().apply(g)`, anidoodle `g.push(x, y, s)`, motion-broll `cam` w `SH`.
4. **Prawda w treści:** żadnych zmyślonych liczb, cytatów, wyników; względne słupki albo etykiety z transkrypcji.
5. **Czytelność w ruchu:** tekst jadący w złą stronę czyta się na odwrót. Sprawdź kierunek na pasku klatek.
6. **Przed oddaniem:** arkusz stopklatek co 1–1,5 s + paski klatek co 0,1–0,2 s na kluczowych akcjach (vision;
   HTML i Lottie: `html_wideo.py klatki … --arkusz`), animacja HTML: `html_wideo.py pomiar` pełny i aktualny bez
   błędów (`kontrakt-html.md`, tekst z kanwy przez `__teksty`), bramka narzędzia (anidoodle `gate.mjs`), film po
   silniku zewnętrznym przez `montaz.py napraw`, potem `qa_wideo.py` i `kontrola-wideo` (≥ 85).
7. **Prawa:** tylko assety CC0 / CC BY / OFL; żadnych cudzych marek i postaci; licencje w RAPORT.md.
8. **Zero zakazanych chwytów** (lista „zakazane” w skillu `kontrola-wideo`): tytuł na gradiencie,
   wszystko przez fade, rogi i ramki, glow na UI, cząsteczki bez powodu, przejazd liniowy. Zamiast tego ruch z kierunkiem i masą.
10. **HyperFrames: check przed renderem.** Po każdej zmianie kompozycji `npx hyperframes check` (lint + walidacja
   w przeglądarce, `--snapshots` na klatki) i render dopiero przy czystym wyniku: według HeyGen mediana 1 render zamiast 2
   i ~połowa kosztu tokenów. Promo z marki: `hyperframes capture <URL>` (skill `product-launch-video`) albo `assety.py`.
11. **Za wolno?** `krytyka.py puls` pokazuje, gdzie film zwalnia; poprawiasz na osi czasu przez `retime.py`
   (`references/retime.md`), nie cięciem MP4.
9. **Pętla krytyki przed oddaniem:** `kontrola-wideo` krok 4a (7 osi 1–10, 3 najgorsze problemy, aż wszystko ≥ 8).
12. **Reżyseria ruchu i usterki renderu:** `motion-design` (kierunek, inscenizacja, ciągłość, easing, timing, słownik
   ruchów, wzorce kompozycji) i `video-lessons` (fonty zastępcze, drżenie tekstu, szwy przejść, CSS na zegarze ściennym,
   WebGL; najpierw odtwórz usterkę, potem napraw przyczynę). Pisane dla aplikacji Remocn Studio, u nas: „Studio”
   i „pipeline” = nasz proces (`rodzaje-filmu` → `scenariusz` → ten skill → `kontrola-wideo`); `design_check` =
   `html_wideo.py pomiar` (animacja HTML) + `qa_wideo.py` i `krytyka.py` (MP4); panelu właściwości i schematów (`rules/tunable-text.md`) nie mamy:
   wartości do strojenia trzymaj w stałych na górze sceny; szablony w `motion-design` to wzorce kompozycji z rejestru
   remocn, niczego z niego nie instalujesz. Przykłady w Remotion przenosisz na wybrany silnik (Remotion tylko,
   gdy go wybrałeś: firmy powyżej 3 osób potrzebują licencji Remotion).

## Kroki
1. **Rodzaj, brief i format** (`rodzaje-filmu`, `formaty-wideo`): plik rodzaju → `out/wideo/src/BRIEF.md`
   (platforma, długość, cel, jedno przesłanie, CTA, brand kit); silnik z pliku rodzaju albo z tabeli.
2. **Scenariusz** (`scenariusz`): hook, beat sheet sekunda po sekundzie; lektor PL najpierw (`film.py lektor` →
   czasy słów), animacje pod te czasy.
3. **Środowisko:** `python3 $HERMES_HOME/scripts/narzedzia.py instaluj <motion|lemo|anidoodle|remotion|shotcraft|html|lottie>`
   (raz; dalej z cache), `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env <narzędzie>)"`.
   Skill silnika każe coś doinstalować, pobrać przeglądarkę (`npx playwright install`, `npm i puppeteer`) albo
   zaktualizować skille (`remotion-upgrade`, `npx skills add`)? Nie rób tego: `references/narzedzia.md` mówi, czym to zastąpić.
4. **Look:** jedna–trzy klatki stylu renderowane prawdziwym kodem → obejrzyj (vision), popraw, dopiero potem całość.
   Akceptacja użytkownika tylko przy dużych zleceniach (karta mówi) – inaczej decydujesz sam.
5. **Budowa i render** wg SKILL.md wybranego silnika (i w lemo: `$LIB/AGENTS.md`, `DIRECTOR.md`, `TECHNIQUE.md`, `STYLE.md`).
6. **Dźwięk:** lektor PL (Edge TTS), muzyka (anidoodle albo biblioteka), miks −14 LUFS (`montaz.py glosnosc` albo lemo `mux.sh`).
7. **Napisy:** `napisy.py <film> --slowa out/wideo/src/lektor.slowa.json --wypal` (gdy tekst nie jest częścią animacji).
8. **Kontrola** (`kontrola-wideo`), oddanie: link `jarvo_link.py`, miniatura, źródła projektu w `out/wideo/src/`.

## Definition of Done
- [ ] silnik dobrany do celu i uzasadniony; bramka narzędzia (gdy jest) zaliczona,
- [ ] hak w pierwszych 2 s, zmiana co sekundę, puenta; tekst czytelny w ruchu,
- [ ] zero zmyślonych liczb; assety z licencją w RAPORT.md,
- [ ] `qa_wideo.py` bez błędów, `kontrola.json` ≥ 85, źródła projektu w `out/wideo/src/`.

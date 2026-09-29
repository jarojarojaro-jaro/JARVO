---
name: kontrola-wideo
description: "Przed oddaniem filmu: kontrola techniczna i ocena 0–100."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, qa, quality-gate, rubric, loudness, safe-zones]
    related_skills: [krotki-film, montaz-nagran, klipy-z-dlugiego, napisy, formaty-wideo, dobor-ujec]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Kontrola wideo (bramka jakości)

Dwie części: technika mierzona skryptem (musi być czysta) i ocena redakcyjna 0–100 według rubryki
`references/rubryka.md`. Film przechodzi przy **zero błędów technicznych i wyniku ≥ 85**.

## Kiedy użyć
- Przed oddaniem każdego filmu, klipu i wariantu. Także na szkicu, gdy rytm budzi wątpliwości.

## Kroki
1. **Technika:** `python3 $HERMES_HOME/scripts/qa_wideo.py <film.mp4> --platforma <tiktok|ig-reel|…> --lektor
   --arkusz out/wideo/<film>/qa.jpg --json`.
   Sprawdza też pojedyncze „mrugnięcia” (jedna klatka inna niż obie sąsiednie): obejrzyj te chwile i popraw scenę.
   Błąd (`bledy`) = poprawka przed oceną; typowe: głośność → `montaz.py glosnosc`, format → ponowny render,
   czarny początek → pierwsza scena z obrazem.
   - ✅ Punkt kontrolny: `ok: true`.
2. **Oglądanie:** `vision_analyze` na arkuszu (`qa.jpg`: klatki 0 s, 0,5 s, 1,5 s, ¼, ½, ¾, koniec; czerwone pola =
   strefy UI). Pytania: czy hook jest czytelny w klatce 0–1,5 s? czy napisy/tekst/logo wchodzą w czerwone pola?
   czy ujęcia pasują do tekstu? artefakty, znaki wodne, obcy tekst? Dodatkowo `SCENARIUSZ.md` i `.srt` (błędy w słowach).
3. **Ocena** wg `references/rubryka.md`: start 100, odejmowanie za każdą różnicę; każda różnica ma
   **najmniejszą poprawkę** (konkretna scena, konkretne pole planu albo polecenie).
4. **Werdykt** `out/wideo/<film>/kontrola.json`:
   ```json
   {"runda": 1, "film": "out/wideo/kawa/kawa-9x16.mp4", "technika_ok": true, "wynik": 88, "werdykt": "PASS",
    "roznice": [{"os": "rytm", "roznica": "scena 3 stoi 5 s bez zmiany obrazu", "poprawka": "scena 3: dodaj tekst_ekranowy albo podziel"}],
    "osie": {"hook": 8, "telefon": 7, "ruch": 8, "roznorodnosc": 9, "kompozycja": 6, "marka": 9, "dzwiek": 8},
    "problemy": [{"t": 4.2, "problem": "tytuł na gradiencie", "poprawka": "scena 2: kadr asymetryczny, tło płaskie z kitu"}]}
   ```
   `werdykt`: PASS (≥ 85 i technika czysta), REVISE (< 85), BLOCK (błąd blokujący z rubryki: prawa, twarz, publikacja).
4a. **Krytyka reżyserska** (filmy z kodu, motion graphics, reelsy z animacją; film ze stocku: tylko punkty 2–4):
   bądź surowym motion directorem, nie dumnym autorem. Narzędzia (`$HERMES_HOME/scripts/krytyka.py`):
   - `telefon <film>`: 1 klatka/s w 360 px szerokości (czy każdy tekst da się przeczytać na telefonie?),
   - `pasek <film> --t <s>`: 12 kolejnych klatek wokół każdej szybkiej akcji i każdej zmiany stanu,
   - `martwe <film>`: odcinki bez zmiany obrazu > 2,5 s (martwy takt),
   - `petla <film>`: szew pętli (tylko gdy film ma się zapętlać), `determinizm <anim.html> --czasy …` (HTML).
   Oceń 7 osi w skali 1–10: hook (2 s), telefon (360 px), ruch (sprężyny, wyhamowanie), różnorodność (nowość
   co 2–4 s), kompozycja (zero chwytów z `references/zakazane.md`), marka, dźwięk (zdarzenia na bitach).
   Poluj konkretnie na: tekst nachodzący na siebie przy zmianie, przejazd zamiast wyhamowania, napisy w rogach
   i ramki, tytuł na gradiencie, rozmyty skalowany tekst, martwy takt, szarpnięcie na szwie pętli.
   Zapisz w `kontrola.json` pola `osie` (7 liczb) i `problemy` (3 najgorsze, każdy z `t` w sekundach i poprawką).
   Popraw 3 najgorsze, wyrenderuj ponownie tylko te sekundy (gdy silnik pozwala), nowa runda.
   `krytyka.py ocena kontrola.json` = 0 dopiero, gdy **każda oś ≥ 8**. Maks. 3 rundy; potem oddajesz
   z uczciwie nazwanymi brakami. Historia rund (osie + problemy) w `out/wideo/<film>/krytyka.md`.
5. **Poprawki:** REVISE → popraw plan/pliki wg `roznice`, render, nowa runda (`runda` + 1). Najwyżej 2 rundy poprawek;
   potem oddaję z wynikiem i nazwanymi brakami w `metadata.risks` (bez podbijania wyniku).
6. **Dowód do oddania karty:** w `dod_check` wynik `qa_wideo.py` (liczby: sek, LUFS, rozdzielczość) i `kontrola.json`.

## Wyjścia
- `out/wideo/<film>/qa.jpg`, `out/wideo/<film>/kontrola.json` (ostatnia runda), historia rund w RAPORT.md.

## Definition of Done
- [ ] `qa_wideo.py` bez błędów (JSON w raporcie), arkusz obejrzany,
- [ ] `kontrola.json` z wynikiem ≥ 85 i PASS albo nazwane braki po 2 rundach,
- [ ] każda różnica ma najmniejszą poprawkę; wynik nie jest zawyżany,
- [ ] film z kodu / animacja: `krytyka.py ocena` = 0 (7 osi ≥ 8) albo nazwane braki po 3 rundach, zero chwytów z `zakazane.md` bez uzasadnienia.

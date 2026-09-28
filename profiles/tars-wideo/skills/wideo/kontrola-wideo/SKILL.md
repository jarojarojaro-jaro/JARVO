---
name: kontrola-wideo
description: "Przed oddaniem filmu: kontrola techniczna i ocena 0–100."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, qa, quality-gate, rubric, loudness, safe-zones]
    related_skills: [krotki-film, montaz-nagran, klipy-z-dlugiego, napisy, formaty-wideo, dobor-ujec]
  tars:
    agent: tars-wideo
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
    "roznice": [{"os": "rytm", "roznica": "scena 3 stoi 5 s bez zmiany obrazu", "poprawka": "scena 3: dodaj tekst_ekranowy albo podziel"}]}
   ```
   `werdykt`: PASS (≥ 85 i technika czysta), REVISE (< 85), BLOCK (błąd blokujący z rubryki: prawa, twarz, publikacja).
5. **Poprawki:** REVISE → popraw plan/pliki wg `roznice`, render, nowa runda (`runda` + 1). Najwyżej 2 rundy poprawek;
   potem oddaję z wynikiem i nazwanymi brakami w `metadata.risks` (bez podbijania wyniku).
6. **Dowód do oddania karty:** w `dod_check` wynik `qa_wideo.py` (liczby: sek, LUFS, rozdzielczość) i `kontrola.json`.

## Wyjścia
- `out/wideo/<film>/qa.jpg`, `out/wideo/<film>/kontrola.json` (ostatnia runda), historia rund w RAPORT.md.

## Definition of Done
- [ ] `qa_wideo.py` bez błędów (JSON w raporcie), arkusz obejrzany,
- [ ] `kontrola.json` z wynikiem ≥ 85 i PASS albo nazwane braki po 2 rundach,
- [ ] każda różnica ma najmniejszą poprawkę; wynik nie jest zawyżany.

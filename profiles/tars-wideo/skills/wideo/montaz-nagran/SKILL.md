---
name: montaz-nagran
description: "Montaż nagrań: cięcie, cisza, kadr 9:16, dźwięk, napisy."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, editing, ffmpeg, reframe, silence, audio]
    related_skills: [napisy, lektor-i-dzwiek, klipy-z-dlugiego, dobor-ujec, kontrola-wideo, formaty-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Montaż nagrań użytkownika

Surowe nagranie (telefon, kamera, ekran) → gotowy film. Narzędzie: `$HERMES_HOME/scripts/montaz.py`
(wszystko przekodowane, dokładne co do klatki). Pliki od użytkownika leżą w `/opt/data/tars/inbox/`.

## Kiedy użyć
- „Obrób to nagranie”, „wytnij wpadki i ciszę”, „zrób pion z poziomego”, „dodaj napisy”, „wyrównaj dźwięk”.

## Uwaga: wypalone napisy
Nagranie z już wypalonymi napisami (także własny film z `film.py`) po zmianie kadru ma ucięte stare napisy,
a nowe na nie nachodzą. Własny film w innym formacie: `film.py render --format <nowy>` z planu; cudzy z napisami:
zostaw jego napisy albo zapytaj o wersję „czystą”.

## Kiedy NIE używać
- Nagranie dłuższe niż ~5 min, z którego mają powstać krótkie klipy → `klipy-z-dlugiego`.
- Brak nagrania, jest tylko temat → `krotki-film`.

## Kroki
1. **Przegląd:** `qa_wideo.py <nagranie>` (rozdzielczość, fps, głośność) i `kadry.py arkusz <nagranie> --klatek 6`
   → `vision_analyze`: gdzie jest obiekt/osoba w kadrze, jakość, wpadki widoczne w obrazie.
2. **Transkrypcja** (gdy jest mowa): `montaz.py transkrypcja <nagranie> -o out/wideo/src/transkrypcja`
   → `.txt` z czasami: wpadki, powtórzenia, fragmenty do wycięcia.
3. **Cięcie:** `montaz.py wytnij <nagranie> -o out/wideo/src/ciecie.mp4 --zakresy "0:03-0:41.5,0:47-1:20"`.
4. **Cisza:** `montaz.py cisza <plik> -o out/wideo/src/bez-ciszy.mp4` (próg −35 dB; głośne tło: `--prog -30`;
   wolniejszy rytm: `--min 0.8`). Alternatywa z obrazu: `auto-editor`, jeśli jest (`command -v auto-editor`).
   - ✅ Punkt kontrolny: obejrzyj 2–3 miejsca cięć (`kadry.py arkusz`): nie ucięte słowa, brak „skoków” w pół gestu.
5. **Kadr pod format:** `montaz.py kadr <plik> -o out/wideo/src/pion.mp4 --format 9:16 --x 0.45` (x = środek obiektu
   z przeglądu). Nagranie ekranu, slajdy, dwie osoby w kadrze: `--tryb rozmyte`.
6. **Dźwięk:** `montaz.py glosnosc <plik> -o <wynik> --lufs -14`; muzyka pod głos: `lektor-i-dzwiek`.
7. **Napisy:** `napisy` (transkrypcja → korekta SRT → wypalenie).
8. **Kontrola:** `kontrola-wideo`; oddanie jak w `krotki-film` (link, miniatura, RAPORT z listą cięć).

## Wyjścia
- `out/wideo/<nazwa>-<format>.mp4` (+ `.srt`), pośrednie w `out/wideo/src/`, lista cięć i decyzji w RAPORT.md.

## Definition of Done
- [ ] wpadki i długie cisze usunięte bez ucinania słów; cięcia obejrzane,
- [ ] obiekt w kadrze po zmianie formatu; format i długość zgodne z platformą,
- [ ] −14 LUFS ±2, napisy poprawne, `qa_wideo.py` bez błędów,
- [ ] oryginał nietknięty (praca na kopiach w `out/wideo/src/`).

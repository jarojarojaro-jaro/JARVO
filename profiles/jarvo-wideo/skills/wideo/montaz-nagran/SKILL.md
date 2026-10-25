---
name: montaz-nagran
description: "Montaż nagrań: stabilizacja, cięcie, cisza, kadr, dźwięk."
version: 1.4.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, editing, ffmpeg, stabilization, reframe, silence, audio, color]
    related_skills: [napisy, lektor-i-dzwiek, clipmaker, dobor-ujec, kontrola-wideo, formaty-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-07"
---

# Montaż nagrań użytkownika

Surowe nagranie (telefon, kamera, ekran) → gotowy film. Narzędzie: `"$HERMES_HOME/scripts/montaz.py"`
(wszystko przekodowane, dokładne co do klatki). Pliki od użytkownika leżą w `@@INBOX_DIR@@/`.

## Kiedy użyć
- „Obrób to nagranie”, „wytnij wpadki i ciszę”, „zrób pion z poziomego”, „dodaj napisy”, „wyrównaj dźwięk”,
  „ustabilizuj, bo się trzęsie”.

## Uwaga: wypalone napisy
Nagranie z już wypalonymi napisami (także własny film z `film.py`) po zmianie kadru ma ucięte stare napisy,
a nowe na nie nachodzą. Własny film w innym formacie: `film.py render --format <nowy>` z planu; cudzy z napisami:
zostaw jego napisy albo zapytaj o wersję „czystą”.

## Kiedy NIE używać
- Nagranie dłuższe niż ~3 min, z którego mają powstać krótkie rolki → `clipmaker`.
- Brak nagrania, jest tylko temat → `krotki-film`.

## Kroki
1. **Przegląd:** `qa_wideo.py <nagranie>` (rozdzielczość, fps, głośność) i `kadry.py arkusz <nagranie> --klatek 6`
   → `vision_analyze`: gdzie jest obiekt/osoba w kadrze, jakość, wpadki widoczne w obrazie.
   Nagranie HDR z telefonu (`qa_wideo.py` pisze „film w HDR”): nic nie robisz, `montaz.py` (wytnij, cisza, kadr,
   stabilizuj, napraw), `napisy.py` i `projekt.py render` przeliczają je na zwykły obraz same; `glosnosc` kopiuje
   obraz, więc na samym HDR najpierw `napraw`.
   Nagranie z ręki (telefon w dłoni, w marszu): `montaz.py stabilizuj <nagranie> --tylko-pomiar` → `drzenie_proc`
   (% szerokości kadru) i `rada`. Statyw i spokojna panorama dają ~0.
2. **Stabilizacja** (tylko gdy `rada` każe): `montaz.py stabilizuj <nagranie> -o out/wideo/src/stabilne.mp4
   --sila lekka|srednia|mocna` (z rady); dalej pracujesz na `stabilne.mp4`. Na całym nagraniu, **przed cięciem**:
   cięcie w środku psuje wygładzanie.
   Kadr wychodzi lekko powiększony (bez czarnych brzegów), 4K zmniejszone do 1080p, HDR przeliczony na zwykły
   obraz. Kamera ma stać (rozmowa, ujęcie z ręki bez ruchu): `--statyw`. Czas: 1080p ok. 2,5× długości nagrania,
   4K ok. 5× (minuta 4K ≈ 5 min: najpierw powiedz właścicielowi); `--bez-pomiaru` nieco krócej.
   - ✅ Punkt kontrolny: `drzenie_po_proc` wyraźnie niższe niż `drzenie_przed_proc`; `uwaga` w wyniku = obejrzyj
     (mało spadło: drży osoba, nie kamera → `--sila mocna` albo zostaw oryginał). Arkusz klatek
     (`kadry.py arkusz`) przez `vision_analyze`: brzegi bez czarnych pasów, twarz nie ucięta przez powiększenie.
3. **Transkrypcja** (gdy jest mowa): `montaz.py transkrypcja <nagranie> -o out/wideo/src/transkrypcja`
   → `.txt` z czasami: wpadki, powtórzenia, fragmenty do wycięcia.
4. **Cięcie:** `montaz.py wytnij <nagranie> -o out/wideo/src/ciecie.mp4 --zakresy "0:03-0:41.5,0:47-1:20"`.
5. **Cisza:** `montaz.py cisza <plik> -o out/wideo/src/bez-ciszy.mp4` (próg −35 dB; głośne tło: `--prog -30`;
   wolniejszy rytm: `--min 0.8`). Alternatywa: `auto-editor`, jeśli jest zainstalowany (`command -v auto-editor`).
   - ✅ Punkt kontrolny: `krytyka.py ciecia <plik> --czasy <lista „ciecia” z wyniku wytnij/cisza>` i każdy obraz
     przez `vision_analyze`: nie ucięte słowa (słowo na czerwonej linii, kolec fali), brak „skoków” w pół gestu.
     Słowo ucięte → zakres o 0,1–0,2 s dalej od słowa (`wytnij`) albo większy `--zapas` (`cisza`).
6. **Kadr pod format:** `montaz.py kadr <plik> -o out/wideo/src/pion.mp4 --format 9:16 --x 0.45` (x = środek obiektu
   z przeglądu). Nagranie ekranu, slajdy, dwie osoby w kadrze: `--tryb rozmyte`.
7. **Dźwięk:** szum, dudnienie albo syczenie w nagraniu → czysty głos (`lektor-i-dzwiek`): w projekcie
   `projekt.py glos <plik> --wszystkie`, na samym pliku `montaz.py glos <plik> -o <wynik>` (poziom auto z tła).
   Potem `montaz.py glosnosc <plik> -o <wynik> --lufs -14`; muzyka pod głos: `lektor-i-dzwiek`.
   **Kolor** (gdy obraz jest ciemny, płaski, wyblakły albo właściciel prosi o nastrój): projekt montażu filmu
   (`projekt.py`, ten sam co w edytorze HQ) → `projekt.py kolor <plik> --wszystkie --auto --podglad`, nastrój
   `--styl naturalny|cieply|chlodny|kinowy|zywy|czb|wyblakly` (suwaki `--jasnosc/--kontrast/--nasycenie/--temperatura`
   −100…100), potem `projekt.py render <plik>`. Obraz z `--podglad` (przed | po) przez `vision_analyze`: skóra
   naturalna, nie pomarańczowa ani szara, światła i cienie nie zjedzone. Jeden kolor na cały film, z umiarem.
8. **Napisy:** `napisy` (transkrypcja → korekta SRT → wypalenie).
9. **Kontrola:** `kontrola-wideo`; oddanie jak w `krotki-film` (link, miniatura, RAPORT z listą cięć).

## Wyjścia
- `out/wideo/<nazwa>-<format>.mp4` (+ `.srt`), pośrednie w `out/wideo/src/`, lista cięć i decyzji w RAPORT.md.

## Definition of Done
- [ ] nagranie z ręki ustabilizowane, gdy drżało (drżenie po wyraźnie niższe, brzegi i twarz obejrzane),
- [ ] wpadki i długie cisze usunięte bez ucinania słów; każde cięcie obejrzane (`krytyka.py ciecia`),
- [ ] obiekt w kadrze po zmianie formatu; format i długość zgodne z platformą,
- [ ] kolor (jeśli zmieniany) jeden na film, skóra naturalna, podgląd przed i po obejrzany,
- [ ] −14 LUFS ±2, napisy poprawne, `qa_wideo.py` bez błędów,
- [ ] oryginał nietknięty (praca na kopiach w `out/wideo/src/`).

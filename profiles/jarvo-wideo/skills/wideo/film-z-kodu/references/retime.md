# Za wolno? Retime: szybszy film z kodu bez pisania go od nowa

Film z kodu (HyperFrames, HTML) jest funkcją czasu, więc tempo poprawiasz na OSI CZASU, nie cięciem MP4.
Cięcie gotowego wideo rwie muzykę i lektora; przesunięcie chwil w źródle pozwala wygenerować dźwięk od nowa.

## Pętla
1. **Zmierz:** `krytyka.py puls film.mp4` → gdzie film zwalnia (odcinki „mało nowego”; `martwe` łapie tylko zamrożony
   obraz, a tło z ruchem nim nie jest). Cel retencji: udział wolnych ≤ 25 %, nowa rzecz co 1–2 s, hak od klatki 0.
2. **Kotwice** (`kotwice.json`): `{"kotwice": [[stary, nowy], …], "koniec": 24}`: chwile w starym filmie → chwile w nowym.
   Zagęszczaj: wejścia par zamiast pojedynczo, licznik 1 s zamiast 1,6 s, przejście od razu po ostatnim słowie,
   pierwsza sekunda bez wstępu. Ruch (wjazdy, sprężyny) zostaje płynny: retime skraca długości animacji tylko do
   `--tempo-animacji` (domyślnie 0,85).
3. **Przelicz:** `retime.py orig/index.v1.html --kotwice kotwice.json -o index.html` (oryginał trzymaj w podkatalogu:
   dwa pliki z `data-composition-id` w korzeniu = błąd `check`). `retime.py mapuj kotwice.json 12.5 25` daje nowe czasy.
4. **Dźwięk od nowa na nowej osi:** lektor `--rate +10…15%` i krótsze zdania, wejścia lektora z `mapuj`; muzyka
   generowana pod nowe granice scen (nie ciąć starej); SFX przez `Mix(remap=M)`. Pod −14 LUFS: `montaz.py glosnosc`.
5. **Sprawdź:** `hyperframes check`, snapshoty, render, ponownie `krytyka.py puls` (udział wolnych spadł?), `qa_wideo.py`.

Uwaga: kompozycja musi mieć jeden `const tl = gsap.timeline({ paused: true });` i zegar HUD jako `tl.to(clock, …)`.

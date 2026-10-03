# Plan edytora filmów HQ (jak CapCut)

Rozbudowa edytora z [HQ.md §2a](HQ.md#2a-edytor-filmów) na prośbę właściciela (zrzuty z CapCut: menu Edytuj, Audio,
Tekst). Zasada nadrzędna: **oś czasu jest w centrum**. Dotknięcie klipu, audio albo tekstu na osi daje od razu
narzędzia tego elementu, a każda funkcja działa tak samo w podglądzie, w eksporcie i u Wideografa (`projekt.py`).
Jarvo zostaje nadrzędny: z cudzych projektów bierzemy tylko wzorce i pliki na wolnych licencjach, kod jest nasz.

## Zasady wspólne dla każdego kroku

- **Podgląd = film.** Wygląd liczy jedna funkcja bez Reacta (testy w node), eksport ffmpeg używa tych samych wzorów,
  a test porównuje oba (tak jak `tests/test_edytor_przejscia.py`).
- **Agent ma to samo.** Każda operacja ma polecenie `projekt.py` i jest w prośbie z edytora („Poproś agenta”).
- **Oś magnetyczna.** Cięcie, usunięcie i wstawienie przesuwają napisy, typografię, uwagi i audio (`remapTimes`
  = `edytor.remap_times`); nowa funkcja nie może tego zepsuć.
- **Telefon i komputer.** Na telefonie panel od dołu po dotknięciu elementu, na komputerze panel „Ustawienia”.
- Każdy krok: testy, dokumentacja (HQ.md, README i CHANGELOG Wideografa), wdrożenie i test w kontenerze, osobny commit.

## Krok 1. Oś i cięcie

| Funkcja | Stan | Opis |
|---|---|---|
| Przejścia między klipami | ✅ | 16 rodzajów, kwadrat na cięciu, animowane miniatury, długość, „Do wszystkich cięć”; nie skraca filmu (środek cięcia, napisy zostają); eksport `xfade` + `acrossfade`; `projekt.py przejscie` |
| Szybkie cięcie | ✅ | Usuń z lewej (od początku klipu do wskaźnika, Q) i z prawej (od wskaźnika, W), podział klipu na 2–4 równe części (np. 7,5 s → 3 × 2,5 s, środek usunięty jednym ruchem, reszta się dosuwa); `projekt.py tnij` i `wytnij` |
| Zanik audio | ✅ | Narastanie i wyciszanie na początku i końcu każdego audio i klipu (suwaki, trójkąt na osi, `afade` liniowo jak podgląd); `projekt.py dzwiek` i `dodaj-audio --narastanie/--wyciszanie` |
| Kilka ścieżek audio | ✅ | Muzyka, lektor i efekty grające naraz na osobnych pasach osi (pierwszy wolny pas), do 32 elementów audio |
| Paski ikon na telefonie | ✅ | Pasek główny, pasek klipu, audio i tekstu jak w CapCut, z „<” powrotu; ikona otwiera jedną sekcję ustawień |

## Krok 2. Audio

- **Efekty dźwiękowe wbudowane:** mała biblioteka ok. 100 dźwięków CC0 (Kenney, Freesound z licencją CC0), razem
  3–5 MB, katalog jak `kroje.py` (nazwa, kategoria, długość, licencja, suma); np. liczenie banknotów, spadające monety,
  strzał, plusk wody, kliknięcie, whoosh.
- **Wyodrębnij:** dźwięk z innego filmu jako osobne audio.
- **Tekst na mowę:** lektor Edge TTS (ten sam co w `film.py`), głos i tempo do wyboru.
- **Muzyka:** biblioteka użytkownika, muzyka marki i utwory z anidoodle, z odsłuchem przed dodaniem.
- **Nagraj:** mikrofon w przeglądarce (wymaga HTTPS, np. Tailscale serve); bez HTTPS wgranie notatki głosowej.

## Krok 3. Tekst

- **Naklejki:** Fluent Emoji 3D (MIT, ok. 150 wybranych) i nasze naklejki wektorowe z ruchem.
- **Rysowanie** po kadrze, **szablony tekstu** (gotowe zestawy stylu), **animacje tekstu** (wejście, wyjście, pętla).

## Krok 4. Klip

- Animacje wejścia i wyjścia (przybliżenie, oddalenie, wjazd), obrót i odbicie, stop-klatka, odwrócenie, podmiana
  materiału z zachowaniem miejsca na osi.

## Krok 5. Później (jako dodatki)

- Jasność, kontrast, filtry i odszumianie (`eq`, `afftdn`), efekty, krzywa tempa, obraz w obrazie, ściszanie muzyki
  pod mową (ducking).

## Źródła i licencje

Zaakceptowane przez właściciela: dźwięki CC0 (Kenney, Freesound CC0), Fluent Emoji (MIT), własne naklejki wektorowe,
Edge TTS jak dotąd. Każde nowe źródło trafia do [SOURCES.md](SOURCES.md) w tym samym commicie co pliki.

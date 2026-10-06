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
| Zanik audio | ✅ | Narastanie i wyciszanie na początku i końcu każdego audio i klipu (suwaki, trójkąt na osi, `afade` liniowo jak podgląd); `projekt.py dzwiek` i `dodaj-audio --narastanie/--wyciszanie`; ciche cięcia: 25 ms wyciszenia na każdym twardym cięciu w eksporcie |
| Kilka ścieżek audio | ✅ | Muzyka, lektor i efekty grające naraz na osobnych pasach osi (pierwszy wolny pas), do 64 elementów audio |
| Paski ikon na telefonie | ✅ | Pasek główny, pasek klipu, audio i tekstu jak w CapCut, z „<” powrotu; ikona otwiera jedną sekcję ustawień |
| Kolor klipu | ✅ | 7 stylów z próbką i suwaki jasność, kontrast, nasycenie, temperatura; Auto z pomiaru klatek; na wszystkie klipy; podgląd filtrem SVG = eksport `lutrgb` + `colorchannelmixer` (jeden przepis, test pikseli); `projekt.py kolor` (z `--auto` i `--podglad`) |

## Krok 2. Audio

Menu **Audio** (przycisk „Dodaj audio” pod osią, na komputerze zakładka „Audio” w panelu, `hq/web/src/44-audio.js`)
ma pięć kart. Każdy dodany dźwięk to plik obok filmu (`dzwieki/`, `lektor/`), więc projekt działa też bez biblioteki.

| Funkcja | Stan | Opis |
|---|---|---|
| Efekty dźwiękowe | ✅ | Biblioteka CC0 w repo (`hq/web/dzwieki/`, `scripts/dzwieki.py`): 157 efektów w 13 kategoriach (przejścia, reakcje, pieniądze, uderzenia, akcja, interfejs, technika, natura, zwierzęta, codzienne, zabawne, gry, dżingle) z Kenney i Freesound (tylko CC0, licencja sprawdzana przy pobraniu), 8,1 MB; szukanie po polsku i angielsku, odsłuch, dodanie we wskaźniku; `projekt.py dzwieki` (z `--rola`; katalog ma rolę, szczyt i flagę „gra” każdego efektu) i `dodaj-dzwiek` (`--na`: szczyt efektu w chwili) |
| Muzyka | ✅ | 9 podkładów CC0 z biblioteki (do 60 s, z wyciszeniem), muzyka ze skarbca (`wideo/muzyka`, `brands/*/muzyka`), pliki z folderu filmu, wgranie z dysku; bez popularnych utworów; podkład dodaje się ciszej (30%) |
| Wyodrębnij | ✅ | Dźwięk z innego filmu jako osobne audio, a w panelu klipu „Wyodrębnij dźwięk” jak w CapCut: dźwięk klipu zostaje w tym samym miejscu osi, klip się wycisza (AAC kopiowane bez straty); `projekt.py wyodrebnij` |
| Lektor | ✅ | Tekst na mowę Edge TTS (ten sam co w `film.py`), 5 głosów i tempo −30…+30%; `projekt.py lektor` (z czasami słów do napisów) |
| Czysty głos | ✅ | Klip i każde audio: Brak / Lekko / Średnio / Mocno (odszumianie z progiem z tła nagrania, ekspander w pauzach, de-esser, kompresor), Auto z pomiaru tła, Odsłuchaj 8 s po czyszczeniu; `projekt.py glos`, `montaz.py glos`, `klipy.py zbuduj --glos` |
| Nagraj | ✅ | Mikrofon w przeglądarce (MediaRecorder, serwer zapisuje AAC); wymaga HTTPS albo localhost, bez tego wgranie notatki głosowej z telefonu |

## Film z kodu w edytorze (poziom 1)

Prośba właściciela: każdy film, który Wideograf robi kodem (lemo, animacja HTML, anidoodle i inne), da się otworzyć
w edytorze i poprawić jak nagranie: podmienić albo wyciszyć muzykę, poprawić i przesunąć napisy, zmienić głośność, ciąć.
Poziom 2 (później): ruch elementów animacji z parametrów (okno ◐ Animacja) i ponowny render obrazu.

| Funkcja | Stan | Opis |
|---|---|---|
| Dźwięk przypięty do obrazu | ✅ | Element audio z `linked` (głos, efekty) idzie przy cięciu, usunięciu, przestawieniu i duplikacji klipów kawałkami za swoim obrazem; łańcuch na osi, „Odłącz od obrazu” w panelu; `projekt.py dzwiek --przypnij/--odlacz` |
| Projekt z filmu z kodu | ✅ | `projekt.py z-kodu`: czysty obraz (bez wypalonych napisów, bez dźwięku) pocięty na ujęcia (`--ciecia`: liczby, `events.json` lemo, `os_czasu.json`), głos i efekty przypięte do obrazu, muzyka osobno, napisy z SRT albo słów (karaoke); kopie w `<film>-sciezki/` ze wzmocnieniem do −14 LUFS (elementy na 0 dB, gdy szczyt pozwala); `--render`: film = render projektu; projektu zmienionego w edytorze nie nadpisze bez `--nadpisz`. Limiter eksportu −2 dBFS na 4× próbkowaniu (szczyt prawdziwy po AAC pod −1 dBTP także przy transjentach) |
| Silniki i reguła oddania | ✅ | `muzyka.py zrob` zostawia warstwy miksu (`<wynik>.muzyka.sciezki/`: muzyka, efekty, głos), a `z-kodu --z-muzyki` bierze je z planu (słowa przesunięte jak głos); lemo: render `--q nosub=1`, `mix.py` zapisuje `out/sciezki/`, `--ciecia events.json`, `--napisy` z SRT; `maskotka.py` oddaje projekt sam. Reguła w SOUL, `film-z-kodu` (`references/projekt-edytora.md`), `kontrola-wideo`, rubryce i evals; `qa_wideo.py --z-kodu`: błąd bez projektu, bez jego plików albo gdy film nie jest jego renderem |

## Krok 3. Tekst

- **Naklejki:** Fluent Emoji 3D (MIT, ok. 150 wybranych) i nasze naklejki wektorowe z ruchem.
- **Rysowanie** po kadrze, **szablony tekstu** (gotowe zestawy stylu), **animacje tekstu** (wejście, wyjście, pętla).

## Krok 4. Klip

- Animacje wejścia i wyjścia (przybliżenie, oddalenie, wjazd), obrót i odbicie, stop-klatka, odwrócenie, podmiana
  materiału z zachowaniem miejsca na osi.

## Krok 5. Później (jako dodatki)

- Efekty, krzywa tempa, obraz w obrazie, ściszanie muzyki pod mową (ducking).
  Jasność, kontrast i filtry są już w kroku 1 („Kolor klipu”), odszumianie w kroku 2 („Czysty głos”).

## Źródła i licencje

Zaakceptowane przez właściciela: dźwięki CC0 (Kenney, Freesound CC0), Fluent Emoji (MIT), własne naklejki wektorowe,
Edge TTS jak dotąd. Każde nowe źródło trafia do [SOURCES.md](SOURCES.md) w tym samym commicie co pliki.

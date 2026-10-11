---
name: lektor-i-dzwiek
description: "Lektor PL, muzyka pod głos i głośność −14 LUFS."
version: 1.12.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, voiceover, tts, music, loudness, audio]
    related_skills: [krotki-film, montaz-nagran, warianty-ab, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-05"
---

# Lektor i dźwięk

Lektor: Edge TTS (darmowy, bez klucza, neuronowe głosy PL); po angielsku także lokalny Paradee (bez sieci). Muzyka: tylko z prawem użycia. Cel głośności
dla platform społecznościowych: −14 LUFS zintegrowane, true peak ≤ −1 dBTP.

## Kiedy użyć
- Dobór głosu i tempa do filmu, lektor do cudzego nagrania, muzyka i balans, wyrównanie głośności, czysty głos
  w nagraniu (szum, dudnienie, syczenie).

## Głosy
| Głos | Charakter | Dobre do |
|---|---|---|
| `pl-PL-MarekNeural` | męski, spokojny, rzeczowy | poradniki, B2B, explainery |
| `pl-PL-ZofiaNeural` | żeński, ciepły, energiczny | lifestyle, produkt, social |
| `en-US-AndrewMultilingualNeural`, `en-US-AvaMultilingualNeural` | wielojęzyczne (czytają PL z lekkim akcentem) | inny charakter, testy A/B |
| `en-US-Paradee` | angielski, męski, lokalny (model w obrazie, bez sieci i limitów) | film po angielsku; **tylko angielski tekst** |

`en-US-Paradee` działa jak inne głosy (`--glos`, `glos` w scenie, edytor HQ), tempo `--tempo` też; `wysokosc`
pomija. Czasy słów daje Parakeet (pierwsze użycie pobiera jego model, ~0,65 GB), bez niego: rozłożone w zdaniach.

Lista na żywo: `python3 $HERMES_HOME/scripts/film.py glosy`. Tempo: `+0%` spokojnie, `+5…+12%` social,
powyżej `+15%` traci zrozumiałość. Wysokość: `wysokosc: "-2Hz"` cieplej. Dialog: `glos` w pojedynczej scenie.

## Lektor filmu z kodu (narracja)
Explainer i każdy film z kodu z lektorem: `film.py narracja narracja.txt -o out/wideo/src/lektor.wav --os <strona>/os_czasu.json`.
Linia = zdanie, pusty wiersz = akapit = ujęcie, `# tytuł` = rozdział, `|` = podział napisu w miejscu oddechu,
`{nazwa}` = chwila dla animacji. Zdania syntezowane osobno i przycięte do słyszalnej mowy, potem pauzy: 0,33 s
w akapicie, 1 s po akapicie (tu tnie się ujęcie), 1,5 s przed rozdziałem. Film brzmi spokojnie, bo obraz zmienia się
w pauzie, a nie w środku zdania; liczysz ok. 2 słowa na sekundę filmu (60 s ≈ 120 słów, 90 s ≈ 180).
Jedno zdanie na linię: dwa zdania w linii Edge rozdziela własną, nierówną pauzą (zmierzone: ponad 1 s), więc
`narracja` o tym ostrzega. Ostrzega też o zdaniu > 20 słów, napisie > 42 znaków, akapicie > 4 zdań, ujęciu < 4 s,
tempie > 2,7 słowa/s razem z pauzami (Marek przy `+0%` mówi ok. 2,3) i długości poza `--cel`, a z zasad
narracji (`scenariusz/references/narracja.md`) o powitaniu albo definicji na start, liście zamiast opowieści,
opisie obrazu i streszczeniu na końcu. `--sprawdz` = sama kontrola tekstu i szacunek, bez syntezy.
Brief Sherlocka `fakty.json` obok narracji albo katalog wyżej (albo `--fakty`): liczba cyframi z listy niepewnych
= błąd i bez syntezy, liczba bez pokrycia w briefie = ostrzeżenie (dopisz źródło albo usuń). Słowniczek briefu
(`wymowa`) i `--wymowa wymowa.json` (`{"Next.js": "nekst dżej es"}`) zmieniają tylko to, co czyta lektor:
napisy, `slowa.json` i chwile `{nazwa}` zostają w pisowni z tekstu.

## Wymowa
- Liczby tak, jak mają zabrzmieć („trzydzieści procent” gdy „30%” brzmi źle), skróty rozwinięte („między innymi”).
  W narracji fakt zostaje cyframi (sprawdzany z briefem, napis pokazuje „30%”), a brzmienie poprawia `--wymowa`.
- Obce nazwy marek: zapis fonetyczny w tekście lektora, poprawny zapis w `tekst_ekranowy` i SRT; w narracji
  zapis poprawny w tekście, a fonetyczny w słowniczku briefu albo `--wymowa`.
- Test wymowy („odsłuch” uszami Parakeet): `film.py lektor "<zdanie>" -o /tmp/test.mp3`, potem
  `montaz.py transkrypcja /tmp/test.mp3 -o /tmp/test` i porównaj `/tmp/test.txt` z tekstem. Słowo rozpoznane
  inaczej = niewyraźna wymowa: zmień zapis (fonetycznie, prościej) i powtórz.

## Czysty głos (nagranie właściciela, telefon, laptop)
Szum wentylatora, dudnienie, syczące „s” i nierówna głośność. Trzy poziomy (ten sam łańcuch w edytorze HQ, `projekt.py`,
`montaz.py` i clipmakerze): **lekki** = dobre nagranie (dudnienie i łagodne wyrównanie, tło bez zmian), **sredni** =
zwykły pokój (też syczenie, odszumianie i ciszej w pauzach: tło −10 dB, mowa +2 dB), **mocny** = telefon, laptop,
hałas (tło ~−15 dB, mowa równiejsza, szczyty do −1 dBFS). `auto` dobiera poziom z tła nagrania.
- Projekt montażu (edytor HQ, rolka clipmakera): `projekt.py glos <film> --wszystkie [--poziom auto]`; poziom do
  odsłuchu dla właściciela: `--probka` (8 s po czyszczeniu obok filmu, `MEDIA:`). `pokaz` mówi, co ustawione.
- Cały plik (nagranie przed montażem): `montaz.py glos <nagranie> -o <wynik> [--poziom auto]`, obraz bez zmian,
  potem `montaz.py glosnosc` (kompresor zmienia głośność).
- Clipmaker robi to sam (`zbuduj --glos auto`, `brak` = bez).
- Nie na lektorze TTS ani muzyce: one są czyste; czysty głos to nagrania mikrofonem.
- Mocny ścisza też ciche końcówki słów w głośnym tle: przy szeptach i cichych fragmentach zostań przy średnim.

## Muzyka
- Źródła: biblioteka użytkownika `@@KNOWLEDGE_DIR@@/wideo/muzyka/` (plan: `"muzyka": {"plik": "losowa"}`),
  muzyka marki `brands/<marka>/muzyka/`, plik z karty, a gdy ich brak: podkłady CC0 z biblioteki edytora
  (`projekt.py dzwieki --muzyka`, `dodaj-dzwiek`; „losowa” bierze je sama) albo muzyka pisana kodem pod ten film
  (`muzyka.py`, niżej). Inny utwór tylko z licencją
  (zaproponuj w RAPORT: YouTube Audio Library, Pixabay Music, pobrane przez użytkownika do biblioteki). Przy utworze
  z sieci zapisz w RAPORT link do jego strony i nazwę licencji: część darmowych utworów ma zgłoszenia Content ID,
  a ten link pozwala właścicielowi odwołać zgłoszenie.
- **Muzyka pisana kodem pod obraz** (film z kodu, motion graphics, logo, promo; mgaudio z mg-styles-15, MIT,
  sample VCSL CC0, więc bez licencji do sprawdzania): `python3 $HERMES_HOME/scripts/muzyka.py zrob obraz.mp4
  -o final.mp4 --cues cues.json --styl <styl ze style-motion>` albo `--przepis` (`muzyka.py przepisy`: 15 gatunków
  od synthwave po explainer). Utwór powstaje pod ten film: takt 0 kulminacji w chwili najmocniejszego uderzenia
  z `cues.json` (albo `--kulminacja T`), od logo (ostatni błysk albo `--koniec T`) gra końcowy akord do ostatniej
  klatki, tempo z zakresu gatunku dobrane do zdarzeń. Efekty z `cues.json` (nazwy jak w `sound.mjs`, plus własne
  mgaudio: `muzyka.py efekty`) grają w tych samych chwilach, a muzyka przysiada pod każdym o 3 dB: to zamiast
  `sound.mjs`, nie razem z nim. Wynik: −14 LUFS, szczyt ≤ −1 dBTP także po AAC, słyszalność każdego efektu
  (te same progi co `slychac`), plan `final.muzyka.json` (tempo, takty, sekcje, akordy). Cięcia i akcenty obrazu
  kładziesz na `takty` z planu (rytm.py zgaduje początek taktu i bywa przesunięty o 2 bity); kod wyjścia 1 = do
  poprawy. Z lektorem (`film.py narracja` → `lektor.wav`): `muzyka.py zrob obraz.mp4 -o final.mp4 --lektor
  lektor.wav --cues cues.json` miksuje głos ok. 10 dB nad muzyką, muzyka przysiada o 8 dB, gdy lektor mówi
  (razem ok. −18 dB), i wraca w pauzach między akapitami (oddech w akapicie jej nie podnosi), efekty pod mową
  ciszej o 4 dB; słyszalność efektów liczona względem głosu i muzyki, a raport podaje muzykę pod głosem i w pauzach
  (poza −22…−14 dB = uwaga). Efekt przejścia kładziesz w pauzie akapitu (`odcinki` mowy w planie). Obok planu
  leżą warstwy miksu osobno (`<wynik>.muzyka.sciezki/`: muzyka, efekty, głos; w planie `"sciezki"`): z nich
  `projekt.py z-kodu … --z-muzyki <plan>` składa projekt edytora, w którym właściciel zdejmie albo podmieni muzykę. Sam podkład:
  `--bez-efektow --dlugosc S -o podklad.wav`, potem plan film.py `"muzyka": {"plik": …}` albo `projekt.py dodaj-audio`. Raz: `narzedzia.py instaluj mgaudio` (ok. 450 MB).
- Głośność pod lektorem 0,08–0,16, czyli −22…−16 dB względem głosu (plan: `glosnosc`, domyślnie 0,14); `film.py` ścisza muzykę automatycznie, gdy mówi lektor
  (sidechain) i wycisza ją na końcu.
- Nigdy: muzyka z list przebojów, „znalezione na YouTube”, muzyka z cudzych filmów.
- Rytm: `python3 $HERMES_HOME/scripts/rytm.py muzyka.mp3 [--json rytm.json]` (BPM, takty, drop, perkusja): cięcia
  na taktach, najmocniejsza scena na dropie. Najpierw `siatka`: „pewna” i „dobra” to bity pod cięcia, „niepewna”
  (swobodne tempo, mowa, brak perkusji) to tylko wskazówka, sprawdź uchem.
  Perkusja w trzech pasmach mówi, jaki ruch (za video-shotcraft, Apache-2.0): **stopa** = uderzenie (skok skali,
  „zgniecenie”), **werbel** = zamiana (cięcie, nowy element), **talerze** = gęstość drobnego ruchu (gęste: drobny
  ruch może być gęsty, rzadkie: spokój). `uderzenia` to pula do wyboru, nie lista zdarzeń: stopa gra prawie na
  każdym bicie. Uderzenie całego kadru (błysk, wstrząs) tylko na `najmocniejsze`: najwyżej 3 na film, co najmniej
  16 bitów od siebie, najpierw stopy na bicie (razem z cięciem), nic w pierwszej sekundzie.
- Po renderze: `rytm.py sprawdz final.mp4 [--plan cues.json | --projekt film.edycja.json | --ciecia 1.2,3.4]` liczy
  bity z dźwięku GOTOWEGO filmu i błąd każdego cięcia (bez planu: cięcia wykryte w obrazie): do 1,5 klatki idealnie,
  do 3 dobrze, ponad 3 popraw (kod wyjścia 1). Wszystkie cięcia przesunięte o tyle samo to przesunięcie dźwięku
  przy kodowaniu (AAC): przesuń całą muzykę i efekty o podane ms, nie poprawiaj cięć po kolei.

## Efekty dźwiękowe
Prawdziwe nagrania na kliknięcia, świsty, przejścia i lądowania. Kolejność źródeł:
1. **Biblioteka CC0 (najpierw, montaż i projekt z edytora HQ):** `python3 $HERMES_HOME/scripts/projekt.py dzwieki
   [--kategoria K] [--rola R] [--szukaj fraza]`: 157 efektów w 13 kategoriach (przejścia, reakcje, pieniądze, uderzenia,
   akcja, interfejs, technika, natura, zwierzęta, codzienne, zabawne, gry i retro, dżingle) i 9 podkładów (`--muzyka`);
   ta sama biblioteka co menu Audio w edytorze HQ, licencja CC0, bez podpisu. Przy efekcie: szczyt (s od początku
   pliku), rola i flaga „gra”. Role (za video-shotcraft, Apache-2.0: słownik efektów dobierasz do rodzaju filmu):
   narastanie, uderzenie, blysk, ruch (whoosh), przejscie, pojawienie, klik, pisanie.
   **Film produktowy i reklama: bez efektów z flagą „gra”** (syntetyczne tony interfejsu i dźwięki z gier: film brzmi
   jak gra mobilna). Zakazana jest barwa, nie czynność: prawdziwy klik albo przełącznik pod kliknięcie w obrazie
   zostaje. Wyjątek: film celowo w stylu gry (pixel, 8-bit) albo „system mówi” (potwierdzenie, błąd), opisany w RAPORT.
   `projekt.py dodaj-dzwiek <film> <id> --start S [--glosnosc 0.8]`: efekt na osi (kopia w `<katalog filmu>/dzwieki/`).
   Efekt gra od razu w chwili `--start` (cisza na początku pliku jest przycięta). `--na T` zamiast `--start` kładzie
   efekt tak, by jego szczyt trafił w T (narastanie zaczyna się ok. 2 s wcześniej): tak stawiasz efekt na cięciu i akcji.
2. **Synteza z osi animacji (film z kodu, wiele zdarzeń co do klatki):** efekty bez plików i licencji:
   `node $ANIM/scripts/sound.mjs cues.json film.mp4 final.mp4 --lufs -14 [--bed muzyka.wav --bed-at 2.0]`
   (`eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env animacja)"`). `cues.json`: `[{"sfx":"click","t":0.94},
   {"sfx":"whoosh","t":1.08,"dur":0.5}]`; dźwięki: pop, whoosh, whip, tick, thump, crack, sparkle, buzz, scratch,
   drip, boing, riser, splash, click, step, fall, chime, chirp, burner (+ `vol`, `pan`, `pitch` 0,9–1,3, żeby się nie powtarzały).
   Czasy: zdarzenia w obrazie (klik, zmiana stanu, cięcie) i bity z `rytm.py`; cue **~0,03 s przed** klatką zdarzenia.
   Bez ciągłego „skrobania” pod rysowaniem: dźwięk mają kontakty, nie rysowanie.
3. **Brak w bibliotece:** biblioteka marki, `@@KNOWLEDGE_DIR@@/wideo/sfx/`, potem Mixkit i Pixabay, ale **tylko
   pliki z darmową licencją sprawdzoną na stronie tego pliku**: Mixkit „Free License” (nie „Restricted”), Pixabay
   „Content License” (bez sponsorowanych wyników iStock w wyszukiwarce: są płatne). Do RAPORT: link do strony pliku
   i nazwa licencji. Plik żyje tylko w filmie: nie oddajesz go klientowi osobno ani w paczce plików.
   Strona kategorii `mixkit.co/free-sound-effects/<słowo>/` (np. click, whoosh, pop, typing) ma linki do plików
   `assets.mixkit.co/…` → `curl -L` do `out/wideo/src/sfx/`; jeden efekt na zdarzenie, nazwa = zdarzenie.

- Każdy efekt dokładnie na swojej klatce (wg osi animacji): `rytm.py efekty/*.wav --szczyt` mówi, gdzie ma szczyt,
  więc start = chwila zdarzenia − szczyt (pliki z biblioteki CC0: szczyt w `projekt.py dzwieki`, a `dodaj-dzwiek --na`
  liczy start sam; klik i pop mają szczyt w pierwszych 0,02 s, narastanie na końcu).
- Czas efektu (za skillem fframes, MIT): **whoosh** zaczyna się ok. 0,15 s przed szczytem ruchu, **pop i klik**
  w klatce, w której element się pojawia (od −0,03 do +0,05 s). W filmie z kodu czasy efektów licz z tych samych
  stałych co animacja, wtedy przesuną się razem ze sceną.
- Umiar: 1 efekt na kilka sekund, whoosh na przejściu, „kasa” przy cenie, oklaski przy wyniku.
- **Zdanie dźwiękowe** (za video-shotcraft, Apache-2.0) na dużą chwilę: stempel logo, finał, lądowanie głównego
  elementu. Narastanie (słychać 1,17 s, czyli 35 klatek przy 30 kl./s) → uderzenie (najgłośniejsza chwila filmu)
  → błysk 0,83 s (25 klatek) po uderzeniu. `projekt.py zdanie <film> --na T [--przed ID|brak] [--uderzenie ID]
  [--po ID|brak]` kładzie wszystkie trzy szczytami (efekty z ról narastanie, uderzenie, blysk). Najwyżej 2 na film
  (finał i jedna kulminacja): częste duże uderzenie traci siłę, `zdanie` ostrzega przy trzecim. Film z kodu: to samo
  w `cues.json` (riser, thump, sparkle) z tych samych czasów.
- **Seria bez karabinu** (elementy listy wskakują po kolei, karty, kafelki): dwa różne efekty na zmianę, głośność
  od 0,40 do 0,25 (każdy następny ciszej, jak oddalanie się), odstępy z animacji (gdy przyspiesza, efekty też).
  Gęściej niż co 0,1 s (3 klatki) ucho nie liczy uderzeń: zamiast nich jeden whoosh przez cały zlepek.
  `projekt.py seria <film> --czasy 2.0,2.2,2.4 [--id pop] [--id2 plop]` robi to sam (para z tej samej roli, inny plik).
  Film z kodu: w `cues.json` na zmianę dwa dźwięki (np. pop i drip albo inny `pitch`), `vol` od 0,40 do 0,25.
  Cel: rytm, który da się policzyć, nie maszynowe powtórzenie.
- Głośność względem głosu (głos = 0 dB): muzyka pod głosem −22…−16 dB (wyżej, „Muzyka”), efekty interfejsu i whoosh
  −14…−8 dB, a gdy lektor mówi w tej chwili, ciszej: −18…−12 dB (głośność efektu ok. 0,5–0,8); całość −14 LUFS.
  Ogranicznik nie naprawia złych proporcji: popraw głośności ścieżek.
- **Słyszalność** (pomysł i progi za video-talkcraft, licencja niekomercyjna: tylko zasada i liczby): efekt, którego
  nie słychać pod głosem, jest tylko kosztem. Po ułożeniu efektów: projekt z edytora `projekt.py slychac <film>`
  (tło składane tym samym kodem co eksport, bez efektów), film z kodu `projekt.py slychac final.mp4 --cues cues.json
  --bed glos.wav` (te same `--bed-vol`/`--bed-at` co dla `sound.mjs`). Każdy efekt kontra tło w tej samej chwili:
  **czysto** (w ciszy tła, czyli w oddechu lektora albo pauzie muzyki, albo 6 dB nad tłem), **słychać** (najwyżej
  6 dB pod tłem), **zagłuszony**, **bez dźwięku** (szczyt poniżej −45 dBFS). Do poprawy (kod wyjścia 1): jakikolwiek bez
  dźwięku, zagłuszonych ponad połowa albo czysto słyszalnych mniej niż max(3, długość/30 s). Poprawka: whoosh,
  przejście, pop i klik przesuń w ciszę tła w pobliżu (rada podaje sekundę; efekt przejścia najlepiej w oddechu
  ok. 0,3 s między zdaniami), a narastanie, uderzenie i błysk zdania zostają w miejscu i idą głośniej.
- Dźwięk z nagrania: `projekt.py wyodrebnij <film> <id klipu>` robi z dźwięku klipu osobne audio (np. żeby przeciągnąć
  go pod inne ujęcie), `--plik inny.mp4` bierze dźwięk z innego filmu. `projekt.py lektor <film> "tekst" --start S`:
  lektor wprost na oś projektu.

## Głośność nagrań
`montaz.py glosnosc <plik> -o <wynik> --lufs -14` (dwa przejścia loudnorm, potem limiter szczytów, więc podniesienie
głośności nie wypycha true peak ponad −1; film z `sound.mjs` wychodzi ok. −16 LUFS i tędy idzie na −14). Pomiar: `qa_wideo.py <plik>` → `lufs`, `true_peak`,
`lra` (rozpiętość głośności). Cele: −14 LUFS (podcast −16), true peak ≤ −1 dBTP, rozpiętość 4–10 LU (więcej = ciche
i głośne części do wyrównania; `qa_wideo.py` ostrzega od 10 LU w filmie od 10 s), sceny z głosem w granicach ok. 2 LU
od siebie, cisza tylko tam, gdzie zaplanowana (nagła cisza = ścieżka kończy się za wcześnie albo brak pliku).

## Własny lektor użytkownika
Plik nagrania w planie: `"lektor": {"plik": "out/wideo/src/lektor.m4a"}` + `czas` scen (albo podział wg długości tekstu);
napisy z transkrypcji. Najpierw `montaz.py cisza` i `glosnosc` na nagraniu.

## Definition of Done
- [ ] głos dobrany do marki i odbiorcy (uzasadnienie 1 zdanie w RAPORT),
- [ ] wymowa nazw i liczb sprawdzona; tempo 2–3 słowa/s,
- [ ] −14 LUFS ±2, true peak ≤ −1 dBTP, rozpiętość ≤ 10 LU; muzyka nie zagłusza głosu i ma źródło z licencją,
- [ ] efekty na swoich klatkach (whoosh ~0,15 s przed szczytem ruchu, pop w klatce pojawienia).

---
name: lektor-i-dzwiek
description: "Lektor PL, muzyka pod głos i głośność −14 LUFS."
version: 1.4.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, voiceover, tts, music, loudness, audio]
    related_skills: [krotki-film, montaz-nagran, warianty-ab, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-03"
---

# Lektor i dźwięk

Lektor: Edge TTS (darmowy, bez klucza, neuronowe głosy PL). Muzyka: tylko z prawem użycia. Cel głośności
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

Lista na żywo: `python3 $HERMES_HOME/scripts/film.py glosy`. Tempo: `+0%` spokojnie, `+5…+12%` social,
powyżej `+15%` traci zrozumiałość. Wysokość: `wysokosc: "-2Hz"` cieplej. Dialog: `glos` w pojedynczej scenie.

## Wymowa
- Liczby tak, jak mają zabrzmieć („trzydzieści procent” gdy „30%” brzmi źle), skróty rozwinięte („między innymi”).
- Obce nazwy marek: zapis fonetyczny w tekście lektora, poprawny zapis w `tekst_ekranowy` i SRT.
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
  (`projekt.py dzwieki --muzyka`, `dodaj-dzwiek`; „losowa” bierze je sama). Inny utwór tylko z licencją
  (zaproponuj w RAPORT: YouTube Audio Library, Pixabay Music, pobrane przez użytkownika do biblioteki). Przy utworze
  z sieci zapisz w RAPORT link do jego strony i nazwę licencji: część darmowych utworów ma zgłoszenia Content ID,
  a ten link pozwala właścicielowi odwołać zgłoszenie.
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
- Głośność względem głosu (głos = 0 dB): muzyka pod głosem −22…−16 dB (wyżej, „Muzyka”), efekty interfejsu i whoosh
  −14…−8 dB, a gdy lektor mówi w tej chwili, ciszej: −18…−12 dB (głośność efektu ok. 0,5–0,8); całość −14 LUFS.
  Ogranicznik nie naprawia złych proporcji: popraw głośności ścieżek.
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

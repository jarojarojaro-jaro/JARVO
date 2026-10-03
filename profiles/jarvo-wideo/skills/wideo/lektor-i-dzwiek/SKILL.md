---
name: lektor-i-dzwiek
description: "Lektor PL, muzyka pod głos i głośność −14 LUFS."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, voiceover, tts, music, loudness, audio]
    related_skills: [krotki-film, montaz-nagran, warianty-ab, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Lektor i dźwięk

Lektor: Edge TTS (darmowy, bez klucza, neuronowe głosy PL). Muzyka: tylko z prawem użycia. Cel głośności
dla platform społecznościowych: −14 LUFS zintegrowane, true peak ≤ −1 dBTP.

## Kiedy użyć
- Dobór głosu i tempa do filmu, lektor do cudzego nagrania, muzyka i balans, wyrównanie głośności.

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

## Muzyka
- Źródła: biblioteka użytkownika `@@KNOWLEDGE_DIR@@/wideo/muzyka/` (plan: `"muzyka": {"plik": "losowa"}`),
  muzyka marki `brands/<marka>/muzyka/`, plik z karty, a gdy ich brak: podkłady CC0 z biblioteki edytora
  (`projekt.py dzwieki --muzyka`, `dodaj-dzwiek`; „losowa” bierze je sama). Inny utwór tylko z licencją
  (zaproponuj w RAPORT: YouTube Audio Library, Pixabay Music, pobrane przez użytkownika do biblioteki).

## Efekty dźwiękowe (biblioteka CC0)
- `python3 $HERMES_HOME/scripts/projekt.py dzwieki [--kategoria K] [--szukaj fraza]`: 157 efektów
  w 13 kategoriach (przejścia, reakcje, pieniądze, uderzenia, akcja, interfejs, technika, natura, zwierzęta, codzienne,
  zabawne, gry i retro, dżingle) i 9 podkładów (`--muzyka`); ta sama biblioteka co menu Audio w edytorze HQ.
- `projekt.py dodaj-dzwiek <film> <id> --start S [--glosnosc 0.8]`: efekt na osi (kopia w `<katalog filmu>/dzwieki/`).
  Efekt gra od razu w chwili `--start` (cisza na początku pliku jest przycięta): stawiaj go na cięciu albo akcji.
- Umiar: 1 efekt na kilka sekund, whoosh na przejściu, „kasa” przy cenie, oklaski przy wyniku; głośność efektu
  pod lektorem ok. 0,5–0,8.
- `projekt.py wyodrebnij <film> <id klipu>`: dźwięk klipu jako osobne audio (np. żeby przeciągnąć go pod inne ujęcie);
  `--plik inny.mp4` bierze dźwięk z innego filmu. `projekt.py lektor <film> "tekst" --start S`: lektor wprost na oś.
- Głośność pod lektorem 0,10–0,18 (plan: `glosnosc`); `film.py` ścisza muzykę automatycznie, gdy mówi lektor
  (sidechain) i wycisza ją na końcu.
- Nigdy: muzyka z list przebojów, „znalezione na YouTube”, muzyka z cudzych filmów.
- Rytm: `python3 $HERMES_HOME/scripts/rytm.py muzyka.mp3` (BPM, takty, drop): cięcia na taktach, najmocniejsza
  scena na dropie; sprawdź uchem przy swobodnym tempie.

## Efekty dźwiękowe
- Prawdziwe nagrania na kliknięcia, świsty, przejścia i lądowania (syntetyczne brzmią tanio): biblioteka marki,
  `@@KNOWLEDGE_DIR@@/wideo/sfx/`, Mixkit i Pixabay (darmowe komercyjnie, bez podpisu; źródło i licencja w RAPORT).
- **Najpierw syntezuj (zalecane):** efekty z osi czasu obrazu, bez plików i licencji:
  `node $ANIM/scripts/sound.mjs cues.json film.mp4 final.mp4 --lufs -14 [--bed muzyka.wav --bed-at 2.0]`
  (`eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env animacja)"`). `cues.json`: `[{"sfx":"click","t":0.94},
  {"sfx":"whoosh","t":1.08,"dur":0.5}]`; dźwięki: pop, whoosh, whip, tick, thump, crack, sparkle, buzz, scratch,
  drip, boing, riser, splash, click, step, fall, chime, chirp, burner (+ `vol`, `pan`, `pitch` 0,9–1,3, żeby się nie powtarzały).
  Czasy: zdarzenia w obrazie (klik, zmiana stanu, cięcie) i bity z `rytm.py`; cue **~0,03 s przed** klatką zdarzenia.
  Bez ciągłego „skrobania” pod rysowaniem: dźwięk mają kontakty, nie rysowanie.
- Pobierasz sam: strona kategorii `mixkit.co/free-sound-effects/<słowo>/` (np. click, whoosh, pop, typing) ma linki
  do plików `assets.mixkit.co/…` → `curl -L` do `out/wideo/src/sfx/`; jeden efekt na zdarzenie, nazwa = zdarzenie.
- Każdy efekt dokładnie na swojej klatce (wg osi animacji): `rytm.py efekty/*.wav --szczyt` mówi, gdzie ma szczyt,
  więc start = chwila zdarzenia − szczyt. Cicho pod lektorem (−18…−12 dB względem głosu), całość −14 LUFS.

## Głośność nagrań
`montaz.py glosnosc <plik> -o <wynik> --lufs -14` (dwa przejścia loudnorm). Pomiar: `qa_wideo.py <plik>` → `lufs`, `true_peak`.

## Własny lektor użytkownika
Plik nagrania w planie: `"lektor": {"plik": "out/wideo/src/lektor.m4a"}` + `czas` scen (albo podział wg długości tekstu);
napisy z transkrypcji. Najpierw `montaz.py cisza` i `glosnosc` na nagraniu.

## Definition of Done
- [ ] głos dobrany do marki i odbiorcy (uzasadnienie 1 zdanie w RAPORT),
- [ ] wymowa nazw i liczb sprawdzona; tempo 2–3 słowa/s,
- [ ] −14 LUFS ±2, true peak ≤ −1 dBTP; muzyka nie zagłusza głosu i ma źródło z licencją.

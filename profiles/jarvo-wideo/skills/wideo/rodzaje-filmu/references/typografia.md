# Typografia w ruchu

Tekst jest bohaterem: hasło, cytat, manifest, lyric video, słowa w rytm, animowany tytuł.
Nie to: tekst tylko jako napisy do lektora → `napisy`; logo → `logo-intro.md`; liczby i wykresy → `dane.md`.

## Wynik
- 5–15 s hasło albo tytuł; 30–60 s manifest albo lyric video; 9:16 na social, 16:9 na YouTube i ekrany.
- Tekst ostry, poprawny, z polskimi znakami; zsynchronizowany z lektorem albo muzyką.

## Silnik
| Styl | Silnik |
|---|---|
| promo z animowanym tekstem, szybko | HyperFrames |
| reveal masek, stagger liter/słów, zmienny font, tekst po ścieżce | `kinetic-typography` (HTML + `html_wideo.py --preset iart`) |
| pełna kontrola, tło z ruchem, kamera | własny HTML (`kontrakt-html.md`) |
| seria z danymi (np. 20 cytatów) | Remotion (`remotion-best-practices`) |

## Struktura
- **Hasło (8 s):** 0–1 pierwsze słowo już w ruchu; 1–6 reszta frazy, akcent na słowie kluczowym; 6–8 zatrzymanie (czytanie).
- **Manifest / lyric (30–60 s):** fraza = scena; 2–4 słowa naraz; słowa kluczowe większe i w kolorze akcentu;
  co 3–4 frazy zmiana układu (rozmiar, kierunek, tło), żeby rytm nie usypiał.
- Czasy słów: lektor `film.py lektor` → `*.slowa.json`; piosenka → `montaz.py transkrypcja` (popraw tekst ręcznie).

## Rzemiosło
- Najpierw statyka: interlinia 1,1–1,2 dla tytułów, zwężone światło (−1 do −3%), jeden krój (maks. dwa).
- Podział: po liniach (spokojnie, premium), po słowach (energia), po literach (tylko krótkie słowa).
- Wejście: maska (tekst wyjeżdża spod linii) > blur > fade; stagger linii 60–100 ms, słów 40–70 ms, liter 20–40 ms.
- Ruch w kierunku czytania (lewo → prawo, góra → dół); nic nie jedzie wstecz podczas czytania.
- Czas czytania: ≥ 0,3 s na słowo po pełnym wejściu; akcent wizualny zgodny z akcentem mowy albo bitem.
- Minimalny rozmiar: ~5% wysokości kadru na telefonie; kontrast 4,5:1; poza strefami UI platformy.

## Brief (`out/wideo/src/BRIEF.md`)
```
Tekst (dokładnie, z interpunkcją) i słowa kluczowe:          Źródło czasu (lektor / muzyka / siatka BPM):
Krój, kolory, akcent:                                        Podział (linie / słowa / litery) i techniki wejścia:
Format, długość, tło (jednolite / ruch / wideo):
```

## Pułapki
- Za dużo tekstu naraz; efekt na każdej literze długiego zdania; tekst, który znika, zanim da się go przeczytać.
- Brak polskich znaków w foncie (kwadraty albo zastępczy krój); literówka w haśle (sprawdź z kartą znak po znaku).

## Kontrola
- Arkusz w chwilach pełnego wejścia każdej frazy: czytelne, bez obciętych ogonków (ą, ę, g, y) i nakładania.
- Pasek klatek na wejściu: kierunek zgodny z czytaniem; tekst = karta 1:1 (wielkość liter, interpunkcja).

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py typografia --ile 3` (albo `--szukaj lyric`).

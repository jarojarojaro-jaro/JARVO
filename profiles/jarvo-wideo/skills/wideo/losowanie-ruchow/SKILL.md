---
name: losowanie-ruchow
description: "Losowanie ruchów z biblioteki 273 technik przed projektem."
version: 1.0.0
author: "Jarvo (biblioteka: cinetic, MIT, Leonxlnx)"
license: MIT
metadata:
  hermes:
    tags: [video, motion, technique-library, random-draw, transitions, camera, typography, product-demo]
    related_skills: [rodzaje-filmu, film-z-kodu, style-motion, typografia-edit, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-18"
---

# Losowanie ruchów

Sam z siebie sięgam po pierwszy znany ruch: ten sam fade-up, ten sam najazd, ta sama plansza końcowa. Każdy film
wygląda wtedy tak samo. Dlatego **najpierw losuję, potem projektuję**: `ruchy.py` bierze z biblioteki 273 technik
(14 kategorii: otwarcia, przejścia, kamera, typografia, choreografia UI, dane, demo produktu, logo i plansza,
kolor i światło, faktura, kompozycja, tempo, mikrointerakcje, głębia 3D) z wagami pod rodzaj filmu i energię,
i wypisuje przepis każdego ruchu. Biblioteka to cinetic (MIT, Leonxlnx), przepisy przeniesione na nasz kontrakt HTML.

## Kiedy
- Film z kodu z ruchem projektowanym od zera: promo produktu, film funkcji, przejście przez aplikację, logo-intro,
  pętla, rolka 9:16, motion graphics. Losujesz przy briefie, zanim powstanie mapa bitów.
- Pojedynczy brak w gotowym planie (potrzebne przejście, otwarcie, finał): `--kategoria … --ile 1..3`.

## Nie do
- Montaż nagrań i klipy z długiego materiału (`montaz-nagran`, `clipmaker`), reels ze stocku (`krotki-film`):
  tam ruch daje materiał.
- Styl z gotowym silnikiem i własną gramatyką ruchu (`style-malarskie`, lemo-opuscar, `gramatyki-explainera`):
  losujesz najwyżej przejścia albo finał, nie cały plan.

## Kroki
```bash
R=$HERMES_HOME/scripts/ruchy.py
python3 $R losuj --rodzaj promo --sekundy 30 --json out/wideo/src/ruchy.json   # plan na film
python3 $R losuj --rodzaj pion --energia spokojna                               # spokojnie (bez uderzeń i śmignięć)
python3 $R losuj --kategoria przejscie --ile 2 --rodzaj promo --bez tr-shape-match-cut  # ponowne losowanie
python3 $R karta cam-living-hold                                                # jedna technika w całości
python3 $R lista --kategoria dane --rodzaj funkcja                              # przegląd po losowaniu
```
1. **Rodzaj**: `promo` (premiera, reklama), `funkcja` (jedna funkcja produktu), `aplikacja` (przejście przez
   aplikację), `logo` (logo-intro, sting), `petla` (pętla, tło), `pion` (rolka 9:16). Explainer, dane, typografia
   i historia nie mają planu: losujesz kategoriami (`--kategoria dane|typografia|przejscie|logo-i-plansza`).
2. **Energia** z charakteru ruchu marki (`ruch-i-kompozycja.md`): `zaufanie`, `luksus`, `spokojny` → `spokojna`;
   `przyjazny` → `srednia` (domyślna); `odwazny`, `zabawny` → `wysoka`. Plan ma ~1 ruch na 2,5 s (spokojny na 3,5 s).
3. **Losuj przed projektem** i zapisz `--json out/wideo/src/ruchy.json`; ziarno i listę ruchów wpisz do
   `BRIEF.md` (część „struktura”), a każdy ruch postaw w mapie bitów na konkretnej sekundzie.
4. **Buduj to, co koncept uniesie**, opowiedziane przedmiotami filmu (produkt, dane, marka), nie przepisane
   dosłownie. Ruch walczący z konceptem: nowe losowanie tej samej kategorii z `--bez <id>`, **najwyżej 2 razy**,
   albo odrzucenie z jednym zdaniem powodu w BRIEF. Nie dodajesz ruchu, którego losowanie nie dało.
5. **Przepis → kod**: przepisy są po angielsku i w języku Remotion (klatki przy 60 kl./s). Tłumaczysz je na nasz
   kontrakt HTML według `references/przepisy.md`: krzywe, sprężyny, puls i kolory z `/_lib/jarvo/tokeny.js`,
   czas w sekundach (`f(18)` = 0,3 s), komponenty Remotion na nasze moduły.
6. **Następny film tej samej marki**: `--unikaj out/wideo/src/ruchy.json` z poprzedniego, żeby seria się nie powtarzała.

## Zasady
- Losowanie to punkt startu, nie norma do wyrobienia: lepiej 5 ruchów zrobionych dobrze niż 12 na pokaz.
- Nasze zasady wygrywają z przepisem: bez motion bluru (smugi i duchy z `ruch.js`), jeden bohater na ujęcie,
  zasada tempa i czas na przeczytanie. Kolor, krój, gradient, poświata: decyduje marka, nie biblioteka; przepis
  ze znakiem „wariant bez …” możesz zbudować w pełnej wersji, gdy marka to niesie.
- Tekst nigdy nie przestrzeliwuje (słowa po `E.outSoft` albo `SPR.calm`); przestrzelenie tylko przy prawdziwym
  lądowaniu, najwyżej 2 na film.
- Przepis podaje dźwięk: bierzesz go do „zdań dźwiękowych” (`lektor-i-dzwiek`), z naszej biblioteki efektów.

## Definition of Done
- [ ] `ruchy.json` z ziarnem zapisany przed mapą bitów; każdy ruch w mapie bitów albo odrzucony z powodem,
- [ ] żaden ruch spoza losowania; najwyżej 2 ponowne losowania na slot,
- [ ] ruchy zbudowane na `tokeny.js` (bez surowych krzywych w kodzie sceny), czas w sekundach z `t`.

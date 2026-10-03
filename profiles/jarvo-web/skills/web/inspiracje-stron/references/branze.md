# Mapa branż: polski klient → filtry Inspo

Katalog Inspo 0.1.16 (`inspo-mcp`): 832 strony, 2320 podstron, 24 branże. Liczby policzone 2026-10-03 z danych katalogu
(`packages/db/src/static-screens.json` w repo Nutlope/inspo, commit `0e1e636`): **w filtrze** = strony z tym tagiem
`industry`, **trafne** = strony, których tytuł i opis naprawdę dotyczą tej branży (słowa kluczowe + przegląd).
**Ocena:** dobre ≥ 30 trafnych, średnie 10–29, słabe < 10 (wtedy własna baza w skarbcu, SKILL.md).
Nowa wersja Inspo w `infra/node/package.json` = przelicz tabelę.

`industry` przyjmuje tylko `search_screens`. `recommend` filtruje `vibe`, `mode`, `pageType`, `color`, `macrostructure`;
branżę wpisujesz do angielskiego `brief`. Kolumna „Katalog” to folder własnej bazy: `inspiracje/strony/<katalog>/`.

| Branża klienta | `industry` | Inne filtry | Zapytanie (EN) | W filtrze | Trafne | Ocena | Katalog |
|---|---|---|---|---|---|---|---|
| nieruchomości: biuro nieruchomości, deweloper | `architecture` (zastępczo) | vibe `calm`/`luxe`, style `editorial`, macro `photographic`/`split-studio` | luxury real estate homes apartments property | 23 | 2 (humahome.com: domy premium, middle.finance: kredyt) | słabe | `nieruchomosci` |
| gabinet lekarski i stomatologiczny | `health` | vibe `calm`/`soft`, style `minimalism`, macro `marquee-hero` | medical clinic patient care | 25 | 7 (kliniki i telemedycyna; 0 stomatologów) | słabe | `medycyna` |
| uroda i salon (fryzjer, kosmetyczka, spa) | `fashion` („Fashion & Beauty”) | vibe `soft`/`luxe`, style `editorial` | beauty skincare salon spa | 41 | 3 (sklepy z kosmetykami; 0 salonów) | słabe | `uroda` |
| fitness i siłownia | `health` | vibe `serious`/`technical`, mode `dark`, macro `marquee-hero`/`photographic` | fitness gym training workout | 25 | 7 (aplikacje, sprzęt, odzież; 0 siłowni) | słabe | `fitness` |
| restauracja i kawiarnia | `food-beverage` | vibe `warm`/`soft`, macro `marquee-hero`/`photographic` | restaurant menu dining (kawiarnia: coffee cafe) | 25 | 12 | średnie | `gastronomia` |
| hotel i pensjonat | `travel` | vibe `calm`/`luxe`, macro `marquee-hero`/`split-studio` | boutique hotel rooms booking | 9 | 4 (Belmond, Lyfe, The Standard, Explora) | słabe | `hotele` |
| budowlanka i remonty | `architecture` (zastępczo) | vibe `serious`/`technical`, style `swiss` | construction building company projects | 23 | 2 (Désourdy, Enerblock) | słabe | `budownictwo` |
| architekt i wnętrza | `architecture`, `furniture` | vibe `calm`, style `editorial`/`minimalism`, macro `split-studio`/`photographic`/`portfolio-grid` | architecture studio interiors projects | 40 | 40 | dobre | — |
| prawnik i kancelaria | brak (bez filtra) | vibe `serious`/`calm`, style `editorial`/`swiss`, mode `light`, macro `long-document`/`split-studio` | law firm legal advisory | 0 | 1 (Everlaw: oprogramowanie prawnicze) | słabe | `prawo` |
| księgowość, biuro rachunkowe | `fintech` (zastępczo) | vibe `calm`/`serious`, style `minimalism` | accounting bookkeeping tax invoicing | 42 | 3 (Puzzle, Qonto, Oyster: produkty; 0 biur) | słabe | `ksiegowosc` |
| szkoła, kursy, szkolenia | `education` | vibe `calm`/`warm`, macro `specimen`/`split-studio` | online courses school learning | 29 | 19 | średnie | `edukacja` |
| sklep internetowy | `ecommerce` | vibe `calm`/`soft`/`warm`, macro `split-studio`/`portfolio-grid` | online store product shop | 87 | 87 | dobre | — |
| SaaS, aplikacja | `saas`, `ai`, `developer-tools` | vibe `technical`/`calm`, macro `feature-stack`/`bento-grid`; podstrony pageType `pricing`/`features` | saas product platform | 335 | 335 | dobre | — |
| agencja (marketing, kreatywna) | `agency` | vibe `serious`, macro `split-studio`/`specimen` | creative agency studio work | 93 | 93 | dobre | — |
| portfolio (fotograf, projektant, twórca) | `portfolio`, `creator` | macro `specimen`/`portfolio-grid` | designer portfolio selected work | 104 | 104 | dobre | — |
| NGO, fundacja, stowarzyszenie | `non-profit` (i `culture`: muzea, instytucje, 48) | vibe `calm`/`serious`, style `editorial` | foundation charity donate | 13 | 13 | średnie | `ngo` |
| motoryzacja (dealer, warsztat, komis) | `automotive` | vibe `luxe`/`serious`, mode `dark`, macro `marquee-hero`/`photographic` | car models dealership | 10 | 10 marek premium (Porsche, Ferrari, Lexus…); 0 dealerów i warsztatów | średnie dla marki, słabe dla dealera i warsztatu | `motoryzacja` |
| eventy i śluby | brak (zastępczo `culture`) | vibe `soft`/`warm`, macro `photographic` | wedding venue events (festiwal: festival conference) | 0 | 3 (OFFF, React Summit, Config; 0 ślubów) | słabe | `eventy` |

Więcej branż na żądanie: `get_filters` pokazuje wszystkie wartości filtrów (24 branże, 19 macrostructure, 10 vibe).
Brak wiersza → najbliższa branża z tabeli albo zapytanie bez `industry` i ocena po wynikach (< 3 trafne = słabe).

## Sekcja „Inspiracje” w `out/PLAN.md`

```markdown
## Inspiracje
Branża: nieruchomości (Inspo: słabe pokrycie → własna baza: inspiracje/strony/nieruchomosci/, 5 stron, wskazał właściciel)

| Strona | Skąd | Co bierzemy | Czego nie bierzemy |
|---|---|---|---|
| example.pl | własna baza | wyszukiwarka ofert w hero, karty ofert 3 w rzędzie | ciemnego motywu, stockowych zdjęć |
| humahome-com | Inspo | serif nagłówków na zdjęciu, dużo światła | terakotowej palety (marka klienta ma granat) |

Decyzje: macrostructure `photographic`; hero: zdjęcie + H1 + wyszukiwarka, całość w 1280×800; sekcje co 96–120 px;
nagłówki szeryfowe z brand kitu; paleta z brand kitu, akcent ciepły jak w referencjach; ruch: tylko fade przy przewijaniu.
```

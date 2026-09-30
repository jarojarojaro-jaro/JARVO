---
source: "Metoda: superdesigndev/treg skills/lead-signals (Apache-2.0, commit 8b2826d); źródła, typy i przepisy własne (polskie rejestry, sprawdzone 2026-09-30)"
reviewed: "2026-09-30"
---
# Źródła sygnałów: co brać, co odrzucać

| Typ (`typ`) | Skąd | Bierz | Odrzuć |
|---|---|---|---|
| `krs-nowa-firma` | `krs.py biuletyn <data> --nowe` | spółka w PKD i regionie z ICP, zarejestrowana w oknie świeżości | fundacje i stowarzyszenia (chyba że to ICP), spółki celowe holdingów |
| `krs-wpis` | `krs.py biuletyn <data>` | wpis w firmie z ICP (zmiana zarządu, adresu, kapitału: sprawdź odpis) | sam wpis bez treści zmiany jako jedyny sygnał |
| `przetarg-ogloszenie` | `przetargi.py bzp`, `ted` | zamawiający kupuje to, co sprzedajesz (CPV), termin ofert jeszcze otwarty | termin minął; zamówienie za duże albo z warunkami, których użytkownik nie spełni |
| `przetarg-wygrany` | `przetargi.py bzp --wyniki` | zwycięzca musi teraz wykonać zamówienie: podwykonawcy, sprzęt, ludzie, marketing | zwycięzca = konkurent użytkownika; wielkie grupy z własnymi działami |
| `przetarg-ted` | `przetargi.py ted` | jak ogłoszenie, powyżej progów UE | ogłoszenia sprostowań bez nowej treści |
| `rekrutacja` | wyszukiwarka | rola, która oznacza potrzebę produktu (np. „specjalista ds. marketingu” dla agencji), ostatnie 30 dni, kilka ról | agencje pośrednictwa, ogłoszenia „zawsze otwarte” |
| `strona-technologia` | `strona.py kontakt` | technologia konkurenta albo brak narzędzia, które sprzedajesz (np. sklep bez analityki) | znaczniki, które ma każda strona (reCAPTCHA, cookies) |
| `strona-kariera` | `strona.py kontakt` | strona kariery z ofertami w roli z ICP | pusta zakładka kariery |
| `strona-zmiana` | `strona.py zmiana --baza` | nowa strona, nowa oferta, nowy cennik (sprawdź, co się zmieniło) | zmiana samej daty, bannera cookies |
| `news` | wyszukiwarka | otwarcie oddziału, nowy produkt, przejęcie, nowy prezes, ostatnie 30 dni | przedruki tej samej informacji |
| `finansowanie` | wyszukiwarka | runda, dotacja, kredyt inwestycyjny w ostatnich 90 dniach, skala pasuje do ceny | dług przedstawiony jako wzrost |
| `reklamy` | Biblioteka reklam Meta (strona publiczna) | firma aktywnie reklamuje ofertę, na której możesz się oprzeć | – |

## Przepisy wyszukiwania (SearXNG, filtr czasu)
- rekrutacja: `"<rola>" praca <miasto>`, `site:pracuj.pl "<rola>"`, `site:justjoin.it <rola>`, `"<rola>" "<branża>" oferta pracy`
- ekspansja: `"otwieramy" "<miasto>" <branża>`, `"nowy oddział" <branża> 2026`, `"<firma>" inwestycja`
- finansowanie: `"pozyskała" "rundę" <branża>`, `"dofinansowanie" "<branża>" 2026`, `site:mambiznes.pl runda`
- zmiana narzędzia: `"przechodzimy z <konkurent>"`, `"migracja z <konkurent>"`
- targi: `"lista wystawców" <targi> 2026` (wystawcy to firmy, które właśnie inwestują w sprzedaż)

## Kody na start
PKD: `62` programowanie i IT, `63` usługi informacyjne, `70.2` doradztwo, `73.1` reklama, `47.91` handel w internecie,
`56` gastronomia, `68` nieruchomości, `41`–`43` budownictwo, `86` zdrowie, `96.02` fryzjerstwo i kosmetyka.
CPV: `72` usługi IT, `48` oprogramowanie, `79341` reklama, `79342` marketing, `80` szkolenia, `45` roboty budowlane,
`30` sprzęt komputerowy, `90` sprzątanie i odpady.

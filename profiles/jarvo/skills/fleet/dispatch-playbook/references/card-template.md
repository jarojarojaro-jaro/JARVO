# Szablon karty (treść `body` w `kanban_create`)

```
CEL:
<Co ma powstać. 1–2 zdania. Rzeczownik + miara, np. „Landing produktu Nova (1 strona, PL) gotowy do podglądu”.>

KONTEKST:
- Dla kogo i po co: <odbiorca, cel biznesowy, intencja właściciela dosłownie „<cytat>”, po czym pozna, że dobre>
- Decyzje już podjęte: <nazwa, język, paleta, domena, ton…>
- Ograniczenia: <prawne, techniczne, czasowe>
- Czego NIE robić: <np. nie publikować, nie wymyślać cen, nie ruszać produkcji>
- Znane braki wykonawcy: <1–3 z `liczby.py --json` → `braki[<agent>]`, skrócone do sedna; brak = „brak”>

WEJŚCIA:
- <plik / URL; wyniki kart-rodziców ścieżką do ich out/ (np. ../karta-1/out/RAPORT.md), nie przepisaną treścią>
- Marka: @@KNOWLEDGE_DIR@@/brands/<marka>/ (BRAND.md, DESIGN.md, product-marketing.md)
- Fakty o firmie: <źródło: USER.md, strona, brand kit>; brakujące → treść przykładowa jawnie oznaczona jako przykład

DoD:
- <mierzalny warunek; np. „Lighthouse mobile ≥ 90 w 4 kategoriach”>
- <mierzalny warunek; np. „każde twierdzenie liczbowe ma źródło z datą”>
- <format; np. „grafiki 1080×1350 i 1080×1920 PNG, < 1 MB”>
- <wartość; np. „zrzut 375 i 1440 obejrzany: wygląda jak strona tej firmy, nie szablon; 0 treści zastępczej”>

WYJŚCIA:
- out/<nazwa pliku> (<format>): <opis>
- out/RAPORT.md: podsumowanie + samokontrola DoD

GRANICE:
- Autonomia: A1 (szkice/podglądy; bez publikacji, wdrożeń, wysyłek, wydatków)
- Budżet: <np. 60 min pracy>
- Nie ruszać: <np. istniejąca produkcja, domena, konta>

STOP: KONTROLA <nazwa>: NIE — <błąd> w notatce postępu; ta sama kontrola 3× z rzędu → kanban_block z dowodem, bez 4. próby
```

KONTEKST ma najwyżej 5 punktów. Historia rozmowy i warianty, które rozważałeś, idą do `MISSION.md`, nie do karty:
wykonawca czyta kartę w każdej turze. Znane braki bierzesz z `liczby.py --json` (`braki[<agent>]`), 1–3 najczęstsze.

## Dobre i złe DoD

| Złe (nieoceniane) | Dobre (mierzalne) |
|---|---|
| „ładny landing” | „zgodny z BRAND.md (kolory, fonty), Lighthouse mobile ≥ 90, zrzuty 375/768/1440 px bez przewijania w poziomie” |
| „dobry research” | „≥ 8 niezależnych źródeł, każde kluczowe twierdzenie potwierdzone ≥ 2 źródłami, sprzeczności opisane, daty źródeł” |
| „fajne posty” | „5 postów LinkedIn ≤ 1300 znaków, hook w 1. linii, CTA, 0 zwrotów z listy zakazanych w BRAND.md” |
| „dokładnie 5 problemów” | „do 5 problemów, każdy potwierdzony i inny; mniej, jeśli tyle jest naprawdę” |
| „10 firm” | „do 10 firm z sygnałem ≤ 30 dni i opublikowanym kontaktem; podaj, ile odpadło” |
| „szkielet z treścią zastępczą” | „pełna strona z treścią z USER.md i strony firmy; czego brak, to treść przykładowa oznaczona w RAPORT.md” |

Nigdy nie pisz w karcie „treść zastępcza”, „[TU WPISZ…]” ani „szkielet” jako wyniku: strażnik zablokuje oddanie
z takimi znacznikami w `out/`, a sędzia odrzuci wynik, którego właściciel nie pokaże klientowi.

# Szablon karty (treść `body` w `kanban_create`)

```
CEL:
<Co ma powstać. 1–2 zdania. Rzeczownik + miara, np. „Landing produktu Nova (1 strona, PL) gotowy do podglądu”.>

KONTEKST:
- Dla kogo: <odbiorca / grupa docelowa>
- Po co: <cel biznesowy / decyzja, którą to wspiera>
- Intencja użytkownika (dosłownie): „<cytat>”
- Decyzje już podjęte: <nazwa, język, paleta, domena, ton…>
- Marka: @@KNOWLEDGE_DIR@@/brands/<marka>/ (BRAND.md, DESIGN.md, product-marketing.md)
- Po czym właściciel pozna, że dobre: <jedno zdanie z jego perspektywy, np. „mógłbym wysłać link klientce”>
- Fakty o firmie: <ze źródłem: USER.md, strona, brand kit>; brakujące → treść przykładowa jawnie oznaczona jako przykład
- Ograniczenia: <czego unikać, prawne, techniczne>

WEJŚCIA:
- <plik / URL / katalog out/ karty-rodzica>

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
```

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

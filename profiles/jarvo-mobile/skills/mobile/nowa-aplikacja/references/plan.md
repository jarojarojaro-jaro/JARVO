# Szablon planu aplikacji (`out/PLAN.md`)

source: App Store Review Guidelines (4.2, 5.1.1), Google Play: zasady dotyczące funkcjonalności, praktyka floty
reviewed: 2026-10-01

```markdown
# Plan aplikacji: <nazwa>

## Cel
Jedno zdanie: co klient załatwi w aplikacji i dlaczego wróci (np. „rezerwuje wizytę w 20 sekund i dostaje przypomnienie”).

## Użytkownik
Kto (klient / pracownik), jak często (codziennie, co tydzień, raz w miesiącu), na jakim telefonie (iPhone, Android, oba).

## Funkcje ponad stronę (Apple 4.2)
Co aplikacja robi lepiej niż strona: powiadomienia, offline, aparat lub skaner, karta lojalnościowa, Face ID, widżet.
Bez tej sekcji aplikacja ryzykuje odrzucenie jako „przepakowana strona”.

## Mapa ekranów
| Zakładka / ekran | Po co | Dane | Stany (ładowanie, pusto, błąd, offline) | Wymaga konta? |
|---|---|---|---|---|
| Start | … | … | … | nie |
| Więcej (szablon) | kontakt, prywatność, usuwanie konta | dane firmy | — | nie |

Najwyżej 5 zakładek. Pierwszy ekran pokazuje wartość bez logowania.

## Dane i backend
Gdzie dane (Supabase, PocketBase, API firmy, brak), co jest w telefonie, co w chmurze, kto jest administratorem danych.

## Konta i logowanie
Czy potrzebne (po co), metody (e-mail, Google + Apple, telefon), usuwanie konta (ekran w szablonie + strona Weba).

## Płatności
Co jest sprzedawane (towar fizyczny, usługa, treść cyfrowa) i czym (Stripe/P24/BLIK poza Apple albo zakupy w aplikacji).

## Powiadomienia
Kiedy i po co (przypomnienie o wizycie 24 h przed), ile tygodniowo najwyżej; prośba o zgodę dopiero po pierwszej rezerwacji.

## Miary sukcesu
Np. 30% klientów salonu z aplikacją po 3 miesiącach, ocena ≥ 4,5, mniej telefonów z pytaniem o termin.

## Poza zakresem (wersja 1)
Czego świadomie nie robimy teraz.
```

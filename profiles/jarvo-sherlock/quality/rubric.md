# Rubryka: jarvo-sherlock

## Blokujące (poprawki obowiązkowe)
- Brak jasnej odpowiedzi na pytanie z CEL w pierwszym akapicie raportu.
- Kluczowe twierdzenie bez źródła albo ze źródłem, które **nie mówi** tego, co mu przypisano (sędzia sprawdza ≥ 3 losowo).
- Zmyślony lub niedziałający link w kluczowym źródle.
- `sources.py verify out/RAPORT.md` kończy się błędem (numer spoza rejestru, blok „Źródła” niezgodny z rejestrem,
  cytowane źródło bez przeczytanego tekstu albo bez oceny wiarygodności).
- Cytat-dowód, którego nie ma w zapisanym tekście strony, albo kluczowe twierdzenie bez numeru i bez `[niezweryfikowane]`.
- Kluczowe twierdzenie oparte na jednym źródle bez oznaczenia niskiej pewności.
- Przemilczana sprzeczność, którą sędzia znalazł w źródłach.
- Brak dat przy danych zmiennych w czasie (ceny, statystyki, stan prawny).
- OSINT wobec osoby prywatnej.
- Punkt DoD niespełniony bez uzasadnienia.

## Ważne (poprawki, jeśli wpływają na decyzję)
- Brak źródeł pierwotnych, gdy są łatwo dostępne.
- Źródła tylko tier C/D przy temacie, gdzie istnieją źródła A/B.
- Liczby nieprzeliczone / nieporównywalne okresy.

## Uwagi (nie blokują)
- Styl, długość, kolejność sekcji.

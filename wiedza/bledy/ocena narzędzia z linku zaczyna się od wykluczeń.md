---
typ: blad
tagi: [linki, narzedzia, koszt, skrzynka-linkow]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "link właściciela 16.11 20:39 (przeglądarka „browse” od opencode), ok. 400 wywołań w 35 min; skrzynka-linkow 1.9.0"
agent: jarvo
sygnatury: ["/requires? (a |the )?(chrome|browser) extension/", "/wymaga (rozszerzenia|wtyczki) (do )?(chrome|przeglądarki)/"]
wystapienia: 1
---
# Ocena narzędzia z linku zaczyna się od wykluczeń

**Link do narzędzia oceniasz od warunków, które je u nas wykluczają; przy wykluczeniu kończysz jednym zdaniem, bez instalowania i pomiarów.**

**Objaw:** 16.11 na pytanie „jak się ma przeglądarka od opencode do naszej” Jarvo pracował ok. 35 minut (ok. 400 wywołań): instalował, pobierał przeglądarkę 2,5 GB, budował licznik tokenów. Wynik: nie bierzemy, bo narzędzie wymaga prawdziwego Chrome z rozszerzeniem, co było w README od pierwszych wywołań.

**Przyczyna:** pełna seria pomiarów zamiast oceny; warunek wykluczający przeczytany, ale nie użyty jako stop.

**Jak poprawnie:** najpierw z README i opisu sprawdzasz wykluczenia: okno albo rozszerzenie w prawdziwej przeglądarce, RAM, płatne, brak Linuksa, licencja. Jest wykluczenie → odpowiedź właścicielowi z powodem i liczbą, szkic w skarbcu, koniec. Brak wykluczeń → próba od jednego przypadku i jednej miary; dalej tylko przy obiecującym wyniku. Bez dużych pobrań i własnych narzędzi pomiarowych dla samego porównania.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/limit zapytań api, bez pętli ponowień|Limit zapytań API]]
- [[bledy/zapasowa przeglądarka pobiera się sama, bez camoufox fetch|Zapasowa przeglądarka pobiera się sama]]
- [[fleet/lekcje|Księga lekcji floty]]

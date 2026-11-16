---
typ: blad
tagi: [github, api, limity]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "jarvo update 9.11 22:45 i 16.11 22:38 (limit 60 zapytań na godzinę bez klucza); CEIDG 429 w skrypcie Łowcy"
sygnatury: [limit zapytań, API rate limit exceeded, secondary rate limit, Too Many Requests]
wystapienia: 2
---
# Limit zapytań API, bez pętli ponowień

**Odpowiedź „limit zapytań” (HTTP 429 albo 403 z rate limit) zatrzymuje serię zapytań: nie ponawiasz w pętli, tylko zmieniasz drogę albo czekasz raz tyle, ile mówi serwis.**

**Objaw:** 9.11 podagenci czytający GitHuba bez klucza wyczerpali limit 60 zapytań na godzinę i `jarvo update` stanął; 16.11 pętla ponawiająca polecenie co 30 s znowu zjadła limit i wdrożenie czekało godzinę.

**Przyczyna:** każde ponowienie to kolejne zapytanie do tego samego limitu; GitHub bez klucza daje 60 zapytań na godzinę z jednego adresu.

**Jak poprawnie:** GitHub czytasz przez `gh api` (z kluczem, 5000 na godzinę) albo przez `git clone --depth 1`, nie anonimowym `curl` na api.github.com. Po odmowie z limitem: jedno odczekanie zgodne z nagłówkiem albo komunikatem (`Retry-After`, czas resetu), węższe zapytanie i mniej stron; nigdy pętla ponowień. Gdy praca czeka na zwolnienie limitu dłużej niż kilka minut, mówisz to w raporcie albo blokadzie karty z godziną resetu.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/limit iteracji karty zjadły skrypty łatające raport|Limit iteracji karty]]
- [[bledy/ocena narzędzia z linku zaczyna się od wykluczeń|Ocena narzędzia od wykluczeń]]
- [[fleet/lekcje|Księga lekcji floty]]

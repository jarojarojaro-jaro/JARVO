---
typ: blad
tagi: [jarvo, wlasciciel, brief, decyzje]
utworzono: 2026-11-23
zmieniono: 2026-11-23
status: aktualna
zrodlo: "brief B-2026-11-23/3 (z B-2026-11-18/6, raport misji Z-261118-monid); właściciel 23.11 do operatora: „dostałem pytanie na temat czegoś, co nas nawet nie dotyczy”"
agent: jarvo
sygnatury: ["Custom Search JSON API"]
wystapienia: 1
---
# Pytanie do właściciela tylko o to, co nas dotyczy

**Zanim sprawa trafi do briefu albo pytania do właściciela, sprawdzasz w konfigu, kodzie albo skarbcu, że flota tego używa; wniosek z raportu agenta to nie dowód.**

**Objaw:** od 18.11 do 23.11 brief pytał właściciela, czy szukać zamiennika, bo Google zamyka Custom Search JSON API 1.01.2027.

**Przyczyna:** Łowca w raporcie Monid napisał, że „nasze darmowe oparcie na SERP ma datę ważności”, a Jarvo przepisał to jako decyzję bez sprawdzenia. Flota szuka przez własny SearXNG (`search_backend: searxng` w config.yaml), który bierze wyniki ze zwykłych stron wyszukiwarek, bez klucza Google; klucza ani wywołania Custom Search nie ma nigdzie.

**Jak poprawnie:** dla każdej nowej pozycji jedno sprawdzenie (`search_files` w konfigu i skryptach albo `wiedza_szukaj`), czy to nasze narzędzie albo nasz koszt; nie dotyczy nas → nie pytasz, a raport agenta dostaje komentarz z poprawką.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/nie proś właściciela o to, co zrobisz sam|Nie proś właściciela o to, co zrobisz sam]]
- [[fleet/lekcje|Księga lekcji floty]]

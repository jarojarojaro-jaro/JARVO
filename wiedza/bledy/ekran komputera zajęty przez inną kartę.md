---
typ: blad
tagi: [komputer, kanban, karty, ekran]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "misja M-261116-pilot-ankiety, karty t_87d11e3a i t_8a2f5f5e 16.11 22:23–22:57; komputer.log, dziennik wejścia"
agent: jarvo
narzedzia: [komputer, computer_use]
sygnatury: ["/\\bzajete\\b/", ekran_zmieniony]
wystapienia: 1
---
# Ekran Komputera zajęty przez inną kartę

**Komputer ma jeden ekran: w danej chwili steruje nim jedna karta, więc karty z Komputerem idą po kolei, z zależnością, nigdy razem.**

**Objaw:** 16.11 22:23 Jarvo założył 3 karty pilota ankiet; dwie ruszyły w tej samej sekundzie i obie sterowały przeglądarką Komputera (rejestracja Google trafiła na stronę GoTranscript, nagranie do wyrzucenia). Po wznowieniu przez patrol znowu razem.

**Przyczyna:** w misji było „karty po jednej”, ale karty nie miały zależności, więc dyspozytor puścił je naraz; zasada w tekście nie działa bez zależności na tablicy.

**Jak poprawnie:** karty, które używają Komputera albo tego samego telefonu, zakładasz jako łańcuch (każda następna z rodzicem poprzedniej). Odmowa `zajete` z `held_by` (ekran ma inna karta): czekasz `free_in_s` i raz ponawiasz, dalej zajęte → `kanban_block` z numerem karty, która ma ekran; nie walczysz o ekran. `zajete` bez innej karty to Twoje poprzednie działanie: czekasz na jego wynik. Odmowa `ekran_zmieniony`: najpierw `patrz` albo `idz`, potem dalej od aktualnego stanu strony.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/zapasowa przeglądarka pobiera się sama, bez camoufox fetch|Zapasowa przeglądarka pobiera się sama]]
- [[bledy/decyzja właściciela tylko z jego cytatem|Decyzja właściciela tylko z cytatem]]
- [[fleet/lekcje|Księga lekcji floty]]

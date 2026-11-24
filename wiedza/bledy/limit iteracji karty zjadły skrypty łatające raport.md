---
typ: blad
tagi: [karty, sherlock, iteracje, raport]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "karta t_3b13572d 7.11 16:23–16:58 (Iteration budget exhausted 250/250)"
agent: jarvo-sherlock
karta: t_3b13572d
sygnatury: [Iteration budget exhausted]
wystapienia: 1
---
# Limit iteracji karty zjadły skrypty łatające raport

**Gotowy wynik oddajesz od razu; poprawki raportu robisz edycją pliku, a nie seriami jednorazowych skryptów, które zjadają limit iteracji przebiegu.**

**Objaw:** 7.11 karta konkurencji Sherlocka przerwana po 35 minutach komunikatem „Iteration budget exhausted (250/250)”; pliki wyniku były gotowe wcześniej, a iteracje zjadło ok. 17 jednorazowych skryptów `fix_*` i `napraw_*` łatających raport.

**Przyczyna:** każda poprawka jako nowy skrypt i nowe uruchomienie kosztuje kilka iteracji; przebieg kończy się na limicie, zanim praca zostanie oddana.

**Jak poprawnie:** gdy pliki z `WYJŚCIA` i punkty DoD są spełnione, oddajesz kartę (`kanban_request_review`) zamiast dalej szlifować. Poprawkę tekstu robisz jedną edycją pliku (`patch`), kilka poprawek w jednym wywołaniu. Po komunikacie o wyczerpanym limicie w kolejnym przebiegu najpierw sprawdzasz, co już jest w `out/`, i oddajesz to, bez powtarzania pracy.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/port zajęty przez serwer z poprzedniej karty|Port zajęty przez stary serwer]]
- [[bledy/limit zapytań api, bez pętli ponowień|Limit zapytań API]]
- [[bledy/praca ogólna do podagentów, nie do specjalistów|Praca ogólna do podagentów]]
- [[fleet/lekcje|Księga lekcji floty]]

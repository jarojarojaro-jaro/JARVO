---
typ: blad
tagi: [komputer, kanban, karty, ekran]
utworzono: 2026-11-17
zmieniono: 2026-11-27
status: aktualna
zrodlo: "misja M-261116-pilot-ankiety, karty t_87d11e3a i t_8a2f5f5e 16.11 22:23–22:57; rozmowy panelu w_001a21b31b2d12bff7794 i w_001a21b41b7cdae1c91a6 27.11 ok. 05:30; komputer.log, dziennik wejścia"
agent: jarvo
narzedzia: [komputer, computer_use]
sygnatury: ["/\\bzajete\\b/", ekran_zmieniony, cudze_okno, ekran ma teraz inna sesja Jarva, ekranem sterowała inna sesja Jarva, należy do innego zadania agenta]
wystapienia: 2
---
# Ekran Komputera zajęty przez inną kartę

**Natywnie każde zadanie (rozmowa albo karta) ma własne okno przeglądarki Komputera i działa tylko w nim; w kontenerze ekran jest jeden i steruje nim jedna sesja naraz, a karty z tym samym kontem na stronie albo z tym samym telefonem idą łańcuchem.**

**Objaw:** dwa zadania naraz sterowały jedną kartą przeglądarki Komputera: 16.11 dwie karty pilota ankiet (rejestracja Google trafiła na stronę GoTranscript), 27.11 rozmowy panelu C1 i W1 (`ctrl+z` w C1 dał paragon ze strony OLX z W1).

**Przyczyna:** oba zadania miały ten sam klucz ekranu (karty bez zależności, rozmowy w jednym procesie bramy bez karty), więc działały na jednej aktywnej karcie.

**Jak poprawnie:** pracujesz bez `window_id`: Komputer sam daje Twojemu zadaniu jego okno, a `list_windows` pokazuje tylko Twoje okna. Odmowa `cudze_okno`: wracasz do swojego okna od `patrz`. Odmowa `zajete` (kontener): czekasz `free_in_s` i raz ponawiasz, dalej zajęte → `kanban_block` z numerem karty, która ma ekran. `zajete` bez innej karty to Twoje poprzednie działanie: czekasz na jego wynik. Odmowa `ekran_zmieniony`: najpierw `patrz` albo `idz`. Profil przeglądarki jest wspólny, więc karty logujące się na tę samą stronę innymi kontami i karty z tym samym telefonem zakładasz jako łańcuch.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/zapasowa przeglądarka pobiera się sama, bez camoufox fetch|Zapasowa przeglądarka pobiera się sama]]
- [[bledy/decyzja właściciela tylko z jego cytatem|Decyzja właściciela tylko z cytatem]]
- [[fleet/lekcje|Księga lekcji floty]]

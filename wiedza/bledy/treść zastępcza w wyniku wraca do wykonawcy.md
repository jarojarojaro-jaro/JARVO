---
typ: blad
tagi: [karty, jakosc, intake, web]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "karta strony-wizytówki 26.10 (25 dziur „[TU WPISZ]”, sędzia zaakceptował); poprawki JARVO 879ce50 (5.11)"
narzedzia: [terminal, search_files]
sygnatury: [TU WPISZ, TU WSTAW, lorem ipsum, JARVO-TODO]
wystapienia: 1
---
# Treść zastępcza w wyniku wraca do wykonawcy

**Wynik z „[TU WPISZ…]”, lorem ipsum albo JARVO-TODO to praca niegotowa: wtyczka nie przepuści takiego oddania, więc dziury uzupełniasz przed oddaniem.**

**Objaw:** 26.10 karta strony przeszła z 25 dziurami „[TU WPISZ]”, bo zlecenie „działaj” nie miało faktów, a wykonawca zostawił miejsca do wypełnienia.

**Przyczyna:** brak faktów w karcie zamieniony na dziury zamiast na pytanie albo treść przykładową opisaną w raporcie.

**Jak poprawnie:** przed oddaniem przeszukujesz `out/` (`search_files` albo `grep -rn`) pod „TU WPISZ”, „lorem ipsum”, „JARVO-TODO”. Brak, który zmienia wynik → `kanban_block(kind="needs_input")` z jednym pytaniem i proponowaną odpowiedzią; drobny brak → wiarygodna treść przykładowa opisana w `RAPORT.md` jako do potwierdzenia. Jarvo przy zleceniu bez faktów zadaje jedno pytanie albo daje pełną wersję z treścią przykładową.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/nie proś właściciela o to, co zrobisz sam|Nie proś właściciela o to, co zrobisz sam]]
- [[bledy/port zajęty przez serwer z poprzedniej karty|Port zajęty przez stary serwer]]
- [[fleet/lekcje|Księga lekcji floty]]

---
typ: blad
tagi: [komputer, google, logowanie, telefon]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "rejestracja testyjarvo@gmail.com 16.11 (misja M-261116-pilot-ankiety); sprawdzenie Jarva 17.11"
agent: jarvo
sygnatury: [Ta przeglądarka lub aplikacja może nie być bezpieczna, This browser or app may not be secure]
wystapienia: 1
---
# Google nie loguje w przeglądarce Komputera, konta Google na telefonie

**Google nie pozwala założyć konta ani zalogować się w przeglądarce Komputera; konta Google i „Zaloguj przez Google” robisz tylko na telefonie floty.**

**Objaw:** 16.11 rejestracja konta testyjarvo@gmail.com w Komputerze stanęła zaraz po haśle na komunikacie „Ta przeglądarka lub aplikacja może nie być bezpieczna”. Jarvo sprawdził 17.11: to samo przy logowaniu.

**Przyczyna:** Google odrzuca logowanie w przeglądarce sterowanej programem (Komputer to Chrome z kanałem narzędzi deweloperskich); ponowienie, inny adres strony ani czekanie tego nie zmienią.

**Jak poprawnie:** zakładanie konta Google, logowanie na nie i każde „Zaloguj przez Google” (OAuth na innych stronach) robisz od razu na telefonie floty: MCP `phone`, Chrome albo aplikacja, konta, które telefon już ma. W Komputerze nie próbujesz drugi raz. Gdy telefon też odmówi (kod SMS, potwierdzenie na innym urządzeniu), `kanban_block` z `kind: needs_input` i jednym zdaniem dla właściciela.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/nagrywanie tylko udanych kroków krótkimi odcinkami|Nagrywanie tylko udanych kroków]]
- [[bledy/cloudflare nie przepuszcza komputera, krok na telefonie floty|Cloudflare nie przepuszcza Komputera]]
- [[bledy/complete account setup w sklepie play to nie płatność, przewiń do skip|Complete account setup to nie płatność]]
- [[fleet/lekcje|Księga lekcji floty]]

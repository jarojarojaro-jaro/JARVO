---
typ: blad
tagi: [komputer, cloudflare, captcha, telefon]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "misja M-261116-pilot-ankiety (karty t_87d11e3a, t_8a2f5f5e), komputer.log 16.11 22:24–23:37; analiza operatora 16.11 23:53"
agent: jarvo
karta: t_8a2f5f5e
sygnatury: [weryfikacja_czlowieka, Weryfikacja negatywna, "We couldn't verify you're human", "/verification (failed|unsuccessful|expired)/", "Sorry, you have been blocked", "/(verify|confirm) (that )?you('| a)re (a )?human/", challenges.cloudflare.com]
wystapienia: 1
---
# Cloudflare nie przepuszcza Komputera, krok na telefonie floty

**Okienko „jestem człowiekiem” (Cloudflare Turnstile, reCAPTCHA, hCaptcha) odrzuca Komputer Jarva; po jednej nieudanej próbie ten sam krok robisz na telefonie floty, a gdy i tam nie przejdzie, jedno zdanie do właściciela.**

**Objaw:** 16.11 przy rejestracji kont (DataAnnotation, Outlier) Turnstile odrzucił Komputer przy pierwszym kliknięciu o 22:24; Jarvo klikał to samo pole do 23:37 i nic nie powiedział właścicielowi.

**Przyczyna:** Komputer to Chrome sterowany programem (`--remote-debugging-pipe`), a Turnstile wykrywa właśnie takie przeglądarki. Telefon przeszedł, bo to prawdziwy Chrome na prawdziwym urządzeniu.

**Jak poprawnie:** w Komputerze najwyżej jedna próba okienka na stronę. Po nieudanej (albo odmowie `weryfikacja_czlowieka`) od razu ten sam krok na telefonie floty: MCP `phone`, Chrome, to samo konto. Telefon też nie przejdzie → `kanban_block` z `kind: needs_input` i jednym zdaniem dla właściciela (strona, co zostało do kliknięcia). Nigdy pętla prób, inna przeglądarka, zmiana user-agenta ani obchodzenie zabezpieczenia.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/google nie loguje w przeglądarce komputera, konta google na telefonie|Google tylko na telefonie]]
- [[bledy/nie proś właściciela o to, co zrobisz sam|Nie proś właściciela o to, co zrobisz sam]]
- [[fleet/lekcje|Księga lekcji floty]]

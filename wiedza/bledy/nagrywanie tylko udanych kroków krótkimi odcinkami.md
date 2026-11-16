---
typ: blad
tagi: [komputer, nagranie, film]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "misja M-261116-pilot-ankiety 16.11 22:32–23:37 (nagranie całego pulpitu); właściciel 16.11 23:52"
agent: jarvo
sygnatury: [x11grab, gdigrab, avfoundation]
wystapienia: 1
---
# Nagrywanie tylko udanych kroków krótkimi odcinkami

**Film z pracy na ekranie to krótkie odcinki kroków, które się udały; przy pierwszej blokadzie nagrywanie się kończy.**

**Objaw:** 16.11 właściciel poprosił „nagraj proces, krótki filmik, każdy krok”; Jarvo nagrywał cały pulpit bez przerwy ok. 20 minut, w tym pętlę nieudanych kliknięć w Turnstile i czas, gdy pracował na telefonie. Właściciel: „nagrywał 20 min jak klika”.

**Przyczyna:** jedno długie nagranie `ffmpeg` z terminala zamiast odcinków po krokach; brak zasady, że porażki i ponowienia nie trafiają do filmu.

**Jak poprawnie:** nagrywasz tylko skryptem nagrywania ze skilla `praca-na-ekranie`, odcinek tuż przed krokiem, który ma się udać, i stop zaraz po jego potwierdzeniu (najwyżej ok. minuty). Krok nieudany oznaczasz jako nieudany i nie wchodzi do filmu. Przy pierwszej blokadzie (odmowa, captcha, prośba o człowieka) kończysz nagrywanie i ponowień nie nagrywasz. Na końcu film z samych udanych odcinków, wysyłasz go właścicielowi, potem sprzątasz nagrania. Nigdy `ffmpeg -f x11grab`, `gdigrab` ani `avfoundation` z terminala.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/zabity pracownik karty wraca jako protocol violation|Zabity pracownik karty wraca]]
- [[bledy/google nie loguje w przeglądarce komputera, konta google na telefonie|Google tylko na telefonie]]
- [[fleet/lekcje|Księga lekcji floty]]

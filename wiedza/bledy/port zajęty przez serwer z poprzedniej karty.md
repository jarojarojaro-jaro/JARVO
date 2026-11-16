---
typ: blad
tagi: [karty, procesy, serwer, wydajnosc]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "karta t_9e433231 8.11 (http.server 8322 żył 16 h po karcie), przebieg 122 karty t_bdb2d534 9.11 (http.server 8791)"
sygnatury: [Address already in use, EADDRINUSE]
wystapienia: 2
---
# Port zajęty przez serwer z poprzedniej karty

**Serwer albo przeglądarkę puszczoną w tle zatrzymujesz, zanim oddasz kartę; „Address already in use” to zwykle Twój własny proces z wcześniejszego przebiegu.**

**Objaw:** 8.11 karta audytu skończyła się o 17:32, a jej `python3 -m http.server 8322` działał jeszcze 16 h; 9.11 przebieg karty zostawił `http.server 8791`, choć ta sama karta pracowała już w następnym przebiegu. Kolejny start serwera na tym porcie kończy się „Address already in use”.

**Przyczyna:** proces puszczony w tle przeżywa przebieg karty i trzyma port, pamięć i CPU, dopóki go ktoś nie zatrzyma (sprzątanie floty robi to dopiero kilka minut po końcu przebiegu).

**Jak poprawnie:** serwer podglądu i inne długie procesy uruchamiasz narzędziem `process` (albo zapisujesz PID) i zatrzymujesz przed `kanban_request_review` albo `kanban_complete`. Przy „Address already in use” najpierw sprawdzasz, czy port trzyma Twój proces z tej karty (`process` list, `lsof -i :<port>`), i zatrzymujesz tylko jego; inaczej bierzesz inny wolny port. Nie zabijasz cudzych procesów ani pracownika karty.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/treść zastępcza w wyniku wraca do wykonawcy|Treść zastępcza w wyniku]]
- [[bledy/limit iteracji karty zjadły skrypty łatające raport|Limit iteracji karty]]
- [[fleet/lekcje|Księga lekcji floty]]

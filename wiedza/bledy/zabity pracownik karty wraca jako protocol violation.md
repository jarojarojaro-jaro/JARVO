---
typ: blad
tagi: [kanban, karty, procesy]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "karta t_87d11e3a 16.11 22:35 (trzy awarie protocol violation z rzędu); strażnik pracowników kart jarvo-zgody"
agent: jarvo
karta: t_87d11e3a
sygnatury: ["/protocol[ _]violation/", zabicie pracownika karty]
wystapienia: 1
---
# Zabity pracownik karty wraca jako protocol violation

**Karty nie zatrzymujesz poleceniem `kill` na procesie jej pracownika; kartę kończy `kanban_block` albo `kanban_complete`.**

**Objaw:** 16.11 22:35 wtyczka odmówiła rozmowie `kanban_block` na karcie w toku (t_87d11e3a), więc Jarvo zabił jej pracownika poleceniem `kill`. Dyspozytor kanbana uznał to za awarię (protocol violation) i uruchomił kartę od nowa, trzy razy z rzędu.

**Przyczyna:** zabity pracownik to dla dyspozytora przebieg zakończony bez wyniku, więc karta wraca do kolejki; PID pracownika to nie przycisk „stop”.

**Jak poprawnie:** kartę, która czeka albo jest zablokowana, kończysz narzędziem kanbana: `kanban_block(task_id, kind="needs_input", reason="…")` (pracownika zamknie sam dyspozytor), a skończoną `kanban_complete`. Gdy narzędzie kanbana odmawia, zostaw komentarz na karcie i powiedz to właścicielowi jednym zdaniem; nigdy `kill`, `pkill` ani `os.kill` na pracowniku karty albo na Hermesie. Własny proces (nagrywanie, serwer) zatrzymujesz przez `process` albo `kill` jego własnego PID.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/decyzja właściciela tylko z jego cytatem|Decyzja właściciela tylko z cytatem]]
- [[bledy/nagrywanie tylko udanych kroków krótkimi odcinkami|Nagrywanie tylko udanych kroków]]
- [[fleet/lekcje|Księga lekcji floty]]

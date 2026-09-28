---
name: kiedy-oddac-snajperowi
description: "Granice ręki: kiedy zadanie należy do specjalisty."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [routing, boundaries, fleet]
  jarvo:
    agent: jarvo-reka
    autonomy: A0
    reviewed: "2026-09-28"
---

# Kiedy oddać snajperowi

Robisz sam, gdy wystarczy „dobrze i szybko”. Oddajesz (`kanban_block(kind="capability")` w karcie
albo mówisz to w rozmowie), gdy liczy się **jakość specjalisty**:

| Sygnał | Właściwy agent |
|---|---|
| decyzja zależy od prawdziwości faktów, potrzebne źródła i weryfikacja | `jarvo-sherlock` |
| strona ma trafić do ludzi (produkcja), SEO, wydajność, dostępność | `jarvo-web` |
| treść/grafika ma reprezentować markę publicznie | `jarvo-studio` |
| film: montaż, lektor, napisy, klipy, wideo na platformy | `jarvo-wideo` |
| kilka etapów, kilku agentów, decyzje po drodze | Jarvo (misja) |

Szybkie wersje robisz sam: „sprawdź na szybko, czy X istnieje”, „zmniejsz ten obrazek”, „przerób tekst na punkty”.
Jeśli nie wiesz, zrób szybką wersję i zaproponuj pogłębienie u specjalisty w jednym zdaniu.

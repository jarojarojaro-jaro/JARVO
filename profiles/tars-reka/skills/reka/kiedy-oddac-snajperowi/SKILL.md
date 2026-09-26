---
name: kiedy-oddac-snajperowi
description: "Granice ręki: kiedy zadanie należy do specjalisty."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [routing, boundaries, fleet]
  tars:
    agent: tars-reka
    autonomy: A0
    reviewed: 2026-09-26
---

# Kiedy oddać snajperowi

Robisz sam, gdy wystarczy „dobrze i szybko”. Oddajesz (`kanban_block(kind="capability")` w karcie
albo mówisz to w rozmowie), gdy liczy się **jakość specjalisty**:

| Sygnał | Właściwy agent |
|---|---|
| decyzja zależy od prawdziwości faktów, potrzebne źródła i weryfikacja | `tars-sherlock` |
| strona ma trafić do ludzi (produkcja), SEO, wydajność, dostępność | `tars-web` |
| treść/grafika/wideo ma reprezentować markę publicznie | `tars-studio` |
| kilka etapów, kilku agentów, decyzje po drodze | TARS (misja) |

Szybkie wersje robisz sam: „sprawdź na szybko, czy X istnieje”, „zmniejsz ten obrazek”, „przerób tekst na punkty”.
Jeśli nie wiesz, zrób szybką wersję i zaproponuj pogłębienie u specjalisty w jednym zdaniu.

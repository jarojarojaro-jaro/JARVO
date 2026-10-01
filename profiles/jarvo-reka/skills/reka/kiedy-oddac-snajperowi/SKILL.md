---
name: kiedy-oddac-snajperowi
description: "Granice ręki: kiedy zadanie należy do specjalisty."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [routing, boundaries, fleet]
  jarvo:
    agent: jarvo-reka
    autonomy: A0
    reviewed: "2026-10-01"
---

# Kiedy oddać snajperowi

Robisz sam, gdy wystarczy „dobrze i szybko”. Oddajesz (`kanban_block(kind="capability")` w karcie
albo mówisz to w rozmowie), gdy liczy się **jakość specjalisty**. Tabela jest generowana z `fleet.yaml`
(pole `oddaj_gdy` każdego specjalisty), więc każdy nowy agent trafia do niej sam:

<!-- Jarvo:ODDAJ -->

Szybkie wersje robisz sam: „sprawdź na szybko, czy X istnieje”, „zmniejsz ten obrazek”, „przerób tekst na punkty”.
Jeśli nie wiesz, zrób szybką wersję i zaproponuj pogłębienie u specjalisty w jednym zdaniu.

## Jak oddać, żeby specjalista nie zaczynał od zera

- **W karcie:** `kanban_block(kind="capability")` z nazwą agenta z tabeli i jednym zdaniem, czego brakuje
  („potrzebne źródła do liczb w akapicie 2”). Jarvo przepina kartę albo zakłada nową.
- **Przekaż to, co już masz:** cel słowami użytkownika, pliki (ścieżki), co sprawdziłeś i co wyszło, termin.
  Specjalista nie zna Twojej rozmowy, zna tylko kartę.
- **W rozmowie:** jedno zdanie, kto zrobi to lepiej i dlaczego, plus szybka wersja, jeśli ma sens od razu
  („tu jest szkic posta; żeby poszedł publicznie w Twojej marce, oddam go Studiu”).
- **Nie oddawaj** rzeczy, które specjalista zrobiłby tak samo jak Ty: przeformatowanie, streszczenie, konwersja pliku.

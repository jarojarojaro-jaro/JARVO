---
name: przejscie-strony
description: "Ścieżka klienta na stronie: gdzie się psuje, z dowodem"
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, user-journey, ux, checkout, qa]
    related_skills: [praca-na-ekranie, formularze, oddaj-ekran]
  jarvo:
    agent: jarvo-operator
    autonomy: A1
    reviewed: "2026-10-19"
---

# Przejście strony jak klient

Przechodzisz ścieżkę na stronie tak, jak zrobiłby to klient (znajdź produkt, dodaj do koszyka, dojdź do płatności;
zapisz się na wizytę do ostatniego kroku; znajdź kontakt), i mówisz, gdzie się psuje. Kroku, który płaci, loguje,
zamawia albo wysyła, nie robisz: ścieżka kończy się przed nim, a raport to mówi.

## Przed startem
1. Cel ścieżki w jednym zdaniu z karty („czy klient z telefonu znajdzie cennik w 3 kliknięciach”).
2. Strona własna właściciela albo klienta: tak. Cudzy sklep: tylko oglądanie i koszyk, bez kont i zamówień.
3. Kroki w `todo`, każdy ze stanem do sprawdzenia („koszyk pokazuje 1 produkt i sumę”).

## Przejście
- Każdy krok: działanie → `capture_after: true` → zapis w `todo`: co kliknięte, co pokazała strona, ile trwało
  (`wait` ile było trzeba), czy było coś mylącego (dwa przyciski o tej samej nazwie, baner zasłaniający przycisk,
  komunikat po angielsku, pole bez etykiety w drzewie dostępności).
- Baner cookies: wybierasz „Odrzuć” albo „Tylko niezbędne”, gdy jest; „Akceptuj wszystkie” tylko gdy nie ma innej
  opcji, z notatką w raporcie.
- Błąd strony (500, pusta strona, pętla przekierowań): `capture` `som` jako dowód, adres, godzina; jedna próba
  ponownie po `wait` 5 s.
- Elementy bez nazw w drzewie dostępności (ikona bez etykiety, przycisk `div`) zapisz: to też problem dla
  klientów z czytnikiem ekranu.

## Raport
`out/RAPORT.md`: cel, wynik (przeszło / przeszło z problemami / nie przeszło), tabela kroków (krok, działanie,
co widać, problem), zrzut miejsca problemu (`screenshot_path`), 3 najważniejsze poprawki w kolejności wpływu.
Poprawki w kodzie strony zleca Jarvo (`jarvo-web`), Ty ich nie robisz.

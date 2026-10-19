---
name: dane-z-ekranu
description: "Dane z ekranu do pliku: tabele, listy, źródło i godzina"
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, extraction, table, csv, gdpr]
    related_skills: [praca-na-ekranie]
  jarvo:
    agent: jarvo-operator
    autonomy: A1
    reviewed: "2026-10-19"
---

# Dane z ekranu

Przepisujesz dane, które widać na ekranie, do pliku w `out/`. Najpierw sprawdź drogę bez ekranu: strona publiczna
bez logowania → `web_extract` (szybciej, bez klikania); eksport w panelu (przycisk „Eksportuj CSV”) → plik
pobiera się w Komputerze, a nie u Ciebie, więc właściciel go zabiera albo Ty przepisujesz widok.

## Kroki
1. Ustal w `todo`, jakie kolumny są potrzebne (z karty). Tylko te.
2. `capture` `mode: ax`: tabela ma role `table`, `row`, `cell` (albo listę `list item`). Napisy komórek są
   w `label`. Gdy elementów jest więcej niż 100, przeczytaj całe drzewo z `elements_file` (`read_file`).
3. Drzewo puste (canvas, obrazek, PDF w podglądzie) → `capture` `mode: som` i odczyt z obrazu; liczby, które nie
   są pewne (kwota, NIP, numer konta), oznacz `?` i nie zgaduj.
4. Strony i przewijanie: `scroll` (`delivery_mode: foreground`) albo przycisk „Następna”; po każdej stronie nowy `capture`. Zapisuj w trakcie
   (`write_file` z dopisywaniem wierszy), żeby limit 60 działań nie zabrał wyniku.
5. Sprawdź liczbę wierszy z licznikiem na stronie („Wyniki: 134”) i napisz w raporcie, ile przepisane.

## Plik
- `out/<nazwa>.csv` (UTF-8, nagłówek, separator `,`) albo `out/<nazwa>.md` (tabela dla człowieka).
- Pod tabelą albo w `out/RAPORT.md`: adres strony, godzina odczytu, filtr, liczba wierszy, `screenshot_path`
  ostatniego zrzutu.

## Dane osób
Tylko kolumny z zadania. Nie przepisujesz: haseł, numerów dokumentów, PESEL-u, danych zdrowia, numerów kart
i kont (chyba że karta wprost dotyczy faktur firmy). Klucze i tokeny wejście i tak ukrywa
(`[ukryte przez Komputer Jarva]`): nie próbujesz ich odczytać innym sposobem.

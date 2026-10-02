---
name: prosty-polski
description: "Prosty polski do właściciela: krótkie zdania, zwykłe słowa."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [writing, plain-language, owner, report]
    related_skills: [daily-brief, decision-queue, weekly-review]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-10-02"
---

# Prosty polski

Każda wiadomość do właściciela ma być jasna przy pierwszym czytaniu. Wzór to ASD-STE100: uproszczony angielski
z dokumentacji samolotów. Bierzemy go „w 80%”: te same limity i zasady, bez zamkniętego słownika 900 słów.

## Kiedy użyć
- Brief, kolejka decyzji, przegląd tygodnia, raport z misji, odpowiedź w rozmowie, eskalacja.
- Nie dotyczy kart dla agentów (kontrakt zlecenia) ani tekstów dla klientów (skill `copy-pl` u wykonawców).

## Limity
| Element | Limit |
|---|---|
| zdanie z poleceniem albo prośbą | 20 słów |
| zdanie opisowe | 25 słów |
| akapit | 6 zdań, jeden temat |
| czynności w zdaniu | 1 |
| łańcuch rzeczowników („zapewnienia poprawności działania”) | 2 słowa |

## Zasady
1. **Strona czynna:** kto co zrobił. „Web wdrożył stronę”, nie „strona została wdrożona”.
2. **Polecenie w trybie rozkazującym:** „Zatwierdź”, „Sprawdź”, „Odpowiedz”.
3. **Jedno słowo na jedną rzecz.** Raz „misja”, to zawsze „misja”, a nie na zmianę „projekt” i „zadanie”.
4. **Zwykłe słowa zamiast urzędowych:** `references/slownik.md` (zamiennik w drugiej kolumnie).
5. **Złożone kroki jako lista numerowana,** po jednej czynności w punkcie.
6. **Dokładne liczby i nazwy:** „3 posty”, „wersja a1b2c3”, a nie „kilka”, „najnowsza”.

## Ostrzeżenia
Najpierw polecenie, potem ryzyko. Dwa poziomy:
- **⛔ OSTRZEŻENIE:** ryzyko straty: pieniędzy, danych, konta albo publikacji, której nie da się cofnąć.
- **⚠ UWAGA:** ryzyko gorszego wyniku albo straty czasu.

Przykład: „⛔ OSTRZEŻENIE: Nie zatwierdzaj budżetu przed sprawdzeniem grupy docelowej. Zła grupa zużyje budżet w 2 dni.”

## Przed i po
- Przed (23 słowa, 9 potknięć według `prosty.py`): „W związku z powyższym dokonano weryfikacji wdrożenia, które zostało zrealizowane w ramach misji M-12,
  w celu zapewnienia poprawności działania formularza kontaktowego na stronie.”
- Po: „Sprawdziłem wdrożenie z misji M-12. Formularz kontaktowy działa.”

## Sprawdzenie
Limity i słownik liczy skrypt bez modelu: `python3 $HERMES_HOME/scripts/prosty.py --tekst "…"` (albo plik), gdy masz
terminal. Przegląd tygodnia dostaje te same liczby dla wszystkich wiadomości Jarva do właściciela (`fleet_report.py
--mode weekly`, klucz `prosty_polski`): ile wiadomości w normie i co zawodzi najczęściej.

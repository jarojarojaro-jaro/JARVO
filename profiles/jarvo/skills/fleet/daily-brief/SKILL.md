---
name: daily-brief
description: "Poranny brief: co w toku, co gotowe, jakie decyzje."
version: 1.3.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, brief, cron, report]
    related_skills: [decision-queue, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-11-15"
---

# Poranny brief

Rutyna cron (codziennie, rano). Skrypt `fleet_report.py --mode daily` dał Ci dane z ostatnich 24 h, `numer` briefu
(`B-RRRR-MM-DD`) i `otwarte_decyzje` (pozycje z wcześniejszych briefów bez odpowiedzi właściciela, z numerem i liczbą dni).
Pole `agenci_biznesowi` to po jednej linii na agenta biznesowego (lejek, rutyny, telefon, brand kit) i linia
sesji Kernel, a `szkice_do_zgody` ({agent: numery szkiców}) budzi brief nawet w cichy dzień. Pole `kopalnia` to materiał do jednej rzeczy wartej zbudowania (skill `kopalnia-pomyslow`). Jeśli nic się nie dzieje,
nic nie czeka i właściciel nic nie pisał, skrypt nie budzi modelu. Po wysłaniu briefu skrypt `briefy.py` zapisuje go
w skarbcu (`@@KNOWLEDGE_DIR@@/briefy/<numer>.md`, z tabelą decyzji), więc numeracja pozycji musi być czysta: 1., 2., 3.

## Format (maks. ~12 linii)
```
☀️ Brief <numer> · Dzień dobry. Stan floty:
Gotowe od wczoraj: <1 linia na wynik, z efektem, nie z nazwą karty>
W toku: <misje: co, kto, kiedy wynik>
Czeka na Ciebie (<N> decyzji):
1. <decyzja z rekomendacją>
2. <decyzja z wcześniejszego briefu z rekomendacją> (z B-2026-11-12/3)
3. 🛠 Zbudować <co> dla <agent>: <dowód>. Rekomenduję tak.
Agenci biznesowi: <1–2 zdania: szkice do zgody z numerami, czego brakuje do startu>
Dziś w planie: <rutyny / terminy z misji, jeśli są>
Odpowiedz np. „1 ok, 2 nie”.
```

## Zasady
- Najpierw `otwarte_decyzje` (najstarsze na górze), potem nowe z kolejki (skill `decision-queue`), na końcu najwyżej
  jedna pozycja „🛠” z kopalni pomysłów, razem najwyżej 5. Bez decyzji i bez pomysłu sekcji „Czeka na Ciebie” nie ma.
  Pozycja z wcześniejszego briefu dostaje na końcu jego numer w nawiasie, dokładnie „(z B-RRRR-MM-DD/n)”: skrypt
  zamyka wtedy starą pozycję, a odpowiedź trafi do nowej. Pozycja otwarta ≥ 3 dni: zapytaj, czy jest jeszcze aktualna.
- **Agenci biznesowi** (`agenci_biznesowi`, `szkice_do_zgody`): jedno-dwa zdania. Najpierw szkice czekające na zgodę
  z numerami lejka („Sklep: 3 szkice do zgody, L-0002, L-0004, L-0007”); każdy szkic to pozycja w „Czeka na Ciebie”.
  Potem czego brakuje do startu: telefon („brak przydziału”), brand kit, wstrzymana rutyna, lejek nie założony, z jednym
  krokiem dla właściciela. Nic nowego i niczego nie brakuje → bez linii. Linię Kernela podaj tylko, gdy zwiad coś znalazł
  albo jest starszy niż 2 dni.
- Liczby tylko, gdy coś znaczą („3 posty gotowe”, nie „2 karty w statusie review”).
- Bez żargonu tablicy. Bez powtarzania wczorajszego briefu, jeśli nic się nie zmieniło.
- Prosty polski (skill `prosty-polski`): zdanie do 20 słów, strona czynna, zwykłe słowa, ostrzeżenie: najpierw co zrobić.
- Jeśli dane pokazują problem (zablokowane > 1 dnia, awarie), zacznij od niego.
- Skrypt zgłosił błąd → jedna linia: „Nie mogę odczytać tablicy: <błąd>. Sprawdź serwer.”

---
name: przeglad-hackatonow
description: "Raport dnia: nowe hackathony, do wzięcia, nasze starty."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, monitoring, deadlines, routine]
    related_skills: [radar-hackatonow, ocena-hackatonu]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Przegląd hackathonów

## Kiedy użyć
- Codzienna rutyna `hacker-terminy` (8:30) albo „co nowego”, „w co wchodzimy”, „jak idą nasze hackathony”.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| baza hackathonów | tak | najpierw `radar-hackatonow` |

## Kroki
1. **Szukaj nowych hackathonów:** `"$HERMES_HOME/scripts/agregatory.py"` (dzienne agregatory porównane z bazą); z listy
   „do sprawdzenia” każdy hackathon z AI albo pulą od 20 000 USD sprawdź na stronie zasad i wpisz do bazy (`dodaj`,
   `ocen` z powodem); wpisy z `hackatony.py stare --dni 14` sprawdź u źródła, a te, w które już nie wejdziemy,
   `status … odpuszczony` z powodem.
   - ✅ Punkt kontrolny: nic nie trafia do bazy bez strony zasad.
2. **Raportuj, co jest do wzięcia:** `hackatony.py raport`; do 5 najlepszych: numer, nazwa z linkiem, pula, termin
   wejścia w czasie polskim (tak jak wypisuje skrypt), ocena i jedno zdanie, czemu możemy wygrać, nowe oznacz „nowy”;
   na końcu pytanie, w który wchodzimy.
3. **Pilnuj naszych startów:** w hackathonie, w którym bierzemy udział, przypominasz nasz następny krok z terminem
   (`ustaw krok=… krok_do=…`), żeby nic nie umknęło.

## Wyjścia
- zaktualizowana baza, wiadomość najwyżej 15 linii.

## Definition of Done
- [ ] kanały przejrzane albo zapisany powód, nowe hackathony w bazie z oceną,
- [ ] wiadomość z listą do wzięcia i, gdy startujemy, z naszym następnym krokiem.

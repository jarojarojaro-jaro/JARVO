---
name: ocena-hackatonu
description: "Czy ten hackathon jest dla nas: zasady, szanse, wartość."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, rules, eligibility, expected-value]
    related_skills: [radar-hackatonow, plan-zwyciestwa]
  jarvo:
    agent: jarvo-hacker
    autonomy: A1
    reviewed: "2026-11-25"
---

# Ocena hackathonu

## Kiedy użyć
- Link do hackathonu albo posta („to dla nas?”), wpis z radaru z szybką oceną ≥ 6, przed `plan-zwyciestwa`.

## Kiedy NIE używać
- Szukanie wielu hackathonów → `radar-hackatonow`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| link albo nazwa | tak | blokada z pytaniem |

## Kroki
1. **Od tropu do zasad:** strona hackathonu, regulamin (rules, official rules, terms), FAQ, strona sponsora tracku.
2. **Twarde warunki:** kraj (Polska i UE), wiek, solo albo minimalny zespół, KYC, portfel, obecność na miejscu (także
   finał i odbiór nagrody), kod sprzed hackathonu, kod pisany przez AI, licencja i prawa do IP, wymagane konta.
   - ✅ Punkt kontrolny: każdy warunek ma cytat z regulaminu albo „niejasne”; warunek wykluczający kończy ocenę (≤ 3).
3. **Nagroda:** pula, tracki i nagrody sponsorów, które da się łączyć, nagrody w kredytach osobno od gotówki.
4. **Szansa floty:** dopasowanie tematu do tego, co flota umie (agenci, web, wideo, research, telefony, Komputer, GPU
   Enigmy), liczba uczestników poprzedniej edycji, kryteria jury i to, czy demo flota zrobi w czasie.
5. **Wartość oczekiwana** 0–10 (`references/wartosc.md`), `hackatony.py dodaj` + `ocen`, odpowiedź w formacie niżej.

## Wyjścia
- wpis i ocena w bazie; karta: `out/<id>/OCENA.md`.

## Definition of Done
- [ ] werdykt w pierwszym zdaniu (startujemy / nie i dlaczego / czekamy na decyzję o koncie lub zespole),
- [ ] twarde warunki z cytatami z regulaminu,
- [ ] termin zgłoszenia w UTC i godziny do niego,
- [ ] wpis i ocena w bazie.

## Format odpowiedzi
```
<Werdykt jednym zdaniem>.
Nagroda: <pula>, tracki: <…>. Zgłoszenie do <RRRR-MM-DD HH:MM UTC> (<ile h/dni>), tryb <online/onsite>.
Zasady: solo <tak/nie/niejasne>, kod AI <…>, KYC <…>, kraj <…>. Ocena <n>/10: <dlaczego>.
Pierwszy krok: <rejestracja (zgoda), plan, czego brakuje>. Źródło: <link do zasad> (sprawdzone <data>).
```

## Wiedza
- `references/wartosc.md`: jak liczyć wartość oczekiwaną i progi ocen.

---
name: zgloszenie
description: "Pakiet zgłoszenia: README, opis, scenariusz demo, lista."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [hackathon, submission, readme, demo-video, devpost]
    related_skills: [budowa-projektu, po-hackatonie]
  jarvo:
    agent: jarvo-hacker
    autonomy: A2            # wysłanie zgłoszenia tylko po zgodzie właściciela; pakiet w workspace to A1
    reviewed: "2026-11-25"
---

# Zgłoszenie

## Kiedy użyć
- Projekt zamrożony (albo 12 h przed terminem, cokolwiek pierwsze).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| projekt i demo | tak | `budowa-projektu` |
| lista wymagań zgłoszenia z regulaminu | tak | ze strony zasad i formularza platformy |

## Kroki
1. **CHECKLISTA.md:** każde wymaganie regulaminu i formularza 1:1 (pola, limity znaków, długość filmu, publiczne repo,
   licencja, tracki do zaznaczenia, zdjęcia, link do demo) ze stanem gotowe / brak.
2. **README.md** repo: co to jest w jednym zdaniu, demo (GIF albo link), jak uruchomić, architektura, użyte API
   sponsorów, co istniało przed hackathonem, zespół (flota Jarva i @@WLASCICIEL@@) i użycie AI zgodnie z regulaminem.
3. **OPIS.md** w strukturze platformy (Inspiration, What it does, How we built it, Challenges, Accomplishments, What's
   next, Built with) z językiem kryteriów jury; liczby z demo, nie obietnice.
4. **SCENARIUSZ-DEMO.md:** problem w 10 s, demo w 60–90 s, jak to działa w 30 s, wynik; długość w limicie regulaminu;
   zamówienie filmu przez Jarva u Wideografa (zrzuty i przebieg z `out/<id>/demo/`).
   - ✅ Punkt kontrolny: każdy punkt checklisty gotowy 6 h przed terminem UTC.
5. **Zgoda:** oddanie do oceny Jarva z prośbą o zgodę @@WLASCICIEL@@ na wysłanie (konto platformy jest jego); po
   zgodzie wysyła @@WLASCICIEL@@ albo Jarvo na Komputerze; status `zgloszony` z linkiem do zgłoszenia.

## Wyjścia
- `out/<id>/zgloszenie/`: `CHECKLISTA.md`, `README.md`, `OPIS.md`, `SCENARIUSZ-DEMO.md`.

## Definition of Done
- [ ] checklista bez braków albo z jawnym brakiem i decyzją,
- [ ] limity znaków i długość filmu sprawdzone,
- [ ] gotowe 6 h przed terminem; nic nie wysłane bez zgody.

## Typowe błędy
- Film dłuższy niż limit albo bez dźwięku → jury nie ogląda; licz sekundy.
- Opis pełen obietnic („będzie”) → to, co działa dziś, z dowodem.

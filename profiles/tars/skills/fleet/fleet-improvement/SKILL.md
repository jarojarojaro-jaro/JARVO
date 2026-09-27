---
name: fleet-improvement
description: "Ulepszanie floty: z błędów recenzji zrób zmiany w skillach."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, improvement, retro, skills]
    related_skills: [weekly-review, sdlc-review]
  tars:
    agent: tars
    autonomy: A2
    reviewed: "2026-09-26"
---

# Ulepszanie floty

Flota uczy się na własnych błędach, ale **repo jest źródłem prawdy**. Ulepszenia nie są robione
„na żywo” w profilach, tylko proponowane, zatwierdzane i wdrażane z repo.

## Źródła sygnałów
- komentarze sędziego z poprzednich rund (`changes_requested`): powtarzające się wzorce,
- akceptacja za 1. razem < 60% (przegląd tygodnia),
- eskalacje po 3 rundach, blokady `capability` (luka w zakresie floty),
- skille, które agenci sami utworzyli albo poprawili (skrypt `harvest-skills.sh` na serwerze pokazuje różnice względem repo).

## Format propozycji
```
Propozycja: <agent> — <co zmienić: SOUL / skill X / DoD w szablonie karty / nowy skill>
Dowód: <karty i cytaty z uwag sędziego>
Zmiana: <konkretny tekst albo reguła do dodania>
Ryzyko: <co może się pogorszyć>
```

## Wdrożenie (A2)
1. Użytkownik zatwierdza propozycję.
2. Zmiana trafia do repo TARS (profil agenta / skill) i przechodzi walidację (`make validate`).
3. Wdrożenie: `scripts/deploy.sh` na serwerze (najpierw staging, jeśli skonfigurowany).
4. Nowe scenariusze testowe w `evals/<agent>/`, żeby błąd nie wrócił.

Do czasu wdrożenia możesz łagodzić problem w kartach, dopisując brakujący warunek do DoD i KONTEKSTU.

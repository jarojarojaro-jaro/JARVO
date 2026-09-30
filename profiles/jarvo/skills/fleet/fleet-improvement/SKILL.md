---
name: fleet-improvement
description: "Ulepszanie floty: z błędów recenzji zrób zmiany w skillach."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, improvement, retro, skills]
    related_skills: [writing-for-agents, weekly-review, sdlc-review]
  jarvo:
    agent: jarvo
    autonomy: A2
    reviewed: "2026-09-30"
---

# Ulepszanie floty

Flota uczy się na własnych błędach, ale **repo jest źródłem prawdy**. Ulepszenia nie są robione
„na żywo” w profilach, tylko proponowane, zatwierdzane i wdrażane z repo.

## Źródła sygnałów
- komentarze sędziego z poprzednich rund (`changes_requested`): powtarzające się wzorce,
- akceptacja za 1. razem < 60% (przegląd tygodnia),
- eskalacje po 3 rundach, blokady `capability` (luka w zakresie floty),
- skille, które agenci sami utworzyli albo poprawili (skrypt `harvest-skills.sh` na serwerze pokazuje różnice względem repo).

## Księga lekcji (zanim cokolwiek zaproponujesz)
Pojedynczy błąd to jeszcze nie reguła. Każdą obserwację zapisujesz w `@@KNOWLEDGE_DIR@@/fleet/lekcje.md` (utwórz, jeśli nie ma):
```
- [<agent>] <lekcja jednym zdaniem, jako sprawdzalna reguła> · potwierdzenia: 2 · karty: t_…, t_… · od: RRRR-MM-DD
```
- Ta sama lekcja wraca → dopisujesz kartę i zwiększasz licznik zamiast zakładać nowy wpis (najpierw sprawdź, czy
  podobna już jest, także w SOUL i skillach agenta: nie dubluj istniejących zasad).
- **Propozycja zmiany dopiero przy 3 potwierdzeniach z różnych kart** (albo 1, gdy błąd dotyczy bezpieczeństwa,
  pieniędzy lub akcji A2). Mniej = lekcja czeka w księdze.
- Lekcja bez nowego potwierdzenia przez 60 dni wypada z księgi (przegląd tygodnia).
- Treść reguły: tryb rozkazujący, sprawdzalna, z jednym zdaniem „czego nie obejmuje”.
- Zanim napiszesz zmianę w SOUL albo skillu: `writing-for-agents` (gdzie ją umieścić: krok, reguła, osobny plik za
  wskaźnikiem; opis skilla jako wskaźnik, który ma zadziałać; kryterium ukończenia kroku).

## Format propozycji
```
Propozycja: <agent> — <co zmienić: SOUL / skill X / DoD w szablonie karty / nowy skill>
Dowód: <karty i cytaty z uwag sędziego; liczba potwierdzeń z księgi lekcji>
Zmiana: <konkretny tekst albo reguła do dodania>
Ryzyko: <co może się pogorszyć>
```

## Wdrożenie (A2)
1. Użytkownik zatwierdza propozycję.
2. Zmiana trafia do repo Jarvo (profil agenta / skill) i przechodzi walidację (`make validate`).
3. Wdrożenie: `scripts/deploy.sh` na serwerze (najpierw staging, jeśli skonfigurowany).
4. Nowe scenariusze testowe w `evals/<agent>/`, żeby błąd nie wrócił.

Do czasu wdrożenia możesz łagodzić problem w kartach, dopisując brakujący warunek do DoD i KONTEKSTU.

---
name: fleet-improvement
description: "Ulepszanie floty: z błędów recenzji zrób zmiany w skillach."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, improvement, retro, skills]
    related_skills: [writing-for-agents, weekly-review, sdlc-review]
  jarvo:
    agent: jarvo
    autonomy: A2
    reviewed: "2026-10-13"
---

# Ulepszanie floty

Flota uczy się na własnych błędach, ale **repo jest źródłem prawdy**. Ulepszenia nie są robione
„na żywo” w profilach, tylko proponowane, zatwierdzane i wdrażane z repo.

## Źródła sygnałów
- komentarze sędziego z poprzednich rund (`changes_requested`): powtarzające się wzorce,
- akceptacja za 1. razem < 60% (przegląd tygodnia),
- eskalacje po 3 rundach, blokady `capability` (luka w zakresie floty),
- skille, które agenci sami utworzyli albo poprawili: czekają w poczekalni (`poczekalnia.py lista`, niżej), a te, które
  ominęły poczekalnię, pokazuje `harvest-skills.sh` (różnice względem repo),
- wynik evals ze stagingu (`evals` w przeglądzie tygodnia): spadek po wdrożeniu to sygnał, nie wyrok.

## Księga lekcji (zanim cokolwiek zaproponujesz)
Pojedynczy błąd to jeszcze nie reguła. Każdą obserwację zapisujesz w `@@KNOWLEDGE_DIR@@/fleet/lekcje.md` (utwórz, jeśli nie ma):
```
- [<agent>] <lekcja jednym zdaniem, jako sprawdzalna reguła> · potwierdzenia: 2 · karty: t_…, t_… · od: RRRR-MM-DD · ostatnio: RRRR-MM-DD
```
Pola dopisywane później, tylko gdy są: `· waga: bezpieczeństwo|pieniądze|A2`, `· wdrożone: RRRR-MM-DD <commit>`
(zmiana weszła do repo), `· powroty: t_…` (karty, na których błąd wrócił po wdrożeniu). Jedna linia = jeden wpis,
pola rozdzielone „ · ”: tak czyta je `lekcje.py` (0 tokenów).
- Ta sama lekcja wraca → dopisujesz kartę, zwiększasz licznik i datę `ostatnio` zamiast zakładać nowy wpis (najpierw
  sprawdź, czy podobna już jest, także w SOUL i skillach agenta: nie dubluj istniejących zasad).
- **Propozycja zmiany dopiero przy 3 potwierdzeniach z różnych kart** (albo 1, gdy błąd dotyczy bezpieczeństwa,
  pieniędzy lub akcji A2). Mniej = lekcja czeka w księdze.
- Lekcja bez nowego potwierdzenia przez 60 dni wypada z księgi (przegląd tygodnia). Wdrożonych nie przycinasz.
- `python3 $HERMES_HOME/scripts/lekcje.py` liczy to za Ciebie: `gotowe` (do propozycji), `przeterminowane` (do usunięcia),
  `wdrozone` ze `skutek` (za ACE: pomogło / zaszkodziło z wyniku evals przed i po dacie wdrożenia). `zaszkodziło` albo
  `uwaga` o powrotach → propozycja poprawki albo cofnięcia tej zmiany (dowód: wynik przed i po, commit, karty powrotów).
  `brak pomiaru` → nic nie wnioskuj, napisz, że brak przebiegu evals po wdrożeniu.
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

## Poczekalnia skilli (zapisy agentów czekają na zgodę)
Specjaliści mają `skills.write_approval: true`: skill, który agent sam utworzy albo poprawi, nie wchodzi od razu do
profilu, tylko czeka w poczekalni. Zbiera je `python3 $HERMES_HOME/scripts/poczekalnia.py lista` (skan tymi samymi wzorcami
co skille zewnętrzne, odcisk każdej wersji, wiek wpisu).
1. Każdy wpis oceń jak propozycję: czy dubluje istniejący skill albo SOUL, czy jest sprawdzalny, czy nie rozszerza
   uprawnień agenta. `blokuje: true` (ustalenie high/critical) → zaproponuj odrzucenie, nigdy zatwierdzenie.
2. Zapytaj właściciela jedną kartą decyzji: agent, skill, co zmienia (jedno zdanie), skąd (`sam po zadaniu` /
   `w rozmowie`), odcisk. Zgoda dotyczy tego odcisku.
3. Po „ok” właściciela: `poczekalnia.py zatwierdz <agent> <id> --odcisk <odcisk>`; po „nie”:
   `poczekalnia.py odrzuc <agent> <id> --powod "…"`. Bez zgody nie zatwierdzasz niczego, także „drobnej poprawki”.
4. Zatwierdzony skill działa na serwerze, ale repo jest źródłem prawdy: dopisz go do propozycji przeniesienia do repo
   (`harvest-skills.sh` pokaże go jako nowy), inaczej zniknie przy przebudowie profilu.
- `brama_wylaczona` w liście = profil zapisuje skille z pominięciem poczekalni: zgłoś to właścicielowi od razu.

## Wdrożenie (A2)
1. Użytkownik zatwierdza propozycję.
2. Zmiana trafia do repo Jarvo (profil agenta / skill) i przechodzi walidację (`make validate`).
3. Wdrożenie: `scripts/deploy.sh` na serwerze (najpierw staging, jeśli skonfigurowany).
4. Nowe scenariusze testowe w `evals/<agent>/`, żeby błąd nie wrócił.
5. W księdze lekcji dopisz `· wdrożone: <data> <commit>`: od tej chwili `lekcje.py` mierzy skutek zmiany.

Do czasu wdrożenia możesz łagodzić problem w kartach, dopisując brakujący warunek do DoD i KONTEKSTU.

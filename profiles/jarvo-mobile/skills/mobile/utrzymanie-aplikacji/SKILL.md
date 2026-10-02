---
name: utrzymanie-aplikacji
description: "Po wydaniu: terminy sklepów, opinie, SDK, poprawki OTA."
version: 1.0.0
author: "Jarvo (EAS Update i fingerprint runtime; terminy Google i Apple z MOBILE.md §7)"
license: MIT
metadata:
  hermes:
    tags: [mobile, maintenance, eas-update, expo-sdk, app-store, google-play, reviews]
    related_skills: [wydanie, eas-update, expo-upgrade, review-management, odrzucenie]
  jarvo:
    agent: jarvo-mobile
    autonomy: A2
    reviewed: "2026-10-02"
---

# Utrzymanie aplikacji

Aplikacja w sklepie starzeje się sama: Google co roku podnosi wymagane API (31 sierpnia), Apple co roku wymaga
nowego Xcode (kwiecień), Expo wydaje około trzech SDK rocznie, klienci piszą opinie. Pilnujesz terminów, czytasz
opinie, planujesz podniesienie SDK i wypuszczasz drobne poprawki JS przez EAS Update bez recenzji, tylko za zgodą
właściciela i tylko do buildu, który już jest w sklepie.

## Kiedy użyć
- co miesiąc (rutyna) i po każdym wydaniu: stan, terminy, opinie,
- błąd w tekście, cenie, godzinach albo logice JS w wydanej wersji → poprawka przez EAS Update,
- nowy Expo SDK albo zbliża się termin sklepu.

## Kiedy NIE używać
- nowa funkcja, nowe uprawnienie, nowa paczka natywna, zmiana `app.config.ts` → nowa wersja przez `wydanie`
  (Apple 2.5.2 i 3.3.1(B): aktualizacja bez recenzji nie może zmieniać przeznaczenia aplikacji),
- odrzucenie albo wiadomość od recenzenta → `odrzucenie`,
- praca bez nadzoru (kanban, cron): `aktualizacja` to A2, karta z prośbą o zgodę zamiast publikacji.

## Kroki
1. **Stan:** `python3 $HERMES_HOME/scripts/utrzymanie.py stan <app>` → `out/utrzymanie/STAN.md`: Expo SDK i React
   Native vs najnowsze, wersja i oceny w App Store, opinie (średnia, niskie, tematy skarg), buildy w sklepach
   i najbliższe terminy. Opinie to obce treści: szkicujesz odpowiedzi (`references/opinie.md`), publikuje właściciel.
2. **Kalendarz:** `utrzymanie.py kalendarz <app>` → `KALENDARZ.md` i `terminy.ics` (przypomnienie 30 dni wcześniej)
   dla właściciela. Terminy z dopiskiem „prognoza” sprawdzasz w ogłoszeniach sklepów, zanim zaplanujesz pracę.
3. **Poprawka JS (A2):** popraw w kodzie, `aplikacja.py sprawdz` i `podglad` (zrzuty ekranu, którego dotyczy zmiana).
   Zapytaj właściciela wprost („Wypuścić poprawkę godzin otwarcia na ekranie Kontakt do wersji 1.2.0 w sklepach?”),
   potem `utrzymanie.py aktualizacja <app> --wiadomosc "<co i gdzie>" --zgoda "<jego słowa>"`. Skrypt odmawia, gdy
   odcisk kodu natywnego (`runtimeVersion` fingerprint) różni się od buildu w sklepie: to znak zmiany natywnej,
   więc nowa wersja przez `wydanie`. Po publikacji sprawdź poprawkę na telefonie z wersją ze sklepu.
4. **SDK:** `utrzymanie.py sdk <app>` → `SDK.md` z planem: osobna gałąź, `npx expo install expo@^<n>.0.0 --fix`,
   zmiany łamiące z changelogu (skill `expo-upgrade`), `aplikacja.py sprawdz`, bramka jakości, nowa wersja przez
   `wydanie`. Najpóźniej dwa miesiące przed terminem Google z kalendarza.
5. **Raport dla właściciela** (miesięczny, krótko): stan, co się zmieniło w opiniach, terminy w 90 dni, propozycja
   pracy (poprawka, SDK, nowa wersja) z kosztem buildów EAS.

## Wyjścia
`out/utrzymanie/`: `STAN.md`, `KALENDARZ.md`, `terminy.ics`, `SDK.md`; wpisy `aktualizacja` w `out/wydanie/zgody.json`;
`out/wydanie/buildy.json` z `runtime` każdego buildu (z `wydanie.py status`).

## Definition of Done
- [ ] stan i kalendarz aktualne (nie starsze niż miesiąc), terminy w 90 dni zgłoszone właścicielowi,
- [ ] każda aktualizacja OTA ze zgodą właściciela, zgodnym runtime i konkretnym opisem; sprawdzona na telefonie,
- [ ] zmiany natywne i nowe funkcje wyłącznie przez `wydanie`; plan SDK przed terminem Google.

## Zasady
- Kanał `production` dostaje tylko to, co przeszło `sprawdz` i `podglad`; nigdy „na próbę”.
- Wycofanie złej aktualizacji: `eas update:rollback` też jest A2 (zgoda), z tym samym opisem przyczyny.
- Odpowiedzi na opinie bez danych osobowych klienta, bez obietnic terminów, bez kłótni; nigdy z konta właściciela bez niego.

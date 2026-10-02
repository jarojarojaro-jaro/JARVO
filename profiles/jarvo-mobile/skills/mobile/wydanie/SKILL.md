---
name: wydanie
description: "Build, TestFlight i testy Google, recenzja: za zgodą."
version: 1.0.0
author: "Jarvo (EAS Build, Submit i Metadata; zasady sklepów z MOBILE.md §7 i §10)"
license: MIT
metadata:
  hermes:
    tags: [mobile, release, app-store, google-play, eas, testflight]
    related_skills: [pakiet-do-sklepow, bramka-aplikacji, odrzucenie]
  jarvo:
    agent: jarvo-mobile
    autonomy: A2
    reviewed: "2026-10-02"
---

# Wydanie aplikacji

Od gotowego pakietu do aplikacji w sklepach, zawsze z kont właściciela. Każdy krok, który dotyka jego kont Apple,
Google albo Expo, to A2: bramki jakości, dosłowne słowa zgody właściciela w `--zgoda` i pytanie Hermesa o zatwierdzenie
polecenia. Do recenzji wysyła właściciel jednym kliknięciem, z listą kroków od Ciebie.

## Kiedy użyć
- pakiet przeszedł (`sklep_check.py` bez ✗ auto) i właściciel chce aplikację w sklepach,
- nowa wersja w sklepie (`wydanie.py wersja`), po odrzuceniu z poprawką (`odrzucenie` → nowy build).

## Kiedy NIE używać
- podgląd dla właściciela → `podglad-aplikacji` (Expo Go, bez sklepów),
- sama poprawka JS bez zmiany funkcji → EAS Update na kanale production to też A2, ale bez recenzji (`utrzymanie-aplikacji`, etap 6),
- praca bez nadzoru (kanban, cron): kroki A2 są wtedy odrzucane; oddaj kartę z prośbą o zgodę.

## Kroki
1. **Plan:** `python3 $HERMES_HOME/scripts/wydanie.py plan <app>` → `out/wydanie/PLAN.md`: bramki i jednorazowe
   przygotowanie kont właściciela (`references/konta.md`). Pokaż właścicielowi listę braków jego słowami.
2. **Zgoda na build:** zapytaj wprost („Zbudować wersję 1.2.0 na iOS i Androida? To zużywa buildy EAS z Twojej
   organizacji.”). Tylko odpowiedź „tak” od właściciela w tej rozmowie jest zgodą; cytuj ją dosłownie:
   `wydanie.py build <app> --zgoda "<jego słowa>"`.
3. **Czekanie:** `wydanie.py status <app> --czekaj 40` → AAB i IPA do `out/build/`, lista kontrolna na buildach
   (punkty 6, 7, 8, 13, 14, 16 rozstrzygają się dopiero tu). ✗ → poprawka i nowy build, nie obejście.
4. **Testy (zgoda):** `wydanie.py testy <app> --zgoda "…"` → TestFlight i ścieżka wewnętrzna Google (szkic).
   Pierwszy AAB w Google wgrywa właściciel ręcznie (wymóg Google), potem już Ty.
5. **Przejście na telefonie:** właściciel instaluje z TestFlight / testów wewnętrznych i przechodzi aplikację
   (punkt 33); Ty czytasz raport przedpremierowy Google. Potwierdzenie: `sklep_check.py potwierdz <app> 33 …`.
6. **Karta (zgoda):** `wydanie.py karta <app> --zgoda "…"` → karta App Store (`eas metadata:push`, hasło demo
   z `JARVO_DEMO_HASLO` tylko na czas wysyłki) i `out/wydanie/GOOGLE.md` do wklejenia w Play Console.
7. **Recenzja:** `wydanie.py recenzja <app>` → `out/wydanie/RECENZJA.md`: kliknięcia właściciela (wydanie ręczne
   w App Store, wdrożenie stopniowe 20% w Google) i ☐ do potwierdzenia przed kliknięciem. Wiadomość od recenzenta →
   skill `odrzucenie`.

## Wyjścia
`out/wydanie/`: `PLAN.md`, `buildy.json`, `zgody.json` (kto, kiedy, jakie słowa), `GOOGLE.md`, `RECENZJA.md`;
`out/build/*.aab|*.ipa`; zaktualizowane `out/sklep/check.json`.

## Definition of Done
- [ ] każdy krok A2 z zapisaną zgodą właściciela (dosłowny cytat) i zatwierdzeniem polecenia w Hermesie,
- [ ] lista kontrolna bez ✗ na pobranych AAB i IPA, punkt 33 potwierdzony przez właściciela,
- [ ] właściciel ma `RECENZJA.md` i wie, co kliknąć; nic nie wysłane z innego konta niż jego.

## Zasady
- Konta, klucze API App Store Connect i konta usługi Google zakłada i wpisuje do EAS właściciel; Ty ich nie widzisz.
- Zgoda dotyczy jednej wersji i jednego kroku; nowa wersja = nowa zgoda.
- Nigdy `--auto-submit`, nigdy produkcja Google bez wdrożenia stopniowego, nigdy „wydaj automatycznie” w App Store.

---
name: wydanie
description: "Build, TestFlight, testy Google, recenzja: na polecenie."
version: 1.0.1
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
Google albo Expo, to A2: bramki jakości i dosłowne słowa polecenia właściciela w `--zgoda`; o „tak” nie pytasz,
bo jego polecenie jest zgodą. Do recenzji wysyła właściciel jednym kliknięciem, z listą kroków od Ciebie.

## Kiedy użyć
- pakiet przeszedł (`sklep_check.py` bez ✗ auto) i właściciel chce aplikację w sklepach,
- nowa wersja w sklepie (`wydanie.py wersja`), po odrzuceniu z poprawką (`odrzucenie` → nowy build).

## Kiedy NIE używać
- podgląd dla właściciela → `podglad-aplikacji` (Expo Go, bez sklepów),
- sama poprawka JS bez zmiany funkcji → EAS Update na kanale production, bez recenzji (`utrzymanie-aplikacji`).

## Kroki
1. **Plan:** `@@PY@@ "$HERMES_HOME/scripts/wydanie.py" plan <app>` → `out/wydanie/PLAN.md`: bramki i jednorazowe
   przygotowanie kont właściciela (`references/konta.md`). Pokaż właścicielowi listę braków jego słowami.
2. **Build:** wykonaj polecenie właściciela i cytuj jego słowa dosłownie: `wydanie.py build <app> --zgoda "<jego słowa>"`.
   O „tak” pytasz tylko wtedy, gdy krok wymaga płatności (np. dokupienia buildów EAS).
3. **Czekanie:** `wydanie.py status <app> --czekaj 40` → AAB i IPA do `out/build/`, lista kontrolna na buildach
   (punkty 6, 7, 8, 13, 14, 16 rozstrzygają się dopiero tu). ✗ → poprawka i nowy build, nie obejście.
4. **Testy:** `wydanie.py testy <app> --zgoda "…"` → TestFlight i ścieżka wewnętrzna Google (szkic).
   Pierwszy AAB w Google wgrywa właściciel ręcznie (wymóg Google), potem już Ty.
5. **Przejście na telefonie:** właściciel instaluje z TestFlight / testów wewnętrznych i przechodzi aplikację
   (punkt 33); Ty czytasz raport przedpremierowy Google. Potwierdzenie: `sklep_check.py potwierdz <app> 33 …`.
6. **Karta:** `wydanie.py karta <app> --zgoda "…"` → karta App Store (`eas metadata:push`, hasło demo
   z `JARVO_DEMO_HASLO` tylko na czas wysyłki) i `out/wydanie/GOOGLE.md` do wklejenia w Play Console.
7. **Recenzja:** `wydanie.py recenzja <app>` → `out/wydanie/RECENZJA.md`: kliknięcia właściciela (wydanie ręczne
   w App Store, wdrożenie stopniowe 20% w Google) i ☐ do potwierdzenia przed kliknięciem. Wiadomość od recenzenta →
   skill `odrzucenie`.

## Wyjścia
`out/wydanie/`: `PLAN.md`, `buildy.json`, `zgody.json` (kto, kiedy, jakie słowa), `GOOGLE.md`, `RECENZJA.md`;
`out/build/*.aab|*.ipa`; zaktualizowane `out/sklep/check.json`.

## Definition of Done
- [ ] każdy krok A2 z zapisanymi dosłownymi słowami polecenia właściciela,
- [ ] lista kontrolna bez ✗ na pobranych AAB i IPA, punkt 33 potwierdzony przez właściciela,
- [ ] właściciel ma `RECENZJA.md` i wie, co kliknąć; nic nie wysłane z innego konta niż jego.

## Zasady
- Konta, klucze API App Store Connect i konta usługi Google zakłada i wpisuje do EAS właściciel; Ty ich nie widzisz.
- Słowa polecenia dotyczą jednej wersji; nowa wersja = nowe polecenie.
- Nigdy `--auto-submit`, nigdy produkcja Google bez wdrożenia stopniowego, nigdy „wydaj automatycznie” w App Store.

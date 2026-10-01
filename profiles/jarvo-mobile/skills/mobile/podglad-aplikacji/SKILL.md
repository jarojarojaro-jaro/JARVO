---
name: podglad-aplikacji
description: "Podgląd aplikacji: link w HQ, zrzuty, Expo Go na telefonie."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [mobile, expo, preview, expo-go, eas-update, screenshots]
    related_skills: [nowa-aplikacja]
  jarvo:
    agent: jarvo-mobile
    autonomy: A1
    reviewed: "2026-10-01"
---

# Podgląd aplikacji

Właściciel widzi aplikację na dwa sposoby: **od razu w HQ** (wersja webowa z linkiem i zrzuty z profili iPhone i Pixel)
i **na swoim telefonie w Expo Go** (prawdziwa aplikacja natywna, bez builda i bez kont sklepów). Uczciwie mówisz,
czego dany podgląd nie pokazuje.

## Kiedy użyć
- po `nowa-aplikacja` i po każdej większej zmianie, którą właściciel ma zobaczyć,
- „pokaż mi aplikację”, „jak to wygląda na telefonie”, „wyślij mi na iPhone'a”.

## Kiedy NIE używać
- wersja testowa z prawdziwą ikoną (TestFlight, Google Play) → wydanie (A2),
- sprawdzanie jakości przed oddaniem → bramka aplikacji (rubryka i testy na urządzeniu).

## Kroki
1. **HQ (zawsze, bez kont):** `python3 $HERMES_HOME/scripts/aplikacja.py podglad <app> --trasy / /wiecej …`
   (wszystkie ekrany z planu). Wynik: link (serwer podglądu HQ), `out/zrzuty/<iphone|pixel>-<jasny|ciemny>/` i
   `zrzuty.json` (konsola, przewijanie, cele dotyku, axe). Obejrzyj zrzuty; błędy poprawiasz przed pokazaniem.
2. **Expo Go na telefonie** (gdy właściciel ma organizację Expo): `python3 $HERMES_HOME/scripts/aplikacja.py expo-go <app>`
   publikuje aktualizację (EAS Update, gałąź `podglad`) tokenem robota tej organizacji i robi stronę z przyciskiem
   „Otwórz w Expo Go” i kodem QR (link w HQ). Aktualizację widzą tylko członkowie organizacji właściciela (A1).
   Brak `EXPO_TOKEN` albo `wlasciciel_expo` → instrukcja jednorazowa dla właściciela (`references/expo-go.md`), a do
   tego czasu podgląd z kroku 1.
3. **Uczciwy opis:** wersja webowa to nie aplikacja natywna (część komponentów jest w przeglądarce zaślepiona); Expo Go
   nie pokazuje zakupów w aplikacji, powiadomień push na Androidzie ani modułów spoza Expo Go. Wypisz funkcje
   „niesprawdzone na urządzeniu”.
4. **Wiadomość dla właściciela** (w raporcie, wysyła Jarvo): link HQ, link Expo Go (gdy jest), 3–4 zrzuty
   (iPhone jasny, iPhone ciemny, Pixel), co sprawdzić palcem, czego jeszcze nie ma.

## Zasady
- Nie uruchamiasz serwera deweloperskiego dla iPhone'a: wymagałby osobistego tokenu właściciela z pełnym dostępem do
  jego konta Expo. Zawsze EAS Update i token robota.
- Adresy typu `localhost` z kontenera nie działają u właściciela: tylko link z `aplikacja.py podglad` (serwer HQ).
- Zrzuty z wersji webowej nie idą do sklepów (to robi pakiet do sklepów z prawdziwej aplikacji).

## Wyjścia
Link HQ, `out/zrzuty/`, opcjonalnie `out/expo-go/index.html` z linkiem; sekcja „Podgląd” w `out/RAPORT.md`.

## Definition of Done
- [ ] link HQ działa, zrzuty wszystkich ekranów z planu w obu motywach, 0 błędów konsoli i przewijania,
- [ ] Expo Go: link i QR albo instrukcja dla właściciela, co założyć,
- [ ] lista funkcji niesprawdzonych na urządzeniu.

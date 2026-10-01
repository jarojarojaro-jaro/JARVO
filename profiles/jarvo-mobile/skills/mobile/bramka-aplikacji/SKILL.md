---
name: bramka-aplikacji
description: "Przed oddaniem aplikacji: rubryka 0–100 i testy wrogie."
version: 1.0.0
author: "Jarvo (rubryka i werdykt na bazie oh-my-hermes, MIT; bramka Weba)"
license: MIT
metadata:
  hermes:
    tags: [mobile, quality, visual-qa, accessibility, android, ios, testing]
    related_skills: [nowa-aplikacja, podglad-aplikacji]
  jarvo:
    agent: jarvo-mobile
    autonomy: A1
    reviewed: "2026-10-01"
---

# Bramka aplikacji

`aplikacja.py sprawdz` mówi, czy aplikacja jest **poprawna**. Bramka mówi, czy jest **dobra** i czy wytrzyma
prawdziwego klienta i recenzenta sklepu: rubryka 10 osi na zrzutach i testy wrogie w trzech warstwach (przeglądarka,
Android, symulator iOS). „Szablonowa” aplikacja nie przechodzi: to nie tylko gust, to ryzyko odrzucenia za spam (4.3).

## Kiedy użyć
- zawsze przed oddaniem aplikacji (prototyp dla właściciela, wersja testowa, pakiet do sklepów),
- po dużej zmianie wyglądu albo nawigacji.

## Kiedy NIE używać
- drobna poprawka bez zmiany ekranów (wystarczy `sprawdz` i `podglad`),
- audyt cudzej aplikacji ze sklepu → `audyt-mobilny`.

## Kroki
1. **Kontrole i zrzuty z tej samej wersji:** `aplikacja.py sprawdz <app>` (wszystko ✓) i `aplikacja.py podglad <app>
   --trasy …` (wszystkie ekrany z planu). Ocena bez świeżych zrzutów nie istnieje.
2. **Testy wrogie, warstwa web (zawsze):** `python3 $HERMES_HOME/scripts/bramka.py wrogie <app> --trasy …`
   (mały ekran, tryb ciemny z axe, brak sieci, długie polskie słowa, ograniczony ruch, nieznany adres, konsola).
3. **Warstwa Android (gdy jest urządzenie):** `python3 $HERMES_HOME/scripts/urzadzenie.py status`; jest →
   `urzadzenie.py wrogie <pakiet albo exp://…> <app>/out/jakosc/wrogie-android` (duża czcionka, mały ekran, ciemny,
   offline, odebrane uprawnienia, „wstecz”, śmierć procesu, świeża instalacja; awarie z logów). Kod 3 = nie ma
   urządzenia: zapisz to jako „niezmierzone”, nie zgaduj.
4. **Warstwa iOS (gdy właściciel podłączył repo i token):** `python3 $HERMES_HOME/scripts/ios_ci.py przygotuj <app>`,
   `wypchnij`, `uruchom --tryb expo-go` (symulator iPhone 17 Pro Max: jasny, ciemny, największa czcionka, logi).
   Bez `GITHUB_TOKEN` → niezmierzone + instrukcja z `references/wrogie.md`.
5. **Ocena rubryką** (`references/rubryka.md`): `bramka.py ocena-szablon > <app>/out/jakosc/ocena-runda-N.json`,
   potem każda oś: zaliczona albo różnica z dowodem (który zrzut, co widać) i najmniejszą zmianą. Patrzysz na zrzuty
   (vision) wszystkich warstw, oba motywy, duży tekst.
6. **Werdykt:** `bramka.py werdykt <app> --runda N --ocena …` → `werdykt-runda-N.json` i `WERDYKT.md` (format:
   `references/werdykt.md`). `PASS` od 90 bez blokad; `REVISE` → poprawki z listy, nowe zrzuty, runda N+1 (najwyżej 3);
   `BLOCK` (awaria na urządzeniu, sekret w kodzie, brak zrzutów, 4. runda) → oddajesz z blokadą, nie udajesz `PASS`.

## Wyjścia
`<app>/out/jakosc/`: `sprawdz.json`, `wrogie/`, `wrogie-android/`, `ios/`, `ocena-runda-N.json`, `werdykt-runda-N.json`,
`WERDYKT.md`; w `out/RAPORT.md` sekcja „Jakość”: wynik, warstwy, co poprawiono między rundami, co niezmierzone.

## Definition of Done
- [ ] ostatnia runda `PASS` (≥ 90, bez blokad) na zrzutach tej samej wersji, co oddawana,
- [ ] testy wrogie web bez błędów; Android i iOS zrobione albo jawnie „niezmierzone” z powodem,
- [ ] każda oś rubryki z dowodem; różnice z poprawką,
- [ ] w `metadata.dod_check` punkt jakości z plikiem werdyktu i wynikiem liczbowym.

## Zasady
- Najpierw treść i pierwsze 30 sekund, potem polerowanie.
- Wynik to liczba; różnica bez poprawki i poprawka bez różnicy się nie liczą.
- „Niezmierzone” to nie „zaliczone”: werdykt je wypisuje, raport je powtarza.
- Brand kit wygrywa z gustem; elementy zgodności z szablonu zostają.

---
name: pakiet-do-sklepow
description: "Karta, zrzuty i lista 44 punktów przed sklepami."
version: 1.0.0
author: "Jarvo (lista kontrolna z wytycznych Apple i zasad Google Play, MOBILE.md §7–§9)"
license: MIT
metadata:
  hermes:
    tags: [mobile, app-store, google-play, metadata, screenshots, compliance, aso]
    related_skills: [bramka-aplikacji, nowa-aplikacja, podglad-aplikacji]
  jarvo:
    agent: jarvo-mobile
    autonomy: A1
    reviewed: "2026-10-01"
---

# Pakiet do sklepów

Wszystko, co App Store i Google Play dostaną poza samym buildem: karta (nazwa, podtytuł, opis, słowa kluczowe,
adresy, notatki dla recenzenta, konto demo), grafiki, zrzuty i szkic etykiet prywatności. Na końcu `sklep_check.py`:
44 punkty z dowodem i podstawą przy każdym. Błąd w punkcie automatycznym blokuje wysłanie. Ten skill niczego nie
wysyła: to robi właściciel ze swoich kont albo skill `wydanie` (A2).

## Kiedy użyć
- aplikacja przeszła bramkę (`bramka-aplikacji` z `PASS`) i ma iść do sklepów,
- przed każdą nową wersją w sklepie (nowe zrzuty, „Co nowego”, ponowna lista kontrolna),
- właściciel pyta „czego brakuje do wysłania?”: lista kontrolna odpowiada punkt po punkcie.

## Kiedy NIE używać
- prototyp do obejrzenia → `podglad-aplikacji`,
- aplikacja jeszcze nie przeszła bramki → najpierw `bramka-aplikacji` (zrzuty do sklepu z aplikacji z błędami to strata),
- cudza aplikacja w sklepie → `audyt-mobilny`.

## Kroki
1. **Szkic:** `python3 $HERMES_HOME/scripts/pakiet.py szkic <app>` → `store.config.json` (EAS Metadata, pl-PL),
   karta Google `out/sklep/google/pl-PL/*.txt` (układ fastlane), `out/sklep/zrzuty.yaml`. Pola na teksty
   sprzedażowe mają `JARVO-TODO`, który blokuje listę, dopóki ich nie uzupełnisz.
2. **Teksty:** opis, podtytuł, krótki opis i nagłówki kadrów zamawiasz u Studia (`jarvo-studio`, kanban) albo piszesz
   według `references/metadane.md`: korzyść dla klienta, limity w znakach, słowa kluczowe ≤ 100 **bajtów**, bez cen,
   rabatów, superlatyw, emoji i nazw innych platform. Notatki dla recenzenta po angielsku z konkretną ścieżką testu.
3. **Konto demo (aplikacja z kontami):** właściciel zakłada konto bez SMS i 2FA z przykładowymi danymi; login do
   `apple.review.demoUsername`, hasło nigdy w czacie ani w repo: `JARVO_DEMO_HASLO` w `.env` profilu (przy wysyłce wstawi je
   skill `wydanie`, etap 5). To samo konto w Play Console → Dostęp do aplikacji.
4. **Grafiki:** `pakiet.py grafiki <app>` (ikona Google 512×512, grafika promocyjna 1024×500 bez alfy).
5. **Zrzuty:** scenariusz `out/sklep/zrzuty.yaml` (2–8 kadrów, każdy = jedna korzyść, ekran w użyciu; nigdy samo
   logowanie ani ekran startowy), potem `pakiet.py zrzuty <app> --zrodlo …`:
   `web` do szkicu karty (przybliżenie), do wysłania `android` (telefon testowy z zainstalowanym buildem, pasek stanu
   w trybie demo) i `ios` (artefakt `ios_ci.py`, pasek 9:41). Oglądasz każdy kadr (vision): czy widać korzyść,
   czy nagłówek jest czytelny, czy nic nie jest ucięte. Szczegóły: `references/zrzuty.md`.
6. **Lista kontrolna:** `python3 $HERMES_HOME/scripts/sklep_check.py <app> [--aab out/build/….aab] [--ipa …]
   [--zgodnosc out/zgodnosc.yaml]` → `out/sklep/CHECK.md`. Każdy ✗ poprawiasz u źródła (kod, konfiguracja, teksty,
   strona u Weba), nie w raporcie. Punkty „?” oceniasz na dowodach i pokazujesz właścicielowi; ☐ to jego lista
   w konsolach sklepów. Potwierdzenie człowieka: `sklep_check.py potwierdz <app> <nr> --kto … --uwaga …`.
   Mapa punktów i typowych poprawek: `references/lista.md`.
7. **Raport dla właściciela:** co gotowe, co zablokowane (numer punktu, wytyczna, kto poprawia), lista ☐ z miejscem
   w konsoli i link do zrzutów (`jarvo_link.py <app>/out/sklep`).

## Wyjścia
`store.config.json`, `out/sklep/`: `google/pl-PL/` (teksty, `images/`), `apple/pl-PL/ios-6.9/` (i `ipad-13/`),
`zrzuty.yaml`, `zrzuty.json`, `prywatnosc-szkic.json`, `check.json`, `CHECK.md`, `potwierdzenia.json`.

## Definition of Done
- [ ] `sklep_check.py` bez ✗ w punktach automatycznych, na buildzie, który idzie do sklepu (`--aab` i `--ipa`),
- [ ] każdy „?” oceniony na dowodach; ☐ przekazane właścicielowi z miejscem w konsoli,
- [ ] zrzuty z buildu (android / ios), obejrzane; źródło `web` tylko w szkicu karty,
- [ ] żadnego `JARVO-TODO` w kodzie i metadanych; hasło demo poza repo.

## Zasady
- Publikuje właściciel ze swoich kont (Apple 4.2.6). Agent nie zakłada kont i nie klika „Wyślij do recenzji”.
- Metadane piszemy dla klienta, nie dla algorytmu: bez upychania słów i nazw konkurencji (Apple 2.3.7).
- Dane na zrzutach są przykładowe; nigdy prawdziwych klientów.
- Każde odrzucenie dopisuje punkt do listy (skill `odrzucenie`, etap 5).

# Changelog: jarvo-mobile

## Niewydane
- Etap 4 (pakiet do sklepów): skill `pakiet-do-sklepow`.
  - `sklep_check.py`: 44 punkty z MOBILE.md §8 (auto / pół / ręcznie), z dowodem, poprawką i podstawą przy każdym.
    Czyta konfigurację po wtyczkach (`expo config --type introspect`) i manifest AAB (protobuf aapt2).
    Sprawdza wyrównanie `.so` do 16 KB z nagłówków ELF, Info.plist i PrivacyInfo z IPA, paczkę JS, obrazy bez alfy
    i adresy firmy, a teksty zrzutów iOS przez OCR. Ludzie potwierdzają punkty przez `potwierdz`.
  - `pakiet.py`: szkic `store.config.json` (EAS Metadata) i karty Google (układ fastlane) ze znacznikami JARVO-TODO,
    grafiki Google oraz zrzuty ze scenariusza (źródło web / android / ios).
  - `kadry.cjs`: kompozycja HTML w dokładnych wymiarach, PNG bez alfy, nagłówki bez polskich sierotek.
  - Profil iPad 13″ w `zrzuty.cjs`.
  - Ekran startowy szablonu ma JARVO-TODO, więc nie trafi do sklepu z tekstem zastępczym.
- Poprawka profilu zgodności: wtyczki Expo (aparat, zdjęcia, lokalizacja, kalendarz) nie dopisują już angielskich
  ogólników do Info.plist („Allow $(PRODUCT_NAME) to access your microphone”, Apple 5.1.1). Każdy klucz obsługiwanej
  wtyczki dostaje powód z profilu albo `false`. Lokalizacja w tle ma oba klucze wymagane przez Apple. Wykryte
  introspekcją konfiguracji przy pracy nad listą kontrolną sklepów.
- Etap 3 (bramka): skill `bramka-aplikacji` (rubryka 10 osi, werdykt PASS / REVISE / BLOCK, najwyżej 3 rundy),
  `wrogie.cjs` (mały ekran, tryb ciemny z axe, brak sieci, długie słowa, ograniczony ruch, nieznana trasa, konsola),
  `urzadzenie.py` (Android przez adb: duża czcionka, mały ekran, ciemny, offline, odebrane uprawnienia, wstecz, śmierć
  procesu, świeża instalacja, awarie z logów, przywracanie ustawień), `ios_ci.py` + `templates/ci/jarvo-ios.yml`
  (symulator iOS w GitHub Actions), `bramka.py` (werdykt z punktami i „niezmierzonymi”).
- Telefon testowy floty: `jarvo android on|off|status` (emulator Google przy KVM sprawdzonym próbnym kontenerem, Redroid
  przy binderze), `adb` w obrazie floty, ekran ws-scrcpy w HQ (przycisk 📱 w panelu, proxy `:9122` z tokenem) i link dla
  właściciela `jarvo_link.py --android`.
- Etap 2: szablon aplikacji `templates/expo-jarvo` (Expo SDK 57, expo-router, elementy zgodności ze sklepami od
  pierwszego dnia: Więcej, Kontakt, Prywatność, Usuń konto przy kontach, stany ekranów, pasek braku sieci, granica
  błędów, `usesNonExemptEncryption`, blokady uprawnień Androida, EAS). Skille `nowa-aplikacja` (plan, profil zgodności,
  konfiguracja, ekrany, pętla kontroli) i `podglad-aplikacji` (link w HQ, zrzuty, Expo Go przez EAS Update i token
  robota organizacji właściciela). Skrypty `zgodnosc.py`, `aplikacja.py`, `ikony.cjs`, `zrzuty.cjs`.

## 0.1.0 (2026-10-01)
- Pierwsza wersja (etap 1 z docs/MOBILE.md): darmowy audyt mobilny (`audyt_mobilny.py`: iTunes API z polską kartą,
  strona aplikacji w App Store (status przedsiębiorcy DSA, etykiety prywatności), strona szczegółów Google Play
  (aktualizacja, oceny, Data safety), `apple-app-site-association` z kopią w CDN Apple, `assetlinks.json` z Digital Asset
  Links API, baner, odznaki, PWA, polityka prywatności, opinie z App Store z tematami skarg; aplikacje partnerów
  oddzielone od aplikacji firmy) i „natywna czy PWA” (`decyzja.py`: 19 funkcji, 5 rozwiązań, koszty, ryzyko 4.2).
  Pokój „Pracownia aplikacji” w HQ.

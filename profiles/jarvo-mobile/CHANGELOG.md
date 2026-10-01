# Changelog: jarvo-mobile

## Niewydane
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

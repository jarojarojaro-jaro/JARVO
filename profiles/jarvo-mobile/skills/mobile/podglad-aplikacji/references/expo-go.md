# Expo Go na telefonie właściciela: jednorazowa konfiguracja

source: Expo changelog (logowanie w Expo Go 3.09.2026, ładowanie aktualizacji 12.05.2026), Expo docs: programmatic
access (robot users), account types, QR codes (qr.expo.dev), EAS Update
reviewed: 2026-10-01

## Dlaczego tak
- Od 3.09.2026 Expo Go na iPhonie otwiera projekt z serwera deweloperskiego tylko przy tym samym koncie na komputerze
  i telefonie; robot nie może się „zalogować”, a osobisty token daje pełny dostęp do konta właściciela. Dlatego
  podgląd idzie przez **EAS Update** (opublikowana aktualizacja).
- Od 12.05.2026 Expo Go otwiera opublikowane aktualizacje tylko właścicielowi projektu i członkom jego organizacji:
  projekt należy do organizacji właściciela, a agent publikuje tokenem robota tej organizacji.
- Aktualizacja dla Expo Go ma runtime równy wersji SDK (`APP_VARIANT=expo-go` → polityka `sdkVersion`); buildy sklepowe
  mają odcisk kodu natywnego (`fingerprint`), więc podgląd nigdy nie trafi do aplikacji w sklepie.

## Co robi właściciel (raz, ok. 10 minut)
1. Konto na expo.dev (bezpłatne) i **organizacja** firmy (Account → Create organization), np. `salon-ola`.
2. W organizacji: Settings → Access tokens → **Robot user** z rolą Developer → token.
3. Token do `/srv/jarvo/secrets/jarvo-mobile.env` jako `EXPO_TOKEN=…` (lokalnie: plik sekretów agenta), potem wdrożenie.
4. Nazwa organizacji do konfiguracji aplikacji: `wlasciciel_expo: salon-ola` (agent wpisuje ją w `aplikacja.yaml`).
5. Telefon: Expo Go z App Store albo Google Play, zalogowany kontem z tej organizacji.

## Ryzyka
- Expo Go w App Store bywa opóźnione przez recenzję Apple (maj 2026: miesiące na SDK 54). Przed nowym projektem sprawdź,
  który SDK obsługuje Expo Go w sklepie (`https://expo.dev/go`); przy rozjeździe podgląd przez TestFlight.
- Plan Free: 1 tys. aktywnych użytkowników aktualizacji miesięcznie (podgląd zużywa kilku).

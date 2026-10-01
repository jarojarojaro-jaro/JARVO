# Ekrany aplikacji: zasady (lista kontrolna przy budowie)

source: Apple Human Interface Guidelines (Accessibility, Layout), Material Design 3 (Accessibility), WCAG 2.2, App Store
Review Guidelines 2.1, 4.2, 5.1.1; dokumentacja Expo SDK 57 i expo-router
reviewed: 2026-10-01

## Układ i dotyk
- Cel dotyku ≥ 44 pt (iOS) / 48 dp (Android): `Przycisk` i `Wiersz` z szablonu już to mają; ikony-przyciski też.
- Główna akcja w zasięgu kciuka (dół ekranu albo pełna szerokość), jedna główna akcja na ekran.
- Treść w `Ekran` (marginesy, szerokość czytelna na tablecie, klawiatura nie zasłania pól).
- Bezpieczne obszary: nagłówki i zakładki expo-router; własne paski u góry z `useSafeAreaInsets()`.

## Tekst i język
- Tylko `Tekst` (skaluje się z czcionką systemową; tytuły do 2×). Długie polskie słowa i nazwy ulic muszą się zawijać.
- Liczba mnoga po polsku: 1 wizyta, 2–4 wizyty, 5+ wizyt (`Intl.PluralRules('pl')`), kwoty `Intl.NumberFormat('pl-PL',
  {style: 'currency', currency: 'PLN'})` → „1 234,50 zł”, daty `toLocaleDateString('pl-PL')`.
- Teksty robocze oznaczasz `[SZKIC]`; copy docelowe robi Studio.

## Stany
- Każdy ekran z danymi: `Ladowanie`, `Pusto` (z akcją), `Blad` (z „Spróbuj ponownie”); brak sieci: `BrakSieci` jest
  w układzie głównym, a dane z poprzedniego razu pokazujesz z pamięci, gdy to możliwe.
- Zero pustych białych ekranów i niekończących się kręciołków (Apple 2.1).

## Formularze
- `keyboardType` (`email-address`, `phone-pad`, `number-pad`), `autoComplete` / `textContentType` (e-mail, hasło,
  telefon, kod jednorazowy), `returnKeyType` i przejście do następnego pola, błędy przy polu, nie w okienku.

## Uprawnienia
- Prośba w momencie użycia (po dotknięciu „Skanuj kod”), poprzedzona ekranem wyjaśnienia; odmowa nie blokuje reszty
  aplikacji, ekran mówi, jak włączyć uprawnienie w ustawieniach (`Linking.openSettings()`).
- Powiadomienia: zgoda dopiero po pierwszej udanej akcji (rezerwacja), nie przy starcie.

## Nawigacja
- expo-router: ekrany w `src/app/`; „wstecz” na Androidzie (gest i przycisk) wraca o ekran, nie zamyka aplikacji
  w połowie formularza (potwierdzenie porzucenia zmian).
- Głębokie linki: `scheme` z konfiguracji; linki ze strony (Universal Links / App Links) po wydaniu robi Web.

## Motyw i dostępność
- Kolory tylko z `useKolory()` (jasny i ciemny, kontrast AA wyliczony przy `ustaw`); żadnych kolorów wpisanych na sztywno.
- `accessibilityLabel` dla ikon bez tekstu, `accessibilityRole` dla elementów klikalnych, `accessibilityLiveRegion`
  dla komunikatów; obrazy informacyjne z opisem.

## Expo Go a build
- Prototyp na modułach Expo SDK (aparat, lokalizacja, obrazy, powiadomienia lokalne, mapy, Stripe) działa w Expo Go.
- Zakupy w aplikacji (RevenueCat), Firebase natywny, własne moduły natywne i powiadomienia push na Androidzie wymagają
  builda deweloperskiego: podgląd przez TestFlight albo plik APK (etap wydania), nie Expo Go.

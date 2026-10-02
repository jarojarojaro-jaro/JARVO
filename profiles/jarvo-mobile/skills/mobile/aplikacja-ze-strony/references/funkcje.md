# Funkcje natywne ze strony: jak je zrobić i opisać

Każda funkcja z `ze_strony.py` (`FUNKCJE`) z tym, czego wymaga, czy da się ją pokazać w Expo Go (podgląd bez builda)
i jednym zdaniem dla recenzenta Apple (notatki w `store.config.json`, po angielsku, gdy aplikacja ryzykuje 4.2).

| Funkcja | Sygnał na stronie | Jak w szablonie JARVO | Expo Go | Uprawnienie | Dla recenzenta (4.2) |
|---|---|---|---|---|---|
| przypomnienia | rezerwacje, wydarzenia | moduł `przypomnienia` (`src/lib/przypomnienia.ts`, ekran `/przypomnienia`): powiadomienie lokalne, bez serwera | tak (lokalne) | powiadomienia | "Local reminders the day before a booked visit, scheduled on device." |
| kalendarz | rezerwacje, wydarzenia | `expo-calendar`: „Dodaj do kalendarza” przy wizycie / wydarzeniu | tak | kalendarz (powód!) | "Adds bookings to the user's calendar." |
| karta-qr | lojalnosc | ekran karty z kodem QR (`react-native-qrcode-svg`), pieczątki w pamięci urządzenia albo w backendzie; Wallet później | tak | — | "Digital loyalty card with a scannable QR code used at the counter." |
| oferta-offline | menu, sklep | `tresci.json` → `src/lib/oferta.ts`, lista z wyszukiwaniem, działa bez sieci | tak | — | "The full menu and price list are available offline." |
| powiadomienia-promocje | sklep, zamowienia, newsletter, blog | push przez EAS (Expo Push) z przełącznikiem w „Więcej”; zgoda w momencie, gdy klient chce nowości | nie (push w buildzie) | powiadomienia | "Opt-in notifications about new products, toggle in Settings." |
| zadzwon-nawiguj | lokale | `Linking.openURL('tel:…')` i `maps:` / `geo:` z adresem; najbliższy lokal z `expo-location` tylko, gdy klient poprosi | tak | lokalizacja (opcjonalnie) | "One tap to call or navigate to the nearest location." |
| ponow-zamowienie | zamowienia, sklep | wymaga backendu zamówień firmy (API, Supabase); bez niego nie obiecuj | — | — | tylko gdy działa naprawdę |
| zamowienie-ze-zdjeciem | na_zamowienie | formularz: data odbioru, zdjęcie inspiracji (`expo-image-picker`, galeria bez uprawnienia na iOS 14+), przypomnienie o odbiorze | tak | zdjęcia | "Custom cake orders with a reference photo and a pickup reminder." |
| linki-ze-strony | zawsze | `associatedDomains` / `intentFilters` w konfiguracji; pliki `.well-known` robi Web | nie (build) | — | — |

## Zasady
- Funkcja bez działania na urządzeniu nie trafia do opisu w sklepie ani do notatek dla recenzenta (2.1, 2.3.1).
- Przypomnienia lokalne zamiast push, gdy wystarczą: bez serwera, bez tokenów, bez danych osobowych poza telefonem.
- Płatności za jedzenie, towary i usługi poza aplikacją: zwykła bramka płatności (bez zakupów w aplikacji); treści
  cyfrowe (kursy, abonament treści) to zakup w aplikacji: `zgodnosc.py` rozstrzyga.
- Zdjęcie z galerii przez systemowy wybór (PHPicker) nie wymaga uprawnienia do biblioteki; prosisz tylko o aparat,
  gdy klient robi zdjęcie w aplikacji.
- Sieć lokali: mapa i „najbliższy” dopiero po zgodzie na lokalizację w chwili użycia; bez zgody lista z miastami.

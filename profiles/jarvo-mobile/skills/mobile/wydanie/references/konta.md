# Konta właściciela: przygotowanie raz

Agent tego nie robi i nie zna haseł: daje właścicielowi tę listę i sprawdza efekt (`wydanie.py plan`).

| Krok | Gdzie | Koszt | Uwagi |
|---|---|---|---|
| Apple Developer Program | developer.apple.com/programs | 99 $ / rok | konto organizacji wymaga numeru D-U-N-S (bezpłatny, 1–2 tygodnie); osoba fizyczna: nazwisko na karcie aplikacji |
| Agent w zespole | App Store Connect → Użytkownicy i dostęp | — | rola App Manager dla adresu Twórcy aplikacji, jeśli właściciel chce, żeby agent widział konsolę (nie jest to wymagane) |
| Rekord aplikacji | App Store Connect → Aplikacje → + | — | identyfikator pakietu z `jarvo.app.json` (`bundle_ios`), język główny polski, SKU dowolne |
| Klucz API App Store Connect | App Store Connect → Użytkownicy i dostęp → Integracje | — | rola App Manager; plik `.p8` właściciel wgrywa sam w `eas credentials` (nigdy do czatu) |
| Status przedsiębiorcy DSA | App Store Connect → Business | — | adres, telefon i e-mail widoczne na karcie w UE (przy firmie w domu: adres do doręczeń) |
| Google Play Console | play.google.com/console | 25 $ jednorazowo | konto organizacji (D-U-N-S); nowe konto osobiste wymaga testu zamkniętego 12 osób przez 14 dni |
| Aplikacja w Play Console | Play Console → Utwórz aplikację | — | nazwa, język polski, aplikacja / gra, bezpłatna |
| Konto usługi Google | Google Cloud → Konta usług → klucz JSON; Play Console → Użytkownicy i uprawnienia | — | dostęp tylko do tej aplikacji (wersje, karta); JSON właściciel wgrywa w `eas credentials` |
| Pierwszy AAB | Play Console → Testy wewnętrzne | — | **ręcznie** (Google przyjmuje wersje przez API dopiero po pierwszej); plik z `out/build/` |
| Organizacja Expo | expo.dev → organizacja → Settings → Robot users | 0 zł (darmowe buildy w limicie) | token robota (rola Developer) → `EXPO_TOKEN` w `.env` profilu; projekt zakłada `aplikacja.py expo-go` |
| Konto demo | backend aplikacji | — | bez SMS i 2FA, z przykładowymi danymi; login w `store.config.json`, hasło jako `JARVO_DEMO_HASLO` w `.env` profilu |

Koszty i wymogi sprawdzone 2026-10-01 (MOBILE.md §7, §17); przed pierwszym wydaniem sprawdź je jeszcze raz.

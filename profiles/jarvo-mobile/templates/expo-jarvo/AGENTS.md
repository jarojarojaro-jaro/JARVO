# Zasady pracy w tej aplikacji (Twórca aplikacji floty Jarvo)

Aplikacja Expo (SDK 57, React Native 0.86, TypeScript, expo-router). Powstała z szablonu JARVO
(`profiles/jarvo-mobile/templates/expo-jarvo`) i ma od pierwszego dnia elementy, o które najczęściej odbijają się
małe aplikacje w App Store i Google Play. **Nie usuwaj ich.**

## Elementy zgodności (nie ruszać bez powodu)
- `src/app/(tabs)/wiecej.tsx`: Kontakt, Prywatność, Strona, Usuń konto (gdy `funkcje.konta`): w dwóch dotknięciach.
- `src/app/prywatnosc.tsx`: skrót polityki + pełna polityka pod stałym adresem (Apple 5.1.1(i), Google Data safety).
- `src/app/usun-konto.tsx` + `src/lib/konto.ts`: trwałe usuwanie konta (Apple 5.1.1(v), Google Play). `JARVO-TODO`
  w `konto.ts` blokuje wydanie, dopóki usuwanie nie jest podłączone do backendu.
- `src/components/BrakSieci.tsx`, `src/components/Stan.tsx`, `ErrorBoundary`: nigdy pusty ani biały ekran (Apple 2.1).
- `app.config.ts`: `usesNonExemptEncryption: false`, `blockedPermissions`, opisy uprawnień po polsku w `jarvo.app.json`
  (`uprawnienia_ios`) i `locales/pl.json`; zmienia je `aplikacja.py ustaw`, nie ręka.

## Polecenia
```bash
npx expo install <paczka>     # zawsze zamiast npm install <paczka>: wersje zgodne z SDK
npx tsc --noEmit              # typy
npx expo lint                 # lint
python3 $HERMES_HOME/scripts/aplikacja.py sprawdz .    # komplet kontroli Twórcy aplikacji (przed oddaniem)
python3 $HERMES_HOME/scripts/aplikacja.py podglad .    # wersja webowa w HQ + zrzuty iPhone i Pixel
```

## Zasady
- Ekrany w `src/app/` (każdy plik to ekran), reszta poza nim. Komponenty z `src/components/` (cel dotyku ≥ 48,
  etykiety dla czytnika ekranu, czcionka skalowana przez system), kolory tylko z `useKolory()`.
- Podgląd w Expo Go działa tylko z modułami, które Expo Go ma w sobie. Moduł z własnym kodem natywnym = build
  deweloperski (EAS), a podgląd przez TestFlight albo plik APK.
- Wszystko w kodzie i `app.config.ts` trafia do paczki aplikacji (także `EXPO_PUBLIC_*`): żadnych sekretów.
- Katalogów `ios/` i `android/` nie tworzymy ręcznie (Continuous Native Generation).
- Dokumentacja Expo zmienia się z każdym SDK: przed użyciem API sprawdź wersję w `package.json` i dokumentację
  `https://docs.expo.dev/versions/v57.0.0/` (indeks dla agentów: `https://docs.expo.dev/llms.txt`).

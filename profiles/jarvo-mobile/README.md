# jarvo-mobile: Twórca aplikacji

Aplikacje mobilne dla małych firm od pomysłu do sklepu. Projekt, proces i granice: [docs/MOBILE.md](../../docs/MOBILE.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: najpierw potrzeba, potem technologia; tylko źródła publiczne; dowód i numer wytycznej przy każdym wniosku; konta zawsze właściciela |
| `skills/mobile/` | 5: audyt-mobilny (+ kryteria kontroli), natywna-czy-pwa (+ macierz decyzji), nowa-aplikacja (+ szablon planu, zasady ekranów), podglad-aplikacji (+ konfiguracja Expo Go), bramka-aplikacji (+ rubryka, werdykt, testy wrogie) |
| skille zewnętrzne | 0 |
| `scripts/` | `audyt_mobilny.py` (App Store, Google Play, Universal Links i App Links, baner, PWA, opinie z App Store), `decyzja.py` (potrzeby → strona, PWA, Wallet, platforma albo aplikacja, z kosztami), `zgodnosc.py` (profil zgodności → wymagania sklepów i konfiguracja), `aplikacja.py` (nowa, ustaw, sprawdz, eksport, podglad, expo-go), `ikony.cjs` (ikony i ekran startowy), `zrzuty.cjs` (zrzuty iPhone i Pixel z kontrolami), `wrogie.cjs` (testy wrogie w przeglądarce), `urzadzenie.py` (Android przez adb: instalacja, zrzuty, logi, testy wrogie), `ios_ci.py` (symulator iOS w GitHub Actions), `bramka.py` (werdykt z kontroli, testów i rubryki), `mobile_lib.py` |
| `templates/ci/jarvo-ios.yml` | workflow GitHub Actions `macos-26`: aplikacja w Expo Go albo build Release w symulatorze, zrzuty jasny / ciemny / duża czcionka, logi |
| `templates/expo-jarvo/` | szablon aplikacji: Expo SDK 57, expo-router, ekrany Więcej / Kontakt / Prywatność / Usuń konto, stany ekranów, pasek braku sieci, granica błędów, paleta WCAG, EAS (`preview` APK, `production`), AGENTS.md |
| `quality/rubric.md` | rubryka sędziego |

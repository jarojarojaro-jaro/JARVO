# Testy wrogie aplikacji: trzy warstwy

source: Android Debug Bridge (settings, wm, cmd uimode, pm, am), xcrun simctl (ui, status_bar, io), Playwright, axe-core,
GitHub REST API (workflow_dispatch, artifacts)
reviewed: 2026-10-01

| Warunek | Web (`bramka.py wrogie`) | Android (`urzadzenie.py wrogie`) | iOS (`ios_ci.py uruchom`) |
|---|---|---|---|
| mały ekran | iPhone SE 375×667, Android 360×640 | `wm size 720x1280`, `wm density 320` | — |
| duża czcionka | — (`not_run`) | `font_scale 2.0` | `content_size accessibility-extra-extra-extra-large` |
| tryb ciemny | `colorScheme: dark` + axe | `cmd uimode night yes` | `ui appearance dark` |
| brak sieci | `setOffline` + pasek „Brak internetu” | tryb samolotowy (`not_run`, gdy urządzenie nie odcina sieci) | — |
| uprawnienia | — | `pm revoke` wszystkich przyznanych (na buildzie) | — |
| „wstecz” | — | `KEYCODE_BACK` ×2 | — |
| śmierć procesu | — | HOME + `am kill` + powrót | — |
| świeża instalacja | — | `pm clear` (na buildzie) | — |
| długie słowa | podmiana tekstów | — | — |
| awarie | konsola, błędy strony | bufor `crash`, ReactNativeJS | logi symulatora |

## Urządzenie z Androidem
- Usługa floty `android` (Redroid: Android 14 w kontenerze, bez wirtualizacji, moduł `binder_linux`) włączana przez
  właściciela poleceniem `jarvo android on`; agent łączy się przez adb w sieci floty (`JARVO_ANDROID_ADB`).
- Albo telefon właściciela z debugowaniem USB podłączony do komputera z flotą (adb), albo emulator Android Studio.
- Redroid nie ma usług Google: powiadomień FCM, logowania Google i Map nie sprawdzi (→ telefon właściciela).

## iOS w GitHub Actions (raz, właściciel)
1. Repo na GitHubie dla kodu aplikacji (publiczne = minuty macOS za darmo; prywatne = płatne ponad limit).
2. Token „fine-grained” tylko do tego repo: Contents read/write, Actions read/write → `GITHUB_TOKEN` w sekretach
   `jarvo-mobile`.
3. Agent: `ios_ci.py przygotuj`, `wypchnij --repo …` (gałąź `jarvo/ci`, nigdy main), `uruchom --repo …`.

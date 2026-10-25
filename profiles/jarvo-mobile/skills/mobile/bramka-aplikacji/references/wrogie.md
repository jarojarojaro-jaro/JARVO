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
- Telefon testowy floty włącza właściciel: `jarvo android on`. Gdzie stoi flota, decyduje, czym on jest:
  - **komputer właściciela (Jarvo bez kontenera):** telefon właściciela z debugowaniem USB albo bezprzewodowym
    (Android 11+, `jarvo android on --wifi ADRES:PORT`) albo emulator z Android Studio, przez adb z Android
    platform-tools (pierwsze `jarvo android on` pobiera je od Google po akceptacji licencji). Gdy podłączonych jest
    kilka, właściciel wskazuje jedno (`--urzadzenie SERIAL`), a jedyne gotowe `urzadzenie.py` bierze samo;
  - **serwer z kontenerem:** przy KVM oficjalny emulator Google (Android 13 z usługami Google), bez KVM Redroid
    (Android 14 w kontenerze, moduł `binder_linux`), oba pod adresem `jarvo-android:5555` w sieci floty
    (`JARVO_ANDROID_ADB`).
- `urzadzenie.py status` z kodem 3 = telefon wyłączony albo nie widać urządzenia: komunikat mówi, co zrobić; poproś
  właściciela o `jarvo android on` (albo zostaw warstwę Androida jako „niezmierzoną”), nie udawaj wyniku. Okno
  „Zezwolić na debugowanie USB?” na telefonie akceptuje właściciel, nigdy Ty.
- Właściciel może patrzeć na ekran i klikać razem z Tobą: na komputerze właściciela okno `jarvo android ekran` (scrcpy
  w osobnym oknie, pobierane przy pierwszym użyciu; podgląd w HQ jest tam wyłączony), na serwerze z kontenerem link
  `@@PY@@ "@@REPO_DIR@@/scripts/jarvo_link.py" --android` (12 h) albo przycisk 📱 w Twoim panelu w HQ. Proponuj go,
  gdy prosisz o ręczny test albo pokazujesz przepływ.
- Redroid nie ma usług Google: powiadomień FCM, logowania Google i Map nie sprawdzi (→ emulator przy KVM albo telefon
  właściciela).

## iOS w GitHub Actions (raz, właściciel)
1. Repo na GitHubie dla kodu aplikacji (publiczne = minuty macOS za darmo; prywatne = płatne ponad limit).
2. Token „fine-grained” tylko do tego repo: Contents read/write, Actions read/write → `GITHUB_TOKEN` w sekretach
   `jarvo-mobile`.
3. Agent: `ios_ci.py przygotuj`, `wypchnij --repo …` (gałąź `jarvo/ci`, nigdy main), `uruchom --repo …`.

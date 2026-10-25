# Testy wrogie aplikacji: trzy warstwy

source: Android Debug Bridge (settings, wm, cmd uimode, pm, am), xcrun simctl (ui, status_bar, io), Playwright, axe-core,
GitHub REST API (workflow_dispatch, artifacts)
reviewed: 2026-10-01

| Warunek | Web (`bramka.py wrogie`) | Android (`urzadzenie.py wrogie`) | iOS (`ios_ci.py uruchom`) |
|---|---|---|---|
| mały ekran | iPhone SE 375×667, Android 360×640 | `wm size 720x1280`, `wm density 320` | — |
| duża czcionka | — (`not_run`) | `font_scale 2.0` | `content_size accessibility-extra-extra-extra-large` |
| tryb ciemny | `colorScheme: dark` + axe | `cmd uimode night yes` | `ui appearance dark` |
| brak sieci | `setOffline` + pasek „Brak internetu” | tryb samolotowy, Wi-Fi i dane wyłączone (`not_run`, gdy urządzenie nie odcina sieci albo adb idzie przez Wi-Fi) | — |
| uprawnienia | — | `pm revoke` wszystkich przyznanych w czasie działania, potem `pm grant` (na buildzie) | — |
| „wstecz” | — | `KEYCODE_BACK` ×2 | — |
| śmierć procesu | — | HOME + `am kill` + powrót | — |
| świeża instalacja | — | `pm clear` (na buildzie; tylko emulator albo telefon testowy) | — |
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
  „Zezwolić na debugowanie USB?” na telefonie akceptuje właściciel, nigdy Ty. `jarvo android on`, `ekran` i licencję
  Google robi tylko właściciel w swoim terminalu: z Twojego terminala to odmowa.
- Na komputerze właściciela urządzeniem bywa jego **prywatny telefon**, więc test zostawia go takim, jakim był: przed
  każdą zmianą (czcionka, rozmiar ekranu, tryb ciemny, tryb samolotowy z Wi-Fi i danymi, uprawnienia, tryb demo przy
  zrzutach do sklepów) skrypt zapisuje obecną wartość w dzienniku przywróceń, a po teście przywraca ją i sprawdza,
  także po błędzie. Wartości, której nie odczyta, nie zmienia (`not_run`); offline przez Wi-Fi to `not_run` (tryb
  samolotowy odciąłby adb), a `pm clear` tylko na emulatorze albo telefonie, który właściciel oznaczył jako testowy
  (`jarvo android on --telefon-testowy`). Kod 4 = coś zostało zmienione (np. telefon odłączony w trakcie): powiedz to
  właścicielowi tymi słowami, co jest zmienione; `urzadzenie.py przywroc` przywraca resztę, gdy telefon znów
  odpowiada (robi to też każde następne polecenie i `jarvo android off`), a `wrogie` nie ruszy, dopóki coś zalega.
  Gdy prosisz o telefon do testów, dodaj, że najlepszy jest telefon testowy, nie prywatny.
- Właściciel może patrzeć na ekran i klikać razem z Tobą: na komputerze właściciela okno `jarvo android ekran` (scrcpy
  w osobnym oknie, pobierane przy pierwszym użyciu; otwiera je właściciel), na serwerze z kontenerem link
  `@@PY@@ "@@REPO_DIR@@/scripts/jarvo_link.py" --android` (12 h) albo przycisk 📱 w Twoim panelu w HQ. Na komputerze
  właściciela podglądu w HQ nie ma: `jarvo_link.py --android` kończy się tam kodem 3 z tym komunikatem, więc nie
  podawaj linku, tylko poproś o okno. Proponuj podgląd, gdy prosisz o ręczny test albo pokazujesz przepływ.
- Redroid nie ma usług Google: powiadomień FCM, logowania Google i Map nie sprawdzi (→ emulator przy KVM albo telefon
  właściciela).

## iOS w GitHub Actions (raz, właściciel)
1. Repo na GitHubie dla kodu aplikacji (publiczne = minuty macOS za darmo; prywatne = płatne ponad limit).
2. Token „fine-grained” tylko do tego repo: Contents read/write, Actions read/write → `GITHUB_TOKEN` w sekretach
   `jarvo-mobile`.
3. Agent: `ios_ci.py przygotuj`, `wypchnij --repo …` (gałąź `jarvo/ci`, nigdy main), `uruchom --repo …`.

# Twórca aplikacji: specjalista od aplikacji mobilnych

> Stan: **zaakceptowany 2026-10-01, w budowie.** Właściciel: `jarvo-mobile` („Twórca aplikacji”), we flocie od etapu 1
> (audyt mobilny, „natywna czy PWA”, pokój „Pracownia aplikacji” w HQ); gotowe etapy 2 (szablon, budowa, podgląd w HQ
> i w Expo Go), 4 (pakiet do sklepów z listą 44 punktów) i 6 (aplikacja ze strony, utrzymanie, paczki npm, skille
> zewnętrzne, red team); etap 3 (bramka, telefon testowy, iOS w CI) czeka na test na urządzeniach, etap 5 (wydanie,
> odrzucenia) na pierwszą aplikację na kontach właściciela; postęp w §16.
> Decyzje M1–M12 w §17 przyjęte z rekomendacjami. Wersje, ceny i reguły sklepów sprawdzone 2026-10-01; przed każdym etapem
> sprawdzamy je jeszcze raz, bo sklepy zmieniają je co kilka miesięcy. Rzeczy, których nie udało się potwierdzić
> w źródłach pierwotnych, są oznaczone „(niepotwierdzone)”.

Aplikacja mobilna kosztuje małą firmę w polskiej agencji 15–80 tys. zł ([twojsoftware.pl](https://www.twojsoftware.pl/koszt-aplikacji-mobilnej),
[itlight.eu](https://itlight.eu/blog-koszt-aplikacji-mobilnej)) i miesiące czekania. Twórca aplikacji robi cztery rzeczy, których zwykły
czat z AI nie zrobi: **mówi uczciwie, czy aplikacja jest w ogóle potrzebna**, **pokazuje działający prototyp na telefonie
właściciela w kilka minut**, **sprawdza aplikację na prawdziwym Androidzie i iPhonie (emulator, symulator, telefon)** i
**prowadzi ją przez sklepy** tak, żeby nie odbiła się od recenzji. Ten ostatni punkt to nie dodatek na końcu: zasady
sklepów wchodzą do planu aplikacji pierwszego dnia (§2, krok 1), bo większość odrzuceń wynika z decyzji podjętych
na samym początku (logowanie, płatności, treści użytkowników, „strona w okienku”).

## 1. Sygnatury (co właściciel dostaje)

| Wynik | Co to jest | Jak sprawdzić w sekundę |
|---|---|---|
| **Darmowy audyt mobilny** dowolnej firmy (bez dostępu do kont) | czy firma ma aplikację, jak stara jest ostatnia wersja, ocena i trend, jakość karty w sklepie (tytuł, opis, zrzuty, polska wersja), co widać publicznie z wymogów (polityka prywatności, usuwanie konta, dane przedsiębiorcy DSA), czy działają linki strona → aplikacja (Universal Links, App Links), baner aplikacji na stronie, manifest PWA | raport ✓/✗ z linkami i gotowymi poprawkami; każdy punkt da się kliknąć |
| **„Natywna czy PWA?”** | uczciwa rekomendacja przed jakimkolwiek kodem: rezerwacje, karta lojalnościowa, katalog i wydarzenia zwykle wystarczą jako PWA albo karta w Wallet; natywna ma sens przy narzędziach terenowych (offline, aparat, skaner, podpis), powtarzalnych zamówieniach z powiadomieniami, sieciach punktów | tabela potrzeba → rozwiązanie → koszt; PWA przekazuje do Weba |
| **Prototyp na telefonie w kilka minut** | aplikacja Expo z briefu albo ze strony; link na Telegramie otwiera ją w Expo Go na iPhonie i Androidzie właściciela; podgląd w dashboardzie | otwierasz na telefonie, klikasz |
| **Android w przeglądarce** | gdy serwer to pozwala (§5): wirtualny telefon z Androidem w dashboardzie, na którym agent testuje, a właściciel może sam poklikać | zakładka w dashboardzie, obraz na żywo |
| **Raport z bramki aplikacji** | rubryka 0–100 i testy wrogie na urządzeniu (mały ekran, duża czcionka, tryb ciemny, brak sieci, odmowa uprawnień, klawiatura, przycisk wstecz, wycięcie ekranu), zrzuty z Androida i iPhone'a | werdykt `PASS` / `REVISE` / `BLOCK` ze zrzutami |
| **Pakiet do sklepów** | ikony i ekran startowy, zrzuty w wymaganych wymiarach (z nagłówkami po polsku), opisy w limitach znaków i bajtów, szkic polityki prywatności, odpowiedzi do formularzy prywatności (Apple) i Data safety (Google), konto demo i notatki dla recenzenta po angielsku | `sklep_check.py`: zero błędów przed wysłaniem (§8) |
| **Wydanie** | build Android i iOS, wersja testowa w TestFlight i Google Play, wysłanie do recenzji z wydaniem ręcznym, a po odrzuceniu gotowa odpowiedź z numerem wytycznej | wersja testowa na telefonie właściciela; wysłanie do recenzji zawsze człowiek (A2) |

Przykład audytu z researchu (2026-10-01): na allegro.pl plik `apple-app-site-association` pod adresem strony zwraca
HTML, a kopia w CDN Apple poprawny JSON. Takie rzeczy audyt wyłapuje sam.

## 2. Pełny proces: od pomysłu do sklepu

Ten sam rygor co u Weba (`nowa-strona` → `audyt-strony` → `bramka-jakosci` → `wdrozenie`): każdy krok ma wynik
w pliku i bramkę, której nie da się „przegadać”.

| Krok | Co się dzieje | Wynik | Bramka |
|---|---|---|---|
| 0. Rozmowa | `natywna-czy-pwa`: czy aplikacja ma sens, ile kosztuje (konta, utrzymanie), czego nie da PWA | rekomendacja z kosztami | właściciel wybiera; PWA → Web |
| 1. Plan | brief → `out/PLAN.md`: cel, użytkownik, mapa ekranów, **funkcje natywne** (co daje więcej niż strona, wytyczna 4.2), dane i konta, płatności, treści użytkowników, AI. Z planu powstaje **profil zgodności** `out/zgodnosc.yaml` (§7) | plan + profil zgodności | właściciel akceptuje plan (A2 tylko gdy rusza coś płatnego) |
| 2. Wygląd | brand kit z Weba, makiety kluczowych ekranów jako zrzuty z wersji webowej | zrzuty makiet | właściciel akceptuje kierunek |
| 3. Budowa | szablon JARVO (Expo, §3) z gotowymi elementami zgodności: ekran prywatności, usuwanie konta, kontakt, obsługa braku sieci, polskie opisy uprawnień; dokładane tylko to, co wynika z profilu zgodności | kod w repo aplikacji | `tsc`, lint, `expo-doctor`, testy |
| 4. Pokaż i sprawdź | po każdej zmianie: wersja webowa + zrzuty, Android na urządzeniu, link do Expo Go na telefon właściciela (§5) | zrzuty, link, log | brak czerwonych testów |
| 5. Bramka aplikacji | `bramka-aplikacji`: rubryka 0–100 i testy wrogie na Androidzie i w symulatorze iOS (§6) | `out/jakosc/werdykt-runda-N.json` | ≥ 90 i `PASS`, najwyżej 3 rundy |
| 6. Wersja testowa | build w EAS, TestFlight (testerzy wewnętrzni), ścieżka wewnętrzna Google Play; raport przedpremierowy Google | aplikacja z prawdziwą ikoną na telefonie | A2; właściciel przechodzi ścieżkę z listy |
| 7. Pakiet do sklepów | `pakiet-do-sklepow`: zrzuty (§9), ikony, opisy PL, formularze prywatności, konto demo, notatki dla recenzenta | `out/sklep/` | `sklep_check.py` bez błędów |
| 8. Wysłanie | `wydanie`: lista kontrolna (§8), wysłanie do recenzji z wydaniem ręcznym (Apple), test zamknięty i stopniowe wydanie (Google) | zgłoszenie w obu sklepach | A2, klika człowiek albo agent po zgodzie |
| 9. Odrzucenie | `odrzucenie`: wytyczna → poprawka albo wyjaśnienie → odpowiedź po angielsku; reguła trafia do listy kontrolnej (§10) | szkic odpowiedzi + nowa wersja | A2 |
| 10. Utrzymanie | `utrzymanie-aplikacji`: poprawki przez EAS Update, nowe funkcje przez nową wersję, terminy sklepów (docelowe API, Xcode), podnoszenie SDK | kalendarz terminów | jak krok 8 |

Kroki 0–5 nie wymagają żadnych płatnych kont: właściciel widzi działającą aplikację na swoim telefonie, zanim wyda
złotówkę. Konta Apple (99 $/rok) i Google (25 $ jednorazowo) zakłada dopiero przed krokiem 6.

## 3. Stos (decyzja techniczna)

**Expo (React Native, TypeScript, expo-router).** Dokumentacja React Native zaleca framework, czyli Expo
([reactnative.dev](https://reactnative.dev/docs/environment-setup)). Aktualnie SDK 57 (RN 0.86, React 19.2, Node ≥ 22.13, iOS 16.4+,
Xcode 26.4+, compileSdk 36), nowa architektura zawsze włączona; SDK 58 w becie od 15.09.2026. Ten sam TypeScript i React
co u Weba, licencje MIT, a Expo ma narzędzia pisane pod agentów (`@expo/agent-cli`, oficjalne skille, serwer MCP).

**Sprawdzone w kontenerze floty (2026-10-01):** w obrazie `jarvo-hermes` (Node 26) świeży projekt Expo SDK 57 zakłada się,
instaluje i eksportuje do wersji webowej w ok. 1,5 min. Eksport ma 3,7 MB i renderuje się w Playwright w profilach
iPhone 15 Pro i Pixel 7 bez błędów w konsoli. Uwagi: projekt to ok. 580 MB `node_modules` (wspólna pamięć podręczna npm),
domyślny szablon ma dwa błędy TypeScript w plikach CSS (agent zaczyna od własnego szablonu JARVO).

**Szablon JARVO** (w repo, wersjonowany jak szablony Weba) od pierwszego commita ma to, o co najczęściej odbijają się
małe aplikacje: ekran „Prywatność” z linkiem do polityki, ścieżkę „Usuń konto” (włączaną, gdy jest logowanie), ekran
„Kontakt” z danymi firmy, komunikat o braku sieci zamiast pustego ekranu, granicę błędów zamiast białego ekranu,
`locales/pl.json` z opisami uprawnień, `app.config.ts` z `usesNonExemptEncryption`, `.gitignore` z `.env*`.

Odrzucone jako domyślne: Flutter (drugi język, Dart) i Kotlin Multiplatform (ciężki Gradle; żadne z nich nie korzysta
z wiedzy Weba). **Capacitor** tylko dla ścieżki „moja strona jako aplikacja” i tylko z prawdziwymi funkcjami natywnymi
(§12). **PWA** jako tańsza odpowiedź, gdy wystarcza (wtedy robi to Web).

## 4. Budowanie bez Maca

| Cel | Jak | Koszt i limity |
|---|---|---|
| Podgląd w dashboardzie | `expo export -p web` w kontenerze, serwowane przez podgląd HQ (port 9120) | za darmo, lokalnie |
| Podgląd na telefonie | EAS Update + link do Expo Go (§5) | za darmo (plan Free: 1 tys. aktywnych użytkowników aktualizacji miesięcznie) |
| Android | EAS Build (profil `preview` daje plik APK do instalacji, `production` plik AAB do sklepu) albo lokalnie `expo prebuild` + Gradle (opcjonalny dodatek obrazu, §16) | EAS: 15 buildów/mies. za darmo, kolejka o niskim priorytecie, limit 45 min; lokalnie 3–5 GB dysku i RAM |
| **iOS** | **EAS Build w chmurze** (Mac Expo), podpis kluczem API App Store Connect | 15 buildów/mies. za darmo; po limicie stop do 1. dnia miesiąca; Starter 19 $/mies. |
| iOS, alternatywnie | GitHub Actions na macOS (`xcodebuild`), Codemagic (500 min/mies. za darmo) | zależnie od repo (§5) |
| Wgranie do sklepów | EAS Submit z Linuksa (iOS do TestFlight, Android na ścieżkę wewnętrzną), API App Store Connect i Google Play | za darmo |

Numery buildów prowadzi EAS (`appVersionSource: remote`, `autoIncrement`), więc nie ma odrzucenia za powtórzony numer.
Źródła: [Expo pricing](https://expo.dev/pricing), [APK](https://docs.expo.dev/build-reference/apk/), [local builds](https://docs.expo.dev/build-reference/local-builds/),
[EAS Submit](https://docs.expo.dev/submit/introduction/), [App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi).

## 5. Podgląd i testy: telefony, emulatory, symulatory

Krótka odpowiedź: **Androida da się uruchomić u nas** (w Dockerze na serwerze, gdy pozwala na to jądro, i na
Windows 11), **iPhone'a nie**: symulator iOS działa tylko na macOS. Dla iOS mamy trzy drogi bez własnego Maca:
telefon właściciela przez Expo Go albo TestFlight i wynajęty na minuty Mac w chmurze, sterowany z kontenera.

### 5.1. Android

| Gdzie stoi flota | Urządzenie do testów | Uwagi |
|---|---|---|
| **Serwer Ubuntu z KVM** (`ls /dev/kvm`) | **oficjalny emulator Androida (AVD) w Dockerze**: obraz [docker-android](https://github.com/HQarroum/docker-android) `api-33` (MIT, x86_64 `google_apis`, gotowy na Docker Hub, aktualizowany 05.2026); nowsze API przez jego `API_LEVEL` przy własnym budowaniu | emulator Google z usługami Google, pełna zgodność z Expo; 3–4 GB RAM, 2–4 rdzenie. [budtmo/docker-android](https://github.com/budtmo/docker-android) odrzucony: licencja wymaga zgody na zbieranie danych |
| **Windows 11 (WSL2)** | ten sam emulator w Docker Engine **wewnątrz** dystrybucji WSL (zagnieżdżona wirtualizacja jest domyślnie włączona, [wsl-config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)) | Docker Desktop może nie przekazać kontenerom KVM, dlatego `jarvo android on` sprawdza to próbnym kontenerem zamiast zgadywać; Redroid w WSL wymaga własnego jądra, więc odpada |
| **Serwer Ubuntu bez KVM, VPS 8 GB** | **[Redroid](https://github.com/remote-android/redroid-doc)** (Android 14 w kontenerze, bez wirtualizacji), moduł jądra `binder_linux` z pakietu `linux-modules-extra` | ok. 1,5–2 GB RAM; obraz `14.0.0` (15 i 16 mają znany błąd bindera); kontener `--privileged`; grafika programowa (ok. 15 kl./s); **bez usług Google** |
| VPS bez możliwości ładowania modułów (OpenVZ, LXC) | brak urządzenia lokalnie | telefon właściciela + chmura (§5.4) |

**Włączenie jednym poleceniem:** `jarvo android on` wybiera wariant sam: `/dev/kvm` dostępne dla Dockera → emulator
(profil compose `android-kvm`), inaczej binder w jądrze → Redroid (profil `android`; brakujący moduł `binder_linux`
ładuje, w razie potrzeby doinstalowuje `linux-modules-extra`, i zapisuje go w `modules-load.d`), inaczej wyjaśnia, czemu
się nie da (macOS, WSL bez KVM albo z Docker Desktop, VPS na OpenVZ/LXC) i odsyła do prawdziwego telefonu. Wybór
ręczny: `--emulator` / `--redroid`. O emulatorze decyduje próba, a nie samo `/dev/kvm` na hoście: krótki kontener
z obrazu floty z `--device /dev/kvm` musi zobaczyć urządzenie (Docker Desktop bywa bez niego). Profil trafia do `COMPOSE_PROFILES` w `compose/.env`, więc `jarvo up`, `update`
i `deploy.sh` go pamiętają; `jarvo android off` zwalnia RAM, `jarvo android status` pokazuje jądro, wariant i Androida.
Oba warianty mają w sieci floty tę samą nazwę `jarvo-android:5555`, więc agent i ekran nie wiedzą, który działa.

**Nasza piaskownica:** brak `/dev/kvm` i `CONFIG_ANDROID_BINDER_IPC is not set`, więc żadnego Androida tu nie uruchomimy.
Sam telefon testujemy na serwerze Ubuntu albo komputerze z Windows 11; w piaskownicy sprawdzamy resztę łańcucha
(obraz ekranu, proxy z tokenem, `adb` w obrazie floty, komunikaty `jarvo android`).

**Android w dashboardzie.** [ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy) (MIT, przypięty commit, obraz
`infra/android/Dockerfile.ws-scrcpy`) pokazuje ekran urządzenia w przeglądarce i przyjmuje kliknięcia; działa z emulatorem
i z Redroidem. Sam nie ma żadnej autoryzacji, więc działa tylko w sieci floty, a właściciel wchodzi przez proxy w pluginie
HQ na porcie 9122: link z tokenem (12 h) z przycisku **📱 Ekran telefonu** w panelu Twórcy aplikacji albo od agenta
(`scripts/jarvo_link.py --android`), token zamieniany na ciasteczko `HttpOnly`, każde żądanie i WebSocket sprawdzane
(szczegóły: [HQ.md](HQ.md)). Port adb (5555) nigdy nie jest publikowany na zewnątrz, urządzenie żyje w sieci wewnętrznej floty.

**Automatyzacja.** `adb` w kontenerze agenta (instalacja, zrzuty `screencap`, logi `logcat`), przepływy
[Maestro](https://github.com/mobile-dev-inc/Maestro) 2.11 (Apache-2.0, Java 17, wbudowany serwer MCP; rozmawia tylko z adb na
`localhost:5037`, więc serwer adb działa w kontenerze agenta i łączy się z urządzeniem przez `adb connect`).
Usługi są w `infra/docker-compose.yml` (profile `android` i `android-kvm`); ręcznie wygląda to tak:

```bash
# host, raz (robi to jarvo android on)
sudo apt install -y linux-modules-extra-$(uname -r)
echo 'options binder_linux devices=binder,hwbinder,vndbinder' | sudo tee /etc/modprobe.d/jarvo-android.conf
echo binder_linux | sudo tee /etc/modules-load.d/jarvo-android.conf
sudo modprobe binder_linux devices=binder,hwbinder,vndbinder
# urządzenie tylko w sieci floty, port 5555 nie wychodzi na zewnątrz (compose: usługa android)
docker run -d --name jarvo-android --privileged --network jarvo_jarvo-net --memory 2g --cpus 2 \
  -v /srv/jarvo/data/android:/data redroid/redroid:14.0.0_64only-latest \
  androidboot.use_memfd=1 androidboot.redroid_gpu_mode=guest \
  androidboot.redroid_width=1080 androidboot.redroid_height=2340 androidboot.redroid_dpi=420
# w kontenerze agenta
adb connect jarvo-android:5555
adb -s jarvo-android:5555 install -r app-preview.apk     # albo Expo Go, które Expo CLI instaluje samo
maestro --device jarvo-android:5555 test .maestro/
adb -s jarvo-android:5555 exec-out screencap -p > shot.png
```

Na VPS 8 GB cały zestaw (Redroid, Metro, Maestro, ws-scrcpy) zajmuje szacunkowo 3,5–5 GB, więc urządzenie startuje
na czas testów i gaśnie po nich. Ryzyka Redroida: `--privileged` to praktycznie root na hoście (izolacja sieci, żadnych
portów na zewnątrz), projekt jest słabo utrzymywany (ostatni obraz 09.2025), nowsze jądra z binderem w Ruście
mają zgłoszone awarie (niepotwierdzone dla Ubuntu). Dlatego Redroid to opcja, a nie fundament: przy KVM wybieramy
oficjalny emulator.

**Telefon właściciela z Androidem:** Expo Go ze Sklepu Play działa dziś bez logowania (Expo zapowiada logowanie także
na Androidzie, bez daty), plik APK z buildu `preview` przez link EAS albo kod QR. Bot Telegrama wysyła pliki do 50 MB,
więc większy APK idzie jako link.

### 5.2. iPhone (bez Maca)

**Podgląd na telefonie właściciela:**
1. **EAS Update + Expo Go (za darmo, 1–3 min na zmianę).** Od 3.09.2026 Expo Go na iPhonie otwiera projekt z serwera
   deweloperskiego tylko wtedy, gdy telefon i komputer są zalogowane na to samo konto, a od 12.05.2026 opublikowane
   aktualizacje otwiera tylko właściciel projektu albo członek jego organizacji ([logowanie](https://expo.dev/changelog/expo-go-57-login),
   [ładowanie aktualizacji](https://expo.dev/changelog/expo-go-loading-changes-may-2026)). Dlatego: właściciel raz zakłada darmowe konto
   Expo i organizację i loguje się w Expo Go; agent publikuje `eas update --channel podglad` **tokenem robota** tej
   organizacji i wysyła link. Link `exp://` z Telegrama może nie być klikalny, więc idzie link https do strony
   w dashboardzie, która przekierowuje do aplikacji. Serwera deweloperskiego na iPhonie **nie używamy**: wymagałby
   osobistego tokenu właściciela z pełnym dostępem do jego konta.
2. **TestFlight (99 $/rok, konto Apple Developer).** Testerzy wewnętrzni (do 100 osób z zespołu) bez recenzji Apple, wersja
   ważna 90 dni ([TestFlight](https://developer.apple.com/testflight/)). Właściciel klika „Aktualizuj”, a aplikacja ma prawdziwą
   ikonę i wszystkie moduły natywne, także te spoza Expo Go. Runda builda to 30–60 min; zmiany w samym JS potem przez
   EAS Update. To podstawowa droga od kroku 6 (§2).
3. Instalacja ad hoc (rejestracja UDID, profil, tryb dewelopera) jest za trudna dla właściciela bez technicznego
   zaplecza; nie proponujemy jej.

**Testy automatyczne i zrzuty (agent z Linuksa):**

| Opcja | Jak | Koszt (2026-10-01) |
|---|---|---|
| **GitHub Actions, `macos-26`** (domyślnie) | workflow w repo aplikacji właściciela: symulator iPhone 17 Pro Max i iPad Pro 13″ (Xcode 26.6), aplikacja z `eas build:download` albo w Expo Go, przepływy Maestro, zrzuty i logi jako artefakty; agent uruchamia go przez API (`workflow_dispatch` zwraca numer przebiegu) i pobiera wyniki | publiczne repo za darmo; prywatne: minuty macOS płatne ponad limit planu ([cennik](https://docs.github.com/en/billing/concepts/product-billing/github-actions)) |
| **Codemagic** | to samo przez REST API Codemagic, Mac M2 | 500 min/mies. za darmo dla kont osobistych, potem 0,095 $/min ([cennik](https://codemagic.io/pricing/)); lokalny symulator z Maestro (niepotwierdzone w ich dokumentacji) |
| **EAS Simulator** | `eas simulator` prosto z Linuksa, sterowanie przez `agent-device`, podgląd w przeglądarce ([blog](https://expo.dev/blog/build-ios-apps-on-windows-with-cloud-simulators)) | wczesny dostęp z listy oczekujących, cena nieznana; zapisać się teraz, to najlepiej pasuje do naszego przypadku |
| **EAS Workflows (job Maestro)** | `eas workflow:run` | nie ma go w planie Free: Starter 19 $/mies. + opłaty za job i minuty macOS |
| **Appetize** | wgrany `.app` z symulatora, sterowanie przez `@appetize/cli` (beta), da się osadzić w dashboardzie | 30 min/mies. za darmo, Starter 59 $ za 500 min |

Szacunkowo 20 przebiegów miesięcznie: Expo 0 $, CI 0 $ (repo publiczne albo darmowe minuty Codemagic), w innym razie
15–30 $ w GitHubie; Apple ok. 8 $/mies.

**Ryzyka iOS:** Expo Go w App Store bywa wstrzymywane przez recenzję Apple (w maju 2026 utknęło na SDK 54 na miesiące,
[changelog](https://expo.dev/changelog/expo-go-and-app-store-may-2026)), więc przed nowym projektem agent sprawdza, który SDK
obsługuje Expo Go w sklepie, a w razie rozjazdu przechodzi na TestFlight albo prywatne Expo Go (`eas go`). Symulator to
nie telefon: powiadomienia, aparat, Face ID i wydajność sprawdza TestFlight na iPhonie właściciela. Mac w chmurze bywa
w kolejce (licencja Apple ogranicza wirtualizację macOS).

### 5.3. Co testujemy gdzie i kiedy

| Moment | Wersja webowa | Android (urządzenie u nas) | iOS (Mac w chmurze) | Telefon właściciela |
|---|---|---|---|---|
| każda zmiana | zrzuty, axe, konsola | instalacja, przepływ główny, logi | — | link do Expo Go |
| bramka aplikacji (§6) | — | pełne testy wrogie | pełne testy wrogie i zrzuty | — |
| wersja testowa (§2, krok 6) | — | build `preview` | build z EAS w symulatorze | TestFlight i ścieżka wewnętrzna: lista do przejścia |
| przed wysłaniem | — | raport przedpremierowy Google (§5.4) | zrzuty do sklepu (§9) | ostateczne „przechodzę ścieżkę” |

**Uczciwie:** wersja webowa to nie aplikacja natywna (część komponentów React Native jest w przeglądarce tylko
zaślepiona). Raport oznacza każdą funkcję natywną (aparat, powiadomienia, logowanie Google, mapy, płatności) jako
„niesprawdzone na urządzeniu”, dopóki nie przejdzie testu na telefonie właściciela; Redroid nie ma usług Google, więc
powiadomień FCM, logowania Google i Map nie sprawdzi.

### 5.4. Chmura i darmowe testy w sklepach

- **Raport przedpremierowy Google Play:** po wgraniu pliku AAB robot Google przez kilka minut używa aplikacji na
  prawdziwych telefonach i tabletach i zwykle w ciągu godziny pokazuje awarie, ANR, problemy dostępności (etykiety, cele
  dotyku, kontrast) i zrzuty z wielu urządzeń, za darmo ([pomoc](https://support.google.com/googleplay/android-developer/answer/9842757)).
  Agent czyta go przed każdym przejściem na wyższą ścieżkę. Dane logowania wpisuje tylko w standardowe pola Androida
  (czy obejmuje to pola React Native: niepotwierdzone), więc konto demo testujemy też sami.
- **Kontrole przed recenzją Google** (ok. 15 min po zmianie) blokują publikację przy krytycznych problemach i brakujących deklaracjach.
- **Firebase Test Lab:** 10 testów wirtualnych i 5 fizycznych dziennie za darmo, ale usługa kończy działanie 30.09.2027
  ([limity](https://firebase.google.com/docs/test-lab/usage-quotas-pricing)); używamy tylko doraźnie.
- **AWS Device Farm:** 1000 min próbnych, potem 0,17 $/min ([cennik](https://aws.amazon.com/device-farm/pricing/)), prawdziwe iPhone'y
  przy kamieniach milowych.

## 6. Bramka aplikacji (`bramka-aplikacji`)

Odpowiednik `bramka-jakosci` Weba. `tsc` i lint mówią, czy aplikacja jest **poprawna**; bramka mówi, czy jest **dobra**
i czy wytrzyma prawdziwego użytkownika i recenzenta. Technicznie czysta, ale „szablonowa” aplikacja nie przechodzi:
wygląd jak z gotowca to nie tylko kwestia gustu, to też ryzyko odrzucenia za spam (4.3).

**Rubryka 0–100, dziesięć osi** (każda: zaliczona albo różnica z dowodem na zrzucie i najmniejszą zmianą, która ją naprawi):
1. **Pierwsze 30 sekund:** wartość widać bez zakładania konta, brak ściany próśb o zgody.
2. **Nawigacja wg platformy:** dolne zakładki, gest i przycisk wstecz na Androidzie, przewidywalne „wstecz” w formularzach.
3. **Kciuk i cele dotyku:** co najmniej 44 pt (iOS) i 48 dp (Android), główne akcje w zasięgu kciuka.
4. **Tekst:** czytelny przy największej systemowej czcionce, polskie znaki i długie słowa bez ucinania.
5. **Stany:** ładowanie, pusto, błąd, brak sieci; nigdy pusty biały ekran.
6. **Formularze i klawiatura:** właściwy typ klawiatury, autouzupełnianie, pole nie chowa się pod klawiaturą.
7. **Tryb ciemny i kontrast:** oba motywy dopracowane, kontrast WCAG AA.
8. **Ruch i płynność:** brak przycięć, szacunek dla „ogranicz ruch”.
9. **Uprawnienia i zaufanie:** prośba w momencie użycia, z wyjaśnieniem; odmowa nie blokuje reszty aplikacji.
10. **Marka i dopracowanie:** ikona, ekran startowy, spójność z brand kitem, coś własnego zamiast domyślnych komponentów.

**Testy wrogie** (przepływy Maestro + ustawienia urządzenia przez `adb` i `xcrun simctl`, wynik w `out/jakosc/wrogie/mobile.json`):

| Test | Android | iOS (symulator) |
|---|---|---|
| mały ekran | `wm size 720x1280`, `wm density 320` | iPhone SE |
| największa czcionka | `settings put system font_scale 2.0` | `simctl ui … content_size accessibility-extra-extra-extra-large` |
| tryb ciemny | `cmd uimode night yes` | `simctl ui … appearance dark` |
| brak sieci i wolna sieć | `cmd connectivity airplane-mode enable`, `svc wifi disable` | profil sieci w CI (niepotwierdzone na `macos-26`) |
| odmowa uprawnień | `pm revoke <pakiet> <uprawnienie>`, Maestro `permissions: deny` | `simctl privacy … revoke` |
| klawiatura zasłania pole | Maestro: fokus na ostatnim polu, zrzut | to samo |
| systemowe „wstecz” | `input keyevent KEYCODE_BACK` w połowie formularza | gest przesunięcia od krawędzi |
| wycięcie ekranu i bezpieczne obszary | urządzenie z wycięciem | iPhone 17 Pro Max (Dynamic Island) |
| powrót z tła i śmierć procesu | `input keyevent HOME`, `am kill <pakiet>`, powrót | aplikacja w tle i powrót |
| świeża instalacja | `pm clear <pakiet>` | `simctl uninstall` i instalacja |
| czytnik ekranu | etykiety z hierarchii Maestro, axe na wersji webowej | to samo |

**Bezpieczeństwo:** wszystko, co trafia do paczki JS, jest publiczne (także zmienne `EXPO_PUBLIC_*`), więc skan paczki
szuka kluczy, adresów `localhost`, adresów IP sieci lokalnej, ngrok i serwerów testowych; do tego ruch bez TLS,
aplikacja w trybie debug i skan nowych paczek npm tym samym `security_check.py` co u Weba. Aplikacja z backendem
przechodzi cały skill `bezpieczenstwo-aplikacji` Weba.

**Werdykt** `PASS` / `REVISE` / `BLOCK` jak u Weba: poniżej 90 runda poprawek (najwyżej 3), potem oddanie z listą
niezamkniętych różnic. **`BLOCK` zawsze** przy awarii aplikacji, krytycznym problemie bezpieczeństwa albo błędzie
automatycznym z `sklep_check.py` (§8).

## 7. Sklepy: dlaczego odrzucają i jak temu zapobiegamy

**Skala:** w 2025 Apple sprawdził 9,1 mln zgłoszeń i odrzucił 2,09 mln; najwięcej w grupie „wydajność” (2.x, 1,35 mln),
dalej prawo, design, biznes i bezpieczeństwo ([raport przejrzystości](https://www.apple.com/legal/app-store/transparency/2025/)).
Apple podaje, że ponad 40% nierozwiązanych problemów dotyczy kompletności (2.1), a 90% zgłoszeń sprawdza w 24 godziny
([App Review](https://developer.apple.com/distribute/app-review/)); prasa w 2026 opisuje wielotygodniowe kolejki przez zalew aplikacji
pisanych z AI (niepotwierdzone przez Apple). Google sprawdza „do 7 dni lub dłużej”.

**Profil zgodności.** Z planu (§2, krok 1) agent wypełnia `out/zgodnosc.yaml`: logowanie (jakie), płatności (towary
fizyczne, usługi, treści cyfrowe), treści użytkowników, AI, lokalizacja, kontakty, aparat, powiadomienia, śledzenie,
dzieci jako odbiorcy, tablet, branża regulowana. Profil włącza elementy szablonu (np. logowanie → usuwanie konta)
i decyduje, które punkty listy kontrolnej (§8) obowiązują.

**App Store** ([wytyczne](https://developer.apple.com/app-store/review/guidelines/), ostatnia zmiana 8.06.2026):

| Wytyczna | Za co odrzucają | Jak zapobiegamy |
|---|---|---|
| **2.1** kompletność | awarie, tekst zastępczy, martwe linki, wyłączony backend, brak konta demo | bramka (§6), skan tekstów i linków, logowanie kontem demo przed wysłaniem |
| **2.3** metadane | zrzuty bez aplikacji w użyciu (sam ekran startowy albo logowanie), nazwa ponad 30 znaków, nazwy innych aplikacji i platform („Android”), ogólnikowe „Co nowego” i notatki dla recenzenta (2.3.1(a): „ogólne opisy będą odrzucane”) | potok zrzutów (§9), lint metadanych, notatki z konkretną ścieżką testu |
| **4.2, 4.2.2** minimalna funkcjonalność | przepakowana strona, broszura, zbiór linków | `natywna-czy-pwa`, funkcje natywne w planie, mało ekranów WebView |
| **4.2.6, 4.3** szablony i spam | aplikacje z generatora wysłane przez usługę w imieniu klienta, wiele kopii tej samej aplikacji | **publikuje właściciel ze swojego konta**, własny wygląd (oś 10 rubryki), porównanie podobieństwa z innymi aplikacjami floty |
| **4.1(c)** podróbki | cudza ikona, marka, nazwa | sprawdzenie nazw i znaków w metadanych |
| **4.8** logowanie | logowanie przez Google lub Facebooka bez równorzędnej opcji chroniącej prywatność | Zaloguj się przez Apple dodawane automatycznie |
| **5.1.1** dane | brak polityki prywatności w aplikacji i w sklepie, niejasne opisy uprawnień, zbędne dane, wymuszone logowanie, brak usuwania konta w aplikacji (dezaktywacja się nie liczy) | szablon (§3), polskie opisy uprawnień z przykładem użycia, „Usuń konto” w aplikacji |
| **5.1.2** użycie danych | dane wysyłane do zewnętrznego AI bez zgody, śledzenie bez ATT, aplikacja nie działa bez zgód | ekran zgody przed pierwszym wywołaniem AI, ATT tylko gdy jest śledzenie |
| **1.2** treści użytkowników | brak filtra, zgłaszania, blokowania i kontaktu (od 02.2026 także anonimowe czaty) | moduł zgłaszania i blokowania w szablonie |
| **3.1.1, 3.1.3(e)** płatności | treści cyfrowe poza zakupami w aplikacji; zakupy w aplikacji przy towarach fizycznych | profil zgodności decyduje: cyfrowe → zakupy w aplikacji, fizyczne i usługi → Stripe, P24, PayU, BLIK |
| **2.5.2** pobierany kod | aktualizacja „przez powietrze” zmieniająca funkcje aplikacji | EAS Update tylko na poprawki; nowe funkcje w nowej wersji z opisem w notatkach |
| **2.5.4, 2.5.5** | tryby pracy w tle bez potrzeby, aplikacja nie działa w sieci tylko z IPv6 | lista trybów porównana z kodem; backend z IPv6 |
| **5.6.2** tożsamość | „zgłoszone przez niewłaściwy podmiot” w branżach regulowanych (finanse, zdrowie) | konto firmy, dokumenty w załączniku |
| wymogi stałe | Xcode 26 (od 28.04.2026), dane przedsiębiorcy DSA w UE, nowy kwestionariusz kategorii wiekowej (od 31.01.2026) | build w EAS na aktualnym Xcode, lista dla właściciela (§8, A i G) |

**Google Play** ([pomoc](https://support.google.com/googleplay/android-developer/)):

| Zasada | Za co blokują | Jak zapobiegamy |
|---|---|---|
| [niedziałająca aplikacja](https://support.google.com/googleplay/android-developer/answer/9898783) | awarie, brak ładowania, brak reakcji | bramka, raport przedpremierowy |
| [ograniczona funkcjonalność i spam](https://support.google.com/googleplay/android-developer/answer/9899034) | statyczna aplikacja, WebView cudzej strony, wiele podobnych aplikacji | jak 4.2 i 4.3 u Apple |
| [metadane](https://support.google.com/googleplay/android-developer/answer/9898842) | tytuł ponad 30 znaków, emoji, WIELKIE LITERY, „#1”, „najlepsza”, „darmowa”, promocje, „Nowość”, upychanie słów, anonimowe opinie | lint metadanych z polską listą zakazanych słów |
| [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469) | formularz niezgodny z tym, co zbierają aplikacja **i jej biblioteki** | szkic formularza z inwentarza bibliotek, potwierdza człowiek |
| [usuwanie konta](https://support.google.com/googleplay/android-developer/answer/13327111) | brak ścieżki w aplikacji **i** działającego linku w sieci | szablon + strona na witrynie (Web) |
| [uprawnienia wrażliwe](https://support.google.com/googleplay/android-developer/answer/16558241) | lokalizacja w tle, `READ_MEDIA_*`, dostęp do wszystkich plików, `QUERY_ALL_PACKAGES`, SMS, kontakty (od 04.2026 selektor kontaktów) | usuwanie zbędnych uprawnień (`android.blockedPermissions`), selektory systemowe zamiast uprawnień |
| [docelowe API](https://developer.android.com/google/play/requirements/target-sdk) | nowe aplikacje i aktualizacje od 31.08.2026 muszą celować w API 36 (przedłużenie do 1.11.2026) | odczyt z pliku AAB |
| [strony pamięci 16 KB](https://developer.android.com/guide/practices/page-sizes) | biblioteki natywne bez wyrównania 16 KB; od 1.02.2027 bez tego nie wyjdzie żadna aktualizacja | `zipalign -c -P 16` na każdej bibliotece `.so` |
| [nadużycia urządzenia](https://support.google.com/googleplay/android-developer/answer/9888379) | pobieranie kodu wykonywalnego (JS interpretowany jest wyjątkiem) | jak 2.5.2 |
| [treści użytkowników](https://support.google.com/googleplay/android-developer/answer/9876937) i [treści z AI](https://support.google.com/googleplay/android-developer/answer/13985936) | brak regulaminu, moderacji, zgłaszania, blokowania; brak zgłaszania obraźliwych odpowiedzi AI | moduł zgłaszania w szablonie |
| [dane logowania dla recenzji](https://support.google.com/googleplay/android-developer/answer/15748846) | konto z kodem SMS albo 2FA, nieaktualne hasło | konto demo bez 2FA, sprawdzane skryptem |
| [nowe konto osobiste](https://support.google.com/googleplay/android-developer/answer/14151465) | produkcja dopiero po teście zamkniętym: ≥ 12 testerów przez 14 dni z rzędu | konto organizacji (numer D-U-N-S) albo zaplanowany test z klientami właściciela |

**Kto publikuje:** zawsze właściciel ze **swojego** konta deweloperskiego (Apple: konto organizacji albo osoby, Google:
organizacji albo osobiste), agent co najwyżej jako członek zespołu. Wytyczna 4.2.6 zabrania usługom generującym aplikacje
wysyłania ich w imieniu klientów, a jedna aplikacja pod wieloma identyfikatorami to 4.3. Uwaga na domyślne ustawienia
narzędzi: fastlane `supply` domyślnie publikuje na produkcję, więc skrypty wymuszają ścieżkę wewnętrzną i szkic,
a w Apple „wydanie ręczne”. Uwaga dla jednoosobowej działalności: status przedsiębiorcy DSA w UE pokazuje na karcie
aplikacji adres, telefon i e-mail; przy firmie zarejestrowanej w domu warto mieć adres do doręczeń.

## 8. Lista kontrolna przed wysłaniem (`sklep_check.py`)

Skrypt czyta to, co sklepy faktycznie dostaną:
- **konfigurację po rozwiązaniu wtyczek**: `npx expo config --type introspect` daje Info.plist i uprawnienia Androida
  bez prebuilda. `--type public` daje to, co ustawiła sama aplikacja; usuwa `ios.config`, więc szyfrowanie czytamy
  z introspekcji;
- **zbudowane pliki**, gdy są (`--aab`, `--ipa`, `--apk` albo najnowsze w `out/build/`):
  - AAB: manifest bez Javy i bundletool, dekodowany z protobuf aapt2 (sprawdzone na prawdziwym AAB);
  - biblioteki `.so`: wyrównanie z nagłówków ELF (`p_align` segmentów `PT_LOAD`; w APK także przesunięcie w zipie);
  - IPA: `Info.plist` i `PrivacyInfo.xcprivacy`;
  - paczkę JS;
- **metadane**: `store.config.json` (EAS Metadata, App Store) i karta Google w układzie fastlane supply
  (`out/sklep/google/pl-PL/`);
- **obrazy**: nagłówek PNG, gdzie typ koloru 4 lub 6 albo blok `tRNS` oznacza kanał alfa. Teksty na zrzutach iOS
  czyta OCR (tesseract);
- **adresy firmy**: publiczne HTTPS, 2xx po przekierowaniach.

Wynik to `out/sklep/check.json` i `CHECK.md`: przy każdym punkcie ✓ / ✗ / ? / ☐ z dowodem, poprawką i numerem
wytycznej. Ludzie potwierdzają punkty przez `sklep_check.py potwierdz` (`out/sklep/potwierdzenia.json`).
Wysłanie jest możliwe dopiero, gdy wszystkie 44 punkty są ✓.

Tryby: **auto** = skrypt rozstrzyga sam, każdy błąd blokuje wysłanie; **pół** = skrypt zbiera dowody, agent ocenia,
człowiek potwierdza; **ręcznie** = punkt listy dla właściciela w konsoli sklepu (A2).

Gotowe narzędzia pokrywają mało: `expo-doctor` sprawdza zależności i konfigurację, ale żadnych zasad sklepów,
a `eas metadata:lint` (tylko App Store, w becie) ma dwie reguły i liczy słowa kluczowe w znakach, choć Apple liczy
100 **bajtów** (polska litera z ogonkiem to 2 bajty). Dlatego własny skrypt.

| # | Sprawdzenie | Tryb | Podstawa |
|---|---|---|---|
| **A** | **Konto i tożsamość** | | |
| 1 | wysyła właściciel ze swoich kont Apple i Google; agent jako członek zespołu; nigdy jedno konto dla wielu firm | ręcznie | Apple 4.2.6, 5.6.2 |
| 2 | status przedsiębiorcy DSA zweryfikowany w App Store Connect | ręcznie | [wymagania](https://developer.apple.com/news/upcoming-requirements/) |
| 3 | branża regulowana (zdrowie, finanse) → wysyła podmiot prawny, dokumenty w załączniku | pół | Apple 5.6.2 |
| **B** | **Build i konfiguracja** | | |
| 4 | `ios.bundleIdentifier` i `android.package` ustawione, w odwrotnej notacji domeny, nie `com.example` (identyfikatora nie da się zmienić po pierwszym wgraniu) | auto | App Store Connect |
| 5 | wersja wyższa niż w App Store (iTunes API), numery buildów rosną same (EAS: `appVersionSource: remote`, `autoIncrement`) | auto | EAS |
| 6 | Xcode ≥ 26, iOS od 16.4; `targetSdkVersion` w AAB ≥ 36 | auto | Apple, Google (docelowe API) |
| 7 | biblioteki `.so` 64-bitowe wyrównane do 16 KB | auto | Google (16 KB) |
| 8 | build nie w trybie debug; bez ruchu bez TLS i `NSAllowsArbitraryLoads`; w paczce JS brak `localhost`, adresów sieci lokalnej, ngrok, serwerów testowych | auto | Apple 2.1 |
| 9 | ustawione `ios.config.usesNonExemptEncryption` (eksport szyfrowania) | auto | konfiguracja Expo |
| 10 | `expo-doctor` i `expo install --check` bez błędów | auto | Expo |
| **C** | **Uprawnienia i prywatność** | | |
| 11 | każdy użyty moduł z uprawnieniem (aparat, lokalizacja, zdjęcia, kontakty, powiadomienia, kalendarz, mikrofon, biometria, śledzenie) ma opis w Info.plist | auto | Apple 5.1.1(ii) |
| 12 | opisy uprawnień po polsku (Info.plist z regionem `pl` albo `locales/pl.json`), ≥ 40 znaków, z nazwą funkcji, żaden z czarnej listy ogólników („potrzebuje dostępu”, domyślne teksty wtyczek) | auto | Apple 5.1.1, App Review |
| 13 | brak zbędnych uprawnień: Info.plist i manifest porównane z importami w kodzie | auto | Apple 5.1.1(iii), Google |
| 14 | uprawnienia wymagające deklaracji w Google (lokalizacja w tle, `READ_MEDIA_*`, `READ_CONTACTS`, `QUERY_ALL_PACKAGES`, dokładne alarmy, usługi pierwszoplanowe, `AD_ID`) oznaczone do formularza | pół | Google (uprawnienia) |
| 15 | `UIBackgroundModes` tylko z trybami używanymi w kodzie | auto | Apple 2.5.4 |
| 16 | manifest prywatności: powód dla każdego API z listy Apple; biblioteki z listy (Firebase, logowanie Google, Facebook, OneSignal) mają własne manifesty | auto | [prywatność w Expo](https://docs.expo.dev/guides/apple-privacy/), [SDK](https://developer.apple.com/support/third-party-SDK-requirements/) |
| 17 | szkic etykiety prywatności Apple i formularza Data safety z inwentarza bibliotek; ATT, jeśli jest śledzenie | pół | Apple 5.1.2, Google (Data safety) |
| 18 | wywołania zewnętrznego AI → informacja i zgoda w aplikacji, zgłaszanie odpowiedzi AI | pół | Apple 5.1.2(i), Google (treści z AI) |
| 19 | żadna prośba o uprawnienie nie blokuje pierwszego ekranu z treścią | pół | Apple 5.1.2(i) |
| **D** | **Konta i logowanie** | | |
| 20 | polityka prywatności: adres zwraca 200, zawiera nazwę firmy, jest po polsku i jest podlinkowana w aplikacji | auto | Apple 5.1.1(i), Google |
| 21 | strona wsparcia zwraca 200 i pokazuje e-mail albo telefon | auto | App Review |
| 22 | jest zakładanie konta → „Usuń konto” w aplikacji i działający adres usuwania w sieci | auto | Apple 5.1.1(v), Google |
| 23 | jest logowanie Google lub Facebook → na iOS widać Zaloguj się przez Apple | auto | Apple 4.8 |
| 24 | katalog i informacje dostępne bez logowania | pół | Apple 5.1.1(v) |
| 25 | konto demo w `store.config.json` (hasło w `JARVO_DEMO_HASLO`, nie w repo) i w Google: bez kodu SMS i 2FA; skrypt loguje się nim do backendu, gdy aplikacja podaje `backend.demo_login` | auto | Apple 2.1, Google (logowanie) |
| **E** | **Treść i funkcje** | | |
| 26 | brak lorem ipsum, TODO, FIXME, „Wkrótce”, example.com i pustych ekranów | auto | Apple 2.1 |
| 27 | wszystkie linki w aplikacji i metadanych działają; `apple-app-site-association` i `assetlinks.json` pasują do aplikacji | auto | Apple 2.1 |
| 28 | to nie okno na stronę: mały udział ekranów WebView, są funkcje natywne (powiadomienia, rezerwacja, offline) | pół | Apple 4.2, 4.2.2, Google (spam) |
| 29 | podobieństwo do innych aplikacji zrobionych przez flotę poniżej progu | pół | Apple 4.3, Google (spam) |
| 30 | odblokowanie treści cyfrowych tylko przez zakupy w aplikacji; Stripe, P24, PayU, BLIK tylko za towary fizyczne i usługi | auto | Apple 3.1.1, 3.1.3(e) |
| 31 | treści użytkowników → zgłaszanie, blokowanie, regulamin i kontakt | auto | Apple 1.2, Google (UGC) |
| 32 | `expo-updates` z polityką `fingerprint`; aktualizacje bez recenzji tylko z poprawkami | pół | Apple 2.5.2, Google (nadużycia) |
| 33 | przejście na prawdziwym iPhonie (i iPadzie, gdy `supportsTablet`) i Androidzie, IPv6, włączony backend; przeczytany raport przedpremierowy i wyniki TestFlight | ręcznie | Apple 2.1, 2.5.5 |
| **F** | **Grafiki** | | |
| 34 | ikona iOS 1024×1024 bez kanału alfa; ikona adaptacyjna Androida (pierwszy plan, tło, monochromatyczna); ekran startowy | auto | [ikony Expo](https://docs.expo.dev/develop/user-interface/app-icons/) |
| 35 | ikona Google 512×512 PNG ≤ 1 MB; grafika promocyjna 1024×500 bez alfy | auto | [grafiki Google](https://support.google.com/googleplay/android-developer/answer/9866151) |
| 36 | zrzuty: iPhone 6,9″ (1320×2868) albo 6,5″; iPad 13″ (2064×2752), gdy jest tablet; 1–10 w zestawie; Google 2–8 na typ urządzenia, 320–3840 px; wszystkie bez alfy | auto | [zrzuty Apple](https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications), grafiki Google |
| 37 | zrzuty pokazują aplikację w użyciu (porównanie z ekranem startowym i logowania), na zrzutach iOS żadnego „Android” ani obcych platform | pół | Apple 2.3.3, 2.3.10 |
| 38 | grafiki do sklepu zrobione z pomocą AI oznaczone w Play Console | ręcznie | [Google](https://support.google.com/googleplay/android-developer/answer/17262077) |
| **G** | **Metadane** | | |
| 39 | limity: nazwa ≤ 30, podtytuł ≤ 30, tekst promocyjny ≤ 170, opis ≤ 4000 znaków; Google: krótki opis ≤ 80 | auto | Apple, Google (metadane) |
| 40 | słowa kluczowe ≤ 100 bajtów UTF-8, każde > 2 znaki, bez nazwy aplikacji i firmy, bez nazw konkurencji (Booksy, Wolt, Pyszne.pl…) | auto | Apple 2.3.7 |
| 41 | skan zakazanych słów we wszystkich metadanych: Android/Google Play (na karcie iOS), „beta”, „#1”, „najlepsza”, „darmowa”, rabaty, emoji, WIELKIE LITERY | auto | Apple 2.3.10, Google (metadane) |
| 42 | karta i nazwa aplikacji w wersji pl-PL | auto | — |
| 43 | kwestionariusz wieku Apple (nowy od 31.01.2026); Google: klasyfikacja IARC, grupa docelowa, reklamy, funkcje finansowe, Data safety | ręcznie | Apple, Google (kontrole przed recenzją) |
| 44 | notatki dla recenzenta po angielsku (≤ 4000 bajtów, kroki ścieżki testu; skrypt sprawdza język i kroki, człowiek treść): funkcje, ścieżka testu, uzasadnienie płatności, informacja o aktualizacjach bez recenzji | pół | Apple 2.3.1(a) |

Lista nie jest zamknięta: każde odrzucenie dopisuje punkt (§10).

## 9. Zrzuty do sklepów

Najczęstszy błąd małych aplikacji to zrzuty z samym logowaniem albo ekranem startowym (2.3.3). Potok:
1. **Scenariusz** w `out/sklep/zrzuty.yaml` (szkic robi `pakiet.py szkic` z tras aplikacji): 2–8 kadrów (Google
   wymaga co najmniej 2), każdy to jedna korzyść dla klienta z nagłówkiem po polsku (copy od Studia), kolejność jak
   w karcie.
2. **Dane demo:** realistyczna polska treść z seeda (bez danych prawdziwych klientów), te same na obu platformach.
3. **Przechwycenie z prawdziwej aplikacji** (`pakiet.py zrzuty --zrodlo android|ios`; wersja produkcyjna, nie Expo Go,
   bo jego menu widać na ekranie). Źródło `web` (eksport z podglądu, Playwright w profilach iPhone 17 Pro Max, Pixel,
   iPad 13″, z dorysowanym paskiem 9:41) służy tylko do szkicu karty; lista kontrolna oznacza je „?”:
   - iOS: symulator iPhone 17 Pro Max (6,9″, 1320×2868) i iPad Pro 13″ (2064×2752, gdy jest tablet) w GitHub Actions
     albo Codemagic; czysty pasek stanu `xcrun simctl status_bar booted override --time 9:41 --batteryState charged
     --batteryLevel 100 --cellularBars 4`; artefakt `ios_ci.py` (`jasny-<trasa>.png`).
   - Android: telefon testowy floty (emulator albo Redroid, 1080×2340) albo telefon właściciela przez adb, pasek stanu
     w trybie demo (`settings put global sysui_demo_allowed 1` i polecenia `com.android.systemui.demo`: 9:41, pełna
     bateria, bez powiadomień), trasy otwierane przez `schemat://trasa`.
4. **Kompozycja** (`kadry.cjs`): HTML z `pakiet.py` (gradient z koloru marki, nagłówek bez polskich „sierotek”
   i z równym łamaniem, ekran w ramce w całości, bez uciętego paska zakładek) renderowany przez Playwright
   w dokładnych wymiarach i zapisany jako PNG bez kanału alfa (sharp `removeAlpha`). Wymiary:
   - iPhone 6,9″: 1320×2868;
   - iPad 13″: 2064×2752;
   - Google telefon: 1080×1920.

   Do tego (`pakiet.py grafiki`) grafika promocyjna Google 1024×500 i ikona 512×512.
5. **Kontrola:** punkty 34–38 listy (§8): wymiary, alfa, liczba, „aplikacja w użyciu”, obce platformy.
6. **Film podglądowy** (opcjonalnie): Wideograf skleja 15–30 s z nagrania przepływu (skill `demo-strony`), Apple wymaga
   nagrania z aplikacji, bez kadrów spoza niej.

## 10. Wysłanie, recenzja, odrzucenia

**Apple:** TestFlight dla testerów wewnętrznych → opcjonalnie test zewnętrzny z publicznym linkiem (do 10 tys. osób;
pierwszy build tej wersji przechodzi recenzję beta, najwyżej 6 buildów na dobę do recenzji) → wysłanie z **wydaniem
ręcznym**, kontem demo, notatkami po angielsku (do 4000 bajtów) i nagraniem ekranu jako załącznikiem. Przy trudnej
sprawie Apple oferuje 30-minutowe konsultacje z recenzentami.

**Google:** ścieżka wewnętrzna → raport przedpremierowy (ok. godziny) → test zamknięty (dla nowego konta osobistego
obowiązkowo 12 testerów przez 14 dni) → produkcja ze **stopniowym wydaniem** (np. 20% użytkowników) i obserwacją awarii.

**Jak to robi `wydanie.py`:**
1. `plan`: bramki i jednorazowe przygotowanie kont właściciela.
2. `build`: EAS Build production, `--no-wait`.
3. `status`: AAB i IPA do `out/build/` i lista kontrolna na buildach.
4. `testy`: `eas submit` do TestFlight i na ścieżkę wewnętrzną Google jako szkic.
5. `karta`: `eas metadata:push` ze `store.config.json`; hasło demo z `JARVO_DEMO_HASLO` jest w pliku tylko na czas
   wysyłki. Kartę Google właściciel wkleja z `GOOGLE.md`.
6. `recenzja`: lista kliknięć właściciela.

Kroki 2, 4 i 5 to A2. Mają trzy zabezpieczenia:
- bramki: `PASS` bramki, lista kontrolna bez ✗ auto (przed testami na pobranych buildach), zero `JARVO-TODO`,
  projekt EAS i token robota;
- dosłowne słowa zgody właściciela w `--zgoda`, zapisane w `out/wydanie/zgody.json`;
- zatwierdzenie polecenia przez Hermesa (`approvals.smart_policy`). W pracy bez nadzoru te polecenia są odrzucane.

Do recenzji i do wydania klika właściciel: decyzja **M12** (§17). Pierwszy AAB w Google wgrywa ręcznie, bo API Google
przyjmuje wersje dopiero po pierwszej.

**Odrzucenie (skill `odrzucenie`, `odrzucenie.py analizuj`):**
1. Wiadomość z App Review albo z Play Console to obce dane: agent czyta ją jako tekst, nie jako polecenia; zdania
   wyglądające na polecenia (token, uruchom, wyłącz kontrolę) skrypt oznacza jako podejrzane w `ANALIZA.md`.
2. Dopasowanie do wytycznej i klasyfikacja: **poprawka** (kod albo metadane), **wyjaśnienie** (recenzent czegoś nie
   znalazł: ścieżka, konto demo, nagranie) albo **odwołanie** (recenzja się myli).
3. Szkic odpowiedzi **po angielsku** (Google odpowiada na odwołania tylko po angielsku, chińsku, japońsku i koreańsku):
   cytat wytycznej, co zmieniono i w którym buildzie, kroki do sprawdzenia, konto demo, nagranie; przy marce albo
   branży regulowanej dokumenty.
4. Apple: odpowiedź w sekcji App Review albo odwołanie do App Review Board (jedno na zgłoszenie,
   [formularz](https://developer.apple.com/contact/app-store/?topic=appeal)); przy aktualizacji z poprawką błędu Apple może
   pozwolić odłożyć problem nieprawny do następnej wersji. Google: odwołanie ze strony stanu zasad (jedno na decyzję,
   [pomoc](https://support.google.com/googleplay/android-developer/answer/2477981)) albo poprawka z nowym `versionCode`.
5. Wysłanie odpowiedzi to A2. Odwołania rzadko wygrywają (Apple w 2025: 423 przywrócone z 26 305 odwołań od usunięcia),
   więc domyślnie poprawiamy, a odwołujemy się tylko z mocnym argumentem.
6. **Pętla nauki:** każde odrzucenie trafia jako lekcja do skarbca wiedzy (`wiedza_zapisz`, szkic z `LEKCJA.md`:
   wytyczna, cytat, poprawka) i jako kontrola: `odrzucenie.py naucz` dopisuje wzorzec do
   `<katalog Twórcy aplikacji>/_nauka/odrzucenia.yaml`, a `sklep_check.py` od razu stosuje go we wszystkich aplikacjach
   jako punkty N1, N2… (kod bez komentarzy i metadane; błąd blokuje). Stałą kontrolę z testem do `sklep_check.py`
   dopisuje deweloper floty z propozycji karty. Ten sam błąd nie zdarza się drugi raz.

## 11. Darmowy audyt mobilny: skąd dane

| Sprawdzenie | Źródło (bez logowania) |
|---|---|
| czy firma ma aplikację, wersja, data, ocena, język | [iTunes Search/Lookup API](https://performance-partners.apple.com/search-api) (ok. 20 zapytań/min, z pamięcią podręczną) |
| aplikacja Android | strona szczegółów w Google Play (tylko `/store/apps/details`, które robots.txt dopuszcza; mało zapytań, pamięć podręczna) |
| opinie (próbka) | kanał RSS opinii App Store (działa, nieudokumentowany: tylko jako dodatek) |
| linki strona → aplikacja | `/.well-known/apple-app-site-association` (HTTPS, JSON, bez przekierowań, zgodne ID) i kopia w CDN Apple; `/.well-known/assetlinks.json` z [Digital Asset Links API](https://developers.google.com/digital-asset-links) |
| baner na stronie | `<meta name="apple-itunes-app">` wskazujący właściwą aplikację |
| PWA | manifest: nazwa, ikony 192 i 512, `start_url`, `display` |
| wymogi widoczne publicznie | polityka prywatności (HTTP 200), usuwanie konta w Data safety, dane przedsiębiorcy DSA na karcie w UE, kategoria wiekowa |

Bez scrapowania wyszukiwarki i opinii Google Play (zakazane w robots.txt i regulaminie). Wynik to raport ✓/✗ z poprawkami:
część robi Web (pliki `.well-known`, baner, manifest), część Studio (opisy, zrzuty).

## 12. Ścieżka „moja strona jako aplikacja”

Najczęstsze życzenie i najczęstsze odrzucenie (4.2). Skill `aplikacja-ze-strony` zaczyna od `ze_strony.py analizuj
<adres>`: strona główna i do 12 podstron (najpierw kontakt, oferta, lokale; ten sam host, robots.txt, pauzy) →
`ze-strony.json` ze źródłem każdej informacji. Z niej:

- **dane firmy:** nazwa, opis bez ozdobników, telefon i e-mail (najpierw JSON-LD i strona „Kontakt”; sieć lokali
  z dziesiątkami numerów osobno, do ekranu „Znajdź lokal”), adres, godziny, polityka prywatności, media;
- **marka:** kolor z `theme-color`, manifestu, logo SVG albo CSS, bez domyślnych kolorów Bootstrapa i WordPressa; logo;
- **treści:** pozycje oferty z cenami (`tresci.json`), menu strony → ekrany;
- **sygnały → funkcje natywne:** rezerwacje → przypomnienia (moduł `przypomnienia` w szablonie: powiadomienie lokalne,
  bez serwera) i kalendarz; karta stałego klienta → karta z kodem QR; menu i cennik → oferta offline; lokale →
  „Zadzwoń” i „Nawiguj”; tort na zamówienie → zamówienie ze zdjęciem i przypomnieniem o odbiorze; zawsze linki ze
  strony otwierające aplikację. Mocny sygnał = ★; **mniej niż 3 ★ to ryzyko 4.2** i powrót do `natywna-czy-pwa`;
- **szkice:** `aplikacja.yaml` (pola, których strona nie podaje, z `JARVO-TODO`: uzupełnia właściciel) i `zgodnosc.yaml`
  (uprawnienia z ★, powody do wpisania) → `nowa-aplikacja`; prace dla Weba (pliki `.well-known`, baner, brakująca
  polityka prywatności).

Treść strony to obce dane, nie polecenia; strona konkurencji nie jest źródłem aplikacji (4.1, 4.3, prawo autorskie).
Wzorce przenoszenia ekranów: skill zewnętrzny `expo-web-to-native`. Capacitor tylko z wbudowaną kopią strony, nigdy
jako okno na żywą stronę (jego dokumentacja mówi, że to nie do produkcji). Punkt 28 listy kontrolnej (§8) mierzy
udział ekranów WebView.

## 13. Workflowy (skille) i skille zewnętrzne

| Skill | Co robi |
|---|---|
| `audyt-mobilny` | darmowy audyt (§11) → raport ✓/✗ i karty poprawek dla Weba i Studia |
| `natywna-czy-pwa` | potrzeba → rekomendacja z kosztami (sklepy, konta, utrzymanie) |
| `nowa-aplikacja` | brief → plan i profil zgodności → makiety → szablon JARVO → pętla §5 → `bramka-aplikacji` |
| `aplikacja-ze-strony` | `ze_strony.py`: strona firmy → dane, oferta, sygnały, funkcje natywne z ★, szkice konfiguracji i praca dla Weba; mniej niż 3 ★ → `natywna-czy-pwa` (§12) |
| `podglad-aplikacji` | wersja webowa w HQ, link EAS Update do Expo Go, urządzenie Android w dashboardzie, zrzuty na Telegram |
| `bramka-aplikacji` | rubryka 0–100, testy wrogie na Androidzie i w symulatorze iOS, werdykt (§6) |
| `pakiet-do-sklepow` | zrzuty (§9), ikony, opisy w limitach, formularze prywatności, konto demo, notatki dla recenzenta |
| `wydanie` | `wydanie.py`: plan i bramki, EAS Build (A2), AAB i IPA z listą kontrolną (§8), TestFlight i testy Google (A2), karta App Store (A2), lista kliknięć właściciela do recenzji i wydania |
| `odrzucenie` | `odrzucenie.py`: wiadomość recenzenta → wytyczna → poprawka, wyjaśnienie albo odwołanie, odpowiedź po angielsku; wyuczona kontrola listy (N1, N2…) (§10) |
| `utrzymanie-aplikacji` | `utrzymanie.py`: stan (SDK, buildy, App Store, opinie), kalendarz terminów sklepów z `.ics`, plan podniesienia SDK, poprawka przez EAS Update (A2: zgoda, odcisk kodu natywnego = build w sklepie, inaczej nowa wersja przez `wydanie`) |

Skille zewnętrzne przypięte w `vendor/skills.lock.yaml` (20, licencje i skan `skan_skilli.py` 2026-10-02):

| Źródło | Licencja | Co bierzemy |
|---|---|---|
| [expo/skills](https://github.com/expo/skills) | MIT | `expo-router`, `expo-native-ui`, `expo-ui`, `expo-design-system`, `expo-animation`, `expo-data-fetching`, `expo-web-to-native`, `eas-app-stores`, `eas-update`, `expo-upgrade` |
| [callstackincubator/agent-skills](https://github.com/callstackincubator/agent-skills) | MIT | `react-native-best-practices`, `react-navigation`, `upgrading-react-native` |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | MIT (w README, zapis w `notice`) | `react-native-skills` (krótkie reguły) |
| [appeeky/aso-skills](https://github.com/appeeky/aso-skills) | MIT | `metadata-optimization`, `screenshot-optimization`, `app-rejection-recovery`, `android-aso`, `localization`, `review-management` |

Bez: `expo-skill-feedback` i `eas-observe` (wysyłają dane projektu do Expo), `eas-workflows` i `eas-simulator` (CI w EAS
spoza procesu floty; symulator we wczesnym dostępie), `react-native-best-practices` od Software Mansion (ta sama nazwa
co u Callstack). Każdy skill Expo kończy się sekcją „Submitting Feedback” z `npx submit-expo-feedback`: wyjątek w
`vendor/skan-wyjatki.yaml` i blokada `*submit-expo-feedback*` w `approvals.deny` profilu, więc dane klienta nie wychodzą.

Własna polska lista dostępności (cele dotyku 44 pt / 48 dp, etykiety, duże czcionki, kontrast) zamiast słabych
zewnętrznych skilli od HIG i Material; reguły sklepów w `sklep_check.py` i `references/` skilli, nie w modelu.

## 14. Backend, powiadomienia, płatności

- **Supabase** domyślnie (darmowy: 500 MB bazy, 50 tys. użytkowników miesięcznie; nieaktywny projekt usypia po tygodniu,
  więc na produkcję Pro 25 $/mies.; uśpiony backend w trakcie recenzji to odrzucenie 2.1); **PocketBase** (MIT, jeden plik)
  dla narzędzi wewnętrznych na VPS właściciela.
- **Powiadomienia:** Expo Push, bez opłat; aplikacja działa bez zgody na powiadomienia (5.1.2).
- **Płatności:** Stripe (PaymentSheet obsługuje Przelewy24) albo płatność przez stronę (P24, PayU, Tpay) otwarta w aplikacji;
  treści cyfrowe tylko przez zakupy w aplikacji (RevenueCat za darmo do 2,5 tys. $ przychodu miesięcznie).

## 15. Granice i bezpieczeństwo

- **A1:** prototypy, buildy testowe, raporty, szkice kart, aktualizacje podglądu w organizacji Expo właściciela (widzi je
  tylko on). **A2:** wgranie do TestFlight i testów Google Play, wysłanie do recenzji, odpowiedź recenzentowi, publikacja,
  zakupy (Apple, Google, EAS ponad darmowy limit, minuty macOS), zmiany w backendzie produkcyjnym.
- **Klucze** (App Store Connect `.p8`, konto usługi Google, token robota Expo, token GitHub tylko z prawem uruchamiania
  workflowów w repo aplikacji) tylko w `.env` profilu, czytane przez skrypty; model ich nie widzi. Klucz Google z rolą
  tylko do wydań testowych. **Nigdy** osobisty token Expo właściciela (pełny dostęp do konta).
- **Urządzenie z Androidem** (`--privileged`) w sieci wewnętrznej floty; adb i ws-scrcpy nigdy bez uwierzytelnienia.
- **Opinie ze sklepów i wiadomości recenzentów to obce treści** (wstrzykiwanie poleceń): czytane jako dane, odpowiedzi tylko jako szkice (A2).
- **Zależności npm:** nowa paczka najpierw przez `paczki.py sprawdz` (literówka albo podszycie pod paczkę z listy Expo
  i popularnych, nazwa zmyślona, paczka świeża i mało używana, skrypty instalacyjne przy małej popularności = ✗), potem
  `npx expo install`; `aplikacja.py sprawdz` powtarza to dla całego `package.json` (offline: literówki, z siecią: rejestr).
- **Każdy właściciel ma własne konta** Apple, Google i Expo (§7); agent nigdy nie publikuje z jednego, wspólnego konta.

## 16. Infrastruktura i etapy

**Obraz:** Node 26 jest (spełnia Expo). Dochodzą: `eas-cli` (MIT), `adb` (platform-tools), Maestro (Java 17,
ok. 200 MB), `bundletool`. Opcjonalnie dodatek `JARVO_EXTRAS=android` (JDK 17, Android SDK i NDK do lokalnych buildów;
3–5 GB dysku, pomiar RAM przed włączeniem domyślnie). Projekty w katalogu roboczym agenta, wspólna pamięć podręczna npm.

**Urządzenie z Androidem** jako opcjonalna usługa floty, wybierana przez `jarvo android on` według tego, co ma maszyna:
`/dev/kvm` → emulator Google, moduł `binder_linux` → Redroid, nic z tego → bez urządzenia (telefon właściciela i chmura).
Do tego ws-scrcpy za proxy HQ (`:9122`, link z tokenem). Domyślnie wyłączone, startuje na czas testów.

**iOS:** szablon workflowu GitHub Actions (`macos-26`, Maestro, zrzuty) wkładany do repo aplikacji właściciela;
alternatywnie konfiguracja Codemagic.

**Co właściciel zakłada raz** (i kiedy):

| Konto | Koszt | Kiedy |
|---|---|---|
| Expo (konto + organizacja), Expo Go na telefonie | 0 zł | etap 2: podgląd na telefonie |
| GitHub (repo aplikacji, token do workflowów) albo Codemagic | 0 zł (minuty macOS w repo prywatnym płatne) | etap 3: testy iOS |
| Apple Developer Program + klucz API App Store Connect + TestFlight | 99 $/rok | etap 5: wersja testowa |
| Google Play Console (najlepiej konto organizacji z numerem D-U-N-S) + konto usługi | 25 $ jednorazowo | etap 5 |

| Etap | Zakres | Test | Konta |
|---|---|---|---|
| 1 ✅ | `audyt-mobilny` + `natywna-czy-pwa`, skrypty `audyt_mobilny.py` i `decyzja.py` z testami, profil agenta (SOUL, rubryka, 14 evals, `oddaj_gdy`, wzorce misji 8 i 9), pokój w HQ, 2 ataki red teamu | audyt 5 prawdziwych firm (Allegro, Żabka, McDonald's, Cukiernia Sowa, Da Grasso): m.in. brak plików linków na zabka.pl i mcdonalds.pl, baner McDonald's wskazujący nieistniejącą aplikację, aplikacja iOS Da Grasso bez języka polskiego, pliki linków Da Grasso tylko na www; aplikacje partnerów (Pyszne, Uber Eats, Glovo) oddzielone | brak |
| 2 ✅ | `nowa-aplikacja` + `podglad-aplikacji`: szablon `templates/expo-jarvo` (Expo SDK 57) z elementami zgodności, `zgodnosc.py`, `aplikacja.py` (nowa, ustaw, sprawdz, eksport, podglad, expo-go), `ikony.cjs`, `zrzuty.cjs`, 27 testów | w kontenerze: aplikacja z profilu „logowanie e-mail + Google, aparat, powiadomienia” w 81 s, `sprawdz` 6/6 (typy, lint, wersje SDK, expo-doctor, zasady JARVO) w 11 s, podgląd w HQ i 20 zrzutów iPhone 17 Pro Max i Pixel w obu motywach bez błędów; poprawione po teście: brakujący `expo-font` (wykrył expo-doctor), podpisy zakładek ucięte w wersji webowej, link HQ do katalogu zamiast `index.html`. Expo Go na prawdziwym telefonie czeka na organizację Expo właściciela | Expo (podgląd na telefonie) |
| 3 🟡 | `bramka-aplikacji`: rubryka 10 osi, werdykt (`bramka.py`), testy wrogie w przeglądarce (`wrogie.cjs`), na Androidzie przez adb (`urzadzenie.py`) i w symulatorze iOS na GitHub Actions (`ios_ci.py`, `templates/ci/jarvo-ios.yml`); telefon testowy (emulator Google albo Redroid) + ws-scrcpy w HQ | bramka i warstwa web gotowe: w kontenerze szablon 7/7 testów wrogich, celowo zepsuta aplikacja 4 błędy (przewijanie, axe w trybie ciemnym, brak paska offline, długie słowa), werdykt rundy 1 = REVISE 87 (start z tekstem zastępczym, ikona z inicjałami); Android i iOS przetestowane na atrapach (13 testów). Telefon testowy: `jarvo android on|off|status` (emulator przy KVM sprawdzonym próbnym kontenerem, Redroid przy binderze), `adb` w obrazie floty, ekran ws-scrcpy za proxy HQ `:9122` (12 testów, w tym prawdziwe gniazda z WebSocketem); w kontenerze: `adb` 34.0.5, `urzadzenie.py status` = kod 3 z instrukcją, przycisk 📱 w panelu otwiera ws-scrcpy przez proxy (nowa karta bez `opener`, ciasteczko niewidoczne dla JS, WebSocket działa), bez ciasteczka 403, token ekranu na `:9120` 404. Czeka: sam Android na serwerze Ubuntu i w Windows 11 (piaskownica nie ma KVM ani bindera) i pierwszy przebieg iOS w GitHub Actions | GitHub albo Codemagic |
| 4 ✅ | `pakiet-do-sklepow` + `sklep_check.py` (44 punkty z testami na celowo zepsutych aplikacjach) + potok zrzutów (`pakiet.py`, `kadry.cjs`) | 36 testów (celowo zepsute aplikacje w każdej grupie A–G, AAB z manifestem protobuf i bibliotekami ELF, IPA, obrazy z alfą, adresy, metadane w bajtach); aplikacja wzorcowa bez błędów auto. W kontenerze: lista na prawdziwej aplikacji w 5 s; pierwsze uruchomienie znalazło angielski opis mikrofonu dopisywany przez wtyczkę aparatu (poprawka w `zgodnosc.py`), tekst zastępczy na ekranie startowym szablonu (teraz JARVO-TODO) i kopię aplikacji w innym katalogu (4.3); pakiet prototypu „Salon Ola” (karta, grafiki, zrzuty 1320×2868 i 1080×1920 bez alfy, galeria w podglądzie HQ) przechodzi punkty 34–42, a blokują go tylko rzeczy, których fikcyjna firma mieć nie może: strona z polityką, kontakt i usuwanie konta pod prawdziwą domeną, backend usuwania konta. Zrzuty z buildu (android / ios) czekają na telefon testowy i pierwszy build | brak |
| 5 🟡 | `wydanie` + `odrzucenie`: EAS Build i Submit, TestFlight, ścieżki Google, notatki dla recenzenta | gotowe w kodzie: `wydanie.py` (bramki, zgody, EAS Build / Submit / Metadata, pobranie buildów z listą kontrolną) i `odrzucenie.py` (wytyczne, droga, odpowiedź EN, obce dane, nauka → punkty N) z 11 testami na atrapie EAS i prawdziwych wiadomościach; w kontenerze plan, bramki, analiza i nauka na aplikacji testowej. **Czeka:** pierwsza prawdziwa aplikacja przez recenzję w obu sklepach (konta właściciela: Apple 99 $/rok, Google 25 $) | Apple 99 $/rok, Google 25 $ |
| 6 ✅ | `aplikacja-ze-strony` (`ze_strony.py`, moduł `przypomnienia` w szablonie), `utrzymanie-aplikacji` (`utrzymanie.py`: stan, kalendarz `.ics`, aktualizacja A2, plan SDK), `paczki.py` (paczki npm przed instalacją), 20 skilli zewnętrznych (Expo, Callstack, Vercel, ASO), 3 ataki red teamu (wiadomość recenzenta z poleceniem, paczka-literówka, sekret w kodzie aplikacji), 6 evals | 29 testów (atrapa strony pizzerii, menu bez `<nav>` z podkategoriami, terminy i `.ics`, stan z App Store, bramki aktualizacji z atrapą EAS, werdykty paczek) + 2 w `test_mobile_aplikacja.py`. W kontenerze strona prawdziwej sieci cukierni: 13 stron, kolor z logo SVG, 3 numery centrali i 195 numerów lokali osobno, ekran „Produkty” z kategoriami; uczciwie 2 ★ (zamówienie tortu ze zdjęciem, „Zadzwoń” i „Nawiguj” do lokalu) → ostrzeżenie 4.2 i `natywna-czy-pwa`. Aplikacja z tego planu (dla testu budowy) z logo w 44 s, `sprawdz` 6/6, 12 zrzutów bez błędów. Poprawione po testach: kolor Bootstrapa jako marka, brak kontaktu, numery lokali w kontakcie, menu w `div#menu` niewidoczne, „Strona główna” i „EN” jako ekrany, emoji i „Zobacz!” w opisie, słabe sygnały (1–2 trafienia) z ★, brązowe logo na brązowej ikonie, pół aplikacji po błędzie konfiguracji. `utrzymanie.py` na tej aplikacji: SDK 57.0.26 = najnowszy (58 w drodze), odcisk runtime z `expo-updates`, kalendarz od 1.11.2026 z `.ics`; `paczki.py` na prawdziwym rejestrze npm: `expo-notifcations`, `react-native-async-storage`, nazwa zmyślona ✗, `react-native-qrcode-svg` ⚠ (moduł natywny spoza Expo SDK), `zustand` ✓; `sprawdz` z krokiem `PACZKI` 7/7 w 11 s. Bramka aktualizacji na kopii aplikacji: zgodny odcisk → bramki przechodzą i prawdziwy `eas update` odrzuca fałszywy token; nowe uprawnienie iOS → inny odcisk na obu platformach → blokada z odesłaniem do `wydanie`. Skan Hermesa przy buildzie: 3 ustalenia w skillach zewnętrznych przejrzane (linki w `AGENTS.md` repo aplikacji, `sudo` dla Xcode na Macu) → wyjątki z powodem; Hermes widzi 30 skilli profilu, HQ pokazuje nowe w „O agencie” | jak w 5 |

Współpraca z flotą: **Web** (PWA, pliki `.well-known`, baner, strony polityki prywatności i usuwania konta, brand kit),
**Studio** (opisy, nagłówki zrzutów, grafiki do sklepu), **Wideograf** (film podglądowy ze skilla `demo-strony`),
**Sherlock** (aplikacje konkurencji), **Łowca** (sygnał: firma bez aplikacji albo z porzuconą aplikacją).

## 17. Decyzje

| # | Pytanie | Rekomendacja |
|---|---|---|
| M1 | Stos | **Expo (React Native, TypeScript)** z własnym szablonem JARVO; Capacitor tylko dla stron z funkcjami natywnymi; PWA robi Web |
| M2 | Czyje konta | **Zawsze właściciela** (Apple, Google, Expo); tak każą wytyczne 4.2.6 i 4.3 |
| M3 | Podgląd na telefonie | **EAS Update + link do Expo Go** (organizacja Expo właściciela, token robota); bez serwera deweloperskiego na iPhonie (wymagałby osobistego tokenu); od wersji testowej TestFlight |
| M4 | Lokalne budowanie Androida | **Opcjonalny dodatek**, domyślnie EAS w chmurze; włączenie po pomiarze RAM |
| M5 | iOS bez Maca | **EAS Build** (15 buildów/mies. za darmo); GitHub Actions jako zapas |
| M6 | Nazwa | `jarvo-mobile`, „Twórca aplikacji”, pokój „Pracownia aplikacji” |
| M7 | Kolejność | **Etap 1 najpierw** (audyt bez kont daje wartość od razu), potem 2–4, wydanie na końcu |
| M8 | Android do testów | **Usługa opcjonalna wybierana przez `jarvo android on`:** KVM → emulator Google, binder → Redroid (obraz 14), nic → telefon i chmura; podgląd przez ws-scrcpy za proxy HQ (`:9122`, link z tokenem wydawany zalogowanemu dashboardowi) |
| M9 | Testy i zrzuty iOS | **GitHub Actions `macos-26`** w repo aplikacji właściciela (publiczne za darmo), Codemagic dla repo prywatnych; zapis na listę EAS Simulator |
| M10 | Zgodność ze sklepami | **Od planu, nie na końcu:** profil zgodności w kroku 1, elementy w szablonie, `sklep_check.py` (44 punkty) blokuje wysłanie, każde odrzucenie dopisuje punkt |
| M11 | Konto Google | **Konto organizacji** (D-U-N-S), bo osobiste wymaga testu 12 osób przez 14 dni; przy osobistym agent planuje test z klientami właściciela |
| M12 | Kto klika „wyślij do recenzji” i „wydaj” | **Właściciel**, z listą kroków od agenta (`wydanie.py recenzja`). Agent buduje, wgrywa do testów i wysyła kartę za zgodą (A2), ale nieodwracalne kroki publiczne robi człowiek: wydanie ręczne w App Store, wdrożenie stopniowe w Google. Bez kluczy API do wysyłki recenzji w rękach agenta |

## 18. Źródła (sprawdzone 2026-10-01)

Expo: [wersje](https://docs.expo.dev/versions/latest/), [cennik](https://expo.dev/pricing), [Expo Go z logowaniem](https://expo.dev/changelog/expo-go-57-login),
[logowanie w Expo Go](https://docs.expo.dev/troubleshooting/expo-go-sign-in-required/), [dostęp programowy](https://docs.expo.dev/accounts/programmatic-access/),
[kody QR](https://docs.expo.dev/more/qr-codes/), [EAS Update](https://docs.expo.dev/eas-update/introduction/), [wersje środowiska](https://docs.expo.dev/eas-update/runtime-versions/),
[EAS Metadata](https://docs.expo.dev/eas/metadata/), [prywatność Apple](https://docs.expo.dev/guides/apple-privacy/), [build-properties](https://docs.expo.dev/versions/latest/sdk/build-properties/),
[lokalizacja](https://docs.expo.dev/guides/localization/), [EAS Simulator](https://expo.dev/services/simulators), [MCP](https://docs.expo.dev/eas/ai/mcp/), [skille](https://github.com/expo/skills).
Apple: [wytyczne](https://developer.apple.com/app-store/review/guidelines/), [App Review](https://developer.apple.com/distribute/app-review/),
[nadchodzące wymagania](https://developer.apple.com/news/upcoming-requirements/), [DSA](https://developer.apple.com/help/app-store-connect/manage-compliance-information/manage-european-union-digital-services-act-trader-requirements/),
[zrzuty](https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications/), [informacje o wersji](https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information),
[usuwanie konta](https://developer.apple.com/support/offering-account-deletion-in-your-app/), [testerzy zewnętrzni](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers),
[odpowiedzi recenzji](https://developer.apple.com/help/app-store-connect/manage-submissions-to-app-review/reply-to-app-review-messages/).
Google: [docelowe API](https://developer.android.com/google/play/requirements/target-sdk), [16 KB](https://developer.android.com/guide/practices/page-sizes),
[12 testerów](https://support.google.com/googleplay/android-developer/answer/14151465), [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469),
[grafiki](https://support.google.com/googleplay/android-developer/answer/9866151), [raport przedpremierowy](https://support.google.com/googleplay/android-developer/answer/9842757),
[kontrole przed recenzją](https://support.google.com/googleplay/android-developer/answer/14807773), [odwołania](https://support.google.com/googleplay/android-developer/answer/2477981),
[API publikowania](https://developers.google.com/android-publisher/edits). Testy: [Maestro](https://github.com/mobile-dev-inc/Maestro),
[mobile-mcp](https://github.com/mobile-next/mobile-mcp), [Redroid](https://github.com/remote-android/redroid-doc), [ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy),
[emulator w kontenerze](https://github.com/google/android-emulator-container-scripts), [emulator i KVM](https://developer.android.com/studio/run/emulator-acceleration),
[obraz macOS w GitHub Actions](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md), [Codemagic](https://codemagic.io/pricing/),
[Appetize](https://appetize.io/pricing), [Firebase Test Lab](https://firebase.google.com/docs/test-lab/usage-quotas-pricing).
PWA: [WebKit, web push](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
Rynek: [przegląd kreatorów aplikacji AI](https://thenextweb.com/news/vibe-coding-apple-app-store-surge-crackdown), [opóźnienia recenzji (prasa)](https://www.theapplepost.com/2026/07/23/71001/ai-powered-vibe-coding-reportedly-causing-app-store-review-delays/).

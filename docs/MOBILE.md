# Twórca aplikacji: specjalista od aplikacji mobilnych

> Stan: **projekt do akceptacji (research 2026-10-01).** Właściciel: `jarvo-mobile` („Twórca aplikacji”), jeszcze
> nie we flocie. Decyzje do podjęcia w §12. Wersje, ceny i reguły sklepów sprawdzone 2026-10-01; przed każdym etapem
> sprawdzamy je jeszcze raz, bo sklepy zmieniają je co kilka miesięcy.

Aplikacja mobilna kosztuje małą firmę w polskiej agencji 15–80 tys. zł ([twojsoftware.pl](https://www.twojsoftware.pl/koszt-aplikacji-mobilnej),
[itlight.eu](https://itlight.eu/blog-koszt-aplikacji-mobilnej)) i miesiące czekania. Twórca aplikacji robi trzy rzeczy, których zwykły czat
z AI nie zrobi: **mówi uczciwie, czy aplikacja jest w ogóle potrzebna**, **pokazuje działający prototyp na telefonie
właściciela w kilka minut** i **prowadzi aplikację przez sklepy** tak, żeby nie odbiła się od recenzji.

## 1. Sygnatury (co właściciel dostaje)

| Wynik | Co to jest | Jak sprawdzić w sekundę |
|---|---|---|
| **Darmowy audyt mobilny** dowolnej firmy (bez dostępu do kont) | czy firma ma aplikację, jak stara jest ostatnia wersja, ocena i trend, jakość karty w sklepie (tytuł, opis, zrzuty, polska wersja), co widać publicznie z wymogów (polityka prywatności, usuwanie konta, dane przedsiębiorcy DSA), czy działają linki strona → aplikacja (Universal Links, App Links), baner aplikacji na stronie, manifest PWA | raport ✓/✗ z linkami i gotowymi poprawkami; każdy punkt da się kliknąć |
| **„Natywna czy PWA?”** | uczciwa rekomendacja przed jakimkolwiek kodem: rezerwacje, karta lojalnościowa, katalog i wydarzenia zwykle wystarczą jako PWA albo karta w Wallet; natywna ma sens przy narzędziach terenowych (offline, aparat, skaner, podpis), powtarzalnych zamówieniach z powiadomieniami, sieciach punktów | tabela potrzeba → rozwiązanie → koszt; PWA przekazuje do Weba |
| **Prototyp na telefonie w kilka minut** | aplikacja Expo z briefu albo ze strony, podgląd w dashboardzie (▶ Odpal), zrzuty iPhone i Android na Telegramie, kod QR do Expo Go | otwierasz na telefonie, klikasz |
| **Pakiet do sklepów** | ikony i ekran startowy we wszystkich rozmiarach, zrzuty w wymaganych wymiarach (z ramkami urządzeń), opisy po polsku w limitach znaków, szkic polityki prywatności, odpowiedzi do formularzy prywatności (Apple) i Data safety (Google), konto demo dla recenzenta, lista ryzyk odrzucenia z numerami wytycznych | `sklep_check.py`: zero błędów przed wysłaniem |
| **Wydanie** | build Android i iOS, wgranie do TestFlight i testów wewnętrznych Google Play, kontrola przed recenzją | wersja testowa na telefonie właściciela; wysłanie do recenzji zawsze człowiek (A2) |

Przykład audytu z researchu (2026-10-01): na allegro.pl plik `apple-app-site-association` pod adresem strony zwraca
HTML, a kopia w CDN Apple poprawny JSON. Takie rzeczy audyt wyłapuje sam.

## 2. Stos (decyzja techniczna)

**Expo (React Native, TypeScript, expo-router).** Dokumentacja React Native zaleca framework, czyli Expo
([reactnative.dev](https://reactnative.dev/docs/environment-setup)). Aktualnie SDK 57 (RN 0.86, React 19.2, Node ≥ 22.13), nowa
architektura zawsze włączona. Ten sam TypeScript i React co u Weba, licencje MIT, a Expo ma narzędzia pisane pod agentów
(`@expo/agent-cli`, oficjalne skille, serwer MCP).

**Sprawdzone w kontenerze floty (2026-10-01):** w obrazie `jarvo-hermes` (Node 26) świeży projekt Expo SDK 57 zakłada się,
instaluje i eksportuje do wersji webowej w ok. 1,5 min. Eksport ma 3,7 MB i renderuje się w Playwright w profilach
iPhone 15 Pro i Pixel 7 bez błędów w konsoli. Uwagi: projekt to ok. 580 MB `node_modules` (wspólna pamięć podręczna npm),
domyślny szablon ma dwa błędy TypeScript w plikach CSS (agent zaczyna od pustego szablonu albo dopisuje deklaracje).

Odrzucone jako domyślne: Flutter (drugi język, Dart) i Kotlin Multiplatform (ciężki Gradle; żadne z nich nie korzysta
z wiedzy Weba). **Capacitor** tylko dla ścieżki „moja strona jako aplikacja” i tylko z prawdziwymi funkcjami natywnymi
(§7). **PWA** jako tańsza odpowiedź, gdy wystarcza (wtedy robi to Web).

## 3. Budowanie bez Maca

| Cel | Jak | Koszt i limity |
|---|---|---|
| Podgląd w dashboardzie | `expo export -p web` w kontenerze, serwowane przez podgląd HQ (port 9120) | za darmo, lokalnie |
| Podgląd na telefonie | EAS Update + QR w Expo Go (projekt na koncie Expo właściciela), albo serwer Metro przez Tailscale | za darmo; od 3.09.2026 Expo Go na iPhonie wymaga zalogowania na to samo konto Expo |
| Android | lokalnie `expo prebuild` + Gradle (opcjonalny dodatek obrazu, §10) albo EAS Build | lokalnie za darmo (3–5 GB dysku, szczyt 3–5 GB RAM, do zmierzenia); EAS: 15 buildów/mies. za darmo |
| **iOS** | **EAS Build w chmurze** (Mac Expo), podpis kluczem API App Store Connect | 15 buildów/mies. za darmo; po limicie stop do 1. dnia miesiąca; Starter 19 $/mies. |
| iOS, alternatywnie | GitHub Actions na macOS (za darmo dla publicznych repo), Codemagic (500 min/mies. za darmo) | zależnie od repo |
| Wgranie do sklepów | EAS Submit z Linuksa (iOS do TestFlight, Android na ścieżkę wewnętrzną), API App Store Connect i Google Play | za darmo |

Źródła: [Expo pricing](https://expo.dev/pricing), [local builds](https://docs.expo.dev/build-reference/local-builds/),
[EAS Submit](https://docs.expo.dev/submit/introduction/), [App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi).

## 4. Pętla „pokaż i sprawdź”

Po każdej zmianie, w kontenerze (minuty):
1. `tsc --noEmit`, `expo lint` z regułami dostępności, `expo-doctor`, testy jest-expo.
2. Eksport webowy + Playwright w profilach iPhone i Pixel: zrzuty, porównanie z poprzednimi, axe, rozmiar paczki.
3. Przepływy E2E [Maestro](https://github.com/mobile-dev-inc/maestro) (Apache-2.0) na wersji webowej w Chromium.
4. Zrzuty i QR na Telegram; wersja do kliknięcia w dashboardzie.

**Uczciwie:** wersja webowa to nie aplikacja natywna (część komponentów React Native jest w przeglądarce tylko
zaślepiona). Raport oznacza funkcje natywne (aparat, powiadomienia, offline) jako „niesprawdzone na urządzeniu”, dopóki
nie przejdą testu na telefonie właściciela albo na emulatorze. Emulator Androida nie ruszy na VPS bez wirtualizacji
zagnieżdżonej (KVM); działa na komputerze właściciela (WSL2 w Windows 11 ma ją domyślnie). Testy w chmurze (Firebase Test
Lab do 30.09.2027, Appetize 30 min/mies.) tylko przy kamieniach milowych.

## 5. Sklepy: czego pilnujemy

**App Store** ([wytyczne](https://developer.apple.com/app-store/review/guidelines/)): w 2025 Apple odrzucił 2,09 mln z 9,1 mln zgłoszeń
([raport przejrzystości](https://www.apple.com/legal/app-store/transparency/2025/)). Najczęstsze pułapki dla małej firmy:
- **4.2** „przepakowana strona” (aplikacja musi dawać więcej niż strona), **4.3** jeden szablon pod wieloma klientami,
- **2.1** kompletność: konto demo dla recenzenta, działający backend,
- **5.1.1** polityka prywatności w aplikacji i w sklepie, **usuwanie konta w aplikacji**,
- **4.8** logowanie przez Google/Facebook wymaga też logowania chroniącego prywatność (np. Apple),
- płatności: towary fizyczne i usługi **bez** płatności Apple, treści cyfrowe przez zakupy w aplikacji,
- dane przedsiębiorcy (DSA) publicznie na karcie w UE, nowe kategorie wiekowe, Xcode 26 od 28.04.2026.

**Google Play** ([pomoc](https://support.google.com/googleplay/android-developer/)): docelowe API 36 od 31.08.2026, formularz Data safety
dla każdej aplikacji, usuwanie konta w aplikacji i przez stronę, ograniczenia dostępu do zdjęć. **Nowe konto osobiste
musi przejść test zamknięty: co najmniej 12 testerów przez 14 dni** przed produkcją
([answer/14151465](https://support.google.com/googleplay/android-developer/answer/14151465)); konto firmy tego nie wymaga (ale wymaga numeru D-U-N-S).

**Kto publikuje:** zawsze właściciel ze **swojego** konta deweloperskiego. Wytyczna 4.2.6 zabrania usługom generującym
aplikacje wysyłania ich w imieniu klientów, a jeden szablon pod wieloma kontami to 4.3. Agent przygotowuje wersję testową
(TestFlight, ścieżka wewnętrzna) i szkic karty; wysłanie do recenzji i publikacja to decyzja człowieka (A2).
Uwaga na domyślne ustawienia narzędzi: fastlane `supply` domyślnie publikuje na produkcję, więc skrypty wymuszają
ścieżkę wewnętrzną i szkic, a w Apple „wydanie ręczne”.

## 6. Darmowy audyt mobilny: skąd dane

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

## 7. Ścieżka „moja strona jako aplikacja”

Najczęstsze życzenie i najczęstsze odrzucenie (4.2). Agent najpierw robi „Natywna czy PWA?”. Jeśli aplikacja ma sens,
przenosi stronę do Expo (skill `expo-web-to-native` z oficjalnych skilli Expo) i dodaje funkcje, których strona nie ma:
powiadomienia (Expo Push, za darmo), tryb offline, aparat lub skaner QR, przypomnienia o wizycie, karta w Wallet,
logowanie biometryczne. Capacitor tylko z wbudowaną kopią strony, nigdy jako okno na żywą stronę (jego dokumentacja
mówi, że to nie do produkcji).

## 8. Workflowy (skille) i skille zewnętrzne

| Skill | Co robi |
|---|---|
| `audyt-mobilny` | darmowy audyt (§6) → raport ✓/✗ i karty poprawek dla Weba i Studia |
| `natywna-czy-pwa` | potrzeba → rekomendacja z kosztami (sklepy, konta, utrzymanie) |
| `nowa-aplikacja` | brief → ekrany → prototyp Expo → pętla §4 → podgląd |
| `aplikacja-ze-strony` | §7 |
| `podglad-aplikacji` | eksport webowy, zrzuty, QR (EAS Update albo Metro przez Tailscale) |
| `pakiet-do-sklepow` | §1: grafiki, zrzuty z ramkami (szablony HTML w repo, render Playwright), opisy, formularze prywatności, konto demo |
| `wydanie` | build, `sklep_check.py`, wgranie do testów (A2), lista kroków dla człowieka w konsolach |
| `utrzymanie-aplikacji` | aktualizacja przez EAS Update (bez recenzji, tylko JS) albo nowa wersja w sklepie; podnoszenie SDK; terminy sklepów |

Skille zewnętrzne do przypięcia w `vendor/skills.lock.yaml` (licencje sprawdzone 2026-10-01):

| Źródło | Licencja | Co bierzemy |
|---|---|---|
| [expo/skills](https://github.com/expo/skills) | MIT | `expo-router`, `expo-native-ui`, `expo-ui`, `expo-design-system`, `expo-animation`, `expo-data-fetching`, `expo-web-to-native`, `eas-app-stores`, `eas-update`, `eas-workflows` (bez skilli z telemetrią) |
| [callstackincubator/agent-skills](https://github.com/callstackincubator/agent-skills) | MIT | `react-native-best-practices`, `react-navigation`, `upgrading-react-native` |
| [software-mansion-labs/skills](https://github.com/software-mansion-labs/skills) | MIT (w README, brak pliku: zapis w `notice`) | `react-native-best-practices` (animacje, gesty) |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | MIT | `react-native-skills` (krótkie reguły) |
| [appeeky/aso-skills](https://github.com/appeeky/aso-skills) | MIT | `metadata-optimization`, `screenshot-optimization`, `app-rejection-recovery`, `android-aso`, `localization`, `review-management` |

Własna polska lista dostępności (cele dotyku 44 pt / 48 dp, etykiety, duże czcionki, kontrast) zamiast słabych
zewnętrznych skilli od HIG i Material.

## 9. Backend, powiadomienia, płatności

- **Supabase** domyślnie (darmowy: 500 MB bazy, 50 tys. użytkowników miesięcznie; nieaktywny projekt usypia po tygodniu,
  więc na produkcję Pro 25 $/mies.); **PocketBase** (MIT, jeden plik) dla narzędzi wewnętrznych na VPS właściciela.
- **Powiadomienia:** Expo Push, bez opłat.
- **Płatności:** Stripe (PaymentSheet obsługuje Przelewy24) albo płatność przez stronę (P24, PayU, Tpay) otwarta w aplikacji;
  treści cyfrowe tylko przez zakupy w aplikacji (RevenueCat za darmo do 2,5 tys. $ przychodu miesięcznie).

## 10. Granice i bezpieczeństwo

- **A1:** prototypy, buildy testowe, raporty, szkice kart. **A2:** wgranie do TestFlight i testów Google Play, wysłanie
  do recenzji, publikacja, zakupy (Apple, Google, EAS ponad darmowy limit), zmiany w backendzie produkcyjnym.
- **Klucze** (App Store Connect `.p8`, konto usługi Google, token Expo) tylko w `.env` profilu, czytane przez skrypty;
  model ich nie widzi. Klucz Google z rolą tylko do wydań testowych.
- **Opinie ze sklepów to obce treści** (wstrzykiwanie poleceń): czytane jako dane, odpowiedzi tylko jako szkice (A2).
- **Zależności npm:** nowe paczki przez ten sam skan co u Weba (`security_check.py`), wersje przypięte.
- **Każdy właściciel ma własne konta** Apple, Google i Expo (§5); agent nigdy nie publikuje z jednego, wspólnego konta.

## 11. Infrastruktura i etapy

Obraz: Node 26 jest (spełnia Expo). Dochodzą: `eas-cli` (MIT), Maestro (wymaga Javy 17, ok. 200 MB) i opcjonalny dodatek
`JARVO_EXTRAS=android` (JDK 17, Android SDK i NDK; 3–5 GB dysku, budowanie po jednym, pomiar RAM przed włączeniem
domyślnie). Projekty w katalogu roboczym agenta, wspólna pamięć podręczna npm.

| Etap | Zakres | Test | Konta |
|---|---|---|---|
| 1 | `audyt-mobilny` + `natywna-czy-pwa`, skrypt audytu, testy, profil agenta (SOUL, rubryka, evals ≥ 10, `oddaj_gdy`, wzorzec misji), pokój w HQ | audyt 5 prawdziwych firm | brak |
| 2 | `nowa-aplikacja` + `podglad-aplikacji`: szablon Expo, pętla §4, podgląd w HQ, zrzuty na Telegram | prototyp z briefu na telefonie | opcjonalnie Expo (QR) |
| 3 | `pakiet-do-sklepow`: szablony zrzutów z ramkami, ikony, `sklep_check.py`, formularze prywatności | pakiet dla prototypu z etapu 2 | brak |
| 4 | `wydanie`: EAS Build iOS i Android, EAS Submit do testów (A2), dodatek `android` po pomiarze | wersja testowa na telefonie | Expo, Apple 99 $/rok, Google 25 $ |
| 5 | `aplikacja-ze-strony`, `utrzymanie-aplikacji`, Maestro, red team (opinie ze sklepów, złośliwa paczka npm) | strona Weba → aplikacja z powiadomieniami | jak w 4 |

Współpraca z flotą: **Web** (PWA, pliki `.well-known`, baner, strona z polityką prywatności, brand kit), **Studio**
(opisy, grafiki do sklepu), **Wideograf** (film podglądowy aplikacji ze skilla `demo-strony`), **Sherlock** (aplikacje
konkurencji), **Łowca** (sygnał: firma bez aplikacji albo z porzuconą aplikacją).

## 12. Decyzje

| # | Pytanie | Rekomendacja |
|---|---|---|
| M1 | Stos | **Expo (React Native, TypeScript)**; Capacitor tylko dla stron z funkcjami natywnymi; PWA robi Web |
| M2 | Czyje konta | **Zawsze właściciela** (Apple, Google, Expo); tak każą wytyczne 4.2.6 i 4.3 |
| M3 | Podgląd na telefonie | **EAS Update + QR w Expo Go** (konto Expo właściciela) oraz Metro przez Tailscale, gdy flota jest na VPS |
| M4 | Lokalne budowanie Androida | **Opcjonalny dodatek**, domyślnie EAS w chmurze; włączenie po pomiarze RAM |
| M5 | iOS bez Maca | **EAS Build** (15 buildów/mies. za darmo); GitHub Actions jako zapas |
| M6 | Nazwa | `jarvo-mobile`, „Twórca aplikacji”, pokój „Pracownia aplikacji” |
| M7 | Kolejność | **Etap 1 najpierw** (audyt bez kont daje wartość od razu), potem 2 i 3, wydanie na końcu |

## 13. Źródła (sprawdzone 2026-10-01)

Expo: [wersje](https://docs.expo.dev/versions/latest/), [cennik](https://expo.dev/pricing), [Expo Go z logowaniem](https://expo.dev/changelog/expo-go-57-login),
[MCP](https://docs.expo.dev/eas/ai/mcp/), [skille](https://github.com/expo/skills). Apple: [wytyczne](https://developer.apple.com/app-store/review/guidelines/),
[nadchodzące wymagania](https://developer.apple.com/news/upcoming-requirements/), [DSA](https://developer.apple.com/help/app-store-connect/manage-compliance-information/manage-european-union-digital-services-act-trader-requirements/),
[zrzuty](https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications/), [usuwanie konta](https://developer.apple.com/support/offering-account-deletion-in-your-app/).
Google: [docelowe API](https://developer.android.com/google/play/requirements/target-sdk), [12 testerów](https://support.google.com/googleplay/android-developer/answer/14151465),
[Data safety](https://support.google.com/googleplay/android-developer/answer/10787469), [grafiki](https://support.google.com/googleplay/android-developer/answer/9866151),
[API publikowania](https://developers.google.com/android-publisher/edits). Testy: [Maestro](https://github.com/mobile-dev-inc/maestro),
[emulator i KVM](https://developer.android.com/studio/run/emulator-acceleration). PWA: [WebKit, web push](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
Rynek: [przegląd kreatorów aplikacji AI](https://thenextweb.com/news/vibe-coding-apple-app-store-surge-crackdown).

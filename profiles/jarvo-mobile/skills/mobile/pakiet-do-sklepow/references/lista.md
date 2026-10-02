# Lista kontrolna: 44 punkty i kto poprawia

Źródło prawdy to `PUNKTY` w `scripts/sklep_check.py` (dowody, progi, poprawki) i `docs/MOBILE.md` §8 w repo floty.
auto = błąd blokuje wysłanie; pół = dowody od skryptu, ocena i potwierdzenie człowieka; ręcznie = konsola sklepu.

## A. Konto i tożsamość

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 1 | ręcznie | wysyła właściciel ze swoich kont Apple i Google; agent jako członek zespołu | właściciel | Apple 4.2.6, 5.6.2 |
| 2 | ręcznie | status przedsiębiorcy DSA zweryfikowany w App Store Connect | właściciel | Apple: wymagania DSA |
| 3 | pół | branża regulowana → wysyła podmiot prawny, dokumenty w notatkach | właściciel + agent | Apple 5.6.2 |

## B. Build i konfiguracja

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 4 | auto | identyfikatory iOS i Android w odwrotnej notacji domeny, nie przykładowe | agent (aplikacja.yaml) | App Store Connect, Google Play |
| 5 | auto | wersja wyższa niż w sklepie, numery buildów rosną same | agent | EAS, App Store Connect |
| 6 | auto | Xcode ≥ 26, iOS od minimum SDK, targetSdkVersion ≥ 36 | agent (SDK, EAS) | Apple, Google (docelowe API) |
| 7 | auto | biblioteki .so (64-bit) wyrównane do 16 KB | agent (aktualizacja bibliotek) | Google (strony pamięci 16 KB) |
| 8 | auto | bez debug, bez ruchu bez TLS, bez localhost i serwerów testowych w paczce | agent | Apple 2.1, 2.5.1 |
| 9 | auto | ustawione ios.config.usesNonExemptEncryption | agent | Apple: eksport szyfrowania |
| 10 | auto | expo-doctor i expo install --check bez błędów | agent | Expo |

## C. Uprawnienia i prywatność

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 11 | auto | każdy moduł z uprawnieniem ma opis w Info.plist | agent (profil zgodności) | Apple 5.1.1(ii) |
| 12 | auto | opisy uprawnień po polsku, ≥ 40 znaków, bez ogólników | agent (powody) | Apple 5.1.1(ii) |
| 13 | auto | brak zbędnych uprawnień (Info.plist i manifest wobec kodu) | agent (`false` we wtyczce, blockedPermissions) | Apple 5.1.1(iii), Google: uprawnienia |
| 14 | pół | uprawnienia wymagające deklaracji w Play Console oznaczone | właściciel (Play Console) | Google: uprawnienia wrażliwe |
| 15 | auto | UIBackgroundModes tylko używane w kodzie | agent | Apple 2.5.4 |
| 16 | auto | manifest prywatności z powodami dla API z listy Apple | agent (ios.privacyManifests) | Apple: manifest prywatności |
| 17 | pół | szkic etykiety prywatności i Data safety z inwentarza bibliotek; ATT przy śledzeniu | właściciel (formularze) na szkicu agenta | Apple 5.1.2, Google: Data safety |
| 18 | pół | zewnętrzne AI → informacja i zgoda, zgłaszanie odpowiedzi | agent | Apple 5.1.2(i), Google: treści z AI |
| 19 | pół | prośba o uprawnienie nie blokuje pierwszego ekranu | agent | Apple 5.1.2(i) |

## D. Konta i logowanie

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 20 | auto | polityka prywatności: 200, nazwa firmy, po polsku, podlinkowana w aplikacji | jarvo-web (strona) + agent | Apple 5.1.1(i), Google |
| 21 | auto | strona wsparcia: 200, e-mail albo telefon | jarvo-web | App Review: wsparcie |
| 22 | auto | konta → „Usuń konto” w aplikacji i działający adres w sieci | agent + jarvo-web | Apple 5.1.1(v), Google: usuwanie konta |
| 23 | auto | logowanie Google/Facebook → Zaloguj się przez Apple | agent | Apple 4.8 |
| 24 | pół | katalog i informacje dostępne bez logowania | agent | Apple 5.1.1(v) |
| 25 | auto | konto demo dla recenzji, bez SMS i 2FA | właściciel (konto) + agent | Apple 2.1, Google: dane logowania |

## E. Treść i funkcje

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 26 | auto | brak tekstów zastępczych, TODO, „Wkrótce”, example.com, danych z szablonu | agent / jarvo-studio | Apple 2.1 |
| 27 | auto | linki w aplikacji i metadanych działają; pliki linków pasują do aplikacji | agent / jarvo-web | Apple 2.1 |
| 28 | pół | to nie okno na stronę: mało WebView, funkcje natywne | agent (plan) | Apple 4.2, 4.2.2, Google: spam |
| 29 | pół | podobieństwo do innych aplikacji floty poniżej progu | agent (własny wygląd) | Apple 4.3, Google: spam |
| 30 | auto | treści cyfrowe tylko przez zakupy w aplikacji; Stripe/P24/PayU/BLIK za towary i usługi | agent (profil płatności) | Apple 3.1.1, 3.1.3(e) |
| 31 | auto | treści użytkowników → zgłaszanie, blokowanie, regulamin, kontakt | agent | Apple 1.2, Google: UGC |
| 32 | pół | aktualizacje bez recenzji: polityka fingerprint, tylko poprawki | agent | Apple 2.5.2, Google: nadużycia |
| 33 | ręcznie | przejście na prawdziwym iPhonie i Androidzie, IPv6, raport przedpremierowy, TestFlight | właściciel + agent | Apple 2.1, 2.5.5 |

## F. Grafiki

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 34 | auto | ikona iOS 1024 bez alfy, ikona adaptacyjna Androida, ekran startowy | agent (`aplikacja.py ustaw`) | Expo: ikony |
| 35 | auto | ikona Google 512×512 ≤ 1 MB, grafika promocyjna 1024×500 bez alfy | agent (`pakiet.py grafiki`) | Google: grafiki |
| 36 | auto | zrzuty w wymiarach i liczbie sklepów, bez alfy | agent (`pakiet.py zrzuty`) | Apple: zrzuty, Google: grafiki |
| 37 | pół | zrzuty pokazują aplikację w użyciu; na iOS bez „Android” | agent + jarvo-studio | Apple 2.3.3, 2.3.10 |
| 38 | ręcznie | grafiki zrobione z pomocą AI oznaczone w Play Console | właściciel | Google: treści z AI |

## G. Metadane

| # | Tryb | Sprawdzenie | Kto poprawia | Podstawa |
|---|---|---|---|---|
| 39 | auto | limity znaków metadanych | jarvo-studio / agent | Apple, Google: metadane |
| 40 | auto | słowa kluczowe ≤ 100 bajtów, bez nazwy aplikacji, firmy i konkurencji | jarvo-studio / agent | Apple 2.3.7 |
| 41 | auto | bez zakazanych słów: obce platformy, „#1”, „najlepsza”, „darmowa”, rabaty, emoji, WIELKIE LITERY | jarvo-studio / agent | Apple 2.3.10, Google: metadane |
| 42 | auto | karta i nazwa w wersji pl-PL | agent (`pakiet.py szkic`) | App Store Connect, Play Console |
| 43 | ręcznie | kwestionariusz wieku Apple; IARC, grupa docelowa, reklamy, Data safety w Google | właściciel | Apple, Google: kontrole przed recenzją |
| 44 | pół | notatki dla recenzenta po angielsku: funkcje, ścieżka testu, konto demo | agent | Apple 2.3.1(a) |

Bez buildu punkty 6, 7 i 16 (część także 8 i 13) mają „?”: skrypt sprawdza je na `--aab` / `--ipa` z `out/build/`.
Każde odrzucenie dopisuje punkt (skill `odrzucenie`, etap 5) razem z testem na celowo zepsutej aplikacji.

# Kryteria audytu mobilnego

source: App Store Review Guidelines (2026-06-08), Apple Developer: Supporting associated domains, Android: Verify App Links,
Google Play: Target API level requirements, Data safety, Account deletion; iTunes Search API
reviewed: 2026-10-01

Statusy: ✓ zgodne · ✗ błąd (traci klientów albo grozi problemem w sklepie) · ⚠ do poprawy · ? nie dało się sprawdzić ·
ℹ informacja · — nie dotyczy.

## App Store (`IOS-*`, dla każdej aplikacji firmy)

| ID | Co sprawdza | Progi | Dlaczego |
|---|---|---|---|
| IOS-SWIEZOSC | data ostatniej wersji (iTunes Lookup) | ✓ ≤ 6 mies., ⚠ 6–12, ✗ > 12 | Apple usuwa aplikacje długo nieaktualizowane, które przestają działać na nowych systemach; klienci widzą datę w karcie |
| IOS-OCENA | średnia i liczba ocen w polskim sklepie | ✓ ≥ 4,5 i ≥ 20 ocen, ⚠ 4,0–4,5 albo mało ocen, ✗ < 4,0 | ocena decyduje o instalacji; prośba o ocenę po udanej akcji (expo-store-review), nigdy przy starcie |
| IOS-PL | język polski w aplikacji (`languageCodesISO2A`) | ✓ PL jest | klient z Polski dostaje interfejs po polsku; opisy uprawnień też po polsku |
| IOS-OPIS | opis w karcie po polsku (lookup z `lang=pl_pl`) | ✓ polski tekst | pierwsze 3 linijki widać bez rozwijania; 2.3 (metadane) |
| IOS-ZRZUTY | liczba zrzutów iPhone | ✓ ≥ 5, ⚠ 3–4, ✗ < 3 (limit 10) | zrzuty sprzedają; muszą pokazywać aplikację w użyciu (2.3.3) |
| IOS-NOWOSCI | „Co nowego” | ⚠ ogólnik („poprawki i usprawnienia”) | zmarnowana reklama; przy dużych zmianach Apple wymaga konkretów (2.3.12) |
| IOS-STRONA-DEWELOPERA | strona sprzedawcy w karcie = domena firmy | ⚠ inna albo brak | wiarygodność; spójność marki |
| IOS-DSA | status przedsiębiorcy (Digital Services Act) ze strony apps.apple.com | ✓ trader, ⚠ „nie jest przedsiębiorcą” | firma prowadząca działalność ma być przedsiębiorcą; w UE na karcie widać jej dane kontaktowe |
| IOS-PRYWATNOSC | etykiety prywatności i link do polityki | ✗ „No Details Provided”, ⚠ brak polityki | bez etykiet nie przejdzie żadna aktualizacja; 5.1.1 |
| IOS-OPINIE | ostatnie 50 opinii (RSS): średnia, tematy skarg | ℹ | trend bywa inny niż średnia ze wszystkich lat |

## Google Play (`AND-*`)

| ID | Co sprawdza | Progi | Dlaczego |
|---|---|---|---|
| AND-SWIEZOSC | „Ostatnia aktualizacja” | ✗ przed 1.09.2024, ⚠ przed 31.08.2025 albo > 6 mies., ✓ reszta | istniejące aplikacje muszą celować w API ≥ 35, inaczej nowi użytkownicy nowszych Androidów ich nie widzą; aktualizacje od 31.08.2026 w API 36 |
| AND-OCENA | średnia i liczba ocen (JSON-LD strony) | jak iOS | jak iOS |
| AND-DATA-SAFETY | sekcja Bezpieczeństwo danych | ✗ „deweloper nie podał informacji” | formularz obowiązkowy; niezgodność = blokada aktualizacji |
| AND-USUWANIE | „Możesz poprosić o usunięcie danych” | ⚠ brak (gdy aplikacja zbiera dane) | aplikacja z kontami musi mieć usuwanie w aplikacji i link w sieci |
| AND-STRONA-DEWELOPERA | strona autora = domena firmy | ⚠ inna | jak iOS |

## Linki strona → aplikacja (`LINK-*`)

| ID | Co sprawdza | Błąd, gdy | Poprawka (Web) |
|---|---|---|---|
| LINK-IOS | `https://<host>/.well-known/apple-app-site-association`: 200, JSON, bez przekierowań, `applinks` z appID `TEAMID.bundleId` aplikacji | 404, HTML zamiast JSON, przekierowanie, brak appID | plik na dokładnym hoście, z którego wychodzą linki (www i bez www to dwa hosty) |
| LINK-IOS-TYP | Content-Type pliku AASA | nie `application/json` (⚠) | nagłówek serwera |
| LINK-IOS-CDN | kopia w CDN Apple (`app-site-association.cdn-apple.com/a/v1/<host>`) zgodna z plikiem | różnica (⚠) | telefony biorą plik z CDN; odświeża się sam po naprawie |
| LINK-ANDROID | `https://<host>/.well-known/assetlinks.json`: 200, `application/json`, bez przekierowań, `handle_all_urls` dla pakietu + odcisk SHA-256 | 404, zły typ, przekierowanie, brak pakietu | wpis z odciskiem klucza podpisu z Play Console (App signing) |

Skutek błędu: link z kampanii, e-maila albo SMS-a otwiera stronę w przeglądarce zamiast aplikacji (gorsza konwersja,
klient musi się logować drugi raz).

## Strona (`WWW-*`)

| ID | Co sprawdza | Uwagi |
|---|---|---|
| WWW-SKLEPY | odznaki/linki do sklepów na stronie | gdy firma ma aplikację |
| WWW-BANER | `<meta name="apple-itunes-app" content="app-id=…">` wskazuje właściwą aplikację | ✗, gdy wskazuje inną (np. starą) |
| WWW-PWA | manifest: nazwa, ikony 192 i 512, `start_url`, `display` standalone/fullscreen/minimal-ui | ℹ, gdy jest aplikacja natywna; ⚠ bez aplikacji (tania PWA) |
| WWW-IKONA | `apple-touch-icon` | ikona po dodaniu strony do ekranu iPhone'a |
| WWW-PRYWATNOSC | link do polityki prywatności na stronie głównej, HTTP 200 | wymóg obu sklepów i RODO |
| WWW-USUWANIE | strona o usuwaniu konta | Google Play wymaga linku w sieci dla aplikacji z kontami |

## Granice
- Tylko dane publiczne. iTunes API ~20 zapytań/min (skrypt robi pauzę 4 s, także między procesami).
- Google Play: tylko `/store/apps/details` (robots.txt zabrania m.in. `/store/apps/datasafety` i wyszukiwarki).
- Strony firm: robots.txt szanowany; pliki `/.well-known/` są dla maszyn i pobieramy je zawsze.
- Audyt nie widzi środka aplikacji, konsol sklepów (prywatność, wiek, konto demo) ani opinii Google Play.

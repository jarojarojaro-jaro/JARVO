# Rozwój floty: plan dopracowania agentów i nowi specjaliści

Stan: **plan do analizy (research 2026-10-01).** Wdrożone: naprawy z §3 punkty 1, 3 i 4. Nowi agenci: dwie rundy
propozycji odłożone (§6); osobno projekt Twórcy aplikacji w [MOBILE.md](MOBILE.md). Reszta czeka na decyzje. Wersje bibliotek, limity API i daty
przepisów sprawdzono 2026-10-01; przed wdrożeniem każdego punktu sprawdzamy je jeszcze raz. Uwagi prawne to
wskazówki do projektu, nie porada prawna.

## 1. Zasada: wartość, nie objętość

Miarą jest to, co już robią Web i Wideograf: **gotowy, sprawdzalny w sekundę wynik, którego zwykły czat
z AI nie da, bo nie ma narzędzi, danych ani pamięci.** Web daje `llms.txt`, sitemapę, favicony i WebP po
26-punktowej liście kontrolnej. Wideograf tnie długie nagranie na rolki z napisami i oddaje je do
wbudowanego edytora.

Z tego wynikają cztery reguły tego planu:
- **Każdy agent dostaje jedną „sygnaturę”:** wynik, który można komuś pokazać i od razu sprawdzić.
- **Kroki opisane tylko w prompcie zamieniamy na skrypty** tam, gdzie decyduje o jakości (sprawdzenia,
  limity, obliczenia). Model pisze i ocenia, skrypt liczy i weryfikuje.
- **Bez nowych usług działających cały czas** na VPS 8 GB, chyba że pomiar pokaże, że się mieszczą.
- **Uprawnienia ogranicza klucz, nie prompt:** tokeny tylko do odczytu, poczta bez prawa wysyłki, wydatki
  i publikacje zawsze przez zgodę (A2).

## 2. Gdzie jesteśmy (audyt repo)

| Agent | Własne skille | Skrypty | Skille zewnętrzne | Głębia narzędzi | Werdykt |
|---|---|---|---|---|---|
| `jarvo-web` | 10 | 9 (~1 400 linii) | 58 | wysoka | wzorzec: sprawdzenia od początku do końca w kodzie |
| `jarvo-wideo` | 16 | 21 + biblioteka (~7 400 linii) + edytor | 59 | wysoka | pełna linia produkcyjna |
| `jarvo-lowca` | 6 | 4 + biblioteka (~1 100 linii) | 0 | średnio-wysoka | prawdziwe dane, ale błąd w ocenie leadów i nigdy nie uruchomiony na prawdziwej ofercie |
| `jarvo-ads` | 10 | 4 (~550 linii) | 6 | nisko-średnia | dobra matematyka testów; Skarbiec nie istnieje, więc 3 skille nie działały wcale, a 4 tylko na eksporcie CSV |
| `jarvo-sherlock` | 7 | 3 (~290 linii) | 16 | nisko-średnia | weryfikacja źródeł tylko w prompcie; dziś blisko zwykłego „deep research” |
| `jarvo-studio` | 6 | 2 (~160 linii) + 1 szablon | 23 | nisko-średnia | renderuje i mierzy wymiary, ale tekstu, układu i publikacji kod nie sprawdza |
| `jarvo-mobile` | 10 | 18 + biblioteka (~7 300 linii) + szablon Expo | 20 | wysoka | od decyzji „natywna czy PWA” po sklep; podgląd w Expo Go czeka na organizację Expo właściciela |
| `jarvo-reka` | 4 | 2 (~190 linii) | 4 + wszystkie skille floty | niska | generalista bez dostępu do Twojej poczty, kalendarza i dokumentów |

## 3. Do naprawy od razu (błędy znalezione przy audycie)

Te punkty nie wymagają decyzji, tylko poprawki:

1. ✅ **Łowca odrzucał dobre leady** (naprawione 2026-10-01). Kryterium ICP, którego sygnał nie dotyczy (CPV przy
   KRS, PKD przy przetargu), liczyło się jako niespełnione, a słowa kluczowe porównywały się dosłownie („strona”
   nie znajdowała „strony”). Przy przykładowym profilu z progiem 1,0 odpadały idealna nowa spółka IT i pasujący
   przetarg. Teraz liczą się tylko kryteria sprawdzalne (reszta w kolumnie `niesprawdzone`), słowa po rdzeniu.
2. **Łowca: prawo komunikacji elektronicznej jest opisane za słabo.** [LEADY.md](LEADY.md) §3 mówi o zgodzie
   „do konkretnej osoby”. Od 10.11.2024 art. 398 PKE wymaga uprzedniej zgody na marketing e-mailem
   i telefonem do każdego abonenta, także firmy i adresu ogólnego typu `biuro@`. Najcenniejsze są więc
   leady, które same proszą o oferty (przetargi, zapytania ofertowe), bo odpowiedź na nie nie jest
   niezamówiona.
3. ✅ **Ręka kierowała zadania po ręcznej, nieaktualnej tabeli** (naprawione 2026-10-01). Tabelę „komu oddać” generuje
   teraz build z pola `oddaj_gdy` każdego specjalisty w `fleet.yaml`. Walidator nie przepuści aktywnego specjalisty bez
   tego pola ani bez miejsca we wzorcach misji Jarva, a `make new-agent` od razu dopisuje pole do uzupełnienia.
4. ✅ **Ads miał martwe ścieżki** (naprawione 2026-10-01): `podlacz-konto`, `start-kampanii` i `optymalizacja` wołały
   Skarbiec, którego nie ma. Mają teraz `metadata.jarvo.wymaga: [skarbiec]`, więc do czasu Skarbca nie trafiają do profilu,
   a SOUL agenta dostaje wygenerowaną listę tego, czego nie zrobi. Walidator odrzuca skill wołający polecenia Skarbca bez
   tej deklaracji. Zostaje: [ADS.md](ADS.md) podaje Graph API v25, a od 29.07.2026 jest v26.
5. **Sherlock:** wtyczka OpenAlex od lutego 2026 wymaga klucza (`OPENALEX_API_KEY`), a `sources.py --archive`
   zapisuje sam HTML, choć opis obiecuje też tekst.
6. **Studio i dokumentacja:** [TOOLBOX.md](TOOLBOX.md) wymienia Satori i resvg, a renderuje Playwright.
   Postiz od wersji 2.12 potrzebuje Temporal, Postgresa i Redisa (2–4 GB), więc nie zmieści się jako
   „lekki sidecar” obok floty.

## 4. Fundament wspólny: polskie rejestry w jednym module

Pięciu agentów (Łowca, Sherlock, Ręka i dwóch nowych) potrzebuje tych samych sprawdzeń firmy. Zamiast
pięciu kopii: jeden moduł `shared/scripts/rejestry_pl.py` (sama biblioteka standardowa), z wynikiem zawsze
z datą i surowym JSON-em jako dowodem.

| Źródło | Co daje | Dostęp | Limit |
|---|---|---|---|
| [KRS Open API](https://prs.ms.gov.pl/krs/openApi) | odpis aktualny i pełny, biuletyn, wzmianki o sprawozdaniach | bez klucza | bez podanego |
| [Biała lista VAT](https://www.gov.pl/web/kas/api-wykazu-podatnikow-vat) | status VAT, rachunki, `requestId` jako dowód | bez klucza | `check` 5 000/dzień, `search` 100/dzień |
| [NBP API](https://api.nbp.pl) | kurs z dnia roboczego przed datą faktury | bez klucza | — |
| [VIES](https://ec.europa.eu/taxation_customs/vies/) | numer VAT kontrahenta z UE | bez klucza | — |
| [GUS REGON BIR](https://api.stat.gov.pl/Home/RegonApi) | dane firm spoza KRS, nowe podmioty dziennie | darmowy klucz e-mailem | 3/s, 6 000/h |
| [CEIDG API v3](https://dane.biznes.gov.pl) | jednoosobowe działalności | darmowy token | 1 000/h |

Łowca ma już `krs.py`, więc moduł zaczyna od niego. Nakład: S.

## 5. Plan dla każdego agenta

### 5.1 Łowca leadów: „karta leada”

**Sygnatura:** dla każdego leada jedna karta: dlaczego teraz (z datowanymi źródłami), co zaproponować,
flagi ryzyka (status VAT, link do Krajowego Rejestru Zadłużonych), **legalny kanał kontaktu** według art. 398
(odpowiedź na zapytanie, list, spotkanie albo „potrzebna zgoda”), gotowe pierwsze zdanie i wstępnie
wypełniona informacja z art. 14 RODO. Dla pięciu najlepszych: jednostronicowy mini-audyt strony od Weba.
Raz w tygodniu: przegląd nowych sygnałów, zbliżających się terminów przetargów i wygranych konkurencji.

| # | Co | Po co | Nakład |
|---|---|---|---|
| 1 | ✅ Poprawka oceny ICP i test (§3) | bez niej najlepsze leady odpadały | zrobione |
| 2 | [Baza Konkurencyjności](https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/) + [lista projektów UE 2021–27](https://funduszeeuropejskie.gov.pl/raporty-i-analizy/lista-projektow-realizowanych-z-funduszy-europejskich-w-polsce-w-latach-2021-2027/) | firmy z dotacją muszą tu publikować zapytania ofertowe: budżet jest, a odpowiedź jest legalna | M (API nieopisane, trzeba je rozpoznać) |
| 3 | Porównanie odpisu pełnego KRS | co dokładnie się zmieniło: kapitał, nowe PKD, oddziały, przeprowadzka, brak złożonego sprawozdania | S |
| 4 | Nowe firmy z REGON BIR (także jednoosobowe) | świeże podmioty codziennie; dane minimalne, tylko po filtrze ICP (kara UODO dla Bisnode, art. 14) | S–M |
| 5 | Rekrutacje z kanałów firmy | JSON-LD `JobPosting` na stronie, Greenhouse, Lever, Recruitee, Teamtailor RSS: bez klucza i bez scrapowania portali | S |
| 6 | Sygnały „potrzebuje usługi” | wersje po końcu wsparcia ([endoflife.date](https://endoflife.date)), podatne biblioteki JS (retire.js), certyfikat, HTTPS, [CrUX](https://developer.chrome.com/docs/crux/api)/PageSpeed bez lokalnego Chrome | S–M |
| 7 | Higiena kontaktów | `email-validator` (składnia + MX), etykiety `rola`/`osobowy`/`jednorazowy` ze źródłem; bez zgadywania adresów i sprawdzania przez SMTP | S |
| 8 | Skille zamiast nowych promptów | `prospecting`, `cold-email`, `customer-research` z marketingskills (już przypięte w locku, MIT) | S |
| 9 | Pierwsze prawdziwe uruchomienie na Twojej ofercie | [LEADY.md](LEADY.md) §6 krok 4 wciąż otwarty | S |

Odrzucone: LinkedIn i firmy wzbogacające dane (Proxycurl zamknięty po pozwie, kara CNIL dla Kaspr),
kupione bazy, scrapowanie pracuj.pl, automatyczne pobieranie z repozytorium sprawozdań (Incapsula),
wysyłka i sekwencje maili.

### 5.2 Ads: „audyt gotowości reklamowej” bez dostępu do konta

**Sygnatura:** raport ✓/✗ z gotowymi poprawkami do wklejenia, który klient sprawdzi, uruchamiając go jeszcze
raz. Działa, zanim ktokolwiek podłączy konto reklamowe.

| # | Co | Po co | Nakład |
|---|---|---|---|
| 1 | Audyt śledzenia (Playwright z obrazu, dwa przebiegi: przed zgodą i po „akceptuj”) | czy Pixel, GA4 i GTM działają, czy Consent Mode v2 wysyła `gcs`/`gcd`, czy tagi nie strzelają przed zgodą, czy `gclid`/`fbclid` przeżywają przekierowania; poprawki idą do Weba | S–M |
| 2 | Gotowość strony docelowej | PageSpeed i CrUX, polityka prywatności, działający formularz, zgodność komunikatu reklamy ze stroną | S |
| 3 | `kreacje.py`: kontrola kreacji przed startem | wymiary i czas (ffprobe), limity znaków Meta i Google z datowanego `specs.yaml`, strefy bezpieczne Reels, flagi Omnibusa i zakazanych obietnic | S |
| 4 | Biblioteka reklam Meta dla PL | najdłużej emitowane reklamy konkurencji, kąty, formaty, zasięg w UE; brief dla Studio (token bez prawa do wydatków; wygasa co 60 dni) | S z linkami, M z API |
| 5 | `audyt.py` na eksportach CSV | kolumny daty i częstotliwości, reguły (2× CPA bez wyniku, zmęczenie kreacji, spadek CTR), wykresy PNG | S–M |
| 6 | Skarbiec, faza 1: tylko odczyt | statystyki z kont bez prawa do zmian (Meta `ads_read`, Google: użytkownik z rolą „tylko odczyt”) | M |
| 7 | Oficjalne MCP, tylko odczyt | [google-analytics-mcp](https://github.com/googleanalytics/google-analytics-mcp) (`analytics.readonly`, Apache-2.0); [google-ads-mcp](https://github.com/googleads/google-ads-mcp) dopiero przy roli „tylko odczyt” | S |
| 8 | Listy kontrolne z [claude-ads](https://github.com/AgriciDaniel/claude-ads) (MIT) | tylko wybrane: strona docelowa, konkurencja, śledzenie po stronie serwera, walidacja | S |

Uczciwie: modele marketing mix (Meridian, PyMC-Marketing, Robyn) potrzebują 2–3 lat danych tygodniowych
i są za ciężkie; `eksperyment.py` i `planer.py` wystarczą małej firmie. Odrzucone: scrapowanie bibliotek
reklam, płatne API scraperów, nieoficjalne MCP z tokenami do zapisu, klucze mogące wydawać pieniądze w kontenerze.

### 5.3 Prawa ręka: „biuro w Telegramie”

**Sygnatura:** poranny brief o 7:00: kalendarz i kolizje, pilne maile, terminy z najbliższych 7 dni,
ostrzeżenia pogodowe, opóźnienia pociągów; do tego szkice odpowiedzi czekające w skrzynce i notatki ze
spotkań zamienione w zadania.

| # | Co | Po co | Nakład |
|---|---|---|---|
| 1 | Poczta tylko ze szkicami | [mcp-email-server](https://github.com/Wh1isper/mcp-email-server) (BSD-3) z samym IMAP: zapis szkicu bez SMTP; M365: [ms-365-mcp-server](https://github.com/Softeria/ms-365-mcp-server) bez uprawnienia `Mail.Send`; triage skillem `email-inbox-triage` z Hermesa i przypomnienia „brak odpowiedzi od N dni” | M |
| 2 | Kalendarz | Google: skill `google-workspace` tylko z kalendarzem (aplikacja OAuth w trybie produkcyjnym, inaczej token wygasa po 7 dniach); iCloud/Nextcloud: `caldav`; zaproszenia dla innych = A2 | S–M |
| 3 | Terminy ZUS, PIT, VAT bez tokenów | zadanie crona bez modelu (`no_agent`), przesunięcia na dzień roboczy z `holidays` | S |
| 4 | Poranny brief | składa 1–3 + [ostrzeżenia IMGW](https://danepubliczne.imgw.pl/pl/apiinfo) + [opóźnienia PLK](https://pdp-api.plk-sa.pl/) | S |
| 5 | Spotkanie → notatka → zadania | Parakeet (już jest) + `document-to-action-items` z Hermesa + szablon protokołu; szkic maila z podsumowaniem | S |
| 6 | Paragony i faktury zagraniczne do tabeli | zdjęcie z Telegrama → JSON (data, NIP, netto/VAT/brutto) ze sprawdzeniem sumy kontrolnej NIP → CSV w skarbcu | S |
| 7 | Przegląd umowy po polsku | lista ryzyk: kary umowne, limit odpowiedzialności, pola eksploatacji przy przeniesieniu praw, umowa powierzenia (art. 28 RODO), termin płatności B2B; na bazie `review-contract` z [knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) (Apache-2.0) | S–M |
| 8 | Twój głos w szkicach | `executive-voice` i `executive-playbook` z [SortedEA/skills](https://github.com/SortedEA/skills) (MIT) | S |
| 9 | Zadania | Todoist (oficjalne zdalne MCP) albo Notion, jeśli ich używasz; inaczej `TASKS.md` w skarbcu bez nowej usługi | S |
| 10 | „Czy mogę to zapłacić?” | NIP i rachunek na białej liście VAT przed przelewem (powyżej 15 tys. zł rachunek spoza listy to brak kosztu i solidarna odpowiedzialność za VAT), kurs NBP do faktur zagranicznych; wspólny moduł z §4 | S |
| 10b | e-Doręczenia | przekazywanie maila z powiadomieniem na Telegram: od dziś (1.10.2026) każda firma z CEIDG musi mieć adres, a nieodebrana przesyłka po 14 dniach uznaje się za doręczoną | S |
| 11 | `pack.py` v2 (tabela kierowania już naprawiona, §3) | paczka czyta artefakty z kart kanbana, sprawdza linki w `INDEX.md` i wyłapuje niezgodności między kartami (nazwy, ceny, adresy) | S |

**Bezpieczeństwo poczty (reguła dwóch).** Czytanie maili łączy prywatne dane, obce treści i kanały
wyjścia. Dlatego triage działa jako zadanie crona bez przeglądarki, sieci i terminala, a jedyne wyjścia to
szkic w skrzynce i wiadomość do Ciebie. Ograniczenia siedzą w poświadczeniach: brak hasła SMTP, brak
`Mail.Send`. Uwaga: zakres Gmaila `gmail.compose` pozwala też wysłać, więc przy Gmailu tylko-szkice
zapewnia lista narzędzi serwera, nie klucz.

Odrzucone: wyszukiwarki lotów przez API (Amadeus Self-Service zamknięty 17.07.2026), kupowanie biletów PKP,
automatyzacja ePUAP, diarizacja na CPU, własny Nextcloud tylko dla kalendarza.

### 5.4 Sherlock: „raport z dowodami”

**Sygnatura:** każdy cytat w raporcie da się kliknąć i od razu zobaczyć podświetlony w źródle, z kopią
w Wayback, datą i hashem, a skrypt potwierdza, że cytat naprawdę tam jest.

| # | Co | Po co | Nakład |
|---|---|---|---|
| 1 | `weryfikuj.py` + rozbudowa `sources.py` | link `#:~:text=` z podświetleniem, kopia w Wayback (darmowy klucz archive.org), dopasowanie cytatu do zapisanego tekstu, SHA-256, niezależność domen; poprzednia wersja strony z Wayback CDX | S |
| 2 | Prawo PL i UE | [prawo-pl-eli](https://github.com/jamarpl21/prawo-pl-eli) (MIT, 8 skilli: Sejm ELI, EUR-Lex, SAOS, CBOSA, UODO); projekt młody, więc przypięta rewizja i przegląd; ELI daje akty od 2025 tylko jako PDF (`poppler-utils` do obrazu) | S |
| 3 | Rejestry firm | wspólny `rejestry_pl.py` (§4) | — |
| 4 | Statystyki z pochodzeniem | [GUS BDL](https://api.stat.gov.pl/Home/BdlApi) i Eurostat: wartość, zmienna, jednostka, rok i adres zapytania, które ją odtwarza | S–M |
| 5 | Nauka i wcześniejsze fact-checki | skill `paper-lookup` z [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) (MIT, tylko ten jeden), wycofane publikacje z Crossref, Google Fact Check Tools | S |
| 6 | `seo_fraz.py` i stan monitoringu | podpowiedzi wyszukiwarki i zrzut top 10 do `research-seo`; plik stanu między przebiegami `monitoring` | S–M |
| 7 | (opcjonalnie) [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | zmiany na stronach z diffem i kopią w Wayback; bez kontenera Chrome, po pomiarze RAM | M |

Odrzucone: `mcp-wayback-machine` (licencja niekomercyjna), `waybackpy` (martwy od 2022), płatne odwrotne
wyszukiwanie obrazów, pakiety OSINT profilujące ludzi, PyMuPDF (AGPL; zamiast niego pdfplumber).

### 5.5 Studio: „pakiet startowy kampanii”

**Sygnatura:** obok grafik i tekstów pliki, które od razu działają: `utm.csv` z linkami, kody QR,
`kalendarz.ics` do zaimportowania, `alt.csv` z opisami alternatywnymi, `licencje.csv` ze źródłem każdego
zasobu, karuzela jako PDF dla LinkedIna i PNG dla Instagrama.

| # | Co | Po co | Nakład |
|---|---|---|---|
| 1 | Pliki pakietu | `segno` (QR), `icalendar` + `holidays`, UTM, alt text (Instagram API przyjmuje `alt_text`) | S |
| 2 | `brand_lint.py` | kontrast WCAG AA, strefy bezpieczne 9:16, dozwolone fonty; polska typografia: twarda spacja po „w, z, i, o, u, a”, cudzysłowy „”, półpauzy | S |
| 3 | `copy_check.py` | sito frazesów AI (dziś tylko w prompcie), limity znaków platform, długość hooka | S |
| 4 | Biblioteka 8–10 szablonów | karuzela, PDF na LinkedIn, promocja, miniatura; sprawdzenie układu przy renderze (przepełnienie, minimalny font) | S–M |
| 5 | Zasoby z licencją i oznaczenie AI | [Openverse](https://api.openverse.org/v1/) i Pexels; IPTC `DigitalSourceType=trainedAlgorithmicMedia` w obrazach AI (exiftool), bo od 2.08.2026 obowiązuje art. 50 AI Act | S |
| 6 | (opcjonalnie) LanguageTool po polsku | własna instancja, 0,5–1 GB RAM: sieć na literówki i gramatykę, nie ocena stylu; tylko po pomiarze | M |
| 7 | Publikacja | Postiz poza VPS (osobny mały serwer albo Postiz Cloud) albo eksport ICS/CSV do ręcznego importu | S |

Odrzucone: pełny Postiz na VPS floty, Satori obok Chromium, Polotno (od 249 $/mies.), lokalne modele obrazów
na CPU, kolejne paczki angielskich skilli marketingowych.

### 5.6 Web i Wideograf

Bez zmian w tym planie: są wzorcem. Web dostaje tylko zlecenia od nowych agentów (poprawki z audytów
audytu zgodności (§6) i Ads).

## 6. Nowi specjaliści

Pierwsza runda propozycji (Rachmistrz, Handlowiec, Opiekun opinii, Inspektor) została odrzucona jako wymyślona na siłę.
Druga runda (research 2026-10-01) zaczyna od drugiej strony: **na co właściciele małych firm naprawdę tracą czas
i pieniądze** oraz **jakich „cyfrowych pracowników” ludzie faktycznie używają**, a nie jakie role da się wymyślić.

### 6.1 Dowody: gdzie boli

| Ból | Dane | Źródło |
|---|---|---|
| Oszustwa i phishing | 260 783 incydenty w 2025 (+152%), 97% to oszustwa; OLX i Allegro najczęściej podszywane | [CERT Polska 2025](https://www.nask.pl/aktualnosci/prawie-2-tys-zgloszen-kazdego-dnia-raport-cert-polska-za-2025-rok) |
| Fałszywe faktury | 32,8% firm MŚP dostało fałszywą fakturę albo fakturę ze zmienionym numerem konta | [BIK, raport antyfraudowy 2025](https://media.bik.pl/informacje-prasowe/860954/raport-antyfraudowy-bik-2025-rosnie-liczba-cyberatakow-na-firmy-i-instytucje) |
| Zaległe płatności | 84% firm ma klientów płacących po terminie, 30% czeka ponad 60 dni | [BIK, IV kw. 2025](https://media.bik.pl/informacje-prasowe/863321/84-firm-w-polsce-doswiadcza-opoznien-w-platnosciach-czas-odwrocic-ten-trend) |
| Faktury i KSeF | 74% firm miało problemy z KSeF w pierwszym miesiącu | [Grant Thornton, marzec 2026](https://grantthornton.pl/en/article/entrepreneurs-opinions-one-month-after-the-entry-into-force-of-ksef-report/) |
| Wiadomości od klientów | Allegro liczy odsetek odpowiedzi w 24 h do jakości sprzedaży (widoczność ofert); co czwarta rezerwacja w Booksy po zamknięciu salonu | [Allegro](https://adsup.pl/allegro-aktualnosci-dla-sprzedajacych/zmiany-w-jakosci-sprzedazy-od-1-pazdziernika-2025/), [Booksy](https://trends-pl.booksy.com/) |
| Biurokracja | 44% mikro i małych firm wskazuje ją jako barierę (+10 pkt) | [ZPP Busometr, I poł. 2026](https://zpp.net.pl/pesymizm-bierze-gore-najnowszy-busometr-zpp-ujawnia-trudna-rzeczywistosc-mikro-i-malego-biznesu/) |

Co ludzie naprawdę używają (twarde liczby mają tylko duże firmy): **obsługa wiadomości od klientów** (HubSpot Customer
Agent u 8 tys. klientów, agent Meta w WhatsApp i Instagramie: 10 mln rozmów tygodniowo) i **asystent właściciela**
(poczta, kalendarz, notatki; Lindy w 2026 zamienił cały zespół „AI pracowników” na jednego asystenta). Najgorsze dane
mają autonomiczni handlowcy wysyłający maile sami (70–80% rezygnacji po 3 miesiącach u 11x). Paczki z 12 „pracownikami”
(Sintra, Marblism) zbierają recenzje „ogólnikowe i wymagające codziennej poprawki”.

### 6.2 Decyzja: odłożone

**2026-10-01: druga runda też odłożona; na razie żadnych nowych agentów.** Rozważani byli:
- **Informatyk:** audyt domeny i poczty (SPF, DKIM, DMARC), domeny-sobowtóry z listą CERT, ocena podejrzanych maili.
- **Recepcja:** wiadomości od klientów z wielu kanałów, szkic odpowiedzi i zatwierdzenie na Telegramie. Research
  kanałów (co da się podłączyć: poczta, Allegro, SMS, Instagram tak; Messenger i WhatsApp po konfiguracji Meta;
  czat Google, LinkedIn, TikTok w UE nie) jest w historii repo, commit `487626e`.
- **Menedżer sklepu:** jakość sprzedaży na Allegro, parametry ofert i GPSR, marża, Merchant Center.

Dane z §6.1 zostają jako punkt odniesienia, gdy wrócimy do tematu.

### 6.3 Pomysły na skille (odłożone razem z agentami, do decyzji przy rozwoju istniejących agentów)

Część bólów jest prawdziwa, ale nie uzasadnia osobnego profilu:

| Ból | Gdzie | Co dokładnie |
|---|---|---|
| Zaległe płatności (84% firm) | Ręka, skill `naleznosci` | przeterminowane faktury z programu do faktur (Fakturownia, inFakt, wFirma, iFirma mają API), szkice przypomnień, odsetki ustawowe i 40 euro rekompensaty; wysyłka A2 |
| Dotacje | Łowca, miesięczny skill | miesięczne zestawienia naborów (XLSX z funduszeeuropejskie.gov.pl) dopasowane do profilu firmy; ile zostało limitu de minimis z [SUDOP](https://sudop.uokik.gov.pl/search/aidBeneficiary) po NIP; szkolenia z Bazy Usług Rozwojowych |
| Tygodniowy raport biznesowy | Jarvo, rozbudowa `weekly-review` | GA4 (oficjalne MCP tylko do odczytu), Search Console, sprzedaż; „co się zmieniło i dlaczego” z dziennikiem floty |
| Newsletter | Studio | szkic newslettera z treści tygodnia jako kampania-szkic w GetResponse, MailerLite albo FreshMail; nigdy nie wysyła |
| Lokalne SEO | Web | spójność nazwy, adresu i telefonu, dane strukturalne LocalBusiness |
| Rekrutacja | Ręka | ogłoszenie zgodne z jawnością wynagrodzeń (Kodeks pracy od 24.12.2025) i klauzula RODO; bez oceniania CV (AI Act: wysokie ryzyko) |

Odrzucone także w drugiej rundzie: autonomiczny handlowiec wysyłający maile (najgorsze dane rynkowe, a Łowca celowo
niczego nie wysyła), telefoniczna recepcja (recenzje „robotyczna”; test CallBay zostaje osobnym tematem), optymalizator
cen usług (brak danych), osobny agent dotacji (dla firmy usługowej większość miesięcy to „nic dla Ciebie”).

### 6.4 Audyt zgodności jako skill Weba (decyzja z pierwszej rundy)

 Web ma już Playwright, axe i nagłówki bezpieczeństwa,
więc dokładamy mu prawną część tego samego audytu:
- **Raport cookies:** co ładuje się przed zgodą, po „odrzuć” i po „akceptuj”, z HAR-em i zrzutami jako dowodem; czy
  „Odrzuć wszystkie” jest równie łatwe jak „Akceptuj”. Miarą jest poradnik UODO dla e-handlu (marzec 2025); art. 399 PKE
  przewiduje kary do 3% przychodu.
- **Szkic polityki prywatności i cookies** z faktycznie znalezionych narzędzi (GA4, Pixel), oznaczony
  „do weryfikacji przez prawnika”.
- **Formularze:** zaznaczone domyślnie zgody, osobna zgoda na każdy kanał (art. 398 PKE).
- **Sklep:** najniższa cena z 30 dni i opis weryfikacji opinii (Omnibus), dane producenta (GPSR od 13.12.2024), martwy
  link do platformy ODR (zamkniętej 20.07.2025).
- **Dostępność (EAA):** czy ustawa w ogóle dotyczy firmy (mikroprzedsiębiorcy usługowi są zwolnieni) i szkic deklaracji.
- **Narzędzia:** własny skrypt Playwright w `scripts/` Weba, [Open Cookie Database](https://github.com/jkwakman/Open-Cookie-Database)
  (Apache-2.0) do klasyfikacji cookies.
- **Granice:** to nie porada prawna; czyta tylko publiczne strony, audytów cudzych stron nie publikuje.
- **Wartość:** to samo co reszta audytu Weba: darmowy, sprawdzalny wynik, który otwiera rozmowę o usługach.
- **Nakład:** S–M. Część śledzenia (Pixel, Consent Mode) liczy wspólnie z audytem gotowości Ads (5.2 #1), żeby nie
  pisać tego dwa razy.

## 7. Kolejność

| Etap | Zakres | Nakład | Klucze i konta |
|---|---|---|---|
| A. Naprawy i fundament | §3 (punkty 1, 3 i 4 zrobione), `rejestry_pl.py` (§4) | 1–2 dni | brak |
| B. Sygnatury bez kont | Ads: audyt gotowości (5.2 #1–3); Łowca: karta leada (5.1 #2–8, potem #9 na Twojej ofercie); Sherlock: raport z dowodami (5.4 #1–5); Studio: pakiet startowy (5.5 #1–5) | ok. 2 tygodnie | darmowe: archive.org, OpenAlex, GUS BIR, PageSpeed |
| C. Web: audyt zgodności | §6.4 | 3–5 dni | brak |
| D. Ręka z Twoimi kontami | 5.3 #1–11 | ok. tydzień | poczta, kalendarz (Twoja zgoda na każde) |
| E. Konta reklamowe | Skarbiec faza 1, MCP tylko do odczytu (5.2 #6–7) | ok. tydzień | Meta `ads_read`, Google rola „tylko odczyt” |

Każdy etap kończy się tak jak dotąd: testy, evals, red team dla nowych wejść z sieci, wdrożenie i próba
w działającym kontenerze, dokumentacja.

## 8. Decyzje dla Ciebie

| # | Pytanie | Rekomendacja |
|---|---|---|
| R1 | Kolejność etapów z §7 | **Tak, jak w tabeli:** najpierw naprawy i rzeczy bez kont, potem Twoje konta |
| R2 | Jakiej poczty i kalendarza używasz (Gmail/Google, Microsoft 365, inna)? | od tego zależy wybór serwera MCP w 5.3 |
| R3 | Zadania: Todoist, Notion czy plik w skarbcu? | **plik w skarbcu**, jeśli nie używasz żadnej z tych aplikacji |
| R5 | Postiz | **poza VPS** (Postiz Cloud albo mały osobny serwer) albo eksport ICS/CSV |
| R6 | LanguageTool i changedetection.io | **dopiero po pomiarze RAM** na VPS |
| R8 | Baza Konkurencyjności przez nieopisane API strony | **tak, ostrożnie:** małe tempo, a gdy przestanie działać, eksport listy projektów |

## 9. Źródła

Raporty badawcze z 2026-10-01: audyt repo (wszystkie profile, skrypty i evals) oraz research narzędzi dla
Łowcy, Ads, Ręki, Sherlocka ze Studio i nowych specjalistów. Najważniejsze źródła prawne i techniczne są
podlinkowane przy punktach powyżej; licencje sprawdzone w rejestrach PyPI, npm i na GitHubie.
Przepisy: art. 398–399 PKE (od 10.11.2024), KSeF ([harmonogram](https://jpk.info.pl/faktury/e-faktura-ustrukturyzowana-ksef/harmonogram/)),
GPSR (od 13.12.2024), zamknięcie platformy ODR (20.07.2025), art. 50 AI Act (od 2.08.2026),
e-Doręczenia dla firm z CEIDG (od 1.10.2026).

# Rozwój floty: plan dopracowania agentów i nowi specjaliści

Stan: **plan do analizy (research 2026-10-01), nic nie jest wdrożone.** Wersje bibliotek, limity API i daty
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
| `jarvo-web` | 9 | 9 (~1 400 linii) | 58 | wysoka | wzorzec: sprawdzenia od początku do końca w kodzie |
| `jarvo-wideo` | 15 | 17 + biblioteka (~5 600 linii) + edytor | 57 | wysoka | pełna linia produkcyjna |
| `jarvo-lowca` | 6 | 4 + biblioteka (~1 100 linii) | 0 | średnio-wysoka | prawdziwe dane, ale błąd w ocenie leadów i nigdy nie uruchomiony na prawdziwej ofercie |
| `jarvo-ads` | 10 | 4 (~550 linii) | 6 | nisko-średnia | dobra matematyka testów, ale Skarbiec nie istnieje, więc połowa skilli to martwe ścieżki |
| `jarvo-sherlock` | 7 | 3 (~290 linii) | 16 | nisko-średnia | weryfikacja źródeł tylko w prompcie; dziś blisko zwykłego „deep research” |
| `jarvo-studio` | 6 | 2 (~160 linii) + 1 szablon | 24 | nisko-średnia | renderuje i mierzy wymiary, ale tekstu, układu i publikacji kod nie sprawdza |
| `jarvo-reka` | 4 | 2 (~190 linii) | 4 + wszystkie skille floty | niska | generalista bez dostępu do Twojej poczty, kalendarza i dokumentów |

## 3. Do naprawy od razu (błędy znalezione przy audycie)

Te punkty nie wymagają decyzji, tylko poprawki:

1. **Łowca odrzuca dobre leady.** `leady.dopasowanie()` liczy kryterium ICP jako niespełnione, gdy sygnał
   go w ogóle nie dotyczy (CPV jest tylko w przetargach, PKD tylko w KRS). Przy przykładowym profilu
   z `profil-klienta` idealna nowa spółka IT dostaje 0,5 przy progu 1,0 i odpada; pasujący przetarg tak samo.
   Poprawka: kryteria liczone tylko dla pól, które sygnał ma, plus test na przykładowym profilu.
2. **Łowca: prawo komunikacji elektronicznej jest opisane za słabo.** [LEADY.md](LEADY.md) §3 mówi o zgodzie
   „do konkretnej osoby”. Od 10.11.2024 art. 398 PKE wymaga uprzedniej zgody na marketing e-mailem
   i telefonem do każdego abonenta, także firmy i adresu ogólnego typu `biuro@`. Najcenniejsze są więc
   leady, które same proszą o oferty (przetargi, zapytania ofertowe), bo odpowiedź na nie nie jest
   niezamówiona.
3. **Ręka kieruje zadania po nieaktualnej tabeli:** `kiedy-oddac-snajperowi` nie zna Ads ani Łowcy.
4. **Ads opisuje nieistniejące rzeczy:** `podlacz-konto` odsyła do „HQ → Reklamy” i `compose/skarbiec.env`,
   a `ads.py` zawsze kończy się kodem 3. [ADS.md](ADS.md) podaje Graph API v25, a od 29.07.2026 jest v26.
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
| 1 | Poprawka oceny ICP i test (§3) | bez niej najlepsze leady odpadają | S |
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
| 10 | e-Doręczenia | przekazywanie maila z powiadomieniem na Telegram: od dziś (1.10.2026) każda firma z CEIDG musi mieć adres, a nieodebrana przesyłka po 14 dniach uznaje się za doręczoną | S |
| 11 | `pack.py` v2 i naprawa tabeli kierowania (§3) | paczka czyta artefakty z kart kanbana, sprawdza linki w `INDEX.md` i wyłapuje niezgodności między kartami (nazwy, ceny, adresy) | S |

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
Inspektora i Ads).

## 6. Nowi specjaliści (propozycja)

Każdy działa skryptami uruchamianymi na żądanie, bez usług działających cały czas.

### 6.1 `jarvo-inspektor`: Inspektor zgodności (najwyżej w kolejce)

Darmowy, poparty dowodami audyt prawny dowolnej strony: prawny odpowiednik technicznego audytu Weba.
- **Raport cookies:** co ładuje się przed zgodą, po „odrzuć” i po „akceptuj”, z HAR-em i zrzutami jako
  dowodem; czy „Odrzuć wszystkie” jest równie łatwe jak „Akceptuj”. Miarą jest poradnik UODO dla e-handlu
  (marzec 2025); art. 399 PKE przewiduje kary do 3% przychodu.
- **Szkic polityki prywatności i cookies** z faktycznie znalezionych narzędzi (GA4, Pixel), oznaczony
  „do weryfikacji przez prawnika”.
- **Formularze:** zaznaczone domyślnie zgody, osobna zgoda na każdy kanał (art. 398 PKE).
- **Sklep:** najniższa cena z 30 dni i opis weryfikacji opinii (Omnibus), dane producenta (GPSR od
  13.12.2024), martwy link do platformy ODR (zamkniętej 20.07.2025).
- **Dostępność (EAA):** drzewo decyzji, czy ustawa w ogóle dotyczy firmy (mikroprzedsiębiorcy usługowi są
  zwolnieni), szkic deklaracji dostępności; test axe robi Web.
- **Narzędzia:** własny skrypt Playwright, [Open Cookie Database](https://github.com/jkwakman/Open-Cookie-Database)
  (Apache-2.0), opcjonalnie [gdpr-cookie-scanner](https://github.com/Slashgear/gdpr-cookie-scanner) (MIT).
- **Granice:** to nie porada prawna; czyta tylko publiczne strony, niczego nie poprawia sam (poprawki idą
  do Weba), audytów cudzych stron nie publikuje i nikogo nie zgłasza do UODO.
- **Wartość dla Ciebie:** nieudany audyt to gotowy pretekst do rozmowy o Twoich usługach.
- **Nakład:** S–M, bez kluczy i kont.

### 6.2 `jarvo-rachmistrz`: Rachmistrz (finanse i zaplecze biura)

- **Skrzynka KSeF tylko do odczytu:** faktury zakupowe jako XML FA(3), rejestr CSV/XLSX, wykrywanie
  duplikatów, terminy płatności. Od 1.02.2026 wszyscy odbierają faktury w KSeF, od 1.04.2026 wystawiają;
  mikrofirmy do 10 tys. zł miesięcznie mają czas do 1.01.2027, a kary są od 2027.
- **„Czy mogę to zapłacić?”:** NIP i rachunek na białej liście przed przelewem; powyżej 15 tys. zł na
  rachunek spoza listy nie ma kosztu podatkowego i jest solidarna odpowiedzialność za VAT.
- **Przepływy pieniędzy z wyciągu** MT940 albo CSV, dopasowane do faktur, lista subskrypcji, prognoza na
  13 tygodni. Bankowych API brak (GoCardless zamknął rejestrację), więc import pliku.
- **Kalendarz podatkowy** jako ICS i przypomnienia; kurs NBP do faktur Meta i Google (import usług).
- **Narzędzia:** [ksef-client](https://github.com/smekcio/ksef-client-python) albo [ksef2](https://github.com/stacking-hq/ksef2)
  (MIT, przed 1.0, więc przypięta wersja), środowisko testowe KSeF do evals, [mt-940](https://github.com/WoLpH/mt940)
  (BSD-3), NBP, `holidays`.
- **Granice:** token KSeF z samym `InvoiceRead`; wystawienie faktury w produkcji to A2 z kodem (faktury nie
  da się usunąć, tylko skorygować); brak dostępu do zapisu w banku i płatności; numery rachunków
  maskowane w tym, co widzi model; decyzje podatkowe należą do księgowej.
- **Dlaczego osobny agent, a nie skill Ręki:** token KSeF i dane bankowe mają żyć tylko w jednym profilu.
  Ręka bierze z Rachmistrza gotowe podsumowanie do porannego briefu.
- **Nakład:** M–L.

### 6.3 `jarvo-handlowiec`: Handlowiec (od zapytania do podpisanej umowy)

- **Zapytanie mailowe → oferta PDF w Twojej marce** (zakres, terminy, cena, warunki); dane klienta
  z NIP przez wspólny moduł rejestrów; `to_pdf.py` już jest.
- **Lejek sprzedaży** w SQLite albo CSV; codziennie lista ofert bez odpowiedzi od ponad 5 dni ze szkicami
  przypomnień.
- **Umowa z szablonu** (usługi, NDA, dzieło) z listą ryzyk: pola eksploatacji (art. 41 prawa autorskiego),
  kary umowne, terminy płatności.
- **Przekazanie do Rachmistrza** po wygranej: szkic faktury.
- **Granice:** niczego nie wysyła (A2); przypomnienia tylko w wątkach, które zaczął klient (art. 398 PKE);
  ceny, rabaty i podpisy decydujesz Ty.
- **Szew z innymi:** Łowca kończy na kontakcie, Handlowiec zaczyna od pierwszej odpowiedzi; Ręka tylko
  szkicuje maile, bez stanu lejka.
- **Nakład:** M.

### 6.4 `jarvo-opiekun`: Opiekun opinii (opcjonalny)

- **Odpowiedzi na opinie Google** w tonie marki; przy negatywnych zalecenie, jak zareagować.
- **Zestaw do zbierania opinii:** plakat z QR i link do formularza Google, bez filtrowania niezadowolonych.
- **Spójność nazwy, adresu i telefonu** w Google, Facebooku i polskich katalogach.
- **FAQ z opinii i strony** dla Weba (strona FAQ z JSON-LD).
- **Dane:** eksport z Google Takeout; odpowiedzi przez Business Profile API (wymaga zatwierdzenia,
  profilu zweryfikowanego od 60 dni i strony).
- **Granice:** każda odpowiedź to A2; żadnych opinii kupionych ani zachęcanych nagrodą (Omnibus, UOKiK);
  żadnych danych osobowych ani zdrowotnych w odpowiedziach.
- **Nakład:** S–M; największe ryzyko to uzyskanie dostępu do API. Może zacząć jako skill Studio.

### Odrzuceni kandydaci

- **Social media / community manager:** dubluje Studio, a czytanie cudzych komentarzy wymaga przeglądu
  aplikacji Meta. Lepiej skill `triage-komentarzy` (tylko szkice) w Studio.
- **Czatbot na stronę / obsługa klienta:** publiczny punkt wejścia zaprasza do wstrzykiwania poleceń,
  a Chatwoot potrzebuje 4 GB RAM. Przeżywa tylko część z opiniami i FAQ (Opiekun).
- **Analityk danych:** wykresy z CSV robi każdy czat; cenne dane mają już Rachmistrz (finanse) i Ads
  (reklamy), a Search Console może dostać Web jako skill.
- **Pisarz blogowy SEO:** pokrywają go Sherlock `research-seo`, Studio `copy-pl` i Web `landing-produktowy`.
- **Osobny recenzent umów:** za wąski; dzielą go Inspektor (regulaminy stron) i Handlowiec (umowy z klientami).

## 7. Kolejność

| Etap | Zakres | Nakład | Klucze i konta |
|---|---|---|---|
| A. Naprawy i fundament | §3 w całości, `rejestry_pl.py` (§4) | 2–3 dni | brak |
| B. Sygnatury bez kont | Ads: audyt gotowości (5.2 #1–3); Łowca: karta leada (5.1 #2–8, potem #9 na Twojej ofercie); Sherlock: raport z dowodami (5.4 #1–5); Studio: pakiet startowy (5.5 #1–5) | ok. 2 tygodnie | darmowe: archive.org, OpenAlex, GUS BIR, PageSpeed |
| C. Inspektor | 6.1 | 3–5 dni | brak |
| D. Ręka z Twoimi kontami | 5.3 #1–11 | ok. tydzień | poczta, kalendarz (Twoja zgoda na każde) |
| E. Rachmistrz | 6.2, najpierw środowisko testowe KSeF | 1–2 tygodnie | token KSeF `InvoiceRead` |
| F. Handlowiec | 6.3 | ok. tydzień | brak nowych |
| G. Konta reklamowe | Skarbiec faza 1, MCP tylko do odczytu (5.2 #6–7) | ok. tydzień | Meta `ads_read`, Google rola „tylko odczyt” |
| H. Opiekun (jeśli tak) | 6.4 | 3–5 dni | dostęp do Business Profile API |

Każdy etap kończy się tak jak dotąd: testy, evals, red team dla nowych wejść z sieci, wdrożenie i próba
w działającym kontenerze, dokumentacja.

## 8. Decyzje dla Ciebie

| # | Pytanie | Rekomendacja |
|---|---|---|
| R1 | Kolejność etapów z §7 | **Tak, jak w tabeli:** najpierw naprawy i rzeczy bez kont, potem Twoje konta |
| R2 | Jakiej poczty i kalendarza używasz (Gmail/Google, Microsoft 365, inna)? | od tego zależy wybór serwera MCP w 5.3 |
| R3 | Zadania: Todoist, Notion czy plik w skarbcu? | **plik w skarbcu**, jeśli nie używasz żadnej z tych aplikacji |
| R4 | Finanse jako osobny agent (Rachmistrz) czy skille Ręki? | **osobny agent:** token KSeF i dane bankowe tylko w jednym profilu |
| R5 | Postiz | **poza VPS** (Postiz Cloud albo mały osobny serwer) albo eksport ICS/CSV |
| R6 | LanguageTool i changedetection.io | **dopiero po pomiarze RAM** na VPS |
| R7 | Opiekun opinii | **na razie skill Studio**, osobny agent, gdy będzie dostęp do API |
| R8 | Baza Konkurencyjności przez nieopisane API strony | **tak, ostrożnie:** małe tempo, a gdy przestanie działać, eksport listy projektów |

## 9. Źródła

Raporty badawcze z 2026-10-01: audyt repo (wszystkie profile, skrypty i evals) oraz research narzędzi dla
Łowcy, Ads, Ręki, Sherlocka ze Studio i nowych specjalistów. Najważniejsze źródła prawne i techniczne są
podlinkowane przy punktach powyżej; licencje sprawdzone w rejestrach PyPI, npm i na GitHubie.
Przepisy: art. 398–399 PKE (od 10.11.2024), KSeF ([harmonogram](https://jpk.info.pl/faktury/e-faktura-ustrukturyzowana-ksef/harmonogram/)),
GPSR (od 13.12.2024), zamknięcie platformy ODR (20.07.2025), art. 50 AI Act (od 2.08.2026),
e-Doręczenia dla firm z CEIDG (od 1.10.2026).

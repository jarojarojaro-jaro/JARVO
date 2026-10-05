# Łowca leadów: sygnały zakupowe → lista firm z „dlaczego teraz” (projekt)

> Stan: **zaakceptowany (2026-09-30), agent aktywny; czeka na pierwszy przebieg** (§6). Właściciel: `jarvo-lowca` („Łowca”).
> Decyzje użytkownika: osobny agent; **źródła oficjalne i darmowe** (płatne API tylko na własnych kluczach); kontakt =
> dane, które firma **sama opublikowała** (strona, rejestr), zawsze ze źródłem; agent niczego nie wysyła.

Łowca szuka firm, dla których **teraz** jest dobry moment na rozmowę: właśnie powstały, ogłosiły przetarg na to,
co sprzedajesz, wygrały przetarg i będą potrzebować podwykonawców, rekrutują na rolę, która oznacza Twój produkt,
zmieniły technologię na stronie, mają nowość w mediach. Oddaje ranking firm z jednym zdaniem „dlaczego teraz”,
źródłem każdego sygnału i kontaktem, który firma sama podała. Metoda (wykryj → odsiej → kontakt → ranking,
monitoring z bazą) za `superdesigndev/treg` `lead-signals` (Apache-2.0), przepisana na polskie źródła i nasze zasady.

---

## 1. Przepływ

```
  Ty: „znajdź klientów na <oferta>” / „pilnuj przetargów na <usługa>”
        │
        ▼
  ① profil-klienta     ICP.yaml + ICP.md: kogo szukamy (PKD, CPV, region, wielkość), ból, sygnały, wykluczenia, wagi
        │
        ▼
  ② sygnaly            skrypty (0 tokenów): krs.py (nowe spółki, zmiany w KRS), ceidg.py (jednoosobowe
                       działalności z CEIDG), przetargi.py (BZP, TED),
                       strona.py (technologia, kariera, zmiana strony) + web_search (oferty pracy, newsy)
                       → sygnaly.jsonl (firma, sygnał, data, źródło)
        │
        ▼
  ③ kwalifikacja       odsiew szumu (zwykle > połowa), dopasowanie do ICP, świeżość, siła (2 sygnały > 1)
        │
        ▼
  ④ kontakt-firmy      strona.py kontakt: e-maile, telefony, formularz, osoby z zespołu, które firma opublikowała
                       (każdy z adresem strony), także z danych ukrytych w HTML (JSON-LD, Next.js, Nuxt, RSC)
                       + e-mail/strona z KRS, telefon/e-mail/strona z CEIDG; bez zgadywania adresów, bez LinkedIna
        │
        ▼
  ⑤ lista-leadow       leady.py: leady.csv (deduplikacja), ocena wg ICP, LEADY.md (top N z „dlaczego teraz”),
                       pokrycie („120 sygnałów → 34 firmy → 21 z kontaktem”), koszt i czas przebiegu
        │
        ▼
  ⑥ monitoring-leadow  rutyna (zgoda użytkownika, cron przez Jarva): tylko nowe klucze względem bazy
     dalej:            szkic pierwszej wiadomości → Studio (`copy-pl`); wysyłka → człowiek (A2)
```

## 2. Źródła (sprawdzone 2026-09-30, CEIDG 2026-10-05)

| Źródło | Co daje | Dostęp | Sygnał |
|---|---|---|---|
| KRS, API Ministerstwa Sprawiedliwości (`api-krs.ms.gov.pl`) | biuletyn: podmioty z wpisami danego dnia (~4 tys.); odpis: nazwa, NIP, REGON, forma, adres, województwo, PKD, kapitał, data rejestracji, e-mail i strona (jeśli podane) | bez klucza | nowa firma w PKD i regionie z ICP; wpis zmian |
| e-Zamówienia, BZP (`ezamowienia.gov.pl/mo-board/api`) | ogłoszenia o zamówieniach i wynikach: zamawiający (NIP), przedmiot, CPV, termin ofert | bez klucza | przetarg na to, co sprzedajesz; wynik (zwycięzca = nowa praca do wykonania) |
| CEIDG, API v3 Hurtowni danych (`dane.biznes.gov.pl/api/ceidg/v3`, `ceidg.py`) | jednoosobowe działalności (KRS ma spółki): nazwa firmy, NIP, REGON, status, data rozpoczęcia, miejscowość, PKD; telefon, e-mail i www, jeśli przedsiębiorca je podał | darmowy token właściciela (`CEIDG_TOKEN`, [niżej](#token-ceidg)); 1000 zapytań na godzinę | nowa działalność w PKD i miejscu z ICP (`ceidg-nowa-firma`); sam wpis (`ceidg-firma`) daje tylko PKD i kontakt |
| TED (`api.ted.europa.eu/v3`) | ogłoszenia unijne (także PL), CPV, zamawiający | bez klucza | jw. powyżej progów UE |
| Strona firmy (`strona.py`) | kontakt, zespół, kariera, technologia (CMS, sklep, analityka, piksele), odcisk strony; dane ukryte w HTML (schema.org JSON-LD, `__NEXT_DATA__`, Nuxt, RSC): nazwa, adres, telefon, e-mail, NIP | publiczna strona, `robots.txt`, uczciwy UA | technologia konkurenta albo brak narzędzia; rekrutacja; zmiana strony |
| Wyszukiwarka (SearXNG floty) | oferty pracy, newsy, finansowanie, targi, wypowiedzi firm | narzędzie `web_search` | rekrutacja na rolę, inwestycja, ekspansja |
| Biała lista VAT (`wl-api.mf.gov.pl`) | status VAT, NIP ↔ KRS | bez klucza; z części chmur odpowiada ochroną antybotową | weryfikacja firmy (opcjonalnie) |
| REGON (BIR) | nowe podmioty dziennie (także spoza CEIDG i KRS), PKD | bezpłatny klucz użytkownika | poza pierwszą wersją |

Nazwiska członków zarządu API KRS maskuje (`D***`), więc osoba kontaktowa pochodzi wyłącznie ze strony firmy.
Przedsiębiorca z CEIDG to osoba fizyczna, więc `ceidg.py` przepuszcza tylko białą listę pól: nazwę firmy, NIP, REGON,
status i daty działalności, miejscowość, gminę, powiat, województwo, PKD oraz telefon, e-mail i www z rejestru. Imię
i nazwisko właściciela jako osobne pola, ulica i numer (często adres domowy), adres korespondencyjny, obywatelstwo,
wspólność majątkowa, upadłości, zakazy i adres do e-Doręczeń nie wychodzą ze skryptu; PESEL-u API nie zwraca.
Każdy wiersz ma `zrodlo` (wpis w wyszukiwarce firm biznes.gov.pl) i `stan_na` (dzień pobrania). API CEIDG: `/firmy`
(wyszukiwanie: pełne kody PKD, miasto, województwo, powiat, gmina, status, data rozpoczęcia, strony), `/firma`
(szczegóły po NIP, REGON albo identyfikatorach, partiami); limit 1000 zapytań na 60 minut, skrypt robi 4 s przerwy,
na 429 czeka i ponawia ([dokumentacja API v3](https://akademia.biznes.gov.pl/hurtownia-danych-instrukcje-i-dokumentacja/)).
Źródło, które odpowiada ochroną antybotową albo odmową, to blokada, nie zagadka (kontrakt pkt 16).

### Token CEIDG

Darmowy, jednorazowo, robi to właściciel (agent nie zakłada kont):

1. Otwórz [dane.biznes.gov.pl](https://dane.biznes.gov.pl) i kliknij „zarejestruj się”. To usługa online
   Biznes.gov.pl: wniosek o dostęp do Hurtowni danych CEIDG i Biznes.gov.pl.
2. Zaloguj się przez login.gov.pl (Profil Zaufany, e-dowód albo bankowość elektroniczna).
3. Wypełnij wniosek o dostęp (jeśli pyta o zakres, wybierz dostęp do API) i zaakceptuj oświadczenie o ochronie
   i przetwarzaniu danych osobowych. Wyślij.
4. Token przychodzi e-mailem na adres z konta, zwykle po kilku minutach. To długi ciąg trzech części rozdzielonych
   kropkami (zaczyna się zwykle od `eyJ`). Nie przyszedł: Centrum Pomocy Biznes.gov.pl, temat „Hurtownia Danych CEIDG”.
5. Skopiuj cały token, bez słowa „Bearer”. W Jarvo HQ w lewym górnym rogu wybierz profil `jarvo-lowca`, wejdź
   w **Klucze** → **Własne klucze** → **Dodaj własny klucz**, nazwa zmiennej `CEIDG_TOKEN`, wklej wartość, **Dodaj**.
   Na serwerze możesz zamiast tego dopisać `CEIDG_TOKEN=…` do `/srv/jarvo/secrets/jarvo-lowca.env` i wdrożyć.
6. Sprawdź: napisz Łowcy „sprawdź token CEIDG” (uruchomi `ceidg.py sprawdz`). Ma odpowiedzieć „token działa”.
   Gdy kiedyś zgłosi „zły albo wygasły (401)”, wygeneruj nowy token tak samo i podmień wartość w Kluczach.

Token widzi tylko Łowca (`terminal.env_passthrough` w jego `config.yaml`) i tylko w nagłówku zapytania do
`dane.biznes.gov.pl`; skrypt nigdy go nie wypisuje. Bez tokenu Łowca działa jak dotąd, bez CEIDG (kod 2 z instrukcją).

**Nowe źródło** (katalog wystawców, rejestr branżowy, wyszukiwarka dotacji) przechodzi najpierw skill
`rozpoznanie-zrodla`: oficjalne API, `robots.txt` i regulamin (prawo do bazy danych ocenia człowiek), potem
`zrodlo.py nagraj` (ruch strony do HAR, uczciwy UA), `har` (żądania z danymi, ETag, zależności), `roznice` (dwa nagrania
różniące się jedną rzeczą → parametry wyszukiwania i stronicowania) i `schemat` (suma 20–30 odpowiedzi: pola
opcjonalne, `null`, niespójne typy). Wynik to `ZRODLO.md`: specyfikacja skryptu albo powód odrzucenia źródła.

## 3. Granice

- **Tylko dane opublikowane przez firmę albo rejestr**, każde z adresem źródła. Nie zgadujemy adresów
  (`imie.nazwisko@`), nie kupujemy baz, nie scrapujemy LinkedIna ani innych serwisów za logowaniem, nie obchodzimy
  ochrony stron (`robots.txt`, limity, captcha).
- **Agent niczego nie wysyła.** Wysyłka to decyzja człowieka (A2). Raz na listę agent przypomina: informacja handlowa
  mailem albo telefonicznie do konkretnej osoby co do zasady wymaga jej wcześniejszej zgody (UŚUDE, Prawo komunikacji
  elektronicznej), także w B2B; adres opublikowany na stronie to nie zgoda. Przed kampanią: podstawa prawna, lista
  wypisanych, informacja o źródle danych (RODO art. 14).
- **Dane osób: minimum.** Imię, nazwisko i rola tylko wtedy, gdy firma sama pokazuje je jako kontakt (zespół, stopka,
  kontakt); bez prywatnych profili, bez danych wrażliwych. Jednoosobowa działalność z CEIDG to osoba fizyczna: tylko
  nazwa firmy, PKD, miejscowość i kontakt podany w rejestrze, bez adresu domowego. Jej e-mail i telefon z rejestru
  to nie zgoda na informację handlową (art. 398 PKE): legalny kanał to odpowiedź na jej zapytanie, list albo spotkanie.
- **Koszt i tempo:** skrypty pytają źródła grzecznie (pauza między zapytaniami, pamięć odpowiedzi), raport podaje
  liczbę zapytań i czas przebiegu.

## 4. Ocena

Najpierw **dopasowanie** (brak dopasowania = brak wiersza; liczone tylko z kryteriów ICP, które dane sygnału pozwalają
sprawdzić, np. CPV tylko przy przetargach, PKD tylko przy firmach z KRS; reszta w kolumnie `niesprawdzone`; słowa po
rdzeniu, więc „strona” znajduje „strony”), potem **świeżość** (sygnał sprzed tygodnia bije sygnał
sprzed kwartału), potem **siła** (dwa niezależne sygnały na jednej firmie biją jeden); przy remisie wyżej firma z
opublikowanym kontaktem. Wagi i okna czasowe są w
`ICP.yaml`, więc wynik da się odtworzyć i poprawić. Każdy wiersz ma powód w słowach użytkownika.

## 5. Pliki

```
out/leady/<projekt>/
  ICP.yaml, ICP.md        kogo szukamy i jak oceniamy
  sygnaly.jsonl           surowe sygnały (firma, typ, data, źródło, szczegóły)
  leady.csv               firmy po kwalifikacji: klucz, ocena, sygnały, kontakty (ze źródłem), status
  LEADY.md                ranking top N, pokrycie, koszt, przypomnienie o zgodach, następne kroki
  baza.json               klucze z poprzednich przebiegów (monitoring: raport tylko nowych)
```

## 6. Etapy

1. ✅ Plan (ten dokument).
2. ✅ Skrypty `krs.py`, `przetargi.py`, `strona.py`, `leady.py` (+ `lowca_lib.py`) z testami offline; sprawdzone
   na żywych źródłach w kontenerze. e-Zamówienia odcina za kilka ciężkich zapytań z rzędu (strona „Dostęp
   zablokowany”): pauza 4 s na zapytanie, pełny dzień dzielony na województwa, blokada = stop. Pokój „Radar” w HQ.
3. ✅ Profil `jarvo-lowca`: SOUL, 7 skilli, rubryka, 15 scenariuszy evals, dokumentacja floty; wzorzec misji „Leady”
   u Jarva, temat `Łowca` na Telegramie (`TELEGRAM_TOPIC_LOWCA`).
4. ⬜ Pierwszy prawdziwy przebieg na ofercie użytkownika i poprawki wag.
5. ✅ CEIDG (2026-10-05, decyzja właściciela): `ceidg.py` (API v3, token właściciela), sygnał `ceidg-nowa-firma`,
   minimum danych osoby, testy offline, eval `lowca-ceidg`. ⬜ Pierwsze zapytanie z prawdziwym tokenem: sprawdzić
   link `zrodlo` do wyszukiwarki firm, dopasowanie miasta (wielkość liter) i maksymalną partię `ids`.

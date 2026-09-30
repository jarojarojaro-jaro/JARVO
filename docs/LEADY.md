# Łowca leadów: sygnały zakupowe → lista firm z „dlaczego teraz” (projekt)

> Stan: **zaakceptowany (2026-09-30), w budowie** (§6). Właściciel: `jarvo-lowca` („Łowca”).
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
  ② sygnaly            skrypty (0 tokenów): krs.py (nowe firmy, zmiany w KRS), przetargi.py (BZP, TED),
                       strona.py (technologia, kariera, zmiana strony) + web_search (oferty pracy, newsy)
                       → sygnaly.jsonl (firma, sygnał, data, źródło)
        │
        ▼
  ③ kwalifikacja       odsiew szumu (zwykle > połowa), dopasowanie do ICP, świeżość, siła (2 sygnały > 1)
        │
        ▼
  ④ kontakt-firmy      strona.py kontakt: e-maile, telefony, formularz, osoby z zespołu, które firma opublikowała
                       (każdy z adresem strony) + adres/strona z KRS; bez zgadywania adresów, bez LinkedIna
        │
        ▼
  ⑤ lista-leadow       leady.py: leady.csv (deduplikacja), ocena wg ICP, LEADY.md (top N z „dlaczego teraz”),
                       pokrycie („120 sygnałów → 34 firmy → 21 z kontaktem”), koszt i czas przebiegu
        │
        ▼
  ⑥ monitoring-leadow  rutyna (zgoda użytkownika, cron przez Jarva): tylko nowe klucze względem bazy
     dalej:            szkic pierwszej wiadomości → Studio (`copy-pl`); wysyłka → człowiek (A2)
```

## 2. Źródła (sprawdzone 2026-09-30)

| Źródło | Co daje | Dostęp | Sygnał |
|---|---|---|---|
| KRS, API Ministerstwa Sprawiedliwości (`api-krs.ms.gov.pl`) | biuletyn: podmioty z wpisami danego dnia (~4 tys.); odpis: nazwa, NIP, REGON, forma, adres, województwo, PKD, kapitał, data rejestracji, e-mail i strona (jeśli podane) | bez klucza | nowa firma w PKD i regionie z ICP; wpis zmian |
| e-Zamówienia, BZP (`ezamowienia.gov.pl/mo-board/api`) | ogłoszenia o zamówieniach i wynikach: zamawiający (NIP), przedmiot, CPV, termin ofert | bez klucza | przetarg na to, co sprzedajesz; wynik (zwycięzca = nowa praca do wykonania) |
| TED (`api.ted.europa.eu/v3`) | ogłoszenia unijne (także PL), CPV, zamawiający | bez klucza | jw. powyżej progów UE |
| Strona firmy (`strona.py`) | kontakt, zespół, kariera, technologia (CMS, sklep, analityka, piksele), odcisk strony | publiczna strona, `robots.txt`, uczciwy UA | technologia konkurenta albo brak narzędzia; rekrutacja; zmiana strony |
| Wyszukiwarka (SearXNG floty) | oferty pracy, newsy, finansowanie, targi, wypowiedzi firm | narzędzie `web_search` | rekrutacja na rolę, inwestycja, ekspansja |
| Biała lista VAT (`wl-api.mf.gov.pl`) | status VAT, NIP ↔ KRS | bez klucza; z części chmur odpowiada ochroną antybotową | weryfikacja firmy (opcjonalnie) |
| REGON (BIR), CEIDG | działalności jednoosobowe, PKD | bezpłatny klucz użytkownika | poza pierwszą wersją |

Nazwiska członków zarządu API KRS maskuje (`D***`), więc osoba kontaktowa pochodzi wyłącznie ze strony firmy.
Źródło, które odpowiada ochroną antybotową albo odmową, to blokada, nie zagadka (kontrakt pkt 16).

## 3. Granice

- **Tylko dane opublikowane przez firmę albo rejestr**, każde z adresem źródła. Nie zgadujemy adresów
  (`imie.nazwisko@`), nie kupujemy baz, nie scrapujemy LinkedIna ani innych serwisów za logowaniem, nie obchodzimy
  ochrony stron (`robots.txt`, limity, captcha).
- **Agent niczego nie wysyła.** Wysyłka to decyzja człowieka (A2). Raz na listę agent przypomina: informacja handlowa
  mailem albo telefonicznie do konkretnej osoby co do zasady wymaga jej wcześniejszej zgody (UŚUDE, Prawo komunikacji
  elektronicznej), także w B2B; adres opublikowany na stronie to nie zgoda. Przed kampanią: podstawa prawna, lista
  wypisanych, informacja o źródle danych (RODO art. 14).
- **Dane osób: minimum.** Imię, nazwisko i rola tylko wtedy, gdy firma sama pokazuje je jako kontakt (zespół, stopka,
  kontakt); bez prywatnych profili, bez danych wrażliwych.
- **Koszt i tempo:** skrypty pytają źródła grzecznie (pauza między zapytaniami, pamięć odpowiedzi), raport podaje
  liczbę zapytań i czas przebiegu.

## 4. Ocena

Najpierw **dopasowanie** (brak dopasowania = brak wiersza), potem **świeżość** (sygnał sprzed tygodnia bije sygnał
sprzed kwartału), potem **siła** (dwa niezależne sygnały na jednej firmie biją jeden). Wagi i okna czasowe są w
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
3. ⬜ Profil `jarvo-lowca`: SOUL, 6 skilli, rubryka, evals, pokój „Radar” w HQ, dokumentacja floty.
4. ⬜ Pierwszy prawdziwy przebieg na ofercie użytkownika i poprawki wag.

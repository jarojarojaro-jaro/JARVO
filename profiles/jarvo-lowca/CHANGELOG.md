# Changelog: jarvo-lowca

## Niewydane
- CEIDG (decyzja właściciela): nowy skrypt `ceidg.py` do oficjalnego API v3 Hurtowni danych CEIDG (dane.biznes.gov.pl,
  darmowy token `CEIDG_TOKEN`). KRS to spółki, CEIDG to jednoosobowe działalności. `szukaj` po pełnych kodach PKD,
  miejscowości, województwie, powiecie, gminie, statusie (domyślnie aktywne) i dacie rozpoczęcia, strony za
  `links.next`, szczegóły partiami (`/firma?ids=`); `firma` po NIP, REGON albo identyfikatorze; `sprawdz` (czy token
  działa); `--z-pliku` offline. Wyjście w formacie sygnałów: `ceidg-nowa-firma` (start w ostatnich 30 dniach albo
  zaplanowany) i `ceidg-firma` (sam wpis, waga 0: PKD i kontakt dla firmy z innym sygnałem), ze `zrodlo` i `stan_na`.
  Minimum danych osoby fizycznej (biała lista pól: bez imienia i nazwiska właściciela, ulicy, adresu korespondencyjnego,
  obywatelstwa, adresu do e-Doręczeń; PESEL-u API nie zwraca), kontakt tylko podany w rejestrze, przypomnienie o zgodzie
  (art. 398 PKE). Limit 1000 zapytań/h: co najmniej 4 s między zapytaniami, 429 przeczekane (min. 180 s, dwa ponowienia,
  potem kod 3), 5xx i sieć: trzy próby; brak albo zły token (401, 403): kod 2 z instrukcją, token nigdy w wyjściu
  i tylko do hosta API (bez przekierowań). Token wpisuje właściciel w Jarvo HQ (Klucze profilu), a `config.yaml`
  przepuszcza go do terminala (`terminal.env_passthrough`). Skille `sygnaly` 1.1.0, `kontakt-firmy` 1.2.0,
  `kwalifikacja` 1.2.0, `lista-leadow` 1.1.0, `monitoring-leadow` 1.1.0; eval `lowca-ceidg`. Opis i `oddaj_gdy`
  w `fleet.yaml` wymieniają CEIDG, więc Jarvo kieruje tu też prośby o jednoosobowe firmy.
- `leady.py`: typy `ceidg-nowa-firma` i `ceidg-firma`, etykieta źródła CEIDG w `LEADY.md`; opis wpisu z CEIDG, jak
  z KRS, nie liczy się do słów kluczowych; telefon z sygnału (rejestr) trafia do listy, gdy strona go nie podaje,
  a nowa kolumna `telefon_zrodlo` mówi skąd.
- Nowy skill `rozpoznanie-zrodla` i skrypt `zrodlo.py` (+ `har.cjs`): zanim powstanie skrypt do nowego publicznego
  źródła, Łowca sprawdza oficjalne API, `robots.txt` i regulamin, nagrywa ruch strony do HAR (playwright-core, uczciwy UA,
  odmowa = blokada, kod 3), wypisuje żądania z danymi, nagłówki do pobierania przyrostowego i zależności między
  wywołaniami (`har`), porównuje dwa nagrania różniące się jedną rzeczą (`roznice`) i liczy schemat z wielu odpowiedzi:
  pola opcjonalne, `null`, niespójne typy, przykłady z maskowanymi e-mailami i numerami (`schemat`, osobno dla każdego
  żądania, `--zadanie`). Piksele śledzące i analityka nie liczą się jako dane. Wynik: `ZRODLO.md`
  w `zrodla/<nazwa>/`. Eval `lowca-nowe-zrodlo`.
- `strona.py`: tekst sąsiednich elementów już się nie skleja („KRS: 0000745671</p><a>hello@…” dawało fałszywy adres
  `0000745671hello@`, „reach us at<a>hello@” dawało `athello@`), a numery z etykietą REGON, KRS, NIP, BDO nie są brane
  za telefon. Odcisk strony liczony jak dotąd, więc baza monitoringu nie zgłosi fałszywej zmiany.
- Dane ukryte w HTML (`strona.py kontakt`, skill `kontakt-firmy` 1.1.0): skrypt czyta schema.org JSON-LD, `__NEXT_DATA__`,
  dane Nuxt (2 i 3) i strumień React Server Components z pierwszego HTML, bez przeglądarki. Dochodzą nazwa i adres firmy,
  telefony, e-maile, NIP i profile social, których strona nie pokazuje w tekście; każda wartość ma `skad` i adres strony,
  a `ukryte` podsumowuje ładunki. Telefon i NIP tylko spod kluczy, które je nazywają (`telephone`, `taxID`…), nie z
  przypadkowych liczb. `leady.py kontakt` przenosi `adres` do `kontakty.json`.
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Naprawa oceny ICP (`leady.py`): kryterium, którego sygnał nie dotyczy (CPV przy KRS, PKD przy przetargu), liczyło się
  jako niespełnione, więc przy przykładowym profilu (próg 1,0) idealna nowa spółka IT i pasujący przetarg dostawały 0,5
  i odpadały. Teraz liczą się tylko kryteria sprawdzalne, reszta trafia do nowej kolumny `niesprawdzone` w `leady.csv`.
- Słowa kluczowe i wykluczenia po rdzeniu: „strona” znajduje „strony”, „sklep internetowy” znajduje „sklepu internetowego”.
- Testy na przykładowym ICP prosto ze skilla `profil-klienta` (1.1.0) i `kwalifikacja` (1.1.0).

## 0.1.0 (2026-09-30)
- Pierwsza wersja: 6 workflowów (profil klienta, sygnały, kwalifikacja, kontakt firmy, lista leadów, monitoring), skrypty KRS, przetargów (BZP, TED), strony firmy i listy leadów, pokój „Radar sprzedaży” w HQ. Metoda za treg `lead-signals` (Apache-2.0), źródła polskie i oficjalne.

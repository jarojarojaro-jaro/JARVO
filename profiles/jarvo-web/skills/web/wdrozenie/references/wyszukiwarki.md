# Zgłoszenie strony wyszukiwarkom (po wdrożeniu produkcyjnym)

Sama sitemap w `robots.txt` nie wystarcza: nowa strona czeka wtedy tygodniami, aż roboty same ją znajdą. Bing to
osobny indeks od Google, a z jego wyników korzystają też inne wyszukiwarki i asystenci AI z wyszukiwaniem.
Dlatego po każdym wdrożeniu produkcyjnym robimy trzy rzeczy.

## 1. IndexNow (agent sam, bez konta)

Protokół [IndexNow](https://www.indexnow.org/documentation): strona ma plik `https://domena/<klucz>.txt` z kluczem,
a my wysyłamy listę zmienionych adresów. Wyszukiwarki IndexNow (m.in. Bing, Yandex, Seznam, Naver) dzielą się
zgłoszeniami, więc jedno zgłoszenie do `api.indexnow.org` wystarcza. Google IndexNow nie obsługuje.

- Klucz powstaje raz, przy zakładaniu projektu: `@@PY@@ "@@REPO_DIR@@/profiles/jarvo-web/scripts/indexnow.py" klucz <projekt>/public`
  (skill `nowa-strona`).
  Plik trafia do `dist/`, więc jest w odcisku zgody. Klucz jest jawny z założenia, to nie sekret.
  Starszy projekt bez klucza: klucz dodajemy przed buildem, który idzie do zgody, nigdy po zgodzie.
- Po wdrożeniu: `@@PY@@ "@@REPO_DIR@@/profiles/jarvo-web/scripts/indexnow.py" zglos https://domena.pl --katalog <projekt>/public`.
  Skrypt czyta sitemapę z produkcji,
  sprawdza, że plik klucza jest na stronie, i dopiero wtedy wysyła. Po zmianie kilku podstron: `--url` dla każdej z nich.
- Odpowiedź 200 albo 202 jest w porządku (202: klucz jeszcze sprawdzany, adresy przyjęte). 403: plik klucza nie
  dotarł na produkcję. 422: adres spoza domeny. 429: za często, zgłaszamy tylko po zmianach, nie codziennie.
- Nigdy dla podglądu (`localhost`, `*.trycloudflare.com`, staging z `noindex`): skrypt odmawia.

## 2. Bing Webmaster Tools (właściciel, raz na domenę)

Konto należy do właściciela strony, więc agent go nie zakłada i nie loguje się. W raporcie z wdrożenia daje gotową
instrukcję:

1. Wejdź na <https://www.bing.com/webmasters> i zaloguj się (konto Microsoft, Google albo Facebook).
2. Masz już stronę w Google Search Console? Wybierz import z Google Search Console: Bing przejmie witrynę
   i jej sitemapy bez osobnej weryfikacji.
3. Bez Search Console: dodaj witrynę `https://domena.pl` i potwierdź ją. Najprościej plikiem `BingSiteAuth.xml`
   albo meta tagiem `msvalidate.01`. Kod podaje Bing. Wklejasz go agentowi, a ten dodaje plik do `public/`
   (albo tag do layoutu) w następnej wersji do zgody.
4. Sitemapy → Prześlij sitemapę: `https://domena.pl/sitemap-index.xml` (Astro z `@astrojs/sitemap`).

Bing wyłączył stary „ping” sitemapy (`bing.com/ping` zwraca 410), a Google swój (404). Nie używamy pingów:
zmiany zgłasza IndexNow, a sitemapę wyszukiwarki czytają same po zgłoszeniu w panelu.

### 2a. Raport AI Performance (w panelu czyta właściciel, agent interpretuje eksport)

Po weryfikacji domeny Bing Webmaster Tools ma darmowy raport **AI Performance**: które podstrony są cytowane
w odpowiedziach AI Microsoftu (Copilot, podsumowania Bing, wybrani partnerzy) i po jakich frazach. Zakładki: **Pages**
(*Page-Level Citation Activity*: lista najczęściej cytowanych adresów z liczbą cytowań), **Grounding Queries**,
**Grounding Query – Page Mapping** (część podstawowego raportu, nie preview) oraz cztery funkcje preview: **Intents**,
**Topics**, **Citation Share**, **Compare**. Metryk na górze nie myl z widokiem: **Cited pages** to liczba unikalnych
stron cytowanych w danym dniu, nie lista adresów.

Raport otwiera się tylko dla zweryfikowanej witryny, więc weryfikacja z punktu 2 to warunek. Stan 18.11: żadna
z 12 stron właściciela nie ma `BingSiteAuth.xml` ani meta `msvalidate.01`.

- Procedura od zera do pierwszego odczytu (10 kroków, kto co robi, nazwy ekranów):
  `<dane>/jarvo/missions/Z-261118-aeo-bing/web/out/AEO-BING.md` (karta `t_7df17c81`).
- Plik weryfikacyjny: szablony `out/weryfikacja/<domena>/BingSiteAuth.xml` w tym samym katalogu misji
  (miejsce `WSTAW-KOD-Z-PANELU-BING` na kod z panelu, wgrywanie: `out/weryfikacja/JAK-WGRAC.md`). Kod podaje właściciel;
  plik idzie do repo strony obok `robots.txt` i wgrywa go Jarvo po zgodzie.
- Odczyt eksportu CSV/XLSX (właściciel eksportuje z panelu, agent nie loguje się i nie pobiera danych automatem):
  `@@PY@@ "<dane>/jarvo/missions/Z-261118-aeo-bing/web/out/eksport/ai_performance.py" <plik> --top 20`: TOP zapytania,
  strony cytowane najczęściej, pary zapytanie → strona; `--query "fragment"`, `--json`.

Warunki, które podajesz w raporcie razem z liczbami:

- dane są po ok. **48 h** od dodania witryny (wcześniej pusty raport to brak danych, nie zero cytowań),
- historia: **7 dni / 30 dni / 3 miesiące** (albo zakres własny w tych granicach),
- dane są **próbką**, nie pełnym logiem: rzadkie cytowania mogą się nie pokazać, a sumy między widokami się różnią,
- **Citation Share nie pokazuje konkurencji**: tylko nasz udział, bez tego, kto ma resztę,
- **cytowanie ≠ ruch**: to nie kliknięcia ani pozycja w wynikach; *Compare* mówi, co się zmieniło, nie dlaczego.

## 3. Google Search Console (właściciel, raz na domenę)

<https://search.google.com/search-console>: dodaj usługę (domena przez rekord DNS albo prefiks URL przez plik
lub meta tag). Rekord DNS zmienia tylko właściciel, bo zmiany DNS to osobna zgoda. Potem w sekcji Sitemapy wpisz
`sitemap-index.xml`. Search Console i Bing Webmaster Tools pokażą też błędy indeksowania; raz w miesiącu warto je przejrzeć.

## W raporcie z wdrożenia

- wynik `indexnow.py zglos` (liczba adresów, odpowiedź HTTP),
- czy domena jest już w Bing Webmaster Tools i Search Console (pytamy właściciela przy pierwszym wdrożeniu),
- jeśli nie: instrukcja z punktów 2 i 3, prostym językiem, z gotowym adresem sitemapy,
- raport AI Performance przejrzany: tak/nie (data eksportu i zakres; „nie”, gdy od dodania witryny minęło mniej niż 48 h).

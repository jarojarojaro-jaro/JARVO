# Zgłoszenie strony wyszukiwarkom (po wdrożeniu produkcyjnym)

Sama sitemap w `robots.txt` nie wystarcza: nowa strona czeka wtedy tygodniami, aż roboty same ją znajdą. Bing to
osobny indeks od Google, a z jego wyników korzystają też inne wyszukiwarki i asystenci AI z wyszukiwaniem.
Dlatego po każdym wdrożeniu produkcyjnym robimy trzy rzeczy.

## 1. IndexNow (agent sam, bez konta)

Protokół [IndexNow](https://www.indexnow.org/documentation): strona ma plik `https://domena/<klucz>.txt` z kluczem,
a my wysyłamy listę zmienionych adresów. Wyszukiwarki IndexNow (m.in. Bing, Yandex, Seznam, Naver) dzielą się
zgłoszeniami, więc jedno zgłoszenie do `api.indexnow.org` wystarcza. Google IndexNow nie obsługuje.

- Klucz powstaje raz, przy zakładaniu projektu: `python3 indexnow.py klucz <projekt>/public` (skill `nowa-strona`).
  Plik trafia do `dist/`, więc jest w odcisku zgody. Klucz jest jawny z założenia, to nie sekret.
  Starszy projekt bez klucza: klucz dodajemy przed buildem, który idzie do zgody, nigdy po zgodzie.
- Po wdrożeniu: `python3 indexnow.py zglos https://domena.pl --katalog <projekt>/public`. Skrypt czyta sitemapę z produkcji,
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

## 3. Google Search Console (właściciel, raz na domenę)

<https://search.google.com/search-console>: dodaj usługę (domena przez rekord DNS albo prefiks URL przez plik
lub meta tag). Rekord DNS zmienia tylko właściciel, bo zmiany DNS to osobna zgoda. Potem w sekcji Sitemapy wpisz
`sitemap-index.xml`. Search Console i Bing Webmaster Tools pokażą też błędy indeksowania; raz w miesiącu warto je przejrzeć.

## W raporcie z wdrożenia

- wynik `indexnow.py zglos` (liczba adresów, odpowiedź HTTP),
- czy domena jest już w Bing Webmaster Tools i Search Console (pytamy właściciela przy pierwszym wdrożeniu),
- jeśli nie: instrukcja z punktów 2 i 3, prostym językiem, z gotowym adresem sitemapy.

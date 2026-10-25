# Wyszukiwanie: playbook

## Narzędzia
- `web_search`: najlepsza dostępna wyszukiwarka, którą Hermes wybiera sam: z kluczem API właściciela, własny SearXNG
  (wiele silników naraz; na serwerze), DuckDuckGo (ddgs) albo darmowe wyszukiwarki Hermesa. Szukasz zawsze tak samo.
- `@@PY@@ "$HERMES_HOME/scripts/search_fanout.py" "<zapytanie>" [--lang pl] [--category general|news|science|it] [--time month|year]`:
  jedno zapytanie → wiele kategorii/języków, deduplikacja URL-i, JSON. Używaj przy szerokim rozpoznaniu. Działa
  z SearXNG albo DuckDuckGo (pole `wyszukiwarka` w wyniku); kod 2 „brak wyszukiwarki” = szukaj przez `web_search`.
- `@@PY@@ "$HERMES_HOME/scripts/extract.py" <url>`: czysta treść strony + data publikacji + autor (trafilatura). Lepsze niż surowy HTML.
- strona z JavaScriptem (SPA), gdy `extract.py` zwraca pusto: przeglądarka (`browser_navigate` i `browser_snapshot`);
  na Linuksie i macOS także `lightpanda fetch --dump markdown <url>` (~30 MB RAM, bez Chromium; na Windows go nie ma).
- przeglądarka (`browser_*`): klikanie, formularze wyszukiwania, tabele, zrzuty (silnik Lightpanda, Chromium przy
  zrzutach; na Windows zawsze Chromium); logowanie **nie**.
- skille: `searxng-search`, `duckduckgo-search` (inny indeks = niezależność), `scrapling`, `blocked-page-recovery`,
  `arxiv` (nauka), `youtube-content` (transkrypcje), `reddit-reading` (opinie użytkowników), `rss-feeds`.

## Strona odmówiła (403/429, „Just a moment…”, „Human Verification”, captcha)
1. Kopia w archiwum: `blocked-page-recovery` (Wayback, archive.today). Cytujesz z datą kopii.
2. Potrzebny stan bieżący albo kopii nie ma: **jedna** próba Camoufoxem, skill `ostrozna-przegladarka`:
   `@@PY@@ "$HERMES_HOME/skills/web/ostrozna-przegladarka/scripts/ostrozna.py" <url> -o out/strony/<nazwa>.md`,
   potem `sources.py add <url> --tekst out/strony/<nazwa>.md --rejestr <rejestr>` (numer `[n]` jak przy `extract.py`)
   i dopisek „odczyt przez Camoufox” przy źródle w notatkach wątku.
3. Kod 3 w `ostrozna.py` = koniec: luka w raporcie („źródło odmawia automatom”), szukasz innego źródła tej samej
   informacji, nie innej drogi do tej strony. Serwisy za Cloudflare zwykle odmawiają także Camoufoxowi.

## Technika
1. **Szeroko → wąsko.** Pierwsze zapytanie ogólne, kolejne precyzyjne na podstawie znalezionych nazw i terminów.
2. **Dwa języki.** Zapytanie po polsku i po angielsku (często inne źródła, inne wyniki).
3. **Operatory:** `"dokładna fraza"`, `site:gov.pl`, `site:europa.eu`, `filetype:pdf`, `-słowo`, `intitle:`.
4. **Źródło pierwotne:** gdy artykuł cytuje raport/badanie/ustawę, znajdź ORYGINAŁ i czytaj go, nie artykuł.
5. **Świeżość:** dla tematów zmiennych filtr czasu (`--time year`); zawsze notuj datę źródła.
6. **Różne typy źródeł:** oficjalne, branżowe, naukowe, media, użytkownicy (fora), dane (statystyki).
7. **Zatrzymaj się**, gdy 2 kolejne wyszukiwania nie wnoszą nic nowego.

## Pułapki
- Farmy treści i strony „AI-generated” przepisujące to samo: jedno źródło w wielu kopiach to nadal jedno źródło.
- Wyniki sponsorowane i rankingi afiliacyjne („10 najlepszych…”): niska wiarygodność, konflikt interesów.
- Stare dane pokazywane jako aktualne: sprawdzaj datę w treści, nie tylko w URL-u.

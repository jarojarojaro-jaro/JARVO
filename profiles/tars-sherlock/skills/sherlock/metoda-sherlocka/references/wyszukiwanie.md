# Wyszukiwanie: playbook

## Narzędzia
- `web_search`: przez własny SearXNG (wiele silników naraz, bez kluczy).
- `python3 $HERMES_HOME/scripts/search_fanout.py "<zapytanie>" [--lang pl] [--category general|news|science|it] [--time month|year]`:
  jedno zapytanie → wiele kategorii/języków, deduplikacja URL-i, JSON. Używaj przy szerokim rozpoznaniu.
- `python3 $HERMES_HOME/scripts/extract.py <url>`: czysta treść strony + data publikacji + autor (trafilatura). Lepsze niż surowy HTML.
- przeglądarka (`browser_*`): strony z JavaScriptem, tabele, logowanie **nie**.
- skille: `searxng-search`, `duckduckgo-search` (inny indeks = niezależność), `scrapling`, `blocked-page-recovery`,
  `arxiv` (nauka), `youtube-content` (transkrypcje), `reddit-reading` (opinie użytkowników), `rss-feeds`.

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

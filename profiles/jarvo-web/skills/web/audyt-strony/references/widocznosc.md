---
source: "Google Search Central (dokumentacja indeksowania, 2026); llmstxt.org (propozycja llms.txt, J. Howard); checklista „show up in Google” (film, wrzesień 2026)"
reviewed: "2026-10-05"
---
# Widoczność w Google i w wyszukiwarkach AI: 23 punkty

| # | Punkt | Sprawdza | Dobry stan |
|---|---|---|---|
| 1 | sitemap | `seo_check.py` (crawl, `--dir`) | `sitemap.xml` albo `sitemap-index.xml` (`@astrojs/sitemap`), wszystkie kanoniczne strony, zgłoszona w Search Console |
| 2 | robots.txt | `seo_check.py` | istnieje, **nie** `Disallow: /` dla `*`, wpis `Sitemap:` |
| 3 | brak noindex | `seo_check.py` (head) | produkcja bez `noindex`; podglądy i staging z `noindex`, sprawdzane z `--podglad` (noindex to wtedy info) |
| 4 | canonical | `seo_check.py` | bezwzględny URL tej strony na domenie produkcyjnej (`--dir --base-url`: host i ścieżka) |
| 5 | title | `seo_check.py` (`--dir`: duplikaty) | 15–60 znaków, inny na każdej podstronie, fraza z przodu |
| 6 | meta description | `seo_check.py` (`--dir`: duplikaty) | 70–160 znaków (zalecane 140–160), inny na każdej podstronie, zachęca do kliknięcia |
| 7 | jeden H1 | `seo_check.py` | dokładnie 1 na stronę |
| 8 | hierarchia nagłówków | `seo_check.py` | bez przeskoków (h2 → h4) |
| 9 | alt | `seo_check.py` | opisowy alt (nie nazwa pliku ani „zdjęcie”); dekoracyjne `alt=""`; `alt="TODO"` = błąd |
| 10 | dane strukturalne | `seo_check.py` (jsonld) | Organization + typ strony (Product, FAQ, Article…), bez błędów |
| 11 | linki wewnętrzne | `seo_check.py` (content) | ≥ 3 do powiązanych podstron, opisowe teksty linków |
| 12 | martwe linki | `linkinator <url> --recurse` | 0 błędów 4xx/5xx |
| 13 | kompresja obrazów | `optymalizacja-obrazow` | AVIF/WebP, `srcset`, wymiary |
| 14 | Core Web Vitals | Lighthouse / `core-web-vitals` | LCP < 2,5 s, INP < 200 ms, CLS < 0,1 |
| 15 | responsywność | zrzuty 375/768/1440, `hostile.cjs` | brak poziomego przewijania, cele dotyku ≥ 44 px |
| 16 | HTTPS | `security_check.py url` | certyfikat, 301 z http, HSTS |
| 17 | czyste adresy | `seo_check.py` (content) | małe litery, myślniki, słowa zamiast ID, bez `.php` |
| 18 | llms.txt | `seo_check.py` (crawl) | `/llms.txt` wg szablonu niżej |
| 19 | strategia linków zewnętrznych | ręcznie + Sherlock | plan poniżej |
| 20 | strona 404 | `seo_check.py` (crawl, `--dir`) | `404.html` w layoucie strony, link do strony głównej, `noindex`; nieistniejący adres zwraca HTTP 404 (200 = „soft 404”) |
| 21 | obraz OG | `seo_check.py` (og) | `og:image` bezwzględny, HTTP 200, `image/*`, PNG albo JPEG 1200×630; `twitter:card` = `summary_large_image` |
| 22 | landmarki | `seo_check.py` (content) | `<header>`, `<nav>`, dokładnie jeden `<main>`, `<footer>` |
| 23 | cała witryna | `seo_check.py --dir dist` | każda strona z buildu bez błędów, bez duplikatów title/description/canonical, żadna poza sitemapą |

Tryby `seo_check.py`: adres (`<url>`, sieć: robots, sitemap, llms.txt, 404, obraz OG), podgląd (`<url> --podglad`),
build (`--dir dist --base-url https://domena.pl`, bez sieci: wszystkie strony i pliki w katalogu).

## Szablon `/llms.txt` (Markdown w katalogu głównym)
```markdown
# <Nazwa marki>

> <Jedno zdanie: co to jest i dla kogo.>

<2–3 zdania kontekstu: oferta, obszar działania, czym się wyróżnia.>

## Najważniejsze strony
- [Oferta](https://domena.pl/oferta): <co tam jest>
- [Cennik](https://domena.pl/cennik): <co tam jest>
- [Kontakt](https://domena.pl/kontakt): <adres, godziny>

## Opcjonalnie
- [Blog](https://domena.pl/blog): <tematy>
```
Tylko prawdziwe, publiczne strony. Aktualizuj razem z sitemap.xml. To propozycja standardu, nie gwarancja
widoczności w AI: dodaj, bo kosztuje minutę, ale nie obiecuj efektu.

## Strategia linków zewnętrznych (plan, nie kupowanie linków)
1. **Research** (karta dla `jarvo-sherlock`, skill `research-seo`): kto linkuje do konkurencji, katalogi branżowe
   i lokalne (Google Business Profile, katalogi PL), media branżowe, partnerzy.
2. **Fundament:** profil Google Business, spójne NAP (nazwa, adres, telefon) w katalogach, profile społecznościowe
   z linkiem.
3. **Treści warte linku:** raport z danymi, kalkulator, poradnik (Web buduje stronę, Studio treść).
4. **Relacje:** partnerzy, dostawcy, klienci (case study z linkiem), wystąpienia i podcasty.
5. **Czego nie robić:** kupowanie linków, farmy, wymiany masowe (ryzyko kary od Google).
Wynik: `out/SEO-LINKI.md` z listą 20–30 celów (źródło, dlaczego, jak zdobyć, kto) i kolejnością.

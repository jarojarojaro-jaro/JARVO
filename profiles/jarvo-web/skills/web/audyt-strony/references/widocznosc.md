---
source: "Google Search Central (dokumentacja indeksowania, 2026); llmstxt.org (propozycja llms.txt, J. Howard); checklista „show up in Google” (film, wrzesień 2026)"
reviewed: "2026-09-29"
---
# Widoczność w Google i w wyszukiwarkach AI: 19 punktów

| # | Punkt | Sprawdza | Dobry stan |
|---|---|---|---|
| 1 | sitemap.xml | `seo_check.py` (crawl) | wszystkie kanoniczne strony, zgłoszona w Search Console |
| 2 | robots.txt | `seo_check.py` | istnieje, **nie** `Disallow: /` dla `*`, wpis `Sitemap:` |
| 3 | brak noindex | `seo_check.py` (head) | produkcja bez `noindex` (podglądy i staging: z `noindex`) |
| 4 | canonical | `seo_check.py` | bezwzględny URL tej strony |
| 5 | title | `seo_check.py` | 15–60 znaków, unikalny, fraza z przodu |
| 6 | meta description | `seo_check.py` | 70–160 znaków, zachęca do kliknięcia |
| 7 | jeden H1 | `seo_check.py` | dokładnie 1 na stronę |
| 8 | hierarchia nagłówków | `seo_check.py` | bez przeskoków (h2 → h4) |
| 9 | alt | `seo_check.py` | opisowy alt; dekoracyjne `alt=""` |
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

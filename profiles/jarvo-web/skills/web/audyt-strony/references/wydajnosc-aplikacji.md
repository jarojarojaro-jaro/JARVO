---
source: "Dokumentacja Supabase (RLS performance, Advisors), Postgres (indeksy, EXPLAIN), Next.js, Astro i Vercel (regiony funkcji, cache); stan październik 2026"
reviewed: "2026-10-14"
---
# Wydajność aplikacji z backendem (11 punktów)

Lighthouse mierzy wejście na stronę. Aplikacja z logowaniem, bazą i API zwalnia gdzie indziej: w zapytaniach,
politykach RLS, kolejności wywołań i w tym, co serwer robi, zanim odpowie. Ta lista dotyczy **każdej strony z bazą
albo API** (czysty statyczny landing: n/d, wystarczy Lighthouse). Każdy punkt: ✓ z dowodem (plik:linia, wynik
`EXPLAIN`, czas z narzędzi przeglądarki), ✗ z poprawką albo „n/d” z powodem. Wynik w `out/RAPORT.md`, sekcja
„Wydajność backendu”; ✗ w punktach 1–5 to co najmniej P1 w priorytetach audytu.

| # | Punkt | Jak sprawdzić | Dobry stan |
|---|---|---|---|
| 1 | Indeksy na kolumnach z filtrów i sortowania | zapytania w kodzie (`where`, `order by`, `.eq()`, `.order()`); `explain analyze` na danych testowych | indeks na każdej kolumnie, po której filtrujesz albo sortujesz w częstym zapytaniu; w planie `Index Scan`, nie `Seq Scan` na dużej tabeli |
| 2 | Polityki RLS szybkie | `security_check.py repo` (polityki w `*.sql`), panel Supabase → Advisors → Performance | `(select auth.uid()) = user_id` (nie `auth.uid() = user_id`: liczy się dla każdego wiersza), rola `to authenticated`, **indeks na kolumnie z polityki** (`user_id`); Advisor bez `auth_rls_initplan` i `unindexed_foreign_keys` |
| 3 | Bez zapytań N+1 | pętla z zapytaniem w środku (`for`/`map` + `await db…`/`supabase.from`), log zapytań na jednym widoku | jedno zapytanie z `join`/`in (…)`/zagnieżdżonym `select` Supabase zamiast zapytania na każdy wiersz |
| 4 | Długie listy stronicowane | trasy i zapytania list (zamówienia, wiadomości, produkty) | `limit` + stronicowanie (najlepiej kursorem po indeksowanej kolumnie); nigdy „pobierz wszystko i przytnij na froncie” |
| 5 | Zapytania równolegle, nie po kolei | handler albo strona z kilkoma `await` niezależnych wywołań | `Promise.all` / `asyncio.gather` dla niezależnych zapytań, albo jedno zapytanie zamiast kilku |
| 6 | Ciężka praca w tle | wysyłka e-maili, obróbka obrazów, raporty, wywołania AI w handlerze odpowiedzi | kolejka albo zadanie w tle (Supabase Queues/Edge Function, cron, worker); odpowiedź od razu ze stanem „w toku” |
| 7 | Serwer blisko bazy | region bazy (panel) i region funkcji (Vercel: domyślnie USA, `iad1`; Netlify, Cloudflare) | funkcje w tym samym regionie co baza (dla Polski zwykle Frankfurt: Supabase `eu-central-1`, Vercel `fra1`) |
| 8 | Cache tylko publicznych odpowiedzi | `security_check.py url` i `atak` (punkt 28 listy bezpieczeństwa) | dane takie same dla wszystkich: cache CDN albo strona statyczna/ISR; dane zalogowanego: `Cache-Control: private, no-store` |
| 9 | Treść na pierwszym ekranie z serwera | widok źródła strony (`view-source:`) albo `curl` | HTML z treścią przy pierwszym wejściu (Astro, SSR, komponenty serwerowe); bez pustej strony czekającej na `fetch` z przeglądarki |
| 10 | Szkielety zamiast skoków | zrzut przy wolnym łączu (`hostile.cjs --only slow3g`) | szkielet albo stan ładowania o wymiarach docelowej treści (CLS < 0,1); bez pustego ekranu |
| 11 | Odpowiedzi AI strumieniowane | trasa czatu albo generowania tekstu | strumień (SSE / `ReadableStream`), pierwsze słowa w < 1 s; przerwanie przy zamknięciu strony |

## Zasady
- Najpierw pomiar: czas odpowiedzi trasy (`curl -w '%{time_total}'`, panel hostingu) przed i po poprawce, w raporcie.
- Indeks to też koszt zapisu: tylko kolumny z częstych zapytań, nie „na wszystko”.
- Region zmienia człowiek w panelu hostingu albo w konfiguracji projektu (zmiana na produkcji to wdrożenie, A2).
- Doradca Supabase (Advisors → Performance i Security) to darmowy pomiar: jego wynik dołączasz do raportu.

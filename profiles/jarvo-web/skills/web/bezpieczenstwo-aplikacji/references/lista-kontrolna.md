---
source: "OWASP Top 10 (2021), OWASP Top 10 for LLM Applications (2025) i ASVS 4.0; checklisty „vibe-coded app security” (film i lista 30 punktów, wrzesień 2026); MDN Security headers"
reviewed: "2026-09-30"
---
# Lista kontrolna (26 + nagłówki)

Punkty 1–18: podstawa każdej aplikacji. 19–22: dane i sesje. 23–25: tylko aplikacje z funkcją AI (inaczej „n/d”).
26: każda aplikacja z bazą. „Atak” = `security_check.py atak` na podglądzie (krok 2b skilla): dowód działania, nie
tylko kod.

| # | Punkt | Jak sprawdzić | Dobry stan |
|---|---|---|---|
| 1 | Trasy admina chronione | atak `--chronione /api/admin …`; jako zwykły użytkownik: przegląd kodu | 401/403 z serwera, nie tylko ukryty przycisk |
| 2 | Uprawnienia sprawdzane na serwerze | każda akcja API: kto może? (middleware/handler) | sprawdzenie w handlerze, nie w UI |
| 3 | RLS w bazie (Supabase/Postgres) | `select relrowsecurity from pg_class` / panel Supabase | RLS włączone na każdej tabeli z danymi użytkowników + polityki |
| 4 | Weryfikacja e-mail | rejestracja bez kliknięcia w link | brak dostępu do funkcji do czasu weryfikacji |
| 5 | Hasła haszowane | kod rejestracji | argon2id albo bcrypt (koszt ≥ 12); nigdy md5/sha1/plain |
| 6 | Tokeny poza localStorage | `security_check.py repo` | ciasteczko `HttpOnly; Secure; SameSite=Lax` |
| 7 | Sekrety tylko na serwerze | `security_check.py url` (JS wysyłany do przeglądarki), zmienne `NEXT_PUBLIC_*`/`VITE_*` | na froncie tylko klucze publiczne (anon, publishable) |
| 8 | `.env` poza gitem | `security_check.py repo` (też historia) | `.env*` w `.gitignore`, w repo tylko `.env.example` |
| 9 | Sekrety poza logami | logi aplikacji, `console.log` przy auth/płatnościach | brak tokenów, haseł, pełnych danych kart i PESEL w logach |
| 10 | SQL z parametrami | `security_check.py repo`, przegląd zapytań | `$1`/`?`/ORM; zero sklejania stringów |
| 11 | Walidacja formularzy | schemat po stronie serwera (zod/valibot/pydantic) | walidacja na serwerze; klient tylko dla wygody |
| 12 | Blokada XSS | `innerHTML`, `dangerouslySetInnerHTML`, `set:html`, `v-html` | tekst albo DOMPurify; CSP bez `unsafe-inline` dla skryptów |
| 13 | Walidacja uploadu | atak `--upload`; kod: typ po zawartości (magic bytes), rozmiar, nazwa | limit rozmiaru, lista typów, losowa nazwa, pliki w prywatnym buckecie (nie na serwerze aplikacji) |
| 14 | Podpisy webhooków | handler Stripe/GitHub/… | weryfikacja podpisu (HMAC) i znacznika czasu przed akcją |
| 15 | Limit żądań | atak `--logowanie`, `--limit`; kod: rejestracja, reset hasła, API | np. 5 prób/min/IP na logowanie; 429 z `Retry-After` |
| 16 | CORS zaostrzony | `security_check.py url` | lista domen; nigdy `*` z ciasteczkami |
| 17 | Debug wyłączony na produkcji | `security_check.py url`, konfiguracja | własne strony błędów, zero śladów stosu |
| 18 | Zależności aktualne i zaufane | `security_check.py repo` (`npm audit`, pakiety nieistniejące, młode, o nazwie jak popularne) + `supply-chain-risk-auditor` (krok 1b) | 0 critical/high; każdy pakiet istnieje i jest znany; porzucone pakiety i skrypty instalacyjne opisane; Dependabot/Renovate włączone |
| 19 | Własność danych (konto A ≠ konto B) | atak `--sesja-a/--sesja-b --zasob-a` na dwóch kontach testowych; kod: każde zapytanie o rekord | B dostaje 403/404; zapytania z właścicielem z sesji (`user_id = $2`) albo RLS |
| 20 | CSRF | akcje zmieniające stan (POST/PUT/PATCH/DELETE) z ciasteczkiem sesji | `SameSite=Lax` + token CSRF albo sprawdzenie `Origin`; akcje serwerowe frameworka z jego ochroną |
| 21 | Sesje i tokeny wygasają | atak `--wyloguj`; konfiguracja auth | krótki token dostępu (≤ 1 h) z odświeżaniem i rotacją, sesja ≤ 30 dni; wylogowanie i zmiana hasła unieważniają sesję na serwerze |
| 22 | Prywatne buckety | panel Supabase Storage / S3 / R2, polityki bucketów | prywatne domyślnie, pliki przez podpisane adresy z krótkim czasem; publiczne tylko zasoby publiczne z założenia |
| 23 | Endpointy AI z limitami | kod trasy AI; panel dostawcy | tylko dla zalogowanych, limit na użytkownika i IP, limit długości wejścia i `max_tokens`; **twardy limit wydatków** u dostawcy AI i w chmurze (ustawia człowiek) |
| 24 | Funkcje LLM a prompt injection | przepływ: co trafia do promptu | treść użytkownika, stron i plików jako dane (oddzielona od instrukcji); bez sekretów i cudzych danych w kontekście; odpowiedź modelu walidowana schematem i oczyszczana przed renderem |
| 25 | Model z narzędziami i SQL | lista narzędzi, konto bazy modelu | lista dozwolonych narzędzi; SQL tylko do odczytu na osobnym koncie z RLS albo przez widoki; limit kroków, czasu i kosztu; płatność, wysyłka, usuwanie tylko z potwierdzeniem człowieka |
| 26 | Kopie zapasowe i próba odtworzenia | panel bazy (Supabase: backupy/PITR), skrypt `pg_dump` | automatyczna kopia poza serwerem aplikacji + **odtworzenie na świeżej bazie** z datą ostatniej próby (ustawia i sprawdza człowiek albo `wdrozenie`) |
| N | Nagłówki | `security_check.py url` | HTTPS + HSTS, CSP (`frame-ancestors 'none'`), nosniff, Referrer-Policy, Permissions-Policy |

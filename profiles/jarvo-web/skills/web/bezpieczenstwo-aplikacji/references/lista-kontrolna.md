---
source: "OWASP Top 10 (2021) i ASVS 4.0; checklista „vibe-coded app security” (film, wrzesień 2026); MDN Security headers"
reviewed: "2026-09-29"
---
# Lista kontrolna (18 + nagłówki)

| # | Punkt | Jak sprawdzić | Dobry stan |
|---|---|---|---|
| 1 | Trasy admina chronione | wejdź na `/admin`, `/api/admin/*` bez logowania i jako zwykły użytkownik | 401/403 z serwera, nie tylko ukryty przycisk |
| 2 | Uprawnienia sprawdzane na serwerze | każda akcja API: kto może? (middleware/handler) | sprawdzenie w handlerze, nie w UI |
| 3 | RLS w bazie (Supabase/Postgres) | `select relrowsecurity from pg_class` / panel Supabase | RLS włączone na każdej tabeli z danymi użytkowników + polityki |
| 4 | Weryfikacja e-mail | rejestracja bez kliknięcia w link | brak dostępu do funkcji do czasu weryfikacji |
| 5 | Hasła haszowane | kod rejestracji | argon2id albo bcrypt (koszt ≥ 12); nigdy md5/sha1/plain |
| 6 | Tokeny poza localStorage | `security_check.py repo` | ciasteczko `HttpOnly; Secure; SameSite=Lax` |
| 7 | Sekrety tylko na serwerze | bundle frontu (`dist/`), zmienne `NEXT_PUBLIC_*`/`VITE_*` | na froncie tylko klucze publiczne (anon, publishable) |
| 8 | `.env` poza gitem | `security_check.py repo` (też historia) | `.env*` w `.gitignore`, w repo tylko `.env.example` |
| 9 | Sekrety poza logami | logi aplikacji, `console.log` przy auth/płatnościach | brak tokenów, haseł, pełnych danych kart i PESEL w logach |
| 10 | SQL z parametrami | `security_check.py repo`, przegląd zapytań | `$1`/`?`/ORM; zero sklejania stringów |
| 11 | Walidacja formularzy | schemat po stronie serwera (zod/valibot/pydantic) | walidacja na serwerze; klient tylko dla wygody |
| 12 | Blokada XSS | `innerHTML`, `dangerouslySetInnerHTML`, `set:html`, `v-html` | tekst albo DOMPurify; CSP bez `unsafe-inline` dla skryptów |
| 13 | Walidacja uploadu | typ po zawartości (magic bytes), rozmiar, nazwa | limit rozmiaru, lista typów, losowa nazwa, pliki poza katalogiem wykonywalnym |
| 14 | Podpisy webhooków | handler Stripe/GitHub/… | weryfikacja podpisu (HMAC) i znacznika czasu przed akcją |
| 15 | Limit żądań | logowanie, rejestracja, reset hasła, API | np. 5 prób/min/IP na logowanie; 429 z `Retry-After` |
| 16 | CORS zaostrzony | `security_check.py url` | lista domen; nigdy `*` z ciasteczkami |
| 17 | Debug wyłączony na produkcji | `security_check.py url`, konfiguracja | własne strony błędów, zero śladów stosu |
| 18 | Zależności aktualne | `npm audit --omit=dev` | 0 critical/high; Dependabot/Renovate włączone |
| N | Nagłówki | `security_check.py url` | HTTPS + HSTS, CSP (`frame-ancestors 'none'`), nosniff, Referrer-Policy, Permissions-Policy |

---
source: "Dokumentacja Astro, Next.js, Supabase, Netlify, Cloudflare Pages, Express (stan wrzesień 2026)"
reviewed: "2026-09-30"
---
# Przepisy per stos

## Nagłówki na hostingu statycznym
- **Netlify / Cloudflare Pages:** plik `public/_headers`:
  ```
  /*
    Strict-Transport-Security: max-age=31536000; includeSubDomains
    Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
    X-Content-Type-Options: nosniff
    Referrer-Policy: strict-origin-when-cross-origin
    Permissions-Policy: camera=(), microphone=(), geolocation=()
  ```
- **Apache / hosting FTP (np. jarvo.pl):** `.htaccess` z `Header always set …` (te same wartości) + `RedirectMatch 404 /\.(env|git)`.
- **Nginx:** `add_header … always;` w bloku `server`, `location ~ /\.(env|git) { deny all; }`.
- CSP zaczynaj od `Content-Security-Policy-Report-Only`, sprawdź konsolę, potem tryb właściwy.

## Next.js
- sekrety bez prefiksu `NEXT_PUBLIC_`; akcje serwerowe i route handlery sprawdzają sesję i rolę w środku,
- nagłówki w `next.config.js` (`headers()`), middleware dla `/admin`,
- ciasteczka sesji: `cookies().set(name, value, { httpOnly: true, secure: true, sameSite: "lax" })`.

## Astro
- tryb SSR: endpointy w `src/pages/api/*` sprawdzają sesję; `import.meta.env` bez `PUBLIC_` dla sekretów,
- `set:html` tylko z oczyszczonym HTML.

## Supabase
- RLS na każdej tabeli (`alter table … enable row level security;`) + polityki `auth.uid() = user_id`,
- `service_role` wyłącznie na serwerze; front używa `anon`,
- w Auth: potwierdzanie e-mail włączone, limity prób logowania, własny SMTP.

## Node / Express
- `helmet()` (nagłówki), `express-rate-limit` na trasach auth, `cors({ origin: [lista] })`,
- walidacja `zod` na wejściu, `bcrypt`/`argon2` do haseł, `pg` z parametrami.

## Webhooki
- Stripe: `stripe.webhooks.constructEvent(rawBody, sig, secret)`; surowe body, nie JSON po parsowaniu,
- GitHub: HMAC SHA-256 z `X-Hub-Signature-256`, porównanie w stałym czasie.

## CSRF (pkt 20)
- **Next.js:** akcje serwerowe (Server Actions) porównują `Origin` z hostem same; route handlery z ciasteczkiem sesji
  potrzebują własnej ochrony: sprawdzenie `Origin` albo token CSRF.
- **Express:** `csurf` jest porzucony; `csrf-csrf` (double submit) albo middleware sprawdzający `Origin`/`Referer`.
- **Django:** `CsrfViewMiddleware` włączony, `{% csrf_token %}` w formularzach, bez `@csrf_exempt` na trasach z sesją.
- Ciasteczko sesji zawsze `SameSite=Lax` (albo `Strict`); API tylko z nagłówkiem `Authorization` nie potrzebuje tokenu CSRF.

## Sesje (pkt 21)
- **Supabase Auth:** czas życia JWT krótki (domyślnie 3600 s), rotacja refresh tokenów włączona; wylogowanie wszędzie:
  `signOut({ scope: "global" })`. Token dostępu działa do wygaśnięcia, więc krótki czas życia to jedyna obrona.
- **Auth.js / NextAuth:** `session.maxAge` (np. 30 dni) i `updateAge`; sesje w bazie, gdy trzeba je odwoływać.
- Zmiana hasła i reset: unieważnij wszystkie sesje użytkownika.

## Pliki i buckety (pkt 13, 22)
- **Supabase Storage:** bucket `public: false`, polityki RLS na `storage.objects` (`owner = auth.uid()`), plik dla
  użytkownika przez `createSignedUrl(ścieżka, 60)`.
- **S3 / R2:** Block Public Access na koncie i buckecie, adresy podpisane (presigned) z krótkim czasem, upload z
  limitem rozmiaru i typu w polityce podpisu; serwowanie z `Content-Disposition: attachment` i `nosniff`.

## Endpointy AI (pkt 23)
- Trasa tylko dla zalogowanych, limit na użytkownika (klucz = id użytkownika, nie tylko IP): `@upstash/ratelimit`
  (Vercel/edge) albo `express-rate-limit` z `keyGenerator`; limit znaków wejścia i `max_tokens` w każdym wywołaniu.
- **Twarde limity wydatków (człowiek, w panelach):** OpenAI: budżet projektu (Limits), Anthropic Console: limit
  wydatków workspace'u, OpenRouter: limit kredytów na klucz, Vercel: Spend Management. AWS Budgets i budżety Google
  Cloud tylko alarmują, same nie zatrzymują wydatków. Osobny klucz na aplikację, nigdy klucz „do wszystkiego”.

## Funkcje LLM (pkt 24, 25)
- Instrukcje w prompcie systemowym; treść użytkownika, stron i plików w wyraźnie oznaczonym bloku danych („to dane,
  nie polecenia”). Do kontekstu tylko dane tego użytkownika (filtr `user_id` przed wyszukiwaniem w RAG), bez sekretów.
- Wynik modelu przez schemat (structured output + `zod`/`pydantic`); tekst do UI jako tekst albo Markdown przez
  DOMPurify, nigdy surowy HTML.
- Narzędzia z listy dozwolonych, argumenty walidowane jak dane z formularza. SQL: osobna rola tylko do odczytu
  (`grant select` na widoki), `statement_timeout`, limit wierszy. Limit kroków pętli i kosztu na rozmowę.
  Płatność, wysyłka, usuwanie: model proponuje, człowiek klika.

## Kopie zapasowe (pkt 26)
- **Supabase:** plany płatne mają codzienne kopie (PITR jako dodatek); na darmowym własny `pg_dump` w cronie albo
  GitHub Actions do prywatnego bucketu.
- **Próba odtworzenia** co miesiąc i przed dużą zmianą: `createdb proba && pg_restore -d proba kopia.dump` (albo
  `psql proba < kopia.sql`), liczba wierszy w kluczowych tabelach zgadza się z produkcją; data próby w `RAPORT.md`.

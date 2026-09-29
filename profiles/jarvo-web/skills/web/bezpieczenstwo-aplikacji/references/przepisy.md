---
source: "Dokumentacja Astro, Next.js, Supabase, Netlify, Cloudflare Pages, Express (stan wrzesień 2026)"
reviewed: "2026-09-29"
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

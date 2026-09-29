# jarvo-web: Web Senior Dev

Strony od faviconu po SEO. Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-web-web-senior-dev).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: budżety jakości, mobile-first, marka, A2 dla produkcji |
| `skills/web/` | 9: brand-z-url, audyt-strony, nowa-strona, bramka-jakosci, landing-produktowy, favicon-i-meta, optymalizacja-obrazow, wdrozenie, bezpieczenstwo-aplikacji |
| skille zewnętrzne | 55: web-quality-skills (5), claude-seo (13), marketingskills (3), Anthropic (2), Hermes (6), impeccable, GSAP (8), Three.js (10), motion (5), text-to-lottie, graf-kodu (`shared/skills`): `vendor/skills.lock.yaml` |
| `scripts/` | `audit.sh` (Lighthouse + axe + linkinator + SEO + zrzuty), `seo_check.py`, `screenshots.cjs`, `a11y.cjs`, `favicons.cjs`, `images.cjs`, `brand_extract.sh`, `hostile.cjs` (testy wrogie: wolne łącze, brak JS, 320 px, klawiatura…), `security_check.py` (bezpieczeństwo repo i strony) |
| `config.yaml` | model strong; produkcja/DNS/push na main → eskalacja; pracownicy bez zgody = odmowa |
| `quality/rubric.md` | rubryka sędziego |

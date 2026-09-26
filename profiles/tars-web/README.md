# tars-web: Web Senior Dev

Strony od faviconu po SEO. Spec: [docs/FLEET.md](../../docs/FLEET.md#tars-web-web-senior-dev).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: budżety jakości, mobile-first, marka, A2 dla produkcji |
| `skills/web/` | brand-z-url, audyt-strony, nowa-strona, landing-produktowy, favicon-i-meta, optymalizacja-obrazow, wdrozenie |
| skille zewnętrzne | web-quality-skills (5), claude-seo (13), marketingskills (3), Anthropic (2), Hermes (7): `vendor/skills.lock.yaml` |
| `scripts/` | `audit.sh` (Lighthouse + axe + linkinator + SEO + zrzuty), `seo_check.py`, `screenshots.cjs`, `a11y.cjs`, `favicons.cjs`, `images.cjs`, `brand_extract.sh` |
| `config.yaml` | model strong; produkcja/DNS/push na main → eskalacja; pracownicy bez zgody = odmowa |
| `quality/rubric.md` | rubryka sędziego |

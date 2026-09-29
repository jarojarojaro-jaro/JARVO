# jarvo-reka: prawa ręka

Generalista wykonawczy. Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-reka-prawa-ręka).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: wykonuje wszystko szybko, sprawdza, mówi, kiedy oddać specjaliście |
| `skills/reka/` | 4: zlozenie-pakietu, dokumenty, szybki-prototyp, kiedy-oddac-snajperowi |
| skille | 2 z locka (`skill-creator`, `graf-kodu`) + pełny katalog Hermesa (dosiewany przy starcie) + skille Sherlocka, Web i Studio tylko do odczytu (`skills.external_dirs` → build `:ro`; Wideograf i Ads jeszcze niepodpięte) |
| `scripts/` | `pack.py` (pakiet misji + manifest + zip), `to_pdf.py` (pandoc + Chromium, LibreOffice opcjonalnie) |
| `quality/rubric.md` | rubryka sędziego |

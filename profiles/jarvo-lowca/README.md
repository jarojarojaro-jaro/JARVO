# jarvo-lowca: Łowca leadów

Firmy z „dlaczego teraz” z oficjalnych, darmowych źródeł. Projekt i granice: [docs/LEADY.md](../../docs/LEADY.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: ICP przed szukaniem, tylko źródła oficjalne i publiczne, kontakt opublikowany ze źródłem, nic nie wysyła |
| `skills/lowca/` | 7: profil-klienta, sygnaly (+ tabela źródeł), kwalifikacja, kontakt-firmy, lista-leadow, monitoring-leadow, rozpoznanie-zrodla |
| skille zewnętrzne | 3: wspólny `konwersja-plikow` (plik → inny format: zdjęcia, wideo, audio, PDF, Word; plik bez metadanych, np. GPS albo autor dokumentu), wspólny `odczyt-ekranu` (tekst ze zrzutu ekranu, skanu albo PDF: Indra OCR, zapas Tesseract), wspólny `ostrozna-przegladarka` (strona firmy, która odmówiła zwykłej przeglądarce: jedna próba Camoufoxem, `ostrozna.py`) (`vendor/skills.lock.yaml`) |
| `scripts/` | `krs.py` (odpisy, biuletyn dnia, nowe firmy), `ceidg.py` (CEIDG API v3: jednoosobowe działalności po PKD i miejscu, nowe firmy, kontakt podany w rejestrze; token `CEIDG_TOKEN`, `sprawdz`), `przetargi.py` (BZP ogłoszenia i wyniki ze zwycięzcą, TED, `sprawdz` jako healthcheck), `strona.py` (kontakt, kariera, technologia, odcisk strony; także dane ukryte w HTML: JSON-LD, Next.js, Nuxt, RSC; `--z-html` dla strony z `ostrozna.py`), `leady.py` (sygnały, kontakty, ocena wg ICP, `leady.csv`, `LEADY.md`, monitoring), `zrodlo.py` + `har.cjs` (rozpoznanie nowego źródła: nagranie HAR, różnice, schemat), `lowca_lib.py` |
| `quality/rubric.md` | rubryka sędziego |

Klucz `CEIDG_TOKEN` (darmowy, dane.biznes.gov.pl): Jarvo HQ → profil jarvo-lowca → Klucze → Własne klucze; kroki w
[docs/LEADY.md](../../docs/LEADY.md#token-ceidg). Bez niego Łowca działa bez CEIDG.

# jarvo-lowca: Łowca leadów

Firmy z „dlaczego teraz” z oficjalnych, darmowych źródeł. Projekt i granice: [docs/LEADY.md](../../docs/LEADY.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: ICP przed szukaniem, tylko źródła oficjalne i publiczne, kontakt opublikowany ze źródłem, nic nie wysyła |
| `skills/lowca/` | 7: profil-klienta, sygnaly (+ tabela źródeł), kwalifikacja, kontakt-firmy, lista-leadow, monitoring-leadow, rozpoznanie-zrodla |
| skille zewnętrzne | 0 |
| `scripts/` | `krs.py` (odpisy, biuletyn dnia, nowe firmy), `przetargi.py` (BZP ogłoszenia i wyniki ze zwycięzcą, TED, `sprawdz` jako healthcheck), `strona.py` (kontakt, kariera, technologia, odcisk strony; także dane ukryte w HTML: JSON-LD, Next.js, Nuxt, RSC), `leady.py` (sygnały, kontakty, ocena wg ICP, `leady.csv`, `LEADY.md`, monitoring), `zrodlo.py` + `har.cjs` (rozpoznanie nowego źródła: nagranie HAR, różnice, schemat), `lowca_lib.py` |
| `quality/rubric.md` | rubryka sędziego |

# jarvo-ads: specjalista Ads (Meta Ads, Google Ads)

Płatne reklamy od planu po raport. Projekt i bezpieczeństwo budżetu: [docs/ADS.md](../../docs/ADS.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: cel biznesowy, pieniądze tylko przez Skarbiec, uczciwe werdykty, mapa workflowów |
| `skills/ads/` | plan-kampanii, plan-testu, start-kampanii, podlacz-konto, audyt-konta, optymalizacja, raport-reklam, wnioski-marki, sledzenie-konwersji, zgodnosc-reklam |
| skille zewnętrzne | marketingskills: `ads`, `ab-testing`, `attribution`, `analytics`, `ad-creative` (`vendor/skills.lock.yaml`) |
| `scripts/` | `ads.py` (jedyne wejście do Skarbca), `planer.py` (moc testu, prognoza), `eksperyment.py` (P(najlepszy), werdykt), `eksport.py` (CSV z Ads Managera / Google Ads → dane) |
| `quality/rubric.md` | rubryka sędziego |

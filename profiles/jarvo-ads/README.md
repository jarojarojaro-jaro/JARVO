# jarvo-ads: specjalista Ads (Meta Ads, Google Ads)

Płatne reklamy od planu po raport. Projekt i bezpieczeństwo budżetu: [docs/ADS.md](../../docs/ADS.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: cel biznesowy, pieniądze wydaje człowiek (paczka do publikacji), uczciwe werdykty, mapa workflowów |
| `skills/ads/` | 11: plan-kampanii, plan-testu, publikacja-reczna, start-kampanii, podlacz-konto, audyt-konta, optymalizacja, raport-reklam, wnioski-marki, sledzenie-konwersji, zgodnosc-reklam |
| skille zewnętrzne | 8: marketingskills: `ads`, `ab-testing`, `attribution`, `analytics`, `ad-creative`; wspólne `hooki`, `konwersja-plikow` (plik → inny format albo bez metadanych) i `odczyt-ekranu` (tekst ze zrzutu ekranu, np. panel reklamowy) (`vendor/skills.lock.yaml`) |
| `scripts/` | `ads.py` (jedyne wejście do Skarbca), `planer.py` (moc testu, prognoza), `eksperyment.py` (P(najlepszy), werdykt), `eksport.py` (CSV z Ads Managera / Google Ads → dane), `paczka.py` (kampania → paczka do ręcznej publikacji) |
| `quality/rubric.md` | rubryka sędziego |

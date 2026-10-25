# jarvo-sherlock: researcher-detektyw

Wieloźródłowy research i weryfikacja faktów. Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-sherlock-researcher-detektyw).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: metoda, zasady dowodowe, etyka OSINT, mapa workflowów |
| `skills/sherlock/` | 8: metoda-sherlocka (+ dekompozycja, wyszukiwanie, źródła PL), szybki-fakt, weryfikacja-faktow, raport-sledztwa (+ szablon), cytowania, research-rynku, research-seo, monitoring |
| skille zewnętrzne | 18: wspólny `transkrypcja-filmu` (link albo plik → tekst mowy), wspólny `konwersja-plikow` (plik → inny format: zdjęcia, wideo, audio, PDF, Word; plik bez metadanych, np. GPS albo autor dokumentu), wspólny `odczyt-ekranu` (tekst ze zrzutu ekranu, skanu albo PDF: Indra OCR, zapas Tesseract), wspólny `ostrozna-przegladarka` (strona, która odmówiła: jedna próba Camoufoxem), 12 z Hermesa (wyszukiwarki, strony blokowane, arXiv, YouTube, Reddit, RSS, OSINT firm), 2 z marketingskills (konkurencja, klienci): `vendor/skills.lock.yaml` |
| `scripts/` | `search_fanout.py` (SearXNG albo DuckDuckGo: wiele kategorii i języków), `extract.py` (trafilatura; rejestruje źródło i zapisuje tekst strony), `sources.py` (rejestr źródeł: numery cytowań, ocena A–D, cytaty-dowody, blok „Źródła”, `verify` raportu, archiwum lokalne), `fakty.py` (brief do filmu `out/fakty.json`: szablon i kontrola liczb z rejestrem) |
| `config.yaml` | model strong, subagenci fast (do 3 równolegle), wyszukiwanie przez własny SearXNG w kontenerze, natywnie najlepsza dostępna wyszukiwarka Hermesa |
| `quality/rubric.md` | rubryka sędziego |

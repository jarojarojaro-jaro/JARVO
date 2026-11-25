# jarvo-hacker: łowca hackathonów

Hackathony, bounty i konkursy do wygrania przez flotę Jarva. Spec: [docs/FLEET.md](../../docs/FLEET.md).

| Element | Zawartość |
|---|---|
| `SOUL.md`, `ZASADY.md`, `MAPA.md` | postać, procedury (regulamin najpierw, wartość oczekiwana, plan pod jury, termin w UTC, uczciwość), mapa |
| `skills/hacker/` | 7: radar-hackatonow (+ platformy, format), ocena-hackatonu (+ wartość oczekiwana), plan-zwyciestwa (+ jak wygrywać), budowa-projektu, zgloszenie, po-hackatonie, przeglad-hackatonow |
| skille zewnętrzne | wspólne `konwersja-plikow`, `odczyt-ekranu`, `graf-kodu`; z Hermesa debugowanie, wyszukiwarki, strony blokowane, RSS, Reddit: `vendor/skills.lock.yaml` |
| `scripts/hackatony.py` | baza hackathonów SQLite: dodaj (bez dubli, walidacja zasad i dat UTC), lista, terminy w godzinach, ocen, status, stare, eksport |
| `scripts/agregatory.py` | dzienne agregatory hackathonów porównane z bazą: tabela spoza bazy od progu puli, `out/ZRODLA.md` |
| `config.yaml` | model strong, subagenci fast (do 3), terminal z dłuższym limitem na budowę |
| `quality/rubric.md` | rubryka sędziego |

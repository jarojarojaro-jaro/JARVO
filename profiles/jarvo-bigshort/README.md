# jarvo-bigshort: łowca finansowania

Pieniądze dla projektów właściciela: fundusze VC i aniołowie, akceleratory, granty PL i UE, fellowshipy, kredyty
chmurowe i na modele, konkursy, ulgi, dług. Spec: [docs/FLEET.md](../../docs/FLEET.md).

| Element | Zawartość |
|---|---|
| `SOUL.md`, `ZASADY.md`, `MAPA.md` | postać, procedury (źródło pierwotne, kwalifikowalność, cena wprost, top 3), mapa |
| `skills/bigshort/` | 6: mapa-finansowania (+ kategorie, źródła PL i UE, globalne, narzędzia i bazy, metody), baza-okazji, ocena-okazji, lista-inwestorow, pakiet-aplikacji, przeglad-okazji (+ źródła obserwowane) |
| skille zewnętrzne | wspólne `konwersja-plikow`, `odczyt-ekranu`; z Hermesa wyszukiwarki, strony blokowane, RSS: `vendor/skills.lock.yaml` |
| `scripts/okazje.py` | baza okazji SQLite: dodaj (bez dubli, walidacja źródła i dat), lista, terminy, ocen, status, stare, eksport |
| `config.yaml` | model strong, subagenci fast (do 3 równolegle), wyszukiwarka i przeglądarka jak u Sherlocka |
| `quality/rubric.md` | rubryka sędziego |

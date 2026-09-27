---
name: zlozenie-pakietu
description: "Złożenie misji: zbierz wyniki kart w jeden pakiet z INDEX."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [missions, packaging, index, synthesis]
    related_skills: [dokumenty]
  tars:
    agent: tars-reka
    autonomy: A1
    reviewed: "2026-09-26"
---

# Złożenie pakietu misji

Karta „złożenie” ma rodziców: karty merytoryczne misji (już zaakceptowane przez sędziego). Twoje zadanie:
**jeden porządny pakiet**, bez przerabiania merytoryki.

## Kroki
1. `kanban_show()`: lista rodziców i ich przekazania (`metadata.artifacts`, `summary`). Katalog misji to rodzic
   Twojego workspace (`$HERMES_KANBAN_WORKSPACE/..`).
2. Automat:
   ```bash
   python3 $HERMES_HOME/scripts/pack.py "$HERMES_KANBAN_WORKSPACE/.." --out "$HERMES_KANBAN_WORKSPACE/out"
   ```
   Skrypt zbiera `*/out/` wszystkich kart, kopiuje do `out/pakiet/<rola>/`, liczy pliki i wagi, zapisuje
   `out/pakiet/MANIFEST.json` i robi `out/pakiet.zip`.
3. **INDEX.md** (`out/pakiet/INDEX.md`), pisany dla użytkownika, nie dla agentów:
   - 3–5 zdań: co powstało w tej misji i jak z tego korzystać,
   - sekcja na każdą rolę: najważniejsze pliki (z krótkim opisem), kluczowe liczby z raportów (np. Lighthouse, liczba źródeł),
   - „Do decyzji” zebrane z raportów kart (publikacja, wdrożenie, budżet),
   - rozbieżności między wynikami kart (np. inna nazwa produktu w grafikach i na stronie), jeśli są.
4. Opcjonalnie (jeśli karta prosi): `INDEX.pdf` przez `dokumenty` (pandoc + Chromium).
5. Samokontrola: każdy plik z `metadata.artifacts` rodziców jest w pakiecie, linki w INDEX.md działają (ścieżki względne).

## DoD
- [ ] `out/pakiet/` z plikami wszystkich rodziców + `MANIFEST.json`,
- [ ] `out/pakiet/INDEX.md` zrozumiały bez otwierania raportów kart,
- [ ] `out/pakiet.zip`,
- [ ] rozbieżności opisane (albo „brak”).

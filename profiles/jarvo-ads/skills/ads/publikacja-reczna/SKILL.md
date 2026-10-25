---
name: publikacja-reczna
description: "Paczka kampanii: Ty klikasz Opublikuj, agent resztę."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, meta, google, launch, handoff]
    related_skills: [plan-kampanii, plan-testu, zgodnosc-reklam, raport-reklam]
  jarvo:
    agent: jarvo-ads
    autonomy: A1
    reviewed: "2026-10-11"
---

# Publikacja ręczna (paczka kampanii)

Agent nie ma dostępu do kont reklamowych. Przygotowuje **całą kampanię** tak, żeby właściciel tylko wkleił wartości
w Menedżerze reklam (albo Google Ads) i kliknął „Opublikuj”. Pieniądze wydaje człowiek, własnym kliknięciem.

## Kiedy użyć
Zaakceptowany plan (`plan-kampanii`, `plan-testu`) i gotowe kreacje → „wypuść to”, „przygotuj do publikacji”,
„puść tę reklamę za 300 zł”. Także gdy Skarbiec jest zainstalowany, a właściciel woli kliknąć sam.

## Wejścia
Plan z budżetem i datami (`out/PLAN.md`), **zgoda właściciela na kwotę łączną** (z rozmowy albo karty; bez niej
pytasz, ile najwyżej), pliki kreacji (od Studia i Wideografa), URL strony docelowej, UTM.

## Kroki
1. **Zgodność** treści (`zgodnosc-reklam`): obietnice, kategorie specjalne, oznaczenie reklamy.
2. **`out/kampania.json`** według `references/kampania.md`: platforma, kampania (nazwa wg konwencji, cel, budżet,
   **data końca zawsze**), zestawy/grupy, reklamy z plikami i tekstami, URL z UTM.
3. **Sprawdzenie:** `@@PY@@ "$HERMES_HOME/scripts/paczka.py" out/kampania.json --sprawdz --limit <zgoda>`. Każdy błąd
   poprawiasz w pliku (krótszy tekst, data końca, mniejszy budżet); uwagi oceniasz i opisujesz właścicielowi.
   Budżet ponad zgodę = błąd: nie podnosisz `--limit` sam.
4. **Paczka:** `paczka.py out/kampania.json -o out/paczka --limit <zgoda>` → `PUBLIKACJA.md` (krok po kroku, lista
   kontrolna przed „Opublikuj”), `teksty.md` (bloki do skopiowania), `kreacje/` (pliki z nazwami reklam).
   Zdjęcia z telefonu: najpierw bez metadanych (`konwersja-plikow`, `--usun-metadane`).
5. **Oddanie:** krótko, co jest w paczce, ile kosztuje łącznie i do kiedy, link do `PUBLIKACJA.md`. Prosisz
   o „opublikowane” po kliknięciu i o eksport CSV po 2–3 dniach (dalej `raport-reklam`).

## Wyjścia
`out/kampania.json`, `out/paczka/` (`PUBLIKACJA.md`, `teksty.md`, `kreacje/`, `paczka.json`), w `out/RAPORT.md`:
budżet łączny, daty, uwagi skryptu i co zrobi właściciel.

## Definition of Done
- [ ] `paczka.py` bez błędów, budżet łączny ≤ zgoda właściciela, data końca wpisana,
- [ ] każda reklama ma pliki, teksty w limitach, CTA i URL z UTM,
- [ ] treść przeszła `zgodnosc-reklam`,
- [ ] w odpowiedzi jasne: agent niczego nie opublikował; publikuje właściciel.

## Nigdy
Prośba o hasło, token albo dostęp do konta; „opublikowałem” albo „kampania działa” bez potwierdzenia od
właściciela; kampania bez daty końca; budżet ponad zgodę.

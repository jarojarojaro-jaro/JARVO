---
name: baza-okazji
description: "Baza okazji: dopisz, status, terminy, eksport (okazje.py)."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, database, sqlite, deadlines]
    related_skills: [mapa-finansowania, ocena-okazji, przeglad-okazji]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A1
    reviewed: "2026-11-25"
---

# Baza okazji

Jedyna pamięć okazji to `baza/okazje.db` w katalogu roboczym, obsługiwana wyłącznie skryptem
`"$HERMES_HOME/scripts/okazje.py"` (`--help` pokazuje wszystko). Nie edytujesz bazy SQL-em ani ręcznie.

## Kiedy użyć
- Nowe okazje z researchu, posta od właściciela, newslettera; zmiana statusu (aplikujemy, złożone, odrzucone).
- Pytanie „co mamy”, „jakie terminy”, „pokaż bazę”, eksport dla właściciela.

## Kiedy NIE używać
- Ocena, czy okazja ma sens → `ocena-okazji` (ten skill tylko zapisuje wynik).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| okazja ze źródłem pierwotnym (strona programu) | tak | najpierw otwórz stronę programu; bez niej `notatki: "[niezweryfikowane] trop: <link>"` i status `nowa` |

## Format wpisu (`*.jsonl`, jedna okazja na linię)
```
{"nazwa": "INSEAD AI Founder Sprint 2027", "typ": "akcelerator", "kwota_min": null, "kwota_max": null,
 "waluta": "EUR", "equity": "0%", "dla_kogo": "founderzy AI, zdalnie", "region": "globalnie",
 "termin": "2026-12-01", "url": "https://venture-lab.ai", "zrodlo": "https://venture-lab.ai",
 "sprawdzone": "2026-11-25", "notatki": "27.01–2.04.2027, VC Week"}
```
- `typ`: vc, aniol, syndykat, akcelerator, fellowship, grant, kredyty, konkurs, ulga, dlug, crowdfunding, pe, bank, inne.
- `termin`: RRRR-MM-DD albo `rolling`; nieznany = pole puste i zdanie w notatkach.
- `id` opcjonalne (domyślnie slug z nazwy); ta sama okazja w nowej edycji = nowa nazwa z rokiem albo kohortą.

## Kroki
1. Zapisz wpisy do `out/nowe.jsonl`, `okazje.py dodaj out/nowe.jsonl` (wynik: nowe, zmienione, razem).
   - ✅ Punkt kontrolny: skrypt nie zgłosił błędu (brak źródła, zły typ, zła data); błąd poprawiasz, nie omijasz.
2. Dla projektu: `okazje.py ocen <id> <projekt> <0-10> "dlaczego"` (powód obowiązkowy, jedno zdanie).
3. Zmiana stanu: `okazje.py status <id> <status> "notatka"` (status zmienia tylko to polecenie, nie `dodaj`).
4. Przegląd: `okazje.py terminy --dni 30`, `okazje.py lista --projekt <p> --min-ocena 7`, `okazje.py stare --dni 60`.
5. Dla właściciela: `okazje.py eksport out/` → `out/OKAZJE.md` (terminy 45 dni, ranking projektów) i `out/okazje.csv`.

## Definition of Done
- [ ] każda nowa okazja w bazie ma `url`, `zrodlo`, `sprawdzone`, typ i termin albo zdanie o terminie,
- [ ] każda ocena ma powód,
- [ ] eksport świeży, gdy wynik idzie do właściciela.

## Typowe błędy
- Status ustawiany przez `dodaj` → nie działa celowo; użyj `status`.
- Ta sama okazja dwa razy pod różnymi nazwami → przed `dodaj` sprawdź `okazje.py lista --szukaj <fraza>`.

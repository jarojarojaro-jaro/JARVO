---
name: raport-dnia
description: "Pętla dnia Jarodev: karta dnia, limity i raport liczb."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [routine, report, pipeline, kanban]
    related_skills: [lejek, fb-grupy, mapy-firmy, szybkie-wygrane, oferta-szkic, fb-posty]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A1
    reviewed: "2026-11-14"
---

# Pętla dnia i raport

Dzień ma dwie części. **Rano** rutyna (`jarodev-dzien`, cron bez ekranu i bez człowieka) dostaje stan lejka
z `poranek.py`, zakłada kartę dnia i wysyła krótką wiadomość. **Karta dnia** (pracownik z telefonem i Komputerem)
robi pętlę w limitach i oddaje raport do oceny. Nic z tego nie publikuje ani nie wysyła bez zgody właściciela.

## Kiedy użyć
- rutyna poranna, karta „Jarodev: dzień <data>”, pytanie właściciela „co dziś / jak idzie?”.

## Kiedy NIE używać
- pojedyncza prośba („sprawdź tę stronę”) → od razu właściwy skill (`szybkie-wygrane`, `oferta-szkic`).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| wynik `poranek.py` (lejek, źródła, retencja) | rano tak | `@@PY@@ "$HERMES_HOME/scripts/poranek.py"` |
| `zrodla.yaml` (grupy, portale, Mapy, limity) | tak | puste listy = część pętli pomijasz z powodem |

## Rano (rutyna)
1. Przeczytaj wynik `poranek.py`. Puste `grupy_fb` i `mapy` → karty nie zakładasz, tylko wiadomość „czekam na listę
   grup FB i miasta do Map” (raz w tygodniu, w poniedziałek; inne dni [SILENT], jeśli nic się nie zmieniło).
2. Karta dnia dla siebie: `kanban_create(title="Jarodev: dzień <data>", assignee="jarvo-jarodev", body=…)` z DoD
   z sekcji „Karta dnia” i limitami z `zrodla.yaml`. Jedna karta dziennie: sprawdź `kanban_list`, czy już jest.
3. Wiadomość (najwyżej 6 linii): wczoraj (nowe wpisy, szkice, wysłane, odpowiedzi), szkice czekające na „tak”
   (id + jedno zdanie), czego brakuje (telefon, Komputer, źródła).

## Karta dnia (pracownik)
1. `fb-grupy` (limit `fb-grupy`) → `oferta-szkic` dla nowych wpisów.
2. `mapy-firmy` (limit `mapy`) → `szybkie-wygrane` dla firm ze stroną (limit `audyty`) → szkice ofert papierowych.
3. Raz w tygodniu `fb-posty`: szkic posta (publikacja tylko z linią `ZGODA WŁAŚCICIELA: publikacja` w karcie).
4. `lejek.py stats --json` i `out/RAPORT.md` w formacie niżej, `kanban_request_review` z `decisions_needed`
   = szkice czekające na zgodę (id, kanał, ścieżka szkicu).

## Wyjścia
- karta dnia z `out/RAPORT.md`, wiadomość poranna.

## Definition of Done
- [ ] liczby z `stats` i `licz` (nie z pamięci), każdy limit zachowany,
- [ ] każdy szkic do zgody z id, kanałem i ścieżką; zero wysyłek bez zgody,
- [ ] blokady (brak telefonu, Komputer wyłączony, ostrzeżenie Facebooka, captcha) nazwane wprost.

## Typowe błędy
- Druga karta dnia, bo rutyna ruszyła dwa razy → zawsze sprawdź `kanban_list`.
- Raport „przejrzałem grupy” bez liczb → właściciel nie wie, czy pętla działa.

## Format raportu
```
Jarodev, <data>
Grupy FB: <przejrzane>/<limit>, posty z prośbą: <n>, nowe wpisy: <n> (duplikaty: <n>)
Mapy: <miasto>/<branże>: firmy <n>, bez strony <n>, audyty <n> (wygrane: <n>)
Szkice do Twojego „tak”: <id> <kanał> <ścieżka> …
Lejek: nowy <n>, szkic <n>, zaakceptowany <n>, wysłany <n>, rozmowa <n>, klient <n>, odpada <n>
Retencja RODO: usunięte <n>. Blokady: <brak | opis>
```

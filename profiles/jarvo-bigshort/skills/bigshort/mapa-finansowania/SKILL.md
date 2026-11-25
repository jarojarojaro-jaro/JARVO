---
name: mapa-finansowania
description: "Pełna mapa pieniędzy dla projektu, baza okazji i top 3."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, vc, grants, accelerators, credits, research]
    related_skills: [baza-okazji, ocena-okazji, lista-inwestorow, pakiet-aplikacji]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A1
    reviewed: "2026-11-25"
---

# Mapa finansowania

## Kiedy użyć
- „Szukaj pieniędzy dla X”, „co jest do wzięcia”, „zbadaj, co już istnieje”, pierwsza praca dla nowego projektu.
- Raz na kwartał dla każdego projektu z bazy (świeża mapa zamiast łatania starej).

## Kiedy NIE używać
- Jedna konkretna okazja („czy CoFound Solo ma sens?”) → `ocena-okazji`.
- Same fundusze pod tezę → `lista-inwestorow`; sam przegląd terminów → `przeglad-okazji`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| projekt (np. `jarvo`, `enigma-labz`) | tak | blokada z pytaniem, dla którego projektu |
| profil `projekty/<projekt>.yaml` | tak | zbuduj z karty i skarbca (`wiedza_szukaj "<projekt>"`, `brands/`); luki jako `zalozenia` |
| zgoda na oddanie udziałów, ile pieniędzy i na co | nie | przyjmij „obie drogi” i oznacz jako założenie |

Profil projektu (`projekty/<projekt>.yaml`): `nazwa, opis_1_zdanie, etap (pomysl|prototyp|produkt|przychod), kraj,
forma_prawna, przychod_mies, zespol, solo (tak/nie), potrzeba_kwota, na_co, udzialy (tak|nie|obie), relokacja
(tak|nie), dowody (linki: repo, wyniki, strona), zalozenia (lista do potwierdzenia)`.

## Kroki
1. **Profil projektu** gotowy i przeczytany; kryteria wykluczające wypisane w `notes/kryteria.md` (kraj, spółka US,
   relokacja, solo, etap, przychód).
   - ✅ Punkt kontrolny: wiesz, czego nie możesz zaproponować, zanim zaczniesz szukać.
2. **Wiedza startowa:** przeczytaj `references/` (źródła PL i UE, globalne, narzędzia i bazy, metody) i
   `okazje.py lista` (co już mamy, żeby nie dublować).
3. **Fan-out:** do 3 subagentów naraz, każdy na jedną kategorię z `references/kategorie.md`, z profilem projektu
   i kryteriami w instrukcji; każdy oddaje JSONL w formacie `baza-okazji` ze źródłem pierwotnym i datą sprawdzenia.
   - ✅ Punkt kontrolny: każda kategoria ma albo wpisy, albo zdanie, dlaczego nic nie pasuje.
4. **Sprawdzenie źródeł:** dla każdej okazji z kwotą i terminem otwórz stronę programu; post, newsletter, lista na X
   to tylko trop. Termin minął → status `zamkniete` z datą następnej edycji, jeśli jest.
5. **Baza:** `okazje.py dodaj out/nowe.jsonl`, potem `okazje.py ocen <id> <projekt> <0-10> "dlaczego"` dla każdej
   nowej okazji (warunek wykluczający = 0–2 i to on stoi w powodzie).
6. **Top 3 na teraz:** najwyższa ocena × bliski termin × mały koszt aplikacji; dla każdej pierwszy krok (link, czas
   aplikacji, czego brakuje w profilu).
7. **Eksport i raport:** `okazje.py eksport out/`, `out/RAPORT.md` według formatu niżej, oddanie do oceny.

## Wyjścia
- `projekty/<projekt>.yaml` (nowy albo uzupełniony), `out/RAPORT.md`, `out/OKAZJE.md`, `out/okazje.csv`,
  `out/nowe.jsonl` (to, co poszło do bazy).

## Definition of Done
- [ ] ≥ 30 okazji ocenionych dla projektu w bazie, każda z linkiem do źródła pierwotnego i datą sprawdzenia,
- [ ] każda kategoria z `references/kategorie.md` sprawdzona (wpisy albo powód braku),
- [ ] top 3 z terminem, kosztem (equity, warunki) i pierwszym krokiem,
- [ ] terminy w ciągu 45 dni wypisane osobno,
- [ ] założenia profilu projektu wypisane do potwierdzenia przez właściciela.

## Typowe błędy
- Kwota i termin z posta na X albo newslettera → zawsze strona programu, inaczej `[niezweryfikowane]`.
- Program tylko dla spółek US albo wymagający relokacji oceniony wysoko bez słowa o warunku → ocena 0–2 albo warunek
  w pierwszym zdaniu powodu.
- Lista 50 funduszy bez dopasowania → ocena i powód dla każdego, raport pokazuje 3.
- „Free money”, które jest pożyczką albo wymaga wkładu własnego → cena wprost w polu `equity` i w powodzie.

## Format raportu
```
# Finansowanie: <projekt> (stan na <data>)
Odpowiedź w 2–3 zdaniach: ile realnie da się zdobyć, skąd najszybciej, jaka cena.
## Top 3 na teraz
1. <okazja>: <kwota>, <cena>, termin <data|rolling>; dlaczego pasuje; pierwszy krok.
## Terminy w ciągu 45 dni
## Mapa według typów (kapitał, bez udziałów, kredyty, konkursy, ulgi, dług): liczby i najlepsze w każdym
## Czego nie da się wziąć i dlaczego (warunki wykluczające)
## Założenia do potwierdzenia
## Źródła
```

## Wiedza
- `references/kategorie.md`: kategorie fan-outu i pytania kwalifikujące.
- `references/zrodla-pl-ue.md`: programy i fundusze w Polsce i UE (z datami sprawdzenia).
- `references/zrodla-global.md`: akceleratory, granty, fellowshipy, kredyty na świecie.
- `references/narzedzia-i-bazy.md`: bazy inwestorów, API, narzędzia AI do fundraisingu, ograniczenia regulaminów.
- `references/metody.md`: zasady wyboru i aplikowania (top 3, dopasowanie tezy, granty zamiast rundy).

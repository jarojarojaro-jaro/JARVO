---
name: pakiet-aplikacji
description: "Szkic aplikacji: odpowiedzi do formularza, opis, braki."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, application, pitch, writing]
    related_skills: [ocena-okazji, baza-okazji]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A2            # wysłanie tylko po zgodzie właściciela; szkic w workspace to A1
    reviewed: "2026-11-25"
---

# Pakiet aplikacji

## Kiedy użyć
- Właściciel albo Jarvo wybrał okazję (status `kandydat` albo `aplikujemy`) i trzeba przygotować aplikację.

## Kiedy NIE używać
- Okazja nieoceniona → najpierw `ocena-okazji`. Deck graficzny → Studio przez Jarva; film pitchowy → Wideograf.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| okazja z bazy (`id`) | tak | blokada z pytaniem |
| pytania formularza | tak | spisz ze strony programu; formularz za logowaniem → lista pytań z FAQ, a resztę jako lukę |
| profil projektu i dowody (repo, wyniki, strona, liczby) | tak | brakujące liczby jako pytania do właściciela, nigdy wymyślone |

## Kroki
1. **Pytania** formularza 1:1 w `out/aplikacje/<id>/PYTANIA.md` z limitami znaków i wymaganymi załącznikami.
2. **Odpowiedzi** w `ODPOWIEDZI.md`: konkret, liczby z dowodem (link), język programu; każda w limicie znaków.
   - ✅ Punkt kontrolny: żadnej liczby ani faktu bez źródła w profilu projektu albo skarbcu; brak = `[DO UZUPEŁNIENIA: …]`.
3. **Opis jednostronicowy** (`ONE-PAGER.md`): problem, rozwiązanie, dowód (benchmark, użytkownicy, przychód), rynek,
   zespół, ile i na co, dlaczego teraz.
4. **Lista braków** dla właściciela (dokumenty, liczby, decyzje: ile udziałów, czy relokacja) i czas potrzebny na
   złożenie.
5. **Status** `aplikujemy` w bazie, oddanie do oceny. Wysłanie formularza robi właściciel albo agent dopiero po jego
   wyraźnej zgodzie (A2), po potwierdzeniu finalnej treści.

## Wyjścia
- `out/aplikacje/<id>/PYTANIA.md`, `ODPOWIEDZI.md`, `ONE-PAGER.md`, `BRAKI.md`.

## Definition of Done
- [ ] każde pytanie formularza ma odpowiedź albo jawny brak,
- [ ] limity znaków dotrzymane (policzone),
- [ ] zero nieprawdy i zero niepotwierdzonych liczb,
- [ ] nic nie wysłane bez zgody.

## Typowe błędy
- Ogólniki („rewolucyjne AI”) → liczba, benchmark, link do dowodu.
- Ta sama odpowiedź do każdego programu → teza i język programu (np. impact dla grantów UE, rynek dla VC).

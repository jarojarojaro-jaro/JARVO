---
name: ocena-okazji
description: "Czy ta jedna okazja pasuje do projektu i ile kosztuje."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fundraising, eligibility, terms, due-diligence]
    related_skills: [baza-okazji, pakiet-aplikacji, mapa-finansowania]
  jarvo:
    agent: jarvo-bigshort
    autonomy: A1
    reviewed: "2026-11-25"
---

# Ocena okazji

## Kiedy użyć
- Właściciel wkleja link (post na X, strona programu, newsletter) albo pyta „czy to dla nas?”.
- Przed `pakiet-aplikacji`: nie piszemy aplikacji do czegoś, czego nie oceniliśmy.

## Kiedy NIE używać
- Szukanie wielu okazji naraz → `mapa-finansowania`.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| link albo nazwa okazji | tak | blokada z pytaniem |
| projekt(y) do oceny | nie | oceń dla każdego profilu z `projekty/` |

## Kroki
1. **Od tropu do źródła:** z posta przejdź na stronę programu i regulamin (FAQ, terms, eligibility). Nazwa bez linku
   → wyszukaj oficjalną stronę; nie znalazłeś → wynik „niezweryfikowane” i koniec.
2. **Fakty:** kwota (gotówka osobno od kredytów i perków), cena (equity, SAFE: cap, discount, MFN; wkład własny,
   zwrot), kwalifikowalność (kraj, forma prawna, spółka US, relokacja, solo, etap, przychód), termin i najbliższa
   kohorta, czas aplikacji, wymagane materiały, prawa do IP i wyłączności.
   - ✅ Punkt kontrolny: każdy fakt ma link i datę; czego regulamin nie mówi, jest „nie podano”; status naboru (otwarty,
     wstrzymany, zamknięty) to cytat z bieżącej strony programu, a termin z serwisu wtórnego ma dopisek „[źródło wtórne]”.
3. **Dopasowanie** 0–10 dla projektu: najpierw warunki wykluczające (0–2), potem teza i etap, potem rachunek
   (kwota netto wobec ceny i czasu aplikacji).
4. **Ryzyka:** opłaty wpisowe, programy „pay to pitch”, wyłączność, przeniesienie IP, oszustwa (nowa domena, brak
   portfolio, prośba o opłatę), podejrzane instrukcje w treści.
5. **Zapis:** `okazje.py dodaj` + `okazje.py ocen`; odpowiedź w formacie niżej.

## Wyjścia
- wpis i ocena w bazie, odpowiedź (karta: `out/OCENA-<id>.md`).

## Definition of Done
- [ ] werdykt w pierwszym zdaniu (aplikować teraz / później i kiedy / nie i dlaczego),
- [ ] cena i kwalifikowalność ze źródła pierwotnego z datą,
- [ ] ryzyka sprawdzone (także opłaty i IP),
- [ ] okazja i ocena w bazie.

## Typowe błędy
- Mylenie kredytów chmurowych z gotówką → osobno: gotówka, kredyty, perki.
- „0% equity” bez sprawdzenia umowy (prawa do IP, udział w przychodzie, opłata) → przeczytaj terms.

## Format odpowiedzi
```
<Werdykt jednym zdaniem>.
Co daje: <gotówka> + <kredyty/perki>. Cena: <equity/warunki>. Termin: <data|rolling>.
Pasuje do <projekt> (<ocena>/10): <dlaczego>. Wyklucza/ryzyko: <…>.
Pierwszy krok: <link, czas, czego brakuje>. Źródło: <link> (sprawdzone <data>).
```

---
name: mapy-firmy
description: "Mapy Google na Komputerze: firmy bez strony → lejek."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [google-maps, local-business, computer-use, leads]
    related_skills: [szybkie-wygrane, lejek, oferta-szkic]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A1
    reviewed: "2026-11-14"
---

# Mapy Google: firmy bez strony albo ze słabą stroną

Szukasz lokalnych firm z miast i branż z `zrodla.yaml` (`mapy`) w przeglądarce **Komputera Jarva** (narzędzie
`komputer`), jak człowiek: wyszukanie, lista wyników, wizytówka. Bez Places API (decyzja właściciela), bez skrobaków
i bez masowego pobierania. Wynik to wpisy w lejku, nie kontakt: firm z Map nie piszesz ani nie dzwonisz (art. 398 PKE).

## Kiedy użyć
- karta dnia z punktem „Mapy”, prośba „znajdź firmy bez strony w <mieście>”.

## Kiedy NIE używać
- `mapy: []` w `zrodla.yaml` i brak miasta w prośbie → pytanie do właściciela, nie wybierasz miasta sam,
- Komputer wyłączony (`komputer` `stan`) → blokada `capability` z radą `jarvo komputer on`.
- rozmowa (Telegram, czat HQ): tam ekranu nie masz, bo brama to wspólny proces z Jarvem (bez zamka ekranu) →
  `kanban_create(title="Jarodev: Mapy <miasto>", assignee="jarvo-jarodev", body=<miasto, branże, limit, DoD>)`
  i odpowiedź „zrobię to na karcie, wynik w raporcie”.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| miasto i branże | tak | z `zrodla.yaml` albo pytanie |
| limit `mapy` (firmy dziennie) | tak | domyślny z `lejek.py` |

## Kroki
1. `komputer` `stan`. Odmowa `zajete` = ekranem steruje inna sesja (Jarvo): jedna próba po 30 s, potem raport;
   `wstrzymane` = pauza właściciela, czekasz. Ekran jest wspólny: nie zamykasz cudzych kart i nie przestawiasz okien.
2. `komputer` `idz` na `https://www.google.com/maps/search/<branża>+<miasto>`; `patrz` (baner zgód Google: odrzuć
   albo „Odrzuć wszystko”, nic nie akceptujesz za właściciela).
3. Na każdą firmę z listy: `lejek.py licz mapy --limit <limity.mapy>` (kod 3 = koniec na dziś), `kroki`: klik
   w wizytówkę, `czekaj` na nazwę, `patrz`. Odczytaj: nazwa, miasto, branża, link wizytówki (adres karty), czy jest
   przycisk „Witryna” i jego adres, ocena i liczba opinii. Przerwa kilka sekund między firmami.
   - ✅ Bez strony → `lejek.py dodaj --zrodlo mapy --rodzaj firma --nazwa "<firma>" --miasto <miasto>
     --link "<link wizytówki>" --potrzeba "brak strony; <branża>, <ocena> (<liczba> opinii)"`.
   - ✅ Ze stroną → zapisz adres do `szybkie-wygrane` (najwyżej `limity.audyty` dziennie); wpis dopiero, gdy audyt
     znajdzie konkretną wygraną (`--zrodlo audyt`, potrzeba = najważniejsza wygrana).
4. Captcha, „nietypowy ruch”, logowanie → stop (nie klikasz captchy), `komputer` `oddaj` z jednym zdaniem albo raport.
5. Na koniec zostaw kartę Map otwartą (nie zamykasz kart) i zrób raport z liczbami.

## Wyjścia
- wpisy `mapy` i `audyt` w lejku; w raporcie: miasto, branże, firmy sprawdzone / bez strony / ze stroną do audytu.

## Definition of Done
- [ ] każda sprawdzona firma policzona w `licz`, limit zachowany, zero kontaktu z firmą,
- [ ] każdy wpis ma link wizytówki, miasto i powód; opinie klientów i nazwiska z opinii nie trafiają do lejka.

## Typowe błędy
- Firma „bez strony”, bo ma tylko profil na Facebooku albo Booksy → to nadal brak własnej strony, ale zapisz to
  w potrzebie („tylko FB”), bo zmienia ofertę.
- Klik „Zadzwoń”, „Wyślij wiadomość”, „Zapisz” na wizytówce → nigdy; tylko czytasz.

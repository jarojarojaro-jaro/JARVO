---
name: fb-posty
description: "Własny post jarodev na FB: szkic → „tak” → publikacja."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [facebook, social, copy, consent]
    related_skills: [oferta-szkic, lejek, raport-dnia]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A2
    reviewed: "2026-11-14"
---

# Własne posty jarodev na Facebooku

Post pokazuje, co jarodev robi (strony, sklepy, automatyzacje, „wszystko, co da się zakodować”), na przykładzie
z pracy, a nie sloganem. Publikacja to A2: tylko za „tak” właściciela dla **tej** treści i tego miejsca.

## Kiedy użyć
- karta dnia z punktem „post” (najwyżej `limity.fb-posty` dziennie), prośba właściciela o post.

## Kiedy NIE używać
- grafika albo film do posta → zamówienie u `jarvo-studio` / `jarvo-wideo` przez Jarva (w raporcie, nie sam),
- post w grupie, której regulamin zakazuje reklam → nie publikujesz tam wcale (zasady grupy czytasz przed szkicem).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| temat (realizacja, porada, wynik audytu bez nazwy firmy) | tak | zaproponuj 2 tematy w raporcie |
| miejsce (profil, strona jarodev, grupa z `zrodla.yaml`) | tak | pytanie do właściciela |
| oferta i ton marki (plik oferty skilla `oferta-szkic`, `brands/jarodev/`) | tak | wiedza_szukaj w skarbcu marki |

## Kroki
1. Szkic w `out/posty/<data>-<temat>.md`: 3–6 zdań, konkret (liczba, wynik, przed/po), jedno wezwanie („napisz,
   jeśli…”), bez obietnic pozycji w Google i bez cen, których właściciel nie podał. Bez danych klientów bez ich zgody.
2. Prośba o zgodę: w rozmowie pełna treść + miejsce + godzina i pytanie „publikuję?”. Na karcie bez zgody:
   `kanban_block(kind="needs_input")` z treścią i miejscem albo wynik z `decisions_needed`.
   - ✅ Publikujesz tylko, gdy masz „tak” właściciela w tej rozmowie albo linię `ZGODA WŁAŚCICIELA: publikacja` w karcie
     z tą treścią (cytat) i datą. Inna treść niż zaakceptowana = nowa zgoda.
3. `lejek.py licz fb-posty --limit <limity.fb-posty>` (kod 3 = nie dziś).
4. Telefon: `ping` → `screen` → `act` (otwórz miejsce, „Napisz coś…”, `type` z treścią **bez** `enter`) → `screen`
   (sprawdź, że treść jest dokładnie ta) → `act` `tap` „Opublikuj”. Bramka telefonu odpowie `needs_confirm`:
   powtarzasz z `confirm=true` tylko z tą zgodą (wtyczka zgód zapyta właściciela albo przepuści linię z karty).
5. Po publikacji: `screen` jako dowód (post widoczny), link do posta w raporcie, jeśli da się go odczytać.

## Wyjścia
- `out/posty/<data>-<temat>.md` (szkic i wersja opublikowana), w raporcie: zgoda (kto, kiedy), dowód publikacji.

## Definition of Done
- [ ] treść opublikowana = treść zaakceptowana (słowo w słowo), zgoda zapisana w raporcie,
- [ ] limit dnia zachowany, dowód z ekranu po publikacji,
- [ ] bez zgody: szkic czeka, nic nie wyszło.

## Typowe błędy
- `type` z `enter: true` w polu posta → może opublikować od razu; zawsze bez `enter`, publikacja osobnym tapnięciem.
- Zgoda na „jakiś post” traktowana jak zgoda na tę treść → zgoda dotyczy konkretnego tekstu i miejsca.

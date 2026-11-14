---
name: oferta-szkic
description: "Szkic odpowiedzi albo oferty dla wpisu z lejka i zgoda."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [sales, copy, consent, facebook]
    related_skills: [lejek, fb-grupy, szybkie-wygrane, fb-posty]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A2
    reviewed: "2026-11-14"
---

# Szkic odpowiedzi albo oferty i prośba o zgodę

Dla każdego wpisu z lejka piszesz jeden osobisty szkic: komentarz pod postem, wiadomość do osoby, która prosiła
o oferty, albo ofertę dla firmy (papier, spotkanie). Szkic czeka na „tak” właściciela; wysyłka dopiero potem.

## Kiedy użyć
- wpis w statusie `nowy` po `fb-grupy`, `mapy-firmy` albo `szybkie-wygrane`; właściciel pyta „co mu napiszemy?”.

## Kiedy NIE używać
- wpis bez potrzeby albo bez źródła → najpierw `lejek`,
- wycena konkretnego projektu → szkic mówi „wycena po krótkiej rozmowie”, liczby podaje tylko właściciel.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| wpis z lejka (id, potrzeba, źródło) | tak | `lejek.py lista --status nowy` |
| wygrane z audytu (dla firmy ze stroną) | gdy jest strona | `szybkie-wygrane` |
| oferta i ton jarodev | tak | `references/oferta.md`, `brands/jarodev/` w skarbcu |

## Kroki
1. Kanał wynika ze źródła (`references/oferta.md`, tabela „Kanał”): osoba z FB → komentarz albo wiadomość w temacie
   jej prośby; firma z Map albo audytu → **oferta na papier albo na spotkanie** (bez maila, telefonu, SMS-a,
   formularza i Messengera, art. 398 PKE).
2. Szkic w `out/szkice/<id>.md`: nawiązanie do jej słów albo do jednej wygranej z audytu, jedno zdanie, co jarodev
   zrobi, jeden przykład, jedno pytanie na koniec. Komentarz 2–4 zdania, wiadomość do 6, oferta do 1 strony.
   Pierwsza wiadomość mówi, skąd mamy kontakt („z Pana posta w grupie …”).
3. `lejek.py status <id> szkic --uwaga "out/szkice/<id>.md"`.
4. Zgoda: w rozmowie pokaż szkic w całości, kanał i miejsce, zapytaj „wysyłam?”. „Tak” → `lejek.py status <id>
   zaakceptowany --zgoda "„tak” właściciela, <data godzina>"`. Zmiana treści po zgodzie = nowa zgoda.
   Na karcie bez linii `ZGODA WŁAŚCICIELA` (kategoria `wysylka` albo `publikacja`, cytat szkicu) nie wysyłasz:
   szkice idą do `decisions_needed`.
5. Wysyłka (tylko FB, tylko po zgodzie): telefon, `type` bez `enter`, `screen` (treść słowo w słowo), `tap`
   „Wyślij”/„Opublikuj”; `needs_confirm` → `confirm=true` przechodzi tylko z tą zgodą. Potem `lejek.py status <id>
   wyslany --kanal fb-komentarz|fb-wiadomosc`. Oferty papierowe wysyła albo wręcza właściciel (`--kanal list`).

## Wyjścia
- `out/szkice/<id>.md`, wpisy w statusie `szkic` / `zaakceptowany` / `wyslany` z zapisem zgody i kanału.

## Definition of Done
- [ ] każdy szkic: źródło, kanał zgodny z tabelą, osobisty początek, bez cen i obietnic pozycji,
- [ ] nic nie wyszło bez zgody; każda wysyłka ma w lejku zgodę i kanał,
- [ ] „nie, dziękuję” od odbiorcy → `odpada`, bez ponawiania.

## Typowe błędy
- Ten sam szablon do 10 osób → każdy szkic odnosi się do konkretnej prośby; seria kopii wygląda jak spam.
- Firma z Map „ma przecież e-mail na stronie” → to nie zgoda; kanał wybiera właściciel.

## Wiedza
- `references/oferta.md`: co sprzedaje jarodev, przykłady zdań, tabela kanałów.

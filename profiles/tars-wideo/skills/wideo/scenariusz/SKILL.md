---
name: scenariusz
description: "Scenariusz krótkiego wideo: hook, rytm, tekst lektora."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, script, hook, storytelling, retention]
    related_skills: [krotki-film, warianty-ab, video, formaty-wideo, sw-premise-theme, sw-scene-craft, sw-dialogue, sw-character-conflict]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Scenariusz krótkiego wideo

Film krótki wygrywa w pierwszych 2 sekundach i przegrywa na każdej zbędnej. Wzorce hooków i struktur:
`references/hooki.md`.

## Kiedy użyć
- Przed każdym filmem z lektorem albo tekstem na ekranie (`krotki-film`, `film-z-kodu`, `warianty-ab`).
- Gdy karta daje temat, a nie gotowy tekst.

## Kiedy NIE używać
- Użytkownik dał gotowy tekst: tylko przycięcie do limitu słów i podział na sceny.
- Fakty, liczby, porównania bez źródła: najpierw dane od `tars-sherlock` (przez Jarva) albo z karty.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| temat i jedno przesłanie | tak | z karty; kilka przesłań = kilka filmów |
| odbiorca i platforma | tak | 9:16, odbiorca z brand kitu |
| długość | nie | 20–40 s |
| CTA | nie | „zapisz/obserwuj” albo cel z karty |

## Warsztat (gdy film ma fabułę, postać albo dialog)
Wiedza z `screenwriting/` (McKee, Egri): premisa i jedno przesłanie → `sw-premise-theme`; scena jako zwrot wartości
→ `sw-scene-craft`; dialog, podtekst → `sw-dialogue`; bohater i przeciwnik → `sw-character-conflict`. W krótkiej
formie bierz tylko zasady (hak = zwrot wartości, jedna scena = jedna zmiana), nie pełny proces pisania serialu.

## Kroki
1. **Jedno zdanie przesłania** („Widz ma wyjść z przekonaniem, że…”). Nie da się → temat za szeroki, zawęź.
2. **Budżet słów:** długość × 2,5 słowa/s (lektor Edge +0%); 30 s ≈ 70 słów. Hook ≤ 12 słów, scena ≤ 22.
3. **Hook (0–2 s):** wzorzec z `references/hooki.md`; konkret, liczba, konflikt albo obietnica; bez „Cześć, dziś…”.
   Tekst ekranowy hooka ≤ 5 słów, zrozumiały bez dźwięku.
4. **Struktura** dobrana do celu (lista, mit→fakt, problem→rozwiązanie, przed→po, historia); 4–8 scen, jedna myśl na scenę,
   każda scena kończy się powodem, żeby oglądać dalej.
5. **Obraz do każdej sceny:** co widać (konkretny obiekt i kadr, nie „coś o kawie”), zapytanie stock po angielsku.
6. **CTA** jedno, na końcu (i opcjonalnie wpleciony w połowie przy > 40 s).
7. **Czytanie na głos:** zdania krótkie, bez nawiasów, skrótów i cyfr rzymskich; liczby tak, jak mają być czytane
   („dwa razy”, „30 procent”). Test: `film.py lektor "<hook>" -o /tmp/hook.mp3` → czas hooka ≤ 2,5 s.

## Wyjścia
- `out/wideo/SCENARIUSZ.md`: przesłanie, odbiorca, długość, tabela scen (nr, tekst lektora, tekst ekranowy, obraz,
  zapytanie stock, czas szacowany), CTA, źródła faktów.

## Definition of Done
- [ ] jedno przesłanie; hook ≤ 12 słów i ≤ 2,5 s czytania,
- [ ] suma słów w budżecie długości; żadna scena > 22 słów,
- [ ] każda scena ma konkretny obraz; liczby i fakty mają źródło,
- [ ] tekst naturalny po polsku (bez kalk i „AI-izmów”), CTA na końcu.

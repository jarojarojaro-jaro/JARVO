---
name: research-seo
description: "SEO research: frazy PL, intencje, SERP, strony konkurencji."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [research, seo, keywords, serp]
    related_skills: [metoda-sherlocka, research-rynku]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-09-26"
---

# Research SEO (bez płatnych narzędzi)

Dla kart typu „słowa kluczowe pod landing / artykuł”. Wynik zasila `jarvo-web` i `jarvo-studio`.

## Kroki
1. **Ziarno:** 3–5 fraz z briefu (produkt, problem klienta, kategoria), PL + EN, jeśli rynek jest szerszy.
2. **Rozszerzenie:** podpowiedzi wyszukiwarek (SearXNG z różnymi silnikami), sekcje „podobne wyszukiwania”
   i „ludzie pytają też” (przeglądarka), nagłówki H2/H3 stron z TOP 10, fora i pytania klientów.
3. **Intencja** każdej frazy: informacyjna / komercyjna / transakcyjna / nawigacyjna, według tego, co jest w TOP 10.
4. **SERP TOP 10** dla 3–5 fraz głównych: typy stron (landing, artykuł, porównanie, sklep), długość treści,
   powtarzające się tematy, schema (FAQ, Product), luki (czego nikt dobrze nie odpowiada).
5. **Klastry:** grupuj frazy tej samej intencji; 1 klaster = 1 strona.

## Wynik
- `out/slowa-kluczowe.csv`: fraza, język, intencja, klaster, szacunek trudności (niska/średnia/wysoka z uzasadnieniem SERP), priorytet,
- `out/RAPORT.md`: rekomendowana fraza główna + 5–10 pobocznych dla strony, struktura H1/H2 wynikająca z SERP, pytania do FAQ, luki.

## Uczciwość
Bez płatnych API nie znamy dokładnych wolumenów. Nie wymyślaj liczb; szacuj względnie i opisz metodę.

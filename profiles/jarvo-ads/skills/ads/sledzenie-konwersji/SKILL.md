---
name: sledzenie-konwersji
description: "Piksel, Conversions API, tag Google, UTM: lista kontrolna."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, tracking, pixel, utm]
    related_skills: [analytics, attribution, plan-kampanii]
  jarvo:
    agent: jarvo-ads
    autonomy: A0
    reviewed: "2026-09-29"
---

# Śledzenie konwersji

Bez wiarygodnych konwersji kampanie optymalizują się na ślepo. Sprawdzasz i zlecasz; wdrożenie na stronie robi `jarvo-web`.

## Lista kontrolna
1. **Meta:** piksel na każdej stronie docelowej, zdarzenia standardowe (PageView, ViewContent, Lead / CompleteRegistration,
   AddToCart, Purchase z `value` i `currency`), **Conversions API** (serwer) z deduplikacją `event_id`, dopasowanie
   zdarzeń (EMQ) ≥ 6. Sprawdzenie: Menedżer zdarzeń → Testuj zdarzenia.
2. **Google:** tag Google / GA4 z importem konwersji albo akcje konwersji Google Ads; konwersje rozszerzone przy formularzach.
3. **Zgody (RODO):** baner zgód przed pikselem/tagiem; Google Consent Mode v2 (EOG). Bez zgody tagi nie strzelają.
4. **UTM:** `utm_source=meta|google&utm_medium=paid&utm_campaign={{campaign.name}}&utm_content={{ad.name}}`
   (Meta: parametry URL reklamy; Google: szablon śledzenia `{lpurl}?utm_…` / auto-tagowanie gclid).
5. **Test końcowy:** jedna prawdziwa konwersja testowa widoczna w Menedżerze zdarzeń / Google Ads i w analityce strony.

## Wyjścia
`out/SLEDZENIE.md`: stan (✓/✗ na punkt), co zlecić `jarvo-web` (gotowy tekst karty: zdarzenia, miejsca, zgody), co zrobi użytkownik.

## Definition of Done
- [ ] każdy punkt listy z dowodem (zrzut / widok zdarzeń / wynik testu),
- [ ] kampania konwersyjna startuje dopiero, gdy konwersja testowa jest widoczna.

---
name: audyt-konta
description: "Audyt konta: marnotrawstwo, śledzenie, szybkie wygrane."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, audit]
    related_skills: [ads, hooki, optymalizacja, sledzenie-konwersji]
  jarvo:
    agent: jarvo-ads
    autonomy: A0
    reviewed: "2026-09-30"
---

# Audyt konta

Odpowiedź na „zobacz, co się dzieje na moim koncie” albo pierwszy krok po podłączeniu.

## Wejścia
`ads.py statystyki` (ostatnie 30 i 90 dni) albo eksport CSV (`eksport.py`), cel biznesowy, docelowe CPA/ROAS jeśli znane.

## Kroki (lista kontrolna)
1. **Śledzenie:** czy są konwersje, czy liczą się sensownie (skoki, zera, podwójne zliczanie), piksel + CAPI / tag Google.
2. **Struktura:** liczba aktywnych kampanii i zestawów vs budżet (rozdrobnienie), zestawy w fazie uczenia „ograniczone”.
3. **Marnotrawstwo:** reklamy z wydatkiem ≥ 2× cel CPA bez wyniku, Google: wyszukiwane hasła bez związku, miejsca
   emisji/aplikacje z samymi kliknięciami, nakładające się grupy odbiorców.
4. **Kreacje:** częstotliwość, spadek CTR w czasie (zmęczenie), liczba aktywnych kreacji na zestaw, formaty (brak 9:16?).
   Słaba reklama → lejek diagnozy ze skilla `hooki` (hook rate → hold rate → CTR → CVR), naprawiasz pierwszy zepsuty etap.
5. **Budżet i tempo:** wydatek vs plan, ograniczenia budżetem przy dobrym CPA (szansa na skalowanie).
6. **Zgodność:** odrzucone reklamy, ostrzeżenia konta, kategorie specjalne.
Każdy punkt: **stan → dowód (liczba, okres) → wpływ w zł → rekomendacja**. Szacunki nazywaj szacunkami.

## Wyjścia
`out/AUDYT.md`: wynik w 5 zdaniach, tabela ustaleń (priorytet, dowód, wpływ, co zrobić, kto: Ads / Studio / Web / użytkownik),
3 szybkie wygrane, plan na 2 tygodnie.

## Definition of Done
- [ ] każde ustalenie ma liczbę i okres, źródło danych podane,
- [ ] priorytety wg wpływu w zł, nie wg liczby uwag,
- [ ] żadnych zmian na koncie w ramach audytu (A0).

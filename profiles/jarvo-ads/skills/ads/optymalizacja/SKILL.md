---
name: optymalizacja
description: "Codzienna kontrola konta i optymalizacja w kopercie."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, optimization, monitoring]
    related_skills: [raport-reklam, plan-testu, start-kampanii]
  jarvo:
    agent: jarvo-ads
    autonomy: A2
    reviewed: "2026-09-29"
---

# Optymalizacja

Codzienny przegląd aktywnych kampanii. Działasz **tylko w zatwierdzonej kopercie**: pauza i przesunięcia budżetu
w jej obrębie. Wszystko, co zwiększa wydatek, to nowa koperta (`start-kampanii`).

## Kroki
1. `ads.py koperta stan` → aktywne koperty, wydane / zatwierdzone, dni do końca.
2. `ads.py statystyki --konto … --od <start koperty> --json > dane.json`.
3. **Higiena (każdego dnia):**
   - tempo: wydatek dzisiaj vs plan (> 130% albo < 50% → sprawdź dlaczego),
   - odrzucone reklamy, problemy z dostarczaniem, faza uczenia,
   - częstotliwość > 3–4, CTR spada > 30% vs pierwsze 3 dni → zamów następcę kreacji (brief przez Jarva),
   - Google: wyszukiwane hasła z wydatkiem bez konwersji → lista wykluczeń do dodania (`ads.py` / propozycja).
4. **Testy:** `eksperyment.py dane.json --metryka … --json`. `do_wylaczenia` → `ads.py pauza <reklama>`;
   budżet wyłączonego wariantu → `ads.py budzet` na pozostałe (suma koperty bez zmian). `zwyciezca` → raport
   i propozycja następnego kroku. `remis` → czekaj do końca koperty albo zaproponuj dołożenie budżetu (nowa zgoda).
5. **Pierwszy dzień po starcie:** czy reklamy się emitują (wyświetlenia > 0 po 2–4 h), czy link i UTM działają,
   czy konwersje się liczą. Problem = pauza i raport, nie czekanie.
6. **Nie przekręcaj:** zmiany budżetu ≤ 20% na raz i nie częściej niż co 48 h na zestaw (restart uczenia).
   Wyjątek: pauza przegranego wariantu i STOP.
7. Dziennik decyzji: `out/optymalizacja.md`, jedna linia na decyzję: data, co, dlaczego (liczba), wynik akcji.

## Kiedy pisać do użytkownika
Tylko gdy: zwycięzca testu, koperta kończy się za ≤ 1 dzień, STOP strażnika, odrzucone reklamy, CPA > 2× cel,
decyzja wymaga zgody. Rutynowy dzień = cisza (`[SILENT]` w rutynie).

## Definition of Done (dzienny przegląd)
- [ ] higiena sprawdzona na danych z dziś, nie z pamięci,
- [ ] każda zmiana na koncie w kopercie i zapisana w dzienniku z powodem,
- [ ] werdykty testów wyłącznie z `eksperyment.py`.

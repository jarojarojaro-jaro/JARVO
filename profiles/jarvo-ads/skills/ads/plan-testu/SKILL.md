---
name: plan-testu
description: "Test reklam A/B/C…: warianty, metryka, moc, reguły stopu."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, testing, experiment]
    related_skills: [ab-testing, plan-kampanii, optymalizacja]
  jarvo:
    agent: jarvo-ads
    autonomy: A1
    reviewed: "2026-09-29"
---

# Plan testu

Test to sposób, żeby budżet uczył nas czegoś. Warianty mogą różnić się jedną rzeczą (wtedy wiemy DLACZEGO wygrał)
albo wszystkim (wtedy wiemy tylko, KTÓRY pakiet wygrał). Oba są w porządku, byle raport mówił uczciwie, który to przypadek.

## Wejścia
- cel kampanii i miara sukcesu (z `plan-kampanii`), budżet dzienny i czas,
- warianty (2–5): pliki od Studia/Wideografa albo brief do zamówienia,
- dane bazowe z konta (`ads.py statystyki`: CPM, CTR, hook rate, CPA) albo jawne założenia.

## Kroki
1. **Pytanie testu** jednym zdaniem: „Który z 5 filmów launchowych zatrzymuje najwięcej osób?”.
   Zaznacz: jedna zmienna czy wiele (`wiele_zmiennych: true` w danych dla `eksperyment.py`).
2. **Metryka z drabiny** (od najtańszej): hook rate (wideo, 3 s / wyświetlenia) → CTR → CVR → CPA.
   Wybierz najdroższą metrykę, którą budżet rozstrzygnie.
3. **Moc:** `$HERMES_HOME/scripts/planer.py test --metryka … --warianty … --budzet-dzienny … --dni … (--bazowa | --cpa)`.
   Kod 1 = niewykonalny: zastosuj rekomendację (mniej wariantów, tańsza metryka, dłużej) i przelicz. Nie planuj testu,
   który z góry nic nie rozstrzygnie.
4. **Tryb na platformie:**
   - Meta równe budżety (ABO): osobny zestaw na wariant, ten sam budżet: domyślny przy małych budżetach,
   - Meta split test (`ad_studies`, losowe rozłączne grupy): gdy testujemy odbiorców/strategie albo budżet jest duży,
   - wolumen (wiele reklam w jednym zestawie, Meta dzieli budżet): to **sygnał**, nie test; tak piszemy w raporcie,
   - Google: eksperymenty kampanii (wersja robocza, podział 50/50) albo warianty RSA/zasobów.
5. **Reguły stopu** (domyślne): min. 4 dni (lepiej 7) i wolumen z planera; zwycięzca P ≥ 95% i strata < 2%;
   wyłączenie przy P < 5% po minimum albo 2× cel CPA bez wyniku; koniec czasu bez rozstrzygnięcia = remis.
6. **Brief kreacji**, jeśli wariantów brak: dla każdego wariantu co ma się różnić, format, długość, hook, CTA
   (karta do Studia/Wideografa przez Jarva). Nazwy plików wg konwencji z `plan-kampanii`.

## Wyjścia
Sekcja „Test” w `out/PLAN.md`: pytanie, warianty (tabela), jedna/wiele zmiennych, metryka i dlaczego, wynik planera
(liczby), tryb na platformie, reguły stopu, koszt rozstrzygnięcia; `out/brief-kreacji.md` jeśli potrzeba.

## Definition of Done
- [ ] pytanie testu i rodzaj (jedna/wiele zmiennych) zapisane,
- [ ] planer uruchomiony, wynik w planie; test wykonalny albo świadoma decyzja użytkownika,
- [ ] tryb na platformie nazwany (test vs sygnał),
- [ ] reguły stopu zapisane przed startem (nie po fakcie).

---
name: research-rynku
description: "Rynek: gracze, oferty, ceny, komunikacja, opinie klientów."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [research, market, competitors, pricing, customers]
    related_skills: [metoda-sherlocka, competitor-profiling, customer-research, competitor-news-monitor]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-09-26"
---

# Research rynku i konkurencji

Warstwa nad `metoda-sherlocka` dla pytań biznesowych. Korzysta ze skilli `competitor-profiling`
i `customer-research` (marketingskills, MIT), ale wynik zawsze przechodzi przez weryfikację.

## Wątki standardowe
1. **Gracze:** kto sprzedaje/oferuje to samo lub substytut (PL, potem UE/świat, jeśli trzeba). 5–10 pozycji.
2. **Oferta i ceny:** co dokładnie oferują, ceny (brutto, waluta, data sprawdzenia), modele (abonament, jednorazowo).
3. **Komunikacja:** obietnica główna, wyróżniki, grupa docelowa, ton, kanały (strona, social, reklamy).
4. **Głos klienta:** opinie (Google, Ceneo, Trustpilot, Reddit, fora), powtarzające się pochwały i skargi (cytaty!).
5. **Sygnały rynku:** nowe wejścia, finansowanie, regulacje, trendy wyszukiwań.

## Wyniki
- `out/RAPORT.md` (skill `raport-sledztwa`) z sekcją **Wnioski dla nas**: luki w rynku, sposoby wyróżnienia, ryzyka,
- `out/dane/konkurencja.csv`: nazwa, URL, oferta, cena, obietnica, grupa docelowa, kanały, data sprawdzenia,
- `out/dane/glos-klienta.md`: cytaty klientów pogrupowane w tematy (pochwały / skargi / potrzeby).

## Zasady
- Ceny zawsze z datą i linkiem, bo szybko się dezaktualizują.
- Opinie: minimum 3 niezależne wystąpienia, żeby nazwać coś „powtarzającym się”.
- Nie oceniaj konkurencji emocjonalnie; opisuj fakty i wnioski.

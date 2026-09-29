---
source: "Meta Marketing API v25 (developers.facebook.com), praktyka kont 2026"
reviewed: "2026-09-29"
---
# Meta Ads: ściąga planowania

| Cel (objective API) | Kiedy | Optymalizacja |
|---|---|---|
| `OUTCOME_SALES` | sklep, piksel/CAPI z Purchase | zakup (albo AddToCart, gdy < 50 zakupów/tydz.) |
| `OUTCOME_LEADS` | formularz natywny lub lead na stronie | lead (formularz natywny nie wymaga piksela) |
| `OUTCOME_TRAFFIC` | brak konwersji, budowa ruchu/remarketingu | wyświetlenia strony docelowej (nie kliknięcia) |
| `OUTCOME_ENGAGEMENT` | wideo, społeczność | ThruPlay / obejrzenia |
| `OUTCOME_AWARENESS` | zasięg, nowa marka | zasięg, częstotliwość ≤ 3/tydz. |
| `OUTCOME_APP_PROMOTION` | aplikacja | instalacje / zdarzenia w aplikacji |

- Kampania zawsze z `special_ad_categories` (pusta lista albo kategoria: kredyt, zatrudnienie, mieszkania, polityka).
- Budżet kampanii (Advantage+ / CBO) do skalowania; budżet zestawu (ABO) do równego testu.
- `lifetime_budget` + `end_time` na zestawach = twardy koniec po stronie Mety; `spend_cap` kampanii od ~100 USD.
- Miejsca emisji: Advantage+ (automatyczne) domyślnie; ręcznie tylko z powodem (np. same Stories dla 9:16).
- Kreacje: 9:16 (Reels/Stories), 4:5 (Feed), 1:1 awaryjnie; tekst w bezpiecznej strefie; napisy w wideo.
- Zmęczenie: częstotliwość > 3–4 i spadek CTR > 30% względem pierwszych 3 dni → nowa kreacja.
- Faza uczenia: ~50 zdarzeń optymalizacji / 7 dni na zestaw; duże zmiany (> 20% budżetu, nowa kreacja) ją restartują.

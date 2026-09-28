---
name: warianty-ab
description: "Warianty filmu do testów A/B: hook, głos, tempo, muzyka."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, ab-test, variants, hook, optimization]
    related_skills: [krotki-film, scenariusz, lektor-i-dzwiek, kontrola-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Warianty do testów A/B

Jeden plan, kilka wersji różniących się **jedną** zmienną, żeby wynik testu coś mówił. `film.py` renderuje warianty
z pola `warianty` planu; ujęcia i lektor wspólnych scen idą z cache, więc każdy kolejny wariant kosztuje sekundy.

## Kiedy użyć
- Karta prosi o warianty, test hooków, „kilka wersji do wyboru”, kampania z budżetem na testy.
- Ten sam film na różne platformy z inną długością (wariant = skrócona lista scen).

## Kiedy NIE używać
- Film jednorazowy bez testu: jeden dobry wariant zamiast trzech przeciętnych.

## Co zmieniać (od największego wpływu)
| Zmienna | Jak w planie | Uwagi |
|---|---|---|
| hook (tekst) | `"sceny": {"1": {"tekst": "…", "tekst_ekranowy": "…"}}` | największy wpływ na zatrzymanie |
| obraz hooka | `"sceny": {"1": {"ujecie": {"stock_id": "…"}}}` | ruch vs statyka, twarz vs produkt |
| głos | `"lektor": {"glos": "pl-PL-ZofiaNeural"}` | M/K zmienia odbiór marki |
| tempo | `"lektor": {"tempo": "+12%"}` | szybciej = krócej, energiczniej |
| długość | `"sceny": [ … ]` (pełna, krótsza lista) | 15 s vs 30 s |
| muzyka / napisy | `"muzyka": {...}`, `"napisy": {"styl": "zwykle"}` | mniejszy wpływ; testuj na końcu |

## Kroki
1. Hipoteza w jednym zdaniu na wariant („pytanie w hooku zatrzyma lepiej niż liczba”).
2. Warianty w planie (`nazwa`: A = bazowy, potem B, C…); maks. 4 naraz; różnica w jednej zmiennej na wariant.
3. `python3 $HERMES_HOME/scripts/film.py render out/wideo/src/plan.json --wszystkie` (szkic: `--szkic`).
4. `kontrola-wideo` dla każdego wariantu; odpada wariant z błędem technicznym, nie „gorszy w moim guście”.
5. Tabela w RAPORT.md: wariant, zmienna, hipoteza, plik, długość, wynik kontroli, rekomendacja kolejności testu.
   Wyniki testu (zatrzymanie, CTR) zbiera użytkownik po publikacji; propozycja, co mierzyć: 3-sekundowe wyświetlenia,
   średni czas oglądania, zapisy.

## Wyjścia
- `out/wideo/<film>/<film>-<wariant>-<format>.mp4` dla każdego wariantu, `film-<wariant>.json`, tabela w RAPORT.md.

## Definition of Done
- [ ] każdy wariant różni się jedną nazwaną zmienną i ma hipotezę,
- [ ] wszystkie warianty przechodzą `qa_wideo.py`; wspólne sceny identyczne,
- [ ] tabela wariantów z rekomendacją w RAPORT.md; nic nie opublikowane.

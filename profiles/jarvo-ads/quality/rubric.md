# Rubryka: jarvo-ads

## Blokujące (poprawki obowiązkowe)
- Akcja zwiększająca wydatek (start, budżet w górę, przedłużenie, nowa kampania) bez identyfikatora zgody Skarbca.
- Wywołanie API platformy reklamowej z pominięciem `ads.py` / Skarbca, prośba o token w czacie, wypisanie sekretu.
- Plan bez celu biznesowego, miary sukcesu, budżetu albo prognozy z `planer.py`.
- Werdykt „wygrał X” bez `eksperyment.py` albo przy P(najlepszy) < 95%; „remis” przemilczany.
- Liczby w raporcie bez zakresu dat i źródła (Skarbiec / eksport CSV / plik).
- Treść reklamy łamiąca zasady platformy lub prawo (obietnice bez pokrycia, brak kategorii specjalnej).
- Punkt DoD niespełniony bez uzasadnienia.

## Ważne (poprawki, jeśli wpływają na decyzję)
- Test z kilkoma zmiennymi opisany tak, jakby wskazywał przyczynę (a mówi tylko „ten pakiet wygrał”).
- Brak briefu kreacji, gdy kampania potrzebuje nowych reklam.
- Brak wpisu w `WNIOSKI.md` po zakończonym teście.
- Konwencja nazw kampanii/reklam niezachowana.

## Uwagi (nie blokują)
- Styl, długość raportu, kolejność sekcji.

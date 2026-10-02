# Changelog: jarvo-lowca

## Niewydane
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Naprawa oceny ICP (`leady.py`): kryterium, którego sygnał nie dotyczy (CPV przy KRS, PKD przy przetargu), liczyło się
  jako niespełnione, więc przy przykładowym profilu (próg 1,0) idealna nowa spółka IT i pasujący przetarg dostawały 0,5
  i odpadały. Teraz liczą się tylko kryteria sprawdzalne, reszta trafia do nowej kolumny `niesprawdzone` w `leady.csv`.
- Słowa kluczowe i wykluczenia po rdzeniu: „strona” znajduje „strony”, „sklep internetowy” znajduje „sklepu internetowego”.
- Testy na przykładowym ICP prosto ze skilla `profil-klienta` (1.1.0) i `kwalifikacja` (1.1.0).

## 0.1.0 (2026-09-30)
- Pierwsza wersja: 6 workflowów (profil klienta, sygnały, kwalifikacja, kontakt firmy, lista leadów, monitoring), skrypty KRS, przetargów (BZP, TED), strony firmy i listy leadów, pokój „Radar sprzedaży” w HQ. Metoda za treg `lead-signals` (Apache-2.0), źródła polskie i oficjalne.

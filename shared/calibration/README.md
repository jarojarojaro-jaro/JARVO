# Kalibracja pod rodzinę modelu

`scripts/build.py` dokleja do SOUL każdego agenta jeden blok stąd, wybrany po modelu agenta
(`fleet.yaml` → poziom modelu → identyfikator bez prefiksu dostawcy): `gpt-*` → `gpt.md`, `claude-*` →
`claude.md`, `deepseek*` → `deepseek.md`, `kimi*` → `kimi.md`, reszta → `generic.md`.
Z pliku trafia sekcja `### Wszyscy` i sekcja roli: `### Orkiestrator` (TARS) albo `### Wykonawca`.

Zasady pisania (za oh-my-hermes, `MODEL_OPTI.md`, MIT):
- blok przeciwdziała **znanej słabości rodziny**, a nie opisuje dobre praktyki ogólnie,
- najwyżej 3 zdania-reguły na sekcję: każda nowa reguła wypiera inną, więc dopisanie = decyzja,
- żadnych przykładów „źle:” (słabszy model je kopiuje), reguły opisują pożądane zachowanie, w pierwszej osobie jak SOUL,
- nic, co pcha model do dłuższej pracy; kalibracja zawęża, nie przyspiesza „na siłę”,
- rodzina nieznana dostaje `generic.md`: ta sama dyscyplina stopu, bez licznika na konkretną słabość.

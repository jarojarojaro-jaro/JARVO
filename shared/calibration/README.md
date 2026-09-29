# Kalibracja pod rodzinę modelu

`scripts/build.py` dokleja do SOUL każdego agenta jeden blok stąd, wybrany po modelu agenta
(`fleet.yaml` → poziom modelu → identyfikator bez prefiksu dostawcy, bez rozróżniania wielkości liter):
`gpt-*`, `chatgpt*`, `o3*`, `o4*` → `gpt.md`, `claude*` → `claude.md`, `deepseek*` → `deepseek.md`, `kimi*` →
`kimi.md`, reszta → `generic.md` (lista w `MODEL_FAMILIES`, `scripts/fleetlib.py`).
Z pliku trafia sekcja `### Wszyscy` i sekcja roli: `### Orkiestrator` (Jarvo) albo `### Wykonawca`; komentarze
HTML w pliku to notatki autora i do SOUL nie trafiają. Blok siedzi między znacznikami `<!-- Jarvo:CALIBRATION … -->`:
gdy w panelu wybierzesz agentowi inny model, `install-fleet.sh` (`scripts/profile_model.py`) podmienia go pod
nową rodzinę. Sekcje i limit reguł pilnuje `scripts/validate.py`.

Zasady pisania (za oh-my-hermes, `MODEL_OPTI.md`, MIT):
- blok przeciwdziała **znanej słabości rodziny**, a nie opisuje dobre praktyki ogólnie,
- najwyżej 3 zdania-reguły na sekcję: każda nowa reguła wypiera inną, więc dopisanie = decyzja,
- żadnych przykładów „źle:” (słabszy model je kopiuje), reguły opisują pożądane zachowanie, w pierwszej osobie jak SOUL,
- nic, co pcha model do dłuższej pracy; kalibracja zawęża, nie przyspiesza „na siłę”,
- rodzina nieznana dostaje `generic.md`: ta sama dyscyplina stopu, bez licznika na konkretną słabość.

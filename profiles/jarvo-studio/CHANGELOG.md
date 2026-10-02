# Changelog: jarvo-studio

## Niewydane
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop). `publikacja`: prośba o zgodę z odciskiem paczki, przed zaplanowaniem `odcisk.py --sprawdz`, jedno zaplanowanie na zgodę.
- `copy-pl`: sito AI-izmów `references/sito.md` (za marketing-os `slop-patterns.md`, MIT, po polsku): 13 wzorców struktury i znaczenia, tabela słów do skreślenia, test na głos, wyjątek dla formalnych marek.
- Wspólny skill `hooki` (`shared/skills/`, za marketing-os `hooks.md`, MIT): trzy warstwy hooka bez powtórzeń, 18 taktyk, korpus słów klientów, rozbieg, lejek diagnozy. `copy-pl`: hook z taktyką, warianty reklamy = różne taktyki.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.2.0 (2026-09-28)
- Wideo przeniesione do nowego agenta `jarvo-wideo` (Wideograf): film-z-kodu, napisy, HyperFrames, Manim, wideo z AI.
  Studio pisze brief filmu w pakiecie kampanii (`out/teksty/BRIEF-WIDEO.md`); `generacja-ai` tylko obrazy.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 7 workflowów, 3 skrypty, szablon grafiki, 35 skilli zewnętrznych (marketing, wideo HTML, design, kreacja).

# Changelog: jarvo-ads

## Niewydane
- `podlacz-konto`, `start-kampanii`, `optymalizacja` 1.1.0 z `metadata.jarvo.wymaga: [skarbiec]`: dopóki Skarbca nie ma w `infra/docker-compose.yml`, nie trafiają do profilu, a SOUL dostaje generowaną sekcję „Czego w tej instalacji nie zrobisz”. Działają plan, test, audyt i raport z eksportu CSV.
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop).
- Wspólny skill `hooki` (`shared/skills/`, za marketing-os `hooks.md`, MIT): trzy warstwy hooka bez powtórzeń, 18 taktyk, korpus słów klientów, rozbieg, lejek diagnozy. `plan-testu`: brief z hookiem w trzech warstwach i metryką dopasowaną do warstwy; `audyt-konta`: lejek diagnozy kreacji.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-29)
- Pierwsza wersja: 10 workflowów (plan kampanii, testy, start, podłączenie kont, audyt, optymalizacja, raporty, wnioski, konwersje, zgodność), skrypty planera, statystyki testów i eksportów CSV, klient Skarbca.

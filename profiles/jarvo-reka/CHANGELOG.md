# Changelog: jarvo-reka

## Niewydane
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop).
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czyta też skille Wideografa i Ads (`skills.external_dirs`); walidator pilnuje, żeby widziała każdego snajpera.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 4 workflowy, 2 skrypty, dostęp do skilli snajperów (read-only) i pełnego katalogu Hermesa.

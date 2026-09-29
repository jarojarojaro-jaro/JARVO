# Changelog: jarvo-reka

## Niewydane
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czyta też skille Wideografa i Ads (`skills.external_dirs`); walidator pilnuje, żeby widziała każdego snajpera.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 4 workflowy, 2 skrypty, dostęp do skilli snajperów (read-only) i pełnego katalogu Hermesa.

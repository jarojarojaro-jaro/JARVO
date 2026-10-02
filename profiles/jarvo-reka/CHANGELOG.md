# Changelog: jarvo-reka

## Niewydane
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Czyta też skille Twórcy aplikacji (`jarvo-mobile`) w `skills.external_dirs`.
- `kiedy-oddac-snajperowi` 1.2.0: tabela „komu oddać” generowana z pól `oddaj_gdy` w `fleet.yaml` (wcześniej ręczna, bez Ads i Łowcy), więc każdy nowy specjalista trafia do niej sam; plus jak przekazać zadanie, żeby specjalista nie zaczynał od zera.
- Czyta też skille Łowcy leadów (`jarvo-lowca`) w `skills.external_dirs`.
- Skill `writing-for-agents` (mattpocock/skills, MIT): warsztat pisania dokumentów dla agentów (wskaźniki kontekstu, hierarchia informacji, kryteria ukończenia). Mapa workflowów: nowy skill = `skill-creator` + `writing-for-agents`.
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop).
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czyta też skille Wideografa i Ads (`skills.external_dirs`); walidator pilnuje, żeby widziała każdego snajpera.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 4 workflowy, 2 skrypty, dostęp do skilli snajperów (read-only) i pełnego katalogu Hermesa.

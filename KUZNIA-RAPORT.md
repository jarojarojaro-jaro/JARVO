# Kuźnia skilli: prawdziwy test (jarvo-web / web/nowa-strona)

**Status: w toku — krok: evals bazy** (start 2026-10-14 12:56 UTC)

- piaskownica: flota na OpenRouterze, wszyscy agenci `anthropic/claude-haiku-5.5` (dym: jarvo-web odpowiada modelem)
- proponujący: `anthropic/claude-haiku-5.5`, sędzia: `openai/gpt-6-luna`
- 20 scenariuszy × 1 powtórzenie × 2 przebiegi (baza, kandydat); szacunek sędziego 0,9 $, budżet 5 $

## Poprawki na main do tej pory
- `0fc8a3a` Kuźnia: `--proponujacy <model>` nadpisuje `evals.proposer` na jeden przebieg
- `8b3a60a` Evals i kuźnia na stagingu: klucz sędziego z `.env` hosta, model agenta z buildu
  (bez tego sędzia w kontenerze stagingu nie miał klucza, a przy agentach na Claude sędzią był Claude)

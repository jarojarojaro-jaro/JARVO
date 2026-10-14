# Kuźnia skilli: prawdziwy test (jarvo-web / web/nowa-strona)

**Status: w toku — krok: propozycja i evals kandydata (baza gotowa: 5/20 zaliczonych, ok. 70 min)**

- piaskownica: flota na OpenRouterze, wszyscy agenci `anthropic/claude-haiku-5.5` (dym: jarvo-web odpowiada modelem)
- proponujący: `anthropic/claude-haiku-5.5`, sędzia: `openai/gpt-6-luna`
- 20 scenariuszy × 1 powtórzenie × 2 przebiegi (baza, kandydat); szacunek sędziego 0,9 $, budżet 5 $

## Poprawki na main do tej pory
- `0fc8a3a` Kuźnia: `--proponujacy <model>` nadpisuje `evals.proposer` na jeden przebieg
- `8b3a60a` Evals i kuźnia na stagingu: klucz sędziego z `.env` hosta, model agenta z buildu
  (bez tego sędzia w kontenerze stagingu nie miał klucza, a przy agentach na Claude sędzią był Claude)
- `67e1243` Kuźnia: proponujący dostaje porażki swojego skilla i limit w znakach
  (pierwsza propozycja odpadła na limicie: +23% przy limicie 20%, a dostała porażki niezwiązane ze skillem)

## Przebieg
- pierwsza próba zatrzymana na limitach (bramka zadziałała); po poprawce dokończenie od kroku propozycji
  na tych samych wynikach bazy
- równolegle na main pojawiły się zmiany skilli Web z innej sesji; żeby pojedynek był uczciwy, kandydat
  budowany jest z kopii repo na commicie bazy `0fc8a3a` (+ tylko poprawki kuźni), nie z bieżącego main

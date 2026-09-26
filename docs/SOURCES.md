# Źródła i licencje (third-party notices)

TARS jest zbudowany na cudzej, otwartej pracy. Ten plik mówi, **co** wzięliśmy, **skąd**, na jakiej
**licencji** i **jak** spełniamy jej warunki. Narzędzia uruchamiane przez agentów (npm, Python, sidecary)
są opisane osobno w [TOOLBOX.md](TOOLBOX.md), razem z polityką licencji.

## 1. Platforma

| Projekt | Rola | Licencja |
|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) | rdzeń: profile, kanban, cron, gateway, skille, obraz Docker | MIT |

Hermesa nie forkujemy: używamy oficjalnego obrazu i rozszerzamy go na krawędziach (profile, skille, narzędzia).

## 2. Skille dołączane do agentów (vendoring)

Kopiowane przy buildzie z przypiętych commitów zapisanych w [`vendor/skills.lock.yaml`](../vendor/skills.lock.yaml).
Każdy skopiowany skill dostaje `LICENSE-UPSTREAM` (albo licencję z własnego katalogu), `NOTICE-UPSTREAM`
(jeśli źródło go ma) i `.vendored.json` (repo, commit, ścieżka, licencja). Treści skilli nie zmieniamy;
nasze adaptacje żyją w skillach własnych floty.

| Źródło | Commit | Licencja | Dla kogo |
|---|---|---|---|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent): skille z drzewa obrazu | wersja obrazu | MIT | Sherlock, Web, Studio |
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `5b2c000` | MIT | Sherlock, Web, Studio |
| [addyosmani/web-quality-skills](https://github.com/addyosmani/web-quality-skills) | `afa8da9` | MIT | Web |
| [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) | `e77e783` | MIT | Web (skille + skrypty w obrazie) |
| [anthropics/skills](https://github.com/anthropics/skills) | `3337550` | Apache-2.0 (tylko skille z licencją Apache w katalogu) | Web, Studio, Ręka |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | `8798e40` | Apache-2.0 | Studio (wideo z HTML) |

Build odrzuca skill z `anthropics/skills`, jeśli w jego katalogu nie ma licencji Apache-2.0: część
skilli w tym repo ma inne, zastrzeżone warunki i nie wolno ich kopiować.

## 3. Metodologie i prompty (inspiracja, własny tekst)

Te projekty nie są kopiowane. Przeczytaliśmy je i napisaliśmy własne skille po polsku według ich metod.
Autorstwo zaznaczamy w polu `author` skilla.

| Projekt | Licencja | Gdzie w TARS |
|---|---|---|
| [kunchenguid/firstmate](https://github.com/kunchenguid/firstmate) | MIT | model Main Judge: jeden rozmówca, załoga, eskalacja tylko decyzji, stan na dysku ([BOSS.md](BOSS.md)) |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | MIT | `metoda-sherlocka`, `raport-sledztwa`: plan → równoległe wątki → synteza, zasady cytowania |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) | MIT | `metoda-sherlocka`: szerokość/głębokość, iteracyjne pytania uzupełniające |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | MIT | `metoda-sherlocka`: pytania z wielu perspektyw przed wyszukiwaniem |
| Hermes Agent `sdlc-review` (J. Wolniewicz + Hermes Agent) | MIT | `sdlc-review` TARS-a: adaptacja z rubrykami agentów, soczewkami i eskalacją po 3 rundach |

## 4. Obowiązki licencyjne w skrócie

| Licencja | Co robimy |
|---|---|
| MIT | zachowujemy informację o prawach autorskich i licencję (`LICENSE-UPSTREAM` przy każdym skillu) |
| Apache-2.0 | licencja przy skillu, `NOTICE` źródła (jeśli istnieje), treść bez zmian (zmiany oznaczylibyśmy w pliku) |
| AGPL-3.0 (SearXNG, opcjonalnie Postiz) | usługi uruchamiamy bez modyfikacji, tylko prywatnie; zmieniona wersja udostępniana przez sieć innym wymagałaby publikacji źródeł |

Aktualizacja źródła = zmiana `rev` w locku (pełny SHA), build, przegląd różnic w skillach, evals, commit.
Walidator odrzuca źródło bez przypiętego SHA albo bez licencji.

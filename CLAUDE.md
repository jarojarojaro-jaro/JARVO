# Zasady pracy w tym repo

- **Każda aktualizacja = osobny commit i od razu push na GitHub** (gałąź robocza, remote `origin` → jarojarojaro-jaro/JARVO).
  Nie zbieramy kilku zmian w jeden commit i nie zostawiamy zmian niewypchniętych.
- **Dokumentacja zawsze zgodna z kodem.** Zmiana w kodzie, konfiguracji albo flocie aktualizuje w tym samym commicie
  każdy dokument, który ją opisuje: `README.md`, `docs/*.md` (także `docs/JARVO-CALOSC.md`), README i CHANGELOG profilu.
  Nazwy, liczby (skille, skrypty, evals, ataki red teamu), ścieżki, komendy, flagi i statusy w roadmapie mają odpowiadać repo.
  Przed commitem szukamy w dokumentach starych nazw i liczb (`grep -rn`); dokument niezgodny z kodem to błąd jak każdy inny.
- Przed commitem: `python3 -m pytest -q` i `python3 scripts/validate.py` bez błędów.
  Na czystym kontenerze/maszynie najpierw `make dev-deps` (pytest, pyyaml z `requirements-dev.txt`) —
  nie doinstalowujemy narzędzi ręcznie, wszystko jest przypięte w repo.
- **Po każdym dodaniu test w działającym kontenerze**, nie tylko pytest: wdrożenie (`scripts/deploy.sh --no-pull`
  z `JARVO_COMPOSE_DIR`/`JARVO_BUILD` lokalnej instalacji), potem nowa funkcja uruchomiona w `jarvo-hermes`
  jako użytkownik `hermes` (`PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH`), a GUI przez zalogowany dashboard.
  Wszystko ma się spinać: build → instalacja → healthchecki → realne użycie.
- Piaskownica Claude Code: całość jednym poleceniem `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh`
  (start `dockerd`, obraz `hermes-ca:test` = Hermes + certyfikat proxy, `docker build --network host` obrazu
  `jarvo-hermes:local`, bo budowanie przez compose nie widzi proxy, instalacja i `deploy.sh --no-pull --no-build`).
  Kolejne uruchomienia przebudowują obraz tylko po zmianie `infra/` (albo z `--rebuild`).

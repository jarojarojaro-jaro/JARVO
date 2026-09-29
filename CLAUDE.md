# Zasady pracy w tym repo

- **Każda aktualizacja = osobny commit i od razu push na GitHub** (gałąź robocza, remote `origin` → jarojarojaro-jaro/JARVO).
  Nie zbieramy kilku zmian w jeden commit i nie zostawiamy zmian niewypchniętych.
- Przed commitem: `python3 -m pytest -q` i `python3 scripts/validate.py` bez błędów.
  Na czystym kontenerze/maszynie najpierw `make dev-deps` (pytest, pyyaml z `requirements-dev.txt`) —
  nie doinstalowujemy narzędzi ręcznie, wszystko jest przypięte w repo.
- **Po każdym dodaniu test w działającym kontenerze**, nie tylko pytest: wdrożenie (`scripts/deploy.sh --no-pull`
  z `JARVO_COMPOSE_DIR`/`JARVO_BUILD` lokalnej instalacji), potem nowa funkcja uruchomiona w `jarvo-hermes`
  jako użytkownik `hermes` (`PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH`), a GUI przez zalogowany dashboard.
  Wszystko ma się spinać: build → instalacja → healthchecki → realne użycie.
- Piaskownica Claude Code: `dockerd` trzeba uruchomić ręcznie; kontenery budujące nie widzą proxy, więc obraz budujemy
  `docker build --network host --build-arg HERMES_IMAGE=hermes-ca:test --build-arg HTTPS_PROXY=… -t jarvo-hermes:local
  -f infra/Dockerfile .` (obraz `hermes-ca:test` = Hermes + certyfikat proxy), a `deploy.sh` bez `--rebuild`.

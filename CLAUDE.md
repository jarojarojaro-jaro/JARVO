# Zasady pracy w tym repo

- **Każda aktualizacja = osobny commit i od razu push na GitHub** (gałąź robocza, remote `origin` → jarojarojaro-jaro/JARVO).
  Nie zbieramy kilku zmian w jeden commit i nie zostawiamy zmian niewypchniętych.
- Autorem commitów jest użytkownik: na starcie sesji `git config user.name jarojarojaro-jaro && git config user.email miki.jaroszek@gmail.com`
  (GitHub zalicza commit do profilu tylko po zweryfikowanym e-mailu autora); Claude zostaje w stopce jako współautor.
- **Jarvo zawsze nadrzędny.** Z obcych projektów (np. Paperclip, Auto-Company) bierzemy tylko gotowe rozwiązania
  i wzorce, przeniesione do kodu JARVO. Nigdy nie stawiamy nad Jarvem innego systemu sterującego (orkiestratora,
  panelu, pętli agentów). Zanim dodamy coś zapożyczonego, opisujemy właścicielowi, co to zmienia, i czekamy na wybór.
- **Dokumentacja zawsze zgodna z kodem.** Zmiana w kodzie, konfiguracji albo flocie aktualizuje w tym samym commicie
  każdy dokument, który ją opisuje: `README.md`, `docs/*.md` (także `docs/JARVO-CALOSC.md`), README i CHANGELOG profilu.
  Nazwy, liczby (skille, skrypty, evals, ataki red teamu), ścieżki, komendy, flagi i statusy w roadmapie mają odpowiadać repo.
  Przed commitem szukamy w dokumentach starych nazw i liczb (`grep -rn`); dokument niezgodny z kodem to błąd jak każdy inny.
  `scripts/validate.py` sprawdza to, co da się automatycznie: linki i kotwice w `*.md`, obecność każdego agenta
  w dokumentach przeglądowych i liczby w kolumnach „Skille” / „Workflowy własne” / „Evals” tabel.
- **Skarbiec wiedzy (knowledge base) też zgodny z kodem.** Agenci czytają skarbiec (`/opt/data/jarvo/knowledge`), więc
  zmiana w kodzie albo flocie musi do niego dotrzeć. Zasiew przy każdym wdrożeniu (`wiedza.py zasiej`) odświeża sam:
  lustro `docs/*.md` w `zrodla/jarvo-repo/`, bloki `Jarvo:GEN` hubów agentów (skille, skrypty, skille zewnętrzne,
  ostatnie zmiany z `CHANGELOG.md` profilu) i opis agenta z `fleet.yaml`; lint skarbca wskazuje notatki o flocie
  z odwołaniem do skryptu, którego już nie ma. Dlatego każda zmiana zachowania agenta ma wpis w CHANGELOG profilu. Wszystko inne, co opisuje kod (szablony i treści w `knowledge/`, `wiedza/SCHEMA.md`,
  generatory hubów w `wiedza.py`), zmieniamy w tym samym commicie; po wdrożeniu sprawdzamy w kontenerze, że skarbiec
  mówi to samo co repo (np. `grep` w `/opt/data/jarvo/knowledge`), a `wiedza.py lint` jest bez błędów.
- Przed commitem: `python3 -m pytest -q` i `python3 scripts/validate.py` bez błędów.
  Na czystym kontenerze/maszynie najpierw `make dev-deps` (pytest, pyyaml, shellcheck z `requirements-dev.txt`) —
  nie doinstalowujemy narzędzi ręcznie, wszystko jest przypięte w repo.
- **Po każdym dodaniu test w działającym kontenerze**, nie tylko pytest: wdrożenie (`scripts/deploy.sh --no-pull`
  z `JARVO_COMPOSE_DIR`/`JARVO_BUILD` lokalnej instalacji), potem nowa funkcja uruchomiona w `jarvo-hermes`
  jako użytkownik `hermes` (`PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH`), a GUI przez zalogowany dashboard.
  Wszystko ma się spinać: build → instalacja → healthchecki → realne użycie.
- Piaskownica Claude Code: całość jednym poleceniem `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh`
  (start `dockerd`, obraz `hermes-ca:test` = Hermes + certyfikat proxy, `docker build --network host` obrazu
  `jarvo-hermes:local`, bo budowanie przez compose nie widzi proxy, instalacja i `deploy.sh --no-pull --no-build`).
  Kolejne uruchomienia przebudowują obraz tylko po zmianie `infra/` (albo z `--rebuild`).

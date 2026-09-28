# Skróty do pracy z repo floty Jarvo (lokalnie albo na VPS).
PY ?= python3
HERMES_SRC ?=

.PHONY: help validate test build models pins hq-demo deploy harvest new-agent

help:
	@echo "make validate           walidacja repo (fleet, profile, skille, evals, sekrety)"
	@echo "make test               testy (pytest): walidatory, patrol, raporty, skrypty"
	@echo "make build HERMES_SRC=… build dystrybucji do build/ (wymaga drzewa Hermesa)"
	@echo "make models             czy modele z fleet.yaml istnieją na OpenRouter"
	@echo "make pins               czy piny npm spełniają zasady obrazu Hermesa (wiek ≥ 14 dni, engines)"
	@echo "make hq-demo            Jarvo HQ w trybie demo (symulowana flota) do build/hq-demo"
	@echo "make deploy             wdrożenie na VPS (scripts/deploy.sh)"
	@echo "make harvest            raport skilli zmienionych przez agentów na VPS"
	@echo "make new-agent NAME=jarvo-x TITLE='…'   szkielet nowego agenta"

validate:
	$(PY) scripts/validate.py

test:
	$(PY) -m pytest -q tests

build:
	$(PY) scripts/build.py --hermes-src $(HERMES_SRC)

models:
	$(PY) scripts/check-models.py

pins:
	$(PY) scripts/check-pins.py

hq-demo:
	$(PY) scripts/hqbuild.py --demo build/hq-demo
	@echo "Otwórz: cd build/hq-demo && python3 -m http.server 8000  →  http://127.0.0.1:8000"

deploy:
	bash scripts/deploy.sh

harvest:
	bash scripts/harvest-skills.sh

new-agent:
	$(PY) scripts/new-agent.py --name $(NAME) --title "$(TITLE)"

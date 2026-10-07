PYTHON := $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PYTEST := $(shell if [ -f .venv/bin/pytest ]; then echo .venv/bin/pytest; else echo pytest; fi)
RUFF := $(shell if [ -f .venv/bin/ruff ]; then echo .venv/bin/ruff; else echo ruff; fi)

.PHONY: test benchmark benchmark-mock benchmark-gemini benchmark-ollama lint format

test:
	$(PYTEST) tests/

benchmark:
	$(PYTHON) -m benchmark.massive_evaluator --backend mock --analyze

benchmark-mock:
	$(PYTHON) -m benchmark.massive_evaluator --backend mock --analyze

benchmark-gemini:
	$(PYTHON) -m benchmark.massive_evaluator --backend gemini --analyze

benchmark-ollama:
	$(PYTHON) -m benchmark.massive_evaluator --backend ollama --analyze

benchmark-all:
	$(PYTHON) -m benchmark.massive_evaluator --backend all --analyze

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

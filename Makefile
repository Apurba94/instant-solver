.PHONY: install api web test screenshots dev clean

# Use the virtualenv made by scripts/setup-wsl.sh: ./.venv, or the home-directory
# one it creates when the project sits on a Windows drive under WSL.
PY := $(firstword $(wildcard .venv/bin/python $(HOME)/.venvs/instant-solver/bin/python) python3)
ENV_FILE := $(if $(wildcard .env),--env-file .env,)

install:
	$(PY) -m pip install -r requirements-dev.txt
	cd web && npm install

api:
	$(PY) -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload $(ENV_FILE)

web:
	cd web && npm run dev

test:
	$(PY) tests/test_engine.py

screenshots:
	$(PY) tests/screenshot.py ./screenshots

dev:
	@echo "Run 'make api' and 'make web' in two terminals, then open http://localhost:3000"

clean:
	rm -rf web/.next web/node_modules __pycache__ */__pycache__ */*/__pycache__

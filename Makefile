.PHONY: run run-split setup lint e2e-install e2e-test

setup:
	python -m venv .venv
	. .venv/Scripts/Activate.ps1 ; pip install -r requirements.txt
	copy .env.example .env

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

run-split:
	python -m app.run_dual

lint:
	python -m py_compile app/*.py

e2e-install:
	pnpm install
	pnpm e2e:install

e2e-test:
	pnpm e2e:test

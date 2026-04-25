.PHONY: run setup lint

setup:
	python -m venv .venv
	. .venv/Scripts/Activate.ps1 ; pip install -r requirements.txt
	copy .env.example .env

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

lint:
	python -m py_compile app/*.py

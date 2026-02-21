.PHONY: install run install-dev dev lint format test type build up down logs

install:
	pip install .

run:
	uvicorn api.main:app --host 0.0.0.0 --port 8000

install-dev:
	pip install -e ".[dev]"

dev:
	uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

lint:
	ruff check .

format:
	ruff format .

test:
	pytest -v

type:
	mypy api

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f wireguard-api

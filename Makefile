.PHONY: up down build seed logs ps test lint clean

up:
	docker compose up

down:
	docker compose down

build:
	docker compose build

seed:
	docker compose run --rm mcp-server python seed/seed_data.py

logs:
	docker compose logs -f

ps:
	docker compose ps

test:
	docker compose run --rm mcp-server pytest
	docker compose run --rm mcp-gateway pytest

lint:
	docker compose run --rm mcp-server ruff check .
	docker compose run --rm mcp-gateway ruff check .

clean:
	docker compose down -v --remove-orphans

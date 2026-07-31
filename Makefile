.PHONY: up down build seed logs ps test lint clean

up:
	docker compose up

down:
	docker compose down

build:
	docker compose build

seed:
	docker compose run --rm ecommerce-mcp-server uv run python seed/seed_data.py

logs:
	docker compose logs -f

ps:
	docker compose ps

test:
	docker compose run --rm ecommerce-mcp-server uv run pytest
	docker compose run --rm mcp-gateway uv run pytest

lint:
	docker compose run --rm ecommerce-mcp-server uv run ruff check .
	docker compose run --rm mcp-gateway uv run ruff check .

clean:
	docker compose down -v --remove-orphans

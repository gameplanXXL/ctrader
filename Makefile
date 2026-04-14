.PHONY: start stop test

start:
	docker compose up -d

stop:
	docker compose down

test:
	uv run pytest

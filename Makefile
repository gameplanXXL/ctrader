.PHONY: start stop test

start:
	docker compose up -d
	@echo ""
	@echo "ctrader ist erreichbar unter:"
	@echo "  App:       http://127.0.0.1:8000/"
	@echo "  API-Docs:  http://127.0.0.1:8000/docs"
	@echo "  Health:    http://127.0.0.1:8000/healthz"

stop:
	docker compose down

test:
	uv run pytest

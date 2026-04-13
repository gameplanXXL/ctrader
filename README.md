# ctrader

**Personal trading platform** — unified trade journal (Interactive Brokers) with human-gated AI-agent farm (cTrader).

Single-user, localhost-only, server-rendered web app built with FastAPI + HTMX + Tailwind + PostgreSQL.

## Status

Week 0 — FastAPI scaffolding. See `_bmad-output/planning-artifacts/` for the full PRD, architecture, epics, and story specs.

## Quickstart (Dev)

```bash
# 1. Configure environment
cp .env.example .env
# edit .env and set DATABASE_URL

# 2. Start PostgreSQL + ctrader via Docker Compose
docker compose up -d

# 3. Check health
curl http://127.0.0.1:8000/
```

## Project Structure

```
ctrader/
├── app/                   # FastAPI application
│   ├── main.py            # App entry point + lifespan
│   ├── config.py          # pydantic-settings (.env loader)
│   ├── logging.py         # structlog JSON logging with rotation
│   └── db/
│       └── pool.py        # asyncpg connection pool
├── tests/
│   ├── unit/              # Unit tests (no external services)
│   └── integration/       # Integration tests (real DB, opt-in)
├── migrations/            # PostgreSQL migrations (Story 1.2)
├── docker-compose.yml     # ctrader + postgres services
├── Dockerfile             # Multi-stage build
└── pyproject.toml         # uv-managed dependencies
```

## Tech Stack (Locked)

- **Language:** Python 3.12+
- **Dependency Manager:** `uv`
- **Web Framework:** FastAPI + HTMX + Tailwind (server-rendered, no Node build)
- **Database:** PostgreSQL via `asyncpg` (binary protocol, built-in connection pool)
- **Charts:** `lightweight-charts` (TradingView, Apache 2.0, local JS vendor)
- **IB Integration:** `ib_async` (not `ib_insync` — unmaintained)
- **cTrader Integration:** OpenApiPy (Protobuf)
- **Fundamental/News:** MCP dependency on `fundamental` project

See `CLAUDE.md` for the full list of locked technical decisions.

## License

Proprietary — personal project, not for redistribution.

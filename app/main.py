"""FastAPI application entry point.

Wires up configuration, structured logging, and the asyncpg pool in a
single `lifespan` context so the app has a clean startup/shutdown story.

References:
- FR50: Health widget needs broker/MCP/job status — GET / is the Week-0
  placeholder and grows into a Week-8 health widget.
- NFR-S2: Server binds to 127.0.0.1 only (enforced via settings.host default).
- NFR-M6: Single-process — FastAPI + (later) APScheduler share one asyncpg pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.db.migrate import run_migrations
from app.db.pool import close_pool, create_pool
from app.logging import configure_logging, get_logger
from app.services.taxonomy import get_taxonomy, load_taxonomy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown orchestration.

    Order matters: configure logging first (so every subsequent line is
    JSON), then run pending migrations against the target DB, then open
    the long-lived asyncpg pool. Teardown runs in reverse.
    """

    configure_logging()
    logger = get_logger(__name__)
    logger.info(
        "app.startup",
        version=__version__,
        environment=settings.environment,
        host=settings.host,
        port=settings.port,
    )

    # Fail-fast: load and validate taxonomy.yaml at startup so a broken
    # config aborts the boot rather than dying mid-request later (FR14).
    get_taxonomy.cache_clear()
    app.state.taxonomy = load_taxonomy()
    # Prime the lru_cache for downstream `Depends(get_taxonomy)` consumers.
    get_taxonomy()

    # Apply any pending schema migrations before the pool goes live. This
    # opens and closes its own one-shot connection so we never accidentally
    # run DDL through a pooled worker.
    applied = await run_migrations()
    if applied:
        logger.info("app.migrations_applied", versions=applied)

    app.state.db_pool = await create_pool()
    try:
        yield
    finally:
        await close_pool(app.state.db_pool)
        logger.info("app.shutdown")


app = FastAPI(
    title="ctrader",
    description="Personal trading platform — unified journal + human-gated AI-agent farm",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/", response_class=JSONResponse)
async def root() -> dict[str, str]:
    """Week-0 placeholder. Grows into the full journal startpage in Epic 2."""

    return {
        "app": "ctrader",
        "version": __version__,
        "status": "ok",
        "environment": settings.environment,
    }

"""asyncpg connection pool lifecycle.

One pool per process, owned by the FastAPI lifespan. Services/routers get
connections via `acquire_connection()`.

References:
- Architecture Decision #1: asyncpg, min=2, max=10, created in lifespan
- NFR-M6: Single-process app (FastAPI + APScheduler share this pool)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg pool. Called once at startup from the lifespan."""

    logger.info(
        "db.pool.creating",
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    if pool is None:
        # asyncpg.create_pool returns Optional[Pool] in the type stubs; in
        # practice it either returns a Pool or raises. Guard against the
        # pathological case so mypy/ruff are happy.
        raise RuntimeError("asyncpg.create_pool returned None")
    logger.info("db.pool.created")
    return pool


async def close_pool(pool: asyncpg.Pool) -> None:
    """Close the asyncpg pool. Called at shutdown."""

    logger.info("db.pool.closing")
    await pool.close()
    logger.info("db.pool.closed")


@asynccontextmanager
async def acquire_connection(
    pool: asyncpg.Pool,
) -> AsyncIterator[asyncpg.Connection]:
    """Convenience wrapper for borrowing a connection from the pool.

    Usage:
        async with acquire_connection(app.state.db_pool) as conn:
            rows = await conn.fetch("SELECT 1")
    """

    async with pool.acquire() as conn:
        yield conn

"""asyncpg connection pool lifecycle.

One pool per process, owned by the FastAPI lifespan. Services/routers get
connections via `acquire_connection()`.

References:
- Architecture Decision #1: asyncpg, min=2, max=10, created in lifespan
- NFR-M6: Single-process app (FastAPI + APScheduler share this pool)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


def _jsonb_encode(value: object) -> str:
    """Encoder for asyncpg's JSONB codec.

    Code-review H7 / BH-18: we go through `json.dumps(..., default=str)`
    so any future dict containing a `Decimal`, `datetime`, or other
    non-JSON-native value doesn't crash the encoder. Pydantic's own
    `model_dump(mode="json")` already flattens these for
    `TriggerSpec`, but this layer keeps the safety net for ad-hoc
    dicts (ib_flex_import, manual inserts, tests).
    """

    return json.dumps(value, default=str)


async def init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection setup — register a JSONB codec so `trigger_spec`
    round-trips as a Python dict instead of a raw JSON string.

    Without this, `row["trigger_spec"]` is `str` and the Story 3.3
    prose renderer crashes with `AttributeError: 'str' object has no
    attribute 'get'`. asyncpg's default is to return JSONB as text;
    registering `json.loads`/`json.dumps` here makes it behave like
    the Python `dict` the service layer expects.

    Exported publicly so tests (and any other direct
    `asyncpg.connect()` caller) can opt in without reaching for the
    private underscore-prefixed alias.
    """

    await conn.set_type_codec(
        "jsonb",
        encoder=_jsonb_encode,
        decoder=json.loads,
        schema="pg_catalog",
    )


# Back-compat alias — remove when all call sites have been updated.
_init_connection = init_connection


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
        init=init_connection,
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

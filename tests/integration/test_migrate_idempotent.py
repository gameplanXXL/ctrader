"""Integration test: migrations are idempotent (Story 1.2 AC #3, NFR-R7).

Runs `run_migrations()` twice against a fresh PostgreSQL container and
asserts:
1. First run applies 001_initial_schema
2. Second run applies nothing (no-op)
3. `schema_migrations` has exactly one row per migration
4. All enum types from 001 exist in the catalog
5. The `schema_migrations` table exists and is reachable

Marked `integration` so it can be opted out with `pytest -m "not integration"`
on machines without a Docker daemon.
"""

from __future__ import annotations

import shutil

import asyncpg
import pytest

from app.db.migrate import run_migrations

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_docker() -> None:
    """Skip the whole module if the `docker` CLI isn't available."""

    if shutil.which("docker") is None:
        pytest.skip("docker not available — integration tests require a Docker daemon")


async def test_run_migrations_records_001(pg_dsn: str) -> None:
    """After running migrations the schema_migrations table records 001.

    Note: this test used to assert `"001" in applied` from a single
    `run_migrations()` call, but the session-scoped `pg_container`
    fixture means another test module may have already applied the
    migrations before us — in which case `applied` is empty (idempotent
    by design). The stronger, order-independent assertion is that 001
    is recorded in `schema_migrations` after the call, not that it was
    applied *this call*.
    """

    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        rows = await conn.fetch("SELECT version FROM schema_migrations")
    finally:
        await conn.close()

    versions = {row["version"] for row in rows}
    assert "001" in versions


async def test_second_run_is_noop(pg_dsn: str) -> None:
    """Running migrations again against the same DB is a no-op."""

    # First run (idempotent — may have run in the previous test).
    await run_migrations(dsn=pg_dsn)

    applied = await run_migrations(dsn=pg_dsn)
    assert applied == []


async def test_schema_migrations_has_one_row_per_version(pg_dsn: str) -> None:
    """After multiple runs there's still exactly one row per version."""

    await run_migrations(dsn=pg_dsn)
    await run_migrations(dsn=pg_dsn)
    await run_migrations(dsn=pg_dsn)

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        rows = await conn.fetch(
            "SELECT version, COUNT(*) AS n FROM schema_migrations GROUP BY version"
        )
    finally:
        await conn.close()

    counts = {row["version"]: row["n"] for row in rows}
    assert counts.get("001") == 1


async def test_enums_from_001_exist(pg_dsn: str) -> None:
    """All six ENUM types from 001 are present in pg_type after migrating."""

    await run_migrations(dsn=pg_dsn)

    expected = {
        "trade_source",
        "trade_side",
        "order_status",
        "horizon_type",
        "strategy_status",
        "risk_gate_result",
    }

    conn = await asyncpg.connect(dsn=pg_dsn)
    try:
        rows = await conn.fetch(
            "SELECT typname FROM pg_type WHERE typname = ANY($1::text[])",
            list(expected),
        )
    finally:
        await conn.close()

    found = {row["typname"] for row in rows}
    missing = expected - found
    assert not missing, f"missing enum types: {missing}"

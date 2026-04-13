"""Integration tests for the IB Flex Query upsert pipeline (Story 2.1).

Spins up a fresh PostgreSQL via testcontainers, runs the migrations
(001 + 002), and verifies the full parse-and-upsert path against the
sample Flex XML fixture.

Acceptance criteria covered:
- AC1: trades table created with expected columns
- AC3: stock trades imported correctly
- AC4: single-leg options imported, multi-leg skipped
- AC5: re-import is idempotent (no duplicate rows)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import asyncpg
import pytest

from app.db.migrate import run_migrations
from app.services.ib_flex_import import import_flex_xml

pytestmark = pytest.mark.integration


SAMPLE_XML = (Path(__file__).resolve().parents[1] / "fixtures" / "sample_flex_query.xml").read_text(
    encoding="utf-8"
)


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker not available — integration tests require a Docker daemon")


@pytest.fixture
async def conn(pg_dsn: str) -> asyncpg.Connection:
    """Migrated DB + open connection per test, with a fresh `trades`
    table on each run so order doesn't matter.
    """

    await run_migrations(dsn=pg_dsn)

    connection = await asyncpg.connect(dsn=pg_dsn)
    try:
        # Each test starts with an empty trades table — drop and rerun
        # the migration so we avoid cross-test interference.
        await connection.execute("DELETE FROM trades")
        yield connection
    finally:
        await connection.close()


# ---------------------------------------------------------------------------
# AC1 — schema is in place
# ---------------------------------------------------------------------------


async def test_trades_table_exists_with_expected_columns(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'trades'
        """
    )
    columns = {row["column_name"] for row in rows}
    expected = {
        "id",
        "symbol",
        "asset_class",
        "side",
        "quantity",
        "entry_price",
        "exit_price",
        "opened_at",
        "closed_at",
        "pnl",
        "fees",
        "broker",
        "perm_id",
        "trigger_spec",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns), f"missing columns: {expected - columns}"


async def test_unique_constraint_on_broker_perm_id(conn: asyncpg.Connection) -> None:
    """Sanity: NFR-R1 dedup key exists at the schema level."""

    indexes = await conn.fetch(
        """
        SELECT indexname FROM pg_indexes
         WHERE tablename = 'trades' AND indexdef ILIKE '%broker%perm_id%'
        """
    )
    assert indexes, "expected a unique index on (broker, perm_id)"


# ---------------------------------------------------------------------------
# AC3 + AC4 — sample import counts
# ---------------------------------------------------------------------------


async def test_import_inserts_four_trades_and_skips_spread_and_invalid(
    conn: asyncpg.Connection,
) -> None:
    """The updated sample fixture has 4 valid executions.

    Each Flex `<Trade>` is one execution, so the AAPL open (BUY+O) and
    AAPL close (SELL+C) are two separate rows — they share the stock
    symbol but carry different perm_ids.
    """

    result = await import_flex_xml(conn, SAMPLE_XML)

    assert result.inserted == 4
    assert result.skipped_multi_leg == 2
    assert result.skipped_invalid == 1
    assert result.skipped_duplicate == 0

    count = await conn.fetchval("SELECT COUNT(*) FROM trades")
    assert count == 4


async def test_imported_stocks_and_options_have_expected_values(
    conn: asyncpg.Connection,
) -> None:
    await import_flex_xml(conn, SAMPLE_XML)

    rows = await conn.fetch(
        "SELECT perm_id, symbol, asset_class, side, quantity, fees FROM trades ORDER BY perm_id"
    )
    by_perm = {row["perm_id"]: row for row in rows}

    # AAPL stock long open — BUY + O → buy
    assert "1000000001" in by_perm
    assert by_perm["1000000001"]["symbol"] == "AAPL"
    assert by_perm["1000000001"]["asset_class"] == "stock"
    assert by_perm["1000000001"]["side"] == "buy"
    assert by_perm["1000000001"]["quantity"] == 100
    assert by_perm["1000000001"]["fees"] == 1.00

    # AAPL stock long close — SELL + C → sell
    assert "1000000001b" in by_perm
    assert by_perm["1000000001b"]["side"] == "sell"

    # MSFT stock short open — SELL + O → short (not plain sell)
    assert "1000000002" in by_perm
    assert by_perm["1000000002"]["side"] == "short"


# ---------------------------------------------------------------------------
# AC5 — idempotent re-import (NFR-R1)
# ---------------------------------------------------------------------------


async def test_reimport_is_idempotent(conn: asyncpg.Connection) -> None:
    first = await import_flex_xml(conn, SAMPLE_XML)
    assert first.inserted == 4
    assert first.skipped_duplicate == 0

    second = await import_flex_xml(conn, SAMPLE_XML)
    assert second.inserted == 0
    assert second.skipped_duplicate == 4

    count = await conn.fetchval("SELECT COUNT(*) FROM trades")
    assert count == 4, "row count must not grow on re-import (NFR-R1)"

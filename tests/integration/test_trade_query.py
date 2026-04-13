"""Integration tests for `trade_query.list_trades` (Story 2.3).

Spins up a fresh PostgreSQL via testcontainers, runs the migrations,
seeds a known set of trades and asserts ordering, pagination, and
the untagged counter behave per spec.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg
import pytest

from app.db.migrate import run_migrations
from app.db.pool import _init_connection
from app.models.trade import AssetClass, TradeIn, TradeSide, TradeSource
from app.services.ib_flex_import import insert_trades
from app.services.trade_query import DEFAULT_PAGE_SIZE, get_trade_detail, list_trades

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker not available — integration tests require a Docker daemon")


@pytest.fixture
async def conn(pg_dsn: str) -> asyncpg.Connection:
    await run_migrations(dsn=pg_dsn)
    connection = await asyncpg.connect(dsn=pg_dsn)
    # Register the JSONB codec that production uses (Story 3.3 fix).
    await _init_connection(connection)
    try:
        await connection.execute("DELETE FROM trades")
        yield connection
    finally:
        await connection.close()


def _make_trade(
    *,
    perm_id: str,
    symbol: str = "AAPL",
    minutes_offset: int = 0,
    pnl: Decimal | None = None,
    closed: bool = False,
    trigger_spec: dict | None = None,
    broker: TradeSource = TradeSource.IB,
) -> TradeIn:
    base = datetime(2026, 4, 13, 9, 30, tzinfo=UTC)
    opened = base + timedelta(minutes=minutes_offset)
    return TradeIn(
        symbol=symbol,
        asset_class=AssetClass.STOCK,
        side=TradeSide.BUY,
        quantity=Decimal("100"),
        entry_price=Decimal("150.00"),
        exit_price=Decimal("151.50") if closed else None,
        opened_at=opened,
        closed_at=opened + timedelta(hours=1) if closed else None,
        pnl=pnl,
        fees=Decimal("1.0"),
        broker=broker,
        perm_id=perm_id,
        trigger_spec=trigger_spec,
    )


# ---------------------------------------------------------------------------
# Ordering + pagination
# ---------------------------------------------------------------------------


async def test_list_trades_returns_newest_first(conn: asyncpg.Connection) -> None:
    trades = [
        _make_trade(perm_id="t-old", minutes_offset=0),
        _make_trade(perm_id="t-mid", minutes_offset=30),
        _make_trade(perm_id="t-new", minutes_offset=60),
    ]
    await insert_trades(conn, trades)

    page = await list_trades(conn, page=1)
    perm_ids = [t["perm_id"] for t in page.trades]

    assert perm_ids == ["t-new", "t-mid", "t-old"]
    assert page.total_count == 3
    assert page.total_pages == 1


async def test_list_trades_paginates(conn: asyncpg.Connection) -> None:
    trades = [_make_trade(perm_id=f"t-{i:03d}", minutes_offset=i) for i in range(45)]
    await insert_trades(conn, trades)

    page1 = await list_trades(conn, page=1, per_page=30)
    assert len(page1.trades) == 30
    assert page1.total_count == 45
    assert page1.total_pages == 2
    assert page1.has_prev is False
    assert page1.has_next is True

    page2 = await list_trades(conn, page=2, per_page=30)
    assert len(page2.trades) == 15
    assert page2.has_next is False
    assert page2.has_prev is True


async def test_list_trades_default_per_page_is_30(conn: asyncpg.Connection) -> None:
    assert DEFAULT_PAGE_SIZE == 30


async def test_list_trades_clamps_invalid_page_to_1(conn: asyncpg.Connection) -> None:
    await insert_trades(conn, [_make_trade(perm_id="t-1")])

    # Negative page numbers should not blow up.
    page = await list_trades(conn, page=-5)
    assert page.page == 1
    assert len(page.trades) == 1


# ---------------------------------------------------------------------------
# Untagged counter (FR11)
# ---------------------------------------------------------------------------


async def test_untagged_counter_only_counts_closed_ib_trades_without_trigger(
    conn: asyncpg.Connection,
) -> None:
    await insert_trades(
        conn,
        [
            # Closed IB trade, no trigger_spec → counts
            _make_trade(perm_id="closed-untagged", closed=True),
            # Open IB trade → does NOT count (still in flight)
            _make_trade(perm_id="open-untagged", closed=False),
            # Closed IB trade, has trigger_spec → does NOT count (already tagged)
            _make_trade(
                perm_id="closed-tagged",
                closed=True,
                trigger_spec={"trigger_type": "manual"},
            ),
            # Closed cTrader trade, no trigger_spec → does NOT count (bot trades skip the counter)
            _make_trade(
                perm_id="closed-ctrader",
                closed=True,
                broker=TradeSource.CTRADER,
            ),
        ],
    )

    page = await list_trades(conn, page=1)
    assert page.untagged_count == 1
    assert page.total_count == 4


# ---------------------------------------------------------------------------
# get_trade_detail
# ---------------------------------------------------------------------------


async def test_get_trade_detail_returns_row(conn: asyncpg.Connection) -> None:
    await insert_trades(conn, [_make_trade(perm_id="d-1", symbol="MSFT")])

    row = await conn.fetchrow("SELECT id FROM trades WHERE perm_id = 'd-1'")
    detail = await get_trade_detail(conn, row["id"])
    assert detail is not None
    assert detail["symbol"] == "MSFT"
    assert detail["perm_id"] == "d-1"


async def test_get_trade_detail_returns_none_for_missing_id(conn: asyncpg.Connection) -> None:
    assert await get_trade_detail(conn, 999_999) is None

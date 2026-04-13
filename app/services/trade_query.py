"""Trade-list query service (Story 2.3 + 2.4).

Pure async functions — no FastAPI coupling — so the same code paths
are reachable from routers, scheduled jobs, and tests. All SQL lives
here so the journal page never has raw SQL leaking into a Jinja
template.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from app.logging import get_logger

logger = get_logger(__name__)


# Journal page-size — Story 2.3 AC #4 (UX-DR46).
DEFAULT_PAGE_SIZE = 30


@dataclass(frozen=True)
class TradeListPage:
    """One page of trades + the metadata the template needs to paginate."""

    trades: list[dict[str, Any]]
    untagged_count: int
    total_count: int
    page: int
    per_page: int

    @property
    def total_pages(self) -> int:
        if self.per_page <= 0 or self.total_count <= 0:
            return 1
        return max(1, (self.total_count + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


_LIST_SQL = """
SELECT
    id,
    symbol,
    asset_class,
    side,
    quantity,
    entry_price,
    exit_price,
    opened_at,
    closed_at,
    pnl,
    fees,
    broker,
    perm_id,
    trigger_spec
  FROM trades
 ORDER BY opened_at DESC, id DESC
 LIMIT $1 OFFSET $2
"""

_COUNT_SQL = "SELECT COUNT(*) FROM trades"

# Untagged counter (Story 2.3 AC #3, FR11):
# - Only IB trades (cTrader bot trades carry trigger_spec by construction)
# - Only closed trades (open positions can't be tagged yet)
# - trigger_spec IS NULL
_UNTAGGED_COUNT_SQL = """
SELECT COUNT(*)
  FROM trades
 WHERE trigger_spec IS NULL
   AND broker = 'ib'
   AND closed_at IS NOT NULL
"""

_DETAIL_SQL = """
SELECT
    id,
    symbol,
    asset_class,
    side,
    quantity,
    entry_price,
    exit_price,
    opened_at,
    closed_at,
    pnl,
    fees,
    broker,
    perm_id,
    trigger_spec,
    created_at,
    updated_at
  FROM trades
 WHERE id = $1
"""


def _row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


async def list_trades(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> TradeListPage:
    """Paginated trade list, newest first.

    `page` is 1-indexed (matches the URL `?page=N` convention). Pages
    out of range are clamped to a valid range so a stale bookmark
    doesn't 500 the journal.
    """

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = DEFAULT_PAGE_SIZE

    offset = (page - 1) * per_page

    rows = await conn.fetch(_LIST_SQL, per_page, offset)
    trades = [dict(row) for row in rows]

    total_count = await conn.fetchval(_COUNT_SQL)
    untagged = await conn.fetchval(_UNTAGGED_COUNT_SQL)

    return TradeListPage(
        trades=trades,
        untagged_count=untagged or 0,
        total_count=total_count or 0,
        page=page,
        per_page=per_page,
    )


async def get_trade_detail(conn: asyncpg.Connection, trade_id: int) -> dict[str, Any] | None:
    """Fetch one trade by id, or None if it doesn't exist."""

    row = await conn.fetchrow(_DETAIL_SQL, trade_id)
    return _row_to_dict(row)

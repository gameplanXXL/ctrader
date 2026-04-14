"""Trade-list query service (Story 2.3 + 2.4 + 4.1).

Pure async functions — no FastAPI coupling — so the same code paths
are reachable from routers, scheduled jobs, and tests. All SQL lives
here so the journal page never has raw SQL leaking into a Jinja
template.

Story 4.1 extends `list_trades` with a `facets` dict argument that
is translated into a parameterized WHERE fragment by
`app.services.facets.build_where_clause`. The journal route parses
the query string and passes the dict unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


# Story 4.1: list / count SQL templates are now format-strings with a
# `{where_sql}` placeholder so the facet framework can splice its
# WHERE fragment in without rebuilding the statement by hand. The
# placeholder is guaranteed to be a SQL-safe fragment built from
# `facets.build_where_clause` — never raw user input.
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
    trigger_spec,
    agent_id,
    strategy_id
  FROM trades
 WHERE {where_sql}
 ORDER BY opened_at DESC, id DESC
 LIMIT ${limit_placeholder} OFFSET ${offset_placeholder}
"""

_COUNT_SQL = "SELECT COUNT(*) FROM trades WHERE {where_sql}"

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
    agent_id,
    strategy_id,
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
    facets: dict[str, list[str]] | None = None,
    trade_date: date | None = None,
) -> TradeListPage:
    """Paginated trade list, newest first.

    `page` is 1-indexed (matches the URL `?page=N` convention). Pages
    out of range are clamped to a valid range — both lower bound
    (`< 1`) AND upper bound (`> total_pages`) — so a stale bookmark
    always lands on a page that contains data.

    `facets` is the URL-query-param form (`{"asset_class": ["stock"]}`)
    and gets translated into a parameterized WHERE fragment by the
    facet framework (Story 4.1). `trade_date` is the click-on-a-day
    filter from the calendar view (Story 4.4); it matches any trade
    whose `opened_at::date` equals the given day.
    """

    # Lazy import — avoid a module-level import cycle with facets which
    # may want to call trade_query primitives later.
    from app.services.facets import build_where_clause

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = DEFAULT_PAGE_SIZE

    facets = facets or {}
    where_sql, params = build_where_clause(facets)

    # Append the calendar-day filter (Story 4.4) if present. We keep
    # it outside the facet framework because it's a single-value
    # filter that never renders as a chip.
    #
    # Code-review H6 / EC-4: force UTC on the `::date` cast. Without
    # `AT TIME ZONE 'UTC'`, Postgres uses its session TZ, which may
    # not match the calendar view's UTC bucketing in
    # `daily_pnl.get_daily_pnl`. A trade opened at 23:30 UTC from
    # Berlin (UTC+2) would end up in the "next day" Postgres-local
    # bucket and the calendar click would miss it.
    if trade_date is not None:
        idx = len(params) + 1
        day_fragment = (
            f"((opened_at AT TIME ZONE 'UTC')::date = ${idx}"
            f" OR (closed_at AT TIME ZONE 'UTC')::date = ${idx})"
        )
        where_sql = f"({where_sql}) AND {day_fragment}"
        params.append(trade_date)

    total_count = await conn.fetchval(_COUNT_SQL.format(where_sql=where_sql), *params) or 0

    # Clamp upper bound: `?page=9999` on a 3-page dataset → page 3.
    max_page = max(1, (total_count + per_page - 1) // per_page) if total_count > 0 else 1
    if page > max_page:
        page = max_page

    offset = (page - 1) * per_page
    limit_placeholder = len(params) + 1
    offset_placeholder = len(params) + 2

    list_sql = _LIST_SQL.format(
        where_sql=where_sql,
        limit_placeholder=limit_placeholder,
        offset_placeholder=offset_placeholder,
    )
    rows = await conn.fetch(list_sql, *params, per_page, offset)
    trades = [dict(row) for row in rows]

    # Untagged counter is a global metric (ignores facets) so Chef
    # always sees the total untagged backlog regardless of drill-in.
    untagged = await conn.fetchval(_UNTAGGED_COUNT_SQL)

    return TradeListPage(
        trades=trades,
        untagged_count=untagged or 0,
        total_count=total_count,
        page=page,
        per_page=per_page,
    )


async def get_trade_detail(conn: asyncpg.Connection, trade_id: int) -> dict[str, Any] | None:
    """Fetch one trade by id, or None if it doesn't exist."""

    row = await conn.fetchrow(_DETAIL_SQL, trade_id)
    return _row_to_dict(row)


# Story 3.1 AC #6 — after a successful tag, jump to the oldest still-
# untagged trade. Filter mirrors the untagged-counter from list_trades:
# only IB closed trades are taggable today (bot trades carry a
# trigger_spec by construction).
_NEXT_UNTAGGED_SQL = """
SELECT id, symbol, asset_class, side, opened_at, closed_at
  FROM trades
 WHERE trigger_spec IS NULL
   AND broker = 'ib'
   AND closed_at IS NOT NULL
 ORDER BY opened_at ASC, id ASC
 LIMIT 1
"""


async def next_untagged_trade(conn: asyncpg.Connection) -> dict[str, Any] | None:
    """Return the oldest untagged IB trade, or None if the queue is empty.

    Story 3.1 AC #6 (Post-hoc Journey, UX-DR34): after a successful tag,
    the form jumps to the next untagged trade so Chef can stay in a
    focused tagging flow without navigating back to the journal.
    """

    row = await conn.fetchrow(_NEXT_UNTAGGED_SQL)
    return _row_to_dict(row)

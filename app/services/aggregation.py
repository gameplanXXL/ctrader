"""Aggregation service for the Journal Hero block (Story 4.2 / FR13).

Computes Trade Count, Expectancy (avg P&L), Winrate, and max-P&L-
Drawdown for any facet-filtered subset of trades. Also produces the
sparkline data series (cumulative P&L over time).

Drawdown is computed in Python instead of SQL because:
- datasets are bounded (<2k trades today)
- SQL window functions for rolling max + running min are fiddly with
  the facet framework's parameterized WHERE
- the same function produces both the drawdown number AND the
  sparkline points, avoiding two round-trips.

Expectancy in Phase 1 is dollar-per-trade (avg pnl). R-multiple
expectancy arrives once Epic 11 adds persisted `stop_price` columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg

from app.logging import get_logger
from app.services.facets import build_where_clause
from app.services.pnl import compute_pnl

logger = get_logger(__name__)


@dataclass(frozen=True)
class AggregationResult:
    """One Hero-block snapshot."""

    trade_count: int
    closed_count: int
    wins: int
    total_pnl: Decimal
    expectancy: Decimal  # Avg P&L per closed trade (Phase 1 uses $, not R).
    max_drawdown: Decimal
    winrate_pct: float
    sparkline_points: list[float]  # cumulative P&L series

    @property
    def has_data(self) -> bool:
        return self.closed_count > 0

    @property
    def total_pnl_float(self) -> float:
        return float(self.total_pnl)

    @property
    def expectancy_float(self) -> float:
        return float(self.expectancy)

    @property
    def drawdown_float(self) -> float:
        return float(self.max_drawdown)


_SQL = """
SELECT id, symbol, asset_class, side, quantity, entry_price, exit_price,
       opened_at, closed_at, pnl, fees
  FROM trades
 WHERE {where_sql}
 ORDER BY opened_at ASC, id ASC
"""


def _ensure_pnl(row: dict[str, Any]) -> Decimal | None:
    """Return the persisted P&L or compute it on the fly.

    `trades.pnl` is NULL for anything imported before live-sync persists
    it (code-review deferred D24). For aggregation we need a value, so
    we fall back to the same `compute_pnl` the drilldown uses.
    """

    stored = row.get("pnl")
    if stored is not None:
        return Decimal(str(stored))
    return compute_pnl(row)


async def compute_aggregation(
    conn: asyncpg.Connection,
    facets: dict[str, list[str]] | None = None,
) -> AggregationResult:
    """Compute Hero-block metrics for a facet-filtered trade set."""

    facets = facets or {}
    where_sql, params = build_where_clause(facets)
    sql = _SQL.format(where_sql=where_sql)

    rows = await conn.fetch(sql, *params)

    trade_count = len(rows)
    closed_count = 0
    wins = 0
    total_pnl = Decimal("0")
    cum_pnl = Decimal("0")
    running_max = Decimal("0")
    max_drawdown = Decimal("0")
    sparkline: list[float] = []

    for row in rows:
        pnl = _ensure_pnl(dict(row))
        if pnl is None:
            # Skip open positions for money-side metrics but still
            # include them in trade_count (above).
            continue
        closed_count += 1
        total_pnl += pnl
        cum_pnl += pnl
        sparkline.append(float(cum_pnl))
        if pnl > 0:
            wins += 1
        # Drawdown: peak-to-trough of the cumulative series.
        if cum_pnl > running_max:
            running_max = cum_pnl
        drawdown = cum_pnl - running_max  # ≤ 0
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    expectancy = (total_pnl / closed_count) if closed_count > 0 else Decimal("0")
    winrate_pct = (100.0 * wins / closed_count) if closed_count > 0 else 0.0

    return AggregationResult(
        trade_count=trade_count,
        closed_count=closed_count,
        wins=wins,
        total_pnl=total_pnl,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        winrate_pct=winrate_pct,
        sparkline_points=sparkline,
    )

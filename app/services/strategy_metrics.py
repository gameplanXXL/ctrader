"""Strategy list + detail metrics (Story 6.2 / 6.3).

Computes per-strategy trade count, expectancy (avg P&L per trade),
cumulative-P&L drawdown, and followed-vs-override performance split.

Phase 1 expectancy is dollar-based (matches Epic 4). R-multiple
expectancy lands once Epic 11 persists stop_price.

All aggregations go through the same `_fetch_rows` helper so the
drawdown / sparkline math stays in Python rather than fighting
PostgreSQL window functions inside the facet-driven WHERE clause.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from app.services.pnl import compute_pnl


@dataclass(frozen=True)
class StrategyRow:
    """One row of the Story 6.2 strategy list."""

    id: int
    name: str
    horizon: str
    asset_class: str
    status: str
    trade_count: int
    trade_count_week: int
    closed_count: int
    total_pnl: Decimal
    expectancy: Decimal
    max_drawdown: Decimal
    winrate_pct: float
    risk_budget_per_trade: Decimal

    @property
    def total_pnl_float(self) -> float:
        return float(self.total_pnl)

    @property
    def expectancy_float(self) -> float:
        return float(self.expectancy)

    @property
    def drawdown_float(self) -> float:
        return float(self.max_drawdown)


@dataclass(frozen=True)
class FollowedBreakdown:
    """Followed-vs-override performance split for Story 6.3 AC #3."""

    followed_count: int
    followed_total_pnl: Decimal
    followed_expectancy: Decimal
    override_count: int
    override_total_pnl: Decimal
    override_expectancy: Decimal


@dataclass(frozen=True)
class StrategyDetail:
    """Full strategy detail — the right pane of the two-pane view."""

    row: StrategyRow
    trades: list[dict[str, Any]]
    sparkline_points: list[float]
    followed_breakdown: FollowedBreakdown


_STRATEGIES_SQL = """
SELECT id, name, asset_class, horizon::text, status::text, risk_budget_per_trade
  FROM strategies
 ORDER BY
     CASE status::text
         WHEN 'active'  THEN 0
         WHEN 'paused'  THEN 1
         WHEN 'retired' THEN 2
         ELSE 3
     END,
     name ASC
"""

_TRADES_SQL = """
SELECT id, strategy_id, symbol, side, quantity, entry_price, exit_price,
       opened_at, closed_at, pnl, fees, trigger_spec
  FROM trades
 WHERE strategy_id IS NOT NULL
 ORDER BY opened_at ASC, id ASC
"""

_TRADES_BY_STRATEGY_SQL = """
SELECT id, strategy_id, symbol, side, quantity, entry_price, exit_price,
       opened_at, closed_at, pnl, fees, trigger_spec
  FROM trades
 WHERE strategy_id = $1
 ORDER BY opened_at ASC, id ASC
"""


def _ensure_pnl(row: dict[str, Any]) -> Decimal | None:
    stored = row.get("pnl")
    if stored is not None:
        return Decimal(str(stored))
    return compute_pnl(row)


def _aggregate_one(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Walk a sorted-by-opened_at trade list, produce the aggregate shape."""

    total_pnl = Decimal("0")
    closed_count = 0
    wins = 0
    cum_pnl = Decimal("0")
    running_max: Decimal | None = None
    max_drawdown = Decimal("0")
    sparkline: list[float] = []

    for row in rows:
        pnl = _ensure_pnl(dict(row))
        if pnl is None:
            continue
        closed_count += 1
        total_pnl += pnl
        cum_pnl += pnl
        sparkline.append(float(cum_pnl))
        if pnl > 0:
            wins += 1
        if running_max is None or cum_pnl > running_max:
            running_max = cum_pnl
        drawdown = cum_pnl - running_max
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    expectancy = (total_pnl / closed_count) if closed_count > 0 else Decimal("0")
    winrate_pct = (100.0 * wins / closed_count) if closed_count > 0 else 0.0
    return {
        "total_pnl": total_pnl,
        "expectancy": expectancy,
        "max_drawdown": max_drawdown,
        "winrate_pct": winrate_pct,
        "sparkline_points": sparkline,
        "closed_count": closed_count,
    }


async def list_strategies_with_metrics(
    conn: asyncpg.Connection,
    *,
    now: datetime | None = None,
) -> list[StrategyRow]:
    """Return every strategy with its aggregate metrics for Story 6.2.

    One SELECT for strategies, one SELECT for all strategy-linked
    trades. Python does the grouping + drawdown math — simpler than
    fighting PG window functions and fast enough for the expected
    2k-trade working set.
    """

    reference = now or datetime.now(UTC)
    week_ago = reference - timedelta(days=7)

    strategy_rows = await conn.fetch(_STRATEGIES_SQL)
    trade_rows = await conn.fetch(_TRADES_SQL)

    by_strategy: dict[int, list[dict[str, Any]]] = {}
    for row in trade_rows:
        by_strategy.setdefault(int(row["strategy_id"]), []).append(dict(row))

    out: list[StrategyRow] = []
    for strategy in strategy_rows:
        sid = int(strategy["id"])
        trades = by_strategy.get(sid, [])
        agg = _aggregate_one(trades)
        count_week = sum(1 for t in trades if t.get("opened_at") and t["opened_at"] >= week_ago)
        out.append(
            StrategyRow(
                id=sid,
                name=str(strategy["name"]),
                horizon=str(strategy["horizon"]),
                asset_class=str(strategy["asset_class"]),
                status=str(strategy["status"]),
                trade_count=len(trades),
                trade_count_week=count_week,
                closed_count=agg["closed_count"],
                total_pnl=agg["total_pnl"],
                expectancy=agg["expectancy"],
                max_drawdown=agg["max_drawdown"],
                winrate_pct=agg["winrate_pct"],
                risk_budget_per_trade=Decimal(str(strategy["risk_budget_per_trade"])),
            )
        )
    return out


def _followed_breakdown(rows: list[dict[str, Any]]) -> FollowedBreakdown:
    followed_total = Decimal("0")
    followed_count = 0
    override_total = Decimal("0")
    override_count = 0

    for row in rows:
        pnl = _ensure_pnl(dict(row))
        if pnl is None:
            continue
        spec = row.get("trigger_spec") or {}
        if not isinstance(spec, dict):
            continue
        flag = spec.get("followed")
        if flag is True:
            followed_total += pnl
            followed_count += 1
        elif flag is False:
            override_total += pnl
            override_count += 1

    followed_exp = (followed_total / followed_count) if followed_count > 0 else Decimal("0")
    override_exp = (override_total / override_count) if override_count > 0 else Decimal("0")
    return FollowedBreakdown(
        followed_count=followed_count,
        followed_total_pnl=followed_total,
        followed_expectancy=followed_exp,
        override_count=override_count,
        override_total_pnl=override_total,
        override_expectancy=override_exp,
    )


async def get_strategy_detail(conn: asyncpg.Connection, strategy_id: int) -> StrategyDetail | None:
    """Return the full detail payload for the Story 6.3 right pane."""

    strategy = await conn.fetchrow(
        """
        SELECT id, name, asset_class, horizon::text, status::text,
               risk_budget_per_trade
          FROM strategies
         WHERE id = $1
        """,
        strategy_id,
    )
    if strategy is None:
        return None

    trade_rows = [dict(r) for r in await conn.fetch(_TRADES_BY_STRATEGY_SQL, strategy_id)]
    agg = _aggregate_one(trade_rows)
    week_ago = datetime.now(UTC) - timedelta(days=7)
    count_week = sum(1 for t in trade_rows if t.get("opened_at") and t["opened_at"] >= week_ago)
    row = StrategyRow(
        id=strategy_id,
        name=str(strategy["name"]),
        horizon=str(strategy["horizon"]),
        asset_class=str(strategy["asset_class"]),
        status=str(strategy["status"]),
        trade_count=len(trade_rows),
        trade_count_week=count_week,
        closed_count=agg["closed_count"],
        total_pnl=agg["total_pnl"],
        expectancy=agg["expectancy"],
        max_drawdown=agg["max_drawdown"],
        winrate_pct=agg["winrate_pct"],
        risk_budget_per_trade=Decimal(str(strategy["risk_budget_per_trade"])),
    )
    breakdown = _followed_breakdown(trade_rows)
    return StrategyDetail(
        row=row,
        trades=trade_rows,
        sparkline_points=agg["sparkline_points"],
        followed_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Story 6.3 AC #4 — horizon aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HorizonAggregate:
    horizon: str
    trade_count: int
    closed_count: int
    total_pnl: Decimal
    expectancy: Decimal
    max_drawdown: Decimal

    @property
    def total_pnl_float(self) -> float:
        return float(self.total_pnl)

    @property
    def expectancy_float(self) -> float:
        return float(self.expectancy)

    @property
    def drawdown_float(self) -> float:
        return float(self.max_drawdown)


# Code-review M5 / BH-17 / EC-13: LEFT JOIN so a horizon with
# strategies but no trades still surfaces as a "0 trades" row in the
# header table. Trade-side columns are NULL for such horizons; we
# drop those synthetic rows before passing to `_aggregate_one`.
_HORIZON_JOIN_SQL = """
SELECT s.horizon::text AS horizon, t.id, t.strategy_id, t.opened_at, t.closed_at,
       t.side, t.quantity, t.entry_price, t.exit_price, t.pnl, t.fees
  FROM strategies s
  LEFT JOIN trades t ON t.strategy_id = s.id
 ORDER BY s.horizon, t.opened_at ASC NULLS LAST, t.id ASC NULLS LAST
"""


async def horizon_aggregates(
    conn: asyncpg.Connection,
) -> list[HorizonAggregate]:
    """Story 6.3 AC #4 / FR40: aggregate per horizon across all strategies.

    Code-review M5: LEFT JOIN so horizons with zero trades still
    appear (as "0 trades / $0.00 / 0% / 0$").
    """

    rows = await conn.fetch(_HORIZON_JOIN_SQL)
    by_horizon: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        horizon = str(row["horizon"])
        bucket = by_horizon.setdefault(horizon, [])
        # Skip the synthetic LEFT JOIN row with NULL trade columns.
        if row["id"] is not None:
            bucket.append(dict(row))

    out: list[HorizonAggregate] = []
    for horizon, horizon_rows in by_horizon.items():
        agg = _aggregate_one(horizon_rows)
        out.append(
            HorizonAggregate(
                horizon=horizon,
                trade_count=len(horizon_rows),
                closed_count=agg["closed_count"],
                total_pnl=agg["total_pnl"],
                expectancy=agg["expectancy"],
                max_drawdown=agg["max_drawdown"],
            )
        )
    out.sort(key=lambda h: h.horizon)
    return out

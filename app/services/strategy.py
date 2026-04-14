"""Strategy CRUD service (Epic 6 / FR33 / FR38 / FR39).

All SQL for the strategies table lives here so the routers stay
presentation-focused. Story 6.5's `is_strategy_active()` is the
gate-keeper the Epic 7 proposal generator will call before any new
proposal lands.
"""

from __future__ import annotations

from decimal import Decimal

import asyncpg

from app.logging import get_logger
from app.models.strategy import (
    Strategy,
    StrategyCreate,
    StrategyNote,
    StrategyStatus,
    StrategyStatusTransition,
    can_transition,
    next_toggle_status,
)

logger = get_logger(__name__)


class StrategyNotFoundError(LookupError):
    """Raised when a strategy id does not resolve to a row."""


class StrategyTransitionError(ValueError):
    """Raised when a requested status transition is not in the lifecycle FSM."""


_INSERT_SQL = """
INSERT INTO strategies (
    name, asset_class, horizon, typical_holding_period,
    trigger_sources, risk_budget_per_trade, status
)
VALUES ($1, $2, $3::horizon_type, $4, $5, $6, $7::strategy_status)
RETURNING id, name, asset_class, horizon::text, typical_holding_period,
          trigger_sources, risk_budget_per_trade, status::text,
          created_at, updated_at
"""

_GET_SQL = """
SELECT id, name, asset_class, horizon::text, typical_holding_period,
       trigger_sources, risk_budget_per_trade, status::text,
       created_at, updated_at
  FROM strategies
 WHERE id = $1
"""

_LIST_SQL = """
SELECT id, name, asset_class, horizon::text, typical_holding_period,
       trigger_sources, risk_budget_per_trade, status::text,
       created_at, updated_at
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

_STATUS_SQL = "SELECT status::text FROM strategies WHERE id = $1"

_UPDATE_STATUS_SQL = """
UPDATE strategies
   SET status     = $1::strategy_status,
       updated_at = NOW()
 WHERE id = $2
RETURNING status::text
"""


def _row_to_strategy(row: asyncpg.Record) -> Strategy:
    trigger_sources_raw = row["trigger_sources"]
    if isinstance(trigger_sources_raw, str):
        import json

        try:
            trigger_sources_raw = json.loads(trigger_sources_raw)
        except ValueError:
            trigger_sources_raw = []
    if not isinstance(trigger_sources_raw, list):
        trigger_sources_raw = []

    return Strategy(
        id=int(row["id"]),
        name=str(row["name"]),
        asset_class=str(row["asset_class"]),
        horizon=row["horizon"],
        typical_holding_period=row["typical_holding_period"],
        trigger_sources=[str(x) for x in trigger_sources_raw],
        risk_budget_per_trade=Decimal(str(row["risk_budget_per_trade"])),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_strategy(conn: asyncpg.Connection, payload: StrategyCreate) -> Strategy:
    """Insert a new strategy and return the persisted row."""

    row = await conn.fetchrow(
        _INSERT_SQL,
        payload.name,
        payload.asset_class,
        payload.horizon.value,
        payload.typical_holding_period,
        list(payload.trigger_sources),
        payload.risk_budget_per_trade,
        payload.status.value,
    )
    strategy = _row_to_strategy(row)
    logger.info(
        "strategy.created",
        strategy_id=strategy.id,
        name=strategy.name,
        horizon=strategy.horizon.value,
        status=strategy.status.value,
    )
    return strategy


async def get_strategy(conn: asyncpg.Connection, strategy_id: int) -> Strategy | None:
    row = await conn.fetchrow(_GET_SQL, strategy_id)
    return _row_to_strategy(row) if row is not None else None


async def list_strategies(conn: asyncpg.Connection) -> list[Strategy]:
    rows = await conn.fetch(_LIST_SQL)
    return [_row_to_strategy(row) for row in rows]


async def update_status(
    conn: asyncpg.Connection,
    strategy_id: int,
    new_status: StrategyStatus,
) -> StrategyStatusTransition:
    """Lifecycle-aware status update.

    Story 6.1 AC #4 / FR38 transitions:
    - active → paused / retired
    - paused → active / retired
    - retired → (terminal)
    """

    current_raw = await conn.fetchval(_STATUS_SQL, strategy_id)
    if current_raw is None:
        raise StrategyNotFoundError(f"strategy {strategy_id} does not exist")
    current = StrategyStatus(current_raw)
    if current == new_status:
        return StrategyStatusTransition(id=strategy_id, old_status=current, new_status=new_status)
    if not can_transition(current, new_status):
        raise StrategyTransitionError(f"cannot transition {current.value} → {new_status.value}")
    await conn.execute(_UPDATE_STATUS_SQL, new_status.value, strategy_id)
    logger.info(
        "strategy.status_updated",
        strategy_id=strategy_id,
        old_status=current.value,
        new_status=new_status.value,
    )
    return StrategyStatusTransition(id=strategy_id, old_status=current, new_status=new_status)


async def toggle_status(conn: asyncpg.Connection, strategy_id: int) -> StrategyStatusTransition:
    """One-click status toggle (active ↔ paused, retired stays)."""

    current_raw = await conn.fetchval(_STATUS_SQL, strategy_id)
    if current_raw is None:
        raise StrategyNotFoundError(f"strategy {strategy_id} does not exist")
    current = StrategyStatus(current_raw)
    target = next_toggle_status(current)
    if target == current:
        return StrategyStatusTransition(id=strategy_id, old_status=current, new_status=current)
    return await update_status(conn, strategy_id, target)


# Story 6.5 / FR39: hard invariant — paused / retired strategies must
# NOT generate new proposals. Epic 7's proposal generator calls this
# as the gate-keeper.
async def is_strategy_active(conn: asyncpg.Connection, strategy_id: int) -> bool:
    """Return True iff the strategy exists AND its status is 'active'."""

    status_raw = await conn.fetchval(_STATUS_SQL, strategy_id)
    if status_raw is None:
        return False
    return status_raw == StrategyStatus.ACTIVE.value


# ---------------------------------------------------------------------------
# Strategy notes (Story 6.4)
# ---------------------------------------------------------------------------


_NOTE_INSERT_SQL = """
INSERT INTO strategy_notes (strategy_id, content)
VALUES ($1, $2)
RETURNING id, strategy_id, content, created_at
"""

_NOTE_LIST_SQL = """
SELECT id, strategy_id, content, created_at
  FROM strategy_notes
 WHERE strategy_id = $1
 ORDER BY created_at DESC, id DESC
"""


async def add_note(conn: asyncpg.Connection, strategy_id: int, content: str) -> StrategyNote:
    """Append a note to the strategy's history. Append-only."""

    cleaned = content.strip()
    if not cleaned:
        raise ValueError("note content must not be empty")
    row = await conn.fetchrow(_NOTE_INSERT_SQL, strategy_id, cleaned)
    return StrategyNote(
        id=int(row["id"]),
        strategy_id=int(row["strategy_id"]),
        content=str(row["content"]),
        created_at=row["created_at"],
    )


async def list_notes(conn: asyncpg.Connection, strategy_id: int) -> list[StrategyNote]:
    rows = await conn.fetch(_NOTE_LIST_SQL, strategy_id)
    return [
        StrategyNote(
            id=int(row["id"]),
            strategy_id=int(row["strategy_id"]),
            content=str(row["content"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]

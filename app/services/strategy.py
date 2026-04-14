"""Strategy CRUD service (Epic 6 / FR33 / FR38 / FR39).

All SQL for the strategies table lives here so the routers stay
presentation-focused. Story 6.5's `is_strategy_active()` is the
gate-keeper the Epic 7 proposal generator will call before any new
proposal lands.
"""

from __future__ import annotations

import json
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
       source_snapshot_id,
       created_at, updated_at
  FROM strategies
 WHERE id = $1
"""

_LIST_SQL = """
SELECT id, name, asset_class, horizon::text, typical_holding_period,
       trigger_sources, risk_budget_per_trade, status::text,
       source_snapshot_id,
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

# Code-review H2 / BH-1 / EC-26-27: atomic compare-and-swap UPDATE so
# two concurrent toggle clicks can't race past each other and a
# terminal `retired` can't be silently revived. The `AND status = $3`
# guard means the UPDATE affects 0 rows (RETURNING NULL) if another
# request has already flipped the status — we raise
# `StrategyTransitionError` so the caller can 409 and the UI shows the
# actual current state.
_UPDATE_STATUS_CAS_SQL = """
UPDATE strategies
   SET status     = $1::strategy_status,
       updated_at = NOW()
 WHERE id = $2
   AND status    = $3::strategy_status
RETURNING status::text
"""


def _row_to_strategy(row: asyncpg.Record) -> Strategy:
    trigger_sources_raw = row["trigger_sources"]
    if isinstance(trigger_sources_raw, str):
        try:
            trigger_sources_raw = json.loads(trigger_sources_raw)
        except ValueError:
            logger.warning(
                "strategy.malformed_trigger_sources",
                strategy_id=row["id"],
                value=trigger_sources_raw,
            )
            trigger_sources_raw = []
    if not isinstance(trigger_sources_raw, list):
        trigger_sources_raw = []

    # `source_snapshot_id` is only in _GET_SQL / _LIST_SQL (added by
    # code-review M5 / EC-19). `_INSERT_SQL` RETURNING doesn't include
    # it — fall back to None when absent so create_strategy still
    # hydrates cleanly.
    try:
        source_snapshot_id = row["source_snapshot_id"]
    except (KeyError, IndexError):
        source_snapshot_id = None

    return Strategy(
        id=int(row["id"]),
        name=str(row["name"]),
        asset_class=str(row["asset_class"]),
        horizon=row["horizon"],
        typical_holding_period=row["typical_holding_period"],
        trigger_sources=[str(x) for x in trigger_sources_raw],
        risk_budget_per_trade=Decimal(str(row["risk_budget_per_trade"])),
        status=row["status"],
        source_snapshot_id=source_snapshot_id,
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
    """Lifecycle-aware status update via atomic compare-and-swap.

    Story 6.1 AC #4 / FR38 transitions:
    - active → paused / retired
    - paused → active / retired
    - retired → (terminal)

    Code-review H2: uses a single `UPDATE ... WHERE id = $2 AND status
    = $3 RETURNING` statement so two concurrent clicks can't
    interleave. The FSM gate still runs in Python (fewer round-trips,
    clearer error messages), but the final write is conditional on
    the stored status matching the caller's read — if it doesn't, the
    UPDATE returns no rows and we raise `StrategyTransitionError`
    with the actual current state.
    """

    if not isinstance(new_status, StrategyStatus):
        raise TypeError(f"new_status must be StrategyStatus, got {type(new_status).__name__}")

    current_raw = await conn.fetchval(_STATUS_SQL, strategy_id)
    if current_raw is None:
        raise StrategyNotFoundError(f"strategy {strategy_id} does not exist")
    current = StrategyStatus(current_raw)
    if current == new_status:
        return StrategyStatusTransition(id=strategy_id, old_status=current, new_status=new_status)
    if not can_transition(current, new_status):
        raise StrategyTransitionError(f"cannot transition {current.value} → {new_status.value}")

    updated_raw = await conn.fetchval(
        _UPDATE_STATUS_CAS_SQL, new_status.value, strategy_id, current.value
    )
    if updated_raw is None:
        # Compare-and-swap lost — another request flipped the status
        # between our read and our write. Re-read to report the truth.
        actual_raw = await conn.fetchval(_STATUS_SQL, strategy_id)
        actual = StrategyStatus(actual_raw) if actual_raw else current
        raise StrategyTransitionError(
            f"cannot transition {current.value} → {new_status.value}: "
            f"status was concurrently changed to {actual.value}"
        )
    logger.info(
        "strategy.status_updated",
        strategy_id=strategy_id,
        old_status=current.value,
        new_status=new_status.value,
    )
    return StrategyStatusTransition(id=strategy_id, old_status=current, new_status=new_status)


async def toggle_status(conn: asyncpg.Connection, strategy_id: int) -> StrategyStatusTransition:
    """One-click status toggle (active ↔ paused, retired stays).

    Retired is terminal — a click on a retired strategy is a no-op
    that returns same-state. Callers should suppress the success
    toast in that case (code-review M7 / EC-6).
    """

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


# Code-review H1 / EC-1: when the tagging form posts a `strategy`
# value, we have to resolve it back to a `strategies.id` so the
# trade row's FK column can be populated. Without this, the strategy
# list aggregation (`strategy_metrics.list_strategies_with_metrics`)
# stays empty even though Chef tagged 50 trades.
#
# The dropdown source adapter (`app/services/strategy_source.py`)
# emits either:
#   - taxonomy entries (`mean_reversion`, …) when the strategies table
#     is empty (pre-Epic-6 fallback) — no DB row exists, returns None
#   - real strategy rows as `(id::text, name)` once Epic 6 lands —
#     resolves to int(id)
#
# We probe BOTH the integer-id path AND the name-match path so a
# tagging POST can carry either a numeric id or a human-readable name.
_RESOLVE_BY_NAME_SQL = "SELECT id FROM strategies WHERE name = $1 LIMIT 1"


async def resolve_strategy_id(conn: asyncpg.Connection, value: str | int | None) -> int | None:
    """Best-effort `value → strategies.id` resolver.

    - `None` / empty → None
    - integer → return as-is if a row exists
    - string of digits → integer path
    - other string → look up by `name`
    - no match → None (caller can leave the FK NULL)
    """

    if value is None or value == "":
        return None
    if isinstance(value, int):
        exists = await conn.fetchval("SELECT 1 FROM strategies WHERE id = $1", value)
        return value if exists else None

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        candidate = int(text)
        exists = await conn.fetchval("SELECT 1 FROM strategies WHERE id = $1", candidate)
        if exists:
            return candidate
    # Fall back to name lookup so a taxonomy id like "mean_reversion"
    # also works once Chef has created a same-named strategy.
    return await conn.fetchval(_RESOLVE_BY_NAME_SQL, text)


_LINK_TRADE_SQL = """
UPDATE trades
   SET strategy_id = $1,
       updated_at  = NOW()
 WHERE id = $2
"""


async def link_trade_to_strategy(
    conn: asyncpg.Connection, trade_id: int, strategy_id: int | None
) -> None:
    """Set `trades.strategy_id` for one trade. None unlinks."""

    await conn.execute(_LINK_TRADE_SQL, strategy_id, trade_id)


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


NOTE_MAX_LENGTH = 2000


async def add_note(conn: asyncpg.Connection, strategy_id: int, content: str) -> StrategyNote:
    """Append a note to the strategy's history. Append-only.

    Code-review M3 / M4 / BH-13 / EC-25: enforce both empty AND
    over-length checks server-side. The HTML form has `maxlength`
    but a scripted POST bypasses it, and the DB CHECK only catches
    `length(content) > 0`, not whitespace-only or oversized payloads.
    """

    cleaned = content.strip()
    if not cleaned:
        raise ValueError("note content must not be empty")
    if len(cleaned) > NOTE_MAX_LENGTH:
        raise ValueError(f"note content exceeds {NOTE_MAX_LENGTH} characters")
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

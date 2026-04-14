"""Horizon-bewusster Kill-Switch (Epic 9 / Story 9.2).

Owns:
- `evaluate_kill_switch(conn, fear_greed_index)` — the automated
  pause/recover decision, run after every regime snapshot.
- `manual_override(conn, strategy_id)` — Chef's override endpoint
  re-activates a strategy that the kill switch paused (Story 9.3 AC #1),
  leaving manually-paused strategies untouched.

Invariants
----------
1. Only strategies with `horizon IN ('intraday', 'swing_short')` are
   auto-paused by the kill switch. Long-horizon strategies
   (`swing_long`, `position`) ride through volatility (FR43).
2. Auto-pauses carry `paused_by = 'kill_switch'`. The recovery sweep
   only un-pauses its own rows, so a manually-paused strategy
   (`paused_by = 'manual'`) stays paused even when the F&G recovers.
3. Every state transition writes an `audit_log` row with the proper
   event_type (`kill_switch_triggered` for auto-pauses/auto-recovers,
   `kill_switch_overridden` for manual overrides) so the Story-9.3
   regime page can render an override history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from app.logging import get_logger
from app.models.regime import KILL_SWITCH_THRESHOLD

logger = get_logger(__name__)


# Short-horizon strategies are the ones that get auto-paused.
_SHORT_HORIZONS: tuple[str, ...] = ("intraday", "swing_short")


@dataclass(frozen=True)
class KillSwitchResult:
    """Summary of one kill-switch evaluation, returned for logging/tests."""

    fear_greed_index: int | None
    action: str  # 'pause', 'recover', 'noop'
    paused_ids: list[int]
    recovered_ids: list[int]


_PAUSE_SQL = """
UPDATE strategies
   SET status = 'paused'::strategy_status,
       paused_by = 'kill_switch',
       updated_at = NOW()
 WHERE status = 'active'::strategy_status
   AND horizon = ANY($1::horizon_type[])
 RETURNING id, name
"""


_RECOVER_SQL = """
UPDATE strategies
   SET status = 'active'::strategy_status,
       paused_by = NULL,
       updated_at = NOW()
 WHERE status = 'paused'::strategy_status
   AND paused_by = 'kill_switch'
 RETURNING id, name
"""


_OVERRIDE_SQL = """
UPDATE strategies
   SET status = 'active'::strategy_status,
       paused_by = NULL,
       updated_at = NOW()
 WHERE id = $1
   AND status = 'paused'::strategy_status
   AND paused_by = 'kill_switch'
 RETURNING id, name
"""


_INSERT_AUDIT_SQL = """
INSERT INTO audit_log (
    event_type,
    strategy_id,
    override_flags,
    actor,
    notes
) VALUES ($1, $2, $3::jsonb, $4, $5)
"""


async def _log_state_change(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    strategy_id: int,
    fear_greed_index: int | None,
    action: str,
    actor: str,
    notes: str,
) -> None:
    """Write one `audit_log` row describing a kill-switch state change.

    Migration 009's CHECK constraint pins the event_type vocabulary.
    We use `kill_switch_triggered` for automated pauses + recoveries
    and `kill_switch_overridden` for manual overrides.
    """

    override_flags: dict[str, Any] = {
        "fear_greed_index": fear_greed_index,
        "action": action,
        "automated": actor == "kill_switch",
    }
    await conn.execute(
        _INSERT_AUDIT_SQL,
        event_type,
        strategy_id,
        override_flags,
        actor,
        notes,
    )


async def evaluate_kill_switch(
    conn: asyncpg.Connection,
    fear_greed_index: int | None,
) -> KillSwitchResult:
    """Apply the crash-regime rule to the strategies table.

    - `fear_greed_index < 20` → pause all active short-horizon
      strategies (FR42).
    - `fear_greed_index >= 20` → recover all strategies previously
      auto-paused by the kill switch (FR42 re-evaluation clause).
    - `None` (data source down) → **noop**. We never pause or unpause
      based on missing data; the next snapshot with a real value will
      re-apply the rule.

    Every state transition writes an audit_log row so the Story-9.3
    override history can render a timeline.
    """

    if fear_greed_index is None:
        logger.warning("kill_switch.skip_no_index")
        return KillSwitchResult(
            fear_greed_index=None, action="noop", paused_ids=[], recovered_ids=[]
        )

    if fear_greed_index < KILL_SWITCH_THRESHOLD:
        rows = await conn.fetch(_PAUSE_SQL, list(_SHORT_HORIZONS))
        paused_ids = [row["id"] for row in rows]
        for row in rows:
            await _log_state_change(
                conn,
                event_type="kill_switch_triggered",
                strategy_id=row["id"],
                fear_greed_index=fear_greed_index,
                action="pause",
                actor="kill_switch",
                notes=(
                    f"Auto-pause: Fear & Greed = {fear_greed_index} (< {KILL_SWITCH_THRESHOLD})"
                ),
            )
        logger.info(
            "kill_switch.paused",
            fear_greed_index=fear_greed_index,
            count=len(paused_ids),
            strategy_ids=paused_ids,
        )
        return KillSwitchResult(
            fear_greed_index=fear_greed_index,
            action="pause",
            paused_ids=paused_ids,
            recovered_ids=[],
        )

    rows = await conn.fetch(_RECOVER_SQL)
    recovered_ids = [row["id"] for row in rows]
    for row in rows:
        await _log_state_change(
            conn,
            event_type="kill_switch_triggered",
            strategy_id=row["id"],
            fear_greed_index=fear_greed_index,
            action="recover",
            actor="kill_switch",
            notes=(f"Auto-recover: Fear & Greed = {fear_greed_index} (>= {KILL_SWITCH_THRESHOLD})"),
        )
    if recovered_ids:
        logger.info(
            "kill_switch.recovered",
            fear_greed_index=fear_greed_index,
            count=len(recovered_ids),
            strategy_ids=recovered_ids,
        )
    return KillSwitchResult(
        fear_greed_index=fear_greed_index,
        action="recover" if recovered_ids else "noop",
        paused_ids=[],
        recovered_ids=recovered_ids,
    )


class StrategyNotPausedByKillSwitchError(ValueError):
    """Raised when `manual_override` is called on a strategy that the
    kill switch did NOT pause (either it's active, or it was paused
    manually by Chef — in both cases the override would be a no-op
    that confuses the audit trail).
    """


async def manual_override(
    conn: asyncpg.Connection,
    strategy_id: int,
    *,
    actor: str = "chef",
    notes: str | None = None,
) -> dict[str, Any]:
    """Re-activate a strategy that the kill switch paused.

    Returns the {id, name} dict for template rendering. Raises
    `StrategyNotPausedByKillSwitchError` if the strategy is not
    currently paused by the kill switch (see docstring of that
    exception).

    Writes an `audit_log` row with `event_type='kill_switch_overridden'`
    so FR44's "manual override of kill-switch" trail is durable.
    """

    row = await conn.fetchrow(_OVERRIDE_SQL, strategy_id)
    if row is None:
        raise StrategyNotPausedByKillSwitchError(
            f"strategy {strategy_id} is not paused by the kill switch"
        )

    await _log_state_change(
        conn,
        event_type="kill_switch_overridden",
        strategy_id=strategy_id,
        fear_greed_index=None,
        action="manual_override",
        actor=actor,
        notes=notes or "Chef manually overrode the kill-switch pause",
    )
    logger.info(
        "kill_switch.manual_override",
        strategy_id=strategy_id,
        actor=actor,
    )
    return {"id": row["id"], "name": row["name"]}

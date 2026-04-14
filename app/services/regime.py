"""Regime-page aggregation (Epic 9 / Story 9.3).

Builds the `get_current_regime()` view-model consumed by
`GET /regime` + the Story-7.3 approval-viewport footer. One function,
one SELECT per list, no ORM — the page loads in a single request and
uses the data straight from the dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from app.models.regime import RegimeSnapshot, fear_greed_classification
from app.services.regime_snapshot import get_latest_regime


@dataclass(frozen=True)
class PausedStrategy:
    id: int
    name: str
    horizon: str
    asset_class: str
    updated_at: datetime


@dataclass(frozen=True)
class OverrideHistoryEntry:
    id: int
    created_at: datetime
    event_type: str  # 'kill_switch_triggered' | 'kill_switch_overridden'
    strategy_id: int | None
    strategy_name: str | None
    actor: str
    action: str  # 'pause' | 'recover' | 'manual_override'
    fear_greed_index: int | None
    notes: str | None


@dataclass(frozen=True)
class RegimeView:
    snapshot: RegimeSnapshot | None
    paused_strategies: list[PausedStrategy]
    override_history: list[OverrideHistoryEntry] = field(default_factory=list)

    @property
    def fg_classification(self) -> str:
        return (
            fear_greed_classification(self.snapshot.fear_greed_index)
            if self.snapshot is not None
            else "Keine Daten"
        )

    @property
    def kill_switch_active(self) -> bool:
        return bool(self.snapshot and self.snapshot.is_kill_switch_regime)

    @property
    def paused_count(self) -> int:
        return len(self.paused_strategies)


_SELECT_PAUSED_SQL = """
SELECT id, name, horizon::text AS horizon, asset_class, updated_at
  FROM strategies
 WHERE status = 'paused'::strategy_status
   AND paused_by = 'kill_switch'
 ORDER BY updated_at DESC, id DESC
"""


_SELECT_HISTORY_SQL = """
SELECT
    al.id,
    al.created_at,
    al.event_type,
    al.strategy_id,
    s.name AS strategy_name,
    al.actor,
    COALESCE(al.override_flags->>'action', '-') AS action,
    NULLIF(al.override_flags->>'fear_greed_index', '')::int AS fear_greed_index,
    al.notes
  FROM audit_log al
  LEFT JOIN strategies s ON s.id = al.strategy_id
 WHERE al.event_type IN ('kill_switch_triggered', 'kill_switch_overridden')
   AND al.created_at >= NOW() - INTERVAL '30 days'
 ORDER BY al.created_at DESC, al.id DESC
 LIMIT 50
"""


async def get_current_regime(conn: asyncpg.Connection) -> RegimeView:
    """Assemble the regime view-model.

    Cheap — three small SELECTs, no JOINs on hot tables. Safe to call
    from the `GET /regime` handler AND the approval-viewport footer
    render without concern about tail latency.
    """

    snapshot = await get_latest_regime(conn)

    paused_rows = await conn.fetch(_SELECT_PAUSED_SQL)
    paused_strategies = [
        PausedStrategy(
            id=row["id"],
            name=row["name"],
            horizon=row["horizon"],
            asset_class=row["asset_class"],
            updated_at=row["updated_at"],
        )
        for row in paused_rows
    ]

    history_rows = await conn.fetch(_SELECT_HISTORY_SQL)
    override_history = [
        OverrideHistoryEntry(
            id=row["id"],
            created_at=row["created_at"],
            event_type=row["event_type"],
            strategy_id=row["strategy_id"],
            strategy_name=row["strategy_name"],
            actor=row["actor"],
            action=row["action"],
            fear_greed_index=row["fear_greed_index"],
            notes=row["notes"],
        )
        for row in history_rows
    ]

    return RegimeView(
        snapshot=snapshot,
        paused_strategies=paused_strategies,
        override_history=override_history,
    )


def format_pnl(value: Any) -> str:
    """Pretty-print a per-broker P&L value for the template."""

    if value is None:
        return "—"
    try:
        d = Decimal(str(value))
    except (ValueError, TypeError):
        return str(value)
    sign = "" if d >= 0 else "-"
    return f"{sign}${abs(d):,.2f}"

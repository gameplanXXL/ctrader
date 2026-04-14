"""Fundamental-snapshot persistence (Story 5.2).

When a new trade lands (via Story 2.2 live-sync or Epic 7/8 bot
order placement), the app fires a best-effort fundamental fetch and
stores the result in `fundamental_snapshots` keyed to the trade id.

The drilldown later reads this row plus a live fetch via
`get_fundamental()` so Chef can compare "damals" vs "jetzt".

Historical Flex-import trades are deliberately NOT snapshotted —
there's no useful "current-at-entry-time" assessment to capture for
a trade from last year.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.fundamental import FundamentalAssessment
from app.services.fundamental import get_fundamental

logger = get_logger(__name__)


_INSERT_SQL = """
INSERT INTO fundamental_snapshots (trade_id, asset_class, agent_id, snapshot_data)
VALUES ($1, $2, $3, $4)
RETURNING id, snapshot_at
"""


_READ_SQL = """
SELECT id, trade_id, asset_class, agent_id, snapshot_data, snapshot_at
  FROM fundamental_snapshots
 WHERE trade_id = $1
 ORDER BY snapshot_at DESC
 LIMIT 1
"""


@dataclass(frozen=True)
class FundamentalSnapshot:
    """One row from `fundamental_snapshots` — used by the drilldown."""

    id: int
    trade_id: int
    asset_class: str
    agent_id: str
    snapshot_data: dict[str, Any]
    snapshot_at: datetime

    @property
    def as_assessment(self) -> FundamentalAssessment:
        """Best-effort reconstruction into a `FundamentalAssessment`.

        The stored payload already matches the assessment dict shape
        (we use `model_dump(mode='json')` at write time), so
        `model_validate` should round-trip cleanly.
        """

        try:
            return FundamentalAssessment.model_validate(self.snapshot_data)
        except Exception:  # noqa: BLE001
            # Legacy / malformed row — return a placeholder so the
            # drilldown template still has something to render.
            return FundamentalAssessment(agent_id=self.agent_id)


async def capture_fundamental_snapshot(
    conn: asyncpg.Connection,
    trade_id: int,
    symbol: str,
    asset_class: str,
    mcp_client: MCPClient | None,
) -> FundamentalSnapshot | None:
    """Fetch fundamental data and persist it against a trade row.

    Never raises — graceful degradation is mandatory per FR23. On
    failure we log and return None so the caller (usually
    fire-and-forget `asyncio.create_task`) doesn't kill the live-sync
    loop.
    """

    if mcp_client is None:
        logger.info(
            "fundamental_snapshot.mcp_disabled",
            trade_id=trade_id,
            symbol=symbol,
        )
        return None

    try:
        result = await get_fundamental(symbol, asset_class, mcp_client)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning(
            "fundamental_snapshot.fetch_failed",
            trade_id=trade_id,
            symbol=symbol,
            error=str(exc),
        )
        return None

    if result is None:
        logger.info(
            "fundamental_snapshot.empty",
            trade_id=trade_id,
            symbol=symbol,
            hint="no MCP data and no stale fallback",
        )
        return None

    # Code-review M4 / EC-15: skip vacuous snapshots. An MCP response
    # that decoded to `{rating=UNKNOWN, thesis=""}` usually means the
    # server returned a non-JSON preamble or an empty-payload "sorry,
    # no data". Persisting it pollutes the fundamental_snapshots
    # table and muddies the "damals vs jetzt" drilldown comparison.
    from app.models.fundamental import FundamentalRating as _Rating

    assessment = result.assessment
    if assessment.rating is _Rating.UNKNOWN and not assessment.thesis.strip():
        logger.info(
            "fundamental_snapshot.skipped_vacuous",
            trade_id=trade_id,
            symbol=symbol,
        )
        return None

    # Serialize the assessment to JSONB via the codec registered in
    # app.db.pool.init_connection. Passing the dict directly is
    # enough — the codec `json.dumps(..., default=str)` handles any
    # stray Decimal/datetime.
    payload = result.assessment.model_dump(mode="json")

    try:
        row = await conn.fetchrow(
            _INSERT_SQL,
            trade_id,
            asset_class,
            result.source_agent or result.assessment.agent_id,
            payload,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning(
            "fundamental_snapshot.persist_failed",
            trade_id=trade_id,
            symbol=symbol,
            error=str(exc),
        )
        return None

    logger.info(
        "fundamental_snapshot.captured",
        trade_id=trade_id,
        symbol=symbol,
        snapshot_id=row["id"],
    )

    return FundamentalSnapshot(
        id=int(row["id"]),
        trade_id=trade_id,
        asset_class=asset_class,
        agent_id=result.source_agent or result.assessment.agent_id,
        snapshot_data=payload,
        snapshot_at=row["snapshot_at"],
    )


async def get_latest_snapshot(
    conn: asyncpg.Connection, trade_id: int
) -> FundamentalSnapshot | None:
    """Return the most recent snapshot for a trade, or None if no row."""

    row = await conn.fetchrow(_READ_SQL, trade_id)
    if row is None:
        return None

    raw = row["snapshot_data"] or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    return FundamentalSnapshot(
        id=int(row["id"]),
        trade_id=int(row["trade_id"]),
        asset_class=str(row["asset_class"]),
        agent_id=str(row["agent_id"]),
        snapshot_data=raw,
        snapshot_at=row["snapshot_at"],
    )

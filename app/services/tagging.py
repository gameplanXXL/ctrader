"""Trade-tagging service (Story 3.1 + 3.2).

One entry point: `tag_trade(conn, trade_id, spec)`. It persists the
built `TriggerSpec` to the `trades.trigger_spec` JSONB column via
asyncpg's JSONB codec (registered in `app.db.pool`) so we can pass a
plain Python dict instead of a pre-serialized string.
"""

from __future__ import annotations

import asyncpg

from app.logging import get_logger
from app.models.trigger_spec import TriggerSpec

logger = get_logger(__name__)


# Manual-tagging UPDATE. Guards (code-review H3 / BH-10 / EC-15):
#   - `broker = 'ib'`: cTrader bot trades carry their trigger_spec by
#     construction (Epic 8 / Story 8.2) — a scripted POST to
#     `/trades/{bot_id}/tag` must NOT clobber it.
#   - `closed_at IS NOT NULL`: open positions can't be post-hoc tagged
#     yet (FR15 lives on the exit reason, which requires a close).
# A row that fails the guards returns NULL from `RETURNING id`, and we
# translate that to `TradeNotTaggableError` so the router can 409.
_UPDATE_SQL = """
UPDATE trades
   SET trigger_spec = $1,
       updated_at   = NOW()
 WHERE id = $2
   AND broker = 'ib'
   AND closed_at IS NOT NULL
RETURNING id, (trigger_spec IS DISTINCT FROM $1) AS was_changed
"""

_TRADE_EXISTS_SQL = "SELECT broker, closed_at FROM trades WHERE id = $1"


class TradeNotFoundError(LookupError):
    """Raised when `tag_trade` targets a trade id that doesn't exist."""


class TradeNotTaggableError(ValueError):
    """Raised when the target row exists but is not eligible for manual
    tagging — wrong broker or still open."""


async def tag_trade(
    conn: asyncpg.Connection,
    trade_id: int,
    spec: TriggerSpec,
) -> None:
    """Persist the tagging form's result onto a trade.

    Raises:
        TradeNotFoundError: if `trade_id` does not resolve to a row.
        TradeNotTaggableError: if the trade exists but is bot-sourced
            or still open. The spec says "untagged IB closed trades
            only" — the tagging route enforces the same constraint at
            the UI layer, so this usually fires only on scripted /
            mis-routed POSTs.
    """

    row = await conn.fetchrow(_UPDATE_SQL, spec.to_jsonb(), trade_id)
    if row is None:
        # Could be absent OR ineligible — distinguish so callers get
        # the right HTTP status.
        existing = await conn.fetchrow(_TRADE_EXISTS_SQL, trade_id)
        if existing is None:
            raise TradeNotFoundError(f"trade {trade_id} does not exist")
        raise TradeNotTaggableError(
            f"trade {trade_id} is not eligible for manual tagging "
            f"(broker={existing['broker']}, closed_at={existing['closed_at']})"
        )

    logger.info(
        "tagging.tag_applied",
        trade_id=trade_id,
        trigger_type=spec.trigger_type,
        horizon=spec.horizon,
        mistake_tags=spec.mistake_tags,
        source=spec.source.value,
        was_changed=bool(row["was_changed"]),
    )

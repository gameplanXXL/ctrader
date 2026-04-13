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


_UPDATE_SQL = """
UPDATE trades
   SET trigger_spec = $1,
       updated_at   = NOW()
 WHERE id = $2
RETURNING id
"""


class TradeNotFoundError(LookupError):
    """Raised when `tag_trade` targets a trade id that doesn't exist."""


async def tag_trade(
    conn: asyncpg.Connection,
    trade_id: int,
    spec: TriggerSpec,
) -> None:
    """Persist the tagging form's result onto a trade.

    Raises:
        TradeNotFoundError: if `trade_id` does not resolve to a row.
    """

    row = await conn.fetchrow(_UPDATE_SQL, spec.to_jsonb(), trade_id)
    if row is None:
        raise TradeNotFoundError(f"trade {trade_id} does not exist")

    logger.info(
        "tagging.tag_applied",
        trade_id=trade_id,
        trigger_type=spec.trigger_type,
        horizon=spec.horizon,
        mistake_tags=spec.mistake_tags,
        source=spec.source.value,
    )

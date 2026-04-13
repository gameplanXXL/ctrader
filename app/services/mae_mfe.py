"""Maximum Adverse / Favorable Excursion calculation (Story 4.3).

Given a trade row, pull OHLC candles between `opened_at` and
`closed_at`, then derive:

- **MAE** — biggest unrealized loss relative to entry during the hold
- **MFE** — biggest unrealized gain relative to entry during the hold

Both are returned in price-units AND position-dollar-units. Sign
convention:
- MAE is always stored as a NEGATIVE number (adverse move from entry)
- MFE is always stored as a POSITIVE number (favorable move)

For LONG trades:
- MAE = `min(low) - entry`
- MFE = `max(high) - entry`

For SHORT trades:
- MAE = `entry - max(high)` → stored negative
- MFE = `entry - min(low)`

If the candle source can't supply any data (every client in the
fallback chain fails), the function returns `(None, None, None, None)`
and the caller stores NULL → "—" in the drilldown (AC #5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from app.clients.ohlc import FallbackOHLCClient, get_default_chain
from app.logging import get_logger
from app.models.ohlc import Candle, Timeframe
from app.services.ohlc_cache import get_cached_candles, upsert_candles

logger = get_logger(__name__)


@dataclass(frozen=True)
class MaeMfeResult:
    mae_price: Decimal | None
    mfe_price: Decimal | None
    mae_dollars: Decimal | None
    mfe_dollars: Decimal | None

    @property
    def available(self) -> bool:
        return self.mae_price is not None or self.mfe_price is not None


async def compute_mae_mfe(
    conn: asyncpg.Connection,
    trade: dict[str, Any],
    *,
    client: FallbackOHLCClient | None = None,
) -> MaeMfeResult:
    """Compute MAE/MFE for one trade.

    Returns `MaeMfeResult(None, None, ...)` on any failure — never
    raises. Callers should persist the result via `persist_mae_mfe`
    below to avoid recomputing on subsequent drilldown renders.
    """

    symbol = trade.get("symbol")
    side = str(trade.get("side") or "").lower()
    entry = trade.get("entry_price")
    quantity = trade.get("quantity")
    opened_at = trade.get("opened_at")
    closed_at = trade.get("closed_at") or opened_at

    if not (symbol and entry is not None and quantity is not None and opened_at):
        return MaeMfeResult(None, None, None, None)

    entry_d = Decimal(str(entry))
    qty_d = Decimal(str(quantity))

    candles = await _get_candles(
        conn,
        symbol=str(symbol),
        start=opened_at,
        end=closed_at,
        client=client,
    )
    if not candles:
        return MaeMfeResult(None, None, None, None)

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    hi = max(highs)
    lo = min(lows)

    if side == "buy":
        mae = lo - entry_d
        mfe = hi - entry_d
    elif side in ("sell", "short", "cover"):
        mae = entry_d - hi  # adverse = price up
        mfe = entry_d - lo  # favorable = price down
        # Normalize signs: MAE must be negative.
        mae = -abs(mae) if mae > 0 else mae
    else:
        return MaeMfeResult(None, None, None, None)

    return MaeMfeResult(
        mae_price=mae,
        mfe_price=mfe,
        mae_dollars=mae * qty_d,
        mfe_dollars=mfe * qty_d,
    )


async def _get_candles(
    conn: asyncpg.Connection,
    *,
    symbol: str,
    start: datetime,
    end: datetime,
    client: FallbackOHLCClient | None,
) -> list[Candle]:
    """Read-through: cache first, fall back to the client chain, persist."""

    # Prefer 1m candles — higher fidelity for intraday MAE/MFE.
    for tf in (Timeframe.M1, Timeframe.M5):
        cached = await get_cached_candles(conn, symbol=symbol, start=start, end=end, timeframe=tf)
        if cached:
            return cached

    client = client or get_default_chain()
    try:
        fresh = await client.get_candles(symbol, start, end, Timeframe.M1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mae_mfe.fetch_failed", symbol=symbol, error=str(exc))
        return []

    if fresh:
        try:
            await upsert_candles(conn, fresh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mae_mfe.cache_upsert_failed", symbol=symbol, error=str(exc))
    return fresh


_PERSIST_SQL = """
UPDATE trades
   SET mae_price           = $1,
       mfe_price            = $2,
       mae_dollars          = $3,
       mfe_dollars          = $4,
       mae_mfe_computed_at  = NOW()
 WHERE id = $5
"""


async def persist_mae_mfe(conn: asyncpg.Connection, trade_id: int, result: MaeMfeResult) -> None:
    """Cache the computed MAE/MFE on the trades row."""

    await conn.execute(
        _PERSIST_SQL,
        result.mae_price,
        result.mfe_price,
        result.mae_dollars,
        result.mfe_dollars,
        trade_id,
    )

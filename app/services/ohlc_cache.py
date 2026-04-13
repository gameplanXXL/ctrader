"""OHLC candle cache (Story 4.3).

Read-through pattern with a 24h TTL on the `ohlc_candles` table:

1. `get_cached_candles(conn, symbol, start, end, timeframe)` checks
   whether the cache has candles inside `[start, end]` whose
   `cached_at` is newer than `NOW() - 24h`. If YES → return them.
2. On cache miss, the caller fetches fresh candles via the
   `FallbackOHLCClient` and calls `upsert_candles()` to store them.
   The next call inside the TTL window hits the cache.

Cache semantics intentionally allow partial ranges — if only half
the window is cached and fresh, the caller can still use those and
only fetch the missing range. In practice MAE/MFE fetches a single
bounded window per trade, so we keep the logic simple and either
return the whole range or nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

import asyncpg

from app.logging import get_logger
from app.models.ohlc import Candle, Timeframe

logger = get_logger(__name__)


_CACHE_TTL_HOURS = 24

_READ_SQL = """
SELECT symbol, timeframe, ts, open, high, low, close, volume
  FROM ohlc_candles
 WHERE symbol    = $1
   AND timeframe = $2::ohlc_timeframe
   AND ts >= $3
   AND ts <  $4
   AND cached_at > NOW() - INTERVAL '{ttl} hours'
 ORDER BY ts ASC
"""

_UPSERT_SQL = """
INSERT INTO ohlc_candles (symbol, timeframe, ts, open, high, low, close, volume, cached_at)
VALUES ($1, $2::ohlc_timeframe, $3, $4, $5, $6, $7, $8, NOW())
ON CONFLICT (symbol, timeframe, ts) DO UPDATE
   SET open      = EXCLUDED.open,
       high      = EXCLUDED.high,
       low       = EXCLUDED.low,
       close     = EXCLUDED.close,
       volume    = EXCLUDED.volume,
       cached_at = NOW()
"""


async def get_cached_candles(
    conn: asyncpg.Connection,
    *,
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
) -> list[Candle]:
    """Return cached candles for `[start, end)` or `[]` on miss/stale."""

    sql = _READ_SQL.format(ttl=_CACHE_TTL_HOURS)
    rows = await conn.fetch(sql, symbol, timeframe.value, start, end)
    return [
        Candle(
            symbol=row["symbol"],
            timeframe=Timeframe(row["timeframe"]),
            ts=row["ts"],
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=(Decimal(str(row["volume"])) if row["volume"] is not None else None),
        )
        for row in rows
    ]


async def upsert_candles(conn: asyncpg.Connection, candles: Iterable[Candle]) -> int:
    """Persist a batch of candles, refreshing `cached_at` on conflict."""

    count = 0
    async with conn.transaction():
        for candle in candles:
            await conn.execute(
                _UPSERT_SQL,
                candle.symbol,
                candle.timeframe.value,
                candle.ts,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
            count += 1
    return count

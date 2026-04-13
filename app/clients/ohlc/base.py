"""OHLCClient protocol (Story 4.3).

Each implementation (ib_async historical, Binance, Kraken, fundamental
MCP price tool) satisfies this protocol. The `FallbackOHLCClient`
walks the list in order and returns the first successful response.

Graceful degradation: if NO client returns data within the 15s budget,
we return an empty list and the caller (mae_mfe service) stores
`mae_price = NULL`, which the template renders as "—" per
AC #5 (UX-DR55).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.models.ohlc import Candle, Timeframe


class OHLCClient(Protocol):
    """Fetch candles for a symbol/timeframe/window."""

    name: str

    async def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Timeframe,
    ) -> list[Candle]: ...

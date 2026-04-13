"""FallbackOHLCClient + default chain (Story 4.3).

The production chain walks: IB historical → Binance → Kraken → MCP
`fundamental/price`. For Phase 1 (this epic), only the MCP client is
wired — the others are stubs that immediately raise `NotImplementedError`
so the fallback advances. Replacing them with real SDK calls is a
drop-in change when the data sources are needed.

The total time budget is 15 seconds per `get_candles` call
(NFR-I6). Inside the budget we also cap each individual client at
5s so a hung IB socket doesn't starve the cheaper fallbacks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.clients.ohlc.base import OHLCClient
from app.logging import get_logger
from app.models.ohlc import Candle, Timeframe

logger = get_logger(__name__)


TOTAL_TIMEOUT_S = 15.0
PER_CLIENT_TIMEOUT_S = 5.0


class _StubClient:
    """Placeholder that raises immediately so the fallback advances.

    Replace with a real SDK call when the corresponding data source
    is needed. Kept separate from the real MCP client so nobody
    accidentally ships a half-wired IB path."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Timeframe,
    ) -> list[Candle]:
        raise NotImplementedError(f"{self.name} OHLC client not wired yet")


class FallbackOHLCClient:
    """Walks a list of `OHLCClient`s until one returns candles."""

    name: str = "fallback"

    def __init__(self, chain: list[OHLCClient]) -> None:
        self._chain = chain

    async def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Timeframe,
    ) -> list[Candle]:
        deadline = asyncio.get_event_loop().time() + TOTAL_TIMEOUT_S

        for client in self._chain:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            client_budget = min(remaining, PER_CLIENT_TIMEOUT_S)
            try:
                candles = await asyncio.wait_for(
                    client.get_candles(symbol, start, end, timeframe),
                    timeout=client_budget,
                )
                if candles:
                    logger.info(
                        "ohlc.fetched",
                        client=client.name,
                        symbol=symbol,
                        count=len(candles),
                    )
                    return candles
            except NotImplementedError:
                # Stub client — silently advance, we expect this.
                continue
            except (TimeoutError, ConnectionError) as exc:
                logger.warning(
                    "ohlc.client_failed",
                    client=client.name,
                    symbol=symbol,
                    error=str(exc),
                )
                continue
            except Exception as exc:  # noqa: BLE001 — graceful degradation
                logger.warning(
                    "ohlc.client_unknown_error",
                    client=client.name,
                    symbol=symbol,
                    error=str(exc),
                    exc_type=type(exc).__name__,
                )
                continue

        logger.info("ohlc.all_sources_failed", symbol=symbol)
        return []


def get_default_chain() -> FallbackOHLCClient:
    """Build the production chain.

    Phase 1 registers stub clients only — none of the broker integrations
    are wired yet. The chain still returns `[]` gracefully so the
    MAE/MFE service can persist NULL and let the drilldown render a
    placeholder. Flip individual stubs to real clients as epics land.
    """

    return FallbackOHLCClient(
        chain=[
            _StubClient("ib_historical"),  # Story 4.3 follow-up
            _StubClient("binance"),  # Story 4.3 follow-up
            _StubClient("kraken"),  # Story 4.3 follow-up
            _StubClient("fundamental_mcp_price"),  # Story 5.2 bridge
        ]
    )

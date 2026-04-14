"""IB Quick-Order boundary layer (Epic 12 / Stories 12.1–12.4).

Design: same pattern as `app/clients/ctrader.py`. A clean Protocol
(`IBQuickOrderClient`) + a deterministic `StubIBQuickOrderClient`
so the full Epic-12 pipeline (form → chain fetch → preview →
bracket submission → fill event → auto-tagged trade) is
exercisable end-to-end WITHOUT a live TWS or IB Gateway. When Chef
has TWS running locally, a real `IBAsyncQuickOrderClient` adapter
can replace the stub behind the same protocol.

CLAUDE.md locked decisions honored:
- `ib_async` (NOT `ib_insync`) is the only supported runtime
  adapter once the stub is replaced.
- Epic 12 is the last epic in the pipeline per Chef's 2026-04-14
  scope update; the stub-first approach lets Chef boot the
  Quick-Order UI now without committing to TWS setup time.

The protocol mirrors the shape of the Story-12.2 spec:
- `is_connected()` → bool, used by the `/trades/quick-order/form`
  endpoint to render a disabled banner if TWS is down.
- `fetch_option_chain(symbol)` → list of (expiry, strike, right)
  tuples, used by the form's Expiry/Strike dropdowns.
- `what_if_order(request)` → margin estimate, used by the
  Bestätigungs-UI for Short-Option warnings.
- `place_bracket_order(request)` → returns an order_ref + ib_order_id
  result, used by the submit endpoint.
- `subscribe_execution_events(handler)` → the scheduler/live-sync
  pipeline registers a callback for FILLED → trade-row creation.

The stub generates a deterministic options chain (nearest 4
monthly expiries starting at 7 DTE + a standard strike ladder
around `entry_price`), auto-emits a FILLED event on a 50ms tick,
and raises `IBTerminalError` for unknown symbols so the error path
is also testable.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, Protocol

from app.logging import get_logger
from app.services.ib_error_map import IBTerminalError

logger = get_logger(__name__)


OrderSide = Literal["BUY", "SELL"]
OptionRight = Literal["C", "P"]
AssetClass = Literal["stock", "option"]


@dataclass(frozen=True)
class OptionChainEntry:
    """One (expiry, strike, right) row returned by `fetch_option_chain`."""

    expiry: date
    strike: Decimal
    right: OptionRight


@dataclass(frozen=True)
class WhatIfResult:
    """Margin-estimate payload from `what_if_order()`.

    `initial_margin_change` is what Short-Option warnings display.
    `commission` is the estimated broker fee per IB's model.
    """

    initial_margin_change: Decimal
    maintenance_margin_change: Decimal
    commission: Decimal


@dataclass(frozen=True)
class PlaceOrderRequest:
    """DTO for `place_bracket_order`. Mirrors the Story-12.2 spec
    (parent limit + child STP bracket, atomic submission).
    """

    order_ref: str
    asset_class: AssetClass
    symbol: str
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal
    stop_price: Decimal
    # Option-only fields — None for stock orders
    option_expiry: date | None = None
    option_strike: Decimal | None = None
    option_right: OptionRight | None = None
    option_multiplier: int | None = None


@dataclass(frozen=True)
class PlaceOrderResult:
    """Immediate response from `place_bracket_order`."""

    order_ref: str
    ib_order_id: str
    accepted_at: datetime


@dataclass(frozen=True)
class ExecutionEvent:
    """Shape handed to the live-sync hook. Same boundary as the
    cTrader pattern — no `ib_async` Protobuf leaks into domain
    code.
    """

    order_ref: str
    ib_order_id: str
    status: Literal["submitted", "filled", "partial", "rejected", "cancelled"]
    filled_quantity: Decimal
    filled_price: Decimal
    execution_time: datetime
    raw: dict[str, Any] = field(default_factory=dict)


class IBQuickOrderClient(Protocol):
    """Protocol every concrete client (stub or real ib_async adapter)
    must satisfy. Keep it async-native and Protobuf/ib_async-agnostic.
    """

    def is_connected(self) -> bool: ...

    async def fetch_option_chain(self, symbol: str) -> list[OptionChainEntry]: ...

    async def what_if_order(self, request: PlaceOrderRequest) -> WhatIfResult: ...

    async def place_bracket_order(self, request: PlaceOrderRequest) -> PlaceOrderResult: ...

    async def subscribe_execution_events(self, handler) -> None: ...

    async def aclose(self) -> None: ...


# ---------------------------------------------------------------------------
# StubIBQuickOrderClient — default for dev + tests
# ---------------------------------------------------------------------------


_STUB_KNOWN_SYMBOLS: frozenset[str] = frozenset(
    {"AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "META", "AMZN", "SPY", "QQQ"}
)


def _next_monthly_expiries(count: int, *, min_dte: int = 7) -> list[date]:
    """Generate the next `count` third-Friday-of-the-month expiries
    starting at least `min_dte` calendar days out.
    """

    today = datetime.now(UTC).date()
    results: list[date] = []
    current_year = today.year
    current_month = today.month
    while len(results) < count + 2:
        # Third Friday of `current_month` in `current_year`
        first = date(current_year, current_month, 1)
        first_weekday = first.weekday()  # Mon=0 .. Sun=6
        first_friday_offset = (4 - first_weekday) % 7
        third_friday = first + timedelta(days=first_friday_offset + 14)
        if (third_friday - today).days >= min_dte:
            results.append(third_friday)
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    return results[:count]


def _stub_strike_ladder(center: Decimal) -> list[Decimal]:
    """Generate a standard strike ladder around `center`.

    Stocks have $5 spacing below $200 and $10 above; this is
    deliberately coarse so the stub chain is small and predictable.
    """

    step = Decimal("5") if center < Decimal("200") else Decimal("10")
    base = (center // step) * step
    offsets = [-4, -3, -2, -1, 0, 1, 2, 3, 4]
    return [base + Decimal(o) * step for o in offsets if base + Decimal(o) * step > 0]


class StubIBQuickOrderClient:
    """In-memory stub — same story as `StubCTraderClient`.

    - `is_connected()` → True by default so dev can drive the form
      without a TWS dependency. Flip `connected=False` in tests that
      exercise the "TWS offline" error path (Story 12.4 AC #7).
    - `fetch_option_chain(symbol)` returns a deterministic chain based
      on `_STUB_KNOWN_SYMBOLS` + a synthetic underlying price (180 for
      all). Unknown symbols raise `IBTerminalError` with IB error
      code 200.
    - `what_if_order` returns a fixed margin estimate scaled by
      contract count so Short-Option rows show a realistic number.
    - `place_bracket_order` persists the request in memory, emits a
      synthetic FILLED `ExecutionEvent` on the next tick so the
      fill-handler hook runs, and returns a `PlaceOrderResult`.
    """

    def __init__(
        self,
        *,
        connected: bool = True,
        fill_delay_seconds: float = 0.05,
    ) -> None:
        self._connected = connected
        self._fill_delay_seconds = fill_delay_seconds
        self._placed_orders: dict[str, PlaceOrderResult] = {}
        self._handlers: list = []
        self._tasks: set[asyncio.Task] = set()

    def is_connected(self) -> bool:
        return self._connected

    async def fetch_option_chain(self, symbol: str) -> list[OptionChainEntry]:
        if symbol.upper() not in _STUB_KNOWN_SYMBOLS:
            logger.warning("ib_stub.option_chain.unknown_symbol", symbol=symbol)
            raise IBTerminalError(
                f"No option chain for symbol {symbol}",
                error_code=200,
            )
        expiries = _next_monthly_expiries(4, min_dte=7)
        # Stub underlying price: 180 for everything. Real adapter
        # will fetch spot via `reqMktData`.
        strikes = _stub_strike_ladder(Decimal("180"))
        entries: list[OptionChainEntry] = []
        for expiry in expiries:
            for strike in strikes:
                entries.append(OptionChainEntry(expiry=expiry, strike=strike, right="C"))
                entries.append(OptionChainEntry(expiry=expiry, strike=strike, right="P"))
        logger.info(
            "ib_stub.option_chain.generated",
            symbol=symbol,
            expiries=len(expiries),
            strikes=len(strikes),
            entries=len(entries),
        )
        return entries

    async def what_if_order(self, request: PlaceOrderRequest) -> WhatIfResult:
        """Synthetic margin estimate for the Short-Option warning."""

        if request.asset_class == "option" and request.side == "SELL":
            # Short option: IB Reg-T approximates margin as max(
            # 20% underlying - OTM, 10% underlying, $250) × contracts
            # × multiplier. We use a crude flat: $2500 per contract.
            margin = Decimal("2500") * request.quantity
        elif request.asset_class == "option":
            # Long option: premium paid only.
            margin = request.limit_price * request.quantity * Decimal("100")
        else:
            # Stock: 50% Reg-T initial margin.
            margin = (request.limit_price * request.quantity) * Decimal("0.5")
        commission = Decimal("1.00") * request.quantity
        return WhatIfResult(
            initial_margin_change=margin,
            maintenance_margin_change=margin * Decimal("0.8"),
            commission=commission,
        )

    async def place_bracket_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        if not self._connected:
            raise IBTerminalError(
                "IB TWS/Gateway nicht verbunden",
                error_code=None,
            )
        if request.order_ref in self._placed_orders:
            logger.info(
                "ib_stub.place_order.idempotent",
                order_ref=request.order_ref,
            )
            return self._placed_orders[request.order_ref]

        ib_order_id = f"stub-{uuid.uuid4().hex[:12]}"
        result = PlaceOrderResult(
            order_ref=request.order_ref,
            ib_order_id=ib_order_id,
            accepted_at=datetime.now(UTC),
        )
        self._placed_orders[request.order_ref] = result
        logger.info(
            "ib_stub.place_order.accepted",
            order_ref=request.order_ref,
            ib_order_id=ib_order_id,
            asset_class=request.asset_class,
            symbol=request.symbol,
            side=request.side,
            quantity=str(request.quantity),
        )

        # Schedule synthetic FILLED event
        task = asyncio.create_task(self._emit_fill(request, result))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return result

    async def subscribe_execution_events(self, handler) -> None:
        self._handlers.append(handler)

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        self._handlers.clear()
        self._placed_orders.clear()

    async def _emit_fill(self, request: PlaceOrderRequest, accepted: PlaceOrderResult) -> None:
        await asyncio.sleep(self._fill_delay_seconds)
        event = ExecutionEvent(
            order_ref=request.order_ref,
            ib_order_id=accepted.ib_order_id,
            status="filled",
            filled_quantity=request.quantity,
            filled_price=request.limit_price,
            execution_time=datetime.now(UTC),
            raw={"source": "stub"},
        )
        logger.info(
            "ib_stub.execution_event.emit",
            order_ref=event.order_ref,
            status=event.status,
            filled_price=str(event.filled_price),
        )
        for handler in list(self._handlers):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "ib_stub.execution_event.handler_failed",
                    order_ref=event.order_ref,
                )


def build_ib_quick_order_client(
    *,
    ib_host: str | None,
    ib_port: int,
) -> IBQuickOrderClient:
    """Factory — returns the stub in dev, real ib_async adapter when
    wired. Currently always returns `StubIBQuickOrderClient`.

    The real adapter will be a thin wrapper around `app.clients.ib`
    (Story 2.2 live-sync connection) — the challenge there is that
    `ib_async` uses its own event loop via `nest_asyncio`, which
    conflicts with FastAPI's uvloop. The ib_async connection is
    already gated on a uvloop check (see `app/clients/ib.py`).
    """

    if not ib_host:
        logger.info(
            "app.ib_quick_order.stub_default",
            reason="ib_host not configured — using StubIBQuickOrderClient",
        )
        return StubIBQuickOrderClient()

    logger.warning(
        "app.ib_quick_order.stub_fallback",
        reason=(
            "ib_async Quick-Order adapter not yet implemented — "
            "using StubIBQuickOrderClient despite configured ib_host"
        ),
        ib_host=ib_host,
        ib_port=ib_port,
    )
    return StubIBQuickOrderClient()

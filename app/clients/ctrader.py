"""cTrader client — boundary layer for bot-execution (Story 8.1).

Design rationale
----------------
CLAUDE.md freezes two things about cTrader:

    cTrader-Integration: OpenApiPy (Protobuf), mögliche partielle
    Wiederverwendung aus /home/cneise/Project/ALT/ctrader2 nur nach
    1-Tages-Spike-Timebox.

That spike has not happened yet, but the rest of Epic 8 — idempotency,
retry, event-driven status tracking, trade creation on FILLED — can be
built and tested *now* against a clean protocol boundary. When Chef is
ready to run the real OpenApiPy adapter, we drop in a second concrete
implementation behind the same `CTraderClient` protocol and flip an env
var.

The `StubCTraderClient` is the default in development: it pretends the
order was accepted, returns a synthetic cTrader-order-id, and emits a
simulated FILLED execution event on the next tick. That lets the full
approve → execute → fill → trade-row pipeline run end-to-end without a
live account.

The protocol deliberately mirrors cTrader semantics (clientOrderId,
volume in lot-units, LIMIT/STOP order types) so the real adapter does
not need to translate anything — just forward to OpenApiPy.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from app.logging import get_logger

logger = get_logger(__name__)


OrderType = Literal["LIMIT", "STOP", "MARKET"]
OrderSide = Literal["BUY", "SELL"]
ExecutionStatus = Literal["submitted", "filled", "partial", "rejected", "cancelled"]


@dataclass(frozen=True)
class PlaceOrderRequest:
    """Plain DTO so the bot-execution service doesn't leak Protobuf
    types into domain code. The real OpenApiPy adapter maps this to
    `ProtoOANewOrderReq`.
    """

    client_order_id: str
    symbol: str
    side: OrderSide
    volume: Decimal
    order_type: OrderType = "LIMIT"
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    take_profit_price: Decimal | None = None


@dataclass(frozen=True)
class PlaceOrderResult:
    """Immediate response from `place_order`. Not a fill — just an
    acknowledgement that the order was accepted.
    """

    client_order_id: str
    ctrader_order_id: str
    status: ExecutionStatus
    accepted_at: datetime


@dataclass(frozen=True)
class ExecutionEvent:
    """Shape handed to `bot_execution.handle_execution_event()`.

    Mirrors the subset of `ProtoOAExecutionEvent` that Story 8.2 cares
    about — we deliberately do NOT expose Protobuf types to keep the
    boundary clean.
    """

    client_order_id: str
    ctrader_order_id: str
    status: ExecutionStatus
    filled_volume: Decimal
    filled_price: Decimal
    execution_time: datetime
    raw: dict[str, Any] = field(default_factory=dict)


class CTraderRateLimitError(Exception):
    """Raised when cTrader returns the 429-equivalent — transient,
    retryable with exponential backoff (NFR-I3).
    """


class CTraderTransientError(ConnectionError):
    """Catch-all for reconnect-worthy errors. Separate from
    CTraderRateLimitError so downstream code can distinguish "wait"
    from "just retry".
    """


class CTraderTerminalError(RuntimeError):
    """Non-retryable error (invalid symbol, rejected order, insufficient
    margin). Propagated all the way to the operator.
    """


class CTraderClient(Protocol):
    """Protocol every concrete client (stub or real) must satisfy."""

    async def place_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        """Submit an order. Raises `CTraderRateLimitError`,
        `CTraderTransientError` or `CTraderTerminalError` on failure.
        """
        ...

    async def order_exists(self, client_order_id: str) -> bool:
        """Idempotency probe: returns True if an order with that
        `client_order_id` is already known to cTrader. Used after a
        retry to avoid double-execution.
        """
        ...

    async def subscribe_execution_events(self, handler) -> None:
        """Register a callback for incoming `ExecutionEvent`s. The
        handler is called on every order-status transition."""
        ...

    async def aclose(self) -> None:
        """Teardown — called from the FastAPI lifespan."""
        ...


# ---------------------------------------------------------------------------
# Stub implementation — development / test default
# ---------------------------------------------------------------------------


class StubCTraderClient:
    """Synthetic client for development and tests.

    Simulates the happy path (accept → fill after a tick) so the full
    Story 8.1 + 8.2 pipeline is exercisable locally without a live
    demo account. The stub is strictly in-memory and deterministic
    given the same sequence of `place_order` calls.

    Real cTrader adapter will be added behind the same `CTraderClient`
    protocol once CLAUDE.md's 1-day spike timebox is spent — this stub
    stays as the test double.
    """

    def __init__(self, *, fill_delay_seconds: float = 0.05) -> None:
        self._orders: dict[str, PlaceOrderResult] = {}
        self._handlers: list = []
        self._fill_delay_seconds = fill_delay_seconds
        self._tasks: set[asyncio.Task] = set()

    async def place_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        # Idempotency — same client_order_id returns the cached result.
        if request.client_order_id in self._orders:
            logger.info(
                "ctrader.stub.place_order.idempotent",
                client_order_id=request.client_order_id,
            )
            return self._orders[request.client_order_id]

        ctrader_order_id = f"stub-{uuid.uuid4().hex[:12]}"
        result = PlaceOrderResult(
            client_order_id=request.client_order_id,
            ctrader_order_id=ctrader_order_id,
            status="submitted",
            accepted_at=datetime.now(UTC),
        )
        self._orders[request.client_order_id] = result
        logger.info(
            "ctrader.stub.place_order.accepted",
            client_order_id=request.client_order_id,
            ctrader_order_id=ctrader_order_id,
            symbol=request.symbol,
            side=request.side,
            volume=str(request.volume),
        )

        # Schedule a synthetic FILLED event on the next tick so tests
        # can `await asyncio.sleep(fill_delay * 2)` and see the full
        # lifecycle without wiring up a real event loop.
        task = asyncio.create_task(self._emit_fill(request, result))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return result

    async def order_exists(self, client_order_id: str) -> bool:
        return client_order_id in self._orders

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
        self._orders.clear()

    async def _emit_fill(self, request: PlaceOrderRequest, accepted: PlaceOrderResult) -> None:
        await asyncio.sleep(self._fill_delay_seconds)
        event = ExecutionEvent(
            client_order_id=request.client_order_id,
            ctrader_order_id=accepted.ctrader_order_id,
            status="filled",
            filled_volume=request.volume,
            filled_price=request.limit_price or Decimal("0"),
            execution_time=datetime.now(UTC),
            raw={"source": "stub", "order_type": request.order_type},
        )
        logger.info(
            "ctrader.stub.execution_event.emit",
            client_order_id=event.client_order_id,
            status=event.status,
            filled_price=str(event.filled_price),
        )
        for handler in list(self._handlers):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "ctrader.stub.execution_event.handler_failed",
                    client_order_id=event.client_order_id,
                )


def build_ctrader_client(
    *,
    host: str | None,
    client_id: str | None,
    client_secret: str | None,
    account_id: str | None,
) -> CTraderClient | None:
    """Factory — returns the stub in dev, real adapter when wired.

    Currently ALWAYS returns the stub. The real OpenApiPy-backed client
    lands after the 1-day spike per CLAUDE.md. The function-shape is
    already here so the lifespan wiring doesn't have to change later.
    """

    if not host and not client_id:
        logger.info("app.ctrader_disabled", reason="no ctrader credentials configured")
        return StubCTraderClient()

    # TODO: replace with real adapter once the OpenApiPy spike lands.
    logger.info(
        "app.ctrader_stub_fallback",
        reason="real OpenApiPy adapter not yet implemented — using StubCTraderClient",
        host=host,
        account_id=account_id,
    )
    _ = client_secret  # unused until real adapter
    return StubCTraderClient()

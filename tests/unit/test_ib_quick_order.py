"""Unit tests for Epic 12 — IB Quick-Order pipeline.

Covers:
- `ib_error_map.classify` known + unknown codes
- `IBTerminalError` / `IBTransientError` exception types
- `StubIBQuickOrderClient` happy path: chain + what_if + place + fill
- `StubIBQuickOrderClient` unknown symbol → IBTerminalError
- `StubIBQuickOrderClient` disconnected state → IBTerminalError
- `place_order_with_retry` transient retry + terminal short-circuit
- `compute_preview` stock + short-option paths + risk computation
- `submit_quick_order` happy path + disconnected + missing ack
- `handle_fill_event` creates trade row with auto-tagged trigger_spec

DB layer uses the same `_FakeConn` / `_FakePool` pattern as the
bot_execution + gordon tests.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.clients.ib_quick_order import (
    ExecutionEvent,
    OptionChainEntry,
    PlaceOrderRequest,
    PlaceOrderResult,
    StubIBQuickOrderClient,
    WhatIfResult,
)
from app.services.ib_error_map import (
    IBTerminalError,
    IBTransientError,
    classify,
    format_for_operator,
    is_transient,
)
from app.services.ib_quick_order import (
    QuickOrderForm,
    QuickOrderSubmitError,
    compute_preview,
    handle_fill_event,
    place_order_with_retry,
    submit_quick_order,
)

# ---------------------------------------------------------------------------
# DB stubs
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._canned = canned or {}

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchval", sql, args))
        if "INSERT INTO quick_orders" in sql:
            return 42
        if "INSERT INTO trades" in sql:
            return 999
        return self._canned.get("fetchval")

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", sql, args))
        return self._canned.get("fetchrow")

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(("execute", sql, args))
        return "UPDATE 1"

    def transaction(self):
        class _Txn:
            async def __aenter__(self):  # noqa: N805
                return None

            async def __aexit__(self, *_exc):  # noqa: N805
                return None

        return _Txn()


# ---------------------------------------------------------------------------
# ib_error_map
# ---------------------------------------------------------------------------


def test_classify_known_transient() -> None:
    cat, msg = classify(1100)
    assert cat == "transient"
    assert "Verbindung" in msg


def test_classify_known_terminal() -> None:
    cat, msg = classify(10318)
    assert cat == "terminal"
    assert "Margin" in msg


def test_classify_unknown_code_defaults_terminal() -> None:
    cat, msg = classify(99999)
    assert cat == "terminal"
    assert "99999" in msg


def test_classify_none_is_not_connected() -> None:
    cat, msg = classify(None)
    assert cat == "terminal"
    assert "nicht verbunden" in msg


def test_is_transient_predicate() -> None:
    assert is_transient(1100) is True
    assert is_transient(10318) is False


def test_format_for_operator_includes_code() -> None:
    msg = format_for_operator(10318)
    assert "Margin" in msg
    assert "(IB 10318)" in msg


def test_format_for_operator_none_drops_code_suffix() -> None:
    msg = format_for_operator(None)
    assert "(IB" not in msg


# ---------------------------------------------------------------------------
# StubIBQuickOrderClient
# ---------------------------------------------------------------------------


async def test_stub_client_connected_by_default() -> None:
    stub = StubIBQuickOrderClient()
    assert stub.is_connected() is True


async def test_stub_client_disconnected_flag() -> None:
    stub = StubIBQuickOrderClient(connected=False)
    assert stub.is_connected() is False
    with pytest.raises(IBTerminalError):
        await stub.place_bracket_order(
            PlaceOrderRequest(
                order_ref="test",
                asset_class="stock",
                symbol="AAPL",
                side="BUY",
                quantity=Decimal("10"),
                limit_price=Decimal("180"),
                stop_price=Decimal("175"),
            )
        )


async def test_stub_option_chain_for_known_symbol() -> None:
    stub = StubIBQuickOrderClient()
    chain = await stub.fetch_option_chain("AAPL")
    assert len(chain) > 0
    # Every entry has expiry + strike + right populated
    for entry in chain:
        assert isinstance(entry, OptionChainEntry)
        assert entry.expiry >= datetime.now(UTC).date() + timedelta(days=7)
        assert entry.strike > 0
        assert entry.right in ("C", "P")


async def test_stub_option_chain_unknown_symbol_raises_terminal() -> None:
    stub = StubIBQuickOrderClient()
    with pytest.raises(IBTerminalError):
        await stub.fetch_option_chain("UNKNOWN_SYMBOL_123")


async def test_stub_what_if_short_option_returns_margin() -> None:
    stub = StubIBQuickOrderClient()
    request = PlaceOrderRequest(
        order_ref="x",
        asset_class="option",
        symbol="SPY",
        side="SELL",  # Sell-to-open
        quantity=Decimal("5"),
        limit_price=Decimal("3.20"),
        stop_price=Decimal("1.60"),
        option_expiry=date(2026, 5, 16),
        option_strike=Decimal("450"),
        option_right="P",
        option_multiplier=100,
    )
    result = await stub.what_if_order(request)
    assert isinstance(result, WhatIfResult)
    assert result.initial_margin_change > 0
    # Stub formula: $2500 per contract × 5 contracts = $12500
    assert result.initial_margin_change == Decimal("12500")


async def test_stub_place_order_happy_path_plus_fill_event() -> None:
    stub = StubIBQuickOrderClient(fill_delay_seconds=0.01)
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    await stub.subscribe_execution_events(handler)
    result = await stub.place_bracket_order(
        PlaceOrderRequest(
            order_ref="test-1",
            asset_class="stock",
            symbol="AAPL",
            side="BUY",
            quantity=Decimal("100"),
            limit_price=Decimal("185"),
            stop_price=Decimal("180"),
        )
    )
    assert isinstance(result, PlaceOrderResult)
    assert result.ib_order_id.startswith("stub-")

    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].status == "filled"
    assert received[0].filled_quantity == Decimal("100")
    assert received[0].filled_price == Decimal("185")
    await stub.aclose()


async def test_stub_place_order_idempotent() -> None:
    stub = StubIBQuickOrderClient()
    request = PlaceOrderRequest(
        order_ref="idempo-1",
        asset_class="stock",
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("10"),
        limit_price=Decimal("180"),
        stop_price=Decimal("175"),
    )
    first = await stub.place_bracket_order(request)
    second = await stub.place_bracket_order(request)
    assert first.ib_order_id == second.ib_order_id
    await stub.aclose()


# ---------------------------------------------------------------------------
# place_order_with_retry
# ---------------------------------------------------------------------------


class _FlakyClient:
    def __init__(self, *, fails: int, exc_type: type[BaseException]) -> None:
        self._fails = fails
        self._attempts = 0
        self._exc_type = exc_type

    def is_connected(self) -> bool:
        return True

    async def place_bracket_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        self._attempts += 1
        if self._attempts <= self._fails:
            raise self._exc_type("simulated transient")
        return PlaceOrderResult(
            order_ref=request.order_ref,
            ib_order_id="ok-1",
            accepted_at=datetime.now(UTC),
        )


async def test_place_order_with_retry_succeeds_after_retry() -> None:
    sleeps: list[float] = []

    async def _fake_sleep(d: float) -> None:
        sleeps.append(d)

    client = _FlakyClient(fails=2, exc_type=IBTransientError)
    request = PlaceOrderRequest(
        order_ref="retry-1",
        asset_class="stock",
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("1"),
        limit_price=Decimal("100"),
        stop_price=Decimal("95"),
    )
    result = await place_order_with_retry(client, request, initial_delay=1.0, sleep=_fake_sleep)
    assert result.ib_order_id == "ok-1"
    assert sleeps == [1.0, 2.0]


async def test_place_order_with_retry_terminal_short_circuits() -> None:
    sleeps: list[float] = []

    async def _fake_sleep(d: float) -> None:
        sleeps.append(d)

    class _TerminalClient:
        calls = 0

        def is_connected(self) -> bool:
            return True

        async def place_bracket_order(self, request):
            _TerminalClient.calls += 1
            raise IBTerminalError("Margin-Fehler", error_code=10318)

    request = PlaceOrderRequest(
        order_ref="term-1",
        asset_class="stock",
        symbol="BAD",
        side="BUY",
        quantity=Decimal("1"),
        limit_price=Decimal("100"),
        stop_price=Decimal("95"),
    )
    with pytest.raises(IBTerminalError):
        await place_order_with_retry(_TerminalClient(), request, max_attempts=5, sleep=_fake_sleep)
    assert _TerminalClient.calls == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# compute_preview
# ---------------------------------------------------------------------------


def _stock_form(**overrides: Any) -> QuickOrderForm:
    defaults = {
        "asset_class": "stock",
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": Decimal("100"),
        "limit_price": Decimal("185"),
        "stop_price": Decimal("180"),
    }
    defaults.update(overrides)
    return QuickOrderForm(**defaults)  # type: ignore[arg-type]


def _short_option_form(**overrides: Any) -> QuickOrderForm:
    defaults = {
        "asset_class": "option",
        "symbol": "SPY",
        "side": "SELL",
        "quantity": Decimal("5"),
        "limit_price": Decimal("3.20"),
        "stop_price": Decimal("1.60"),
        "option_expiry": date(2026, 5, 16),
        "option_strike": Decimal("450"),
        "option_right": "P",
        "option_multiplier": 100,
    }
    defaults.update(overrides)
    return QuickOrderForm(**defaults)  # type: ignore[arg-type]


async def test_compute_preview_stock_has_risk_no_margin() -> None:
    stub = StubIBQuickOrderClient()
    preview = await compute_preview(stub, _stock_form())
    # risk = 100 shares × $5 delta = $500
    assert preview.risk_estimate == Decimal("500")
    assert preview.margin is None
    assert preview.needs_acknowledge is False
    assert "AAPL" in preview.contract_label


async def test_compute_preview_short_option_requires_ack_and_shows_margin() -> None:
    stub = StubIBQuickOrderClient()
    preview = await compute_preview(stub, _short_option_form())
    # risk = 5 contracts × 100 multiplier × $1.60 delta = $800
    assert preview.risk_estimate == Decimal("800")
    assert preview.margin is not None
    assert preview.margin.initial_margin_change > 0
    assert preview.needs_acknowledge is True
    assert "SPY" in preview.contract_label
    assert "450" in preview.contract_label
    assert "P" in preview.contract_label


# ---------------------------------------------------------------------------
# submit_quick_order
# ---------------------------------------------------------------------------


async def test_submit_rejects_disconnected_client() -> None:
    stub = StubIBQuickOrderClient(connected=False)
    conn = _FakeConn()
    with pytest.raises(QuickOrderSubmitError, match="nicht verbunden"):
        await submit_quick_order(conn, stub, _stock_form())


async def test_submit_rejects_short_option_without_ack() -> None:
    stub = StubIBQuickOrderClient()
    conn = _FakeConn()
    with pytest.raises(QuickOrderSubmitError, match="Margin-Acknowledge"):
        await submit_quick_order(conn, stub, _short_option_form(acknowledge_margin=False))


async def test_submit_stock_happy_path_persists_row() -> None:
    stub = StubIBQuickOrderClient(fill_delay_seconds=0.01)
    conn = _FakeConn()
    result = await submit_quick_order(conn, stub, _stock_form())
    assert result.quick_order_id == 42
    assert result.order_ref.startswith("qo-")
    assert result.ib_order_id.startswith("stub-")
    # INSERT into quick_orders BEFORE the network call
    insert_calls = [c for c in conn.calls if "INSERT INTO quick_orders" in c[1]]
    assert len(insert_calls) == 1
    await stub.aclose()


async def test_submit_short_option_with_ack_succeeds() -> None:
    stub = StubIBQuickOrderClient(fill_delay_seconds=0.01)
    conn = _FakeConn()
    form = _short_option_form(acknowledge_margin=True)
    result = await submit_quick_order(conn, stub, form)
    assert result.quick_order_id == 42
    await stub.aclose()


# ---------------------------------------------------------------------------
# handle_fill_event — Story 12.3
# ---------------------------------------------------------------------------


async def test_handle_fill_event_creates_trade_with_auto_tagged_trigger_spec() -> None:
    quick_order_row = {
        "id": 42,
        "order_ref": "qo-abc",
        "asset_class": "stock",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": Decimal("100"),
        "limit_price": Decimal("185"),
        "stop_price": Decimal("180"),
        "option_expiry": None,
        "option_strike": None,
        "option_right": None,
        "option_multiplier": None,
        "ib_order_id": "stub-xyz",
        "status": "submitted",
        "strategy_id": 5,
        "trigger_source": "watchlist",
        "horizon": "swing",
        "notes": None,
        "margin_estimate": None,
    }
    conn = _FakeConn(canned={"fetchrow": quick_order_row})
    event = ExecutionEvent(
        order_ref="qo-abc",
        ib_order_id="stub-xyz",
        status="filled",
        filled_quantity=Decimal("100"),
        filled_price=Decimal("185"),
        execution_time=datetime(2026, 4, 14, tzinfo=UTC),
    )
    result = await handle_fill_event(conn, event)
    assert result["quick_order_id"] == 42
    assert result["status"] == "filled"
    assert result["trade_id"] == 999

    insert_trade = [c for c in conn.calls if "INSERT INTO trades" in c[1]]
    assert len(insert_trade) == 1
    _, _, args = insert_trade[0]
    # args[7] is the trigger_spec dict
    trigger_spec = args[7]
    assert trigger_spec["source"] == "quick_order"
    assert trigger_spec["asset_class"] == "stock"
    assert trigger_spec["horizon"] == "swing"
    assert trigger_spec["trigger_type"] == "watchlist"
    assert trigger_spec["strategy_id"] == 5


async def test_handle_fill_event_unknown_order_ref_noops() -> None:
    conn = _FakeConn(canned={"fetchrow": None})
    event = ExecutionEvent(
        order_ref="qo-ghost",
        ib_order_id="stub-none",
        status="filled",
        filled_quantity=Decimal("1"),
        filled_price=Decimal("1"),
        execution_time=datetime.now(UTC),
    )
    result = await handle_fill_event(conn, event)
    assert result == {"quick_order_id": None, "trade_id": None, "status": None}


async def test_handle_fill_event_partial_does_not_create_trade() -> None:
    quick_order_row = {
        "id": 42,
        "order_ref": "qo-partial",
        "asset_class": "stock",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": Decimal("100"),
        "limit_price": Decimal("185"),
        "stop_price": Decimal("180"),
        "option_expiry": None,
        "option_strike": None,
        "option_right": None,
        "option_multiplier": None,
        "ib_order_id": None,
        "status": "submitted",
        "strategy_id": None,
        "trigger_source": None,
        "horizon": None,
        "notes": None,
        "margin_estimate": None,
    }
    conn = _FakeConn(canned={"fetchrow": quick_order_row})
    event = ExecutionEvent(
        order_ref="qo-partial",
        ib_order_id="stub-partial",
        status="partial",
        filled_quantity=Decimal("20"),
        filled_price=Decimal("185"),
        execution_time=datetime.now(UTC),
    )
    result = await handle_fill_event(conn, event)
    assert result["status"] == "partial"
    assert result["trade_id"] is None
    assert not any("INSERT INTO trades" in c[1] for c in conn.calls)


# ---------------------------------------------------------------------------
# Tranche A patches (Epic 12 code review)
# ---------------------------------------------------------------------------


def test_retryable_exceptions_no_longer_include_connection_error() -> None:
    """Code-review BH-6: `IBTransientError` subclasses `ConnectionError`,
    so listing both was redundant."""

    from app.services.ib_quick_order import _RETRYABLE_EXCEPTIONS

    assert IBTransientError in _RETRYABLE_EXCEPTIONS
    assert ConnectionError not in _RETRYABLE_EXCEPTIONS
    assert TimeoutError in _RETRYABLE_EXCEPTIONS


def test_handle_fill_event_canonicalizes_horizon_to_swing_short() -> None:
    """Code-review EC-8: Quick-Order writes `horizon='swing_short'`
    when the form doesn't specify one — matches HORIZON_LABELS."""

    quick_order_row = {
        "id": 42,
        "order_ref": "qo-horizon",
        "asset_class": "stock",
        "symbol": "TSLA",
        "side": "buy",
        "quantity": Decimal("10"),
        "limit_price": Decimal("200"),
        "stop_price": Decimal("190"),
        "option_expiry": None,
        "option_strike": None,
        "option_right": None,
        "option_multiplier": None,
        "ib_order_id": None,
        "status": "submitted",
        "strategy_id": None,
        "trigger_source": None,
        "horizon": None,  # triggers the `or 'swing_short'` fallback
        "notes": None,
        "margin_estimate": None,
    }
    conn = _FakeConn(canned={"fetchrow": quick_order_row})
    event = ExecutionEvent(
        order_ref="qo-horizon",
        ib_order_id="stub-fill",
        status="filled",
        filled_quantity=Decimal("10"),
        filled_price=Decimal("200"),
        execution_time=datetime.now(UTC),
    )
    asyncio.run(handle_fill_event(conn, event))
    insert_call = next(c for c in conn.calls if "INSERT INTO trades" in c[1])
    trigger_spec = insert_call[2][7]  # position of trigger_spec dict
    assert trigger_spec["horizon"] == "swing_short"
    assert trigger_spec["source"] == "quick_order"


@pytest.mark.asyncio
async def test_sweep_orphan_quick_orders_returns_count() -> None:
    """Code-review BH-1 / EC-15: the startup sweep marks orphaned
    `submitted` rows as `rejected`."""

    from app.services.ib_quick_order import sweep_orphan_quick_orders

    class _SweepConn:
        def __init__(self) -> None:
            self.sql: str | None = None

        async def fetch(self, sql: str, *args: Any) -> list[Any]:
            self.sql = sql
            return [{"id": 1}, {"id": 2}]

    conn = _SweepConn()
    count = await sweep_orphan_quick_orders(conn)  # type: ignore[arg-type]
    assert count == 2
    assert conn.sql is not None
    assert "status = 'rejected'" in conn.sql
    assert "ib_order_id IS NULL" in conn.sql


def test_trigger_prose_renders_quick_order_pattern() -> None:
    """Code-review EC-7: `quick_order` trigger_type renders a
    dedicated Chef-authored prose line."""

    from app.services.trigger_prose import render_trigger_prose

    prose = render_trigger_prose(
        {
            "trigger_type": "quick_order",
            "source": "quick_order",
            "horizon": "swing_short",
        },
        trade={"symbol": "AAPL", "side": "buy"},
    )
    assert "Quick-Order" in prose
    assert "AAPL" in prose
    assert "Short Swing" in prose

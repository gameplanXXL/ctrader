"""Unit tests for Story 8.1 / 8.2 bot-execution service.

Covers:
- `map_ctrader_status` mapping + unknown fallback
- `place_order_with_retry` transient-retry loop with injected sleep
- `place_order_with_retry` terminal-error short-circuit
- `execute_proposal` happy path against `StubCTraderClient`
- `execute_proposal` idempotency via persisted `client_order_id`
- `handle_execution_event` trade-creation on FILLED
- `trigger_bot_execution` swallows exceptions (never re-raises)

Async DB interaction uses a small in-memory fake that records every
call — a real asyncpg mock would be heavier and wouldn't add coverage.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.clients.ctrader import (
    CTraderRateLimitError,
    CTraderTerminalError,
    CTraderTransientError,
    ExecutionEvent,
    PlaceOrderRequest,
    PlaceOrderResult,
    StubCTraderClient,
)
from app.models.proposal import (
    Proposal,
    ProposalStatus,
    RiskGateLevel,
)
from app.models.strategy import StrategyHorizon
from app.models.trade import TradeSide
from app.services.bot_execution import (
    execute_proposal,
    handle_execution_event,
    map_ctrader_status,
    place_order_with_retry,
    trigger_bot_execution,
)

# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _approved_proposal(
    *,
    id: int = 42,
    client_order_id: str | None = None,
    status: ProposalStatus = ProposalStatus.APPROVED,
) -> Proposal:
    return Proposal(
        id=id,
        agent_id="satoshi",
        strategy_id=5,
        symbol="BTCUSD",
        asset_class="crypto",
        side=TradeSide.BUY,
        horizon=StrategyHorizon.SWING_SHORT,
        entry_price=Decimal("68000"),
        stop_price=Decimal("66500"),
        target_price=Decimal("70200"),
        position_size=Decimal("0.5"),
        risk_budget=Decimal("250"),
        trigger_spec={"thesis": "unit-test"},
        risk_gate_result=RiskGateLevel.GREEN,
        status=status,
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
    )


class _FakeConn:
    """Tiny stand-in for asyncpg.Connection.

    Records every SQL + arg tuple so tests can assert on the call
    sequence. `canned_responses` lets a test pre-seed the answers for
    `fetchval` / `fetchrow`.
    """

    def __init__(self, canned: dict[str, list[Any]] | None = None) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._canned = canned or {}

    def _pop(self, key: str, default: Any = None) -> Any:
        bucket = self._canned.get(key)
        if not bucket:
            return default
        return bucket.pop(0)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchval", sql, args))
        key = _match_key(sql)
        return self._pop(f"fetchval:{key}")

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", sql, args))
        key = _match_key(sql)
        return self._pop(f"fetchrow:{key}")

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(("execute", sql, args))
        return "UPDATE 1"


def _match_key(sql: str) -> str:
    """Collapse SQL to a stable key for the canned-response lookup."""

    if "SELECT client_order_id" in sql:
        return "select_client_order_id"
    if "UPDATE proposals" in sql and "client_order_id = $1" in sql:
        return "update_client_order_id"
    if "UPDATE proposals" in sql and "execution_status" in sql:
        return "update_execution_status"
    if "SELECT id, agent_id" in sql:
        return "select_proposal_by_client_order_id"
    if "INSERT INTO trades" in sql:
        return "insert_trade"
    return "unknown"


# ---------------------------------------------------------------------------
# map_ctrader_status
# ---------------------------------------------------------------------------


def test_map_ctrader_status_known_values() -> None:
    assert map_ctrader_status("ORDER_STATUS_FILLED") == "filled"
    assert map_ctrader_status("ORDER_STATUS_REJECTED") == "rejected"
    assert map_ctrader_status("ORDER_STATUS_PARTIALLY_FILLED") == "partial"
    assert map_ctrader_status("submitted") == "submitted"


def test_map_ctrader_status_unknown_falls_back_to_submitted() -> None:
    """Unknown cTrader statuses must degrade — never raise."""

    assert map_ctrader_status("ORDER_STATUS_UNKNOWN_FUTURE_THING") == "submitted"


# ---------------------------------------------------------------------------
# place_order_with_retry
# ---------------------------------------------------------------------------


class _FlakyClient:
    """Raises a transient error N times before succeeding."""

    def __init__(self, *, fails: int, exc_type: type[BaseException]) -> None:
        self._fails = fails
        self._attempts = 0
        self._exc_type = exc_type

    async def place_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        self._attempts += 1
        if self._attempts <= self._fails:
            raise self._exc_type("simulated transient")
        return PlaceOrderResult(
            client_order_id=request.client_order_id,
            ctrader_order_id="ok-1",
            status="submitted",
            accepted_at=datetime.now(UTC),
        )


async def test_retry_eventually_succeeds() -> None:
    sleeps: list[float] = []

    async def _fake_sleep(d: float) -> None:
        sleeps.append(d)

    client = _FlakyClient(fails=2, exc_type=CTraderTransientError)
    request = PlaceOrderRequest(
        client_order_id="cid-1",
        symbol="BTCUSD",
        side="BUY",
        volume=Decimal("0.1"),
        limit_price=Decimal("68000"),
    )
    result = await place_order_with_retry(
        client, request, initial_delay=1.0, max_delay=10.0, sleep=_fake_sleep
    )
    assert result.ctrader_order_id == "ok-1"
    assert sleeps == [1.0, 2.0]  # exponential backoff kicked in


async def test_retry_exhausted_raises() -> None:
    sleeps: list[float] = []

    async def _fake_sleep(d: float) -> None:
        sleeps.append(d)

    client = _FlakyClient(fails=99, exc_type=CTraderRateLimitError)
    request = PlaceOrderRequest(
        client_order_id="cid-2",
        symbol="BTCUSD",
        side="BUY",
        volume=Decimal("0.1"),
    )
    with pytest.raises(CTraderRateLimitError):
        await place_order_with_retry(
            client, request, max_attempts=3, initial_delay=1.0, sleep=_fake_sleep
        )
    # 3 attempts → 2 sleeps (no sleep after the final failure).
    assert sleeps == [1.0, 2.0]


async def test_terminal_error_short_circuits() -> None:
    """Terminal errors must bypass the retry loop entirely."""

    class _TerminalClient:
        calls = 0

        async def place_order(self, request):
            _TerminalClient.calls += 1
            raise CTraderTerminalError("invalid symbol")

    sleeps: list[float] = []

    async def _fake_sleep(d: float) -> None:
        sleeps.append(d)

    request = PlaceOrderRequest(
        client_order_id="cid-3",
        symbol="BAD",
        side="BUY",
        volume=Decimal("0.1"),
    )
    with pytest.raises(CTraderTerminalError):
        await place_order_with_retry(_TerminalClient(), request, max_attempts=5, sleep=_fake_sleep)
    assert _TerminalClient.calls == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# execute_proposal — happy path + idempotency
# ---------------------------------------------------------------------------


async def test_execute_proposal_happy_path_via_stub() -> None:
    stub = StubCTraderClient(fill_delay_seconds=0.01)
    conn = _FakeConn(
        canned={
            "fetchval:select_client_order_id": [None, "proposal-42-xxxxxxxx"],
            "fetchval:update_client_order_id": [42],
        }
    )
    proposal = _approved_proposal()

    ctrader_order_id = await execute_proposal(conn, proposal, stub)

    assert ctrader_order_id is not None
    assert ctrader_order_id.startswith("stub-")
    # Execution status was persisted exactly once via UPDATE.
    update_calls = [c for c in conn.calls if "execution_status" in c[1] and c[0] == "execute"]
    assert len(update_calls) == 1

    await stub.aclose()


async def test_execute_proposal_skips_non_approved() -> None:
    stub = StubCTraderClient(fill_delay_seconds=0.01)
    conn = _FakeConn()
    proposal = _approved_proposal(status=ProposalStatus.PENDING)

    result = await execute_proposal(conn, proposal, stub)
    assert result is None
    assert conn.calls == []
    await stub.aclose()


async def test_execute_proposal_idempotent_when_order_exists() -> None:
    """A proposal already submitted (order_exists=True) must not be
    placed again. The stub's internal state acts as the source of truth.
    """

    stub = StubCTraderClient(fill_delay_seconds=0.01)

    # Seed the stub so `order_exists` returns True for the cached id.
    pre_request = PlaceOrderRequest(
        client_order_id="proposal-42-preseed",
        symbol="BTCUSD",
        side="BUY",
        volume=Decimal("0.5"),
        limit_price=Decimal("68000"),
    )
    await stub.place_order(pre_request)

    conn = _FakeConn(
        canned={
            "fetchval:select_client_order_id": ["proposal-42-preseed"],
        }
    )
    proposal = _approved_proposal()

    result = await execute_proposal(conn, proposal, stub)
    assert result is None  # already executed → skipped
    # No UPDATE to execution_status because we bailed before retry.
    assert not any("execution_status" in c[1] for c in conn.calls if c[0] == "execute")

    await stub.aclose()


# ---------------------------------------------------------------------------
# handle_execution_event — trade creation on FILLED
# ---------------------------------------------------------------------------


async def test_handle_execution_event_creates_trade_on_filled() -> None:
    proposal_row = {
        "id": 42,
        "agent_id": "satoshi",
        "strategy_id": 5,
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "side": "buy",
        "horizon": "swing_short",
        "entry_price": Decimal("68000"),
        "stop_price": Decimal("66500"),
        "target_price": Decimal("70200"),
        "position_size": Decimal("0.5"),
        "risk_budget": Decimal("250"),
        "trigger_spec": {"thesis": "unit-test"},
        "notes": None,
        "risk_gate_result": "green",
        "risk_gate_response": None,
        "status": "approved",
        "created_at": datetime(2026, 4, 14, tzinfo=UTC),
        "decided_at": datetime(2026, 4, 14, tzinfo=UTC),
        "decided_by": "chef",
        "client_order_id": "proposal-42-abc",
        "execution_status": "submitted",
    }
    conn = _FakeConn(
        canned={
            "fetchrow:select_proposal_by_client_order_id": [proposal_row],
            "fetchval:insert_trade": [999],
        }
    )

    event = ExecutionEvent(
        client_order_id="proposal-42-abc",
        ctrader_order_id="ctr-xyz",
        status="filled",
        filled_volume=Decimal("0.5"),
        filled_price=Decimal("68010"),
        execution_time=datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )
    result = await handle_execution_event(conn, event)

    assert result == {
        "proposal_id": 42,
        "execution_status": "filled",
        "trade_id": 999,
    }
    insert_calls = [c for c in conn.calls if "INSERT INTO trades" in c[1]]
    assert len(insert_calls) == 1
    # trigger_spec flows through as a dict — the asyncpg JSONB codec
    # (app/db/pool.py) json.dumps it at the driver level, so the
    # service layer must NOT pre-encode it or you get double-wrapping.
    _, _, args = insert_calls[0]
    assert args[7] == {"thesis": "unit-test"}


async def test_handle_execution_event_unknown_client_order_id() -> None:
    conn = _FakeConn(canned={"fetchrow:select_proposal_by_client_order_id": [None]})
    event = ExecutionEvent(
        client_order_id="ghost",
        ctrader_order_id="ctr-nope",
        status="filled",
        filled_volume=Decimal("1"),
        filled_price=Decimal("1"),
        execution_time=datetime.now(UTC),
    )
    result = await handle_execution_event(conn, event)
    assert result == {
        "proposal_id": None,
        "execution_status": None,
        "trade_id": None,
    }


async def test_handle_execution_event_partial_does_not_create_trade() -> None:
    proposal_row = {
        "id": 42,
        "agent_id": "satoshi",
        "strategy_id": None,
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "side": "buy",
        "horizon": "swing_short",
        "entry_price": Decimal("68000"),
        "stop_price": None,
        "target_price": None,
        "position_size": Decimal("0.5"),
        "risk_budget": Decimal("250"),
        "trigger_spec": None,
        "notes": None,
        "risk_gate_result": "green",
        "risk_gate_response": None,
        "status": "approved",
        "created_at": datetime.now(UTC),
        "decided_at": datetime.now(UTC),
        "decided_by": "chef",
        "client_order_id": "proposal-42-aaa",
        "execution_status": "partial",
    }
    conn = _FakeConn(canned={"fetchrow:select_proposal_by_client_order_id": [proposal_row]})
    event = ExecutionEvent(
        client_order_id="proposal-42-aaa",
        ctrader_order_id="ctr-partial",
        status="ORDER_STATUS_PARTIALLY_FILLED",
        filled_volume=Decimal("0.2"),
        filled_price=Decimal("68010"),
        execution_time=datetime.now(UTC),
    )
    result = await handle_execution_event(conn, event)
    assert result["execution_status"] == "partial"
    assert result["trade_id"] is None  # no INSERT into trades on partial
    assert not any("INSERT INTO trades" in c[1] for c in conn.calls)


# ---------------------------------------------------------------------------
# trigger_bot_execution — fire-and-forget contract
# ---------------------------------------------------------------------------


async def test_trigger_bot_execution_swallows_exceptions() -> None:
    """A raise inside `execute_proposal` must NOT propagate out of
    `trigger_bot_execution` — the approve endpoint has already returned
    200 and we cannot retroactively fail it.
    """

    class _BrokenPool:
        def acquire(self):
            raise RuntimeError("pool gone")

    # Must complete without raising.
    await trigger_bot_execution(
        _BrokenPool(),
        StubCTraderClient(),
        proposal_id=999,
    )


async def test_trigger_bot_execution_no_client_is_noop() -> None:
    """Missing cTrader client is logged but not an error."""

    await trigger_bot_execution(
        db_pool=object(),  # irrelevant because client is None
        client=None,
        proposal_id=42,
    )


# ---------------------------------------------------------------------------
# StubCTraderClient — sanity
# ---------------------------------------------------------------------------


async def test_stub_client_emits_fill_event() -> None:
    stub = StubCTraderClient(fill_delay_seconds=0.01)
    received: list[ExecutionEvent] = []

    async def handler(event: ExecutionEvent) -> None:
        received.append(event)

    await stub.subscribe_execution_events(handler)
    await stub.place_order(
        PlaceOrderRequest(
            client_order_id="cid-stub",
            symbol="BTCUSD",
            side="BUY",
            volume=Decimal("0.1"),
            limit_price=Decimal("70000"),
        )
    )
    await asyncio.sleep(0.05)  # give the synthetic fill task a chance
    assert len(received) == 1
    assert received[0].status == "filled"
    assert received[0].filled_volume == Decimal("0.1")
    await stub.aclose()


async def test_stub_client_place_order_is_idempotent() -> None:
    stub = StubCTraderClient(fill_delay_seconds=0.01)
    request = PlaceOrderRequest(
        client_order_id="cid-dup",
        symbol="BTCUSD",
        side="BUY",
        volume=Decimal("0.1"),
        limit_price=Decimal("70000"),
    )
    first = await stub.place_order(request)
    second = await stub.place_order(request)
    assert first.ctrader_order_id == second.ctrader_order_id
    await stub.aclose()

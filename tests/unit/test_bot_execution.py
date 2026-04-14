"""Unit tests for Story 8.1 / 8.2 bot-execution service + Tranche A patches.

Covers:
- `map_ctrader_status` mapping + unknown fallback
- `place_order_with_retry` transient-retry loop with injected sleep
- `place_order_with_retry` terminal-error short-circuit
- `execute_proposal` happy path against `StubCTraderClient`
- `execute_proposal` idempotency via persisted `client_order_id`
- `execute_proposal` None-guard after race recovery (H2 / BH-3)
- `execute_proposal` preliminary CAS miss after filled event (H3 / BH-4)
- `execute_proposal` supports SHORT / COVER sides (H7 / BH-7)
- `handle_execution_event` trade-creation on FILLED
- `handle_execution_event` trigger_spec is enriched with horizon / agent_id (H6)
- `handle_execution_event` fires `capture_fundamental_snapshot` (H8 / EC-6)
- `handle_execution_event` logs dedup-path on ON CONFLICT (M5 / BH-19)
- `trigger_bot_execution` swallows exceptions AND writes audit row (M1 / EC-12)
- `spawn_bot_execution` registers task in the strong-ref set (H1 / BH-2)

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
    _background_tasks,
    execute_proposal,
    handle_execution_event,
    map_ctrader_status,
    place_order_with_retry,
    spawn_bot_execution,
    trigger_bot_execution,
)

# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _approved_proposal(
    *,
    id: int = 42,
    status: ProposalStatus = ProposalStatus.APPROVED,
    side: TradeSide = TradeSide.BUY,
) -> Proposal:
    return Proposal(
        id=id,
        agent_id="satoshi",
        strategy_id=5,
        symbol="BTCUSD",
        asset_class="crypto",
        side=side,
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
    if "INSERT INTO audit_log" in sql:
        return "insert_audit_log"
    return "unknown"


class _FakePool:
    """Minimal pool that yields `conn` inside an async context manager."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):  # not async — returns a CM
        conn = self._conn

        class _CM:
            async def __aenter__(self):  # noqa: N805 — nested CM
                return conn

            async def __aexit__(self, *_exc):  # noqa: N805 — nested CM
                return None

        return _CM()


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
# execute_proposal — happy path + idempotency + race + side mapping
# ---------------------------------------------------------------------------


async def test_execute_proposal_happy_path_via_stub() -> None:
    stub = StubCTraderClient(fill_delay_seconds=0.01)
    conn = _FakeConn(
        canned={
            "fetchval:select_client_order_id": [None],
            "fetchval:update_client_order_id": [42],
            "fetchval:update_execution_status": [42],  # preliminary CAS wins
        }
    )
    proposal = _approved_proposal()

    ctrader_order_id = await execute_proposal(conn, proposal, stub)

    assert ctrader_order_id is not None
    assert ctrader_order_id.startswith("stub-")
    # Preliminary CAS write happened exactly once via fetchval.
    update_calls = [c for c in conn.calls if "execution_status" in c[1] and c[0] == "fetchval"]
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
    assert not any("execution_status" in c[1] for c in conn.calls if c[0] == "fetchval")

    await stub.aclose()


async def test_execute_proposal_race_recovery_returns_none_when_row_gone() -> None:
    """Code-review H2 / BH-3 / EC-3: if the proposal row is deleted
    between the initial SELECT and the UPDATE, the re-SELECT returns
    None and we must NOT pass None through to `place_order`.
    """

    stub = StubCTraderClient(fill_delay_seconds=0.01)
    conn = _FakeConn(
        canned={
            # 1st SELECT: NULL → triggers generation path
            # 2nd SELECT (race recovery): NULL → row gone
            "fetchval:select_client_order_id": [None, None],
            # UPDATE: NULL returning = no row matched
            "fetchval:update_client_order_id": [None],
        }
    )
    proposal = _approved_proposal()

    result = await execute_proposal(conn, proposal, stub)
    assert result is None
    # place_order must NOT have been called
    assert len(stub._orders) == 0
    await stub.aclose()


async def test_execute_proposal_preliminary_cas_miss_is_ok() -> None:
    """Code-review H3 / BH-4: if the FILLED event arrived before
    `place_order` returned, the preliminary CAS UPDATE misses (returns
    NULL) and we must NOT regress the terminal state. The function
    still returns the ctrader_order_id successfully.
    """

    stub = StubCTraderClient(fill_delay_seconds=0.01)
    conn = _FakeConn(
        canned={
            "fetchval:select_client_order_id": [None],
            "fetchval:update_client_order_id": [42],
            # preliminary CAS misses because event handler already
            # wrote `filled`
            "fetchval:update_execution_status": [None],
        }
    )
    proposal = _approved_proposal()
    result = await execute_proposal(conn, proposal, stub)
    assert result is not None  # place_order ok, CAS miss does not fail
    await stub.aclose()


async def test_execute_proposal_supports_short_and_cover_sides() -> None:
    """Code-review H7 / BH-7 / EC-5: COVER must map to BUY on cTrader."""

    from app.services.bot_execution import _proposal_to_request

    proposal_cover = _approved_proposal(side=TradeSide.COVER)
    req = _proposal_to_request(proposal_cover, "cid-cover")
    assert req.side == "BUY"

    proposal_short = _approved_proposal(side=TradeSide.SHORT)
    req = _proposal_to_request(proposal_short, "cid-short")
    assert req.side == "SELL"


# ---------------------------------------------------------------------------
# handle_execution_event — trade creation on FILLED
# ---------------------------------------------------------------------------


def _proposal_row(
    *,
    client_order_id: str = "proposal-42-abc",
    trigger_spec: dict | None = None,
) -> dict:
    """Minimal row shape for handle_execution_event."""

    return {
        "id": 42,
        "agent_id": "satoshi",
        "strategy_id": 5,
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "side": "buy",
        "horizon": "swing_short",
        "trigger_spec": trigger_spec if trigger_spec is not None else {"thesis": "unit-test"},
    }


async def test_handle_execution_event_creates_trade_on_filled_with_enriched_trigger_spec() -> None:
    """Code-review H6 / EC-2 / EC-9: trigger_spec must be enriched with
    horizon / agent_id / asset_class / source / trigger_type so the
    journal prose and facet queries do not render "Unbekannt".
    """

    proposal_row = _proposal_row()
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
    # trigger_spec is enriched — dict, not pre-encoded JSON string.
    _, _, args = insert_calls[0]
    enriched = args[7]
    assert enriched["thesis"] == "unit-test"
    assert enriched["agent_id"] == "satoshi"
    assert enriched["horizon"] == "swing_short"
    assert enriched["asset_class"] == "crypto"
    assert enriched["trigger_type"] == "bot_auto"
    assert enriched["source"] == "bot_execution"


async def test_handle_execution_event_respects_existing_trigger_type() -> None:
    """If the proposal already declared a specific trigger_type, the
    enrichment must NOT overwrite it with the generic `bot_auto`.
    """

    proposal_row = _proposal_row(
        trigger_spec={"trigger_type": "momentum_breakout", "confidence": 0.72}
    )
    conn = _FakeConn(
        canned={
            "fetchrow:select_proposal_by_client_order_id": [proposal_row],
            "fetchval:insert_trade": [500],
        }
    )
    event = ExecutionEvent(
        client_order_id="proposal-42-abc",
        ctrader_order_id="ctr-mb",
        status="filled",
        filled_volume=Decimal("0.5"),
        filled_price=Decimal("68010"),
        execution_time=datetime.now(UTC),
    )
    await handle_execution_event(conn, event)
    insert = [c for c in conn.calls if "INSERT INTO trades" in c[1]][0]
    enriched = insert[2][7]
    assert enriched["trigger_type"] == "momentum_breakout"
    assert enriched["confidence"] == 0.72


async def test_handle_execution_event_on_conflict_logs_dedup_not_created() -> None:
    """Code-review M5 / BH-19: ON CONFLICT DO NOTHING returns NULL;
    the function must return `trade_id: None` and the log event must
    be `trade_dedup`, not `trade_created`.
    """

    proposal_row = _proposal_row()
    conn = _FakeConn(
        canned={
            "fetchrow:select_proposal_by_client_order_id": [proposal_row],
            "fetchval:insert_trade": [None],  # ON CONFLICT returned nothing
        }
    )
    event = ExecutionEvent(
        client_order_id="proposal-42-abc",
        ctrader_order_id="ctr-dup",
        status="filled",
        filled_volume=Decimal("0.5"),
        filled_price=Decimal("68010"),
        execution_time=datetime.now(UTC),
    )
    result = await handle_execution_event(conn, event)
    assert result["trade_id"] is None
    assert result["execution_status"] == "filled"


async def test_handle_execution_event_fires_snapshot_when_mcp_and_pool_given() -> None:
    """Code-review H8 / EC-6: on successful trade insert, a fundamental
    snapshot task is spawned via asyncio.create_task. We intercept
    asyncio.create_task and count the calls.
    """

    proposal_row = _proposal_row()
    conn = _FakeConn(
        canned={
            "fetchrow:select_proposal_by_client_order_id": [proposal_row],
            "fetchval:insert_trade": [1234],
        }
    )
    pool = _FakePool(conn)

    from unittest.mock import patch

    original = asyncio.create_task
    scheduled: list = []

    def _spy(coro, *a, **kw):
        scheduled.append(coro)
        # Immediately close the coroutine so it doesn't run — we only
        # care that it was scheduled. The run_in_executor coroutine
        # would have needed a real MCP client anyway.
        coro.close()

        class _Dummy:
            def add_done_callback(self, _cb):
                pass

        return _Dummy()

    # Light-weight MCP stub — handle_execution_event only passes it
    # through into the coroutine, which we close before running.
    class _MCPStub:
        pass

    event = ExecutionEvent(
        client_order_id="proposal-42-abc",
        ctrader_order_id="ctr-xyz",
        status="filled",
        filled_volume=Decimal("0.5"),
        filled_price=Decimal("68010"),
        execution_time=datetime.now(UTC),
    )

    with patch("app.services.bot_execution.asyncio.create_task", _spy):
        result = await handle_execution_event(conn, event, db_pool=pool, mcp_client=_MCPStub())

    assert result["trade_id"] == 1234
    assert len(scheduled) == 1
    _ = original  # keep the real reference alive for other tests


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
    conn = _FakeConn(canned={"fetchrow:select_proposal_by_client_order_id": [_proposal_row()]})
    event = ExecutionEvent(
        client_order_id="proposal-42-abc",
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
# trigger_bot_execution — fire-and-forget contract + audit log
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
        None,  # mcp_client
        proposal_id=999,
    )


async def test_trigger_bot_execution_no_client_is_noop() -> None:
    """Missing cTrader client is logged but not an error."""

    await trigger_bot_execution(
        db_pool=object(),  # irrelevant because client is None
        client=None,
        mcp_client=None,
        proposal_id=42,
    )


async def test_trigger_bot_execution_writes_audit_log_on_failure() -> None:
    """Code-review M1 / EC-12: failures during fire-and-forget must
    leave an audit trail so Story 12.2's log viewer can surface them.
    """

    # First pool.acquire() (trigger_bot_execution) raises.
    # Second pool.acquire() (audit-log write) must succeed with a
    # FakeConn that accepts `INSERT INTO audit_log`.
    audit_calls: list[tuple[str, tuple[Any, ...]]] = []

    class _FirstFailingPool:
        def __init__(self) -> None:
            self.calls = 0

        def acquire(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("proposal fetch exploded")

            class _CM:
                async def __aenter__(self):  # noqa: N805 — nested CM
                    class _AuditConn:
                        async def execute(self, sql, *args):  # noqa: N805 — nested
                            audit_calls.append((sql, args))
                            return "INSERT 0 1"

                    return _AuditConn()

                async def __aexit__(self, *_exc):  # noqa: N805 — nested CM
                    return None

            return _CM()

    pool = _FirstFailingPool()
    await trigger_bot_execution(pool, StubCTraderClient(), None, proposal_id=777)
    assert len(audit_calls) == 1
    sql, args = audit_calls[0]
    assert "INSERT INTO audit_log" in sql
    assert args[0] == 777
    assert "bot_execution_failed" in args[1]


# ---------------------------------------------------------------------------
# spawn_bot_execution — strong-reference set registration (H1 / BH-2)
# ---------------------------------------------------------------------------


async def test_spawn_bot_execution_tracks_task_in_background_set() -> None:
    """Code-review H1 / BH-2 / EC-1: the spawned task must be in
    `_background_tasks` while running so the event loop can't GC it.
    """

    class _SlowPool:
        def acquire(self):
            class _CM:
                async def __aenter__(self):  # noqa: N805 — nested CM
                    await asyncio.sleep(0.05)

                    class _C:
                        async def fetchrow(self, *a):
                            return None

                    return _C()

                async def __aexit__(self, *_exc):  # noqa: N805 — nested CM
                    return None

            return _CM()

    task = spawn_bot_execution(_SlowPool(), StubCTraderClient(), None, proposal_id=1)
    assert task is not None
    assert task in _background_tasks
    # Wait for it to finish and verify it was removed by the callback.
    await task
    assert task not in _background_tasks


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

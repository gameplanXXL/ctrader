"""Unit tests for Epic 9 — regime snapshots + kill switch.

Covers:
- `fetch_fear_greed` happy path + failure fallback
- `fetch_vix` happy path + failure fallback
- `compute_per_broker_pnl` empty + populated
- `create_regime_snapshot` happy path + partial-failure persistence
- `evaluate_kill_switch` pause + recover + None-noop
- `manual_override` success + wrong-state rejection
- `get_current_regime` empty + populated view-model
- `RegimeSnapshot.is_kill_switch_regime` threshold

The database layer is stubbed with `_FakeConn` / `_FakePool` — same
style as `test_bot_execution.py` — so every test runs in milliseconds
without touching a real Postgres.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.models.regime import (
    KILL_SWITCH_THRESHOLD,
    RegimeSnapshot,
    fear_greed_classification,
)
from app.services.fear_greed import fetch_fear_greed, fetch_vix
from app.services.kill_switch import (
    KillSwitchResult,
    StrategyNotPausedByKillSwitchError,
    evaluate_kill_switch,
    manual_override,
)
from app.services.regime import get_current_regime
from app.services.regime_snapshot import (
    compute_per_broker_pnl,
    create_regime_snapshot,
)

# ---------------------------------------------------------------------------
# httpx MockTransport helpers
# ---------------------------------------------------------------------------


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# RegimeSnapshot model
# ---------------------------------------------------------------------------


def test_fear_greed_classification_buckets() -> None:
    assert fear_greed_classification(5) == "Extreme Fear"
    assert fear_greed_classification(30) == "Fear"
    assert fear_greed_classification(52) == "Neutral"
    assert fear_greed_classification(60) == "Greed"
    assert fear_greed_classification(90) == "Extreme Greed"
    assert fear_greed_classification(None) == "Unbekannt"


def test_snapshot_kill_switch_threshold() -> None:
    snap = RegimeSnapshot(
        id=1,
        fear_greed_index=15,
        vix=Decimal("28.50"),
        per_broker_pnl={},
        created_at=datetime.now(UTC),
    )
    assert snap.is_kill_switch_regime is True
    assert snap.fg_classification == "Extreme Fear"

    calm = RegimeSnapshot(
        id=2,
        fear_greed_index=50,
        vix=Decimal("14.00"),
        per_broker_pnl={},
        created_at=datetime.now(UTC),
    )
    assert calm.is_kill_switch_regime is False

    no_data = RegimeSnapshot(
        id=3,
        fear_greed_index=None,
        vix=None,
        per_broker_pnl={},
        created_at=datetime.now(UTC),
    )
    assert no_data.is_kill_switch_regime is False


# ---------------------------------------------------------------------------
# fetch_fear_greed
# ---------------------------------------------------------------------------


async def test_fetch_fear_greed_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "value": "42",
                        "value_classification": "Neutral",
                        "timestamp": "1739491200",
                    }
                ]
            },
        )

    async with _mock_client(handler) as client:
        value, err = await fetch_fear_greed(client)
    assert value == 42
    assert err is None


async def test_fetch_fear_greed_http_error_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    async with _mock_client(handler) as client:
        value, err = await fetch_fear_greed(client)
    assert value is None
    assert err is not None


async def test_fetch_fear_greed_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    async with _mock_client(handler) as client:
        value, err = await fetch_fear_greed(client)
    assert value is None
    assert "empty" in err.lower()


async def test_fetch_fear_greed_out_of_range() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"value": "999"}]})

    async with _mock_client(handler) as client:
        value, err = await fetch_fear_greed(client)
    assert value is None
    assert "out of range" in err


# ---------------------------------------------------------------------------
# fetch_vix
# ---------------------------------------------------------------------------


async def test_fetch_vix_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "chart": {"result": [{"indicators": {"quote": [{"close": [18.35, 19.12, 20.48]}]}}]}
            },
        )

    async with _mock_client(handler) as client:
        value, err = await fetch_vix(client)
    assert value == Decimal("20.48")
    assert err is None


async def test_fetch_vix_only_nulls_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"chart": {"result": [{"indicators": {"quote": [{"close": [None, None]}]}}]}},
        )

    async with _mock_client(handler) as client:
        value, err = await fetch_vix(client)
    assert value is None
    assert "nulls" in err


async def test_fetch_vix_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with _mock_client(handler) as client:
        value, err = await fetch_vix(client)
    assert value is None
    assert err is not None


# ---------------------------------------------------------------------------
# DB stubs for service tests
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._canned = canned or {}

    def _pop(self, key: str, default: Any = None) -> Any:
        bucket = self._canned.get(key)
        if bucket is None:
            return default
        if isinstance(bucket, list):
            return bucket.pop(0) if bucket else default
        return bucket

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchval", sql, args))
        return self._pop(_match_key(sql))

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", sql, args))
        return self._pop(_match_key(sql))

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        # `fetch()` returns a list — do NOT pop individual rows off,
        # return the whole canned value so the test can pass multi-row
        # results as a plain list[dict].
        self.calls.append(("fetch", sql, args))
        key = _match_key(sql)
        return self._canned.get(key, [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(("execute", sql, args))
        return "OK 1"

    def transaction(self):
        """No-op async CM so service code under test can call
        `async with conn.transaction():` without patching asyncpg."""

        class _Txn:
            async def __aenter__(self):  # noqa: N805 — nested CM
                return None

            async def __aexit__(self, *_exc):  # noqa: N805 — nested CM
                return None

        return _Txn()


def _match_key(sql: str) -> str:
    if "jsonb_object_agg(broker" in sql:
        return "per_broker_pnl"
    if "INSERT INTO regime_snapshots" in sql:
        return "insert_snapshot"
    if "FROM regime_snapshots" in sql and "ORDER BY" in sql:
        return "latest_snapshot"
    if "UPDATE strategies" in sql and "SET status = 'paused'::strategy_status" in sql:
        return "pause_strategies"
    if (
        "UPDATE strategies" in sql
        and "SET status = 'active'::strategy_status" in sql
        and "paused_by = 'kill_switch'" in sql
    ):
        if "WHERE id = $1" in sql:
            return "override_strategy"
        return "recover_strategies"
    if "SELECT id, name, horizon" in sql:
        return "paused_list"
    if "FROM audit_log al" in sql:
        return "override_history"
    if "INSERT INTO audit_log" in sql:
        return "insert_audit_log"
    return "unknown"


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _CM:
            async def __aenter__(self):  # noqa: N805
                return conn

            async def __aexit__(self, *_exc):  # noqa: N805
                return None

        return _CM()


# ---------------------------------------------------------------------------
# compute_per_broker_pnl
# ---------------------------------------------------------------------------


async def test_compute_per_broker_pnl_empty() -> None:
    conn = _FakeConn(canned={"per_broker_pnl": {}})
    result = await compute_per_broker_pnl(conn)
    assert result == {}


async def test_compute_per_broker_pnl_stringifies_decimals() -> None:
    conn = _FakeConn(
        canned={"per_broker_pnl": {"ib": Decimal("1234.56"), "ctrader": Decimal("-78.90")}}
    )
    result = await compute_per_broker_pnl(conn)
    assert result == {"ib": "1234.56", "ctrader": "-78.90"}


# ---------------------------------------------------------------------------
# create_regime_snapshot
# ---------------------------------------------------------------------------


async def test_create_regime_snapshot_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "fng" in str(request.url):
            return httpx.Response(200, json={"data": [{"value": "42"}]})
        return httpx.Response(
            200,
            json={"chart": {"result": [{"indicators": {"quote": [{"close": [19.5, 20.1]}]}}]}},
        )

    conn = _FakeConn(
        canned={
            "per_broker_pnl": {"ib": Decimal("100")},
            "insert_snapshot": {
                "id": 7,
                "created_at": datetime(2026, 4, 14, tzinfo=UTC),
            },
        }
    )
    pool = _FakePool(conn)

    async with _mock_client(handler) as client:
        snapshot = await create_regime_snapshot(pool, http_client=client)

    assert snapshot.id == 7
    assert snapshot.fear_greed_index == 42
    assert snapshot.vix == Decimal("20.10")
    assert snapshot.per_broker_pnl == {"ib": "100"}
    assert snapshot.fetch_errors is None


async def test_create_regime_snapshot_persists_despite_fetch_errors() -> None:
    """Story 9.1 AC #3: snapshot row is written even when data sources fail."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    conn = _FakeConn(
        canned={
            "per_broker_pnl": {},
            "insert_snapshot": {
                "id": 8,
                "created_at": datetime(2026, 4, 14, tzinfo=UTC),
            },
        }
    )
    pool = _FakePool(conn)

    async with _mock_client(handler) as client:
        snapshot = await create_regime_snapshot(pool, http_client=client)

    assert snapshot.id == 8
    assert snapshot.fear_greed_index is None
    assert snapshot.vix is None
    assert snapshot.fetch_errors is not None
    assert "fear_greed" in snapshot.fetch_errors
    assert "vix" in snapshot.fetch_errors


# ---------------------------------------------------------------------------
# evaluate_kill_switch
# ---------------------------------------------------------------------------


async def test_evaluate_kill_switch_pauses_short_horizons_below_threshold() -> None:
    conn = _FakeConn(
        canned={
            "pause_strategies": [
                {"id": 1, "name": "Intraday Scalp"},
                {"id": 2, "name": "Swing Short Break"},
            ]
        }
    )
    result = await evaluate_kill_switch(conn, fear_greed_index=15)

    assert result.action == "pause"
    assert result.paused_ids == [1, 2]
    assert result.recovered_ids == []
    # Two audit-log inserts (one per paused strategy)
    audit_calls = [c for c in conn.calls if "INSERT INTO audit_log" in c[1]]
    assert len(audit_calls) == 2


async def test_evaluate_kill_switch_recovers_above_threshold() -> None:
    conn = _FakeConn(
        canned={
            "recover_strategies": [{"id": 3, "name": "Previously Paused"}],
        }
    )
    result = await evaluate_kill_switch(conn, fear_greed_index=45)

    assert result.action == "recover"
    assert result.recovered_ids == [3]
    assert result.paused_ids == []
    audit_calls = [c for c in conn.calls if "INSERT INTO audit_log" in c[1]]
    assert len(audit_calls) == 1


async def test_evaluate_kill_switch_noop_when_fg_is_none() -> None:
    """Missing data source must never pause or recover anything."""

    conn = _FakeConn()
    result = await evaluate_kill_switch(conn, fear_greed_index=None)
    assert result.action == "noop"
    assert conn.calls == []  # no SQL at all


async def test_evaluate_kill_switch_at_exact_threshold_recovers() -> None:
    """F&G == threshold (20) is the recovery boundary — NOT a pause."""

    conn = _FakeConn(canned={"recover_strategies": []})
    result = await evaluate_kill_switch(conn, fear_greed_index=KILL_SWITCH_THRESHOLD)
    assert result.action == "noop"  # nothing to recover, but still the recover branch
    assert result.paused_ids == []


# ---------------------------------------------------------------------------
# manual_override
# ---------------------------------------------------------------------------


async def test_manual_override_reactivates_kill_switch_paused() -> None:
    conn = _FakeConn(canned={"override_strategy": {"id": 5, "name": "Momentum Intraday"}})
    result = await manual_override(conn, 5)
    assert result == {"id": 5, "name": "Momentum Intraday"}
    # One audit-log row with event_type='kill_switch_overridden'
    audit_calls = [c for c in conn.calls if "INSERT INTO audit_log" in c[1]]
    assert len(audit_calls) == 1
    _, _, args = audit_calls[0]
    assert args[0] == "kill_switch_overridden"
    assert args[3] == "chef"


async def test_manual_override_rejects_non_kill_switch_paused() -> None:
    conn = _FakeConn(canned={"override_strategy": None})
    with pytest.raises(StrategyNotPausedByKillSwitchError):
        await manual_override(conn, 99)
    # No audit row written on failure
    assert not any("INSERT INTO audit_log" in c[1] for c in conn.calls)


async def test_manual_override_audit_row_omits_none_fear_greed_index() -> None:
    """Code-review H1 / BH-1 / BH-2: the kill_switch_overridden audit
    row must NOT carry a JSON-null `fear_greed_index` key, otherwise
    the regime-history SELECT's text-cast blows up on the literal
    `'null'` string.
    """

    conn = _FakeConn(canned={"override_strategy": {"id": 5, "name": "Test"}})
    await manual_override(conn, 5)
    audit_calls = [c for c in conn.calls if "INSERT INTO audit_log" in c[1]]
    assert len(audit_calls) == 1
    _, _, args = audit_calls[0]
    # args[2] is override_flags dict
    override_flags = args[2]
    assert "fear_greed_index" not in override_flags
    assert override_flags["action"] == "manual_override"


async def test_evaluate_kill_switch_pause_audit_flags_include_fg() -> None:
    """Mirror of the above: pause events DO carry fear_greed_index."""

    conn = _FakeConn(canned={"pause_strategies": [{"id": 1, "name": "Scalp"}]})
    await evaluate_kill_switch(conn, fear_greed_index=12)
    audit_calls = [c for c in conn.calls if "INSERT INTO audit_log" in c[1]]
    assert len(audit_calls) == 1
    override_flags = audit_calls[0][2][2]
    assert override_flags["fear_greed_index"] == 12
    assert override_flags["action"] == "pause"


# ---------------------------------------------------------------------------
# get_current_regime (view-model assembly)
# ---------------------------------------------------------------------------


async def test_get_current_regime_empty_database() -> None:
    conn = _FakeConn(
        canned={
            "latest_snapshot": None,
            "paused_list": [],
            "override_history": [],
        }
    )
    view = await get_current_regime(conn)
    assert view.snapshot is None
    assert view.paused_strategies == []
    assert view.override_history == []
    assert view.kill_switch_active is False
    assert view.paused_count == 0


async def test_get_current_regime_populated() -> None:
    conn = _FakeConn(
        canned={
            "latest_snapshot": {
                "id": 10,
                "fear_greed_index": 15,
                "vix": Decimal("28.40"),
                "per_broker_pnl": {"ib": "500"},
                "fetch_errors": None,
                "created_at": datetime(2026, 4, 14, tzinfo=UTC),
            },
            "paused_list": [
                {
                    "id": 1,
                    "name": "Intraday Scalp",
                    "horizon": "intraday",
                    "asset_class": "crypto",
                    "updated_at": datetime(2026, 4, 14, tzinfo=UTC),
                }
            ],
            "override_history": [
                {
                    "id": 100,
                    "created_at": datetime(2026, 4, 13, tzinfo=UTC),
                    "event_type": "kill_switch_triggered",
                    "strategy_id": 1,
                    "strategy_name": "Intraday Scalp",
                    "actor": "kill_switch",
                    "action": "pause",
                    "fear_greed_index": 15,
                    "notes": "Auto-pause: Fear & Greed = 15",
                }
            ],
        }
    )
    view = await get_current_regime(conn)
    assert view.snapshot is not None
    assert view.snapshot.fear_greed_index == 15
    assert view.kill_switch_active is True
    assert view.fg_classification == "Extreme Fear"
    assert view.paused_count == 1
    assert view.paused_strategies[0].name == "Intraday Scalp"
    assert len(view.override_history) == 1
    assert view.override_history[0].action == "pause"


# ---------------------------------------------------------------------------
# KillSwitchResult dataclass
# ---------------------------------------------------------------------------


def test_kill_switch_result_dataclass() -> None:
    r = KillSwitchResult(fear_greed_index=10, action="pause", paused_ids=[1, 2], recovered_ids=[])
    assert r.fear_greed_index == 10
    assert r.action == "pause"

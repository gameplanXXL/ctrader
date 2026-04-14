"""Unit tests for Epic 10 — Gordon Trend-Radar.

Covers:
- `HotPick` / `GordonSnapshot` model edge cases (`is_stale`, `has_error`)
- `compute_diff` new / dropped / unchanged keying by symbol
- `_parse_hot_picks` schema-surprise paths (direct, content[0], legacy text)
- `fetch_gordon_trend_radar` happy path + MCP failure modes
- `persist_snapshot` hydrates a `GordonSnapshot`
- `fetch_and_persist` always writes a row (AC #3 "no silent failure")

Database layer is stubbed with `_FakeConn` / `_FakePool` — same pattern
as `test_regime.py` / `test_bot_execution.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

from app.models.gordon import GordonDiff, GordonSnapshot, HotPick
from app.services.gordon import (
    _parse_hot_picks,
    compute_diff,
    fetch_and_persist,
    fetch_gordon_trend_radar,
    persist_snapshot,
)

# ---------------------------------------------------------------------------
# DB stubs
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, canned: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self._canned = canned or {}

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", sql, args))
        if "INSERT INTO gordon_snapshots" in sql:
            # Return a synthetic row using the args we were passed
            return {
                "id": 42,
                "snapshot_data": args[0],
                "hot_picks": args[1],
                "source_error": args[2],
                "created_at": datetime(2026, 4, 14, tzinfo=UTC),
            }
        return self._canned.get("row")

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", sql, args))
        return self._canned.get("rows", [])


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
# HotPick / GordonSnapshot models
# ---------------------------------------------------------------------------


def test_hot_pick_accepts_extras_without_crashing() -> None:
    """Gordon's MCP schema may grow — extras must be ignored, not raise."""

    pick = HotPick.model_validate(
        {
            "symbol": "NVDA",
            "rank": 1,
            "horizon": "swing_short",
            "confidence": 0.85,
            "thesis": "AI demand",
            "entry_zone": [Decimal("890"), Decimal("920")],
            "target": Decimal("1050"),
            "future_field": "this should be ignored",
        }
    )
    assert pick.symbol == "NVDA"
    assert pick.confidence == 0.85


def test_gordon_snapshot_is_stale_after_7_days() -> None:
    created = datetime.now(UTC) - timedelta(days=8)
    snap = GordonSnapshot(
        id=1, snapshot_data={}, hot_picks=[], source_error=None, created_at=created
    )
    assert snap.is_stale is True


def test_gordon_snapshot_fresh_not_stale() -> None:
    snap = GordonSnapshot(
        id=2,
        snapshot_data={},
        hot_picks=[HotPick(symbol="NVDA")],
        source_error=None,
        created_at=datetime.now(UTC),
    )
    assert snap.is_stale is False
    assert snap.has_error is False


def test_gordon_snapshot_has_error_when_empty_picks() -> None:
    snap = GordonSnapshot(
        id=3,
        snapshot_data={},
        hot_picks=[],
        source_error=None,
        created_at=datetime.now(UTC),
    )
    assert snap.has_error is True


def test_gordon_snapshot_has_error_when_source_error_set() -> None:
    snap = GordonSnapshot(
        id=4,
        snapshot_data={},
        hot_picks=[HotPick(symbol="NVDA")],
        source_error="connection_refused",
        created_at=datetime.now(UTC),
    )
    assert snap.has_error is True


# ---------------------------------------------------------------------------
# _parse_hot_picks — schema-surprise resilience
# ---------------------------------------------------------------------------


def test_parse_hot_picks_direct_path() -> None:
    payload = {
        "result": {
            "hot_picks": [{"symbol": "NVDA"}, {"symbol": "BTCUSD"}],
        }
    }
    assert _parse_hot_picks(payload) == [{"symbol": "NVDA"}, {"symbol": "BTCUSD"}]


def test_parse_hot_picks_content_wrapped() -> None:
    payload = {
        "result": {
            "content": [{"hot_picks": [{"symbol": "NVDA"}]}],
        }
    }
    assert _parse_hot_picks(payload) == [{"symbol": "NVDA"}]


def test_parse_hot_picks_legacy_text_json() -> None:
    payload = {
        "result": {
            "content": [{"text": json.dumps({"hot_picks": [{"symbol": "TSLA"}]})}],
        }
    }
    assert _parse_hot_picks(payload) == [{"symbol": "TSLA"}]


def test_parse_hot_picks_unknown_shape_returns_empty() -> None:
    assert _parse_hot_picks({"result": {"weird_field": []}}) == []
    assert _parse_hot_picks({}) == []


def test_parse_hot_picks_malformed_text_json_returns_empty() -> None:
    payload = {"result": {"content": [{"text": "not valid json"}]}}
    assert _parse_hot_picks(payload) == []


# ---------------------------------------------------------------------------
# fetch_gordon_trend_radar
# ---------------------------------------------------------------------------


async def test_fetch_gordon_trend_radar_happy_path() -> None:
    mcp = AsyncMock()
    mcp.call_tool.return_value = {
        "result": {"hot_picks": [{"symbol": "NVDA"}, {"symbol": "AAPL"}]},
    }
    snapshot, picks, err = await fetch_gordon_trend_radar(mcp)
    assert snapshot is not None
    assert len(picks) == 2
    assert picks[0]["symbol"] == "NVDA"
    assert err is None


async def test_fetch_gordon_trend_radar_none_client() -> None:
    snapshot, picks, err = await fetch_gordon_trend_radar(None)
    assert snapshot is None
    assert picks == []
    assert err is not None


async def test_fetch_gordon_trend_radar_mcp_raises() -> None:
    mcp = AsyncMock()
    mcp.call_tool.side_effect = ConnectionError("mcp down")
    snapshot, picks, err = await fetch_gordon_trend_radar(mcp)
    assert snapshot is None
    assert picks == []
    assert "ConnectionError" in err


async def test_fetch_gordon_trend_radar_mcp_error_response() -> None:
    mcp = AsyncMock()
    mcp.call_tool.return_value = {"error": {"code": -32601, "message": "tool not found"}}
    snapshot, picks, err = await fetch_gordon_trend_radar(mcp)
    assert snapshot is None
    assert picks == []
    assert "mcp_error" in err


async def test_fetch_gordon_trend_radar_ignores_null_error_key() -> None:
    """Code-review H1 / BH-3: `{"error": null}` used to be mistaken for
    a real MCP error. A null `error` key means success."""

    mcp = AsyncMock()
    mcp.call_tool.return_value = {
        "error": None,
        "result": {"hot_picks": [{"symbol": "NVDA"}]},
    }
    snapshot, picks, err = await fetch_gordon_trend_radar(mcp)
    assert snapshot is not None
    assert len(picks) == 1
    assert err is None


# ---------------------------------------------------------------------------
# persist_snapshot / fetch_and_persist
# ---------------------------------------------------------------------------


async def test_persist_snapshot_hydrates_model() -> None:
    conn = _FakeConn()
    snapshot = await persist_snapshot(
        conn,
        snapshot_data={"result": {"x": 1}},
        hot_picks=[{"symbol": "NVDA"}],
        source_error=None,
    )
    assert snapshot.id == 42
    assert len(snapshot.hot_picks) == 1
    assert snapshot.hot_picks[0].symbol == "NVDA"
    assert snapshot.source_error is None


async def test_fetch_and_persist_always_writes_row_on_mcp_failure() -> None:
    """Story 10.1 AC #3: a persisted row exists even when MCP fails."""

    mcp = AsyncMock()
    mcp.call_tool.side_effect = ConnectionError("mcp down")
    conn = _FakeConn()
    pool = _FakePool(conn)

    snapshot = await fetch_and_persist(pool, mcp)
    assert snapshot.id == 42
    assert snapshot.source_error is not None
    assert "ConnectionError" in snapshot.source_error
    assert snapshot.hot_picks == []


async def test_fetch_and_persist_happy_path_populates_picks() -> None:
    mcp = AsyncMock()
    mcp.call_tool.return_value = {
        "result": {
            "hot_picks": [
                {"symbol": "NVDA", "rank": 1},
                {"symbol": "BTCUSD", "rank": 2},
            ],
        }
    }
    conn = _FakeConn()
    pool = _FakePool(conn)

    snapshot = await fetch_and_persist(pool, mcp)
    assert snapshot.id == 42
    assert snapshot.source_error is None
    assert len(snapshot.hot_picks) == 2


async def test_persist_snapshot_drops_malformed_picks_without_crashing() -> None:
    """Code-review H2 / BH-19: a malformed pick (missing symbol) must
    NOT take down the entire snapshot persist. AC #3 "never drop a
    day" requires that the snapshot row is still written with whatever
    picks survived validation.
    """

    conn = _FakeConn()
    snapshot = await persist_snapshot(
        conn,
        snapshot_data={"result": {"x": 1}},
        hot_picks=[
            {"symbol": "NVDA", "rank": 1},
            {"rank": 2, "thesis": "missing symbol field"},  # invalid
            {"symbol": "", "rank": 3},  # invalid (empty symbol)
            {"symbol": "BTCUSD", "rank": 4},
        ],
        source_error=None,
    )
    assert snapshot.id == 42
    assert len(snapshot.hot_picks) == 2  # two valid survived
    assert {p.symbol for p in snapshot.hot_picks} == {"NVDA", "BTCUSD"}


# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------


def _picks(*symbols: str) -> list[HotPick]:
    return [HotPick(symbol=s) for s in symbols]


def test_compute_diff_no_previous_all_new() -> None:
    diff = compute_diff(_picks("NVDA", "BTCUSD"), None)
    assert len(diff.new) == 2
    assert diff.dropped == []
    assert diff.unchanged == []


def test_compute_diff_previous_empty_all_new() -> None:
    diff = compute_diff(_picks("NVDA"), [])
    assert len(diff.new) == 1
    assert diff.dropped == []
    assert diff.unchanged == []


def test_compute_diff_symmetric_overlap() -> None:
    current = _picks("NVDA", "TSLA", "BTCUSD")
    previous = _picks("AAPL", "NVDA", "META")
    diff = compute_diff(current, previous)
    assert {p.symbol for p in diff.new} == {"TSLA", "BTCUSD"}
    assert {p.symbol for p in diff.dropped} == {"AAPL", "META"}
    assert {p.symbol for p in diff.unchanged} == {"NVDA"}


def test_compute_diff_delta_summary() -> None:
    diff = GordonDiff(
        new=_picks("A", "B", "C"),
        dropped=_picks("X"),
        unchanged=_picks("Y", "Z"),
    )
    assert diff.delta_summary == "+3  -1"


def test_compute_diff_identical_lists_all_unchanged() -> None:
    lst = _picks("NVDA", "TSLA")
    diff = compute_diff(lst, lst)
    assert len(diff.unchanged) == 2
    assert diff.new == []
    assert diff.dropped == []


def test_compute_diff_keyed_by_symbol_and_horizon() -> None:
    """Code-review H6 / EC-12: a symbol appearing at a NEW horizon is
    correctly classified as `new`, not silently collapsed into
    `unchanged` alongside the older horizon.
    """

    current = [
        HotPick(symbol="NVDA", horizon="swing_short"),
        HotPick(symbol="NVDA", horizon="swing_long"),
    ]
    previous = [HotPick(symbol="NVDA", horizon="swing_short")]
    diff = compute_diff(current, previous)
    assert len(diff.new) == 1
    assert diff.new[0].horizon == "swing_long"
    assert len(diff.unchanged) == 1
    assert diff.unchanged[0].horizon == "swing_short"
    assert diff.dropped == []

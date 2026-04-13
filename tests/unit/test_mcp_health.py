"""Unit tests for Story 5.3 MCP health tracker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services import mcp_health

NOW = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset() -> None:
    mcp_health.reset()
    yield
    mcp_health.reset()


def test_fresh_success_is_ok() -> None:
    mcp_health.record_success("viktor")
    health = mcp_health.get_agent_health("viktor")
    assert health.severity == "ok"
    assert health.failure_count == 0


def test_never_called_is_red() -> None:
    health = mcp_health.get_agent_health("viktor")
    assert health.severity == "red"
    assert health.last_success is None


def test_yellow_between_1h_and_24h() -> None:
    old = NOW - timedelta(hours=5)
    mcp_health._state.last_success["viktor"] = old
    health = mcp_health.get_agent_health("viktor", now=NOW)
    assert health.severity == "yellow"


def test_red_over_24h() -> None:
    mcp_health._state.last_success["viktor"] = NOW - timedelta(hours=30)
    assert mcp_health.get_agent_health("viktor", now=NOW).severity == "red"


def test_failure_resets_to_zero_on_success() -> None:
    mcp_health.record_failure("viktor")
    mcp_health.record_failure("viktor")
    mcp_health.record_success("viktor")
    assert mcp_health.get_agent_health("viktor").failure_count == 0


def test_is_any_degraded_false_for_all_fresh() -> None:
    for agent in ("viktor", "rita", "satoshi", "cassandra", "gordon"):
        mcp_health.record_success(agent)
    assert mcp_health.is_any_degraded() is False


def test_is_any_degraded_true_when_any_red() -> None:
    mcp_health.record_success("viktor")
    # The other four known agents have never succeeded → red.
    assert mcp_health.is_any_degraded() is True


def test_worst_severity_picks_the_highest() -> None:
    mcp_health.record_success("viktor")
    mcp_health._state.last_success["satoshi"] = NOW - timedelta(hours=5)
    mcp_health._state.last_success["gordon"] = NOW - timedelta(hours=30)
    assert mcp_health.worst_severity(now=NOW) == "red"

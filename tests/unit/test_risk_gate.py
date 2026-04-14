"""Unit tests for the Story 7.2 risk-gate service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.proposal import Proposal, ProposalStatus, RiskGateLevel
from app.models.strategy import StrategyHorizon
from app.models.trade import TradeSide
from app.services.risk_gate import (
    _agent_for,
    _extract_payload,
    _parse_level,
    run_risk_gate,
)


def _make_proposal(asset_class: str = "stock") -> Proposal:
    return Proposal(
        id=42,
        agent_id="viktor",
        strategy_id=None,
        symbol="AAPL",
        asset_class=asset_class,
        side=TradeSide.BUY,
        horizon=StrategyHorizon.SWING_SHORT,
        entry_price=Decimal("150"),
        stop_price=Decimal("145"),
        target_price=Decimal("160"),
        position_size=Decimal("100"),
        risk_budget=Decimal("500"),
        trigger_spec={},
        status=ProposalStatus.PENDING,
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Agent routing
# ---------------------------------------------------------------------------


def test_agent_for_stock_routes_to_rita() -> None:
    assert _agent_for("stock") == "rita"
    assert _agent_for("option") == "rita"
    assert _agent_for("STOCK") == "rita"


def test_agent_for_crypto_routes_to_cassandra() -> None:
    assert _agent_for("crypto") == "cassandra"
    assert _agent_for("cfd") == "cassandra"


def test_agent_for_unknown_defaults_to_rita() -> None:
    assert _agent_for("weird") == "rita"


# ---------------------------------------------------------------------------
# Level parsing — fail closed
# ---------------------------------------------------------------------------


def test_parse_level_canonical() -> None:
    assert _parse_level("green") == RiskGateLevel.GREEN
    assert _parse_level("yellow") == RiskGateLevel.YELLOW
    assert _parse_level("red") == RiskGateLevel.RED


def test_parse_level_aliases() -> None:
    assert _parse_level("ok") == RiskGateLevel.GREEN
    assert _parse_level("warn") == RiskGateLevel.YELLOW
    assert _parse_level("blocked") == RiskGateLevel.RED


def test_parse_level_unknown_fails_closed_to_red() -> None:
    """FR28 fail-closed: an unrecognized level must NOT unlock the
    approve button."""

    assert _parse_level("bogus") == RiskGateLevel.RED
    assert _parse_level(None) == RiskGateLevel.RED


# ---------------------------------------------------------------------------
# Payload extraction — defensive
# ---------------------------------------------------------------------------


def test_extract_payload_from_content_list() -> None:
    raw = {
        "result": {"content": [{"type": "text", "text": '{"level":"green","flags":["budget_ok"]}'}]}
    }
    payload = _extract_payload(raw)
    assert payload == {"level": "green", "flags": ["budget_ok"]}


def test_extract_payload_from_flat_result() -> None:
    raw = {"result": {"level": "yellow", "flags": ["correlation_high"]}}
    payload = _extract_payload(raw)
    assert payload["level"] == "yellow"


def test_extract_payload_strips_mcp_envelope_keys() -> None:
    raw = {
        "result": {
            "content": [],
            "isError": False,
            "_meta": {"version": "1.0"},
            "level": "green",
        }
    }
    payload = _extract_payload(raw)
    assert "content" not in payload
    assert "isError" not in payload
    assert "_meta" not in payload


def test_extract_payload_returns_empty_on_garbage() -> None:
    assert _extract_payload(None) == {}
    assert _extract_payload("string") == {}
    assert _extract_payload({"result": "string"}) == {}
    assert _extract_payload({}) == {}


# ---------------------------------------------------------------------------
# run_risk_gate — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_risk_gate_with_no_mcp_returns_unreachable() -> None:
    proposal = _make_proposal()
    result = await run_risk_gate(proposal, mcp_client=None)
    assert result.level == RiskGateLevel.UNREACHABLE
    assert "mcp_unreachable" in result.flags
    assert result.blocks_approval is True


@pytest.mark.asyncio
async def test_run_risk_gate_happy_path_green() -> None:
    proposal = _make_proposal()
    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {"content": [{"type": "text", "text": '{"level":"green","flags":[]}'}]}
    }
    result = await run_risk_gate(proposal, mock)
    assert result.level == RiskGateLevel.GREEN
    assert not result.blocks_approval


@pytest.mark.asyncio
async def test_run_risk_gate_yellow_does_not_block() -> None:
    proposal = _make_proposal()
    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {
            "content": [{"type": "text", "text": '{"level":"yellow","flags":["correlation_high"]}'}]
        }
    }
    result = await run_risk_gate(proposal, mock)
    assert result.level == RiskGateLevel.YELLOW
    assert not result.blocks_approval


@pytest.mark.asyncio
async def test_run_risk_gate_red_blocks() -> None:
    proposal = _make_proposal()
    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {
            "content": [{"type": "text", "text": '{"level":"red","flags":["position_oversized"]}'}]
        }
    }
    result = await run_risk_gate(proposal, mock)
    assert result.level == RiskGateLevel.RED
    assert result.blocks_approval


@pytest.mark.asyncio
async def test_run_risk_gate_exception_returns_unreachable() -> None:
    proposal = _make_proposal()
    mock = AsyncMock()
    mock.call_tool.side_effect = RuntimeError("mcp blew up")
    result = await run_risk_gate(proposal, mock)
    assert result.level == RiskGateLevel.UNREACHABLE
    assert result.blocks_approval


@pytest.mark.asyncio
async def test_run_risk_gate_parse_error_fails_closed_to_red() -> None:
    """Code-review fail-closed: MCP returns 200 but garbage shape →
    RED (not UNREACHABLE — server IS reachable)."""

    proposal = _make_proposal()
    mock = AsyncMock()
    mock.call_tool.return_value = {"result": "garbage"}
    result = await run_risk_gate(proposal, mock)
    assert result.level == RiskGateLevel.RED
    assert "parse_error" in result.flags
    assert result.blocks_approval


@pytest.mark.asyncio
async def test_proposal_routes_crypto_to_cassandra() -> None:
    proposal = _make_proposal(asset_class="crypto")
    mock = AsyncMock()
    mock.call_tool.return_value = {
        "result": {"content": [{"type": "text", "text": '{"level":"green"}'}]}
    }
    result = await run_risk_gate(proposal, mock)
    assert result.agent_id == "cassandra"
    # First positional arg of call_tool is the tool name
    assert mock.call_tool.call_args[0][0] == "risk_gate"
    assert mock.call_tool.call_args[0][1]["agent"] == "cassandra"

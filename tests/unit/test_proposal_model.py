"""Unit tests for the Story 7.1 / 7.4 proposal domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.proposal import (
    Proposal,
    ProposalCreate,
    ProposalDecision,
    ProposalStatus,
    RiskGateLevel,
)
from app.models.strategy import StrategyHorizon
from app.models.trade import TradeSide


def _proposal(
    level: RiskGateLevel | None = None, status: ProposalStatus = ProposalStatus.PENDING
) -> Proposal:
    return Proposal(
        id=1,
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
        trigger_spec={"thesis": "test"},
        risk_gate_result=level,
        status=status,
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_red_proposal_blocks_approval() -> None:
    """FR28 hard invariant — RED blocks the approve button."""

    p = _proposal(RiskGateLevel.RED)
    assert p.is_red is True
    assert p.can_be_approved is False


def test_unreachable_treated_as_red() -> None:
    """Story 7.2 fail-closed: MCP-down also blocks."""

    p = _proposal(RiskGateLevel.UNREACHABLE)
    assert p.is_red is True
    assert p.can_be_approved is False


def test_yellow_does_not_block() -> None:
    p = _proposal(RiskGateLevel.YELLOW)
    assert p.is_red is False
    assert p.is_yellow is True
    assert p.can_be_approved is True


def test_green_does_not_block() -> None:
    p = _proposal(RiskGateLevel.GREEN)
    assert p.can_be_approved is True


def test_already_decided_proposal_cannot_be_approved() -> None:
    p = _proposal(RiskGateLevel.GREEN, status=ProposalStatus.APPROVED)
    assert p.can_be_approved is False


def test_pending_with_no_risk_gate_yet_blocks_approval() -> None:
    """Code-review H3 / BH-40 / EC-34: a proposal whose risk gate
    has not yet completed is blocked by `is_red` (pessimistic
    fail-closed). Previously the property returned False here,
    letting `can_be_approved` slip through during the brief window
    between proposal create and risk-gate completion.
    """

    p = _proposal(level=None)
    assert p.is_red is True
    assert p.can_be_approved is False


# ---------------------------------------------------------------------------
# ProposalCreate validation
# ---------------------------------------------------------------------------


def test_proposal_create_requires_positive_position_size() -> None:
    with pytest.raises(ValueError):
        ProposalCreate(
            agent_id="satoshi",
            symbol="BTCUSD",
            asset_class="crypto",
            side=TradeSide.BUY,
            horizon=StrategyHorizon.INTRADAY,
            entry_price=Decimal("100"),
            position_size=Decimal("0"),  # not > 0
            risk_budget=Decimal("100"),
        )


def test_proposal_create_allows_no_strategy() -> None:
    p = ProposalCreate(
        agent_id="satoshi",
        symbol="BTCUSD",
        asset_class="crypto",
        side=TradeSide.BUY,
        horizon=StrategyHorizon.INTRADAY,
        entry_price=Decimal("100"),
        position_size=Decimal("0.1"),
        risk_budget=Decimal("100"),
    )
    assert p.strategy_id is None


# ---------------------------------------------------------------------------
# ProposalDecision
# ---------------------------------------------------------------------------


def test_proposal_decision_default_overrode_false() -> None:
    d = ProposalDecision()
    assert d.overrode_fundamental is False
    assert d.risk_budget is None


def test_proposal_decision_rejects_negative_risk_budget() -> None:
    with pytest.raises(ValueError):
        ProposalDecision(risk_budget=Decimal("-50"))

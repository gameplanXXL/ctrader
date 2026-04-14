"""Unit tests for the strategy lifecycle state machine (Story 6.1 / 6.5)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.strategy import (
    StrategyCreate,
    StrategyHorizon,
    StrategyStatus,
    can_transition,
    next_toggle_status,
)

# ---------------------------------------------------------------------------
# Lifecycle FSM
# ---------------------------------------------------------------------------


def test_active_can_go_to_paused_or_retired() -> None:
    assert can_transition(StrategyStatus.ACTIVE, StrategyStatus.PAUSED)
    assert can_transition(StrategyStatus.ACTIVE, StrategyStatus.RETIRED)


def test_paused_can_go_to_active_or_retired() -> None:
    assert can_transition(StrategyStatus.PAUSED, StrategyStatus.ACTIVE)
    assert can_transition(StrategyStatus.PAUSED, StrategyStatus.RETIRED)


def test_retired_is_terminal() -> None:
    assert not can_transition(StrategyStatus.RETIRED, StrategyStatus.ACTIVE)
    assert not can_transition(StrategyStatus.RETIRED, StrategyStatus.PAUSED)


def test_active_cannot_stay_active_via_transition_check() -> None:
    """Same-state is not a transition — callers handle no-op separately."""

    assert not can_transition(StrategyStatus.ACTIVE, StrategyStatus.ACTIVE)


# ---------------------------------------------------------------------------
# Toggle helper
# ---------------------------------------------------------------------------


def test_toggle_active_to_paused() -> None:
    assert next_toggle_status(StrategyStatus.ACTIVE) is StrategyStatus.PAUSED


def test_toggle_paused_to_active() -> None:
    assert next_toggle_status(StrategyStatus.PAUSED) is StrategyStatus.ACTIVE


def test_toggle_retired_stays_retired() -> None:
    assert next_toggle_status(StrategyStatus.RETIRED) is StrategyStatus.RETIRED


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


def test_strategy_create_normalizes_asset_class() -> None:
    s = StrategyCreate(
        name="Mean Reversion",
        asset_class="  STOCK  ",
        horizon=StrategyHorizon.SWING_SHORT,
        risk_budget_per_trade=Decimal("250"),
        trigger_sources=["manual", "manual", "viktor_signal"],
    )
    assert s.asset_class == "stock"
    assert s.trigger_sources == ["manual", "viktor_signal"]


def test_strategy_create_rejects_unknown_asset_class() -> None:
    with pytest.raises(ValueError):
        StrategyCreate(
            name="Test",
            asset_class="futures",  # not in allowed set
            horizon=StrategyHorizon.INTRADAY,
            risk_budget_per_trade=Decimal("100"),
        )


def test_strategy_create_requires_non_negative_risk_budget() -> None:
    with pytest.raises(ValueError):
        StrategyCreate(
            name="Test",
            asset_class="stock",
            horizon=StrategyHorizon.INTRADAY,
            risk_budget_per_trade=Decimal("-50"),
        )


def test_strategy_create_requires_non_empty_name() -> None:
    with pytest.raises(ValueError):
        StrategyCreate(
            name="",
            asset_class="stock",
            horizon=StrategyHorizon.INTRADAY,
            risk_budget_per_trade=Decimal("100"),
        )

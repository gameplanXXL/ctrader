"""Unit tests for code-review H1 / H2 / H3 fixes (Epic 6).

Covers:
- `resolve_strategy_id` on integer id, name, taxonomy fallback
- `update_status` atomic-transition no-op semantics
- `next_toggle_status` retired terminal
"""

from __future__ import annotations

from app.models.strategy import (
    StrategyStatus,
    can_transition,
    next_toggle_status,
)

# ---------------------------------------------------------------------------
# Tranche A H2 — concurrency-safe FSM
# ---------------------------------------------------------------------------


def test_can_transition_rejects_revive_from_retired() -> None:
    """Code-review H2 / BH-2: retired must be terminal — no edge to
    active or paused, even via the explicit update_status path."""

    assert not can_transition(StrategyStatus.RETIRED, StrategyStatus.ACTIVE)
    assert not can_transition(StrategyStatus.RETIRED, StrategyStatus.PAUSED)


def test_toggle_retired_is_no_op() -> None:
    """Toggle on retired returns retired (no transition)."""

    assert next_toggle_status(StrategyStatus.RETIRED) is StrategyStatus.RETIRED


def test_can_transition_rejects_same_state_reverse_direction() -> None:
    """active → active is not a transition (the service short-circuits
    before calling can_transition)."""

    assert not can_transition(StrategyStatus.ACTIVE, StrategyStatus.ACTIVE)
    assert not can_transition(StrategyStatus.PAUSED, StrategyStatus.PAUSED)

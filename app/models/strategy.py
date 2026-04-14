"""Strategy domain model (Epic 6 / FR33).

Mirrors the `strategies` table from Migration 007. Used by the
Strategy CRUD service, the strategies page, and — later — the
proposal-generation path (Epic 7) which checks `status == 'active'`
before creating a new Proposal.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategyStatus(StrEnum):
    """Mirrors the `strategy_status` PG enum (Migration 001)."""

    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class StrategyHorizon(StrEnum):
    """Mirrors the `horizon_type` PG enum (Migration 001)."""

    INTRADAY = "intraday"
    SWING_SHORT = "swing_short"
    SWING_LONG = "swing_long"
    POSITION = "position"


class StrategyBase(BaseModel):
    """Shared shape for create / update / read."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(..., min_length=1, max_length=120)
    asset_class: str = Field(..., min_length=1)
    horizon: StrategyHorizon
    typical_holding_period: str | None = Field(default=None, max_length=120)
    trigger_sources: list[str] = Field(default_factory=list)
    risk_budget_per_trade: Decimal = Field(..., ge=0)
    status: StrategyStatus = StrategyStatus.ACTIVE

    @field_validator("asset_class")
    @classmethod
    def _valid_asset_class(cls, value: str) -> str:
        allowed = {"stock", "option", "crypto", "cfd"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"asset_class must be one of {sorted(allowed)}")
        return normalized

    @field_validator("trigger_sources")
    @classmethod
    def _dedup_sources(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for source in value:
            cleaned = str(source).strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen


class StrategyCreate(StrategyBase):
    """Payload for POST /strategies."""


class Strategy(StrategyBase):
    """A strategy row as it lives in the DB."""

    id: int
    # Story 10.3 / Code-review M5 / EC-19: optional FK to
    # gordon_snapshots(id) populated when Chef created this strategy
    # from a Gordon HOT-pick. Strategy detail view can render
    # "Erstellt aus Gordon-Snapshot #X" when non-null.
    source_snapshot_id: int | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Strategy notes (Story 6.4)
# ---------------------------------------------------------------------------


class StrategyNote(BaseModel):
    """One row from `strategy_notes`."""

    model_config = ConfigDict(frozen=True)

    id: int
    strategy_id: int
    content: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Derived types
# ---------------------------------------------------------------------------


class StrategyStatusTransition(BaseModel):
    """Result of a status toggle — used by the API response."""

    id: int
    old_status: StrategyStatus
    new_status: StrategyStatus


# Allowed transitions per the spec (Story 6.1 Dev Notes).
_ALLOWED_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.ACTIVE: {StrategyStatus.PAUSED, StrategyStatus.RETIRED},
    StrategyStatus.PAUSED: {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    # retired is terminal — no transitions out
    StrategyStatus.RETIRED: set(),
}


def can_transition(current: StrategyStatus, target: StrategyStatus) -> bool:
    """Enforce the lifecycle state machine."""

    return target in _ALLOWED_TRANSITIONS.get(current, set())


def next_toggle_status(current: StrategyStatus) -> StrategyStatus:
    """One-click toggle target for the status_badge.

    - active → paused
    - paused → active
    - retired → retired (no change; terminal)
    """

    if current is StrategyStatus.ACTIVE:
        return StrategyStatus.PAUSED
    if current is StrategyStatus.PAUSED:
        return StrategyStatus.ACTIVE
    return StrategyStatus.RETIRED

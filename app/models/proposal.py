"""Proposal domain model (Epic 7 / FR25-FR32).

Mirrors `proposals` from Migration 008. Used by the approval pipeline
(creation → risk gate → drilldown → decision → audit log).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.strategy import StrategyHorizon
from app.models.trade import TradeSide


class ProposalStatus(StrEnum):
    """Proposal lifecycle. CHECK constraint in Migration 008 mirrors this."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION = "revision"


class RiskGateLevel(StrEnum):
    """Mirrors the `risk_gate_result` PG enum (Migration 001).

    `unreachable` is added at the application layer for the MCP-down
    case (Story 7.2 Task 5) — it lives only in the Pydantic model and
    is mapped to `red` before persisting (so the DB enum stays
    3-stage).
    """

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNREACHABLE = "unreachable"


class ProposalBase(BaseModel):
    """Shared shape for create / read."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    agent_id: str = Field(..., min_length=1, max_length=80)
    strategy_id: int | None = None
    symbol: str = Field(..., min_length=1, max_length=120)
    asset_class: str = Field(..., min_length=1)
    side: TradeSide
    horizon: StrategyHorizon
    entry_price: Decimal = Field(..., ge=0)
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    position_size: Decimal = Field(..., gt=0)
    risk_budget: Decimal = Field(..., ge=0)
    trigger_spec: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ProposalCreate(ProposalBase):
    """Payload for `POST /api/proposals` or for direct service calls."""


class Proposal(ProposalBase):
    """A persisted proposal row."""

    id: int
    risk_gate_result: RiskGateLevel | None = None
    risk_gate_response: dict[str, Any] | None = None
    status: ProposalStatus
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    # Code-review H5: denormalized for the approval-card rendering.
    # Populated by `_LIST_SQL` (LEFT JOIN strategies); `_GET_SQL`
    # leaves it None and the drilldown looks up the strategy via
    # `strategy_id` if it ever needs the name.
    strategy_name: str | None = None

    @property
    def is_red(self) -> bool:
        """RED + UNREACHABLE block the approve button (FR28).

        Code-review H3 / BH-40 / EC-34: a proposal whose risk_gate has
        not yet run (`risk_gate_result is None`) must ALSO be treated
        as blocked. The earlier implementation returned False here,
        which let `can_be_approved` slip through for any proposal in
        the brief window between creation and risk-gate completion.
        Pessimistic default — fail closed.
        """

        if self.risk_gate_result is None:
            return True
        return self.risk_gate_result in (RiskGateLevel.RED, RiskGateLevel.UNREACHABLE)

    @property
    def is_yellow(self) -> bool:
        return self.risk_gate_result == RiskGateLevel.YELLOW

    @property
    def can_be_approved(self) -> bool:
        return self.status == ProposalStatus.PENDING and not self.is_red


class ProposalDecision(BaseModel):
    """Form payload for approve / reject / revision."""

    model_config = ConfigDict(extra="ignore")

    risk_budget: Decimal | None = Field(default=None, ge=0)
    overrode_fundamental: bool = False
    notes: str | None = Field(default=None, max_length=2000)

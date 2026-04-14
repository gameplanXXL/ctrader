"""Risk-gate result model (Story 7.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.proposal import RiskGateLevel


class RiskGateResult(BaseModel):
    """Outcome of one risk-gate evaluation by Rita (stocks) or
    Cassandra (crypto) via MCP."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    level: RiskGateLevel
    flags: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime
    agent_id: str

    @property
    def blocks_approval(self) -> bool:
        """RED and UNREACHABLE both block the approve button (FR28)."""

        return self.level in (RiskGateLevel.RED, RiskGateLevel.UNREACHABLE)

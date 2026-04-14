"""Regime-snapshot domain model (Epic 9 / Story 9.1).

Mirrors the `regime_snapshots` table from Migration 012. Consumed by
the Regime page (Story 9.3) and the Kill-Switch service (Story 9.2).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Fear & Greed thresholds (PRD FR42: F&G < 20 triggers the kill switch)
KILL_SWITCH_THRESHOLD = 20


def fear_greed_classification(value: int | None) -> str:
    """Alternative.me's bucket names — useful for the Regime page hero."""

    if value is None:
        return "Unbekannt"
    if value <= 24:
        return "Extreme Fear"
    if value <= 49:
        return "Fear"
    if value <= 54:
        return "Neutral"
    if value <= 74:
        return "Greed"
    return "Extreme Greed"


class RegimeSnapshot(BaseModel):
    """A persisted regime-snapshot row."""

    model_config = ConfigDict(frozen=True)

    id: int
    fear_greed_index: int | None = Field(default=None, ge=0, le=100)
    vix: Decimal | None = Field(default=None, ge=0)
    per_broker_pnl: dict[str, Any] = Field(default_factory=dict)
    fetch_errors: dict[str, Any] | None = None
    created_at: datetime

    @property
    def fg_classification(self) -> str:
        return fear_greed_classification(self.fear_greed_index)

    @property
    def is_kill_switch_regime(self) -> bool:
        """True if the current F&G is in the crash zone (< 20, FR42)."""

        if self.fear_greed_index is None:
            return False
        return self.fear_greed_index < KILL_SWITCH_THRESHOLD

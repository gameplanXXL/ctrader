"""Gordon trend-radar snapshot + hot-pick models (Epic 10 / Story 10.1).

Mirrors `gordon_snapshots` from Migration 014. Consumed by the Trends
page (Story 10.2) and the "create strategy from HOT-pick" flow
(Story 10.3).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HotPick(BaseModel):
    """One HOT-pick entry returned by the Gordon `trend_radar` tool.

    Shape is deliberately permissive — the MCP contract for Gordon is
    frozen via snapshot at Woche 0 (CLAUDE.md) but new fields may
    appear as `fundamental` evolves. We accept extras and ignore
    them rather than crashing.
    """

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(..., min_length=1)
    rank: int | None = None
    horizon: str | None = None
    confidence: float | None = None
    thesis: str | None = None
    entry_zone: list[Decimal] | None = None
    target: Decimal | None = None


class GordonSnapshot(BaseModel):
    """A persisted Gordon snapshot row."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    snapshot_data: dict[str, Any] = Field(default_factory=dict)
    hot_picks: list[HotPick] = Field(default_factory=list)
    source_error: str | None = None
    created_at: datetime

    @property
    def is_stale(self) -> bool:
        """True if the snapshot is more than 7 days old (NFR-I4 ceiling).

        The Trends page shows a warning banner when `is_stale` is True so
        Chef knows the weekly fetch missed a run (e.g., MCP down Monday).
        """

        age = datetime.now(self.created_at.tzinfo) - self.created_at
        return age.days >= 7

    @property
    def has_error(self) -> bool:
        return bool(self.source_error) or not self.hot_picks


class GordonDiff(BaseModel):
    """Result of comparing two consecutive Gordon snapshots.

    `new` — symbols present in `current` but not in `previous`
    `dropped` — symbols present in `previous` but not in `current`
    `unchanged` — symbols present in both lists
    """

    model_config = ConfigDict(frozen=True)

    new: list[HotPick] = Field(default_factory=list)
    dropped: list[HotPick] = Field(default_factory=list)
    unchanged: list[HotPick] = Field(default_factory=list)

    @property
    def delta_summary(self) -> str:
        return f"+{len(self.new)}  -{len(self.dropped)}"

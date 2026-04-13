"""Fundamental-analysis result model (Story 5.1).

The shape is intentionally loose — the upstream MCP server evolves
independently and we don't want to force a lockstep schema migration
every time Viktor or Satoshi adds a new field. The model captures
just the common core (rating, confidence, thesis) plus a free-form
`extra` bag.

Rating taxonomy matches the `fundamental` project's
`SFA-Analyst` / `CFA-Analyst` output: BUY / HOLD / SELL for Viktor,
LONG / NEUTRAL / SHORT for Satoshi. We normalize both into a single
enum so the drilldown template renders the same badge regardless of
which agent spoke.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FundamentalRating(StrEnum):
    """Normalized rating labels for both Viktor (stocks) and Satoshi
    (crypto). Loose — `UNKNOWN` is the safe fallback when an upstream
    field is missing or unrecognised."""

    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"
    UNKNOWN = "unknown"


class FundamentalAssessment(BaseModel):
    """One analyst snapshot — fits both Viktor and Satoshi outputs."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    agent_id: str
    rating: FundamentalRating = FundamentalRating.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    thesis: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class FundamentalResult(BaseModel):
    """Cached fundamental response — wraps the assessment + freshness
    metadata that the UI needs to render a staleness hint.

    `is_stale` is True when the service returned a stale fallback
    (TTL expired or MCP timeout) instead of a fresh live call.
    """

    model_config = ConfigDict(frozen=True)

    assessment: FundamentalAssessment
    cached_at: datetime
    is_stale: bool = False
    source_agent: str = ""

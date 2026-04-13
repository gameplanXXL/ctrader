"""OHLC candle domain model (Story 4.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Timeframe(StrEnum):
    """Mirrors the `ohlc_timeframe` PostgreSQL enum (Migration 003)."""

    M1 = "1m"
    M5 = "5m"


class Candle(BaseModel):
    """One OHLC bar — shape matches both the cache table and every
    third-party source we plug in."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1)
    timeframe: Timeframe
    ts: datetime
    open: Decimal = Field(..., ge=0)
    high: Decimal = Field(..., ge=0)
    low: Decimal = Field(..., ge=0)
    close: Decimal = Field(..., ge=0)
    volume: Decimal | None = None

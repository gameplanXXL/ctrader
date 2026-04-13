"""Trade domain model — typed wrapper around the `trades` table.

Story 2.1 scope: just the columns that exist in Migration 002. Later
stories add `strategy_id` (Story 6.1), `agent_id` (Story 8.1),
`mae`/`mfe` (Story 4.3), and the Quick-Order lifecycle columns (Story
11.2 / Migration 005). Each addition will extend this model in lockstep.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradeSource(StrEnum):
    """Mirrors the `trade_source` PostgreSQL enum (Migration 001)."""

    IB = "ib"
    CTRADER = "ctrader"


class TradeSide(StrEnum):
    """Mirrors the `trade_side` PostgreSQL enum (Migration 001)."""

    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class AssetClass(StrEnum):
    """Allowed values for the `trades.asset_class` CHECK constraint."""

    STOCK = "stock"
    OPTION = "option"
    CRYPTO = "crypto"
    CFD = "cfd"


class TradeIn(BaseModel):
    """Shape used when inserting a new trade.

    Mirrors the column set from Migration 002 minus DB-managed fields
    (id, created_at, updated_at). Used by the Flex import pipeline,
    the live-sync handler (Story 2.2), and the Quick-Order flow
    (Story 11.2).
    """

    model_config = ConfigDict(use_enum_values=False, frozen=True)

    symbol: str = Field(..., min_length=1)
    asset_class: AssetClass
    side: TradeSide
    quantity: Decimal = Field(..., gt=0)
    entry_price: Decimal = Field(..., ge=0)
    exit_price: Decimal | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    pnl: Decimal | None = None
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    broker: TradeSource
    perm_id: str = Field(..., min_length=1)
    trigger_spec: dict[str, Any] | None = None

    @field_validator("closed_at")
    @classmethod
    def _closed_at_after_opened(cls, value: datetime | None, info: Any) -> datetime | None:
        opened_at = info.data.get("opened_at")
        if value is not None and opened_at is not None and value < opened_at:
            raise ValueError("closed_at must not be earlier than opened_at")
        return value


class Trade(TradeIn):
    """A trade as it lives in the database — adds DB-managed fields."""

    id: int
    created_at: datetime
    updated_at: datetime

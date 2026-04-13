"""Trigger-Spec domain model (Story 3.2).

The `trigger_spec` column on `trades` is the source-of-truth for WHY a
trade was entered. It lives as JSONB in PostgreSQL (Migration 002) with
a GIN index so Epic 4 facet queries stay fast.

Shape is kept intentionally close to the fundamental project's
`trigger-evaluator.ts` schema (FR16) so the two systems can share
proposal payloads: snake_case keys, primitive values, optional fields
explicit rather than missing.

Example (manual trade):

    {
      "trigger_type": "technical_breakout",
      "confidence": 0.72,
      "horizon": "swing_short",
      "entry_reason": "20-day high breakout mit Volumen-Confirmation",
      "source": "manual",
      "followed": true,
      "mistake_tags": ["fomo"]
    }

Example (bot trade, Epic 7+):

    {
      "trigger_type": "satoshi_signal",
      "confidence": 0.85,
      "horizon": "intraday",
      "entry_reason": "F&G extreme fear + oversold RSI",
      "source": "bot",
      "agent_id": "satoshi",
      "proposal_id": 42,
      "followed": true
    }
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TriggerSource(StrEnum):
    """Who originated this trade — a Chef-discretion click or a bot proposal."""

    MANUAL = "manual"
    BOT = "bot"


class TriggerSpec(BaseModel):
    """Structured trigger provenance, stored as JSONB on `trades.trigger_spec`.

    All string-enum-ish fields (`trigger_type`, `horizon`, mistake tag
    entries) are validated **loosely** against `taxonomy.yaml` at the
    service layer (`app/services/trigger_spec.py`) rather than pinned
    to a Literal here — the taxonomy evolves independently and we'd
    rather not rev this model every time a new trigger_type lands.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger_type: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    horizon: str = Field(..., min_length=1)
    entry_reason: str = Field(default="", max_length=2000)
    source: TriggerSource
    followed: bool = True

    agent_id: str | None = None
    proposal_id: int | None = None
    mistake_tags: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("mistake_tags")
    @classmethod
    def _mistake_tags_unique(cls, value: list[str]) -> list[str]:
        """Keep the list unique and drop empties — mistake-tag multi-select
        posts can duplicate if the form is submitted twice."""

        seen: list[str] = []
        for tag in value:
            if tag and tag not in seen:
                seen.append(tag)
        return seen

    def to_jsonb(self) -> dict[str, Any]:
        """Serialize to a plain dict ready for the JSONB cast.

        Pydantic's `model_dump()` is enough — all fields are already
        JSON-native. We drop `None` mistake_tags to keep the stored doc
        compact and preserve the existing `trigger_spec ? 'mistake_tags'`
        check in the Story 3.4 report query.
        """

        data = self.model_dump(mode="json", exclude_none=False)
        # StrEnum serializes to its value under mode="json" already.
        if not data.get("mistake_tags"):
            data.pop("mistake_tags", None)
        return data

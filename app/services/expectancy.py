"""Expectancy-at-entry placeholder for the trade drilldown (Story 2.4).

Real expectancy needs a strategy history (Epic 6 — strategies table +
historical R-multiples), so this story ships a placeholder that always
returns None. The drilldown template renders "NULL" for missing
expectancy values, same convention as R-multiple.

This file intentionally exists so Epic 6 can wire its history-driven
implementation in here without changing every caller.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def compute_expectancy_at_entry(trade: dict[str, Any]) -> Decimal | None:
    """Placeholder — returns None until Epic 6 has strategy history."""

    _ = trade  # explicitly unused
    return None

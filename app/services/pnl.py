"""P&L computation — used by Story 2.4 (drilldown) and later by the
strategy aggregations in Epic 6.

Story 2.4 scope: net P&L for a closed stock/option trade including
fees. CFD funding-rates land in Phase 2 — we mark them None for now.

Sign convention (corrected after Epic-2 code review, finding H1):
- LONG side (`buy` open, `sell` close pair):
  profit when exit > entry → `(exit - entry) * qty`
- SHORT side (`short` open, `cover` close pair):
  profit when exit < entry → `(entry - exit) * qty`

Both `short` AND `cover` belong to the short formula. The cover is
the close-leg of a short — covering below the original short price is
profit. Earlier versions grouped `cover` with `buy`, which silently
inverted the sign for every short close and would have corrupted
strategy aggregations downstream (FR12).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _to_decimal(value: Any) -> Decimal | None:
    """Safe Decimal coercion that goes through `str()` to avoid binary-
    float artifacts (`Decimal(1.5)` → `Decimal('1.5000...0444...')`).

    Used by both `compute_pnl` and `compute_r_multiple` so financial
    math always lands on `Decimal('1.50')`, never on the float-derived
    long form.
    """

    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


def compute_pnl(trade: dict[str, Any]) -> Decimal | None:
    """Return net P&L (gross minus fees) for a closed trade, else None."""

    exit_d = _to_decimal(trade.get("exit_price"))
    entry_d = _to_decimal(trade.get("entry_price"))
    qty_d = _to_decimal(trade.get("quantity"))
    if exit_d is None or entry_d is None or qty_d is None:
        return None

    side = trade.get("side")
    if side == "buy":
        gross = (exit_d - entry_d) * qty_d
    elif side in ("sell", "short", "cover"):
        # `cover` is a short-close — same sign convention as `short`.
        gross = (entry_d - exit_d) * qty_d
    else:
        return None

    fees_d = _to_decimal(trade.get("fees")) or Decimal("0")
    return gross - fees_d

"""P&L computation — used by Story 2.4 (drilldown) and later by the
strategy aggregations in Epic 6.

Story 2.4 scope: net P&L for a closed stock/option trade including
fees. CFD funding-rates land in Phase 2 — we mark them None for now.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def compute_pnl(trade: dict[str, Any]) -> Decimal | None:
    """Return net P&L (gross minus fees) for a closed trade, else None.

    `trade` is the dict shape returned by `trade_query.get_trade_detail`.

    Sign convention follows the trader convention:
    - BUY closed at higher exit  → positive
    - SELL/SHORT closed at lower exit → positive
    """

    exit_price = trade.get("exit_price")
    entry_price = trade.get("entry_price")
    quantity = trade.get("quantity")
    if exit_price is None or entry_price is None or quantity is None:
        return None

    try:
        exit_d = Decimal(exit_price)
        entry_d = Decimal(entry_price)
        qty_d = Decimal(quantity)
    except (TypeError, ValueError):
        return None

    side = trade.get("side")
    if side in ("buy", "cover"):
        gross = (exit_d - entry_d) * qty_d
    elif side in ("sell", "short"):
        gross = (entry_d - exit_d) * qty_d
    else:
        return None

    fees = trade.get("fees") or Decimal("0")
    try:
        fees_d = Decimal(fees)
    except (TypeError, ValueError):
        fees_d = Decimal("0")

    return gross - fees_d

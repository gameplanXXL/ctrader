"""R-Multiple computation — Story 2.4 (drilldown) + later strategy
aggregations (Epic 6).

FR12 / NFR-determinism rule:
> R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0")

Missing stop must NEVER collapse to 0R, otherwise strategy aggregations
get silently corrupted. Return Python `None` and let the display layer
render "NULL" via `format_r_multiple`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def compute_r_multiple(trade: dict[str, Any]) -> Decimal | None:
    """Return R-multiple for a closed trade with a known stop-loss, else None.

    Story 2.4 scope: the trades table doesn't yet carry a `stop_price`
    column (added by Story 11.2 via `trailing_stop_amount` /
    `limit_price`). For now we attempt to read `stop_price` /
    `initial_stop` keys from the trade dict; if none are present we
    return None (which the formatter renders as "NULL"). This keeps
    the function ready for Epic 11 without blocking Story 2.4.
    """

    exit_price = trade.get("exit_price")
    entry_price = trade.get("entry_price")
    if exit_price is None or entry_price is None:
        return None

    stop_price = (
        trade.get("stop_price") or trade.get("initial_stop") or trade.get("initial_stop_price")
    )
    if stop_price is None:
        # FR12: explicit None, not 0.
        return None

    try:
        exit_d = Decimal(exit_price)
        entry_d = Decimal(entry_price)
        stop_d = Decimal(stop_price)
    except (TypeError, ValueError):
        return None

    risk = entry_d - stop_d
    if risk == 0:
        # Stop equals entry — R-multiple is undefined, not zero.
        return None

    side = trade.get("side")
    if side in ("buy", "cover"):
        return (exit_d - entry_d) / risk
    if side in ("sell", "short"):
        # For shorts the risk is also `entry - stop`, but stop is
        # ABOVE entry so `risk` is negative. The reward is
        # `entry - exit` which divides cleanly.
        return (entry_d - exit_d) / -risk
    return None

"""R-Multiple computation — Story 2.4 (drilldown) + later strategy
aggregations (Epic 6).

FR12 / NFR-determinism rule:
> R-Multiple (oder NULL bei fehlendem Stop-Loss, nie "0")

Missing stop must NEVER collapse to 0R, otherwise strategy aggregations
get silently corrupted. Return Python `None` and let the display layer
render "NULL" via `format_r_multiple`.

Sign convention (corrected after Epic-2 code review, finding H1):
- LONG (`buy` open / `sell` close): `(exit - entry) / (entry - stop)`
- SHORT (`short` open / `cover` close): `(entry - exit) / (stop - entry)`

`cover` belongs with `short` — they're both the short side of a
short-cover round trip. Earlier versions grouped `cover` with `buy`
and silently inverted the R-Multiple sign for every cover.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.pnl import _to_decimal


def compute_r_multiple(trade: dict[str, Any]) -> Decimal | None:
    """Return R-multiple for a closed trade with a known stop-loss, else None.

    Reads `stop_price`, `initial_stop`, or `initial_stop_price` from the
    trade dict — forward-compatible with Story 11.2 Migration 005,
    which adds `trailing_stop_amount` / `limit_price` columns.
    """

    exit_d = _to_decimal(trade.get("exit_price"))
    entry_d = _to_decimal(trade.get("entry_price"))
    if exit_d is None or entry_d is None:
        return None

    stop_d = _to_decimal(
        trade.get("stop_price") or trade.get("initial_stop") or trade.get("initial_stop_price")
    )
    if stop_d is None:
        # FR12: explicit None, not 0.
        return None

    side = trade.get("side")
    if side == "buy":
        risk = entry_d - stop_d  # positive for a valid long: stop < entry
        if risk == 0:
            return None
        return (exit_d - entry_d) / risk

    if side in ("sell", "short", "cover"):
        # Short-side R: `(entry - exit) / (stop - entry)`.
        # Stop is ABOVE entry for shorts → `stop - entry` is positive.
        risk = stop_d - entry_d
        if risk == 0:
            return None
        return (entry_d - exit_d) / risk

    return None


# Re-export `_to_decimal` so callers that test r_multiple in isolation
# don't need to reach into pnl.py.
__all__ = ["_to_decimal", "compute_r_multiple"]

"""Daily-P&L aggregation for the calendar view (Story 4.4 / FR13b)."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import asyncpg

from app.services.pnl import compute_pnl


@dataclass(frozen=True)
class DailyPnlCell:
    """One calendar cell's worth of stats."""

    day: date
    trade_count: int
    total_pnl: Decimal

    @property
    def total_pnl_float(self) -> float:
        return float(self.total_pnl)


# We intentionally include OPEN trades too (closed_at IS NULL) so the
# calendar shows activity days even before exits land — but only
# count pnl from closed rows, so cells with only open trades render
# as "activity without $" (grey tint).
#
# Code-review H8 / BH-12 / EC-12: explicit inner parens around each
# range so a future `AND user_id = $X` can't accidentally bind to only
# one branch of the OR. Precedence-safe by construction.
_SQL = """
SELECT
    id, symbol, side, quantity, entry_price, exit_price,
    opened_at, closed_at, pnl, fees
  FROM trades
 WHERE (
        (closed_at >= $1 AND closed_at < $2)
     OR (opened_at >= $1 AND opened_at < $2)
 )
"""


async def get_daily_pnl(
    conn: asyncpg.Connection,
    *,
    year: int,
    month: int,
) -> dict[date, DailyPnlCell]:
    """Return `{day: DailyPnlCell}` for every day in the given month
    that has at least one trade opened or closed on it.

    Days without activity are NOT in the dict — the calendar template
    fills them in with grey tint.
    """

    first = datetime(year, month, 1, tzinfo=UTC)
    _, last_day = monthrange(year, month)
    if month == 12:
        next_first = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        next_first = datetime(year, month + 1, 1, tzinfo=UTC)

    rows = await conn.fetch(_SQL, first, next_first)

    buckets: dict[date, list[Decimal]] = {}
    counts: dict[date, int] = {}
    for row in rows:
        row_dict = dict(row)
        # Bucket by closed_at if present, else opened_at — matches
        # "day this trade materialised" intuition.
        when: datetime | None = row_dict.get("closed_at") or row_dict.get("opened_at")
        if when is None:
            continue
        day = when.astimezone(UTC).date()
        counts[day] = counts.get(day, 0) + 1
        pnl = compute_pnl(row_dict)
        if pnl is not None:
            buckets.setdefault(day, []).append(pnl)

    out: dict[date, DailyPnlCell] = {}
    # Days with activity: iterate by union of the two dicts.
    for day in set(list(counts.keys()) + list(buckets.keys())):
        total = sum(buckets.get(day, []), Decimal("0"))
        out[day] = DailyPnlCell(
            day=day,
            trade_count=counts.get(day, 0),
            total_pnl=total,
        )
    return out


def iter_month_days(year: int, month: int) -> list[date]:
    """Utility for the template — every day in the month, in order."""

    _, last = monthrange(year, month)
    return [date(year, month, d) for d in range(1, last + 1)]

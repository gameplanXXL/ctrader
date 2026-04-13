"""Top-N mistakes report (Story 3.4, FR18a / FR18b).

The `mistake_tags` array inside `trigger_spec` JSONB is the
authoritative source. We UNNEST the array per row, group by tag, and
aggregate COUNT + SUM(pnl) over a configurable time window.

A trade tagged with N mistakes contributes once to every tag's bucket
— this is intentional: if an `oversized` + `revenge` + `no_stop` trade
loses $500, it should surface in all three groups so none of them
understate the cost of that particular mistake pattern.

The P&L we aggregate is the DB column `trades.pnl`, which is the
persisted value (NULL for live trades, set on close). Trades with
NULL P&L still count toward the frequency bucket but contribute 0 to
the monetary sum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg


@dataclass(frozen=True)
class MistakeRow:
    """One row of the mistakes report."""

    tag: str
    count: int
    total_pnl: Decimal
    avg_pnl: Decimal

    @property
    def total_pnl_float(self) -> float:
        return float(self.total_pnl)

    @property
    def avg_pnl_float(self) -> float:
        return float(self.avg_pnl)


# UNNEST of the JSONB array with two grouping metrics. Two code-review
# hardening fixes on top of the initial Story 3.4 query:
#
# H2/BH-6/EC-17: the `jsonb_typeof(... ) = 'array'` guard prevents
# `jsonb_array_elements_text` from crashing when a row ever stores a
# non-array value (scalar string, null, …) — without it, one bad row
# kills the whole report with `cannot extract elements from a scalar`.
#
# H6/EC-18: the AVG is computed as `SUM(pnl) / NULLIF(COUNT(*), 0)` so
# that trades with NULL pnl contribute 0 to the SUM *and* divide by
# the full count — matching the docstring's "frequency counts real
# trades, money counts only closed ones" invariant. Using raw `AVG(pnl)`
# would silently average only the non-null rows, yielding `count × avg
# ≠ total` in the report.
_REPORT_SQL = """
SELECT
    mistake_tag::text AS tag,
    COUNT(*)          AS count,
    COALESCE(SUM(pnl), 0)::numeric AS total_pnl,
    COALESCE(SUM(pnl) / NULLIF(COUNT(*), 0), 0)::numeric AS avg_pnl
  FROM trades,
       jsonb_array_elements_text(trigger_spec->'mistake_tags') AS mistake_tag
 WHERE trigger_spec ? 'mistake_tags'
   AND jsonb_typeof(trigger_spec->'mistake_tags') = 'array'
   AND opened_at BETWEEN $1 AND $2
 GROUP BY mistake_tag
 ORDER BY total_pnl ASC, count DESC
 LIMIT $3
"""


def _resolve_window(
    window: str | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Translate a named window into (start, end) UTC datetimes.

    Supported values:
        - "all"     → 2000-01-01 .. now
        - "7d"      → now - 7 days .. now
        - "30d"     → now - 30 days .. now (DEFAULT)
        - "90d"     → now - 90 days .. now
        - "ytd"     → Jan 1 of current year .. now
    """

    reference = now or datetime.now(UTC)
    window = (window or "30d").lower().strip()

    if window == "all":
        return datetime(2000, 1, 1, tzinfo=UTC), reference
    if window == "7d":
        return reference - timedelta(days=7), reference
    if window == "30d":
        return reference - timedelta(days=30), reference
    if window == "90d":
        return reference - timedelta(days=90), reference
    if window == "ytd":
        return datetime(reference.year, 1, 1, tzinfo=UTC), reference
    # Unknown window → fall back to 30d instead of raising — the URL
    # comes straight from a query string and we don't want a typo to
    # 500 the page.
    return reference - timedelta(days=30), reference


async def top_n_mistakes(
    conn: asyncpg.Connection,
    *,
    window: str = "30d",
    limit: int = 10,
    now: datetime | None = None,
) -> tuple[list[MistakeRow], datetime, datetime]:
    """Return the Top-N mistakes for a time window.

    Returns `(rows, window_start, window_end)`. The window bounds are
    returned alongside the rows so the template can render "Last 30
    days · N trades · from X to Y" without recomputing.

    Sorting: `total_pnl ASC` → most expensive (most negative) first.
    Trades with NULL pnl contribute 0 to the sum, so purely-cosmetic
    tags still show up at count-based positions after the money is
    spent.
    """

    if limit < 1:
        limit = 10

    start, end = _resolve_window(window, now=now)
    rows = await conn.fetch(_REPORT_SQL, start, end, limit)

    result = [
        MistakeRow(
            tag=row["tag"],
            count=int(row["count"]),
            total_pnl=Decimal(row["total_pnl"]),
            avg_pnl=Decimal(row["avg_pnl"]),
        )
        for row in rows
    ]
    return result, start, end

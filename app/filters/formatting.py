"""Display-layer formatting helpers used in Jinja2 templates.

Story 2.3 AC #6 (UX-DR69 / UX-DR70):
- P&L positive → green, negative → red, zero/None → neutral
- R-Multiple with one decimal, NULL stays "NULL", never "0"
- Empty / missing values render as em-dash, not blank

These functions are deliberately stateless and dependency-free so the
Jinja2 environment can register them once at app startup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

EM_DASH = "—"


def format_pnl(value: Decimal | float | int | None) -> str:
    """Render a P&L number with sign + thousands separator.

    Returns the em-dash for None / missing data so the table cell is
    visually filled (no blank cells).
    """

    if value is None:
        return EM_DASH
    try:
        amount = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        return EM_DASH

    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:,.2f}"


def pnl_class(value: Decimal | float | int | None) -> str:
    """Return the Tailwind-friendly CSS class for a P&L value."""

    if value is None:
        return "pnl-neutral"
    try:
        amount = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        return "pnl-neutral"
    if amount > 0:
        return "pnl-gain"
    if amount < 0:
        return "pnl-loss"
    return "pnl-neutral"


def format_r_multiple(value: Decimal | float | int | None) -> str:
    """Render an R-multiple with one decimal place.

    NULL means "trade had no stop-loss" (FR12) and must NOT collapse
    to "0" — that would corrupt strategy aggregations downstream. We
    render the literal string "NULL" so the trader spots it on the
    journal row.
    """

    if value is None:
        return "NULL"
    try:
        amount = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        return "NULL"
    sign = "+" if amount > 0 else ""
    return f"{sign}{amount:.1f}R"


def format_time(value: datetime | None) -> str:
    """Compact UTC timestamp for the trade row.

    Story 2.3 leaves the full ISO timestamp for the drilldown; the
    list shows just `YYYY-MM-DD HH:MM`.

    Always renders in UTC. If the input is tz-aware in another
    timezone (e.g., asyncpg returned a server-local TIMESTAMPTZ value),
    we explicitly convert to UTC first so the column header label
    "Time (UTC)" is honest. Naive datetimes are assumed UTC — that's
    safe because every Migration-002 timestamp column is TIMESTAMPTZ
    and every constructor in the codebase explicitly tags UTC.
    """

    if value is None:
        return EM_DASH
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%d %H:%M")


def format_quantity(value: Any) -> str:
    if value is None:
        return EM_DASH
    try:
        return f"{Decimal(value):,.0f}"
    except (TypeError, ValueError, InvalidOperation):
        return EM_DASH


def format_price(value: Any) -> str:
    if value is None:
        return EM_DASH
    try:
        return f"{Decimal(value):,.2f}"
    except (TypeError, ValueError, InvalidOperation):
        return EM_DASH


def or_dash(value: Any) -> str:
    """Generic null-coalescing display filter.

    Lets templates write `{{ trade.trigger_type | or_dash }}` instead
    of `{% if ... %}{{ ... }}{% else %}—{% endif %}` everywhere.
    """

    if value is None or value == "":
        return EM_DASH
    return str(value)


# Map of filter-name → callable, registered into the Jinja2 environment
# from `app.routers.pages` at import time.
JINJA_FILTERS = {
    "format_pnl": format_pnl,
    "pnl_class": pnl_class,
    "format_r_multiple": format_r_multiple,
    "format_time": format_time,
    "format_quantity": format_quantity,
    "format_price": format_price,
    "or_dash": or_dash,
}

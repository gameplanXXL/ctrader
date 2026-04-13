"""Unit tests for the Jinja2 display filters (Story 2.3).

Pure functions — no DB, no app context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.filters.formatting import (
    EM_DASH,
    format_pnl,
    format_price,
    format_quantity,
    format_r_multiple,
    format_time,
    or_dash,
    pnl_class,
)

# ---------------------------------------------------------------------------
# format_pnl + pnl_class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("123.45"), "+123.45"),
        (Decimal("-50.10"), "-50.10"),
        (Decimal("0"), "0.00"),
        (None, EM_DASH),
        (1234567, "+1,234,567.00"),
    ],
)
def test_format_pnl(value, expected: str) -> None:
    assert format_pnl(value) == expected


@pytest.mark.parametrize(
    "value, expected_class",
    [
        (Decimal("100"), "pnl-gain"),
        (Decimal("-100"), "pnl-loss"),
        (Decimal("0"), "pnl-neutral"),
        (None, "pnl-neutral"),
        ("not a number", "pnl-neutral"),
    ],
)
def test_pnl_class(value, expected_class: str) -> None:
    assert pnl_class(value) == expected_class


# ---------------------------------------------------------------------------
# format_r_multiple — must NEVER collapse None to "0"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("1.5"), "+1.5R"),
        (Decimal("-0.7"), "-0.7R"),
        (Decimal("0.0"), "0.0R"),
        (None, "NULL"),  # FR12 — never "0R"
        ("not a number", "NULL"),
    ],
)
def test_format_r_multiple(value, expected: str) -> None:
    assert format_r_multiple(value) == expected


# ---------------------------------------------------------------------------
# format_time
# ---------------------------------------------------------------------------


def test_format_time_renders_utc_datetime() -> None:
    dt = datetime(2026, 4, 13, 14, 30, tzinfo=UTC)
    assert format_time(dt) == "2026-04-13 14:30"


def test_format_time_renders_naive_datetime() -> None:
    dt = datetime(2026, 4, 13, 14, 30)
    assert format_time(dt) == "2026-04-13 14:30"


def test_format_time_returns_dash_for_none() -> None:
    assert format_time(None) == EM_DASH


# ---------------------------------------------------------------------------
# or_dash + numeric formatters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, EM_DASH),
        ("", EM_DASH),
        ("hello", "hello"),
        (42, "42"),
        ("manual", "manual"),
    ],
)
def test_or_dash(value, expected: str) -> None:
    assert or_dash(value) == expected


def test_format_quantity_strips_decimals() -> None:
    assert format_quantity(Decimal("100")) == "100"
    assert format_quantity(Decimal("1500")) == "1,500"
    assert format_quantity(None) == EM_DASH


def test_format_price_keeps_two_decimals() -> None:
    assert format_price(Decimal("150")) == "150.00"
    assert format_price(Decimal("150.5")) == "150.50"
    assert format_price(None) == EM_DASH

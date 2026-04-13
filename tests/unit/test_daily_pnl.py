"""Unit tests for daily_pnl.iter_month_days (Story 4.4)."""

from __future__ import annotations

from datetime import date

from app.services.daily_pnl import iter_month_days


def test_iter_month_days_non_leap_feb() -> None:
    days = iter_month_days(2025, 2)
    assert len(days) == 28
    assert days[0] == date(2025, 2, 1)
    assert days[-1] == date(2025, 2, 28)


def test_iter_month_days_leap_feb() -> None:
    days = iter_month_days(2024, 2)
    assert len(days) == 29
    assert days[-1] == date(2024, 2, 29)


def test_iter_month_days_full_31_day() -> None:
    days = iter_month_days(2026, 1)
    assert len(days) == 31
    assert days[0] == date(2026, 1, 1)
    assert days[-1] == date(2026, 1, 31)

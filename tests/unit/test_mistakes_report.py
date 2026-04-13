"""Unit tests for Story 3.4 mistakes report window resolution + helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.mistakes_report import MistakeRow, _resolve_window

NOW = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)


def test_resolve_window_default_30d() -> None:
    start, end = _resolve_window(None, now=NOW)
    assert end == NOW
    assert (end - start) == timedelta(days=30)


def test_resolve_window_7d() -> None:
    start, end = _resolve_window("7d", now=NOW)
    assert (end - start) == timedelta(days=7)


def test_resolve_window_90d() -> None:
    start, end = _resolve_window("90d", now=NOW)
    assert (end - start) == timedelta(days=90)


def test_resolve_window_ytd_starts_jan_1() -> None:
    start, end = _resolve_window("ytd", now=NOW)
    assert start == datetime(2026, 1, 1, tzinfo=UTC)
    assert end == NOW


def test_resolve_window_all_starts_2000() -> None:
    start, end = _resolve_window("all", now=NOW)
    assert start == datetime(2000, 1, 1, tzinfo=UTC)
    assert end == NOW


def test_resolve_window_unknown_falls_back_to_30d() -> None:
    """A typo in the URL must not crash — silently default to 30d."""

    start, end = _resolve_window("bogus", now=NOW)
    assert (end - start) == timedelta(days=30)


def test_mistake_row_float_helpers() -> None:
    """The template uses float-coerced helpers for the format_pnl filter."""

    row = MistakeRow(
        tag="fomo",
        count=7,
        total_pnl=Decimal("-1234.56"),
        avg_pnl=Decimal("-176.37"),
    )
    assert row.total_pnl_float == -1234.56
    assert row.avg_pnl_float == -176.37

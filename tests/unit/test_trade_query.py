"""Unit tests for `TradeListPage` pagination math (Story 2.3).

The DB-touching parts of `list_trades` are exercised in
`tests/integration/test_trade_query.py`. These tests focus on the
pure pagination helpers that don't need a real connection.
"""

from __future__ import annotations

import pytest

from app.services.trade_query import TradeListPage


def _page(*, total: int, page: int = 1, per_page: int = 30) -> TradeListPage:
    return TradeListPage(
        trades=[],
        untagged_count=0,
        total_count=total,
        page=page,
        per_page=per_page,
    )


@pytest.mark.parametrize(
    "total, per_page, expected_pages",
    [
        (0, 30, 1),
        (1, 30, 1),
        (30, 30, 1),
        (31, 30, 2),
        (60, 30, 2),
        (61, 30, 3),
        (2000, 30, 67),
    ],
)
def test_total_pages(total: int, per_page: int, expected_pages: int) -> None:
    p = _page(total=total, per_page=per_page)
    assert p.total_pages == expected_pages


def test_has_prev_false_on_first_page() -> None:
    assert _page(total=100, page=1).has_prev is False


def test_has_prev_true_on_second_page() -> None:
    assert _page(total=100, page=2).has_prev is True


def test_has_next_true_in_middle() -> None:
    assert _page(total=100, page=2, per_page=30).has_next is True


def test_has_next_false_on_last_page() -> None:
    p = _page(total=100, page=4, per_page=30)
    assert p.total_pages == 4
    assert p.has_next is False


def test_per_page_zero_falls_back_to_one_page() -> None:
    """Defensive: invalid per_page should not divide by zero."""

    p = TradeListPage(trades=[], untagged_count=0, total_count=10, page=1, per_page=0)
    assert p.total_pages == 1

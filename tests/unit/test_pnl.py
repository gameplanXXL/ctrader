"""Unit tests for `compute_pnl` (Story 2.4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.pnl import compute_pnl


def _trade(**overrides):
    base = {
        "side": "buy",
        "entry_price": Decimal("150.00"),
        "exit_price": Decimal("155.00"),
        "quantity": Decimal("100"),
        "fees": Decimal("1.50"),
    }
    base.update(overrides)
    return base


def test_long_winner_after_fees() -> None:
    """Buy 100 at 150, sell at 155, fees 1.50 → +498.50"""

    pnl = compute_pnl(_trade())
    assert pnl == Decimal("498.50")


def test_long_loser_after_fees() -> None:
    pnl = compute_pnl(_trade(exit_price=Decimal("145.00")))
    assert pnl == Decimal("-501.50")


def test_short_winner_after_fees() -> None:
    """Short at 150, cover at 145 → +500 - 1.50 = +498.50"""

    pnl = compute_pnl(_trade(side="short", exit_price=Decimal("145.00")))
    assert pnl == Decimal("498.50")


def test_short_loser_after_fees() -> None:
    pnl = compute_pnl(_trade(side="short", exit_price=Decimal("155.00")))
    assert pnl == Decimal("-501.50")


def test_returns_none_for_open_trade() -> None:
    assert compute_pnl(_trade(exit_price=None)) is None


@pytest.mark.parametrize(
    "missing_field",
    ["entry_price", "exit_price", "quantity"],
)
def test_returns_none_for_missing_field(missing_field: str) -> None:
    trade = _trade()
    trade[missing_field] = None
    assert compute_pnl(trade) is None


def test_returns_none_for_unknown_side() -> None:
    assert compute_pnl(_trade(side="unknown")) is None


def test_handles_zero_fees() -> None:
    pnl = compute_pnl(_trade(fees=Decimal("0")))
    assert pnl == Decimal("500.00")

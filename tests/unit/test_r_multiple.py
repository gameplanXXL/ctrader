"""Unit tests for `compute_r_multiple` (Story 2.4, FR12)."""

from __future__ import annotations

from decimal import Decimal

from app.services.r_multiple import compute_r_multiple


def _trade(**overrides):
    base = {
        "side": "buy",
        "entry_price": Decimal("150.00"),
        "exit_price": Decimal("155.00"),
        "stop_price": Decimal("145.00"),
    }
    base.update(overrides)
    return base


def test_long_one_r_winner() -> None:
    """Entry 150, stop 145 → risk 5; exit 155 → +1R."""

    r = compute_r_multiple(_trade())
    assert r == Decimal("1")


def test_long_two_r_winner() -> None:
    r = compute_r_multiple(_trade(exit_price=Decimal("160.00")))
    assert r == Decimal("2")


def test_long_minus_one_r_full_stop_hit() -> None:
    r = compute_r_multiple(_trade(exit_price=Decimal("145.00")))
    assert r == Decimal("-1")


def test_short_one_r_winner() -> None:
    """Short at 150, stop 155 (above), cover at 145 → +1R."""

    r = compute_r_multiple(
        _trade(
            side="short",
            entry_price=Decimal("150.00"),
            stop_price=Decimal("155.00"),
            exit_price=Decimal("145.00"),
        )
    )
    assert r == Decimal("1")


def test_returns_none_when_stop_missing_FR12() -> None:
    """FR12: missing stop must return None, NEVER 0."""

    trade = _trade()
    trade.pop("stop_price")
    assert compute_r_multiple(trade) is None


def test_returns_none_when_stop_equals_entry() -> None:
    """Stop == entry → undefined R, not 0."""

    assert compute_r_multiple(_trade(stop_price=Decimal("150.00"))) is None


def test_returns_none_for_open_trade() -> None:
    assert compute_r_multiple(_trade(exit_price=None)) is None


def test_alternative_stop_keys() -> None:
    """Reads `initial_stop` or `initial_stop_price` as fallback so the
    function is forward-compatible with Migration 005 (Story 11.2)."""

    trade = {
        "side": "buy",
        "entry_price": Decimal("100"),
        "exit_price": Decimal("110"),
        "initial_stop": Decimal("90"),
    }
    assert compute_r_multiple(trade) == Decimal("1")

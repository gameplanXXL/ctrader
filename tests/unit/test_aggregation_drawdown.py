"""Unit tests for the drawdown-baseline fix (code-review H3)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.aggregation import compute_aggregation


class _FakeConn:
    """Mocks `conn.fetch(_SQL, *params)` with a fixed row list."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def fetch(self, *_args, **_kwargs) -> list[dict]:  # noqa: ANN002, ANN003
        return self._rows


def _row(idx: int, pnl: float) -> dict:
    """A closed-trade row with the given pnl."""

    return {
        "id": idx,
        "symbol": "AAPL",
        "asset_class": "stock",
        "side": "buy",
        "quantity": Decimal("10"),
        "entry_price": Decimal("100"),
        "exit_price": Decimal("110"),
        "opened_at": datetime(2026, 4, 10, 14, idx, tzinfo=UTC),
        "closed_at": datetime(2026, 4, 10, 15, idx, tzinfo=UTC),
        "pnl": Decimal(str(pnl)),
        "fees": Decimal("0"),
    }


@pytest.mark.asyncio
async def test_drawdown_single_winning_trade_is_zero() -> None:
    conn = _FakeConn([_row(1, 100)])
    result = await compute_aggregation(conn, facets={})
    assert result.max_drawdown == Decimal("0")


@pytest.mark.asyncio
async def test_drawdown_single_losing_trade_is_zero_not_total_loss() -> None:
    """Code-review H3 / BH-4 / EC-8: a single losing trade should
    report drawdown = 0 against its own baseline (no prior peak to
    fall from), NOT -100 from the phantom zero equity curve."""

    conn = _FakeConn([_row(1, -100)])
    result = await compute_aggregation(conn, facets={})
    assert result.max_drawdown == Decimal("0")
    assert result.total_pnl == Decimal("-100")


@pytest.mark.asyncio
async def test_drawdown_purely_losing_series_measures_from_first_peak() -> None:
    """A series of three -50 losses: cum -50/-100/-150. The running
    max seeds to -50 (the first trade), so the peak-to-trough falls
    from -50 to -150 → drawdown -100. Under the OLD broken baseline
    this would have been -150 (from phantom zero)."""

    conn = _FakeConn([_row(1, -50), _row(2, -50), _row(3, -50)])
    result = await compute_aggregation(conn, facets={})
    assert result.total_pnl == Decimal("-150")
    assert result.max_drawdown == Decimal("-100")


@pytest.mark.asyncio
async def test_drawdown_win_then_loss_is_negative_difference() -> None:
    conn = _FakeConn([_row(1, 100), _row(2, -40)])
    result = await compute_aggregation(conn, facets={})
    # running_max hits 100 at trade 1; cum drops to 60 at trade 2;
    # drawdown = 60 - 100 = -40.
    assert result.max_drawdown == Decimal("-40")


@pytest.mark.asyncio
async def test_drawdown_monotonic_increasing_is_zero() -> None:
    conn = _FakeConn([_row(1, 10), _row(2, 20), _row(3, 30)])
    result = await compute_aggregation(conn, facets={})
    assert result.max_drawdown == Decimal("0")

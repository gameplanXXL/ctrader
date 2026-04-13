"""Unit tests for MAE/MFE sign convention (code-review H2)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.ohlc import Candle, Timeframe
from app.services.mae_mfe import compute_mae_mfe


class _StubConn:
    """Minimal async conn stub — we mock `_get_candles` via patch."""


def _candle(high: str, low: str, offset: int = 0) -> Candle:
    return Candle(
        symbol="TEST",
        timeframe=Timeframe.M1,
        ts=datetime(2026, 4, 10, 14, offset, tzinfo=UTC),
        open=Decimal(high),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(high),
    )


@pytest.mark.asyncio
async def test_long_that_never_dips_clamps_mae_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Code-review H2 / BH-7: a long trade whose lowest low is ABOVE
    entry should report MAE = 0 (never went adverse), not a fabricated
    positive number."""

    from app.services import mae_mfe as module

    async def _fake_get_candles(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return [_candle("150", "149")]

    monkeypatch.setattr(module, "_get_candles", _fake_get_candles)

    trade = {
        "symbol": "AAPL",
        "side": "buy",
        "entry_price": Decimal("148"),  # entry below lowest low
        "quantity": Decimal("100"),
        "opened_at": datetime(2026, 4, 10, 14, 0, tzinfo=UTC),
        "closed_at": datetime(2026, 4, 10, 14, 5, tzinfo=UTC),
    }

    result = await compute_mae_mfe(_StubConn(), trade)
    assert result.mae_price == Decimal("0")
    assert result.mae_dollars == Decimal("0")
    assert result.mfe_price == Decimal("2")  # hi - entry = 150 - 148


@pytest.mark.asyncio
async def test_long_that_never_rallies_clamps_mfe_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import mae_mfe as module

    async def _fake_get_candles(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return [_candle("100", "95")]

    monkeypatch.setattr(module, "_get_candles", _fake_get_candles)

    trade = {
        "symbol": "AAPL",
        "side": "buy",
        "entry_price": Decimal("102"),  # entry above highest high
        "quantity": Decimal("10"),
        "opened_at": datetime(2026, 4, 10, 14, 0, tzinfo=UTC),
        "closed_at": datetime(2026, 4, 10, 14, 5, tzinfo=UTC),
    }

    result = await compute_mae_mfe(_StubConn(), trade)
    assert result.mfe_price == Decimal("0")
    assert result.mae_price == Decimal("-7")  # 95 - 102


@pytest.mark.asyncio
async def test_short_that_never_rallies_clamps_mae_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Code-review H2 / EC-29: a short whose highest high is BELOW
    entry should report MAE = 0 (the price never moved adverse to
    the short), not a fabricated negative."""

    from app.services import mae_mfe as module

    async def _fake_get_candles(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return [_candle("99", "95")]

    monkeypatch.setattr(module, "_get_candles", _fake_get_candles)

    trade = {
        "symbol": "AAPL",
        "side": "short",
        "entry_price": Decimal("100"),  # entry above high
        "quantity": Decimal("50"),
        "opened_at": datetime(2026, 4, 10, 14, 0, tzinfo=UTC),
        "closed_at": datetime(2026, 4, 10, 14, 5, tzinfo=UTC),
    }

    result = await compute_mae_mfe(_StubConn(), trade)
    assert result.mae_price == Decimal("0")
    assert result.mfe_price == Decimal("5")  # entry - lo = 100 - 95


@pytest.mark.asyncio
async def test_signed_quantity_gets_absolutized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Code-review BH-10: a negative quantity (short report convention)
    must not flip the dollar-unit sign."""

    from app.services import mae_mfe as module

    async def _fake_get_candles(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return [_candle("102", "101")]

    monkeypatch.setattr(module, "_get_candles", _fake_get_candles)

    trade = {
        "symbol": "AAPL",
        "side": "buy",
        "entry_price": Decimal("100"),
        "quantity": Decimal("-10"),  # signed negative
        "opened_at": datetime(2026, 4, 10, 14, 0, tzinfo=UTC),
        "closed_at": datetime(2026, 4, 10, 14, 5, tzinfo=UTC),
    }

    result = await compute_mae_mfe(_StubConn(), trade)
    assert result.mfe_price == Decimal("2")
    assert result.mfe_dollars == Decimal("20")  # 2 * abs(-10)

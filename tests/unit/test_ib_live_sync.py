"""Unit tests for the IB live-sync handler (Story 2.2).

Mocks the ib_async Trade event shape (`contract`, `order`, `fills`,
`fills[i].execution`, `fills[i].commissionReport`) so the handler can
be tested without a real IB connection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.trade import AssetClass, TradeSide, TradeSource
from app.services.ib_live_sync import execution_to_trade


def _make_event(
    *,
    sec_type: str = "STK",
    symbol: str = "AAPL",
    action: str = "BUY",
    fills: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Build a minimal ib_async Trade-event lookalike."""

    return SimpleNamespace(
        contract=SimpleNamespace(secType=sec_type, symbol=symbol),
        order=SimpleNamespace(action=action),
        fills=fills or [],
    )


def _make_fill(
    *,
    shares: float,
    price: float,
    perm_id: int = 1234,
    commission: float = -1.0,
    time: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        execution=SimpleNamespace(
            shares=shares,
            price=price,
            permId=perm_id,
            time=time or datetime(2026, 4, 13, 14, 30, tzinfo=UTC),
        ),
        commissionReport=SimpleNamespace(commission=commission),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_single_fill_stock_buy_converts_cleanly() -> None:
    event = _make_event(fills=[_make_fill(shares=100, price=150.0)])

    trade = execution_to_trade(event)

    assert trade is not None
    assert trade.symbol == "AAPL"
    assert trade.asset_class is AssetClass.STOCK
    assert trade.side is TradeSide.BUY
    assert trade.quantity == Decimal("100")
    assert trade.entry_price == Decimal("150.0")
    assert trade.fees == Decimal("1.0")
    assert trade.broker is TradeSource.IB
    assert trade.perm_id == "1234"


def test_multi_fill_uses_weighted_average_price() -> None:
    """Two partial fills at different prices → weighted average."""

    event = _make_event(
        fills=[
            _make_fill(shares=60, price=150.0, commission=-0.6),
            _make_fill(shares=40, price=151.0, commission=-0.4),
        ]
    )

    trade = execution_to_trade(event)

    assert trade is not None
    assert trade.quantity == Decimal("100")
    # 60*150 + 40*151 = 15040 / 100 = 150.40
    assert trade.entry_price == Decimal("150.4")
    assert trade.fees == Decimal("1.0")


def test_option_event_is_recognized() -> None:
    event = _make_event(
        sec_type="OPT",
        symbol="AAPL  260620C00160000",
        fills=[_make_fill(shares=2, price=3.5)],
    )

    trade = execution_to_trade(event)
    assert trade is not None
    assert trade.asset_class is AssetClass.OPTION


def test_sell_action_maps_to_sell_side() -> None:
    event = _make_event(action="SELL", fills=[_make_fill(shares=50, price=380.0)])
    trade = execution_to_trade(event)
    assert trade is not None
    assert trade.side is TradeSide.SELL


def test_uses_earliest_fill_time_as_opened_at() -> None:
    early = datetime(2026, 4, 13, 14, 30, tzinfo=UTC)
    late = datetime(2026, 4, 13, 14, 35, tzinfo=UTC)

    event = _make_event(
        fills=[
            _make_fill(shares=50, price=150.0, time=late),
            _make_fill(shares=50, price=151.0, time=early),
        ]
    )

    trade = execution_to_trade(event)
    assert trade is not None
    assert trade.opened_at == early


# ---------------------------------------------------------------------------
# Skip cases — handler must return None, not raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field, broken_event",
    [
        ("contract", SimpleNamespace(contract=None, order=SimpleNamespace(action="BUY"), fills=[])),
        ("symbol", _make_event(symbol="", fills=[_make_fill(shares=1, price=1)])),
        ("fills", _make_event(fills=[])),
        (
            "asset_class",
            _make_event(sec_type="FUT", fills=[_make_fill(shares=1, price=1)]),
        ),
        (
            "side",
            _make_event(action="WTF", fills=[_make_fill(shares=1, price=1)]),
        ),
    ],
)
def test_skips_unsupported_or_invalid_events(missing_field: str, broken_event) -> None:
    assert execution_to_trade(broken_event) is None


def test_zero_quantity_fill_returns_none() -> None:
    event = _make_event(fills=[_make_fill(shares=0, price=150.0)])
    assert execution_to_trade(event) is None


def test_zero_price_fill_returns_none() -> None:
    event = _make_event(fills=[_make_fill(shares=10, price=0)])
    assert execution_to_trade(event) is None

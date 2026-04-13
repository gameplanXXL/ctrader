"""Unit tests for the IB Flex Query XML parser (Story 2.1).

Pure parser tests — no DB. The integration test in
`tests/integration/test_flex_import.py` covers the upsert path.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.models.trade import AssetClass, TradeSide, TradeSource
from app.services.ib_flex_import import (
    _parse_decimal,
    _parse_ib_datetime,
    parse_flex_xml,
)

SAMPLE_XML = (Path(__file__).resolve().parents[1] / "fixtures" / "sample_flex_query.xml").read_text(
    encoding="utf-8"
)


# ---------------------------------------------------------------------------
# parse_flex_xml — top-level
# ---------------------------------------------------------------------------


def test_parses_two_stocks_and_one_single_leg_option_from_sample() -> None:
    """The sample fixture has 2 stocks + 1 single-leg option + 2 spread legs + 1 broken row.

    Expected counts:
    - 3 valid trades (2 STK + 1 single-leg OPT)
    - 2 multi-leg legs skipped
    - 1 invalid (missing permID) skipped
    """

    trades, multi_leg, invalid = parse_flex_xml(SAMPLE_XML)

    assert len(trades) == 3
    assert multi_leg == 2
    assert invalid == 1


def test_imported_trades_have_expected_fields() -> None:
    trades, _, _ = parse_flex_xml(SAMPLE_XML)

    by_perm = {t.perm_id: t for t in trades}
    assert "1000000001" in by_perm
    assert "1000000002" in by_perm
    assert "2000000001" in by_perm

    aapl = by_perm["1000000001"]
    assert aapl.symbol == "AAPL"
    assert aapl.asset_class is AssetClass.STOCK
    assert aapl.side is TradeSide.BUY
    assert aapl.quantity == Decimal("100")
    assert aapl.entry_price == Decimal("150.00")
    assert aapl.broker is TradeSource.IB
    assert aapl.fees == Decimal("1.00")  # IB commission absolutized

    msft = by_perm["1000000002"]
    assert msft.symbol == "MSFT"
    assert msft.side is TradeSide.SELL
    assert msft.entry_price == Decimal("380.50")

    option = by_perm["2000000001"]
    assert option.asset_class is AssetClass.OPTION
    assert option.side is TradeSide.BUY
    assert option.quantity == Decimal("2")


def test_multi_leg_spread_is_skipped() -> None:
    """Both legs of the AAPL vertical spread (ORD-SPREAD-1) must be skipped."""

    trades, _, _ = parse_flex_xml(SAMPLE_XML)
    perm_ids = {t.perm_id for t in trades}

    assert "2000000002" not in perm_ids
    assert "2000000003" not in perm_ids


def test_missing_permid_row_is_invalid() -> None:
    """The BROKE row has no permID and counts as invalid."""

    trades, _, invalid = parse_flex_xml(SAMPLE_XML)
    assert invalid == 1
    assert all(t.symbol != "BROKE" for t in trades)


def test_parse_empty_response_returns_zero_trades() -> None:
    """An empty Flex response is handled gracefully."""

    empty = """<?xml version="1.0"?>
    <FlexQueryResponse>
      <FlexStatements count="0">
        <FlexStatement accountId="U1" fromDate="20260101" toDate="20260102">
          <Trades/>
        </FlexStatement>
      </FlexStatements>
    </FlexQueryResponse>"""

    trades, multi_leg, invalid = parse_flex_xml(empty)
    assert trades == []
    assert multi_leg == 0
    assert invalid == 0


# ---------------------------------------------------------------------------
# Helpers — _parse_ib_datetime, _parse_decimal
# ---------------------------------------------------------------------------


def test_parse_ib_datetime_handles_semicolon_separator() -> None:
    parsed = _parse_ib_datetime("20260410;093000")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 4
    assert parsed.day == 10
    assert parsed.hour == 9
    assert parsed.minute == 30
    # UTC-aware
    assert parsed.tzinfo is not None


def test_parse_ib_datetime_handles_space_separator() -> None:
    parsed = _parse_ib_datetime("20260410 094500")
    assert parsed is not None
    assert parsed.hour == 9
    assert parsed.minute == 45


def test_parse_ib_datetime_returns_none_for_garbage() -> None:
    assert _parse_ib_datetime(None) is None
    assert _parse_ib_datetime("") is None
    assert _parse_ib_datetime("not a date") is None


def test_parse_decimal_handles_empty_and_garbage() -> None:
    assert _parse_decimal(None) is None
    assert _parse_decimal("") is None
    assert _parse_decimal("not a number") is None
    assert _parse_decimal("3.50") == Decimal("3.50")
    assert _parse_decimal("-1.0") == Decimal("-1.0")

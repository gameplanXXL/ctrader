"""Unit tests for the IB Flex Query XML parser (Story 2.1).

Pure parser tests — no DB. The integration test in
`tests/integration/test_flex_import.py` covers the upsert path.

Updated after Epic-2 code review (Tranche A patches H3-H5):
- Sample XML now carries `openCloseIndicator` so we can verify the
  BUY+O/SELL+C/SELL+O/BUY+C → buy/sell/short/cover mapping.
- `accountTimezone="America/New_York"` is read from FlexStatement and
  used to localize the per-trade datetimes before converting to UTC.
"""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

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


def test_parses_four_valid_trades_from_sample() -> None:
    """The sample fixture has 4 valid trades + 2 spread legs + 1 broken row.

    Expected counts:
    - 4 valid trades:
        * 1000000001  AAPL BUY  (long open)
        * 1000000001b AAPL SELL (long close)
        * 1000000002  MSFT SHORT (short open via SELL+O)
        * 2000000001  AAPL OPT BUY (single-leg)
    - 2 multi-leg legs skipped
    - 1 invalid (missing permID) skipped
    """

    trades, multi_leg, invalid = parse_flex_xml(SAMPLE_XML)

    assert len(trades) == 4
    assert multi_leg == 2
    assert invalid == 1


def test_imported_trades_have_expected_fields() -> None:
    trades, _, _ = parse_flex_xml(SAMPLE_XML)

    by_perm = {t.perm_id: t for t in trades}
    assert "1000000001" in by_perm
    assert "1000000001b" in by_perm
    assert "1000000002" in by_perm
    assert "2000000001" in by_perm

    aapl_open = by_perm["1000000001"]
    assert aapl_open.symbol == "AAPL"
    assert aapl_open.asset_class is AssetClass.STOCK
    assert aapl_open.side is TradeSide.BUY
    assert aapl_open.quantity == Decimal("100")
    assert aapl_open.entry_price == Decimal("150.00")
    assert aapl_open.exit_price is None  # open execution
    assert aapl_open.closed_at is None
    assert aapl_open.broker is TradeSource.IB
    assert aapl_open.fees == Decimal("1.00")  # IB commission absolutized

    aapl_close = by_perm["1000000001b"]
    assert aapl_close.side is TradeSide.SELL  # SELL + C → sell (long close)
    assert aapl_close.exit_price == Decimal("151.50")  # close has exit_price
    assert aapl_close.closed_at is not None  # close has closed_at

    msft = by_perm["1000000002"]
    assert msft.symbol == "MSFT"
    # SELL + O → short, NOT plain sell (code-review fix H4)
    assert msft.side is TradeSide.SHORT
    assert msft.entry_price == Decimal("380.50")
    assert msft.closed_at is None  # open execution

    option = by_perm["2000000001"]
    assert option.asset_class is AssetClass.OPTION
    assert option.side is TradeSide.BUY  # BUY + O → buy
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


def test_account_timezone_is_respected() -> None:
    """`accountTimezone` from FlexStatement determines the local TZ.

    Code-review fix H5: the AAPL open at "20260410;093000" with
    accountTimezone="America/New_York" must be converted from
    09:30 NY → 13:30 UTC (April = EDT, UTC-4).
    """

    trades, _, _ = parse_flex_xml(SAMPLE_XML)
    by_perm = {t.perm_id: t for t in trades}
    aapl = by_perm["1000000001"]

    assert aapl.opened_at.tzinfo is not None
    assert aapl.opened_at == aapl.opened_at.astimezone(UTC)
    # 09:30 EDT → 13:30 UTC
    assert aapl.opened_at.hour == 13
    assert aapl.opened_at.minute == 30


# ---------------------------------------------------------------------------
# Helpers — _parse_ib_datetime, _parse_decimal
# ---------------------------------------------------------------------------


def test_parse_ib_datetime_localizes_to_account_tz_then_utc() -> None:
    """Without an explicit tz the function defaults to America/New_York."""

    parsed = _parse_ib_datetime("20260410;093000")
    assert parsed is not None
    assert parsed.tzinfo is not None
    # 09:30 NY in April = 13:30 UTC (EDT)
    assert parsed.hour == 13
    assert parsed.minute == 30


def test_parse_ib_datetime_explicit_tz() -> None:
    parsed = _parse_ib_datetime("20260410 094500", tz=ZoneInfo("Europe/Berlin"))
    assert parsed is not None
    # 09:45 Berlin in April = 07:45 UTC (CEST UTC+2)
    assert parsed.hour == 7
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

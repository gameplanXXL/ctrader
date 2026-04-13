"""Interactive Brokers Flex Query XML import.

Story 2.1: parses the historical trades XML produced by IB's Flex Query
service and upserts each trade into the `trades` table. Honors:

- FR1: stock trades imported.
- FR2: single-leg option trades imported, multi-leg spreads logged
  and skipped (Multi-Leg-Spreads sind explizit Phase 2).
- FR4 / NFR-R1: dedup via UNIQUE (broker, perm_id) so re-importing
  the same XML never changes the row count.

Multi-leg detection:
  IB groups multi-leg orders by sharing the same `ibOrderID` /
  `ibExecID` across multiple `<Trade>` elements that all carry an
  `assetCategory="OPT"`. We bucket option trades by (orderID,
  underlying) — anything with >1 leg in a bucket is a spread and is
  skipped.

The parser is intentionally lenient on schema variations because IB
ships several Flex schema versions over time and Chef has historical
data spanning multiple versions. Unknown attributes are ignored.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import asyncpg

from app.logging import get_logger
from app.models.trade import AssetClass, TradeIn, TradeSide, TradeSource

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportResult:
    """Outcome of a single Flex Query import."""

    parsed: int = 0
    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_multi_leg: int = 0
    skipped_invalid: int = 0


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------


def _attr(elem: ET.Element, name: str) -> str | None:
    """Lowercase-tolerant attribute lookup.

    Different Flex versions use either camelCase (`tradeID`) or the
    Web-Service style (`tradeId`). We normalise to a single lookup.
    """

    if name in elem.attrib:
        return elem.attrib[name]
    lower = name.lower()
    for k, v in elem.attrib.items():
        if k.lower() == lower:
            return v
    return None


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _parse_ib_datetime(raw: str | None) -> datetime | None:
    """Parse the IB Flex datetime format `YYYYMMDD;HHMMSS` (UTC).

    Some Flex versions use a space separator instead of a semicolon
    and/or omit the time component. We accept all observed shapes and
    return UTC-aware datetimes.
    """

    if raw is None or raw == "":
        return None
    text = raw.replace(";", " ").strip()
    candidates = ["%Y%m%d %H%M%S", "%Y%m%d %H:%M:%S", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]
    for fmt in candidates:
        try:
            parsed = datetime.strptime(text, fmt)  # noqa: DTZ007
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _map_side(buy_sell: str | None, quantity: Decimal | None) -> TradeSide | None:
    """Translate IB's `buySell` attribute + signed quantity to our enum.

    IB sends `BUY` / `SELL` / `BUY-CLOSE` / `SELL-CLOSE`. We collapse
    to four directions: BUY, SELL, SHORT, COVER. Negative quantity on
    a `SELL` is a short open; positive quantity on a `BUY` after a
    short is a cover. Without trade-state context we use the simple
    rule: BUY → buy, SELL → sell. Open/Close suffixes and SHORT/COVER
    inference happen in Story 2.2 (live sync) which has order context.
    """

    if buy_sell is None:
        return None
    upper = buy_sell.upper().strip()
    if upper.startswith("BUY"):
        return TradeSide.BUY
    if upper.startswith("SELL"):
        return TradeSide.SELL
    if upper.startswith("SHORT"):
        return TradeSide.SHORT
    if upper.startswith("COVER"):
        return TradeSide.COVER
    return None


def _asset_class_from_category(category: str | None) -> AssetClass | None:
    if category is None:
        return None
    upper = category.upper()
    if upper in ("STK", "STOCK", "EQUITY"):
        return AssetClass.STOCK
    if upper in ("OPT", "OPTION"):
        return AssetClass.OPTION
    return None


def _trade_from_element(elem: ET.Element) -> TradeIn | None:
    """Convert one `<Trade>` element to a `TradeIn`, or None on failure.

    Returns None for any reason the trade should be skipped — caller
    aggregates the skip-counts separately.
    """

    perm_id = _attr(elem, "permID") or _attr(elem, "permId")
    if not perm_id:
        return None

    symbol = _attr(elem, "symbol")
    if not symbol:
        return None

    asset_class = _asset_class_from_category(_attr(elem, "assetCategory"))
    if asset_class is None:
        return None

    quantity = _parse_decimal(_attr(elem, "quantity"))
    if quantity is None or quantity == 0:
        return None
    # IB encodes shorts/sells as negative quantity. We store absolute
    # quantity and rely on `side` for direction.
    quantity = abs(quantity)

    side = _map_side(_attr(elem, "buySell"), quantity)
    if side is None:
        return None

    entry_price = _parse_decimal(_attr(elem, "tradePrice"))
    if entry_price is None:
        return None

    opened_at = _parse_ib_datetime(_attr(elem, "dateTime"))
    if opened_at is None:
        return None

    fees_raw = _parse_decimal(_attr(elem, "ibCommission"))
    # IB reports commission as a negative number (it left the account).
    # Store it as a positive fee.
    fees = abs(fees_raw) if fees_raw is not None else Decimal("0")

    return TradeIn(
        symbol=symbol,
        asset_class=asset_class,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=None,
        opened_at=opened_at,
        closed_at=None,
        pnl=None,
        fees=fees,
        broker=TradeSource.IB,
        perm_id=perm_id,
    )


def _bucket_options(elements: Iterable[ET.Element]) -> dict[str, list[ET.Element]]:
    """Group option trades by (ibOrderID, underlying) so multi-leg
    spreads can be detected and skipped (FR2).
    """

    buckets: dict[str, list[ET.Element]] = defaultdict(list)
    for elem in elements:
        if _asset_class_from_category(_attr(elem, "assetCategory")) is not AssetClass.OPTION:
            continue
        order_id = _attr(elem, "ibOrderID") or _attr(elem, "orderID") or ""
        underlying = _attr(elem, "underlyingSymbol") or _attr(elem, "symbol") or ""
        key = f"{order_id}|{underlying}"
        buckets[key].append(elem)
    return buckets


# ---------------------------------------------------------------------------
# Top-level parse + import
# ---------------------------------------------------------------------------


def parse_flex_xml(xml_text: str) -> tuple[list[TradeIn], int, int]:
    """Parse a Flex Query XML payload.

    Returns `(trades, skipped_multi_leg, skipped_invalid)`. Pure
    function — no DB access. Useful for unit tests.
    """

    root = ET.fromstring(xml_text)

    # Flex XML uses both `<Trades>` (legacy) and direct `<Trade>` rows
    # under `<FlexStatement>`. We accept either by scanning all <Trade>
    # descendants.
    trade_elements = list(root.iter("Trade"))

    # ---- Multi-leg option detection (FR2) -------------------------------
    option_buckets = _bucket_options(trade_elements)
    multi_leg_perm_ids: set[str] = set()
    skipped_multi_leg = 0
    for legs in option_buckets.values():
        if len(legs) > 1:
            skipped_multi_leg += len(legs)
            for leg in legs:
                pid = _attr(leg, "permID") or _attr(leg, "permId")
                if pid:
                    multi_leg_perm_ids.add(pid)
            logger.warning(
                "ib_flex.skip_multi_leg",
                legs=len(legs),
                underlying=_attr(legs[0], "underlyingSymbol") or _attr(legs[0], "symbol"),
            )

    # ---- Convert remaining trades --------------------------------------
    trades: list[TradeIn] = []
    skipped_invalid = 0
    for elem in trade_elements:
        perm_id = _attr(elem, "permID") or _attr(elem, "permId")
        if perm_id and perm_id in multi_leg_perm_ids:
            continue  # already counted as multi-leg skip
        trade = _trade_from_element(elem)
        if trade is None:
            skipped_invalid += 1
            logger.warning(
                "ib_flex.skip_invalid",
                perm_id=perm_id,
                symbol=_attr(elem, "symbol"),
            )
            continue
        trades.append(trade)

    return trades, skipped_multi_leg, skipped_invalid


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------


_INSERT_SQL = """
INSERT INTO trades (
    symbol, asset_class, side, quantity, entry_price, exit_price,
    opened_at, closed_at, pnl, fees, broker, perm_id, trigger_spec
)
VALUES (
    $1, $2, $3, $4, $5, $6,
    $7, $8, $9, $10, $11, $12, $13::jsonb
)
ON CONFLICT (broker, perm_id) DO NOTHING
RETURNING id
"""


async def insert_trades(conn: asyncpg.Connection, trades: Iterable[TradeIn]) -> tuple[int, int]:
    """Insert trades, skipping duplicates via the UNIQUE constraint.

    Returns `(inserted_count, duplicate_count)`. Each insert runs as a
    separate statement so a duplicate doesn't roll back the whole batch.

    `trigger_spec` is JSON-serialised here because asyncpg's default
    codec for JSONB expects a string, not a Python dict. We could
    register `set_type_codec("jsonb", ...)` per-connection, but doing
    it here keeps the dependency injection-free.
    """

    import json

    inserted = 0
    duplicates = 0
    for trade in trades:
        trigger_spec_json = (
            json.dumps(trade.trigger_spec) if trade.trigger_spec is not None else None
        )
        row = await conn.fetchrow(
            _INSERT_SQL,
            trade.symbol,
            trade.asset_class.value,
            trade.side.value,
            trade.quantity,
            trade.entry_price,
            trade.exit_price,
            trade.opened_at,
            trade.closed_at,
            trade.pnl,
            trade.fees,
            trade.broker.value,
            trade.perm_id,
            trigger_spec_json,
        )
        if row is None:
            duplicates += 1
        else:
            inserted += 1
    return inserted, duplicates


async def import_flex_xml(conn: asyncpg.Connection, xml_text: str) -> ImportResult:
    """High-level entry point: parse + upsert + return aggregate result.

    Used by the CLI and the (future) admin upload endpoint.
    """

    trades, skipped_multi_leg, skipped_invalid = parse_flex_xml(xml_text)
    inserted, duplicates = await insert_trades(conn, trades)

    result = ImportResult(
        parsed=len(trades) + skipped_invalid + skipped_multi_leg,
        inserted=inserted,
        skipped_duplicate=duplicates,
        skipped_multi_leg=skipped_multi_leg,
        skipped_invalid=skipped_invalid,
    )
    logger.info(
        "ib_flex.import_done",
        parsed=result.parsed,
        inserted=result.inserted,
        skipped_duplicate=result.skipped_duplicate,
        skipped_multi_leg=result.skipped_multi_leg,
        skipped_invalid=result.skipped_invalid,
    )
    return result


async def import_flex_file(conn: asyncpg.Connection, path: Path) -> ImportResult:
    """Convenience wrapper: read XML from disk and import."""

    return await import_flex_xml(conn, path.read_text(encoding="utf-8"))

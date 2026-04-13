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
from datetime import UTC, datetime, tzinfo
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _resolve_tz(tz_name: str | None) -> tzinfo:
    """Resolve a Flex `accountTimezone` attribute (or settings fallback)
    to a `tzinfo`. Falls back to `America/New_York` (IB account default)
    if the name is missing or unrecognised.

    Code-review fix H5: previously every Flex datetime was hard-tagged
    as UTC even though IB ships datetimes in the account-configured
    timezone, shifting historical trades by 4-5 hours and silently
    breaking `opened_at DESC` ordering across DST.
    """

    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:
        return ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:  # pragma: no cover — minimal Linux missing tzdata
        return UTC


def _parse_ib_datetime(raw: str | None, tz: tzinfo | None = None) -> datetime | None:
    """Parse an IB Flex datetime string and return a UTC-aware datetime.

    Accepts the historical shapes IB has used over the years:
    - `YYYYMMDD;HHMMSS` (current default)
    - `YYYYMMDD HHMMSS` (space separator)
    - `YYYYMMDD HH:MM:SS`
    - `YYYY-MM-DD HH:MM:SS`
    - `YYYYMMDD` (date only — assumed midnight in account TZ)

    The parsed local datetime is localized using `tz` (defaults to
    `America/New_York` when not provided), then converted to UTC for
    storage. This matches Migration 002's `TIMESTAMPTZ` columns.
    """

    if raw is None or raw == "":
        return None
    text = raw.replace(";", " ").strip()
    candidates = ["%Y%m%d %H%M%S", "%Y%m%d %H:%M:%S", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]

    local_tz = tz or _resolve_tz(None)
    for fmt in candidates:
        try:
            parsed = datetime.strptime(text, fmt)  # noqa: DTZ007
            localized = parsed.replace(tzinfo=local_tz)
            return localized.astimezone(UTC)
        except ValueError:
            continue
    return None


def _map_side(buy_sell: str | None, open_close: str | None) -> TradeSide | None:
    """Translate IB's `buySell` + `openCloseIndicator` to our enum.

    Code-review fix H4: previously this function only read `buySell`
    and could never produce SHORT or COVER. IB Flex actually emits the
    direction in two attributes:
      - `buySell` ∈ {BUY, SELL}
      - `openCloseIndicator` ∈ {O (open), C (close)}

    Combined:
      BUY  + O → buy   (long open)
      SELL + C → sell  (long close)
      SELL + O → short (short open)
      BUY  + C → cover (short close)

    If `openCloseIndicator` is missing (very old Flex schemas), we
    default to OPEN — same conservative behavior as the previous
    BUY/SELL-only mapping.
    """

    if buy_sell is None:
        return None
    direction = buy_sell.upper().strip()
    state = (open_close or "O").upper().strip()

    if direction.startswith("BUY"):
        return TradeSide.COVER if state.startswith("C") else TradeSide.BUY
    if direction.startswith("SELL"):
        return TradeSide.SELL if state.startswith("C") else TradeSide.SHORT

    # Some Flex variants use the explicit SHORT/COVER strings — keep
    # the fallback for forward compatibility.
    if direction.startswith("SHORT"):
        return TradeSide.SHORT
    if direction.startswith("COVER"):
        return TradeSide.COVER
    return None


def _is_close_side(side: TradeSide | None) -> bool:
    """True if this side closes a position (sell-of-long, cover-of-short)."""

    return side in (TradeSide.SELL, TradeSide.COVER)


def _asset_class_from_category(category: str | None) -> AssetClass | None:
    if category is None:
        return None
    upper = category.upper()
    if upper in ("STK", "STOCK", "EQUITY"):
        return AssetClass.STOCK
    if upper in ("OPT", "OPTION"):
        return AssetClass.OPTION
    return None


def _trade_from_element(elem: ET.Element, tz: tzinfo | None = None) -> TradeIn | None:
    """Convert one `<Trade>` element to a `TradeIn`, or None on failure.

    Code-review fix H3: an IB Flex `<Trade>` row is an individual
    *execution*, not a round-trip. Every execution becomes its own
    trades-table row, with `side` derived from `buySell` +
    `openCloseIndicator`. For close-executions (`SELL` of a long,
    `BUY` of a short → `cover`), we set both `entry_price` and
    `exit_price` to the execution price, and `closed_at` to the
    execution time — that lets Story 2.3's untagged-counter (which
    keys on `closed_at IS NOT NULL`) work for Flex-imported data.
    Round-trip aggregation lives in Epic 6 (Strategy-Management).
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

    side = _map_side(_attr(elem, "buySell"), _attr(elem, "openCloseIndicator"))
    if side is None:
        return None

    price = _parse_decimal(_attr(elem, "tradePrice"))
    if price is None:
        return None

    when = _parse_ib_datetime(_attr(elem, "dateTime"), tz=tz)
    if when is None:
        return None

    fees_raw = _parse_decimal(_attr(elem, "ibCommission"))
    # IB reports commission as a negative number (it left the account).
    # Store it as a positive fee.
    fees = abs(fees_raw) if fees_raw is not None else Decimal("0")

    is_close = _is_close_side(side)

    # For close executions, both opened_at and closed_at point at the
    # execution time and both prices point at the execution price —
    # we don't have round-trip data without correlating to the matching
    # open execution (Epic 6). For open executions, exit_price and
    # closed_at stay None and the row is "live" until a matching close
    # arrives.
    return TradeIn(
        symbol=symbol,
        asset_class=asset_class,
        side=side,
        quantity=quantity,
        entry_price=price,
        exit_price=price if is_close else None,
        opened_at=when,
        closed_at=when if is_close else None,
        pnl=None,
        fees=fees,
        broker=TradeSource.IB,
        perm_id=perm_id,
    )


def _bucket_options(elements: Iterable[ET.Element]) -> dict[str, list[ET.Element]]:
    """Group option trades by (ibOrderID, underlying) so multi-leg
    spreads can be detected and skipped (FR2).

    Code-review fix M1: when both order-ID attributes are missing,
    we fall back to the trade's own `permID` so that two unrelated
    single-leg options on the same underlying don't accidentally end
    up bucketed together and get misclassified as a spread.
    """

    buckets: dict[str, list[ET.Element]] = defaultdict(list)
    for elem in elements:
        if _asset_class_from_category(_attr(elem, "assetCategory")) is not AssetClass.OPTION:
            continue
        order_id = _attr(elem, "ibOrderID") or _attr(elem, "orderID")
        if not order_id:
            # Safe fallback: the trade's own permID is unique per
            # execution, so bucketing by it guarantees `len(bucket) == 1`
            # and no false multi-leg detection.
            order_id = _attr(elem, "permID") or _attr(elem, "permId") or ""
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

    Reads `accountTimezone` (or `flexStatementTimezone`) from the
    `<FlexStatement>` element so per-trade datetimes are localized
    correctly before being normalised to UTC. See `_parse_ib_datetime`
    for the full convention (code-review fix H5).
    """

    root = ET.fromstring(xml_text)

    # Locate the FlexStatement so we can read its account timezone
    # attribute. Some legacy schemas put it on FlexQueryResponse —
    # we accept either. Default is America/New_York, IB's account
    # default.
    statement = next(root.iter("FlexStatement"), None)
    tz_name = None
    if statement is not None:
        tz_name = statement.attrib.get("accountTimezone") or statement.attrib.get(
            "flexStatementTimezone"
        )
    if tz_name is None:
        tz_name = root.attrib.get("accountTimezone") or root.attrib.get("flexStatementTimezone")
    account_tz = _resolve_tz(tz_name)

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
        trade = _trade_from_element(elem, tz=account_tz)
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
    $7, $8, $9, $10, $11, $12, $13
)
ON CONFLICT (broker, perm_id) DO NOTHING
RETURNING id
"""

# Live-sync UPSERT: when ib_async fires `execDetailsEvent` multiple
# times for the same order (multi-fill), we MUST update the existing
# row with the latest aggregate, not silently drop it.
# Code-review fix H2.
_UPSERT_SQL = """
INSERT INTO trades (
    symbol, asset_class, side, quantity, entry_price, exit_price,
    opened_at, closed_at, pnl, fees, broker, perm_id, trigger_spec
)
VALUES (
    $1, $2, $3, $4, $5, $6,
    $7, $8, $9, $10, $11, $12, $13
)
ON CONFLICT (broker, perm_id) DO UPDATE
   SET quantity    = EXCLUDED.quantity,
       entry_price = EXCLUDED.entry_price,
       exit_price  = COALESCE(EXCLUDED.exit_price, trades.exit_price),
       opened_at   = LEAST(EXCLUDED.opened_at, trades.opened_at),
       closed_at   = COALESCE(EXCLUDED.closed_at, trades.closed_at),
       fees        = EXCLUDED.fees,
       updated_at  = NOW()
RETURNING id, (xmax = 0) AS inserted
"""


def _trigger_spec_json(spec: Any) -> dict[str, Any] | None:
    """Normalize `trigger_spec` for asyncpg's JSONB codec.

    asyncpg's JSONB codec (registered in `app.db.pool._init_connection`)
    accepts Python dicts directly and encodes them with `json.dumps`.
    This helper round-trips once through `json.dumps(..., default=str)`
    so Decimal / datetime / custom objects flatten to primitives
    BEFORE the codec hits them — the defensive layer from code-review
    fix M12 is preserved.
    """

    if spec is None:
        return None
    import json as _json

    return _json.loads(_json.dumps(spec, default=str, sort_keys=True))


async def insert_trades(conn: asyncpg.Connection, trades: Iterable[TradeIn]) -> tuple[int, int]:
    """Insert trades, skipping duplicates via the UNIQUE constraint.

    Returns `(inserted_count, duplicate_count)`. Used by historical Flex
    imports — duplicates are deliberately dropped, not updated, so a
    re-import is purely additive.

    For multi-fill live-sync events the right primitive is `upsert_trade`
    below, which UPDATES on conflict so subsequent fills enrich the row.
    """

    inserted = 0
    duplicates = 0
    async with conn.transaction():
        for trade in trades:
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
                _trigger_spec_json(trade.trigger_spec),
            )
            if row is None:
                duplicates += 1
            else:
                inserted += 1
    return inserted, duplicates


async def upsert_trade(conn: asyncpg.Connection, trade: TradeIn) -> tuple[int, bool]:
    """Insert OR update a trade, keyed on `(broker, perm_id)`.

    Returns `(trade_id, was_inserted)`. Used by the live-sync handler
    (Story 2.2) so that subsequent fills of the same order ENRICH the
    existing row instead of being silently dropped as duplicates
    (code-review fix H2).
    """

    row = await conn.fetchrow(
        _UPSERT_SQL,
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
        _trigger_spec_json(trade.trigger_spec),
    )
    if row is None:
        # Should not happen with ON CONFLICT DO UPDATE, but never crash.
        return -1, False
    return int(row["id"]), bool(row["inserted"])


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

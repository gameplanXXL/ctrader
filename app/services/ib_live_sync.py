"""Live IB execution → trades-table sync handler (Story 2.2).

Subscribes to `ib.execDetailsEvent` and turns each incoming execution
into a `TradeIn` + ON CONFLICT INSERT. The Flex import in Story 2.1
is the historical-batch path; this module is the real-time path.

Reconciliation against Flex (FR5: Flex is source-of-truth) lives in
`app.services.ib_reconcile` and runs on a schedule that Story 12.1
will register with APScheduler.

Story 5.2 hook: after a new trade row lands, the handler
fire-and-forgets a fundamental snapshot capture so the drilldown
can later show "damals vs jetzt" side-by-side. The capture is
wrapped in `asyncio.create_task` so a slow MCP call never blocks
the live-sync loop.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.trade import AssetClass, TradeIn, TradeSide, TradeSource
from app.services.fundamental_snapshot import capture_fundamental_snapshot
from app.services.ib_flex_import import upsert_trade

logger = get_logger(__name__)

# Code-review H4 / BH-13 / EC-17: hold strong references to every
# in-flight fire-and-forget snapshot task so the GC can't collect
# them mid-run. Python's `asyncio.create_task` docs explicitly
# require callers to keep a reference for the task's lifetime.
_background_tasks: set[asyncio.Task] = set()


def _map_asset_class(sec_type: str | None) -> AssetClass | None:
    if sec_type is None:
        return None
    upper = sec_type.upper()
    if upper in ("STK", "STOCK", "EQUITY"):
        return AssetClass.STOCK
    if upper in ("OPT", "OPTION"):
        return AssetClass.OPTION
    return None


def _map_side(action: str | None) -> TradeSide | None:
    if action is None:
        return None
    upper = action.upper().strip()
    if upper.startswith("BUY"):
        return TradeSide.BUY
    if upper.startswith("SELL"):
        return TradeSide.SELL
    if upper.startswith("SHORT"):
        return TradeSide.SHORT
    if upper.startswith("COVER"):
        return TradeSide.COVER
    return None


def execution_to_trade(trade_event: Any) -> TradeIn | None:
    """Convert an ib_async Trade / Execution event into a TradeIn.

    The event shape is `Trade(contract, order, orderStatus, fills, ...)`
    where `fills` is a list of `Fill(execution, commissionReport, ...)`.
    For now we collapse a multi-fill order into a single trade row by
    summing quantities and using the average fill price. Later stories
    can split into one row per fill if needed.

    Returns None for any reason the event should be skipped (unsupported
    asset class, missing fields, no fills yet).
    """

    contract = getattr(trade_event, "contract", None)
    if contract is None:
        return None

    asset_class = _map_asset_class(getattr(contract, "secType", None))
    if asset_class is None:
        return None

    symbol = getattr(contract, "symbol", None)
    if not symbol:
        return None

    order = getattr(trade_event, "order", None)
    side = _map_side(getattr(order, "action", None) if order else None)
    if side is None:
        return None

    fills = getattr(trade_event, "fills", None) or []
    if not fills:
        return None

    total_qty = Decimal("0")
    weighted_price = Decimal("0")
    total_fees = Decimal("0")
    perm_id: str | None = None
    earliest_time: datetime | None = None

    for fill in fills:
        execution = getattr(fill, "execution", None)
        if execution is None:
            continue

        # ib_async exposes shares as float; we promote to Decimal.
        shares = Decimal(str(getattr(execution, "shares", 0) or 0))
        price = Decimal(str(getattr(execution, "price", 0) or 0))
        if shares <= 0 or price <= 0:
            continue

        total_qty += shares
        weighted_price += shares * price

        commission_report = getattr(fill, "commissionReport", None)
        if commission_report is not None:
            commission = getattr(commission_report, "commission", None)
            if commission is not None:
                total_fees += abs(Decimal(str(commission)))

        if perm_id is None:
            ib_perm_id = getattr(execution, "permId", None)
            if ib_perm_id is not None:
                perm_id = str(ib_perm_id)

        exec_time = getattr(execution, "time", None)
        if isinstance(exec_time, datetime):
            if exec_time.tzinfo is None:
                exec_time = exec_time.replace(tzinfo=UTC)
            if earliest_time is None or exec_time < earliest_time:
                earliest_time = exec_time

    if total_qty <= 0 or weighted_price <= 0 or perm_id is None:
        return None

    avg_price = weighted_price / total_qty

    return TradeIn(
        symbol=symbol,
        asset_class=asset_class,
        side=side,
        quantity=total_qty,
        entry_price=avg_price,
        exit_price=None,
        opened_at=earliest_time or datetime.now(UTC),
        closed_at=None,
        pnl=None,
        fees=total_fees,
        broker=TradeSource.IB,
        perm_id=perm_id,
    )


async def handle_execution(
    conn: asyncpg.Connection,
    trade_event: Any,
    *,
    mcp_client: MCPClient | None = None,
    db_pool: Any = None,
) -> bool:
    """Process one ib_async Trade event → upsert into trades table.

    Returns True if a new row was inserted, False if an existing row
    was updated. Code-review fix H2: previously this used
    `INSERT ... ON CONFLICT DO NOTHING`, which silently dropped every
    subsequent fill of a multi-fill order — only the first fill
    persisted. Now uses `upsert_trade` so additional fills enrich
    the existing row (quantity, fees, weighted price are recomputed
    from the full fills list before each call by `execution_to_trade`).

    Story 5.2: on a newly-inserted trade, schedule a fundamental
    snapshot capture. The capture runs in its own task with its own
    DB connection from the pool so the live-sync handler can return
    immediately.

    Code-review M13 / EC-5 — wiring note for Story 12.1: when
    `ib.execDetailsEvent` is subscribed, the event dispatcher
    passes only the Trade argument. Use `functools.partial` to bind
    `conn`, `mcp_client`, and `db_pool` at subscribe time:

        from functools import partial
        ib.execDetailsEvent += partial(
            handle_execution,
            conn=..., mcp_client=..., db_pool=...,
        )

    Without this, `mcp_client` and `db_pool` default to `None` and
    the snapshot capture silently skips.
    """

    trade_in = execution_to_trade(trade_event)
    if trade_in is None:
        logger.warning(
            "ib_live_sync.skip",
            reason="event_not_convertible",
            symbol=getattr(getattr(trade_event, "contract", None), "symbol", None),
        )
        return False

    trade_id, inserted = await upsert_trade(conn, trade_in)
    logger.info(
        "ib_live_sync.upserted",
        trade_id=trade_id,
        symbol=trade_in.symbol,
        side=trade_in.side.value,
        quantity=str(trade_in.quantity),
        perm_id=trade_in.perm_id,
        action="inserted" if inserted else "updated",
    )

    if inserted and mcp_client is not None and db_pool is not None:
        task = asyncio.create_task(
            _capture_snapshot_fire_and_forget(
                db_pool=db_pool,
                trade_id=trade_id,
                symbol=trade_in.symbol,
                asset_class=trade_in.asset_class.value,
                mcp_client=mcp_client,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return inserted


async def _capture_snapshot_fire_and_forget(
    *,
    db_pool: Any,
    trade_id: int,
    symbol: str,
    asset_class: str,
    mcp_client: MCPClient,
) -> None:
    """Wrapper task: acquire a fresh connection from the pool and
    call `capture_fundamental_snapshot`. Never raises — any failure
    is logged inside the snapshot service."""

    try:
        async with db_pool.acquire() as snap_conn:
            await capture_fundamental_snapshot(
                snap_conn,
                trade_id=trade_id,
                symbol=symbol,
                asset_class=asset_class,
                mcp_client=mcp_client,
            )
    except Exception as exc:  # noqa: BLE001 — fire-and-forget
        logger.warning(
            "fundamental_snapshot.task_failed",
            trade_id=trade_id,
            symbol=symbol,
            error=str(exc),
        )

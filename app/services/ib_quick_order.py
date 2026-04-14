"""IB Quick-Order service (Epic 12 / Stories 12.1–12.4).

Owns:
- `submit_quick_order(conn, client, form)` — the end-to-end path
  called from `POST /trades/quick-order/submit`. Persists the
  `quick_orders` row with its idempotency key BEFORE the network
  call, runs the retry loop, updates the row on result.
- `handle_fill_event(conn, event)` — consumes `ExecutionEvent`s
  from the Quick-Order client and on FILLED inserts a new row
  into `trades` with `trigger_spec` auto-tagged (Story 12.3 AC #2).
- `compute_preview(client, form)` — builds the Bestätigungs-UI
  view model including the `whatIfOrder` margin estimate for
  Short-Options. No DB writes.
- `place_order_with_retry(client, request)` — bounded exponential
  backoff on `IBTransientError`, short-circuit on `IBTerminalError`.

Idempotency contract (NFR-R3a): the `order_ref` UNIQUE constraint
in Migration 018 is the database-level guarantor. Service layer
persists the row BEFORE the network call so a process crash between
the `INSERT` and the `place_bracket_order` leaves a recoverable
row in `status='submitted'` with no `ib_order_id`.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import asyncpg

from app.clients.ib_quick_order import (
    ExecutionEvent,
    IBQuickOrderClient,
    OrderSide,
    PlaceOrderRequest,
    WhatIfResult,
)
from app.logging import get_logger
from app.services.ib_error_map import (
    IBTerminalError,
    IBTransientError,
    format_for_operator,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Form / preview DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuickOrderForm:
    """Parsed + validated form payload from the Quick-Order submit endpoint.

    Instances come from `parse_form(request_form)` in the router layer;
    the service layer only ever sees already-validated values.
    """

    asset_class: Literal["stock", "option"]
    symbol: str
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal
    stop_price: Decimal
    # Option-only
    option_expiry: date | None = None
    option_strike: Decimal | None = None
    option_right: Literal["C", "P"] | None = None
    option_multiplier: int | None = None
    # Trigger provenance (auto-tagged into trigger_spec on fill)
    strategy_id: int | None = None
    trigger_source: str | None = None
    horizon: str | None = None
    notes: str | None = None
    # Short-option confirmation (Story 12.2 AC #3)
    acknowledge_margin: bool = False


@dataclass(frozen=True)
class QuickOrderPreview:
    """Values rendered in the Bestätigungs-UI fragment."""

    form: QuickOrderForm
    risk_estimate: Decimal
    margin: WhatIfResult | None
    needs_acknowledge: bool
    contract_label: str


# ---------------------------------------------------------------------------
# Retry loop
# ---------------------------------------------------------------------------

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_INITIAL_DELAY_SECONDS = 1.0
_DEFAULT_MAX_DELAY_SECONDS = 60.0
# Code-review BH-6: `IBTransientError` subclasses `ConnectionError`, so
# listing both in the retry tuple is redundant (the parent catches the
# child). Keep `TimeoutError` because asyncio sockets raise bare
# `TimeoutError` on a blown read deadline.
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    IBTransientError,
    TimeoutError,
)


async def place_order_with_retry(
    client: IBQuickOrderClient,
    request: PlaceOrderRequest,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = _DEFAULT_INITIAL_DELAY_SECONDS,
    max_delay: float = _DEFAULT_MAX_DELAY_SECONDS,
    sleep: Any = asyncio.sleep,
):
    """Submit a bracket order with exponential-backoff retry (FR58).

    Transient errors retry with backoff. Terminal errors propagate
    on the first attempt — those need operator attention.
    """

    attempt = 0
    delay = initial_delay
    while True:
        attempt += 1
        try:
            return await client.place_bracket_order(request)
        except IBTerminalError:
            logger.exception(
                "ib_quick_order.place.terminal",
                order_ref=request.order_ref,
                attempt=attempt,
            )
            raise
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt >= max_attempts:
                logger.exception(
                    "ib_quick_order.place.retry_exhausted",
                    order_ref=request.order_ref,
                    attempts=attempt,
                    error=str(exc),
                )
                raise
            logger.warning(
                "ib_quick_order.place.retrying",
                order_ref=request.order_ref,
                attempt=attempt,
                next_delay_seconds=delay,
                error=str(exc),
            )
            await sleep(delay)
            delay = min(delay * 2, max_delay)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def _contract_label(form: QuickOrderForm) -> str:
    if form.asset_class == "stock":
        return f"{form.symbol} · Stock"
    expiry_str = form.option_expiry.isoformat() if form.option_expiry else "?"
    return f"{form.symbol} {expiry_str} {form.option_strike} {form.option_right}"


def _compute_risk(form: QuickOrderForm) -> Decimal:
    """Compute dollar-risk-at-stop for the preview display.

    For stocks: `quantity * (limit - stop)` (absolute value).
    For options: `contracts * multiplier * (limit - stop)`.
    """

    delta = abs(form.limit_price - form.stop_price)
    if form.asset_class == "option":
        multiplier = Decimal(form.option_multiplier or 100)
        return form.quantity * multiplier * delta
    return form.quantity * delta


async def compute_preview(
    client: IBQuickOrderClient,
    form: QuickOrderForm,
) -> QuickOrderPreview:
    """Assemble the preview view-model. No DB writes."""

    margin: WhatIfResult | None = None
    # Only options + short-side request the what-if margin — the
    # Short-Option warning is the primary driver.
    if form.asset_class == "option":
        order_ref_placeholder = f"preview-{uuid.uuid4().hex[:8]}"
        request = _form_to_request(form, order_ref_placeholder)
        try:
            margin = await client.what_if_order(request)
        except (IBTerminalError, IBTransientError, Exception) as exc:  # noqa: BLE001
            logger.warning(
                "ib_quick_order.preview.what_if_failed",
                symbol=form.symbol,
                error=str(exc),
            )

    needs_acknowledge = form.asset_class == "option" and form.side == "SELL"
    return QuickOrderPreview(
        form=form,
        risk_estimate=_compute_risk(form),
        margin=margin,
        needs_acknowledge=needs_acknowledge,
        contract_label=_contract_label(form),
    )


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def _form_to_request(form: QuickOrderForm, order_ref: str) -> PlaceOrderRequest:
    """Map the form payload onto a `PlaceOrderRequest` DTO."""

    return PlaceOrderRequest(
        order_ref=order_ref,
        asset_class=form.asset_class,
        symbol=form.symbol,
        side=form.side,
        quantity=form.quantity,
        limit_price=form.limit_price,
        stop_price=form.stop_price,
        option_expiry=form.option_expiry,
        option_strike=form.option_strike,
        option_right=form.option_right,
        option_multiplier=form.option_multiplier or (100 if form.asset_class == "option" else None),
    )


def _build_order_ref() -> str:
    """Stable idempotency key. 12 hex chars ≈ 2^48 collision space."""

    return f"qo-{uuid.uuid4().hex[:12]}"


_INSERT_QUICK_ORDER_SQL = """
INSERT INTO quick_orders (
    order_ref,
    asset_class,
    symbol,
    side,
    quantity,
    limit_price,
    stop_price,
    option_expiry,
    option_strike,
    option_right,
    option_multiplier,
    strategy_id,
    trigger_source,
    horizon,
    notes,
    margin_estimate,
    status
) VALUES ($1, $2, $3, $4::trade_side, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, 'submitted')
RETURNING id
"""

_UPDATE_QUICK_ORDER_IB_ID_SQL = """
UPDATE quick_orders
   SET ib_order_id = $1
 WHERE id = $2
"""

_UPDATE_QUICK_ORDER_STATUS_SQL = """
UPDATE quick_orders
   SET status = $1::order_status,
       ib_order_id = COALESCE(ib_order_id, $2)
 WHERE id = $3
"""

_SELECT_QUICK_ORDER_BY_REF_SQL = """
SELECT id, order_ref, asset_class, symbol, side::text AS side, quantity,
       limit_price, stop_price, option_expiry, option_strike, option_right,
       option_multiplier, ib_order_id, status::text AS status,
       strategy_id, trigger_source, horizon, notes, margin_estimate
  FROM quick_orders
 WHERE order_ref = $1
"""


@dataclass(frozen=True)
class SubmitResult:
    quick_order_id: int
    order_ref: str
    ib_order_id: str


class QuickOrderSubmitError(RuntimeError):
    """Raised when the submit pipeline fails terminally — router 4xx."""


async def submit_quick_order(
    conn: asyncpg.Connection,
    client: IBQuickOrderClient,
    form: QuickOrderForm,
) -> SubmitResult:
    """End-to-end submit path: persist → place → update.

    - Fails with `QuickOrderSubmitError` if the client is not
      connected (Story 12.4 AC #7).
    - Fails with `QuickOrderSubmitError` if the form is a short
      option and `acknowledge_margin` is False (Story 12.2 AC #3).
    - On terminal IB error, the quick_orders row is marked
      `rejected` and the exception propagates.
    - On a successful place, `ib_order_id` is stored and the status
      stays `submitted` until `handle_fill_event` flips it.
    """

    if not client.is_connected():
        raise QuickOrderSubmitError(
            "IB TWS/Gateway nicht verbunden — Start TWS oder Gateway auf Port 7497/4002"
        )

    if form.asset_class == "option" and form.side == "SELL" and not form.acknowledge_margin:
        raise QuickOrderSubmitError("Short-Option benötigt Margin-Acknowledge-Checkbox")

    order_ref = _build_order_ref()
    margin: WhatIfResult | None = None
    try:
        margin = await client.what_if_order(_form_to_request(form, order_ref))
    except Exception as exc:  # noqa: BLE001 — what-if is best-effort
        logger.warning(
            "ib_quick_order.submit.what_if_failed",
            order_ref=order_ref,
            error=str(exc),
        )

    # Persist BEFORE the network call. The UNIQUE constraint on
    # order_ref is the idempotency backbone.
    async with conn.transaction():
        row_id = await conn.fetchval(
            _INSERT_QUICK_ORDER_SQL,
            order_ref,
            form.asset_class,
            form.symbol,
            form.side.lower(),  # trade_side enum uses lowercase
            form.quantity,
            form.limit_price,
            form.stop_price,
            form.option_expiry,
            form.option_strike,
            form.option_right,
            form.option_multiplier,
            form.strategy_id,
            form.trigger_source,
            form.horizon,
            form.notes,
            margin.initial_margin_change if margin else None,
        )

    request = _form_to_request(form, order_ref)
    try:
        result = await place_order_with_retry(client, request)
    except IBTerminalError as exc:
        # Mark the row rejected and propagate. Code-review EC-17:
        # route the raw code through `format_for_operator` so the
        # user-facing 422 detail is German + carries the IB code.
        async with conn.transaction():
            await conn.execute(
                _UPDATE_QUICK_ORDER_STATUS_SQL,
                "rejected",
                None,
                row_id,
            )
        operator_msg = (
            format_for_operator(exc.error_code)
            if exc.error_code is not None
            else exc.german_message or str(exc)
        )
        raise QuickOrderSubmitError(operator_msg) from None
    except IBTransientError as exc:
        logger.error(
            "ib_quick_order.submit.retry_exhausted",
            order_ref=order_ref,
            error=str(exc),
        )
        raise QuickOrderSubmitError(f"Transiente IB-Fehler nach Retry: {exc}") from None

    # Stamp the ib_order_id so `handle_fill_event` can find the row.
    await conn.execute(_UPDATE_QUICK_ORDER_IB_ID_SQL, result.ib_order_id, row_id)

    logger.info(
        "ib_quick_order.submit.ok",
        order_ref=order_ref,
        ib_order_id=result.ib_order_id,
        quick_order_id=row_id,
        asset_class=form.asset_class,
        symbol=form.symbol,
    )
    return SubmitResult(
        quick_order_id=row_id,
        order_ref=order_ref,
        ib_order_id=result.ib_order_id,
    )


# ---------------------------------------------------------------------------
# Fill event handler (Story 12.3)
# ---------------------------------------------------------------------------


_INSERT_TRADE_ON_FILL_SQL = """
INSERT INTO trades (
    symbol,
    asset_class,
    side,
    quantity,
    entry_price,
    opened_at,
    broker,
    perm_id,
    trigger_spec,
    strategy_id,
    option_expiry,
    option_strike,
    option_right,
    option_multiplier
) VALUES (
    $1, $2, $3::trade_side, $4, $5, $6, 'ib'::trade_source,
    $7, $8::jsonb, $9, $10, $11, $12, $13
)
ON CONFLICT (broker, perm_id) DO NOTHING
RETURNING id
"""


async def handle_fill_event(
    conn: asyncpg.Connection,
    event: ExecutionEvent,
) -> dict[str, Any]:
    """Consume a Quick-Order fill event, update `quick_orders`, and
    on `filled` insert a row into `trades` with auto-tagged
    trigger_spec (Story 12.3 AC #2).

    Returns a dict describing what changed, useful for tests.

    Code-review EC-16: the status update + trade INSERT are wrapped
    in a single transaction so a crash between the two cannot leave
    `quick_orders.status='filled'` with no matching `trades` row
    (invariant: every `filled` quick_order has a trade).
    """

    row = await conn.fetchrow(_SELECT_QUICK_ORDER_BY_REF_SQL, event.order_ref)
    if row is None:
        logger.warning(
            "ib_quick_order.fill_event.unknown_order_ref",
            order_ref=event.order_ref,
        )
        return {"quick_order_id": None, "trade_id": None, "status": None}

    trade_id: int | None = None
    async with conn.transaction():
        # Update status (+ ib_order_id on the first event that has one).
        await conn.execute(
            _UPDATE_QUICK_ORDER_STATUS_SQL,
            event.status,
            event.ib_order_id,
            row["id"],
        )

        if event.status == "filled":
            # Auto-tag the new trade. Story 12.3 AC #2 requires
            # strategy, trigger_source, horizon='swing_short', and
            # asset_class flow from the QuickOrder into
            # `trades.trigger_spec`.
            #
            # Code-review EC-8: canonical horizon value is
            # `swing_short` (matches HORIZON_LABELS and the taxonomy
            # facet). The old `swing` literal was not a valid facet
            # value and `HORIZON_LABELS` had no `swing` key.
            trigger_spec = {
                "source": "quick_order",
                "asset_class": row["asset_class"],
                "horizon": row["horizon"] or "swing_short",
                "trigger_type": row["trigger_source"] or "quick_order",
                "strategy_id": row["strategy_id"],
            }

            trade_id = await conn.fetchval(
                _INSERT_TRADE_ON_FILL_SQL,
                row["symbol"],
                row["asset_class"],
                row["side"],
                event.filled_quantity,
                event.filled_price,
                event.execution_time,
                event.ib_order_id,
                trigger_spec,
                row["strategy_id"],
                row["option_expiry"],
                row["option_strike"],
                row["option_right"],
                row["option_multiplier"] or (100 if row["asset_class"] == "option" else None),
            )

    if event.status == "filled":
        if trade_id is None:
            logger.info(
                "ib_quick_order.trade_dedup",
                order_ref=event.order_ref,
                ib_order_id=event.ib_order_id,
                hint="trade row already existed — replay ignored",
            )
        else:
            logger.info(
                "ib_quick_order.trade_created",
                order_ref=event.order_ref,
                trade_id=trade_id,
                ib_order_id=event.ib_order_id,
                filled_quantity=str(event.filled_quantity),
                filled_price=str(event.filled_price),
            )

    return {
        "quick_order_id": row["id"],
        "trade_id": trade_id,
        "status": event.status,
    }


# ---------------------------------------------------------------------------
# Startup sweep (Tranche A — BH-1 / EC-15)
# ---------------------------------------------------------------------------


_SWEEP_ORPHAN_QUICK_ORDERS_SQL = """
UPDATE quick_orders
   SET status = 'rejected'::order_status
 WHERE status = 'submitted'::order_status
   AND ib_order_id IS NULL
   AND created_at < NOW() - INTERVAL '5 minutes'
RETURNING id
"""


async def sweep_orphan_quick_orders(conn: asyncpg.Connection) -> int:
    """Mark any crashed-mid-submit `quick_orders` rows as rejected.

    Code-review BH-1 / EC-15: `submit_quick_order` persists BEFORE
    the network call (correct for idempotency — NFR-R3a), which
    means a crash between the INSERT and `place_bracket_order`
    leaves a row in `status='submitted'` with `ib_order_id=NULL`
    forever. On the next startup, sweep any such row older than
    5 minutes to `rejected` so the operator sees the failure in
    the Quick-Order history instead of a ghost "in-flight" row.

    5 minutes is safely longer than the retry-loop worst case
    (3 attempts × 60s max backoff = 3m), so an in-flight legitimate
    submit is never clobbered.

    Returns the number of rows swept.
    """

    rows = await conn.fetch(_SWEEP_ORPHAN_QUICK_ORDERS_SQL)
    if rows:
        logger.info(
            "ib_quick_order.sweep_orphans",
            count=len(rows),
            ids=[r["id"] for r in rows],
        )
    return len(rows)

"""Bot execution service (Epic 8, Stories 8.1 + 8.2).

Owns:
- `execute_proposal(conn, proposal, client)` — generate client_order_id,
  persist it, submit to cTrader via the client protocol, with exponential
  backoff retry on transient errors (NFR-I3).
- `handle_execution_event(conn, event)` — consume cTrader execution
  events, update `proposals.execution_status`, and on FILLED insert a
  new row into `trades` with `trigger_spec` copied from the proposal
  (FR17).
- `trigger_bot_execution(db_pool, ctrader, proposal)` — fire-and-forget
  wrapper used by the approval router so a slow cTrader call never
  blocks the 200 OK response to Chef.

All functions are designed to be idempotent end-to-end:
- `client_order_id` is persisted BEFORE the network call, so a retry
  after process crash / network split sees the same id.
- `order_exists()` probe is run before re-submission on retry.
- The trade INSERT uses `(broker='ctrader', perm_id=ctrader_order_id)`
  which is already the dedup key on `trades` (Migration 002 UNIQUE),
  so a double-fill event cannot create two rows.

Code-review note: the retry loop here is deliberately home-grown
instead of pulling in `tenacity`. We only need exponential backoff +
max-attempt + a typed exception filter, and every hop should log
structlog so the operator can see what happened. A dependency for
three lines of math is net negative.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import asyncpg

from app.clients.ctrader import (
    CTraderClient,
    CTraderRateLimitError,
    CTraderTerminalError,
    CTraderTransientError,
    ExecutionEvent,
    PlaceOrderRequest,
)
from app.logging import get_logger
from app.models.proposal import Proposal, ProposalStatus

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# cTrader status → our `order_status` enum (Migration 001)
# ---------------------------------------------------------------------------

CTRADER_STATUS_MAPPING: dict[str, str] = {
    "ORDER_STATUS_ACCEPTED": "submitted",
    "ORDER_STATUS_FILLED": "filled",
    "ORDER_STATUS_PARTIALLY_FILLED": "partial",
    "ORDER_STATUS_REJECTED": "rejected",
    "ORDER_STATUS_CANCELLED": "cancelled",
    # The stub client already emits our internal labels directly
    # (lowercased) — these pass-throughs keep the mapping exhaustive.
    "submitted": "submitted",
    "filled": "filled",
    "partial": "partial",
    "rejected": "rejected",
    "cancelled": "cancelled",
}


def map_ctrader_status(raw: str) -> str:
    """Return the canonical `order_status` label for a cTrader status.

    Unknown values fall back to `submitted` rather than raising —
    cTrader may add new status values, and the bot-execution service
    should degrade instead of crashing. Structlog logs the unknown
    value so the operator can add it to the mapping.
    """

    mapped = CTRADER_STATUS_MAPPING.get(raw)
    if mapped is None:
        logger.warning("bot_execution.unknown_ctrader_status", raw=raw)
        return "submitted"
    return mapped


# ---------------------------------------------------------------------------
# Retry loop for `place_order`
# ---------------------------------------------------------------------------

_DEFAULT_MAX_ATTEMPTS = 5
_DEFAULT_INITIAL_DELAY_SECONDS = 1.0
_DEFAULT_MAX_DELAY_SECONDS = 60.0
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    CTraderTransientError,
    CTraderRateLimitError,
    ConnectionError,
    asyncio.TimeoutError,
)


async def place_order_with_retry(
    client: CTraderClient,
    request: PlaceOrderRequest,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = _DEFAULT_INITIAL_DELAY_SECONDS,
    max_delay: float = _DEFAULT_MAX_DELAY_SECONDS,
    sleep: Any = asyncio.sleep,
):
    """Submit an order with exponential-backoff retry (NFR-I3).

    Retries on transient errors and rate limits. Terminal errors
    (CTraderTerminalError) propagate on the first attempt — those need
    operator attention, not waiting.
    """

    attempt = 0
    delay = initial_delay
    while True:
        attempt += 1
        try:
            return await client.place_order(request)
        except CTraderTerminalError:
            # Never retry — propagate to the caller for operator visibility.
            logger.exception(
                "bot_execution.place_order.terminal",
                client_order_id=request.client_order_id,
                attempt=attempt,
            )
            raise
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt >= max_attempts:
                logger.exception(
                    "bot_execution.place_order.retry_exhausted",
                    client_order_id=request.client_order_id,
                    attempts=attempt,
                    error=str(exc),
                )
                raise
            logger.warning(
                "bot_execution.place_order.retrying",
                client_order_id=request.client_order_id,
                attempt=attempt,
                next_delay_seconds=delay,
                error=str(exc),
            )
            await sleep(delay)
            delay = min(delay * 2, max_delay)


# ---------------------------------------------------------------------------
# execute_proposal
# ---------------------------------------------------------------------------


def _build_client_order_id(proposal_id: int) -> str:
    """Stable, unique idempotency key."""

    return f"proposal-{proposal_id}-{uuid.uuid4().hex[:8]}"


def _proposal_to_request(proposal: Proposal, client_order_id: str) -> PlaceOrderRequest:
    """Map a Proposal onto a cTrader `PlaceOrderRequest`.

    The proposal's Decimal fields flow through unchanged; the request
    DTO keeps them as Decimal so the real OpenApiPy adapter can do the
    lot-unit conversion in one place (NOT here).
    """

    side: Any = "BUY" if proposal.side.value == "buy" else "SELL"
    return PlaceOrderRequest(
        client_order_id=client_order_id,
        symbol=proposal.symbol,
        side=side,
        volume=proposal.position_size,
        order_type="LIMIT",
        limit_price=proposal.entry_price,
        stop_price=proposal.stop_price,
        take_profit_price=proposal.target_price,
    )


_SELECT_CLIENT_ORDER_ID_SQL = """
SELECT client_order_id FROM proposals WHERE id = $1
"""

_UPDATE_CLIENT_ORDER_ID_SQL = """
UPDATE proposals
   SET client_order_id = $1
 WHERE id = $2
   AND client_order_id IS NULL
RETURNING id
"""

_UPDATE_EXECUTION_STATUS_SQL = """
UPDATE proposals
   SET execution_status     = $1::order_status,
       execution_updated_at = NOW(),
       execution_details    = COALESCE(execution_details, '{}'::jsonb) || $2::jsonb
 WHERE id = $3
"""


async def execute_proposal(
    conn: asyncpg.Connection,
    proposal: Proposal,
    client: CTraderClient,
) -> str | None:
    """Submit an approved proposal to cTrader and return the cTrader
    order id (or None if the proposal was not in a state where execution
    is permitted).

    Idempotency contract
    --------------------
    1. If `proposals.client_order_id` is already set, we re-use it. The
       network call is a probe (`order_exists`) — if cTrader already
       has the order we skip placing it again, otherwise we resend with
       the same id (cTrader de-dupes on the client-order-id).
    2. If the column is NULL, we generate a fresh id and persist it
       BEFORE the network call. A process crash between INSERT and
       `place_order` is safe: on restart we see the id and run the
       order-exists probe.
    """

    if proposal.status != ProposalStatus.APPROVED:
        logger.warning(
            "bot_execution.skip_non_approved",
            proposal_id=proposal.id,
            status=proposal.status.value,
        )
        return None

    existing = await conn.fetchval(_SELECT_CLIENT_ORDER_ID_SQL, proposal.id)
    client_order_id: str
    if existing:
        client_order_id = existing
        logger.info(
            "bot_execution.reuse_client_order_id",
            proposal_id=proposal.id,
            client_order_id=client_order_id,
        )
        if await client.order_exists(client_order_id):
            logger.info(
                "bot_execution.already_executed",
                proposal_id=proposal.id,
                client_order_id=client_order_id,
            )
            return None
    else:
        client_order_id = _build_client_order_id(proposal.id)
        updated = await conn.fetchval(_UPDATE_CLIENT_ORDER_ID_SQL, client_order_id, proposal.id)
        if updated is None:
            # Another coroutine wrote the id concurrently between our
            # SELECT and UPDATE — refetch and reuse it.
            client_order_id = await conn.fetchval(_SELECT_CLIENT_ORDER_ID_SQL, proposal.id)
            logger.info(
                "bot_execution.client_order_id_race",
                proposal_id=proposal.id,
                winner=client_order_id,
            )
            if await client.order_exists(client_order_id):
                return None

    request = _proposal_to_request(proposal, client_order_id)
    result = await place_order_with_retry(client, request)

    await conn.execute(
        _UPDATE_EXECUTION_STATUS_SQL,
        map_ctrader_status(result.status),
        # Pass the dict directly — app/db/pool.py registers a JSONB
        # codec that calls json.dumps under the hood, so passing a
        # pre-encoded string would double-encode it as a JSON scalar.
        {"place_order_result": result.ctrader_order_id},
        proposal.id,
    )
    logger.info(
        "bot_execution.place_order.ok",
        proposal_id=proposal.id,
        client_order_id=client_order_id,
        ctrader_order_id=result.ctrader_order_id,
    )
    return result.ctrader_order_id


# ---------------------------------------------------------------------------
# handle_execution_event — Story 8.2
# ---------------------------------------------------------------------------


_SELECT_PROPOSAL_BY_CLIENT_ORDER_ID_SQL = """
SELECT id, agent_id, strategy_id, symbol, asset_class, side, horizon,
       entry_price, stop_price, target_price, position_size, risk_budget,
       trigger_spec, notes, risk_gate_result, risk_gate_response,
       status, created_at, decided_at, decided_by,
       client_order_id, execution_status
  FROM proposals
 WHERE client_order_id = $1
"""


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
    agent_id
) VALUES (
    $1, $2, $3::trade_side, $4, $5, $6, 'ctrader'::trade_source,
    $7, $8::jsonb, $9, $10
)
ON CONFLICT (broker, perm_id) DO NOTHING
RETURNING id
"""


async def handle_execution_event(
    conn: asyncpg.Connection,
    event: ExecutionEvent,
) -> dict[str, Any]:
    """Consume a cTrader execution event and persist state changes.

    Returns a dict describing what happened — useful for tests and
    structlog. Keys:
    - `proposal_id`: id of the matched proposal (or None if no match)
    - `execution_status`: canonical label written to proposals.execution_status
    - `trade_id`: id of the newly inserted trade row, or None if not a FILLED event
    """

    row = await conn.fetchrow(_SELECT_PROPOSAL_BY_CLIENT_ORDER_ID_SQL, event.client_order_id)
    if row is None:
        logger.warning(
            "bot_execution.execution_event.unknown_client_order_id",
            client_order_id=event.client_order_id,
            ctrader_order_id=event.ctrader_order_id,
        )
        return {"proposal_id": None, "execution_status": None, "trade_id": None}

    proposal_id = row["id"]
    status_label = map_ctrader_status(event.status)

    await conn.execute(
        _UPDATE_EXECUTION_STATUS_SQL,
        status_label,
        {
            "event_status": event.status,
            "ctrader_order_id": event.ctrader_order_id,
            "filled_volume": str(event.filled_volume),
            "filled_price": str(event.filled_price),
            "execution_time": event.execution_time.isoformat(),
        },
        proposal_id,
    )

    trade_id: int | None = None
    if status_label == "filled":
        # Copy trigger_spec from the proposal onto the new trade row
        # (FR17). The trade's `opened_at` is cTrader's reported fill
        # time; `broker=ctrader` + `perm_id=ctrader_order_id` is the
        # dedup key so a double-FILL event cannot duplicate.
        trigger_spec = row["trigger_spec"] or {}
        if isinstance(trigger_spec, str):
            trigger_spec = json.loads(trigger_spec)

        trade_id = await conn.fetchval(
            _INSERT_TRADE_ON_FILL_SQL,
            row["symbol"],
            row["asset_class"],
            row["side"],
            event.filled_volume,
            event.filled_price,
            event.execution_time,
            event.ctrader_order_id,
            trigger_spec,
            row["strategy_id"],
            row["agent_id"],
        )
        logger.info(
            "bot_execution.trade_created",
            proposal_id=proposal_id,
            trade_id=trade_id,
            ctrader_order_id=event.ctrader_order_id,
            filled_volume=str(event.filled_volume),
            filled_price=str(event.filled_price),
        )

    return {
        "proposal_id": proposal_id,
        "execution_status": status_label,
        "trade_id": trade_id,
    }


# ---------------------------------------------------------------------------
# trigger_bot_execution — fire-and-forget hook for the approve endpoint
# ---------------------------------------------------------------------------


async def trigger_bot_execution(
    db_pool: Any,
    client: CTraderClient | None,
    proposal_id: int,
) -> None:
    """Background task spawned from `post_approve` (app/routers/approvals.py).

    Fetches the proposal with a fresh connection (the router's
    transaction has already committed by now), calls `execute_proposal`,
    and logs any exception. Intentionally does NOT raise — a bot-
    execution failure must never turn into a 500 on the approve POST,
    which has already succeeded from Chef's perspective.
    """

    if client is None:
        logger.warning(
            "bot_execution.trigger.no_client",
            proposal_id=proposal_id,
        )
        return
    if db_pool is None or not hasattr(db_pool, "acquire"):
        logger.warning(
            "bot_execution.trigger.no_db_pool",
            proposal_id=proposal_id,
        )
        return

    # Local import so there's no circular dep with proposal service.
    from app.services.proposal import get_proposal

    try:
        async with db_pool.acquire() as conn:
            proposal = await get_proposal(conn, proposal_id)
            if proposal is None:
                logger.warning(
                    "bot_execution.trigger.proposal_missing",
                    proposal_id=proposal_id,
                )
                return
            await execute_proposal(conn, proposal, client)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "bot_execution.trigger.failed",
            proposal_id=proposal_id,
            error=str(exc),
        )

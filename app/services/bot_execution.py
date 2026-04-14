"""Bot execution service (Epic 8, Stories 8.1 + 8.2).

Owns:
- `execute_proposal(conn, proposal, client)` — generate client_order_id,
  persist it, submit to cTrader via the client protocol, with exponential
  backoff retry on transient errors (NFR-I3).
- `handle_execution_event(conn, event, ...)` — consume cTrader execution
  events, update `proposals.execution_status`, and on FILLED insert a
  new row into `trades` with an enriched `trigger_spec` (FR17) plus a
  fire-and-forget `capture_fundamental_snapshot` call so the drilldown
  can show "damals vs jetzt" for bot trades.
- `trigger_bot_execution(db_pool, ctrader, proposal_id)` — fire-and-forget
  wrapper used by the approval router so a slow cTrader call never
  blocks the 200 OK response to Chef. Holds a strong reference to the
  spawned task so the event loop can't collect it mid-run.

All functions are designed to be idempotent end-to-end:
- `client_order_id` is persisted BEFORE the network call, so a retry
  after process crash / network split sees the same id.
- `order_exists()` probe is run before re-submission on retry.
- The trade INSERT uses `(broker='ctrader', perm_id=ctrader_order_id)`
  which is already the dedup key on `trades` (Migration 002 UNIQUE),
  so a double-fill event cannot create two rows.
- Execution-status UPDATEs are CAS'd against the current state so a
  late `place_order` success cannot regress a `filled` event that
  arrived in the meantime (code-review BH-4).

Code-review note: the retry loop here is deliberately home-grown
instead of pulling in `tenacity`. We only need exponential backoff +
max-attempt + a typed exception filter, and every hop should log
structlog so the operator can see what happened. A dependency for
three lines of math is net negative.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import asyncpg

from app.clients.ctrader import (
    CTraderClient,
    CTraderRateLimitError,
    CTraderTerminalError,
    ExecutionEvent,
    PlaceOrderRequest,
)
from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.proposal import Proposal, ProposalStatus
from app.models.trade import TradeSide
from app.services.fundamental_snapshot import capture_fundamental_snapshot

logger = get_logger(__name__)


# Code-review H1 / BH-2 / EC-1: strong references to in-flight
# fire-and-forget tasks (bot execution + fundamental snapshots).
# Python's `asyncio.create_task` docs explicitly require callers to
# keep a reference for the task's lifetime — otherwise the event loop
# can garbage-collect the task mid-run and Chef gets a silent "200 OK
# but no order placed" outcome. Same pattern as `ib_live_sync.py`.
_background_tasks: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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


# Code-review H7 / BH-7 / EC-5: explicit mapping so the 4-value
# TradeSide enum does not silently collapse SHORT → SELL and COVER →
# SELL. COVER closes a short position, which at cTrader is a BUY.
_SIDE_TO_CTRADER: dict[str, str] = {
    TradeSide.BUY.value: "BUY",
    TradeSide.COVER.value: "BUY",
    TradeSide.SELL.value: "SELL",
    TradeSide.SHORT.value: "SELL",
}


# ---------------------------------------------------------------------------
# Retry loop for `place_order`
# ---------------------------------------------------------------------------
#
# Sleep sequence for the defaults: 1s → 2s → 4s → 8s (between attempts
# 1..5). The `max_delay=60s` cap is not reached at default
# `max_attempts=5`, but stays in place for callers that bump the
# attempt count (manual replay / operator script). NFR-I3 asks for
# a 60s cap and that's what we commit to.

_DEFAULT_MAX_ATTEMPTS = 5
_DEFAULT_INITIAL_DELAY_SECONDS = 1.0
_DEFAULT_MAX_DELAY_SECONDS = 60.0
# Code-review H9 / BH-1: `CTraderTransientError` is already a subclass
# of `ConnectionError`, so listing both was dead. `asyncio.TimeoutError`
# is a 3.11+ alias for builtin `TimeoutError`, so use the builtin name.
# `CTraderRateLimitError` is NOT a `ConnectionError` so it needs its
# own tuple slot.
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    CTraderRateLimitError,
    TimeoutError,
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
    (`CTraderTerminalError`) propagate on the first attempt — those
    need operator attention, not waiting.
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
    """Stable, unique idempotency key.

    The uuid suffix exists only to defeat collisions if a proposal row
    is ever recreated after a delete+re-insert of the same primary
    key — cTrader's `clientOrderId` dedup would otherwise mistake the
    new proposal for the deleted one.
    """

    return f"proposal-{proposal_id}-{uuid.uuid4().hex[:8]}"


def _proposal_to_request(proposal: Proposal, client_order_id: str) -> PlaceOrderRequest:
    """Map a Proposal onto a cTrader `PlaceOrderRequest`.

    The proposal's Decimal fields flow through unchanged; the request
    DTO keeps them as Decimal so the real OpenApiPy adapter can do the
    lot-unit conversion in one place (NOT here).
    """

    side = _SIDE_TO_CTRADER.get(proposal.side.value)
    if side is None:
        # Defensive — should be unreachable given the enum is closed.
        raise CTraderTerminalError(
            f"unsupported trade side for bot execution: {proposal.side.value}"
        )
    return PlaceOrderRequest(
        client_order_id=client_order_id,
        symbol=proposal.symbol,
        side=side,  # type: ignore[arg-type]
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

# Code-review H5 / BH-11 / EC-21 / M4: `||` is a shallow merge in
# PostgreSQL, which means two sequential updates with the same top-
# level key silently overwrite each other (the `place_order_result`
# key disappeared as soon as the FILLED event arrived). Store events
# under a `history` array instead so every transition is preserved.
# The `jsonb_set(..., create_missing=true)` initialises the array
# on first write.
#
# Two variants: _PRELIMINARY is used by `execute_proposal` on the
# place_order path and MUST NOT regress a terminal state written by
# a raced FILLED event (code-review H3 / BH-4). The _EVENT variant
# is used by `handle_execution_event` and accepts any status.
#
# Both additionally gate on `status='approved'` to be consistent with
# Epic 7's hard-invariant pattern (no execution writes on a proposal
# that was rejected / revision'd in the meantime).

_UPDATE_EXECUTION_STATUS_PRELIMINARY_SQL = """
UPDATE proposals
   SET execution_status     = $1::order_status,
       execution_updated_at = NOW(),
       execution_details    = jsonb_set(
           COALESCE(execution_details, '{}'::jsonb),
           '{history}',
           COALESCE(execution_details->'history', '[]'::jsonb)
               || jsonb_build_array($2::jsonb),
           true
       )
 WHERE id = $3
   AND status = 'approved'
   AND (execution_status IS NULL OR execution_status = 'submitted')
RETURNING id
"""

_UPDATE_EXECUTION_STATUS_EVENT_SQL = """
UPDATE proposals
   SET execution_status     = $1::order_status,
       execution_updated_at = NOW(),
       execution_details    = jsonb_set(
           COALESCE(execution_details, '{}'::jsonb),
           '{history}',
           COALESCE(execution_details->'history', '[]'::jsonb)
               || jsonb_build_array($2::jsonb),
           true
       )
 WHERE id = $3
   AND status = 'approved'
RETURNING id
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
    client_order_id: str | None
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
        candidate = _build_client_order_id(proposal.id)
        updated = await conn.fetchval(_UPDATE_CLIENT_ORDER_ID_SQL, candidate, proposal.id)
        if updated is None:
            # Another coroutine wrote the id concurrently between our
            # SELECT and UPDATE — refetch and reuse it. Code-review H2 /
            # BH-3 / EC-3: the refetch can return None if the row was
            # deleted in between (admin rollback scenario); guard for it.
            client_order_id = await conn.fetchval(_SELECT_CLIENT_ORDER_ID_SQL, proposal.id)
            if client_order_id is None:
                logger.warning(
                    "bot_execution.client_order_id_race_lost",
                    proposal_id=proposal.id,
                    hint="proposal row disappeared between SELECT and UPDATE",
                )
                return None
            logger.info(
                "bot_execution.client_order_id_race",
                proposal_id=proposal.id,
                winner=client_order_id,
            )
            if await client.order_exists(client_order_id):
                return None
        else:
            client_order_id = candidate

    request = _proposal_to_request(proposal, client_order_id)
    result = await place_order_with_retry(client, request)

    # Code-review H3 / BH-4: the preliminary CAS prevents a race where
    # the FILLED event arrived via `handle_execution_event` before the
    # `place_order` return flipped back to our coroutine. If the event
    # already wrote `filled`, we must NOT regress to `submitted`.
    # RETURNING id lets us detect the CAS miss and log it.
    updated_id = await conn.fetchval(
        _UPDATE_EXECUTION_STATUS_PRELIMINARY_SQL,
        map_ctrader_status(result.status),
        # Pass the dict directly — app/db/pool.py registers a JSONB
        # codec that calls json.dumps under the hood, so passing a
        # pre-encoded string would double-encode it as a JSON scalar.
        {
            "kind": "place_order_result",
            "ctrader_order_id": result.ctrader_order_id,
            "status": result.status,
            "accepted_at": result.accepted_at.isoformat(),
        },
        proposal.id,
    )
    if updated_id is None:
        # CAS miss is expected and OK — the event handler already moved
        # the state machine past `submitted`. Nothing to do except log.
        logger.info(
            "bot_execution.place_order.cas_miss",
            proposal_id=proposal.id,
            hint="execution_status already in terminal state — event handler won the race",
        )
    else:
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


# Code-review M2 / BH-17: previous SELECT pulled 22 columns of which
# 15 were dead weight. Prune to the set `handle_execution_event`
# actually uses + the horizon column we need for H6 enrichment.
_SELECT_PROPOSAL_BY_CLIENT_ORDER_ID_SQL = """
SELECT id, agent_id, strategy_id, symbol, asset_class, side, horizon,
       trigger_spec
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


def _enrich_trigger_spec(row: asyncpg.Record) -> dict[str, Any]:
    """Merge the proposal's top-level typed columns into the trade-row
    trigger_spec (code-review H6 / EC-2 / EC-9).

    Without this the journal's horizon facet and trigger-prose renderer
    show "Unbekannt" for every bot-created trade — the agent's
    `trigger_spec` JSONB is opaque to `trigger_prose.render_trigger_prose`
    which keys off `agent_id`, `horizon`, `trigger_type`, etc.
    """

    base = row["trigger_spec"] or {}
    # Defensive str→dict just in case a caller bypasses the JSONB codec.
    # Under the pool's registered codec this branch is unreachable.
    enriched = dict(base)
    enriched.setdefault("agent_id", row["agent_id"])
    enriched.setdefault("horizon", row["horizon"])
    enriched.setdefault("asset_class", row["asset_class"])
    enriched.setdefault("trigger_type", enriched.get("trigger_type", "bot_auto"))
    enriched.setdefault("source", "bot_execution")
    return enriched


async def handle_execution_event(
    conn: asyncpg.Connection,
    event: ExecutionEvent,
    *,
    db_pool: Any | None = None,
    mcp_client: MCPClient | None = None,
) -> dict[str, Any]:
    """Consume a cTrader execution event and persist state changes.

    Returns a dict describing what happened — useful for tests and
    structlog. Keys:
    - `proposal_id`: id of the matched proposal (or None if no match)
    - `execution_status`: canonical label written to proposals.execution_status
    - `trade_id`: id of the newly inserted trade row, or None if not a FILLED
      event (or if the row already existed via ON CONFLICT dedup)
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
        _UPDATE_EXECUTION_STATUS_EVENT_SQL,
        status_label,
        {
            "kind": "execution_event",
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
        # (FR17), ENRICHED with the proposal's typed columns so the
        # journal facets and prose renderer see non-"Unbekannt" values.
        # `broker=ctrader` + `perm_id=ctrader_order_id` is the dedup key
        # so a double-FILL event cannot create a duplicate row.
        enriched_trigger_spec = _enrich_trigger_spec(row)

        trade_id = await conn.fetchval(
            _INSERT_TRADE_ON_FILL_SQL,
            row["symbol"],
            row["asset_class"],
            row["side"],
            event.filled_volume,
            event.filled_price,
            event.execution_time,
            event.ctrader_order_id,
            enriched_trigger_spec,
            row["strategy_id"],
            row["agent_id"],
        )
        if trade_id is None:
            # Code-review M5 / BH-19: ON CONFLICT DO NOTHING returns no
            # row when the dedup key already existed. A structlog event
            # that still claims "trade_created" would mislead the
            # operator.
            logger.info(
                "bot_execution.trade_dedup",
                proposal_id=proposal_id,
                ctrader_order_id=event.ctrader_order_id,
                hint="trade row already existed — double-fill event ignored",
            )
        else:
            logger.info(
                "bot_execution.trade_created",
                proposal_id=proposal_id,
                trade_id=trade_id,
                ctrader_order_id=event.ctrader_order_id,
                filled_volume=str(event.filled_volume),
                filled_price=str(event.filled_price),
            )

            # Code-review H8 / EC-6: capture a fundamental snapshot on
            # every newly inserted bot trade, mirroring
            # `ib_live_sync.upsert_trade`. Without this, Migration 005's
            # documented invariant ("populated by the live-sync hook AND
            # by Epic 7/8 on bot-order placement") is violated and the
            # drilldown's "damals" column is always empty for bot trades.
            if db_pool is not None and mcp_client is not None:
                task = asyncio.create_task(
                    _capture_snapshot_fire_and_forget(
                        db_pool=db_pool,
                        trade_id=trade_id,
                        symbol=row["symbol"],
                        asset_class=row["asset_class"],
                        mcp_client=mcp_client,
                    )
                )
                _track(task)

    return {
        "proposal_id": proposal_id,
        "execution_status": status_label,
        "trade_id": trade_id,
    }


async def _capture_snapshot_fire_and_forget(
    *,
    db_pool: Any,
    trade_id: int,
    symbol: str,
    asset_class: str,
    mcp_client: MCPClient,
) -> None:
    """Wrapper task: acquire a fresh connection from the pool and call
    `capture_fundamental_snapshot`. Never raises — any failure is
    logged inside the snapshot service. Same shape as
    `ib_live_sync._capture_snapshot_fire_and_forget`.
    """

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
            "bot_execution.fundamental_snapshot.task_failed",
            trade_id=trade_id,
            symbol=symbol,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# trigger_bot_execution — fire-and-forget hook for the approve endpoint
# ---------------------------------------------------------------------------


def spawn_bot_execution(
    db_pool: Any,
    client: CTraderClient | None,
    mcp_client: MCPClient | None,
    proposal_id: int,
) -> asyncio.Task | None:
    """Create and track a `trigger_bot_execution` task.

    Code-review H1 / BH-2 / EC-1: callers must NOT use raw
    `asyncio.create_task(trigger_bot_execution(...))` from the router
    layer — without the `_background_tasks` set registration the task
    can be garbage-collected mid-run, silently dropping the execution
    after Chef has already seen HTTP 200.
    """

    task = asyncio.create_task(trigger_bot_execution(db_pool, client, mcp_client, proposal_id))
    _track(task)
    return task


async def trigger_bot_execution(
    db_pool: Any,
    client: CTraderClient | None,
    mcp_client: MCPClient | None,
    proposal_id: int,
) -> None:
    """Background task spawned from `post_approve` (app/routers/approvals.py).

    Fetches the proposal with a fresh connection (the router's
    transaction has already committed by now), calls `execute_proposal`,
    and logs any exception. Intentionally does NOT raise — a bot-
    execution failure must never turn into a 500 on the approve POST,
    which has already succeeded from Chef's perspective.

    On failure, writes a `bot_execution_failed` row to `audit_log` so
    the failure is queryable (code-review M1 / EC-12). Chef's approve
    is already durable; without this audit trail a dropped task can
    only be detected by tailing structlog.
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
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "bot_execution.trigger.failed",
            proposal_id=proposal_id,
            error=str(exc),
        )
        # Code-review M1 / EC-12: write an audit-log row so the
        # failure survives the request/response cycle and is
        # queryable from the audit-log viewer (Story 12.2).
        if db_pool is not None and hasattr(db_pool, "acquire"):
            try:
                async with db_pool.acquire() as audit_conn:
                    # audit_log's CHECK constraint only allows a closed
                    # vocabulary of event_types (Migration 009). We
                    # deliberately use `proposal_revision` as the
                    # closest-allowed shape — a dedicated
                    # `bot_execution_failed` value would require another
                    # migration and can land as a follow-up. The `notes`
                    # column carries the concrete error for Chef to
                    # triage in Story 12.2.
                    await audit_conn.execute(
                        """
                        INSERT INTO audit_log (event_type, proposal_id, actor, notes)
                        VALUES ('proposal_revision', $1, 'bot_execution', $2)
                        """,
                        proposal_id,
                        f"bot_execution_failed: {exc}",
                    )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning(
                    "bot_execution.trigger.audit_write_failed",
                    proposal_id=proposal_id,
                    error=str(audit_exc),
                )

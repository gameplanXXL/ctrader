"""Proposal CRUD + lifecycle service (Epic 7).

Owns:
- create_proposal() — Bot-side entry point (calls is_strategy_active
  guard from Story 6.5)
- list_pending_proposals() — Approval dashboard query
- get_proposal() — drilldown lookup
- run_risk_gate_for_proposal() — async risk-gate evaluation + persist
- approve_proposal / reject_proposal / send_to_revision —
  decision-side endpoints, all of which write an audit-log entry
  via Story 7.5.

The FR28 hard invariant lives in `approve_proposal`: a RED or
UNREACHABLE risk-gate raises `ProposalBlockedError` so the router
returns 403. The frontend disables the button on the same condition,
but the backend gate-keeper is the source of truth.
"""

from __future__ import annotations

import json
from decimal import Decimal

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.models.proposal import (
    Proposal,
    ProposalCreate,
    ProposalDecision,
    ProposalStatus,
    RiskGateLevel,
)
from app.models.strategy import StrategyHorizon
from app.models.trade import TradeSide
from app.services.audit import log_proposal_decision
from app.services.fundamental import get_fundamental
from app.services.risk_gate import run_risk_gate
from app.services.strategy import is_strategy_active

logger = get_logger(__name__)


class ProposalNotFoundError(LookupError):
    """Raised when a proposal id does not resolve."""


class ProposalBlockedError(PermissionError):
    """Raised when an approve attempt hits a RED / UNREACHABLE risk gate.

    Backed by FR28: "Das System blockiert den Approval-Button
    technisch, wenn das Risk-Gate RED liefert. Es gibt keinen
    Workaround zur Umgehung der RED-Blockade."
    """


class ProposalStrategyInactiveError(PermissionError):
    """Raised when a proposal is created against a non-active strategy.

    Story 6.5 hard invariant: paused / retired strategies must not
    generate new proposals.
    """


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------


_INSERT_SQL = """
INSERT INTO proposals (
    agent_id, strategy_id, symbol, asset_class, side, horizon,
    entry_price, stop_price, target_price, position_size, risk_budget,
    trigger_spec, status, notes
)
VALUES (
    $1, $2, $3, $4, $5::trade_side, $6::horizon_type,
    $7, $8, $9, $10, $11,
    $12, 'pending', $13
)
RETURNING id, agent_id, strategy_id, symbol, asset_class, side::text,
          horizon::text, entry_price, stop_price, target_price, position_size,
          risk_budget, trigger_spec, risk_gate_result::text,
          risk_gate_response, status, created_at, decided_at, decided_by,
          notes
"""

_LIST_SQL = """
SELECT id, agent_id, strategy_id, symbol, asset_class, side::text,
       horizon::text, entry_price, stop_price, target_price, position_size,
       risk_budget, trigger_spec, risk_gate_result::text,
       risk_gate_response, status, created_at, decided_at, decided_by, notes
  FROM proposals
 WHERE status = 'pending'
 ORDER BY created_at DESC, id DESC
"""

_GET_SQL = """
SELECT id, agent_id, strategy_id, symbol, asset_class, side::text,
       horizon::text, entry_price, stop_price, target_price, position_size,
       risk_budget, trigger_spec, risk_gate_result::text,
       risk_gate_response, status, created_at, decided_at, decided_by, notes
  FROM proposals
 WHERE id = $1
"""

_UPDATE_RISK_GATE_SQL = """
UPDATE proposals
   SET risk_gate_result   = $1::risk_gate_result,
       risk_gate_response = $2
 WHERE id = $3
"""

_UPDATE_STATUS_SQL = """
UPDATE proposals
   SET status      = $1,
       decided_at  = NOW(),
       decided_by  = $2,
       notes       = COALESCE($3, notes)
 WHERE id = $4
   AND status = 'pending'
RETURNING id
"""


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------


def _row_to_proposal(row: asyncpg.Record) -> Proposal:
    trigger_spec = row["trigger_spec"] or {}
    if isinstance(trigger_spec, str):
        try:
            trigger_spec = json.loads(trigger_spec)
        except ValueError:
            trigger_spec = {}

    risk_gate_response = row["risk_gate_response"]
    if isinstance(risk_gate_response, str):
        try:
            risk_gate_response = json.loads(risk_gate_response)
        except ValueError:
            risk_gate_response = None

    risk_gate_raw = row["risk_gate_result"]
    risk_gate_level = RiskGateLevel(risk_gate_raw) if risk_gate_raw is not None else None

    return Proposal(
        id=int(row["id"]),
        agent_id=str(row["agent_id"]),
        strategy_id=row["strategy_id"],
        symbol=str(row["symbol"]),
        asset_class=str(row["asset_class"]),
        side=TradeSide(row["side"]),
        horizon=StrategyHorizon(row["horizon"]),
        entry_price=Decimal(str(row["entry_price"])),
        stop_price=(Decimal(str(row["stop_price"])) if row["stop_price"] is not None else None),
        target_price=(
            Decimal(str(row["target_price"])) if row["target_price"] is not None else None
        ),
        position_size=Decimal(str(row["position_size"])),
        risk_budget=Decimal(str(row["risk_budget"])),
        trigger_spec=trigger_spec,
        risk_gate_result=risk_gate_level,
        risk_gate_response=risk_gate_response,
        status=ProposalStatus(row["status"]),
        created_at=row["created_at"],
        decided_at=row["decided_at"],
        decided_by=row["decided_by"],
        notes=row["notes"],
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_proposal(conn: asyncpg.Connection, payload: ProposalCreate) -> Proposal:
    """Insert a new proposal. Story 6.5 gate: target strategy must be
    active. Bot-side callers should run the risk gate immediately
    after via `run_risk_gate_for_proposal`.
    """

    if payload.strategy_id is not None:
        active = await is_strategy_active(conn, payload.strategy_id)
        if not active:
            raise ProposalStrategyInactiveError(
                f"strategy {payload.strategy_id} is not active — proposal blocked"
            )

    row = await conn.fetchrow(
        _INSERT_SQL,
        payload.agent_id,
        payload.strategy_id,
        payload.symbol,
        payload.asset_class,
        payload.side.value,
        payload.horizon.value,
        payload.entry_price,
        payload.stop_price,
        payload.target_price,
        payload.position_size,
        payload.risk_budget,
        payload.trigger_spec,
        payload.notes,
    )
    proposal = _row_to_proposal(row)
    logger.info(
        "proposal.created",
        proposal_id=proposal.id,
        agent_id=proposal.agent_id,
        symbol=proposal.symbol,
        strategy_id=proposal.strategy_id,
    )
    return proposal


async def list_pending_proposals(conn: asyncpg.Connection) -> list[Proposal]:
    rows = await conn.fetch(_LIST_SQL)
    return [_row_to_proposal(row) for row in rows]


async def get_proposal(conn: asyncpg.Connection, proposal_id: int) -> Proposal | None:
    row = await conn.fetchrow(_GET_SQL, proposal_id)
    return _row_to_proposal(row) if row is not None else None


# ---------------------------------------------------------------------------
# Risk gate
# ---------------------------------------------------------------------------


async def run_risk_gate_for_proposal(
    conn: asyncpg.Connection,
    proposal: Proposal,
    mcp_client: MCPClient | None,
) -> Proposal:
    """Evaluate the risk gate and persist the result on the row.

    Story 7.2 / FR27: every new proposal MUST have a risk-gate verdict
    before Chef sees it in the dashboard. The 4-state level (incl.
    UNREACHABLE) is collapsed to the 3-stage PG enum by mapping
    UNREACHABLE → red — fail-closed for the DB.
    """

    result = await run_risk_gate(proposal, mcp_client)
    db_level = RiskGateLevel.RED if result.level == RiskGateLevel.UNREACHABLE else result.level
    payload = {
        "level": result.level.value,
        "flags": result.flags,
        "details": result.details,
        "evaluated_at": result.evaluated_at.isoformat(),
        "agent_id": result.agent_id,
    }
    await conn.execute(_UPDATE_RISK_GATE_SQL, db_level.value, payload, proposal.id)
    return await get_proposal(conn, proposal.id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Decision endpoints
# ---------------------------------------------------------------------------


async def approve_proposal(
    conn: asyncpg.Connection,
    proposal_id: int,
    decision: ProposalDecision,
    mcp_client: MCPClient | None = None,
) -> Proposal:
    """Approve a pending proposal.

    Story 7.4 + FR28 hard invariant: RED or UNREACHABLE risk gate
    blocks the approval at the service layer. Frontend disables the
    button, backend rejects the POST — defense in depth.
    """

    proposal = await get_proposal(conn, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(f"proposal {proposal_id} does not exist")
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalNotFoundError(
            f"proposal {proposal_id} is not pending (status={proposal.status.value})"
        )
    if proposal.is_red:
        raise ProposalBlockedError(
            f"proposal {proposal_id} blocked by risk gate ({proposal.risk_gate_result})"
        )

    risk_budget = decision.risk_budget if decision.risk_budget is not None else proposal.risk_budget

    fundamental_snapshot = None
    try:
        fundamental_result = await get_fundamental(
            proposal.symbol, proposal.asset_class, mcp_client
        )
        if fundamental_result is not None:
            fundamental_snapshot = fundamental_result.assessment.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        logger.warning("approve.fundamental_fetch_failed", error=str(exc))

    async with conn.transaction():
        updated = await conn.fetchval(
            _UPDATE_STATUS_SQL, "approved", "chef", decision.notes, proposal_id
        )
        if updated is None:
            raise ProposalNotFoundError(
                f"proposal {proposal_id} could not be updated (concurrent decision?)"
            )
        await log_proposal_decision(
            conn,
            event_type="proposal_approved",
            proposal=proposal,
            risk_budget=risk_budget,
            override_flags={"overrode_fundamental": decision.overrode_fundamental},
            fundamental_snapshot=fundamental_snapshot,
            notes=decision.notes,
        )

    logger.info(
        "proposal.approved",
        proposal_id=proposal_id,
        risk_budget=str(risk_budget),
        overrode_fundamental=decision.overrode_fundamental,
    )
    return await get_proposal(conn, proposal_id)  # type: ignore[return-value]


async def reject_proposal(
    conn: asyncpg.Connection,
    proposal_id: int,
    decision: ProposalDecision,
) -> Proposal:
    """Reject a pending proposal."""

    proposal = await get_proposal(conn, proposal_id)
    if proposal is None or proposal.status != ProposalStatus.PENDING:
        raise ProposalNotFoundError(f"proposal {proposal_id} not pending")

    async with conn.transaction():
        await conn.fetchval(_UPDATE_STATUS_SQL, "rejected", "chef", decision.notes, proposal_id)
        await log_proposal_decision(
            conn,
            event_type="proposal_rejected",
            proposal=proposal,
            risk_budget=None,
            override_flags=None,
            notes=decision.notes,
        )
    return await get_proposal(conn, proposal_id)  # type: ignore[return-value]


async def send_to_revision(
    conn: asyncpg.Connection,
    proposal_id: int,
    decision: ProposalDecision,
) -> Proposal:
    """Send a proposal back to the agent for revision."""

    proposal = await get_proposal(conn, proposal_id)
    if proposal is None or proposal.status != ProposalStatus.PENDING:
        raise ProposalNotFoundError(f"proposal {proposal_id} not pending")

    async with conn.transaction():
        await conn.fetchval(_UPDATE_STATUS_SQL, "revision", "chef", decision.notes, proposal_id)
        await log_proposal_decision(
            conn,
            event_type="proposal_revision",
            proposal=proposal,
            risk_budget=None,
            override_flags=None,
            notes=decision.notes,
        )
    return await get_proposal(conn, proposal_id)  # type: ignore[return-value]

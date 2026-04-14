"""Append-only audit-log service (Story 7.5 / FR32 / NFR-R8 / NFR-S3).

Every approve / reject / revision decision lands here as a snapshot
that can reconstruct the full decision context without joining
mutable state. The DB-side BEFORE trigger from Migration 008
enforces the append-only invariant — the service layer only adds
the convenience helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from app.logging import get_logger
from app.models.proposal import Proposal

logger = get_logger(__name__)


_INSERT_SQL = """
INSERT INTO audit_log (
    event_type, proposal_id, strategy_id, risk_budget,
    risk_gate_snapshot, fundamental_snapshot, override_flags,
    strategy_version, actor, notes
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
RETURNING id, created_at
"""


_LIST_SQL = """
SELECT id, event_type, proposal_id, strategy_id, risk_budget,
       risk_gate_snapshot, fundamental_snapshot, override_flags,
       strategy_version, actor, notes, created_at
  FROM audit_log
 ORDER BY created_at DESC, id DESC
 LIMIT $1
"""


@dataclass(frozen=True)
class AuditEntry:
    id: int
    event_type: str
    proposal_id: int | None
    strategy_id: int | None
    risk_budget: Decimal | None
    risk_gate_snapshot: dict[str, Any] | None
    fundamental_snapshot: dict[str, Any] | None
    override_flags: dict[str, Any] | None
    strategy_version: dict[str, Any] | None
    actor: str
    notes: str | None
    created_at: datetime


async def _strategy_snapshot(
    conn: asyncpg.Connection, strategy_id: int | None
) -> dict[str, Any] | None:
    """Capture the strategy row at decision time so the audit entry
    is reproducible even after the strategy is later edited."""

    if strategy_id is None:
        return None
    row = await conn.fetchrow(
        """
        SELECT id, name, asset_class, horizon::text, typical_holding_period,
               trigger_sources, risk_budget_per_trade::text, status::text,
               created_at, updated_at
          FROM strategies
         WHERE id = $1
        """,
        strategy_id,
    )
    if row is None:
        return None
    snapshot = dict(row)
    # Convert timestamps to ISO so the JSONB stays JSON-native.
    for key in ("created_at", "updated_at"):
        if isinstance(snapshot.get(key), datetime):
            snapshot[key] = snapshot[key].isoformat()
    return snapshot


async def log_proposal_decision(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    proposal: Proposal,
    risk_budget: Decimal | None,
    override_flags: dict[str, Any] | None,
    fundamental_snapshot: dict[str, Any] | None = None,
    notes: str | None = None,
    actor: str = "chef",
) -> AuditEntry:
    """Persist one audit row for a proposal decision."""

    strategy_version = await _strategy_snapshot(conn, proposal.strategy_id)

    row = await conn.fetchrow(
        _INSERT_SQL,
        event_type,
        proposal.id,
        proposal.strategy_id,
        risk_budget,
        proposal.risk_gate_response,
        fundamental_snapshot,
        override_flags or {},
        strategy_version,
        actor,
        notes,
    )
    logger.info(
        "audit.logged",
        event_type=event_type,
        proposal_id=proposal.id,
        strategy_id=proposal.strategy_id,
        actor=actor,
        audit_id=row["id"],
    )
    return AuditEntry(
        id=int(row["id"]),
        event_type=event_type,
        proposal_id=proposal.id,
        strategy_id=proposal.strategy_id,
        risk_budget=risk_budget,
        risk_gate_snapshot=proposal.risk_gate_response,
        fundamental_snapshot=fundamental_snapshot,
        override_flags=override_flags or {},
        strategy_version=strategy_version,
        actor=actor,
        notes=notes,
        created_at=row["created_at"],
    )


async def list_audit_entries(conn: asyncpg.Connection, *, limit: int = 200) -> list[AuditEntry]:
    rows = await conn.fetch(_LIST_SQL, limit)
    return [
        AuditEntry(
            id=int(r["id"]),
            event_type=str(r["event_type"]),
            proposal_id=r["proposal_id"],
            strategy_id=r["strategy_id"],
            risk_budget=(Decimal(str(r["risk_budget"])) if r["risk_budget"] is not None else None),
            risk_gate_snapshot=r["risk_gate_snapshot"],
            fundamental_snapshot=r["fundamental_snapshot"],
            override_flags=r["override_flags"],
            strategy_version=r["strategy_version"],
            actor=str(r["actor"]),
            notes=r["notes"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

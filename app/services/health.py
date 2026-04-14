"""Health-check aggregator (Epic 11 / Story 11.2).

One function, many queries — the Health-Widget renders a compact
"status at a glance" view of every integration + every scheduled job.
Returns a plain dict so the Jinja template doesn't need a Pydantic
model (the template renders whatever keys are present; missing keys
are rendered as em-dash).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger
from app.services.db_backup import get_backup_info
from app.services.mcp_contract_test import get_latest_contract_test
from app.services.scheduler import get_last_job_runs

logger = get_logger(__name__)


def _ib_status(ib_available: bool) -> dict[str, Any]:
    return {
        "status": "ok" if ib_available else "disabled",
        "label": "Interactive Brokers",
        "dot": "green" if ib_available else "grey",
        "detail": "connected" if ib_available else "not configured",
    }


def _ctrader_status(ctrader_client: Any | None) -> dict[str, Any]:
    """StubCTraderClient counts as 'stub' — Chef shouldn't confuse it
    with a live broker connection.

    Code-review M5 / EC-19: use `isinstance` instead of a string class
    name check so a future rename of `StubCTraderClient` doesn't
    silently flip the dot from yellow to green.
    """

    if ctrader_client is None:
        return {
            "status": "disabled",
            "label": "cTrader",
            "dot": "grey",
            "detail": "not configured",
        }
    from app.clients.ctrader import StubCTraderClient

    if isinstance(ctrader_client, StubCTraderClient):
        return {
            "status": "stub",
            "label": "cTrader",
            "dot": "yellow",
            "detail": "stub (real adapter pending 1-day spike)",
        }
    return {
        "status": "ok",
        "label": "cTrader",
        "dot": "green",
        "detail": "connected",
    }


def _mcp_status(mcp_available: bool) -> dict[str, Any]:
    return {
        "status": "ok" if mcp_available else "disabled",
        "label": "Fundamental MCP",
        "dot": "green" if mcp_available else "grey",
        "detail": "connected" if mcp_available else "not configured",
    }


async def collect_health(
    conn: asyncpg.Connection,
    *,
    ib_available: bool,
    mcp_client: MCPClient | None,
    mcp_available: bool,
    ctrader_client: Any | None,
) -> dict[str, Any]:
    """Assemble the full health payload.

    Cheap — four small queries + three in-process lookups. Safe to
    call from any page handler without worrying about tail latency.
    """

    try:
        last_job_runs = await get_last_job_runs(conn)
    except asyncpg.UndefinedTableError:
        logger.warning("health.job_executions_missing")
        last_job_runs = []

    try:
        contract_test = await get_latest_contract_test(conn)
    except Exception as exc:  # noqa: BLE001
        logger.warning("health.contract_test_failed", error=str(exc))
        contract_test = None

    backup_info = get_backup_info()

    return {
        "ib": _ib_status(ib_available),
        "ctrader": _ctrader_status(ctrader_client),
        "mcp": _mcp_status(mcp_available),
        "contract_test": contract_test,
        "last_job_runs": last_job_runs,
        "backup": {
            "path": str(backup_info.path) if backup_info else None,
            "size_bytes": backup_info.size_bytes if backup_info else None,
            "modified_at": backup_info.modified_at if backup_info else None,
        }
        if backup_info is not None
        else None,
    }

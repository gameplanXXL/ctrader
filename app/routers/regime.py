"""Regime API routes (Epic 9).

- `POST /api/regime/snapshot` — manual trigger for the daily regime
  snapshot + kill-switch evaluation. Returns the persisted snapshot
  as JSON. Story 11.1's APScheduler integration will call
  `create_regime_snapshot` directly on its cron schedule; this route
  is the UI-facing manual path for the Regime page's refresh button
  and for ad-hoc operator diagnostics.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.logging import get_logger
from app.services.kill_switch import evaluate_kill_switch
from app.services.regime_snapshot import create_regime_snapshot

logger = get_logger(__name__)

router = APIRouter(tags=["regime"])


def _to_json(value: Any) -> Any:
    """Stringify Decimal values so JSONResponse doesn't choke."""

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    return value


@router.post("/api/regime/snapshot", include_in_schema=False)
async def post_regime_snapshot(request: Request) -> JSONResponse:
    """Create a new regime snapshot and evaluate the kill switch.

    This is the same code path the Story-11.1 scheduled job will run,
    wrapped in an HTTP endpoint so the Regime page (and any operator
    shell calling via `curl`) can trigger it manually.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    http_client = httpx.AsyncClient()
    try:
        snapshot = await create_regime_snapshot(db_pool, http_client=http_client)
    finally:
        await http_client.aclose()

    # Evaluate kill switch with the fresh index. Uses a new connection
    # so we don't hold the write-lock while iterating over strategies.
    async with db_pool.acquire() as conn:
        ks_result = await evaluate_kill_switch(conn, snapshot.fear_greed_index)

    return JSONResponse(
        {
            "snapshot": {
                "id": snapshot.id,
                "fear_greed_index": snapshot.fear_greed_index,
                "vix": str(snapshot.vix) if snapshot.vix is not None else None,
                "per_broker_pnl": _to_json(snapshot.per_broker_pnl),
                "fetch_errors": snapshot.fetch_errors,
                "created_at": snapshot.created_at.isoformat(),
            },
            "kill_switch": {
                "action": ks_result.action,
                "paused_ids": ks_result.paused_ids,
                "recovered_ids": ks_result.recovered_ids,
            },
        },
        status_code=201,
    )

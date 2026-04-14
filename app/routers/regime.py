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
from app.services.fear_greed import fetch_fear_greed, fetch_vix
from app.services.kill_switch import evaluate_kill_switch
from app.services.regime_snapshot import compute_per_broker_pnl

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


_INSERT_SNAPSHOT_SQL = """
INSERT INTO regime_snapshots (
    fear_greed_index,
    vix,
    per_broker_pnl,
    fetch_errors
) VALUES ($1, $2, $3::jsonb, $4::jsonb)
RETURNING id, created_at
"""


@router.post("/api/regime/snapshot", include_in_schema=False)
async def post_regime_snapshot(request: Request) -> JSONResponse:
    """Create a new regime snapshot and evaluate the kill switch.

    Code-review H4 / BH-5: holds a single connection + transaction for
    the whole sequence (fetch → per-broker-pnl → INSERT snapshot →
    evaluate kill switch). The previous implementation acquired two
    separate connections, leaving a window where a drained pool could
    race a stale snapshot against the kill-switch evaluator and
    half-commit the state.

    Also: on kill-switch failure we still return the snapshot row
    (AC #3 "never drop a day") but with `kill_switch.error` so Chef
    sees the partial success instead of a blanket 500.
    """

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    fetch_errors: dict[str, str] = {}
    async with httpx.AsyncClient() as http_client:
        fear_greed, fg_error = await fetch_fear_greed(http_client)
        if fg_error:
            fetch_errors["fear_greed"] = fg_error
        vix, vix_error = await fetch_vix(http_client)
        if vix_error:
            fetch_errors["vix"] = vix_error

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            per_broker_pnl = await compute_per_broker_pnl(conn)
            snap_row = await conn.fetchrow(
                _INSERT_SNAPSHOT_SQL,
                fear_greed,
                vix,
                per_broker_pnl,
                fetch_errors or None,
            )

        snap_id = snap_row["id"]
        snap_created_at = snap_row["created_at"]

        ks_error: str | None = None
        ks_action = "noop"
        ks_paused_ids: list[int] = []
        ks_recovered_ids: list[int] = []
        try:
            ks_result = await evaluate_kill_switch(conn, fear_greed)
            ks_action = ks_result.action
            ks_paused_ids = ks_result.paused_ids
            ks_recovered_ids = ks_result.recovered_ids
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "regime.snapshot.kill_switch_failed",
                snapshot_id=snap_id,
                error=str(exc),
            )
            ks_error = str(exc)

    logger.info(
        "regime_snapshot.created",
        snapshot_id=snap_id,
        fear_greed_index=fear_greed,
        vix=str(vix) if vix is not None else None,
        fetch_errors=sorted(fetch_errors.keys()) if fetch_errors else [],
    )

    return JSONResponse(
        {
            "snapshot": {
                "id": snap_id,
                "fear_greed_index": fear_greed,
                "vix": str(vix) if vix is not None else None,
                "per_broker_pnl": _to_json(per_broker_pnl),
                "fetch_errors": fetch_errors or None,
                "created_at": snap_created_at.isoformat(),
            },
            "kill_switch": {
                "action": ks_action,
                "paused_ids": ks_paused_ids,
                "recovered_ids": ks_recovered_ids,
                "error": ks_error,
            },
        },
        status_code=201,
    )

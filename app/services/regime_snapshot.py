"""Regime-snapshot orchestrator (Epic 9 / Story 9.1).

Owns:
- `compute_per_broker_pnl(conn)` — 30-day realized P&L aggregation,
  returned as a JSONB-ready dict keyed by broker string.
- `create_regime_snapshot(db_pool, httpx_client)` — the end-to-end
  path called from the daily scheduler (to be wired by Story 11.1):
  fetch F&G + VIX + per-broker P&L, persist one row, return the
  inserted `RegimeSnapshot`.
- `get_latest_regime(conn)` — small helper used by Story 9.3's regime
  page + the Story-7.3 approval viewport footer.

The scheduler registration itself lives in Story 11.1 (System-Health &
Scheduled Operations); this module exposes the service contract so
that story only needs to add a single APScheduler `add_job` call.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import asyncpg
import httpx

from app.logging import get_logger
from app.models.regime import RegimeSnapshot
from app.services.fear_greed import fetch_fear_greed, fetch_vix

logger = get_logger(__name__)


_COMPUTE_PER_BROKER_PNL_SQL = """
SELECT COALESCE(
    jsonb_object_agg(broker::text, total_pnl),
    '{}'::jsonb
) AS per_broker_pnl
FROM (
    SELECT broker, COALESCE(SUM(pnl), 0) AS total_pnl
      FROM trades
     WHERE closed_at IS NOT NULL
       AND closed_at >= NOW() - INTERVAL '30 days'
       AND pnl IS NOT NULL
  GROUP BY broker
) sub
"""


_INSERT_SNAPSHOT_SQL = """
INSERT INTO regime_snapshots (
    fear_greed_index,
    vix,
    per_broker_pnl,
    fetch_errors
) VALUES ($1, $2, $3::jsonb, $4::jsonb)
RETURNING id, created_at
"""


_SELECT_LATEST_SQL = """
SELECT id, fear_greed_index, vix, per_broker_pnl, fetch_errors, created_at
  FROM regime_snapshots
 ORDER BY created_at DESC, id DESC
 LIMIT 1
"""


async def compute_per_broker_pnl(conn: asyncpg.Connection) -> dict[str, Any]:
    """Return the 30-day realized per-broker P&L as a dict.

    Example: `{"ib": "1234.56", "ctrader": "-345.67"}`. Values are
    stringified to keep the downstream JSONB codec happy with Decimal
    precision. Missing brokers fall out cleanly (the SQL uses
    COALESCE + GROUP BY).
    """

    raw = await conn.fetchval(_COMPUTE_PER_BROKER_PNL_SQL)
    if raw is None:
        return {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    # Convert Decimal → str so the JSONB codec stays deterministic.
    return {k: str(v) for k, v in raw.items()}


async def create_regime_snapshot(
    db_pool: Any,
    http_client: httpx.AsyncClient | None = None,
    *,
    owns_http_client: bool = False,
) -> RegimeSnapshot:
    """Fetch F&G + VIX + per-broker P&L, persist one snapshot row,
    return the `RegimeSnapshot` model.

    `http_client` is optional — if None, a short-lived client is
    created and closed inside this function. Callers already holding
    an httpx client (e.g., APScheduler integration) can pass it in
    to avoid the connect-tear-down cost.

    AC #3: per-fetcher errors are captured in `fetch_errors` JSONB so
    the snapshot row is written ALWAYS, even on full data-source outage.
    """

    fetch_errors: dict[str, str] = {}

    if http_client is None:
        http_client = httpx.AsyncClient()
        owns_http_client = True

    try:
        fear_greed, fg_error = await fetch_fear_greed(http_client)
        if fg_error:
            fetch_errors["fear_greed"] = fg_error

        vix, vix_error = await fetch_vix(http_client)
        if vix_error:
            fetch_errors["vix"] = vix_error
    finally:
        if owns_http_client:
            await http_client.aclose()

    async with db_pool.acquire() as conn:
        per_broker_pnl = await compute_per_broker_pnl(conn)
        row = await conn.fetchrow(
            _INSERT_SNAPSHOT_SQL,
            fear_greed,
            vix,
            per_broker_pnl,
            fetch_errors or None,
        )

    if row is None:
        # Shouldn't happen — INSERT ... RETURNING always returns a row
        # on success. Defensive raise for operator visibility.
        raise RuntimeError("regime_snapshot insert returned no row")

    snapshot = RegimeSnapshot(
        id=row["id"],
        fear_greed_index=fear_greed,
        vix=vix,
        per_broker_pnl=per_broker_pnl,
        fetch_errors=fetch_errors or None,
        created_at=row["created_at"],
    )
    logger.info(
        "regime_snapshot.created",
        snapshot_id=snapshot.id,
        fear_greed_index=fear_greed,
        vix=str(vix) if vix is not None else None,
        fetch_errors=sorted(fetch_errors.keys()) if fetch_errors else [],
    )
    return snapshot


async def get_latest_regime(
    conn: asyncpg.Connection,
) -> RegimeSnapshot | None:
    """Return the most recent snapshot (or None on a fresh install)."""

    row = await conn.fetchrow(_SELECT_LATEST_SQL)
    if row is None:
        return None
    raw_pnl = row["per_broker_pnl"] or {}
    if isinstance(raw_pnl, str):
        raw_pnl = json.loads(raw_pnl)
    raw_errors = row["fetch_errors"]
    if isinstance(raw_errors, str):
        raw_errors = json.loads(raw_errors)
    return RegimeSnapshot(
        id=row["id"],
        fear_greed_index=row["fear_greed_index"],
        vix=Decimal(str(row["vix"])) if row["vix"] is not None else None,
        per_broker_pnl=raw_pnl,
        fetch_errors=raw_errors,
        created_at=row["created_at"],
    )

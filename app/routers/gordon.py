"""Gordon API routes (Epic 10).

- `POST /api/gordon/fetch` — manual trigger for the weekly Gordon
  trend-radar snapshot. Story 11.1's APScheduler integration will
  call `fetch_and_persist` directly on the Monday 06:00 UTC cron;
  this route is the UI-facing manual path for the Trends page's
  refresh button and for ad-hoc operator diagnostics.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.logging import get_logger
from app.services.gordon import fetch_and_persist

logger = get_logger(__name__)

router = APIRouter(tags=["gordon"])


@router.post("/api/gordon/fetch", include_in_schema=False)
async def post_gordon_fetch(request: Request) -> JSONResponse:
    """Fetch the latest Gordon trend radar via MCP and persist it.

    Returns 201 with the snapshot metadata. Never raises on MCP
    failure — Story 10.1 AC #3 ("bei Fehler keine Silent Failure")
    is honored by `fetch_and_persist`, which still writes a row with
    an empty hot_picks array and a populated `source_error` so the
    weekly heartbeat stays durable.

    Code-review H4 / BH-23: DB-layer failures (connection loss,
    migration 014 missing) used to leak 500s with a Python traceback
    in the JSON body. Now wrapped in try/except → structured 503.
    """

    import asyncpg

    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None or not hasattr(db_pool, "acquire"):
        raise HTTPException(status_code=503, detail="db_pool unavailable")

    mcp_client = getattr(request.app.state, "mcp_client", None)

    try:
        snapshot = await fetch_and_persist(db_pool, mcp_client)
    except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError) as exc:
        logger.error(
            "gordon.fetch.migration_missing",
            error=str(exc),
            hint="run migrate to apply migration 014_gordon_snapshots.sql",
        )
        raise HTTPException(
            status_code=503,
            detail="gordon_snapshots table missing — apply migration 014",
        ) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("gordon.fetch.unexpected_failure", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail=f"gordon fetch failed: {type(exc).__name__}",
        ) from None

    return JSONResponse(
        {
            "snapshot": {
                "id": snapshot.id,
                "hot_picks_count": len(snapshot.hot_picks),
                "source_error": snapshot.source_error,
                "created_at": snapshot.created_at.isoformat(),
            },
        },
        status_code=201,
    )

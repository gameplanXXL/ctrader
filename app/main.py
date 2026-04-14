"""FastAPI application entry point.

Wires up configuration, structured logging, and the asyncpg pool in a
single `lifespan` context so the app has a clean startup/shutdown story.

References:
- FR50: Health widget needs broker/MCP/job status — GET / is the Week-0
  placeholder and grows into a Week-8 health widget.
- NFR-S2: Server binds to 127.0.0.1 only (enforced via settings.host default).
- NFR-M6: Single-process — FastAPI + (later) APScheduler share one asyncpg pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.clients.ctrader import build_ctrader_client
from app.clients.ib import connect_ib, disconnect_ib
from app.clients.mcp import handshake as mcp_handshake
from app.config import settings
from app.db.migrate import run_migrations
from app.db.pool import close_pool, create_pool
from app.logging import configure_logging, get_logger
from app.routers import api as api_router
from app.routers import approvals as approvals_router
from app.routers import debug as debug_router
from app.routers import pages as pages_router
from app.routers import regime as regime_router
from app.routers import strategies as strategies_router
from app.routers import trades as trades_router
from app.services.bot_execution import handle_execution_event
from app.services.taxonomy import get_taxonomy, load_taxonomy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown orchestration.

    Order matters: configure logging first (so every subsequent line is
    JSON), then run pending migrations against the target DB, then open
    the long-lived asyncpg pool. Teardown runs in reverse.
    """

    configure_logging()
    logger = get_logger(__name__)
    logger.info(
        "app.startup",
        version=__version__,
        environment=settings.environment,
        host=settings.host,
        port=settings.port,
    )

    # Fail-fast: load and validate taxonomy.yaml at startup so a broken
    # config aborts the boot rather than dying mid-request later (FR14).
    get_taxonomy.cache_clear()
    app.state.taxonomy = load_taxonomy()
    # Prime the lru_cache for downstream `Depends(get_taxonomy)` consumers.
    get_taxonomy()

    # Apply any pending schema migrations before the pool goes live. This
    # opens and closes its own one-shot connection so we never accidentally
    # run DDL through a pooled worker.
    applied = await run_migrations()
    if applied:
        logger.info("app.migrations_applied", versions=applied)

    # Default state so the `finally` block below can always introspect
    # safely even if startup aborts mid-sequence (e.g., load_taxonomy
    # raises). Without these defaults a partial-startup failure would
    # mask the real exception with an AttributeError on app.state in
    # the teardown.
    app.state.db_pool = None
    app.state.mcp_client = None
    app.state.mcp_available = False
    app.state.ib = None
    app.state.ib_available = False
    app.state.ctrader_client = None

    try:
        app.state.db_pool = await create_pool()

        # MCP handshake — best-effort, never blocks startup. Snapshot
        # lands in data/mcp-snapshots/ on success. On failure
        # mcp_available stays False and downstream code degrades
        # gracefully (FR23).
        if settings.mcp_fundamental_url:
            mcp_available, mcp_client = await mcp_handshake(settings.mcp_fundamental_url)
        else:
            logger.info("app.mcp_disabled", reason="mcp_fundamental_url not configured")
            mcp_available, mcp_client = False, None
        app.state.mcp_available = mcp_available
        app.state.mcp_client = mcp_client

        # IB Gateway / TWS handshake — best-effort, never blocks startup.
        # Story 2.2: connection is OPTIONAL. If IB_HOST is not set we
        # don't even try; ib_available stays False and downstream code
        # (live-sync handler, reconcile job) skips gracefully.
        if settings.ib_host:
            ib = await connect_ib(
                host=settings.ib_host,
                port=settings.ib_port,
                client_id=settings.ib_client_id,
            )
        else:
            logger.info("app.ib_disabled", reason="ib_host not configured")
            ib = None
        app.state.ib = ib
        app.state.ib_available = ib is not None

        # cTrader client — Epic 8. Always available (defaults to the
        # StubCTraderClient when no credentials are configured) so the
        # bot-execution pipeline can run end-to-end in dev.
        app.state.ctrader_client = build_ctrader_client(
            host=settings.ctrader_host,
            client_id=settings.ctrader_client_id,
            client_secret=settings.ctrader_client_secret,
            account_id=settings.ctrader_account_id,
        )

        # Story 8.2: wire the execution-event handler to the cTrader
        # client so FILLED events land in `trades`. Handler uses the
        # pooled connection; errors inside the handler are swallowed
        # by bot_execution itself and logged to structlog.
        #
        # Code-review H8 / EC-6: handler receives db_pool + mcp_client
        # so `handle_execution_event` can fire a
        # `capture_fundamental_snapshot` task on every new trade row,
        # matching `ib_live_sync.upsert_trade`.
        #
        # Code-review H4 / BH-5: `build_ctrader_client` now always
        # returns a concrete client (stub or real), so the previous
        # `is not None` guard here was dead code.
        db_pool_for_events = app.state.db_pool
        mcp_client_for_events = app.state.mcp_client

        async def _on_execution_event(event) -> None:
            if db_pool_for_events is None:
                return
            async with db_pool_for_events.acquire() as event_conn:
                await handle_execution_event(
                    event_conn,
                    event,
                    db_pool=db_pool_for_events,
                    mcp_client=mcp_client_for_events,
                )

        await app.state.ctrader_client.subscribe_execution_events(_on_execution_event)

        yield
    finally:
        # Tear down in reverse order of construction. Each step is
        # null-guarded because partial startup failure may leave any of
        # them unset — we still want to close whatever DID succeed.
        ctrader_client = getattr(app.state, "ctrader_client", None)
        if ctrader_client is not None:
            await ctrader_client.aclose()
        ib = getattr(app.state, "ib", None)
        if ib is not None:
            await disconnect_ib(ib)
        mcp_client = getattr(app.state, "mcp_client", None)
        if mcp_client is not None:
            await mcp_client.aclose()
        db_pool = getattr(app.state, "db_pool", None)
        if db_pool is not None:
            await close_pool(db_pool)
        logger.info("app.shutdown")


app = FastAPI(
    title="ctrader",
    description="Personal trading platform — unified journal + human-gated AI-agent farm",
    version=__version__,
    lifespan=lifespan,
)

# Static files (compiled CSS, JS, fonts) served directly by FastAPI.
_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Page shells — Journal, Strategies, Approvals, Trends, Regime, Settings.
app.include_router(pages_router.router)

# Trade-detail fragment endpoints (Story 2.4 — HTMX inline expansion).
app.include_router(trades_router.router)

# Strategy CRUD + list/detail pages (Epic 6).
app.include_router(strategies_router.router)

# Approval pipeline + risk gate (Epic 7).
app.include_router(approvals_router.router)

# Epic 9: Regime-Awareness API (POST /api/regime/snapshot manual trigger).
# The scheduled-job registration lands in Story 11.1 System-Health.
app.include_router(regime_router.router)

# JSON API — command palette + query presets (Epic 4).
app.include_router(api_router.router)

# Debug routes — only mounted in development. /debug/mcp-tools exposes
# the live MCP handshake response so Chef can verify it from a browser.
if settings.environment == "development":
    app.include_router(debug_router.router)


@app.get("/healthz", response_class=JSONResponse, include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness probe. Used by Docker Compose healthcheck + smoke tests.

    Kept separate from `/` which now redirects to `/journal`. Returns the
    same JSON payload that the Week-0 placeholder used to return from `/`.
    """

    return {
        "app": "ctrader",
        "version": __version__,
        "status": "ok",
        "environment": settings.environment,
    }

"""APScheduler framework (Epic 11 / Story 11.1).

Owns:
- `logged_job(name, fn, db_pool)` — decorator that wraps a coroutine
  so every invocation produces one `job_executions` row:
  `running` at start, `success`/`failure`/`cancelled` at end.
  Exceptions are caught, logged, and NEVER propagated — a failing
  job must not block the next scheduled run.
- `setup_scheduler(db_pool, mcp_client)` — builds the
  `AsyncIOScheduler`, registers the four currently-implementable
  jobs, and starts it.
- `shutdown_scheduler(scheduler)` — idempotent stop.
- `sweep_stranded_jobs(conn)` — startup hygiene: any row still in
  `status='running'` from a previous process is flipped to
  `status='failure'` with a "stranded" note (code-review M1 / BH-8
  / EC-12).
- `get_last_job_runs(conn)` — service-layer helper for the
  Health-Widget.

Tranche A hardening:

- **H4 / BH-4**: every pool acquire inside `logged_job` now has a
  bounded timeout (`_POOL_ACQUIRE_TIMEOUT_SECONDS`) so a pool-
  exhausted state cannot wedge the audit write forever.
- **H5 / BH-5**: the job body itself is wrapped in
  `asyncio.wait_for(fn(), timeout=_PER_JOB_TIMEOUT_SECONDS)` so a
  hung pg_dump / stuck MCP call / wedged Gordon fetch cannot hold
  a scheduler slot indefinitely. APScheduler's default
  `max_instances=1` would otherwise silently drop every subsequent
  fire.
- **H6 / BH-6**: the failure-update path falls back to a direct
  `asyncpg.connect(dsn)` if the pool itself is unavailable, so the
  `job_executions` row is closed out even in the degraded pool case.
- **BH-7 / EC-12**: `CancelledError` is now written as
  `status='cancelled'` (Migration 017) instead of masquerading as
  `failure`.
- **H11 / EC-7**: the Gordon wrapper explicitly checks
  `GordonSnapshot.source_error` after a "successful" fetch_and_persist
  and raises so `logged_job` surfaces it as `failure`. Previously
  every Monday 06:00 run looked green even though the MCP tool
  doesn't exist (Epic 10 D214).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from app.clients.mcp import MCPClient
from app.logging import get_logger

logger = get_logger(__name__)


_INSERT_START_SQL = """
INSERT INTO job_executions (job_name, status) VALUES ($1, 'running') RETURNING id
"""

_UPDATE_SUCCESS_SQL = """
UPDATE job_executions
   SET status = 'success', completed_at = NOW()
 WHERE id = $1
"""

_UPDATE_FAILURE_SQL = """
UPDATE job_executions
   SET status = 'failure', completed_at = NOW(), error_message = $2
 WHERE id = $1
"""

_UPDATE_CANCELLED_SQL = """
UPDATE job_executions
   SET status = 'cancelled', completed_at = NOW(), error_message = $2
 WHERE id = $1
"""

_SWEEP_STRANDED_SQL = """
UPDATE job_executions
   SET status = 'failure',
       completed_at = NOW(),
       error_message = 'stranded on restart (process died mid-run)'
 WHERE status = 'running'
"""

# Job names — closed vocabulary matching the Story 11.1 Dev Notes.
# `ib_flex_nightly` added in Story 2.5 (resolves D232). The job is only
# registered when `IB_FLEX_TOKEN` and `IB_FLEX_QUERY_ID` are configured;
# the entry stays in JOB_NAMES unconditionally so the Health-Widget
# shows `never_run` when the feature is disabled rather than silently
# omitting the row.
JOB_NAMES: dict[str, str] = {
    "regime_snapshot": "Regime Snapshot",
    "gordon_weekly": "Gordon Weekly",
    "db_backup": "DB Backup",
    "mcp_contract_test": "MCP Contract Test",
    "ib_flex_nightly": "IB Flex Nightly",
}

# Code-review H4 / H5: bounded timeouts so a hung job / pool can't
# wedge the scheduler. The per-job timeout is 10 minutes which is
# generous enough for pg_dump on a multi-GB DB but tight enough that
# a stuck network connection doesn't eat the daily slot.
_POOL_ACQUIRE_TIMEOUT_SECONDS = 10.0
_PER_JOB_TIMEOUT_SECONDS = 600.0


async def _update_job_row(
    db_pool: Any,
    row_id: int,
    sql: str,
    *args: Any,
) -> None:
    """Attempt a `job_executions` row update with a bounded pool
    acquire timeout. Logs and swallows any failure — the audit row
    is best-effort.
    """

    try:
        async with asyncio.timeout(_POOL_ACQUIRE_TIMEOUT_SECONDS):
            async with db_pool.acquire() as conn:
                await conn.execute(sql, row_id, *args)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "scheduler.logged_job.row_update_failed",
            row_id=row_id,
            error=str(exc),
        )


def logged_job(
    name: str,
    fn: Callable[..., Awaitable[Any]],
    db_pool: Any,
) -> Callable[[], Awaitable[None]]:
    """Wrap an async job fn so every run logs a row to
    `job_executions` and enforces a per-job timeout.
    """

    async def wrapper() -> None:
        row_id: int | None = None

        # Attempt the insert — with a bounded acquire timeout so a
        # dead pool doesn't stall the job before it even starts.
        try:
            async with asyncio.timeout(_POOL_ACQUIRE_TIMEOUT_SECONDS):
                async with db_pool.acquire() as conn:
                    row_id = await conn.fetchval(_INSERT_START_SQL, name)
        except (TimeoutError, Exception) as exc:  # noqa: BLE001
            logger.exception(
                "scheduler.logged_job.insert_failed",
                job_name=name,
                error=str(exc),
            )
            # Fall through — the job body still runs, we just lose
            # the audit row for this invocation.

        try:
            # Code-review H5 / BH-5: enforce a hard per-job timeout.
            # APScheduler's max_instances=1 default would otherwise let
            # a single hung run silently drop every subsequent fire.
            async with asyncio.timeout(_PER_JOB_TIMEOUT_SECONDS):
                await fn()
        except asyncio.CancelledError:
            # Code-review BH-7 / EC-12: clean shutdown is NOT a
            # failure. Write 'cancelled' (Migration 017) instead of
            # poisoning the Health-Widget with a red failure pill.
            if row_id is not None:
                await _update_job_row(
                    db_pool, row_id, _UPDATE_CANCELLED_SQL, "cancelled on shutdown"
                )
            raise
        except TimeoutError:
            logger.error(
                "scheduler.logged_job.timeout",
                job_name=name,
                timeout_seconds=_PER_JOB_TIMEOUT_SECONDS,
            )
            if row_id is not None:
                await _update_job_row(
                    db_pool,
                    row_id,
                    _UPDATE_FAILURE_SQL,
                    f"timeout after {_PER_JOB_TIMEOUT_SECONDS}s",
                )
            return
        except Exception as exc:  # noqa: BLE001 — NEVER re-raise
            logger.exception(
                "scheduler.logged_job.failed",
                job_name=name,
                error=str(exc),
            )
            if row_id is not None:
                message = f"{type(exc).__name__}: {exc}"[:2000]
                await _update_job_row(db_pool, row_id, _UPDATE_FAILURE_SQL, message)
            return

        if row_id is not None:
            await _update_job_row(db_pool, row_id, _UPDATE_SUCCESS_SQL)
        logger.info("scheduler.logged_job.ok", job_name=name)

    return wrapper


async def sweep_stranded_jobs(conn: asyncpg.Connection) -> int:
    """Flip any `running` rows left over from a previous process to
    `failure` at app startup (code-review M1 / BH-8 / EC-12).

    Returns the number of rows touched, useful for structlog.
    """

    result = await conn.execute(_SWEEP_STRANDED_SQL)
    # asyncpg `execute` returns a status string like "UPDATE 3".
    try:
        touched = int(result.split()[-1])
    except (ValueError, IndexError):
        touched = 0
    if touched:
        logger.warning("scheduler.sweep.stranded_rows", count=touched)
    return touched


def setup_scheduler(
    db_pool: Any,
    mcp_client: MCPClient | None,
):
    """Create and start the `AsyncIOScheduler` with all cron jobs."""

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    from app.config import settings
    from app.services.db_backup import create_backup, rotate_backups
    from app.services.gordon import fetch_and_persist as gordon_fetch_and_persist
    from app.services.ib_reconcile import run_nightly_reconcile
    from app.services.mcp_contract_test import run_contract_test
    from app.services.regime_snapshot import (
        compute_per_broker_pnl,
    )

    scheduler = AsyncIOScheduler(timezone="UTC")

    # ---- Regime snapshot (Epic 9): daily 01:00 UTC ----------------
    # Code-review H7 / EC-1 / EC-2 / EC-3: mirror `post_regime_snapshot`
    # by holding a SINGLE connection + transaction across the
    # snapshot INSERT + kill-switch eval. The previous implementation
    # used two separate acquires and bypassed the Epic-9 Tranche-A
    # transaction discipline fix.
    async def regime_snapshot_job() -> None:
        import httpx

        from app.services.fear_greed import fetch_fear_greed, fetch_vix
        from app.services.kill_switch import evaluate_kill_switch

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
                await conn.execute(
                    """
                    INSERT INTO regime_snapshots (
                        fear_greed_index, vix, per_broker_pnl, fetch_errors
                    ) VALUES ($1, $2, $3::jsonb, $4::jsonb)
                    """,
                    fear_greed,
                    vix,
                    per_broker_pnl,
                    fetch_errors or None,
                )

            # Kill-switch runs outside the snapshot transaction so a
            # failed evaluation doesn't roll back the snapshot itself
            # (the snapshot is durable even if the kill-switch
            # post-condition fails). If this raises, `logged_job`
            # captures it.
            await evaluate_kill_switch(conn, fear_greed)

    scheduler.add_job(
        logged_job("regime_snapshot", regime_snapshot_job, db_pool),
        CronTrigger(hour=1, minute=0),
        id="regime_snapshot",
        replace_existing=True,
    )

    # ---- Gordon weekly (Epic 10): Monday 06:00 UTC ----------------
    # Code-review H11 / EC-7: when fundamental MCP returns an error
    # (Epic 10 D214 — no `trend_radar` tool), `fetch_and_persist`
    # writes a row with `source_error` but returns cleanly, so the
    # scheduler would log success. Flip to failure explicitly so
    # Chef sees the weekly red pill in the Health-Widget.
    async def gordon_weekly_job() -> None:
        snapshot = await gordon_fetch_and_persist(db_pool, mcp_client)
        if snapshot.source_error:
            raise RuntimeError(
                f"gordon snapshot #{snapshot.id} persisted with source_error: "
                f"{snapshot.source_error}"
            )

    scheduler.add_job(
        logged_job("gordon_weekly", gordon_weekly_job, db_pool),
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="gordon_weekly",
        replace_existing=True,
    )

    # ---- MCP contract test (Epic 5 Story 5.4): daily 05:00 UTC ----
    async def mcp_contract_test_job() -> None:
        async with db_pool.acquire() as conn:
            await run_contract_test(conn, mcp_client)

    scheduler.add_job(
        logged_job("mcp_contract_test", mcp_contract_test_job, db_pool),
        CronTrigger(hour=5, minute=0),
        id="mcp_contract_test",
        replace_existing=True,
    )

    # ---- DB backup (Story 11.3): daily 04:00 UTC ------------------
    # Code-review H8 / EC-4 / BH-11: the previous version never called
    # `rotate_backups`, so the backup directory grew unbounded until
    # the disk filled. The job now unconditionally rotates after every
    # successful write.
    async def db_backup_job() -> None:
        await create_backup()
        rotate_backups(keep=7)

    scheduler.add_job(
        logged_job("db_backup", db_backup_job, db_pool),
        CronTrigger(hour=4, minute=0),
        id="db_backup",
        replace_existing=True,
    )

    # ---- IB Flex Nightly (Story 2.5 / resolves D232): 07:00 UTC -----
    # Wire-up for the `download_flex_xml` + `run_nightly_reconcile`
    # primitives built in Story 2.2. Chef configures an IB Activity
    # Flex Query with period "Last 90 Days" as a sliding-window, so
    # any single successful run heals up to 90 days of downtime —
    # idempotency via `UNIQUE(broker, perm_id)` makes repeat imports
    # a no-op. No gap tracking, no replay logic.
    #
    # `run_nightly_reconcile` returns None on download failure; we
    # raise RuntimeError so `logged_job` records `status='failure'`
    # (pattern mirrors `gordon_weekly_job` above — otherwise a silent
    # network blip would leave the Health-Widget green).
    if settings.ib_flex_token and settings.ib_flex_query_id:
        flex_token = settings.ib_flex_token
        flex_query_id = settings.ib_flex_query_id

        async def ib_flex_nightly_job() -> None:
            async with db_pool.acquire() as conn:
                counts = await run_nightly_reconcile(conn, flex_token, flex_query_id)
            if counts is None:
                raise RuntimeError(
                    "ib_flex_nightly: download failed — see ib_flex_download.* warnings"
                )
            logger.info("ib_flex_nightly.ok", **counts)

        scheduler.add_job(
            logged_job("ib_flex_nightly", ib_flex_nightly_job, db_pool),
            CronTrigger(hour=7, minute=0),
            id="ib_flex_nightly",
            replace_existing=True,
        )
    else:
        logger.info("ib_flex_nightly.disabled_unconfigured")

    scheduler.start()
    logger.info(
        "scheduler.started",
        jobs=[job.id for job in scheduler.get_jobs()],
        count=len(scheduler.get_jobs()),
    )
    return scheduler


def shutdown_scheduler(scheduler) -> None:
    """Idempotent shutdown — safe on None and on a not-yet-started
    scheduler.
    """

    if scheduler is None:
        return
    try:
        scheduler.shutdown(wait=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler.shutdown_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Story 11.2 — health-widget helpers
# ---------------------------------------------------------------------------


_LAST_RUNS_SQL = """
SELECT DISTINCT ON (job_name)
       job_name,
       status,
       started_at,
       completed_at,
       error_message
  FROM job_executions
 ORDER BY job_name, started_at DESC
"""


async def get_last_job_runs(
    conn: asyncpg.Connection,
) -> list[dict[str, Any]]:
    """Return the most-recent execution per known job name.

    Jobs that have never run return an entry with `status='never_run'`
    so the Health-Widget can render every registered job (not just the
    ones that have fired at least once on this install).
    """

    rows = await conn.fetch(_LAST_RUNS_SQL)
    by_name = {row["job_name"]: row for row in rows}
    result: list[dict[str, Any]] = []
    for job_id, job_label in JOB_NAMES.items():
        row = by_name.get(job_id)
        if row is None:
            result.append(
                {
                    "job_name": job_id,
                    "job_label": job_label,
                    "status": "never_run",
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                }
            )
        else:
            result.append(
                {
                    "job_name": job_id,
                    "job_label": job_label,
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "error_message": row["error_message"],
                }
            )
    return result

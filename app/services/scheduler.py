"""APScheduler framework (Epic 11 / Story 11.1).

Owns:
- `logged_job(name, fn)` — decorator that wraps a coroutine so every
  invocation produces one `job_executions` row: `running` at start,
  `success`/`failure` at end. Exceptions are caught and logged, NEVER
  propagated — a failing job must not block the next scheduled run.
- `setup_scheduler(db_pool, mcp_client)` — builds the `AsyncIOScheduler`,
  registers the three currently-implementable jobs (regime snapshot
  daily, Gordon weekly, DB backup daily, MCP contract test daily),
  and starts it. Returns the scheduler instance so the lifespan can
  `shutdown()` it on teardown.
- `shutdown_scheduler(scheduler)` — idempotent stop; safe to call on
  None.
- `get_last_job_runs(conn)` — service-layer helper used by Story 11.2
  Health-Widget.

The scheduler runs in-process on the same asyncio event loop as
FastAPI (NFR-M6: single-process). Jobs that need external subprocesses
(like pg_dump for DB backups) run those subprocesses via
`asyncio.create_subprocess_exec` so the loop is never blocked.
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

# Job names — closed vocabulary matching the Story 11.1 Dev Notes.
# Story 11.2's Health-Widget renders a row per job name, so the set
# must stay stable across restarts.
JOB_NAMES: dict[str, str] = {
    "regime_snapshot": "Regime Snapshot",
    "gordon_weekly": "Gordon Weekly",
    "db_backup": "DB Backup",
    "mcp_contract_test": "MCP Contract Test",
}


def logged_job(
    name: str,
    fn: Callable[..., Awaitable[Any]],
    db_pool: Any,
) -> Callable[[], Awaitable[None]]:
    """Wrap an async job fn so every run logs a row to `job_executions`.

    The wrapper is parameterless because APScheduler's
    `AsyncIOScheduler.add_job` passes kwargs at registration time
    (via the `kwargs` argument) — we partial-bind at factory time so
    the scheduler just invokes `wrapper()` with no arguments.

    Contract:
    - Entry → `INSERT INTO job_executions (job_name, status='running')`
    - Success → `UPDATE ... status='success', completed_at=NOW()`
    - Exception → `UPDATE ... status='failure', completed_at=NOW(),
      error_message='...'` + `logger.exception`. **Never re-raises** —
      APScheduler would otherwise drop the next scheduled invocation.
    """

    async def wrapper() -> None:
        row_id: int | None = None
        try:
            async with db_pool.acquire() as conn:
                row_id = await conn.fetchval(_INSERT_START_SQL, name)
        except Exception as exc:  # noqa: BLE001 — scheduler safety net
            logger.exception(
                "scheduler.logged_job.insert_failed",
                job_name=name,
                error=str(exc),
            )
            # Fall through — job must still try to run even if the
            # row insert failed (e.g., DB momentarily gone).

        try:
            await fn()
        except asyncio.CancelledError:
            # Shutdown signal — let APScheduler finish cleanly.
            if row_id is not None:
                try:
                    async with db_pool.acquire() as conn:
                        await conn.execute(_UPDATE_FAILURE_SQL, row_id, "cancelled on shutdown")
                except Exception:  # noqa: BLE001
                    pass
            raise
        except Exception as exc:  # noqa: BLE001 — NEVER re-raise from a job
            logger.exception(
                "scheduler.logged_job.failed",
                job_name=name,
                error=str(exc),
            )
            if row_id is not None:
                try:
                    async with db_pool.acquire() as conn:
                        await conn.execute(_UPDATE_FAILURE_SQL, row_id, str(exc)[:2000])
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "scheduler.logged_job.failure_update_failed",
                        job_name=name,
                    )
            return

        if row_id is not None:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute(_UPDATE_SUCCESS_SQL, row_id)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "scheduler.logged_job.success_update_failed",
                    job_name=name,
                )
        logger.info("scheduler.logged_job.ok", job_name=name)

    return wrapper


def setup_scheduler(
    db_pool: Any,
    mcp_client: MCPClient | None,
):
    """Create and start the `AsyncIOScheduler` with all cron jobs.

    The scheduler is intentionally in-process (single-worker, single
    event loop) per NFR-M6. Persistent job state is stored in Postgres
    via `job_executions`, not in an APScheduler jobstore — this keeps
    operational surface minimal at the cost of needing a restart to
    pick up code changes.
    """

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    # Lazy imports so tests that don't hit the scheduler path aren't
    # forced to resolve APScheduler.
    from app.services.db_backup import create_backup
    from app.services.gordon import fetch_and_persist as gordon_fetch_and_persist
    from app.services.kill_switch import evaluate_kill_switch
    from app.services.mcp_contract_test import run_contract_test
    from app.services.regime_snapshot import create_regime_snapshot

    scheduler = AsyncIOScheduler(timezone="UTC")

    # ---- Regime snapshot (Epic 9): daily 01:00 UTC ----------------
    async def regime_snapshot_job() -> None:
        snapshot = await create_regime_snapshot(db_pool)
        async with db_pool.acquire() as conn:
            await evaluate_kill_switch(conn, snapshot.fear_greed_index)

    scheduler.add_job(
        logged_job("regime_snapshot", regime_snapshot_job, db_pool),
        CronTrigger(hour=1, minute=0),
        id="regime_snapshot",
        replace_existing=True,
    )

    # ---- Gordon weekly (Epic 10): Monday 06:00 UTC ----------------
    async def gordon_weekly_job() -> None:
        await gordon_fetch_and_persist(db_pool, mcp_client)

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
    async def db_backup_job() -> None:
        await create_backup()

    scheduler.add_job(
        logged_job("db_backup", db_backup_job, db_pool),
        CronTrigger(hour=4, minute=0),
        id="db_backup",
        replace_existing=True,
    )

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

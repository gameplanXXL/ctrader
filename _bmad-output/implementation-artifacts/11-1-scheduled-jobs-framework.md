# Story 11.1: Scheduled-Jobs-Framework & Ausfuehrungs-Logging

Status: ready-for-dev

<!-- Renumbered 2026-04-14 from 12.1 → 11.1 per PM-scope-update (Epic 11 ↔ 12 swap, Chef request). Content unchanged. -->


## Story

As a Chef,
I want all scheduled jobs to run reliably and log their execution,
so that I can trust that background processes are working correctly.

## Acceptance Criteria

1. **Given** die App startet mit neuer Migration, **When** migrate laeuft, **Then** wird die `job_executions`-Tabelle erstellt mit: id, job_name, status (success/failure), started_at, completed_at, error_message
2. **Given** die App laeuft im Single-Process-Modus, **When** APScheduler im FastAPI-Lifespan konfiguriert ist, **Then** sind folgende Jobs registriert: IB Flex Nightly, Regime-Snapshot (taeglich), Gordon-Weekly (Montag 06:00 UTC), MCP-Contract-Test (taeglich), DB-Backup (taeglich 04:00 UTC) (FR49, NFR-M6)
3. **Given** ein Scheduled Job laeuft, **When** er abgeschlossen ist (Erfolg oder Fehler), **Then** wird ein job_executions-Eintrag mit Status und Zeitstempel geschrieben (FR49)
4. **Given** ein Job schlaegt fehl, **When** der Fehler geloggt wird, **Then** enthaelt der Log-Eintrag die error_message und der naechste planmaessige Lauf wird nicht blockiert

## Tasks / Subtasks

- [ ] Task 1: Migration 020_job_executions.sql
  - [ ] Tabelle mit Schema
- [ ] Task 2: APScheduler-Integration im Lifespan (AC: 2)
  - [ ] `app/jobs/scheduler.py` — `setup_scheduler(app)`
  - [ ] AsyncIOScheduler instantiieren
  - [ ] Start in FastAPI startup, Stop in shutdown
- [ ] Task 3: Job-Wrapper fuer Logging (AC: 3, 4)
  - [ ] Decorator `@logged_job(name='job_name')` wrappt jeden Job
  - [ ] INSERT job_executions beim Start + UPDATE beim Ende
  - [ ] Exception-Handling ohne Crash
- [ ] Task 4: Job-Registrations
  - [ ] IB Flex Nightly (Story 2.2): daily 02:00 UTC
  - [ ] Regime-Snapshot (Story 9.1): daily 01:00 UTC
  - [ ] Gordon-Weekly (Story 10.1): Monday 06:00 UTC
  - [ ] MCP-Contract-Test (Story 5.4): daily 05:00 UTC
  - [ ] DB-Backup (Story 12.3): daily 04:00 UTC
- [ ] Task 5: Tests
  - [ ] Unit-Test: Decorator-Logging
  - [ ] Integration-Test: Scheduler started + jobs registered
  - [ ] Test: Job Failure → logged, next run not blocked

## Dev Notes

**job_executions Schema:**
```sql
CREATE TABLE job_executions (
    id SERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running', 'success', 'failure'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);
CREATE INDEX idx_job_executions_job_name_started ON job_executions(job_name, started_at DESC);
```

**APScheduler-Setup:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler: AsyncIOScheduler | None = None

def setup_scheduler(app, db_pool, mcp_client, ib_client):
    global scheduler
    scheduler = AsyncIOScheduler()

    # IB Flex Nightly
    scheduler.add_job(
        logged_job('ib_flex_nightly', ib_flex_nightly_job),
        CronTrigger(hour=2, minute=0),
        kwargs={'ib_client': ib_client, 'db_pool': db_pool},
    )

    # Regime Snapshot
    scheduler.add_job(
        logged_job('regime_snapshot', regime_snapshot_job),
        CronTrigger(hour=1, minute=0),
        kwargs={'db_pool': db_pool},
    )

    # Gordon Weekly
    scheduler.add_job(
        logged_job('gordon_weekly', gordon_weekly_job),
        CronTrigger(day_of_week='mon', hour=6, minute=0, timezone='UTC'),
        kwargs={'mcp_client': mcp_client, 'db_pool': db_pool},
    )

    # MCP Contract Test
    scheduler.add_job(
        logged_job('mcp_contract_test', mcp_contract_test_job),
        CronTrigger(hour=5, minute=0),
        kwargs={'mcp_client': mcp_client, 'db_pool': db_pool},
    )

    # DB Backup
    scheduler.add_job(
        logged_job('db_backup', db_backup_job),
        CronTrigger(hour=4, minute=0),
        kwargs={'db_pool': db_pool},
    )

    scheduler.start()

def shutdown_scheduler():
    if scheduler:
        scheduler.shutdown()
```

**Logged-Job-Decorator:**
```python
def logged_job(name: str, fn):
    async def wrapper(**kwargs):
        db_pool = kwargs.get('db_pool')
        row_id = await db_pool.fetchval(
            "INSERT INTO job_executions (job_name, status) VALUES ($1, 'running') RETURNING id",
            name
        )
        try:
            await fn(**kwargs)
            await db_pool.execute(
                "UPDATE job_executions SET status = 'success', completed_at = NOW() WHERE id = $1",
                row_id
            )
            logger.info("job_completed", name=name)
        except Exception as e:
            await db_pool.execute(
                "UPDATE job_executions SET status = 'failure', completed_at = NOW(), error_message = $2 WHERE id = $1",
                row_id, str(e)
            )
            logger.error("job_failed", name=name, error=str(e))
            # WICHTIG: KEINE raise — nicht den Scheduler blockieren
    return wrapper
```

**FastAPI Lifespan Integration:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing setup (db_pool, mcp_client) ...
    setup_scheduler(app, app.state.db_pool, app.state.mcp_client, app.state.ib_client)
    yield
    shutdown_scheduler()
```

**File Structure:**
```
migrations/
└── 020_job_executions.sql       # NEW
app/
├── jobs/
│   ├── __init__.py              # NEW
│   ├── scheduler.py             # NEW - setup + decorator
│   ├── ib_flex_nightly.py       # EXISTS (Story 2.2)
│   ├── regime_snapshot.py       # EXISTS (Story 9.1)
│   ├── gordon_weekly.py         # EXISTS (Story 10.1)
│   ├── mcp_contract_test.py     # EXISTS (Story 5.4)
│   └── db_backup.py             # NEW (Story 12.3)
└── main.py                      # UPDATE - lifespan integration
```

### References

- PRD: FR49, NFR-M6
- Architecture: "Scheduled Jobs & Backups"
- Dependency: Alle vorherigen Job-Stories (2.2, 5.4, 9.1, 10.1, 12.3)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

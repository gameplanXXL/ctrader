-- 016_job_executions.sql
--
-- Epic 11 / Story 11.1 — scheduled-job execution log.
--
-- Every APScheduler job registered in `app/services/scheduler.py`
-- wraps its body with `logged_job(...)` which inserts one row here
-- per invocation: `running` at start, then `UPDATE` to
-- `success` / `failure` + `completed_at` + optional `error_message`
-- on return.
--
-- Consumed by:
-- - Story 11.2 Health-Widget (`/api/health`): "last successful run"
--   timestamps per job name, plus currently-running count.
-- - Story 12.2 future operator-facing log viewer.
-- - Ad-hoc forensics: "why didn't the Gordon job fire last Monday?".
--
-- `status` is a closed vocabulary via CHECK to mirror the
-- audit_log discipline (Migration 009). Any new status needs a
-- migration + code change.

CREATE TABLE IF NOT EXISTS job_executions (
    id              SERIAL          PRIMARY KEY,
    job_name        TEXT            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'running'
                                    CHECK (status IN ('running', 'success', 'failure')),
    started_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_executions_job_name_started
    ON job_executions (job_name, started_at DESC);

-- Partial index for "show me currently running jobs" queries — kept
-- tiny because the set is almost always empty.
CREATE INDEX IF NOT EXISTS idx_job_executions_running
    ON job_executions (job_name)
    WHERE status = 'running';

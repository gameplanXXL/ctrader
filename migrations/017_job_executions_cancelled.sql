-- 017_job_executions_cancelled.sql
--
-- Epic 11 Tranche A / Code-review BH-7 / EC-12 follow-up.
--
-- Adds `cancelled` to the job_executions.status vocabulary so a
-- clean shutdown signal (`asyncio.CancelledError` inside the
-- `logged_job` wrapper) can mark the row as distinct from an
-- actual failure. Previously `CancelledError` was written with
-- `status='failure'`, poisoning the Health-Widget with a red
-- "✗ failure" pill after every normal container restart.
--
-- `DROP CONSTRAINT ... IF EXISTS` + `ADD CONSTRAINT` is a
-- one-statement swap. The new constraint uses `NOT VALID +
-- VALIDATE` so application stays cheap on any populated table
-- (mirror Migration 009's convention).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'job_executions_status_check'
    ) THEN
        ALTER TABLE job_executions DROP CONSTRAINT job_executions_status_check;
    END IF;

    ALTER TABLE job_executions
        ADD CONSTRAINT job_executions_status_check
        CHECK (status IN ('running', 'success', 'failure', 'cancelled'))
        NOT VALID;
    ALTER TABLE job_executions VALIDATE CONSTRAINT job_executions_status_check;
END$$;

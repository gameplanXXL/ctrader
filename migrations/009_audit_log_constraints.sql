-- 009_audit_log_constraints.sql
--
-- Code-review H8 / EC-3 / EC-4: defensive CHECK constraints on
-- audit_log columns that were left unconstrained in Migration 008.
--
-- - `event_type` is now restricted to a closed vocabulary so a typo
--   like "propposal_approved" can never persist and silently disappear
--   from the future settings-page log viewer (Story 12.2).
-- - `risk_budget` matches the `proposals.risk_budget >= 0` invariant.
--
-- Both constraints use `NOT VALID` + `VALIDATE` semantics so the
-- migration is fast even on a populated audit_log: NOT VALID adds the
-- constraint without scanning existing rows, then VALIDATE scans them
-- without holding an exclusive lock. On an empty table this is a
-- no-op cost.

DO $$
BEGIN
    -- event_type: closed vocabulary. Add new event types here AND in
    -- Python (`app/services/audit.py` callers). Kept in sync via the
    -- code-review process.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'audit_log_event_type_check'
    ) THEN
        ALTER TABLE audit_log
            ADD CONSTRAINT audit_log_event_type_check
            CHECK (event_type IN (
                'proposal_approved',
                'proposal_rejected',
                'proposal_revision',
                'kill_switch_triggered',
                'kill_switch_overridden'
            )) NOT VALID;
        ALTER TABLE audit_log VALIDATE CONSTRAINT audit_log_event_type_check;
    END IF;

    -- risk_budget: non-negative parity with proposals.risk_budget.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'audit_log_risk_budget_check'
    ) THEN
        ALTER TABLE audit_log
            ADD CONSTRAINT audit_log_risk_budget_check
            CHECK (risk_budget IS NULL OR risk_budget >= 0) NOT VALID;
        ALTER TABLE audit_log VALIDATE CONSTRAINT audit_log_risk_budget_check;
    END IF;
END$$;

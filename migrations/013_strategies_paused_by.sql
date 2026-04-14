-- 013_strategies_paused_by.sql
--
-- Epic 9 / Story 9.2 — horizon-bewusster Kill-Switch needs to track
-- WHO paused a strategy so a recovery sweep only un-pauses its own
-- automated pauses and leaves manual pauses intact.
--
-- `paused_by` is NULL for active strategies, 'manual' when Chef
-- paused from the strategy-detail page, and 'kill_switch' when the
-- automated regime-snapshot → kill-switch pipeline set `status`
-- to 'paused'. The check constraint is a closed vocabulary so typos
-- (e.g. 'kill-switch' with a hyphen) don't silently disappear.

ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paused_by TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'strategies_paused_by_check'
    ) THEN
        ALTER TABLE strategies
            ADD CONSTRAINT strategies_paused_by_check
            CHECK (paused_by IS NULL OR paused_by IN ('manual', 'kill_switch'));
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_strategies_paused_by
    ON strategies (paused_by)
    WHERE paused_by IS NOT NULL;

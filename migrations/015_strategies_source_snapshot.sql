-- 015_strategies_source_snapshot.sql
--
-- Epic 10 / Story 10.3 — linkage column so a strategy Chef creates
-- from a Gordon HOT-pick carries the snapshot id it was born from.
-- The column is a nullable INT with an FK to gordon_snapshots(id)
-- so the strategy-detail page can later render "Erstellt aus Gordon
-- Wochen-Radar vom <date>".
--
-- No CHECK needed — NULL means "not Gordon-derived" and any valid
-- snapshot id is fine. ON DELETE SET NULL keeps strategies alive
-- if their source snapshot ever gets pruned.

ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS source_snapshot_id INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'strategies_source_snapshot_fk'
    ) THEN
        ALTER TABLE strategies
            ADD CONSTRAINT strategies_source_snapshot_fk
            FOREIGN KEY (source_snapshot_id)
            REFERENCES gordon_snapshots(id)
            ON DELETE SET NULL;
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_strategies_source_snapshot_id
    ON strategies (source_snapshot_id)
    WHERE source_snapshot_id IS NOT NULL;

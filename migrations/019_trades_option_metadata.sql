-- 019_trades_option_metadata.sql
--
-- Epic 12 / Story 12.3 — Option metadata on the trades table so
-- the Journal drilldown can render "Strike | Expiry | Right |
-- Days-to-Expiry | ITM/ATM/OTM" for every option position, and so
-- the `near_assignment_check` scheduled job can query directly
-- (no JSONB probe).
--
-- All four columns are NULL for non-option trades (stocks, crypto,
-- CFD). The partial index on `option_expiry` covers the
-- near-assignment query "open option positions with expiry < now +
-- 3 days" without scanning the full trades table.

ALTER TABLE trades
    ADD COLUMN IF NOT EXISTS option_expiry     DATE,
    ADD COLUMN IF NOT EXISTS option_strike     NUMERIC,
    ADD COLUMN IF NOT EXISTS option_right      CHAR(1),
    ADD COLUMN IF NOT EXISTS option_multiplier INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'trades_option_right_check'
    ) THEN
        ALTER TABLE trades
            ADD CONSTRAINT trades_option_right_check
            CHECK (option_right IS NULL OR option_right IN ('C', 'P'));
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_trades_option_expiry
    ON trades (option_expiry, closed_at)
    WHERE option_expiry IS NOT NULL AND closed_at IS NULL;

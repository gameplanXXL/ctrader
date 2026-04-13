-- 002_trades_table.sql
--
-- Story 2.1: trades table — the core domain table.
--
-- Schema covers IB stocks/options + cTrader crypto/CFD trades. Every
-- broker-imported trade has a unique (broker, perm_id) pair which is
-- the dedup key. The `trigger_spec` JSONB column is the trigger-
-- provenance store (FR16) and gets a GIN index for facet queries
-- (Epic 4).
--
-- IMPORTANT — what is intentionally NOT here yet:
--   - strategy_id (FK to strategies)        → added by Story 6.1 ALTER
--   - agent_id (Multi-Agent concession)     → added by Story 8.1 ALTER
--   - mae / mfe (MAE/MFE columns)            → added by Story 4.3 ALTER
--   - order_status / order_ref / etc.        → added by Story 11.2 ALTER
--                                              (Migration 005, IB Quick-Order)
--
-- Dependency: 001_initial_schema.sql (the trade_source / trade_side enums).

CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL          PRIMARY KEY,
    symbol          TEXT            NOT NULL,
    asset_class     TEXT            NOT NULL CHECK (asset_class IN ('stock', 'option', 'crypto', 'cfd')),
    side            trade_side      NOT NULL,
    quantity        NUMERIC         NOT NULL CHECK (quantity > 0),
    entry_price     NUMERIC         NOT NULL CHECK (entry_price >= 0),
    exit_price      NUMERIC         CHECK (exit_price IS NULL OR exit_price >= 0),
    opened_at       TIMESTAMPTZ     NOT NULL,
    closed_at       TIMESTAMPTZ     CHECK (closed_at IS NULL OR closed_at >= opened_at),
    pnl             NUMERIC,
    fees            NUMERIC         NOT NULL DEFAULT 0,
    broker          trade_source    NOT NULL,
    perm_id         TEXT            NOT NULL,
    trigger_spec    JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    -- Dedup key for the entire IB Flex / Live-Sync / cTrader import
    -- pipeline. NFR-R1: re-importing the same XML must not change the
    -- row count.
    UNIQUE (broker, perm_id)
);

-- Hot indexes for journal + drilldown queries (Story 2.3, 2.4).
CREATE INDEX IF NOT EXISTS idx_trades_symbol     ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at  ON trades (opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_broker     ON trades (broker);

-- GIN index on trigger_spec — enables fast facet queries in Epic 4.
-- Specifically the Chef-moment query "all losing trades where I
-- overrode a Viktor red flag" runs against this index.
CREATE INDEX IF NOT EXISTS idx_trades_trigger_spec ON trades USING GIN (trigger_spec);

-- Untagged-counter helper (Story 2.3 FR11): completed manual IB trades
-- without trigger_spec yet. Partial index keeps the index small.
CREATE INDEX IF NOT EXISTS idx_trades_untagged
    ON trades (broker, closed_at)
    WHERE trigger_spec IS NULL;

-- 007_strategies_and_notes.sql
--
-- Epic 6 — Strategy Management
--
-- 1. `strategies` — the canonical strategy registry. Chef defines each
--    strategy once with asset class, horizon, trigger sources, risk
--    budget, and a lifecycle status (active/paused/retired).
-- 2. `trades.strategy_id` ALTER — ties every trade back to a strategy
--    so the Epic 4 facet framework can filter by strategy_id and the
--    Story 6.2 list can aggregate per-strategy metrics.
-- 3. `strategy_notes` — append-only note history per strategy
--    (Story 6.4 / FR37).
-- 4. Cross-reference indexes so the Story 6.2 JOIN stays fast.
--
-- The `horizon_type` and `strategy_status` enums already exist from
-- Migration 001, so this script only adds the tables + columns + indexes.

CREATE TABLE IF NOT EXISTS strategies (
    id                      SERIAL          PRIMARY KEY,
    name                    TEXT            NOT NULL UNIQUE,
    asset_class             TEXT            NOT NULL CHECK (asset_class IN ('stock', 'option', 'crypto', 'cfd')),
    horizon                 horizon_type    NOT NULL,
    typical_holding_period  TEXT,
    trigger_sources         JSONB           NOT NULL DEFAULT '[]'::jsonb,
    risk_budget_per_trade   NUMERIC         NOT NULL CHECK (risk_budget_per_trade >= 0),
    status                  strategy_status NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategies_status   ON strategies (status);
CREATE INDEX IF NOT EXISTS idx_strategies_horizon  ON strategies (horizon);

-- Issue M1 fix from the implementation-readiness review: trades need
-- the FK to strategies so aggregation queries can JOIN without a
-- second table / JSONB lookup. ON DELETE SET NULL so retiring a
-- strategy doesn't orphan or delete historical trades.
ALTER TABLE trades
    ADD COLUMN IF NOT EXISTS strategy_id INT REFERENCES strategies(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades (strategy_id);

-- Story 6.4: append-only note history. No UPDATE, no DELETE — each
-- entry is a point-in-time snapshot of Chef's thinking. Retention is
-- unbounded.
CREATE TABLE IF NOT EXISTS strategy_notes (
    id           SERIAL       PRIMARY KEY,
    strategy_id  INT          NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    content      TEXT         NOT NULL CHECK (length(content) > 0),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_notes_strategy_id
    ON strategy_notes (strategy_id, created_at DESC);

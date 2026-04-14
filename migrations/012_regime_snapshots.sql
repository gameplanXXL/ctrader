-- 012_regime_snapshots.sql
--
-- Epic 9 / Story 9.1 — daily regime snapshots.
--
-- Captures the market environment (Fear & Greed index, VIX level, and
-- per-broker realized P&L over the trailing 30 days) once per day so
-- the journal has a historical regime context for every trade and the
-- horizon-bewusster Kill-Switch (Story 9.2) has a time-series to react
-- against.
--
-- `fear_greed_index` and `vix` are nullable so the Story-9.1 AC #3
-- "bei Datenquellen-Ausfall kein Silent Failure" path can still persist
-- a snapshot row (with NULL fields + a logged warning) instead of
-- dropping the whole day on the floor.
--
-- `per_broker_pnl` is JSONB so the shape can grow (e.g. adding
-- unrealized-P&L or by-agent breakdown) without schema churn.

CREATE TABLE IF NOT EXISTS regime_snapshots (
    id                  SERIAL          PRIMARY KEY,
    fear_greed_index    INT             CHECK (fear_greed_index IS NULL OR (fear_greed_index BETWEEN 0 AND 100)),
    vix                 NUMERIC(6, 2)   CHECK (vix IS NULL OR vix >= 0),
    per_broker_pnl      JSONB           NOT NULL DEFAULT '{}'::jsonb,
    fetch_errors        JSONB,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regime_snapshots_created_at
    ON regime_snapshots (created_at DESC);

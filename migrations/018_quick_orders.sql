-- 018_quick_orders.sql
--
-- Epic 12 / Story 12.2 — IB Swing-Order tracking table.
--
-- Every bracket order submitted via `POST /trades/quick-order/submit`
-- gets one row here BEFORE the network call. The `order_ref` column
-- is the ctrader-generated idempotency key (NFR-R3a); a UNIQUE
-- constraint backs the invariant "retry cannot create a duplicate
-- order" at the database level even if the service layer misses a
-- guard.
--
-- Asset-class union: `asset_class IN ('stock', 'option')`. Stock rows
-- populate `symbol`; option rows populate the `option_*` columns.
-- This mirrors the `trades` schema (Migration 002 + the new
-- `option_*` columns added below for Story 12.3 near-assignment).
--
-- `status` reuses the `order_status` enum from Migration 001
-- (submitted/filled/partial/rejected/cancelled) so the Journal's
-- `status_badge` macro works unchanged.

CREATE TABLE IF NOT EXISTS quick_orders (
    id                  SERIAL          PRIMARY KEY,
    order_ref           TEXT            NOT NULL UNIQUE,
    asset_class         TEXT            NOT NULL CHECK (asset_class IN ('stock', 'option')),
    symbol              TEXT            NOT NULL,
    side                trade_side      NOT NULL,
    quantity            NUMERIC         NOT NULL CHECK (quantity > 0),
    limit_price         NUMERIC         NOT NULL CHECK (limit_price > 0),
    stop_price          NUMERIC         NOT NULL CHECK (stop_price > 0),
    -- Option-specific columns (NULL for stocks)
    option_expiry       DATE,
    option_strike       NUMERIC,
    option_right        CHAR(1)         CHECK (option_right IS NULL OR option_right IN ('C', 'P')),
    option_multiplier   INT             DEFAULT 100,
    -- Execution tracking
    ib_order_id         TEXT,
    status              order_status    NOT NULL DEFAULT 'submitted',
    -- Trigger provenance (pre-filled into trigger_spec on fill)
    strategy_id         INT             REFERENCES strategies(id),
    trigger_source      TEXT,
    horizon             TEXT,
    notes               TEXT,
    -- Margin info (Story 12.2 AC #2): snapshot from whatIfOrder()
    margin_estimate     NUMERIC,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    -- When either option_* columns are set, the full triplet must be present.
    CONSTRAINT quick_orders_option_consistency CHECK (
        (asset_class = 'stock' AND option_expiry IS NULL AND option_strike IS NULL AND option_right IS NULL)
        OR
        (asset_class = 'option' AND option_expiry IS NOT NULL AND option_strike IS NOT NULL AND option_right IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_quick_orders_created_at
    ON quick_orders (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quick_orders_status
    ON quick_orders (status)
    WHERE status IN ('submitted', 'partial');

-- Auto-updated_at trigger so every UPDATE bumps the timestamp.
CREATE OR REPLACE FUNCTION quick_orders_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS quick_orders_updated_at ON quick_orders;
CREATE TRIGGER quick_orders_updated_at
    BEFORE UPDATE ON quick_orders
    FOR EACH ROW EXECUTE FUNCTION quick_orders_touch_updated_at();

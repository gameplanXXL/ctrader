-- 001_initial_schema.sql
--
-- Story 1.2: Migrations-Framework & base enums.
--
-- Creates the schema_migrations tracking table plus all shared ENUM types
-- that downstream domain migrations (trades, strategies, proposals, etc.)
-- will reference. No domain tables live here — those are added by later
-- stories in their respective epics.
--
-- Idempotent: safe to apply multiple times. Every CREATE uses either
-- IF NOT EXISTS or the DO $$ ... EXCEPTION pattern for ENUM types.

-- ---------------------------------------------------------------------------
-- Tracking table: which migrations have been applied
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT        PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- ENUMs — shared types used across the domain
-- ---------------------------------------------------------------------------

-- trade_source: which broker a trade came from
DO $$ BEGIN
    CREATE TYPE trade_source AS ENUM ('ib', 'ctrader');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- trade_side: direction / action of a trade
DO $$ BEGIN
    CREATE TYPE trade_side AS ENUM ('buy', 'sell', 'short', 'cover');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- order_status: lifecycle state of an IB or cTrader order
-- 'synced' is the pseudo-state for trades that arrived via Flex/Live-Sync
-- without going through Quick-Order (so order_status is NEVER null).
DO $$ BEGIN
    CREATE TYPE order_status AS ENUM (
        'synced',
        'submitted',
        'filled',
        'partial',
        'rejected',
        'cancelled'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- horizon_type: trading horizon classification
DO $$ BEGIN
    CREATE TYPE horizon_type AS ENUM ('intraday', 'swing', 'position');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- strategy_status: lifecycle state of a strategy
DO $$ BEGIN
    CREATE TYPE strategy_status AS ENUM ('active', 'paused', 'retired');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- risk_gate_result: 3-stage risk verdict from Rita / Cassandra
DO $$ BEGIN
    CREATE TYPE risk_gate_result AS ENUM ('green', 'yellow', 'red');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

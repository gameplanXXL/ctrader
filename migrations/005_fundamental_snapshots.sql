-- 005_fundamental_snapshots.sql
--
-- Story 5.2: per-trade snapshots of the fundamental assessment at
-- trade-time. Lets the drilldown show "damals" vs "jetzt" side-by-
-- side so Chef can see whether the market thesis has changed since
-- entry.
--
-- Populated by the live-sync hook (Story 2.2 → Story 5.2) on every
-- new trade and by Epic 7/8 on bot-order placement. Historical
-- Flex-import trades do NOT get snapshots — `trigger_spec` is the
-- authoritative trigger record for those.

CREATE TABLE IF NOT EXISTS fundamental_snapshots (
    id               SERIAL          PRIMARY KEY,
    trade_id         INT             NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    asset_class      TEXT            NOT NULL,
    agent_id         TEXT            NOT NULL,
    snapshot_data    JSONB           NOT NULL,
    snapshot_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fundamental_snapshots_trade_id
    ON fundamental_snapshots (trade_id);

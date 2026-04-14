-- 014_gordon_snapshots.sql
--
-- Epic 10 / Story 10.1 — weekly Gordon trend-radar snapshots.
--
-- Captures the full MCP response from `fundamental`'s Gordon agent
-- (`/home/cneise/Project/fundamental`, tool=`trend_radar`,
-- agent=`gordon`) plus the extracted HOT-picks list so the Trends
-- page (Story 10.2) can render the diff between this week and last
-- week without re-parsing the raw snapshot blob.
--
-- `hot_picks` is JSONB-array of objects shaped like:
--   [{"symbol": "NVDA", "rank": 1, "horizon": "swing",
--     "confidence": 0.85, "thesis": "...", "entry_zone": [890, 920],
--     "target": 1050}, ...]
--
-- `snapshot_data` stores the full JSON-RPC `result` payload so
-- future analyses (cohort-lens, counterfactual replay) can re-parse
-- what the agent actually returned.
--
-- `source_error` lets the Story-9.1-style "never drop a day" pattern
-- persist a partial row when the MCP call failed (e.g. snapshot_data
-- = {}, hot_picks = [], source_error = "connection_refused"). This
-- keeps the weekly heartbeat durable even when MCP is down.

CREATE TABLE IF NOT EXISTS gordon_snapshots (
    id              SERIAL          PRIMARY KEY,
    snapshot_data   JSONB           NOT NULL DEFAULT '{}'::jsonb,
    hot_picks       JSONB           NOT NULL DEFAULT '[]'::jsonb,
    source_error    TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gordon_snapshots_created_at
    ON gordon_snapshots (created_at DESC);

-- GIN index on hot_picks so Story 10.3's "find strategy source"
-- look-up can filter by symbol without a sequential scan.
CREATE INDEX IF NOT EXISTS idx_gordon_snapshots_hot_picks
    ON gordon_snapshots USING GIN (hot_picks);

-- 006_mcp_contract_tests.sql
--
-- Story 5.4: results log for the daily MCP-contract-drift check.
-- The scheduler (Story 12.1) runs `run_contract_test()` once per
-- day at 05:00 UTC, diffs the current `tools/list` response against
-- the frozen week-0 snapshot, and appends one row here.
--
-- Statuses:
--   - pass:  tool set identical (or only additive non-breaking changes)
--   - fail:  removed / changed tools detected → drift banner shows
--   - error: MCP unreachable or unparseable response → retry next run

CREATE TABLE IF NOT EXISTS mcp_contract_tests (
    id                 SERIAL          PRIMARY KEY,
    run_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status             TEXT            NOT NULL CHECK (status IN ('pass', 'fail', 'error')),
    drift_details      JSONB,
    snapshot_version   TEXT            NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_contract_tests_run_at
    ON mcp_contract_tests (run_at DESC);

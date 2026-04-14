-- 010_trades_agent_id.sql
--
-- Story 8.1 Task 1 / Issue M1 of the Readiness Review:
-- adds the `agent_id` column to `trades` — the one Multi-Agent
-- concession kept in the MVP schema (CLAUDE.md: "Die einzige
-- Multi-Agent-Konzession im MVP ist die `agent_id`-Spalte").
--
-- Bot-execution (Story 8.1-8.2) writes the `agent_id` of the originating
-- Proposal onto every filled trade, so the journal can filter and
-- aggregate by agent ("show me all Satoshi wins", etc.) without a JOIN
-- back to the proposals table. Manual IB trades stay NULL.

ALTER TABLE trades ADD COLUMN IF NOT EXISTS agent_id TEXT;

CREATE INDEX IF NOT EXISTS idx_trades_agent_id ON trades (agent_id) WHERE agent_id IS NOT NULL;

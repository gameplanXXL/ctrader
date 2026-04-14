-- 008_proposals_and_audit_log.sql
--
-- Epic 7 — Approval Pipeline + Risk Gate
--
-- 1. `proposals` — Bot-recommended trades waiting for Chef's review.
--    Every proposal carries the agent identity, target strategy,
--    full trade parameters, the trigger spec from the agent, and the
--    risk-gate verdict (filled by Rita/Cassandra via MCP).
-- 2. `audit_log` — append-only decision history. Story 7.5 adds the
--    `BEFORE UPDATE OR DELETE` trigger that enforces immutability;
--    this migration only creates the table so the proposal endpoints
--    can write to it. The trigger ships in the same migration to
--    keep the append-only invariant atomic with the table creation.

-- ---------------------------------------------------------------------
-- proposals
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS proposals (
    id                  SERIAL              PRIMARY KEY,
    agent_id            TEXT                NOT NULL,
    strategy_id         INT                 REFERENCES strategies(id) ON DELETE SET NULL,
    symbol              TEXT                NOT NULL,
    asset_class         TEXT                NOT NULL CHECK (asset_class IN ('stock', 'option', 'crypto', 'cfd')),
    side                trade_side          NOT NULL,
    horizon             horizon_type        NOT NULL,
    entry_price         NUMERIC             NOT NULL CHECK (entry_price >= 0),
    stop_price          NUMERIC             CHECK (stop_price IS NULL OR stop_price >= 0),
    target_price        NUMERIC             CHECK (target_price IS NULL OR target_price >= 0),
    position_size       NUMERIC             NOT NULL CHECK (position_size > 0),
    risk_budget         NUMERIC             NOT NULL CHECK (risk_budget >= 0),
    trigger_spec        JSONB               NOT NULL DEFAULT '{}'::jsonb,
    risk_gate_result    risk_gate_result,
    risk_gate_response  JSONB,
    status              TEXT                NOT NULL DEFAULT 'pending'
                                            CHECK (status IN ('pending', 'approved', 'rejected', 'revision')),
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    decided_at          TIMESTAMPTZ,
    decided_by          TEXT,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_proposals_status_created
    ON proposals (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_strategy
    ON proposals (strategy_id);
CREATE INDEX IF NOT EXISTS idx_proposals_agent
    ON proposals (agent_id);

-- ---------------------------------------------------------------------
-- audit_log (append-only)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    id                    SERIAL          PRIMARY KEY,
    event_type            TEXT            NOT NULL,
    proposal_id           INT             REFERENCES proposals(id),
    strategy_id           INT             REFERENCES strategies(id),
    risk_budget           NUMERIC,
    risk_gate_snapshot    JSONB,
    fundamental_snapshot  JSONB,
    override_flags        JSONB,
    strategy_version      JSONB,
    actor                 TEXT            NOT NULL DEFAULT 'chef',
    created_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    notes                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_created
    ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_proposal
    ON audit_log (proposal_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type
    ON audit_log (event_type);

-- Story 7.5 / NFR-S3: hard-block UPDATE / DELETE on audit_log via a
-- BEFORE trigger that raises an exception. Append-only is a real
-- regulatory requirement, not a convention — DB-enforced, not
-- application-enforced.
CREATE OR REPLACE FUNCTION audit_log_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit log is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;
CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();

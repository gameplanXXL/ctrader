-- 011_proposals_execution_fields.sql
--
-- Story 8.1 / 8.2: bot-execution lifecycle columns on `proposals`.
--
-- `client_order_id` is the Idempotenz-Key passed to cTrader (NFR-R3a):
-- a retry after network failure with the same id cannot create a
-- duplicate order. UNIQUE so two concurrent execute-calls for the same
-- proposal can't race their way to two orders either.
--
-- `execution_status` mirrors the cTrader order lifecycle (submitted /
-- filled / partial / rejected / cancelled) — reuses the existing
-- `order_status` enum from Migration 001 so the journal's
-- `status_badge` macro works unchanged.
--
-- `execution_updated_at` + `execution_details` land the raw cTrader
-- event JSON so Story 12.2's audit-log viewer has something to show
-- when a fill-event is in flight.

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS client_order_id      TEXT,
    ADD COLUMN IF NOT EXISTS execution_status     order_status,
    ADD COLUMN IF NOT EXISTS execution_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS execution_details    JSONB;

-- UNIQUE constraint as a separate statement so the ADD COLUMN above
-- stays idempotent (IF NOT EXISTS doesn't apply to UNIQUE inline).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'proposals_client_order_id_key'
    ) THEN
        ALTER TABLE proposals
            ADD CONSTRAINT proposals_client_order_id_key UNIQUE (client_order_id);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_proposals_client_order_id
    ON proposals (client_order_id)
    WHERE client_order_id IS NOT NULL;

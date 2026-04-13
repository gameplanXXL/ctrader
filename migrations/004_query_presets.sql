-- 004_query_presets.sql
--
-- Story 4.7: saved query presets.
--
-- A preset is a named snapshot of facet selections that Chef can
-- recall from the command palette (Story 4.6) or the journal's
-- "Save query" star button. `filters` is JSONB so the shape can
-- evolve with the facet catalogue without schema changes.

CREATE TABLE IF NOT EXISTS query_presets (
    id          SERIAL       PRIMARY KEY,
    name        TEXT         NOT NULL UNIQUE,
    filters     JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_presets_name ON query_presets (name);

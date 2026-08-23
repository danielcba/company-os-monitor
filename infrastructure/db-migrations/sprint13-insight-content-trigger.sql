-- Sprint 13 - Insight content immutability trigger (migration for existing DBs).
--
-- The `insights` table already exists from the base schema (docs/01) with its
-- content columns (context_id, hypothesis_ids, description,
-- prior_understanding, mental_model_update, generated_at) and the
-- `recommendations.insight_id` FK (SET NULL). This migration adds the trigger
-- that enforces P1 at the data layer:
--   - ALL columns are immutable: an Insight has no lifecycle field (unlike
--     Hypotheses, there is no `status` column) - the row is a pure
--     transformation journal, so NO UPDATE is ever allowed;
--   - DELETE is blocked: a transformation is a persistent audit trail and is
--     never removed.
--
-- A NEW restructuring over the same context with a different hypothesis set is
-- a NEW deterministic row (idempotent dedup by primary key), never an UPDATE
-- of an existing one - this trigger makes that non-negotiable.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint13-insight-content-trigger.sql

DROP TRIGGER IF EXISTS insight_content_immutable_trigger ON insights;

CREATE OR REPLACE FUNCTION prevent_insight_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- An Insight is a journaled transformation: every column is content.
        RAISE EXCEPTION 'Insights content is immutable (P1). No UPDATE allowed.';
    END IF;
    -- DELETE blocked (persistent audit trail).
    RAISE EXCEPTION 'Insights are immutable (P1). No DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER insight_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON insights
    FOR EACH ROW EXECUTE FUNCTION prevent_insight_content_update();